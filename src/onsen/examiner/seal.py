"""Sealing: write the hidden exam to the Examiner's own disk and publish only its hash.

Commit-reveal: the SHA-256 goes into the room when the exam is sealed; the file
is revealed after the human ships, so anyone can check that the exam never
changed mid-run.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..common import REPO_ROOT, state_dir
from .models import JudgeVerdict, SealedExam, StageExam

logger = logging.getLogger("onsen.examiner")

STAGE_RE = re.compile(r"^##\s+Stage\s+(\d+)\b[^\n]*$", re.M | re.I)


def spec_path(name: str) -> Path:
    specs_dir = Path(os.environ.get("ONSEN_SPECS_DIR", REPO_ROOT / "specs"))
    candidate = Path(name)
    if candidate.suffix == ".md" and candidate.exists():
        return candidate
    return specs_dir / f"{name.removesuffix('.md')}.md"


def parse_stages(spec_text: str) -> list[tuple[int, str]]:
    """[(stage_number, section_text)] from '## Stage N — Title' headings."""
    matches = list(STAGE_RE.finditer(spec_text))
    out: list[tuple[int, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(spec_text)
        nxt = re.search(r"^##\s+(?!Stage\b)", spec_text[m.end():end], re.M)
        section_end = m.end() + nxt.start() if nxt else end
        out.append((int(m.group(1)), spec_text[m.start():section_end].strip()))
    return out


def canonical_bytes(exam: SealedExam) -> bytes:
    return json.dumps(exam.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)


def exam_dir(run_id: str) -> Path:
    return state_dir("exams", run_id)


def save_sealed(exam: SealedExam, run_id: str) -> str:
    data = canonical_bytes(exam)
    path = exam_dir(run_id) / "sealed.json"
    path.write_bytes(data)
    os.chmod(path, 0o600)
    return sha256_hex(data)


def load_sealed(run_id: str) -> tuple[SealedExam, str]:
    data = (exam_dir(run_id) / "sealed.json").read_bytes()
    return SealedExam.model_validate_json(data), sha256_hex(data)


class RoomRuns:
    """Which sealed run belongs to which room, plus each run's exam history."""

    def __init__(self) -> None:
        self.path = state_dir("exams") / "rooms.json"

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}

    def get(self, room_id: str) -> str | None:
        return self._read().get(room_id)

    def set(self, room_id: str, run_id: str) -> None:
        data = self._read()
        data[room_id] = run_id
        self.path.write_text(json.dumps(data, indent=2))


def history_path(run_id: str) -> Path:
    return exam_dir(run_id) / "history.json"


def load_history(run_id: str) -> dict[str, list[dict[str, Any]]]:
    try:
        return json.loads(history_path(run_id).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def append_history(run_id: str, stage: int, entry: dict[str, Any]) -> list[dict[str, Any]]:
    hist = load_history(run_id)
    rounds = hist.setdefault(str(stage), [])
    rounds.append(entry)
    history_path(run_id).write_text(json.dumps(hist, indent=2))
    return rounds


CHECK_KEYS = ("field", "op", "value", "number")
STEP_KEYS = ("path", "label", "role", "name", "text", "testid", "value", "min", "max")


def fill_defaults(stage: dict[str, Any]) -> dict[str, Any]:
    """Hand-written exams may omit null fields; the model-written schema requires them."""
    for sc in stage.get("scenarios", []):
        sc.setdefault("stage", stage.get("stage"))
        sc.setdefault("requests", [])
        sc.setdefault("steps", [])
        for req in sc["requests"]:
            req.setdefault("method", "GET")
            req.setdefault("body_json", None)
            req.setdefault("capture", None)
            req.setdefault("checks", [])
            for chk in req["checks"]:
                for k in CHECK_KEYS:
                    chk.setdefault(k, None)
        for step in sc["steps"]:
            for k in STEP_KEYS:
                step.setdefault(k, None)
    return stage


def load_fixture_exam(path: str | Path, spec_name: str, spec_text: str) -> SealedExam:
    raw = json.loads(Path(path).read_text())
    stages = [StageExam.model_validate(fill_defaults(s)) for s in raw["stages"]]
    return SealedExam(spec_name=spec_name, spec_sha256=sha256_hex(spec_text.encode()),
                      created_at=datetime.now(UTC).isoformat(), nonce=secrets.token_hex(16),
                      author=f"fixture:{Path(path).name}", stages=stages)


WRITER_SYSTEM = """You are the Examiner in an AI software factory. Builders implement a product from a written spec.
You write the HIDDEN acceptance exam they will be graded on. They will never see your scenarios; when a
scenario fails they only see its one-sentence story and what went wrong. Your exam is the factory's holdout set.

Write scenarios in this executable language (the JSON schema is enforced):
- kind=http: `requests` run in order. Each has method, path (with query), optional body_json, optional
  capture ("name=dotted.path; other=[0].field"), and `checks`:
  status(number) | json_type(value list|object) | min_items(number) | max_items(number) |
  every_item / some_item / no_item (field, op, value) | has_fields(value "a,b,c") | field(field, op, value on an object) |
  body_contains / body_not_contains(value) | header_contains(field=header, value).
  ops: eq ne contains icontains not_icontains gte lte exists regex. Comparisons are case-insensitive for eq/ne.
- kind=web: optional setup `requests` (only to capture values), then `steps`:
  goto(path) | fill(label or testid, value) | click(role+name, text, or testid) | press(value=key, optional target) |
  select(label or testid, value) | check(label or testid) | expect_text(text) | expect_no_text(text) |
  expect_count(role(+name) or testid, min, max) | expect_visible(role+name, testid, or text) |
  expect_url_contains(value) | expect_link(name, value=href substring) | wait_ms(value) |
  judge(text = a claim a careful user would verify by looking at the page).
- Use {name} to insert captured values into later paths, bodies, check values, or step fields. Filters:
  {name|lower} {name|upper} {name|strip} {name|url} (URL-encode, use inside query strings) {name|first_word}.
  The capture path `length` gives the number of items in a list response (e.g. capture "n=length").

Rules:
1. Use ONLY the routes, JSON fields, labels, roles and test ids that the spec's acceptance contract defines.
   Never invent selectors or endpoints.
2. The product's data comes from the live web and changes between runs. Never hard-code data values the
   spec does not guarantee. Capture real values first (e.g. capture "c=[0].country; id=[0].id" from the list
   endpoint), then test behavior with them.
3. Test what a real user or API client would notice: correct filtering, search, empty states, unknown ids,
   validation, provenance (every record shows its source), and accessibility basics the contract requires.
   Include edge cases builders tend to miss (case-insensitivity, whitespace, no results, unknown values).
4. Each scenario is independent and small (1-4 requests or 2-8 steps). Web scenarios start with goto.
5. Stories are one sentence in user language ("A visitor who searches for a city sees only spots in that city").
6. Use at most one `judge` step per web scenario, and only for something a check cannot express.
7. Ids: s<stage>-<two digits>, e.g. s2-04.
"""


class ScenarioWriter:
    """Claude writes the exam (once, at seal time) and judges `judge` steps."""

    def __init__(self, model: str | None = None):
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic()
        self.model = model or os.environ.get("ONSEN_EXAMINER_MODEL", "claude-opus-5-5")

    async def _parse(self, *, system: list[dict[str, Any]], prompt: str, output: type, effort: str) -> Any:
        resp = await self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # if a safety classifier declines, the API retries on a fallback model
            output_config={"effort": effort},
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=output,
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"Claude declined to write this exam ({getattr(resp.stop_details, 'category', None)})")
        if resp.parsed_output is None:
            raise RuntimeError(f"Claude returned no structured output (stop_reason={resp.stop_reason})")
        return resp.parsed_output

    async def write_stage(self, spec_text: str, stage: int, per_stage: int) -> StageExam:
        system = [
            {"type": "text", "text": WRITER_SYSTEM},
            # The spec is identical for every stage's call, so cache it.
            {"type": "text", "text": f"<spec>\n{spec_text}\n</spec>", "cache_control": {"type": "ephemeral"}},
        ]
        prompt = (
            f"Write exactly {per_stage} hidden scenarios for Stage {stage}. Earlier stages must keep working, so "
            f"at most one of them may re-check an earlier stage. Return stage={stage}."
        )
        exam: StageExam = await self._parse(system=system, prompt=prompt, output=StageExam, effort="high")
        for sc in exam.scenarios:
            sc.stage = stage
        exam.stage = stage
        return exam

    async def judge(self, claim: str, page_text: str) -> tuple[bool, str]:
        system = [{"type": "text", "text": (
            "You check a web page the way a careful, fair user would. Given the visible text of a page and a claim, "
            "decide whether the page satisfies the claim. Be strict about facts, lenient about wording."
        )}]
        prompt = f"Claim: {claim}\n\n<page_text>\n{page_text}\n</page_text>"
        verdict: JudgeVerdict = await self._parse(system=system, prompt=prompt, output=JudgeVerdict, effort="low")
        return verdict.satisfied, verdict.reason


def llm_enabled() -> bool:
    if os.environ.get("ONSEN_EXAMINER_LLM", "on").lower() in ("off", "0", "false", "no"):
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
