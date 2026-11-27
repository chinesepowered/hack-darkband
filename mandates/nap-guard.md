# Nap Guard

Harness: band-sdk (Python agent)
Model: none (deterministic rules, no model calls)

You guard the human's sleep and the stage gate. You are code, not a model: every decision below is a rule, and no
seat's summary of a result is taken on trust.

- **The gate.** A stage is accepted when the Examiner's latest exam passes and the Reviewer's latest review approves
  the same commit, and then the event's acceptance checker, which you run on that commit yourself, claims the stage.
  An exam passes when at least 90% of its checks pass, counted from its `passed=a/b`, whatever word the message
  uses. Then you post `[gate] stage=N ACCEPTED` to the Architect and the Examiner. If the checker doesn't claim the
  stage, you post `[gate] stage=N WAITING` to the Builder and the Architect with what the checker found. A block
  after acceptance reopens the stage.
- **The sleep.** The task is the only human input. A question meant for the human gets `[decide]`: decide from the
  requirements and state the assumption. You never mention the human.
- **The stall.** When a stage fails three rounds in a row without improving, or runs past its round budget, you post
  `[chill]` to the Architect and the Builder; so do three blocked reviews of three different commits in a row. A
  verdict repeated on the same commit counts once. The first chill break of a stage asks the Architect to re-plan.
  After the second, one grader is enough: the exam's pass or the Reviewer's approval, plus the checker's claim on
  that commit, accepts the stage, and the other grader's open findings carry forward. After the third, the checker's
  claim on the latest graded commit alone accepts it. Nobody is removed and nobody waits.
- **The quiet room.** A seat only acts when a message mentions it. When no seat has done anything for six minutes
  while the run is open, you post `[nudge]` to the Architect and the Builder, at most thirty times per run.
- **The late handoff.** A seat in the middle of a turn hears nothing. When the acceptance checker has claimed the
  open stage on a commit and no `[ready]` for it (or a later commit) follows within five minutes, you interrupt the
  Builder's turn and post `[nudge] handoff=late` to it, once per commit.
- **The receipt.** When the Architect posts `[report]`, you answer with `[receipt]`: human inputs, wake-ups, each
  stage's exam curve, rounds and checker claim, chill breaks, and the time taken.
