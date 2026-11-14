import html
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "spots.json")

VALID_TYPES = ("zoo", "onsen", "cafe", "sanctuary", "farm", "park")


def load_spots():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


SPOTS = load_spots()
SPOTS_BY_ID = {spot["id"]: spot for spot in SPOTS}
LATEST_VERIFIED = max(spot["verified_on"] for spot in SPOTS)


def esc(value):
    return html.escape(str(value), quote=True)


def query_param(params, name):
    values = params.get(name)
    if not values:
        return None
    value = values[0].strip()
    return value if value else None


def is_hot_spring(spot):
    if spot["type"].casefold() == "onsen":
        return True
    experience = spot["capybara_experience"].casefold()
    return "hot spring" in experience or "onsen" in experience


def hot_spring_param(params):
    values = params.get("hot_spring")
    if not values:
        return False
    return values[0].strip().lower() not in ("", "0", "false", "off")


def filter_spots(country=None, spot_type=None, q=None, hot_spring=False):
    results = []
    for spot in SPOTS:
        if country is not None and spot["country"].casefold() != country.casefold():
            continue
        if spot_type is not None and spot["type"].casefold() != spot_type.casefold():
            continue
        if hot_spring and not is_hot_spring(spot):
            continue
        if q is not None:
            needle = q.casefold()
            if needle not in spot["name"].casefold() and needle not in spot["city"].casefold():
                continue
        results.append(spot)
    results.sort(key=lambda s: s["name"].casefold())
    return results


def country_options():
    return sorted({spot["country"] for spot in SPOTS})


def type_options():
    present = {spot["type"] for spot in SPOTS}
    return [t for t in VALID_TYPES if t in present]


def build_stats():
    countries = sorted({spot["country"] for spot in SPOTS})
    types = sorted({spot["type"] for spot in SPOTS})
    return {
        "total": len(filter_spots()),
        "by_country": {c: len(filter_spots(country=c)) for c in countries},
        "by_type": {t: len(filter_spots(spot_type=t)) for t in types},
    }


PAGE_CSS = """
    body { font-family: system-ui, -apple-system, sans-serif; margin: 2rem auto;
           max-width: 44rem; padding: 0 1rem; color: #1f2933; line-height: 1.5; }
    h1 { color: #0b5345; }
    .controls label { display: block; font-weight: 600; margin-top: 0.6rem; }
    .controls input, .controls select { display: block; width: 100%; max-width: 22rem;
           padding: 0.4rem 0.5rem; font-size: 1rem; box-sizing: border-box; margin-top: 0.15rem; }
    article[data-testid="spot-card"] { border: 1px solid #d5dde0; border-radius: 0.5rem;
           padding: 0.75rem 1rem; margin: 0.75rem 0; }
    article[data-testid="spot-card"] h2 { margin: 0 0 0.25rem; font-size: 1.15rem; }
    article[data-testid="spot-card"] p { margin: 0.1rem 0; }
    dl { margin: 1rem 0; }
    dt { font-weight: 600; margin-top: 0.6rem; }
    dd { margin: 0; }
    .meta { color: #52606d; }
    .controls input[type="checkbox"] { display: inline-block; width: auto; max-width: none;
           margin-top: 0.3rem; }
    footer { margin-top: 2rem; }
"""

PAGE_JS = """
(function () {
  var form = document.getElementById("spot-form");
  var search = document.getElementById("search");
  var country = document.getElementById("country");
  var type = document.getElementById("type");
  var results = document.getElementById("results");
  var count = document.getElementById("result-count");
  var hotSpring = document.getElementById("hot-spring");
  if (!form || !search || !country || !type || !results || !count || !hotSpring) return;

  var seq = 0;
  var controller = null;
  var timer = null;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&" + "amp;", "<": "&" + "lt;", ">": "&" + "gt;", '"': "&" + "quot;", "'": "&" + "#39;" }[c];
    });
  }

  function card(s) {
    return '<article data-testid="spot' + '-card">' +
      '<h2><a href="/spots/' + encodeURIComponent(s.id) + '">' + esc(s.name) + '</a></h2>' +
      '<p>' + esc(s.city) + '</p>' +
      '<p>' + esc(s.country) + '</p>' +
      '<p>' + esc(s.type) + '</p>' +
      '<p><a href="' + esc(s.source_url) + '">Source</a></p>' +
      '</article>';
  }

  function render(spots) {
    var html = "";
    for (var i = 0; i < spots.length; i++) html += card(spots[i]);
    if (spots.length === 0) {
      html += '<p data-testid="no-results">No capybaras here' + ' yet</p>';
    }
    results.innerHTML = html;
    count.textContent = spots.length === 1 ? "1 spot" : spots.length + " spots";
  }

  function update() {
    var params = new URLSearchParams();
    if (search.value.trim()) params.set("q", search.value.trim());
    if (country.value) params.set("country", country.value);
    if (type.value) params.set("type", type.value);
    if (hotSpring.checked) params.set("hot_spring", "1");
    var mySeq = ++seq;
    if (controller) {
      try { controller.abort(); } catch (e) {}
    }
    controller = new AbortController();
    fetch("/api/spots?" + params.toString(), { signal: controller.signal })
      .then(function (r) { return r.json(); })
      .then(function (spots) {
        if (mySeq !== seq) return;
        if (!Array.isArray(spots)) return;
        render(spots);
      })
      .catch(function (err) {
        if (err && err.name === "AbortError") return;
      });
  }

  function scheduleUpdate() {
    if (timer) clearTimeout(timer);
    timer = setTimeout(update, 120);
  }

  search.addEventListener("input", scheduleUpdate);
  country.addEventListener("change", update);
  type.addEventListener("change", update);
  hotSpring.addEventListener("change", update);
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (timer) clearTimeout(timer);
    update();
  });
})();
"""


def render_card(spot):
    return (
        '  <article data-testid="spot-card">\n'
        '    <h2><a href="/spots/{id}">{name}</a></h2>\n'
        '    <p>{city}</p>\n'
        '    <p>{country}</p>\n'
        '    <p>{type}</p>\n'
        '    <p><a href="{source_url}">Source</a></p>\n'
        '  </article>\n'
    ).format(
        id=esc(spot["id"]),
        name=esc(spot["name"]),
        city=esc(spot["city"]),
        country=esc(spot["country"]),
        type=esc(spot["type"]),
        source_url=esc(spot["source_url"]),
    )


def render_home(q, country, spot_type, hot):
    spots = filter_spots(country=country, spot_type=spot_type, q=q, hot_spring=hot)
    n = len(spots)
    count_text = "1 spot" if n == 1 else "%d spots" % n
    cards = "\n".join(render_card(s) for s in spots)
    no_results = '  <p data-testid="no-results">No capybaras here yet</p>\n' if n == 0 else ""
    country_opts = "\n".join(
        '        <option value="%s"%s>%s</option>'
        % (c, ' selected' if (country is not None and c.casefold() == country.casefold()) else "", c)
        for c in country_options()
    )
    type_opts = "\n".join(
        '        <option value="%s"%s>%s</option>'
        % (t, ' selected' if (spot_type is not None and t.casefold() == spot_type.casefold()) else "", t)
        for t in type_options()
    )
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>CapyFinder</title>\n"
        "<style>%s</style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>CapyFinder</h1>\n"
        '  <form id="spot-form" method="get" action="/">\n'
        '    <div class="controls">\n'
        '      <label for="search">Search spots</label>\n'
        '      <input type="search" id="search" name="q" value="%s" placeholder="Name or city">\n'
        '      <label for="country">Country</label>\n'
        "      <select id=\"country\" name=\"country\">\n"
        '        <option value="">All countries</option>\n'
        "%s\n"
        "      </select>\n"
        '      <label for="type">Type</label>\n'
        "      <select id=\"type\" name=\"type\">\n"
        '        <option value="">All types</option>\n'
        "%s\n"
        "      </select>\n"
        '      <label for="hot-spring">Hot spring spots only</label>\n'
        '      <input type="checkbox" id="hot-spring" name="hot_spring" value="1"%s>\n'
        "    </div>\n"
        "  </form>\n"
        '  <p id="result-count" data-testid="result-count" class="meta">%s</p>\n'
        '  <div id="results" data-testid="results">\n'
        "%s%s  </div>\n"
        '  <footer><p class="meta">Data verified %s</p></footer>\n'
        "  <script>%s</script>\n"
        "</body>\n"
        "</html>\n"
    ) % (
        PAGE_CSS,
        esc(q or ""),
        country_opts,
        type_opts,
        " checked" if hot else "",
        count_text,
        cards,
        no_results,
        LATEST_VERIFIED,
        PAGE_JS,
    )


def render_detail(spot):
    rows = (
        ("ID", spot["id"]),
        ("City", spot["city"]),
        ("Country", spot["country"]),
        ("Type", spot["type"]),
        ("Capybara experience", spot["capybara_experience"]),
        ("Hours", spot["hours"]),
        ("Adult price", spot["adult_price"]),
        ("Verified on", spot["verified_on"]),
    )
    dl = "\n".join("    <dt>%s</dt>\n    <dd>%s</dd>" % (esc(k), esc(v)) for k, v in rows)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>%s — CapyFinder</title>\n"
        "<style>%s</style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>%s</h1>\n"
        "  <dl>\n"
        "%s\n"
        "    <dt>Source</dt>\n"
        '    <dd><a href="%s">Source</a></dd>\n'
        "  </dl>\n"
        '  <p><a href="/">Back to all spots</a></p>\n'
        '  <footer><p class="meta">Data verified %s</p></footer>\n'
        "</body>\n"
        "</html>\n"
    ) % (esc(spot["name"]), PAGE_CSS, esc(spot["name"]), dl, esc(spot["source_url"]), LATEST_VERIFIED)


def render_not_found():
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        "<title>Spot not found — CapyFinder</title>\n"
        "<style>%s</style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>Spot not found</h1>\n"
        '  <p><a href="/">Back to all spots</a></p>\n'
        '  <footer><p class="meta">Data verified %s</p></footer>\n'
        "</body>\n"
        "</html>\n"
    ) % (PAGE_CSS, LATEST_VERIFIED)


class Handler(BaseHTTPRequestHandler):
    server_version = "CapyFinder/1.0"

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, status, html_text):
        body = html_text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            self.route()
        except BrokenPipeError:
            pass
        except Exception:
            self.send_json(500, {"error": "internal server error"})

    def route(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if len(path) > 1:
            path = path.rstrip("/") or "/"

        if path == "/api/health":
            self.send_json(200, {"ok": True, "spots": len(SPOTS)})
        elif path == "/api/spots":
            self.handle_spots(parse_qs(parsed.query, keep_blank_values=True))
        elif path == "/api/stats":
            self.send_json(200, build_stats())
        elif re.fullmatch(r"/api/spots/[^/]+", path):
            spot_id = unquote(path[len("/api/spots/"):])
            spot = SPOTS_BY_ID.get(spot_id)
            if spot is None:
                self.send_json(404, {"error": "unknown spot id: %s" % spot_id})
            else:
                self.send_json(200, spot)
        elif path == "/":
            self.handle_home(parse_qs(parsed.query, keep_blank_values=True))
        elif re.fullmatch(r"/spots/[^/]+", path):
            spot_id = unquote(path[len("/spots/"):])
            spot = SPOTS_BY_ID.get(spot_id)
            if spot is None:
                self.send_html(404, render_not_found())
            else:
                self.send_html(200, render_detail(spot))
        else:
            self.send_json(404, {"error": "not found"})

    def handle_spots(self, params):
        country = query_param(params, "country")
        spot_type = query_param(params, "type")
        q = query_param(params, "q")
        hot = hot_spring_param(params)

        if spot_type is not None and spot_type.casefold() not in VALID_TYPES:
            self.send_json(400, {"error": "unknown type: %s" % spot_type})
            return

        self.send_json(200, filter_spots(country=country, spot_type=spot_type, q=q, hot_spring=hot))

    def handle_home(self, params):
        country = query_param(params, "country")
        spot_type = query_param(params, "type")
        q = query_param(params, "q")
        hot = hot_spring_param(params)

        if spot_type is not None and spot_type.casefold() not in VALID_TYPES:
            self.send_json(400, {"error": "unknown type: %s" % spot_type})
            return

        self.send_html(200, render_home(q, country, spot_type, hot))

    def method_not_allowed(self):
        self.send_json(405, {"error": "method not allowed"})

    do_POST = method_not_allowed
    do_PUT = method_not_allowed
    do_DELETE = method_not_allowed
    do_PATCH = method_not_allowed


def main():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("CapyFinder listening on port %d" % port, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()