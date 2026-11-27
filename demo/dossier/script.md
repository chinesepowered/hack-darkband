# Demo video: "Don't wake the capybara" (Dossier track, about 2½ minutes)

Built by `scripts/make_video.py` from the judged run: each `> VO:` line becomes narration (ElevenLabs), the replay
scenes play the real room transcript (`scripts/fetch_room.py`), the clip scene is the BAND Desktop recording, and the
app scene records the service the band built. Numbers in {braces} come from `scripts/run_facts.py` on the judged run.

### 1. Title (card: title)
> VO: This capybara is the only human on our team. Our software factory has one rule: don't wake the capybara.

### 2. The band (card: crew)
> VO: Onsen is five seats in one BAND room. An Architect, a Builder, an Examiner and a Reviewer run in BAND Desktop, on OpenCode with GPT-6 Luna. The fifth, Nap Guard, has no model at all. It's code, and it gates every stage.

### 3. One message (replay: the task to the Architect's first handoff)
> VO: I send one message, the whole task, four stages of a company-research service, and go back to my bath. That's the only human input. The Architect hands every seat the complete spec, in numbered parts.

### 4. The sealed exam (replay: to the first [seal])
> VO: Before any code exists, the Examiner writes its own exam as executable checks, and seals it by hash. The Builder never sees it.

### 5. Build, hand off, judge (replay: to the first [exam] and [review])
> VO: The Builder commits in small steps, runs the event's checker, and hands off one exact commit. The Examiner grades it with a tool that computes the verdict. The Reviewer reads the diff and probes the running service.

### 6. The gate (card: gate)
> VO: No seat's word opens the gate. Nap Guard recounts the exam, needs the review on that same commit, then runs the event's checker itself.

### 7. A bad result it caught (replay: the block and the fix, from the judged run)
> VO: {what the graders caught in the judged run, and how the fix came back through the room}

### 8. A stage is in (replay: to [gate] stage=N ACCEPTED and [reveal])
> VO: Stage {N} is in. The Architect copies the folder forward for the next spec, and the Examiner publishes its exam. The hash matches the seal from the start.

### 9. What the practice runs taught it (card: lessons)
> VO: It took {R} practice runs to get here. A model Examiner reported checks it never ran, so verdicts are computed by tools. Seats argued by re-posting, so the room has a linter. A Builder kept polishing a finished stage, so accepted stages close.

### 10. What it built (app)
> VO: Here's what the band built: dossiers researched on the live web through Nimble, every value with its source, and contested fields side by side.

### 11. The numbers (card: numbers)
> VO: {stages} stages in {hours} hours, {spend} of model time, one human message, and no wake-ups.

### 12. Outro (card: outro)
> VO: Onsen. Specs go in, software comes out, and the capybara keeps napping.
