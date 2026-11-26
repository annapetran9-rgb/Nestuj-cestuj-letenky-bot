"""HTTP vrstva pro collectory — jen standardní knihovna.

Jediné místo, odkud se v collectorech sahá na síť. Hlídá tři věci:
minimální odstup mezi požadavky na stejný host, slušný User-Agent
a to, že chyba jednoho požadavku neshodí celý běh.

Pravidlo z CLAUDE.md: collector nikdy nevolá urllib ani requests přímo.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from config import USER_AGENT

log = logging.getLogger(__name__)

#: Minimální odstup mezi dvěma požadavky na stejný host (sekundy).
MIN_INTERVAL_SECONDS = 1.0

_last_request_at: dict[str, float] = {}


class FetchError(RuntimeError):
    """Požadavek se nepovedl. Volající má zalogovat a pokračovat dál."""


def _throttle(host: str) -> None:
    """Počká, aby mezi požadavky na stejný host byl vždy odstup."""
    last = _last_request_at.get(host)
    if last is not None:
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_request_at[host] = time.monotonic()


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
    retries: int = 2,
) -> Any:
    """Stáhne JSON. Vyhodí `FetchError`, pokud to nejde ani po opakování."""
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        url = f"{url}?{urllib.parse.urlencode(clean)}"

    host = urllib.parse.urlparse(url).netloc
    all_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "cs,en;q=0.8",
        **(headers or {}),
    }

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        _throttle(host)
        request = urllib.request.Request(url, headers=all_headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
            return json.loads(payload)
        except urllib.error.HTTPError as exc:
            last_error = exc
            # 4xx kromě 429 nemá smysl opakovat — odpověď se nezmění.
            if exc.code != 429 and 400 <= exc.code < 500:
                break
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(2 ** attempt)

    raise FetchError(f"{url} selhalo: {last_error}") from last_error
