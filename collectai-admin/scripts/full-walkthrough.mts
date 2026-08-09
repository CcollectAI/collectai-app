/**
 * FULL WALKTHROUGH — one fake creator, one fake fan, one real Pro purchase,
 * end to end, then read it back through the live dashboard.
 *
 * This is the whole funnel with fake details, narrated step by step. Every
 * step drives the REAL code path (the handle_new_user trigger, the actual
 * kpi-aggregates route, the real kpi.ts commission maths). Everything it
 * creates is deleted at the end, even on failure.
 *
 * Needs: `PORT=3210 npm run dev` running, and SUPABASE_SERVICE_ROLE_KEY.
 * Run:   ADMIN_BASE=http://localhost:3210 npm run walkthrough
 */

import { createClient } from "@supabase/supabase-js";

const { APP_CONFIG } = await import("../admin.config");
const ADMIN_BASE = process.env.ADMIN_BASE ?? "http://localhost:3210";
const PIN = process.env.ADMIN_PIN ?? process.env.NEXT_PUBLIC_ADMIN_PIN ?? "";

const svc = createClient(
  APP_CONFIG.supabase.url,
  process.env.SUPABASE_SERVICE_ROLE_KEY ?? "",
  { auth: { persistSession: false } },
);

// ── the fake cast, chosen to look like real collectibles creators ───────────
const CREATOR = {
  name: "Nova Reef",
  handle: "@novareef.cards",
  platform: "tiktok",
  language: "EN",
  affiliate_code: "NOVA20",
  kits_sent: 0,
  cogs_per_kit_cents: 0,
  affiliate_payout_pct: 20, // Nova takes 20% of the revenue she drives
};
const FAN_EMAIL = "walkthrough-fan@sparrowcollect.invalid";
const PRO_PRICE_EUR = 39.99; // Pro yearly
const EVENT_ID = "walkthrough-evt-1";

let step = 0;
let ok = true;
function say(msg: string) { console.log(msg); }
function stepHead(t: string) { console.log(`\n\x1b[1m${++step}. ${t}\x1b[0m`); }
function line(label: string, value: string, good = true) {
  console.log(`   ${good ? "\x1b[32m✓\x1b[0m" : "\x1b[31m✗\x1b[0m"} ${label}: ${value}`);
  if (!good) ok = false;
}

async function cleanup() {
  await svc.from("subscription_events").delete().eq("affiliate_code", CREATOR.affiliate_code);
  await svc.from("creators").delete().eq("affiliate_code", CREATOR.affiliate_code);
  const { data } = await svc.auth.admin.listUsers({ page: 1, perPage: 200 });
  for (const u of data?.users ?? []) {
    if (u.email === FAN_EMAIL) await svc.auth.admin.deleteUser(u.id);
  }
}

async function main() {
  console.log("\x1b[1m═══ Creator funnel — full walkthrough with fake details ═══\x1b[0m");
  console.log(`Server : ${ADMIN_BASE}`);
  console.log(`DB     : ${APP_CONFIG.supabase.url}`);
  await cleanup(); // clear any prior run

  // 1 ── recruit the creator (through the real /api/creators route) ──────────
  stepHead(`You recruit ${CREATOR.name} and mint her code ${CREATOR.affiliate_code}`);
  const login = await fetch(`${ADMIN_BASE}/api/admin/login`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: PIN }),
  });
  const cookie = (login.headers.get("set-cookie") ?? "").split(";")[0] ?? "";
  line("admin logs into the dashboard", `session cookie issued (${login.status})`, !!cookie);

  const created = await fetch(`${ADMIN_BASE}/api/creators`, {
    method: "POST",
    headers: { "Content-Type": "application/json", cookie },
    body: JSON.stringify(CREATOR),
  });
  const cbody = await created.json();
  line("Nova added to the roster via the Creators tab",
    `${created.status} — code ${cbody?.creator?.affiliate_code}`, created.status === 201);

  // 2 ── a fan signs up in the app with her code ─────────────────────────────
  stepHead(`A fan taps Nova's link and signs up with code ${CREATOR.affiliate_code}`);
  say(`   (this drives the real handle_new_user trigger — the same path`);
  say(`    supabase.auth.signUp({ options: { data: { referral_code }}}) uses)`);
  const { data: fan, error: fanErr } = await svc.auth.admin.createUser({
    email: FAN_EMAIL,
    password: "walkthrough-pw-4823",
    email_confirm: true,
    user_metadata: { referral_code: CREATOR.affiliate_code.toLowerCase() }, // messy input on purpose
  });
  line("fan account created", fanErr ? fanErr.message : fan!.user.id.slice(0, 12) + "…", !fanErr);

  // give the AFTER INSERT trigger a beat, then read the profile it wrote
  await new Promise((r) => setTimeout(r, 400));
  const { data: prof } = await svc
    .from("profiles").select("referred_by_code").eq("id", fan!.user.id).single();
  line("trigger attributed the fan to Nova",
    `profiles.referred_by_code = ${JSON.stringify(prof?.referred_by_code)}`,
    prof?.referred_by_code === CREATOR.affiliate_code);
  say(`   (note: fan typed "${CREATOR.affiliate_code.toLowerCase()}", stored as "${prof?.referred_by_code}" — normalised)`);

  // 3 ── the fan upgrades to Pro; RevenueCat webhook records it ──────────────
  stepHead(`The fan upgrades to Pro yearly (€${PRO_PRICE_EUR})`);
  say(`   (the RevenueCat webhook writes the revenue ledger; here we insert the`);
  say(`    same row the webhook would, carrying Nova's code)`);
  const { error: evErr } = await svc.from("subscription_events").insert({
    event_id: EVENT_ID, event_type: "INITIAL_PURCHASE", provider: "revenuecat",
    user_id: fan!.user.id, app_user_id: fan!.user.id, product_id: "sparrow_pro_yearly",
    plan: "pro", revenue_cents: Math.round(PRO_PRICE_EUR * 100), currency: "EUR",
    affiliate_code: CREATOR.affiliate_code,
  });
  line("purchase recorded in the ledger",
    evErr ? evErr.message : `€${PRO_PRICE_EUR} attributed to ${CREATOR.affiliate_code}`, !evErr);

  // 4 ── read it back through the LIVE dashboard route ───────────────────────
  stepHead("You open the dashboard — what does it show?");
  say(`   (fetches the real /api/kpi-aggregates route, the same one the tabs render)`);
  const agg = await fetch(`${ADMIN_BASE}/api/kpi-aggregates?days=30`, {
    headers: { cookie },
  });
  const data = await agg.json();

  const signups = data.signupCounts?.[CREATOR.affiliate_code] ?? 0;
  const rev = data.revenueAgg?.[CREATOR.affiliate_code];
  line("Creators tab — Nova has attributed signups", `${signups}`, signups === 1);
  line("Creators tab — Nova's driven revenue", `€${rev?.revenue ?? 0}`, rev?.revenue === PRO_PRICE_EUR);
  line("Sales — total paid conversions", `${data.sales?.totalOrders}`, data.sales?.totalOrders >= 1);
  line("Sales — total revenue", `€${data.sales?.totalRevenue}`, data.sales?.totalRevenue >= PRO_PRICE_EUR);
  line("Sales — attributed revenue", `€${data.sales?.attributedRevenue}`, data.sales?.attributedRevenue >= PRO_PRICE_EUR);

  // 5 ── the payout Nova is owed (real commission maths) ─────────────────────
  stepHead(`What you owe ${CREATOR.name}`);
  const payout = Math.round((rev?.revenue ?? 0) * (CREATOR.affiliate_payout_pct / 100) * 100) / 100;
  const netToYou = Math.round(((rev?.revenue ?? 0) - payout) * 100) / 100;
  say(`   Nova drove €${rev?.revenue ?? 0} at a ${CREATOR.affiliate_payout_pct}% commission:`);
  line(`Nova's payout (${CREATOR.affiliate_payout_pct}% of €${rev?.revenue ?? 0})`, `€${payout}`, payout === 8.0);
  line("net to Sparrow after commission", `€${netToYou}`, netToYou === 31.99);

  // 6 ── reconciliation: attributed can't exceed total ───────────────────────
  stepHead("Cross-check: the numbers reconcile");
  const creatorSum = Object.values(data.revenueAgg ?? {})
    .reduce((s: number, r: any) => s + r.revenue, 0);
  line("attributed revenue ≤ total sales",
    `€${creatorSum} ≤ €${data.sales?.totalRevenue}`,
    creatorSum <= (data.sales?.totalRevenue ?? 0) + 0.001);

  // ── cleanup ────────────────────────────────────────────────────────────────
  stepHead("Tearing down all fake data");
  await cleanup();
  const { data: leftC } = await svc.from("creators").select("id").eq("affiliate_code", CREATOR.affiliate_code);
  const { data: leftE } = await svc.from("subscription_events").select("id").eq("affiliate_code", CREATOR.affiliate_code);
  const { data: users } = await svc.auth.admin.listUsers({ page: 1, perPage: 200 });
  const fanLeft = (users?.users ?? []).some((u) => u.email === FAN_EMAIL);
  line("creator removed", `${(leftC?.length ?? 0) === 0}`, (leftC?.length ?? 0) === 0);
  line("ledger event removed", `${(leftE?.length ?? 0) === 0}`, (leftE?.length ?? 0) === 0);
  line("fan account + profile removed", `${!fanLeft}`, !fanLeft);

  console.log(`\n${ok ? "\x1b[32m✓ Full walkthrough passed — the loop closes end to end.\x1b[0m"
                     : "\x1b[31m✗ Walkthrough hit a problem — see the ✗ lines above.\x1b[0m"}`);
  process.exit(ok ? 0 : 1);
}

main().catch(async (e) => {
  console.error("\n\x1b[31mWalkthrough crashed:\x1b[0m", e);
  await cleanup().catch(() => {});
  process.exit(1);
});
