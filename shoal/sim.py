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
REASONS = ("effort", "confusion", "trust", "waiting", "fatigue", "low_motivation", "out_of_time", "observed")


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


def wait_cost(step, agent, seconds):
    """People tolerate a wait of a few seconds; past about ten they start to leave (Nielsen's response-time limits).
    Zero up to 10 s × patience, then rising with every further ten seconds, capped.
    Only for waits the user has to sit through: a step marked background (an emailed code,
    a review, a job that runs while they do something else) costs nothing here."""
    if step["type"] not in ("wait", "external") or seconds is None or step.get("background"):
        return 0.0
    return min(0.6, 0.25 * max(0.0, seconds / 10.0 - agent["patience"]))


def continue_parts(step, agent, steps_done, elapsed, budget, errors, seconds=None):
    """The pieces that decide whether an agent carries on past a step.
    Returned separately so an abandonment can be attributed to its largest cause.
    steps_done counts every step taken so far, repeats included: going round a loop tires people."""
    skill, mot, trust = agent["skill"], agent["motivation"], agent["trust"]
    effort = step["effort"] * (1 - 0.6 * skill)
    confusion = (1 - step["clarity"]) * (0.9 - 0.5 * skill)
    trust_cost = (1 - trust) * 0.5 if step.get("sensitive") else 0.0
    waiting = wait_cost(step, agent, seconds)
    fatigue = 0.04 * steps_done + 0.25 * max(0.0, elapsed / budget - 0.6)
    pull = 0.55 * mot + 0.25 * step["value"] + 0.20 * trust - 0.05 * min(errors, 4)
    return {"effort": effort, "confusion": confusion, "trust": trust_cost, "waiting": waiting, "fatigue": fatigue, "pull": pull}


def _z(motivation, skill):
    return (motivation - 0.5) + 0.5 * (skill - 0.5)


def p_continue(step, agent, parts, mean_z=0.0, seg_z=None):
    """Chance of carrying on. A step pinned to a real rate (observed_continue) reproduces that rate on average,
    with keener and more skilled users above it and the rest below. The rate can be one number for everyone
    or one per segment: {"regular": 0.6, "new": 0.2, "default": 0.4}."""
    obs = step.get("observed_continue")
    if isinstance(obs, dict):
        centre = (seg_z or {}).get(agent["segment"], mean_z)
        obs = obs.get(agent["segment"], obs.get("default"))
    else:
        centre = mean_z
    if obs is not None:
        return _sig(_logit(obs) + 2.0 * (_z(agent["motivation"], agent["skill"]) - centre))
    cost = 0.75 * (parts["effort"] + parts["confusion"] + parts["trust"] + parts.get("waiting", 0.0)) + parts["fatigue"]
    return _sig(6.0 * (parts["pull"] - cost) + 1.2)


def _reason(parts):
    scores = {
        "effort": parts["effort"],
        "confusion": parts["confusion"],
        "trust": parts["trust"],
        "waiting": parts.get("waiting", 0.0),
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


def new_tally(m: dict) -> dict:
    """Everything one run counts, plus the lookups the walk needs. Shared by simulate() and the
    word-of-mouth run in spread.py, so both send users through exactly the same flow."""
    idx = step_index(m)
    entries = {e["id"]: e for e in m["entry_points"]}
    repeat = m["feature"].get("repeat") or {}
    seg_z = {g["id"]: _z(g["traits"]["motivation"], g["traits"]["skill"]) for g in m["segments"]}
    return {
        "idx": idx, "entries": entries, "repeat": repeat, "seg_z": seg_z,
        "budget_base": float(m["feature"].get("session_budget_s", 300)),
        "mean_z": sum(g["share"] * seg_z[g["id"]] for g in m["segments"]),
        "seg_dist": {g["id"]: g["share"] for g in m["segments"]},
        "seg_by_id": {g["id"]: g for g in m["segments"]},
        "steps": {sid: {"entered": 0, "continued": 0, "abandoned": 0, "blocked": 0, "error_exit": 0, "skipped": 0, "diverted": 0,
                        "errors": 0, "retries": 0, "fallbacks": 0, "reasons": {}, "times": []} for sid in idx},
        "segs": {g["id"]: {"n": 0, "entered": 0, "success": 0, "abandoned": 0, "blocked": 0, "error_exit": 0, "stuck": 0,
                           "users_with_error": 0, "times": [], "repeat": {k: 0 for k in repeat},
                           "steps": {sid: [0, 0] for sid in idx}} for g in m["segments"]},
        "ctx": {},
        "ents": {eid: {"exposed": 0, "entered": 0, "success": 0} for eid in entries},
        "outcomes": {"never_saw": 0, "success": 0, "abandoned": 0, "blocked": 0, "error_exit": 0, "stuck": 0},
        "events": {}, "sessions": [],
    }


def draw_user(T: dict, rng, uid: int):
    """One synthetic user and the entry point they would meet the feature through."""
    seg = T["seg_by_id"][_pick(rng, T["seg_dist"])]
    a = _new_agent(rng, seg, uid)
    T["segs"][seg["id"]]["n"] += 1
    entry_dist = seg["entry"] or {eid: 1.0 for eid in T["entries"]}
    eid = _pick(rng, entry_dist) or next(iter(T["entries"]))
    T["ents"][eid]["exposed"] += 1
    return seg, a, eid


def count_context(T: dict, a: dict, entered: bool, new: bool = True) -> None:
    for dim, val in a["context"].items():
        c = T["ctx"].setdefault(dim, {}).setdefault(str(val), {"n": 0, "entered": 0, "success": 0})
        if new:
            c["n"] += 1
        if entered:
            c["entered"] += 1


def never_saw(T: dict, a: dict, eid: str, keep: bool) -> None:
    T["outcomes"]["never_saw"] += 1
    if keep:
        T["sessions"].append(_session(a, eid, "never_saw", None, None, 0, 0, []))


def walk(T: dict, rng, a: dict, eid: str, keep: bool, start: str | None = None, ent: str | None = None) -> dict:
    """Send one user through the flow from an entry point and count what happens.
    start overrides the first step; ent overrides the entry the visit is counted under
    (word of mouth is counted as its own way in)."""
    idx, entries, steps, events = T["idx"], T["entries"], T["steps"], T["events"]
    mean_z, seg_z, repeat = T["mean_z"], T["seg_z"], T["repeat"]
    sg = T["segs"][a["segment"]]
    ent = ent or eid
    trace = [] if keep else None

    sg["entered"] += 1
    T["ents"][ent]["entered"] += 1
    budget = T["budget_base"] * (0.4 + 1.2 * a["patience"]) * rng.lognormvariate(0, 0.25)
    sid, visited, moved_on = start or entries[eid]["to"], set(), set()
    elapsed, errors, hops, friction_sum, taken = 0.0, 0, 0, 0.0, 0
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
            sg["steps"][sid][0] += 1
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
                    sg["steps"][sid][1] += 1
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
                sg["steps"][sid][1] += 1
            sid = jump
            continue

        # Carry on, skip, or quit.
        parts = continue_parts(s, a, taken, elapsed, budget, errors, t)
        taken += 1
        friction_sum += parts["effort"] + parts["confusion"]
        stays = rng.random() < p_continue(s, a, parts, mean_z, seg_z)
        note = None
        if not stays:
            if s["optional"]:
                st["skipped"] += 1
                note = "skipped"
            elif s.get("otherwise"):
                # not lost yet: the flow has a second route for people who do not act here (a reminder, another channel)
                st["diverted"] += 1
                if trace is not None:
                    trace.append({"step": sid, "t": round(elapsed), "note": f"did not act → {s['otherwise']}"})
                sid = s["otherwise"]
                continue
            else:
                # a step pinned to a real rate reproduces the drop without knowing its cause
                why = "observed" if s.get("observed_continue") is not None else _reason(parts)
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
            sg["steps"][sid][1] += 1
        for cap in s.get("grants", []):
            a["caps"].add(cap)
        sid = s["next"][choice]["to"]

    T["outcomes"][outcome] += 1
    if outcome != "success":
        sg[outcome] += 1
    if errors:
        sg["users_with_error"] += 1
    if outcome == "success":
        sg["success"] += 1
        sg["times"].append(elapsed)
        T["ents"][ent]["success"] += 1
        for dim, val in a["context"].items():
            T["ctx"][dim][str(val)]["success"] += 1
        factor = (0.55 + 0.9 * a["motivation"]) * (1 - 0.15 * min(errors, 3)) * (1 - 0.2 * _clamp(friction_sum / max(1, len(visited))))
        for k, base in repeat.items():
            if rng.random() < _clamp(float(base) * factor):
                sg["repeat"][k] += 1
    if trace is not None:
        trace.append({"step": where, "t": round(elapsed), "note": outcome if outcome == "success" else f"{outcome}: {why}"})
        T["sessions"].append(_session(a, ent, outcome, where, why, elapsed, errors, trace))
    return {"outcome": outcome, "at": where, "why": why, "errors": errors, "seconds": elapsed,
            "friction": friction_sum / max(1, taken)}


def result(T: dict, users: int, seed: int) -> dict:
    return {"users": users, "seed": seed, "outcomes": T["outcomes"], "steps": T["steps"], "segments": T["segs"],
            "contexts": T["ctx"], "entries": T["ents"], "events": T["events"], "sessions": T["sessions"]}


def simulate(m: dict, users: int = 5000, seed: int = 7, keep_sessions: int = 200) -> dict:
    rng = random.Random(seed)
    T = new_tally(m)
    for uid in range(users):
        seg, a, eid = draw_user(T, rng, uid)
        keep = uid < keep_sessions
        saw = rng.random() < _clamp(T["entries"][eid]["discovery"] * seg["exposure"])
        count_context(T, a, saw)
        if not saw:
            never_saw(T, a, eid, keep)
            continue
        walk(T, rng, a, eid, keep)
    return result(T, users, seed)


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
