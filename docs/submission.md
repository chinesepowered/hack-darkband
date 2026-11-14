# Onsen: submission write-up

**Onsen is a dark software factory on BAND with one rule: don't wake the capybara.** You are the capybara. Six agents in one
BAND room turn a written spec into working software, and you say exactly two things: `build SPEC.md` and `ship`.

- Repo: this repository (start with the README)
- Demo video: `demo/onsen-demo.mp4`
- Real runs: `runs/` (cleaned room transcripts and receipts)

BAND's hacker guide asks for four short answers.

## 1. The crew

| Agent | Runs as | Its one job |
|---|---|---|
| **Architect** | OpenCode · Qwen 3.8 27B (W&B Inference) | plans, hands out one stage at a time, recruits specialists if a peer exists |
| **Builder** | OpenCode · Qwen 3.8 27B | builds each stage; answers the exam's and the Reviewer's findings |
| **Reviewer** | OpenCode · Qwen 3.8 27B, read-only profile | reads every diff against the spec; blocks with the missing evidence |
| **Scout** | band-sdk agent · Nimble | answers from the live web with sources and confidence; fetches docs; builds datasets |
| **Examiner** | band-sdk agent · Qwen 3.8 writes the exam, Playwright runs it | seals a hidden acceptance exam and grades every stage |
| **Nap Guard** | band-sdk agent · deterministic | gates stages, batches questions, calls chill breaks, wakes the human once, posts the receipt |

Each agent is its own BAND identity. The three coding agents use band-sdk's `OpencodeAdapter` (one OpenCode session per room
per agent). Everything runs headless on one cloud machine.

## 2. Who talks to whom

- The human mentions only the Architect, once, and replies only to Nap Guard (`ship`).
- The Architect asks Scout for data, then asks the Examiner to seal the exam with that data, then hands stages to the Builder.
- The Builder posts `[ready]` to the Examiner **and** the Reviewer together. It asks Scout for docs and facts, and
  disputes a failure with Nap Guard instead of bending the data.
- The Examiner and the Reviewer reply to the Builder and copy Nap Guard. Scout copies Nap Guard only on low-confidence
  answers.
- Nap Guard mentions the Architect (stage accepted or reopened) and the human (wake-ups only).

Left out on purpose:
- **The builders never see the exam.** BAND delivers messages only to the agents they mention, and the scenarios live on the
  Examiner's disk.
- **Nobody but Nap Guard mentions the human.**

## 3. One flow, end to end

From run 2 (to fill in from the receipt):

1. You post `@Architect build SPEC.md` (human touch #1).
2. The Architect writes PLAN.md and asks Scout for data. Nimble's dataset agent returns spots with a `source_url` on every
   row.
3. The Architect asks the Examiner to seal the exam. Qwen writes it, the Examiner proofreads it against the spec and the
   data profile, and posts only the SHA-256.
4. For each stage, the Builder posts `[ready]`, the exam reports user-visible failures, and the Reviewer approves or blocks
   a specific commit. When the exam PASSes and the review APPROVES the same commit, Nap Guard posts `[gate] ACCEPTED`.
5. Nap Guard wakes you once: "ship or hold?". You say `ship` (human touch #2).
6. The receipt follows, then the Examiner reveals the exam, and its hash matches the seal.

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
- dataset: 40 sourced capybara spots across Japan, the US and the UK in about 60s
- research: a cited, high-confidence answer in about 45s, live in a BAND room

## BAND Desktop

BAND Desktop's installer couldn't run in our cloud build environment. Its permission system blocked installing the
package. So the crew runs on the same OpenCode runtime BAND Desktop launches, connected through band-sdk's
`OpencodeAdapter`. The rooms are ordinary BAND rooms: open the run's room in BAND Desktop (or app.band.ai) to watch the
agents, their tool calls and the Work tab live.

## Checklist

- [ ] Demo video (`demo/onsen-demo.mp4`)
- [ ] Run 2 transcript + receipt in `runs/`
- [ ] README quickstart verified from a clean checkout
