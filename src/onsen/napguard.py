"""Nap Guard: the only agent allowed to wake the capybara (the human).

It is copied on verdicts and turns them into decisions:
  * stage gate   — a stage is ACCEPTED when its latest sealed exam PASSes and the
                   Reviewer APPROVES; Nap Guard then hands the next stage to the Architect.
  * one wake-up  — when every stage is accepted it wakes the human once, with any
                   questions the web couldn't settle batched in: "ship or hold?"
  * chill break  — if a stage thrashes (N failing rounds with no improvement) or
                   blows its round budget, it pulls the looping agent out of the
                   room and wakes the human with a choice. (Desktop has no hard
                   budget guardrail; this is ours.)
  * receipt      — after `ship`, it collects tallies from Scout and Examiner, posts
                   the run receipt, and asks the Examiner to reveal the exam.

Human commands (mention Nap Guard): ship | hold | resume | status

Dark mode (ONSEN_DARK=1), for a run where the dispatched task is the only human input:
  * nobody is ever woken: a blocking question is answered with "decide from the requirements
    and record the assumption", and a stalled stage gets a [chill] notice to the Architect
    instead of a pause that waits for a human `resume`
  * verdicts are computed, not taken on trust: an exam PASSes when at least 90% of its checks pass
    (from `passed=a/b`, whatever word the message uses), and before a stage is accepted Nap Guard runs the
    event's acceptance checker on the commit itself and needs it to claim the stage
  * a stalled stage escalates: the first chill break asks the Architect to re-plan; after the second, one grader's
    pass (the exam's or the Reviewer's) plus the checker's claim accepts the stage, the other's open findings carried
    forward; after the third, the checker's claim alone does
  * a verdict repeated on the same commit counts once, and review blocks count per blocked commit
  * the Architect's final `[report]` ends the run; Nap Guard answers with the receipt
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
import yaml

from band.core.simple_adapter import SimpleAdapter
from band.core.types import PlatformMessage

from .common import (
    NAMES,
    JsonState,
    agent_config_path,
    build_agent,
    clip,
    command_text,
    find_participant,
    fmt_duration,
    humans,
    load_env,
    now,
    parse_kv,
    parse_tagged,
    run_agent,
)

logger = logging.getLogger("onsen.napguard")

PCT_RE = re.compile(r"^(\d+(?:\.\d+)?)%?$")


def _pct(value: str | None) -> float:
    m = PCT_RE.match((value or "").strip())
    if not m:
        return 0.0
    v = float(m.group(1))
    return v / 100 if v > 1 else v


def _stage_no(value: str | None) -> int:
    """A message's stage number, or 0 when the field isn't one (say, a commit pasted into it)."""
    v = (value or "").strip()
    return int(v) if v.isdigit() else 0


def _open_stage(st: Any) -> int:
    """The lowest stage that isn't accepted yet, among those Nap Guard has heard of."""
    open_ = sorted(int(k) for k, v in st.data["stages"].items() if not v.get("accepted"))
    return open_[0] if open_ else 0


def _same_commit(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    n = min(len(a), len(b), 7)
    return n >= 4 and a[:n] == b[:n]


def thrash_limit() -> int:
    return int(os.environ.get("ONSEN_THRASH_LIMIT", "3"))


def review_thrash_limit() -> int:
    """Blocked reviews of different commits in a row that count as a stall (each block is real work for the Builder,
    but review rounds don't converge on their own)."""
    return int(os.environ.get("ONSEN_REVIEW_THRASH_LIMIT", "2"))


def max_rounds() -> int:
    return int(os.environ.get("ONSEN_MAX_ROUNDS_PER_STAGE", "6"))


def chill_action() -> str:
    return os.environ.get("ONSEN_CHILL_ACTION", "remove").lower()  # remove | notice


def dark() -> bool:
    """A dark-factory run: the dispatched task is the only human input, so nobody is woken."""
    return os.environ.get("ONSEN_DARK", "").lower() in ("1", "true", "yes")


def pass_mark() -> float:
    return float(os.environ.get("ONSEN_PASS_MARK", "0.9"))


PASSED_RE = re.compile(r"^(\d+)/(\d+)$")
ROOT = Path(__file__).resolve().parents[2]
API = os.environ.get("BAND_REST_URL", "https://app.band.ai").rstrip("/")


async def run_checker(n: int, commit: str) -> dict[str, Any]:
    """Run the event's acceptance checker (bin/onsen-check) on one commit of the run's repository."""
    repo = os.environ.get("ONSEN_REPO")
    if not repo:
        return {"claimed": None, "summary": "ONSEN_REPO is not set, so the checker can't run"}
    proc = await asyncio.create_subprocess_exec(str(ROOT / "bin" / "onsen-check"), repo, str(n), commit,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=float(os.environ.get("ONSEN_CHECK_TIMEOUT", "2400")))
    except TimeoutError:
        proc.kill()
        return {"claimed": None, "summary": "the checker ran out of time"}
    text = out.decode(errors="replace")
    logs = re.search(r"^--- full logs: (.+)$", text, re.M)
    claimed, counts = None, {}
    if logs:
        d = Path(logs.group(1).strip())
        try:
            claimed = json.loads((d / "report.json").read_text()).get("claimed_stage")
        except (OSError, ValueError):
            pass
        try:
            counts = json.loads((d / f"stage-{n}.counts.json").read_text())
        except (OSError, ValueError):
            pass
    failing = text.split("--- failing checks", 1)[-1].split("--- full logs", 1)[0] if "--- failing checks" in text else text[-1500:]
    summary = "\n".join(ln for ln in failing.splitlines()[1:] if ln.strip())
    stopped = re.search(r"^--- stopped:.*?(?=^---|\Z)", text, re.M | re.S)
    if stopped:  # the run hit its time cap: that is the finding
        summary = stopped.group(0).strip() + ("\n" + summary if summary else "")
    return {"claimed": int(claimed) if str(claimed or "").isdigit() else None,
            "passed": counts.get("passed"), "total": counts.get("collected"),
            "summary": clip(summary, 1500)}


async def post_as_napguard(room: str, content: str, roles: list[str]) -> None:
    """Post outside a message turn (a finished background check), through the REST API."""
    cfg = yaml.safe_load(agent_config_path().read_text()) or {}
    me = cfg["napguard"]
    mentions = [{"id": cfg[r]["agent_id"], "name": NAMES[r]} for r in roles if r in cfg]
    body = {"message": {"content": " ".join(f"@{NAMES[r]}" for r in roles) + " " + content, "mentions": mentions}}
    async with httpx.AsyncClient(base_url=API, headers={"X-API-Key": me["api_key"]}, timeout=30) as c:
        r = await c.post(f"/api/v1/agent/chats/{room}/messages", json=body)
        if r.status_code >= 300:
            logger.warning("post failed: HTTP %s %s", r.status_code, r.text[:200])


DEFAULT_STATE: dict[str, Any] = {
    "started_at": None,
    "stages_total": None,
    "seal_sha256": None,
    "stages": {},
    "questions": [],
    "disputes": [],
    "wakeups": [],
    "chill_breaks": 0,
    "human_touches": 0,
    "shipped": False,
    "held": False,
    "tallies": {},
    "awaiting_tallies": False,
    "removed": [],
    "receipt_posted": False,
    "dispatched_at": None,
    "decisions": [],
}


def _participants(tools: Any) -> list[dict[str, Any]]:
    p = getattr(tools, "participants", [])
    return list(p() if callable(p) else p)


class NapGuardAdapter(SimpleAdapter[Any]):
    def __init__(self, checker: Callable[[int, str], Awaitable[dict[str, Any]]] | None = None,
                 poster: Callable[[str, str, list[str]], Awaitable[None]] | None = None) -> None:
        super().__init__()
        self.checker = checker or run_checker
        self.poster = poster or post_as_napguard
        self._checks: dict[tuple[str, int, str], asyncio.Task] = {}
        self._room = ""

    async def settle(self) -> None:
        """Wait for background checker runs (tests)."""
        while any(not t.done() for t in self._checks.values()):
            await asyncio.gather(*self._checks.values(), return_exceptions=True)

    # ----- entry point -----
    async def on_message(self, msg: PlatformMessage, tools: Any, history: Any, participants_msg: str | None,
                         contacts_msg: str | None, *, is_session_bootstrap: bool, room_id: str) -> None:
        self._room = room_id
        text = command_text(msg.content)
        tag, rest = parse_tagged(text)
        st = JsonState("napguard", room_id, {k: (v.copy() if isinstance(v, (dict, list)) else v)
                                              for k, v in DEFAULT_STATE.items()})
        try:
            if str(msg.sender_type or "").lower() == "user":
                await self._human(msg, text, tools, st)
            elif tag == "seal":
                await self._on_seal(rest, tools, st)
            elif tag == "exam":
                await self._on_exam(rest, tools, st)
            elif tag == "review":
                await self._on_review(rest, msg, tools, st)
            elif tag == "answer":
                await self._on_answer(rest, msg, tools, st)
            elif tag == "dispute":
                kv = parse_kv(rest)
                st.data["disputes"].append({"stage": kv.get("stage"), "from": msg.sender_name, "text": clip(rest, 600),
                                            "at": now()})
                await tools.no_reply("dispute recorded; it goes to the human only if the stage stalls")
            elif tag in ("blocking-question", "question") and dark():
                await self._decide_yourself(msg, rest, tools, st)
            elif tag == "blocking-question":
                await self._wake(tools, st, f"[wake] #{len(st.data['wakeups']) + 1} reason=blocking-question "
                                 f"from={msg.sender_name}\n{clip(rest, 1200)}\nReply to me with your answer; "
                                 "I'll pass it on.", reason="blocking-question")
            elif tag == "tally":
                await self._on_tally(rest, tools, st)
            elif tag == "appeal":
                await tools.no_reply("appeal verdict noted")
            elif tag == "report" and dark():
                await self._on_report(rest, msg, tools, st)
            else:
                await tools.no_reply("not addressed to Nap Guard's protocol")
        finally:
            st.save()

    # ----- helpers -----
    def _stage(self, st: JsonState, n: int) -> dict[str, Any]:
        stages = st.data["stages"]
        s = stages.setdefault(str(n), {"exams": [], "review": None, "accepted": False, "fails_in_row": 0,
                                       "best": 0.0, "by": None, "review_note": None})
        s.setdefault("chills", 0)
        s.setdefault("checks", [])
        s.setdefault("seen", [])           # (kind, commit, verdict) already counted
        s.setdefault("review_blocks", 0)   # distinct commits blocked in a row, reset by an approval
        return s

    @staticmethod
    def _repeat(s: dict[str, Any], kind: str, commit: str | None, verdict: str) -> bool:
        """Whether this grader already gave this commit this verdict (a repeat counts once)."""
        key = f"{kind}:{(commit or '?')[:7]}:{verdict}"
        if key in s["seen"]:
            return True
        s["seen"].append(key)
        return False

    def _human_mention(self, tools: Any) -> list[str]:
        wanted = os.environ.get("ONSEN_HUMAN")
        people = humans(_participants(tools))
        if wanted:
            hit = find_participant(people, wanted)
            if hit:
                return [hit["id"]]
        return [people[0]["id"]] if people else []

    async def _wake(self, tools: Any, st: JsonState, content: str, *, reason: str) -> None:
        mention = self._human_mention(tools)
        st.data["wakeups"].append({"reason": reason, "at": now()})
        if not mention:
            logger.warning("No human in the room to wake: %s", reason)
            await tools.send_event(content=f"Wanted to wake the human ({reason}) but nobody is in the room.",
                                   message_type="error")
            await tools.no_reply("no human present")
            return
        await tools.send_message(content, mentions=mention)

    async def _say(self, tools: Any, content: str, names: list[str]) -> None:
        try:
            await tools.send_message(content, mentions=names)
        except ValueError:
            await tools.send_message(content, mentions=[n for n in names if n != NAMES["architect"]] or names[:1])

    # ----- protocol handlers -----
    async def _on_seal(self, rest: str, tools: Any, st: JsonState) -> None:
        kv = parse_kv(rest)
        st.data["stages_total"] = int(kv.get("stages") or 0) or None
        st.data["seal_sha256"] = kv.get("sha256")
        if kv.get("stage"):
            st.data.setdefault("seals", {})[str(kv["stage"])] = kv.get("sha256")
        st.data["started_at"] = st.data["started_at"] or now()
        await tools.no_reply("seal recorded")

    async def _on_exam(self, rest: str, tools: Any, st: JsonState) -> None:
        kv = parse_kv(rest)
        n = _stage_no(kv.get("stage")) or _open_stage(st)
        if not n:
            await tools.no_reply("exam without stage")
            return
        s = self._stage(st, n)
        said = (kv.get("verdict") or "FAIL").upper()
        m = PASSED_RE.match((kv.get("passed") or "").strip())
        sat = int(m.group(1)) / int(m.group(2)) if m and int(m.group(2)) else _pct(kv.get("satisfaction"))
        # The verdict is the numbers', not the message's word. In a dark run an exam without counts can't pass.
        if dark():
            verdict = "PASS" if m and int(m.group(2)) and sat >= pass_mark() - 1e-9 else "FAIL"
        else:
            verdict = said
        s["exams"].append({"satisfaction": sat, "verdict": verdict, "said": said, "at": now(),
                           "commit": kv.get("commit")})
        s["last_commit"] = kv.get("commit") or s.get("last_commit")
        s["by"] = (kv.get("by") or s.get("by") or NAMES["builder"]).replace("_", " ")
        st.data["started_at"] = st.data["started_at"] or now()
        repeat = dark() and self._repeat(s, "exam", kv.get("commit"), verdict)
        if repeat or (dark() and s["chills"] >= 2):
            pass  # a repeated verdict counts once; after two chill breaks the exam is advisory
        elif verdict == "PASS":
            s["fails_in_row"] = 0
        elif sat > s["best"] + 1e-9:
            s["fails_in_row"] = 1  # still failing, but improving: not thrash yet
        else:
            s["fails_in_row"] += 1
        s["best"] = max(s["best"], sat)
        counting = not repeat and not (dark() and s["chills"] >= 2)
        exam_rounds = len({e.get("commit") for e in s["exams"][s.get("rounds_at_chill", 0):]})
        if counting and verdict == "FAIL" and (s["fails_in_row"] >= thrash_limit() or exam_rounds >= max_rounds()):
            await self._chill(tools, st, n, s)
            return
        await self._maybe_gate(tools, st, n, s)

    async def _on_review(self, rest: str, msg: PlatformMessage, tools: Any, st: JsonState) -> None:
        kv = parse_kv(rest)
        n = _stage_no(kv.get("stage")) or _open_stage(st)
        if not n:
            await tools.no_reply("review without stage")
            return
        s = self._stage(st, n)
        approved = "APPROVED" in rest.upper() and "BLOCKED" not in rest.upper()
        s["review"] = "APPROVED" if approved else "BLOCKED"
        s["review_commit"] = kv.get("commit")
        s["last_commit"] = kv.get("commit") or s.get("last_commit")
        s["review_note"] = clip(rest, 300)
        repeat = dark() and self._repeat(s, "review", kv.get("commit"), s["review"])
        if approved:
            s["review_blocks"] = 0
        elif not repeat:
            if dark():
                s["review_blocks"] += 1  # one count per blocked commit, however often it is re-reviewed
                if s["review_blocks"] >= review_thrash_limit():
                    await self._chill(tools, st, n, s, reason="review-thrash")
                    return
            else:
                s["fails_in_row"] += 1
                if s["fails_in_row"] >= thrash_limit():
                    await self._chill(tools, st, n, s)
                    return
        if not approved:
            if s["accepted"] and dark():
                # In a dark run an accepted stage stays accepted: the next stage's requirements are already open and its
                # folder can't change again (the event's rule). A late block is a finding carried forward, not a reopen.
                s.setdefault("late_findings", []).append(clip(rest, 300))
                await tools.no_reply("finding on an accepted stage, carried forward")
                return
            if s["accepted"]:
                # A block after acceptance reopens the stage: approval is about the code as it is now.
                s["accepted"] = False
                await self._say(
                    tools,
                    f"[gate] stage={n} REOPENED reason=review-blocked commit={kv.get('commit') or '?'}\n"
                    f"The Reviewer blocked stage {n} after it was accepted. Builder: fix it and post `[ready]` again. "
                    f"Architect: stage {n} isn't done.",
                    [NAMES["architect"], NAMES["builder"]],
                )
                return
        await self._maybe_gate(tools, st, n, s)

    async def _on_answer(self, rest: str, msg: PlatformMessage, tools: Any, st: JsonState) -> None:
        kv = parse_kv(rest)
        empty = kv.get("claims") == "0" and kv.get("sources") == "0"  # a failed lookup, not an open question
        if kv.get("confidence", "").lower() in ("low", "none") and not empty:
            st.data["questions"].append({"for": kv.get("for"), "text": clip(rest, 600), "at": now()})
        await tools.no_reply("question batched for the single wake-up")

    async def _maybe_gate(self, tools: Any, st: JsonState, n: int, s: dict[str, Any]) -> None:
        last = s["exams"][-1] if s["exams"] else {}
        last_exam = last.get("verdict")
        advisory = dark() and s["chills"] >= 2   # one grader's pass is enough, the other's findings carry forward
        spent = dark() and s["chills"] >= 3      # review effort spent: the checker alone gates the latest commit
        exam_pass, review_pass = last_exam == "PASS", s["review"] == "APPROVED"
        exam_commit, review_commit = last.get("commit"), s.get("review_commit")
        same_code = not exam_commit or not review_commit or _same_commit(exam_commit, review_commit)
        if s["accepted"]:
            await tools.no_reply("already accepted")
            return
        if advisory and not spent and (exam_pass or review_pass):
            commit = exam_commit if exam_pass else review_commit
            key = (self._room, n, (commit or "HEAD")[:7])
            if commit and key not in self._checks:
                self._checks[key] = asyncio.create_task(self._check_and_gate(
                    self._room, n, commit, True, carried=not (exam_pass and review_pass and same_code)))
            await tools.no_reply("one grader passed after two chill breaks: running the checker")
            return
        exam_ok = exam_pass or advisory
        if not exam_ok or (not review_pass and not spent):
            await tools.no_reply("gate not ready")
            return
        if spent and s.get("last_commit"):
            key = (self._room, n, s["last_commit"][:7])
            if key not in self._checks:
                self._checks[key] = asyncio.create_task(
                    self._check_and_gate(self._room, n, s["last_commit"], True,
                                         carried=s["review"] != "APPROVED"))
            await tools.no_reply("running the acceptance checker on the latest commit")
            return
        if not advisory and not same_code:
            await self._say(
                tools,
                f"[gate] stage={n} WAITING exam passed commit={exam_commit} but the approval was for "
                f"commit={review_commit}. Please review commit {exam_commit}.",
                [NAMES["reviewer"]],
            )
            return
        if dark():
            # Nobody's word is enough: the event's checker has to claim the stage on this exact commit.
            commit = (review_commit if advisory else exam_commit) or review_commit or exam_commit or "HEAD"
            key = (self._room, n, commit[:7])
            if key not in self._checks:
                self._checks[key] = asyncio.create_task(self._check_and_gate(self._room, n, commit, advisory))
            await tools.no_reply(f"running the acceptance checker on {commit}")
            return
        s["accepted"] = True
        curve = "→".join(f"{e['satisfaction']:.0%}" for e in s["exams"])
        total = st.data["stages_total"]
        accepted = sorted(int(k) for k, v in st.data["stages"].items() if v["accepted"])
        if total and len(accepted) >= total:
            await self._wake_for_ship(tools, st)
            return
        await self._say(
            tools,
            f"[gate] stage={n} ACCEPTED exam={curve} review=approved accepted={','.join(map(str, accepted))}"
            f"{f'/{total}' if total else ''}\nStage {n} is in. Hand the next stage to the builders.",
            [NAMES["architect"]],
        )

    async def _check_and_gate(self, room: str, n: int, commit: str, advisory: bool, carried: bool = False) -> None:
        """Background: run the checker on `commit`, then accept stage n or say what the checker found."""
        try:
            res = await self.checker(n, commit)
        except Exception as exc:  # noqa: BLE001
            res = {"claimed": None, "summary": f"the checker could not run: {clip(str(exc), 200)}"}
        st = JsonState("napguard", room, {k: (v.copy() if isinstance(v, (dict, list)) else v)
                                          for k, v in DEFAULT_STATE.items()})
        s = self._stage(st, n)
        counts = f"{res.get('passed')}/{res.get('total')}" if res.get("total") else "?"
        s["checks"].append({"commit": commit, "claimed": res.get("claimed"), "counts": counts, "at": now()})
        if s["accepted"]:
            st.save()
            return
        if res.get("claimed") == n:
            s["accepted"] = True
            s["accepted_commit"] = commit
            curve = "→".join(f"{e['satisfaction']:.0%}" for e in s["exams"]) or "none"
            accepted = sorted(int(k) for k, v in st.data["stages"].items() if v["accepted"])
            st.save()
            how = ("after its chill breaks one grader's pass is enough, so the other grader's open findings are "
                   "carried forward" if carried else
                   "its exam passed and the Reviewer approved the same commit")
            if carried:
                s["carried"] = clip(s.get("review_note") or "", 400)
                st.save()
            await self.poster(room,
                f"[gate] stage={n} ACCEPTED commit={commit} exam={curve} "
                f"review={'approved' if s['review'] == 'APPROVED' else 'carried'} checker=claimed:{n} "
                f"({counts} shipped checks) accepted={','.join(map(str, accepted))}\n"
                f"Stage {n} is in: {how}, and I ran the acceptance checker on that commit myself: it claims stage {n}. "
                f"Architect: carry it forward. Examiner: publish stage {n}'s exam.",
                ["architect", "examiner"])
            return
        st.save()
        await self.poster(room,
            f"[gate] stage={n} WAITING commit={commit} checker=claimed:{res.get('claimed') or 'none'} ({counts})\n"
            + (f"I ran the acceptance checker on {commit} after the stage's third chill break, " if carried else
               f"The exam and the review agree on {commit}, ")
            + f"but the checker doesn't claim stage {n} there, "
            f"so the stage stays open. What it reported:\n{res.get('summary') or 'no detail'}\n"
            "Builder: fix it and post `[ready]` with the new commit.",
            ["builder", "architect"])

    async def _wake_for_ship(self, tools: Any, st: JsonState) -> None:
        lines = [
            f"[wake] #{len(st.data['wakeups']) + 1} reason=ready-to-ship",
            "🛁 Sorry to wake you. Every stage passed the sealed exam and was approved by the Reviewer:",
        ]
        for k in sorted(st.data["stages"], key=int):
            v = st.data["stages"][k]
            lines.append(f"• Stage {k}: " + "→".join(f"{e['satisfaction']:.0%}" for e in v["exams"]) + " · review approved")
        qs = st.data["questions"]
        if qs:
            lines.append(f"While you slept, {len(qs)} question(s) got only a low-confidence answer from the web. "
                         "The builders went with the most reasonable assumption:")
            lines.extend(f"  {i + 1}. {clip(q['text'], 240)}" for i, q in enumerate(qs[:5]))
        lines.append("Reply to me with `ship` to ship, or `hold` to stop here.")
        await self._wake(tools, st, "\n".join(lines), reason="ready-to-ship")

    async def _chill(self, tools: Any, st: JsonState, n: int, s: dict[str, Any], reason: str | None = None) -> None:
        st.data["chill_breaks"] += 1
        if dark():
            s["chills"] += 1
            curve = "→".join(f"{e['satisfaction']:.0%}" for e in s["exams"]) or "no exams"
            reason = reason or ("thrash" if s["fails_in_row"] >= thrash_limit() else "round-budget")
            s["fails_in_row"] = 0  # one notice per stall, not one per round
            s["review_blocks"] = 0
            s["rounds_at_chill"] = len(s["exams"])
            if s["chills"] == 1:
                what = ("Architect: re-plan this stage. Hand the Builder one failing behaviour at a time, with the "
                        "requirement it comes from.")
            elif s["chills"] == 2:
                what = (f"This is stage {n}'s second chill break, so one grader is enough from now on: the stage is "
                        "accepted once the exam passes or the Reviewer approves a commit and the acceptance checker "
                        "claims the stage on it; the other grader's open findings carry forward. Builder: post "
                        "`[ready]` for your best commit. Architect: carry the open findings into the next stage's plan "
                        "and your report.")
            else:
                what = (f"This is stage {n}'s third chill break, so its review effort is spent: I'm running the "
                        "acceptance checker on the latest graded commit, and if it claims the stage, the stage is "
                        "accepted with the open review findings carried forward. Architect: carry them into the next "
                        "stage's plan and into your report.")
            await self._say(
                tools,
                f"[chill] stage={n} break={s['chills']} reason={reason} rounds={len(s['exams'])} exam={curve}\n"
                f"🧘 Stage {n} has stopped improving. Last review: {clip(s.get('review_note') or 'none', 200)}\n"
                f"{what} Nobody wakes the human in a dark run.",
                [NAMES["architect"], NAMES["builder"]],
            )
            commit = None
            last = s["exams"][-1] if s["exams"] else {}
            if s["chills"] == 2 and not s["accepted"] and (last.get("verdict") == "PASS" or s["review"] == "APPROVED"):
                commit = last.get("commit") if last.get("verdict") == "PASS" else s.get("review_commit")
            elif s["chills"] >= 3 and not s["accepted"]:
                commit = s.get("review_commit") or (s["exams"][-1].get("commit") if s["exams"] else None)
            if commit:
                key = (self._room, n, commit[:7])
                both = last.get("verdict") == "PASS" and s["review"] == "APPROVED"
                if key not in self._checks:
                    self._checks[key] = asyncio.create_task(
                        self._check_and_gate(self._room, n, commit, True, carried=s["chills"] >= 3 or not both))
            return
        culprit = s.get("by") or NAMES["builder"]
        curve = "→".join(f"{e['satisfaction']:.0%}" for e in s["exams"]) or "no exams"
        action = "I left everyone in the room."
        if chill_action() == "remove":
            target = find_participant(_participants(tools), culprit)
            if target:
                try:
                    await tools.remove_participant(target["id"])
                    st.data["removed"].append(target.get("name") or culprit)
                    action = f"I took {target.get('name') or culprit} out of the room so it stops spending tokens."
                except Exception as exc:  # noqa: BLE001
                    action = f"I couldn't take {culprit} out of the room ({clip(str(exc), 80)})."
        reason = "thrash" if s["fails_in_row"] >= thrash_limit() else "round-budget"
        last_review = s.get("review_note") or "none"
        disputes = [d for d in st.data.get("disputes", []) if str(d.get("stage")) == str(n)]
        dispute_note = ("\nThe builders dispute the exam on this stage (they believe the check contradicts the spec):\n"
                        + "\n".join(f"  • {clip(d['text'], 300)}" for d in disputes[-3:])) if disputes else ""
        await self._wake(
            tools, st,
            f"[chill] #{len(st.data['wakeups']) + 1} stage={n} reason={reason}\n"
            f"🧘 Chill break. Stage {n} has gone {len(s['exams'])} exam round(s) ({curve}) and isn't getting better. "
            f"Last review: {clip(last_review, 200)}{dispute_note}\n{action}\n"
            "Reply `resume` to put it back and keep going, or `hold` to stop the run.",
            reason=f"chill-{reason}",
        )

    async def _decide_yourself(self, msg: PlatformMessage, rest: str, tools: Any, st: JsonState) -> None:
        st.data["decisions"].append({"from": msg.sender_name, "text": clip(rest, 400), "at": now()})
        await tools.send_message(
            "[decide] 😴 The capybara is asleep and stays asleep: in a dark run nobody asks the human anything. "
            "Decide from the requirements you were given, choose the most reasonable reading, state the assumption "
            "in your next handoff, and keep going.",
            mentions=[msg.sender_id],
        )

    async def _on_report(self, rest: str, msg: PlatformMessage, tools: Any, st: JsonState) -> None:
        d = st.data
        if d["receipt_posted"]:
            await tools.no_reply("receipt already posted")
            return
        lines = []
        for k in sorted(d["stages"], key=int):
            v = d["stages"][k]
            curve = "→".join(f"{e['satisfaction']:.0%}" for e in v["exams"]) or "no exam"
            claim = next((c for c in reversed(v.get("checks", [])) if c.get("claimed") == int(k)), None)
            checker = f", checker claims it at {claim['commit']} ({claim['counts']})" if claim else ""
            lines.append(f"{k} {'✔' if v['accepted'] else '✘'} exam {curve} ({len(v['exams'])} rounds{checker})")
        elapsed = fmt_duration(now() - d["started_at"]) if d["started_at"] else "n/a"
        receipt = "\n".join([
            "[receipt] 🛁 Onsen dark run complete",
            "• Human input: 1 (the dispatched task) · wake-ups: 0 · questions sent to the human: 0",
            "• Stages: " + (" · ".join(lines) or "none accepted"),
            f"• Chill breaks: {d['chill_breaks']} · questions the band decided for itself: {len(d['decisions'])}"
            f" · disputes: {len(d['disputes'])}",
            f"• Time from the first exam seal to this report: {elapsed}",
            "The capybara slept through all of it. 🍊",
        ])
        d["receipt_posted"] = True
        await tools.send_message(receipt, mentions=[msg.sender_id])

    async def _on_tally(self, rest: str, tools: Any, st: JsonState) -> None:
        kv = parse_kv(rest)
        agent = (kv.get("agent") or "").lower()
        if agent:
            st.data["tallies"][agent] = kv
        if st.data["awaiting_tallies"] and {"scout", "examiner"} <= set(st.data["tallies"]):
            st.data["awaiting_tallies"] = False
            await self._post_receipt(tools, st)
            return
        await tools.no_reply("tally recorded")

    async def _post_receipt(self, tools: Any, st: JsonState) -> None:
        d = st.data
        scout = d["tallies"].get("scout", {})
        exam = d["tallies"].get("examiner", {})
        elapsed = fmt_duration(now() - d["started_at"]) if d["started_at"] else "n/a"
        stage_lines = []
        for k in sorted(d["stages"], key=int):
            v = d["stages"][k]
            curve = "→".join(f"{e['satisfaction']:.0%}" for e in v["exams"])
            stage_lines.append(f"{k} {'✔' if v['accepted'] else '✘'} {curve} ({len(v['exams'])} rounds)")
        wakeups = len(d["wakeups"])
        receipt = "\n".join([
            "[receipt] 🛁 Onsen run complete",
            f"• Human touches: {d['human_touches'] + 1} (the spec + {d['human_touches']} repl"
            f"{'y' if d['human_touches'] == 1 else 'ies'} to Nap Guard) · wake-ups: {wakeups} · chill breaks: {d['chill_breaks']}",
            "• Stages: " + (" · ".join(stage_lines) or "none"),
            f"• Questions the web answered: {scout.get('answered', '?')} · escalated: {scout.get('escalated', '?')} "
            f"(batched into the wake-up)",
            f"• Docs fetched: {scout.get('docs', '?')} · datasets built: {scout.get('data', '?')} · exam rounds: {exam.get('rounds', '?')}"
            f" · exam checks voided on appeal: {exam.get('voided', '0')}",
            f"• Time from seal to ship: {elapsed}",
            f"• Sealed exam sha256={(d.get('seal_sha256') or '?')[:16]}… — asking the Examiner to reveal it now.",
            f"The capybara was woken {wakeups} time{'s' if wakeups != 1 else ''}. 🍊",
        ])
        d["receipt_posted"] = True
        human = self._human_mention(tools)
        await tools.send_message(receipt, mentions=human or [NAMES["examiner"]])
        try:
            await tools.send_notice("reveal — the human shipped. Please publish the sealed exam.",
                                    mentions=[NAMES["examiner"]])
        except ValueError:
            logger.warning("Examiner not in room; cannot request reveal")

    # ----- the human -----
    async def _human(self, msg: PlatformMessage, text: str, tools: Any, st: JsonState) -> None:
        st.data["human_touches"] += 1
        word = text.strip().split()[0].lower().strip("`.!") if text.strip() else "status"
        reply = [msg.sender_id]
        if word == "ship":
            st.data["shipped"] = True
            st.data["awaiting_tallies"] = True
            st.data["tallies"] = {}
            try:
                await tools.send_message(
                    "[tally-request] The human shipped 🚀. Scout and Examiner, send me your tallies for the receipt.",
                    mentions=[NAMES["scout"], NAMES["examiner"]],
                )
            except ValueError:
                await tools.send_message("Shipped. (Scout or Examiner isn't in this room, so there's no full receipt.)",
                                         mentions=reply)
        elif word in ("hold", "stop"):
            st.data["held"] = True
            await tools.send_message("Holding. Nothing ships. Mention me with `resume` when you want to continue.",
                                     mentions=reply)
        elif word == "resume":
            st.data["held"] = False
            restored = []
            for name in list(st.data["removed"]):
                try:
                    await tools.add_participant(name)
                    restored.append(name)
                    st.data["removed"].remove(name)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not re-add %s: %s", name, exc)
            for s in st.data["stages"].values():
                s["fails_in_row"] = 0
            note = f" I put {', '.join(restored)} back in the room." if restored else ""
            await self._say(tools, f"[gate] resume=true{note} Picking up where we left off.",
                            [NAMES["architect"], msg.sender_id])
        else:
            await tools.send_message(self._status(st), mentions=reply)

    def _status(self, st: JsonState) -> str:
        d = st.data
        parts = [f"[status] wake-ups={len(d['wakeups'])} chill_breaks={d['chill_breaks']} "
                 f"questions_batched={len(d['questions'])} shipped={d['shipped']}"]
        for k in sorted(d["stages"], key=int):
            v = d["stages"][k]
            curve = "→".join(f"{e['satisfaction']:.0%}" for e in v["exams"]) or "no exam yet"
            parts.append(f"• Stage {k}: exam {curve} · review {v['review'] or 'pending'} · "
                         f"{'ACCEPTED' if v['accepted'] else 'open'}")
        parts.append("Commands: `ship` · `hold` · `resume` · `status`")
        return "\n".join(parts)


def main() -> None:
    load_env()
    run_agent(build_agent("napguard", NapGuardAdapter()))


if __name__ == "__main__":
    main()
