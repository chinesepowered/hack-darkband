# Demo video: "Don't wake the capybara" (about 3 minutes)

The video is built from run 4, a real run. `scripts/make_video.py` turns each `> VO:` line into narration with
ElevenLabs (voice: Jessica, young and warm). It then replays the real BAND room transcript for the scenes in
`demo/scenes.json`, records the app the factory built, and joins everything with ffmpeg. Every message in the replay
is the agents' own words.

### 1. Cold open
> VO: This capybara is the only human on our engineering team. Our software factory has exactly one rule: don't wake the capybara.

### 2. The crew
> VO: Six agents share one BAND room. An Architect, a Builder and a read-only Reviewer run OpenCode on Qwen three point eight. Scout reads the live web with Nimble. The Examiner keeps a sealed exam. And Nap Guard is the only one allowed to wake me. I send one message, and go back to my bath.

### 3. Ask the web, not the human
> VO: The Architect plans the build and asks Scout for data. Nimble's agents come back with thirty-six real capybara spots, and every row carries the page it came from.

### 4. The sealed exam
> VO: The Examiner writes a hidden exam from the spec: twenty scenarios, checked against that data. It posts only a fingerprint. BAND delivers a message only to the agents it mentions, so the builders never see the exam.

### 5. Stage one
> VO: Stage one, the API, passes seven out of seven. The Reviewer approves that exact commit, and Nap Guard accepts the stage.

### 6. Stage two
> VO: Stage two is the web page, and the exam fails it. A syntax error left live search dead in a real browser. The Reviewer had approved it by reading the HTML. The exam caught it by using the page. The Builder fixes it, and the Reviewer starts testing in a real browser too. Then the exam itself stumbles. After four rounds without progress, Nap Guard calls a chill break and wakes me.

### 7. Our bugs
> VO: The bugs were ours, not the Builder's: a check that asked for the wrong kind of text box, a parser that crashed Nap Guard, a judge that changed its mind, and a re-run request filed as a note. Every fix went into the factory itself.

### 8. Stage two passes
> VO: I say resume, and pass along the Builder's request for a re-run. Stage two passes seven out of seven, on the same commit the Reviewer approved.

### 9. Stage three
> VO: Stage three, stats and a hot-spring toggle, passes six out of six on the first try. The Reviewer recomputes every count from the data and approves. Only then does Nap Guard wake me again.

### 10. The rehearsal
> VO: Every run teaches the factory something. In our rehearsal, the Builder edited the dataset to pass a bad check. The Reviewer blocked it, and now every approval is bound to the exact commit that passed.

### 11. Ship
> VO: Every stage passed, so I get one question: ship, or hold? I say ship. The receipt is honest: four human touches, two wake-ups, one chill break. Then the Examiner reveals the exam, and its fingerprint matches the one from the start.

### 12. What it built
> VO: Here's what the factory built: CapyFinder. Search, filters, a hot-spring toggle, and a source link on every spot.

### 13. Outro
> VO: Onsen. Specs go in, software comes out, and the capybara keeps napping. Built on BAND, with Nimble.
