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
  status(number) | json_type(value "list" or "object") | min_items(number) | max_items(number) |
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
8. A comparison always has an expected value. To check that a field is present, use op=exists with value null.
   Never compare against a type name like "number".
9. After filling a search box, press Enter: the spec lets results update on Enter.
10. Checks must hold for ANY correct implementation and ANY data Scout finds. When unsure, test less, not more.
11. When a filter may match any of several fields (like a search over name OR city), check the results with
    some_item, never every_item on one of those fields.
"""


VAR_HINT = "{"
ROUTE_RE = re.compile(r"`(?:GET|POST|PUT|PATCH|DELETE)?\s*(/[A-Za-z0-9_/{}.-]*)")
QUERY_NAME_RE = re.compile(r"[?&]([A-Za-z_][A-Za-z0-9_]*)=")
CAPTURE_PATH_RE = re.compile(r"length|(?:\[\d+\]|[A-Za-z_][A-Za-z0-9_]*)(?:\.?[A-Za-z_][A-Za-z0-9_]*|\[\d+\])*")


def _route_patterns(spec_text: str) -> list[re.Pattern[str]]:
    pats = []
    for route in set(ROUTE_RE.findall(spec_text)):
        rx = re.escape(route).replace(r"\{", "{").replace(r"\}", "}")
        rx = re.sub(r"\{[^}]*\}", r"[^/?]+", rx)
        pats.append(re.compile(rf"^{rx}/?$"))
    return pats


TYPE_WORDS = {"number", "integer", "string", "boolean", "bool", "array", "list", "object", "null", "true/false"}


def repair_stage(exam: StageExam) -> StageExam:
    """Fix the slips models make in the scenario language before linting:
    a comparison with no expected value means "exists"; type names aren't values; a status check
    without a number means 200; a search box gets an Enter after it's filled (the spec allows results
    to update on Enter); plain-text visibility checks become text checks."""
    from .models import WebStep

    for sc in exam.scenarios:
        for req in sc.requests:
            fixed = []
            for chk in req.checks:
                if chk.type == "status" and chk.number is None:
                    chk.number = 200
                if chk.type in ("min_items", "max_items") and chk.number is None:
                    continue
                if chk.type in ("every_item", "some_item", "no_item", "field"):
                    if chk.op not in (None, "exists") and (chk.value is None or chk.value.strip().lower() in TYPE_WORDS):
                        chk.op, chk.value = "exists", None
                if chk.type == "has_fields" and not chk.value:
                    continue
                fixed.append(chk)
            req.checks = fixed
        steps: list[WebStep] = []
        for i, st in enumerate(sc.steps):
            if st.action == "expect_visible" and st.text and not (st.role or st.testid or st.label):
                st.action = "expect_text"
            steps.append(st)
            nxt = sc.steps[i + 1] if i + 1 < len(sc.steps) else None
            if st.action == "fill" and (nxt is None or nxt.action != "press"):
                steps.append(WebStep(action="press", path=None, label=st.label, role=None, name=None, text=None,
                                     testid=st.testid, value="Enter", min=None, max=None))
        sc.steps = steps
    return exam


def lint_stage(spec_text: str, exam: StageExam) -> tuple[StageExam, list[str]]:
    """Drop scenarios that use anything the spec's contract doesn't define: unknown routes, query
    parameters, labels or test ids, or literal UI text the spec never promises. Model-written exams
    otherwise fail correct apps for invented reasons."""
    spec_lower = spec_text.lower()
    routes = _route_patterns(spec_text)

    def known(text: str | None) -> bool:
        return text is None or VAR_HINT in text or text.lower() in spec_lower

    def route_ok(path: str) -> bool:
        bare = path.split("?", 1)[0]
        if VAR_HINT in bare:
            bare = re.sub(r"\{[^}]*\}", "x", bare)
        return any(p.match(bare) for p in routes)

    param_routes = [(re.compile("^" + re.sub(r"\\\{([^}]*)\\\}", r"(?P<\1>[^/?]+)", re.escape(r)) + "/?$"), r)
                    for r in set(ROUTE_RE.findall(spec_text)) if "{" in r]

    kept, dropped = [], []
    for sc in exam.scenarios:
        problems: list[str] = []
        captured_from: dict[str, str] = {}
        for req in sc.requests:
            for part in (req.capture or "").split(";"):
                if "=" in part:
                    name, path = (x.strip() for x in part.split("=", 1))
                    if not CAPTURE_PATH_RE.fullmatch(path):
                        problems.append(f"capture path {path!r}")
                    captured_from[name] = path
        for req in sc.requests:
            if not route_ok(req.path):
                problems.append(f"route {req.path}")
            bare = req.path.split("?", 1)[0]
            expects_ok = any(c.type == "status" and (c.number or 200) < 300 for c in req.checks)
            for rx, _route in param_routes:
                m = rx.match(bare)
                if not m:
                    continue
                for param, segment in m.groupdict().items():
                    var = re.fullmatch(r"\{([a-zA-Z_]\w*)(?:\|[a-z_]+)*\}", segment)
                    if var is None and expects_ok:
                        problems.append(f"hard-coded {param} {segment!r}")
                    elif var is not None and var.group(1) in captured_from:
                        leaf = re.split(r"[.\[\]]", captured_from[var.group(1)].strip())[-1]
                        if leaf != param:
                            problems.append(f"{param} taken from {captured_from[var.group(1)]!r}")
            problems += [f"query {q}" for q in QUERY_NAME_RE.findall(req.path) if f"`{q}`" not in spec_text]
            for chk in req.checks:
                if chk.field and chk.type in ("every_item", "some_item", "no_item", "field"):
                    leaf = re.split(r"[.\[\]]", chk.field.strip())[-1] or chk.field
                    if leaf not in ("length",) and not known(leaf):
                        problems.append(f"field {chk.field}")
        for st in sc.steps:
            if st.action == "goto" and st.path and not route_ok(st.path):
                problems.append(f"page {st.path}")
            for attr in ("label", "testid"):
                if not known(getattr(st, attr)):
                    problems.append(f"{attr} {getattr(st, attr)!r}")
            if st.action in ("click", "expect_visible", "expect_link", "expect_count") and st.name and not known(st.name):
                problems.append(f"name {st.name!r}")
            if st.action == "expect_text" and st.text and not known(st.text):
                problems.append(f"text {st.text!r}")
        if sc.kind == "web" and (not sc.steps or sc.steps[0].action != "goto"):
            problems.append("web scenario doesn't start with goto")
        if sc.kind == "http" and not sc.requests:
            problems.append("http scenario has no requests")
        (dropped if problems else kept).append((sc, problems))
    exam.scenarios = [sc for sc, _ in kept]
    return exam, [f"{sc.id}: {', '.join(p)}" for sc, p in dropped]


class ScenarioWriter:
    """The LLM (Qwen 3.8 on W&B by default) writes the exam once, at seal time, and judges `judge` steps."""

    def __init__(self, model: str | None = None):
        from ..llm import LLM, llm_model

        self.llm = LLM(model=model or llm_model("ONSEN_EXAMINER_MODEL"))
        self.model = self.llm.model
        self.dropped: list[str] = []

    async def write_stage(self, spec_text: str, stage: int, per_stage: int) -> StageExam:
        system = f"{WRITER_SYSTEM}\n<spec>\n{spec_text}\n</spec>"
        prompt = (
            f"Write exactly {per_stage} hidden scenarios for Stage {stage}. Earlier stages must keep working, so "
            f"at most one of them may re-check an earlier stage. Return stage={stage}. Every field in the schema "
            f"must be present; use null for fields a check or step doesn't use."
        )
        reasoning = os.environ.get("ONSEN_EXAMINER_REASONING", "none")
        # Guided JSON decoding can occasionally loop on whitespace; a tighter cap fails fast and retries.
        exam = await self.llm.structured(system=system, prompt=prompt, output=StageExam, reasoning=reasoning,
                                         max_tokens=8000)
        exam, dropped = lint_stage(spec_text, repair_stage(exam))
        if len(exam.scenarios) < max(3, per_stage // 2):
            feedback = ("These scenarios used routes, fields, labels or text the spec doesn't define, so they were "
                        "dropped:\n" + "\n".join(dropped[:12]) + "\nUse ONLY what the acceptance contract defines.")
            again = await self.llm.structured(system=system, prompt=f"{prompt}\n\n{feedback}", output=StageExam,
                                              reasoning=reasoning, max_tokens=8000)
            again, dropped_again = lint_stage(spec_text, repair_stage(again))
            exam.scenarios += again.scenarios
            dropped += dropped_again
        self.dropped += [f"stage {stage} {d}" for d in dropped]
        exam.stage = stage
        exam.scenarios = exam.scenarios[: per_stage + 2]
        for i, sc in enumerate(exam.scenarios, start=1):
            sc.stage = stage
            sc.id = f"s{stage}-{i:02d}"
        return exam

    async def judge(self, claim: str, page_text: str) -> tuple[bool, str]:
        system = ("You check a web page the way a careful, fair user would. Given the visible text of a page and a "
                  "claim, decide whether the page satisfies the claim. Be strict about facts, lenient about wording.")
        prompt = f"Claim: {claim}\n\n<page_text>\n{page_text}\n</page_text>"
        verdict = await self.llm.structured(system=system, prompt=prompt, output=JudgeVerdict, max_tokens=4000)
        return verdict.satisfied, verdict.reason


def llm_enabled() -> bool:
    if os.environ.get("ONSEN_EXAMINER_LLM", "on").lower() in ("off", "0", "false", "no"):
        return False
    from ..llm import llm_api_key

    return bool(llm_api_key())
