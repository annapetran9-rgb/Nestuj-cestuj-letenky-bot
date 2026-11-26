"""Co je na dané trase normální cena.

Bez tohohle modulu systém nemůže fungovat: „levná letenka" není absolutní
pojem, je to cena výrazně nižší než obvyklá cena na stejné trase ve stejném
měsíci. Proto robot první měsíc jen sbírá data a nic neposílá.

Všechno jsou čisté funkce nad seznamem čísel — snadno testovatelné.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Sequence


@dataclass(frozen=True, slots=True)
class Baseline:
    """Statistika ceny na jedné trase a měsíci odletu."""

    count: int
    lowest: float
    p05: float
    p10: float
    p25: float
    median: float

    @property
    def is_reliable(self) -> bool:
        """Méně než 30 pozorování je na percentily málo."""
        return self.count >= 30


def percentile(values: Sequence[float], p: float) -> float:
    """Percentil s lineární interpolací (p je 0–1).

    Nepoužívá numpy — jedna závislost navíc se tady nevyplatí.
    """
    if not values:
        raise ValueError("percentil z prázdného seznamu")
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p musí být 0–1, dostal jsem {p}")

    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])

    position = p * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return float(ordered[low] * (1 - weight) + ordered[high] * weight)


def compute_baseline(prices: Sequence[float]) -> Baseline | None:
    """Spočítá statistiku z historických cen. None u prázdného vstupu."""
    clean = [float(p) for p in prices if p and p > 0]
    if not clean:
        return None
    return Baseline(
        count=len(clean),
        lowest=min(clean),
        p05=percentile(clean, 0.05),
        p10=percentile(clean, 0.10),
        p25=percentile(clean, 0.25),
        median=float(median(clean)),
    )


def drop_vs_median(price: float, baseline: Baseline) -> float:
    """O kolik je cena pod mediánem, jako podíl (0.4 = o 40 % níž).

    Negativní hodnota znamená, že cena je nad mediánem.
    """
    if baseline.median <= 0:
        return 0.0
    return (baseline.median - price) / baseline.median
