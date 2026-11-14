from __future__ import annotations

from pathlib import Path

import pytest
from band.testing.fake_tools import FakeAgentTools
from conftest import CREW, FIXTURES, deliver

from onsen.examiner.agent import ExaminerAdapter, split_command
from onsen.examiner.runner import run_scenarios, satisfaction, substitute
from onsen.examiner.seal import load_fixture_exam, load_sealed, parse_stages, save_sealed, sha256_hex

SPEC = Path(__file__).parents[1] / "specs" / "capyfinder.md"


def exam():
    return load_fixture_exam(FIXTURES / "capyfinder_exam.json", "capyfinder", SPEC.read_text())


@pytest.fixture
def app():
    import ref_app

    servers = []

    def start(bugs=()):
        server, url = ref_app.serve(FIXTURES / "spots.json", 0, set(bugs))
        servers.append(server)
        return url

    yield start
    for s in servers:
        s.shutdown()


def test_spec_has_three_stages():
    assert [n for n, _ in parse_stages(SPEC.read_text())] == [1, 2, 3]


def test_substitute_filters():
    env = {"city": " Ito ", "c": "JP"}
    assert substitute("/api/spots?q={city|strip|upper|url}&country={c|lower}", env) == "/api/spots?q=ITO&country=jp"


def test_seal_roundtrip_hash_is_stable():
    e = exam()
    digest = save_sealed(e, "run-1")
    loaded, digest2 = load_sealed("run-1")
    assert digest == digest2 and len(digest) == 64
    assert loaded.scenario_count == e.scenario_count


async def test_correct_app_passes_every_stage(app):
    url = app()
    for stage in exam().stages:
        results = await run_scenarios(url, stage.scenarios)
        failed = [(r.id, r.observed) for r in results if not r.passed]
        assert not failed, failed
        passed, total, sat = satisfaction(results)
        assert sat == 1.0 and total >= 2


async def test_exam_catches_injected_bugs(app):
    url = app(bugs=("country_case", "no_empty_state", "stats_off"))
    e = exam()
    results = {r.id: r for st in e.stages for r in await run_scenarios(url, st.scenarios)}
    assert not results["s1-03"].passed and "country" in results["s1-03"].observed
    assert not results["s2-03"].passed and "No capybaras here yet" in results["s2-03"].observed
    assert not results["s3-01"].passed and "total" in results["s3-01"].observed
    assert results["s1-01"].passed and results["s2-01"].passed


def test_split_command():
    assert split_command("[ready] stage=2 url=http://localhost:8000") == ("exam", "stage=2 url=http://localhost:8000")
    assert split_command("seal spec=capyfinder")[0] == "seal"
    assert split_command("[tally-request] please")[0] == "tally"


async def test_seal_then_exam_through_band_messages(app, monkeypatch):
    monkeypatch.setenv("ONSEN_EXAM_FILE", str(FIXTURES / "capyfinder_exam.json"))
    url = app(bugs=("country_case",))
    adapter = ExaminerAdapter()
    tools = FakeAgentTools(participants=CREW)
    await deliver(adapter, "@examiner seal spec=capyfinder", "Architect", tools)
    seal_msg = tools.messages_sent[-1]["content"]
    assert seal_msg.startswith("[seal]") and "sha256=" in seal_msg and "stages=3" in seal_msg
    assert "nap" in str(tools.messages_sent[-1]["mentions"]).lower()

    await deliver(adapter, f"@examiner [ready] stage=1 url={url}", "Builder", tools)
    verdict = tools.messages_sent[-1]["content"]
    assert verdict.startswith("[exam] stage=1 verdict=FAIL")
    assert "lowercase country code" in verdict  # the story is shown...
    assert "/api/spots?country=" not in verdict.split("\n", 1)[0]  # ...but not as a test script header
    assert "by=Builder" in verdict


async def test_builders_cannot_open_the_exam(app, monkeypatch):
    monkeypatch.setenv("ONSEN_EXAM_FILE", str(FIXTURES / "capyfinder_exam.json"))
    adapter = ExaminerAdapter()
    tools = FakeAgentTools(participants=CREW)
    await deliver(adapter, "@examiner seal", "Architect", tools)
    await deliver(adapter, "@examiner reveal", "Builder", tools)
    assert "refused" in tools.messages_sent[-1]["content"]
    await deliver(adapter, "@examiner reveal", "Nap Guard", tools)
    reveal = tools.messages_sent[-1]["content"]
    assert reveal.startswith("[reveal]") and "sha256=" in reveal and "s1-01" in reveal
    # the revealed file hashes to the sealed hash
    digest = reveal.split("sha256=")[1].split()[0]
    path = Path(reveal.split("The exam file is at ")[1].split(" ")[0])
    assert sha256_hex(path.read_bytes()) == digest
