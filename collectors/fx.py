"""Přepočet měn kurzem ČNB.

ČNB zveřejňuje denní kurzy jako prostý text bez klíče a bez limitů, což je
pro tenhle projekt ideální. Kurz se cachuje na den do `data/fx_cache.json`.

Pravidlo z CLAUDE.md: cena se ukládá v originální měně plus přepočet kurzem
ke dni pozorování. Nikdy se nepřepočítává zpětně aktuálním kurzem.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from collectors.http import FetchError
from config import ROOT

log = logging.getLogger(__name__)

CNB_URL = (
    "https://www.cnb.cz/cs/financni-trhy/devizovy-trh/"
    "kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/denni_kurz.txt"
)
CACHE_PATH = ROOT / "data" / "fx_cache.json"

#: Záložní kurzy, když ČNB není dostupná. Hrubé, jen aby běh nespadl —
#: pozorování se stejně ukládá i v originální měně.
FALLBACK_RATES: dict[str, float] = {
    "CZK": 1.0, "EUR": 25.0, "USD": 23.0, "GBP": 29.0, "PLN": 5.8, "HUF": 0.065,
}


def _parse_cnb_text(text: str) -> dict[str, float]:
    """Rozparsuje formát ČNB.

    26.11.2026 #228
    země|měna|množství|kód|kurz
    Austrálie|dolar|1|AUD|15,123
    """
    rates: dict[str, float] = {"CZK": 1.0}
    for line in text.splitlines()[2:]:
        parts = line.split("|")
        if len(parts) != 5:
            continue
        _, _, amount_raw, code, rate_raw = parts
        try:
            amount = float(amount_raw.replace(",", "."))
            rate = float(rate_raw.replace(",", "."))
        except ValueError:
            continue
        if amount > 0:
            rates[code.strip().upper()] = rate / amount
    return rates


def get_rates(on: date | None = None) -> dict[str, float]:
    """Vrátí kurzy k CZK. Výsledek pro dnešní den se cachuje."""
    day = (on or date.today()).isoformat()

    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if cache.get("date") == day and cache.get("rates"):
                return {k: float(v) for k, v in cache["rates"].items()}
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            log.warning("cache kurzů je poškozená, stahuju znovu")

    try:
        import urllib.request

        from config import USER_AGENT

        request = urllib.request.Request(CNB_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=15) as response:
            text = response.read().decode("windows-1250", errors="replace")
        rates = _parse_cnb_text(text)
        if len(rates) < 5:
            raise FetchError("ČNB vrátila podezřele málo kurzů")
    except Exception as exc:  # noqa: BLE001 — chce to pokračovat i bez kurzů
        log.warning("kurzy ČNB nedostupné (%s), používám záložní", exc)
        return dict(FALLBACK_RATES)

    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps({"date": day, "rates": rates}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        log.warning("cache kurzů se nepodařilo zapsat: %s", exc)

    return rates


def to_czk(amount: float, currency: str, rates: dict[str, float] | None = None) -> float | None:
    """Přepočte částku do CZK. Vrátí None, když kurz není známý."""
    table = rates if rates is not None else get_rates()
    rate = table.get(currency.upper())
    if rate is None:
        return None
    return round(amount * rate, 2)
