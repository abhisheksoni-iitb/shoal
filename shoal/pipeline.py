"""One rehearsal, end to end: check the model, simulate, analyse, write the report."""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import __version__
from . import analyze, edges, model as model_mod, report
from .sim import simulate

TROUBLE = ("confusion", "hesitation", "error", "question", "workaround", "frustration")


class LintFailed(Exception):
    def __init__(self, findings):
        super().__init__("model has errors")
        self.findings = findings


def _read_json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def run(m: dict, out_dir, users: int = 5000, seed: int = 7, reps: int = 24, jitter: float = 0.1,
        variant: str | None = None, quick: bool = False, rep_users: int = 1500) -> dict:
    """rep_users: synthetic users in each replication. Raise it when the outcome is rare
    (a few percent), or the ranges mostly show sampling noise."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    findings = model_mod.lint(m)
    if any(f["level"] == "error" for f in findings):
        raise LintFailed(findings)
    base = m
    if variant:
        var = next((v for v in m["variants"] if v.get("id") == variant), None)
        if var is None:
            raise model_mod.ModelError(f"no variant '{variant}' in the model")
        m = model_mod.apply_variant(m, var)
        findings = model_mod.lint(m)
    scen = {**m, "scenarios": model_mod.scenarios_for(base, variant)}
    hyp = {**m, "hypotheses": model_mod.hypotheses_for(m, variant)}
    if quick:
        users, reps, rep_users = min(users, 1500), min(reps, 8), min(rep_users, 1500)
    rep_n = min(users, rep_users)

    res = simulate(m, users=users, seed=seed, keep_sessions=300)
    rep = analyze.replicate(m, users=rep_n, seed=seed, reps=reps, jitter=jitter)
    fun = analyze.funnel(m, res)
    summary = {
        "shoal": __version__,
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "feature": {k: m["feature"].get(k) for k in ("id", "name", "summary")},
        "variant": variant,
        "users": users, "seed": seed, "args": {"users": users, "seed": seed, "reps": reps, "jitter": jitter, "variant": variant, "quick": quick, "rep_users": rep_users},
        "metrics": analyze.metrics(res),
        "outcomes": res["outcomes"],
        "funnel": fun,
        "segments": [{"id": g["id"], "name": g["name"], "share": g["share"], "metrics": analyze.metrics(res, g["id"])} for g in m["segments"]],
        "contexts": res["contexts"],
        "entries": res["entries"],
        "events": dict(sorted(res["events"].items(), key=lambda kv: -kv[1])),
        "hypotheses": analyze.test_hypotheses(hyp, rep),
        "levers": analyze.sensitivity(m, users=1500 if quick else 4000, seed=seed, seeds=1 if quick else 2),
        "variants": analyze.compare_variants(base, users=rep_n, seed=seed, reps=reps, jitter=jitter) if not variant and base["variants"] else [],
        "scenarios": analyze.compare_variants(scen, users=rep_n, seed=seed, reps=reps, jitter=jitter, key="scenarios") if scen["scenarios"] else [],
        "outcome_split": analyze.outcome_split(m, res, rep),
        "volume": analyze.volume(m),
        "watchlist": analyze.watchlist(m, rep, fun),
        "instrumentation": analyze.instrumentation(m),
        "lint": findings,
    }
    rep.pop("_raw", None)
    summary["replication"] = rep

    cases = edges.edge_cases(m)
    review = _read_json(out / "edge_review.json")
    if review:
        cases = edges.merge_review(cases, review.get("cases", review) if isinstance(review, dict) else review)
    summary["edge_cases"] = cases
    summary["combinations"] = edges.combination_cases(m, seed)

    qual = _read_json(out / "sessions.json")
    if qual:
        summary["qualitative"] = qual
        summary["triangulation"] = _triangulate(summary, qual)
    summary["sessions"] = _sample_sessions(res["sessions"])

    model_mod.save(base, out / "model.json")
    report.write_json(summary, out / "summary.json")
    report.write_json(findings, out / "lint.json")
    report.write_json({"cases": cases, "combinations": summary["combinations"]}, out / "edge_cases.json")
    with open(out / "events.sample.jsonl", "w", encoding="utf-8") as fh:
        for s in res["sessions"]:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    report.write_html(summary, out / "report.html")
    report.write_md(summary, out / "report.md")
    return summary


def rerun(run_dir) -> dict:
    """Rebuild the report of an existing run, picking up sessions.json and edge_review.json.
    Same model, same seed, so the numbers do not change."""
    d = Path(run_dir)
    prev = _read_json(d / "summary.json")
    if not prev:
        raise FileNotFoundError(f"{d}/summary.json not found: not a Shoal run folder")
    m = model_mod.load(d / "model.json")
    a = prev["args"]
    return run(m, d, users=a["users"], seed=a["seed"], reps=a["reps"], jitter=a["jitter"], variant=a.get("variant"), quick=a.get("quick", False),
               rep_users=a.get("rep_users", 1500))


def _sample_sessions(sessions: list, n: int = 12) -> list:
    by = {}
    for s in sessions:
        by.setdefault(s["outcome"], []).append(s)
    order = ["abandoned", "blocked", "error_exit", "stuck", "success", "never_saw"]
    picked, i = [], 0
    while len(picked) < n and any(by.get(o) for o in order):
        o = order[i % len(order)]
        if by.get(o):
            picked.append(by[o].pop(0))
        i += 1
        if o == "never_saw" and by.get(o):
            by[o] = []  # one is enough
    return picked


def _triangulate(summary: dict, qual: dict) -> list:
    sessions = qual.get("sessions", [])
    if not sessions:
        return []
    starters = summary["metrics"]["entered"] or 1
    rows = []
    for r in summary["funnel"]:
        if r["type"] == "success":
            continue
        mentions = sum(1 for s in sessions if any(mo.get("step") == r["step"] and mo.get("kind") in TROUBLE for mo in s.get("moments", [])))
        loss = r["lost"] / starters
        hi_n, hi_v = loss >= 0.05, mentions / len(sessions) >= 0.25
        if not (hi_n or hi_v):
            continue
        read = "Both agree: fix this first." if hi_n and hi_v else \
            "Numbers only: check this step's effort and clarity scores." if hi_n else \
            "Voices only: the model may be underrating this step."
        rows.append({"step": r["step"], "name": r["name"], "loss_share": loss, "mentions": mentions, "sessions": len(sessions), "read": read})
    rows.sort(key=lambda t: -(t["loss_share"] + t["mentions"] / len(sessions)))
    return rows
