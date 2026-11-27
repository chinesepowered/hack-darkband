# Practice runs: every run on Dossier, and every human-side action

Onsen ran on the Dossier track twenty-one times, Runs A to U. Each run started in a fresh BAND room and
a fresh result repository with one dispatched task, and each was started meaning to submit it; when a run showed a
factory defect we stopped it (or, in Run R, fixed the factory while it ran and treated it as practice), changed the
factory, and started again. **Run U is the judged run**, on factory commit `defe350`. Runs A to C ran on
26 November (UTC), the rest on 27 November.

This file lists everything the humans' side did, including actions that touched nothing in the room: restarting a
factory process, restarting the BAND Desktop window we watched, and every click that landed in the room. Nothing was
ever typed or sent into a room except each run's task.

- Run A (20:15 UTC): the quiet-room watcher exited at start because the task text mentions `[report]`; fixed the
  check and restarted it at 21:16. Its nudge at 21:20 woke an idle Builder. Run A was stopped at 23:23 after 3 h with
  no runnable revision: Qwen 3.8 at its default reasoning effort spent thousands of tokens thinking per step.
- Run B (23:24): reasoning effort medium. Stopped after 5 minutes to switch to thinking off (our choice;
  7.9 s vs 28.4 s on a coding test prompt).
- Run C (23:48): thinking off for every seat.
  - 01:06: the Builder used OpenCode's question tool to ask the human for the checker's full logs (outside its
    workspace). Nobody answered; the Builder carried on. We then denied the question tool in every seat's OpenCode
    profile (it applies when a runtime restarts) and made onsen-check print each failure's assertion lines, so no
    seat needs the log file.
  - 02:35: the Reviewer reported the checker's stage-2 browser suite erroring with "playwright chromium missing"
    (host mode had no browser). onsen-check now points Playwright at the machine's preinstalled Chromium, which
    matches its version. No message to the band.
- The container restarted during Run C (between 02:49 and 04:22 UTC), killing every process, so Run C ended there.
- Run D (04:28): every BAND Desktop seat on gpt-6-luna (OpenAI), medium effort, by our
  decision. Before it, a stuck Builder peer (10 undelivered messages from Run C's room) needed a daemon restart.
  We stopped Run D a minute in: BAND Desktop gives every seat a built-in ask-the-human tool
  (`jam-runtime_AskUserQuestion`), which the Builder used seven times to ask for "the rest of the spec", and seats
  acted on single parts of a nine-part handoff. Nothing was answered. We switched that tool off for every seat by
  name, made parts larger, and added the rule that a numbered handoff is complete only at part k/k.
- Run E (04:31): stopped after three minutes for chatter (acknowledgements, status requests). The protocol gained
  "quiet by default".
- Run F (04:34): stopped at 05:04. Two factory defects that more rules in the mandates would not have fixed:
  - The Examiner reported `passed=25/26` three times while its tool log shows it ran one probe per commit, and that
    probe used a company that isn't in the corpus, so "every field unknown" was the correct answer. It also called
    25/26 a FAIL although its mandate passes at 90%. The gate could never open.
  - The Architect kept a single turn open for 30 minutes, asking Nap Guard for status every 10 to 30 seconds.
    BAND Desktop hands a seat new messages only between its turns, so it never saw Nap Guard's `[chill]`.
  Before Run G the factory changed so that no seat's word is taken for a result: the Examiner's checks are
  executable and `onsen-exam` runs them and writes the verdict; Nap Guard recomputes PASS from the counts and runs
  the event's checker itself before it accepts a stage; `band send` passes only protocol messages, and none to Nap
  Guard but its five tags; every mandate tells the seat to end its turn while it waits.
- Run G (05:15): stopped after three minutes. The Examiner committed the Builder's uncommitted files under its own
  name, and read Run F's exam through `python` after OpenCode's file tool refused the path. Before Run H: a git
  pre-commit hook for the Examiner's and Reviewer's seats (only `onsen-exam publish` may commit), and `run-dark.sh`
  moves earlier runs' exam workspaces and the seats' scratch files out of reach; we moved earlier result repositories
  out of `band-work` by hand.
- Run H (05:19): ran to its report at 05:57. Stage 1 reached 122/122 shipped checks and passed the exam (14 checks,
  93-100%), but the Reviewer kept blocking real parser defects (a non-ASCII city, a greedy city match, then an
  overcorrection). The Builder re-posted `[ready]` for the same commit to argue, the Reviewer re-blocked each time,
  and Nap Guard counted every repeat: three chill breaks in 30 seconds, and the third told the Architect to end the
  run. Before Run I: Nap Guard counts a repeated verdict on one commit once and review blocks per blocked commit; the
  third chill break falls back to the checker instead of ending the run (open findings carry forward); the seats'
  `band send` refuses a second `[ready]` or `[review]` for the same commit.
- Run I (06:01): stopped at 06:58, before stage 1 was handed off. Twice the Builder ended a turn mid-work on a
  statement of intent and sat idle until the quiet-room nudge twelve minutes later, and the nudge budget (six per run)
  would not have lasted four stages. Two checker runs also failed to start because Docker could not create a network,
  most likely left over from checks we killed in earlier runs. Before Run J: the Builder's ACP proxy continues a turn
  that ended mid-work without a message to the room (at most four times per prompt); the quiet-room nudge comes after
  six minutes, at most thirty times; we removed the leftover Docker networks and images between runs.
- Run J (06:58): stopped at 07:09. The Examiner forwarded the Architect's handoff parts into the room with the
  Architect's splitting tool, then said it would wait for a `[ready]` instead of writing its exam. Before Run K: the
  seats' `band send` accepts a tag only from the seat that owns it; the Examiner's proxy keeps it going until its exam
  is sealed; a turn's closing text no longer reaches the room; each seat's notes list only its own tools.
- Run K (07:10): stopped at 07:14. An untagged Reviewer message reached the room, which showed that BAND Desktop
  starts each runtime with `/usr/bin` first on PATH: the seats had been reaching the real `band` CLI directly, so the
  room linter had never run in Runs H to K. Before Run L the seat launcher puts the factory's `bin/` first; all four
  seats were checked to resolve `band` to the linter.
- Run L (07:14): no operator action in the room. At 07:17 the BAND Desktop window (a display client
  only; the seats run in the separate daemon) stopped responding with its renderer at 174% CPU, so we restarted the
  window to keep the screen recording useful. While re-opening the room, a click landed on a room card's reply box;
  it was closed with Escape, and nothing was typed or sent.
  At 07:26 we added a timeout hint to `onsen-check`'s first output line for later runs, then reverted it at 07:27
  because the band was using that tool in this run; the only check started in that minute was still waiting for the
  checker lock, so it never read the changed line. (The launcher's longer shell timeout applies only to runtimes
  started after the change, so not to this run's seats.)
  We stopped Run L at 07:43, before stage 1 was handed off. The Builder's service spun a CPU core under test, so the
  stage-1 suite never finished: OpenCode's two-minute shell limit killed the Builder's first check, the harness kept
  running orphaned and held the checker lock, and later checks (with longer timeouts) waited behind it with no result.
  Before Run M: `onsen-check` caps a run (5 minutes plus 3 per stage), interrupts the harness so it cleans up, and
  says a check that runs out of time means a slow or hung service; the launcher gives shell commands 15 minutes.
- Run M (07:47): stopped at 08:52. The handoff, a sealed 11-check exam and the room were clean, but the Builder
  reached a claimed stage (120 of 122 shipped checks) at 08:04 and then spent the next 48 minutes in a single turn
  chasing the last two without posting `[ready]`, so the graders never saw a revision. A message can't reach a seat
  mid-turn, so before Run N `onsen-check` itself ends a claimed run with the instruction to hand that commit off and
  keep improving in new revisions.
- Run N (08:52): stopped at 10:33, with stage 1 not yet accepted. The handoff note worked (the first `[ready]` came
  seven minutes in), the exam passed at 93% from 09:32 and the shipped checks at 122 of 122, and the Architect
  mediated a dispute between the Builder and the Reviewer. But the Reviewer blocked eight commits on ever finer
  edge cases, and from 10:12 it wrote its verdicts as its turn's answer instead of sending them, so they never
  reached the room and the gate could not move. Before Run O: a seat's tagged answer reaches the room when it sent
  nothing else that turn; the Reviewer is kept going until it sends its verdict; two blocked commits in a row are a
  review stall; after a second chill break one grader's pass plus the checker accepts a stage.
- Run O (10:30): stopped at 11:06, stage 1 not accepted. Seven of the Examiner's sixteen checks read the mock's call
  log without its admin header and so failed on their own mistake (the mock answers 404); the Reviewer began writing
  `stage=<commit>` in its verdicts, which Nap Guard couldn't read; and seats' closing remarks reached the room around
  the linter (a status note tagged `[ready]`). Before Run P: the linter checks each tag's first line for what the
  gate reads and refuses a repeated identical exam result; closing remarks never reach the room again, and keep-going
  asks the Builder, Examiner and Reviewer to send instead; Nap Guard reads a garbled stage as the open stage; checks
  get `onsen_exam_kit` for the mock's admin calls. (At 11:05, before stopping Run O, we added the kit to
  `onsen-exam`'s import path; no check in Run O used it.)
- Run P (11:09): stopped at 11:21. The room was clean and the exam (16 checks, using the mock kit) sealed in a
  minute, but the checker claimed stage 1 at 11:15 and the Builder, though `onsen-check` told it to hand that commit
  off, kept polishing in one turn. Before Run Q: Nap Guard's quiet-room watcher interrupts the Builder's turn and
  posts `[nudge] handoff=late` when a claimed commit goes five minutes without a `[ready]`.
- Run Q (11:22): stopped at 12:10. The Builder's background builds never finished under test, so every check ran
  into its cap (the factory reported a slow or hung service each time) and the Builder spent 45 minutes instrumenting
  its build loop without a claimed commit. No factory change; a fresh run.
- Run R (12:10): no operator action in the room. At 12:31 we restarted Nap Guard's quiet-room watcher
  (a factory process; no seat or room message involved) with one fix: its late-handoff interrupt had been sent to the
  Builder's parked default session instead of the session BAND Desktop keeps for this room, so the 12:24 interrupt
  changed nothing. The restarted watcher knows which commits it already nudged and doesn't repeat them.
  At 13:17 we restarted the watcher once more, adding a rule: stage 1 had been accepted at 13:15, but the Builder,
  mid-turn, kept editing `stage-1/` (one commit at 13:16, after the stage-2 handoff reached the room) because it could
  not see the handoff. On each newly accepted stage the watcher now interrupts the Builder and posts
  `[nudge] stage=N closed`. Like the rest of Nap Guard it acts on room events, never on our judgement.
  The Builder kept committing to `stage-1/`, and at 13:23 Nap Guard reopened stage 1 after the Reviewer blocked one of
  those late commits (a rule from Onsen's non-dark mode). At 13:25 we restarted Nap Guard (its state file kept) with a
  dark-mode rule that an accepted stage is never reopened, its late blocks carried as findings, and installed a
  pre-commit hook in the result repository that refuses commits to a stage folder Nap Guard has accepted. Stage 1
  stayed open until Nap Guard re-accepted it on its own checker run; we did not edit its state.
  At 13:38 Nap Guard re-accepted stage 1 (0d5ff17, review approved, checker 120/122) and the Architect started
  stage 2 on a branch of its own, `stage-2-work`, cut from that accepted commit; the Builder's last stage-1 commit
  (422555b) and the Examiner's published stage-1 exam (e1596e6) stay on `main`. We changed nothing in the repository.
  At 13:47 we restarted BAND Desktop's window (a viewer only: the seats run in its separate daemon, which kept
  running). Its renderer used about two of the machine's four cores in the room view and slowed the band's checks;
  we left the restarted window on its Home page, where it uses about a tenth of a core. Opening the room from its
  card first opened an empty reply box, which we closed without typing or sending anything.
  At 13:50 the room linter gained two rules, live for Run R's seats from then on because they call it on every send:
  a `[review]` or `[exam]` is refused for a commit no `[ready]` names (at 13:39 the Reviewer had blocked the
  Architect's stage-2 copy commit before anything was handed off, which counted toward the stage's review stall), and
  a `[ready]`, `[review]`, `[exam]` or `[dispute]` is refused for a stage Nap Guard has accepted (at 13:42 the Builder
  handed off a stage-1 commit after stage 1 was accepted, and both graders spent a turn on it).
  At 13:52 Nap Guard posted stage 2's first chill break, 14 minutes into the stage: the Reviewer had blocked the
  Architect's copy commit and the Builder's first handoff (c312718, which the checker didn't claim; the quiet-room
  nudge had told the Builder to post `[ready]` once a revision was committed). At 13:54 we restarted Nap Guard (state
  file kept) so that in a dark run a failing exam or a blocked review counts toward a chill only when a finished
  checker run claims the stage on that commit, and restarted the watcher with the nudge reworded to hand off once the
  checker claims the stage. Stage 2's first break stands; we didn't edit the state.
  At 14:09 we restarted the watcher again: it had nudged at 13:51, 14:00 and 14:08 while the Builder was mid-turn
  (a seven-minute check, then a patch it streamed for over a quarter of an hour), and each nudge woke the Architect
  to post a status `[plan]`. The watcher now holds its quiet nudge while any seat is mid-turn (BAND Desktop's turn
  events), interrupts a seat whose turn has shown nothing for 30 minutes, and keeps its closed-stage and handoff rules
  until the run reports. (At 14:10 we restarted it once more so that a stuck turn is measured by that seat's own
  silence, not the room's.)
  At 14:13 `onsen-check`'s cap became 5 minutes plus 4 per stage (from 3), live for Run R's checks from then on, so
  stage 3 and 4 checks, which run three and four suites, have room to finish.
  Run R stopped at 14:16, in stage 2. From 13:54 the Builder streamed one stage-2 patch for 17 minutes until the
  model's output limit cut it off ("Tool execution aborted"); prompted to carry on, it started the same patch again
  at 14:11. Before Run S: keep each edit under about 300 lines (the Builder's mandate), a keep-going prompt that says a
  cut-off edit was lost and to redo it in parts, the screenshot tool for the Builder and the Reviewer (with image
  input switched on for the model), the Examiner re-reading a check that keeps failing, every seat on `main`, the
  linter's two new rules, stalls counted only on commits the checker claims, the quiet watch's turn awareness and
  stuck rule, a check cap of 5 minutes plus 4 per stage and a 25-minute shell timeout.
- Run S (14:16): stopped at 14:47, in stage 1, with no operator action until then. The checker claimed stage 1 at
  14:33 (103 of 122 shipped checks) and again at 14:37 (110 of 122), but the Builder kept improving without posting
  `[ready]`, and Nap Guard's late-handoff rule never fired: the Architect's handoff had explained that a stage is
  accepted only when Nap Guard posts `[gate] stage=1 ACCEPTED`, and the watcher read that quotation as the stage being
  accepted. Rather than fix the watcher mid-run, we stopped the run. Before Run T: every tag the watcher reads counts
  only from a message that is that tag, not one that quotes it; and a new result repository starts with a
  `.gitignore` for Python's bytecode caches (Run S's first commit included one).
- Run T (14:47): ended itself at 14:50, with no operator action. The Builder's first turns each brought it one part of
  the four-part handoff, and instead of waiting it posted a `[dispute]` per part saying the task was incomplete; the
  Architect answered each by re-sending parts (part 4/4 five times), the Examiner re-posted its seal four times and
  disputed too, and three minutes in the Architect posted its final `[report]` ("stage 1 not accepted") and Nap
  Guard closed the run with its receipt. Before Run U: a `[dispute]` must answer a verdict on its commit; each task
  part and each stage's seal is posted once; a `[report]` is refused (by the linter, and answered by Nap Guard if it
  gets through) until the last stage is accepted or the open stage has used its time budget, which `run-dark.sh` now
  records with the run; the watch ends only on Nap Guard's receipt; and the keep-going prompts tell a seat to end its
  turn quietly while a numbered handoff is still arriving.
- Run U (14:55, room ad53a6bc, the judged run, factory commit defe350): no operator action until 20:02.
  At 20:02 we stopped Nap Guard's quiet-room watcher (a factory process; we posted nothing and changed nothing in the
  room or the repository). From 19:57 it had posted a late-handoff nudge every minute for stage-1 commits handed off
  or superseded four hours earlier, each interrupting the Builder mid-stage-4: it reads only the newest 100 room
  messages, stage 1's `[gate] ACCEPTED` had scrolled out of that window, and so it took stage 1 for open. Nap Guard's
  gate, a separate process, kept running; the run needed nothing else from the watcher to finish.
  Run U ended at 20:09 with all four stages accepted (16:25, 18:01, 19:05, 20:09) and the Architect's `[report]`;
  Nap Guard posted its receipt the same second. We then stopped the seats' runtimes and Nap Guard to package.
