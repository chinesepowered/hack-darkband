# Run `run5-desktop-shakedown`

One BAND room, six agents, 18:24:34–18:42:29 UTC. 34 messages, 322 tool calls.

**The first run with the crew in BAND Desktop. Stopped after stage 1 on two factory bugs that BAND Desktop's reply model exposed.** BAND Desktop posts an agent's closing remark as a reply to whoever woke it. Qwen 3.8 rarely manages a truly empty remark, so the crew traded short acknowledgments (".", "(no reply)") that died out within a minute. When the instructions demanded total silence, the Architect instead looped on harmless tool calls until it was interrupted and its runtime restarted. Its first reply after the restart began "Seal receipt confirmed …", and the Examiner read the bare word "Seal" as a command and sealed a second exam mid-run. The first exam had also put two home-page checks into stage 1, which is API-only in the spec, so the Builder built the UI early instead of disputing. The run was stopped there. Fixes: bare command words need key=value arguments; re-run requests and duplicate `[ready]`s are rate-limited; Scout only searches on explicit `ask:`/`docs:`/`data:`; and a stage's exam may only use routes that its own and earlier stages introduce (see run6).

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
| 18:24:34 | You (the capybara) | build SPEC.md |
| 18:26:57 | Architect | [plan] stages=3 |
| 18:28:38 | Scout | [data] rows=24 dropped_without_source=0 saved=data/spots.json |
| 18:29:31 | Architect | [task] stage=1 |
| 18:32:29 | Examiner | [seal] run=20261116-183228-5f19ab spec=capyfinder stages=3 scenarios=21 sha256=4017a1cbb950aeac06e25f30a5b812d366b0652c7c8d6b7072ab23bd85cf213f |
| 18:34:23 | Builder | [ready] stage=1 url=http://localhost:8000 commit=2d69257 Stage 1 built: stdlib Python server (python3 app.py, port 8000, PORT override), data/spots.json (24 spo |
| 18:34:38 | Examiner | [exam] stage=1 verdict=FAIL passed=5/7 satisfaction=71% threshold=90% round=1 by=Builder run=20261116-183228-5f19ab commit=2d69257 |
| 18:37:14 | Reviewer | [review] stage=1 commit=2d69257 APPROVED read full diff 2a96e18..2d69257 and ran every contract case live (health count, case-insensitive name sort, country/typ |
| 18:41:50 | Examiner | [seal] run=20261116-184150-29a473 spec=capyfinder stages=3 scenarios=20 sha256=6fe29829ba08f11f01bab68bd06acca68f4d1895add56a7dfff722f2bcc29d4c |
| 18:42:12 | Builder | [ready] stage=1 url=http://localhost:8000 commit=09f8217 Fixed both failures: implemented the Web UI per SPEC.md acceptance contract. Home page now renders all  |
| 18:42:14 | Examiner | [exam] stage=1 verdict=PASS passed=7/7 satisfaction=100% threshold=90% round=1 by=Builder run=20261116-184150-29a473 commit=09f8217 |
| 18:42:15 | Nap Guard | [gate] stage=1 WAITING exam passed commit=09f8217 but the approval was for commit=2d69257. Please review commit 09f8217. |
