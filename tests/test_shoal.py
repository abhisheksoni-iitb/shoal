"""Run: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m unittest discover -s tests -v"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from http.server import ThreadingHTTPServer
import threading
import urllib.request

from shoal import analyze, edges, model, pipeline, server
from shoal.sim import simulate

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "one-tap-reorder" / "feature.json"


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.m = model.load(EX)

    def test_template_and_example_are_valid(self):
        for p in (EX, ROOT / "shoal" / "template.json"):
            findings = model.lint(model.load(p))
            self.assertFalse([f for f in findings if f["level"] == "error"], p)

    def test_lint_finds_design_gaps(self):
        codes = {f["code"] for f in model.lint(self.m)}
        self.assertIn("blocked-without-fallback", codes)
        self.assertIn("error-without-recovery", codes)
        self.assertIn("not-instrumented", codes)

    def test_lint_catches_broken_references_and_dead_ends(self):
        raw = json.loads(EX.read_text())
        raw["steps"][1]["next"] = ["nowhere"]
        self.assertTrue(any(f["code"] == "bad-ref" for f in model.lint(model.normalise(raw))))
        raw = json.loads(EX.read_text())
        raw["steps"][3]["next"] = []
        codes = {f["code"] for f in model.lint(model.normalise(raw))}
        self.assertIn("dead-end", codes)
        self.assertIn("unreachable", codes)

    def test_variant_patch(self):
        v = model.apply_variant(self.m, self.m["variants"][1])
        self.assertIn("add_card", model.step_index(v))
        self.assertEqual(model.step_index(v)["confirm_pay"]["fallback"], "add_card")
        self.assertEqual(model.step_index(self.m)["confirm_pay"]["fallback"], None)

    def test_variant_feature_patch(self):
        v = model.apply_variant(self.m, {"id": "fast-budget", "patch": {"feature": {"session_budget_s": 420, "handles": ["back_button"]}}})
        self.assertEqual(v["feature"]["session_budget_s"], 420)
        self.assertEqual(v["feature"]["handles"], ["back_button"])


class SimTests(unittest.TestCase):
    def setUp(self):
        self.m = model.load(EX)

    def test_same_seed_same_result(self):
        a = simulate(self.m, users=800, seed=3, keep_sessions=0)
        b = simulate(self.m, users=800, seed=3, keep_sessions=0)
        self.assertEqual(a["outcomes"], b["outcomes"])
        self.assertNotEqual(a["outcomes"], simulate(self.m, users=800, seed=4, keep_sessions=0)["outcomes"])

    def test_every_user_is_accounted_for(self):
        r = simulate(self.m, users=3000, seed=5, keep_sessions=0)
        self.assertEqual(sum(r["outcomes"].values()), 3000)
        for sid, st in r["steps"].items():
            if sid in self.m["success"]:
                continue
            self.assertEqual(st["entered"], st["continued"] + st["abandoned"] + st["blocked"] + st["error_exit"], sid)
        self.assertEqual(r["outcomes"]["stuck"], 0)

    def test_easier_step_and_fallback_help(self):
        base = analyze.metrics(simulate(self.m, users=6000, seed=9, keep_sessions=0))
        easy = copy.deepcopy(self.m)
        for s in easy["steps"]:
            s["effort"], s["clarity"] = 0.0, 1.0
        self.assertGreater(analyze.metrics(simulate(easy, users=6000, seed=9, keep_sessions=0))["completion_rate"], base["completion_rate"])
        v = model.apply_variant(self.m, self.m["variants"][1])
        self.assertGreater(analyze.metrics(simulate(v, users=6000, seed=9, keep_sessions=0))["adoption_rate"], base["adoption_rate"])

    def test_funnel_main_reason_counts_blocked_users(self):
        m = copy.deepcopy(self.m)
        for g in m["segments"]:
            g["capabilities"]["saved_card"] = 0.0
        rows = analyze.funnel(m, simulate(m, users=3000, seed=4, keep_sessions=0))
        row = next(r for r in rows if r["step"] == "confirm_pay")
        self.assertGreater(row["blocked"], row["abandoned"])
        self.assertEqual(row["top_reason"], "blocked")

    def test_offline_users_cannot_place_an_order(self):
        r = simulate(self.m, users=6000, seed=2, keep_sessions=0)
        off = r["contexts"]["network"]["offline"]
        self.assertGreater(off["entered"], 0)
        self.assertLess(off["success"] / off["entered"], 0.05)

    def test_calibration_reproduces_observed_rate(self):
        obs = {"review_items": {"entered": 1000, "continued": 620, "rate": 0.62}}
        mm, applied, unknown = analyze.calibrate(self.m, obs)
        self.assertEqual((applied, unknown), (["review_items"], []))
        st = simulate(mm, users=20000, seed=1, keep_sessions=0)["steps"]["review_items"]
        self.assertAlmostEqual(st["continued"] / st["entered"], 0.62, delta=0.05)


class EdgeTests(unittest.TestCase):
    def test_pairwise_covers_every_pair(self):
        dims = {"a": [1, 2, 3], "b": ["x", "y"], "c": ["p", "q", "r", "s"]}
        rows = edges.pairwise(dims)
        for da, db in (("a", "b"), ("a", "c"), ("b", "c")):
            for va in dims[da]:
                for vb in dims[db]:
                    self.assertTrue(any(r[da] == va and r[db] == vb for r in rows))
        self.assertLess(len(rows), 3 * 2 * 4)

    def test_handles_and_review_change_status(self):
        m = model.load(EX)
        cases = edges.edge_cases(m)
        by = {c["id"]: c for c in cases}
        self.assertEqual(by["E-confirmed-no_confirmation"]["status"], "handled")
        self.assertEqual(by["E-place_order-double_submit"]["status"], "open")
        merged = edges.merge_review(cases, [{"id": "E-place_order-double_submit", "verdict": "gap"}, {"id": "X-new", "title": "New", "verdict": "gap"}])
        by = {c["id"]: c for c in merged}
        self.assertEqual(by["E-place_order-double_submit"]["status"], "gap")
        self.assertIn("X-new", by)


class PipelineTests(unittest.TestCase):
    def test_run_writes_all_files_and_scores(self):
        m = model.load(EX)
        with tempfile.TemporaryDirectory() as d:
            s = pipeline.run(m, d, users=1200, seed=7, reps=6, quick=True)
            for f in ("report.html", "report.md", "summary.json", "edge_cases.json", "events.sample.jsonl", "model.json", "lint.json"):
                self.assertTrue((Path(d) / f).stat().st_size > 0, f)
            self.assertEqual(len(s["hypotheses"]), 4)
            self.assertEqual(len(s["variants"]), 2)
            again = pipeline.rerun(d)
            self.assertEqual(again["metrics"], s["metrics"])
            self.assertTrue(again["args"]["quick"])
            sc = analyze.score(json.loads((Path(d) / "summary.json").read_text()), analyze.read_observed(ROOT / "examples" / "one-tap-reorder" / "observed.sample.csv"))
            self.assertEqual(sc["steps_compared"], 6)
            self.assertTrue(0 <= sc["fidelity"] <= 1)

    def test_server_index_new_and_compare(self):
        server.Handler.root = ROOT / "examples"
        srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            with urllib.request.urlopen(f"{base}/") as resp:
                html = resp.read().decode("utf-8")
                self.assertEqual(resp.status, 200)
                self.assertIn("One-tap reorder", html)
            with urllib.request.urlopen(f"{base}/new") as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("Feature model (JSON)", resp.read().decode("utf-8"))
        finally:
            srv.shutdown()
            srv.server_close()

    def test_broken_model_is_refused(self):
        raw = json.loads(EX.read_text())
        raw["success"] = ["missing"]
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(pipeline.LintFailed):
                pipeline.run(model.normalise(raw), d, quick=True)


if __name__ == "__main__":
    unittest.main()
