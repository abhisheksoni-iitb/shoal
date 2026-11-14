"""Edge-case generator: a checklist of the situations features usually forget,
applied to each step by its type, plus pairwise combinations of the model's own
dimensions. Deterministic. Anything the model does not list under 'handles' is open."""

from __future__ import annotations

import itertools
import random

from .model import step_index, step_order

# key, title, question, severity
LIB = {
    "input": [
        ("empty_input", "Submitted empty", "What does the user see if they submit with nothing entered?", "med"),
        ("invalid_format", "Wrong format", "Is the error shown next to the field, in plain words, before or after submit?", "med"),
        ("max_length", "Very long value", "Is there a limit, is it shown, and what happens at and beyond it?", "low"),
        ("special_chars", "Emoji, accents, right-to-left text", "Are these stored and displayed correctly everywhere the value appears?", "low"),
        ("paste_formatted", "Pasted value with spaces or formatting", "Are leading/trailing spaces and pasted formatting cleaned up?", "low"),
        ("boundary_numbers", "Zero, negative, decimal or huge numbers", "Which are allowed, and what is the message for the rest?", "med"),
        ("duplicate_value", "Value that already exists", "Is a duplicate rejected, merged or allowed, and does the user understand which?", "med"),
        ("autofill", "Browser or password-manager autofill", "Does autofill put the right value in the right field?", "low"),
        ("keyboard_covers_field", "On-screen keyboard hides the field or button", "On a phone, can the user still see what they type and reach the button?", "med"),
        ("progress_lost", "Typed data lost on error or navigation", "If the step fails or the user steps back, is what they typed kept?", "high"),
    ],
    "external": [
        ("offline", "No connection", "What does the user see offline, and is their work kept until they are back?", "high"),
        ("timeout", "No answer in time", "After how long does it give up, and what can the user do then?", "high"),
        ("server_error", "The other system returns an error", "Is the message specific, and is there a retry or another route?", "high"),
        ("double_submit", "Button pressed twice", "Can a double press create two records, charges or messages?", "high"),
        ("partial_success", "Half of it worked", "If only part succeeded, what state is the user left in and how do they finish?", "high"),
        ("slow_response", "Takes longer than 10 seconds", "Is there progress feedback, and can the user leave and come back?", "med"),
        ("stale_data", "Data changed since the screen loaded", "If price, stock, permissions or status changed meanwhile, who wins?", "high"),
        ("rate_limited", "Too many attempts", "What happens on the 5th quick retry?", "low"),
    ],
    "wait": [
        ("offline", "Connection drops while waiting", "Does the wait resume, restart or fail silently?", "high"),
        ("never_completes", "The thing being waited for never arrives", "Is there a time limit and a next step when it runs out?", "high"),
        ("user_leaves", "User closes the screen while waiting", "Does it carry on in the background, and how do they learn the result?", "med"),
        ("slow_response", "Wait is much longer than promised", "Is the expected time shown, and updated?", "med"),
    ],
    "decision": [
        ("no_option_fits", "None of the choices fit", "Is there an 'other', a skip, or a way to ask for help?", "med"),
        ("change_mind", "User wants to change the choice later", "Can they go back or change it afterwards without starting over?", "med"),
        ("default_bias", "User accepts the default without reading", "Is the default safe for someone who never looks at it?", "med"),
    ],
    "view": [
        ("empty_state", "Nothing to show yet", "What does a first-time or zero-data user see, and what should they do next?", "med"),
        ("huge_list", "Thousands of items", "Does it page, search and stay fast with 10,000 rows?", "low"),
        ("long_text", "Very long names or translated text", "Does long or translated text wrap without breaking the layout?", "low"),
        ("loading_state", "Still loading", "What is shown while loading, and for how long before it looks broken?", "low"),
    ],
    "success": [
        ("no_confirmation", "No proof it worked", "Does the user get clear confirmation and a record they can find later?", "high"),
        ("repeat_action", "Does it again right after", "What happens if the user completes the same thing twice?", "med"),
        ("undo", "Wants to undo", "Can it be undone or edited, by whom and until when?", "med"),
        ("next_step_unclear", "What now?", "Is the next useful action obvious from the success screen?", "low"),
        ("others_not_told", "Other people affected are not told", "Who else needs to know, and how are they notified?", "med"),
    ],
}

FLOW = [
    ("back_button", "Back button mid-flow", "Does Back go one step back with data kept, or drop the user out?", "med"),
    ("refresh_midflow", "Page refresh or app restart mid-flow", "Is progress restored or does the user start again?", "med"),
    ("deep_link_midflow", "Link opens the middle of the flow", "What happens if someone lands on step 3 without doing steps 1 and 2?", "med"),
    ("session_expired", "Signed out while in the flow", "After signing in again, do they return to where they were?", "high"),
    ("two_tabs", "Same flow open in two tabs or devices", "Which one wins, and can the two conflict?", "med"),
    ("permission_changed", "Role or access changes mid-flow", "If access is removed while the user is in the flow, what do they see?", "med"),
    ("interrupted_resume", "Interrupted and resumed days later", "Is a half-done flow kept, expired or cleaned up, and is the user reminded?", "med"),
    ("returning_user", "Second and tenth use", "Is the repeat experience shorter than the first, and are earlier choices remembered?", "med"),
    ("flag_off", "Feature switched off while in use", "What happens to users and data mid-flow if the feature is turned off?", "low"),
    ("keyboard_only", "Keyboard only", "Can the whole flow be completed without a mouse, in a sensible focus order?", "med"),
    ("screen_reader", "Screen reader", "Are states, errors and progress announced?", "med"),
    ("large_text", "Large text or 200% zoom", "Does anything clip, overlap or become unreachable?", "low"),
    ("small_screen", "Small phone screen", "Is the main button reachable without scrolling past everything?", "med"),
    ("timezone_boundary", "Time zones and midnight", "Do dates, deadlines and 'today' hold up across time zones?", "low"),
]
SEV_ORDER = {"high": 0, "med": 1, "low": 2}


def edge_cases(m: dict) -> list:
    idx = step_index(m)
    out = []
    flow_handles = set(m["feature"].get("handles", []))
    for key, title, question, sev in FLOW:
        out.append({"id": f"E-flow-{key}", "step": None, "step_name": "Whole flow", "key": key, "title": title,
                    "question": question, "severity": sev, "status": "handled" if key in flow_handles else "open", "source": "checklist"})
    for sid in step_order(m):
        s = idx[sid]
        handles = set(s["handles"]) | flow_handles
        for key, title, question, sev in LIB.get(s["type"], []):
            out.append({"id": f"E-{sid}-{key}", "step": sid, "step_name": s["name"], "key": key, "title": title,
                        "question": question, "severity": sev, "status": "handled" if key in handles else "open", "source": "checklist"})
    out.sort(key=lambda c: (c["status"] != "open", SEV_ORDER[c["severity"]]))
    return out


def pairwise(dims: dict, seed: int = 7) -> list:
    """Smallest practical set of combinations in which every pair of values appears
    at least once (greedy all-pairs)."""
    names = [n for n, vals in dims.items() if vals]
    if len(names) < 2:
        return [{n: v} for n in names for v in dims[n]]
    need = set()
    for a, b in itertools.combinations(names, 2):
        for va in dims[a]:
            for vb in dims[b]:
                need.add((a, va, b, vb))
    rng = random.Random(seed)
    rows = []
    while need:
        best, best_cov = None, -1
        for _ in range(60):
            a, va, b, vb = rng.choice(sorted(need, key=str)) if _ == 0 else (None, None, None, None)
            cand = {n: rng.choice(dims[n]) for n in names}
            if a:
                cand[a], cand[b] = va, vb
            cov = sum(1 for (x, vx, y, vy) in need if cand[x] == vx and cand[y] == vy)
            if cov > best_cov:
                best, best_cov = cand, cov
        rows.append(best)
        need = {(x, vx, y, vy) for (x, vx, y, vy) in need if not (best[x] == vx and best[y] == vy)}
    return rows


def combination_cases(m: dict, seed: int = 7) -> list:
    dims = dict(m.get("dimensions") or {})
    if not dims:
        return []
    out = []
    for i, combo in enumerate(pairwise(dims, seed), 1):
        share = _share(m, combo)
        out.append({"id": f"C-{i:02d}", "combo": combo, "share": share,
                    "title": " + ".join(f"{k}: {v}" for k, v in combo.items()),
                    "question": "What exactly should happen in this situation, and does the spec say so?", "status": "open", "source": "combination"})
    return out


def _share(m: dict, combo: dict):
    """Rough share of users in this combination, using only the dimensions that are
    also segment context (the rest are unknown, so the figure is an upper bound)."""
    known = [k for k in combo if any(k in g["context"] for g in m["segments"])]
    if not known:
        return None
    total = 0.0
    for g in m["segments"]:
        p = 1.0
        for k in known:
            dist = g["context"].get(k)
            if not dist:
                continue
            s = sum(dist.values()) or 1.0
            p *= dist.get(combo[k], 0.0) / s
        total += g["share"] * p
    return total


def merge_review(cases: list, review: list) -> list:
    """Fold a reviewer's verdicts (from a person or a model) into the generated cases.
    Review items with an unknown id are added as new cases."""
    by_id = {c["id"]: c for c in cases}
    for r in review or []:
        rid = r.get("id")
        if rid in by_id:
            c = by_id[rid]
            for k in ("verdict", "severity", "expected", "note"):
                if r.get(k):
                    c[k] = r[k]
            if r.get("verdict") in ("handled", "not_applicable"):
                c["status"] = r["verdict"]
            elif r.get("verdict") == "gap":
                c["status"] = "gap"
        else:
            cases.append({"id": rid or f"X-{len(cases)}", "step": r.get("step"), "step_name": r.get("step_name") or r.get("step") or "Whole flow",
                          "key": r.get("key", "found"), "title": r.get("title", "Found in review"), "question": r.get("question", ""),
                          "severity": r.get("severity", "med"), "status": "gap" if r.get("verdict", "gap") == "gap" else r["verdict"],
                          "expected": r.get("expected"), "note": r.get("note"), "verdict": r.get("verdict", "gap"), "source": "review"})
    rank = {"gap": 0, "open": 1, "handled": 2, "not_applicable": 3}
    cases.sort(key=lambda c: (rank.get(c["status"], 1), SEV_ORDER.get(c.get("severity", "med"), 1)))
    return cases
