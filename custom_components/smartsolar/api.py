"""Async client for the SmartSolar inverter API."""

from __future__ import annotations

import asyncio
from collections import deque
import json
import time
from typing import Any

import aiohttp

from .const import BASE_URL, MAX_REQUESTS_PER_MINUTE, RATE_LIMIT_BACKOFF_SECONDS


class SmartSolarError(Exception):
    """Base error for the SmartSolar API."""


class SmartSolarConnectionError(SmartSolarError):
    """The API could not be reached."""


class SmartSolarAuthError(SmartSolarError):
    """The API key is missing, invalid or revoked."""


class SmartSolarRateLimitError(SmartSolarError):
    """A request was refused to stay within the API rate limit."""


class SmartSolarApiError(SmartSolarError):
    """The API returned an error message."""


class _RateLimiter:
    """Sliding-window request budget shared by every client using one API key."""

    def __init__(self) -> None:
        self._sent: deque[float] = deque()
        self._blocked_until = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if now < self._blocked_until:
                minutes = int((self._blocked_until - now) // 60) + 1
                raise SmartSolarRateLimitError(
                    f"Paused after a rate-limit response; retrying in ~{minutes} min"
                )
            while self._sent and now - self._sent[0] >= 60:
                self._sent.popleft()
            if len(self._sent) >= MAX_REQUESTS_PER_MINUTE:
                raise SmartSolarRateLimitError(
                    "Local request budget exhausted; skipping this request"
                )
            self._sent.append(now)

    def block(self) -> None:
        self._blocked_until = time.monotonic() + RATE_LIMIT_BACKOFF_SECONDS


# Keyed by API key so the budget survives config entry reloads.
_LIMITERS: dict[str, _RateLimiter] = {}


class SmartSolarClient:
    """Client for one SmartSolar device (API keys are per device)."""

    def __init__(
        self, session: aiohttp.ClientSession, api_key: str, base_url: str = BASE_URL
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._limiter = _LIMITERS.setdefault(api_key, _RateLimiter())

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        body: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        await self._limiter.acquire()
        try:
            async with self._session.request(
                method,
                f"{self._base_url}{path}",
                headers={"X-API-KEY": self._api_key, "Accept": "application/json"},
                params=params,
                json=body,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                status = resp.status
                text = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SmartSolarConnectionError(f"Error talking to SmartSolar: {err}") from err

        try:
            payload = json.loads(text)
        except ValueError:
            payload = None

        error = payload.get("error") if isinstance(payload, dict) else None
        if error and ("rate limit" in error.lower() or "temporarily disabled" in error.lower()):
            self._limiter.block()
            raise SmartSolarRateLimitError(error)
        if status in (401, 403):
            raise SmartSolarAuthError(error or f"Access denied (HTTP {status})")
        if error:
            raise SmartSolarApiError(error)
        if status >= 400 or not isinstance(payload, dict):
            raise SmartSolarApiError(f"Unexpected response (HTTP {status})")
        return payload

    async def get_status(self) -> dict[str, Any]:
        """Return the real-time status block (includes Dev_ID)."""
        payload = await self._request("GET", "/api/inverter/status.php")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise SmartSolarApiError("Status response has no data")
        return data

    async def get_usage(
        self, period: str, date_from: str | None = None, date_to: str | None = None
    ) -> dict[str, Any]:
        """Return the usage report for today, yesterday, this_month, last_month or custom."""
        params = {"period": period}
        if period == "custom":
            params |= {"from": date_from or "", "to": date_to or ""}
        payload = await self._request("GET", "/api/inverter/usage.php", params=params)
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    async def get_faults(self, period: str = "this_month", hide_grid: bool = False) -> list[dict[str, Any]]:
        """Return the list of faults; empty when none were reported."""
        params = {"period": period}
        if hide_grid:
            params["hide_grid"] = "true"
        payload = await self._request("GET", "/api/inverter/fault.php", params=params)
        faults = (payload.get("data") or {}).get("dev_fault")
        return faults if isinstance(faults, list) else []

    async def get_settings(self) -> list[dict[str, Any]]:
        """Return the inverter settings with their allowed options."""
        payload = await self._request("GET", "/api/inverter/isetting.php")
        data = payload.get("data")
        return data if isinstance(data, list) else []

    async def set_setting(self, key: str, value: str) -> None:
        """Send a setting to the inverter. Raises if the inverter rejects it."""
        payload = await self._request(
            "POST", "/api/inverter/isetting.php", body={"key": key, "value": value}
        )
        if notice := payload.get("dev_notice"):
            raise SmartSolarApiError(notice)
