# Levné letenky — robot pro Nestůj, cestuj!

Hledá letenky z ČR a okolních letišť, porovnává je s vlastní cenovou historií,
detekuje mimořádné ceny a posílá je do Telegramu a e-mailem.

## Rychlý start (nic neplatíš, nic neinstaluješ)

```bash
git clone <tvoje-repo> && cd flight-deals
cp .env.example .env          # tokeny doplň později, Ryanair je bez tokenu
python3 pipeline.py collect --origins PRG,BRQ,OSR --dry-run
```

`--dry-run` jen vypíše, co by se uložilo. Bez něj se to zapíše do `flight_deals.db`.

```bash
python3 pipeline.py collect --origins PRG,BRQ,OSR,VIE,KRK   # uloží do DB
python3 pipeline.py stats                                    # co už máš nasbírané
python3 pipeline.py analyze --dry-run                        # co by poslalo za alerty
pytest                                                       # testy, bez sítě
```

## Co je potřeba zařídit ručně

| Krok | Kde | Potřeba pro |
|---|---|---|
| Travelpayouts token + marker | travelpayouts.com → Profil → API token | světové trasy, provize z letenek |
| Telegram bot | `@BotFather` → `/newbot` | okamžité alerty |
| Neon nebo Supabase Postgres | neon.tech | běh v GitHub Actions |
| SerpApi klíč (nepovinné) | serpapi.com, free 250/měsíc | verifikace ceny |
| Stay22 embed kód | tvůj Stay22 účet | provize z ubytování |

Ryanair API nepotřebuje nic.

## Důležité: první měsíc neposílá nic

Robot nepozná akci od běžné ceny, dokud nemá vlastní historii. Nech ho
**2–4 týdny jen sbírat** (`collect`), teprve potom zapni `analyze --notify`.
Minimum pozorování na trasu je v `.env` jako `MIN_HISTORY_OBSERVATIONS`.

## Struktura

```
collectors/   zdroje dat → FareObservation, nic jiného
analysis/     čisté funkce: percentily, scoring, vzdálenosti, letiště
storage/      SQLite (lokálně) a Postgres (Actions) za jedním rozhraním
notify/       Telegram, formátování zprávy, affiliate odkazy
web/          univerzální nabídková stránka /nabidka/ se Stay22 mapou
worker/       Cloudflare Worker pro přihlašovací formulář (7. milník)
db/schema.sql schéma databáze
```

Pravidla a invarianty projektu jsou v [CLAUDE.md](CLAUDE.md). Přečti si je,
než začneš něco měnit — hlavně část o monetizaci, ta není jen technická.
