#!/usr/bin/env python3
"""CapyFinder — where can I meet a capybara today? (stages 1-2: API + web UI)"""

import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "spots.json")
PORT = int(os.environ.get("PORT", "8000"))

VALID_TYPES = ("zoo", "onsen", "cafe", "sanctuary", "farm", "park")
SPOT_FIELDS = ("id", "name", "city", "country", "type", "capybara_experience",
               "hours", "adult_price", "source_url", "verified_on")

STYLE = """
body { font-family: system-ui, -apple-system, sans-serif; max-width: 46rem; margin: 2rem auto; padding: 0 1rem; color: #222; }
h1 { margin-bottom: .25rem; }
.tagline { margin-top: 0; color: #555; }
form.spots-form { display: flex; flex-wrap: wrap; gap: .75rem 1.25rem; align-items: center; margin: 1.25rem 0; }
label { font-weight: 600; }
input[type="search"], select { padding: .35rem .5rem; font-size: 1rem; }
input[type="search"] { flex: 1 1 14rem; }
[data-testid="spot-card"] { border: 1px solid #ddd; border-radius: 8px; padding: .75rem 1rem; margin: .5rem 0; }
[data-testid="spot-card"] h2 { margin: 0 0 .35rem; font-size: 1.15rem; }
[data-testid="spot-card"] p { margin: .15rem 0; }
#results [data-testid="empty-state"] { color: #555; font-style: italic; }
dl.spot-fields div { display: grid; grid-template-columns: 11rem 1fr; gap: .5rem; padding: .35rem 0; border-bottom: 1px solid #eee; }
dl.spot-fields dt { font-weight: 600; }
dl.spot-fields dd { margin: 0; overflow-wrap: anywhere; }
.actions { margin-top: 1rem; }
.actions a { margin-right: 1rem; }
"""

PAGE_SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{style}</style>
</head>
<body>
{body}
{script}
</body>
</html>
"""


def esc(value, quote=False):
    return html.escape("" if value is None else str(value), quote=quote)


def load_spots():
    with open(DATA_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("data/spots.json must be a JSON array")
    return data


def first_param(query, name):
    values = query.get(name)
    if not values:
        return None
    return values[0]


def filter_spots(spots, country, stype, q):
    q_norm = q.strip().lower() if q is not None else None
    out = []
    for spot in spots:
        if country is not None and (spot.get("country") or "").lower() != country.lower():
            continue
        if stype is not None and (spot.get("type") or "").lower() != stype.lower():
            continue
        if q_norm:
            name = (spot.get("name") or "").lower()
            city = (spot.get("city") or "").lower()
            if q_norm not in name and q_norm not in city:
                continue
        out.append(spot)
    return out


def apply_filters(spots, query):
    """Shared by the API and the web UI so they always agree."""
    stype = first_param(query, "type")
    if stype is not None and stype.lower() not in VALID_TYPES:
        return (400, {"error": "unknown type: %s (valid types: %s)"
                      % (stype, ", ".join(VALID_TYPES))}), None
    country = first_param(query, "country")
    q = first_param(query, "q")
    result = filter_spots(spots, country, stype, q)
    result.sort(key=lambda s: (s.get("name") or "").lower())
    return None, result


def countries_in_data(spots):
    return sorted({s.get("country") for s in spots if s.get("country")})


def is_hot_spring(spot):
    if (spot.get("type") or "").lower() == "onsen":
        return True
    experience = (spot.get("capybara_experience") or "").lower()
    return "hot spring" in experience or "onsen" in experience


def latest_verified_on(spots):
    dates = {s.get("verified_on") for s in spots if s.get("verified_on")}
    return max(dates) if dates else None


def compute_stats(spots):
    by_country = {}
    by_type = {}
    for spot in spots:
        country = spot.get("country")
        stype = spot.get("type")
        if country:
            by_country[country] = by_country.get(country, 0) + 1
        if stype:
            by_type[stype] = by_type.get(stype, 0) + 1
    return {
        "total": len(spots),
        "by_country": {k: by_country[k] for k in sorted(by_country)},
        "by_type": {k: by_type[k] for k in sorted(by_type)},
    }


def render_card(spot):
    return (
        '<article data-testid="spot-card">\n'
        '  <h2><a href="/spots/%s">%s</a></h2>\n'
        '  <p>%s</p>\n'
        '  <p>%s</p>\n'
        '  <p>%s</p>\n'
        '  <p><a href="%s">Source</a></p>\n'
        '</article>\n'
        % (esc(spot.get("id"), True), esc(spot.get("name")),
           esc(spot.get("city")), esc(spot.get("country")),
           esc(spot.get("type")), esc(spot.get("source_url"), True))
    )


def render_results(spot_list):
    n = len(spot_list)
    if n == 0:
        return '<p data-testid="empty-state">No capybaras here yet</p>\n'
    count = "1 spot" if n == 1 else "%d spots" % n
    return '<p data-testid="spot-count">%s</p>\n' % count + "".join(render_card(s) for s in spot_list)


HOME_SCRIPT = """
<script>
(function () {
  var form = document.getElementById("spot-form");
  var qInput = document.getElementById("q");
  var countrySel = document.getElementById("country");
  var typeSel = document.getElementById("type");
  var onsenBox = document.getElementById("onsen");
  var results = document.getElementById("results");
  var timer = null;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function isHotSpring(spot) {
    var experience = String(spot.capybara_experience == null ? "" : spot.capybara_experience).toLowerCase();
    return String(spot.type == null ? "" : spot.type).toLowerCase() === "onsen" ||
      experience.indexOf("hot spring") !== -1 ||
      experience.indexOf("onsen") !== -1;
  }

  function card(spot) {
    return '<article data-testid="spot-card">' +
      '<h2><a href="/spots/' + esc(spot.id) + '">' + esc(spot.name) + '</a></h2>' +
      '<p>' + esc(spot.city) + '</p>' +
      '<p>' + esc(spot.country) + '</p>' +
      '<p>' + esc(spot.type) + '</p>' +
      '<p><a href="' + esc(spot.source_url) + '">Source</a></p>' +
      '</article>';
  }

  function render(list) {
    var html = "";
    if (list.length === 0) {
      html = '<p data-testid="empty-state">No capybaras here yet</p>';
    } else {
      html = '<p data-testid="spot-count">' + list.length + (list.length === 1 ? " spot" : " spots") + '</p>';
      for (var i = 0; i < list.length; i++) html += card(list[i]);
    }
    results.innerHTML = html;
  }

  function apply() {
    var params = [];
    var q = qInput.value || "";
    if (q.trim()) params.push("q=" + encodeURIComponent(q));
    var c = countrySel.value || "";
    if (c) params.push("country=" + encodeURIComponent(c));
    var t = typeSel.value || "";
    if (t) params.push("type=" + encodeURIComponent(t));
    fetch("/api/spots" + (params.length ? "?" + params.join("&") : ""))
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then(function (list) {
        if (onsenBox.checked) list = list.filter(isHotSpring);
        render(list);
      })
      .catch(function () {});
  }

  qInput.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(apply, 200);
  });
  countrySel.addEventListener("change", apply);
  typeSel.addEventListener("change", apply);
  onsenBox.addEventListener("change", apply);
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    apply();
  });
})();
</script>
"""


def onsen_on_param(query):
    value = first_param(query, "onsen")
    return value is not None and value != "0"


def render_home(filtered, q, country, stype, countries, onsen_on, verified_date):
    q_val = q if q is not None else ""
    country_options = '<option value="">All countries</option>\n' + "".join(
        '<option value="%s"%s>%s</option>\n'
        % (esc(c, True), ' selected' if (country or "").lower() == c.lower() else "", esc(c))
        for c in countries
    )
    type_options = '<option value="">All types</option>\n' + "".join(
        '<option value="%s"%s>%s</option>\n'
        % (t, ' selected' if (stype or "").lower() == t else "", t)
        for t in VALID_TYPES
    )
    body = (
        "<h1>CapyFinder</h1>\n"
        '<p class="tagline">Where can I meet a capybara today?</p>\n'
        '<form id="spot-form" class="spots-form" method="get" action="/">\n'
        '  <label for="q">Search spots</label>\n'
        '  <input id="q" name="q" type="search" value="%s">\n'
        '  <label for="country">Country</label>\n'
        '  <select id="country" name="country">\n%s  </select>\n'
        '  <label for="type">Type</label>\n'
        '  <select id="type" name="type">\n%s  </select>\n'
        '  <label for="onsen">Hot spring spots only</label>\n'
        '  <input id="onsen" name="onsen" type="checkbox" value="1"%s>\n'
        "</form>\n"
        '<div id="results">\n%s</div>\n'
        '<footer>Data verified %s</footer>\n'
        % (esc(q_val, True), country_options, type_options,
           ' checked' if onsen_on else "", render_results(filtered), esc(verified_date))
    )
    return PAGE_SHELL.format(title="CapyFinder", style=STYLE, body=body, script=HOME_SCRIPT)


def render_detail(spot):
    rows = "\n".join(
        '  <div><dt>%s</dt><dd>%s</dd></div>' % (f, esc(spot.get(f))) for f in SPOT_FIELDS
    )
    body = (
        "<h1>%s</h1>\n"
        "<dl class=\"spot-fields\">\n%s\n</dl>\n"
        '<p class="actions"><a href="%s">Source</a><a href="/">Back to all spots</a></p>\n'
        % (esc(spot.get("name")), rows, esc(spot.get("source_url"), True))
    )
    return PAGE_SHELL.format(title="%s — CapyFinder" % (spot.get("name") or "Spot"),
                             style=STYLE, body=body, script="")


def render_spot_not_found():
    body = ('<h1>Spot not found</h1>\n'
            '<p class="actions"><a href="/">Back to all spots</a></p>\n')
    return PAGE_SHELL.format(title="Spot not found — CapyFinder", style=STYLE, body=body, script="")


class Handler(BaseHTTPRequestHandler):
    server_version = "CapyFinder/1.0"

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status, html_body):
        body = html_body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _spots_or_error(self):
        try:
            return None, load_spots()
        except (OSError, ValueError) as exc:
            return self._send_json(500, {"error": "data unavailable: %s" % exc}), None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)

        if path == "/api/health":
            err, spots = self._spots_or_error()
            if err:
                return err
            return self._send_json(200, {"ok": True, "spots": len(spots)})

        if path == "/api/spots":
            err, spots = self._spots_or_error()
            if err:
                return err
            error, result = apply_filters(spots, query)
            if error:
                return self._send_json(error[0], error[1])
            return self._send_json(200, result)

        if path == "/api/stats":
            err, spots = self._spots_or_error()
            if err:
                return err
            return self._send_json(200, compute_stats(spots))

        if path.startswith("/api/spots/"):
            spot_id = unquote(path[len("/api/spots/") :])
            if not spot_id or "/" in spot_id:
                return self._send_json(404, {"error": "spot not found"})
            err, spots = self._spots_or_error()
            if err:
                return err
            for spot in spots:
                if spot.get("id") == spot_id:
                    return self._send_json(200, spot)
            return self._send_json(404, {"error": "spot not found"})

        if path in ("", "/"):
            err, spots = self._spots_or_error()
            if err:
                return err
            error, result = apply_filters(spots, query)
            if error:
                return self._send_json(error[0], error[1])
            onsen_on = onsen_on_param(query)
            if onsen_on:
                result = [s for s in result if is_hot_spring(s)]
            return self._send_html(200, render_home(
                result, first_param(query, "q"), first_param(query, "country"),
                first_param(query, "type"), countries_in_data(spots), onsen_on,
                latest_verified_on(spots)))

        if path.startswith("/spots/"):
            spot_id = unquote(path[len("/spots/") :])
            if not spot_id or "/" in spot_id:
                return self._send_html(404, render_spot_not_found())
            err, spots = self._spots_or_error()
            if err:
                return err
            for spot in spots:
                if spot.get("id") == spot_id:
                    return self._send_html(200, render_detail(spot))
            return self._send_html(404, render_spot_not_found())

        return self._send_json(404, {"error": "not found"})


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("CapyFinder listening on http://localhost:%d" % PORT, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()