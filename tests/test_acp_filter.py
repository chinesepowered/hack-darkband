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
