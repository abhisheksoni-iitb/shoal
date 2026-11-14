"""Local web app: paste a feature model, run a rehearsal, browse and compare reports.
Binds to 127.0.0.1 only. Standard library only."""

from __future__ import annotations

import html
import json
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import model as model_mod, pipeline
from .report import CSS, pct

HERE = Path(__file__).resolve().parent
TYPES = {".html": "text/html; charset=utf-8", ".json": "application/json", ".md": "text/plain; charset=utf-8",
         ".jsonl": "text/plain; charset=utf-8", ".csv": "text/csv"}


def find_runs(root: Path) -> list:
    runs = []
    for p in root.rglob("summary.json"):
        if len(p.relative_to(root).parts) > 6:
            continue
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "shoal" not in s:
            continue
        runs.append({"rel": str(p.parent.relative_to(root)), "s": s})
    runs.sort(key=lambda r: r["s"].get("generated", ""), reverse=True)
    return runs


def page(title: str, body: str) -> bytes:
    extra = ("textarea{width:100%;min-height:340px;font:13px/1.45 ui-monospace,Menlo,monospace;background:var(--page);color:var(--ink);border:1px solid var(--grid);border-radius:8px;padding:10px}"
             "input,button,select{font:inherit;padding:7px 10px;border-radius:8px;border:1px solid var(--axis);background:var(--surface);color:var(--ink)}"
             "button{background:var(--s1);border-color:var(--s1);color:#fff;font-weight:600;cursor:pointer}a{color:var(--s1)}"
             ".row{display:flex;gap:12px;flex-wrap:wrap;align-items:end;margin:10px 0}label{display:block;font-size:12px;color:var(--ink2)}nav{margin-bottom:8px}")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{CSS}{extra}</style></head><body><main><nav><a href='/'>Shoal</a> · <a href='/new'>New rehearsal</a></nav>{body}</main></body></html>").encode()


class Handler(BaseHTTPRequestHandler):
    root: Path = Path(".")

    def log_message(self, *args):
        pass

    def _send(self, code, body: bytes, ctype="text/html; charset=utf-8", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        if url.path == "/":
            return self._send(200, self._index())
        if url.path == "/new":
            return self._send(200, self._new())
        if url.path == "/compare":
            return self._send(200, self._compare(q.get("a", [""])[0], q.get("b", [""])[0]))
        if url.path.startswith("/view/"):
            rel = urllib.parse.unquote(url.path[6:])
            target = (self.root / rel).resolve()
            if self.root not in target.parents or not target.is_file() or target.suffix not in TYPES:
                return self._send(404, page("Not found", "<h1>Not found</h1>"))
            return self._send(200, target.read_bytes(), TYPES[target.suffix])
        self._send(404, page("Not found", "<h1>Not found</h1>"))

    def do_POST(self):
        if self.path != "/run":
            return self._send(404, page("Not found", "<h1>Not found</h1>"))
        if self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
            return self._send(403, page("Forbidden", "<h1>Forbidden</h1>"))
        length = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        text = form.get("model", [""])[0]
        try:
            m = model_mod.normalise(json.loads(text))
            users = max(100, min(50000, int(form.get("users", ["5000"])[0])))
            seed = int(form.get("seed", ["7"])[0])
            fid = "".join(c if c.isalnum() or c in "-_" else "-" for c in m["feature"]["id"])[:60] or "feature"
            out = self.root / fid / "runs" / time.strftime("%Y%m%d-%H%M%S")
            pipeline.run(m, out, users=users, seed=seed, quick=bool(form.get("quick")))
        except pipeline.LintFailed as exc:
            items = "".join(f"<li>{html.escape(f['message'])}</li>" for f in exc.findings if f["level"] == "error")
            return self._send(400, self._new(text, f"<div class='callout'><b>The model has errors.</b><ul>{items}</ul></div>"))
        except (ValueError, model_mod.ModelError) as exc:
            return self._send(400, self._new(text, f"<div class='callout'><b>Could not read the model:</b> {html.escape(str(exc))}</div>"))
        rel = urllib.parse.quote(str(out.relative_to(self.root)))
        self._send(303, b"", headers={"Location": f"/view/{rel}/report.html"})

    def _index(self) -> bytes:
        runs = find_runs(self.root)
        if not runs:
            body = "<h1>Shoal</h1><section><p>No rehearsals yet in this folder.</p><p><a href='/new'>Run the first one</a></p></section>"
            return page("Shoal", body)
        rows = []
        for r in runs:
            s, ov = r["s"], r["s"]["replication"]["overall"]
            rel = urllib.parse.quote(r["rel"])
            gaps = sum(1 for c in s["edge_cases"] if c["status"] in ("gap", "open") and c.get("severity") == "high")
            rows.append(f"<tr><td><input type='checkbox' name='pick' value='{html.escape(r['rel'])}'></td><td><a href='/view/{rel}/report.html'>{html.escape(s['feature']['name'])}</a>"
                        f"{' · ' + html.escape(s['variant']) if s.get('variant') else ''}<div class='muted'>{html.escape(r['rel'])}</div></td><td>{html.escape(s['generated'])}</td>"
                        f"<td class='n'>{pct(ov['adoption_rate']['p50'])}</td><td class='n'>{pct(ov['discovery_rate']['p50'])}</td><td class='n'>{pct(ov['completion_rate']['p50'])}</td>"
                        f"<td class='n'>{gaps}</td><td><a href='/view/{rel}/report.md'>md</a> · <a href='/view/{rel}/summary.json'>json</a></td></tr>")
        script = ("<script>function cmp(){var p=[...document.querySelectorAll('input[name=pick]:checked')].map(x=>x.value);"
                  "if(p.length!==2){alert('Tick exactly two runs to compare.');return}"
                  "location='/compare?a='+encodeURIComponent(p[0])+'&b='+encodeURIComponent(p[1])}</script>")
        body = ("<h1>Shoal</h1><p class='sub'>Rehearsals in this folder, newest first.</p><section><div class='scroll'><table><tr><th></th><th>Feature</th><th>When</th>"
                "<th class='n'>Adoption</th><th class='n'>Discovery</th><th class='n'>Completion</th><th class='n'>High-risk gaps</th><th>Files</th></tr>"
                + "".join(rows) + "</table></div><div class='row'><button onclick='cmp()'>Compare two</button></div></section>" + script)
        return page("Shoal", body)

    def _new(self, text: str = "", note: str = "") -> bytes:
        text = text or (HERE / "template.json").read_text(encoding="utf-8")
        body = (f"<h1>New rehearsal</h1>{note}<section><form method='post' action='/run'><label>Feature model (JSON)</label>"
                f"<textarea name='model' spellcheck='false'>{html.escape(text)}</textarea><div class='row'>"
                "<div><label>Synthetic users</label><input name='users' value='5000' size='7'></div>"
                "<div><label>Seed</label><input name='seed' value='7' size='5'></div>"
                "<div><label><input type='checkbox' name='quick' value='1'> Quick run</label></div>"
                "<div><button>Run rehearsal</button></div></div></form>"
                "<p class='muted'>A full run takes a few seconds. The model format is described in skill/shoal/references/feature-model.md.</p></section>")
        return page("New rehearsal", body)

    def _compare(self, a: str, b: str) -> bytes:
        runs = {r["rel"]: r["s"] for r in find_runs(self.root)}
        if a not in runs or b not in runs:
            return page("Compare", "<h1>Compare</h1><section><p>Pick two runs on the home page.</p></section>")
        sa, sb = runs[a], runs[b]
        rows = []
        for k, label in (("adoption_rate", "Adoption"), ("discovery_rate", "Discovery"), ("completion_rate", "Completion"),
                         ("error_rate", "Hit an error"), ("blocked_rate", "Blocked"), ("median_time_s", "Median time")):
            va, vb = sa["replication"]["overall"][k], sb["replication"]["overall"][k]
            if k == "median_time_s":
                cells = f"<td class='n'>{va['p50']:.0f}s</td><td class='n'>{vb['p50']:.0f}s</td><td class='n'>{vb['p50'] - va['p50']:+.0f}s</td>"
                overlap = not (va["p95"] < vb["p5"] or vb["p95"] < va["p5"])
            else:
                cells = f"<td class='n'>{pct(va['p50'], 1)}</td><td class='n'>{pct(vb['p50'], 1)}</td><td class='n'>{100 * (vb['p50'] - va['p50']):+.1f} pts</td>"
                overlap = not (va["p95"] < vb["p5"] or vb["p95"] < va["p5"])
            rows.append(f"<tr><td>{label}</td>{cells}<td>{'ranges overlap: not a clear difference' if overlap else 'clear difference'}</td></tr>")
        head = lambda s, rel: f"{html.escape(s['feature']['name'])}{' · ' + html.escape(s['variant']) if s.get('variant') else ''}<div class='muted'>{html.escape(rel)}</div>"
        body = (f"<h1>Compare</h1><section><div class='scroll'><table><tr><th>Metric</th><th class='n'>A: {head(sa, a)}</th><th class='n'>B: {head(sb, b)}</th><th class='n'>B − A</th><th>Read</th></tr>"
                + "".join(rows) + "</table></div><p class='muted'>For a fair test of two designs, define them as variants in one model: Shoal then runs them on the same users.</p></section>")
        return page("Compare", body)


def serve(root: Path, port: int = 8787) -> None:
    Handler.root = root
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Shoal is running at http://127.0.0.1:{port}  (folder: {root})\nCtrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
