# Demo video: "Don't wake the capybara" (about 3 minutes)

Record the real BAND Desktop room. In BAND's live feed, show messages, tool calls and tasks. Speed up the waiting parts
4–8×, but never fake a step. Narration is in the `> VO:` lines; `uv run python scripts/voiceover.py` turns them into
MP3s with ElevenLabs (Jessica, a young, warm, playful voice).

### 1. Cold open (0:00–0:15)
**Screen:** the mascot in its hot spring. Title card "Onsen".
> VO: This capybara is the only human on our engineering team. Our software factory has exactly one rule: don't wake the capybara.

### 2. The crew (0:15–0:35)
**Screen:** BAND Desktop, the room's participant list: Architect and Reviewer on Claude Code, Builder on Codex, plus
Scout, Examiner and Nap Guard. The human types a single message: `@Architect build SPEC.md`.
> VO: Six agents share one BAND room. Claude Code plans and reviews, Codex builds, Scout reads the live web with Nimble, the Examiner grades, and Nap Guard decides if anything is worth waking me up for. I send one message and go back to my bath.

### 3. The sealed exam (0:35–1:00)
**Screen:** the Examiner's `[seal]` message with the SHA-256. Then switch to the Builder's view to show the exam isn't
in its context.
> VO: First, the Examiner writes a hidden exam from the spec and posts only its fingerprint. The builders never see it. BAND only delivers a message to the agents it mentions, and the exam lives in the Examiner's own container. Nobody can grade their own homework.

### 4. Ask the web, not the human (1:00–1:25)
**Screen:** Scout's `[data]` reply (40 spots, each with a source). Then a `[docs]` reply, and a low-confidence `[answer]`
that Nap Guard quietly batches.
> VO: When the factory needs facts, it asks Scout, not me. Nimble's agents built our dataset, forty capybara spots with a source on every row. When the web can't settle a question, Nap Guard saves it for later instead of waking me.

### 5. The loop (1:25–2:00)
**Screen:** the Builder's `[ready]` → the Examiner's `[exam] FAIL 62%` with user-visible failures → a fix → the
Reviewer's `BLOCKED` on a hard-coded value → `[exam] PASS 100%` → `[review] APPROVED` → Nap Guard's
`[gate] ACCEPTED`. Show the Work tab moving.
> VO: Here's the loop. The Examiner fails stage one at sixty-two percent, and the Builder only sees what a user would notice. The Reviewer blocks a shortcut. Round two passes, and Nap Guard hands the next stage to the Architect. Nobody asked me anything.

### 6. Chill break (2:00–2:20)
**Screen:** a `[chill]` message from a deliberately thrashing run. The looping agent leaves the room.
> VO: And if a stage starts going in circles, Nap Guard calls a chill break. It takes the looping agent out of the room before it burns the budget, and that's the only other way to wake me.

### 7. The one wake-up (2:20–2:50)
**Screen:** `[wake] #1 ready-to-ship` → the human types `ship` → `[receipt]` → `[reveal]`, then `sha256sum` matching
the seal.
> VO: When every stage passes, I get exactly one message: ship or hold? I say ship. The receipt counts two human touches and one wake-up. Then the Examiner reveals the exam, and its fingerprint matches the one from the start.

### 8. Outro (2:50–3:00)
**Screen:** the CapyFinder app running, then the mascot.
> VO: Onsen. Specs go in, software comes out, and the capybara keeps napping. Built on BAND, with Nimble.
