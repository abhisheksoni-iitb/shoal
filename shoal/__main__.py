"""Command line: python3 -m shoal <command>."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from . import __version__, analyze, edges, model as model_mod, pipeline, report

HERE = Path(__file__).resolve().parent
ICON = {"error": "✗", "warn": "!", "info": "·"}


def _print_findings(findings, show_info=True):
    for f in findings:
        if f["level"] == "info" and not show_info:
            continue
        print(f"  {ICON[f['level']]} [{f['code']}] {f['message']}" + (f"  → {f['fix']}" if f.get("fix") else ""))


def cmd_init(a):
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    target = d / "feature.json"
    if target.exists() and not a.force:
        sys.exit(f"{target} already exists (use --force to overwrite)")
    shutil.copyfile(HERE / "template.json", target)
    print(f"Wrote {target}\nEdit it to describe your feature, then: shoal lint {target} && shoal run {target}")


def cmd_lint(a):
    m = model_mod.load(a.model)
    findings = model_mod.lint(m)
    errors = [f for f in findings if f["level"] == "error"]
    warns = [f for f in findings if f["level"] == "warn"]
    print(f"{m['feature']['name']}: {len(m['steps'])} steps, {len(m['segments'])} segments, {len(m['entry_points'])} entry points")
    _print_findings(findings)
    print(f"{len(errors)} errors, {len(warns)} warnings, {len(findings) - len(errors) - len(warns)} notes")
    if a.json:
        report.write_json(findings, a.json)
    sys.exit(2 if errors else 0)


def _summary_lines(s):
    ov = s["replication"]["overall"]
    lines = [f"Report: {s['_dir']}/report.html", ""]
    lines += [f"- {x}" for x in report.headline(s)]
    lines.append("")
    for k in ("adoption_rate", "discovery_rate", "completion_rate", "error_rate", "blocked_rate"):
        lines.append(f"{analyze.METRIC_LABELS[k]:<36} {100 * ov[k]['p50']:5.1f}%   range {report.rng_txt(ov[k])}")
    lines.append(f"{analyze.METRIC_LABELS['median_time_s']:<36} {ov['median_time_s']['p50']:5.0f}s   range {report.rng_txt(ov['median_time_s'], True)}")
    for h in s["hypotheses"]:
        lines.append(f"Hypothesis {h['id']}: {h['verdict']} ({report._fmt_metric(h['metric'], h['predicted']['p50'])} predicted; holds in {100 * h['holds_share']:.0f}% of runs)")
    for v in s.get("variants") or []:
        lines.append(f"Variant {v['name']}: {v['verdict']} ({100 * v['diff']['adoption_rate']['p50']:+.1f} pts adoption, beats base in {100 * v['wins_share']:.0f}% of runs)")
    for v in s.get("scenarios") or []:
        lines.append(f"Scenario {v['name']}: {100 * v['value']['adoption_rate']['p50']:.1f}% adoption ({100 * v['diff']['adoption_rate']['p50']:+.1f} pts, {v['verdict']})")
    ec = s["edge_cases"]
    lines.append(f"Edge cases: {sum(c['status'] == 'gap' for c in ec)} gaps, {sum(c['status'] == 'open' for c in ec)} open, {sum(c['status'] in ('handled', 'not_applicable') for c in ec)} handled")
    return lines


def cmd_run(a):
    m = model_mod.load(a.model)
    out = Path(a.out) if a.out else Path(a.model).resolve().parent / "runs" / (time.strftime("%Y%m%d-%H%M%S") + (f"-{a.variant}" if a.variant else ""))
    t0 = time.time()
    try:
        s = pipeline.run(m, out, users=a.users, seed=a.seed, reps=a.reps, jitter=a.jitter, variant=a.variant, quick=a.quick)
    except pipeline.LintFailed as exc:
        print("The model has errors; fix these first:")
        _print_findings([f for f in exc.findings if f["level"] == "error"])
        sys.exit(2)
    s["_dir"] = str(out)
    print("\n".join(_summary_lines(s)))
    print(f"\nDone in {time.time() - t0:.1f}s. Files: report.html, report.md, summary.json, edge_cases.json, events.sample.jsonl, model.json")


def cmd_report(a):
    s = pipeline.rerun(a.run_dir)
    s["_dir"] = str(a.run_dir)
    print("\n".join(_summary_lines(s)))


def cmd_edges(a):
    m = model_mod.load(a.model)
    cases = edges.edge_cases(m)
    combos = edges.combination_cases(m)
    if a.out:
        report.write_json({"cases": cases, "combinations": combos}, a.out)
        print(f"Wrote {a.out}")
    open_cases = [c for c in cases if c["status"] == "open"]
    print(f"{len(cases)} cases, {len(open_cases)} open, {len(combos)} combinations")
    for c in open_cases[: a.top]:
        print(f"  [{c['severity']}] {c['id']}  {c['step_name']}: {c['title']}. {c['question']}")


def cmd_calibrate(a):
    m = model_mod.load(a.model)
    obs = analyze.read_observed(a.observed)
    mm, applied, unknown = analyze.calibrate(m, obs)
    out = a.out or str(Path(a.model).with_suffix("")) + ".calibrated.json"
    model_mod.save(mm, out)
    print(f"Calibrated {len(applied)} items from real data: {', '.join(applied) or 'none'}")
    if unknown:
        print(f"Ignored unknown ids: {', '.join(unknown)}")
    print(f"Wrote {out}")


def cmd_score(a):
    d = Path(a.run_dir)
    summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    sc = analyze.score(summary, analyze.read_observed(a.observed))
    report.write_json(sc, d / "score.json")
    if not sc["steps_compared"]:
        sys.exit("No step ids in the CSV match this run.")
    print(f"Compared {sc['steps_compared']} steps. Fidelity {100 * sc['fidelity']:.0f}% (mean error {100 * sc['mean_abs_error']:.1f} points). "
          f"{100 * sc['coverage']:.0f}% of real numbers fell inside the predicted range.")
    for r in sc["rows"]:
        print(f"  {r['step']:<28} predicted {100 * r['predicted']['p50']:5.1f}% ({100 * r['predicted']['p5']:.1f}–{100 * r['predicted']['p95']:.1f}%)  actual {100 * r['actual']:5.1f}%  {'ok' if r['inside_range'] else 'OUTSIDE'}")
    print(f"Wrote {d / 'score.json'}")


def cmd_serve(a):
    from . import server
    server.serve(Path(a.root).resolve(), a.port)


def main(argv=None):
    p = argparse.ArgumentParser(prog="shoal", description="Rehearse a feature with synthetic users before real ones see it.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="write a starter feature.json")
    s.add_argument("dir")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("lint", help="check a feature model and list design gaps")
    s.add_argument("model")
    s.add_argument("--json")
    s.set_defaults(fn=cmd_lint)

    s = sub.add_parser("run", help="simulate, analyse and write the report")
    s.add_argument("model")
    s.add_argument("--out")
    s.add_argument("--users", type=int, default=5000)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--reps", type=int, default=24)
    s.add_argument("--jitter", type=float, default=0.1)
    s.add_argument("--variant", help="run this variant as the design under test")
    s.add_argument("--quick", action="store_true", help="smaller, faster run for iterating")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("report", help="rebuild a run's report after adding sessions.json or edge_review.json")
    s.add_argument("run_dir")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("edges", help="list edge cases and combinations for a model")
    s.add_argument("model")
    s.add_argument("--out")
    s.add_argument("--top", type=int, default=25)
    s.set_defaults(fn=cmd_edges)

    s = sub.add_parser("calibrate", help="pin steps to real conversion numbers from a CSV")
    s.add_argument("model")
    s.add_argument("observed")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_calibrate)

    s = sub.add_parser("score", help="compare a run's predictions with real numbers after launch")
    s.add_argument("run_dir")
    s.add_argument("observed")
    s.set_defaults(fn=cmd_score)

    s = sub.add_parser("serve", help="local web app: run rehearsals and browse reports")
    s.add_argument("--root", default=".")
    s.add_argument("--port", type=int, default=8787)
    s.set_defaults(fn=cmd_serve)

    a = p.parse_args(argv)
    try:
        a.fn(a)
    except model_mod.ModelError as exc:
        sys.exit(f"Model error: {exc}")
    except FileNotFoundError as exc:
        sys.exit(f"Not found: {exc}")


if __name__ == "__main__":
    main()
