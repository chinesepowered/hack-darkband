# CapyFinder — build plan

Run: capyfinder-20261116-1904 · Spec: SPEC.md · Stages: 3
Gating: Nap Guard accepts a stage only on sealed-exam PASS + review APPROVED for the same commit. One stage at a time.

## Stage 1 — Data and API
- Data (one request, Architect sends; only the Architect asks): Scout gathers `data/spots.json` from the live web — 20–40 spots across at least 3 countries, every row carries a `source_url`. Never typed in by hand.
- Build: `GET /api/health`, `GET /api/spots` (filters `country`, `type`, `q`; case-insensitive; combined with AND; unknown `type` → 400; no match → 200 `[]`), `GET /api/spots/{id}` (unknown → 404).
- Exit: one-command start documented in the README; port 8000, `PORT` env overrides; contract holds for whatever data arrived.

## Stage 2 — Web UI
- Build: `/` — h1 **CapyFinder**; search box **Search spots** (`input type=search`, updates as you type or on Enter); **Country** select (first option **All countries**, then one option per country code in the data); **Type** select (first option **All types**, then each type); each result is `article[data-testid="spot-card"]` (name as heading, then city, country, type, **Source** link → `source_url`); result count **N spots**/**1 spot**; empty state **No capybaras here yet**; card name links to `/spots/{id}`. `/spots/{id}` — h1 = the spot's name; every field shown; **Source** link and **Back to all spots** link; unknown id → **Spot not found** with HTTP 404. Every form control has a visible label.
- The Search, Country and Type controls must agree with the API (same values, same case-insensitive matching).
- Pre-stage recruitment (Architect): look up peers for an **Accessibility Auditor**. If available, add it to the room and tell Builder + Reviewer that it will also review stage 2 and can block it. If not available, record it here and carry on.

## Stage 3 — Onsen mode and stats
- Build: `GET /api/stats` → `{"total": n, "by_country": {...}, "by_type": {...}}` (keys only for values that appear in the data; counts agree with `/api/spots`); home page checkbox **Hot spring spots only** (shows spots whose `type` is `onsen`, or whose `capybara_experience` mentions "hot spring" or "onsen", case-insensitive; count updates); footer **Data verified YYYY-MM-DD** where the date is the most recent `verified_on` in the data.

## Decisions
- D1 Stack is the Builder's choice (SPEC: "builders choose"); hard requirements only: one-command start documented in README, listen on port 8000 with `PORT` override.
- D2 The data request is verbatim from SPEC stage 1 and only the Architect sends it. One retry is permitted if a fetch returns 0 rows (attempts are recorded in Assumptions). If attempt 2 also returns 0 rows, this becomes a `[blocking-question]` — an empty dataset is not a safe assumption (it breaks the stage 3 footer contract, which needs a most-recent `verified_on`).
- D3 A `[task] stage=N+1` is posted only after Nap Guard's `[gate] stage=N ACCEPTED`.
- D4 The Examiner's seal is posted only after Scout's data is verified (file exists, has rows), so the sealed exam is grounded in the real data.
- D5 Out of scope per SPEC: accounts, booking, payments, maps.
- D7 No "Accessibility Auditor" peer exists (registry search before stage 2 returned no reachable peers) → stage 2 is reviewed by the Reviewer alone, per plan.
- D6 Exam sealed by Examiner: run=20261116-191723-c54045, sha256=7324ab7dfac23e4bb9ad4b66ca1f3a220c06d666c4cb033f7a01b7da0f5069cd, stages=3, scenarios=17. The `[reveal]` hash must match this commitment.

## Assumptions
- A1 Data lands at `data/spots.json` in this workspace, written by Scout (never typed in by hand).
- A2 Accessibility Auditor recruitment (checked before stage 2): `peers --search "Accessibility Auditor"` → no reachable peers. Stage 2 carries on with the Reviewer as sole reviewer (D7).
- A3 Data attempts: attempt 1 (19:10 UTC) returned rows=0, dropped_without_source=1, confidence=low → one retry per D2. Attempt 2 (19:14 UTC): rows=5, dropped_without_source=0 — JP + US (2 countries), types onsen/zoo/cafe, all 9 contract fields present, absolute https `source_url`, `verified_on`=2026-11-16. Deviation: below the requested 20–40 spots / ≥3 countries; we proceed with these 5 rows because SPEC stage 1's exit is "the API contract holds for whatever data Scout found" and the acceptance contract sets no minimum. No further retries (D2); exam is sealed against this exact data.