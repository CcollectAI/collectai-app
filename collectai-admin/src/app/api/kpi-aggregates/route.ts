/**
 * GET /api/kpi-aggregates — every aggregate the KPI dashboard renders, derived
 * from the real tables.
 *
 * One route, one round trip, because each section used to read a different
 * table and a Pro subscription attributed to a creator only ever showed up on
 * the Creators tab. Sales, the revenue timeline and the market breakdown were
 * still pointed at the kit template's `orders`/`daily_revenue`/`market_metrics`,
 * which nothing writes — so the same €4.99 was simultaneously "real" in one tab
 * and "0.00" in three others.
 *
 * Server-side because subscription_events has RLS enabled with no policy: the
 * public anon key reads zero rows silently. Granting anon SELECT would publish
 * revenue to anyone who loads the page.
 *
 * Returns raw aggregates, never finished rows — the commission/ROI maths stays
 * in kpi.ts so there is exactly one implementation of it.
 */

import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { adminAuthConfigured, isAdminRequest } from "@/lib/adminAuth";

type RevenueRow = {
  affiliate_code: string | null;
  revenue_cents: number;
  occurred_at: string;
  plan: string | null;
};

function serviceClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
    process.env.SUPABASE_SERVICE_ROLE_KEY ?? "",
    { auth: { persistSession: false } },
  );
}

export async function GET(req: Request) {
  const cfg = adminAuthConfigured();
  if (!cfg.ok) {
    return NextResponse.json(
      { error: `Admin auth not configured. Missing: ${cfg.missing.join(", ")}` },
      { status: 503 },
    );
  }
  if (!isAdminRequest(req)) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const daysRaw = Number(new URL(req.url).searchParams.get("days") ?? 30);
  const days = Number.isFinite(daysRaw) && daysRaw > 0 ? daysRaw : 30;
  const since = new Date(Date.now() - days * 86400000).toISOString();
  const sb = serviceClient();

  const [creatorsRes, signupsRes, revenueRes] = await Promise.all([
    sb.from("creators").select("*").eq("is_active", true).order("name"),
    sb.from("profiles").select("referred_by_code, created_at").gte("created_at", since),
    sb.from("subscription_events")
      .select("affiliate_code, revenue_cents, occurred_at, plan")
      .gte("occurred_at", since).gt("revenue_cents", 0),
  ]);

  for (const [label, res] of [
    ["creators", creatorsRes], ["profiles", signupsRes], ["subscription_events", revenueRes],
  ] as const) {
    if (res.error) {
      return NextResponse.json(
        { error: `${label} unreadable (${res.error.code}: ${res.error.message})` },
        { status: res.error.code === "42P01" ? 503 : 500 },
      );
    }
  }

  const creators = creatorsRes.data ?? [];
  const signups = (signupsRes.data ?? []) as { referred_by_code: string | null }[];
  const revenue = (revenueRes.data ?? []) as RevenueRow[];

  // ── per-creator: attributed signups and revenue ───────────────────────────
  const signupCounts: Record<string, number> = {};
  for (const s of signups) {
    if (s.referred_by_code) {
      signupCounts[s.referred_by_code] = (signupCounts[s.referred_by_code] ?? 0) + 1;
    }
  }

  const revenueAgg: Record<string, { count: number; revenue: number }> = {};
  for (const r of revenue) {
    if (!r.affiliate_code) continue;
    revenueAgg[r.affiliate_code] ??= { count: 0, revenue: 0 };
    revenueAgg[r.affiliate_code].count += 1;
    revenueAgg[r.affiliate_code].revenue += r.revenue_cents / 100;
  }

  // ── sales: ALL paid transactions, attributed or not ───────────────────────
  const totalOrders = revenue.length;
  const totalRevenue = revenue.reduce((s, r) => s + r.revenue_cents, 0) / 100;
  const attributedOrders = revenue.filter((r) => r.affiliate_code).length;
  const attributedRevenue =
    revenue.filter((r) => r.affiliate_code).reduce((s, r) => s + r.revenue_cents, 0) / 100;

  const byPlan: Record<string, { orders: number; revenue: number }> = {};
  for (const r of revenue) {
    const plan = r.plan ?? "unknown";
    byPlan[plan] ??= { orders: 0, revenue: 0 };
    byPlan[plan].orders += 1;
    byPlan[plan].revenue += r.revenue_cents / 100;
  }

  // ── timeline: revenue per calendar day ────────────────────────────────────
  const daily: Record<string, { orders: number; revenue: number }> = {};
  for (const r of revenue) {
    const day = r.occurred_at.slice(0, 10);
    daily[day] ??= { orders: 0, revenue: 0 };
    daily[day].orders += 1;
    daily[day].revenue += r.revenue_cents / 100;
  }
  const timeline = Object.entries(daily)
    .map(([date, v]) => ({ date, orders: v.orders, revenue: Math.round(v.revenue * 100) / 100 }))
    .sort((a, b) => a.date.localeCompare(b.date));

  // ── market: roll signups + revenue up by the creator's language ───────────
  const codeLang: Record<string, string> = {};
  for (const c of creators as { affiliate_code: string; language: string | null }[]) {
    codeLang[c.affiliate_code] = (c.language ?? "en").toUpperCase();
  }
  const market: Record<string, { signups: number; orders: number; revenue: number }> = {};
  const ensure = (l: string) => (market[l] ??= { signups: 0, orders: 0, revenue: 0 });
  for (const [code, n] of Object.entries(signupCounts)) {
    ensure(codeLang[code] ?? "—").signups += n;
  }
  for (const r of revenue) {
    if (!r.affiliate_code) continue;
    const m = ensure(codeLang[r.affiliate_code] ?? "—");
    m.orders += 1;
    m.revenue += r.revenue_cents / 100;
  }

  return NextResponse.json({
    creators,
    signupCounts,
    revenueAgg,
    sales: {
      totalOrders, totalRevenue: Math.round(totalRevenue * 100) / 100,
      attributedOrders, attributedRevenue: Math.round(attributedRevenue * 100) / 100,
      byPlan,
    },
    timeline,
    market,
    totalSignups: signups.length,
    attributedSignups: signups.filter((s) => s.referred_by_code).length,
  });
}
