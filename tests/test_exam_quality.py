"""The repair + lint pass that keeps model-written exams honest."""

from __future__ import annotations

from pathlib import Path

from onsen.examiner.models import Check, HttpRequest, Scenario, StageExam, WebStep
from onsen.examiner.seal import lint_stage, repair_stage

SPEC = (Path(__file__).parents[1] / "specs" / "capyfinder.md").read_text()


def step(action, **kw):
    base = dict(path=None, label=None, role=None, name=None, text=None, testid=None, value=None, min=None, max=None)
    base.update(kw)
    return WebStep(action=action, **base)


def check(type_, **kw):
    base = dict(field=None, op=None, value=None, number=None)
    base.update(kw)
    return Check(type=type_, **base)


def req(path, *checks, capture=None):
    return HttpRequest(method="GET", path=path, body_json=None, capture=capture, checks=list(checks))


def test_repair_turns_valueless_comparisons_into_exists_and_adds_enter():
    exam = StageExam(stage=1, scenarios=[
        Scenario(id="x", stage=1, story="health", kind="http", steps=[],
                 requests=[req("/api/health", check("field", field="ok", op="eq"),
                               check("field", field="spots", op="eq", value="number"),
                               check("status"))]),
        Scenario(id="y", stage=2, story="search", kind="web", requests=[],
                 steps=[step("goto", path="/"), step("fill", label="Search spots", value="zzz"),
                        step("expect_visible", text="All countries")]),
    ])
    repair_stage(exam)
    checks = exam.scenarios[0].requests[0].checks
    assert checks[0].op == "exists" and checks[1].op == "exists" and checks[2].number == 200
    actions = [s.action for s in exam.scenarios[1].steps]
    assert actions == ["goto", "fill", "press", "expect_text"]


def test_lint_drops_invented_routes_labels_and_text():
    exam = StageExam(stage=2, scenarios=[
        Scenario(id="ok", stage=2, story="fine", kind="web", requests=[],
                 steps=[step("goto", path="/"), step("fill", label="Search spots", value="{x}"),
                        step("expect_text", text="No capybaras here yet")]),
        Scenario(id="bad-route", stage=1, story="x", kind="http", steps=[],
                 requests=[req("/api/capybaras", check("status", number=200))]),
        Scenario(id="bad-label", stage=2, story="x", kind="web", requests=[],
                 steps=[step("goto", path="/"), step("fill", label="Find a capybara", value="a")]),
        Scenario(id="bad-text", stage=2, story="x", kind="web", requests=[],
                 steps=[step("goto", path="/"), step("expect_text", text="Welcome to the zoo")]),
        Scenario(id="detail", stage=1, story="detail", kind="http", steps=[],
                 requests=[req("/api/spots", capture="id=[0].id"), req("/api/spots/{id}", check("status", number=200))]),
    ])
    kept, dropped = lint_stage(SPEC, exam)
    assert [s.id for s in kept.scenarios] == ["ok", "detail"]
    assert len(dropped) == 3


def test_lint_catches_hard_coded_ids_bad_captures_and_wrong_sources():
    exam = StageExam(stage=1, scenarios=[
        Scenario(id="literal-id", stage=1, story="x", kind="http", steps=[],
                 requests=[req("/api/spots/40", check("status", number=200))]),
        Scenario(id="literal-404", stage=1, story="x", kind="http", steps=[],
                 requests=[req("/api/spots/no-such-spot", check("status", number=404))]),
        Scenario(id="wrong-source", stage=1, story="x", kind="http", steps=[],
                 requests=[req("/api/spots", capture="c=[0].country"),
                           req("/api/spots/{c}", check("status", number=200))]),
        Scenario(id="bad-capture", stage=1, story="x", kind="http", steps=[],
                 requests=[req("/api/spots", capture="n=[{country eq JP}].length")]),
        Scenario(id="good", stage=1, story="x", kind="http", steps=[],
                 requests=[req("/api/spots", capture="id=[0].id; n=length"),
                           req("/api/spots/{id}", check("status", number=200))]),
    ])
    kept, dropped = lint_stage(SPEC, exam)
    assert [s.id for s in kept.scenarios] == ["literal-404", "good"], dropped


def test_repair_swaps_backwards_captures_and_fixes_judge_text():
    exam = StageExam(stage=3, scenarios=[
        Scenario(id="x", stage=3, story="x", kind="web",
                 requests=[req("/api/spots", capture="length=n; [0].id=first")],
                 steps=[step("goto", path="/"), step("judge", value="every card is a hot-spring spot"),
                        step("judge")]),
    ])
    repair_stage(exam)
    sc = exam.scenarios[0]
    assert sc.requests[0].capture == "n=length; first=[0].id"
    assert [s.action for s in sc.steps] == ["goto", "judge"] and sc.steps[1].text == "every card is a hot-spring spot"


def test_repair_wraps_bare_captured_names():
    exam = StageExam(stage=3, scenarios=[
        Scenario(id="x", stage=3, story="x", kind="http", steps=[],
                 requests=[req("/api/spots", capture="list_count=length"),
                           req("/api/stats", check("field", field="total", op="eq", value="list_count"))]),
    ])
    repair_stage(exam)
    assert exam.scenarios[0].requests[1].checks[0].value == "{list_count}"


def test_lint_drops_scenarios_from_a_later_stage():
    # Run 5: stage 1 (the API) was examined on the home page that stage 2 builds.
    from onsen.examiner.models import StageExam
    from onsen.examiner.seal import fill_defaults, lint_stage, stage_scope

    spec = SPEC
    web = {"id": "x", "story": "Home page shows spots.", "kind": "web",
           "steps": [{"action": "goto", "path": "/"}, {"action": "expect_visible", "testid": "spot-card"}]}
    api = {"id": "y", "story": "Health is up.", "kind": "http",
           "requests": [{"path": "/api/health", "checks": [{"type": "status", "number": 200}]}]}
    for stage, kept_ids in ((1, {"y"}), (2, {"x", "y"})):
        exam = StageExam.model_validate(fill_defaults({"stage": stage, "scenarios": [dict(web), dict(api)]}))
        linted, dropped = lint_stage(spec, exam, stage_scope(spec, stage))
        assert {sc.id for sc in linted.scenarios} == kept_ids, dropped
