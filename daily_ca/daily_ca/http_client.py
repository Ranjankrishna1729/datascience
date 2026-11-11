from __future__ import annotations

import time
from typing import Optional

import requests

from .config import Settings


class PoliteSession:
    """HTTP helper with identifying User-Agent and inter-request delay."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-IN,en;q=0.8",
            }
        )
        self._last_request_at: Optional[float] = None

    def _throttle(self) -> None:
        delay = self.settings.request_delay_seconds
        if delay <= 0:
            return
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def get_text(self, url: str) -> str:
        self._throttle()
        resp = self._session.get(url, timeout=self.settings.request_timeout_seconds)
        self._last_request_at = time.monotonic()
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding
        return resp.text