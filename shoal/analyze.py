"""Analytics over simulation results: metrics, funnel, uncertainty, hypotheses,
levers, variant comparison, calibration and scoring against real data."""

from __future__ import annotations

import copy
import csv
import random
import statistics

from .model import apply_variant, step_index, step_order
from .sim import jittered, simulate

PCT_METRICS = ("discovery_rate", "completion_rate", "adoption_rate", "error_rate", "blocked_rate",
               "repeat_d1", "repeat_d7", "repeat_d30")
METRIC_LABELS = {
    "discovery_rate": "Discovery (saw it and started)",
    "completion_rate": "Completion (of those who started)",
    "adoption_rate": "Adoption (of everyone eligible)",
    "error_rate": "Hit at least one error",
    "blocked_rate": "Blocked (could not proceed)",
    "median_time_s": "Median time to finish",
    "repeat_d1": "Came back next day",
    "repeat_d7": "Came back within a week",
    "repeat_d30": "Came back within a month",
}


def _div(a, b):
    return a / b if b else 0.0


def metrics(res: dict, segment: str = "all") -> dict:
    if segment == "all":
        rows = list(res["segments"].values())
    else:
        rows = [res["segments"][segment]]
    n = sum(r["n"] for r in rows)
    entered = sum(r["entered"] for r in rows)
    success = sum(r["success"] for r in rows)
    times = [t for r in rows for t in r["times"]]
    out = {
        "n": n,
        "entered": entered,
        "success": success,
        "discovery_rate": _div(entered, n),
        "completion_rate": _div(success, entered),
        "adoption_rate": _div(success, n),
        "error_rate": _div(sum(r["users_with_error"] for r in rows), entered),
        "blocked_rate": _div(sum(r["blocked"] for r in rows), entered),
        "median_time_s": statistics.median(times) if times else 0.0,
    }
    for k in (rows[0]["repeat"] if rows else {}):
        out[f"repeat_{k}"] = _div(sum(r["repeat"][k] for r in rows), success)
    return out


def step_counts(res: dict, sid: str, segment: str = "all") -> tuple:
    """(entered, continued) for a step, for everyone or for one segment."""
    if segment == "all":
        st = res["steps"].get(sid)
        return (st["entered"], st["continued"]) if st else (0, 0)
    ent, con = res["segments"][segment]["steps"].get(sid, (0, 0))
    return ent, con


def metric_value(res: dict, metric: str, segment: str = "all") -> float:
    """A named metric from one simulation result.
    step_continue:<id> = carried on ÷ reached; step_reach:<id> = reached ÷ started."""
    if metric.startswith("step_continue:"):
        ent, con = step_counts(res, metric.split(":", 1)[1], segment)
        return _div(con, ent)
    if metric.startswith("step_reach:"):
        ent, _ = step_counts(res, metric.split(":", 1)[1], segment)
        return _div(ent, metrics(res, segment)["entered"])
    return metrics(res, segment).get(metric, 0.0)


def success_steps(m: dict) -> list:
    """Success steps in the order users meet them."""
    idx = step_index(m)
    return [sid for sid in step_order(m) if idx[sid]["type"] == "success"]


def outcome_split(m: dict, res: dict, rep: dict) -> list:
    """When a flow can end well in more than one way: how finishers divide between the endings."""
    idx = step_index(m)
    starters = res["users"] - res["outcomes"]["never_saw"]
    rows = []
    for sid in success_steps(m):
        n = res["steps"][sid]["entered"]
        rows.append({"step": sid, "name": idx[sid]["name"], "users": n,
                     "share_of_starters": _div(n, starters), "share_of_eligible": _div(n, res["users"]),
                     "share_of_finishers": _div(n, res["outcomes"]["success"]),
                     "range": rep.get("reach", {}).get(sid),
                     "segments": {g["id"]: _div(res["segments"][g["id"]]["steps"][sid][0], res["segments"][g["id"]]["entered"])
                                  for g in m["segments"]}})
    return rows


def volume(m: dict):
    """feature.volume = {"eligible": 700, "per": "week", "unit": "searches"} turns shares into counts."""
    v = m["feature"].get("volume")
    if not isinstance(v, dict) or not v.get("eligible"):
        return None
    return {"eligible": float(v["eligible"]), "per": str(v.get("per", "week")), "unit": str(v.get("unit", "users"))}


def funnel(m: dict, res: dict) -> list:
    idx = step_index(m)
    entered_total = res["users"] - res["outcomes"]["never_saw"]
    rows = []
    for sid in step_order(m):
        st, s = res["steps"][sid], idx[sid]
        if st["entered"] == 0:
            continue
        lost = st["abandoned"] + st["blocked"] + st["error_exit"]
        causes = dict(st["reasons"])
        if st["blocked"]:
            causes["blocked"] = st["blocked"]
        if st["error_exit"]:
            causes["error"] = st["error_exit"]
        top = max(causes, key=causes.get) if causes else None
        rows.append({
            "step": sid, "name": s["name"], "type": s["type"],
            "entered": st["entered"], "share_of_starters": _div(st["entered"], entered_total),
            "continued": st["continued"], "continue_rate": 1.0 if s["type"] == "success" else _div(st["continued"], st["entered"]),
            "lost": lost, "abandoned": st["abandoned"], "blocked": st["blocked"], "error_exit": st["error_exit"],
            "skipped": st["skipped"], "errors": st["errors"], "retries": st["retries"], "fallbacks": st["fallbacks"],
            "reasons": dict(sorted(st["reasons"].items(), key=lambda kv: -kv[1])), "top_reason": top,
            "median_time_s": statistics.median(st["times"]) if st["times"] else 0.0,
        })
    return rows


def interval(values: list) -> dict:
    if not values:
        return {"p5": 0.0, "p50": 0.0, "p95": 0.0}
    v = sorted(values)

    def q(p):
        i = p * (len(v) - 1)
        lo = int(i)
        hi = min(lo + 1, len(v) - 1)
        return v[lo] + (v[hi] - v[lo]) * (i - lo)

    return {"p5": q(0.05), "p50": q(0.5), "p95": q(0.95)}


def replicate(m: dict, users: int = 1500, seed: int = 7, reps: int = 24, jitter: float = 0.1) -> dict:
    """Re-run with different random users AND nudged parameters. The spread is the
    honest error bar: it covers both sampling noise and 'we guessed the inputs'."""
    names = list(PCT_METRICS) + ["median_time_s"]
    overall = {k: [] for k in names}
    by_seg = {g["id"]: {k: [] for k in names} for g in m["segments"]}
    by_step = {s["id"]: [] for s in m["steps"]}
    by_reach = {s["id"]: [] for s in m["steps"]}
    by_entry = {e["id"]: [] for e in m["entry_points"]}
    raw = []
    for i in range(reps):
        rng = random.Random(seed * 7919 + i)
        jm = jittered(m, rng, jitter) if jitter > 0 else m
        res = simulate(jm, users=users, seed=seed * 104729 + i, keep_sessions=0)
        raw.append(res)
        mo = metrics(res)
        for k in names:
            if k in mo:
                overall[k].append(mo[k])
        for gid in by_seg:
            ms = metrics(res, gid)
            for k in names:
                if k in ms:
                    by_seg[gid][k].append(ms[k])
        for sid, st in res["steps"].items():
            if st["entered"]:
                by_step[sid].append(_div(st["continued"], st["entered"]))
            by_reach[sid].append(_div(st["entered"], mo["entered"]))
        for eid, en in res["entries"].items():
            if en["exposed"]:
                by_entry[eid].append(_div(en["entered"], en["exposed"]))
    return {
        "reps": reps, "users": users, "jitter": jitter,
        "overall": {k: interval(v) for k, v in overall.items() if v},
        "segments": {g: {k: interval(v) for k, v in d.items() if v} for g, d in by_seg.items()},
        "steps": {s: interval(v) for s, v in by_step.items() if v},
        "reach": {s: interval(v) for s, v in by_reach.items() if v},
        "entries": {x: interval(v) for x, v in by_entry.items() if v},
        "_raw": raw,
    }


_OPS = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, "<": lambda a, b: a < b}


def test_hypotheses(m: dict, rep: dict) -> list:
    out = []
    for h in m["hypotheses"]:
        seg = h.get("segment", "all")
        vals = [metric_value(r, h["metric"], seg) for r in rep["_raw"]]
        holds = sum(1 for v in vals if _OPS[h["op"]](v, h["value"])) / max(1, len(vals))
        verdict = "supported" if holds >= 0.9 else "contradicted" if holds <= 0.1 else "uncertain"
        out.append({**h, "segment": seg, "holds_share": holds, "verdict": verdict, "predicted": interval(vals)})
    return out


def sensitivity(m: dict, users: int = 4000, seed: int = 7, seeds: int = 2) -> list:
    """One change at a time: which single improvement moves adoption most?"""
    def score(model):
        a = c = 0.0
        for i in range(seeds):
            res = simulate(model, users=users, seed=seed + 31 * i, keep_sessions=0)
            mt = metrics(res)
            a += mt["adoption_rate"]
            c += mt["completion_rate"]
        return a / seeds, c / seeds

    base_a, base_c = score(m)
    reach = _reached(m, seed, users)
    trials = []
    for s in m["steps"]:
        if s["type"] == "success" or s["id"] not in reach:
            continue
        if s.get("observed_continue") is None:
            if s["effort"] >= 0.15:
                trials.append((f"Cut the effort of '{s['name']}'", s["id"], "effort", lambda mm, sid=s["id"]: _set(mm, sid, "effort", -0.2)))
            if s["clarity"] <= 0.85:
                trials.append((f"Make '{s['name']}' clearer", s["id"], "clarity", lambda mm, sid=s["id"]: _set(mm, sid, "clarity", +0.2)))
        if s["error_rate"] > 0:
            trials.append((f"Halve the errors at '{s['name']}'", s["id"], "errors", lambda mm, sid=s["id"]: _mul(mm, sid, "error_rate", 0.5)))
        if s["requires"] and not s.get("fallback"):
            trials.append((f"Give users without {', '.join(s['requires'])} a way through '{s['name']}'", s["id"], "blocked", lambda mm, sid=s["id"]: _clear(mm, sid)))
    for e in m["entry_points"]:
        if e["discovery"] < 0.95:
            trials.append((f"Make the '{e['name']}' entry point easier to find", None, "discovery", lambda mm, eid=e["id"]: _disc(mm, eid)))
    noise = 1.2 * (base_a * (1 - base_a) / (users * seeds)) ** 0.5 * 1.96
    out = []
    for label, sid, kind, fn in trials:
        mm = copy.deepcopy(m)
        fn(mm)
        a, c = score(mm)
        out.append({"lever": label, "step": sid, "kind": kind, "adoption_delta": a - base_a,
                    "completion_delta": c - base_c, "within_noise": abs(a - base_a) < noise})
    out.sort(key=lambda r: -r["adoption_delta"])
    return out


def _reached(m, seed, users):
    res = simulate(m, users=min(users, 1500), seed=seed, keep_sessions=0)
    return {sid for sid, st in res["steps"].items() if st["entered"]}


def _step(mm, sid):
    return next(s for s in mm["steps"] if s["id"] == sid)


def _set(mm, sid, f, d):
    s = _step(mm, sid)
    s[f] = min(1.0, max(0.0, s[f] + d))


def _mul(mm, sid, f, k):
    _step(mm, sid)[f] *= k


def _clear(mm, sid):
    _step(mm, sid)["requires"] = []


def _disc(mm, eid):
    e = next(e for e in mm["entry_points"] if e["id"] == eid)
    e["discovery"] = min(1.0, e["discovery"] + 0.15)


def compare_variants(m: dict, users: int = 1500, seed: int = 7, reps: int = 24, jitter: float = 0.1, key: str = "variants") -> list:
    """Paired comparison: each replication runs base and patched model on the same nudged inputs and seed.
    key="variants" compares alternative designs; key="scenarios" compares other assumptions about the world."""
    names = ("adoption_rate", "completion_rate", "discovery_rate", "error_rate", "median_time_s")
    words = ("better", "worse", "no clear difference") if key == "variants" else ("higher", "lower", "about the same")
    base_ends = success_steps(m)
    out = []
    for var in m.get(key, []):
        ends = base_ends + [s for s in success_steps(apply_variant(m, var)) if s not in base_ends]
        diffs = {k: [] for k in names}
        vals = {k: [] for k in names}
        end_diff = {s: [] for s in ends}
        end_val = {s: [] for s in ends}
        for i in range(reps):
            rng = random.Random(seed * 7919 + i)
            jm = jittered(m, rng, jitter) if jitter > 0 else m
            vm = apply_variant(jm, var)
            s = seed * 104729 + i
            rb = simulate(jm, users=users, seed=s, keep_sessions=0)
            rv = simulate(vm, users=users, seed=s, keep_sessions=0)
            mb, mv = metrics(rb), metrics(rv)
            for k in names:
                diffs[k].append(mv[k] - mb[k])
                vals[k].append(mv[k])
            for sid in ends:
                # share of everyone eligible who ends at this success step
                b = _div(rb["steps"][sid]["entered"], rb["users"]) if sid in rb["steps"] else 0.0
                v = _div(rv["steps"][sid]["entered"], rv["users"]) if sid in rv["steps"] else 0.0
                end_diff[sid].append(v - b)
                end_val[sid].append(v)
        wins = sum(1 for d in diffs["adoption_rate"] if d > 0) / reps
        out.append({"id": var.get("id"), "name": var.get("name", var.get("id")), "note": var.get("note", ""),
                    "wins_share": wins, "diff": {k: interval(v) for k, v in diffs.items()},
                    "value": {k: interval(v) for k, v in vals.items()},
                    "ends": {sid: {"diff": interval(end_diff[sid]), "value": interval(end_val[sid])} for sid in ends},
                    "verdict": words[0] if wins >= 0.9 else words[1] if wins <= 0.1 else words[2]})
    return out


def watchlist(m: dict, rep: dict, fun: list) -> list:
    """What to watch after launch: the predicted range per step and the event that shows it."""
    idx = step_index(m)
    rows = []
    for r in fun:
        s = idx[r["step"]]
        if s["type"] == "success" or r["step"] not in rep["steps"]:
            continue
        iv = rep["steps"][r["step"]]
        rows.append({"step": r["step"], "name": r["name"], "event": (s["events"] or [None])[0],
                     "expected": iv, "calibrated": s.get("observed_continue") is not None})
    return rows


def instrumentation(m: dict) -> list:
    rows = []
    for sid in step_order(m):
        s = step_index(m)[sid]
        rows.append({"step": sid, "name": s["name"], "type": s["type"], "events": s["events"],
                     "error_event": f"{sid}.error" if s["error_rate"] > 0 or s["type"] in ("external", "wait", "input") else None,
                     "missing": not s["events"]})
    return rows


# ---- real data: calibrate before launch, score after --------------------------------

def read_observed(path) -> dict:
    """CSV with columns: id, entered, continued. 'id' is a step id, or 'entry:<entry id>'
    where entered = users exposed and continued = users who started."""
    obs = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = (row.get("id") or row.get("step") or "").strip()
            if not key:
                continue
            ent, con = float(row["entered"]), float(row["continued"])
            if ent > 0:
                obs[key] = {"entered": ent, "continued": con, "rate": con / ent}
    return obs


def calibrate(m: dict, obs: dict) -> tuple:
    mm = copy.deepcopy(m)
    applied, unknown = [], []
    idx = step_index(mm)
    ents = {e["id"]: e for e in mm["entry_points"]}
    for key, o in obs.items():
        rate = min(0.999, max(0.001, o["rate"]))
        if key.startswith("entry:") and key[6:] in ents:
            ents[key[6:]]["discovery"] = rate
            ents[key[6:]]["observed"] = True
            applied.append(key)
        elif key in idx:
            idx[key]["observed_continue"] = rate
            applied.append(key)
        else:
            unknown.append(key)
    return mm, applied, unknown


def score(summary: dict, obs: dict) -> dict:
    """Compare what a run predicted with what really happened.
    Rows: a step id (carry-on rate), 'reach:<step id>' (share of starters who got there),
    or 'entry:<entry id>' (share of exposed users who started)."""
    rows, errs, inside = [], [], 0
    rep = summary["replication"]
    for key, o in obs.items():
        if key.startswith("reach:"):
            iv = rep.get("reach", {}).get(key[6:])
        elif key.startswith("entry:"):
            iv = rep.get("entries", {}).get(key[6:])
        else:
            iv = rep["steps"].get(key)
        if iv is None:
            continue
        err = abs(iv["p50"] - o["rate"])
        hit = iv["p5"] <= o["rate"] <= iv["p95"]
        errs.append(err)
        inside += hit
        rows.append({"step": key, "predicted": iv, "actual": o["rate"], "abs_error": err, "inside_range": hit})
    rows.sort(key=lambda r: -r["abs_error"])
    n = len(rows)
    return {"steps_compared": n, "mean_abs_error": sum(errs) / n if n else None,
            "fidelity": 1 - sum(errs) / n if n else None, "coverage": inside / n if n else None, "rows": rows}
