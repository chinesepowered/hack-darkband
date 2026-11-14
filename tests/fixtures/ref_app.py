"""Reference CapyFinder used ONLY to test the Examiner (stdlib, no deps).

This is not the factory's output — the factory builds its own CapyFinder in a
separate workspace. Set REF_BUGS (comma-separated) to inject bugs:
  country_case   country filter is case-sensitive
  no_empty_state the "No capybaras here yet" text is missing
  stats_off      /api/stats total is off by one
"""

from __future__ import annotations

import html
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

TYPES = ["zoo", "onsen", "cafe", "sanctuary", "farm", "park"]


def load(path: Path) -> list[dict]:
    return sorted(json.loads(path.read_text()), key=lambda s: s["name"].lower())


def make_handler(spots: list[dict], bugs: set[str]):
    def filtered(q: str = "", country: str = "", type_: str = "", onsen: bool = False) -> list[dict]:
        out = spots
        if country:
            out = [s for s in out if (s["country"] == country if "country_case" in bugs
                                      else s["country"].lower() == country.lower())]
        if type_:
            out = [s for s in out if s["type"].lower() == type_.lower()]
        q = q.strip().lower()
        if q:
            out = [s for s in out if q in s["name"].lower() or q in s["city"].lower()]
        if onsen:
            out = [s for s in out if s["type"] == "onsen" or any(
                w in (s.get("capybara_experience") or "").lower() for w in ("hot spring", "onsen"))]
        return out

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet
            pass

        def _send(self, status: int, body: str, ctype: str = "application/json") -> None:
            data = body.encode()
            self.send_response(status)
            self.send_header("content-type", f"{ctype}; charset=utf-8")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json(self, status: int, obj) -> None:
            self._send(status, json.dumps(obj))

        def do_GET(self) -> None:  # noqa: N802
            u = urlparse(self.path)
            qs = {k: v[0] for k, v in parse_qs(u.query).items()}
            parts = [p for p in u.path.split("/") if p]
            if u.path == "/api/health":
                return self._json(200, {"ok": True, "spots": len(spots)})
            if u.path == "/api/spots":
                if qs.get("type") and qs["type"].lower() not in TYPES:
                    return self._json(400, {"error": f"unknown type {qs['type']}"})
                return self._json(200, filtered(qs.get("q", ""), qs.get("country", ""), qs.get("type", "")))
            if len(parts) == 3 and parts[:2] == ["api", "spots"]:
                hit = next((s for s in spots if s["id"] == parts[2]), None)
                return self._json(200, hit) if hit else self._json(404, {"error": "not found"})
            if u.path == "/api/stats":
                by_c: dict[str, int] = {}
                by_t: dict[str, int] = {}
                for s in spots:
                    by_c[s["country"]] = by_c.get(s["country"], 0) + 1
                    by_t[s["type"]] = by_t.get(s["type"], 0) + 1
                total = len(spots) + (1 if "stats_off" in bugs else 0)
                return self._json(200, {"total": total, "by_country": by_c, "by_type": by_t})
            if u.path == "/":
                return self._send(200, self._home(qs), "text/html")
            if len(parts) == 2 and parts[0] == "spots":
                hit = next((s for s in spots if s["id"] == parts[1]), None)
                if not hit:
                    return self._send(404, "<!doctype html><title>Not found</title><h1>Spot not found</h1>", "text/html")
                return self._send(200, self._detail(hit), "text/html")
            self._send(404, "<h1>Not found</h1>", "text/html")

        def _home(self, qs: dict[str, str]) -> str:
            onsen = qs.get("onsen") == "1"
            rows = filtered(qs.get("q", ""), qs.get("country", ""), qs.get("type", ""), onsen)
            countries = sorted({s["country"] for s in spots})
            e = html.escape
            opt = lambda v, label, cur: f'<option value="{e(v)}"{" selected" if v == cur else ""}>{e(label)}</option>'
            cards = "".join(
                f'<article data-testid="spot-card"><h2><a href="/spots/{e(s["id"])}">{e(s["name"])}</a></h2>'
                f'<p>{e(s["city"])}, {e(s["country"])} · {e(s["type"])}</p>'
                f'<a href="{e(s["source_url"])}" target="_blank" rel="noopener">Source</a></article>'
                for s in rows
            )
            empty = "" if rows or "no_empty_state" in bugs else "<p>No capybaras here yet</p>"
            latest = max((s.get("verified_on", "") for s in spots), default="")
            return f"""<!doctype html><html><head><title>CapyFinder</title></head><body>
<h1>CapyFinder</h1>
<form method="get" action="/">
<label for="q">Search spots</label> <input id="q" name="q" type="search" value="{e(qs.get('q', ''))}">
<label for="country">Country</label> <select id="country" name="country" onchange="this.form.submit()">
{opt('', 'All countries', qs.get('country', ''))}{''.join(opt(c, c, qs.get('country', '')) for c in countries)}</select>
<label for="type">Type</label> <select id="type" name="type" onchange="this.form.submit()">
{opt('', 'All types', qs.get('type', ''))}{''.join(opt(t, t, qs.get('type', '')) for t in TYPES)}</select>
<input id="onsen" name="onsen" value="1" type="checkbox" onchange="this.form.submit()"{' checked' if onsen else ''}>
<label for="onsen">Hot spring spots only</label>
</form>
<p>{len(rows)} spot{'s' if len(rows) != 1 else ''}</p>{empty}{cards}
<footer>Data verified {e(latest)}</footer></body></html>"""

        def _detail(self, s: dict) -> str:
            e = html.escape
            fields = "".join(f"<dt>{e(k)}</dt><dd>{e(str(v))}</dd>" for k, v in s.items())
            return (f"<!doctype html><title>{e(s['name'])}</title><h1>{e(s['name'])}</h1><dl>{fields}</dl>"
                    f'<a href="{e(s["source_url"])}">Source</a> <a href="/">Back to all spots</a>')

    return Handler


def serve(data_path: Path, port: int = 0, bugs: set[str] | None = None) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(load(data_path), bugs or set()))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


if __name__ == "__main__":
    data = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("spots.json"))
    port = int(os.environ.get("PORT", "8000"))
    bugs = {b for b in os.environ.get("REF_BUGS", "").split(",") if b}
    srv, url = serve(data, port, bugs)
    print(f"reference CapyFinder on {url} (bugs: {sorted(bugs) or 'none'})")
    threading.Event().wait()
