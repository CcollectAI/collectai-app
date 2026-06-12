# TestFlight QA Checklist — Sparrow Collect

> **Use this for every new TestFlight build.** Most recent build at time of
> last refresh: **v1.0.0 build #64** (eas auto-increment, profile `store`,
> `BETA_UNLOCK_ALL=false`). Each section is independent — start with the
> golden path, then loop the others. Anything red or behaving weird,
> note it and we fix before submitting for App Store review.
>
> Total time on the happy path: ~10 minutes. Full sweep: ~30 minutes.

## Pre-flight

- [ ] TestFlight app installed on iPhone
- [ ] You appear in App Store Connect → TestFlight → Internal Testing
- [ ] Latest build shows "Ready to Test" in TestFlight app (not "Processing")
- [ ] Install button visible in TestFlight; tap it
- [ ] App icon (Sparrow logo, Tiffany Blue gradient) appears on Home Screen
- [ ] Launching the app shows the splash screen, not a black-screen-of-death

## What changed since the previous build (build #3, buildNumber 9 — 2026-05-12)

Build #13 includes the **2026-05-18 onboarding rework** (commit `d0c4713`):
- Age checkbox → point-of-sale seller gate (HTTP 412 from BE + auto-modal in `httpClient` + retry)
- Followed categories now drive: add-flow sort, scan classifier prior, AI catalog-match tiebreaker, home empty state, Deal Hub filter
- Auth bug fixes: OfflineBanner status-bar bleed; AuthTextInput tap-eating label; onboarding completion loop; Skip-button bypass

When running through QA, give those flows extra attention — see Section 1 (auth) and any new "Followed categories" surface.

If splash → main app transition takes >5 seconds, something's slow. Note the time.

---

## Section 1 — Auth flow (golden path)

> **Email/password only at launch.** Apple/Google social sign-in is hidden
> (`SOCIAL_LOGIN_ENABLED=false` in `src/config/featureFlags.ts`; Supabase
> social providers not configured). Do NOT test "Sign in with Apple/Google" —
> those buttons are intentionally absent. (Subscriptions still use Apple/Google
> IAP billing — that's separate from auth.)
>
> Email confirmation is ON. The confirmation link goes to
> `https://sparrowcollect.com/auth/confirm` (an https Universal Link that hands
> off to the app), not a `sparrow://` link directly.

- [ ] Open the app fresh (sign out first if you're auto-logged in from a previous build)
- [ ] Tap **Sign Up** → enter a brand-new email (use `+test@` aliasing to keep your inbox clean: `slendebroekmerle+sparrow1@gmail.com`)
- [ ] Pick a password
- [ ] Tap continue → confirm Supabase emails it (open Gmail → click confirmation link)
- [ ] App should auto-launch back to the home screen on tap of the confirmation link
- [ ] Home screen shows your collection (empty state — that's correct on a fresh account)
- [ ] Profile / Settings shows your email correctly

**Note any:** error toasts, blank screens, crashes, slow auth (>10s).

---

## Section 2 — Quick Scan flow (core feature)

This is the most critical flow Apple's reviewer will exercise.

- [ ] From home screen, tap the **Quick Scan / camera** button
- [ ] iOS permission prompt appears with **"Sparrow needs camera access to scan and photograph your collectibles."** (your custom string from app.json)
- [ ] Tap **Allow**
- [ ] Camera viewfinder opens
- [ ] Point at any collectible (any card, figure, vinyl — even non-collectible items work to test the flow)
- [ ] Snap a photo
- [ ] Loading state appears ("Analyzing…" / spinner)
- [ ] Within ~5-10 seconds, result screen shows: item name, category, price range, condition guess
- [ ] Buttons visible: "Add to collection" / "Try another"
- [ ] Tap **Add to collection** → item should appear in the Collection tab

**Note any:** stuck on "Analyzing" >20s, identification clearly wrong for an obvious item, no price shown, "Add" button doesn't work, app crashes after photo capture.

---

## Section 3 — Photo Library scan

- [ ] From Quick Scan screen, tap the "Photo Library" / gallery icon
- [ ] iOS permission prompt: **"Sparrow needs access to your photo library to add item photos and analyze screenshots."**
- [ ] Allow → pick any photo
- [ ] Same identification flow as Section 2
- [ ] Result + add-to-collection works

---

## Section 4 — Collection view

- [ ] Bottom nav → **Collection** tab
- [ ] Items you added in Sections 2-3 appear
- [ ] Tap any item → detail view opens
- [ ] Item detail shows: photo, name, price prediction (low/mid/high), category
- [ ] Tap back → returns to collection list (no crash, no scroll lost)
- [ ] Try long-press / swipe an item → contextual menu or delete affordance works

---

## Section 5 — Paywalled features (BETA — all should be UNLOCKED)

This is the test for `EXPO_PUBLIC_BETA_UNLOCK_ALL=true`. **Every paywall
should be open**, no "Upgrade to Pro" CTAs should be visible.

- [ ] Bottom nav → **Analytics** tab (or wherever you have it) — should load chart UI, NOT a paywall card
- [ ] Side drawer → **Deal Discovery** / **Deal Hub** → should show deal listings, NOT a locked state
- [ ] Side drawer → **Sets to Complete** → should show set tracker UI, NOT "Upgrade to unlock"
- [ ] Item detail → Advanced Predictions → should show q10/q50/q90 charts, NOT a lock icon
- [ ] Settings → **Subscription** → should render **"You're in the Sparrow beta — every Pro feature unlocked for free"** info card, NOT plan cards
- [ ] Verify NO "Upgrade to Pro" button anywhere in the app

If a paywall IS showing during beta, that means `EXPO_PUBLIC_BETA_UNLOCK_ALL` didn't reach the build (EAS env miswire). Note which screen and we'll re-trigger a build.

---

## Section 6 — Settings, Profile, Sign-out

- [ ] Settings → all sections load (Account, Notifications, Privacy, Appearance, etc.)
- [ ] Profile → display name editable, photo upload works
- [ ] Toggle dark mode → app re-renders in dark theme, NO white flashes
- [ ] Currency picker → can change between EUR / USD / GBP — prices in Collection reflect the new currency
- [ ] Sign out → returns to auth screen
- [ ] Sign back in with the same email → collection items still there

---

## Section 7 — Deep links + universal links

- [ ] In Safari, type `sparrow://settings` → app opens to Settings
- [ ] Type `sparrow://subscription` → app opens to the beta info card
- [ ] On the Sparrow website (https://sparrowcollect.com), tap any "Open in app" link if you have one — should hand off to the installed app via universal link

---

## Section 8 — Permissions + privacy

- [ ] App Settings (iOS Settings app → Sparrow Collect) → all granted permissions match what the app actually uses (Camera, Photos, Location When in Use, Calendar, Reminders)
- [ ] Toggle Camera permission OFF → return to app → Quick Scan should show a permission-denied state with re-prompt, NOT crash
- [ ] Re-enable, return to app

---

## Section 9 — Network / offline behaviour

- [ ] Enable Airplane Mode → open the app
- [ ] Should show offline state or cached data, NOT a crash
- [ ] Disable Airplane Mode → data refreshes within ~10 seconds

---

## Section 10 — Crash audit

- [ ] Background the app → foreground it → no relaunch needed
- [ ] Rotate phone (if rotation supported) → UI re-flows correctly
- [ ] Run for ~5 minutes touching different screens → no memory crashes, no spinning beach ball

If you see ANY crash in this section, check Sentry (if configured) or rerun and capture an iOS device-log snapshot:
- iPhone → Settings → Privacy & Security → Analytics & Improvements → Analytics Data → look for `Sparrow-…-ips`
- Email yourself the .ips file for investigation

---

## What to flag back to me

When you finish, paste back:
1. ✅ All passed
2. ❌ Specific section + screen + what went wrong (screenshot if you can)
3. ⚠️ Anything that worked but felt slow / off

Most likely outcomes:

| Symptom | Probable cause |
|---|---|
| Auth signup fails | Supabase URL/key mismatch in EAS env |
| Scan times out | Backend rate-limit or model-loading delay; check `/healthz` |
| Paywall still shows in Settings | `EXPO_PUBLIC_BETA_UNLOCK_ALL` not reaching the build |
| App crashes on launch | Native module missing — check EAS build log |
| Permission prompts look wrong | `app.json` infoPlist regression |

---

## When everything passes

You're cleared to move to **Phase 1 of `docs/PUBLIC_LAUNCH_CHECKLIST.md`** — start creating the ASC IAP products. The TestFlight beta validates the same binary that'll be reviewed by Apple (modulo the `store` profile which flips the beta flag off).
