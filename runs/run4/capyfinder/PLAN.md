# PLAN — capyfinder

Spec: SPEC.md (CapyFinder — "where can I meet a capybara today?"). Stages = 3, in spec order.

## Stages

1. **Stage 1 — Data and API**
   - Architect asks Scout (once, verbatim from spec) for `data/spots.json`: 20–40 spots across ≥3 countries, every spot with `source_url`.
   - Build `GET /api/health`, `GET /api/spots` (filters: `country`, `type`, `q`; AND-combined; unknown type → 400), `GET /api/spots/{id}` (404 shape) per the acceptance contract.
   - One-command start (README), port 8000, `PORT` env override.
   - Done: server starts; API contract holds for whatever Scout found.
2. **Stage 2 — Web UI**
   - `GET /` (h1 CapyFinder; search box labelled "Search spots"; Country/Type selects with "All countries"/"All types" first options; `article[data-testid="spot-card"]` cards with name heading → `/spots/{id}`, city, country, type, Source link; result count "N spots"/"1 spot"; "No capybaras here yet" empty state).
   - `GET /spots/{id}` (h1 = name, all fields, Source link, "Back to all spots" → `/`; unknown id → "Spot not found" + HTTP 404).
   - Controls must agree with the API; every form control has a visible label.
   - Note: no "Accessibility Auditor" peer exists in the roster (checked via band_lookup_peers, 0 peers) — Reviewer carries label/accessibility checks alone; stage 2 not additionally gated.
3. **Stage 3 — Onsen mode and stats**
   - `GET /api/stats` (`total`, `by_country`, `by_type`; keys only for values present; counts agree with `/api/spots`).
   - Home checkbox "Hot spring spots only": keep `type == onsen` or `capybara_experience` containing "hot spring"/"onsen" (case-insensitive); count updates.
   - Footer "Data verified YYYY-MM-DD" = most recent `verified_on` in data.

## Decisions

- Data flow: Scout → `data/spots.json` only. No hand-typed spots; `verified_on` from Scout's fetch.
- Exam seal: `spec=capyfinder data=data/spots.json` — Examiner reads the real data so the sealed exam cannot demand results the data can't produce. Seal sent only after Scout's `[data]` reply and the file verified (exists, has rows).
- Stack: Builder's choice per spec; must satisfy README one-command start + port 8000/`PORT`.
- `[task] stage=1` is issued only after Scout's data is verified in the file, so the API is built against real data.

## Run log

- 2026-11-14 04:47 — Scout `[data]` rows=36, dropped_without_source=0, saved `data/spots.json` (+ `data/spots.sources.json`). Verified: 36 rows; countries BR/GB/JP/US; types cafe/farm/park/zoo; all contract fields present; ids unique; `source_url` absolute on every row; `verified_on` well-formed.
- Seal sent to Examiner: `spec=capyfinder data=data/spots.json` (noted to Examiner that no `onsen`-type or `sanctuary` rows exist in the data).
- `[task] stage=1` issued to Builder.
- Examiner `[seal]` run=20261114-045130-0c6f0d stages=3 scenarios=20 sha256=138aa57aa9039a53041983f97f105ad35f4f9d21f0ae42ebdcad399ea5cb0bca — exam sealed; publish hash must match at reveal.
- `[gate] stage=1 ACCEPTED` exam=100% review=approved (1/3). Re-checked peers before stage 2: still no "Accessibility Auditor". `[task] stage=2` issued to Builder.
- 2026-11-14 05:30 — Nap Guard `[gate] resume=true`, Builder re-added to room. Repo shows stage-2 commits `4a4d6b1` → `4731c94` → `a57aa44` → `75d2f77` (last: triple-wired Search label). No stage-2 gate on record. Sent Builder a status check: confirm stage 2 state and post `[ready] stage=2` if complete and unsubmitted.
- 2026-11-14 05:34 — Builder status: stage 2 **mid-verification, not yet gateable**. App code = `75d2f77`; HEAD `731832e` is a docs-only PLAN.md log commit (verified: working tree clean). `[ready] stage=2 commit=75d2f77` already in the room (not re-posted). Exam round 4 on 75d2f77 = **FAIL 6/7**, single country-filter failure whose text arrived truncated; Builder asked Examiner to re-send full text. Builder's headless repro of the scenario passes on all facets; if full text contradicts, fix; else `[dispute]`. Reviewer's earlier BLOCKED was provenance-only, resolved at 75d2f77; formal `[review]` on that commit pending. Room waits on Examiner's re-sent failure text + Reviewer's formal review; then Nap Guard gates (exam PASS + review APPROVED on same commit).
- 2026-11-14 05:37 — `[gate] stage=2 ACCEPTED` exam curve 57%→86%→86%→86%→100% review=approved (2/3). `[task] stage=3` issued to Builder (final stage) with data facts: 36 rows; US=12, JP=11, GB=9, BR=4; zoo=24, park=6, cafe=5, farm=1; no `onsen`-type rows (checkbox matches via `capybara_experience` text); max `verified_on` = 2026-11-14.

## Assumptions

- (none yet — low-confidence Scout answers and safe assumptions are recorded here as they arise)