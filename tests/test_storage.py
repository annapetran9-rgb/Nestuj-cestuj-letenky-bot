"""Perzistence — SQLite backend."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from collectors.base import FareObservation


def fare(price: float = 11980.0, destination: str = "MNL",
         observed_at: datetime | None = None) -> FareObservation:
    return FareObservation(
        source="travelpayouts", origin="PRG", destination=destination,
        depart_date=date(2027, 3, 14), return_date=date(2027, 3, 28),
        price=price, currency="CZK", price_czk=price,
        observed_at=observed_at or datetime.now(timezone.utc),
    )


def test_ulozeni_a_nacteni(store):
    assert store.add_observations([fare(), fare(12500, "BKK")]) == 2
    assert store.observation_count() == 2


def test_prazdny_seznam_nic_nerozbije(store):
    assert store.add_observations([]) == 0


def test_historie_trasy_se_filtruje_podle_mesice(store):
    store.add_observations([fare(11980), fare(12500)])
    assert sorted(store.route_prices("PRG", "MNL", "2027-03")) == [11980.0, 12500.0]
    assert store.route_prices("PRG", "MNL", "2027-04") == []
    assert store.route_prices("PRG", "BKK", "2027-03") == []


def test_stara_pozorovani_se_do_historie_nepocitaji(store):
    stare = datetime.now(timezone.utc) - timedelta(days=200)
    store.add_observations([fare(11980), fare(9000, observed_at=stare)])
    ceny = store.route_prices("PRG", "MNL", "2027-03", days_back=90)
    assert ceny == [11980.0]


def test_nedavna_pozorovani(store):
    stare = datetime.now(timezone.utc) - timedelta(hours=48)
    store.add_observations([fare(11980), fare(9000, observed_at=stare)])
    nedavna = store.recent_observations(hours=24)
    assert len(nedavna) == 1
    assert nedavna[0].price_czk == 11980.0
    # zpětné mapování musí zachovat všechno podstatné
    assert nedavna[0].return_date == date(2027, 3, 28)
    assert nedavna[0].source == "travelpayouts"


def test_deduplikace_alertu(store):
    obs = fare()
    fingerprint = obs.fingerprint()
    assert store.was_alerted(fingerprint) is False
    store.mark_alerted(fingerprint, "PRG", "MNL", 11980.0, 5.0, False, "telegram")
    assert store.was_alerted(fingerprint) is True
    # druhé označení nesmí spadnout na duplicitním klíči
    store.mark_alerted(fingerprint, "PRG", "MNL", 11980.0, 5.0, False, "telegram")


def test_stranka_destinace_kdyz_neexistuje(store):
    assert store.destination_page_url("MNL") is None


def test_souhrn_tras(store):
    store.add_observations([fare(11980), fare(12500), fare(9000, "BKK")])
    souhrn = dict(((o, d), (n, low)) for o, d, n, low in store.route_summary())
    assert souhrn[("PRG", "MNL")] == (2, 11980.0)
    assert souhrn[("PRG", "BKK")] == (1, 9000.0)


def test_historie_umi_vynechat_nejnovejsi_okno(store):
    """Kandidát se nesmí počítat do své vlastní historie.

    Kdyby se počítal, výjimečně nízká cena by si sama snížila percentily
    a vypadala by jako běžná — přesně to, co má systém odhalit.
    """
    stare = datetime.now(timezone.utc) - timedelta(days=10)
    store.add_observations([
        fare(14000, observed_at=stare),
        fare(15000, observed_at=stare),
        fare(4200),  # kandidát z poslední hodiny
    ])

    vcetne = store.route_prices("PRG", "MNL", "2027-03")
    bez = store.route_prices("PRG", "MNL", "2027-03", exclude_recent_hours=24)

    assert sorted(vcetne) == [4200.0, 14000.0, 15000.0]
    assert sorted(bez) == [14000.0, 15000.0]


def test_stejna_nabidka_se_neulozi_kazdou_hodinu(store):
    """Sběr běží každou hodinu. Nezměněná cena se má uložit jen jednou denně,
    jinak by limit historie „splnila" jediná opakovaná letenka."""
    assert store.add_observations([fare(11980)]) == 1
    assert store.add_observations([fare(11980)]) == 0
    assert store.observation_count() == 1


def test_zmena_ceny_se_ulozi_hned(store):
    store.add_observations([fare(11980)])
    assert store.add_observations([fare(10990)]) == 1


def test_stejna_cena_v_ruznych_dnech_jsou_dve_pozorovani(store):
    pred_tydnem = datetime.now(timezone.utc) - timedelta(days=7)
    assert store.add_observations([fare(11980, observed_at=pred_tydnem)]) == 1
    assert store.add_observations([fare(11980)]) == 1
    assert store.observation_count() == 2


def test_opakovani_v_jedne_davce_se_vyradi(store):
    assert store.add_observations([fare(11980), fare(11980)]) == 1
