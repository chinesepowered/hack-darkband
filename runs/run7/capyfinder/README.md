# capyfinder (built by the Onsen factory)

Spec: [SPEC.md](SPEC.md). "Where can I meet a capybara today?" — with a source for every fact.

## Run

```sh
python3 app.py
```

The server listens on port `8000`; the `PORT` environment variable overrides it
(e.g. `PORT=9000 python3 app.py`). No dependencies — Python 3 standard library only.

Data comes from `data/spots.json` (collected from the live web; every spot carries a `source_url`).

## Web UI

- `GET /` — home page: **CapyFinder** heading, a **Search spots** box, **Country** and **Type** selects,
  and a **Hot spring spots only** checkbox (shows spots whose type is `onsen` or whose capybara experience
  mentions "hot spring"/"onsen"). Results show as cards (name links to the detail page, plus city, country,
  type and a **Source** link); a count reads **N spots** / **1 spot**, and an empty result shows
  **No capybaras here yet**. The controls use the same values and case-insensitive matching as the API.
  A footer reads **Data verified YYYY-MM-DD** (the most recent `verified_on` in the data).
- `GET /spots/{id}` — detail page with every field of the spot, a **Source** link and **Back to all spots**;
  unknown ids get **Spot not found** with HTTP 404.

## API

- `GET /api/health` → `200` `{"ok": true, "spots": <count>}`
- `GET /api/spots` → `200`, JSON array of spot objects sorted by `name` (case-insensitive).
  Optional query filters, combined with AND:
  - `country` — exact match, case-insensitive (`jp` = `JP`)
  - `type` — exact match, case-insensitive; one of `zoo`, `onsen`, `cafe`, `sanctuary`, `farm`, `park`; an unknown type → `400`
  - `q` — case-insensitive substring of `name` or `city`, surrounding whitespace ignored
  - no match → `200` `[]`
- `GET /api/spots/{id}` → `200` the spot, or `404` `{"error": "..."}`
- `GET /api/stats` → `200` `{"total": n, "by_country": {...}, "by_type": {...}}`; counts agree with
  `/api/spots`, and `by_country` / `by_type` only contain keys for values present in the data.