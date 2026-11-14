# The crew

| Agent | Runs as | Its one job | BAND signal it demonstrates |
|---|---|---|---|
| **Architect** | `onsen-crew architect` · OpenCode · Qwen 3.8 | plan, sequence data → sealed exam → stages, recruit specialists | roster decided at runtime (recruits an Accessibility Auditor only when one exists and the spec has a UI) |
| **Builder** | `onsen-crew builder` · OpenCode · Qwen 3.8 | build each stage; fix what the exam and the review report; dispute bad checks | dependent handoff (it answers the finding, not the task) |
| **Reviewer** | `onsen-crew reviewer` · OpenCode · Qwen 3.8 · read-only profile | read every diff against the spec and say no when needed | a verdict that can be blocked |
| **Scout** | `onsen-scout` · Nimble | answer from the live web with sources; fetch docs; build datasets | dependent handoff; it stands in for the human on factual questions |
| **Examiner** | `onsen-examiner` · Qwen 3.8 writes, Playwright runs | seal the hidden exam (data-aware, proofread) and grade every stage | a boundary BAND enforces (mention-scoped visibility) + a blockable verdict |
| **Nap Guard** | `onsen-nap-guard` · deterministic | gate stages per commit, batch questions, chill breaks, the one wake-up, the receipt | one human gate; a hard stop the platform doesn't have |

The coding agents read the **Instructions** section of their file in this folder, with [PROTOCOL.md](PROTOCOL.md)
appended. Their permissions come from [opencode/opencode.json](../opencode/opencode.json):
- nobody fetches the web; web questions go to Scout
- nobody leaves the workspace
- the Reviewer can't edit

`scripts/run-factory.sh` starts all six. To use BAND Desktop instead, create agents with the same names and paste the
same instructions.

Agent files: [architect.md](architect.md) · [builder.md](builder.md) · [reviewer.md](reviewer.md) ·
[accessibility-auditor.md](accessibility-auditor.md) · [PROTOCOL.md](PROTOCOL.md)
