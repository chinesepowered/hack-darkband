import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE, "data", "spots.json")
KNOWN_TYPES = ("zoo", "onsen", "cafe", "sanctuary", "farm", "park")


def load_spots():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_spots(spots, params, strict_type):
    country = params.get("country", [None])[0]
    spot_type = params.get("type", [None])[0]
    q = params.get("q", [None])[0]

    if spot_type is not None:
        if spot_type.lower() not in KNOWN_TYPES:
            if strict_type:
                return None
        else:
            spot_type = spot_type.lower()
            spots = [s for s in spots if s.get("type", "").lower() == spot_type]

    if country is not None:
        country = country.lower()
        spots = [s for s in spots if s.get("country", "").lower() == country]

    if q is not None:
        q = q.strip().lower()
        spots = [
            s for s in spots
            if q in s.get("name", "").lower() or q in s.get("city", "").lower()
        ]

    return sorted(spots, key=lambda s: (s.get("name", "").lower(), s.get("id", "")))


def esc(value):
    return html.escape(str(value), quote=True)


PAGE_CSS = """
body { font-family: system-ui, -apple-system, sans-serif; margin: 0 auto; max-width: 900px; padding: 1rem 1.25rem 3rem; line-height: 1.5; color-scheme: light dark; }
h1 { margin: 0.5rem 0 1rem; }
form#filters { display: grid; grid-template-columns: max-content 1fr; gap: 0.5rem 0.75rem; align-items: center; margin-bottom: 1rem; padding: 0.75rem 1rem; border: 1px solid #9995; border-radius: 10px; }
form#filters label { font-weight: 600; }
input[type=search], select { padding: 0.4rem 0.55rem; font: inherit; border: 1px solid #8888; border-radius: 6px; background: transparent; color: inherit; }
#result-count { font-weight: 600; margin: 0 0 0.75rem; }
#results { display: grid; gap: 0.75rem; }
article[data-testid="spot-card"] { border: 1px solid #9995; border-radius: 10px; padding: 0.65rem 1rem; }
article[data-testid="spot-card"] h2 { margin: 0 0 0.25rem; font-size: 1.1rem; }
article[data-testid="spot-card"] h2 a { color: inherit; }
.meta, .source { margin: 0; }
.empty { color: #777; font-style: italic; }
dl.fields { display: grid; grid-template-columns: max-content 1fr; gap: 0.4rem 1.25rem; margin: 1rem 0 1.5rem; }
dl.fields dt { font-weight: 600; }
dl.fields dd { margin: 0; overflow-wrap: anywhere; }
.dim { color: #777; }
.actions { display: flex; gap: 1.5rem; margin-top: 0.5rem; }
form#filters label.onsen-row { grid-column: 1 / -1; }
footer { margin-top: 2rem; color: #777; font-size: 0.9rem; }
"""

HOME_JS = """
<script>
(function () {
  var escMap = {};
  escMap["&"] = "&" + "amp;";
  escMap["<"] = "&" + "lt;";
  escMap[">"] = "&" + "gt;";
  escMap['"'] = "&" + "quot;";
  escMap["'"] = "&" + "#39;";
  function escHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) { return escMap[c]; });
  }
  var form = document.getElementById("filters");
  var q = document.getElementById("q");
  var country = document.getElementById("country");
  var type = document.getElementById("type");
  var results = document.getElementById("results");
  var count = document.getElementById("result-count");
  var onsen = document.getElementById("onsen");
  var timer = null;

  function isOnsen(spot) {
    var t = String(spot.type || "").toLowerCase();
    var e = String(spot.capybara_experience || "").toLowerCase();
    return t === "onsen" || e.indexOf("hot spring") !== -1 || e.indexOf("onsen") !== -1;
  }

  function cardHtml(spot) {
    return '<article data-testid="spot-card">' +
      '<h2><a href="/spots/' + escHtml(spot.id) + '">' + escHtml(spot.name) + '</a></h2>' +
      '<p class="meta"><span class="city">' + escHtml(spot.city) + '</span>, ' +
      '<span class="country">' + escHtml(spot.country) + '</span> &mdash; ' +
      '<span class="type">' + escHtml(spot.type) + '</span></p>' +
      '<p class="source"><a href="' + escHtml(spot.source_url) + '">Source</a></p>' +
      '</article>';
  }

  function render(spots) {
    count.textContent = spots.length === 1 ? "1 spot" : spots.length + " spots";
    if (spots.length === 0) {
      results.innerHTML = '<p data-testid="empty-state" class="empty">No capybaras here yet</p>';
    } else {
      results.innerHTML = spots.map(cardHtml).join("");
    }
  }

  function buildParams() {
    var p = [];
    var v = q.value.trim();
    if (v) p.push("q=" + encodeURIComponent(v));
    if (country.value) p.push("country=" + encodeURIComponent(country.value));
    if (type.value) p.push("type=" + encodeURIComponent(type.value));
    return p;
  }

  function refresh() {
    var p = buildParams();
    var qs = p.length ? "?" + p.join("&") : "";
    fetch("/api/spots" + qs, { headers: { "Accept": "application/json" } })
      .then(function (res) {
        if (!res.ok) return null;
        return res.json();
      })
      .then(function (spots) {
        if (!Array.isArray(spots)) return;
        if (onsen.checked) spots = spots.filter(isOnsen);
        render(spots);
        try { history.replaceState(null, "", "/" + qs); } catch (e) {}
      });
  }

  q.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(refresh, 150);
  });
  q.addEventListener("change", refresh);
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    clearTimeout(timer);
    refresh();
  });
  country.addEventListener("change", refresh);
  type.addEventListener("change", refresh);
  onsen.addEventListener("change", refresh);
})();
</script>
"""


def page_shell(title, body):
    dates = [s["verified_on"] for s in load_spots() if s.get("verified_on")]
    verified = max(dates) if dates else ""
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n"
        f"<style>{PAGE_CSS}</style>\n"
        "</head>\n<body>\n"
        f"{body}\n"
        f'<footer>Data verified {esc(verified)}</footer>\n'
        "</body>\n</html>\n"
    )


def spot_card_html(spot):
    return (
        f'<article data-testid="spot-card">'
        f'<h2><a href="/spots/{esc(spot["id"])}">{esc(spot["name"])}</a></h2>'
        f'<p class="meta"><span class="city">{esc(spot["city"])}</span>, '
        f'<span class="country">{esc(spot["country"])}</span> &mdash; '
        f'<span class="type">{esc(spot["type"])}</span></p>'
        f'<p class="source"><a href="{esc(spot["source_url"])}">Source</a></p>'
        f"</article>"
    )


def render_home(spots, all_spots, q="", country="", spot_type=""):
    countries = sorted({s["country"] for s in all_spots})
    country_opts = ['<option value="">All countries</option>'] + [
        f'<option value="{esc(c)}"{ " selected" if c.lower() == (country or "").lower() else ""}>{esc(c)}</option>'
        for c in countries
    ]
    type_opts = ['<option value="">All types</option>'] + [
        f'<option value="{t}"{ " selected" if t == (spot_type or "").lower() else ""}>{t}</option>'
        for t in KNOWN_TYPES
    ]

    n = len(spots)
    count_text = "1 spot" if n == 1 else f"{n} spots"
    if spots:
        cards = "\n".join(spot_card_html(s) for s in spots)
    else:
        cards = '<p data-testid="empty-state" class="empty">No capybaras here yet</p>'

    form = f"""<header><h1>CapyFinder</h1></header>
<form id="filters" action="/" method="get" role="search">
  <label for="q">Search spots</label>
  <input type="search" id="q" name="q" aria-label="Search spots" value="{esc(q)}" placeholder="Search spots" autocomplete="off">
  <label for="country">Country</label>
  <select id="country" name="country">{''.join(country_opts)}</select>
  <label for="type">Type</label>
  <select id="type" name="type">{''.join(type_opts)}</select>
  <label class="onsen-row" for="onsen"><input type="checkbox" id="onsen" name="onsen"> Hot spring spots only</label>
</form>
<p id="result-count">{count_text}</p>
<main id="results">
{cards}
</main>"""
    return page_shell("CapyFinder — where can I meet a capybara today?", form + HOME_JS)


def render_detail(spot):
    def cell(value):
        value = str(value)
        if value == "":
            return '<span class="dim">&mdash;</span>'
        return esc(value)

    fields = [
        ("City", spot["city"]),
        ("Country", spot["country"]),
        ("Type", spot["type"]),
        ("Capybara experience", spot["capybara_experience"]),
        ("Hours", spot["hours"]),
        ("Adult price", spot["adult_price"]),
        ("Source URL", spot["source_url"]),
        ("Verified on", spot["verified_on"]),
        ("ID", spot["id"]),
    ]
    dl = "".join(
        f'<div><dt>{esc(label)}</dt><dd>{cell(value)}</dd></div>'
        for label, value in fields
    )
    body = f"""<h1>{esc(spot["name"])}</h1>
<dl class="fields">{dl}</dl>
<p class="actions">
  <a href="{esc(spot["source_url"])}">Source</a>
  <a href="/">Back to all spots</a>
</p>"""
    return page_shell(f"{spot['name']} — CapyFinder", body)


def render_not_found():
    body = """<h1>Spot not found</h1>
<p><a href="/">Back to all spots</a></p>"""
    return page_shell("Spot not found — CapyFinder", body)


class Handler(BaseHTTPRequestHandler):
    server_version = "CapyFinder/1.0"

    def _send(self, status, body, content_type):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status, payload):
        self._send(status, json.dumps(payload, ensure_ascii=False), "application/json")

    def _send_html(self, status, payload):
        self._send(status, payload, "text/html; charset=utf-8")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query, keep_blank_values=True)

        if path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path in ("/api/health", "/api/health/"):
            self._send_json(200, {"ok": True, "spots": len(load_spots())})
            return

        if path in ("/api/spots", "/api/spots/"):
            result = filter_spots(load_spots(), params, strict_type=True)
            if result is None:
                self._send_json(
                    400,
                    {
                        "error": "unknown type; must be one of: "
                        + ", ".join(KNOWN_TYPES)
                    },
                )
            else:
                self._send_json(200, result)
            return

        if path in ("/api/stats", "/api/stats/"):
            spots = load_spots()
            by_country = {}
            by_type = {}
            for s in spots:
                by_country[s["country"]] = by_country.get(s["country"], 0) + 1
                by_type[s["type"]] = by_type.get(s["type"], 0) + 1
            self._send_json(
                200,
                {"total": len(spots), "by_country": by_country, "by_type": by_type},
            )
            return

        if path.startswith("/api/spots/"):
            rest = path[len("/api/spots/"):]
            if rest and "/" not in rest:
                for s in load_spots():
                    if s.get("id") == unquote(rest):
                        self._send_json(200, s)
                        return
            self._send_json(404, {"error": "spot not found"})
            return

        if path == "/":
            all_spots = load_spots()
            spots = filter_spots(all_spots, params, strict_type=False)
            q = params.get("q", [""])[0]
            country = params.get("country", [""])[0]
            spot_type = params.get("type", [""])[0]
            self._send_html(200, render_home(spots, all_spots, q, country, spot_type))
            return

        if path.startswith("/spots/"):
            rest = path[len("/spots/"):]
            if rest and "/" not in rest:
                for s in load_spots():
                    if s.get("id") == unquote(rest):
                        self._send_html(200, render_detail(s))
                        return
            self._send_html(404, render_not_found())
            return

        self._send_json(404, {"error": "not found"})


def main():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    print(f"capyfinder listening on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    main()