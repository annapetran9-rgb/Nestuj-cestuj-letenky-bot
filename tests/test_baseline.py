"""Percentily a baseline — základ celé detekce."""
from __future__ import annotations

import pytest

from analysis.baseline import Baseline, compute_baseline, drop_vs_median, percentile


def test_percentil_na_znamych_datech():
    values = list(range(1, 11))  # 1..10
    assert percentile(values, 0.0) == 1.0
    assert percentile(values, 1.0) == 10.0
    assert percentile(values, 0.5) == 5.5
    assert percentile(values, 0.10) == pytest.approx(1.9)


def test_percentil_jednoho_prvku():
    assert percentile([42.0], 0.5) == 42.0


def test_percentil_odmita_prazdny_vstup():
    with pytest.raises(ValueError, match="prázdného"):
        percentile([], 0.5)


def test_percentil_odmita_rozsah_mimo():
    with pytest.raises(ValueError, match="0–1"):
        percentile([1, 2, 3], 1.5)


def test_baseline_ignoruje_nuly_a_none():
    baseline = compute_baseline([100, 0, None, 200, -5, 300])
    assert baseline.count == 3
    assert baseline.lowest == 100


def test_baseline_prazdneho_vstupu_je_none():
    assert compute_baseline([]) is None
    assert compute_baseline([0, None]) is None


def test_spolehlivost_potrebuje_30_pozorovani():
    assert compute_baseline([1000] * 29).is_reliable is False
    assert compute_baseline([1000] * 30).is_reliable is True


def test_pokles_proti_medianu():
    baseline = Baseline(count=50, lowest=5000, p05=6000, p10=7000,
                        p25=8000, median=10000)
    assert drop_vs_median(6000, baseline) == pytest.approx(0.40)
    assert drop_vs_median(10000, baseline) == pytest.approx(0.0)
    # cena nad mediánem dává negativní pokles
    assert drop_vs_median(12000, baseline) == pytest.approx(-0.20)
