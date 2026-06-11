# New-tester smoke test — signup → branded email → confirm → onboarding

What "working" looks like end to end when you invite a fresh tester. Tick top to
bottom; the **If it fails** notes cover the usual snags.

## Phase 0 — Before you invite (one-time)
- [ ] **Confirm signup** email template pasted + saved in Supabase (Auth → Email Templates). *This is the only one the signup flow uses.*
- [ ] Build **#60** shows **Ready to Submit / in TestFlight** in App Store Connect (not stuck "Processing"). Auto-submit was scheduled from EAS.
- [ ] Supabase → Auth → **URL Configuration**: redirect allowlist includes the app scheme (`io.sparrowcollect.app` / `sparrow://`) and `https://sparrowcollect.com`.
  - *If it fails:* the confirm link dead-ends. Add the URLs and re-test.

## Phase 1 — TestFlight delivery
- [ ] Add the tester in **App Store Connect → TestFlight** (internal = instant; external = needs a quick Beta App Review) — or send them the public TestFlight link.
- [ ] Tester gets Apple's TestFlight invite → installs **TestFlight** → installs **Sparrow Collect**.
- [ ] App opens to the auth/welcome screen, branded (Tiffany, sparrow logo).

## Phase 2 — Signup
- [ ] Tester taps **Sign up**, enters a real email they can open + a password.
- [ ] App advances to the **"Check your inbox" verify-email screen** (pulsing mail icon, the tester's email shown, a Resend button).
  - *If it fails (error on submit):* check Supabase Auth is enabled for email/password and you haven't hit the default-sender rate limit (~3–4/hour — wait or use a different email).

## Phase 3 — The branded email
- [ ] Email arrives within a minute (**check Spam/Promotions** — default sender is `…@mail.app.supabase.io` until SMTP is set up).
- [ ] It renders **branded**: "Sparrow Collect" wordmark + logo, deep-tiffany **Confirm my email** button, the fallback link, and the "we'll never ask for your password" line.
- [ ] Subject reads **"Confirm your email — Sparrow Collect"**.
  - *If it's the old plain email:* the template wasn't saved — re-paste `confirmation.html` into Confirm signup and save.
  - *If the logo is missing but text shows:* fine — images are often blocked; the wordmark is intentional insurance.

## Phase 4 — Confirm + onboarding
- [ ] Tester taps **Confirm my email** → link confirms the account.
- [ ] Back in the app, the verify screen **auto-detects** confirmation (it polls every ~5s) and moves to **onboarding** — no manual step.
  - *If it sits on the verify screen:* close/reopen the app, or tap "Go to sign in" and log in; means confirmation succeeded but the poll missed.
- [ ] Onboarding runs: age/seller gate → **follow a few categories** → lands in the app.

## Phase 5 — Quick app sanity (new account)
- [ ] **Items** tab shows the "Add your first item" hero (empty state), not a broken screen.
- [ ] **Events** tab shows real upcoming events (ingestion is back on — should not be empty).
- [ ] A category page opens and renders (museum layout, prices).
- [ ] No crash / infinite spinner on the main tabs.

## Backend confirmation (optional, your side)
- [ ] In Supabase → Authentication → Users, the new user exists with **email_confirmed_at** set.

---
**Done = green** when the tester goes signup → branded email → confirm → onboarding →
into a working app without you intervening. The only thing still on the default
(non-branded) sender is the *From address* — that's the Resend/SMTP step
(`SMTP_SETUP.md`), separate from this test.
