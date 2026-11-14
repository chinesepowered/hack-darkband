# PLAN — capyfinder

Spec: SPEC.md. Spec name: `capyfinder`. Data: `data/spots.json` (supplied by Scout, never hand-typed).
Stack: builders' choice per spec; server must start with one command (README) and listen on port 8000 (`PORT` overrides).

## Stages

### Stage 1 — Data and API
- Request: `@Scout data: places where the public can see capybaras (zoos, hot-spring parks, cafes, sanctuaries, farms) — 20 to 40 spots across at least 3 countries out=data/spots.json`
- When Scout replies `[data]`: verify `data/spots.json` exists, is a JSON array, has 20–40 rows, ≥3 countries, every spot has `source_url` + `verified_on`, fields match the Spot object table.
- [VERIFIED 2026-11-14] 40 rows, 5 countries (JP 6, US 31, BR 1, AR 1, PE 1), types {zoo 30, park 7, farm 2, sanctuary 1}; all fields/slugs/URLs/dates valid, 0 dropped. Note: no `onsen`-type spots in this dataset, so stage 3's hot-spring filter can only match via `capybara_experience`.
- [SUPERSEDED 2026-11-14] The duplicate Scout request ran and rewrote the file. Current dataset (FINAL, sha256 `3b8e0ef2…`): 30 rows, 7 countries (JP 10, US 10, GB 5, AU 2, NZ 1, DE 1, DK 1), types {zoo 14, onsen 5, cafe 5, park 4, sanctuary 1, farm 1}; all fields/slugs/URLs/dates valid. 5 rows are type `onsen`; no row's `capybara_experience` contains literal "hot spring"/"onsen" except one hyphenated "hot-spring" (row is type onsen anyway) — stage 3 checkbox therefore shows the 5 onsen-type spots. Examiner re-sealed against this file; Builder instructed to reload from disk.
- Seal: `seal spec=capyfinder data=data/spots.json` → @Examiner (only after the data file is verified). Seals on record: `20261114-024407-9c9657` (17 scenarios, sha256 759d213b…) then superseded by **`20261114-024856-01efb0` (20 scenarios, sha256 076f12b213e3f1cb2aaf55e05ef4b19f948cc1044c6b15389e48058a543ad720) — the governing commitment**, sealed after the 30-row file correction and Builder's re-verification.
- Build: `GET /api/health`, `GET /api/spots` (filters `country`, `type`, `q`; unknown type → 400; AND-combined; no match → `[]`), `GET /api/spots/{id}` (404 on unknown). Sorted by `name` case-insensitive.
- Definition of done: server starts with one command; API contract holds for whatever data Scout found.

### Stage 2 — Web UI
- `/`: `h1` **CapyFinder**; search box labelled **Search spots** (`input type=search`, live or on Enter); **Country** select (first option **All countries**, then one option per country in the data, text = country code); **Type** select (first option **All types**, then each type); results as `<article data-testid="spot-card">` with name heading, city, country, type, **Source** link → `source_url`; name links to `/spots/{id}`; count **N spots** / **1 spot**; empty state **No capybaras here yet**.
- `/spots/{id}`: `h1` = spot name, every field shown, **Source** link, **Back to all spots** → `/`; unknown id → **Spot not found** with HTTP 404.
- Every form control has a visible label. Controls must agree with the API.
- Runtime recruiting (before this stage): `band_lookup_peers`; if an **Accessibility Auditor** peer exists, add it to the room and tell Builder + Reviewer it co-reviews stage 2 and can block it. If not, record here under Assumptions and carry on.
- [RECRUIT 2026-11-14] `band_lookup_peers` returned 0 available peers — no Accessibility Auditor exists. Stage 2 review is Reviewer-only; accessibility checked against the spec's own requirements (visible labels, labelled controls).

### Stage 3 — Onsen mode and stats
- `GET /api/stats` → `{"total", "by_country", "by_type"}`; counts agree with `/api/spots`; keys only for values present in data.
- Home page: checkbox labelled **Hot spring spots only**; when checked, show only spots with `type == onsen` or `capybara_experience` mentioning "hot spring"/"onsen" (case-insensitive); count updates.
- Footer: **Data verified YYYY-MM-DD** = most recent `verified_on` in the data.

## Decisions
- Stack left to Builder (spec permits). README must document the single start command.
- Spec name for the seal = `capyfinder` (run folder name before the date).
- Country filter semantics are exact match, case-insensitive, per acceptance contract.
- Exam seal happens only after Scout's data is on disk and verified, so the hidden exam is grounded in real data.

## Assumptions
- (none yet — to be appended as the run proceeds; low-confidence Scout answers land here and Nap Guard batches them for the human)
- [A1] Duplicate Scout data request (Builder's ~02:39, raced with mine): the second run's output (30-row dataset) is treated as the final dataset; no further writes to `data/spots.json` are expected or allowed. Scout's duplicate-run `[answer]` was confidence=low with 0 sources; verified the file on disk instead.
- [A2] Type select options: spec says "first option All types, then each type" (no "in the data" qualifier, unlike the Country clause). Interpretation: one option per type present in the data (parallel with Country). If the sealed exam reads it as all six allowed types, that surfaces as an exam failure and Builder may raise `[dispute]`.