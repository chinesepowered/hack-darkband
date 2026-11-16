# Onsen: submission write-up

**Onsen is a dark software factory on BAND with one rule: don't wake the capybara.** You are the capybara. Six agents in one
BAND room turn a written spec into working software, and you say exactly two things: `build SPEC.md` and `ship`.

- Repo: this repository (start with the README)
- Demo video: `demo/onsen-demo.mp4` (built from run 7, with the crew in BAND Desktop)
- Real runs: `runs/` (cleaned room transcripts and receipts)

BAND's hacker guide asks for four short answers.

## 1. The crew

| Agent | Runs as | Its one job |
|---|---|---|
| **Architect** | BAND Desktop · OpenCode · Qwen 3.8 27B (W&B Inference) | plans, hands out one stage at a time, recruits specialists if a peer exists |
| **Builder** | BAND Desktop · OpenCode · Qwen 3.8 27B | builds each stage; answers the exam's and the Reviewer's findings |
| **Reviewer** | BAND Desktop · OpenCode · Qwen 3.8 27B, read-only profile | reads every diff against the spec; blocks with the missing evidence |
| **Scout** | band-sdk agent · Nimble | answers from the live web with sources and confidence; fetches docs; builds datasets |
| **Examiner** | band-sdk agent · Qwen 3.8 writes the exam, Playwright runs it | seals a hidden acceptance exam and grades every stage |
| **Nap Guard** | band-sdk agent · deterministic | gates stages, batches questions, calls chill breaks, wakes the human once, posts the receipt |

Each agent is its own BAND identity. BAND Desktop runs the three coding agents: its daemon owns each one's OpenCode
runtime, one per agent per room. Scout, the Examiner and Nap Guard are band-sdk agents. Runs 1–4 ran the crew through
band-sdk's `OpencodeAdapter` instead; that mode still works without the desktop app (`ONSEN_CREW=sdk`).

## 2. Who talks to whom

- The human mentions only the Architect, once, and replies only to Nap Guard (`ship`).
- The Architect asks Scout for data, then asks the Examiner to seal the exam with that data, then hands stages to the Builder.
- The Builder posts `[ready]` to the Examiner **and** the Reviewer together. It asks Scout for docs and facts. When
  it disputes a failure, it posts `[dispute]` to the Examiner and Nap Guard instead of bending the data.
- The Examiner and the Reviewer reply to the Builder and copy Nap Guard. Scout copies Nap Guard only on low-confidence
  answers.
- Nap Guard mentions the Architect (stage accepted or reopened) and the human (wake-ups only).

Left out on purpose:
- **The builders never see the exam.** BAND delivers messages only to the agents they mention, and the scenarios live on the
  Examiner's disk.
- **Nobody but Nap Guard mentions the human.**

## 3. One flow, end to end

From run 7, the recorded run, with the crew in BAND Desktop (full receipt and timeline in `runs/run7/RUN.md`):

1. You post `@Architect build SPEC.md` (human touch #1).
2. The Architect writes PLAN.md and asks Scout for data. Nimble's dataset agent came back empty twice. The Architect
   asked again and built on the 5 sourced spots it got, noting in the room that this is below the spec's 20–40 (the
   contract sets no minimum, so the exam grades what the data can produce).
3. The Architect asks the Examiner to seal the exam. Qwen writes 17 scenarios, each limited to the routes that its own
   and earlier stages introduce. The Examiner proofreads them against the spec and the data profile, and posts only
   the SHA-256.
4. For each stage, the Builder posts `[ready]` to the Examiner and the Reviewer, the exam reports what a user would
   notice, and the Reviewer approves or blocks a specific commit. When the exam PASSes and the review APPROVES the same
   commit, Nap Guard posts `[gate] ACCEPTED`. All three stages passed on round 1 (5/5, 6/6, 6/6). The Reviewer ran
   89, about 110 and about 75 live checks of its own before approving.
5. Nap Guard wakes you once: "ship or hold?". You say `ship` (human touch #2).
6. The receipt follows, then the Examiner reveals the exam, and its hash matches the seal.

```
[receipt] 🛁 Onsen run complete
• Human touches: 2 (the spec + 1 reply to Nap Guard) · wake-ups: 1 · chill breaks: 0
• Stages: 1 ✔ 100% (1 rounds) · 2 ✔ 100% (1 rounds) · 3 ✔ 100% (1 rounds)
• Docs fetched: 0 · datasets built: 2 · exam rounds: 3 · exam checks voided on appeal: 0
• Time from seal to ship: 23m 19s
The capybara was woken 1 time. 🍊
```

### What runs 5–7 showed (moving the crew into BAND Desktop)

BAND Desktop posts the text an agent ends its turn with as a reply to whoever woke it. Qwen 3.8 can't end a turn
silently: it writes "." or "No reply needed.". In run 5 that became an acknowledgment ping-pong. When told to stay
silent, the Architect looped on no-op tool calls instead. Run 5 also exposed two factory bugs:
- an agent's remark, "Seal receipt confirmed …", re-sealed the exam;
- stage 1 was examined on the home page that stage 2 builds.

The fixes went into the factory:
- the role launchers run a small ACP filter that keeps closing remarks out of the room unless they are protocol
  messages;
- bare command words need `key=value` arguments;
- re-runs and duplicate `[ready]`s are rate-limited;
- Scout only searches on explicit `ask:` / `docs:` / `data:`, and retries an empty dataset;
- a stage's exam may only use routes that its own and earlier stages introduce.

Run 7 then went from kickoff to `ship` with one wake-up.

### What run 4 showed

**The hidden exam caught what the Reviewer missed.** The Reviewer approved stage 2 after checking the server-rendered
HTML. The exam drives a real browser, and there a JavaScript syntax error left live search and the filters dead. All
the Builder saw was the user-visible symptom, and that was enough to find the bug. From then on, the Reviewer verified
every stage in headless Chrome itself.

**The rest of stage 2's failures were the factory's own bugs.**
- A check asked for role `textbox`, where the spec says `input type=search` (role `searchbox`).
- Nap Guard's parser read `stage=N` from the dispute hint at the bottom of the Examiner's messages and crashed on every
  failing exam.
- An LLM judge failed a page it had passed the round before.
- The Examiner filed the Builder's "please re-run" as a note.

After four rounds without progress, Nap Guard called a chill break and woke the human. That is the
thrash guard doing its job. Each bug was then fixed in the factory, with tests (commit `f0f616a`), and the Examiner and
Nap Guard were restarted mid-run. The sealed exam file never changed. The human said `resume`, relayed the Builder's
re-run request once, and stage 2 passed 7/7 on the commit the Reviewer had approved. The receipt counts all of it.

### What run 1 (the rehearsal) showed

**The Reviewer catches reward hacking.** An early version of our Examiner had a check that was too strict: it compared a
city name case-sensitively. To pass it, the Builder lowercased "Worcestershire" in the dataset. The Reviewer blocked it:

> `[review] stage=1 BLOCKED: data/spots.json:352 — city was mutated from Scout's Worcestershire to worcestershire … That is
> special-casing data to a test-looking input, and it is not a contract fix`

The Builder reverted it, and the Reviewer re-approved only after checking "zero value-level changes" against Scout's original
data. We then fixed the factory itself:
- approvals are now tied to the exact commit that passed the exam
- a later block reopens an accepted stage
- builders have a `[dispute]` channel instead of an incentive to bend data
- the Examiner proofreads its own exam against the spec before sealing

See `runs/run1-rehearsal/room.json`.

## 4. What breaks without the room

Without the room, nothing keeps the exam away from the builders, the Reviewer's block has nothing to stop, and Scout's
evidence never reaches the agent that asked. You're back to one agent grading its own homework and asking the human
everything.

---

## Nimble: how it's used (for the Nimble prize)

Nimble is how the factory runs without waking the human. It replaces the human as the source of facts.

| Need | Nimble product | What Onsen does with the result |
|---|---|---|
| "Build me the dataset" | Web Search Agents, `use_case=dataset_building` + JSON schema | `data/spots.json`. Rows without a `source_url` are dropped, every field from the schema is present, and the trust report goes to `.sources.json`. |
| "Is this true? What's the convention?" | Web Search Agents, `use_case=research` | Uses the per-claim confidence and primary-source flags to decide between answering the builder and batching the question for the human |
| "What's the current API for X?" | Search `focus=coding` + Extract → markdown | Current docs land in the workspace's `docs/vendor/`, so builders code against today's API |

Measured:
- dataset (run 4): 36 sourced capybara spots across Brazil, Japan, the UK and the US in 55 seconds, with nothing
  dropped for a missing source
- research (smoke-test room): a cited, high-confidence answer in about 45 seconds, live in a BAND room

## BAND Desktop

BAND Desktop (0.4.18, the Linux package) runs the coding crew:
- **The Architect, the Builder and the Reviewer were adopted into BAND Desktop** (`band adopt`) with their existing
  BAND identities. Each got an OpenCode runtime in its Runtime tab: Qwen 3.8 on W&B, approvals allowed automatically,
  and a per-role launcher that picks the role's OpenCode permission profile, so the Reviewer can't edit files.
- **BAND Desktop's daemon starts each agent's runtime** in the run's workspace when a message mentions it. It shows
  their reasoning, tool calls and live status in the room, each with an Interrupt button. `onsen-desktop prepare`
  points the crew at each new workspace and writes their instructions, including a roster of handles.
- **The daemon runs with a minimal environment**, because it passes its environment to every runtime. Tokens in the
  operator's shell stay out of the agents' reach.

Full setup: [docs/band-desktop.md](band-desktop.md). Runs 5–7 ran this way.

## Checklist

- [x] Demo video (`demo/onsen-demo.mp4`, built from run 7 with the crew in BAND Desktop)
- [x] Run 7 transcript, receipt and revealed exam in `runs/run7/` (and every earlier run in `runs/`)
- [x] README quickstart: a fresh clone runs `uv sync` and passes all 29 tests; the factory itself ran live in runs 1–4
