# Demo video: "Don't wake the capybara" (about 3 minutes)

The video is built from a real run. `scripts/make_video.py` turns each `> VO:` line into narration with ElevenLabs
(voice: Jessica, young and warm). It then replays the real BAND room transcript for the scenes in `demo/scenes.json`,
records the app the factory built, and joins everything with ffmpeg. Every message in the replay is the agents' own
words.

### 1. Cold open
> VO: This capybara is the only human on our engineering team. Our software factory has exactly one rule: don't wake the capybara.

### 2. The crew
> VO: Six agents share one BAND room. An Architect, a Builder and a read-only Reviewer run OpenCode on Qwen three point eight. Scout reads the live web with Nimble. The Examiner keeps a sealed exam. And Nap Guard is the only one allowed to wake me. I send one message, and go back to my bath.

### 3. Ask the web, not the human
> VO: The Architect plans the build and asks Scout for data. Nimble's agents come back with real capybara spots from around the world, and every row carries the page it came from.

### 4. The sealed exam
> VO: Next, the Examiner writes a hidden exam from the spec, proofreads it against the data, and posts only its fingerprint. The builders never see it. BAND only delivers a message to the agents it mentions.

### 5. The loop
> VO: The Builder ships stage one. The Reviewer reads the diff and re-runs the contract on its own server. The sealed exam passes. Because the approval and the exam are for the same commit, Nap Guard accepts the stage and hands the next one to the Architect.

### 6. Stages two and three
> VO: Stages two and three run the same loop: build, exam, review, gate. When a check fails, the Builder only learns what a user would notice. Nobody asks me anything.

### 7. The rehearsal
> VO: It wasn't always this smooth. In our rehearsal, the Builder edited the dataset to pass a bad check. The Reviewer blocked it, the Builder reverted, and we fixed the factory, not just the code.

### 8. The one wake-up
> VO: When every stage passes, I get exactly one message: ship, or hold? I say ship. The receipt counts two human touches and one wake-up, and the Examiner reveals the exam. Its fingerprint matches the one from the start.

### 9. What it built
> VO: Here's what the factory built: CapyFinder. Search, filters, a hot-spring toggle, and a source link on every spot.

### 10. Outro
> VO: Onsen. Specs go in, software comes out, and the capybara keeps napping. Built on BAND, with Nimble.
