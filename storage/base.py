"""Rozhraní pro ukládání dat.

Pipeline mluví jen s `Store`. Díky tomu je přechod SQLite → Postgres
jen otázkou `DATABASE_URL`, bez zásahu do logiky.
"""
from __future__ import annotations

from datetime import date
from typing import Protocol, Sequence, runtime_checkable

from collectors.base import FareObservation


@runtime_checkable
class Store(Protocol):
    """Co musí umět každý backend."""

    def init_schema(self) -> None: ...

    def add_observations(self, observations: Sequence[FareObservation]) -> int:
        """Uloží pozorování. Vrací počet skutečně vložených řádků."""
        ...

    def route_prices(
        self,
        origin: str,
        destination: str,
        depart_month: str,
        days_back: int = 90,
        exclude_recent_hours: int = 0,
    ) -> list[float]:
        """Ceny v CZK na trase a měsíci odletu za posledních N dní.

        Tohle je vstup pro výpočet baseline — jediný dotaz, na kterém
        stojí celá detekce akcí.

        `exclude_recent_hours` vynechá nejnovější pozorování. Je to důležité:
        kdyby se hodnocená nabídka počítala do své vlastní historie, sama by si
        snižovala laťku a výjimečná cena by vypadala jako běžná. Volající sem
        posílá stejné okno, z jakého bere kandidáty.
        """
        ...

    def recent_observations(self, hours: int = 24) -> list[FareObservation]:
        """Pozorování z posledních N hodin — kandidáti na vyhodnocení."""
        ...

    def observation_count(self) -> int: ...

    def route_summary(self, limit: int = 20) -> list[tuple[str, str, int, float]]:
        """(origin, destination, počet pozorování, nejnižší cena) pro `stats`."""
        ...

    def was_alerted(self, fingerprint: str) -> bool: ...

    def mark_alerted(
        self,
        fingerprint: str,
        origin: str,
        destination: str,
        price_czk: float | None,
        score: float,
        is_error_fare: bool,
        channel: str,
    ) -> None: ...

    def destination_page_url(self, destination: str) -> str | None:
        """URL stránky destinace, nebo None když ještě neexistuje."""
        ...

    def close(self) -> None: ...


def open_store(database_url: str = "", sqlite_path: str = "flight_deals.db") -> Store:
    """Vybere backend podle `DATABASE_URL`.

    Prázdné URL → SQLite (lokální vývoj, testy).
    postgres://… → Postgres (GitHub Actions, Neon/Supabase).
    """
    if database_url.startswith(("postgres://", "postgresql://")):
        from storage.postgres_store import PostgresStore

        store = PostgresStore(database_url)
    else:
        from storage.sqlite_store import SQLiteStore

        store = SQLiteStore(sqlite_path)
    store.init_schema()
    return store


def month_key(day: date) -> str:
    return day.strftime("%Y-%m")
