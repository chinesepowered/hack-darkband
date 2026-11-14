<p align="center"><img src="assets/capybara.svg" width="180" alt="A sleepy capybara soaking in a hot spring with a yuzu on its head"></p>

# Onsen 🛁

**A dark software factory on BAND that has one rule: don't wake the capybara.**

▶ **Demo video:** [demo/onsen-demo.mp4](demo/onsen-demo.mp4) (3 minutes, built from the real run in [runs/run4](runs/run4/))

The human is a capybara napping in a hot spring. Six agents in one BAND room turn a written spec into working
software. Two ideas make it a *dark* factory you can trust:

1. **A sealed exam.** The Examiner writes hidden acceptance scenarios from the spec and posts only their SHA-256.
   Builders never see the scenarios: BAND delivers a message only to the agents it mentions, and the exam lives on
   the Examiner's own disk. When a stage fails, builders see what a *user* would notice, never the test. Nobody grades
   their own homework.
2. **Ask the web, not the human.** Every factual question goes to Scout, which answers from the live web with
   [Nimble](https://www.nimbleway.com/), citing a source and a confidence grade for each claim. Only a low-confidence answer
   reaches the human, and even that waits for the one wake-up.

Nap Guard is the only agent allowed to wake the human. It wakes them once, to ask "ship or hold?" (plus a chill break
if work starts thrashing). The run ends with a receipt that counts how many times the capybara was woken.

## The crew

| Agent | Runs as | Job | BAND collaboration signal |
|---|---|---|---|
| Architect | OpenCode · Qwen 3.8 27B | plan, hand out stages, recruit specialists at runtime | roster decided at runtime |
| Builder | OpenCode · Qwen 3.8 27B | build each stage; fix what the exam and the review report | dependent handoff |
| Reviewer | OpenCode · Qwen 3.8 27B · read-only profile | read the diff and say no when needed | verdict that can be blocked |
| Scout | `onsen-scout` · Nimble | cited answers, current docs, datasets with a source on every row | dependent handoff |
| Examiner | `onsen-examiner` · Qwen 3.8 writes the exam, Playwright runs it | seal the hidden exam, grade each stage | boundary BAND enforces |
| Nap Guard | `onsen-nap-guard` (deterministic) | stage gate, batched questions, chill breaks, the one wake-up, the receipt | one human gate + hard stop |

Every agent is its own BAND identity. The three coding agents use BAND's `OpencodeAdapter`: each room gets its own
OpenCode session per agent, and the model is Qwen 3.8 27B on W&B Inference. The Reviewer's OpenCode profile can't
edit files, and no profile can fetch the web, so web questions have to go through Scout. Agent instructions are in
[crew/](crew/), and the message protocol is in [crew/PROTOCOL.md](crew/PROTOCOL.md).

## One run

```
human ──"@Architect build SPEC.md"──▶ Architect ──seal──▶ Examiner ──[seal] sha256──▶ (room)
Architect ──data:──▶ Scout ──Nimble dataset agent──▶ data/spots.json (a source on every row)
Architect ──[task] stage=1──▶ Builder ──docs:/ask:──▶ Scout          (low confidence ─▶ Nap Guard batches it)
Builder ──[ready] stage=1──▶ Examiner + Reviewer
Examiner ──[exam] FAIL "what a user noticed"──▶ Builder   ·   Reviewer ──[review] BLOCKED: …──▶ Builder
… fix …  ──▶  [exam] PASS  +  [review] APPROVED  ──▶ Nap Guard ──[gate] ACCEPTED──▶ Architect ──▶ stage 2 …
Nap Guard ──[wake] #1 "ship or hold?"──▶ human ──ship──▶ [receipt] ──▶ Examiner [reveal] (hash matches the seal)
```

## Real runs

Every run happened in a real BAND room. Cleaned transcripts, receipts and the code each run built are in [runs/](runs/):

| Run | What it shows |
|---|---|
| [run4](runs/run4/) | the recorded run: the exam caught a browser-only bug the Reviewer had approved; four factory bugs surfaced, caused a chill break, and were fixed live; `ship`, an honest receipt (4 touches, 2 wake-ups), exam revealed with a matching hash |
| [run3-dispute](runs/run3-dispute/) | the hidden exam caught a real race; the per-commit gate held; the Builder disputed a bad check with evidence, which led to appeals |
| [run2-partial](runs/run2-partial/) | stages 1–2 passed on the first try with commit-bound approvals; stage 3's exam slips led to automatic repairs |
| [run1-rehearsal](runs/run1-rehearsal/) | the Reviewer caught the Builder editing data to pass a bad check, which led to per-commit gates, reopening, and disputes |

Each failure taught the factory something, and the fix went into the factory itself rather than into one run's code.

## Run it

You need:
- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node 20+ for OpenCode (`npm i -g opencode-ai`)
- a Chromium for the Examiner's Playwright: `uv run playwright install chromium` (or point `ONSEN_CHROMIUM_PATH` at one)
- three keys in `.env`: `BAND_USER_KEY`, `NIMBLE_API_KEY` and `WANDB_API_KEY`

Everything runs headless; no desktop is required.

```bash
cp .env.example .env
```

```bash
uv sync
```

```bash
uv run onsen-register
```

```bash
scripts/run-factory.sh capyfinder
```

- `onsen-register` registers the six agents and saves their keys to `~/.onsen/`, outside the repo.
- `run-factory.sh` creates a fresh workspace, starts OpenCode and the six agents, posts your one kickoff message, and
  follows the room until the receipt. When Nap Guard wakes you, reply in the room with `@Nap Guard ship`, or use
  `uv run onsen-say ship`.

To watch the room live, open it at app.band.ai or in BAND Desktop; the room is the same either way. Stop everything
with:

```bash
scripts/stop-factory.sh
```

Other commands:
- `uv run onsen-smoke --agent scout --say "ask: …"` checks a single agent live.
- `uv run pytest` runs the tests. The Examiner is graded against a reference app with injected bugs.
- `docker compose -f docker/compose.yaml up --build examiner` runs the Examiner in its own container for stronger
  isolation.

## How the pieces work

- **Sealed exam** ([src/onsen/examiner](src/onsen/examiner)):
  - Qwen writes scenarios in a small executable language: HTTP checks plus browser steps that use the labels, roles
    and test ids from the spec's acceptance contract.
  - The output is constrained to a JSON schema. A repair pass then fixes common slips, and a contract linter drops any
    scenario that uses a route, field, label or piece of text the spec doesn't define. Exams written by a model
    otherwise fail correct apps for invented reasons.
  - Values are captured from live responses, so the exam works with whatever data Scout found.
  - The file is hashed at seal time and re-checked before every grading. Only Nap Guard or a human can trigger the reveal.
  - **Appeals:** a builder that believes a check contradicts the spec posts `[dispute]` with evidence instead of
    bending the code. The Examiner re-examines just those checks against the spec and the data. Wrong checks are
    voided, listed at reveal, and the stage is re-graded; the sealed file never changes. A scenario that breaks in its
    own setup (an exam bug) never counts against the builder.
  - **Fair grading** (from run 4): role checks follow WAI-ARIA subclass roles, so a `searchbox` counts as a `textbox`.
    An LLM judge sees each form control's current value, and its "no" fails the builder only if two of three reads
    agree. A builder that asks for a re-run gets one.
- **Scout** ([src/onsen/scout.py](src/onsen/scout.py)) uses three parts of Nimble:
  - **Web Search Agents** in `research` mode, for answers with a per-claim trust report
  - **Search** in `focus=coding` mode plus **Extract** to markdown, for current docs saved to `docs/vendor/`
  - **Web Search Agents** in `dataset_building` mode with a JSON schema, for data where every row must carry a
    `source_url` or it's dropped
- **Nap Guard** ([src/onsen/napguard.py](src/onsen/napguard.py)):
  - A stage is accepted when its latest exam PASSes and the Reviewer APPROVES.
  - Thrash means N failing rounds with no improvement. On thrash, or when a stage runs out of rounds, it removes the
    looping agent from the room and calls a chill break.
  - It counts human touches and wake-ups for the receipt.

## Repo map

```
specs/          capyfinder.md (3-stage demo spec) + the dataset schema Scout uses
crew/           the coding crew's instructions + PROTOCOL.md
opencode/       opencode.json: Qwen 3.8 on W&B + one permission profile per role
src/onsen/      scout.py · napguard.py · examiner/ · crew.py · llm.py · register/kickoff/watch/smoke
scripts/        run-factory.sh · stop-factory.sh · new-run.sh · voiceover.py
runs/           transcripts and receipts from real runs
demo/           the 3-minute demo video (onsen-demo.mp4), its narration script and scene list
docs/           submission.md (the write-up BAND asks for)
tests/          reference app + fixture exam + unit tests
```

## Safety notes

- Agent keys live in `~/.onsen/agent_config.yaml` (chmod 600), outside every workspace. `.env` is gitignored.
- The builders work in a separate workspace, and OpenCode's `external_directory: deny` keeps their file tools inside it.
- Nap Guard is the only agent that mentions the human.
