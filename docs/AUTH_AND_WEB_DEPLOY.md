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

## ⚠️ The apex domain 307s to `www` — Universal Links are dead at the apex

**Found 2026-07-30. Not fixed — both fixes are outward-facing config changes.**

The verification command at the bottom of this file no longer passes:

```
curl -sD- -o/dev/null https://sparrowcollect.com/.well-known/apple-app-site-association
  HTTP/2 307
  location: https://www.sparrowcollect.com/.well-known/apple-app-site-association
```

`www` serves the file correctly (HTTP 200, right `appIDs`, `/auth/*` present). The
apex redirects. **Apple does not follow redirects when fetching AASA** — the file
must be served directly over https — so the apex domain has no valid
app-site association. `/auth/confirm` behaves the same way (apex 307 → www 200).

The redirect is **not** in `web/vercel.json`; it is Vercel domain config
(apex → www) in the `collectais-projects` dashboard.

### What this does and does not break

Traced end-to-end with a real signup (mail.tm + `/auth/v1/signup`) on 2026-07-30:

| Step | Result |
|------|--------|
| Supabase `/auth/v1/verify` | **303** → `https://sparrowcollect.com/auth/confirm#access_token=…` |
| that apex URL | **307** → `https://www.sparrowcollect.com/auth/confirm` |
| `www` confirm page | **200**, forwards the fragment to `sparrow://` |

So **the flow still completes** — the browser reattaches the `#fragment` across a
redirect whose `Location` carries none, and the branded page hands off to the app.
What is lost:

- the **direct** app open. `emailRedirectTo` targets the apex, so iOS cannot match
  it to the app and always opens Safari first — the browser detour this file's
  design was written to avoid.
- **`webcredentials`** at the apex (Password AutoFill association).

### Two ways to fix — both need a decision, neither was taken

1. **Serve the apex directly** (stop redirecting apex → www in Vercel). Keeps
   `emailRedirectTo` as-is and needs no Supabase change. Preferred.
2. **Point `emailRedirectTo` at `www`** in `register.tsx` + `forgot-password.tsx`.
   Then `https://www.sparrowcollect.com/**` **must** be added to the Supabase
   redirect allowlist — the current entry is the apex only, and `www` is a
   different host, so this fails closed if forgotten.

Also drifted: prod's AASA is missing `/r/*` (referral links) which the repo has,
and is served as `application/octet-stream` though `web/vercel.json` sets
`application/json`. Both indicate **`web/` is deployed from an older commit** —
redeploy per the Vercel section below.

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
