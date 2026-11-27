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
  The second makes the stage's exam advisory: from then on the Reviewer's approval and the checker's claim gate it.
  The third spends the stage's review effort: you run the checker on the latest graded commit and, if it claims the
  stage, accept it with the open review findings carried forward. Nobody is removed and nobody waits.
- **The quiet room.** A seat only acts when a message mentions it. When no seat has done anything for twelve minutes
  while the run is open, you post `[nudge]` to the Architect and the Builder, at most six times per run.
- **The receipt.** When the Architect posts `[report]`, you answer with `[receipt]`: human inputs, wake-ups, each
  stage's exam curve, rounds and checker claim, chill breaks, and the time taken.
