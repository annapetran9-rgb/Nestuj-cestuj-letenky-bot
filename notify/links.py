"""Odkazy do alertů — affiliate i vlastní web.

Zásadní pravidlo projektu (viz CLAUDE.md): **affiliate odkazy na ubytování
nepatří do e-mailu.** Booking má session cookie, takže klik z e-mailu je
u ubytování téměř vždy promarněný — člověk řeší hotel za dva dny, ne v tu
minutu. E-mail proto vede na vlastní `/nabidka/`, kde je Stay22 mapa a kde
cookie funguje ve chvíli, kdy ubytování skutečně řeší.

Z toho plyne, co se tady staví:
* odkaz na letenku → affiliate (Travelpayouts), provize hned,
* odkaz na vlastní web → `/nabidka/` s parametry, dokud nemá destinace stránku.
"""
from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from analysis.airports import airport
from collectors.base import FareObservation

AVIASALES_SEARCH = "https://www.aviasales.com/search"


def aviasales_link(observation: FareObservation, marker: str) -> str:
    """Affiliate odkaz do vyhledávání Aviasales.

    Formát hledání je `PRG1403MNL28031`: odlet + DDMM + cíl + DDMM + počet osob.

    TODO: ověř si přesnou podobu odkazu ve svém Travelpayouts dashboardu —
    u některých kampaní se používá redirect přes tp.media. Tohle je funkční
    základ, ne poslední slovo.
    """
    out = observation.depart_date.strftime("%d%m")
    path = f"{observation.origin}{out}{observation.destination}"
    if observation.return_date:
        path += observation.return_date.strftime("%d%m")
    path += "1"  # jeden dospělý

    url = f"{AVIASALES_SEARCH}/{path}"
    return f"{url}?marker={marker}" if marker else url


def flight_link(observation: FareObservation, marker: str = "") -> str:
    """Nejlepší dostupný odkaz na letenku.

    U Ryanairu vede přímo na ryanair.com (affiliate program nemají), u ostatních
    na Aviasales s markerem.
    """
    if observation.source == "ryanair":
        return observation.deep_link or aviasales_link(observation, marker)
    if marker:
        return aviasales_link(observation, marker)
    return observation.deep_link or aviasales_link(observation, marker)


def offer_page_link(
    observation: FareObservation,
    site_base_url: str,
    destination_page_url: str | None = None,
    campaign: str = "telegram",
) -> str:
    """Odkaz na vlastní web — stránka destinace, nebo univerzální `/nabidka/`.

    Dokud destinace nemá vlastní stránku, posílá se na `/nabidka/` s parametry.
    Jedna stránka obslouží celý svět, takže monetizace funguje od první nabídky
    a nemusí se čekat na vybudování sekce Destinace.
    """
    utm = {
        "utm_source": campaign,
        "utm_medium": "alert",
        "utm_campaign": "levne-letenky",
    }

    if destination_page_url:
        joiner = "&" if "?" in destination_page_url else "?"
        return f"{destination_page_url}{joiner}{urlencode(utm)}"

    info = airport(observation.destination)
    params = {
        "misto": info.name if info else observation.destination,
        "iata": observation.destination,
        "zeme": info.country if info else "",
        "odlet": observation.origin,
        "od": observation.depart_date.isoformat(),
        **(
            {"do": observation.return_date.isoformat()}
            if observation.return_date else {}
        ),
        **(
            {"cena": int(observation.price_czk)}
            if observation.price_czk else {}
        ),
        **utm,
    }
    clean = {k: v for k, v in params.items() if v != ""}
    return f"{site_base_url}/nabidka/?{urlencode(clean)}"
