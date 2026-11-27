#!/usr/bin/env python3
"""Keep a crew agent's closing remarks out of the room.

    acp_filter.py <agent command> [args…]      e.g. acp_filter.py opencode acp

BAND Desktop posts the text an agent ends its turn with as a reply to whoever woke it. Onsen's crew sends every
protocol message itself with `band send`, so the closing remark is never needed. Qwen 3.8 also can't end a turn
without one: it writes "." or "No reply needed.", which wakes the other agent, which replies "."; told to stay
silent, it loops on tool calls instead (runs 5 and 6).

This stdio proxy sits between BAND Desktop and `opencode acp` (the Agent Client Protocol: newline-delimited JSON-RPC).
While a turn is in flight, it holds the agent's message text. When the turn ends, it passes the text on only if it
is a protocol message, i.e. it starts with a tag such as `[ready]`. Tool calls, reasoning, permission requests and
everything else pass straight through. Standard library only, because the runtime's environment is minimal.

Closing remarks: by default none reach the room (ONSEN_PASS_REMARKS=1 passes tagged ones). Seats speak through
`band send`, whose linter checks each message; a remark would skip it (Run O posted a status note tagged [ready] and a
malformed [review] that way). When a seat's turn ends without a message, keep-going asks it to send one.

Keep going (ONSEN_KEEP_GOING=1, set for the Builder and the Examiner, with a prompt for each): a seat is woken only by a mention, so a Builder that ends its
turn on "I'll keep working on X" sits idle until someone mentions it. When a turn that used tools ends without the
seat having sent anything to the room, the proxy doesn't end the turn: it asks the agent to carry on, up to
ONSEN_KEEP_GOING_MAX times (default 4) per prompt, and ends the turn when the agent sends a message, stops using
tools, or the limit is reached. BAND Desktop sees one longer turn.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import os
import re
import signal
import sys
from typing import Any

# "[ready] …", "@owner/handle [ready] …": a protocol message the agent meant to send to whoever woke it. Only the
# crew's own tags (crew/PROTOCOL.md) count; a closing "[ok] all done" is still a closing remark.
CREW_TAGS = ("ready", "review", "task", "plan", "dispute", "exam", "seal", "reveal", "report", "blocking-question",
             "question")
PROTOCOL = re.compile(r"^\s*(?:@\S+\s+)*\[(?:" + "|".join(CREW_TAGS) + r")\]", re.I)
LIMIT = 1 << 26  # tool output can make single lines very long
SENDS = re.compile(r"\bband\b[^\n]{0,300}?\bsend\b")  # a tool call that posts to the room
ABORTED = re.compile(r"\babort", re.I)  # "Tool execution aborted": an edit cut off mid-stream, lost whole
# Run R: a Builder streamed one stage-2 patch for 17 minutes until the model's output limit cut it off, and then,
# prompted to carry on, started the same patch again.
LOST_EDIT = ("Your last tool call was cut off before it finished (it was too long for one response), so that whole "
             "change was lost. Make it again in parts of at most about 300 lines per edit (a large new file can be "
             "written in several appends), and commit each part once it imports and runs.")
KEEP_GOING = {
    "builder": ("Your turn ended, but you haven't sent anything to the room, so nobody will wake you to finish. If a "
                "numbered handoff is still arriving (you have part i/k but not part k/k), end your turn now without "
                "using any tool: the next part wakes you. If the stage's work is unfinished, carry on now: implement, "
                "commit, run the checker, and post [ready] when it claims the stage. If your latest commit is already "
                "handed off and you are only waiting for verdicts, end your turn without using any tool."),
    "reviewer": ("Your turn ended, but you haven't sent anything to the room, so nobody has your verdict. If you "
                 "reviewed a commit that was handed off with [ready], send your [review] now with band send, to the "
                 "Builder and Nap Guard. If nothing is waiting for your review, or a numbered handoff is still "
                 "arriving, end your turn without using any tool."),
    "examiner": ("Your turn ended, but you haven't sent anything to the room. If every part of the stage's task has "
                 "arrived and its exam isn't sealed yet, write it now and seal it with onsen-exam seal. If a [ready] is "
                 "waiting for your grade, grade it. If the exam is sealed and nothing is waiting, end your turn without "
                 "using any tool."),
}


def is_protocol(text: str) -> bool:
    return bool(PROTOCOL.match(text))


class Filter:
    """The decision logic, kept apart from the pipes so it can be tested line by line."""

    def __init__(self, keep_going: bool = False, max_keep_going: int = 4, role: str = "builder",
                 pass_remarks: bool = True) -> None:
        self.prompts: dict[Any, Any] = {}  # in-flight session/prompt request id -> sessionId
        self.held: dict[Any, list[tuple[bytes, str]]] = {}  # sessionId -> held message chunks
        self.keep_going, self.max_keep_going = keep_going, max_keep_going
        self.turns: dict[Any, dict[str, Any]] = {}  # sessionId -> {client_id, tools, sent, continued}
        self.to_agent: list[bytes] = []  # lines the proxy itself sends to the agent (keep-going prompts)
        self.role, self.pass_remarks = role, pass_remarks
        self._ids = itertools.count(1)

    def from_client(self, line: bytes) -> None:
        msg = _parse(line)
        if msg and msg.get("method") == "session/prompt" and "id" in msg:
            sid = (msg.get("params") or {}).get("sessionId")
            self.prompts[msg["id"]] = sid
            self.turns[sid] = {"client_id": msg["id"], "tools": 0, "sent": False, "continued": 0}

    def from_agent(self, line: bytes) -> list[bytes]:
        """The lines to forward to the client now (possibly none, possibly held ones too)."""
        msg = _parse(line)
        if msg is None:
            return [line]
        if msg.get("method") == "session/update":
            params = msg.get("params") or {}
            update = params.get("update") or {}
            sid = params.get("sessionId")
            if update.get("sessionUpdate") == "agent_message_chunk" and sid in self.prompts.values():
                text = (update.get("content") or {}).get("text") or ""
                self.held.setdefault(sid, []).append((line, text))
                return []
            if update.get("sessionUpdate") in ("tool_call", "tool_call_update") and sid in self.turns:
                t = self.turns[sid]
                if update.get("sessionUpdate") == "tool_call":
                    t["tools"] += 1
                if SENDS.search(json.dumps(update)):
                    t["sent"] = True
                if update.get("status") == "failed" and ABORTED.search(json.dumps(update)):
                    t["lost"] = True
            return [line]
        if "method" not in msg and msg.get("id") in self.prompts and ("result" in msg or "error" in msg):
            sid = self.prompts.pop(msg["id"])
            chunks = self.held.pop(sid, [])
            text = "".join(t for _, t in chunks)
            protocol = is_protocol(text)
            t = self.turns.get(sid)
            stop = (msg.get("result") or {}).get("stopReason")
            # A closing remark reaches the room only when remarks pass: otherwise a tagged answer would skip the linter
            # (a status note tagged [ready], a malformed [review]); keep-going asks the seat to send it properly.
            forward = protocol and self.pass_remarks
            posted = forward
            if (self.keep_going and t and stop == "end_turn" and t["tools"] > 0 and not t["sent"] and not posted
                    and t["continued"] < self.max_keep_going):
                # The agent stopped mid-work without telling anyone: ask it to carry on, in the same client turn.
                t["continued"] += 1
                t["tools"] = 0
                text = LOST_EDIT if t.pop("lost", False) else KEEP_GOING.get(self.role, KEEP_GOING["builder"])
                rid = f"onsen-keep-going-{next(self._ids)}"
                self.prompts[rid] = sid
                self.to_agent.append(_line({"jsonrpc": "2.0", "id": rid, "method": "session/prompt",
                                            "params": {"sessionId": sid, "prompt": [{"type": "text", "text": text}]}}))
                return []
            kept = [raw for raw, _ in chunks] if forward else []
            if t is not None:
                self.turns.pop(sid, None)
                if msg["id"] != t["client_id"]:  # the client's turn ends with its own request id
                    msg["id"] = t["client_id"]
                    line = _line(msg)
            return [*kept, line]
        return [line]


def _line(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj) + "\n").encode()


def _parse(line: bytes) -> dict[str, Any] | None:
    try:
        msg = json.loads(line)
    except ValueError:
        return None
    return msg if isinstance(msg, dict) else None


async def run(argv: list[str]) -> int:
    proc = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                limit=LIMIT)
    loop = asyncio.get_running_loop()
    stdin = asyncio.StreamReader(limit=LIMIT)
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(stdin), sys.stdin)
    out = sys.stdout.buffer
    f = Filter(keep_going=os.environ.get("ONSEN_KEEP_GOING", "") in ("1", "true", "yes"),
               max_keep_going=int(os.environ.get("ONSEN_KEEP_GOING_MAX", "4")),
               role=os.environ.get("ONSEN_ROLE", "builder"),
               # Seats speak through `band send`; a turn's closing text, even a tagged one, only duplicates it.
               pass_remarks=os.environ.get("ONSEN_PASS_REMARKS", "") in ("1", "true", "yes"))
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, proc.terminate)

    async def client_to_agent() -> None:
        assert proc.stdin is not None
        while line := await stdin.readline():
            f.from_client(line)
            proc.stdin.write(line)
            await proc.stdin.drain()
        proc.stdin.close()

    async def agent_to_client() -> None:
        assert proc.stdout is not None and proc.stdin is not None
        while line := await proc.stdout.readline():
            for item in f.from_agent(line):
                out.write(item)
            out.flush()
            while f.to_agent:  # the proxy's own keep-going prompt
                proc.stdin.write(f.to_agent.pop(0))
                await proc.stdin.drain()

    pumps = [asyncio.create_task(client_to_agent()), asyncio.create_task(agent_to_client())]
    code = await proc.wait()
    for p in pumps:
        p.cancel()
    return code


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    return asyncio.run(run(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
