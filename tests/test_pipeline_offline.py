"""Celý řetězec nasucho: fixture → databáze → vyhodnocení → zpráva.

Nesahá na síť. Tenhle test je pojistka, že se jednotlivé díly po změně
pořád domluví — a zároveň ukázka, jak systém funguje jako celek.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from analysis.baseline import compute_baseline
from analysis.scoring import score_fare
from collectors.base import FareObservation, dedupe
from collectors.fx import to_czk
from collectors.ryanair import parse_one_way_fares
from collectors.travelpayouts import parse_prices
from notify.format import format_telegram
from notify.links import flight_link, offer_page_link

KURZY = {"CZK": 1.0, "EUR": 24.315, "USD": 21.043}
SITE = "https://nestuj-cestuj.cz"


def test_sber_z_obou_zdroju_a_ulozeni(store, load_fixture):
    """Dva zdroje, jeden formát, jedna databáze."""
    observations = [
        *parse_one_way_fares(load_fixture("ryanair_oneway.json")),
        *parse_prices(load_fixture("travelpayouts_prices.json"), marker="654321"),
    ]
    observations = [
        obs.with_czk(to_czk(obs.price, obs.currency, KURZY) or 0)
        for obs in dedupe(observations)
    ]

    assert store.add_observations(observations) == 5

    # Ryanair z EUR přepočtený do CZK
    bergamo = [o for o in observations if o.destination == "BGY"][0]
    assert bergamo.price_czk == round(16.99 * 24.315, 2)

    # Travelpayouts už v CZK
    manila = [o for o in observations if o.destination == "MNL"][0]
    assert manila.price_czk == 11980.0


def test_akce_se_najde_az_po_nasbirani_historie(store):
    """Stejná cena: bez historie nic, s historií akce."""
    depart = date.today() + timedelta(days=90)
    month = depart.strftime("%Y-%m")

    def fare(price: float, observed_at=None) -> FareObservation:
        return FareObservation(
            source="travelpayouts", origin="PRG", destination="MNL",
            depart_date=depart, return_date=depart + timedelta(days=14),
            price=price, currency="CZK", price_czk=price,
            observed_at=observed_at or datetime.now(timezone.utc),
        )

    kandidat = fare(10500)

    # Fáze 1: prázdná databáze → robot nemá co tvrdit
    baseline = compute_baseline(store.route_prices("PRG", "MNL", month))
    assert baseline is None
    assert score_fare(kandidat, baseline).is_deal is False

    # Fáze 2: měsíc sběru (40 pozorování okolo 14–17 tisíc)
    historie = [
        fare(price, datetime.now(timezone.utc) - timedelta(days=d))
        for d, price in enumerate(
            [14000, 15000, 16000, 14500, 17000, 15500, 14200, 16500] * 5
        )
    ]
    store.add_observations(historie)

    baseline = compute_baseline(store.route_prices("PRG", "MNL", month))
    assert baseline is not None and baseline.is_reliable

    verdict = score_fare(kandidat, baseline)
    assert verdict.is_deal is True

    # Zpráva se vyrenderuje a obsahuje oba odkazy
    message = format_telegram(
        kandidat, verdict,
        flight_link(kandidat, "654321"),
        offer_page_link(kandidat, SITE, store.destination_page_url("MNL")),
    )
    assert "Manila" in message
    assert "10 500 Kč" in message
    assert "marker=654321" in message
    assert "/nabidka/" in message
    assert "ověř" in message

    # Deduplikace: po odeslání se stejná nabídka neposílá znovu
    assert store.was_alerted(kandidat.fingerprint()) is False
    store.mark_alerted(
        kandidat.fingerprint(), "PRG", "MNL", 10500.0,
        verdict.score, verdict.is_error_fare, "telegram",
    )
    assert store.was_alerted(kandidat.fingerprint()) is True
