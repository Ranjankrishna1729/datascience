from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from CWD if present (optional).
load_dotenv()

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "daily_ca.sqlite3"
SCHEMA_PATH = PACKAGE_ROOT / "schema.sql"

SOURCE_INSIGHTS = "insightsias"

DEFAULT_CATEGORY_URL = "https://www.insightsonindia.com/category/current-affairs-2/"
DEFAULT_USER_AGENT = (
    "UPSC-DailyCA-Bot/0.1 "
    "(+https://github.com/Ranjankrishna1729/datascience; educational personal use)"
)


@dataclass(frozen=True)
class Settings:
    database_url: str
    user_agent: str
    request_delay_seconds: float
    request_timeout_seconds: float
    insights_category_url: str

    @property
    def sqlite_path(self) -> Path:
        """Resolve sqlite file path from DATABASE_URL or plain path."""
        url = self.database_url
        if url.startswith("sqlite:///"):
            raw = url[len("sqlite:///") :]
            path = Path(raw)
            if not path.is_absolute():
                path = Path.cwd() / path
            return path
        # Allow bare path for convenience.
        path = Path(url)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path


def load_settings() -> Settings:
    db = os.getenv("DAILY_CA_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db:
        db = f"sqlite:///{DEFAULT_DB_PATH}"
    return Settings(
        database_url=db,
        user_agent=os.getenv("DAILY_CA_USER_AGENT", DEFAULT_USER_AGENT),
        request_delay_seconds=float(os.getenv("DAILY_CA_REQUEST_DELAY_SECONDS", "1.5")),
        request_timeout_seconds=float(os.getenv("DAILY_CA_REQUEST_TIMEOUT_SECONDS", "30")),
        insights_category_url=os.getenv(
            "DAILY_CA_INSIGHTS_CATEGORY_URL", DEFAULT_CATEGORY_URL
        ),
    )