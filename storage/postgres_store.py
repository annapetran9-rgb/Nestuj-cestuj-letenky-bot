"""Postgres backend — pro běh v GitHub Actions (Neon, Supabase).

Vyžaduje `psycopg[binary]`. Neon i Supabase v bezplatném tarifu občas
potřebují pár sekund na probuzení, proto se připojení opakuje.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from collectors.base import FareObservation
from config import ROOT
from storage.base import REPEAT_INTERVAL_HOURS, skip_repeats

log = logging.getLogger(__name__)


class PostgresStore:
    def __init__(self, dsn: str, connect_retries: int = 3) -> None:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Postgres backend potřebuje psycopg: pip install 'psycopg[binary]'"
            ) from exc

        self._psycopg = psycopg
        last_error: Exception | None = None
        for attempt in range(connect_retries):
            try:
                self.conn = psycopg.connect(dsn, autocommit=True)
                break
            except Exception as exc:  # noqa: BLE001 — probouzení free tieru
                last_error = exc
                log.warning("databáze se probouzí, zkouším znovu (%s)", exc)
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"nepodařilo se připojit k databázi: {last_error}")

    def init_schema(self) -> None:
        schema = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
        # SQLite používá INTEGER PRIMARY KEY pro autoincrement, Postgres potřebuje
        # GENERATED. Jediný rozdíl mezi oběma backendy.
        schema = schema.replace(
            "id              INTEGER PRIMARY KEY",
            "id              BIGGENERATED_PLACEHOLDER",
        ).replace(
            "id              BIGGENERATED_PLACEHOLDER",
            "id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY",
        )
        with self.conn.cursor() as cur:
            cur.execute(schema)

    def _recent_fingerprints(self) -> dict[str, datetime]:
        """fingerprint → čas posledního uložení, za posledních N hodin."""
        since = (
            datetime.now(timezone.utc) - timedelta(hours=REPEAT_INTERVAL_HOURS)
        ).isoformat()
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT fingerprint, MAX(observed_at) FROM fare_observations
                   WHERE observed_at >= %s GROUP BY fingerprint""",
                (since,),
            )
            return {r[0]: datetime.fromisoformat(r[1]) for r in cur.fetchall()}

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
        with self.conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO fare_observations
                   (source, origin, destination, depart_date, return_date,
                    depart_month, price, currency, price_czk, airline,
                    flight_number, transfers, deep_link, fingerprint, observed_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                rows,
            )
        return len(rows)

    def route_prices(
        self, origin: str, destination: str, depart_month: str,
        days_back: int = 90, exclude_recent_hours: int = 0,
    ) -> list[float]:
        now = datetime.now(timezone.utc)
        since = (now - timedelta(days=days_back)).isoformat()
        until = (now - timedelta(hours=exclude_recent_hours)).isoformat()
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT price_czk FROM fare_observations
                   WHERE origin = %s AND destination = %s AND depart_month = %s
                     AND observed_at >= %s AND observed_at < %s
                     AND price_czk IS NOT NULL""",
                (origin, destination, depart_month, since, until),
            )
            return [r[0] for r in cur.fetchall()]

    def recent_observations(self, hours: int = 24) -> list[FareObservation]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT source, origin, destination, depart_date, return_date, price, currency, price_czk, airline, flight_number, transfers, deep_link, observed_at
                   FROM fare_observations
                   WHERE observed_at >= %s
                   ORDER BY observed_at DESC""",
                (since,),
            )
            return [self._row_to_observation(r) for r in cur.fetchall()]

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
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fare_observations")
            return cur.fetchone()[0]

    def route_summary(self, limit: int = 20) -> list[tuple[str, str, int, float]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT origin, destination, COUNT(*) AS n, MIN(price_czk)
                   FROM fare_observations GROUP BY origin, destination
                   ORDER BY n DESC LIMIT %s""",
                (limit,),
            )
            return [(r[0], r[1], r[2], r[3] or 0.0) for r in cur.fetchall()]

    def was_alerted(self, fingerprint: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM alerts_sent WHERE fingerprint = %s", (fingerprint,)
            )
            return cur.fetchone() is not None

    def mark_alerted(
        self, fingerprint: str, origin: str, destination: str,
        price_czk: float | None, score: float, is_error_fare: bool, channel: str,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO alerts_sent
                   (fingerprint, origin, destination, price_czk, score,
                    is_error_fare, channel, sent_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (fingerprint) DO NOTHING""",
                (
                    fingerprint, origin, destination, price_czk, score,
                    1 if is_error_fare else 0, channel,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def destination_page_url(self, destination: str) -> str | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT url FROM destination_pages WHERE destination = %s",
                (destination,),
            )
            row = cur.fetchone()
            return row[0] if row and row[0] else None

    def close(self) -> None:
        self.conn.close()
