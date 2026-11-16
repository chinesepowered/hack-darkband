# Demo video: "Don't wake the capybara" (about 2½ minutes)

The video is built from run 7, a real run with the coding crew in BAND Desktop. `scripts/make_video.py` turns each
`> VO:` line into narration with ElevenLabs (voice: Jessica, young and warm). It replays the real BAND room transcript
for the scenes in `demo/scenes.json`, shows a sped-up stretch of the BAND Desktop window recorded during the run
(`ONSEN_DESKTOP_RECORDING`), records the app the factory built, and joins everything with ffmpeg. Every message in the
replay is the agents' own words.

### 1. Cold open
> VO: This capybara is the only human on our engineering team. Our software factory has exactly one rule: don't wake the capybara.

### 2. The crew
> VO: Six agents share one BAND room. BAND Desktop runs the coding crew: an Architect, a Builder and a read-only Reviewer, on OpenCode with Qwen three point eight. Scout reads the live web with Nimble. The Examiner keeps a sealed exam. And Nap Guard is the only one allowed to wake me.

### 3. BAND Desktop
> VO: BAND Desktop's daemon owns each crew agent's runtime. When a message mentions one, it starts OpenCode in the run's workspace and posts what the agent sends back to the room.

### 4. Ask the web, not the human
> VO: I send one message and go back to my bath. The Architect plans and asks Scout for data. Nimble comes back empty twice, so the Architect asks again and builds on the five sourced spots it gets, noting that the spec asked for more.

### 5. The sealed exam
> VO: The Examiner writes a hidden exam from the spec and that data, seventeen scenarios, and posts only its fingerprint. The builders never see it.

### 6. Live in BAND Desktop
> VO: In BAND Desktop you can watch every agent work, and interrupt any of them. Stage one passes its hidden exam five out of five, and the Reviewer approves that exact commit after eighty-nine checks of its own.

### 7. Stage two
> VO: Stage two, the web page, passes six out of six on the first try.

### 8. Stage three
> VO: So does stage three, the hot-spring mode. Nobody asks me anything.

### 9. Getting here
> VO: It took seven runs to get here. The Reviewer caught a Builder bending data. The exam caught a bug the Reviewer missed. And when BAND Desktop turned every closing remark into a message, the launcher learned to keep them out.

### 10. Ship
> VO: Then I get one message: ship, or hold? I say ship. The receipt: two human touches, one wake-up. The Examiner reveals the exam, and its fingerprint matches the one from the start.

### 11. What it built
> VO: Here's what the factory built: CapyFinder. Search, filters, a hot-spring toggle, and a source link on every spot.

### 12. Outro
> VO: Onsen. Specs go in, software comes out, and the capybara keeps napping. Built on BAND, with Nimble.
