# Přihlašovací formulář (7. milník)

Statický web nemůže sám přijímat formuláře, takže endpointy běží na
Cloudflare Workers — 100 000 požadavků denně je v bezplatném tarifu.

**Tohle je zatím stub.** Je to poslední milník a má smysl do něj jít teprve
až robot posílá nabídky, které sama chceš dostávat. Dřív nemáš co nabízet.

## Rozdělení práce

Dvojité potvrzení (double opt-in) a odhlašování neřeš vlastním kódem —
Brevo to umí a je za to zodpovědný jako zpracovatel. Worker jen:

1. zvaliduje e-mail a segmentační údaje z formuláře,
2. zavolá Brevo, které pošle potvrzovací e-mail,
3. vrátí frontendu výsledek.

Tím se vyhneš ukládání nepotvrzených e-mailů u sebe, což je i z pohledu
GDPR jednodušší.

## Nastavení

```bash
cp wrangler.toml.example wrangler.toml   # wrangler.toml je v .gitignore
npx wrangler secret put BREVO_API_KEY
npx wrangler deploy
```

## Co ověřit před nasazením

- Přesný název endpointu pro double opt-in v aktuální dokumentaci Brevo
  (v kódu je `POST /v3/contacts/doubleOptinConfirmation`).
- ID seznamu a ID potvrzovací šablony ve svém Brevo účtu.
- Doménu v CORS hlavičkách.
- Zásady ochrany osobních údajů na webu — bez nich formulář nespouštěj.
