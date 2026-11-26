#!/usr/bin/env python3
"""Hlavní vstupní bod robota.

    python3 pipeline.py collect --origins PRG,BRQ,OSR --dry-run
    python3 pipeline.py collect --origins PRG,BRQ,OSR,VIE,KRK
    python3 pipeline.py stats
    python3 pipeline.py analyze --dry-run
    python3 pipeline.py analyze --notify

POZOR: `analyze --notify` nemá smysl zapínat dřív než po 2–4 týdnech sběru.
Bez vlastní historie robot nepozná akci od běžné ceny a posílal by nesmysly.
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from datetime import date, timedelta

from analysis.airports import DEFAULT_ORIGINS
from analysis.baseline import compute_baseline
from analysis.scoring import score_fare
from collectors import fx, ryanair, travelpayouts
from collectors.base import FareObservation, dedupe
from config import Settings, load_dotenv
from notify import telegram
from notify.format import format_plain, format_telegram
from notify.links import flight_link, offer_page_link
from storage.base import Store, open_store

log = logging.getLogger("pipeline")

#: Jak daleko do budoucnosti hledat.
SEARCH_WINDOW_DAYS = 180
#: Nejbližší odlet, který má smysl posílat (pod tím se to nedá zorganizovat).
MIN_DAYS_AHEAD = 7


def _add_czk(observations: list[FareObservation]) -> list[FareObservation]:
    """Doplní přepočet do CZK kurzem ČNB."""
    rates = fx.get_rates()
    result = []
    for obs in observations:
        czk = fx.to_czk(obs.price, obs.currency, rates)
        result.append(obs.with_czk(czk) if czk is not None else obs)
    return result


def collect(settings: Settings, origins: list[str], dry_run: bool) -> int:
    """Projde zdroje a uloží pozorování."""
    today = date.today()
    date_from = today + timedelta(days=MIN_DAYS_AHEAD)
    date_to = today + timedelta(days=SEARCH_WINDOW_DAYS)

    collected: list[FareObservation] = []

    for origin in origins:
        # Ryanair, režim „kamkoliv" — tady se objevují nabídky,
        # o kterých člověk nevěděl, že existují.
        collected.extend(
            ryanair.fetch_one_way_fares(
                origin=origin, date_from=date_from, date_to=date_to, currency="EUR",
            )
        )

        # Travelpayouts: co uživatelé Aviasales reálně našli za levné
        if settings.travelpayouts_token:
            collected.extend(
                travelpayouts.fetch_latest_prices(
                    token=settings.travelpayouts_token,
                    origin=origin,
                    marker=settings.travelpayouts_marker,
                )
            )

    collected = _add_czk(dedupe(collected))
    log.info("celkem %d unikátních pozorování", len(collected))

    if dry_run:
        for obs in sorted(collected, key=lambda o: o.price_czk or 1e9)[:40]:
            print(
                f"  {obs.source:14} {obs.origin}→{obs.destination} "
                f"{obs.depart_date} {obs.price_czk or '?':>8} Kč"
            )
        print(f"\n[dry-run] {len(collected)} pozorování by se uložilo")
        return len(collected)

    store = open_store(settings.database_url, settings.sqlite_path)
    try:
        inserted = store.add_observations(collected)
        log.info("uloženo %d pozorování (celkem v DB: %d)",
                 inserted, store.observation_count())
        return inserted
    finally:
        store.close()


def analyze(settings: Settings, notify: bool, hours: int = 24) -> int:
    """Vyhodnotí nedávná pozorování a případně pošle alerty."""
    store: Store = open_store(settings.database_url, settings.sqlite_path)
    sent = 0
    try:
        candidates = store.recent_observations(hours=hours)
        log.info("vyhodnocuji %d pozorování z posledních %d h",
                 len(candidates), hours)

        baselines: dict[tuple[str, str, str], object] = {}
        # Na jednu trasu a termín posíláme jen nejlepší cenu. Kandidáti jsou
        # setřídění od nejnižší ceny, takže první výskyt je ten správný —
        # dvě skoro stejné nabídky na stejný termín jsou pro čtenáře šum.
        seen_trips: set[tuple[str, str, str, str]] = set()

        for obs in sorted(candidates, key=lambda o: o.price_czk or 1e9):
            if obs.price_czk is None:
                continue
            if (obs.depart_date - date.today()).days < MIN_DAYS_AHEAD:
                continue

            trip = (
                obs.origin, obs.destination,
                obs.depart_date.isoformat(),
                obs.return_date.isoformat() if obs.return_date else "oneway",
            )
            if trip in seen_trips:
                continue

            key = (obs.origin, obs.destination, obs.depart_month)
            if key not in baselines:
                # Vynecháme stejné okno, z jakého bereme kandidáty — jinak
                # by si hodnocená nabídka snižovala vlastní laťku.
                baselines[key] = compute_baseline(
                    store.route_prices(
                        obs.origin, obs.destination, obs.depart_month,
                        exclude_recent_hours=hours,
                    )
                )

            verdict = score_fare(
                obs,
                baselines[key],  # type: ignore[arg-type]
                min_history=settings.min_history_observations,
                deal_drop_threshold=settings.deal_drop_threshold,
                error_fare_drop_threshold=settings.error_fare_drop_threshold,
            )
            if not verdict.is_deal:
                continue

            seen_trips.add(trip)
            fingerprint = obs.fingerprint()
            if store.was_alerted(fingerprint):
                continue

            print(format_plain(obs, verdict))

            if verdict.needs_verification:
                print("        ↳ před odesláním ověř cenu (4. milník: SerpApi)")

            if not notify:
                continue

            page_url = offer_page_link(
                obs,
                settings.site_base_url,
                store.destination_page_url(obs.destination),
            )
            message = format_telegram(
                obs, verdict,
                flight_link(obs, settings.travelpayouts_marker),
                page_url,
            )
            if telegram.send_message(
                settings.telegram_bot_token, settings.telegram_chat_id, message
            ):
                store.mark_alerted(
                    fingerprint, obs.origin, obs.destination,
                    obs.price_czk, verdict.score, verdict.is_error_fare, "telegram",
                )
                sent += 1

        if not notify:
            print("\n[dry-run] nic se neposlalo, spusť s --notify")
        else:
            log.info("odesláno %d alertů", sent)
        return sent
    finally:
        store.close()


def stats(settings: Settings) -> None:
    """Co už je nasbírané — kontrola, jestli má smysl zapínat alerty."""
    store = open_store(settings.database_url, settings.sqlite_path)
    try:
        total = store.observation_count()
        print(f"Pozorování v databázi: {total}")
        print(f"Minimum na trasu pro alerty: {settings.min_history_observations}\n")

        rows = store.route_summary(limit=25)
        if not rows:
            print("Zatím nic. Spusť `collect`.")
            return

        print(f"{'trasa':12} {'pozorování':>11} {'nejnižší':>12}")
        print("-" * 37)
        ready = 0
        for origin, destination, count, lowest in rows:
            mark = "✓" if count >= settings.min_history_observations else " "
            ready += 1 if count >= settings.min_history_observations else 0
            print(f"{mark} {origin}→{destination:<8} {count:>11} {lowest:>9.0f} Kč")
        print(f"\nTras s dostatečnou historií: {ready} z {len(rows)}")
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    settings = Settings.from_env()

    parser = argparse.ArgumentParser(
        description="Robot na levné letenky pro Nestůj, cestuj!"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--db", default=None,
        help="cesta k SQLite souboru (ignoruje se, když je DATABASE_URL)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_collect = sub.add_parser("collect", help="posbírat ceny ze zdrojů")
    p_collect.add_argument(
        "--origins", default=",".join(DEFAULT_ORIGINS),
        help="IATA kódy odletových letišť oddělené čárkou",
    )
    p_collect.add_argument("--dry-run", action="store_true",
                           help="jen vypsat, neukládat")

    p_analyze = sub.add_parser("analyze", help="vyhodnotit a případně poslat")
    p_analyze.add_argument("--notify", action="store_true",
                           help="skutečně poslat do Telegramu")
    p_analyze.add_argument("--hours", type=int, default=24)
    p_analyze.add_argument("--dry-run", action="store_true",
                           help="výchozí chování, uvedeno pro přehlednost")

    sub.add_parser("stats", help="co je nasbírané")

    args = parser.parse_args(argv)
    if args.db:
        settings = replace(settings, sqlite_path=args.db)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(name)s: %(message)s",
    )

    if args.command == "collect":
        origins = [o.strip().upper() for o in args.origins.split(",") if o.strip()]
        collect(settings, origins, dry_run=args.dry_run)
    elif args.command == "analyze":
        analyze(settings, notify=args.notify, hours=args.hours)
    elif args.command == "stats":
        stats(settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
