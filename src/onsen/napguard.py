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
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from band.core.simple_adapter import SimpleAdapter
from band.core.types import PlatformMessage

from .common import (
    NAMES,
    JsonState,
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


def _same_commit(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    n = min(len(a), len(b), 7)
    return n >= 4 and a[:n] == b[:n]


def thrash_limit() -> int:
    return int(os.environ.get("ONSEN_THRASH_LIMIT", "3"))


def max_rounds() -> int:
    return int(os.environ.get("ONSEN_MAX_ROUNDS_PER_STAGE", "6"))


def chill_action() -> str:
    return os.environ.get("ONSEN_CHILL_ACTION", "remove").lower()  # remove | notice


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
}


def _participants(tools: Any) -> list[dict[str, Any]]:
    p = getattr(tools, "participants", [])
    return list(p() if callable(p) else p)


class NapGuardAdapter(SimpleAdapter[Any]):
    def __init__(self) -> None:
        super().__init__()

    # ----- entry point -----
    async def on_message(self, msg: PlatformMessage, tools: Any, history: Any, participants_msg: str | None,
                         contacts_msg: str | None, *, is_session_bootstrap: bool, room_id: str) -> None:
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
            elif tag == "blocking-question":
                await self._wake(tools, st, f"[wake] #{len(st.data['wakeups']) + 1} reason=blocking-question "
                                 f"from={msg.sender_name}\n{clip(rest, 1200)}\nReply to me with your answer; "
                                 "I'll pass it on.", reason="blocking-question")
            elif tag == "tally":
                await self._on_tally(rest, tools, st)
            elif tag == "appeal":
                await tools.no_reply("appeal verdict noted")
            else:
                await tools.no_reply("not addressed to Nap Guard's protocol")
        finally:
            st.save()

    # ----- helpers -----
    def _stage(self, st: JsonState, n: int) -> dict[str, Any]:
        stages = st.data["stages"]
        return stages.setdefault(str(n), {"exams": [], "review": None, "accepted": False, "fails_in_row": 0,
                                          "best": 0.0, "by": None, "review_note": None})

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
        st.data["started_at"] = st.data["started_at"] or now()
        await tools.no_reply("seal recorded")

    async def _on_exam(self, rest: str, tools: Any, st: JsonState) -> None:
        kv = parse_kv(rest)
        n = int(kv.get("stage") or 0)
        if not n:
            await tools.no_reply("exam without stage")
            return
        s = self._stage(st, n)
        sat = _pct(kv.get("satisfaction"))
        verdict = (kv.get("verdict") or "FAIL").upper()
        s["exams"].append({"satisfaction": sat, "verdict": verdict, "at": now(), "commit": kv.get("commit")})
        s["by"] = (kv.get("by") or s.get("by") or NAMES["builder"]).replace("_", " ")
        st.data["started_at"] = st.data["started_at"] or now()
        if verdict == "PASS":
            s["fails_in_row"] = 0
        elif sat > s["best"] + 1e-9:
            s["fails_in_row"] = 1  # still failing, but improving: not thrash yet
        else:
            s["fails_in_row"] += 1
        s["best"] = max(s["best"], sat)
        if verdict == "FAIL" and (s["fails_in_row"] >= thrash_limit() or len(s["exams"]) >= max_rounds()):
            await self._chill(tools, st, n, s)
            return
        await self._maybe_gate(tools, st, n, s)

    async def _on_review(self, rest: str, msg: PlatformMessage, tools: Any, st: JsonState) -> None:
        kv = parse_kv(rest)
        n = int(kv.get("stage") or 0)
        if not n:
            await tools.no_reply("review without stage")
            return
        s = self._stage(st, n)
        approved = "APPROVED" in rest.upper() and "BLOCKED" not in rest.upper()
        s["review"] = "APPROVED" if approved else "BLOCKED"
        s["review_commit"] = kv.get("commit")
        s["review_note"] = clip(rest, 300)
        if not approved:
            s["fails_in_row"] += 1
            if s["fails_in_row"] >= thrash_limit():
                await self._chill(tools, st, n, s)
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
        exam_commit, review_commit = last.get("commit"), s.get("review_commit")
        same_code = not exam_commit or not review_commit or _same_commit(exam_commit, review_commit)
        if last_exam == "PASS" and s["review"] == "APPROVED" and not same_code and not s["accepted"]:
            await self._say(
                tools,
                f"[gate] stage={n} WAITING exam passed commit={exam_commit} but the approval was for "
                f"commit={review_commit}. Please review commit {exam_commit}.",
                [NAMES["reviewer"]],
            )
            return
        if last_exam == "PASS" and s["review"] == "APPROVED" and same_code and not s["accepted"]:
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
            return
        await tools.no_reply("gate not ready")

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

    async def _chill(self, tools: Any, st: JsonState, n: int, s: dict[str, Any]) -> None:
        st.data["chill_breaks"] += 1
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
