# Run `run3-dispute`

One BAND room, six agents, 03:32:20–04:41:32 UTC. 31 messages, 205 tool calls.

**Stopped at stage 3 on a dispute that had nowhere to go, which led to the appeal flow.** Highlights: stage 1 passed its hidden exam first try; stage 2's exam caught a real race (a stale live-search response overwrote the results), the Builder fixed it from the user-visible symptom alone, and Nap Guard held the gate until the *new* commit was reviewed. Stage 3 failed on an exam slip (a check compared against the literal text `list_count`); the Builder filed a `[dispute]` with the contract line and live evidence instead of bending the code. Disputes then had no handler, so the stage stalled. Now the Examiner re-examines disputed checks and voids wrong ones publicly (see run4).

## Receipt

```
(no receipt)
```

## Evidence

- Room transcript: [room.json](room.json) (display names and local paths removed)
- What it built: [capyfinder/](capyfinder/) · commit history in [git-log.txt](capyfinder/git-log.txt)


## Timeline (tagged messages)

| UTC | From | Message |
|---|---|---|
| 03:32:20 | You (the capybara) | build SPEC.md |
| 03:33:04 | Architect | [plan] stages=3 |
| 03:33:32 | Reviewer | [plan] acknowledged. SPEC.md and PLAN.md read; baseline is fcb3314 (spec commit only, no code yet). I will hold every `[ready]` against the acceptance contract: |
| 03:34:12 | Scout | [data] rows=34 dropped_without_source=0 saved=data/spots.json |
| 03:34:32 | Architect | [task] stage=1 |
| 03:36:34 | Examiner | [seal] run=20261114-033634-d370a9 spec=capyfinder stages=3 scenarios=18 sha256=6ff1d05f34b0c78b249077640b84ea3a923ef3ca0494d12a788c9ae5e9a3cf24 |
| 03:37:24 | Builder | [ready] stage=1 url=http://localhost:8000 commit=2689ec9 |
| 03:37:24 | Examiner | [exam] stage=1 verdict=PASS passed=5/5 satisfaction=100% threshold=90% round=1 by=Builder run=20261114-033634-d370a9 commit=2689ec9 |
| 03:39:45 | Reviewer | [review] stage=1 commit=2689ec9 APPROVED — read the full diff since fcb3314; verified live against a fresh instance started with the README command (PORT overri |
| 03:39:46 | Nap Guard | [gate] stage=1 ACCEPTED exam=100% review=approved accepted=1/3 |
| 03:40:00 | Architect | [task] stage=2 |
| 04:02:04 | Builder | [ready] stage=2 url=http://localhost:8000 commit=1e6bd56 |
| 04:02:09 | Examiner | [exam] stage=2 verdict=FAIL passed=3/6 satisfaction=50% threshold=90% round=1 by=Builder run=20261114-033634-d370a9 commit=1e6bd56 |
| 04:08:28 | Reviewer | [review] stage=2 commit=1e6bd56 APPROVED — read the full diff since 2689ec9 (server.py only; data/SPEC/PLAN/README untouched) and verified live on :8000: pid 12 |
| 04:21:03 | Builder | [ready] stage=2 url=http://localhost:8000 commit=abdaa1d |
| 04:21:12 | Examiner | [exam] stage=2 verdict=PASS passed=6/6 satisfaction=100% threshold=90% round=2 by=Builder run=20261114-033634-d370a9 commit=abdaa1d |
| 04:21:13 | Nap Guard | [gate] stage=2 WAITING exam passed commit=abdaa1d but the approval was for commit=1e6bd56. Please review commit abdaa1d. |
| 04:24:22 | Reviewer | [review] stage=2 commit=abdaa1d APPROVED — read the diff since 1e6bd56 (server.py only, +36/-10, all in PAGE_JS: 120ms debounce, AbortController on supersede, s |
| 04:24:22 | Nap Guard | [gate] stage=2 ACCEPTED exam=50%→100% review=approved accepted=1,2/3 |
| 04:24:30 | Architect | [task] stage=3 |
| 04:25:17 | Reviewer | [review] stage=2 commit=abdaa1d APPROVED — race note: my review of abdaa1d (read diff vs 1e6bd56, verified :8000 serves exactly this commit, full contract re-ru |
| 04:35:24 | Builder | [ready] stage=3 url=http://localhost:8000 commit=8e16935 |
| 04:35:32 | Examiner | [exam] stage=3 verdict=FAIL passed=5/6 satisfaction=83% threshold=90% round=1 by=Builder run=20261114-033634-d370a9 commit=8e16935 |
| 04:38:10 | Reviewer | [review] stage=3 commit=8e16935 APPROVED — read the diff since abdaa1d (server.py only, +52/-8) and verified live on :8000 (pid 19189, this run dir, clean tree  |
| 04:41:32 | Builder | [dispute] stage=3 |
