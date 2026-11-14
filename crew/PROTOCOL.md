# Onsen room protocol

Every agent starts its messages with a tag, then `key=value` pairs, then free text. The tags make every handoff
readable by the agent that receives it, with no LLM deciding where messages go. BAND only delivers a message to the
agents it @mentions, so **who you mention is the routing**.

| Tag | From → to (mentions) | Meaning |
|---|---|---|
| *(spec)* | human → Architect | `@Architect build SPEC.md`. Human touch #1. |
| `[plan]` | Architect → Builder, Reviewer | stages and order of work; PLAN.md written |
| `seal spec=<name>` | Architect → Examiner | write the hidden exam |
| `[seal]` | Examiner → Architect, Nap Guard | exam sealed; `sha256=` commitment; `stages=` |
| `data: …` / `docs: …` / `ask: …` | anyone → Scout | the live web, via Nimble |
| `[answer]` / `[docs]` / `[data]` | Scout → asker (+ Nap Guard if `confidence=low`) | cited result |
| `[task] stage=N` | Architect → Builder | build stage N |
| `[ready] stage=N url=… commit=…` | Builder → Examiner **and** Reviewer | stage N is running; grade it |
| `[exam] stage=N verdict=PASS/FAIL satisfaction=… commit=…` | Examiner → Builder, Nap Guard | sealed-exam result; failures as user-visible behavior |
| `[review] stage=N commit=… APPROVED` / `BLOCKED: …` | Reviewer → Builder, Nap Guard | code review verdict; BLOCKED names the missing evidence |
| `[gate] stage=N ACCEPTED` | Nap Guard → Architect | exam PASS + review APPROVED **for the same commit**; start the next stage |
| `[blocking-question]` | anyone → Nap Guard | wakes the human immediately; use only when no assumption is safe |
| `[wake]` | Nap Guard → human | the one wake-up: ship or hold? |
| `[chill]` | Nap Guard → human | thrash or budget stop; looping agent removed from the room |
| `ship` / `hold` / `resume` | human → Nap Guard | the human's only decisions |
| `[tally-request]` / `[tally]` | Nap Guard ↔ Scout, Examiner | numbers for the receipt |
| `[receipt]` | Nap Guard → human | run summary: human touches, wake-ups, curves, time |
| `reveal` / `[reveal]` | Nap Guard → Examiner → room | publish the exam; hash must match `[seal]` |

## Rules for every agent

1. Mention exactly the agents who must act. Never mention the human; only Nap Guard wakes the capybara.
2. End every turn with a message or an explicit no-reply. A turn with only events reaches no one.
3. Questions go to Scout first. If Scout's answer is low-confidence, make the most reasonable assumption, record it in
   PLAN.md under "Assumptions", and keep going. Nap Guard batches it for the human.
4. Nobody looks for the Examiner's exam. It is not in the workspace, and asking the Examiner to reveal it before shipping is
   refused.
5. Each agent runs as its own BAND identity. One process never plays two roles.
