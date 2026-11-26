# CLAUDE.md — pravidla projektu

Robot, který hledá levné letenky z ČR a okolních letišť do celého světa,
detekuje mimořádné ceny a posílá je do Telegramu a e-mailem.
Součást projektu **Nestůj, cestuj!** (nestuj-cestuj.cz).

Tento soubor je závazný. Když se v něm něco neshoduje s kódem, ptej se — neměň pravidla sám.

---

## Architektonické invarianty

1. **Collector vrací jen `FareObservation`.** Nikdy nic neposílá, nic nehodnotí,
   nic neukládá. Collector = zdroj dat, nic jiného.
2. **Fetch a parse jsou vždy dvě oddělené funkce.** `fetch_*()` sahá na síť,
   `parse_*()` je čistá funkce nad už načteným JSONem. Bez této separace nejde
   psát testy a parsery se rozbijí při každé změně API.
3. **`analysis/` neobsahuje žádné I/O.** Žádná síť, žádná databáze, žádné soubory.
   Jen čisté funkce nad seznamy čísel a `FareObservation`. Proto jsou testovatelné.
4. **Databáze jen přes `storage.base.Store`.** Nikdy nepiš SQL mimo
   `storage/*_store.py`. Změna SQLite → Postgres nesmí znamenat změnu v pipeline.
5. **Nic se neposílá bez deduplikace.** Každý alert má fingerprint
   (`origin|destination|depart|return|price`). Co už bylo odesláno, se neposílá znovu.
   Navíc platí: na jednu trasu a termín jde jen nejlepší cena. Dvě skoro stejné
   nabídky na stejný termín jsou pro čtenáře šum.
6. **Kandidát se nikdy nepočítá do své vlastní historie.** `route_prices` se volá
   s `exclude_recent_hours` rovným okénku, z jakého se berou kandidáti. Kdyby se
   hodnocená nabídka počítala do baseline, snižovala by si sama laťku a výjimečná
   cena by vypadala jako běžná. Tohle je snadné omylem rozbít a projeví se to tím,
   že systém přestane hlásit ty nejlepší nabídky.
7. **Žádný signál sám nestačí na alert.** `DEAL_SCORE_THRESHOLD` je záměrně nad
   hodnotou nejsilnějšího jednotlivého signálu — musí se potkat aspoň dva.
   Hlavní pojistka proti falešným poplachům.

## Pravidla pro data

- **Ceny se ukládají v originální měně** plus přepočet do CZK kurzem ČNB
  z dne pozorování. Nikdy nepřepočítávej zpětně aktuálním kurzem.
- **Žádné alerty, dokud není historie.** Minimum je `MIN_HISTORY_OBSERVATIONS`
  pozorování na trasu (výchozí 30). Bez historie robot nepozná akci od běžné ceny.
  Jediná výjimka je absolutní regionální strop.
- **Cena z Travelpayouts je z cache** (2–7 dní). Do alertu vždy patří čas pozorování
  a věta, že cenu je potřeba ověřit.
- Letiště se vždy drží IATA kódů, velkými písmeny, tři znaky.

## Pravidla pro síť

- **Minimálně 1 sekunda mezi požadavky na stejný host.** Řeší `collectors/http.py`,
  nepřeskakuj ho a nevolej `urllib`/`requests` přímo z collectoru.
- Žádné paralelní stahování. Tento robot nemá spěchat, má běžet dlouho a nenápadně.
- Vždy posílej slušný `User-Agent` s odkazem na projekt.
- Když API vrátí chybu, zaloguj a pokračuj dalším letištěm. Jeden mrtvý endpoint
  nesmí shodit celý běh.

## Bezpečnost a soukromí

- **Tokeny jen z prostředí** (`os.environ`), nikdy v kódu, nikdy v commitu.
  Vzor je v `.env.example`.
- **Databáze odběratelů se nikdy necommituje.** `.gitignore` to hlídá, nerozbíjej ho.
  Repo může být veřejné, data odběratelů ne.
- Odběratelé: double opt-in povinně, odhlášení v každém e-mailu.

## Monetizace — nepřehlédnutelné pravidlo

- **Affiliate odkazy na ubytování nepatří do e-mailu.** Booking má session cookie,
  klik z e-mailu je u ubytování téměř vždy promarněný. E-mail vede na
  `/nabidka/` na vlastním webu, kde je Stay22 mapa.
- Do e-mailu patří jen odkaz na letenku (Aviasales/Travelpayouts) a odkaz na vlastní web.

## Konvence kódu

- Identifikátory anglicky, komentáře a docstringy česky.
- Python 3.11+, standardní knihovna kdekoliv to jde. Každá nová závislost
  potřebuje důvod — běží to na GitHub Actions, kde se každá instalace platí minutami.
- Type hinty všude.
- **Každý nový collector musí mít fixture test.** Ulož reálnou odpověď API do
  `tests/fixtures/` a testuj parser proti ní. Testy nikdy nesahají na síť.
- Před commitem `pytest`.

## Stav milníků

- [x] 1. Skelet, schéma DB, Ryanair collector, dry-run
- [x] 2. Travelpayouts collector, normalizace
- [ ] 3. GitHub Actions cron, 2–4 týdny sběr dat naprázdno
- [x] 4a. Scoring a detekce chybových cen (zbývá verifikace přes SerpApi)
- [x] 5a. Telegram notifier + univerzální stránka `/nabidka/` (zbývá Stay22 kód)
- [ ] 6. Grafové skládání tras (open-jaw, víceúsekové cesty)
- [ ] 7. Cloudflare Worker, formulář, double opt-in, denní digest

Když dokončíš milník, zaškrtni ho tady.

## Co zatím chybí a ví se o tom

- `notify/links.py` — formát affiliate odkazu je potřeba ověřit v Travelpayouts
  dashboardu, výchozí šablona je odhad.
- `web/nabidka.html` — místo pro Stay22 embed je označené `TODO`, kód se vkládá
  z vlastního Stay22 účtu.
- `worker/` — stub pro 7. milník, Brevo endpoint ověřit v dokumentaci.
- `analysis/distance.py` — souřadnice jen pro vybraná letiště, rozšiřuj podle potřeby.
- `tests/fixtures/` — obě fixtures jsou ručně sestavené, ne reálné odpovědi API.
  Až to půjde, nahraď je skutečnou odpovědí Ryanairu a Travelpayouts.
- `collectors/travelpayouts.py` — `/get_latest_prices` vrací jiné názvy polí
  než `/prices_for_dates` (`depart_date`, `value`, `number_of_changes`),
  ověřeno proti živému API 26. 11. 2026. Reálná fixture zatím chybí.
