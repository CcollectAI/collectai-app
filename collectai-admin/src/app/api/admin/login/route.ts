/**
 * POST /api/admin/login — exchange the admin PIN for a signed session cookie.
 *
 * The PIN is compared server-side against ADMIN_PIN (not NEXT_PUBLIC_ADMIN_PIN),
 * so it never reaches the browser bundle. The response sets an httpOnly cookie
 * that the service-role write routes require.
 */

import { NextResponse } from "next/server";
import { ADMIN_COOKIE, adminAuthConfigured, mintSession, verifyPin } from "@/lib/adminAuth";

export async function POST(req: Request) {
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
    return NextResponse.json({ error: "Invalid PIN" }, { status: 401 });
  }

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
