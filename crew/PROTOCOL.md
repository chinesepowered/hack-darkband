# Onsen room protocol (dark run)

The dispatched task is the only human input. From then until the Architect's final report, no seat asks the human
anything and no message mentions them. Every message starts with a tag, then `key=value` pairs, then free text, so
each handoff is machine-readable. BAND delivers a message only to the seats it mentions: who you mention is the
routing.

| Tag | From → to | Meaning |
|---|---|---|
| `[plan] stage=N` | Architect → Builder, Examiner, Reviewer | work items in order, and the requirements most likely to be missed |
| `[task] stage=N part=i/k` | Architect → Builder, Examiner, Reviewer | the complete requirements, in numbered parts, then the task |
| `[seal] stage=N sha256=… checks=K` | Examiner → Architect, Nap Guard | the band's own exam for the stage is written and committed to by hash |
| `[ready] stage=N commit=<sha>` | Builder → Examiner **and** Reviewer | a committed revision to grade |
| `[exam] stage=N verdict=PASS\|FAIL passed=a/b satisfaction=P% commit=<sha>` | Examiner → Builder, Nap Guard | exam result; failures as observed behaviour plus the requirement |
| `[review] stage=N commit=<sha> claimed=<N\|none> APPROVED\|BLOCKED: …` | Reviewer → Builder, Nap Guard | acceptance-checker result plus code review |
| `[gate] stage=N ACCEPTED commit=<sha>` | Nap Guard → Architect, Examiner | PASS and APPROVED on the same commit, which the checker claims |
| `[dispute] stage=N` | Builder → Examiner, Nap Guard | evidence that an exam check contradicts the requirements |
| `[reveal] stage=N sha256=…` | Examiner → Architect, Nap Guard | the stage's exam is published in the repository; the hash matches the seal |
| `[chill] stage=N` | Nap Guard → Architect, Builder | the stage stopped improving: re-plan |
| `[decide]` | Nap Guard → the asker | nobody asks the human: decide from the requirements |
| `[report]` | Architect → Nap Guard, every seat | the end of the run: stages, accepted commits, blockers, evidence |
| `[receipt]` | Nap Guard → Architect | the run's numbers |

## Rules for every seat

1. **Whole handoffs.** A handoff carries everything the receiver needs: the complete requirements and the task.
   Never point at an earlier message or "see above". A handoff in numbered parts (`part=i/k`) is complete only when
   part k/k arrives: until then, keep each part and end your turn without replying or asking for the rest.
2. **Nobody asks the human.** There is no human to answer during the run. Never use a tool that asks the human a
   question; decide from the requirements and state your assumption in your next message.
3. **One stage at a time.** Work only on the current stage. A stage's folder never changes once the next stage's
   requirements are open.
4. **Verdicts name commits.** Every `[ready]`, `[exam]`, `[review]` and `[gate]` names the exact commit. An approval
   is for that commit only.
5. **Checks are not targets.** No seat edits, skips or weakens a check, or special-cases inputs that look like one.
   Behaviour follows the requirements.
6. **Commit your own work, often.** Messages say what changed and which requirement it serves. Commit only your own
   files (`git commit -- <paths>`). If git reports a lock, wait a moment and retry.
7. **Stay in the band.** Questions go to the seat that owns the answer, and the requirements decide. Make the most
   reasonable reading, state it in your next message, and keep going.
