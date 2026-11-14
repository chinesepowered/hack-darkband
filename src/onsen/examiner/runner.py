"""Run sealed scenarios against a live app, the way a user (or an API client) would.

Deterministic: Claude is only consulted for `judge` steps. Failures are reported
as behavior ("filtering by JP returned a spot in CA"), never as the scenario
script, so builders fix the product instead of the test.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from .models import Check, HttpRequest, Scenario, ScenarioResult, WebStep

Judge = Callable[[str, str], Awaitable[tuple[bool, str]]]

VAR_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)((?:\|[a-z_]+)*)\}")
PATH_TOKEN_RE = re.compile(r"\[(\d+)\]|([^.\[\]]+)")
STEP_TIMEOUT_MS = int(os.environ.get("ONSEN_STEP_TIMEOUT_MS", "6000"))

FILTERS = {
    "lower": lambda s: s.lower(),
    "upper": lambda s: s.upper(),
    "strip": lambda s: s.strip(),
    "url": lambda s: __import__("urllib.parse", fromlist=["quote"]).quote(s, safe=""),
    "first_word": lambda s: (s.split() or [""])[0],
}


class ScenarioFailure(Exception):
    """Raised with a short, behavioral description of what a user would notice."""


class ExamError(ScenarioFailure):
    """The scenario itself is broken (a capture or variable that can't resolve): an exam bug, not a product bug."""


# ---------- helpers ----------

def substitute(text: str | None, env: dict[str, Any]) -> str | None:
    """Insert captured values: {name}, with optional filters {name|lower|url}."""
    if text is None:
        return None

    def repl(m: re.Match[str]) -> str:
        key, filters = m.group(1), [f for f in m.group(2).split("|") if f]
        if key not in env:
            raise ExamError(f"needed a value ({key}) from an earlier response, but it never appeared")
        value = str(env[key])
        for f in filters:
            value = FILTERS.get(f, lambda s: s)(value)
        return value

    return VAR_RE.sub(repl, text)


def get_path(obj: Any, dotted: str | None) -> Any:
    if not dotted:
        return obj
    if dotted.strip() == "length":
        items = as_items(obj)
        return len(items) if items is not None else _MISSING
    cur = obj
    for idx, key in PATH_TOKEN_RE.findall(dotted.strip()):
        if idx:
            if not isinstance(cur, list) or int(idx) >= len(cur):
                return _MISSING
            cur = cur[int(idx)]
        else:
            if not isinstance(cur, dict) or key not in cur:
                return _MISSING
            cur = cur[key]
    return cur


class _Missing:
    def __repr__(self) -> str:
        return "<missing>"


_MISSING = _Missing()


def compare(actual: Any, op: str | None, expected: str | None) -> bool:
    op = op or "eq"
    if op == "exists":
        return actual is not _MISSING and actual is not None
    if actual is _MISSING:
        return False
    a = "" if actual is None else (json.dumps(actual) if isinstance(actual, (dict, list)) else str(actual))
    e = "" if expected is None else str(expected)
    if op == "eq":
        return a.strip().lower() == e.strip().lower()
    if op == "ne":
        return a.strip().lower() != e.strip().lower()
    if op == "contains":  # case-insensitive like eq: acceptance checks are about what a user sees
        return e.lower() in a.lower()
    if op == "icontains":
        return e.lower() in a.lower()
    if op == "not_icontains":
        return e.lower() not in a.lower()
    if op in ("gte", "lte"):
        try:
            av, ev = float(re.sub(r"[^\d.\-]", "", a)), float(e)
        except ValueError:
            return False
        return av >= ev if op == "gte" else av <= ev
    if op == "regex":
        return re.search(e, a) is not None
    return False


def as_items(payload: Any) -> list[Any] | None:
    """A JSON list, or the single list inside an envelope like {"items": [...]}."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        lists = [v for v in payload.values() if isinstance(v, list)]
        if len(lists) == 1:
            return lists[0]
    return None


def apply_captures(spec: str | None, payload: Any, env: dict[str, Any]) -> None:
    if not spec:
        return
    for part in spec.split(";"):
        if "=" not in part:
            continue
        name, path = (s.strip() for s in part.split("=", 1))
        value = get_path(payload, path)
        if value is _MISSING or value is None:
            raise ExamError(f"the response had no value at {path}")
        env[name] = value


def describe(check: Check, value: str | None) -> str:
    target = f"{check.field} {check.op or 'eq'} {value!r}" if check.field else f"{check.op or 'eq'} {value!r}"
    return target


# ---------- HTTP ----------

async def run_http_request(client: httpx.AsyncClient, req: HttpRequest, env: dict[str, Any]) -> None:
    path = substitute(req.path, env) or "/"
    body = substitute(req.body_json, env)
    label = f"{req.method} {path}"
    try:
        resp = await client.request(req.method, path, content=body,
                                    headers={"content-type": "application/json"} if body else None)
    except httpx.HTTPError as exc:
        raise ScenarioFailure(f"{label} could not be reached ({type(exc).__name__})") from exc
    text = resp.text
    try:
        payload: Any = resp.json()
    except (json.JSONDecodeError, ValueError):
        payload = _MISSING

    for check in req.checks:
        value = substitute(check.value, env)
        t = check.type
        if t == "status":
            if resp.status_code != (check.number or 200):
                raise ScenarioFailure(f"{label} returned HTTP {resp.status_code}, expected {check.number}")
            continue
        if t in ("body_contains", "body_not_contains"):
            found = (value or "").lower() in text.lower()
            if found != (t == "body_contains"):
                raise ScenarioFailure(f"{label} {'did not include' if t == 'body_contains' else 'unexpectedly included'} {value!r}")
            continue
        if t == "header_contains":
            header = resp.headers.get(check.field or "", "")
            if (value or "").lower() not in header.lower():
                raise ScenarioFailure(f"{label} header {check.field} was {header!r}, expected it to contain {value!r}")
            continue
        if payload is _MISSING:
            raise ScenarioFailure(f"{label} did not return JSON (HTTP {resp.status_code})")
        if t == "json_type":
            wants_list = (value or "").strip().lower() in ("list", "array")
            ok = isinstance(payload, list) if wants_list else isinstance(payload, dict)
            if not ok:
                raise ScenarioFailure(f"{label} returned a JSON {type(payload).__name__}, expected a {value}")
            continue
        if t == "field":
            actual = get_path(payload, check.field)
            if not compare(actual, check.op, value):
                raise ScenarioFailure(f"{label}: {check.field} was {actual!r}, expected {describe(check, value)}")
            continue
        if t == "has_fields":
            fields = [f.strip() for f in (value or "").split(",") if f.strip()]
            targets = as_items(payload) if isinstance(payload, list) else [payload]
            for i, item in enumerate(targets or []):
                # Presence, not emptiness: a contract field may legitimately be "" (e.g. "may be empty").
                missing = [f for f in fields if get_path(item, f) in (_MISSING, None)]
                if missing:
                    raise ScenarioFailure(f"{label}: item {i + 1} is missing {', '.join(missing)}")
            continue
        items = as_items(payload)
        if items is None:
            raise ScenarioFailure(f"{label} did not return a list")
        if t == "min_items" and len(items) < (check.number or 0):
            raise ScenarioFailure(f"{label} returned {len(items)} items, expected at least {check.number}")
        if t == "max_items" and len(items) > (check.number or 0):
            raise ScenarioFailure(f"{label} returned {len(items)} items, expected at most {check.number}")
        if t in ("every_item", "some_item", "no_item"):
            hits = [compare(get_path(it, check.field), check.op, value) for it in items]
            if t == "every_item" and not all(hits):
                bad = items[hits.index(False)]
                shown = get_path(bad, check.field)
                raise ScenarioFailure(f"{label}: expected every item to have {describe(check, value)}, "
                                      f"but one had {check.field}={shown!r}")
            if t == "some_item" and not any(hits):
                raise ScenarioFailure(f"{label}: no item had {describe(check, value)}")
            if t == "no_item" and any(hits):
                raise ScenarioFailure(f"{label}: an item had {describe(check, value)}, which should never happen")
    apply_captures(req.capture, payload if payload is not _MISSING else None, env)


# ---------- Web ----------

def _locator(page: Any, st: WebStep, env: dict[str, Any]) -> Any:
    if st.testid:
        return page.get_by_test_id(substitute(st.testid, env))
    if st.role:
        name = substitute(st.name, env)
        return page.get_by_role(st.role, name=name) if name else page.get_by_role(st.role)
    if st.label:
        return page.get_by_label(substitute(st.label, env) or "", exact=False)
    if st.text:
        return page.get_by_text(substitute(st.text, env) or "", exact=False)
    raise ScenarioFailure("a step had nothing to act on")


async def _count_between(locator: Any, lo: int | None, hi: int | None) -> int:
    deadline = time.monotonic() + STEP_TIMEOUT_MS / 1000
    while True:
        n = await locator.count()
        if (lo is None or n >= lo) and (hi is None or n <= hi):
            return n
        if time.monotonic() > deadline:
            return n
        await asyncio.sleep(0.2)


async def run_web_step(page: Any, base_url: str, st: WebStep, env: dict[str, Any], judge: Judge | None) -> str | None:
    """Returns "skipped" for judge steps without a judge; raises ScenarioFailure on failure."""
    from playwright.async_api import Error as PWError
    from playwright.async_api import expect

    a = st.action
    value = substitute(st.value, env)
    try:
        if a == "goto":
            await page.goto(base_url.rstrip("/") + (substitute(st.path, env) or "/"), wait_until="domcontentloaded")
        elif a == "fill":
            await _locator(page, st, env).first.fill(value or "")
        elif a == "click":
            await _locator(page, st, env).first.click()
        elif a == "press":
            if st.label or st.testid or st.role:
                await _locator(page, st, env).first.press(value or "Enter")
            else:
                await page.keyboard.press(value or "Enter")
        elif a == "select":
            loc = _locator(page, st, env).first
            try:
                await loc.select_option(label=value)
            except PWError:
                await loc.select_option(value=value)
        elif a == "check":
            await _locator(page, st, env).first.check()
        elif a == "uncheck":
            await _locator(page, st, env).first.uncheck()
        elif a == "expect_text":
            text = substitute(st.text, env) or value or ""
            try:
                await expect(page.locator("body")).to_contain_text(text, ignore_case=True, timeout=STEP_TIMEOUT_MS)
            except AssertionError as exc:
                raise ScenarioFailure(f"the page never showed {text!r}") from exc
        elif a == "expect_no_text":
            text = substitute(st.text, env) or value or ""
            try:
                await expect(page.locator("body")).not_to_contain_text(text, ignore_case=True, timeout=STEP_TIMEOUT_MS)
            except AssertionError as exc:
                raise ScenarioFailure(f"the page showed {text!r}, which it shouldn't") from exc
        elif a == "expect_count":
            n = await _count_between(_locator(page, st, env), st.min, st.max)
            if (st.min is not None and n < st.min) or (st.max is not None and n > st.max):
                what = st.testid or (f"{st.role} {st.name or ''}".strip() if st.role else st.text or st.label)
                raise ScenarioFailure(f"expected between {st.min} and {st.max} of {what!r} on the page, found {n}")
        elif a == "expect_visible":
            loc = _locator(page, st, env).first
            try:
                await expect(loc).to_be_visible(timeout=STEP_TIMEOUT_MS)
            except AssertionError as exc:
                # <option> text and similar are never "visible" to Playwright; being on the page is enough.
                if not (st.text and not st.role and not st.testid and await loc.count() > 0):
                    what = st.testid or st.name or st.text or st.label
                    raise ScenarioFailure(f"{what!r} never became visible") from exc
        elif a == "expect_url_contains":
            deadline = time.monotonic() + STEP_TIMEOUT_MS / 1000
            while (value or "") not in page.url:
                if time.monotonic() > deadline:
                    raise ScenarioFailure(f"the address bar showed {page.url!r}, expected it to contain {value!r}")
                await asyncio.sleep(0.2)
        elif a == "expect_link":
            name = substitute(st.name, env) or substitute(st.text, env) or ""
            links = page.get_by_role("link", name=name) if name else page.get_by_role("link")
            n = await _count_between(links, 1, None)
            if n < 1:
                raise ScenarioFailure(f"there was no link named {name!r}")
            href = await links.first.get_attribute("href") or ""
            if value and value.lower() not in href.lower():
                raise ScenarioFailure(f"the {name!r} link pointed to {href!r}, expected it to contain {value!r}")
        elif a == "wait_ms":
            await page.wait_for_timeout(int(value or "300"))
        elif a == "judge":
            if judge is None:
                return "skipped"
            claim = substitute(st.text, env) or ""
            body = await page.inner_text("body")
            ok, reason = await judge(claim, body[:12000])
            if not ok:
                raise ScenarioFailure(f"a careful user would not agree that {claim!r}: {reason}")
        else:
            raise ScenarioFailure(f"unknown step {a}")
    except PWError as exc:
        what = st.testid or st.label or st.name or st.text or st.path or a
        raise ScenarioFailure(f"couldn't {a} {what!r} ({str(exc).splitlines()[0][:120]})") from exc
    return None


# ---------- orchestration ----------

def localize(base_url: str) -> str:
    """Inside Docker on macOS/Windows, the host's localhost is host.docker.internal."""
    alias = os.environ.get("ONSEN_LOCALHOST_ALIAS")
    if alias:
        base_url = re.sub(r"//(localhost|127\.0\.0\.1)(?=[:/]|$)", f"//{alias}", base_url)
    return base_url


async def run_scenarios(base_url: str, scenarios: list[Scenario], *, judge: Judge | None = None,
                        repeats: int = 1) -> list[ScenarioResult]:
    base_url = localize(base_url)
    results: list[ScenarioResult] = []
    needs_browser = any(s.kind == "web" for s in scenarios)
    pw = browser = None
    try:
        if needs_browser:
            from playwright.async_api import async_playwright

            pw = await async_playwright().start()
            browser = await pw.chromium.launch(
                executable_path=os.environ.get("ONSEN_CHROMIUM_PATH") or None, args=["--no-sandbox"]
            )
        async with httpx.AsyncClient(base_url=base_url, timeout=15, follow_redirects=True) as client:
            for _ in range(max(1, repeats)):
                for sc in scenarios:
                    results.append(await _run_one(sc, client, browser, base_url, judge))
    finally:
        if browser is not None:
            await browser.close()
        if pw is not None:
            await pw.stop()
    return results


async def _run_one(sc: Scenario, client: httpx.AsyncClient, browser: Any, base_url: str,
                   judge: Judge | None) -> ScenarioResult:
    t0 = time.monotonic()
    env: dict[str, Any] = {}
    skipped = False
    try:
        for req in sc.requests:
            await run_http_request(client, req, env)
        if sc.kind == "web":
            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(STEP_TIMEOUT_MS)
            try:
                for st in sc.steps:
                    if await run_web_step(page, base_url, st, env, judge) == "skipped":
                        skipped = True
            finally:
                await context.close()
        return ScenarioResult(id=sc.id, stage=sc.stage, story=sc.story, passed=True, skipped=skipped,
                              seconds=time.monotonic() - t0)
    except ExamError as exc:
        return ScenarioResult(id=sc.id, stage=sc.stage, story=sc.story, passed=False, invalid=True,
                              observed=f"exam error: {exc}", seconds=time.monotonic() - t0)
    except ScenarioFailure as exc:
        return ScenarioResult(id=sc.id, stage=sc.stage, story=sc.story, passed=False, observed=str(exc),
                              seconds=time.monotonic() - t0)
    except Exception as exc:  # noqa: BLE001 - an exam must never crash the Examiner
        return ScenarioResult(id=sc.id, stage=sc.stage, story=sc.story, passed=False,
                              observed=f"the check itself broke ({type(exc).__name__}: {str(exc)[:120]})",
                              seconds=time.monotonic() - t0)


def satisfaction(results: list[ScenarioResult]) -> tuple[int, int, float]:
    """Share of valid scenarios passed. Scenarios that broke in their own setup (exam bugs) and judge-only
    passes without a judge don't count either way."""
    counted = [r for r in results if not (r.passed and r.skipped) and not r.invalid]
    passed = sum(1 for r in counted if r.passed)
    total = len(counted)
    return passed, total, (passed / total if total else 0.0)
