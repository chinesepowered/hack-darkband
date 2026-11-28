# Demo video: "Don't wake the capybara" (Dossier track, about 2½ minutes)

Built by `scripts/make_video.py` from the judged run (Run U): each `> VO:` line becomes narration (ElevenLabs), the
scenes 3 and 5 are a screen recording of the judged room in BAND Desktop (scrolled from the task, cut with held
frames; the clips are in `$ONSEN_DESKTOP_CLIPS`), the replay scenes play the real room transcript
(`scripts/fetch_room.py`), and the app scene records the service the band built (stage 4, beside the event's mock
web). Every number comes from `scripts/run_facts.py` on that run.

### 1. Title (card: title)
> VO: This capybara is the only human on our team. Our software factory has one rule: don't wake the capybara.

### 2. The band (card: crew)
> VO: Onsen is five seats in one BAND room. An Architect, a Builder, an Examiner and a Reviewer run in BAND Desktop, on OpenCode with GPT-6 Luna. The fifth, Nap Guard, has no model at all. It's code, and it gates every stage.

### 3. One message (BAND Desktop: the task, then the Architect's numbered parts)
> VO: I sent one message, the whole task: four stages of a company research service. Then I went back to my bath. The Architect hands every seat the complete spec, in numbered parts.

### 4. The sealed exam (replay: to the first seal)
> VO: Before any code exists, the Examiner writes its own exam as executable checks, and seals it by hash. The Builder never sees it.

### 5. Build, hand off, judge (BAND Desktop: the seal, the first handoff, its exam and its review)
> VO: The Builder commits in small steps, runs the event's checker, and hands off one exact commit. The Examiner grades it with a tool that computes the verdict, while the Reviewer reads the diff and probes the running service.

### 6. The gate (card: gate)
> VO: No seat's word opens the gate. Nap Guard recounts the exam, needs the review on the same commit, and runs the event's checker itself.

### 7. A bad result it caught (replay: the block, the fixes, the passing exam)
> VO: Stage one's first handoff passed most of the event's checks. But the hidden exam caught that importing an export failed outright, and the Reviewer caught a build that carried on after its search failed. The fixes came back through the room, and the next handoff passed the exam at ninety-six percent.

### 8. A stage is in (replay: to the gate)
> VO: Stalls escalate instead of looping. After two chill breaks, one grader's pass and the checker's claim are enough. Stage one is in, and the Architect copies the folder forward for the next spec.

### 9. What the practice runs taught it (card: lessons)
> VO: It took twenty practice runs to get here. A model Examiner reported checks it never ran, so verdicts are computed by tools. Seats argued by re-posting, so the room has a linter. A Builder kept polishing a finished stage, so accepted stages close.

### 10. What it built (app)
> VO: Here's what the band built: company dossiers researched through Nimble, every value with the excerpt that supports it, and competing sources side by side.

### 11. The numbers (card: numbers)
> VO: All four stages, in five hours and fourteen minutes, for under ten dollars of model time. One human message, and no wake-ups.

### 12. Outro (card: outro)
> VO: Onsen. Specs go in, software comes out, and the capybara keeps napping.
