"""Odkazy v alertech — affiliate a vlastní web."""
from __future__ import annotations

from datetime import date

from collectors.base import FareObservation
from notify.links import aviasales_link, flight_link, offer_page_link

SITE = "https://nestuj-cestuj.cz"


def fare(source: str = "travelpayouts", **kwargs) -> FareObservation:
    defaults = dict(
        source=source, origin="PRG", destination="MNL",
        depart_date=date(2027, 3, 14), return_date=date(2027, 3, 28),
        price=11980.0, currency="CZK",
    )
    return FareObservation(**{**defaults, **kwargs}).with_czk(11980.0)


def test_aviasales_odkaz_ma_spravny_format():
    link = aviasales_link(fare(), marker="654321")
    assert "/search/PRG1403MNL28031" in link
    assert "marker=654321" in link


def test_jednosmerny_odkaz_nema_datum_zpet():
    link = aviasales_link(fare(return_date=None), marker="1")
    assert "/search/PRG1403MNL1?" in link


def test_ryanair_vede_na_ryanair():
    obs = fare(source="ryanair", deep_link="https://www.ryanair.com/cz/cs/trip")
    assert "ryanair.com" in flight_link(obs, marker="654321")


def test_univerzalni_stranka_kdyz_destinace_nema_vlastni():
    url = offer_page_link(fare(), SITE, destination_page_url=None)
    assert url.startswith(f"{SITE}/nabidka/?")
    assert "iata=MNL" in url
    assert "cena=11980" in url
    assert "utm_source=telegram" in url


def test_vlastni_stranka_dostane_prednost():
    url = offer_page_link(
        fare(), SITE, destination_page_url=f"{SITE}/destinace/filipiny/"
    )
    assert url.startswith(f"{SITE}/destinace/filipiny/?")
    assert "nabidka" not in url
    assert "utm_medium=alert" in url
