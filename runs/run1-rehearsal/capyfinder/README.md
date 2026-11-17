# capyfinder (built by the Onsen factory)

Spec: [SPEC.md](SPEC.md). Data: `data/spots.json` (gathered from the live web by Scout; every spot carries its `source_url`).

## Run

```
python3 server.py
```

Starts the server on http://localhost:8000 (no dependencies beyond the Python 3 standard library). Override the port with the `PORT` env var, e.g. `PORT=9000 python3 server.py`.

## API (stage 1)

- `GET /api/health` → `{"ok": true, "spots": <count>}`
- `GET /api/spots` → spots sorted by name (case-insensitive); filters `country`, `type`, `q` combine with AND; unknown `type` → 400
- `GET /api/spots/{id}` → one spot, or 404

## Web UI (stage 2)

- `GET /` — home: search box (**Search spots**), **Country** and **Type** selects, spot cards, live count
- `GET /spots/{id}` — detail page with every field, **Source** and **Back to all spots** links