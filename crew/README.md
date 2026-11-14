# The crew

| Agent | Where it runs | Vendor | Its one job | BAND signal it demonstrates |
|---|---|---|---|---|
| **Architect** | BAND Desktop | Claude Code | plan, roster, hand out stages | roster decided at runtime (recruits the Accessibility Auditor only for UI specs) |
| **Builder** | BAND Desktop | Codex | build each stage, fix what the exam and the review report | dependent handoff (it answers the finding, not the task) |
| **Reviewer** | BAND Desktop | Claude Code (≠ the Builder's vendor) | read the diff and say no when needed | a verdict that can be blocked |
| **Scout** | `uv run onsen-scout` | Nimble | answer from the live web with sources; fetch docs; build datasets | dependent handoff; it stands in for the human on factual questions |
| **Examiner** | Docker (`docker/compose.yaml`) | Claude (writes the exam) + Playwright | seal the hidden exam and grade every stage | a boundary BAND enforces (mention-scoped visibility) + a blockable verdict |
| **Nap Guard** | `uv run onsen-nap-guard` | none (deterministic) | gate stages, batch questions, chill breaks, the one wake-up, the receipt | one human gate; a hard stop Desktop doesn't have |

Desktop agents: create each one in BAND Desktop. Use the name above, the provider above, and the run workspace, then
paste the **Instructions** block from its file in this folder. SDK agents: `uv run onsen-register` once, then start them as
described in the top-level README.

Agent files: [architect.md](architect.md) · [builder.md](builder.md) · [reviewer.md](reviewer.md) ·
[accessibility-auditor.md](accessibility-auditor.md) · [PROTOCOL.md](PROTOCOL.md)
