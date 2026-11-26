"""Parser Travelpayouts Data API."""
from __future__ import annotations

from datetime import date

from collectors.travelpayouts import parse_prices


def test_parsuje_odpoved(load_fixture):
    observations = parse_prices(load_fixture("travelpayouts_prices.json"))

    # Poslední záznam má stejný odlet i cíl — musí se zahodit.
    assert len(observations) == 3

    manila = observations[0]
    assert manila.origin == "PRG"
    assert manila.destination == "MNL"
    assert manila.depart_date == date(2027, 3, 14)
    assert manila.return_date == date(2027, 3, 28)
    assert manila.price == 11980.0
    assert manila.currency == "CZK"
    assert manila.transfers == 1
    assert manila.nights == 14


def test_marker_se_prida_do_odkazu(load_fixture):
    observations = parse_prices(load_fixture("travelpayouts_prices.json"),
                                marker="654321")
    assert "marker=654321" in observations[0].deep_link
    assert observations[0].deep_link.startswith("https://www.aviasales.com/search/")


def test_bez_markeru_zustane_odkaz_cisty(load_fixture):
    observations = parse_prices(load_fixture("travelpayouts_prices.json"))
    assert "marker=" not in observations[0].deep_link


def test_chybova_odpoved():
    assert parse_prices({"success": False, "error": "token je neplatný"}) == []


def test_prazdna_data():
    assert parse_prices({"success": True, "data": []}) == []
