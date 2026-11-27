from __future__ import annotations

import json

from onsen.acp_filter import Filter


def line(obj) -> bytes:
    return (json.dumps(obj) + "\n").encode()


def chunk(sid, text):
    return line({"jsonrpc": "2.0", "method": "session/update",
                 "params": {"sessionId": sid, "update": {"sessionUpdate": "agent_message_chunk",
                                                         "content": {"type": "text", "text": text}}}})


def turn(text: str) -> list[bytes]:
    """Run one prompt through the filter; return what the client would receive."""
    f = Filter()
    f.from_client(line({"jsonrpc": "2.0", "id": 7, "method": "session/prompt", "params": {"sessionId": "s"}}))
    out: list[bytes] = []
    tool = line({"jsonrpc": "2.0", "method": "session/update",
                 "params": {"sessionId": "s", "update": {"sessionUpdate": "tool_call", "title": "bash"}}})
    for raw in (chunk("s", "\n\n"), tool, chunk("s", text)):
        out += f.from_agent(raw)
    out += f.from_agent(line({"jsonrpc": "2.0", "id": 7, "result": {"stopReason": "end_turn"}}))
    return out


def texts(out: list[bytes]) -> str:
    return "".join(json.loads(x)["params"]["update"]["content"]["text"] for x in out
                   if b"agent_message_chunk" in x)


def test_closing_remarks_are_dropped_but_tool_calls_and_the_turn_end_pass():
    out = turn("No reply needed.")
    assert texts(out) == ""
    assert texts(turn("[ok] Smoke test passed.")) == ""  # tag-shaped, but not a crew protocol tag
    assert any(b"tool_call" in x for x in out) and b"end_turn" in out[-1]


def test_protocol_messages_pass():
    assert texts(turn("[ready] stage=1 url=http://localhost:8000 commit=abc1234")).strip().startswith("[ready]")
    assert "[review]" in texts(turn("@clai/builder [review] stage=1 commit=abc APPROVED"))


def test_text_outside_a_prompt_passes():
    # session/load replays history as message chunks with no prompt in flight; those go straight through.
    assert Filter().from_agent(chunk("s", "old message")) != []


def tool_call(sid, command):
    return line({"jsonrpc": "2.0", "method": "session/update",
                 "params": {"sessionId": sid, "update": {"sessionUpdate": "tool_call", "title": "bash",
                                                         "rawInput": {"command": command}}}})


def end(rid, reason="end_turn"):
    return line({"jsonrpc": "2.0", "id": rid, "result": {"stopReason": reason}})


def test_keep_going_continues_a_builder_that_stopped_mid_work():
    f = Filter(keep_going=True, max_keep_going=2)
    f.from_client(line({"jsonrpc": "2.0", "id": 7, "method": "session/prompt", "params": {"sessionId": "s"}}))
    assert f.from_agent(tool_call("s", "git commit -m wip")) != []
    assert f.from_agent(chunk("s", "I'll keep fixing the parser.")) == []
    # the turn ends without a message to the room: nothing reaches the client, a keep-going prompt reaches the agent
    assert f.from_agent(end(7)) == []
    assert len(f.to_agent) == 1
    req = json.loads(f.to_agent.pop())
    assert req["method"] == "session/prompt" and req["params"]["sessionId"] == "s"
    # the continuation works and then posts to the room: the client's turn ends, with the client's own id
    f.from_agent(tool_call("s", "onsen-check /repo 1 abc1234"))
    f.from_agent(tool_call("s", "band --profile default --session onsen-builder send ROOM --body-file /tmp/r.md"))
    out = f.from_agent(end(req["id"]))
    assert json.loads(out[-1])["id"] == 7 and not f.to_agent


def test_keep_going_stops_when_the_agent_only_talks_or_hits_the_limit():
    f = Filter(keep_going=True, max_keep_going=1)
    f.from_client(line({"jsonrpc": "2.0", "id": 9, "method": "session/prompt", "params": {"sessionId": "s"}}))
    f.from_agent(tool_call("s", "pytest"))
    assert f.from_agent(end(9)) == [] and len(f.to_agent) == 1
    rid = json.loads(f.to_agent.pop())["id"]
    f.from_agent(tool_call("s", "pytest"))
    out = f.from_agent(end(rid))  # the limit is reached: the turn ends
    assert json.loads(out[-1])["id"] == 9
    # a turn with no tool calls (waiting for verdicts) ends right away; so does a cancelled one
    f.from_client(line({"jsonrpc": "2.0", "id": 10, "method": "session/prompt", "params": {"sessionId": "s"}}))
    assert json.loads(f.from_agent(end(10))[-1])["id"] == 10
    f.from_client(line({"jsonrpc": "2.0", "id": 11, "method": "session/prompt", "params": {"sessionId": "s"}}))
    f.from_agent(tool_call("s", "pytest"))
    assert json.loads(f.from_agent(end(11, "cancelled"))[-1])["id"] == 11


def test_keep_going_is_off_by_default():
    f = Filter()
    f.from_client(line({"jsonrpc": "2.0", "id": 7, "method": "session/prompt", "params": {"sessionId": "s"}}))
    f.from_agent(tool_call("s", "git commit -m wip"))
    assert json.loads(f.from_agent(end(7))[-1])["id"] == 7 and not f.to_agent


def test_a_tagged_remark_after_band_send_is_a_duplicate_and_stays_out():
    f = Filter(keep_going=True, role="examiner", pass_remarks=False)
    f.from_client(line({"jsonrpc": "2.0", "id": 5, "method": "session/prompt", "params": {"sessionId": "s"}}))
    f.from_agent(tool_call("s", "band --profile default --session onsen-examiner send ROOM --body-file /tmp/e.md"))
    f.from_agent(chunk("s", "[exam] stage=1 passed 13/14, sent to the Builder."))
    out = f.from_agent(end(5))
    assert texts(out) == "" and json.loads(out[-1])["id"] == 5 and not f.to_agent


def test_a_verdict_written_as_the_turns_answer_reaches_the_room_when_nothing_else_was_sent():
    f = Filter(keep_going=True, role="reviewer", pass_remarks=False, max_keep_going=1)
    f.from_client(line({"jsonrpc": "2.0", "id": 3, "method": "session/prompt", "params": {"sessionId": "s"}}))
    f.from_agent(tool_call("s", "git diff abc..def"))
    f.from_agent(chunk("s", "[review] stage=1 commit=def BLOCKED: providers.py:87"))
    out = f.from_agent(end(3))
    # the remark is the seat's only message this turn, so it goes to the room and the turn ends
    assert "[review]" in texts(out) and json.loads(out[-1])["id"] == 3 and not f.to_agent


def test_the_reviewer_is_asked_to_send_its_verdict():
    f = Filter(keep_going=True, role="reviewer", pass_remarks=False)
    f.from_client(line({"jsonrpc": "2.0", "id": 4, "method": "session/prompt", "params": {"sessionId": "s"}}))
    f.from_agent(tool_call("s", "onsen-serve /repo stage-1 abc"))
    f.from_agent(chunk("s", "I checked it."))
    assert f.from_agent(end(4)) == []
    prompt = json.loads(f.to_agent.pop())["params"]["prompt"][0]["text"]
    assert "send your [review] now" in prompt
