-- Schéma pro SQLite i Postgres. Rozdíly jsou ošetřené v storage/*_store.py.
--
-- Zásada: fare_observations je append-only. Pozorování je fakt o minulosti,
-- nikdy se needituje. Z téhle historie se počítá, co je normální cena.

CREATE TABLE IF NOT EXISTS fare_observations (
    id              INTEGER PRIMARY KEY,
    source          TEXT    NOT NULL,
    origin          TEXT    NOT NULL,
    destination     TEXT    NOT NULL,
    depart_date     TEXT    NOT NULL,
    return_date     TEXT,
    depart_month    TEXT    NOT NULL,   -- 'YYYY-MM', baseline se počítá po měsících
    price           REAL    NOT NULL,
    currency        TEXT    NOT NULL,
    price_czk       REAL,
    airline         TEXT,
    flight_number   TEXT,
    transfers       INTEGER NOT NULL DEFAULT 0,
    deep_link       TEXT,
    fingerprint     TEXT    NOT NULL,
    observed_at     TEXT    NOT NULL
);

-- Hlavní dotaz systému: historie ceny na trase v daném měsíci odletu.
CREATE INDEX IF NOT EXISTS idx_obs_route_month
    ON fare_observations (origin, destination, depart_month);
CREATE INDEX IF NOT EXISTS idx_obs_observed
    ON fare_observations (observed_at);
CREATE INDEX IF NOT EXISTS idx_obs_fingerprint
    ON fare_observations (fingerprint);


-- Co už bylo odesláno. Brání tomu, aby stejná nabídka přišla dvakrát.
CREATE TABLE IF NOT EXISTS alerts_sent (
    fingerprint     TEXT PRIMARY KEY,
    origin          TEXT NOT NULL,
    destination     TEXT NOT NULL,
    price_czk       REAL,
    score           REAL,
    is_error_fare   INTEGER NOT NULL DEFAULT 0,
    channel         TEXT NOT NULL,
    sent_at         TEXT NOT NULL
);


-- Odběratelé. POZOR: tato tabulka obsahuje osobní údaje.
-- Databázový soubor se nikdy necommituje (viz .gitignore).
CREATE TABLE IF NOT EXISTS subscribers (
    id              INTEGER PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    confirmed_at    TEXT,              -- NULL = nepotvrzený double opt-in
    confirm_token   TEXT,
    origin_airports TEXT,              -- 'PRG,BRQ,VIE'
    regions         TEXT,              -- 'asie,evropa'
    max_price_czk   REAL,
    created_at      TEXT NOT NULL,
    unsubscribed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_subscribers_confirmed
    ON subscribers (confirmed_at);


-- Mapování destinace → stránka na webu. Dokud záznam neexistuje,
-- alert odkazuje na univerzální /nabidka/ s parametry.
CREATE TABLE IF NOT EXISTS destination_pages (
    destination     TEXT PRIMARY KEY,  -- IATA kód cíle
    city_name       TEXT,
    country_name    TEXT,
    url             TEXT,              -- NULL = stránka ještě není
    deal_count      INTEGER NOT NULL DEFAULT 0,  -- kolik akcí se tam našlo
    click_count     INTEGER NOT NULL DEFAULT 0,  -- kolik kliknutí to dostalo
    updated_at      TEXT
);
