"""Helpers for exam checks: `from onsen_exam_kit import service, mock_reset, mock_log, ...`.

The service under test and the task's mock web, as onsen-exam starts them (SERVICE_URL, MOCK_URL, MOCK_ADMIN_TOKEN).
Every mock admin request carries the admin header: a request without it is answered 404, as if the route didn't
exist, and a check that forgets it fails on its own mistake. See the mock web's README for what each call does.
"""
from __future__ import annotations

import os
from typing import Any, Iterable

import httpx


def service(path: str = "") -> str:
    """The service's URL, with `path` appended."""
    return os.environ["SERVICE_URL"].rstrip("/") + path


def mock(method: str, path: str, json: Any = None, timeout: float = 10) -> httpx.Response:
    """One admin request to the mock web; raises on an error status (a 404 means a wrong path or a missing token)."""
    r = httpx.request(method, os.environ["MOCK_URL"].rstrip("/") + path, json=json, timeout=timeout,
                      headers={"X-Mock-Admin": os.environ["MOCK_ADMIN_TOKEN"]})
    r.raise_for_status()
    return r


def mock_reset(epoch: int = 0) -> None:
    mock("POST", "/_mock/reset", {"epoch": epoch})


def mock_epoch(epoch: int) -> None:
    mock("POST", "/_mock/epoch", {"epoch": epoch})


def mock_fault(provider: str, methods: Iterable[str], mode: str, **extra: Any) -> None:
    mock("POST", "/_mock/faults", {"provider": provider, "methods": list(methods), "mode": mode, **extra})


def mock_weather(on: bool) -> None:
    mock("POST", "/_mock/weather", {"on": bool(on)})


def mock_log() -> list[dict[str, Any]]:
    """Every provider call since the last reset, in order."""
    return mock("GET", "/_mock/log").json()["calls"]
