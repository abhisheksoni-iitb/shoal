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


def two_endings():
    """A small flow that can end well in two ways, with one guessed input worth varying."""
    return model.normalise({
        "feature": {"id": "two-endings", "name": "Two endings", "volume": {"eligible": 1000, "per": "week", "unit": "searches"}},
        "segments": [
            {"id": "keen", "share": 0.5, "traits": {"motivation": 0.8, "skill": 0.7}, "capabilities": {"account": 0.9}},
            {"id": "casual", "share": 0.5, "traits": {"motivation": 0.35, "skill": 0.4}, "capabilities": {"account": 0.4}},
        ],
        "entry_points": [{"id": "box", "to": "ask", "discovery": 0.8}],
        "steps": [
            {"id": "ask", "type": "input", "effort": 0.2, "clarity": 0.8, "value": 0.5,
             "next": [{"to": "look", "weight": 0.7}, {"to": "act", "weight": 0.3}], "events": ["asked"]},
            {"id": "look", "type": "success", "events": ["looked"]},
            {"id": "act", "type": "input", "effort": 0.4, "requires": ["account"], "next": ["acted"], "events": ["act_started"]},
            {"id": "acted", "type": "success", "events": ["acted"]},
        ],
        "hypotheses": [
            {"id": "H1", "text": "At least 10% of starters act", "metric": "step_reach:acted", "op": ">=", "value": 0.10},
            {"id": "H2", "text": "Keen users carry on from ask", "metric": "step_continue:ask", "op": ">=", "value": 0.5, "segment": "keen"},
        ],
        "variants": [{"id": "third-ending", "name": "Add a third ending", "patch": {
            "steps": {"ask": {"next": [{"to": "look", "weight": 0.5}, {"to": "act", "weight": 0.3}, {"to": "saved", "weight": 0.2}]}},
            "add_steps": [{"id": "saved", "type": "success", "events": ["saved"]}]}}],
        "scenarios": [{"id": "few-accounts", "name": "Few users have an account",
                       "patch": {"segments": {"keen": {"capabilities": {"account": 0.2}}, "casual": {"capabilities": {"account": 0.1}}}}}],
    })


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.m = two_endings()

    def test_step_reach_and_segment_step_metrics(self):
        res = simulate(self.m, users=6000, seed=3, keep_sessions=0)
        started = analyze.metrics(res)["entered"]
        self.assertAlmostEqual(analyze.metric_value(res, "step_reach:look"), res["steps"]["look"]["entered"] / started)
        self.assertAlmostEqual(analyze.metric_value(res, "step_reach:ask"), 1.0)
        # per-segment counts add up to the whole, and segments differ as their traits say
        for sid in ("ask", "look", "act", "acted"):
            self.assertEqual(sum(res["segments"][g]["steps"][sid][0] for g in ("keen", "casual")), res["steps"][sid]["entered"])
            self.assertEqual(sum(res["segments"][g]["steps"][sid][1] for g in ("keen", "casual")), res["steps"][sid]["continued"])
        self.assertGreater(analyze.metric_value(res, "step_continue:ask", "keen"), analyze.metric_value(res, "step_continue:ask", "casual"))
        self.assertGreater(analyze.metric_value(res, "step_reach:acted", "keen"), analyze.metric_value(res, "step_reach:acted", "casual"))

    def test_outcome_split_adds_up(self):
        res = simulate(self.m, users=6000, seed=3, keep_sessions=0)
        rep = analyze.replicate(self.m, users=800, seed=3, reps=4)
        split = analyze.outcome_split(self.m, res, rep)
        self.assertEqual([r["step"] for r in split], ["look", "acted"])
        self.assertEqual(sum(r["users"] for r in split), res["outcomes"]["success"])
        self.assertAlmostEqual(sum(r["share_of_finishers"] for r in split), 1.0)
        for r in split:
            self.assertLessEqual(r["range"]["p5"], r["range"]["p95"])

    def test_bad_metric_and_bad_patch_are_model_errors(self):
        raw = copy.deepcopy(self.m)
        raw["hypotheses"][0]["metric"] = "step_reach:nowhere"
        self.assertTrue(any(f["code"] == "bad-hypothesis" for f in model.lint(model.normalise(raw))))
        raw = copy.deepcopy(self.m)
        raw["scenarios"][0]["patch"] = {"steps": {"nowhere": {"effort": 0.1}}}
        self.assertTrue(any(f["code"] == "bad-patch" for f in model.lint(model.normalise(raw))))
        raw = copy.deepcopy(self.m)
        raw["variants"][0]["patch"]["steps"]["ask"]["next"] = ["nowhere"]
        self.assertTrue(any(f["code"] == "bad-patch" for f in model.lint(model.normalise(raw))))
        raw = copy.deepcopy(self.m)
        raw["feature"]["volume"] = {"eligible": 0}
        with self.assertRaises(model.ModelError):
            model.normalise(raw)

    def test_variant_can_add_and_remove_ways_to_finish(self):
        v = model.apply_variant(self.m, self.m["variants"][0])
        self.assertEqual(sorted(v["success"]), ["acted", "look", "saved"])
        res = simulate(v, users=3000, seed=5, keep_sessions=0)
        self.assertEqual(sum(res["steps"][s]["entered"] for s in v["success"]), res["outcomes"]["success"])
        gone = model.apply_variant(self.m, {"id": "no-look", "patch": {"steps": {"ask": {"next": ["act"]}}, "remove_steps": ["look"]}})
        self.assertEqual(gone["success"], ["acted"])
        self.assertFalse([f for f in model.lint(gone) if f["level"] == "error"])

    def test_scenarios_volume_and_ends_reach_the_report(self):
        with tempfile.TemporaryDirectory() as d:
            s = pipeline.run(self.m, d, users=1500, seed=7, reps=6, quick=True)
            self.assertEqual(s["volume"], {"eligible": 1000.0, "per": "week", "unit": "searches"})
            sc = s["scenarios"][0]
            self.assertEqual(sc["verdict"], "lower")
            self.assertLess(sc["ends"]["acted"]["diff"]["p50"], 0)
            self.assertAlmostEqual(sc["ends"]["look"]["diff"]["p50"], 0, delta=0.03)
            var = s["variants"][0]
            self.assertGreater(var["ends"]["saved"]["value"]["p50"], 0.05)
            self.assertEqual(var["ends"]["saved"]["diff"]["p50"], var["ends"]["saved"]["value"]["p50"])
            self.assertEqual({h["id"]: h["verdict"] for h in s["hypotheses"]}["H2"], "supported")
            html = (Path(d) / "report.html").read_text()
            for text in ("How finishers end", "If the guesses are wrong", "Few users have an account", "Effect on each way of finishing", "a week"):
                self.assertIn(text, html)
            md = (Path(d) / "report.md").read_text()
            self.assertIn("## If the guesses are wrong", md)
            again = pipeline.rerun(d)
            self.assertEqual(again["scenarios"][0]["value"], sc["value"])

    def test_scenario_tied_to_a_variant_and_new_entry_point(self):
        raw = copy.deepcopy(self.m)
        raw["variants"].append({"id": "second-door", "name": "A second way in", "patch": {
            "add_entry_points": [{"id": "email", "to": "nudge", "discovery": 0.3}],
            "add_steps": [{"id": "nudge", "type": "view", "effort": 0.1, "next": ["ask"], "events": ["nudge_opened"]}],
            "segments": {"casual": {"entry": {"box": 0.5, "email": 0.5}}}}})
        raw["scenarios"].append({"id": "email-ignored", "name": "The email is ignored", "on": "second-door",
                                 "patch": {"entry_points": {"email": {"discovery": 0.02}}}})
        m = model.normalise(raw)
        self.assertFalse([f for f in model.lint(m) if f["level"] == "error"])
        self.assertEqual([s["id"] for s in model.scenarios_for(m)], ["few-accounts"])
        self.assertEqual([s["id"] for s in model.scenarios_for(m, "second-door")], ["email-ignored"])
        with tempfile.TemporaryDirectory() as d:
            s = pipeline.run(m, d, users=1500, seed=7, reps=6, quick=True, variant="second-door")
            self.assertEqual([x["id"] for x in s["scenarios"]], ["email-ignored"])
            self.assertEqual(s["scenarios"][0]["verdict"], "lower")
            self.assertGreater(s["entries"]["email"]["exposed"], 0)
            saved = model.load(Path(d) / "model.json")
            self.assertEqual(len(saved["scenarios"]), 2)  # the full model is kept, so a rerun sees every scenario
            self.assertEqual(pipeline.rerun(d)["scenarios"][0]["value"], s["scenarios"][0]["value"])
        raw["scenarios"][-1]["on"] = "no-such-variant"
        self.assertTrue(any(f["code"] == "bad-patch" for f in model.lint(model.normalise(raw))))
        raw["scenarios"][-1]["on"] = None  # untied: the patch names an entry point the base does not have
        self.assertTrue(any(f["code"] == "bad-patch" for f in model.lint(model.normalise(raw))))

    def test_going_round_a_loop_tires_users(self):
        loop = model.normalise({
            "feature": {"id": "loop"}, "segments": [{"id": "all", "traits": {"motivation": 0.6, "patience": 0.9}}],
            "steps": [{"id": "try", "type": "input", "effort": 0.3, "next": [{"to": "try_again", "weight": 0.9}, {"to": "done", "weight": 0.1}]},
                      {"id": "try_again", "type": "view", "effort": 0.3, "next": ["try"]},
                      {"id": "done", "type": "success"}]})
        res = simulate(loop, users=3000, seed=11, keep_sessions=0)
        self.assertEqual(res["outcomes"]["stuck"], 0)
        self.assertGreater(res["steps"]["try"]["reasons"].get("fatigue", 0) + res["steps"]["try_again"]["reasons"].get("fatigue", 0), 0)

    def test_long_waits_lose_people_and_say_why(self):
        def flow(seconds):
            return model.normalise({"feature": {"id": "wait"}, "segments": [{"id": "all"}],
                                    "steps": [{"id": "ask", "type": "input", "next": ["answer"]},
                                              {"id": "answer", "type": "wait", "time_s": seconds, "effort": 0.05, "next": ["done"]},
                                              {"id": "done", "type": "success"}]})
        quick = simulate(flow(3), users=4000, seed=2, keep_sessions=0)["steps"]["answer"]
        slow = simulate(flow(40), users=4000, seed=2, keep_sessions=0)["steps"]["answer"]
        self.assertGreater(quick["continued"] / quick["entered"], slow["continued"] / slow["entered"] + 0.15)
        self.assertLess(quick["reasons"].get("waiting", 0), 0.05 * quick["abandoned"])  # only the least patient, on a slow day
        self.assertEqual(max(slow["reasons"], key=slow["reasons"].get), "waiting")

    def test_background_wait_costs_nothing_and_watched_wait_is_flagged(self):
        def flow(background):
            return model.normalise({"feature": {"id": "wait"}, "segments": [{"id": "all"}],
                                    "steps": [{"id": "ask", "type": "input", "next": ["code"]},
                                              {"id": "code", "type": "external", "time_s": 40, "effort": 0.05, "background": background,
                                               "error_rate": 0.02, "on_error": {"recoverable": True}, "next": ["done"]},
                                              {"id": "done", "type": "success"}]})
        watched = simulate(flow(False), users=4000, seed=2, keep_sessions=0)["steps"]["code"]
        away = simulate(flow(True), users=4000, seed=2, keep_sessions=0)["steps"]["code"]
        self.assertGreater(away["continued"] / away["entered"], watched["continued"] / watched["entered"] + 0.15)
        self.assertNotIn("waiting", away["reasons"])
        self.assertIn("long-wait", {f["code"] for f in model.lint(flow(False))})
        self.assertNotIn("long-wait", {f["code"] for f in model.lint(flow(True))})

    def test_examples_and_template_all_lint_clean(self):
        paths = sorted((ROOT / "examples").glob("*/feature.json")) + [ROOT / "shoal" / "template.json"]
        self.assertGreaterEqual(len(paths), 5)
        for p in paths:
            self.assertFalse([f for f in model.lint(model.load(p)) if f["level"] == "error"], p)

    def test_otherwise_gives_non_actors_a_second_route(self):
        def flow(reminder):
            ask = {"id": "ask", "type": "view", "observed_continue": 0.10, "next": ["done"]}
            steps = [ask, {"id": "done", "type": "success"}]
            if reminder:
                ask["otherwise"] = "reminder"
                steps.insert(1, {"id": "reminder", "type": "view", "observed_continue": 0.05, "next": ["done"]})
            return model.normalise({"feature": {"id": "ask"}, "segments": [{"id": "all"}], "steps": steps})
        plain = simulate(flow(False), users=20000, seed=6, keep_sessions=0)
        twice = simulate(flow(True), users=20000, seed=6, keep_sessions=0)
        self.assertFalse([f for f in model.lint(flow(True)) if f["level"] == "error"])
        ask = twice["steps"]["ask"]
        self.assertEqual(ask["abandoned"], 0)
        self.assertEqual(ask["entered"], ask["continued"] + ask["diverted"])
        self.assertEqual(twice["steps"]["reminder"]["entered"], ask["diverted"])
        self.assertAlmostEqual(analyze.metrics(plain)["adoption_rate"], 0.10, delta=0.01)
        self.assertAlmostEqual(analyze.metrics(twice)["adoption_rate"], 0.10 + 0.90 * 0.05, delta=0.012)
        self.assertEqual(sum(twice["outcomes"].values()), 20000)
        row = analyze.funnel(flow(True), twice)[0]
        self.assertEqual((row["otherwise"], row["diverted"], row["lost"]), ("reminder", ask["diverted"], 0))

    def test_bigger_replications_narrow_the_range_of_a_rare_outcome(self):
        rare = model.normalise({"feature": {"id": "rare"}, "segments": [{"id": "all"}],
                                "steps": [{"id": "ask", "type": "view", "observed_continue": 0.05, "next": ["done"]}, {"id": "done", "type": "success"}]})
        with tempfile.TemporaryDirectory() as d:
            small = pipeline.run(rare, d, users=24000, seed=7, reps=24, jitter=0)["replication"]["overall"]["adoption_rate"]
            big = pipeline.run(rare, d, users=24000, seed=7, reps=24, jitter=0, rep_users=24000)
            wide, narrow = small["p95"] - small["p5"], big["replication"]["overall"]["adoption_rate"]
            self.assertLess(narrow["p95"] - narrow["p5"], wide * 0.6)   # sixteen times the users: about a quarter of the spread
            self.assertEqual(pipeline.rerun(d)["args"]["rep_users"], 24000)
            self.assertIn("5.", (Path(d) / "report.md").read_text().split("## What it says")[1].split("\n")[2])

    def test_otherwise_must_point_at_a_step_and_survives_removal(self):
        raw = {"feature": {"id": "x"}, "segments": [{"id": "all"}],
               "steps": [{"id": "ask", "next": ["done"], "otherwise": "nowhere"}, {"id": "done", "type": "success"}]}
        self.assertTrue(any(f["code"] == "bad-ref" for f in model.lint(model.normalise(raw))))
        raw["steps"] = [{"id": "ask", "next": ["done"], "otherwise": "nudge"}, {"id": "nudge", "next": ["last"]},
                        {"id": "last", "next": ["done"]}, {"id": "done", "type": "success"}]
        v = model.apply_variant(model.normalise(raw), {"id": "no-nudge", "patch": {"remove_steps": ["nudge"]}})
        self.assertEqual(model.step_index(v)["ask"]["otherwise"], "last")

    def test_measured_drop_is_not_given_an_invented_cause(self):
        m = copy.deepcopy(self.m)
        next(s for s in m["steps"] if s["id"] == "ask")["observed_continue"] = 0.5
        res = simulate(m, users=4000, seed=2, keep_sessions=0)
        self.assertEqual(set(res["steps"]["ask"]["reasons"]), {"observed"})
        self.assertEqual(analyze.funnel(m, res)[0]["top_reason"], "observed")

    def test_measured_rate_per_segment(self):
        m = copy.deepcopy(self.m)
        next(s for s in m["steps"] if s["id"] == "ask")["observed_continue"] = {"keen": 0.8, "casual": 0.2}
        self.assertFalse([f for f in model.lint(m) if f["level"] == "error"])
        res = simulate(m, users=20000, seed=4, keep_sessions=0)
        self.assertAlmostEqual(analyze.metric_value(res, "step_continue:ask", "keen"), 0.8, delta=0.04)
        self.assertAlmostEqual(analyze.metric_value(res, "step_continue:ask", "casual"), 0.2, delta=0.04)
        m["steps"][0]["observed_continue"] = {"keen": 0.8, "nobody": 0.5}
        self.assertTrue(any(f["code"] == "bad-ref" for f in model.lint(m)))
        m["steps"][0]["observed_continue"] = {"keen": 1.2}
        self.assertTrue(any(f["code"] == "range" for f in model.lint(m)))

    def test_hypothesis_tied_to_a_variant(self):
        raw = copy.deepcopy(self.m)
        raw["hypotheses"].append({"id": "H3", "text": "A fifth of starters save", "metric": "step_reach:saved", "op": ">=", "value": 0.1, "on": "third-ending"})
        m = model.normalise(raw)
        self.assertFalse([f for f in model.lint(m) if f["level"] == "error"])
        self.assertEqual([h["id"] for h in model.hypotheses_for(m)], ["H1", "H2"])
        with tempfile.TemporaryDirectory() as d:
            base = pipeline.run(m, d, users=1500, seed=7, reps=4, quick=True)
            self.assertEqual([h["id"] for h in base["hypotheses"]], ["H1", "H2"])
        with tempfile.TemporaryDirectory() as d:
            var = pipeline.run(m, d, users=1500, seed=7, reps=4, quick=True, variant="third-ending")
            self.assertEqual({h["id"]: h["verdict"] for h in var["hypotheses"]}["H3"], "supported")
        raw["hypotheses"][-1].pop("on")  # untied: the base has no such step
        self.assertTrue(any(f["code"] == "bad-hypothesis" for f in model.lint(model.normalise(raw))))

    def test_score_reads_reach_and_entry_rows(self):
        with tempfile.TemporaryDirectory() as d:
            s = pipeline.run(self.m, d, users=1500, seed=7, reps=6, quick=True)
            reach = s["replication"]["reach"]["acted"]["p50"]
            obs = {"reach:acted": {"entered": 1000, "continued": 1000 * reach, "rate": reach},
                   "entry:box": {"entered": 1000, "continued": 100, "rate": 0.10},
                   "reach:nowhere": {"entered": 10, "continued": 1, "rate": 0.1}}
            sc = analyze.score(json.loads((Path(d) / "summary.json").read_text()), obs)
            rows = {r["step"]: r for r in sc["rows"]}
            self.assertEqual(sorted(rows), ["entry:box", "reach:acted"])
            self.assertTrue(rows["reach:acted"]["inside_range"])
            self.assertFalse(rows["entry:box"]["inside_range"])


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
            self.assertEqual(sc["steps_compared"], 7)  # six steps and the entry point
            self.assertIn("entry:home_banner", [r["step"] for r in sc["rows"]])
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
