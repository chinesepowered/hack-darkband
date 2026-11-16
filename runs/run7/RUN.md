# Run `run7`

One BAND room, six agents, 19:04:57–19:40:44 UTC. 30 messages, 153 tool calls.

**The recorded run, with the coding crew in BAND Desktop: one kickoff, one wake-up, `ship`.** BAND Desktop's daemon ran the Architect, the Builder and the Reviewer (OpenCode, Qwen 3.8 on W&B). Scout, the Examiner and Nap Guard ran as band-sdk agents. Nimble's dataset agent came back empty twice. The Architect asked Scout again and took the 5 sourced rows the retry returned, noting in the room that this is below the spec's 20–40 spots; the acceptance contract sets no minimum, so the exam grades what the data can produce. Every stage passed its hidden exam on the first round (5/5, 6/6, 6/6). The Reviewer approved each exact commit after its own live checks (89, about 110 and about 75). Nobody needed the human until Nap Guard's one wake-up, and the exam revealed after `ship` hashes to the seal.

Operator notes: no restarts and no interventions during the run. The one human message besides the kickoff is `ship`.

## Receipt

```
[receipt] 🛁 Onsen run complete
• Human touches: 2 (the spec + 1 reply to Nap Guard) · wake-ups: 1 · chill breaks: 0
• Stages: 1 ✔ 100% (1 rounds) · 2 ✔ 100% (1 rounds) · 3 ✔ 100% (1 rounds)
• Questions the web answered: 0 · escalated: 0 (batched into the wake-up)
• Docs fetched: 0 · datasets built: 2 · exam rounds: 3 · exam checks voided on appeal: 0
• Time from seal to ship: 23m 19s
• Sealed exam sha256=7324ab7dfac23e4b… — asking the Examiner to reveal it now.
The capybara was woken 1 time. 🍊
```

## Evidence

- Room transcript: [room.json](room.json) (display names and local paths removed)
- What it built: [capyfinder/](capyfinder/) · commit history in [git-log.txt](capyfinder/git-log.txt)
- Revealed exam: [exam.json](exam.json) · sha256 `7324ab7dfac23e4bb9ad4b66ca1f3a220c06d666c4cb033f7a01b7da0f5069cd` · matches the last `[seal]`

## Timeline (tagged messages)

| UTC | From | Message |
|---|---|---|
| 19:04:57 | You (the capybara) | build SPEC.md |
| 19:07:58 | Architect | [plan] stages=3 |
| 19:10:54 | Scout | [data] rows=0 dropped_without_source=1 saved=data/spots.json |
| 19:13:25 | Scout | [data] rows=5 dropped_without_source=0 saved=data/spots.json |
| 19:14:56 | Architect | [task] stage=1 |
| 19:16:29 | Builder | [ready] stage=1 url=http://localhost:8000 commit=25fd6c2 Stage 1 is live: /api/health, /api/spots (country / type / q filters, case-insensitive, AND-combined, u |
| 19:17:24 | Examiner | [seal] run=20261116-191723-c54045 spec=capyfinder stages=3 scenarios=17 sha256=7324ab7dfac23e4bb9ad4b66ca1f3a220c06d666c4cb033f7a01b7da0f5069cd |
| 19:17:24 | Examiner | [exam] stage=1 verdict=PASS passed=5/5 satisfaction=100% threshold=90% round=1 by=Builder run=20261116-191723-c54045 commit=25fd6c2 |
| 19:20:13 | Reviewer | [review] stage=1 commit=25fd6c2984fbc8cd617f7d337273446b9e203034 APPROVED read full diff 283f03f..25fd6c2 (app.py, README.md, data/spots.json) and ran 89 live c |
| 19:20:14 | Nap Guard | [gate] stage=1 ACCEPTED exam=100% review=approved accepted=1/3 |
| 19:21:20 | Architect | [task] stage=2 |
| 19:28:32 | Builder | [ready] stage=2 url=http://localhost:8000 commit=bf1f479 Stage 2 is live: / (h1 CapyFinder; Search spots box input[type=search]; Country select with All countri |
| 19:28:35 | Examiner | [exam] stage=2 verdict=PASS passed=6/6 satisfaction=100% threshold=90% round=1 by=Builder run=20261116-191723-c54045 commit=bf1f479 |
| 19:31:48 | Reviewer | [review] stage=2 commit=bf1f479f912c6904d8c018450b9af5bbff832931 APPROVED read full diff 25fd6c2..bf1f479 (app.py +248/-14, README) and ran ~110 live checks on  |
| 19:31:49 | Nap Guard | [gate] stage=2 ACCEPTED exam=100% review=approved accepted=1,2/3 |
| 19:32:15 | Architect | [task] stage=3 |
| 19:36:49 | Builder | [ready] stage=3 url=http://localhost:8000 commit=76bfa74 Stage 3 is live (final stage): GET /api/stats -> {'total': 5, 'by_country': {'JP': 1, 'US': 4}, 'by_typ |
| 19:37:06 | Examiner | [exam] stage=3 verdict=PASS passed=6/6 satisfaction=100% threshold=90% round=1 by=Builder run=20261116-191723-c54045 commit=76bfa74 |
| 19:40:06 | Reviewer | [review] stage=3 commit=76bfa74f6ff03e9cd04fe2c26d65dc249ea65b5e APPROVED read full diff bf1f479..76bfa74 (app.py +68/-9, README) and ran ~75 live checks on my  |
| 19:40:06 | Nap Guard | [wake] #1 reason=ready-to-ship |
| 19:40:41 | You (the capybara) | ship |
| 19:40:42 | Nap Guard | [tally-request] The human shipped 🚀. Scout and Examiner, send me your tallies for the receipt. |
| 19:40:42 | Scout | [tally] agent=scout answered=0 escalated=0 docs=0 data=2 failed=0 |
| 19:40:42 | Examiner | [tally] agent=examiner run=20261116-191723-c54045 rounds=3 curves=1:100%;2:100%;3:100% voided=0 |
| 19:40:43 | Nap Guard | [receipt] 🛁 Onsen run complete |
| 19:40:44 | Examiner | [reveal] run=20261116-191723-c54045 sha256=7324ab7dfac23e4bb9ad4b66ca1f3a220c06d666c4cb033f7a01b7da0f5069cd scenarios=17 author=Qwen/Qwen3.8-27B |
