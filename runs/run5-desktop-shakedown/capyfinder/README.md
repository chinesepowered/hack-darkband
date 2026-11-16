# capyfinder (built by the Onsen factory)

Spec: [SPEC.md](SPEC.md). A small web app that answers "where can I meet a capybara today?" with a source for every fact.

## Run

```
python3 app.py
```

Listens on port `8000`. Override with the `PORT` env var, e.g. `PORT=9000 python3 app.py`.

Data is read from `data/spots.json` (collected from the live web by Scout; every spot carries its `source_url`).

## API

- `GET /api/health` → `{"ok": true, "spots": <count>}`
- `GET /api/spots` → JSON array of spots sorted by `name` (case-insensitive).
  - `country` — exact, case-insensitive
  - `type` — exact, case-insensitive (`zoo`, `onsen`, `cafe`, `sanctuary`, `farm`, `park`); unknown type → `400`
  - `q` — case-insensitive substring of `name` or `city`
  - filters combine with AND; no match → `200 []`
- `GET /api/spots/{id}` → spot, or `404`