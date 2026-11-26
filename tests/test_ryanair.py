"""Parser Ryanair API proti reálné odpovědi z farfnd/v4."""
from __future__ import annotations

from datetime import date

from collectors.ryanair import booking_link, parse_one_way_fares, parse_round_trip_fares


def test_parsuje_realnou_odpoved(load_fixture):
    observations = parse_one_way_fares(load_fixture("ryanair_oneway.json"))

    # Třetí záznam má nevalidní IATA kód "XX" — musí se zahodit, ne spadnout.
    assert len(observations) == 2

    first = observations[0]
    assert first.origin == "PRG"
    assert first.destination == "BGY"
    assert first.depart_date == date(2027, 1, 21)
    assert first.price == 16.99
    assert first.currency == "EUR"
    assert first.airline == "FR"
    assert first.flight_number == "FR3527"
    assert first.transfers == 0
    assert first.return_date is None
    assert "ryanair.com" in first.deep_link


def test_prazdna_odpoved_nevyhodi_vyjimku():
    assert parse_one_way_fares({}) == []
    assert parse_one_way_fares({"fares": []}) == []
    assert parse_one_way_fares({"fares": None}) == []


def test_chybejici_cena_se_preskoci():
    payload = {"fares": [{"outbound": {
        "departureAirport": {"iataCode": "PRG"},
        "arrivalAirport": {"iataCode": "BGY"},
        "departureDate": "2027-01-21T17:05:00",
        "price": {},
    }}]}
    assert parse_one_way_fares(payload) == []


def test_zpatecni_pouziva_cenu_ze_summary():
    payload = {"fares": [{
        "outbound": {
            "departureAirport": {"iataCode": "PRG"},
            "arrivalAirport": {"iataCode": "AGP"},
            "departureDate": "2027-02-11T06:20:00",
            "price": {"value": 24.99, "currencyCode": "EUR"},
        },
        "inbound": {
            "departureAirport": {"iataCode": "AGP"},
            "arrivalAirport": {"iataCode": "PRG"},
            "departureDate": "2027-02-18T10:30:00",
            "price": {"value": 19.99, "currencyCode": "EUR"},
        },
        "summary": {"price": {"value": 44.98, "currencyCode": "EUR"}},
    }]}
    observations = parse_round_trip_fares(payload)
    assert len(observations) == 1
    assert observations[0].price == 44.98
    assert observations[0].return_date.isoformat() == "2027-02-18"


def test_odkaz_na_rezervaci():
    link = booking_link("PRG", "BGY", date(2027, 1, 21))
    assert "originIata=PRG" in link
    assert "destinationIata=BGY" in link
    assert "dateOut=2027-01-21" in link
    assert "isReturn=false" in link

    link_return = booking_link("PRG", "BGY", date(2027, 1, 21), date(2027, 1, 28))
    assert "isReturn=true" in link_return
    assert "dateIn=2027-01-28" in link_return
