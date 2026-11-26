"""Letiště, regiony a cena dostupnosti odletových letišť.

Dvě věci, které tenhle modul řeší a bez kterých by systém dával nesmysly:

1. **Cena dostupnosti.** Let z Vídně není pro člověka z Prahy stejně dostupný
   jako let z Prahy. Ke každé ceně se přičítá odhad nákladu na dopravu na dané
   letiště, takže robot sám nikdy nedoporučí „levný" let z Milána.
2. **Regionální stropy.** Letenka do Asie za 25 000 Kč může být statisticky pod
   mediánem a pořád to není akce. Strop je pojistka proti statistice.

Seznam je záměrně neúplný — obsahuje odletový cluster a běžné cíle. Rozšiřuj
podle toho, co se v datech objeví.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Airport:
    iata: str
    name: str
    country: str
    region: str
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class Region:
    key: str
    name: str
    hard_cap_czk: float        # nad tuto cenu se alert neposílá nikdy
    exceptional_czk: float     # pod tuto cenu je to akce i bez historie


REGIONS: dict[str, Region] = {
    "evropa":          Region("evropa", "Evropa", 4500, 1200),
    "blizky-vychod":   Region("blizky-vychod", "Blízký východ", 8000, 4500),
    "afrika":          Region("afrika", "Afrika", 10000, 5500),
    "asie":            Region("asie", "Asie", 14000, 8500),
    "severni-amerika": Region("severni-amerika", "Severní Amerika", 12000, 6500),
    "stredni-amerika": Region("stredni-amerika", "Střední Amerika", 15000, 9000),
    "jizni-amerika":   Region("jizni-amerika", "Jižní Amerika", 16000, 10000),
    "oceanie":         Region("oceanie", "Oceánie", 20000, 13000),
}

#: Odletová letiště dostupná z ČR a odhad nákladu na dopravu tam a zpět (CZK).
#: Čísla si uprav podle toho, odkud reálně vyjíždíš.
ORIGIN_ACCESS_COST_CZK: dict[str, float] = {
    "PRG": 0, "BRQ": 0, "OSR": 0, "PED": 0,
    "VIE": 500, "BTS": 400, "LNZ": 700,
    "KRK": 600, "KTW": 600, "WRO": 700, "POZ": 900, "WAW": 900,
    "BUD": 900,
    "DRS": 600, "BER": 700, "LEJ": 700, "NUE": 900, "MUC": 1000,
}

#: Výchozí cluster pro skenování. Prvních pět pokryje většinu nabídek.
DEFAULT_ORIGINS: tuple[str, ...] = ("PRG", "BRQ", "OSR", "VIE", "KRK", "BER", "BTS")


def _a(iata, name, country, region, lat, lon) -> tuple[str, Airport]:
    return iata, Airport(iata, name, country, region, lat, lon)


AIRPORTS: dict[str, Airport] = dict([
    # --- odletový cluster ---
    _a("PRG", "Praha", "Česko", "evropa", 50.10, 14.26),
    _a("BRQ", "Brno", "Česko", "evropa", 49.15, 16.69),
    _a("OSR", "Ostrava", "Česko", "evropa", 49.70, 18.11),
    _a("PED", "Pardubice", "Česko", "evropa", 50.01, 15.74),
    _a("VIE", "Vídeň", "Austria", "evropa", 48.11, 16.57),
    _a("BTS", "Bratislava", "Slovensko", "evropa", 48.17, 17.21),
    _a("LNZ", "Linec", "Austria", "evropa", 48.23, 14.19),
    _a("KRK", "Krakov", "Polsko", "evropa", 50.08, 19.80),
    _a("KTW", "Katovice", "Polsko", "evropa", 50.47, 19.08),
    _a("WRO", "Vratislav", "Polsko", "evropa", 51.10, 16.89),
    _a("POZ", "Poznaň", "Polsko", "evropa", 52.42, 16.83),
    _a("WAW", "Varšava", "Polsko", "evropa", 52.17, 20.97),
    _a("BUD", "Budapešť", "Maďarsko", "evropa", 47.44, 19.26),
    _a("BER", "Berlín", "Německo", "evropa", 52.37, 13.50),
    _a("DRS", "Drážďany", "Německo", "evropa", 51.13, 13.77),
    _a("LEJ", "Lipsko", "Německo", "evropa", 51.42, 12.24),
    _a("NUE", "Norimberk", "Německo", "evropa", 49.50, 11.08),
    _a("MUC", "Mnichov", "Německo", "evropa", 48.35, 11.79),
    # --- Evropa, běžné cíle ---
    _a("BGY", "Milán Bergamo", "Itálie", "evropa", 45.67, 9.70),
    _a("FCO", "Řím Fiumicino", "Itálie", "evropa", 41.80, 12.25),
    _a("BCN", "Barcelona", "Španělsko", "evropa", 41.30, 2.08),
    _a("MAD", "Madrid", "Španělsko", "evropa", 40.49, -3.57),
    _a("AGP", "Málaga", "Španělsko", "evropa", 36.68, -4.50),
    _a("LIS", "Lisabon", "Portugalsko", "evropa", 38.77, -9.13),
    _a("OPO", "Porto", "Portugalsko", "evropa", 41.25, -8.68),
    _a("TFS", "Tenerife Sur", "Španělsko", "evropa", 28.04, -16.57),
    _a("LPA", "Gran Canaria", "Španělsko", "evropa", 27.93, -15.39),
    _a("ATH", "Athény", "Řecko", "evropa", 37.94, 23.95),
    _a("STN", "Londýn Stansted", "Velká Británie", "evropa", 51.89, 0.24),
    _a("LGW", "Londýn Gatwick", "Velká Británie", "evropa", 51.15, -0.18),
    _a("DUB", "Dublin", "Irsko", "evropa", 53.43, -6.25),
    _a("CDG", "Paříž CDG", "Francie", "evropa", 49.01, 2.55),
    _a("AMS", "Amsterdam", "Nizozemsko", "evropa", 52.31, 4.76),
    _a("KEF", "Reykjavík", "Island", "evropa", 63.99, -22.61),
    _a("TIA", "Tirana", "Albánie", "evropa", 41.41, 19.72),
    # --- Blízký východ ---
    _a("IST", "Istanbul", "Turecko", "blizky-vychod", 41.26, 28.74),
    _a("DXB", "Dubaj", "SAE", "blizky-vychod", 25.25, 55.36),
    _a("AUH", "Abú Dhabí", "SAE", "blizky-vychod", 24.43, 54.65),
    _a("DOH", "Dauhá", "Katar", "blizky-vychod", 25.27, 51.61),
    _a("TLV", "Tel Aviv", "Izrael", "blizky-vychod", 32.01, 34.89),
    _a("AMM", "Ammán", "Jordánsko", "blizky-vychod", 31.72, 35.99),
    # --- Afrika ---
    _a("CAI", "Káhira", "Egypt", "afrika", 30.11, 31.41),
    _a("HRG", "Hurghada", "Egypt", "afrika", 27.18, 33.80),
    _a("RAK", "Marrákeš", "Maroko", "afrika", 31.61, -8.04),
    _a("CMN", "Casablanca", "Maroko", "afrika", 33.37, -7.59),
    _a("JNB", "Johannesburg", "JAR", "afrika", -26.14, 28.25),
    _a("CPT", "Kapské Město", "JAR", "afrika", -33.97, 18.60),
    _a("NBO", "Nairobi", "Kenya", "afrika", -1.32, 36.93),
    _a("ZNZ", "Zanzibar", "Tanzanie", "afrika", -6.22, 39.22),
    _a("MRU", "Mauricius", "Mauricius", "afrika", -20.43, 57.68),
    # --- Asie ---
    _a("BKK", "Bangkok Suvarnabhumi", "Thajsko", "asie", 13.69, 100.75),
    _a("DMK", "Bangkok Don Mueang", "Thajsko", "asie", 13.91, 100.61),
    _a("HKT", "Phuket", "Thajsko", "asie", 8.11, 98.31),
    _a("SGN", "Ho Či Minovo Město", "Vietnam", "asie", 10.82, 106.66),
    _a("HAN", "Hanoj", "Vietnam", "asie", 21.22, 105.81),
    _a("SIN", "Singapur", "Singapur", "asie", 1.36, 103.99),
    _a("KUL", "Kuala Lumpur", "Malajsie", "asie", 2.75, 101.71),
    _a("MNL", "Manila", "Filipíny", "asie", 14.51, 121.02),
    _a("CEB", "Cebu", "Filipíny", "asie", 10.31, 123.98),
    _a("DPS", "Bali Denpasar", "Indonésie", "asie", -8.75, 115.17),
    _a("CGK", "Jakarta", "Indonésie", "asie", -6.13, 106.66),
    _a("NRT", "Tokio Narita", "Japonsko", "asie", 35.77, 140.39),
    _a("HND", "Tokio Haneda", "Japonsko", "asie", 35.55, 139.78),
    _a("KIX", "Ósaka", "Japonsko", "asie", 34.43, 135.23),
    _a("ICN", "Soul", "Korea", "asie", 37.46, 126.44),
    _a("PEK", "Peking", "Čína", "asie", 40.08, 116.58),
    _a("PVG", "Šanghaj", "Čína", "asie", 31.14, 121.81),
    _a("HKG", "Hongkong", "Hongkong", "asie", 22.31, 113.91),
    _a("TPE", "Tchaj-pej", "Tchaj-wan", "asie", 25.08, 121.23),
    _a("DEL", "Dillí", "Indie", "asie", 28.56, 77.10),
    _a("BOM", "Bombaj", "Indie", "asie", 19.09, 72.87),
    _a("CMB", "Kolombo", "Srí Lanka", "asie", 6.83, 79.89),
    _a("MLE", "Male", "Maledivy", "asie", 4.19, 73.53),
    _a("KTM", "Káthmándú", "Nepál", "asie", 27.70, 85.36),
    # --- Severní Amerika ---
    _a("JFK", "New York JFK", "USA", "severni-amerika", 40.64, -73.78),
    _a("EWR", "New York Newark", "USA", "severni-amerika", 40.69, -74.17),
    _a("BOS", "Boston", "USA", "severni-amerika", 42.36, -71.01),
    _a("ORD", "Chicago", "USA", "severni-amerika", 41.98, -87.90),
    _a("LAX", "Los Angeles", "USA", "severni-amerika", 33.94, -118.41),
    _a("SFO", "San Francisco", "USA", "severni-amerika", 37.62, -122.38),
    _a("MIA", "Miami", "USA", "severni-amerika", 25.80, -80.29),
    _a("YYZ", "Toronto", "Kanada", "severni-amerika", 43.68, -79.63),
    _a("YVR", "Vancouver", "Kanada", "severni-amerika", 49.19, -123.18),
    # --- Střední Amerika a Karibik ---
    _a("MEX", "Mexico City", "Mexiko", "stredni-amerika", 19.44, -99.07),
    _a("CUN", "Cancún", "Mexiko", "stredni-amerika", 21.04, -86.87),
    _a("PUJ", "Punta Cana", "Dominikánská rep.", "stredni-amerika", 18.57, -68.36),
    _a("HAV", "Havana", "Kuba", "stredni-amerika", 23.00, -82.41),
    _a("SJO", "San José", "Kostarika", "stredni-amerika", 9.99, -84.21),
    _a("PTY", "Panama", "Panama", "stredni-amerika", 9.07, -79.38),
    # --- Jižní Amerika ---
    _a("GRU", "São Paulo", "Brazílie", "jizni-amerika", -23.43, -46.47),
    _a("EZE", "Buenos Aires", "Argentina", "jizni-amerika", -34.82, -58.54),
    _a("SCL", "Santiago", "Chile", "jizni-amerika", -33.39, -70.79),
    _a("BOG", "Bogotá", "Kolumbie", "jizni-amerika", 4.70, -74.15),
    _a("LIM", "Lima", "Peru", "jizni-amerika", -12.02, -77.11),
    _a("UIO", "Quito", "Ekvádor", "jizni-amerika", -0.13, -78.36),
    # --- Oceánie ---
    _a("SYD", "Sydney", "Austrálie", "oceanie", -33.95, 151.18),
    _a("MEL", "Melbourne", "Austrálie", "oceanie", -37.67, 144.84),
    _a("AKL", "Auckland", "Nový Zéland", "oceanie", -37.01, 174.79),
    _a("HNL", "Honolulu", "USA", "oceanie", 21.32, -157.92),
])


def airport(iata: str) -> Airport | None:
    return AIRPORTS.get(iata.upper())


def region_for(destination: str) -> Region | None:
    """Region cílového letiště, nebo None když letiště neznáme."""
    found = airport(destination)
    return REGIONS.get(found.region) if found else None


def access_cost_czk(origin: str) -> float:
    """Odhad nákladu na dopravu na odletové letiště a zpět.

    Neznámé letiště dostane vysokou hodnotu — radši nabídku nepošleme,
    než poslat „akci", kam se člověk nedostane.
    """
    return ORIGIN_ACCESS_COST_CZK.get(origin.upper(), 2000.0)


def total_cost_czk(origin: str, price_czk: float) -> float:
    """Skutečná cena výletu z pohledu člověka v ČR."""
    return price_czk + access_cost_czk(origin)
