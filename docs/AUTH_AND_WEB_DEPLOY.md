# Auth (email confirm/reset) + web deploy

How the email-confirmation / password-reset deep-link flow works, the Supabase
config it depends on, and how to deploy `web/`. Written 2026-06-12 after the
"address is invalid" confirm-link bug.

## The deep-link confirm/reset flow

A raw `sparrow://` `emailRedirectTo` makes iOS Safari show **"address is invalid"**
when the email link redirects to a custom scheme. So we redirect to an **https
Universal Link** instead:

1. **App** (`app/(auth)/register.tsx` signup, `app/(auth)/forgot-password.tsx` reset)
   sets the redirect to `https://sparrowcollect.com/auth/confirm`.
2. **Supabase** verifies the token, then 302-redirects to
   `https://sparrowcollect.com/auth/confirm#access_token=...&refresh_token=...&type=...`.
3. **`web/auth/confirm.html`** loads (branded, public) and its JS forwards the
   `#fragment` to `sparrow://#...`.
4. **`src/providers/AuthProvider.tsx`** has a `Linking` handler that parses the
   fragment and calls `supabase.auth.setSession(...)`. If `type=recovery`, it sets
   the `src/auth/recoveryState.ts` flag and routes to `app/(auth)/reset-password.tsx`;
   the root gate in `app/_layout.tsx` honors that flag (and excludes the reset
   screen from its normal redirects). Otherwise the user lands signed-in → onboarding.
5. **Universal Links**: `web/.well-known/apple-app-site-association` maps
   `appIDs: ["3DX8FBF7S6.io.sparrowcollect.app"]`, `paths: [..., "/auth/*"]`, and
   `app.json` has `associatedDomains: applinks:sparrowcollect.com`. (Earlier this
   file had placeholder `TEAM_ID.com.sparrowcollect.app` — broken app-wide.)

If the app isn't installed, `/auth/confirm` is a graceful branded web page.

## Apex domain serves directly — do not re-add a redirect

**2026-07-30: the apex `sparrowcollect.com` was redirecting (307) to `www`, which
silently broke Universal Links. Fixed by clearing the redirect. Do not restore it.**

Apple **does not follow redirects** when fetching
`/.well-known/apple-app-site-association` — the file must be served directly over
https. While the apex redirected, it had no valid app-site association, so
`emailRedirectTo` (which targets the apex) could never open the app: iOS opened
Safari, and only the branded page's `sparrow://` hand-off completed the flow.
`webcredentials`/Password AutoFill was unassociated at the apex for the same reason.

The redirect was **not** in `web/vercel.json` — it was Vercel project domain config.
Inspect or change it via the REST API (the CLI cannot show it):

```bash
TOKEN=$(python3 -c "import json;print(json.load(open('$HOME/Library/Application Support/com.vercel.cli/auth.json'))['token'])")
TEAM=team_pNV3OxYiiWRDhC96aN2H3Tm5   # collectais-projects
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.vercel.com/v9/projects/sparrowcollect/domains?teamId=$TEAM"
# to clear:  -X PATCH -d '{"redirect":null}' .../domains/sparrowcollect.com?teamId=$TEAM
```

Apex is the right canonical host: every `<link rel="canonical">`, `og:url` and
`sitemap.xml` entry in `web/` already points at `https://sparrowcollect.com`, and
so does `emailRedirectTo`. Both apex and `www` now serve directly (200) and both
are in `app.json` `associatedDomains`.

Verified after the fix — this is the check to re-run:
```
curl -sD- -o/dev/null https://sparrowcollect.com/.well-known/apple-app-site-association   # 200, appIDs 3DX8FBF7S6…
curl -o /dev/null -w "%%{http_code}" https://sparrowcollect.com/auth/confirm              # 200
```

### `web/` redeployed 2026-07-30 — drift cleared

Prod had been serving a build older than `8f03de3`. Redeployed per the procedure
below; verified live afterwards:

- AASA now lists `/r/*` (referral universal links) — `['/r/*', '/item/*', '/events/*', '/categories/*', '/purchase/*', '/users/*', '/auth/*']`
- AASA content-type is now `application/json` (was `application/octet-stream`),
  matching the header rule in `web/vercel.json`
- `/auth/confirm`, `/pro`, `/` all 200 on both apex and `www`; the confirm page
  still forwards the fragment to `sparrow://`

`web/pro.html` had a literal `REPLACE_WITH_REAL_ANON_KEY` placeholder; filled in
with the project anon key (public by design — RLS governs access, and it is the
same value the app bundles as `EXPO_PUBLIC_SUPABASE_ANON_KEY`). Verified against
the project before deploying: `/auth/v1/settings` 200, an RLS-scoped
`/rest/v1/profiles` read 200.

### ⚠️ `/pro` is live but CANNOT take payment — Stripe web prices unset

The page signs in and reaches checkout, then
`POST /billing/web/checkout-session` returns **503**:

```
"Web Stripe Price ID not configured for pro/monthly. Set STRIPE_PRICE_PRO_MONTHLY_WEB."
```

On EC2 (`/opt/collectors/.env`):

| Var | State |
|-----|-------|
| `STRIPE_SECRET_KEY` | set, but **`sk_test_…` — test mode** |
| `STRIPE_PRICE_PRO_MONTHLY` / `_YEARLY` | set (`price_1T…`) |
| `STRIPE_PRICE_PRO_MONTHLY_WEB` / `_YEARLY_WEB` | **empty** — what the web checkout reads |

So web subscriptions cannot be sold yet. Two things are needed: the `_WEB` price
IDs, and a **live** secret key (`sk_live_…`) before real money can move.

Exposure is limited meanwhile, and already handled — verified live 2026-07-31:

- `/pro` is **not linked from any public page** and is **not in `sitemap.xml`**;
  only `pro/cancel.html` links back to it.
- all three pages (`pro.html`, `pro/success.html`, `pro/cancel.html`) already
  ship `<meta name="robots" content="noindex,nofollow">`. Nothing to add.
- the public pages (`/`, `guides.html`, …) carry no robots meta, so they remain
  indexable — the noindex is scoped to `/pro*` only.

**When Stripe goes live, removing that `noindex,nofollow` from the three pro
pages is part of the switch-on** — otherwise the pricing page sells nothing
because no one can find it.

## Supabase auth config (project `ykqrruipzmrrvjcvwfgp`)

- **Site URL**: `https://sparrowcollect.com`
- **Redirect allowlist**: `sparrow://**, https://sparrowcollect.com/**, collectai://**`
- **Email confirmation**: ON (`mailer_autoconfirm=false`)
- **SMTP**: Resend — `smtp.resend.com:465`, user `resend`, sender
  `noreply@sparrowcollect.com` / "Sparrow Collect" (see `supabase/templates/SMTP_SETUP.md`)
- **Templates**: 6 branded, tiffany `#44A9A1` (see `supabase/templates/`)

Editing config via the Management API: send a **browser `User-Agent`** or Cloudflare
returns **HTTP 403 error 1010**. `GET/PATCH https://api.supabase.com/v1/projects/ykqrruipzmrrvjcvwfgp/config/auth`,
fields `site_url`, `uri_allow_list`, `mailer_templates_*_content`, `mailer_subjects_*`.

## MFA (TOTP) — `app/mfa-setup.tsx`

Entirely client-side via the Supabase SDK: `mfa.listFactors()` → `mfa.enroll()`
→ `mfa.challenge()` → `mfa.verify()` → `mfa.unenroll()`. No EC2 route involved.

Verified end to end 2026-07-31 against prod with a throwaway user and a
self-generated RFC 6238 code (no authenticator app needed — 20 lines of hmac):

| Step | Result |
|------|--------|
| `POST /auth/v1/factors` (enroll) | 200, returns `totp.qr_code` + `totp.secret` |
| `POST /auth/v1/factors/{id}/challenge` | 200 |
| verify with a correct TOTP code | 200, elevated token returned |
| verify with `000000` | **422** — correctly rejected |
| `DELETE /auth/v1/factors/{id}` (unenroll) | 200 |

`GET /auth/v1/factors` returns **405** — factors are read from the user object,
which is what `listFactors()` does. Not a bug; don't "fix" it.

### The abandoned-enrollment trap (fixed 2026-07-31)

Tapping **Enable** creates an `unverified` factor immediately. If the user walks
away without entering a code it persists, and because `friendlyName` is a
constant the next attempt fails:

```
422  A factor with the friendly name "Sparrow Collect Authenticator" for this user already exists
```

The factor list renders only `status === 'verified'` factors, so there was no
Remove button for it, and `hasVerifiedFactor` stayed false — the user was
offered **Enable** forever and it failed every time, with no way out of the UI.
Reproduced against Supabase, then fixed: `handleEnroll` now unenrolls any
non-verified factor before enrolling (an unverified factor grants nothing).
Re-verified: the second enroll returns 200 where it previously returned 422.

**If `friendlyName` is ever made user-editable, keep the cleanup** — the
collision is on that name.

## Login is email-only (App Store guideline 4.8)

Apple/Google sign-in is hidden behind **`SOCIAL_LOGIN_ENABLED=false`**
(`src/config/featureFlags.ts`). Email-only avoids 4.8 (offering Google requires
also offering Apple) and the broken-button rejection. To enable later: configure
the Apple Services-ID/key + Google OAuth client in Supabase, then flip the flag.

## Deploying `web/` — the Vercel account gotcha

`web/` (marketing site + AASA + `/auth/confirm`) lives under the Vercel team
**`collectais-projects`** ("CollectAI's projects"), project **`sparrowcollect`**
— which owns `sparrowcollect.com` + `www`. It is **NOT** under Merle's personal
Vercel account (`eusammysam-2709` / "Merle's projects"), which can't see it.

> Deploying while logged into the personal account leads Vercel down the
> "create a NEW project" path → a duplicate that does **not** own the domain.
> Don't do that.

**Correct deploy:**
```bash
vercel login           # the account that owns collectais-projects (e.g. ccollect.ai@gmail.com)
vercel teams ls        # confirm "collectais-projects" is listed
cd web
rm -rf .vercel
vercel link --yes --project sparrowcollect --scope collectais-projects
vercel --prod --scope collectais-projects
```
Notes:
- Find the project owning the domain: `vercel domains inspect sparrowcollect.com --scope collectais-projects`.
- Preview `*.vercel.app` URLs require auth (**Deployment Protection**); the production
  custom domain serves publicly. Static HTML edge-caches a few minutes post-deploy.
- Verify live: `curl https://sparrowcollect.com/.well-known/apple-app-site-association`
  (should show `3DX8FBF7S6...` + `/auth/*`) and `curl -o /dev/null -w "%{http_code}" https://sparrowcollect.com/auth/confirm` (200).

## Testing the email end-to-end (no real inbox needed)

mail.tm disposable-inbox API + Supabase `/auth/v1/signup` (public anon key): create
inbox → poll `/messages` → read `/sources/{id}` or `/messages/{id}` for headers/HTML.
Confirms From, DKIM `d=sparrowcollect.com` alignment (passes strict DMARC), and the
tiffany body. **Always** clean up: `DELETE FROM auth.users WHERE email LIKE 'sparrowtest%@web-library.net'`.

Cleaner cleanup, since deleting from `auth.users` by hand can leave orphans —
use the admin API with `SUPABASE_SERVICE_KEY` from `/opt/collectors/.env`:
`DELETE {SUPABASE_URL}/auth/v1/admin/users/{id}` (cascades to `profiles`).

Pass `?redirect_to=<url-encoded>` on `/auth/v1/signup` and `/auth/v1/recover`, or
Supabase silently falls back to the **Site URL** and you end up testing a link the
app never sends. That cost a run on 2026-07-30.

### Full chain, verified 2026-07-30 (all green)

| Check | Result |
|-------|--------|
| signup | 200, confirmation email sent |
| login **before** confirming | 400 `email_not_confirmed` — correct, `mailer_autoconfirm=false` |
| confirm email | from `noreply@sparrowcollect.com`, subject "Confirm Your Sparrow Collect Account", tiffany `#44A9A1` present |
| confirm link | 303, `#access_token` delivered |
| login **after** confirming | 200, access + refresh tokens |
| login with wrong password | 400 |
| `/auth/v1/recover` | 200, "Reset Your Sparrow Collect Password" |
| reset link | 303, fragment carries **`type=recovery`** + tokens — what `AuthProvider` needs to set the `recoveryState` flag and route to `reset-password.tsx` |
| signup trigger | `handle_new_user` wrote both `username` and `display_name` from signup metadata |

The only defect found was the apex-domain redirect documented at the top of this file.
