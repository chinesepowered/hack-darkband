import html
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "spots.json")
VALID_TYPES = ["zoo", "onsen", "cafe", "sanctuary", "farm", "park"]
SPOT_ID_PATH = re.compile(r"^/api/spots/[^/]+$")
DETAIL_ID_PATH = re.compile(r"^/spots/[^/]+$")
SPOT_FIELDS = [
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
]
JSON_TYPE = "application/json"
HTML_TYPE = "text/html; charset=utf-8"


def load_spots():
    with open(DATA_PATH, encoding="utf-8") as f:
        spots = json.load(f)
    return sorted(spots, key=lambda s: s["name"].lower())


SPOTS = load_spots()
SPOTS_BY_ID = {s["id"]: s for s in SPOTS}
COUNTRIES = sorted({s["country"] for s in SPOTS})
TYPES_IN_DATA = sorted({s["type"] for s in SPOTS})
LATEST_VERIFIED_ON = max(s["verified_on"] for s in SPOTS)
ONSEN_TRUTHY = {"on", "true", "1", "yes"}


def build_stats():
    by_country = {}
    by_type = {}
    for spot in SPOTS:
        by_country[spot["country"]] = by_country.get(spot["country"], 0) + 1
        by_type[spot["type"]] = by_type.get(spot["type"], 0) + 1
    return {"total": len(SPOTS), "by_country": by_country, "by_type": by_type}


STATS = build_stats()


def esc(value):
    return html.escape(str(value), quote=True)


def is_hot_spring(spot):
    if spot["type"].lower() == "onsen":
        return True
    experience = spot["capybara_experience"].lower()
    return "hot spring" in experience or "onsen" in experience


def filter_spots(params):
    def first(key):
        values = params.get(key)
        return values[0] if values else None

    country = first("country")
    spot_type = first("type")
    query = first("q")
    onsen_only = first("onsen")

    if spot_type is not None and spot_type != "":
        if spot_type.lower() not in VALID_TYPES:
            return None, 400, {
                "error": "unknown type '%s'; valid types: %s"
                % (spot_type, ", ".join(VALID_TYPES))
            }

    result = SPOTS
    if country is not None and country != "":
        wanted = country.lower()
        result = [s for s in result if s["country"].lower() == wanted]
    if spot_type is not None and spot_type != "":
        wanted = spot_type.lower()
        result = [s for s in result if s["type"].lower() == wanted]
    if query is not None:
        needle = query.strip().lower()
        if needle:
            result = [
                s
                for s in result
                if needle in s["name"].lower() or needle in s["city"].lower()
            ]
    if onsen_only is not None and onsen_only.strip().lower() in ONSEN_TRUTHY:
        result = [s for s in result if is_hot_spring(s)]
    return result, 200, None


PAGE_CSS = """
body { font-family: system-ui, -apple-system, sans-serif; margin: 2rem auto;
       max-width: 46rem; padding: 0 1rem; color: #1c1c1c; line-height: 1.5; }
h1 { margin-bottom: .25rem; }
.tagline { margin-top: 0; color: #555; }
.filters { display: flex; gap: 1rem; flex-wrap: wrap; align-items: flex-end;
           margin: 1.5rem 0 .5rem; }
.field { display: flex; flex-direction: column; gap: .35rem; }
.field label { font-weight: 600; }
input[type=search], select { padding: .5rem .6rem; font-size: 1rem;
    border: 1px solid #b5b5b5; border-radius: 6px; background: #fff; }
input[type=search] { min-width: 15rem; }
#result-count { font-weight: 600; margin: 1.25rem 0 .5rem; }
#empty-state { color: #555; font-style: italic; margin: .5rem 0; }
.spot-card { border: 1px solid #dcdcdc; border-radius: 8px;
             padding: .75rem 1rem; margin-bottom: .75rem; background: #fff; }
.spot-card h2 { margin: 0 0 .3rem; font-size: 1.15rem; }
.spot-card a { color: #9a5b00; }
.spot-card p { margin: .15rem 0; color: #333; }
.spot-source { font-weight: 600; }
table.spot-fields { border-collapse: collapse; margin-top: 1rem; }
table.spot-fields th, table.spot-fields td { border: 1px solid #d5d5d5;
    padding: .4rem .6rem; text-align: left; vertical-align: top; }
table.spot-fields th { width: 11rem; background: #faf6ef; }
.actions { margin-top: 1.5rem; display: flex; gap: 1.5rem; }
.actions a { font-weight: 600; }
.not-found { margin-top: 2rem; }
"""

PAGE_JS = """
(function () {
  var qInput = document.getElementById('search-q');
  var countrySelect = document.getElementById('filter-country');
  var typeSelect = document.getElementById('filter-type');
  var onsenCheck = document.getElementById('onsen-only');
  var timer = null;

  function refresh() {
    var params = new URLSearchParams();
    var q = qInput.value.trim();
    if (q) params.set('q', q);
    if (countrySelect.value) params.set('country', countrySelect.value);
    if (typeSelect.value) params.set('type', typeSelect.value);
    if (onsenCheck && onsenCheck.checked) params.set('onsen', 'on');
    var url = '/?' + params.toString();
    fetch(url)
      .then(function (response) { return response.text(); })
      .then(function (htmlText) {
        var doc = new DOMParser().parseFromString(htmlText, 'text/html');
        var fresh = doc.getElementById('results');
        var current = document.getElementById('results');
        if (fresh && current) current.outerHTML = fresh.outerHTML;
      })
      .catch(function () {});
  }

  qInput.addEventListener('input', function () {
    if (timer) clearTimeout(timer);
    timer = setTimeout(refresh, 250);
  });
  countrySelect.addEventListener('change', refresh);
  typeSelect.addEventListener('change', refresh);
  if (onsenCheck) onsenCheck.addEventListener('change', refresh);
})();
"""


def render_card(spot):
    return (
        '<article class="spot-card" data-testid="spot-card">'
        '<h2><a href="/spots/%s">%s</a></h2>'
        '<p class="spot-city">%s</p>'
        '<p class="spot-country">%s</p>'
        '<p class="spot-type">%s</p>'
        '<a class="spot-source" href="%s">Source</a>'
        "</article>"
    ) % (
        esc(spot["id"]),
        esc(spot["name"]),
        esc(spot["city"]),
        esc(spot["country"]),
        esc(spot["type"]),
        esc(spot["source_url"]),
    )


def render_results_body(spots):
    count = len(spots)
    count_text = "1 spot" if count == 1 else "%d spots" % count
    body = '<p id="result-count">%s</p>' % esc(count_text)
    if count == 0:
        body += '<p id="empty-state">No capybaras here yet</p>'
    else:
        body += '<div id="spot-list">%s</div>' % "".join(
            render_card(s) for s in spots
        )
    return body


def render_option_group(options, current, all_label):
    parts = ['<option value="">%s</option>' % all_label]
    for option in options:
        selected = ' selected' if option.lower() == current.lower() else ""
        parts.append('<option value="%s"%s>%s</option>' % (esc(option), selected, esc(option)))
    return "".join(parts)


def render_home_page(params):
    spots, status, error = filter_spots(params)
    if error is not None:
        return status, JSON_TYPE, json.dumps(error).encode("utf-8")

    def first(key):
        values = params.get(key)
        return values[0] if values else None

    query = first("q") or ""
    country = first("country") or ""
    spot_type = first("type") or ""
    onsen_checked = ' checked' if (first("onsen") or "").strip().lower() in ONSEN_TRUTHY else ""

    country_options = render_option_group(COUNTRIES, country, "All countries")
    type_options = render_option_group(TYPES_IN_DATA, spot_type, "All types")
    results_body = render_results_body(spots)

    page = (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>CapyFinder</title>\n"
        "<style>%s</style>\n"
        "</head>\n"
        "<body>\n"
        "<h1>CapyFinder</h1>\n"
        '<p class="tagline">Where can I meet a capybara today?</p>\n'
        '<form class="filters" action="/" method="get">\n'
        '  <div class="field">'
        '<label for="search-q">Search spots</label>'
        '<input type="search" id="search-q" name="q" value="%s" placeholder="Name or city">'
        "</div>\n"
        '  <div class="field">'
        '<label for="filter-country">Country</label>'
        '<select id="filter-country" name="country">%s</select>'
        "</div>\n"
        '  <div class="field">'
        '<label for="filter-type">Type</label>'
        '<select id="filter-type" name="type">%s</select>'
        "</div>\n"
        '  <div class="field checkbox-field">'
        '<label for="onsen-only"><input type="checkbox" id="onsen-only" name="onsen" value="on"%s> Hot spring spots only</label>'
        "</div>\n"
        "</form>\n"
        '<div id="results">\n%s\n</div>\n'
        "<footer>Data verified %s</footer>\n"
        "<script>%s</script>\n"
        "</body>\n"
        "</html>\n"
    ) % (
        PAGE_CSS,
        esc(query),
        country_options,
        type_options,
        onsen_checked,
        results_body,
        LATEST_VERIFIED_ON,
        PAGE_JS,
    )
    return 200, HTML_TYPE, page.encode("utf-8")


def render_detail_page(spot):
    rows = []
    for field in SPOT_FIELDS:
        value = spot[field]
        cell = esc(value) if value != "" else "&mdash;"
        rows.append(
            '<tr><th scope="row">%s</th><td>%s</td></tr>' % (field, cell)
        )
    page = (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>%s &mdash; CapyFinder</title>\n"
        "<style>%s</style>\n"
        "</head>\n"
        "<body>\n"
        "<h1>%s</h1>\n"
        '<table class="spot-fields">\n<tbody>\n%s\n</tbody>\n</table>\n'
        '<div class="actions">'
        '<a class="spot-source" href="%s">Source</a> '
        '<a href="/">Back to all spots</a>'
        "</div>\n"
        "<footer>Data verified %s</footer>\n"
        "</body>\n"
        "</html>\n"
    ) % (
        esc(spot["name"]),
        PAGE_CSS,
        esc(spot["name"]),
        "".join(rows),
        esc(spot["source_url"]),
        LATEST_VERIFIED_ON,
    )
    return 200, HTML_TYPE, page.encode("utf-8")


def render_not_found_page():
    page = (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        "<title>Spot not found &mdash; CapyFinder</title>\n"
        "<style>%s</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="not-found">'
        "<h1>Spot not found</h1>\n"
        "<p>That capybara spot is not in our data.</p>\n"
        '<p><a href="/">Back to all spots</a></p>'
        "</div>\n"
        "<footer>Data verified %s</footer>\n"
        "</body>\n"
        "</html>\n"
    ) % (PAGE_CSS, LATEST_VERIFIED_ON)
    return 404, HTML_TYPE, page.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "CapyFinder/1.0"

    def _send(self, status, content_type, body, include_body=True):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def _route(self, params=None):
        parsed = urlparse(self.path)
        path = parsed.path
        if len(path) > 1:
            path = path.rstrip("/") or "/"
        if params is None:
            params = parse_qs(parsed.query, keep_blank_values=True)
        params = {
            key: [value if len(value) <= 1 else value.rstrip("/") for value in values]
            for key, values in params.items()
        }

        if path == "/api/health":
            return 200, JSON_TYPE, json.dumps({"ok": True, "spots": len(SPOTS)}).encode("utf-8")
        if path == "/api/stats":
            return 200, JSON_TYPE, json.dumps(STATS).encode("utf-8")
        if path == "/api/spots":
            spots, status, error = filter_spots(params)
            if error is not None:
                return status, JSON_TYPE, json.dumps(error).encode("utf-8")
            return status, JSON_TYPE, json.dumps(spots).encode("utf-8")
        if SPOT_ID_PATH.match(path):
            spot_id = unquote(path[len("/api/spots/"):])
            spot = SPOTS_BY_ID.get(spot_id)
            if spot is None:
                return 404, JSON_TYPE, json.dumps(
                    {"error": "spot '%s' not found" % spot_id}
                ).encode("utf-8")
            return 200, JSON_TYPE, json.dumps(spot).encode("utf-8")
        if path in ("/", ""):
            return render_home_page(params)
        if DETAIL_ID_PATH.match(path):
            spot_id = unquote(path[len("/spots/"):])
            spot = SPOTS_BY_ID.get(spot_id)
            if spot is None:
                return render_not_found_page()
            return render_detail_page(spot)
        return 404, JSON_TYPE, json.dumps({"error": "not found"}).encode("utf-8")

    def do_GET(self):
        status, content_type, body = self._route()
        self._send(status, content_type, body)

    def do_HEAD(self):
        status, content_type, body = self._route()
        self._send(status, content_type, body, include_body=False)

    def do_POST(self):
        params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > 0:
            form_body = self.rfile.read(length).decode("utf-8", "replace")
            for key, values in parse_qs(form_body, keep_blank_values=True).items():
                params.setdefault(key, values)
        status, content_type, body = self._route(params=params)
        self._send(status, content_type, body)


def main():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("CapyFinder serving %d spots on http://localhost:%d" % (len(SPOTS), port))
    server.serve_forever()


if __name__ == "__main__":
    main()