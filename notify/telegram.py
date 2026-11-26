"""Odesílání do Telegramu.

Nejrychlejší a nejlevnější kanál: zdarma, bez schvalování šablon, doručení
v řádu sekund. U chybových cen, které platí někdy jen hodiny, rozhoduje
rychlost víc než cokoliv jiného — proto je tohle první kanál, ne e-mail.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from config import USER_AGENT

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"


def send_message(
    bot_token: str,
    chat_id: str,
    text: str,
    disable_preview: bool = True,
) -> bool:
    """Pošle zprávu. Vrací True při úspěchu, jinak zaloguje a vrátí False."""
    if not bot_token or not chat_id:
        log.warning("Telegram není nastavený (chybí token nebo chat ID)")
        return False

    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true" if disable_preview else "false",
    }).encode()

    request = urllib.request.Request(
        f"{API_BASE}/bot{bot_token}/sendMessage",
        data=payload,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode())
        if not result.get("ok"):
            log.error("Telegram odmítl zprávu: %s", result.get("description"))
            return False
        return True
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        log.error("Telegram selhal: %s", exc)
        return False
