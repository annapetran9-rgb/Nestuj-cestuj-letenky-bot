"""Rozhodnutí, jestli je nabídka hodna poslání.

Skládá dohromady čtyři nezávislé signály. Žádný z nich nestačí sám:

* **percentil** — cena pod p10 vlastní historie trasy,
* **pokles proti mediánu** — relativní sleva,
* **Kč/km** — jediná metrika srovnatelná mezi Bergamem a Manilou,
* **regionální strop** — pojistka proti statistice.

Nejčastější důvod, proč tyhle systémy umřou, jsou falešné poplachy. Proto je
výchozí nastavení přísné: lepší tři skvělé nabídky týdně než dvacet
průměrných denně. Prahy se povolují, ne utahují.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from analysis.airports import access_cost_czk, region_for
from analysis.baseline import Baseline, drop_vs_median
from analysis.distance import price_per_km
from collectors.base import FareObservation

#: Kč/km, pod kterými je dálkový let mimořádný.
LONG_HAUL_CPK_THRESHOLD = 0.80
#: Od kolika km se trasa počítá jako dálková.
LONG_HAUL_MIN_KM = 4000
#: Skóre, od kterého se nabídka posílá.
#: Záměrně nad hodnotou nejsilnějšího jednotlivého signálu (2.0) — žádný
#: signál sám nestačí, musí se potkat aspoň dva. Tohle je hlavní pojistka
#: proti falešným poplachům, povoluj ji opatrně.
DEAL_SCORE_THRESHOLD = 2.5


@dataclass(frozen=True, slots=True)
class Verdict:
    """Výsledek vyhodnocení jedné nabídky."""

    is_deal: bool
    is_error_fare: bool
    score: float
    total_cost_czk: float
    reasons: tuple[str, ...] = field(default_factory=tuple)
    rejected_because: str | None = None

    @property
    def needs_verification(self) -> bool:
        """Mimořádné ceny se vždy ověřují druhým zdrojem, než se pošlou."""
        return self.is_error_fare or self.score >= 4.0


def score_fare(
    observation: FareObservation,
    baseline: Baseline | None,
    min_history: int = 30,
    deal_drop_threshold: float = 0.40,
    error_fare_drop_threshold: float = 0.60,
) -> Verdict:
    """Vyhodnotí jedno pozorování proti historii trasy.

    Čistá funkce — nesahá na databázi ani na síť. Historii si volající
    načte sám a předá ji jako `baseline`.
    """
    price_czk = observation.price_czk
    if price_czk is None:
        return Verdict(
            is_deal=False, is_error_fare=False, score=0.0, total_cost_czk=0.0,
            rejected_because="chybí přepočet do CZK",
        )

    # Reálná cena z pohledu člověka v ČR, včetně dopravy na letiště.
    total = price_czk + access_cost_czk(observation.origin)
    region = region_for(observation.destination)

    # --- Pojistka první: regionální strop. Statistika sem nemá co mluvit. ---
    if region and total > region.hard_cap_czk:
        return Verdict(
            is_deal=False, is_error_fare=False, score=0.0, total_cost_czk=total,
            rejected_because=(
                f"nad stropem pro {region.name} "
                f"({total:.0f} > {region.hard_cap_czk:.0f} Kč)"
            ),
        )

    score = 0.0
    reasons: list[str] = []

    # --- Signál: absolutní mimořádná cena. Funguje i bez historie. ---
    exceptional = bool(region and total <= region.exceptional_czk)
    if exceptional:
        score += 2.0
        reasons.append(
            f"mimořádná cena pro {region.name} (pod {region.exceptional_czk:.0f} Kč)"
        )

    # --- Signál: Kč/km u dálkových letů ---
    cpk = price_per_km(
        total, observation.origin, observation.destination,
        observation.is_round_trip,
    )
    from analysis.distance import route_distance_km

    distance = route_distance_km(observation.origin, observation.destination)
    if cpk is not None and distance and distance >= LONG_HAUL_MIN_KM:
        if cpk <= LONG_HAUL_CPK_THRESHOLD * 0.6:
            score += 2.0
            reasons.append(f"extrémní {cpk:.2f} Kč/km")
        elif cpk <= LONG_HAUL_CPK_THRESHOLD:
            score += 1.0
            reasons.append(f"výhodné {cpk:.2f} Kč/km")

    # --- Signály z vlastní historie ---
    drop = 0.0
    if baseline is not None and baseline.count >= min_history:
        drop = drop_vs_median(price_czk, baseline)

        if price_czk <= baseline.p05:
            score += 2.0
            reasons.append("nejnižší 5 % cen, co jsem na téhle trase viděl")
        elif price_czk <= baseline.p10:
            score += 1.5
            reasons.append("nejnižší 10 % cen na téhle trase")

        if drop >= error_fare_drop_threshold:
            score += 2.0
            reasons.append(f"o {drop * 100:.0f} % pod mediánem trasy")
        elif drop >= deal_drop_threshold:
            score += 1.0
            reasons.append(f"o {drop * 100:.0f} % pod mediánem trasy")
    elif not exceptional:
        # Bez historie a bez absolutně mimořádné ceny nemáme co tvrdit.
        return Verdict(
            is_deal=False, is_error_fare=False, score=score, total_cost_czk=total,
            reasons=tuple(reasons),
            rejected_because=(
                f"málo historie na trase "
                f"({baseline.count if baseline else 0}/{min_history} pozorování)"
            ),
        )

    # --- Chyba v ceně: extrémní sleva proti spolehlivé historii ---
    is_error_fare = bool(
        baseline is not None
        and baseline.count >= min_history
        and drop >= error_fare_drop_threshold
        and (cpk is None or distance is None or distance < LONG_HAUL_MIN_KM
             or cpk <= LONG_HAUL_CPK_THRESHOLD)
    )
    if is_error_fare:
        reasons.append("vypadá to na chybu v ceně — ověř a nekupuj nic nevratného")

    return Verdict(
        is_deal=score >= DEAL_SCORE_THRESHOLD,
        is_error_fare=is_error_fare,
        score=round(score, 2),
        total_cost_czk=round(total, 2),
        reasons=tuple(reasons),
    )
