# capyfinder (built by the Onsen factory)

Spec: [SPEC.md](SPEC.md).

## Run

    python3 server.py

Starts the API on port `8000` (override with the `PORT` env var). Data is read from
`data/spots.json` at startup. No dependencies beyond the Python standard library.

API: `GET /api/health`, `GET /api/spots` (filters: `country`, `type`, `q`), `GET /api/spots/{id}`.
