"""Word of mouth: what people say about the feature after using it, and what that does
to who tries it next.

The launch-day rehearsal in sim.py treats every user as alone. Here they are joined in a
network of contacts and the launch runs over several periods. People who used the feature
form an opinion from what happened to them and tell some contacts. A listener's opinion
moves toward what they hear only if it is not too far from their own (bounded confidence,
after Deffuant and Weisbuch), which is why early bad word can shut out later good word.
Opinion then feeds the two inputs the flow model already has: whether someone finds the
feature, and how much they trust it when they do.

Every rule and default is in this file. The defaults are hand-set, not measured: read the
result as "if talk works roughly like this", and use the dependence table to see which
assumption carries the answer.
"""

from __future__ import annotations

import copy
import random

from . import analyze
from .sim import _clamp, count_context, draw_user, jittered, never_saw, new_tally, result, walk

WOM = "word_of_mouth"
UNHAPPY = ("abandoned", "blocked", "error_exit", "stuck")

DEFAULTS = {
    "periods": 8,             # how long the launch is watched
    "period": "week",         # what one period is called in the report
    "rollout_periods": 4,     # periods the official entry points take to reach everyone
    "contacts": 6,            # people each user is in touch with, on average
    "within_segment": 0.7,    # share of those contacts who are the same kind of user
    "talk": {"success": 0.20, "abandoned": 0.06, "blocked": 0.15, "error_exit": 0.25, "stuck": 0.25},
    "tell": 2,                # contacts told each time someone talks
    "decay": 0.5,             # how fast people stop talking: chance is multiplied by this each period
    "relay": 0.0,             # chance someone passes on what they heard without having tried it
    "opinion": {"abandoned": 0.35, "blocked": 0.25, "error_exit": 0.15, "stuck": 0.15},
    "openness": 0.45,         # a listener ignores opinions further than this from their own
    "pull": 0.5,              # how far a listener moves toward an opinion they accept
    "convert": 0.5,           # how readily a good opinion turns into trying the feature
    "trust_gain": 0.15,       # how much opinion shifts trust when the person does try it
    "to": None,               # step a recommended user lands on (default: where the first entry point leads)
}
RATES = ("within_segment", "decay", "relay", "openness", "pull", "convert", "trust_gain")


def fill(sp) -> dict:
    """The model's spread block with defaults filled in. `true` or {} means all defaults."""
    sp = {} if sp is True else dict(sp or {})
    out = copy.deepcopy(DEFAULTS)
    for k, v in sp.items():
        if isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def problems(m: dict) -> list:
    """(level, message) pairs for the lint."""
    sp, out = m["spread"], []
    unknown = sorted(set(sp) - set(DEFAULTS))
    if unknown:
        out.append(("error", f"spread: unknown field {', '.join(unknown)}."))
    for k in ("periods", "rollout_periods", "tell"):
        if not isinstance(sp[k], int) or isinstance(sp[k], bool) or sp[k] < 1:
            out.append(("error", f"spread.{k} must be a whole number of 1 or more."))
    if not isinstance(sp["contacts"], (int, float)) or sp["contacts"] < 0:
        out.append(("error", "spread.contacts must be zero or more."))
    for k in RATES:
        if not isinstance(sp[k], (int, float)) or not 0 <= sp[k] <= 1:
            out.append(("error", f"spread.{k} must be between 0 and 1."))
    for table in ("talk", "opinion"):
        if not isinstance(sp[table], dict):
            out.append(("error", f"spread.{table} must be an object of outcome: number."))
            continue
        for k, v in sp[table].items():
            if k not in DEFAULTS["talk"] or (table == "opinion" and k == "success"):
                out.append(("error", f"spread.{table}: unknown outcome '{k}'."))
            elif not isinstance(v, (int, float)) or not 0 <= v <= 1:
                out.append(("error", f"spread.{table}.{k} must be between 0 and 1."))
    if sp["to"] is not None and sp["to"] not in {s["id"] for s in m["steps"]}:
        out.append(("error", f"spread.to points to unknown step '{sp['to']}'."))
    if any(e["id"] == WOM for e in m["entry_points"]):
        out.append(("error", f"An entry point is called '{WOM}'. That name is kept for people who arrive on a recommendation; rename the entry point."))
    if not out and sp["rollout_periods"] == 1:
        out.append(("info", "spread.rollout_periods is 1: everyone meets the feature at once, so bad word of mouth cannot reach anyone "
                            "before the feature does and talk can only add users. Set it to how long the launch really takes to reach everyone."))
    return out


def _opinion_after(sp: dict, r: dict) -> float:
    """Opinion once someone has used the feature: finishing is good, more so when it went smoothly."""
    if r["outcome"] == "success":
        quality = _clamp(1 - 0.2 * min(r["errors"], 3) - 0.6 * r["friction"])
        return 0.62 + 0.33 * quality
    return float(sp["opinion"].get(r["outcome"], 0.3))


def _network(net, people: list, sp: dict) -> None:
    by_seg = {}
    for i, p in enumerate(people):
        by_seg.setdefault(p["a"]["segment"], []).append(i)
    n = len(people)
    if n < 2:
        return
    half = sp["contacts"] / 2.0   # each tie is counted for both ends
    for i, p in enumerate(people):
        ties = int(half) + (1 if net.random() < half - int(half) else 0)
        for _ in range(ties):
            pool = by_seg[p["a"]["segment"]] if net.random() < sp["within_segment"] else None
            j = pool[net.randrange(len(pool))] if pool and len(pool) > 1 else net.randrange(n)
            if j != i:
                p["contacts"].append(j)
                people[j]["contacts"].append(i)


def simulate_spread(m: dict, users: int = 5000, seed: int = 7, keep_sessions: int = 0) -> dict:
    """The launch over several periods, with talk. Returns the same shape as sim.simulate()
    plus a "spread" block. Users and their walks come from the same random stream as
    simulate(); the network and the talk use a second one, so with no talk and a one-period
    rollout the outcome is exactly simulate()'s."""
    sp = m["spread"]
    rng = random.Random(seed)
    net = random.Random(seed * 1000003 + 17)
    T = new_tally(m)
    T["ents"][WOM] = {"exposed": 0, "entered": 0, "success": 0}
    wom_to = sp["to"] or m["entry_points"][0]["to"]
    wom_eid = m["entry_points"][0]["id"]
    periods = sp["periods"]
    roll = min(sp["rollout_periods"], periods)
    people, new_success = [], [0]

    def enter(p, period, via, start=None, ent=None):
        a, shift = p["a"], p["x"] - p["x0"]
        a["trust"] = _clamp(a["trust"] + sp["trust_gain"] * 2 * shift, 0.02, 0.98)
        r = walk(T, rng, a, p["eid"] if via == "official" else wom_eid, p["keep"], start, ent)
        p["outcome"], p["tried"], p["via"] = r["outcome"], period, via
        p["x"] = _opinion_after(sp, r)
        if r["outcome"] == "success":
            new_success[0] += 1

    def official(p, period) -> bool:
        """The feature reaches this person through its own entry point. What they have heard by then moves the odds."""
        sway = _clamp(1 + 2 * (p["x"] - p["x0"]), 0.2, 1.8)
        saw = p["u"] < _clamp(T["entries"][p["eid"]]["discovery"] * p["seg"]["exposure"] * sway)
        if saw:
            if period > 1:
                count_context(T, p["a"], True, new=False)
            enter(p, period, "official")
        return saw

    started_official = 0
    for uid in range(users):
        seg, a, eid = draw_user(T, rng, uid)
        x0 = _clamp(0.5 + 0.3 * (a["trust"] - 0.5) + net.gauss(0, 0.05), 0.05, 0.95)
        p = {"a": a, "seg": seg, "eid": eid, "u": rng.random(), "keep": uid < keep_sessions,
             "when": 1 if roll == 1 else net.randint(1, roll), "x0": x0, "x": x0, "contacts": [],
             "outcome": None, "tried": None, "via": None, "heard": 0, "heard_good": False, "bad_first": False, "last_heard": 0}
        people.append(p)
        if p["when"] == 1:
            saw = p["u"] < _clamp(T["entries"][eid]["discovery"] * seg["exposure"])
            count_context(T, a, saw)
            if saw:
                enter(p, 1, "official")
                started_official += 1
        else:
            count_context(T, a, False)
    _network(net, people, sp)

    timeline, tried, finished = [], 0, 0
    for period in range(1, periods + 1):
        if period > 1:
            new_success[0] = 0
            started_official = 0
            for p in people:
                if p["when"] == period and p["outcome"] is None and official(p, period):
                    started_official += 1

        # Talk. Who speaks is fixed at the start of the period; opinions move as messages land.
        speakers = []
        for i, p in enumerate(people):
            if p["outcome"] is not None:
                chance = sp["talk"].get(p["outcome"], 0.0) * sp["decay"] ** (period - p["tried"])
            else:
                chance = sp["relay"] if p["last_heard"] == period - 1 and period > 1 else 0.0
            if chance > 0 and p["contacts"] and net.random() < chance:
                speakers.append(i)
        good = bad = 0
        recruits = []
        for i in speakers:
            sx = people[i]["x"]
            for _ in range(sp["tell"]):
                q = people[people[i]["contacts"][net.randrange(len(people[i]["contacts"]))]]
                good, bad = good + (sx > 0.5), bad + (sx <= 0.5)
                q["heard"] += 1
                q["last_heard"] = period
                untried = q["outcome"] is None
                if untried and sx <= 0.5 and not q["heard_good"] and q["heard"] == 1:
                    q["bad_first"] = True
                if abs(sx - q["x"]) > sp["openness"]:
                    continue   # too far from what they already think: it does not land
                q["x"] += sp["pull"] * (sx - q["x"]) * (1.0 if untried else 0.25)
                if untried and sx > 0.5 and not q.get("queued"):
                    if not q["heard_good"]:
                        q["heard_good"] = True
                        T["ents"][WOM]["exposed"] += 1
                    p_try = sp["convert"] * 2 * max(0.0, q["x"] - 0.5) * (0.5 + q["a"]["motivation"])
                    if net.random() < _clamp(p_try):
                        q["queued"] = True
                        recruits.append(q)
        for q in recruits:
            count_context(T, q["a"], True, new=False)
            enter(q, period, WOM, start=wom_to, ent=WOM)

        tried += started_official + len(recruits)
        finished += new_success[0]
        timeline.append({"period": period, "started_official": started_official, "started_wom": len(recruits),
                         "finished": new_success[0], "tried": tried, "adopted": finished, "adoption": finished / users if users else 0.0,
                         "talkers": len(speakers), "good": good, "bad": bad})

    untried = [p for p in people if p["outcome"] is None]
    for p in untried:
        never_saw(T, p["a"], p["eid"], p["keep"])
    res = result(T, users, seed)
    n_un = len(untried) or 1
    res["spread"] = {
        "timeline": timeline,
        "recommended": dict(T["ents"][WOM]),
        "put_off": sum(1 for p in untried if p["x"] < p["x0"] - 0.05),
        "bad_first": sum(1 for p in people if p["bad_first"]),
        "untried": {"n": len(untried),
                    "against": sum(1 for p in untried if p["x"] < 0.4) / n_un,
                    "neutral": sum(1 for p in untried if 0.4 <= p["x"] <= 0.6) / n_un,
                    "for": sum(1 for p in untried if p["x"] > 0.6) / n_un},
        "messages": {"good": sum(r["good"] for r in timeline), "bad": sum(r["bad"] for r in timeline)},
    }
    return res


def silent(m: dict) -> dict:
    """The same launch with nobody talking: the comparison that shows what talk adds or costs."""
    v = copy.deepcopy(m)
    v["spread"]["talk"] = {k: 0.0 for k in v["spread"]["talk"]}
    v["spread"]["relay"] = 0.0
    return v


def _with(m: dict, **changes) -> dict:
    v = copy.deepcopy(m)
    for k, val in changes.items():
        if isinstance(val, dict):
            v["spread"][k].update(val)
        else:
            v["spread"][k] = val
    return v


def _jitter(m: dict, rng: random.Random, j: float) -> dict:
    """Nudge the guessed talk settings as well as the flow's guessed inputs."""
    v = jittered(m, rng, j)
    sp = v["spread"]
    sp["talk"] = {k: _clamp(x * rng.uniform(1 - 2 * j, 1 + 2 * j)) for k, x in sp["talk"].items()}
    sp["contacts"] = sp["contacts"] * rng.uniform(1 - 2 * j, 1 + 2 * j)
    for k in ("convert", "pull", "openness"):
        sp[k] = _clamp(sp[k] * rng.uniform(1 - 2 * j, 1 + 2 * j))
    return v


def _adoption(res: dict, segment: str = "all") -> float:
    return analyze.metrics(res, segment)["adoption_rate"]


def _pair(m: dict, users: int, seed: int) -> tuple:
    return _adoption(simulate_spread(silent(m), users, seed)), _adoption(simulate_spread(m, users, seed))


def knobs(m: dict) -> list:
    """The assumptions worth testing one at a time."""
    sp = m["spread"]
    out = [
        ("Unhappy users say nothing", _with(m, talk={k: 0.0 for k in UNHAPPY})),
        ("Unhappy users talk twice as much", _with(m, talk={k: _clamp(sp["talk"].get(k, 0) * 2) for k in UNHAPPY})),
        ("Happy users talk twice as much", _with(m, talk={"success": _clamp(sp["talk"].get("success", 0) * 2)})),
        ("Each person who talks tells twice as many people", _with(m, tell=sp["tell"] * 2)),
        ("Listeners accept any opinion, however far from their own", _with(m, openness=1.0)),
    ]
    if sp["rollout_periods"] > 1:
        out.append(("The feature reaches everyone in the first " + sp["period"], _with(m, rollout_periods=1)))
    return out


def analyse(m: dict, users: int = 5000, seed: int = 7, reps: int = 24, jitter: float = 0.1, rep_users: int = 1500,
            base: dict | None = None) -> dict:
    """The word-of-mouth section of a run. base is the unpatched model, for the variants table."""
    sp = m["spread"]
    res = simulate_spread(m, users, seed, keep_sessions=0)
    quiet = simulate_spread(silent(m), users, seed)
    a_with, a_without = _adoption(res), _adoption(quiet)

    withs, withouts, lifts = [], [], []
    for i in range(reps):
        rng = random.Random(seed * 7919 + i)
        jm = _jitter(m, rng, jitter) if jitter > 0 else m
        wo, wi = _pair(jm, rep_users, seed * 104729 + i)
        withs.append(wi)
        withouts.append(wo)
        lifts.append(wi - wo)
    lift = analyze.interval(lifts)
    noise = max(0.002, 0.1 * analyze.interval(withouts)["p50"])
    verdict = "adds" if lift["p5"] > 0 and lift["p50"] >= noise else "costs" if lift["p95"] < 0 and -lift["p50"] >= noise else "no clear effect"

    # One assumption at a time. Same users in every row; a change smaller than the noise floor is marked.
    k_seeds = (seed + 101, seed + 202, seed + 303)
    ref = sum(_adoption(simulate_spread(m, users, s)) for s in k_seeds) / len(k_seeds)
    depends = []
    for label, km in knobs(m):
        val = sum(_adoption(simulate_spread(km, users, s)) for s in k_seeds) / len(k_seeds)
        depends.append({"change": label, "adoption": val, "delta": val - ref, "within_noise": abs(val - ref) < max(0.004, 0.04 * ref)})
    depends.sort(key=lambda d: -abs(d["delta"]))

    segments = [{"id": g["id"], "name": g["name"], "without": _adoption(quiet, g["id"]), "with": _adoption(res, g["id"])} for g in m["segments"]]

    designs = []
    src = base if base is not None else m
    if src.get("variants"):
        from .model import apply_variant
        k = max(6, reps // 3)
        rows = [("Base design", src)] + [(v.get("name", v["id"]), apply_variant(src, v)) for v in src["variants"]]
        for name, dm in rows:
            if not dm.get("spread"):
                continue
            pairs = [_pair(dm, rep_users, seed * 15485863 + i) for i in range(k)]
            wo, wi = sum(x[0] for x in pairs) / k, sum(x[1] for x in pairs) / k
            designs.append({"name": name, "without": wo, "with": wi, "lift": wi - wo})

    s = res["spread"]
    rec = s["recommended"]
    return {
        "settings": {k: sp[k] for k in DEFAULTS},
        "periods": sp["periods"], "period": sp["period"], "rollout_periods": min(sp["rollout_periods"], sp["periods"]),
        "without": a_without, "with": a_with, "lift": a_with - a_without,
        "range": {"without": analyze.interval(withouts), "with": analyze.interval(withs), "lift": lift},
        "adds_in": sum(1 for x in lifts if x > 0) / len(lifts) if lifts else 0.0,
        "verdict": verdict,
        "timeline": s["timeline"], "timeline_without": quiet["spread"]["timeline"],
        "recommended": {"heard": rec["exposed"], "tried": rec["entered"], "finished": rec["success"]},
        "put_off": s["put_off"], "bad_first": s["bad_first"], "untried": s["untried"], "messages": s["messages"],
        "users": users, "depends": depends, "segments": segments, "designs": designs,
    }


def lines(sp: dict) -> list:
    """Plain sentences for the headline and the command line."""
    per, n = sp["period"], sp["periods"]
    out = []
    lift, r = sp["lift"], sp["range"]["lift"]
    if sp["verdict"] == "no clear effect":
        out.append(f"Word of mouth: no clear effect over {n} {per}s ({100 * sp['without']:.1f}% adoption without talk, {100 * sp['with']:.1f}% with; "
                   f"change between {100 * r['p5']:+.1f} and {100 * r['p95']:+.1f} points).")
    else:
        out.append(f"Word of mouth {sp['verdict']} about {abs(100 * lift):.1f} points of adoption over {n} {per}s: {100 * sp['without']:.1f}% without talk, "
                   f"{100 * sp['with']:.1f}% with (change between {100 * r['p5']:+.1f} and {100 * r['p95']:+.1f} points).")
    rec, msg = sp["recommended"], sp["messages"]
    if rec["heard"]:
        out.append(f"{rec['heard']:,} of {sp['users']:,} users heard a recommendation before trying; {rec['tried']:,} tried it because of one and {rec['finished']:,} finished.")
    total = msg["good"] + msg["bad"]
    if total:
        out.append(f"{100 * msg['bad'] / total:.0f}% of what was said was negative; {sp['put_off']:,} people who never tried it ended up thinking worse of it than they started.")
    if sp["depends"] and not sp["depends"][0]["within_noise"]:
        d = sp["depends"][0]
        out.append(f"The answer depends most on this assumption: {d['change'].lower()} would move adoption by {100 * d['delta']:+.1f} points.")
    return out
