# CapyFinder — product spec

> Where can I meet a capybara today? A small web app that answers with a source for every fact.

The Onsen factory builds this from this file alone. Each stage is graded by the Examiner's **sealed exam**. Builders
never see the exam; they only see what a user would notice when something fails.

## Product

- **Audience:** capybara fans planning a day out.
- **Data:** `data/spots.json`, a JSON array of spots gathered from the live web by **Scout** (Nimble), never typed in
  by hand. Every spot carries the `source_url` it came from.
- **Stack:** the builders choose. It must start with one command written in the README and listen on port `8000`
  (the `PORT` env var overrides it).
- **Out of scope:** accounts, booking, payments, maps.

## Acceptance contract

The exam only uses what this section defines. Builders must not rename anything here.

### Spot object

| field | type | rules |
|---|---|---|
| `id` | string | URL-safe slug, unique |
| `name` | string | required |
| `city` | string | required |
| `country` | string | ISO 3166-1 alpha-2, uppercase |
| `type` | string | one of `zoo`, `onsen`, `cafe`, `sanctuary`, `farm`, `park` |
| `capybara_experience` | string | may be empty |
| `hours` | string | may be empty |
| `adult_price` | string | may be empty |
| `source_url` | string | absolute `http(s)` URL |
| `verified_on` | string | `YYYY-MM-DD` |

### API

- `GET /api/health` → `200` `{"ok": true, "spots": <count>}`
- `GET /api/spots` → `200`, JSON array of spot objects, sorted by `name` (case-insensitive).
  - `country` — matches `country` exactly, case-insensitive (`jp` = `JP`).
  - `type` — matches `type` exactly, case-insensitive. An unknown type → `400` `{"error": "..."}`.
  - `q` — case-insensitive substring of `name` **or** `city`; surrounding whitespace is ignored.
  - Filters combine with AND. No match → `200` and `[]`.
- `GET /api/spots/{id}` → `200` spot, or `404` `{"error": "..."}`.
- `GET /api/stats` *(stage 3)* → `200` `{"total": n, "by_country": {"JP": n, …}, "by_type": {"zoo": n, …}}`; the
  counts agree with `/api/spots`.

### Web UI

- `/` — home page
  - `h1` heading **CapyFinder**
  - a search box labelled **Search spots** (`input type=search`); results update as you type or on Enter
  - a select labelled **Country**: first option **All countries**, then one option per country in the data (option
    text = the country code)
  - a select labelled **Type**: first option **All types**, then each type
  - each result is an `<article data-testid="spot-card">` showing the name as a heading, then city, country, type,
    and a link named **Source** whose `href` is the spot's `source_url`
  - a result count reading **N spots** (or **1 spot**)
  - when nothing matches, the text **No capybaras here yet**
  - the card's name links to `/spots/{id}`
- `/spots/{id}` — detail page
  - `h1` = the spot's name; every field of the spot is shown
  - a link named **Source** (`href` = `source_url`) and a link named **Back to all spots** (`href` = `/`)
  - an unknown id shows **Spot not found** with HTTP status `404`
- Every form control has a visible label.

## Stage 1 — Data and API

- Ask Scout for the data: `@Scout data: places where the public can see capybaras (zoos, hot-spring parks, cafes,
  sanctuaries, farms) — 20 to 40 spots across at least 3 countries out=data/spots.json`
- Implement `/api/health`, `/api/spots` (all filters) and `/api/spots/{id}` per the contract.
- Done when the server starts with one command and the API contract holds for whatever data Scout found.

## Stage 2 — Web UI

- Implement `/` and `/spots/{id}` per the contract (server-rendered or client-side; builders' choice).
- The Search, Country and Type controls must agree with the API.

## Stage 3 — Onsen mode and stats

- Implement `GET /api/stats` per the contract.
- Home page: a checkbox labelled **Hot spring spots only**. When it's checked, only spots whose `type` is `onsen`, or
  whose `capybara_experience` mentions "hot spring" or "onsen" (case-insensitive), are shown, and the count updates.
- Footer: **Data verified YYYY-MM-DD**, where the date is the most recent `verified_on` in the data.
