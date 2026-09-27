/**
 * POST /api/admin/login — exchange the admin PIN for a signed session cookie.
 *
 * The PIN is compared server-side against ADMIN_PIN. (NEXT_PUBLIC_ADMIN_PIN,
 * which the browser used to compare against, is gone as of 2026-09-27 — it
 * was the same value and shipped in the bundle.) The response sets an httpOnly cookie
 * that the service-role write routes require.
 */

import { NextResponse } from "next/server";
import { ADMIN_COOKIE, adminAuthConfigured, mintSession, verifyPin } from "@/lib/adminAuth";

// Failed-PIN limiter. The PIN is short, and this route mints a session that
// unlocks the service-role Supabase proxy and the ops-key API proxy, so it must
// not accept unlimited guesses. In memory, per client address: fine for one
// dashboard process; a multi-instance deploy would need a shared store.
const MAX_FAILURES = 5;
const WINDOW_MS = 15 * 60 * 1000;
const failures = new Map<string, number[]>();

function clientKey(req: Request): string {
  return (req.headers.get("x-forwarded-for") ?? "").split(",")[0].trim() || "local";
}

function recentFailures(key: string): number[] {
  const now = Date.now();
  const kept = (failures.get(key) ?? []).filter((t) => now - t < WINDOW_MS);
  failures.set(key, kept);
  return kept;
}

export async function POST(req: Request) {
  const key = clientKey(req);
  if (recentFailures(key).length >= MAX_FAILURES) {
    return NextResponse.json(
      { error: "Too many wrong PINs. Try again in 15 minutes." },
      { status: 429 },
    );
  }

  const cfg = adminAuthConfigured();
  if (!cfg.ok) {
    return NextResponse.json(
      { error: `Admin auth not configured. Missing: ${cfg.missing.join(", ")}` },
      { status: 503 },
    );
  }

  let pin = "";
  try {
    pin = String(((await req.json()) as { pin?: unknown }).pin ?? "");
  } catch {
    return NextResponse.json({ error: "Malformed body" }, { status: 400 });
  }

  if (!verifyPin(pin)) {
    recentFailures(key).push(Date.now());
    return NextResponse.json({ error: "Invalid PIN" }, { status: 401 });
  }
  failures.delete(key);

  const token = mintSession();
  if (!token) {
    return NextResponse.json({ error: "Session secret unavailable" }, { status: 503 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(ADMIN_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 8 * 60 * 60,
  });
  return res;
}
