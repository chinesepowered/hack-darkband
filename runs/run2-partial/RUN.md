# Run `run2-partial`

One BAND room, six agents, 02:38:00–03:29:15 UTC. 47 messages, 192 tool calls.

**Partial run, stopped on purpose.** Stages 1 and 2 were accepted cleanly: the hidden exam passed on the first try, and each approval was bound to the commit that passed. Stage 3 kept failing on four of the exam's own slips: captures written backwards, and a judge step with no claim. We stopped the run, made the Examiner repair those slips and count setup errors as exam bugs, and ran again (see run3).

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
| 02:38:00 | You (the capybara) | build SPEC.md |
| 02:38:33 | Architect | [plan] stages=3 |
| 02:39:05 | Reviewer | [review] baseline read: SPEC.md + PLAN.md in hand; repo at commit 384e850 (spec only, no code/data yet). I'll verify every [ready] stage against the acceptance  |
| 02:39:22 | Builder | [plan] acknowledged — 3 stages understood. Stage 1 first step dispatched: data request sent to Scout for `data/spots.json` (20–40 spots, ≥3 countries, every spo |
| 02:39:35 | Architect | [task] pending — heads-up: the data request is already dispatched by me to Scout (exact spec wording, `out=data/spots.json`), so please do not send a second one |
| 02:39:41 | Scout | [data] rows=40 dropped_without_source=0 saved=data/spots.json |
| 02:39:50 | Builder | [task] understood — standing by, no stage 1 work, hands off `data/spots.json`. One disclosure: my data request to Scout went out at ~02:39 UTC, just before this |
| 02:40:20 | Architect | [task] stage=1 |
| 02:40:21 | Architect | [data] received and verified — 40 rows, 5 countries, 0 dropped, all fields valid. Thank you; no further data requests in this run. |
| 02:40:47 | Scout | [data] rows=30 dropped_without_source=0 saved=data/spots.json |
| 02:40:52 | Scout | [answer] for=Architect confidence=low claims=0 sources=0 |
| 02:40:57 | Scout | [answer] for=Architect confidence=low claims=0 sources=0 |
| 02:41:56 | Architect | [task] stage=1 UPDATE — dataset swap: `data/spots.json` was rewritten by the duplicate Scout run. Current file is FINAL: 30 rows, 7 countries (JP 10, US 10, GB  |
| 02:42:03 | Scout | [answer] for=Architect confidence=low claims=0 sources=0 |
| 02:42:24 | Scout | [answer] for=Architect confidence=low claims=0 sources=0 |
| 02:44:07 | Examiner | [seal] run=20261114-024407-9c9657 spec=capyfinder stages=3 scenarios=17 sha256=759d213b440372f9c8c682c5e1630743cbd4879e5095096f188fceca93c69e98 |
| 02:44:29 | Builder | [ready] stage=1 url=http://localhost:8000 commit=1548f05 |
| 02:48:29 | Reviewer | [review] stage=1 commit=1548f05 APPROVED diff read (app.py 106 lines stdlib, data/spots.json, README, .gitignore); contract verified live on two instances (buil |
| 02:48:56 | Examiner | [seal] run=20261114-024856-01efb0 spec=capyfinder stages=3 scenarios=20 sha256=076f12b213e3f1cb2aaf55e05ef4b19f948cc1044c6b15389e48058a543ad720 |
| 02:48:56 | Examiner | [exam] stage=1 verdict=PASS passed=7/7 satisfaction=100% threshold=90% round=1 by=Builder run=20261114-024856-01efb0 commit=1548f05 |
| 02:48:57 | Nap Guard | [gate] stage=1 ACCEPTED exam=100% review=approved accepted=1/3 |
| 02:50:03 | Architect | [task] stage=2 |
| 03:01:57 | Builder | [ready] stage=2 url=http://localhost:8000 commit=ef2ffd9 |
| 03:02:00 | Examiner | [exam] stage=2 verdict=PASS passed=5/5 satisfaction=100% threshold=90% round=1 by=Builder run=20261114-024856-01efb0 commit=ef2ffd9 |
| 03:07:03 | Reviewer | [review] stage=2 commit=ef2ffd9 APPROVED diff read (app.py only, +250/−13; data hash 3b8e0ef2… unchanged, read-only confirmed); verified live on builder's :8000 |
| 03:07:03 | Nap Guard | [gate] stage=2 ACCEPTED exam=100% review=approved accepted=1,2/3 |
| 03:07:22 | Architect | [task] stage=3 |
| 03:14:34 | Builder | [ready] stage=3 url=http://localhost:8000 commit=2f395a6 |
| 03:14:39 | Examiner | [exam] stage=3 verdict=FAIL passed=4/8 satisfaction=50% threshold=90% round=1 by=Builder run=20261114-024856-01efb0 commit=2f395a6 |
| 03:16:51 | Reviewer | [review] stage=3 commit=2f395a6 APPROVED diff read (app.py only, +55/−3; data hash 3b8e0ef2… unchanged); verified live on builder's :8000 + my own instance of t |
| 03:28:45 | Builder | [ready] stage=3 url=http://localhost:8000 commit=bc1d48f |
| 03:28:51 | Examiner | [exam] stage=3 verdict=FAIL passed=4/8 satisfaction=50% threshold=90% round=2 by=Builder run=20261114-024856-01efb0 commit=bc1d48f |
