# Onsen room protocol (dark run)

The dispatched task is the only human input. From then until the Architect's final report, no seat asks the human
anything and no message mentions them. Every message starts with a tag, then `key=value` pairs, then free text, so
each handoff is machine-readable. BAND delivers a message only to the seats it mentions: who you mention is the
routing.

| Tag | From → to | Meaning |
|---|---|---|
| `[plan] stage=N` | Architect → Builder, Examiner, Reviewer | work items in order, and the requirements most likely to be missed |
| `[task] stage=N part=i/k` | Architect → Builder, Examiner, Reviewer | the complete requirements, in numbered parts, then the task |
| `[seal] stage=N sha256=… checks=K` | Examiner → Architect, Nap Guard | the band's own exam for the stage is written and committed to by hash (written by `onsen-exam seal`) |
| `[ready] stage=N commit=<sha>` | Builder → Examiner **and** Reviewer | a committed revision to grade, with the checker's result line |
| `[exam] stage=N verdict=PASS\|FAIL passed=a/b satisfaction=P% commit=<sha>` | Examiner → Builder, Nap Guard | the exam's result, written by `onsen-exam grade`; failures as observed behaviour plus the requirement |
| `[review] stage=N commit=<sha> APPROVED\|BLOCKED: …` | Reviewer → Builder **and** Nap Guard | code review against the requirements |
| `[gate] stage=N ACCEPTED\|WAITING commit=<sha>` | Nap Guard → Architect, Examiner (accepted) or Builder, Architect (waiting) | the exam passed and the review approved the same commit; Nap Guard then ran the acceptance checker on it, and it claims the stage (or doesn't yet) |
| `[dispute] stage=N commit=<sha>` | Builder → the seat whose verdict it disputes, and Nap Guard | evidence that a check or a review finding contradicts the requirements |
| `[reveal] stage=N sha256=…` | Examiner → Architect, Nap Guard | the stage's exam is published in the repository; the hash matches the seal (written by `onsen-exam publish`) |
| `[chill] stage=N break=B` | Nap Guard → Architect, Builder | the stage stopped improving. Break 1: re-plan. Break 2: one grader's pass (exam or review) plus the checker accepts the stage. Break 3: the checker alone does. Open findings carry forward |
| `[nudge]` | Nap Guard → Architect, Builder | the room has been quiet for a while and the run isn't finished |
| `[decide]` | Nap Guard → the asker | nobody asks the human: decide from the requirements |
| `[report]` | Architect → Nap Guard, every seat | the end of the run: stages, accepted commits, blockers, evidence |
| `[receipt]` | Nap Guard → Architect | the run's numbers |

**Verdicts are computed, not asserted.** `onsen-exam` counts the exam's checks and writes the `[exam]` line; Nap
Guard recomputes PASS from `passed=a/b` (at least 90%) and runs the acceptance checker itself before it accepts a
stage. A seat's own summary of a result never opens the gate.

## Rules for every seat

1. **Whole handoffs.** A handoff carries everything the receiver needs: the complete requirements and the task.
   Never point at an earlier message or "see above". A handoff in numbered parts (`part=i/k`) is complete only when
   part k/k arrives: until then, keep each part and end your turn without replying or asking for the rest.
2. **Nobody asks the human.** There is no human to answer during the run. Never use a tool that asks the human a
   question; decide from the requirements and state your assumption in your next message.
3. **One stage at a time.** Work only on the current stage. A stage's folder never changes once the next stage's
   requirements are open.
4. **Verdicts name commits, once.** Every `[ready]`, `[exam]`, `[review]` and `[gate]` names the exact commit. An
   approval is for that commit only. A commit is handed off once and judged once by each grader; `band send` refuses
   a second `[ready]` or `[review]` for the same commit (a review may change its verdict once, after a dispute).
5. **Checks are not targets.** No seat edits, skips or weakens a check, or special-cases inputs that look like one.
   Behaviour follows the requirements.
6. **Commit your own work, often.** Messages say what changed and which requirement it serves. Commit only your own
   files (`git commit -- <paths>`). If git reports a lock, wait a moment and retry.
7. **Quiet by default, and end your turn.** Post only when it moves the work: a handoff, a verdict, a blocker, or
   the answer to a question someone asked you. Don't acknowledge receipt, don't ask for status, and don't reply to a
   message that needs nothing from you. BAND Desktop gives you new messages only between turns, so when you are
   waiting, end your turn: the next message that mentions you wakes you. `band send` refuses a message that has no
   protocol tag, and any message to Nap Guard other than `[seal]`, `[exam]`, `[review]`, `[dispute]` or `[report]`.
8. **Stay in the band.** Questions go to the seat that owns the answer, and the requirements decide. Make the most
   reasonable reading, state it in your next message, and keep going.
