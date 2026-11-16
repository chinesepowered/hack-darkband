import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "spots.json")

VALID_TYPES = ("zoo", "onsen", "cafe", "sanctuary", "farm", "park")


def esc(value):
    return html.escape(str(value), quote=True)


def load_spots():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def sort_spots(spots):
    return sorted(spots, key=lambda s: str(s.get("name", "")).lower())


PAGE_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>%(title)s</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 60rem; padding: 0 1rem; color: #222; }
  form { display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; align-items: end; margin: 1rem 0; }
  form label { display: block; font-weight: 600; }
  form input, form select { padding: 0.35rem; }
  #results { display: grid; grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr)); gap: 1rem; }
  article { border: 1px solid #ccc; border-radius: 8px; padding: 0.75rem 1rem; }
  article[hidden], [hidden] { display: none; }
  article h3 { margin: 0 0 0.5rem; }
  article p { margin: 0.15rem 0; }
  dl { display: grid; grid-template-columns: max-content 1fr; gap: 0.3rem 1rem; }
  dt { font-weight: 600; }
</style>
</head>
<body>
"""

HOME_BODY = """<h1>CapyFinder</h1>
<p>Where can I meet a capybara today?</p>
<form method="get" action="/" id="filter-form">
  <div>
    <label for="q">Search spots</label>
    <input type="search" id="q" name="q" value="%(q)s" placeholder="Search spots">
  </div>
  <div>
    <label for="country">Country</label>
    <select id="country" name="country">
      <option value=""%(country_all_sel)s>All countries</option>
%(country_options)s
    </select>
  </div>
  <div>
    <label for="type">Type</label>
    <select id="type" name="type">
      <option value=""%(type_all_sel)s>All types</option>
%(type_options)s
    </select>
  </div>
  <button type="submit">Filter</button>
</form>
<p data-testid="result-count">%(count_text)s</p>
<p data-testid="empty-state"%(empty_hidden)s>No capybaras here yet</p>
<div id="results">
%(cards)s
</div>
<script>
(function () {
  var q = document.getElementById("q");
  var country = document.getElementById("country");
  var type = document.getElementById("type");
  var count = document.getElementById("result-count");
  var empty = document.getElementById("empty-state");
  var cards = Array.prototype.slice.call(document.querySelectorAll('[data-testid="spot-card"]'));
  function applyFilters() {
    var query = q.value.trim().toLowerCase();
    var c = country.value.toLowerCase();
    var t = type.value.toLowerCase();
    var n = 0;
    cards.forEach(function (card) {
      var okQ = !query || card.dataset.name.indexOf(query) !== -1 || card.dataset.city.indexOf(query) !== -1;
      var okC = !c || card.dataset.country.toLowerCase() === c;
      var okT = !t || card.dataset.type.toLowerCase() === t;
      var show = okQ && okC && okT;
      card.hidden = !show;
      if (show) n++;
    });
    count.textContent = n === 1 ? "1 spot" : n + " spots";
    empty.hidden = n !== 0;
  }
  q.addEventListener("input", applyFilters);
  country.addEventListener("change", applyFilters);
  type.addEventListener("change", applyFilters);
  cards.forEach(function (card) {
    card.addEventListener("click", function (e) {
      if (e.target.closest("a")) return;
      window.location.href = card.dataset.href;
    });
  });
})();
</script>
</body>
</html>
"""

DETAIL_BODY = """<h1>%(name)s</h1>
<dl>
%(fields)s
</dl>
<p><a href="%(source_url)s">Source</a></p>
<p><a href="/">Back to all spots</a></p>
</body>
</html>
"""

NOT_FOUND_BODY = """<h1>Spot not found</h1>
<p><a href="/">Back to all spots</a></p>
</body>
</html>
"""


def card_html(spot, visible):
    hidden = "" if visible else " hidden"
    return (
        '<article data-testid="spot-card"%s data-name="%s" data-city="%s" '
        'data-country="%s" data-type="%s" data-href="/spots/%s">'
        '<h3><a href="/spots/%s">%s</a></h3>'
        '<p class="city">%s</p>'
        '<p class="country">%s</p>'
        '<p class="type">%s</p>'
        '<p class="source"><a href="%s">Source</a></p>'
        "</article>"
    ) % (
        hidden,
        esc(spot.get("name", "").lower()),
        esc(spot.get("city", "").lower()),
        esc(spot.get("country", "")),
        esc(spot.get("type", "")),
        esc(spot.get("id", "")),
        esc(spot.get("id", "")),
        esc(spot.get("name", "")),
        esc(spot.get("city", "")),
        esc(spot.get("country", "")),
        esc(spot.get("type", "")),
        esc(spot.get("source_url", "")),
    )


def render_home(spots, params):
    q = (params.get("q", [""])[0] or "").strip().lower()
    country = (params.get("country", [""])[0] or "").lower()
    type_value = (params.get("type", [""])[0] or "").lower()

    def included(s):
        if q and not (q in s.get("name", "").lower() or q in s.get("city", "").lower()):
            return False
        if country and s.get("country", "").lower() != country:
            return False
        if type_value and s.get("type", "").lower() != type_value:
            return False
        return True

    ordered = sort_spots(spots)
    visible = [s for s in ordered if included(s)]
    n = len(visible)
    count_text = "1 spot" if n == 1 else "%d spots" % n

    countries = sorted({s.get("country", "") for s in spots if s.get("country")})
    country_options = "\n      ".join(
        '<option value="%s"%s>%s</option>'
        % (esc(c), " selected" if c.lower() == country else "", esc(c))
        for c in countries
    )
    type_options = "\n      ".join(
        '<option value="%s"%s>%s</option>'
        % (esc(t), " selected" if t == type_value else "", esc(t))
        for t in VALID_TYPES
    )

    cards = "\n  ".join(card_html(s, s in visible) for s in ordered)

    body = HOME_BODY % {
        "q": esc((params.get("q", [""])[0] or "").strip()),
        "country_all_sel": " selected" if not country else "",
        "country_options": country_options,
        "type_all_sel": " selected" if not type_value else "",
        "type_options": type_options,
        "count_text": esc(count_text),
        "empty_hidden": " hidden" if n else "",
        "cards": cards,
    }
    return PAGE_HEAD % {"title": "CapyFinder"} + body


DETAIL_FIELDS = (
    ("Name", "name"),
    ("City", "city"),
    ("Country", "country"),
    ("Type", "type"),
    ("Capybara experience", "capybara_experience"),
    ("Hours", "hours"),
    ("Adult price", "adult_price"),
    ("ID", "id"),
    ("Verified on", "verified_on"),
)


def render_detail(spot):
    fields = "\n".join(
        "<dt>%s</dt>\n<dd>%s</dd>" % (esc(label), esc(spot.get(key, "")))
        for label, key in DETAIL_FIELDS
    )
    body = DETAIL_BODY % {
        "name": esc(spot.get("name", "")),
        "fields": fields,
        "source_url": esc(spot.get("source_url", "")),
    }
    return PAGE_HEAD % {"title": "%s — CapyFinder" % spot.get("name", "spot")} + body


class Handler(BaseHTTPRequestHandler):
    server_version = "CapyFinder"
    protocol_version = "HTTP/1.1"

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status, html_text):
        body = html_text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            parts = urlsplit(self.path)
            path = parts.path
            params = parse_qs(parts.query, keep_blank_values=True)
            if path == "/api/health":
                self._send_json(200, {"ok": True, "spots": len(load_spots())})
            elif path == "/api/spots":
                self._handle_api_spots(params)
            elif path.startswith("/api/spots/"):
                self._handle_api_spot(unquote(path[len("/api/spots/"):]))
            elif path == "/":
                self._send_html(200, render_home(load_spots(), params))
            elif path.startswith("/spots/"):
                spot_id = unquote(path[len("/spots/"):])
                for spot in load_spots():
                    if spot.get("id") == spot_id:
                        self._send_html(200, render_detail(spot))
                        return
                self._send_html(404, PAGE_HEAD % {"title": "Spot not found"} + NOT_FOUND_BODY)
            else:
                self._send_json(404, {"error": "not found"})
        except (OSError, ValueError):
            self._send_json(500, {"error": "internal server error"})

    def _handle_api_spots(self, params):
        spots = load_spots()

        if "country" in params:
            country = params["country"][0].lower()
            spots = [s for s in spots if str(s.get("country", "")).lower() == country]

        if "type" in params:
            type_value = params["type"][0]
            if type_value.lower() not in VALID_TYPES:
                self._send_json(
                    400,
                    {"error": "unknown type %r; expected one of: %s"
                     % (type_value, ", ".join(VALID_TYPES))},
                )
                return
            spots = [s for s in spots if str(s.get("type", "")).lower() == type_value.lower()]

        if "q" in params:
            q = params["q"][0].strip().lower()
            if q:
                spots = [
                    s for s in spots
                    if q in str(s.get("name", "")).lower() or q in str(s.get("city", "")).lower()
                ]

        self._send_json(200, sort_spots(spots))

    def _handle_api_spot(self, spot_id):
        for spot in load_spots():
            if spot.get("id") == spot_id:
                self._send_json(200, spot)
                return
        self._send_json(404, {"error": "spot not found: %s" % spot_id})


def main():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("CapyFinder listening on http://localhost:%d" % port, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()