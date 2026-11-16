"""Scout: the factory's eyes on the live web, powered by Nimble.

Rule of the house: builders ask @Scout before they ever ask a human.

Commands (first word after the @mention, case-insensitive):
  ask: <question>          Nimble research agent -> cited answer + confidence
  docs: <topic> [site:x]   Nimble search + extract -> fresh docs saved to the workspace
  docs: <url>              extract one page to markdown
  data: <request> [schema=path] [out=data/spots.json]
                           Nimble dataset-building agent -> JSON rows with sources
  tally                    counts for the run receipt (asked by Nap Guard)
  help

An untagged message is treated as ``ask``. Low-confidence answers are copied to
Nap Guard, which batches them into the single human wake-up instead of waking
the human now.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from band.core.simple_adapter import SimpleAdapter
from band.core.types import PlatformMessage

from .common import (
    NAMES,
    REPO_ROOT,
    JsonState,
    build_agent,
    clip,
    command_text,
    load_env,
    parse_kv,
    parse_tagged,
    run_agent,
    state_dir,
)
from .nimble_tools import DatasetResult, NimbleScout, ResearchAnswer, slugify

logger = logging.getLogger("onsen.scout")

COMMANDS = ("ask", "docs", "data", "tally", "help")
URL_RE = re.compile(r"https?://\S+")
SITE_RE = re.compile(r"\bsite:([\w.-]+)")

HELP = (
    "Scout commands — ask me before you ask a human:\n"
    "• `ask: <question>` → cited answer from the live web (Nimble research agent)\n"
    "• `docs: <library + topic> [site:docs.example.com]` or `docs: <url>` → current docs saved to docs/vendor/\n"
    "• `data: <what rows you need> [schema=path] [out=data/file.json]` → dataset with a source on every row\n"
    "• `tally` → my counts for the run receipt"
)


def split_command(text: str, *, from_human: bool = False) -> tuple[str, str]:
    """Commands are explicit: `ask:`, `docs:`, `data:` or a [question] tag. Other text is a note (no web search,
    no reply), except a human's question. In BAND Desktop every agent's closing remark reaches Scout as a reply, so
    an agent's "Data verified …" must not start a dataset build."""
    tag, rest = parse_tagged(text)
    if tag in ("question", "blocking-question"):
        return "ask", rest
    if tag == "tally-request":
        return "tally", rest
    body = (rest if tag else text).strip()
    m = re.match(r"^(ask|docs|data)\s*:\s*(.*)$", body, re.I | re.S)
    if m:
        return m.group(1).lower(), m.group(2).strip()
    if from_human:
        m = re.match(r"^(ask|docs|data)\s+(.*)$", body, re.I | re.S)
        if m:
            return m.group(1).lower(), m.group(2).strip()
    if re.fullmatch(r"(tally|help)[.!]?", body, re.I):
        return body.lower().rstrip(".!"), ""
    return ("ask", body) if from_human and "?" in body else ("note", body)


def workspace() -> Path:
    ws = os.environ.get("ONSEN_WORKSPACE")
    path = Path(ws).expanduser() if ws else state_dir("scout-output")
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_answer(ans: ResearchAnswer, asker: str) -> str:
    conf = ans.best_confidence if ans.confident else "low"
    lines = [
        f"[answer] for={asker.replace(' ', '_')} confidence={conf} claims={len(ans.claims)} sources={len(ans.sources)}",
        clip(ans.content.strip(), 2200),
    ]
    if not ans.confident:
        lines.append(
            "⚠️ The web didn't settle this. Go with the most reasonable assumption, write it down in the "
            f"plan, and keep going. {NAMES['napguard']} will put this question in the one batch the human sees."
        )
    stats = ans.stats or {}
    lines.append(
        f"_Nimble research agent · {stats.get('searches', 0)} searches · {stats.get('page_reads', 0)} pages read · "
        f"{ans.seconds:.0f}s · run {ans.run_id}_"
    )
    return "\n".join(lines)


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    today = date.today().isoformat()
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        row = {k: v for k, v in row.items() if v not in (None, "")}
        if not row.get("source_url"):
            continue  # every row must carry its evidence
        row_id = row.get("id") or slugify(f"{row.get('name', '')}-{row.get('city', '')}")
        if row_id in seen:
            continue
        seen.add(row_id)
        if isinstance(row.get("country"), str):
            row["country"] = row["country"].strip().upper()[:2]
        out.append({"id": row_id, **{k: v for k, v in row.items() if k != "id"}, "verified_on": row.get("verified_on", today)})
    return out


class ScoutAdapter(SimpleAdapter[Any]):
    def __init__(self, nimble: NimbleScout | None = None):
        super().__init__()
        self.nimble = nimble or NimbleScout()

    async def on_message(self, msg: PlatformMessage, tools: Any, history: Any, participants_msg: str | None,
                         contacts_msg: str | None, *, is_session_bootstrap: bool, room_id: str) -> None:
        text = command_text(msg.content)
        cmd, arg = split_command(text, from_human=str(msg.sender_type or "").lower() == "user")
        asker = msg.sender_name or "teammate"
        reply_to = [msg.sender_id]
        state = JsonState("scout", room_id, {"answered": 0, "escalated": 0, "docs": 0, "data": 0, "failed": 0})
        try:
            if cmd == "note":
                await tools.no_reply("not a question or command; nothing to look up")
            elif cmd == "help" or (cmd == "ask" and not arg):
                await tools.send_message(HELP, mentions=reply_to)
            elif cmd == "tally":
                d = state.data
                await tools.send_message(
                    f"[tally] agent=scout answered={d['answered']} escalated={d['escalated']} "
                    f"docs={d['docs']} data={d['data']} failed={d['failed']}",
                    mentions=reply_to,
                )
            elif cmd == "docs":
                await self._docs(arg, tools, reply_to, state)
            elif cmd == "data":
                await self._data(arg, tools, reply_to, state)
            else:
                await self._ask(arg, asker, tools, reply_to, state)
        except Exception as exc:  # noqa: BLE001 - always answer the asker, never leave them hanging
            logger.exception("Scout failed on %r", text)
            state.data["failed"] += 1
            await tools.send_message(
                f"[answer] for={asker} confidence=none error=true\nI couldn't get that from the web: {clip(str(exc), 300)}. "
                f"Try rephrasing, or ask {NAMES['napguard']} to batch it for the human.",
                mentions=reply_to,
            )
        finally:
            state.save()

    async def _ask(self, question: str, asker: str, tools: Any, reply_to: list[str], state: JsonState) -> None:
        kv = parse_kv(question)
        effort = kv.get("effort")
        await tools.send_event(content=f"Asking Nimble's research agent: {clip(question, 200)}", message_type="tool_call",
                               metadata={"tool": "nimble.agents.run", "use_case": "research"})
        ans = await self.nimble.research(question, effort=effort)
        await tools.send_event(content=f"Nimble answered with {len(ans.claims)} graded claims ({ans.best_confidence} best).",
                               message_type="tool_result", metadata={"run_id": ans.run_id, "overall": ans.overall_confidence})
        mentions = list(reply_to)
        if ans.confident:
            state.data["answered"] += 1
        else:
            state.data["escalated"] += 1
            mentions.append(NAMES["napguard"])
        body = format_answer(ans, asker)
        try:
            await tools.send_message(body, mentions=mentions)
        except ValueError:  # Nap Guard not in this room
            await tools.send_message(body, mentions=reply_to)

    async def _docs(self, arg: str, tools: Any, reply_to: list[str], state: JsonState) -> None:
        url_match = URL_RE.search(arg)
        site = SITE_RE.search(arg)
        query = SITE_RE.sub("", URL_RE.sub("", arg)).strip() or arg
        await tools.send_event(content=f"Fetching current docs via Nimble: {clip(arg, 200)}", message_type="tool_call",
                               metadata={"tool": "nimble.search+extract"})
        result = await self.nimble.docs(query, url=url_match.group(0) if url_match else None,
                                        domain=site.group(1) if site else None)
        out_dir = workspace() / "docs" / "vendor"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{slugify(result.title or query)}.md"
        out_path.write_text(
            f"<!-- fetched by Scout via Nimble on {date.today().isoformat()} from {result.url} -->\n\n{result.markdown}"
        )
        state.data["docs"] += 1
        alts = "\n".join(f"• {a['title']} — {a['url']}" for a in result.alternatives) or "• (none)"
        await tools.send_message(
            f"[docs] saved={out_path.relative_to(workspace()) if out_path.is_relative_to(workspace()) else out_path} "
            f"source={result.url}\n**{result.title}** ({len(result.markdown):,} chars of current docs). "
            f"Read it before writing code against this API.\nOther sources:\n{alts}",
            mentions=reply_to,
        )

    async def _data(self, arg: str, tools: Any, reply_to: list[str], state: JsonState) -> None:
        kv = parse_kv(arg)
        request = re.sub(r"\b(schema|out|effort)=\S+", "", arg).strip()
        out_rel = kv.get("out") or "data/dataset.json"
        done = state.data.setdefault("datasets", {})
        if out_rel in done and not kv.get("refresh"):
            prev = done[out_rel]
            await tools.send_message(
                f"[data] rows={prev['rows']} duplicate=true saved={out_rel}\nThat dataset is already built for this room "
                f"(at {prev['at']}), so I'm not running Nimble again or overwriting it. Add `refresh=true` to rebuild it.",
                mentions=reply_to,
            )
            return
        schema_path = Path(kv.get("schema") or os.environ.get("ONSEN_DEFAULT_SCHEMA",
                                                             REPO_ROOT / "specs" / "capyfinder.spot.schema.json"))
        if not schema_path.is_absolute():
            schema_path = (REPO_ROOT / schema_path).resolve()
        schema = json.loads(schema_path.read_text())
        await tools.send_event(content=f"Building a dataset with Nimble: {clip(request, 200)}", message_type="tool_call",
                               metadata={"tool": "nimble.agents.run", "use_case": "dataset_building", "schema": schema_path.name})
        # Nimble's dataset agent occasionally comes back empty for a few minutes at a time (runs 6 and 7: 0% of cells
        # filled, no sources), so retry with a growing pause; each attempt is about a minute.
        attempts, min_rows = int(os.environ.get("ONSEN_DATA_ATTEMPTS", "3")), int(os.environ.get("ONSEN_DATA_MIN_ROWS", "5"))
        pause = float(os.environ.get("ONSEN_DATA_RETRY_PAUSE_S", "30"))
        for attempt in range(1, attempts + 1):
            result: DatasetResult = await self.nimble.dataset(request, schema, effort=kv.get("effort"))
            rows = normalize_rows(result.rows)
            if len(rows) >= min_rows or attempt == attempts:
                break
            await tools.send_event(content=f"Nimble returned {len(rows)} sourced rows; asking again",
                                   message_type="tool_call", metadata={"tool": "nimble.agents.run", "attempt": attempt + 1})
            await asyncio.sleep(pause * attempt)
        # Every row carries every field the schema defines ("" when the web had nothing), so the data is uniform.
        item_props = (((schema.get("properties") or {}).get(next(iter(schema.get("properties") or {"": 0})), {})
                       .get("items") or {}).get("properties") or {})
        for row in rows:
            for field in item_props:
                row.setdefault(field, "")
        out_path = workspace() / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
        out_path.with_suffix(".sources.json").write_text(
            json.dumps({"trust": result.trust, "sources": result.sources}, indent=2, ensure_ascii=False, default=str)
        )
        state.data["data"] += 1
        from datetime import datetime, timezone

        if len(rows) >= min_rows:  # a dataset too thin to build on can be asked for again
            done[out_rel] = {"rows": len(rows), "at": datetime.now(timezone.utc).strftime("%H:%M UTC")}
        sample = "\n".join(
            f"• {r.get('name')} — {r.get('city')}, {r.get('country')} ({r.get('type', '?')}) · {r.get('source_url')}"
            for r in rows[:5]
        )
        await tools.send_message(
            f"[data] rows={len(rows)} dropped_without_source={len(result.rows) - len(rows)} saved={kv.get('out') or 'data/dataset.json'}\n"
            f"Every row carries a source_url; sources and confidence are in the matching .sources.json file.\n{sample}\n"
            f"_Nimble dataset agent · {result.seconds:.0f}s_",
            mentions=reply_to,
        )


def main() -> None:
    load_env()
    run_agent(build_agent("scout", ScoutAdapter()))


if __name__ == "__main__":
    main()
