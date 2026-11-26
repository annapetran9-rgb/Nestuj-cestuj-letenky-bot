"""Konfigurace z prostředí. Jediné místo, kde se čtou proměnné prostředí."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent

USER_AGENT = (
    "NestujCestujFareBot/0.1 (+https://nestuj-cestuj.cz; levne-letenky-robot)"
)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    travelpayouts_token: str = ""
    travelpayouts_marker: str = ""
    serpapi_key: str = ""
    database_url: str = ""
    sqlite_path: str = "flight_deals.db"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    brevo_api_key: str = ""
    brevo_list_id: str = ""
    site_base_url: str = "https://nestuj-cestuj.cz"

    # Prahy pro vyhodnocování
    min_history_observations: int = 30
    deal_drop_threshold: float = 0.40
    error_fare_drop_threshold: float = 0.60

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            travelpayouts_token=os.environ.get("TRAVELPAYOUTS_TOKEN", "").strip(),
            travelpayouts_marker=os.environ.get("TRAVELPAYOUTS_MARKER", "").strip(),
            serpapi_key=os.environ.get("SERPAPI_KEY", "").strip(),
            database_url=os.environ.get("DATABASE_URL", "").strip(),
            sqlite_path=os.environ.get("SQLITE_PATH", "flight_deals.db").strip(),
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
            brevo_api_key=os.environ.get("BREVO_API_KEY", "").strip(),
            brevo_list_id=os.environ.get("BREVO_LIST_ID", "").strip(),
            site_base_url=os.environ.get(
                "SITE_BASE_URL", "https://nestuj-cestuj.cz"
            ).strip().rstrip("/"),
            min_history_observations=_env_int("MIN_HISTORY_OBSERVATIONS", 30),
            deal_drop_threshold=_env_float("DEAL_DROP_THRESHOLD", 0.40),
            error_fare_drop_threshold=_env_float("ERROR_FARE_DROP_THRESHOLD", 0.60),
        )


def load_dotenv(path: Path | None = None) -> None:
    """Jednoduchý loader .env, aby nebyla potřeba externí závislost.

    Proměnné už nastavené v prostředí mají přednost (důležité pro GitHub Actions).
    """
    env_path = path or ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
