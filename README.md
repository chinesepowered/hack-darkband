<p align="center"><img src="assets/capybara.svg" width="180" alt="A sleepy capybara soaking in a hot spring with a yuzu on its head"></p>

# Onsen 🛁

**A dark software factory on BAND that has one rule: don't wake the capybara.**

The human is a capybara napping in a hot spring. A crew of coding agents in one BAND room turns a written spec into
working software. Two things make it different:

1. **A sealed exam.** The Examiner writes hidden acceptance scenarios from the spec and posts only their SHA-256.
   Builders never see the scenarios: BAND delivers a message only to the agents it mentions, and the exam lives in the
   Examiner's own container. When a stage fails, builders see what a *user* would notice, never the test. Nobody grades
   their own homework.
2. **Ask the web, not the human.** Every factual question goes to Scout, which answers from the live web with
   [Nimble](https://www.nimbleway.com/), citing a source and a confidence grade for each claim. Only a low-confidence answer
   reaches the human, and even that waits for the one wake-up.

Nap Guard is the only agent allowed to wake the human. It wakes them once, to ask "ship or hold?" (plus a chill break
if work starts thrashing). The run ends with a receipt that counts how many times the capybara was woken.

## The crew

| Agent | Runs on | Job | BAND collaboration signal |
|---|---|---|---|
| Architect | BAND Desktop · Claude Code | plan, hand out stages, recruit specialists at runtime | roster decided at runtime |
| Builder | BAND Desktop · Codex | build each stage; fix what the exam and the review report | dependent handoff |
| Reviewer | BAND Desktop · Claude Code (never the Builder's vendor) | read the diff and say no when needed | verdict that can be blocked |
| Scout | `onsen-scout` · Nimble | cited answers, current docs, datasets with a source on every row | dependent handoff |
| Examiner | Docker · Claude + Playwright | seal the hidden exam, grade each stage | boundary BAND enforces |
| Nap Guard | `onsen-nap-guard` | stage gate, batched questions, chill breaks, the one wake-up, the receipt | one human gate + hard stop |

Agent instructions live in [crew/](crew/). The message protocol is in [crew/PROTOCOL.md](crew/PROTOCOL.md).

## One run

```
human ──"@Architect build SPEC.md"──▶ Architect ──seal──▶ Examiner ──[seal] sha256──▶ (room)
Architect ──data:──▶ Scout ──Nimble dataset agent──▶ data/spots.json (a source on every row)
Architect ──[task] stage=1──▶ Builder ──docs:/ask:──▶ Scout          (low confidence ─▶ Nap Guard batches it)
Builder ──[ready] stage=1──▶ Examiner + Reviewer
Examiner ──[exam] FAIL 62% "what a user noticed"──▶ Builder   ·   Reviewer ──[review] BLOCKED: …──▶ Builder
… fix …  ──▶  [exam] PASS 100%  +  [review] APPROVED  ──▶ Nap Guard ──[gate] ACCEPTED──▶ Architect ──▶ stage 2 …
Nap Guard ──[wake] #1 "ship or hold?"──▶ human ──ship──▶ [receipt] ──▶ Examiner [reveal] (hash matches the seal)
```

## Quickstart

You need:
- BAND Desktop, with Claude Code and Codex installed and signed in
- Docker
- [uv](https://docs.astral.sh/uv/) and Python 3.11+
- API keys for BAND, Nimble and Anthropic

```bash
cp .env.example .env
```

Fill in the keys in `.env`, then:

```bash
uv sync
```

```bash
uv run onsen-register
```

This registers Scout, Examiner and Nap Guard. It needs 3 free agent slots, and keys go to `~/.onsen/`, outside the repo.

```bash
ws=$(scripts/new-run.sh capyfinder) && echo "$ws"
```

This creates a fresh product workspace with SPEC.md in it. Then start the three SDK agents, each in its own terminal:

```bash
ONSEN_WORKSPACE="$ws" uv run onsen-scout
```

```bash
uv run onsen-nap-guard
```

```bash
docker compose -f docker/compose.yaml up --build examiner
```

In BAND Desktop:
1. Create **Architect**, **Builder** and **Reviewer**. Point each one's workspace at `$ws` and paste the Instructions block
   from its file in [crew/](crew/).
2. Create a room with all six agents and yourself.
3. Post `@Architect build SPEC.md`, then go have a bath.

Check a single agent live before a full run:

```bash
uv run onsen-smoke --agent scout --say "ask: Which zoo started the capybara hot-spring bath?"
```

Run the tests. The Examiner is graded against a reference app with injected bugs:

```bash
uv run pytest
```

## How the pieces work

- **Sealed exam** ([src/onsen/examiner](src/onsen/examiner)):
  - Claude (structured outputs; model set by `ONSEN_EXAMINER_MODEL`) writes scenarios in a small executable language: HTTP checks plus
    browser steps that use accessible labels, roles and test ids from the spec's acceptance contract.
  - Values are captured from live responses, so the exam works with whatever data Scout found.
  - The file is hashed at seal time and re-checked before every grading. Only Nap Guard or a human can trigger the reveal.
  - Satisfaction is the share of scenarios passed, and a stage passes at 90% by default.
- **Scout** ([src/onsen/scout.py](src/onsen/scout.py)) uses three parts of Nimble:
  - **Web Search Agents** in `research` mode, for answers with a per-claim trust report
  - **Search** in `focus=coding` mode plus **Extract** to markdown, for current docs saved to `docs/vendor/`
  - **Web Search Agents** in `dataset_building` mode with a JSON schema, for data where every row must carry a
    `source_url` or it's dropped
- **Nap Guard** ([src/onsen/napguard.py](src/onsen/napguard.py)):
  - A stage is accepted when its latest exam PASSes and the Reviewer APPROVES.
  - Thrash means `ONSEN_THRASH_LIMIT` failing rounds with no improvement. On thrash, or when a stage runs out of rounds,
    it removes the looping agent from the room and calls a chill break.
  - It counts human touches and wake-ups for the receipt.

## Repo map

```
specs/          capyfinder.md (3-stage demo spec) + the dataset schema Scout uses
crew/           Desktop agent instructions + PROTOCOL.md
src/onsen/      scout.py · napguard.py · examiner/ · register.py · smoke.py
docker/         the Examiner's isolated container
scripts/        new-run.sh (fresh workspace) · voiceover.py (ElevenLabs narration)
demo/           script.md for the 3-minute video
docs/           submission.md (the write-up BAND asks for)
tests/          reference app + fixture exam + unit tests
```

## Safety notes

- Agent keys live in `~/.onsen/agent_config.yaml` (chmod 600), outside every workspace. `.env` is gitignored.
- Builders work in a separate workspace. They are told not to read outside it, and the exam isn't there anyway.
- No vendor reviews its own code. Nap Guard is the only agent that mentions the human.
