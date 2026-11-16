# CapyFinder — build plan

Run: `capyfinder-20261116-1846`. Spec: `SPEC.md`. Stages run in order; each stage is gated by Nap Guard
(`[gate] stage=N ACCEPTED` = Examiner exam PASS + Reviewer APPROVED on the same commit). No human involvement
until the final `[wake]`.

## Stage 1 — Data and API

- Data: Scout gathers `data/spots.json` from the live web (20–40 spots, at least 3 countries; every spot carries
  its `source_url`). The Architect sends the data request once, in the spec's exact words.
- Build: `GET /api/health`, `GET /api/spots` (filters `country`, `type`, `q`; AND-combined; unknown `type` → `400`;
  no match → `200 []`; sorted by `name` case-insensitive), `GET /api/spots/{id}` (unknown id → `404`).
- Done: server starts with one command (documented in README), listens on port `8000` (`PORT` env var overrides).

## Stage 2 — Web UI

- Build `/` — `h1` **CapyFinder**; search box labelled **Search spots** (`input type=search`); select **Country**
  (first option **All countries**, then one option per country in the data, option text = country code); select
  **Type** (first option **All types**, then each type); results as `<article data-testid="spot-card">` with name
  heading, city, country, type, and a **Source** link (`href` = `source_url`); count **N spots** / **1 spot**;
  empty state **No capybaras here yet**; card name links to `/spots/{id}`.
- Build `/spots/{id}` — `h1` = spot's name; every field shown; **Source** and **Back to all spots** links; unknown
  id shows **Spot not found** with HTTP `404`.
- Search/Country/Type controls must agree with the API filters. Every form control has a visible label.
- Accessibility Auditor: not available in the peer registry at kickoff (checked 2026-11-16, searches
  "Accessibility Auditor" and "accessibility" returned no reachable peers). No extra reviewer is added; stage 2 is
  reviewed by Reviewer only.

## Stage 3 — Onsen mode and stats

- Build: `GET /api/stats` → `{"total": n, "by_country": {...}, "by_type": {...}}`; counts agree with `/api/spots`;
  keys only for values that appear in the data.
- Home page: checkbox labelled **Hot spring spots only** — when checked, show only spots with `type` = `onsen` or
  whose `capybara_experience` mentions "hot spring" or "onsen" (case-insensitive); count updates.
- Footer: **Data verified YYYY-MM-DD**, the most recent `verified_on` in the data.

## Decisions

- Stack: builders' choice; constraints are one-command start and port `8000` with `PORT` override.
- UI rendering (server-side vs client-side): builders' choice.
- Spot schema, API paths, and field names are fixed by the acceptance contract — nothing renamed.
- `data/spots.json` is always Scout-collected (Nimble, live web), never typed by hand.
- Out of scope: accounts, booking, payments, maps.
- Runtime recruiting: checked before stage 2 — no "Accessibility Auditor" peer exists in the registry (see Stage 2);
  carrying on without it.

## Assumptions

- (none yet — if Scout returns low-confidence facts, the assumption made will be recorded here)