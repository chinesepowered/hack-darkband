# Submission write-up (draft)

BAND's hacker guide asks for four short answers. Update the numbers after the recorded run.

## 1. The crew

- **Architect** (BAND Desktop, Claude Code): plans and hands out stages; brings in specialists only when the spec calls for them.
- **Builder** (BAND Desktop, Codex): builds each stage and fixes whatever the Examiner and Reviewer report.
- **Reviewer** (BAND Desktop, Claude Code): reads every diff and blocks with the missing evidence. Never the Builder's vendor.
- **Scout** (band-sdk, Nimble): answers questions from the live web with per-claim sources and confidence; fetches current docs; builds datasets.
- **Examiner** (band-sdk in Docker, Claude + Playwright): seals a hidden acceptance exam and grades every stage against it.
- **Nap Guard** (band-sdk, deterministic): the only agent that can wake the human. Gates stages, batches open questions, calls chill breaks, posts the receipt.

## 2. Who talks to whom

- The human mentions only the Architect, once.
- The Architect mentions the Examiner (seal), Scout (data) and the Builder (tasks).
- The Builder mentions the Examiner and Reviewer together on `[ready]`, and Scout for questions.
- The Examiner and Reviewer reply to the Builder and copy Nap Guard.
- Scout copies Nap Guard only on low-confidence answers.
- Nap Guard mentions the Architect (stage accepted) and the human (wake-ups only).

Who we left out on purpose:
- **The Builder never sees the exam.** Mention-scoped routing keeps it out of its context, and the container keeps it off
  its disk.
- **Nobody but Nap Guard mentions the human.**

## 3. One flow, end to end

1. The human posts `@Architect build SPEC.md`.
2. The Architect writes the plan, asks the Examiner to seal the exam (SHA-256 posted), and asks Scout for data. Nimble
   returns 40 spots, each with a source.
3. The Architect sends stage 1 to the Builder, which asks Scout for docs and builds it.
4. `[ready]` goes to the Examiner and Reviewer. The exam FAILs at 62%; the Builder sees "a lowercase country code
   returned nothing" and fixes the behavior.
5. The Reviewer BLOCKs a hard-coded value; the Builder fixes it.
6. The exam PASSes at 100% and the review is APPROVED. Nap Guard posts `[gate] ACCEPTED` and the Architect starts stage 2.
7. Repeat for stages 2 and 3.
8. Nap Guard wakes the human for the first time: "ship or hold?". The human says `ship`.
9. The receipt reads 2 human touches and 1 wake-up. The Examiner reveals the exam, and its hash matches the seal.

## 4. What breaks without the room

Without the room, nothing keeps the exam away from the builders, the blocks have nothing to stop, and Scout's evidence
never reaches the agent that asked. You're back to one agent grading its own homework and asking the human everything.

---

## Nimble: how it's used (for the Nimble prize)

Nimble is how the factory runs without waking the human. It replaces the human as the source of facts.

| Need | Nimble product | What Onsen does with the result |
|---|---|---|
| "Is this true? What's the convention?" | Web Search Agents, `use_case=research` | Uses the per-claim trust report (sources and confidence) to decide between answering the builder and batching the question for the human |
| "What's the current API for X?" | Search `focus=coding` + Extract → markdown | Writes current docs into the workspace's `docs/vendor/`, so builders code against today's API |
| "Build me the dataset" | Web Search Agents, `use_case=dataset_building` + JSON schema | Saves `data/spots.json`, dropping any row without a `source_url`; trust report goes to `.sources.json` |

Measured in development:
- research answer in ~45s, with 3 graded claims
- 40-row dataset in 58s, across 3 countries

## Checklist

- [ ] Recorded room walkthrough (BAND's free plan keeps data 2 weeks; record before then)
- [ ] 3-minute video (demo/script.md + voiceover)
- [ ] Repo link, README quickstart verified on a clean machine
- [ ] Final numbers in this file and in the receipt screenshot
