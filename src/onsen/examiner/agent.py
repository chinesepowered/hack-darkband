"""Examiner: holds the sealed exam and grades each stage. Never edits code.

Commands (first word after the @mention):
  seal [spec=capyfinder] [per_stage=8]   write the hidden exam, post only its SHA-256
  exam stage=N url=http://localhost:8000 run stage N's hidden scenarios against the app
  [ready] stage=N url=...                same as exam (what builders post when a stage is done)
  reveal                                  publish the exam after shipping (Nap Guard or a human only)
  tally | status | help

Why the builders can't see the exam: BAND delivers a message only to the agents
it mentions, agents never receive each other's events, and the scenarios live on
the Examiner's own disk (run it in its own container: see docker/).
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

from band.core.simple_adapter import SimpleAdapter
from band.core.types import PlatformMessage

from ..common import (
    NAMES,
    build_agent,
    clip,
    command_text,
    load_env,
    parse_kv,
    parse_tagged,
    run_agent,
    state_dir,
)
from .models import SealedExam
from .runner import run_scenarios, satisfaction
from .seal import (
    RoomRuns,
    ScenarioWriter,
    append_history,
    exam_dir,
    llm_enabled,
    load_fixture_exam,
    load_history,
    load_sealed,
    new_run_id,
    parse_stages,
    save_sealed,
    sha256_hex,
    spec_path,
)

logger = logging.getLogger("onsen.examiner")

HELP = (
    "Examiner commands:\n"
    "• `seal spec=capyfinder` → I write the hidden exam and post only its SHA-256\n"
    "• `[ready] stage=1 url=http://localhost:8000` → I run stage 1's hidden scenarios and report what a user would notice\n"
    "• `reveal` → after shipping, I publish the exam so anyone can check the hash (Nap Guard or a human only)\n"
    "• `tally` / `status`"
)


def threshold() -> float:
    return float(os.environ.get("ONSEN_PASS_THRESHOLD", "0.9"))


def split_command(text: str) -> tuple[str, str]:
    tag, rest = parse_tagged(text)
    if tag in ("ready", "exam"):
        return "exam", rest
    if tag == "tally-request":
        return "tally", rest
    if tag in ("seal", "reveal", "status", "tally", "help"):
        return tag, rest
    word, _, remainder = text.strip().partition(" ")
    word = word.lower().rstrip(":")
    if word in ("seal", "exam", "reveal", "tally", "status", "help"):
        return word, remainder.strip()
    return "help", text


class ExaminerAdapter(SimpleAdapter[Any]):
    def __init__(self, writer: ScenarioWriter | None = None):
        super().__init__()
        self._writer = writer
        self.rooms = RoomRuns()

    @property
    def writer(self) -> ScenarioWriter | None:
        if self._writer is None and llm_enabled():
            self._writer = ScenarioWriter()
        return self._writer

    async def on_message(self, msg: PlatformMessage, tools: Any, history: Any, participants_msg: str | None,
                         contacts_msg: str | None, *, is_session_bootstrap: bool, room_id: str) -> None:
        text = command_text(msg.content)
        cmd, arg = split_command(text)
        reply_to = [msg.sender_id]
        try:
            if cmd == "seal":
                await self._seal(arg, tools, reply_to, room_id)
            elif cmd == "exam":
                await self._exam(arg, msg, tools, reply_to, room_id)
            elif cmd == "reveal":
                await self._reveal(msg, tools, reply_to, room_id)
            elif cmd in ("tally", "status"):
                await tools.send_message(self._tally(room_id), mentions=reply_to)
            else:
                await tools.send_message(HELP, mentions=reply_to)
        except Exception as exc:  # noqa: BLE001 - report, never go silent
            logger.exception("Examiner failed on %r", text)
            await tools.send_message(f"[exam-error] {clip(str(exc), 400)}", mentions=reply_to)

    async def _mention_with_napguard(self, tools: Any, content: str, reply_to: list[str]) -> None:
        try:
            await tools.send_message(content, mentions=[*reply_to, NAMES["napguard"]])
        except ValueError:
            await tools.send_message(content, mentions=reply_to)

    async def _seal(self, arg: str, tools: Any, reply_to: list[str], room_id: str) -> None:
        kv = parse_kv(arg)
        spec_name = kv.get("spec") or os.environ.get("ONSEN_SPEC", "capyfinder")
        path = spec_path(spec_name)
        spec_text = path.read_text()
        stages = parse_stages(spec_text)
        if not stages:
            raise ValueError(f"{path.name} has no '## Stage N' sections to examine")
        per_stage = int(kv.get("per_stage") or os.environ.get("ONSEN_SCENARIOS_PER_STAGE", "8"))
        dropped_note = ""
        if self.writer is not None:
            self.writer.dropped = []
            await tools.send_event(content=f"Writing hidden scenarios for {len(stages)} stages in parallel…",
                                   message_type="thought")
            import asyncio

            facts = ""
            data_arg = kv.get("data")
            if data_arg:
                data_path = Path(data_arg)
                if not data_path.is_absolute():
                    data_path = Path(os.environ.get("ONSEN_WORKSPACE", ".")) / data_arg
                if data_path.exists():
                    from .seal import data_profile

                    facts = data_profile(data_path)
            stage_exams = list(await asyncio.gather(*(self.writer.write_stage(spec_text, n, per_stage, facts)
                                                      for n, _section in stages)))
            from datetime import UTC, datetime
            import secrets

            exam = SealedExam(spec_name=path.stem, spec_sha256=sha256_hex(spec_text.encode()),
                              created_at=datetime.now(UTC).isoformat(), nonce=secrets.token_hex(16),
                              author=self.writer.model, stages=stage_exams)
            if self.writer.dropped:
                dropped_note = (f" ({len(self.writer.dropped)} model-written scenarios were dropped by the contract lint "
                                f"and proofreading before sealing)")
        elif os.environ.get("ONSEN_EXAM_FILE"):
            exam = load_fixture_exam(os.environ["ONSEN_EXAM_FILE"], path.stem, spec_text)
        else:
            raise RuntimeError("I need an LLM key (WANDB_API_KEY or ONSEN_LLM_API_KEY) to write the exam, "
                               "or ONSEN_EXAM_FILE for a fixture exam")
        run_id = new_run_id()
        digest = save_sealed(exam, run_id)
        (exam_dir(run_id) / "sha256.txt").write_text(digest + "\n")
        self.rooms.set(room_id, run_id)
        await self._mention_with_napguard(
            tools,
            f"[seal] run={run_id} spec={exam.spec_name} stages={len(exam.stages)} scenarios={exam.scenario_count} "
            f"sha256={digest}\nThe exam is sealed{dropped_note}. Builders won't see it: it's on my disk, and BAND only delivers "
            f"messages to the agents they mention. When a stage is ready, post `[ready] stage=N url=…` to me. "
            f"I'll publish the exam after the human ships, and its hash will match this one.",
            reply_to,
        )

    def _load_run(self, room_id: str) -> tuple[str, SealedExam, str]:
        run_id = self.rooms.get(room_id)
        if not run_id:
            raise RuntimeError("No exam is sealed for this room yet. Ask me to `seal spec=<name>` first.")
        exam, digest = load_sealed(run_id)
        recorded = (exam_dir(run_id) / "sha256.txt").read_text().strip()
        if digest != recorded:
            raise RuntimeError(f"The sealed exam changed on disk (expected {recorded[:12]}…, found {digest[:12]}…). Refusing to grade.")
        return run_id, exam, digest

    async def _exam(self, arg: str, msg: PlatformMessage, tools: Any, reply_to: list[str], room_id: str) -> None:
        kv = parse_kv(arg)
        stage = int(kv.get("stage") or 0)
        url = kv.get("url") or os.environ.get("ONSEN_APP_URL")
        if not stage or not url:
            raise ValueError("Tell me which stage and where it runs: `[ready] stage=1 url=http://localhost:8000`")
        run_id, exam, _ = self._load_run(room_id)
        stage_exam = exam.stage(stage)
        if stage_exam is None:
            raise ValueError(f"The sealed exam has no stage {stage}")
        await tools.send_event(content=f"Running {len(stage_exam.scenarios)} hidden scenarios for stage {stage}…",
                               message_type="tool_call", metadata={"stage": stage, "url": url})
        judge = self.writer.judge if self.writer is not None else None
        results = await run_scenarios(url, stage_exam.scenarios, judge=judge,
                                      repeats=int(os.environ.get("ONSEN_EXAM_REPEATS", "1")))
        passed, total, sat = satisfaction(results)
        verdict = "PASS" if total and sat >= threshold() else "FAIL"
        rounds = append_history(run_id, stage, {"passed": passed, "total": total, "satisfaction": round(sat, 4),
                                                "verdict": verdict, "by": msg.sender_name})
        failures = [r for r in results if not r.passed]
        lines = [
            f"[exam] stage={stage} verdict={verdict} passed={passed}/{total} satisfaction={sat:.0%} "
            f"threshold={threshold():.0%} round={len(rounds)} by={(msg.sender_name or 'unknown').replace(' ', '_')} run={run_id}"
            + (f" commit={kv['commit']}" if kv.get("commit") else ""),
        ]
        if failures:
            lines.append("What a user would notice (the scenarios themselves stay sealed):")
            seen: set[str] = set()
            for r in failures:
                if r.id in seen:
                    continue
                seen.add(r.id)
                lines.append(f"{len(seen)}. {r.story} — {clip(r.observed or 'failed', 220)}")
                if len(seen) >= 8:
                    break
            lines.append("Fix the behavior, then post `[ready]` again.")
        else:
            lines.append("Every hidden scenario for this stage passed. 🍊")
        await self._mention_with_napguard(tools, "\n".join(lines), reply_to)

    async def _reveal(self, msg: PlatformMessage, tools: Any, reply_to: list[str], room_id: str) -> None:
        is_human = str(msg.sender_type or "").lower() == "user"
        if not (is_human or (msg.sender_name or "") == NAMES["napguard"]):
            await tools.send_message("[reveal] refused: only Nap Guard or a human can open the exam.", mentions=reply_to)
            return
        run_id, exam, digest = self._load_run(room_id)
        reveal_dir = Path(os.environ.get("ONSEN_REVEAL_DIR") or state_dir("revealed")).expanduser()
        reveal_dir.mkdir(parents=True, exist_ok=True)
        target = reveal_dir / f"exam-{run_id}.json"
        shutil.copyfile(exam_dir(run_id) / "sealed.json", target)
        stories = []
        for st in exam.stages:
            stories.append(f"Stage {st.stage}:")
            stories.extend(f"  • {sc.id}: {sc.story}" for sc in st.scenarios)
        await tools.send_message(
            f"[reveal] run={run_id} sha256={digest} scenarios={exam.scenario_count} author={exam.author}\n"
            f"The exam file is at {target} — `sha256sum` it and compare with the [seal] message.\n"
            + clip("\n".join(stories), 3000),
            mentions=reply_to,
        )

    def _tally(self, room_id: str) -> str:
        run_id = self.rooms.get(room_id)
        if not run_id:
            return "[tally] agent=examiner run=none rounds=0"
        hist = load_history(run_id)
        rounds = sum(len(v) for v in hist.values())
        curves = "; ".join(
            f"{stage}:" + "→".join(f"{r['satisfaction']:.0%}" for r in entries) for stage, entries in sorted(hist.items())
        ) or "none"
        return f"[tally] agent=examiner run={run_id} rounds={rounds} curves={curves.replace(' ', '')}"


def main() -> None:
    load_env()
    run_agent(build_agent("examiner", ExaminerAdapter()))


if __name__ == "__main__":
    main()
