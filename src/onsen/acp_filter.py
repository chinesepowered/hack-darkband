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
"""

from __future__ import annotations

import asyncio
import json
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


def is_protocol(text: str) -> bool:
    return bool(PROTOCOL.match(text))


class Filter:
    """The decision logic, kept apart from the pipes so it can be tested line by line."""

    def __init__(self) -> None:
        self.prompts: dict[Any, Any] = {}  # in-flight session/prompt request id -> sessionId
        self.held: dict[Any, list[tuple[bytes, str]]] = {}  # sessionId -> held message chunks

    def from_client(self, line: bytes) -> None:
        msg = _parse(line)
        if msg and msg.get("method") == "session/prompt" and "id" in msg:
            self.prompts[msg["id"]] = (msg.get("params") or {}).get("sessionId")

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
            return [line]
        if "method" not in msg and msg.get("id") in self.prompts and ("result" in msg or "error" in msg):
            sid = self.prompts.pop(msg["id"])
            chunks = self.held.pop(sid, [])
            text = "".join(t for _, t in chunks)
            kept = [raw for raw, _ in chunks] if is_protocol(text) else []
            return [*kept, line]
        return [line]


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
    f = Filter()
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
        assert proc.stdout is not None
        while line := await proc.stdout.readline():
            for item in f.from_agent(line):
                out.write(item)
            out.flush()

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
