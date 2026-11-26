"""Datový formát a jeho validace."""
from __future__ import annotations

from datetime import date

import pytest

from collectors.base import FareObservation, InvalidObservation, dedupe


def make(**kwargs) -> FareObservation:
    defaults = dict(
        source="test", origin="PRG", destination="BKK",
        depart_date=date(2027, 5, 2), price=9450.0, currency="CZK",
    )
    return FareObservation(**{**defaults, **kwargs})


def test_route_a_mesic():
    obs = make()
    assert obs.route == "PRG-BKK"
    assert obs.depart_month == "2027-05"
    assert obs.is_round_trip is False
    assert obs.nights is None


def test_pocet_noci():
    obs = make(return_date=date(2027, 5, 23))
    assert obs.is_round_trip is True
    assert obs.nights == 21


@pytest.mark.parametrize("kwargs, zprava", [
    ({"origin": "prg"}, "IATA"),
    ({"origin": "PRAHA"}, "IATA"),
    ({"destination": "PRG"}, "stejné letiště"),
    ({"price": 0}, "větší než nula"),
    ({"price": -100}, "větší než nula"),
    ({"currency": "czk"}, "měna"),
    ({"return_date": date(2027, 4, 1)}, "dřív než odlet"),
    ({"transfers": -1}, "negativní"),
])
def test_validace_odmita_nesmysly(kwargs, zprava):
    with pytest.raises(InvalidObservation, match=zprava):
        make(**kwargs)


def test_fingerprint_je_stabilni_a_nezavisi_na_zdroji():
    a = make(source="ryanair")
    b = make(source="travelpayouts")
    assert a.fingerprint() == b.fingerprint()


def test_fingerprint_se_meni_s_cenou():
    assert make(price=9450).fingerprint() != make(price=9451).fingerprint()


def test_dedupe_necha_nizsi_cenu():
    result = dedupe([make(), make(destination="MNL"), make()])
    assert len(result) == 2


def test_with_czk_nemeni_original():
    obs = make(price=100, currency="EUR")
    converted = obs.with_czk(2431.5)
    assert obs.price_czk is None
    assert converted.price_czk == 2431.5
    assert converted.price == 100
