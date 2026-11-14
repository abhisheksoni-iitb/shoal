"""Report writers: one self-contained HTML page and a short Markdown summary."""

from __future__ import annotations

import html
import json

from .analyze import METRIC_LABELS

REASON_LABEL = {"effort": "Too much effort", "confusion": "Confusing", "trust": "Did not trust it", "waiting": "The wait was too long",
                "fatigue": "Ran out of steam", "low_motivation": "Did not care enough", "out_of_time": "Ran out of time",
                "observed": "Measured drop, cause not modelled", "blocked": "Blocked", "error": "Error"}
REASON_PHRASE = {"effort": "it asks for too much effort", "confusion": "it is confusing", "trust": "they did not trust it",
                 "waiting": "the wait was too long", "fatigue": "they ran out of steam", "low_motivation": "they did not care enough",
                 "out_of_time": "they ran out of time", "observed": "that is the measured rate (the model does not say why)"}
REASON_ORDER = ["effort", "confusion", "trust", "waiting", "fatigue", "low_motivation", "out_of_time", "observed", "blocked", "error"]
OUTCOME_LABEL = {"success": "Finished", "abandoned": "Gave up", "blocked": "Blocked", "error_exit": "Stopped by an error",
                 "stuck": "Stuck in a loop", "never_saw": "Never started"}
LIMITS = [
    "These are predictions from a model of your feature, not measurements of real people. Treat every number as a hypothesis to check.",
    "The ranges cover random variation and a ±10% wobble on the guessed inputs. They do not cover a wrong model (a missing step, a missing kind of user).",
    "Language models asked to play users tend to be more agreeable, more goal-directed and less varied than real people. Qualitative sessions find problems; they do not prove their absence.",
    "Rank order (which step is worst, which fix helps most) is more reliable than absolute levels. Calibrate with real data when you have any, and score the run after launch.",
]

CSS = """
:root{--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
--s1:#2a78d6;--s1soft:#cde2fb;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--s7:#6250d6;--s8:#e34948;--s9:#0e8f9b;
--good:#0ca30c;--warn:#fab219;--serious:#ec835a;--crit:#d03b3b;--goodtx:#006300}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;
--s1:#3987e5;--s1soft:#184f95;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s7:#9085e9;--s8:#e66767;--goodtx:#0ca30c}}
:root[data-theme=dark]{--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;
--s1:#3987e5;--s1soft:#184f95;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s7:#9085e9;--s8:#e66767;--goodtx:#0ca30c}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:1040px;margin:0 auto;padding:28px 16px 64px}h1{font-size:26px;line-height:1.2;margin:0 0 6px}h2{font-size:19px;margin:0 0 4px}
h3{font-size:15px;margin:18px 0 6px}p{margin:6px 0}.sub{color:var(--ink2)}.muted{color:var(--muted);font-size:13px}
section{background:var(--surface);border:1px solid var(--grid);border-radius:12px;padding:20px;margin-top:16px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:14px}
.tile{border:1px solid var(--grid);border-radius:10px;padding:12px}.tile b{display:block;font-size:26px;line-height:1.15}
.tile span{font-size:13px;color:var(--ink2)}.tile i{display:block;font-style:normal;font-size:12px;color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
th{font-weight:600;color:var(--ink2);font-size:12px;text-transform:uppercase;letter-spacing:.03em}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.scroll{overflow-x:auto}.bar{background:transparent;height:14px;min-width:120px;position:relative}
.bar>span{display:block;height:100%;background:var(--s1);border-radius:0 4px 4px 0;min-width:2px}
.stack{display:flex;gap:2px;height:14px;min-width:140px}.stack>span{display:block;height:100%;border-radius:2px;min-width:2px}
.range{position:relative;height:14px;min-width:140px;border-left:1px solid var(--axis)}.range>s{position:absolute;top:6px;height:2px;background:var(--s1)}
.range>u{position:absolute;top:2px;width:10px;height:10px;margin-left:-5px;border-radius:50%;background:var(--s1);border:2px solid var(--surface)}
.dv{position:relative;height:14px;min-width:160px}.dv>span{position:absolute;top:0;height:100%;background:var(--s1);border-radius:0 4px 4px 0}
.dv>span.neg{background:var(--muted);border-radius:4px 0 0 4px}.dv>em{position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:var(--axis)}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--ink2);margin:8px 0}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
.pill{display:inline-block;font-size:12px;font-weight:600;padding:1px 8px;border-radius:999px;border:1px solid var(--grid);white-space:nowrap}
.pill.good{color:var(--goodtx)}.pill.bad{color:var(--crit)}.pill.mid{color:var(--ink2)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}.card{border:1px solid var(--grid);border-radius:10px;padding:12px}
blockquote{margin:8px 0;padding-left:10px;border-left:3px solid var(--axis);color:var(--ink2)}details{border-top:1px solid var(--grid);padding:8px 0}
summary{cursor:pointer}code{font-size:13px;background:var(--page);padding:1px 5px;border-radius:4px}ul{margin:6px 0;padding-left:20px}
.callout{border-left:3px solid var(--s1);padding:8px 12px;background:var(--page);border-radius:0 8px 8px 0;margin:10px 0}
"""
GAP_PILL = "<span class='pill bad'>gap</span>"
OPEN_PILL = "<span class='pill mid'>open</span>"
RCOL = {"effort": "var(--s1)", "confusion": "var(--s2)", "trust": "var(--s3)", "fatigue": "var(--s4)", "low_motivation": "var(--s5)",
        "out_of_time": "var(--s6)", "blocked": "var(--s7)", "error": "var(--s8)", "waiting": "var(--s9)", "observed": "var(--muted)"}


def e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def pct(x, d=0) -> str:
    return f"{100 * x:.{d}f}%"


def rng_txt(iv, time=False) -> str:
    if time:
        return f"{iv['p5']:.0f}–{iv['p95']:.0f}s"
    d = 1 if iv["p95"] < 0.1 else 0   # small shares need a decimal or the range reads as one number
    return f"{100 * iv['p5']:.{d}f}–{100 * iv['p95']:.{d}f}%"


def _bar(v, title="") -> str:
    return f'<div class="bar" title="{e(title)}"><span style="width:{max(0.0, min(1.0, v)) * 100:.1f}%"></span></div>'


def _range(iv, title="", scale=1.0) -> str:
    lo, mid, hi = (max(0.0, min(1.0, iv[k] / scale)) * 100 for k in ("p5", "p50", "p95"))
    return (f'<div class="range" title="{e(title)}"><s style="left:{lo:.1f}%;width:{max(0.5, hi - lo):.1f}%"></s>'
            f'<u style="left:{mid:.1f}%"></u></div>')


def _diverge(v, scale, title="") -> str:
    w = min(50.0, abs(v) / scale * 50.0) if scale else 0
    if v >= 0:
        span = f'<span style="left:50%;width:{w:.1f}%"></span>'
    else:
        span = f'<span class="neg" style="left:{50 - w:.1f}%;width:{w:.1f}%"></span>'
    return f'<div class="dv" title="{e(title)}"><em></em>{span}</div>'


def _verdict_pill(v) -> str:
    cls = {"supported": "good", "better": "good", "higher": "good", "contradicted": "bad", "worse": "bad", "lower": "bad"}.get(v, "mid")
    return f'<span class="pill {cls}">{e(v)}</span>'


def _sev_pill(s) -> str:
    cls = {"high": "bad", "error": "bad", "warn": "bad"}.get(s, "mid")
    return f'<span class="pill {cls}">{e(s)}</span>'


def count_txt(vol, share) -> str:
    """A share of the eligible population as a count per period, e.g. 'about 24 a week'."""
    n = vol["eligible"] * share
    num = f"{n:,.0f}" if n >= 10 else f"{n:.1f}"
    return f"about {num} a {vol['per']}"


def _ends_table(rows, ends, names, vol) -> list:
    """Per-outcome effect of each variant or scenario, in points of the eligible population."""
    P = ["<h3>Effect on each way of finishing</h3><p class='sub'>Change in the share of everyone eligible who ends at each outcome.</p>"
         "<div class='scroll'><table><tr><th></th>" + "".join(f"<th class='n'>{e(names.get(s, s))}</th>" for s in ends) + "</tr>"]
    for v in rows:
        cells = []
        for s in ends:
            x = (v.get("ends") or {}).get(s)
            if not x:
                cells.append("<td class='n'>—</td>")
                continue
            extra = f"<div class='muted'>{e(count_txt(vol, x['value']['p50']))}</div>" if vol else ""
            cells.append(f"<td class='n'>{100 * x['diff']['p50']:+.1f} pts<div class='muted'>now {pct(x['value']['p50'], 1)}</div>{extra}</td>")
        P.append(f"<tr><td><b>{e(v['name'])}</b></td>{''.join(cells)}</tr>")
    P.append("</table></div>")
    return P


def headline(summary: dict) -> list:
    """Plain-language findings, most important first. Shared by HTML and Markdown."""
    out = []
    ov = summary["replication"]["overall"]
    vol = summary.get("volume")
    who = vol["unit"] if vol else "eligible users"
    out.append(f"Out of 100 {who}, about {100 * ov['adoption_rate']['p50']:.{1 if ov['adoption_rate']['p50'] < 0.1 else 0}f} are predicted to finish "
               f"(range {rng_txt(ov['adoption_rate'])}).")
    if vol:
        out.append(f"At {vol['eligible']:,.0f} {vol['unit']} a {vol['per']}, that is {count_txt(vol, ov['adoption_rate']['p50'])} "
                   f"(range {vol['eligible'] * ov['adoption_rate']['p5']:,.0f} to {vol['eligible'] * ov['adoption_rate']['p95']:,.0f}).")
    split = summary.get("outcome_split") or []
    if len(split) > 1 and summary["outcomes"]["success"]:
        parts = [f"{pct(r['share_of_finishers'])} at “{r['name']}”" for r in sorted(split, key=lambda r: -r["users"]) if r["users"]]
        out.append("Finishers end in different places: " + ", ".join(parts) + ".")
    fun = [r for r in summary["funnel"] if r["type"] != "success" and r["lost"] > 0]
    if fun:
        worst = max(fun, key=lambda r: r["lost"])
        starters = summary["metrics"]["entered"] or 1
        if worst["blocked"] >= max(worst["abandoned"], worst["error_exit"]):
            why = "they could not proceed (blocked)"
        elif worst["error_exit"] >= worst["abandoned"]:
            why = "an error stopped them"
        else:
            why = REASON_PHRASE.get(worst["top_reason"], "")
        out.append(f"The biggest loss is at “{worst['name']}”: {pct(worst['lost'] / starters)} of everyone who started leaves there"
                   + (f", mostly because {why}." if why else "."))
    never = summary["outcomes"]["never_saw"] / max(1, summary["users"])
    if never >= 0.4:
        out.append(f"{pct(never)} of eligible users never start: they do not see the entry point, or see it and pass. Discovery, not the flow, caps adoption.")
    levers = [l for l in summary["levers"] if not l["within_noise"] and l["adoption_delta"] > 0]
    if levers:
        out.append(f"Best single fix: {levers[0]['lever']} (+{100 * levers[0]['adoption_delta']:.1f} points of adoption).")
    gaps = [c for c in summary["edge_cases"] if c["status"] in ("gap", "open") and c.get("severity") == "high"]
    if gaps:
        confirmed = sum(1 for c in gaps if c["status"] == "gap")
        out.append(f"{len(gaps)} high-severity edge cases are not covered by the spec" + (f" ({confirmed} confirmed in review)." if confirmed else " (not yet reviewed)."))
    for h in summary["hypotheses"]:
        if h["verdict"] == "contradicted":
            out.append(f"Hypothesis {h['id']} looks wrong: “{h['text']}” (predicted {_fmt_metric(h['metric'], h['predicted']['p50'])}).")
    return out


def _fmt_metric(metric, v) -> str:
    return f"{v:.0f}s" if metric == "median_time_s" else pct(v)


def write_html(summary: dict, path) -> None:
    f, m = summary["feature"], summary["metrics"]
    rep = summary["replication"]
    ov = rep["overall"]
    P = []
    P.append(f"<h1>{e(f['name'])}</h1><p class='sub'>{e(f.get('summary', ''))}</p>")
    P.append(f"<p class='muted'>Shoal rehearsal · {summary['users']:,} synthetic users · seed {summary['seed']} · "
             f"{rep['reps']} replications · generated {e(summary['generated'])}"
             + (f" · variant: {e(summary['variant'])}" if summary.get("variant") else "") + "</p>")

    P.append("<section><h2>What the rehearsal says</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in headline(summary)) + "</ul>")
    P.append("<div class='tiles'>")
    for k in ("adoption_rate", "discovery_rate", "completion_rate", "error_rate", "blocked_rate", "median_time_s"):
        if k not in ov:
            continue
        t = k == "median_time_s"
        val = f"{ov[k]['p50']:.0f}s" if t else pct(ov[k]["p50"])
        P.append(f"<div class='tile'><span>{e(METRIC_LABELS[k])}</span><b>{val}</b><i>range {rng_txt(ov[k], t)}</i></div>")
    P.append("</div><p class='muted'>Each range is the 5th to 95th percentile across replications in which both the users and the guessed inputs vary.</p></section>")

    if summary["hypotheses"]:
        P.append("<section><h2>Your hypotheses</h2><div class='scroll'><table><tr><th>ID</th><th>Hypothesis</th><th>Test</th><th class='n'>Predicted</th><th class='n'>Range</th><th class='n'>Holds in</th><th>Verdict</th></tr>")
        for h in summary["hypotheses"]:
            t = h["metric"] == "median_time_s"
            tgt = f"{h['value']:.0f}s" if t else pct(h["value"])
            P.append(f"<tr><td>{e(h['id'])}</td><td>{e(h['text'])}</td><td><code>{e(h['metric'])} {e(h['op'])} {tgt}</code>"
                     f"{' · ' + e(h['segment']) if h['segment'] != 'all' else ''}</td><td class='n'>{_fmt_metric(h['metric'], h['predicted']['p50'])}</td>"
                     f"<td class='n'>{rng_txt(h['predicted'], t)}</td><td class='n'>{pct(h['holds_share'])} of runs</td><td>{_verdict_pill(h['verdict'])}</td></tr>")
        P.append("</table></div><p class='muted'>Supported = holds in at least 90% of replications. Contradicted = holds in 10% or fewer. Otherwise uncertain.</p></section>")

    # Funnel
    starters = m["entered"] or 1
    P.append("<section><h2>Funnel</h2><p class='sub'>Share of everyone who started that reaches each step.</p><div class='scroll'><table>"
             "<tr><th>Step</th><th style='width:32%'>Reached</th><th class='n'>Reached</th><th class='n'>Carried on</th><th class='n'>Left here</th><th>Main reason</th><th class='n'>Median time</th></tr>")
    for r in summary["funnel"]:
        reason = REASON_LABEL.get(r["top_reason"], "") if r["lost"] else ""
        if r["blocked"] > r["abandoned"]:
            reason = "Blocked"
        elif r["error_exit"] > r["abandoned"]:
            reason = "Error"
        names = {x["step"]: x["name"] for x in summary["funnel"]}
        onward = (f"<div class='muted'>{pct(r['diverted'] / r['entered'])} go on to “{e(names.get(r['otherwise'], r['otherwise']))}”</div>"
                  if r.get("diverted") and r["entered"] else "")
        P.append(f"<tr><td>{e(r['name'])}<div class='muted'>{e(r['type'])}</div></td><td>{_bar(r['share_of_starters'], f'{r_entered(r)} users')}</td>"
                 f"<td class='n'>{pct(r['share_of_starters'])}</td><td class='n'>{'—' if r['type'] == 'success' else pct(r['continue_rate'], 1 if r['continue_rate'] < 0.1 else 0)}{onward}</td>"
                 f"<td class='n'>{pct(r['lost'] / starters, 1) if r['lost'] else '—'}</td><td>{e(reason)}</td><td class='n'>{r['median_time_s']:.0f}s</td></tr>")
    P.append("</table></div>")
    split = summary.get("outcome_split") or []
    vol = summary.get("volume")
    if len(split) > 1:
        P.append("<h3>How finishers end</h3><p class='sub'>This flow can end well in more than one way. Shares are of everyone who started.</p><div class='scroll'><table>"
                 "<tr><th>Outcome</th><th style='width:28%'>Share of starters</th><th class='n'>Share</th><th class='n'>Range</th>"
                 + (f"<th class='n'>Per {e(vol['per'])}</th>" if vol else "") + "".join(f"<th class='n'>{e(g['name'])}</th>" for g in summary["segments"]) + "</tr>")
        for r in split:
            P.append(f"<tr><td>{e(r['name'])}</td><td>{_bar(r['share_of_starters'])}</td><td class='n'>{pct(r['share_of_starters'], 1)}</td>"
                     f"<td class='n'>{rng_txt(r['range']) if r.get('range') else '—'}</td>"
                     + (f"<td class='n'>{vol['eligible'] * r['share_of_eligible']:,.0f}</td>" if vol else "")
                     + "".join(f"<td class='n'>{pct(r['segments'].get(g['id'], 0))}</td>" for g in summary["segments"]) + "</tr>")
        P.append("</table></div><p class='muted'>Segment columns: share of that segment's starters who end at the outcome.</p>")
    P.append("</section>")

    # Why people leave
    lossy = [r for r in summary["funnel"] if r["lost"] > 0]
    if lossy:
        mx = max(r["lost"] for r in lossy)
        used = [k for k in REASON_ORDER if any((_loss_parts(r).get(k, 0)) for r in lossy)]
        P.append("<section><h2>Where and why people leave</h2><div class='legend'>" +
                 "".join(f"<span><i style='background:{RCOL[k]}'></i>{e(REASON_LABEL[k])}</span>" for k in used) + "</div><div class='scroll'><table>"
                 "<tr><th>Step</th><th style='width:45%'>Users lost</th><th class='n'>Lost</th><th class='n'>Errors</th><th class='n'>Retries</th></tr>")
        for r in sorted(lossy, key=lambda r: -r["lost"]):
            parts = _loss_parts(r)
            segs = "".join(f"<span title='{e(REASON_LABEL[k])}: {v}' style='background:{RCOL[k]};width:{v / mx * 100:.1f}%'></span>" for k, v in parts.items() if v)
            P.append(f"<tr><td>{e(r['name'])}</td><td><div class='stack'>{segs}</div></td><td class='n'>{r['lost']:,}</td><td class='n'>{r['errors']:,}</td><td class='n'>{r['retries']:,}</td></tr>")
        P.append("</table></div></section>")

    # Segments
    top = max(rep["segments"][g["id"]]["adoption_rate"]["p95"] for g in summary["segments"]) or 1.0
    top = min(1.0, max(0.05, round(top * 1.2 + 0.049, 1)))
    P.append(f"<section><h2>By kind of user</h2><div class='scroll'><table><tr><th>Segment</th><th class='n'>Share</th><th style='width:28%'>Adoption, 0 to {pct(top)}</th>"
             "<th class='n'>Adoption</th><th class='n'>Discovery</th><th class='n'>Completion</th><th class='n'>Errors</th><th class='n'>Blocked</th><th class='n'>Time</th></tr>")
    for g in summary["segments"]:
        iv = rep["segments"][g["id"]]
        P.append(f"<tr><td>{e(g['name'])}</td><td class='n'>{pct(g['share'])}</td><td>{_range(iv['adoption_rate'], rng_txt(iv['adoption_rate']), top)}</td>"
                 f"<td class='n'>{pct(iv['adoption_rate']['p50'])}</td><td class='n'>{pct(iv['discovery_rate']['p50'])}</td><td class='n'>{pct(iv['completion_rate']['p50'])}</td>"
                 f"<td class='n'>{pct(iv['error_rate']['p50'])}</td><td class='n'>{pct(iv['blocked_rate']['p50'])}</td><td class='n'>{iv['median_time_s']['p50']:.0f}s</td></tr>")
    P.append("</table></div>")
    if summary["contexts"]:
        P.append("<h3>By situation</h3><div class='scroll'><table><tr><th>Situation</th><th class='n'>Users</th><th class='n'>Started</th><th style='width:30%'>Finished, of those who started</th><th class='n'>Finished</th></tr>")
        for dim, vals in summary["contexts"].items():
            for val, c in sorted(vals.items(), key=lambda kv: -kv[1]["n"]):
                cr = c["success"] / c["entered"] if c["entered"] else 0
                P.append(f"<tr><td>{e(dim)}: {e(val)}</td><td class='n'>{c['n']:,}</td><td class='n'>{c['entered']:,}</td><td>{_bar(cr)}</td><td class='n'>{pct(cr)}</td></tr>")
        P.append("</table></div>")
    if any("repeat_d7" in rep["segments"][g["id"]] for g in summary["segments"]):
        keys = [k for k in ("repeat_d1", "repeat_d7", "repeat_d30") if k in ov]
        P.append("<h3>Coming back (of those who finished)</h3><p>" + " · ".join(f"{e(METRIC_LABELS[k])}: <b>{pct(ov[k]['p50'])}</b> ({rng_txt(ov[k])})" for k in keys) + "</p>")
    P.append("</section>")

    # Levers
    if summary["levers"]:
        scale = max(abs(l["adoption_delta"]) for l in summary["levers"]) or 1
        P.append("<section><h2>Biggest levers</h2><p class='sub'>One change at a time: how many points of adoption each would add.</p><div class='scroll'><table>"
                 "<tr><th>Change</th><th style='width:34%'>Effect on adoption</th><th class='n'>Adoption</th><th class='n'>Completion</th><th></th></tr>")
        for l in summary["levers"][:12]:
            P.append(f"<tr><td>{e(l['lever'])}</td><td>{_diverge(l['adoption_delta'], scale)}</td><td class='n'>{100 * l['adoption_delta']:+.1f} pts</td>"
                     f"<td class='n'>{100 * l['completion_delta']:+.1f} pts</td><td class='muted'>{'within noise' if l['within_noise'] else ''}</td></tr>")
        P.append("</table></div></section>")

    # Variants
    if summary.get("variants"):
        P.append("<section><h2>Variants against the base design</h2><div class='scroll'><table><tr><th style='width:38%'>Variant</th><th class='n'>Adoption change</th><th class='n'>Range</th>"
                 "<th class='n'>Completion change</th><th class='n'>Time change</th><th class='n'>Beats base in</th><th>Verdict</th></tr>")
        for v in summary["variants"]:
            d = v["diff"]
            P.append(f"<tr><td><b>{e(v['name'])}</b><div class='muted'>{e(v['note'])}</div></td><td class='n'>{100 * d['adoption_rate']['p50']:+.1f} pts</td>"
                     f"<td class='n'>{100 * d['adoption_rate']['p5']:+.1f} to {100 * d['adoption_rate']['p95']:+.1f}</td><td class='n'>{100 * d['completion_rate']['p50']:+.1f} pts</td>"
                     f"<td class='n'>{d['median_time_s']['p50']:+.0f}s</td><td class='n'>{pct(v['wins_share'])} of runs</td><td>{_verdict_pill(v['verdict'])}</td></tr>")
        P.append("</table></div>")
        names = {r["step"]: r["name"] for r in summary["funnel"]}
        ends = [s for v in summary["variants"] for s in (v.get("ends") or {})]
        ends = list(dict.fromkeys(ends))
        if len(ends) > 1:
            P += _ends_table(summary["variants"], ends, names, vol)
        P.append("</section>")

    if summary.get("scenarios"):
        P.append("<section><h2>If the guesses are wrong</h2><p class='sub'>The same design under other assumptions about users and the world. "
                 "A design decision should hold across these rows.</p><div class='scroll'><table><tr><th style='width:38%'>Scenario</th><th class='n'>Adoption</th><th class='n'>Range</th>"
                 + (f"<th class='n'>Per {e(vol['per'])}</th>" if vol else "") + "<th class='n'>Change from base</th><th class='n'>Completion</th><th>Against base</th></tr>")
        P.append(f"<tr><td><b>As modelled</b></td><td class='n'>{pct(ov['adoption_rate']['p50'], 1)}</td><td class='n'>{rng_txt(ov['adoption_rate'])}</td>"
                 + (f"<td class='n'>{vol['eligible'] * ov['adoption_rate']['p50']:,.0f}</td>" if vol else "")
                 + f"<td class='n'>—</td><td class='n'>{pct(ov['completion_rate']['p50'])}</td><td></td></tr>")
        for v in summary["scenarios"]:
            a, d = v["value"]["adoption_rate"], v["diff"]["adoption_rate"]
            P.append(f"<tr><td><b>{e(v['name'])}</b><div class='muted'>{e(v['note'])}</div></td><td class='n'>{pct(a['p50'], 1)}</td><td class='n'>{rng_txt(a)}</td>"
                     + (f"<td class='n'>{vol['eligible'] * a['p50']:,.0f}</td>" if vol else "")
                     + f"<td class='n'>{100 * d['p50']:+.1f} pts</td><td class='n'>{pct(v['value']['completion_rate']['p50'])}</td><td>{_verdict_pill(v['verdict'])}</td></tr>")
        P.append("</table></div>")
        names = {r["step"]: r["name"] for r in summary["funnel"]}
        ends = list(dict.fromkeys(s for v in summary["scenarios"] for s in (v.get("ends") or {})))
        if len(ends) > 1:
            P += _ends_table(summary["scenarios"], ends, names, vol)
        P.append("</section>")

    # Qualitative
    q = summary.get("qualitative")
    if q:
        P.append("<section><h2>What the synthetic users said</h2><p class='muted'>Think-aloud walkthroughs played by a language model in persona. Use them to find problems, not to count them.</p>")
        if q.get("themes"):
            P.append("<h3>Themes</h3><div class='cards'>" + "".join(
                f"<div class='card'><b>{e(t.get('title'))}</b><p>{e(t.get('evidence'))}</p>" + (f"<p class='muted'>Steps: {e(', '.join(t.get('steps', [])))}</p>" if t.get("steps") else "")
                + (f"<p><b>Do:</b> {e(t['recommendation'])}</p>" if t.get("recommendation") else "") + "</div>" for t in q["themes"]) + "</div>")
        if summary.get("triangulation"):
            P.append("<h3>Where numbers and voices agree</h3><div class='scroll'><table><tr><th>Step</th><th class='n'>Simulated loss</th><th class='n'>Sessions with trouble here</th><th>Read</th></tr>")
            for t in summary["triangulation"]:
                P.append(f"<tr><td>{e(t['name'])}</td><td class='n'>{pct(t['loss_share'], 1)}</td><td class='n'>{t['mentions']} of {t['sessions']}</td><td>{e(t['read'])}</td></tr>")
            P.append("</table></div>")
        if q.get("sessions"):
            P.append("<h3>Sessions</h3>")
            for s in q["sessions"]:
                moments = "".join(f"<li><b>{e(mo.get('step'))}</b> · {e(mo.get('kind'))}: {e(mo.get('thought'))}</li>" for mo in s.get("moments", []))
                P.append(f"<details><summary><b>{e(s.get('persona'))}</b> · {e(s.get('context', ''))} · {e(OUTCOME_LABEL.get(s.get('outcome'), s.get('outcome')))}"
                         + (f" at {e(s['at'])}" if s.get("at") and s.get("outcome") != "success" else "") + f"</summary><p class='muted'>Goal: {e(s.get('goal'))}</p>"
                         + (f"<blockquote>{e(s['quote'])}</blockquote>" if s.get("quote") else "") + f"<ul>{moments}</ul>"
                         + (f"<p><b>Unmet need:</b> {e(s['unmet_need'])}</p>" if s.get("unmet_need") else "") + "</details>")
        if q.get("spec_gaps"):
            P.append("<h3>Gaps in the spec</h3><ul>" + "".join(f"<li>{_sev_pill(g.get('severity', 'med'))} <b>{e(g.get('title'))}</b>: {e(g.get('detail'))}</li>" for g in q["spec_gaps"]) + "</ul>")
        P.append("</section>")

    # Design findings
    design = [x for x in summary["lint"] if x["kind"] == "design"]
    if design:
        P.append("<section><h2>Design gaps found by reading the flow</h2><p class='sub'>Checked without simulating anything: these hold however users behave.</p><div class='scroll'><table><tr><th></th><th>Finding</th><th>Fix</th></tr>")
        for x in design:
            P.append(f"<tr><td>{_sev_pill(x['level'])}</td><td>{e(x['message'])}</td><td>{e(x.get('fix') or '')}</td></tr>")
        P.append("</table></div></section>")

    # Edge cases
    ec = summary["edge_cases"]
    n_gap, n_open = sum(c["status"] == "gap" for c in ec), sum(c["status"] == "open" for c in ec)
    n_ok = sum(c["status"] in ("handled", "not_applicable") for c in ec)
    P.append(f"<section><h2>Edge cases</h2><p class='sub'>{len(ec)} situations checked: {n_gap} confirmed gaps, {n_open} not addressed by the spec, {n_ok} handled or not applicable.</p>")
    shown = [c for c in ec if c["status"] in ("gap", "open")]
    P.append("<div class='scroll'><table><tr><th></th><th>Where</th><th>Situation</th><th>Question the spec must answer</th><th>Status</th></tr>")
    for c in shown[:60]:
        extra = (f"<div class='muted'>Expected: {e(c['expected'])}</div>" if c.get("expected") else "") + (f"<div class='muted'>{e(c['note'])}</div>" if c.get("note") else "")
        P.append(f"<tr><td>{_sev_pill(c.get('severity', 'med'))}</td><td>{e(c['step_name'])}</td><td>{e(c['title'])}</td><td>{e(c['question'])}{extra}</td>"
                 f"<td>{GAP_PILL if c['status'] == 'gap' else OPEN_PILL}</td></tr>")
    P.append("</table></div>")
    if len(shown) > 60:
        P.append(f"<p class='muted'>{len(shown) - 60} more in edge_cases.json.</p>")
    if summary.get("combinations"):
        P.append("<h3>Combinations to test</h3><p class='sub'>The smallest set in which every pair of conditions appears together at least once.</p><div class='scroll'><table><tr><th>ID</th><th>Combination</th><th class='n'>Share of users</th></tr>")
        for c in summary["combinations"]:
            P.append(f"<tr><td>{e(c['id'])}</td><td>{e(c['title'])}</td><td class='n'>{'≤ ' + pct(c['share'], 1) if c.get('share') is not None else '—'}</td></tr>")
        P.append("</table></div>")
    P.append("</section>")

    # Instrumentation + watchlist
    P.append("<section><h2>Tracking plan and launch watchlist</h2><p class='sub'>The events needed to see this funnel for real, and the range each step should land in. "
             "A real number outside its range means the model is wrong there: look first.</p><div class='scroll'><table>"
             "<tr><th>Step</th><th>Event</th><th>Error event</th><th style='width:24%'>Expected carry-on rate</th><th class='n'>Range</th></tr>")
    wl = {w["step"]: w for w in summary["watchlist"]}
    for r in summary["instrumentation"]:
        w = wl.get(r["step"])
        ev = ", ".join(f"<code>{e(x)}</code>" for x in r["events"]) if r["events"] else "<span class='pill bad'>missing</span>"
        P.append(f"<tr><td>{e(r['name'])}</td><td>{ev}</td><td>{'<code>' + e(r['error_event']) + '</code>' if r['error_event'] else '—'}</td>"
                 f"<td>{_range(w['expected']) if w else ''}</td><td class='n'>{rng_txt(w['expected']) + (' · calibrated' if w['calibrated'] else '') if w else '—'}</td></tr>")
    P.append("</table></div></section>")

    # Sample sessions
    if summary.get("sessions"):
        P.append("<section><h2>Sample simulated journeys</h2><p class='muted'>A few individual synthetic users, to make the numbers concrete.</p>")
        for s in summary["sessions"]:
            trail = " → ".join(e(p["step"]) + (f" <span class='muted'>({e(p['note'])})</span>" if p.get("note") else "") for p in s["path"])
            tr = ", ".join(f"{k} {v}" for k, v in s["traits"].items())
            cx = ", ".join(f"{k}: {v}" for k, v in s["context"].items())
            P.append(f"<details><summary>User {s['user']} · {e(s['segment'])} · <b>{e(OUTCOME_LABEL.get(s['outcome'], s['outcome']))}</b>"
                     + (f" at {e(s['at'])}" if s["outcome"] not in ("success", "never_saw") else "") + f" · {s['seconds']}s</summary>"
                     f"<p class='muted'>{e(tr)} · {e(cx)}</p><p>{trail or 'Never saw the feature.'}</p></details>")
        P.append("</section>")

    P.append("<section><h2>How to read this, and its limits</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in LIMITS) + "</ul>"
             "<p class='muted'>Method: each synthetic user gets traits (motivation, skill, patience, trust), a situation and capabilities drawn from their segment, "
             "then walks the flow. At each step the chance of carrying on rises with motivation, visible value and trust and falls with effort, unclear screens, errors and fatigue. "
             "All formulas are in <code>shoal/sim.py</code>; the model used is saved next to this report as <code>model.json</code>.</p></section>")

    doc = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Shoal · {e(f['name'])}</title><style>{CSS}</style></head><body><main>{''.join(P)}</main></body></html>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)


def r_entered(r) -> str:
    return f"{r['entered']:,}"


def _loss_parts(r) -> dict:
    parts = {k: r["reasons"].get(k, 0) for k in REASON_ORDER if k in r["reasons"]}
    if r["blocked"]:
        parts["blocked"] = r["blocked"]
    if r["error_exit"]:
        parts["error"] = r["error_exit"]
    return parts


def write_md(summary: dict, path) -> None:
    f, rep = summary["feature"], summary["replication"]
    ov = rep["overall"]
    L = [f"# Shoal rehearsal: {f['name']}", "", f"{summary['users']:,} synthetic users, seed {summary['seed']}, {rep['reps']} replications, {summary['generated']}.", "",
         "## What it says", ""] + [f"- {x}" for x in headline(summary)] + ["", "## Headline numbers (predicted)", "", "| Metric | Predicted | Range |", "|---|---:|---:|"]
    for k in ("adoption_rate", "discovery_rate", "completion_rate", "error_rate", "blocked_rate", "median_time_s"):
        if k in ov:
            t = k == "median_time_s"
            L.append(f"| {METRIC_LABELS[k]} | {_fmt_metric(k, ov[k]['p50'])} | {rng_txt(ov[k], t)} |")
    if summary["hypotheses"]:
        L += ["", "## Hypotheses", "", "| ID | Hypothesis | Predicted | Verdict |", "|---|---|---:|---|"]
        L += [f"| {h['id']} | {h['text']} | {_fmt_metric(h['metric'], h['predicted']['p50'])} | {h['verdict']} |" for h in summary["hypotheses"]]
    starters = summary["metrics"]["entered"] or 1
    L += ["", "## Funnel", "", "| Step | Reached | Carried on | Left here | Main reason |", "|---|---:|---:|---:|---|"]
    for r in summary["funnel"]:
        L.append(f"| {r['name']} | {pct(r['share_of_starters'])} | {'—' if r['type'] == 'success' else pct(r['continue_rate'])} | "
                 f"{pct(r['lost'] / starters, 1) if r['lost'] else '—'} | {REASON_LABEL.get(r['top_reason'], '') if r['lost'] else ''} |")
    if summary["levers"]:
        L += ["", "## Biggest levers", "", "| Change | Adoption |", "|---|---:|"]
        L += [f"| {l['lever']} | {100 * l['adoption_delta']:+.1f} pts{' (within noise)' if l['within_noise'] else ''} |" for l in summary["levers"][:8]]
    if summary.get("variants"):
        L += ["", "## Variants", "", "| Variant | Adoption change | Beats base in | Verdict |", "|---|---:|---:|---|"]
        L += [f"| {v['name']} | {100 * v['diff']['adoption_rate']['p50']:+.1f} pts | {pct(v['wins_share'])} | {v['verdict']} |" for v in summary["variants"]]
    split = summary.get("outcome_split") or []
    if len(split) > 1:
        L += ["", "## How finishers end", "", "| Outcome | Share of starters | Range |", "|---|---:|---:|"]
        L += [f"| {r['name']} | {pct(r['share_of_starters'], 1)} | {rng_txt(r['range']) if r.get('range') else '—'} |" for r in split]
    if summary.get("scenarios"):
        L += ["", "## If the guesses are wrong", "", "| Scenario | Adoption | Range | Change from base |", "|---|---:|---:|---:|",
              f"| As modelled | {pct(ov['adoption_rate']['p50'], 1)} | {rng_txt(ov['adoption_rate'])} | — |"]
        L += [f"| {v['name']} | {pct(v['value']['adoption_rate']['p50'], 1)} | {rng_txt(v['value']['adoption_rate'])} | {100 * v['diff']['adoption_rate']['p50']:+.1f} pts |"
              for v in summary["scenarios"]]
    design = [x for x in summary["lint"] if x["kind"] == "design" and x["level"] == "warn"]
    if design:
        L += ["", "## Design gaps", ""] + [f"- {x['message']}" + (f" Fix: {x['fix']}" if x.get("fix") else "") for x in design]
    hi = [c for c in summary["edge_cases"] if c["status"] in ("gap", "open") and c.get("severity") == "high"]
    if hi:
        L += ["", f"## High-severity edge cases not covered ({len(hi)})", ""] + [f"- [{c['status']}] {c['step_name']}: {c['title']}. {c['question']}" for c in hi[:25]]
    L += ["", "## Limits", ""] + [f"- {x}" for x in LIMITS] + [""]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


def write_json(obj, path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False, default=str)
        fh.write("\n")
