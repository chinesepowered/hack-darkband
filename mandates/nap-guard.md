# Nap Guard

Harness: band-sdk (Python agent)
Model: none (deterministic rules, no model calls)

You guard the human's sleep and the stage gate. You are code, not a model: every decision below is a rule.

- **The gate.** A stage is accepted only when the Examiner's latest verdict is PASS, the Reviewer's latest review is
  APPROVED, both name the same commit, and the review reports that the acceptance checker claims the stage. Then you
  post `[gate] stage=N ACCEPTED` to the Architect and the Examiner. A block after acceptance reopens the stage.
- **The sleep.** The task is the only human input. A question meant for the human gets `[decide]`: decide from the
  requirements and state the assumption. You never mention the human.
- **The stall.** When a stage fails three rounds in a row without improving, or runs past its round budget, you post
  `[chill]` to the Architect and the Builder so the Architect re-plans. Nobody is removed and nobody waits.
- **The receipt.** When the Architect posts `[report]`, you answer with `[receipt]`: human inputs, wake-ups, each
  stage's exam curve and rounds, chill breaks, and the time taken.
