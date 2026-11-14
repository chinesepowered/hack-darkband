# PLAN.md — CapyFinder

Spec: `SPEC.md` (run: capyfinder-20261114-0332, spec name: `capyfinder`).
Stages: **3**. Data: `data/spots.json` (fetched by Scout only, never hand-typed).

## Stages

### Stage 1 — Data and API
- Architect sends the spec's exact one-time data request to Scout: `data: places where the public can see capybaras (zoos, hot-spring parks, cafes, sanctuaries, farms) — 20 to 40 spots across at least 3 countries out=data/spots.json`
- On Scout's `[data]` reply: verify `data/spots.json` exists, is a JSON array, 20–40 rows, every row carries the contract fields incl. `source_url`; then seal with the Examiner.
- Builder implements: server starts with one command (documented in README), listens on port `8000` (`PORT` env var overrides); `GET /api/health`, `GET /api/spots` (filters `country`, `type`, `q`; AND-combined; unknown type → 400; no match → 200 []), `GET /api/spots/{id}` (404 on unknown).

### Stage 2 — Web UI
- Home `/` and detail `/spots/{id}` per the acceptance contract (h1 CapyFinder, labelled Search spots / Country / Type controls, `article[data-testid="spot-card"]` results, **N spots** / **1 spot** count, **No capybaras here yet** empty state, name → `/spots/{id}`, **Source** link, **Back to all spots**, unknown id → **Spot not found** + HTTP 404, visible labels on every form control).
- Search/Country/Type controls must agree with the API.

### Stage 3 — Onsen mode and stats
- `GET /api/stats` per contract (counts agree with `/api/spots`; keys only for values present).
- Home checkbox **Hot spring spots only**: show only `type=onsen` or `capybara_experience` mentioning "hot spring"/"onsen" (case-insensitive); count updates.
- Footer: **Data verified YYYY-MM-DD** = most recent `verified_on` in the data.

## Decisions
- Stack: builders' choice; hard requirements are one-command start (in README) and port 8000 with `PORT` override.
- Accessibility Auditor: **not available** (peer lookup returned 0 peers at plan time). Stage 2 will be graded by Examiner + Reviewer only. Recorded here per protocol; carry on.
- Sealing: `seal spec=capyfinder data=data/spots.json` goes to the Examiner only after the data file is verified.
- The Architect is the only one who asks Scout for this dataset, and only once.

## Assumptions
- Empty/whitespace-only `country`, `type`, `q` query params are treated as absent (no filter), not as an unknown type. Recorded by Builder, stage 1.
- Stage 3 (Builder): the hot-spring filter is exposed as an optional `hot_spring` query param on `/api/spots` and `/` (checked → `hot_spring=1`; values `0`/`false`/`off`/blank treated as absent). This lets the checkbox update the list live through the API and also works for a no-JS form submit. The `Data verified YYYY-MM-DD` footer (max `verified_on` in the data) is rendered on every HTML page (home, detail, 404).

## Status
- [x] PLAN.md written
- [x] `[plan]` posted to Builder + Reviewer
- [x] data request sent to Scout
- [x] data verified (34 rows, GB/JP/US, all contract fields, every row has source_url)
- [x] sealed with Examiner (`[seal]` ack: sha256=6ff1d05f34b0c78b249077640b84ea3a923ef3ca0494d12a788c9ae5e9a3cf24, stages=3, scenarios=18)
- [x] stage 1 → `[task]` posted; `[gate] stage=1 ACCEPTED` (exam=100%, review=approved, 1/3)
- [x] stage 2 → `[task]` posted (peer re-check: no Accessibility Auditor, Examiner + Reviewer only); `[gate] stage=2 ACCEPTED` (exam 50%→100%, review=approved, 1,2/3)
- [x] stage 3 → `[task]` posted
- [ ] stage 2 → `[task]`
- [ ] stage 3 → `[task]`
- [ ] all stages ACCEPTED → ship