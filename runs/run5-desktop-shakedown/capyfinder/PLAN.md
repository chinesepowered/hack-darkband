# PLAN — CapyFinder

Spec: `SPEC.md` · run folder: `capyfinder-20261116-1824` · spec name for the seal: **capyfinder** · data file: **data/spots.json**

## Stages

### Stage 1 — Data and API
- Data: Scout gathers `data/spots.json` from the live web (once; request sent by the Architect). 20–40 spots across ≥3 countries, every spot carrying its `source_url`.
- T1: Server skeleton — builder's stack choice; one command to start (documented in README), listens on port `8000`, `PORT` env var overrides.
- T2: `GET /api/health` → `200 {"ok": true, "spots": <count>}`.
- T3: `GET /api/spots` — JSON array sorted by `name` (case-insensitive); filters combine with AND:
  - `country` — exact, case-insensitive
  - `type` — exact, case-insensitive; unknown type → `400 {"error": ...}`
  - `q` — case-insensitive substring of `name` **or** `city`, surrounding whitespace ignored
  - no match → `200 []`
- T4: `GET /api/spots/{id}` → `200` spot or `404 {"error": ...}`.
- Exit: server starts with one command; API contract holds for whatever data Scout found.

### Stage 2 — Web UI
- T1: `/` home — `h1` **CapyFinder**; search box labelled **Search spots** (`input type=search`), results update on typing or Enter; select **Country** (first option **All countries**, then one option per country in the data, text = country code); select **Type** (first option **All types**, then each type).
- T2: Each result is `<article data-testid="spot-card">`: name as heading (linking to `/spots/{id}`), then city, country, type, and a **Source** link (`href` = `source_url`); result count **N spots** / **1 spot**; empty state text **No capybaras here yet**.
- T3: `/spots/{id}` detail — `h1` = spot's name; every field shown; **Source** link; **Back to all spots** link (`href` = `/`); unknown id → **Spot not found** with HTTP `404`.
- T4: Every form control has a visible label. Search/Country/Type controls must agree with the API.
- Note: Accessibility Auditor (if recruited) also reviews this stage and can block it.

### Stage 3 — Onsen mode and stats
- T1: `GET /api/stats` → `200 {"total": n, "by_country": {...}, "by_type": {...}}`; counts agree with `/api/spots`; only keys for values present in the data.
- T2: Home — checkbox labelled **Hot spring spots only**: checked → only spots with `type` = `onsen` or `capybara_experience` mentioning "hot spring"/"onsen" (case-insensitive); count updates.
- T3: Footer — **Data verified YYYY-MM-DD**, date = most recent `verified_on` in the data.

## Decisions
- Stack: builder's choice (spec leaves it open); hard constraints are one-command start, port `8000` with `PORT` override, and the API/UI contract above.
- Server-rendered vs client-side UI: builder's choice.
- Seal order: `seal spec=capyfinder data=data/spots.json` goes to the Examiner only after Scout's data file has landed, so the sealed exam is written against the actual data.
- Runtime recruiting: peer lookup happens before the stage 2 task; outcome recorded under Assumptions.

## Assumptions
- Spec name = `capyfinder` (run folder name before the date).
- Data as delivered (verified by the Architect): 24 spots, 5 countries (CA, GB, JP, TH, US), types cafe/farm/park/sanctuary/zoo, all rows carry a valid `source_url` and `verified_on`; ids unique and URL-safe. **No spot has `type` = `onsen`; exactly 2 spots (Izu Shaboten Zoo, Saitama Children's Zoo) mention "onsen"/"hot spring" in `capybara_experience`** — the stage 3 checkbox is therefore expected to show exactly those 2.
- Accessibility Auditor: TBD — recorded before the stage 2 task is posted (peer lookup outcome).