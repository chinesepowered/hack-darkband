# capyfinder (built by the Onsen factory)

Spec: [SPEC.md](SPEC.md).

## Run

```
python3 server.py
```

Listens on port **8000** by default. Override with the `PORT` env var:

```
PORT=9000 python3 server.py
```

## API (stage 1)

- `GET /api/health` → `{"ok": true, "spots": <count>}`
- `GET /api/spots` — filters: `country` (case-insensitive), `type` (case-insensitive; unknown type → 400), `q` (case-insensitive substring of name or city, surrounding whitespace ignored); AND-combined; sorted by `name`
- `GET /api/spots/{id}` — the spot, or 404 `{"error": ...}`

## Pages (stage 2)

- `GET /` — home: search box (Search spots), Country and Type selects, spot cards, result count, empty state
- `GET /spots/{id}` — spot detail with all fields, Source link, Back to all spots; unknown id → 404 "Spot not found"

Data: `data/spots.json` (Scout-verified; read fresh on every request).

Stage 3 (onsen mode, stats) per [PLAN.md](PLAN.md).