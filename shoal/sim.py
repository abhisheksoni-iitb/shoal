"""Seeded agent simulation: synthetic users walk the feature model step by step.

Every rule that turns a trait into behaviour is in this file, on purpose. The output
is a set of hypotheses conditioned on the model, not a measurement of real people.
"""

from __future__ import annotations

import copy
import math
import random

from .model import step_index, TRAITS

MAX_STEPS = 60
MAX_RETRIES = 3
REASONS = ("effort", "confusion", "trust", "fatigue", "low_motivation", "out_of_time")


def _clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def _sig(x):
    if x < -40:
        return 0.0
    if x > 40:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def _logit(p):
    p = _clamp(p, 1e-4, 1 - 1e-4)
    return math.log(p / (1 - p))


def _pick(rng, dist: dict):
    """Pick a key from {key: weight}."""
    total = sum(max(0.0, w) for w in dist.values())
    if total <= 0:
        return None
    r = rng.random() * total
    for k, w in dist.items():
        r -= max(0.0, w)
        if r <= 0:
            return k
    return next(iter(dist))


def _when_ok(when, agent) -> bool:
    if not when:
        return True
    for k, want in when.items():
        if k == "segment":
            have = agent["segment"]
        elif k == "has":
            wants = [want] if isinstance(want, str) else want
            if not all(c in agent["caps"] for c in wants):
                return False
            continue
        elif k == "lacks":
            wants = [want] if isinstance(want, str) else want
            if any(c in agent["caps"] for c in wants):
                return False
            continue
        else:
            have = agent["context"].get(k)
        if isinstance(want, list):
            if have not in want:
                return False
        elif have != want:
            return False
    return True


def continue_parts(step, agent, steps_done, elapsed, budget, errors):
    """The pieces that decide whether an agent carries on past a step.
    Returned separately so an abandonment can be attributed to its largest cause."""
    skill, mot, trust = agent["skill"], agent["motivation"], agent["trust"]
    effort = step["effort"] * (1 - 0.6 * skill)
    confusion = (1 - step["clarity"]) * (0.9 - 0.5 * skill)
    trust_cost = (1 - trust) * 0.5 if step.get("sensitive") else 0.0
    fatigue = 0.04 * steps_done + 0.25 * max(0.0, elapsed / budget - 0.6)
    pull = 0.55 * mot + 0.25 * step["value"] + 0.20 * trust - 0.05 * min(errors, 4)
    return {"effort": effort, "confusion": confusion, "trust": trust_cost, "fatigue": fatigue, "pull": pull}


def p_continue(step, agent, parts, mean_z=0.0):
    obs = step.get("observed_continue")
    if obs is not None:
        z = (agent["motivation"] - 0.5) + 0.5 * (agent["skill"] - 0.5)
        return _sig(_logit(obs) + 2.0 * (z - mean_z))
    cost = 0.75 * (parts["effort"] + parts["confusion"] + parts["trust"]) + parts["fatigue"]
    return _sig(6.0 * (parts["pull"] - cost) + 1.2)


def _reason(parts):
    scores = {
        "effort": parts["effort"],
        "confusion": parts["confusion"],
        "trust": parts["trust"],
        "fatigue": parts["fatigue"] / 0.75,
        "low_motivation": max(0.0, 0.55 - parts["pull"]),
    }
    return max(scores, key=scores.get)


def _new_agent(rng, seg, uid):
    a = {"id": uid, "segment": seg["id"]}
    for t in TRAITS:
        a[t] = _clamp(rng.gauss(seg["traits"][t], 0.13), 0.02, 0.98)
    a["context"] = {dim: _pick(rng, dist) for dim, dist in seg["context"].items()}
    a["caps"] = {c for c, p in seg["capabilities"].items() if rng.random() < float(p)}
    return a


def simulate(m: dict, users: int = 5000, seed: int = 7, keep_sessions: int = 200) -> dict:
    rng = random.Random(seed)
    idx = step_index(m)
    success = set(m["success"])
    entries = {e["id"]: e for e in m["entry_points"]}
    budget_base = float(m["feature"].get("session_budget_s", 300))
    repeat = m["feature"].get("repeat") or {}
    mean_z = sum(g["share"] * ((g["traits"]["motivation"] - 0.5) + 0.5 * (g["traits"]["skill"] - 0.5)) for g in m["segments"])

    steps = {sid: {"entered": 0, "continued": 0, "abandoned": 0, "blocked": 0, "error_exit": 0, "skipped": 0,
                   "errors": 0, "retries": 0, "fallbacks": 0, "reasons": {}, "times": []} for sid in idx}
    segs = {g["id"]: {"n": 0, "entered": 0, "success": 0, "abandoned": 0, "blocked": 0, "error_exit": 0, "stuck": 0,
                      "users_with_error": 0, "times": [], "repeat": {k: 0 for k in repeat}} for g in m["segments"]}
    ctx = {}
    ents = {eid: {"exposed": 0, "entered": 0, "success": 0} for eid in entries}
    outcomes = {"never_saw": 0, "success": 0, "abandoned": 0, "blocked": 0, "error_exit": 0, "stuck": 0}
    events, sessions = {}, []
    seg_dist = {g["id"]: g["share"] for g in m["segments"]}
    seg_by_id = {g["id"]: g for g in m["segments"]}

    for uid in range(users):
        seg = seg_by_id[_pick(rng, seg_dist)]
        a = _new_agent(rng, seg, uid)
        sg = segs[seg["id"]]
        sg["n"] += 1
        entry_dist = seg["entry"] or {eid: 1.0 for eid in entries}
        eid = _pick(rng, entry_dist) or next(iter(entries))
        ents[eid]["exposed"] += 1
        trace = [] if uid < keep_sessions else None
        saw = rng.random() < _clamp(entries[eid]["discovery"] * seg["exposure"])
        for dim, val in a["context"].items():
            c = ctx.setdefault(dim, {}).setdefault(str(val), {"n": 0, "entered": 0, "success": 0})
            c["n"] += 1
            if saw:
                c["entered"] += 1
        if not saw:
            outcomes["never_saw"] += 1
            if trace is not None:
                sessions.append(_session(a, eid, "never_saw", None, None, 0, 0, []))
            continue

        sg["entered"] += 1
        ents[eid]["entered"] += 1
        budget = budget_base * (0.4 + 1.2 * a["patience"]) * rng.lognormvariate(0, 0.25)
        sid, visited, moved_on = entries[eid]["to"], set(), set()
        elapsed, errors, hops, friction_sum = 0.0, 0, 0, 0.0
        outcome, where, why = None, None, None
        network = a["context"].get("network")
        device = a["context"].get("device")

        while outcome is None:
            hops += 1
            s = idx[sid]
            st = steps[sid]
            first = sid not in visited
            if first:
                visited.add(sid)
                st["entered"] += 1
            if hops > MAX_STEPS:
                outcome, where, why = "stuck", sid, "loop"
                break

            missing = [c for c in s["requires"] if c not in a["caps"]]
            if missing:
                if s.get("fallback"):
                    st["fallbacks"] += 1
                    if trace is not None:
                        trace.append({"step": sid, "t": round(elapsed), "note": f"lacks {', '.join(missing)} → sent to {s['fallback']}"})
                    if sid not in moved_on:
                        moved_on.add(sid)
                        st["continued"] += 1
                    sid = s["fallback"]
                    continue
                st["blocked"] += 1
                outcome, where, why = "blocked", sid, "lacks " + ", ".join(missing)
                break

            for ev in s["events"]:
                events[ev] = events.get(ev, 0) + 1
            t = s["time_s"] * rng.lognormvariate(0, 0.45) * (1.35 - 0.6 * a["skill"])
            if network in ("flaky", "slow") and s["type"] in ("wait", "external"):
                t *= 2.5
            elapsed += t
            st["times"].append(t)

            if s["type"] == "success":
                outcome, where = "success", sid
                break

            # Errors and recovery.
            p_err = s["error_rate"]
            if s["type"] in ("wait", "external"):
                if network in ("flaky", "slow"):
                    p_err *= 3
                elif network == "offline" and "offline" not in s["handles"]:
                    p_err = 0.97
            elif s["type"] == "input":
                p_err *= (1.5 - a["skill"]) * (1.3 if device == "mobile" else 1.0)
            p_err = _clamp(p_err, 0, 0.97)
            oe = s.get("on_error") or {}
            retries, jump = 0, None
            while rng.random() < p_err:
                errors += 1
                st["errors"] += 1
                events[f"{sid}.error"] = events.get(f"{sid}.error", 0) + 1
                can_retry = oe.get("recoverable", False) and retries < MAX_RETRIES
                if can_retry and rng.random() < _clamp(0.35 + 0.6 * a["patience"] - 0.15 * retries):
                    retries += 1
                    st["retries"] += 1
                    elapsed += t * 0.6
                    continue
                if oe.get("to"):
                    jump = oe["to"]
                else:
                    st["error_exit"] += 1
                    outcome, where, why = "error_exit", sid, "error, no way to recover" if not oe.get("recoverable") else "gave up after errors"
                break
            if outcome:
                break
            if trace is not None and (retries or jump):
                trace.append({"step": sid, "t": round(elapsed), "note": f"error ×{retries + (1 if jump else 0)}" + (f" → {jump}" if jump else ", retried")})
            if jump:
                if sid not in moved_on:
                    moved_on.add(sid)
                    st["continued"] += 1
                sid = jump
                continue

            # Carry on, skip, or quit.
            parts = continue_parts(s, a, len(visited) - 1, elapsed, budget, errors)
            friction_sum += parts["effort"] + parts["confusion"]
            stays = rng.random() < p_continue(s, a, parts, mean_z)
            note = None
            if not stays:
                if s["optional"]:
                    st["skipped"] += 1
                    note = "skipped"
                else:
                    why = _reason(parts)
                    st["abandoned"] += 1
                    st["reasons"][why] = st["reasons"].get(why, 0) + 1
                    outcome, where = "abandoned", sid
                    break
            if elapsed > budget * 1.6:
                why = "out_of_time"
                st["abandoned"] += 1
                st["reasons"][why] = st["reasons"].get(why, 0) + 1
                outcome, where = "abandoned", sid
                break

            edges = {i: e["weight"] for i, e in enumerate(s["next"]) if _when_ok(e.get("when"), a)}
            choice = _pick(rng, edges)
            if choice is None:
                outcome, where, why = "stuck", sid, "no way forward"
                break
            if trace is not None:
                trace.append({"step": sid, "t": round(elapsed), "note": note})
            if sid not in moved_on:
                moved_on.add(sid)
                st["continued"] += 1
            for cap in s.get("grants", []):
                a["caps"].add(cap)
            sid = s["next"][choice]["to"]

        outcomes[outcome] += 1
        if outcome != "success":
            sg[outcome] += 1
        if errors:
            sg["users_with_error"] += 1
        if outcome == "success":
            sg["success"] += 1
            sg["times"].append(elapsed)
            ents[eid]["success"] += 1
            for dim, val in a["context"].items():
                ctx[dim][str(val)]["success"] += 1
            factor = (0.55 + 0.9 * a["motivation"]) * (1 - 0.15 * min(errors, 3)) * (1 - 0.2 * _clamp(friction_sum / max(1, len(visited))))
            for k, base in repeat.items():
                if rng.random() < _clamp(float(base) * factor):
                    sg["repeat"][k] += 1
        if trace is not None:
            trace.append({"step": where, "t": round(elapsed), "note": outcome if outcome == "success" else f"{outcome}: {why}"})
            sessions.append(_session(a, eid, outcome, where, why, elapsed, errors, trace))

    return {"users": users, "seed": seed, "outcomes": outcomes, "steps": steps, "segments": segs,
            "contexts": ctx, "entries": ents, "events": events, "sessions": sessions}


def _session(a, eid, outcome, where, why, elapsed, errors, trace):
    return {"user": a["id"], "segment": a["segment"], "entry": eid,
            "traits": {t: round(a[t], 2) for t in TRAITS}, "context": a["context"], "capabilities": sorted(a["caps"]),
            "outcome": outcome, "at": where, "why": why, "seconds": round(elapsed), "errors": errors, "path": trace}


def jittered(m: dict, rng: random.Random, j: float) -> dict:
    """Copy of the model with its guessed parameters nudged, to show how much the
    answer depends on those guesses. Calibrated steps (observed_continue) are left alone."""
    v = copy.deepcopy(m)
    for s in v["steps"]:
        if s.get("observed_continue") is None:
            for f in ("effort", "clarity", "value"):
                s[f] = _clamp(s[f] + rng.uniform(-j, j))
        s["error_rate"] = _clamp(s["error_rate"] * rng.uniform(1 - 2 * j, 1 + 2 * j))
    for e in v["entry_points"]:
        if not e.get("observed"):
            e["discovery"] = _clamp(e["discovery"] * rng.uniform(1 - 2 * j, 1 + 2 * j))
    return v
