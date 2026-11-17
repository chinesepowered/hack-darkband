#!/usr/bin/env python3
"""CapyFinder — stdlib-only server: API (stage 1) + web UI (stage 2)."""
import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, "data", "spots.json")
PORT = int(os.environ.get("PORT", "8000"))

VALID_TYPES = ("zoo", "onsen", "cafe", "sanctuary", "farm", "park")
FIELDS = (
    "id",
    "name",
    "city",
    "country",
    "type",
    "capybara_experience",
    "hours",
    "adult_price",
    "source_url",
    "verified_on",
)

PAGE_CSS = """
:root { --ink: #2c2418; --paper: #faf6ef; --card: #fffdf8; --accent: #b0653a; --muted: #8a7f6d; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Georgia, 'Times New Roman', serif; background: var(--paper); color: var(--ink); }
.wrap { max-width: 880px; margin: 0 auto; padding: 24px 20px 60px; }
h1 { font-size: 2.1rem; margin: 0 0 4px; }
.tagline { color: var(--muted); margin: 0 0 20px; }
.filters { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; background: var(--card); border: 1px solid #e5dccb; border-radius: 10px; padding: 14px 16px; margin-bottom: 14px; }
.filters label { display: block; font-size: 0.85rem; color: var(--muted); margin-bottom: 4px; }
.filters input[type=search] { min-width: 220px; }
.filters input, .filters select { font: inherit; padding: 7px 9px; border: 1px solid #d8cdb8; border-radius: 7px; background: #fff; color: var(--ink); }
#result-count { font-weight: bold; margin: 10px 2px; }
#empty { color: var(--muted); font-style: italic; }
#results { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }
article[data-testid="spot-card"] { background: var(--card); border: 1px solid #e5dccb; border-radius: 10px; padding: 14px 16px; }
article[data-testid="spot-card"] h2 { font-size: 1.15rem; margin: 0 0 8px; }
article[data-testid="spot-card"] h2 a { color: var(--accent); text-decoration: none; }
article[data-testid="spot-card"] h2 a:hover { text-decoration: underline; }
article[data-testid="spot-card"] p { margin: 2px 0; }
.src { display: inline-block; margin-top: 8px; font-size: 0.9rem; }
a { color: var(--accent); }
.muted { color: var(--muted); font-size: 0.85rem; word-break: break-all; }
.detail { background: var(--card); border: 1px solid #e5dccb; border-radius: 10px; padding: 20px 22px; }
.detail dl { display: grid; grid-template-columns: 170px 1fr; row-gap: 8px; column-gap: 16px; margin: 18px 0; }
.detail dt { color: var(--muted); }
.detail dd { margin: 0; }
.actions { margin-top: 18px; }
"""

HOME_JS = """
(function () {
  var q = document.getElementById('q');
  var country = document.getElementById('country');
  var type = document.getElementById('type');
  var results = document.getElementById('results');
  var count = document.getElementById('result-count');
  var empty = document.getElementById('empty');
  var form = document.getElementById('filters');
  var timer = null;

  function card(spot) {
    var a = document.createElement('article');
    a.setAttribute('data-testid', 'spot-card');
    var h = document.createElement('h2');
    var link = document.createElement('a');
    link.href = '/spots/' + encodeURIComponent(spot.id);
    link.textContent = spot.name;
    h.appendChild(link);
    a.appendChild(h);
    ['city', 'country', 'type'].forEach(function (k) {
      var p = document.createElement('p');
      p.textContent = spot[k];
      a.appendChild(p);
    });
    var s = document.createElement('a');
    s.className = 'src';
    s.href = spot.source_url;
    s.textContent = 'Source';
    a.appendChild(s);
    return a;
  }

  function render(spots) {
    results.innerHTML = '';
    spots.forEach(function (s) { results.appendChild(card(s)); });
    count.textContent = spots.length === 1 ? '1 spot' : spots.length + ' spots';
    empty.hidden = spots.length !== 0;
  }

  function refresh() {
    var params = new URLSearchParams();
    if (q.value.trim()) params.set('q', q.value.trim());
    if (country.value) params.set('country', country.value);
    if (type.value) params.set('type', type.value);
    fetch('/api/spots?' + params.toString())
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function () { count.textContent = 'search failed, try again'; });
  }

  q.addEventListener('input', function () {
    clearTimeout(timer);
    timer = setTimeout(refresh, 200);
  });
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearTimeout(timer);
    refresh();
  });
  country.addEventListener('change', refresh);
  type.addEventListener('change', refresh);
})();
"""


def escape(value):
    return html.escape(str(value), quote=True)


def render_card(spot):
    return (
        '<article data-testid="spot-card">'
        '<h2><a href="/spots/{id}">{name}</a></h2>'
        "<p>{city}</p>"
        "<p>{country}</p>"
        "<p>{type}</p>"
        '<a class="src" href="{source}">Source</a>'
        "</article>"
    ).format(
        id=escape(spot["id"]),
        name=escape(spot["name"]),
        city=escape(spot["city"]),
        country=escape(spot["country"]),
        type=escape(spot["type"]),
        source=escape(spot["source_url"]),
    )


def make_page(include_script):
    def render(title, body):
        script = "<script>{}</script>".format(HOME_JS) if include_script else ""
        return (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>{title}</title><style>{css}</style></head>"
            "<body><div class=\"wrap\">{body}</div>{script}</body></html>"
        ).format(title=escape(title), css=PAGE_CSS, body=body, script=script)

    return render


def render_home(spots):
    countries = sorted({s["country"] for s in spots if s["country"]})
    country_options = "".join(
        '<option value="{}">{}</option>'.format(escape(c), escape(c)) for c in countries
    )
    type_options = "".join(
        '<option value="{}">{}</option>'.format(escape(t), escape(t)) for t in VALID_TYPES
    )
    cards = "".join(render_card(s) for s in spots)
    count_text = "1 spot" if len(spots) == 1 else "{} spots".format(len(spots))
    empty_hidden = " hidden" if spots else ""
    body = (
        "<h1>CapyFinder</h1>"
        "<p class=\"tagline\">Where can I meet a capybara today? Every fact carries a source.</p>"
        '<form id="filters" autocomplete="off">'
        "<div><label for=\"q\">Search spots</label>"
        '<input type="search" id="q" name="q" placeholder="name or city"></div>'
        "<div><label for=\"country\">Country</label>"
        '<select id="country" name="country"><option value="">All countries</option>{}</select></div>'
        "<div><label for=\"type\">Type</label>"
        '<select id="type" name="type"><option value="">All types</option>{}</select></div>'
        "</form>"
        '<p id="result-count">{}</p>'
        '<p id="empty"{}>No capybaras here yet</p>'
        '<div id="results">{}</div>'
    ).format(country_options, type_options, escape(count_text), empty_hidden, cards)
    return make_page(True)("CapyFinder", body)


def render_detail(spot):
    def dd(value):
        return escape(value) if value else "—"

    body = (
        "<h1>{}</h1>"
        '<div class="detail"><dl>'
        "<dt>ID</dt><dd>{}</dd>"
        "<dt>City</dt><dd>{}</dd>"
        "<dt>Country</dt><dd>{}</dd>"
        "<dt>Type</dt><dd>{}</dd>"
        "<dt>Capybara experience</dt><dd>{}</dd>"
        "<dt>Hours</dt><dd>{}</dd>"
        "<dt>Adult price</dt><dd>{}</dd>"
        "<dt>Verified on</dt><dd>{}</dd>"
        "</dl>"
        '<p><a href="{src}">Source</a> <span class="muted">({src})</span></p>'
        '<p class="actions"><a href="/">Back to all spots</a></p>'
        "</div>"
    ).format(
        escape(spot["name"]),
        escape(spot["id"]),
        dd(spot["city"]),
        dd(spot["country"]),
        dd(spot["type"]),
        dd(spot["capybara_experience"]),
        dd(spot["hours"]),
        dd(spot["adult_price"]),
        dd(spot["verified_on"]),
        src=escape(spot["source_url"]),
    )
    return make_page(False)("{} — CapyFinder".format(spot["name"]), body)


def render_not_found():
    body = (
        "<h1>Spot not found</h1>"
        '<p class="actions"><a href="/">Back to all spots</a></p>'
    )
    return make_page(False)("Spot not found — CapyFinder", body)


def load_spots():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [{field: item.get(field, "") for field in FIELDS} for item in raw]


def sort_spots(spots):
    return sorted(spots, key=lambda s: (s["name"].lower(), s["id"]))


def first(query, key):
    values = query.get(key)
    if not values:
        return None
    value = values[0].strip()
    return value or None


class Handler(BaseHTTPRequestHandler):
    server_version = "CapyFinder/1.0"

    def _send(self, status, body, content_type="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status, payload):
        self._send(status, json.dumps(payload))

    def _send_html(self, status, html_body):
        self._send(status, html_body, "text/html; charset=utf-8")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/health":
                self._send_json(200, {"ok": True, "spots": len(load_spots())})
            elif path.rstrip("/") == "/api/spots":
                self._handle_spots(parsed)
            elif path.startswith("/api/spots/"):
                self._handle_spot(path)
            elif path == "/":
                self._send_html(200, render_home(sort_spots(load_spots())))
            elif path.startswith("/spots/"):
                self._handle_detail(path)
            else:
                self._send_json(404, {"error": "not found"})
        except Exception:
            self._send_json(500, {"error": "internal server error"})

    def _handle_spots(self, parsed):
        query = parse_qs(parsed.query)
        country = first(query, "country")
        type_filter = first(query, "type")
        q = first(query, "q")

        if type_filter is not None and type_filter.lower() not in VALID_TYPES:
            self._send_json(
                400,
                {
                    "error": "unknown type %r; expected one of: %s"
                    % (type_filter, ", ".join(VALID_TYPES))
                },
            )
            return

        spots = load_spots()
        result = []
        for spot in spots:
            if country is not None and spot["country"].lower() != country.lower():
                continue
            if type_filter is not None and spot["type"].lower() != type_filter.lower():
                continue
            if q is not None:
                needle = q.lower()
                if needle not in spot["name"].lower() and needle not in spot["city"].lower():
                    continue
            result.append(spot)
        self._send_json(200, sort_spots(result))

    def _handle_spot(self, path):
        parts = [part for part in path.split("/") if part]
        if len(parts) != 3:
            self._send_json(404, {"error": "not found"})
            return
        spot_id = unquote(parts[2])
        for spot in load_spots():
            if spot["id"] == spot_id:
                self._send_json(200, spot)
                return
        self._send_json(404, {"error": "spot not found: %s" % spot_id})

    def _handle_detail(self, path):
        parts = [part for part in path.split("/") if part]
        if len(parts) != 2:
            self._send_html(404, render_not_found())
            return
        spot_id = unquote(parts[1])
        for spot in load_spots():
            if spot["id"] == spot_id:
                self._send_html(200, render_detail(spot))
                return
        self._send_html(404, render_not_found())

    def log_message(self, format, *args):
        pass


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("CapyFinder listening on http://0.0.0.0:%d" % PORT, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()