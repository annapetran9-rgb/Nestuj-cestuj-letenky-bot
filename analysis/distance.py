"""Vzdálenost mezi letišti — vstup pro metriku Kč/km.

Kč/km je jediná metrika, která dovoluje porovnat nabídku do Bergama
s nabídkou do Manily. U dálkových letů je to zároveň nejspolehlivější
indikátor chyby v ceně.
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from analysis.airports import airport

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Vzdálenost po povrchu Země v kilometrech."""
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def route_distance_km(origin: str, destination: str) -> float | None:
    """Vzdálenost trasy, nebo None když některé letiště neznáme."""
    a, b = airport(origin), airport(destination)
    if a is None or b is None:
        return None
    return round(haversine_km(a.lat, a.lon, b.lat, b.lon), 1)


def price_per_km(price_czk: float, origin: str, destination: str,
                 round_trip: bool) -> float | None:
    """Kč za kilometr. U zpátečního letu se vzdálenost počítá dvakrát."""
    distance = route_distance_km(origin, destination)
    if not distance:
        return None
    total = distance * 2 if round_trip else distance
    return round(price_czk / total, 3)
