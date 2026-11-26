"""Rozhodovací logika — co se pošle a co ne.

Tyhle testy chrání nejcitlivější část systému. Když se někdy začnou posílat
falešné poplachy, chyba bude nejspíš tady.
"""
from __future__ import annotations

from datetime import date

from analysis.baseline import compute_baseline
from analysis.scoring import score_fare
from collectors.base import FareObservation

# Historie trasy Praha–Manila: ceny okolo 13–17 tisíc, medián cca 14 750
ASIA_HISTORY = [14000, 15000, 13500, 16000, 14500, 15500, 13000, 17000,
                14200, 15800] * 4


def fare(price: float, origin: str = "PRG", destination: str = "MNL",
         round_trip: bool = True) -> FareObservation:
    return FareObservation(
        source="travelpayouts", origin=origin, destination=destination,
        depart_date=date(2027, 3, 14),
        return_date=date(2027, 3, 28) if round_trip else None,
        price=price, currency="CZK",
    ).with_czk(price)


def test_bezna_cena_neni_akce():
    verdict = score_fare(fare(13800), compute_baseline(ASIA_HISTORY))
    assert verdict.is_deal is False
    assert verdict.is_error_fare is False


def test_vyrazne_nizsi_cena_je_akce():
    verdict = score_fare(fare(11000), compute_baseline(ASIA_HISTORY))
    assert verdict.is_deal is True
    assert verdict.is_error_fare is False


def test_extremni_sleva_je_chyba_v_cene():
    verdict = score_fare(fare(4500), compute_baseline(ASIA_HISTORY))
    assert verdict.is_deal is True
    assert verdict.is_error_fare is True
    assert verdict.needs_verification is True
    assert any("chyb" in r for r in verdict.reasons)


def test_bez_historie_se_neposila_nic_prumerneho():
    """Nejdůležitější test v repu.

    Dokud není historie, robot nesmí tvrdit, že něco je akce — jedině
    když je cena absolutně mimořádná pro daný region.
    """
    verdict = score_fare(fare(13000), None)
    assert verdict.is_deal is False
    assert "málo historie" in verdict.rejected_because


def test_bez_historie_projde_absolutne_mimoradna_cena():
    verdict = score_fare(fare(7900), None)
    assert verdict.is_deal is True
    assert verdict.rejected_because is None


def test_malo_pozorovani_se_pocita_jako_bez_historie():
    verdict = score_fare(fare(12000), compute_baseline([14000] * 10),
                         min_history=30)
    assert verdict.is_deal is False
    assert "málo historie" in verdict.rejected_because


def test_regionalni_strop_prebije_statistiku():
    """Cena pod mediánem pořád nemusí být akce."""
    drahá_historie = [25000, 26000, 27000, 24000, 28000] * 8
    verdict = score_fare(fare(19000), compute_baseline(drahá_historie))
    assert verdict.is_deal is False
    assert "nad stropem" in verdict.rejected_because


def test_cena_dostupnosti_se_pripocita():
    """Let z Vídně musí být penalizovaný o dopravu na letiště."""
    z_prahy = score_fare(fare(9000, origin="PRG"), compute_baseline(ASIA_HISTORY))
    z_vidne = score_fare(fare(9000, origin="VIE", destination="SIN"),
                         compute_baseline(ASIA_HISTORY))
    assert z_prahy.total_cost_czk == 9000
    assert z_vidne.total_cost_czk == 9500


def test_chybejici_prepocet_do_czk_se_nevyhodnocuje():
    obs = FareObservation(
        source="ryanair", origin="PRG", destination="BGY",
        depart_date=date(2027, 1, 21), price=16.99, currency="EUR",
    )
    verdict = score_fare(obs, None)
    assert verdict.is_deal is False
    assert "CZK" in verdict.rejected_because


def test_neznamou_destinaci_system_nevyhodi():
    """Letiště mimo seznam nesmí nic rozbít, jen se nepoužijí stropy."""
    obs = FareObservation(
        source="travelpayouts", origin="PRG", destination="ZZZ",
        depart_date=date(2027, 3, 14), price=5000, currency="CZK",
    ).with_czk(5000)
    verdict = score_fare(obs, compute_baseline(ASIA_HISTORY))
    assert isinstance(verdict.is_deal, bool)


def test_jeden_signal_sam_nestaci():
    """Pojistka proti falešným poplachům.

    Krátká trasa pod historickým minimem, ale bez výrazného poklesu proti
    mediánu — to je příliš slabý důvod obtěžovat stovky lidí e-mailem.
    """
    evropska_historie = [2000, 2100, 2200, 1900, 2300, 2050] * 7
    verdict = score_fare(
        fare(1850, destination="BGY"), compute_baseline(evropska_historie)
    )
    assert verdict.score == 2.0          # jen percentilový signál
    assert verdict.is_deal is False


def test_dva_signaly_uz_staci():
    evropska_historie = [2000, 2100, 2200, 1900, 2300, 2050] * 7
    verdict = score_fare(
        fare(1100, destination="BGY"), compute_baseline(evropska_historie)
    )
    assert verdict.is_deal is True
    assert len(verdict.reasons) >= 2


def test_bezna_evropska_jednosmerka_neni_mimoradna():
    """Ryanair prodává jednosměrky za 400–800 Kč běžně. Práh pro zpáteční
    letenky (1 200 Kč) by z nich udělal „mimořádné" skoro všechny."""
    verdict = score_fare(fare(700, destination="BGY", round_trip=False), None)
    assert not any("mimořádná" in r for r in verdict.reasons)


def test_extremne_levna_jednosmerka_je_mimoradna():
    verdict = score_fare(fare(400, destination="BGY", round_trip=False), None)
    assert any("mimořádná" in r for r in verdict.reasons)


def test_jednosmerka_ma_vlastni_strop():
    """Jednosměrka do Asie za 12 000 Kč je pod zpátečním stropem, ale akce to není."""
    verdict = score_fare(fare(12000, round_trip=False), compute_baseline(ASIA_HISTORY))
    assert verdict.is_deal is False
    assert "nad stropem" in verdict.rejected_because
