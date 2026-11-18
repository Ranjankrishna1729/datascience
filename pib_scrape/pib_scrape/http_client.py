from __future__ import annotations

import time
from typing import Mapping, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Settings


class PoliteSession:
    """HTTP helper: browser-like headers, throttle, retries."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-IN,en;q=0.9",
                # Non-standard; documents educational intent without tripping CDN UA filters.
                "X-Research-Purpose": (
                    "UPSC-LLM-educational; "
                    "https://github.com/Ranjankrishna1729/datascience"
                ),
            }
        )
        retry = Retry(
            total=settings.max_retries,
            connect=settings.max_retries,
            read=settings.max_retries,
            status=settings.max_retries,
            backoff_factor=1.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST", "HEAD"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        self._last_request_at: Optional[float] = None

    def absolute(self, url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return urljoin(self.settings.base_url + "/", url.lstrip("/"))

    def _throttle(self) -> None:
        delay = self.settings.request_delay_seconds
        if delay <= 0 or self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def get_text(self, url: str, *, referer: str | None = None) -> str:
        headers = {}
        if referer:
            headers["Referer"] = referer
        self._throttle()
        resp = self._session.get(
            self.absolute(url),
            timeout=self.settings.request_timeout_seconds,
            headers=headers or None,
        )
        self._last_request_at = time.monotonic()
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding
        return resp.text

    def post_form(
        self,
        url: str,
        data: Mapping[str, str],
        *,
        referer: str | None = None,
    ) -> str:
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if referer:
            headers["Referer"] = referer
        self._throttle()
        abs_url = self.absolute(url)
        resp = self._session.post(
            abs_url,
            data=dict(data),
            timeout=self.settings.request_timeout_seconds,
            headers=headers,
        )
        self._last_request_at = time.monotonic()
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding
        return resp.text
