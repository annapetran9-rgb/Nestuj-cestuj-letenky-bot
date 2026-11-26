"""SQLite backend — pro lokální vývoj a testy. Žádné závislosti."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from collectors.base import FareObservation
from config import ROOT
from storage.base import REPEAT_INTERVAL_HOURS, skip_repeats


class SQLiteStore:
    def __init__(self, path: str = "flight_deals.db") -> None:
        self.path = path
        # ':memory:' se používá v testech
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")

    def init_schema(self) -> None:
        schema = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
        self.conn.executescript(schema)
        self.conn.commit()

    def _recent_fingerprints(self) -> dict[str, datetime]:
        """fingerprint → čas posledního uložení, za posledních N hodin."""
        since = (
            datetime.now(timezone.utc) - timedelta(hours=REPEAT_INTERVAL_HOURS)
        ).isoformat()
        cursor = self.conn.execute(
            """SELECT fingerprint, MAX(observed_at) FROM fare_observations
               WHERE observed_at >= ? GROUP BY fingerprint""",
            (since,),
        )
        return {row[0]: datetime.fromisoformat(row[1]) for row in cursor.fetchall()}

    def add_observations(self, observations: Sequence[FareObservation]) -> int:
        fresh = skip_repeats(observations, self._recent_fingerprints())
        rows = [
            (
                o.source, o.origin, o.destination,
                o.depart_date.isoformat(),
                o.return_date.isoformat() if o.return_date else None,
                o.depart_month, o.price, o.currency, o.price_czk,
                o.airline, o.flight_number, o.transfers, o.deep_link,
                o.fingerprint(), o.observed_at.isoformat(),
            )
            for o in fresh
        ]
        if not rows:
            return 0
        self.conn.executemany(
            """INSERT INTO fare_observations
               (source, origin, destination, depart_date, return_date, depart_month,
                price, currency, price_czk, airline, flight_number, transfers,
                deep_link, fingerprint, observed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def route_prices(
        self, origin: str, destination: str, depart_month: str,
        days_back: int = 90, exclude_recent_hours: int = 0,
    ) -> list[float]:
        now = datetime.now(timezone.utc)
        since = (now - timedelta(days=days_back)).isoformat()
        until = (now - timedelta(hours=exclude_recent_hours)).isoformat()
        cursor = self.conn.execute(
            """SELECT price_czk FROM fare_observations
               WHERE origin = ? AND destination = ? AND depart_month = ?
                 AND observed_at >= ? AND observed_at < ?
                 AND price_czk IS NOT NULL""",
            (origin, destination, depart_month, since, until),
        )
        return [row[0] for row in cursor.fetchall()]

    def recent_observations(self, hours: int = 24) -> list[FareObservation]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        cursor = self.conn.execute(
            """SELECT source, origin, destination, depart_date, return_date, price, currency, price_czk, airline, flight_number, transfers, deep_link, observed_at
               FROM fare_observations
               WHERE observed_at >= ?
               ORDER BY observed_at DESC""",
            (since,),
        )
        return [self._row_to_observation(r) for r in cursor.fetchall()]

    @staticmethod
    def _row_to_observation(row) -> FareObservation:
        """Řádek z DB → FareObservation. Jediné místo, kde se to mapuje zpět."""
        return FareObservation(
            source=row[0],
            origin=row[1],
            destination=row[2],
            depart_date=date.fromisoformat(row[3]),
            return_date=date.fromisoformat(row[4]) if row[4] else None,
            price=float(row[5]),
            currency=row[6],
            price_czk=float(row[7]) if row[7] is not None else None,
            airline=row[8],
            flight_number=row[9],
            transfers=int(row[10] or 0),
            deep_link=row[11],
            observed_at=datetime.fromisoformat(row[12]),
        )

    def observation_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM fare_observations").fetchone()[0]

    def route_summary(self, limit: int = 20) -> list[tuple[str, str, int, float]]:
        cursor = self.conn.execute(
            """SELECT origin, destination, COUNT(*) AS n, MIN(price_czk) AS lowest
               FROM fare_observations
               GROUP BY origin, destination
               ORDER BY n DESC LIMIT ?""",
            (limit,),
        )
        return [(r[0], r[1], r[2], r[3] or 0.0) for r in cursor.fetchall()]

    def was_alerted(self, fingerprint: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM alerts_sent WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()
        return row is not None

    def mark_alerted(
        self, fingerprint: str, origin: str, destination: str,
        price_czk: float | None, score: float, is_error_fare: bool, channel: str,
    ) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO alerts_sent
               (fingerprint, origin, destination, price_czk, score,
                is_error_fare, channel, sent_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                fingerprint, origin, destination, price_czk, score,
                1 if is_error_fare else 0, channel,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.commit()

    def destination_page_url(self, destination: str) -> str | None:
        row = self.conn.execute(
            "SELECT url FROM destination_pages WHERE destination = ?", (destination,)
        ).fetchone()
        return row[0] if row and row[0] else None

    def close(self) -> None:
        self.conn.close()
