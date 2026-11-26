/**
 * Přihlašovací endpoint pro formulář na nestuj-cestuj.cz.
 * Cloudflare Worker — 7. milník, zatím stub. Viz worker/README.md.
 *
 * POST /subscribe
 *   { email, origins: ["PRG","BRQ"], regions: ["asie"], maxPrice: 12000 }
 *
 * Double opt-in a odhlašování řeší Brevo, ne tenhle kód.
 */

const ALLOWED_ORIGINS = [
  "https://nestuj-cestuj.cz",
  "https://www.nestuj-cestuj.cz",
];

const IATA = /^[A-Z]{3}$/;
const EMAIL = /^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$/;

function cors(request) {
  const origin = request.headers.get("Origin") || "";
  const allowed = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };
}

function json(body, status, request) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...cors(request) },
  });
}

/** Vytáhne z požadavku jen to, co čekáme, a zahodí zbytek. */
function parseSubscription(payload) {
  const email = String(payload.email || "").trim().toLowerCase();
  if (!EMAIL.test(email) || email.length > 254) {
    return { error: "Zadej prosím platnou e-mailovou adresu." };
  }

  const origins = (Array.isArray(payload.origins) ? payload.origins : [])
    .map((code) => String(code).trim().toUpperCase())
    .filter((code) => IATA.test(code))
    .slice(0, 10);

  const regions = (Array.isArray(payload.regions) ? payload.regions : [])
    .map((region) => String(region).trim().toLowerCase().slice(0, 32))
    .slice(0, 10);

  const maxPriceRaw = Number(payload.maxPrice);
  const maxPrice =
    Number.isFinite(maxPriceRaw) && maxPriceRaw > 0
      ? Math.min(Math.round(maxPriceRaw), 200000)
      : null;

  return { email, origins, regions, maxPrice };
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(request) });
    }

    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== "/subscribe") {
      return json({ error: "Nenalezeno" }, 404, request);
    }

    let payload;
    try {
      payload = await request.json();
    } catch {
      return json({ error: "Neplatný požadavek." }, 400, request);
    }

    const subscription = parseSubscription(payload);
    if (subscription.error) {
      return json({ error: subscription.error }, 400, request);
    }

    // TODO: ověř aktuální podobu endpointu v dokumentaci Brevo.
    // Brevo pošle potvrzovací e-mail a kontakt uloží teprve po potvrzení.
    const response = await fetch(
      "https://api.brevo.com/v3/contacts/doubleOptinConfirmation",
      {
        method: "POST",
        headers: {
          "api-key": env.BREVO_API_KEY,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: subscription.email,
          includeListIds: [Number(env.BREVO_LIST_ID)],
          templateId: Number(env.BREVO_TEMPLATE_ID),
          redirectionUrl: "https://nestuj-cestuj.cz/odber-potvrzen/",
          attributes: {
            ODLETOVA_LETISTE: subscription.origins.join(","),
            REGIONY: subscription.regions.join(","),
            MAX_CENA: subscription.maxPrice,
          },
        }),
      },
    );

    if (!response.ok) {
      // Detail chyby jde do logu, uživateli nic technického neříkáme.
      console.error("Brevo odmítl požadavek", response.status,
                    await response.text());
      return json(
        { error: "Přihlášení se teď nepovedlo, zkus to prosím za chvíli." },
        502, request,
      );
    }

    return json(
      { ok: true, message: "Poslal jsem ti potvrzovací e-mail." },
      200, request,
    );
  },
};
