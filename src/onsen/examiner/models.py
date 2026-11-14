"""The Examiner's scenario language: small, flat, and executable without an LLM.

Scenarios are written once (by Claude, at seal time) and then run
deterministically by runner.py. Flat models with nullable fields keep the JSON
schema friendly to structured outputs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CheckType = Literal[
    "status",  # number = expected HTTP status
    "json_type",  # value = "list" | "object"
    "min_items",  # number
    "max_items",  # number
    "every_item",  # field/op/value must hold for every item of the JSON list
    "some_item",  # ... for at least one item
    "no_item",  # ... for no item
    "has_fields",  # value = comma-separated field names (object, or every list item)
    "field",  # field/op/value on a JSON object response
    "body_contains",  # value = substring (case-insensitive)
    "body_not_contains",
    "header_contains",  # field = header name, value = substring
]

Op = Literal["eq", "ne", "contains", "icontains", "not_icontains", "gte", "lte", "exists", "regex"]

WebAction = Literal[
    "goto",  # path
    "fill",  # label | testid, value
    "click",  # role+name | text | testid
    "press",  # key=value (e.g. Enter), optional label | testid target
    "select",  # label | testid, value = option label or value
    "check",  # label | testid
    "expect_text",  # text visible somewhere on the page (case-insensitive)
    "expect_no_text",  # text absent
    "expect_count",  # role(+name) | testid; min / max
    "expect_visible",  # role+name | testid | text
    "expect_url_contains",  # value
    "expect_link",  # name = link text (substring), value = substring the href must contain
    "wait_ms",  # value = milliseconds
    "judge",  # text = a claim a careful user would check by eye; judged by Claude from the page text
]


class Check(BaseModel):
    type: CheckType
    field: str | None = Field(description="Dotted JSON path (item/object checks) or header name; null if unused")
    op: Op | None = Field(description="Comparison for item/field checks; null if unused")
    value: str | None = Field(description="Expected value as text; null if unused")
    number: int | None = Field(description="Expected number for status/min_items/max_items; null if unused")


class HttpRequest(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str = Field(description="Path plus query string, e.g. /api/spots?country={c}. {name} inserts a captured value")
    body_json: str | None = Field(description="JSON request body as text, or null")
    capture: str | None = Field(
        description="Save values from this JSON response for later requests/steps: 'name=dotted.path; other=path'. "
        "Paths index lists like [0].id. Null if unused"
    )
    checks: list[Check]


class WebStep(BaseModel):
    action: WebAction
    path: str | None
    label: str | None
    role: str | None
    name: str | None
    text: str | None
    testid: str | None
    value: str | None
    min: int | None
    max: int | None


class Scenario(BaseModel):
    id: str = Field(description="Stable id like s1-03")
    stage: int
    story: str = Field(description="One-sentence user story. Shown to builders only if this scenario fails.")
    kind: Literal["http", "web"]
    requests: list[HttpRequest] = Field(
        description="kind=http: the requests to check. kind=web: optional setup requests that only capture values"
    )
    steps: list[WebStep] = Field(description="For kind=web; empty list for http")


class StageExam(BaseModel):
    stage: int
    scenarios: list[Scenario]


class SealedExam(BaseModel):
    spec_name: str
    spec_sha256: str
    created_at: str
    nonce: str
    author: str  # model id, or "fixture:<path>"
    stages: list[StageExam]

    def stage(self, n: int) -> StageExam | None:
        return next((s for s in self.stages if s.stage == n), None)

    @property
    def scenario_count(self) -> int:
        return sum(len(s.scenarios) for s in self.stages)


class ScenarioResult(BaseModel):
    id: str
    stage: int
    story: str
    passed: bool
    skipped: bool = False
    observed: str | None = None  # behavioral description of the failure
    seconds: float = 0.0


class JudgeVerdict(BaseModel):
    satisfied: bool
    reason: str = Field(description="One sentence a user would agree with")


class ScenarioFlag(BaseModel):
    id: str
    reason: str = Field(description="Which spec rule the scenario contradicts, or which unguaranteed data it relies on")


class ExamAudit(BaseModel):
    flags: list[ScenarioFlag] = Field(description="Only scenarios that are wrong; empty if all are sound")
