/**
 * GET /api/admin/session — is this browser signed in to the admin dashboard?
 *
 * The UI gate reads this instead of comparing a PIN in the browser. Until
 * 2026-09-27 AdminShell compared against NEXT_PUBLIC_ADMIN_PIN — inlined into
 * the client bundle, and the SAME value as the server-side ADMIN_PIN — so the
 * PIN that mints a real session cookie could be read out of the page's JS.
 */
import { NextResponse } from "next/server";
import { adminAuthConfigured, isAdminRequest } from "@/lib/adminAuth";

export async function GET(req: Request) {
  const cfg = adminAuthConfigured();
  return NextResponse.json(
    { authenticated: cfg.ok && isAdminRequest(req), configured: cfg.ok, missing: cfg.missing },
    { headers: { "cache-control": "no-store" } },
  );
}
