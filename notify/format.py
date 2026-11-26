"""Text alertu.

Tón podle značky Nestůj, cestuj: přirozený, praktický, bez reklamního nadšení.
Žádné „ÚŽASNÁ NABÍDKA!!!" — jen co to je, kolik to stojí a co je potřeba vědět.
"""
from __future__ import annotations

from analysis.airports import airport
from analysis.scoring import Verdict
from collectors.base import FareObservation

SOURCE_LABELS = {
    "ryanair": "Ryanair",
    "travelpayouts": "Aviasales",
}


def _place(iata: str) -> str:
    info = airport(iata)
    if info is None:
        return iata
    return f"{info.name} ({iata})"


def _money(amount: float | None) -> str:
    if amount is None:
        return "?"
    return f"{amount:,.0f}".replace(",", " ") + " Kč"


def format_telegram(
    observation: FareObservation,
    verdict: Verdict,
    flight_url: str,
    page_url: str,
) -> str:
    """Zpráva pro Telegram (HTML parse mode)."""
    destination = airport(observation.destination)
    headline = destination.name if destination else observation.destination
    country = f", {destination.country}" if destination else ""

    if verdict.is_error_fare:
        title = f"⚠️ Možná chyba v ceně: {headline}{country}"
    else:
        title = f"✈️ {headline}{country}"

    lines = [f"<b>{title}</b>", ""]
    lines.append(f"{_place(observation.origin)} → {_place(observation.destination)}")

    if observation.return_date:
        lines.append(
            f"📅 {observation.depart_date.strftime('%-d. %-m.')} – "
            f"{observation.return_date.strftime('%-d. %-m. %Y')}"
            f" ({observation.nights} nocí)"
        )
    else:
        lines.append(
            f"📅 {observation.depart_date.strftime('%-d. %-m. %Y')} (jednosměrný)"
        )

    lines.append(f"💰 <b>{_money(observation.price_czk)}</b>")

    access = verdict.total_cost_czk - (observation.price_czk or 0)
    if access > 0:
        lines.append(
            f"   {_money(verdict.total_cost_czk)} i s dopravou na letiště"
        )

    if observation.transfers:
        lines.append(f"🔁 {observation.transfers}× přestup")

    if verdict.reasons:
        lines.append("")
        lines.extend(f"• {reason}" for reason in verdict.reasons)

    lines.append("")
    lines.append(f'<a href="{flight_url}">Zobrazit letenku</a>')
    lines.append(f'<a href="{page_url}">Kde spát a co vidět</a>')

    source = SOURCE_LABELS.get(observation.source, observation.source)
    observed = observation.observed_at.strftime("%-d. %-m. %H:%M")
    lines.append("")
    lines.append(
        f"<i>Zdroj {source}, cena zjištěna {observed} UTC. "
        f"Ceny se mění po hodinách — ověř si ji, než budeš plánovat dál.</i>"
    )

    return "\n".join(lines)


def format_plain(
    observation: FareObservation, verdict: Verdict,
    flight_url: str = "", page_url: str = "",
) -> str:
    """Jednoříádkový výpis pro konzoli a dry-run."""
    route = f"{observation.origin}→{observation.destination}"
    dates = observation.depart_date.strftime("%d.%m.")
    if observation.return_date:
        dates += observation.return_date.strftime("-%d.%m.")
    flag = "CHYBA?" if verdict.is_error_fare else "akce"
    return (
        f"[{flag:6}] {route:9} {dates:14} "
        f"{_money(observation.price_czk):>12} "
        f"(skóre {verdict.score:>4}) {'; '.join(verdict.reasons)}"
    )
