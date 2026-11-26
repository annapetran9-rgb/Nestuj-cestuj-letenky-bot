"""Společné nastavení testů. Testy nikdy nesahají na síť (viz CLAUDE.md)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def load_fixture():
    def _load(name: str):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return _load


@pytest.fixture
def store():
    """Prázdná databáze v paměti."""
    from storage.base import open_store

    s = open_store(sqlite_path=":memory:")
    yield s
    s.close()
