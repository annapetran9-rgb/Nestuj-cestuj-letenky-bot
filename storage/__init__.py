"""Perzistence. Mimo tento balíček se nepíše žádné SQL (viz CLAUDE.md)."""
from storage.base import Store, open_store

__all__ = ["Store", "open_store"]
