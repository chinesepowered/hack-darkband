"""Nimble wrappers used by the Scout: research answers, fresh docs, and datasets.

Every answer keeps Nimble's trust report (per-claim sources and confidence) so
the factory can decide whether the web settled a question or a human must.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from nimble_python import AsyncNimble

CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


@dataclass
class Claim:
    callout: int
    confidence: str
    urls: list[str]
    primary: bool


@dataclass
class ResearchAnswer:
    content: str
    overall_confidence: str
    claims: list[Claim]
    sources: list[dict[str, str]]
    stats: dict[str, Any]
    run_id: str
    seconds: float

    @property
    def best_confidence(self) -> str:
        ranks = [CONFIDENCE_RANK.get(c.confidence, 0) for c in self.claims]
        best = max(ranks, default=CONFIDENCE_RANK.get(self.overall_confidence, 0))
        return {v: k for k, v in CONFIDENCE_RANK.items()}[best]

    @property
    def confident(self) -> bool:
        """The web settled it: at least one claim is high-confidence and backed by
        a primary source, or Nimble's overall grade is medium or better."""
        strong = any(c.confidence == "high" and c.primary for c in self.claims)
        return strong or CONFIDENCE_RANK.get(self.overall_confidence, 0) >= 1


@dataclass
class DocsResult:
    url: str
    title: str
    markdown: str
    alternatives: list[dict[str, str]] = field(default_factory=list)


@dataclass
class DatasetResult:
    rows: list[dict[str, Any]]
    trust: dict[str, Any] | None
    sources: list[dict[str, str]]
    raw: dict[str, Any]
    seconds: float


class NimbleScout:
    """Thin async facade over the Nimble SDK with polling and timeouts."""

    def __init__(self, api_key: str | None = None, *, effort: str | None = None, timeout_s: float | None = None):
        self.client = AsyncNimble(api_key=api_key or os.environ["NIMBLE_API_KEY"])
        self.effort = effort or os.environ.get("ONSEN_NIMBLE_EFFORT", "low")
        self.timeout_s = timeout_s or float(os.environ.get("ONSEN_NIMBLE_TIMEOUT_S", "900"))

    async def _run_agent(self, *, prompt: str, use_case: str, effort: str | None = None,
                         output_schema: dict[str, Any] | None = None) -> tuple[dict[str, Any], float]:
        t0 = time.monotonic()
        kwargs: dict[str, Any] = {"input": prompt, "use_case": use_case, "effort": effort or self.effort}
        if output_schema:
            kwargs["output_schema"] = output_schema
        run = await self.client.agents.run(**kwargs)
        agent_id = run.web_search_agent_id
        status = run
        while getattr(status, "is_active", False):
            if time.monotonic() - t0 > self.timeout_s:
                raise TimeoutError(f"Nimble run {run.id} still running after {self.timeout_s:.0f}s")
            await asyncio.sleep(4)
            status = await self.client.agents.runs.get(run.id, agent_id=agent_id)
        if status.status != "completed":
            raise RuntimeError(f"Nimble run {run.id} ended as {status.status}: {getattr(status, 'error', None)}")
        result = await self.client.agents.runs.result(run.id, agent_id=agent_id)
        return result.model_dump(mode="json"), time.monotonic() - t0

    async def research(self, question: str, *, effort: str | None = None) -> ResearchAnswer:
        raw, seconds = await self._run_agent(prompt=question, use_case="research", effort=effort)
        out = raw.get("output") or {}
        trust = out.get("trust") or {}
        claims = [
            Claim(
                callout=int(c.get("callout") or 0),
                confidence=str(c.get("confidence") or "low"),
                urls=[x.get("url") for x in (c.get("citations") or []) if x.get("url")],
                primary=any((x.get("source_type") == "primary") for x in (c.get("citations") or [])),
            )
            for c in (trust.get("claims") or [])
        ]
        content = out.get("content")
        if not isinstance(content, str):
            content = json.dumps(content, indent=2, ensure_ascii=False)
        return ResearchAnswer(
            content=content or "",
            overall_confidence=str(trust.get("confidence") or "low"),
            claims=claims,
            sources=[{"url": s.get("url", ""), "title": s.get("title", "")} for s in (out.get("sources") or [])],
            stats=raw.get("stats") or {},
            run_id=str((raw.get("run") or {}).get("id") or ""),
            seconds=seconds,
        )

    async def docs(self, query: str, *, url: str | None = None, domain: str | None = None) -> DocsResult:
        alternatives: list[dict[str, str]] = []
        if not url:
            base: dict[str, Any] = {"query": query, "max_results": 5, "search_depth": "lite"}
            if domain:
                found = await self.client.search(**base, include_domains=[domain])
                results = [r.model_dump() for r in (found.results or [])]
            else:
                found = await self.client.search(**base, focus="coding")
                results = [r.model_dump() for r in (found.results or [])]
                if not results or min(_docs_rank(r)[0] for r in results) > 0:
                    # The coding focus favors snippets (gists, Q&A); a general search usually finds the official docs.
                    general = await self.client.search(**base)
                    seen = {r.get("url") for r in results}
                    results += [r for r in (x.model_dump() for x in (general.results or [])) if r.get("url") not in seen]
            if not results:
                raise LookupError(f"No docs found for {query!r}")
            ranked = sorted(results, key=_docs_rank)
            url = ranked[0]["url"]
            alternatives = [{"url": r["url"], "title": r.get("title") or ""} for r in ranked[1:4]]
        page = await self.client.extract.run(url=url, formats=["markdown"], markdown_backend="main_content")
        data = page.model_dump().get("data") or {}
        markdown = data.get("markdown") or ""
        if not markdown.strip():
            raise LookupError(f"Extract returned no markdown for {url}")
        title = _first_heading(markdown) or urlparse(url).path.rsplit("/", 1)[-1] or url
        return DocsResult(url=url, title=title, markdown=markdown, alternatives=alternatives)

    async def dataset(self, request: str, schema: dict[str, Any], *, effort: str | None = None) -> DatasetResult:
        raw, seconds = await self._run_agent(prompt=request, use_case="dataset_building",
                                             effort=effort, output_schema=schema)
        out = raw.get("output") or {}
        rows = _extract_rows(out.get("content"))
        return DatasetResult(
            rows=rows,
            trust=out.get("trust"),
            sources=[{"url": s.get("url", ""), "title": s.get("title", "")} for s in (out.get("sources") or [])],
            raw=raw,
            seconds=seconds,
        )


DOC_HINTS = ("docs.", "developer.", "developers.", "readthedocs", "/docs", "/reference", "/api/", "/library/")
LOW_SIGNAL = ("medium.com", "dev.to", "geeksforgeeks", "w3schools", "quora", "gist.github.com", "stackoverflow.com")


def _docs_rank(result: dict[str, Any]) -> tuple[int, int]:
    """Official documentation first, then source repositories, then everything else, then low-signal pages
    (a gist outranked docs.python.org before this ordering)."""
    url = (result.get("url") or "").lower()
    if any(h in url for h in LOW_SIGNAL):
        tier = 3
    elif any(h in url for h in DOC_HINTS):
        tier = 0
    elif "github.com" in url:
        tier = 1
    else:
        tier = 2
    return (tier, int((result.get("metadata") or {}).get("position") or 99))


def _first_heading(markdown: str) -> str | None:
    for line in markdown.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()[:120] or None
    return None


def _extract_rows(content: Any) -> list[dict[str, Any]]:
    """Nimble may return rows as a list, as {"rows"/"data"/"items": [...]}, or as JSON text."""
    if isinstance(content, str):
        text = content.strip()
        fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
        if fenced:
            text = fenced.group(1)
        try:
            content = json.loads(text)
        except json.JSONDecodeError:
            return []
    if isinstance(content, list):
        return [r for r in content if isinstance(r, dict)]
    if isinstance(content, dict):
        # Dataset schemas wrap rows in one array property (e.g. {"spots": [...]}).
        for key in ("rows", "data", "items", "results", "records"):
            if isinstance(content.get(key), list):
                return [r for r in content[key] if isinstance(r, dict)]
        for value in content.values():
            if isinstance(value, list) and value and all(isinstance(r, dict) for r in value):
                return value
        return [content]
    return []


def slugify(text: str, limit: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:limit].strip("-") or "item"
