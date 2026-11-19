from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DEFAULT_CHROMA_DIR = PROJECT_ROOT / "data" / "chroma"
DEFAULT_COLLECTION = "pib_releases"

# PIB Delhi English listing (reg=3 ≈ Delhi/HQ feed on allRel).
DEFAULT_LISTING_URL = "https://www.pib.gov.in/allRel.aspx?reg=3&lang=1"
DEFAULT_BASE_URL = "https://www.pib.gov.in"

# Akamai on pib.gov.in rejects non-browser User-Agents (403). Use a desktop
# Chrome UA so listing/article GETs succeed; identify educational purpose in
# docs / Accept headers instead.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_REQUEST_DELAY_SECONDS = 1.5
DEFAULT_REQUEST_TIMEOUT_SECONDS = 45.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_CHARS = 1800


@dataclass(frozen=True)
class Settings:
    listing_url: str
    base_url: str
    user_agent: str
    request_delay_seconds: float
    request_timeout_seconds: float
    max_retries: int
    persist_dir: Path
    collection_name: str
    max_chars: int


def load_settings() -> Settings:
    persist = os.getenv("PIB_SCRAPE_PERSIST_DIR") or str(DEFAULT_CHROMA_DIR)
    persist_path = Path(persist)
    if not persist_path.is_absolute():
        persist_path = Path.cwd() / persist_path
    return Settings(
        listing_url=os.getenv("PIB_SCRAPE_LISTING_URL", DEFAULT_LISTING_URL),
        base_url=os.getenv("PIB_SCRAPE_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        user_agent=os.getenv("PIB_SCRAPE_USER_AGENT", DEFAULT_USER_AGENT),
        request_delay_seconds=float(
            os.getenv(
                "PIB_SCRAPE_REQUEST_DELAY_SECONDS",
                str(DEFAULT_REQUEST_DELAY_SECONDS),
            )
        ),
        request_timeout_seconds=float(
            os.getenv(
                "PIB_SCRAPE_REQUEST_TIMEOUT_SECONDS",
                str(DEFAULT_REQUEST_TIMEOUT_SECONDS),
            )
        ),
        max_retries=int(os.getenv("PIB_SCRAPE_MAX_RETRIES", str(DEFAULT_MAX_RETRIES))),
        persist_dir=persist_path,
        collection_name=os.getenv("PIB_SCRAPE_COLLECTION", DEFAULT_COLLECTION),
        max_chars=int(os.getenv("PIB_SCRAPE_MAX_CHARS", str(DEFAULT_MAX_CHARS))),
    )
