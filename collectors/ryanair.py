"""Ryanair — veřejné fare-finder API (farfnd/v4).

Stejné API, které pohání hledání na ryanair.com. Nepotřebuje token ani proxy,
takže je to nejlevnější zdroj dat, jaký pro Evropu existuje. Vrací nejnižší
cenu na den a trasu, ne celou dostupnost.

Dvě věci stojí za zapamatování:

* Nechat `destination` prázdný znamená „kamkoliv" — to je režim, kterým se
  objevují nabídky, o kterých člověk nevěděl, že existují.
* Ceny jsou jen pro dospělého a bez zavazadel. Do alertu patří poznámka,
  že s kufrem to bude dražší.

Pravidlo z CLAUDE.md: `fetch_*` sahá na síť, `parse_*` je čistá funkce.
Parser se testuje proti `tests/fixtures/ryanair_oneway.json`.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from collectors.base import FareObservation, InvalidObservation
from collectors.http import FetchError, get_json

log = logging.getLogger(__name__)

SOURCE = "ryanair"
BASE_URL = "https://services-api.ryanair.com/farfnd/v4"
PAGE_LIMIT = 500
MAX_PAGES = 20


def _parse_dt(raw: str | None) -> date | None:
    """'2027-01-21T17:05:00' → date(2027, 1, 21)"""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        log.warning("nerozpoznané datum z Ryanairu: %r", raw)
        return None


def booking_link(origin: str, destination: str, depart: date,
                 return_date: date | None = None) -> str:
    """Odkaz do vyhledávání na ryanair.com.

    Ryanair affiliate program nemá, takže tady žádná provize není — monetizace
    těchto nabídek jde přes ubytování na vlastním webu (viz CLAUDE.md).
    """
    params = [
        "adults=1",
        f"dateOut={depart.isoformat()}",
        f"originIata={origin}",
        f"destinationIata={destination}",
        f"isReturn={'true' if return_date else 'false'}",
    ]
    if return_date:
        params.append(f"dateIn={return_date.isoformat()}")
    return "https://www.ryanair.com/cz/cs/trip/flights/select?" + "&".join(params)


def _leg_to_fields(leg: dict[str, Any]) -> dict[str, Any] | None:
    """Vytáhne z jednoho úseku ('outbound' nebo 'inbound') to, co potřebujeme."""
    departure = (leg.get("departureAirport") or {}).get("iataCode")
    arrival = (leg.get("arrivalAirport") or {}).get("iataCode")
    day = _parse_dt(leg.get("departureDate"))
    price_block = leg.get("price") or {}
    if not (departure and arrival and day):
        return None
    return {
        "origin": departure.upper(),
        "destination": arrival.upper(),
        "day": day,
        "price": price_block.get("value"),
        "currency": (price_block.get("currencyCode") or "EUR").upper(),
        "flight_number": leg.get("flightNumber"),
    }


def parse_one_way_fares(payload: dict[str, Any]) -> list[FareObservation]:
    """Rozparsuje odpověď `/oneWayFares` na pozorování."""
    observations: list[FareObservation] = []
    for fare in payload.get("fares") or []:
        leg = _leg_to_fields(fare.get("outbound") or {})
        if leg is None or leg["price"] is None:
            continue
        try:
            observations.append(
                FareObservation(
                    source=SOURCE,
                    origin=leg["origin"],
                    destination=leg["destination"],
                    depart_date=leg["day"],
                    price=float(leg["price"]),
                    currency=leg["currency"],
                    airline="FR",
                    flight_number=leg["flight_number"],
                    transfers=0,
                    deep_link=booking_link(
                        leg["origin"], leg["destination"], leg["day"]
                    ),
                )
            )
        except (InvalidObservation, TypeError, ValueError) as exc:
            log.warning("přeskakuji vadný záznam z Ryanairu: %s", exc)
    return observations


def parse_round_trip_fares(payload: dict[str, Any]) -> list[FareObservation]:
    """Rozparsuje odpověď `/roundTripFares`.

    Cena je součet obou úseků, který Ryanair posílá v `summary.price`.
    """
    observations: list[FareObservation] = []
    for fare in payload.get("fares") or []:
        outbound = _leg_to_fields(fare.get("outbound") or {})
        inbound = _leg_to_fields(fare.get("inbound") or {})
        if outbound is None or inbound is None:
            continue
        summary_price = ((fare.get("summary") or {}).get("price") or {}).get("value")
        if summary_price is None:
            continue
        try:
            observations.append(
                FareObservation(
                    source=SOURCE,
                    origin=outbound["origin"],
                    destination=outbound["destination"],
                    depart_date=outbound["day"],
                    return_date=inbound["day"],
                    price=float(summary_price),
                    currency=outbound["currency"],
                    airline="FR",
                    transfers=0,
                    deep_link=booking_link(
                        outbound["origin"], outbound["destination"],
                        outbound["day"], inbound["day"],
                    ),
                )
            )
        except (InvalidObservation, TypeError, ValueError) as exc:
            log.warning("přeskakuji vadný záznam z Ryanairu: %s", exc)
    return observations


def fetch_one_way_fares(
    origin: str,
    date_from: date,
    date_to: date,
    destination: str | None = None,
    price_limit: float | None = None,
    currency: str = "EUR",
    market: str = "cs-cz",
) -> list[FareObservation]:
    """Najde nejnižší jednosměrné ceny z letiště.

    `destination=None` znamená „kamkoliv v síti Ryanairu".
    """
    collected: list[FareObservation] = []
    offset = 0

    for _ in range(MAX_PAGES):
        params = {
            "departureAirportIataCode": origin.upper(),
            "arrivalAirportIataCode": destination.upper() if destination else None,
            "outboundDepartureDateFrom": date_from.isoformat(),
            "outboundDepartureDateTo": date_to.isoformat(),
            "priceValueTo": price_limit,
            "currency": currency,
            "market": market,
            "language": "cs",
            "limit": PAGE_LIMIT,
            "offset": offset,
        }
        try:
            payload = get_json(f"{BASE_URL}/oneWayFares", params=params)
        except FetchError as exc:
            log.warning("Ryanair %s: %s", origin, exc)
            break

        page = parse_one_way_fares(payload)
        collected.extend(page)

        next_page = payload.get("nextPage")
        if not page or next_page is None or len(page) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT

    log.info("Ryanair %s → %d pozorování", origin, len(collected))
    return collected


def fetch_round_trip_fares(
    origin: str,
    destination: str,
    outbound_from: date,
    outbound_to: date,
    inbound_from: date,
    inbound_to: date,
    price_limit: float | None = None,
    currency: str = "EUR",
    market: str = "cs-cz",
) -> list[FareObservation]:
    """Najde nejnižší zpáteční ceny na konkrétní trase."""
    params = {
        "departureAirportIataCode": origin.upper(),
        "arrivalAirportIataCode": destination.upper(),
        "outboundDepartureDateFrom": outbound_from.isoformat(),
        "outboundDepartureDateTo": outbound_to.isoformat(),
        "inboundDepartureDateFrom": inbound_from.isoformat(),
        "inboundDepartureDateTo": inbound_to.isoformat(),
        "priceValueTo": price_limit,
        "currency": currency,
        "market": market,
        "language": "cs",
        "limit": PAGE_LIMIT,
        "offset": 0,
    }
    try:
        payload = get_json(f"{BASE_URL}/roundTripFares", params=params)
    except FetchError as exc:
        log.warning("Ryanair %s→%s: %s", origin, destination, exc)
        return []
    return parse_round_trip_fares(payload)
