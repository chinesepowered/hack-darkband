# Run `run4`

One BAND room, six agents, 04:46:13–05:48:13 UTC. 59 messages, 237 tool calls.

**The recorded run: one kickoff, a chill break we caused, `ship`, and a revealed exam whose hash matches the seal.** Stage 1 passed its hidden exam on the first try (7/7). Stage 2's first exam caught a real bug the Reviewer had approved: a JavaScript syntax error left live search and filters dead in a real browser. The Builder fixed it from the user-visible symptom, and from then on the Reviewer verified in headless Chrome. The rest of stage 2's failures were the factory's own: a check asked for role `textbox` where the spec says `input type=search` (role `searchbox`); Nap Guard's parser read `stage=N` from the Examiner's dispute hint and crashed on every failing exam; an LLM judge failed a page it had passed the round before; and the Examiner filed the Builder's request for a re-run as a note. After four rounds without progress, Nap Guard called a chill break (wake-up #1). Stage 3 passed on the first try (6/6).

**Operator actions, all outside the room:** each bug was fixed in the factory, with tests (commit `f0f616a`), and the Examiner (5 times) and Nap Guard (once) were restarted mid-run. BAND redelivered the three exam messages Nap Guard had failed on, so its stage record is complete. The sealed exam file never changed. Human messages in the room: the kickoff, `resume`, one relay of the Builder's re-run request (it reached the old Examiner 37 seconds before the fix), and `ship`.

## Receipt

```
[receipt] 🛁 Onsen run complete
• Human touches: 4 (the spec + 3 replies to Nap Guard) · wake-ups: 2 · chill breaks: 1
• Stages: 1 ✔ 100% (1 rounds) · 2 ✔ 57%→86%→86%→86%→100% (5 rounds) · 3 ✔ 100% (1 rounds)
• Questions the web answered: 0 · escalated: 0 (batched into the wake-up)
• Docs fetched: 0 · datasets built: 1 · exam rounds: 7 · exam checks voided on appeal: 0
• Time from seal to ship: 56m 42s
• Sealed exam sha256=138aa57aa9039a53… — asking the Examiner to reveal it now.
The capybara was woken 2 times. 🍊
```

## Evidence

- Room transcript: [room.json](room.json) (display names and local paths removed)
- What it built: [capyfinder/](capyfinder/) · commit history in [git-log.txt](capyfinder/git-log.txt)
- Revealed exam: [exam.json](exam.json) · sha256 `138aa57aa9039a53041983f97f105ad35f4f9d21f0ae42ebdcad399ea5cb0bca` · matches the last `[seal]`

## Timeline (tagged messages)

| UTC | From | Message |
|---|---|---|
| 04:46:13 | You (the capybara) | build SPEC.md |
| 04:46:57 | Architect | [plan] stages=3 |
| 04:47:17 | Builder | [ack] stage=1 status=waiting — plan read, SPEC.md acceptance contract noted (field names, routes, labels, test ids will not be renamed). `data/` is empty right  |
| 04:47:53 | Scout | [data] rows=36 dropped_without_source=0 saved=data/spots.json |
| 04:48:15 | Architect | [task] stage=1 |
| 04:50:41 | Builder | [ready] stage=1 url=http://localhost:8000 commit=811625e |
| 04:51:30 | Examiner | [seal] run=20261114-045130-0c6f0d spec=capyfinder stages=3 scenarios=20 sha256=138aa57aa9039a53041983f97f105ad35f4f9d21f0ae42ebdcad399ea5cb0bca |
| 04:51:30 | Examiner | [exam] stage=1 verdict=PASS passed=7/7 satisfaction=100% threshold=90% round=1 by=Builder run=20261114-045130-0c6f0d commit=811625e |
| 04:51:43 | Builder | [ack] stage=1 exam=PASS 7/7 — noted. Server stays up on 8000 at commit 811625e; waiting on the review verdict before the gate. |
| 04:51:48 | Reviewer | [review] stage=1 commit=811625e APPROVED read the full diff (server.py, data/spots.json, README) and verified live: 36 rows / 4 countries, every record has all  |
| 04:51:48 | Nap Guard | [gate] stage=1 ACCEPTED exam=100% review=approved accepted=1/3 |
| 04:51:56 | Builder | [ack] stage=1 complete — exam PASS (7/7) + review APPROVED, both at commit 811625e. Server remains up on 8000; ready for `[task] stage=2`. |
| 04:52:04 | Architect | [task] stage=2 |
| 05:05:46 | Builder | [ready] stage=2 url=http://localhost:8000 commit=4a4d6b1 |
| 05:06:06 | Examiner | [exam] stage=2 verdict=FAIL passed=4/7 satisfaction=57% threshold=90% round=1 by=Builder run=20261114-045130-0c6f0d commit=4a4d6b1 |
| 05:08:06 | Reviewer | [review] stage=2 commit=4a4d6b1 APPROVED read the full diff vs 811625e and verified the live DOM on :8000: h1 exactly "CapyFinder"; `input type=search` with vis |
| 05:16:23 | Builder | [ready] stage=2 url=http://localhost:8000 commit=4731c94 |
| 05:16:38 | Examiner | [exam] stage=2 verdict=FAIL passed=6/7 satisfaction=86% threshold=90% round=2 by=Builder run=20261114-045130-0c6f0d commit=4731c94 |
| 05:18:38 | Builder | [ready] stage=2 url=http://localhost:8000 commit=a57aa44 |
| 05:18:52 | Examiner | [exam] stage=2 verdict=FAIL passed=6/7 satisfaction=86% threshold=90% round=3 by=Builder run=20261114-045130-0c6f0d commit=a57aa44 |
| 05:25:23 | Builder | [ready] stage=2 url=http://localhost:8000 commit=75d2f77 |
| 05:25:27 | Reviewer | [review] stage=2 commit=4731c94 BLOCKED: the presented commit no longer matches the running app — `git log` now has a57aa44 on top (Type pre-select polish, whic |
| 05:25:28 | Examiner | [exam-error] invalid literal for int() with base 10: '2`' |
| 05:27:59 | Builder | [ready] stage=2 url=http://localhost:8000 commit=75d2f77 |
| 05:28:11 | Examiner | [exam] stage=2 verdict=FAIL passed=6/7 satisfaction=86% threshold=90% round=4 by=Builder run=20261114-045130-0c6f0d commit=75d2f77 |
| 05:28:12 | Nap Guard | [chill] #1 stage=2 reason=thrash |
| 05:29:43 | Reviewer | [review] stage=2 commit=75d2f77 APPROVED (for Builder and Nap Guard; Builder is no longer in the room, so addressed to you, @Nap Guard) — read the full stage-2  |
| 05:30:12 | You (the capybara) | resume |
| 05:30:13 | Nap Guard | [gate] resume=true I put Builder back in the room. Picking up where we left off. |
| 05:30:49 | Architect | [status] stage=2 |
| 05:30:52 | Reviewer | [review] stage=2 commit=75d2f77 APPROVED — this [ready] names the exact commit I already approved in my previous message (full evidence there: full stage-2 diff |
| 05:32:19 | Reviewer | [review] stage=2 commit=75d2f77 APPROVED — standing, confirmed for this [ready]. I'd already approved 75d2f77 in two earlier messages (full evidence there: diff |
| 05:37:44 | You (the capybara) | rerun stage=2 commit=75d2f77 (the Builder asked for a clean re-run at 05:35) |
| 05:37:45 | Nap Guard | [status] wake-ups=1 chill_breaks=1 questions_batched=0 shipped=False |
| 05:37:52 | Examiner | [exam] stage=2 verdict=PASS passed=7/7 satisfaction=100% threshold=90% round=5 by=Builder run=20261114-045130-0c6f0d commit=75d2f77 |
| 05:37:53 | Nap Guard | [gate] stage=2 ACCEPTED exam=57%→86%→86%→86%→100% review=approved accepted=1,2/3 |
| 05:38:11 | Architect | [task] stage=3 |
| 05:42:34 | Builder | [ready] stage=3 url=http://localhost:8000 commit=a16e43f |
| 05:42:40 | Examiner | [exam] stage=3 verdict=PASS passed=6/6 satisfaction=100% threshold=90% round=1 by=Builder run=20261114-045130-0c6f0d commit=a16e43f |
| 05:47:44 | Reviewer | [review] stage=3 commit=a16e43f APPROVED read the full diff since my approved stage-2 commit (a16e43f on top of the 731832e PLAN.md log) and verified live at :8 |
| 05:47:45 | Nap Guard | [wake] #2 reason=ready-to-ship |
| 05:48:11 | You (the capybara) | ship |
| 05:48:11 | Nap Guard | [tally-request] The human shipped 🚀. Scout and Examiner, send me your tallies for the receipt. |
| 05:48:12 | Examiner | [tally] agent=examiner run=20261114-045130-0c6f0d rounds=7 curves=1:100%;2:57%→86%→86%→86%→100%;3:100% voided=0 |
| 05:48:12 | Scout | [tally] agent=scout answered=0 escalated=0 docs=0 data=1 failed=0 |
| 05:48:12 | Nap Guard | [receipt] 🛁 Onsen run complete |
| 05:48:13 | Examiner | [reveal] run=20261114-045130-0c6f0d sha256=138aa57aa9039a53041983f97f105ad35f4f9d21f0ae42ebdcad399ea5cb0bca scenarios=20 author=Qwen/Qwen3.8-27B |
