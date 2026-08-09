/**
 * Server-side admin gate.
 *
 * The existing PIN check (AdminShell.tsx) reads NEXT_PUBLIC_ADMIN_PIN, which is
 * inlined into the client bundle, compares it in the browser, and remembers the
 * result in sessionStorage. That is fine for keeping a casual visitor out of the
 * UI, but it authenticates nothing — anyone can read the PIN from the bundle or
 * set the sessionStorage key directly.
 *
 * The service-role key must never sit behind a gate like that, because it
 * bypasses RLS on the production database. This module is the server-only half:
 * the PIN is compared in a route handler against a NON-public env var, and
 * success mints a short-lived HMAC-signed httpOnly cookie the browser cannot
 * forge or read.
 *
 * Required server-only env (never prefix these with NEXT_PUBLIC_):
 *   ADMIN_PIN                 — the real PIN, server side only
 *   ADMIN_SESSION_SECRET      — random string used to sign session cookies
 *   SUPABASE_SERVICE_ROLE_KEY — used by the write routes
 */

import { createHmac, timingSafeEqual } from "node:crypto";

export const ADMIN_COOKIE = "admin_session";
const SESSION_TTL_MS = 8 * 60 * 60 * 1000; // 8h

function sign(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(payload).digest("base64url");
}

function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

/** Compare a submitted PIN against the server-only ADMIN_PIN. */
export function verifyPin(pin: string): boolean {
  const expected = process.env.ADMIN_PIN ?? "";
  // Fail closed. An unset PIN must never mean "everyone is an admin".
  if (!expected || !pin) return false;
  return safeEqual(pin, expected);
}

/** Mint a signed session token: "<expiryMs>.<hmac>". */
export function mintSession(): string | null {
  const secret = process.env.ADMIN_SESSION_SECRET ?? "";
  if (!secret) return null;
  const exp = String(Date.now() + SESSION_TTL_MS);
  return `${exp}.${sign(exp, secret)}`;
}

/** Validate a session cookie value. */
export function verifySession(token: string | undefined): boolean {
  const secret = process.env.ADMIN_SESSION_SECRET ?? "";
  if (!secret || !token) return false;

  const dot = token.lastIndexOf(".");
  if (dot < 1) return false;

  const exp = token.slice(0, dot);
  const mac = token.slice(dot + 1);
  if (!safeEqual(mac, sign(exp, secret))) return false;

  const expiryMs = Number(exp);
  return Number.isFinite(expiryMs) && expiryMs > Date.now();
}

/** True when the request carries a valid admin session cookie. */
export function isAdminRequest(req: Request): boolean {
  const cookie = req.headers.get("cookie") ?? "";
  const match = cookie.match(new RegExp(`(?:^|;\\s*)${ADMIN_COOKIE}=([^;]+)`));
  return verifySession(match?.[1]);
}

/** Configuration completeness — surfaced by the routes so misconfig isn't silent. */
export function adminAuthConfigured(): { ok: boolean; missing: string[] } {
  const missing: string[] = [];
  if (!process.env.ADMIN_PIN) missing.push("ADMIN_PIN");
  if (!process.env.ADMIN_SESSION_SECRET) missing.push("ADMIN_SESSION_SECRET");
  if (!process.env.SUPABASE_SERVICE_ROLE_KEY) missing.push("SUPABASE_SERVICE_ROLE_KEY");
  return { ok: missing.length === 0, missing };
}
