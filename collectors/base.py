"""Společný datový formát všech collectorů.

Invariant projektu: collector vrací výhradně `FareObservation`. Nic neukládá,
nic nehodnotí, nic neposílá. Díky tomu lze přidat nový zdroj dat bez zásahu
do zbytku systému.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from typing import Iterable

IATA_RE = re.compile(r"^[A-Z]{3}$")


class InvalidObservation(ValueError):
    """Collector vrátil záznam, který neprošel validací."""


@dataclass(frozen=True, slots=True)
class FareObservation:
    """Jedno pozorování ceny letenky v konkrétním okamžiku.

    Pozorování je fakt o minulosti: „v tento moment tento zdroj ukazoval tuto
    cenu". Nikdy se needituje, jen se přidávají nová. Z téhle historie se pak
    počítá, co je normální cena a co je akce.
    """

    source: str                      # "ryanair", "travelpayouts", ...
    origin: str                      # IATA odletového letiště
    destination: str                 # IATA cílového letiště
    depart_date: date
    price: float                     # v originální měně
    currency: str                    # ISO 4217, velkými písmeny
    return_date: date | None = None  # None = jednosměrný
    airline: str | None = None
    flight_number: str | None = None
    transfers: int = 0
    deep_link: str | None = None     # odkaz na konkrétní nabídku, bez affiliate
    price_czk: float | None = None   # přepočet kurzem ČNB ke dni pozorování
    observed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        if not IATA_RE.match(self.origin):
            raise InvalidObservation(f"neplatný IATA kód odletu: {self.origin!r}")
        if not IATA_RE.match(self.destination):
            raise InvalidObservation(f"neplatný IATA kód cíle: {self.destination!r}")
        if self.origin == self.destination:
            raise InvalidObservation("odlet a cíl jsou stejné letiště")
        if not (self.price > 0):
            raise InvalidObservation(f"cena musí být větší než nula: {self.price!r}")
        if len(self.currency) != 3 or not self.currency.isupper():
            raise InvalidObservation(f"neplatná měna: {self.currency!r}")
        if self.return_date is not None and self.return_date < self.depart_date:
            raise InvalidObservation("návrat je dřív než odlet")
        if self.transfers < 0:
            raise InvalidObservation("počet přestupů nemůže být negativní")

    @property
    def is_round_trip(self) -> bool:
        return self.return_date is not None

    @property
    def route(self) -> str:
        """Trasa bez datumů — klíč pro cenovou historii."""
        return f"{self.origin}-{self.destination}"

    @property
    def depart_month(self) -> str:
        """Měsíc odletu, 'YYYY-MM'. Srpen a únor nejsou srovnatelné ceny,
        takže se baseline počítá zvlášť po měsících."""
        return self.depart_date.strftime("%Y-%m")

    @property
    def nights(self) -> int | None:
        if self.return_date is None:
            return None
        return (self.return_date - self.depart_date).days

    def fingerprint(self) -> str:
        """Stabilní identifikátor nabídky pro deduplikaci odeslaných alertů.

        Nezahrnuje `observed_at` ani zdroj — stejná nabídka nalezená dvakrát
        nebo dvěma zdroji se nemá posílat dvakrát.
        """
        parts = [
            self.origin,
            self.destination,
            self.depart_date.isoformat(),
            self.return_date.isoformat() if self.return_date else "oneway",
            f"{round(self.price, 2):.2f}",
            self.currency,
        ]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]

    def with_czk(self, price_czk: float) -> "FareObservation":
        return replace(self, price_czk=round(price_czk, 2))


def dedupe(observations: Iterable[FareObservation]) -> list[FareObservation]:
    """Odstraní duplicitní nabídky, ponechá tu s nižší cenou."""
    best: dict[str, FareObservation] = {}
    for obs in observations:
        key = obs.fingerprint()
        current = best.get(key)
        if current is None or obs.price < current.price:
            best[key] = obs
    return list(best.values())
