from __future__ import annotations

from band.testing.fake_tools import FakeAgentTools
from conftest import CREW, deliver

from onsen.nimble_tools import Claim, ResearchAnswer, _extract_rows
from onsen.scout import ScoutAdapter, format_answer, normalize_rows, split_command


def test_split_command_variants():
    assert split_command("ask: is it open?") == ("ask", "is it open?")
    assert split_command("docs: FastAPI static files site:fastapi.tiangolo.com")[0] == "docs"
    assert split_command("[question] what currency does Japan use?") == ("ask", "what currency does Japan use?")
    assert split_command("[tally-request] for the receipt")[0] == "tally"
    assert split_command("where do capybaras live?", from_human=True) == ("ask", "where do capybaras live?")
    assert split_command("docs FastAPI static files", from_human=True)[0] == "docs"


def test_agent_remarks_are_notes():
    # BAND Desktop posts an agent's closing remark as a reply to whoever woke it, Scout included.
    assert split_command("Data verified — 24 rows, nothing new to post?")[0] == "note"
    assert split_command("State verified. Should I wait?")[0] == "note"


def test_rows_need_a_source_and_get_ids():
    rows = normalize_rows([
        {"name": "Izu Shaboten Zoo", "city": "Ito", "country": "jp", "type": "zoo", "source_url": "https://x"},
        {"name": "No Source Cafe", "city": "Tokyo", "country": "JP", "type": "cafe"},
        {"name": "Izu Shaboten Zoo", "city": "Ito", "country": "JP", "type": "zoo", "source_url": "https://y"},
    ])
    assert len(rows) == 1 and rows[0]["id"] == "izu-shaboten-zoo-ito" and rows[0]["country"] == "JP"


def test_extract_rows_from_wrapped_schema():
    assert len(_extract_rows({"spots": [{"name": "a"}, {"name": "b"}]})) == 2
    assert len(_extract_rows('```json\n[{"name": "a"}]\n```')) == 1


class FakeNimble:
    def __init__(self, confident: bool):
        self.confident = confident

    async def research(self, question, effort=None):
        conf = "high" if self.confident else "low"
        return ResearchAnswer(content="Ueno Zoo is closed on Mondays. [1]", overall_confidence=conf,
                              claims=[Claim(1, conf, ["https://www.tokyo-zoo.net/"], self.confident)],
                              sources=[{"url": "https://www.tokyo-zoo.net/", "title": "Ueno Zoo"}],
                              stats={"searches": 1, "page_reads": 2}, run_id="run-x", seconds=3.0)


async def test_confident_answer_goes_only_to_the_asker():
    tools = FakeAgentTools(participants=CREW)
    await deliver(ScoutAdapter(FakeNimble(True)), "@scout ask: Is Ueno Zoo open on Mondays?", "Builder", tools)
    msg = tools.messages_sent[-1]
    assert msg["content"].startswith("[answer] for=Builder confidence=high")
    assert "Nap Guard" not in str(msg["mentions"]) and "nap-guard" not in str(msg["mentions"])


async def test_low_confidence_answer_is_copied_to_nap_guard():
    tools = FakeAgentTools(participants=CREW)
    await deliver(ScoutAdapter(FakeNimble(False)), "@scout ask: Is Ueno Zoo open on Mondays?", "Builder", tools)
    msg = tools.messages_sent[-1]
    assert "confidence=low" in msg["content"]
    assert "Nap Guard" in msg["mentions"]


def test_format_answer_mentions_batching_when_unsure():
    ans = ResearchAnswer("x", "low", [], [], {}, "r", 1.0)
    assert "Nap Guard" in format_answer(ans, "Builder")


async def test_notes_to_scout_are_not_researched():
    tools = FakeAgentTools(participants=CREW)
    await deliver(ScoutAdapter(FakeNimble(True)), "@scout heads-up: the file is final, do not rewrite it.", "Architect", tools)
    assert not tools.messages_sent


def test_split_command_question_vs_note():
    assert split_command("is the zoo open on mondays?", from_human=True)[0] == "ask"
    assert split_command("is the zoo open on mondays?")[0] == "note"  # agents ask with `ask:`
    assert split_command("thanks, noted")[0] == "note"


def test_docs_rank_prefers_official_docs():
    from onsen.nimble_tools import _docs_rank

    results = [{"url": "https://gist.github.com/someone/abc", "metadata": {"position": 1}},
               {"url": "https://github.com/python/cpython", "metadata": {"position": 2}},
               {"url": "https://docs.python.org/3/library/http.server.html", "metadata": {"position": 3}},
               {"url": "https://example.com/blog/http-server", "metadata": {"position": 4}}]
    ranked = [r["url"] for r in sorted(results, key=_docs_rank)]
    assert ranked[0].startswith("https://docs.python.org") and ranked[1].startswith("https://github.com/python")
    assert ranked[-1].startswith("https://gist.github.com")
