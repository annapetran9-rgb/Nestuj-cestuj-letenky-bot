"""Rozdělení období na měsíce pro dotazy na Ryanair."""
from __future__ import annotations

from datetime import date

from pipeline import month_windows


def test_obdobi_se_rozdeli_po_mesicich():
    windows = month_windows(date(2026, 12, 3), date(2027, 2, 10))
    assert windows == [
        (date(2026, 12, 3), date(2026, 12, 31)),
        (date(2027, 1, 1), date(2027, 1, 31)),
        (date(2027, 2, 1), date(2027, 2, 10)),
    ]


def test_kratke_obdobi_v_jednom_mesici():
    assert month_windows(date(2027, 3, 5), date(2027, 3, 20)) == [
        (date(2027, 3, 5), date(2027, 3, 20)),
    ]


def test_obdobi_pres_pul_roku_ma_sest_oken():
    windows = month_windows(date(2026, 12, 3), date(2027, 5, 25))
    assert len(windows) == 6
    assert windows[0][0] == date(2026, 12, 3)
    assert windows[-1][1] == date(2027, 5, 25)


def test_kazdy_dalkovy_cil_ma_region_a_stropy():
    """Cíl mimo AIRPORTS by neměl regionální strop ani Kč/km — pojistky by neplatily."""
    from analysis.airports import AIRPORTS, LONG_HAUL_ORIGINS, LONG_HAUL_TARGETS, region_for

    for iata in LONG_HAUL_TARGETS:
        assert iata in AIRPORTS, iata
        assert region_for(iata) is not None, iata
    for iata in LONG_HAUL_ORIGINS:
        assert iata in AIRPORTS, iata


def test_dalkova_letiste_se_stridaji_po_hodinach():
    """Za 7 po sobě jdoucích hodin musí přijít na řadu každé velké letiště."""
    from datetime import datetime, timedelta, timezone

    from analysis.airports import LONG_HAUL_ORIGINS
    from pipeline import long_haul_origin_now

    start = datetime(2026, 11, 26, 10, 17, tzinfo=timezone.utc)
    hours = [long_haul_origin_now(start + timedelta(hours=h))
             for h in range(len(LONG_HAUL_ORIGINS))]
    assert sorted(hours) == sorted(LONG_HAUL_ORIGINS)
    # v rámci jedné hodiny je výsledek stabilní
    assert long_haul_origin_now(start) == long_haul_origin_now(start + timedelta(minutes=30))


def test_vsechna_odletova_letiste_maji_cenu_dopravy():
    from analysis.airports import AIRPORTS, DEFAULT_ORIGINS, ORIGIN_ACCESS_COST_CZK

    for iata in DEFAULT_ORIGINS:
        assert iata in ORIGIN_ACCESS_COST_CZK and iata in AIRPORTS, iata
