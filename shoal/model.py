"""Feature model: load, normalise, check (lint) and patch (variants).

The feature model is the contract between the spec and the simulation. It is plain
JSON so a person, a script or a language model can write it and anyone can read it.
"""

from __future__ import annotations

import copy
import json
from collections import deque
from pathlib import Path

STEP_TYPES = ("view", "input", "decision", "wait", "external", "success")
TRAITS = ("motivation", "skill", "patience", "trust")
STEP_DEFAULTS = {
    "type": "view",
    "effort": 0.2,
    "clarity": 0.8,
    "value": 0.4,
    "time_s": 10,
    "error_rate": 0.0,
    "requires": [],
    "fallback": None,
    "next": [],
    "on_error": None,
    "optional": False,
    "events": [],
    "handles": [],
    "observed_continue": None,
    "sensitive": False,
    "grants": [],
    "background": False,
}
METRICS = (
    "discovery_rate",
    "completion_rate",
    "adoption_rate",
    "error_rate",
    "blocked_rate",
    "median_time_s",
    "repeat_d1",
    "repeat_d7",
    "repeat_d30",
)


class ModelError(ValueError):
    pass


def load(path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ModelError(f"{path}: not valid JSON ({exc})") from exc
    return normalise(raw)


def normalise(raw: dict) -> dict:
    """Fill defaults and index the model. Raises ModelError on structural problems."""
    if not isinstance(raw, dict):
        raise ModelError("model must be a JSON object")
    m = copy.deepcopy(raw)
    feat = m.setdefault("feature", {})
    feat.setdefault("id", "feature")
    feat.setdefault("name", feat["id"])
    feat.setdefault("summary", "")
    feat.setdefault("session_budget_s", 300)

    steps = m.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ModelError("model needs a non-empty 'steps' list")
    seen = set()
    for s in steps:
        if "id" not in s:
            raise ModelError("every step needs an 'id'")
        if s["id"] in seen:
            raise ModelError(f"duplicate step id '{s['id']}'")
        seen.add(s["id"])
        for k, v in STEP_DEFAULTS.items():
            s.setdefault(k, copy.deepcopy(v))
        s.setdefault("name", s["id"].replace("_", " "))
        if s["type"] not in STEP_TYPES:
            raise ModelError(f"step '{s['id']}': unknown type '{s['type']}' (use {', '.join(STEP_TYPES)})")
        s["next"] = [{"to": e} if isinstance(e, str) else e for e in (s["next"] or [])]
        for e in s["next"]:
            e.setdefault("weight", 1.0)
        if isinstance(s["requires"], str):
            s["requires"] = [s["requires"]]

    segs = m.get("segments")
    if not isinstance(segs, list) or not segs:
        raise ModelError("model needs a non-empty 'segments' list")
    seen = set()
    for g in segs:
        if "id" not in g:
            raise ModelError("every segment needs an 'id'")
        if g["id"] in seen:
            raise ModelError(f"duplicate segment id '{g['id']}'")
        seen.add(g["id"])
        g.setdefault("name", g["id"].replace("_", " "))
        g.setdefault("share", 1.0)
        tr = g.setdefault("traits", {})
        for t in TRAITS:
            tr.setdefault(t, 0.5)
        g.setdefault("context", {})
        caps = g.setdefault("capabilities", {})
        if isinstance(caps, list):
            g["capabilities"] = {c: 1.0 for c in caps}
        g.setdefault("exposure", 1.0)
        g.setdefault("entry", {})
    total = sum(max(0.0, float(g["share"])) for g in segs)
    if total <= 0:
        raise ModelError("segment shares must add up to more than zero")
    m["_share_total"] = total
    for g in segs:
        g["share"] = max(0.0, float(g["share"])) / total

    entries = m.get("entry_points")
    if not entries:
        entries = [{"id": "default", "to": steps[0]["id"], "discovery": 1.0}]
    for e in entries:
        if "id" not in e or "to" not in e:
            raise ModelError("every entry point needs 'id' and 'to'")
        e.setdefault("name", e["id"].replace("_", " "))
        e.setdefault("discovery", 1.0)
    m["entry_points"] = entries

    if not m.get("success"):
        m["success"] = [s["id"] for s in steps if s["type"] == "success"]
    if isinstance(m["success"], str):
        m["success"] = [m["success"]]
    m.setdefault("dimensions", {})
    m.setdefault("hypotheses", [])
    m.setdefault("variants", [])
    m.setdefault("scenarios", [])
    vol = feat.get("volume")
    if vol is not None:
        if not isinstance(vol, dict) or not isinstance(vol.get("eligible"), (int, float)) or vol["eligible"] <= 0:
            raise ModelError("feature.volume must look like {\"eligible\": 700, \"per\": \"week\", \"unit\": \"searches\"}")
    return m


def step_index(m: dict) -> dict:
    return {s["id"]: s for s in m["steps"]}


def _edges(step: dict):
    for e in step["next"]:
        yield e["to"]
    if step.get("fallback"):
        yield step["fallback"]
    oe = step.get("on_error") or {}
    if oe.get("to"):
        yield oe["to"]


def step_order(m: dict) -> list:
    """Steps in the order a user meets them (breadth-first from the entry points)."""
    idx = step_index(m)
    order, seen = [], set()
    q = deque(e["to"] for e in m["entry_points"] if e["to"] in idx)
    while q:
        sid = q.popleft()
        if sid in seen or sid not in idx:
            continue
        seen.add(sid)
        order.append(sid)
        q.extend(_edges(idx[sid]))
    order += [s["id"] for s in m["steps"] if s["id"] not in seen]
    return order


def _finding(level, code, message, step=None, kind="design", fix=None):
    return {"level": level, "code": code, "kind": kind, "step": step, "message": message, "fix": fix}


def lint(m: dict) -> list:
    """Static checks. 'model' findings are mistakes in the model file; 'design' findings
    are things the feature itself leaves open (the useful ones)."""
    out = []
    idx = step_index(m)
    seg_ids = {g["id"] for g in m["segments"]}
    entry_ids = {e["id"] for e in m["entry_points"]}

    if abs(m.get("_share_total", 1.0) - 1.0) > 0.02:
        out.append(_finding("info", "shares-normalised", f"Segment shares added up to {m['_share_total']:.2f}; scaled to 1.", kind="model"))

    for e in m["entry_points"]:
        if e["to"] not in idx:
            out.append(_finding("error", "bad-ref", f"Entry point '{e['id']}' points to unknown step '{e['to']}'.", kind="model"))
        if not 0 <= e["discovery"] <= 1:
            out.append(_finding("error", "range", f"Entry point '{e['id']}': discovery must be between 0 and 1.", kind="model"))
    for g in m["segments"]:
        for k in g["entry"]:
            if k not in entry_ids:
                out.append(_finding("error", "bad-ref", f"Segment '{g['id']}' uses unknown entry point '{k}'.", kind="model"))
        for t, v in g["traits"].items():
            if not 0 <= v <= 1:
                out.append(_finding("error", "range", f"Segment '{g['id']}': trait '{t}' must be between 0 and 1.", kind="model"))
    for s in m["steps"]:
        for to in _edges(s):
            if to not in idx:
                out.append(_finding("error", "bad-ref", f"Step '{s['id']}' points to unknown step '{to}'.", s["id"], "model"))
        for f in ("effort", "clarity", "value", "error_rate"):
            if not 0 <= s[f] <= 1:
                out.append(_finding("error", "range", f"Step '{s['id']}': '{f}' must be between 0 and 1.", s["id"], "model"))
        oc = s.get("observed_continue")
        rates = list(oc.values()) if isinstance(oc, dict) else [] if oc is None else [oc]
        if any(not isinstance(r, (int, float)) or not 0 < r < 1 for r in rates):
            out.append(_finding("error", "range", f"Step '{s['id']}': observed_continue must be strictly between 0 and 1.", s["id"], "model"))
        if isinstance(oc, dict):
            for k in oc:
                if k != "default" and k not in seg_ids:
                    out.append(_finding("error", "bad-ref", f"Step '{s['id']}': observed_continue names unknown segment '{k}'.", s["id"], "model"))
    for sid in m["success"]:
        if sid not in idx:
            out.append(_finding("error", "bad-ref", f"Success step '{sid}' does not exist.", kind="model"))
    if not m["success"]:
        out.append(_finding("error", "no-success", "No success step: mark at least one step with type 'success'.", kind="model"))
    all_variants = {v.get("id"): v for v in m.get("variants", [])}
    for h in m["hypotheses"]:
        metric = str(h.get("metric", ""))
        tied = scenario_designs(h)
        missing = [d for d in tied if d not in all_variants]
        if missing:
            out.append(_finding("error", "bad-hypothesis", f"Hypothesis '{h.get('id')}': 'on' names unknown variant {', '.join(map(str, missing))}.", kind="model"))
            continue
        ok = metric in METRICS
        if metric.startswith(("step_continue:", "step_reach:")):
            sid = metric.split(":", 1)[1]
            try:
                ok = all(sid in step_index(apply_variant(m, all_variants[d])) for d in tied) if tied else sid in idx
            except (ModelError, KeyError, TypeError, AttributeError):
                ok = True  # the broken patch is reported with the variants below
        if not ok:
            out.append(_finding("error", "bad-hypothesis", f"Hypothesis '{h.get('id')}': unknown metric '{metric}'.", kind="model"))
        if h.get("segment", "all") not in seg_ids | {"all"}:
            out.append(_finding("error", "bad-hypothesis", f"Hypothesis '{h.get('id')}': unknown segment '{h.get('segment')}'.", kind="model"))
        if h.get("op") not in (">=", "<=", ">", "<"):
            out.append(_finding("error", "bad-hypothesis", f"Hypothesis '{h.get('id')}': op must be one of >= <= > <.", kind="model"))
    var_ids = {v.get("id") for v in m.get("variants", [])}
    for kind in ("variants", "scenarios"):
        for var in m.get(kind, []):
            label = f"{kind[:-1].capitalize()} '{var.get('id')}'"
            if not var.get("id"):
                out.append(_finding("error", "bad-patch", f"Every entry in '{kind}' needs an 'id'.", kind="model"))
                continue
            designs = [None]
            if kind == "scenarios" and var.get("on"):
                designs = scenario_designs(var)
                unknown = [d for d in designs if d not in var_ids]
                if unknown:
                    out.append(_finding("error", "bad-patch", f"{label}: 'on' names unknown variant {', '.join(map(str, unknown))}.", kind="model"))
                    continue
            for design in designs:
                try:
                    target = m if design is None else apply_variant(m, next(v for v in m["variants"] if v.get("id") == design))
                    patched = apply_variant(target, var)
                except (ModelError, KeyError, TypeError, AttributeError) as exc:
                    out.append(_finding("error", "bad-patch", f"{label} cannot be applied: {exc}", kind="model"))
                    continue
                for f in lint(patched):
                    if f["level"] == "error":
                        out.append(_finding("error", "bad-patch", f"{label}: {f['message']}", f.get("step"), "model"))
    if any(f["level"] == "error" for f in out):
        return out

    # Reachability: forward from the entries, backward from success.
    reach = set()
    q = deque(e["to"] for e in m["entry_points"])
    while q:
        sid = q.popleft()
        if sid in reach:
            continue
        reach.add(sid)
        q.extend(_edges(idx[sid]))
    rev = {sid: set() for sid in idx}
    for s in m["steps"]:
        for to in _edges(s):
            rev[to].add(s["id"])
    can_finish = set()
    q = deque(m["success"])
    while q:
        sid = q.popleft()
        if sid in can_finish:
            continue
        can_finish.add(sid)
        q.extend(rev[sid])

    for s in m["steps"]:
        sid, name = s["id"], s["name"]
        if sid not in reach:
            out.append(_finding("warn", "unreachable", f"'{name}' can never be reached from any entry point.", sid, fix="Link it from another step or remove it."))
            continue
        if s["type"] == "success":
            if not s["events"]:
                out.append(_finding("warn", "success-not-tracked", f"Success step '{name}' fires no analytics event, so the main outcome cannot be measured.", sid, fix="Add a success event."))
            continue
        if not s["next"]:
            out.append(_finding("warn", "dead-end", f"'{name}' has no way forward and is not a success step.", sid, fix="Add a next step or mark it as success."))
        elif sid not in can_finish:
            out.append(_finding("warn", "no-path-to-success", f"From '{name}' there is no route to a success step.", sid, fix="Connect this branch back to the main flow."))
        if s["error_rate"] > 0 and not s.get("on_error"):
            out.append(_finding("warn", "error-without-recovery", f"'{name}' can fail ({s['error_rate']:.0%}) but the model says nothing about what happens next.", sid, fix="Define on_error: can the user retry, or where do they land?"))
        if s["type"] in ("external", "wait") and s["time_s"] >= 15 and not s.get("background"):
            out.append(_finding("warn", "long-wait", f"'{name}' keeps the user waiting about {s['time_s']:.0f} seconds. Past ten seconds people start to leave.", sid,
                                fix="Make it faster or show the result in steps. If the user can go away and come back (an emailed code, a review), mark the step background: true."))
        if s["type"] in ("external", "wait") and s["error_rate"] == 0:
            out.append(_finding("info", "never-fails", f"'{name}' depends on something outside the screen but is modelled as never failing.", sid, fix="Set a realistic error_rate and an on_error path."))
        if s["requires"] and not s.get("fallback"):
            lacking = _share_lacking(m, s["requires"])
            out.append(_finding("warn" if lacking >= 0.03 else "info", "blocked-without-fallback", f"'{name}' needs {', '.join(s['requires'])}. About {lacking:.0%} of users lack it and have nowhere to go.", sid, fix="Add a fallback step (set it up, request it, or explain why not)."))
        if not s["events"]:
            out.append(_finding("info", "not-instrumented", f"'{name}' fires no analytics event: a drop here would be invisible after launch.", sid, fix="Add an event for this step."))
        if s["clarity"] < 0.5 and s["effort"] > 0.6:
            out.append(_finding("info", "hard-and-unclear", f"'{name}' is both high effort and low clarity, the usual shape of the biggest drop.", sid))

    for g in m["segments"]:
        if g["entry"] and all(v <= 0 for v in g["entry"].values()):
            out.append(_finding("warn", "segment-never-enters", f"Segment '{g['name']}' has no entry point with a share above zero.", kind="design"))
    for cyc in _cycles(m, idx):
        names = " → ".join(idx[c]["name"] for c in cyc + [cyc[0]])
        out.append(_finding("info", "loop", f"Loop: {names}. Check there is a retry limit and a way out.", cyc[0]))
    return out


def _share_lacking(m: dict, requires: list) -> float:
    lacking = 0.0
    for g in m["segments"]:
        have = 1.0
        for cap in requires:
            have *= float(g["capabilities"].get(cap, 0.0))
        lacking += g["share"] * (1.0 - have)
    return lacking


def _cycles(m: dict, idx: dict) -> list:
    """Simple cycles found by depth-first search, one per back edge, capped at 5."""
    found, state, stack = [], {}, []

    def visit(sid):
        if len(found) >= 5:
            return
        state[sid] = 1
        stack.append(sid)
        for to in _edges(idx[sid]):
            if to not in idx:
                continue
            if state.get(to) == 1:
                found.append(stack[stack.index(to):])
            elif to not in state:
                visit(to)
        stack.pop()
        state[sid] = 2

    for e in m["entry_points"]:
        if e["to"] in idx and e["to"] not in state:
            visit(e["to"])
    return found[:5]


def scenario_designs(scenario: dict) -> list:
    """Variant ids a scenario is tied to (its 'on' field); empty means it applies to every design."""
    on = scenario.get("on")
    return [on] if isinstance(on, str) else list(on or [])


def scenarios_for(m: dict, variant=None) -> list:
    """Scenarios that apply to the design under test: untied ones for the base design,
    and the ones tied to a variant when that variant is being run."""
    return [s for s in m.get("scenarios", []) if (variant in scenario_designs(s)) or (not scenario_designs(s) and variant is None)]


def hypotheses_for(m: dict, variant=None) -> list:
    """Hypotheses to test on the design under test: untied ones always, tied ones only on their variant."""
    return [h for h in m.get("hypotheses", []) if not scenario_designs(h) or variant in scenario_designs(h)]


def apply_variant(m: dict, variant: dict) -> dict:
    """Return a copy of the model with a variant patch applied."""
    v = copy.deepcopy(m)
    patch = variant.get("patch", {})
    idx = step_index(v)
    for sid in patch.get("remove_steps", []):
        if sid not in idx:
            raise ModelError(f"variant '{variant.get('id')}': cannot remove unknown step '{sid}'")
        gone = idx[sid]
        onward = gone["next"][0]["to"] if gone["next"] else None
        for s in v["steps"]:
            new_next = []
            for e in s["next"]:
                if e["to"] == sid:
                    if onward and onward != s["id"]:
                        new_next.append({**e, "to": onward})
                else:
                    new_next.append(e)
            s["next"] = new_next
            if s.get("fallback") == sid:
                s["fallback"] = onward
            if (s.get("on_error") or {}).get("to") == sid:
                s["on_error"]["to"] = onward
        for e in v["entry_points"]:
            if e["to"] == sid and onward:
                e["to"] = onward
        v["steps"] = [s for s in v["steps"] if s["id"] != sid]
        idx = step_index(v)
    for s in patch.get("add_steps", []):
        v["steps"].append(s)
    for sid, changes in patch.get("steps", {}).items():
        target = next((s for s in v["steps"] if s["id"] == sid), None)
        if target is None:
            raise ModelError(f"variant '{variant.get('id')}': unknown step '{sid}'")
        target.update(copy.deepcopy(changes))
    for gid, changes in patch.get("segments", {}).items():
        target = next((g for g in v["segments"] if g["id"] == gid), None)
        if target is None:
            raise ModelError(f"variant '{variant.get('id')}': unknown segment '{gid}'")
        for k, val in changes.items():
            if isinstance(val, dict) and isinstance(target.get(k), dict):
                target[k].update(val)
            else:
                target[k] = val
    for ep in patch.get("add_entry_points", []):
        v["entry_points"].append(copy.deepcopy(ep))
    for eid, changes in patch.get("entry_points", {}).items():
        target = next((e for e in v["entry_points"] if e["id"] == eid), None)
        if target is None:
            raise ModelError(f"variant '{variant.get('id')}': unknown entry point '{eid}'")
        target.update(changes)
    for k, val in patch.get("feature", {}).items():
        if isinstance(val, dict) and isinstance(v["feature"].get(k), dict):
            v["feature"][k].update(copy.deepcopy(val))
        else:
            v["feature"][k] = copy.deepcopy(val)
    v.pop("_share_total", None)
    v["variants"] = []
    v["scenarios"] = []
    # keep the hypotheses that still make sense on the patched design
    v["hypotheses"] = [{k: val for k, val in h.items() if k != "on"} for h in v.get("hypotheses", [])
                       if not scenario_designs(h) or variant.get("id") in scenario_designs(h)]
    # A patch may add or remove ways to finish: follow the step types unless the model named its own list.
    if set(m.get("success", [])) == {s["id"] for s in m["steps"] if s["type"] == "success"}:
        v.pop("success", None)
    else:
        v["success"] = [sid for sid in v["success"] if any(s["id"] == sid for s in v["steps"])]
    return normalise(v)


def save(m: dict, path) -> None:
    clean = {k: v for k, v in m.items() if not k.startswith("_")}
    Path(path).write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
