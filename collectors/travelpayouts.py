"""Travelpayouts / Aviasales Data API — světové trasy a monetizace.

Zdroj pro všechno, co neletí Ryanair. Token je bezplatný po registraci do
affiliate sítě a Aviasales u tohoto API nevyžaduje schvalování brandem.

Zásadní vlastnost: **ceny jsou z cache** (2–7 dní podle typu dotazu). Jde o
ceny, které reálně našli uživatelé Aviasales, ne o live dostupnost. Proto:

* je to zdroj *kandidátů*, ne pravdy — před odesláním alertu se cena ověřuje,
* do každého alertu patří čas pozorování a poznámka, že cena nemusí platit.

Live Search API s realtime cenami vyžaduje 50 000 MAU, takže není ve hře.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from collectors.base import FareObservation, InvalidObservation
from collectors.http import FetchError, get_json

log = logging.getLogger(__name__)

SOURCE = "travelpayouts"
BASE_URL = "https://api.travelpayouts.com/aviasales/v3"
AVIASALES_BASE = "https://www.aviasales.com"


def _parse_dt(raw: str | None) -> date | None:
    """'2027-03-14T10:25:00+03:00' nebo '2027-03-14' → date"""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            log.warning("nerozpoznané datum z Travelpayouts: %r", raw)
            return None


def parse_prices(payload: dict[str, Any], marker: str = "") -> list[FareObservation]:
    """Rozparsuje odpověď `/prices_for_dates` nebo `/get_latest_prices`.

    Obě vracejí stejný tvar položek, takže jeden parser stačí.
    """
    if not payload.get("success", True):
        log.warning("Travelpayouts vrátil chybu: %s", payload.get("error"))
        return []

    currency = (payload.get("currency") or "CZK").upper()
    observations: list[FareObservation] = []

    for item in payload.get("data") or []:
        origin = (item.get("origin_airport") or item.get("origin") or "").upper()
        destination = (
            item.get("destination_airport") or item.get("destination") or ""
        ).upper()
        # `/prices_for_dates` posílá `departure_at`, `/get_latest_prices` posílá
        # `depart_date` (ověřeno proti živému API), proto obojí.
        depart = _parse_dt(item.get("departure_at") or item.get("depart_date"))
        return_date = _parse_dt(item.get("return_at") or item.get("return_date"))
        price = item.get("price") or item.get("value")

        if not (origin and destination and depart and price):
            continue

        link = item.get("link") or ""
        deep_link = f"{AVIASALES_BASE}{link}" if link.startswith("/") else link or None
        if deep_link and marker:
            joiner = "&" if "?" in deep_link else "?"
            deep_link = f"{deep_link}{joiner}marker={marker}"

        try:
            observations.append(
                FareObservation(
                    source=SOURCE,
                    origin=origin,
                    destination=destination,
                    depart_date=depart,
                    return_date=return_date,
                    price=float(price),
                    currency=currency,
                    airline=item.get("airline"),
                    flight_number=(
                        f"{item.get('airline') or ''}{item.get('flight_number') or ''}"
                        or None
                    ),
                    transfers=int(
                        item.get("transfers") or item.get("number_of_changes") or 0
                    ),
                    deep_link=deep_link,
                )
            )
        except (InvalidObservation, TypeError, ValueError) as exc:
            log.warning("přeskakuji vadný záznam z Travelpayouts: %s", exc)

    return observations


def fetch_prices_for_dates(
    token: str,
    origin: str,
    destination: str | None = None,
    departure_at: str | None = None,
    return_at: str | None = None,
    one_way: bool = False,
    direct: bool = False,
    currency: str = "czk",
    limit: int = 100,
    sorting: str = "price",
    marker: str = "",
    market: str = "cz",
) -> list[FareObservation]:
    """Nejnižší ceny na trase pro dané období.

    `departure_at` přijímá 'YYYY-MM' (celý měsíc) i 'YYYY-MM-DD' (konkrétní den).
    Měsíční tvar je pro sběr historie výhodnější — jeden dotaz pokryje víc dní.
    """
    if not token:
        log.warning("TRAVELPAYOUTS_TOKEN není nastavený, přeskakuji")
        return []

    params = {
        "origin": origin.upper(),
        "destination": destination.upper() if destination else None,
        "departure_at": departure_at,
        "return_at": return_at,
        "one_way": str(one_way).lower(),
        "direct": str(direct).lower(),
        "currency": currency,
        "limit": limit,
        "page": 1,
        "sorting": sorting,
        "unique": "false",
        "market": market,
        "token": token,
    }
    try:
        payload = get_json(f"{BASE_URL}/prices_for_dates", params=params)
    except FetchError as exc:
        log.warning("Travelpayouts %s→%s: %s", origin, destination, exc)
        return []

    observations = parse_prices(payload, marker=marker)
    log.info(
        "Travelpayouts %s→%s (%s) → %d pozorování",
        origin, destination or "*", departure_at or "-", len(observations),
    )
    return observations


def fetch_latest_prices(
    token: str,
    origin: str,
    destination: str | None = None,
    period_type: str = "year",
    one_way: bool = False,
    currency: str = "czk",
    limit: int = 500,
    marker: str = "",
) -> list[FareObservation]:
    """Nejnižší ceny nalezené uživateli za poslední období.

    Užitečné jako „co je teď levné" průzkum bez znalosti cíle — doplněk
    k režimu „kamkoliv" u Ryanairu.
    """
    if not token:
        log.warning("TRAVELPAYOUTS_TOKEN není nastavený, přeskakuji")
        return []

    params = {
        "origin": origin.upper(),
        "destination": destination.upper() if destination else None,
        "period_type": period_type,
        "one_way": str(one_way).lower(),
        "currency": currency,
        "limit": limit,
        "page": 1,
        "sorting": "price",
        "show_to_affiliates": "true",
        "token": token,
    }
    try:
        payload = get_json(f"{BASE_URL}/get_latest_prices", params=params)
    except FetchError as exc:
        log.warning("Travelpayouts latest %s: %s", origin, exc)
        return []

    return parse_prices(payload, marker=marker)
