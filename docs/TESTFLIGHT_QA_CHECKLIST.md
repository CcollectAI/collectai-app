# TestFlight QA Checklist — Sparrow Collect

> **Use this for every new TestFlight build.** Most recent build at time of
> last refresh: **v1.0.0 build #67** (eas auto-increment, profile `store`,
> `BETA_UNLOCK_ALL=false`). Each section is independent — start with the
> golden path, then loop the others. Anything red or behaving weird,
> note it and we fix before submitting for App Store review.
>
> Total time on the happy path: ~10 minutes. Full sweep: ~30 minutes.

## What changed in build #67 (2026-06-13) — QuickScan & manual-add

Give these flows extra attention this build:

- **QuickScan 8s timeout** — if a scan takes longer than ~4s the analyzing
  screen shows "This is taking longer than expected…"; at 8s it stops waiting
  and drops you into **Add Manually** instead of spinning forever.
- **Scan → manual-add handoff** — when a scan times out or comes back
  low-confidence, the snapped photo persists into Add Manually, and on the
  low-confidence path the vision-extracted **name / category / condition /
  attributes are pre-filled** so you confirm rather than retype.
- **"Looks like…" tag removed** from both the camera viewfinder and the
  analyzing screen (it was often wrong).
- **Add-Manually photo upload fixed** — uploads no longer fail on a 5s
  timeout (multipart now gets a 60s budget). Verify a gallery/camera photo
  attaches and shows on the saved item.
- **Add-Manually category dropdown** now lifts above the keyboard (both the
  list and the search box stay visible while typing).
- **Add-Manually polish** — redundant "Manual Entry" intro banner removed;
  the save toast no longer claims "~5 min saved" (that's QuickScan-only).
- **Home empty state** now reads the generic "Add your first item" regardless
  of onboarding category picks.

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

## Section 4b — Spreadsheet import + watchlist acquire

> **Added 2026-07-28.** Both flows returned success while silently dropping
> data, and the watchlist one 500'd outright. Neither had a QA row, and no
> automated test covered them. Check the **values**, not just that the row
> appears — a structurally-valid row with a NULL half is exactly what shipped.

- [ ] Add tab → **Import from spreadsheet** → download the template
- [ ] Import the filled template as **.csv** → success count matches your rows
- [ ] Import the same data as **.xlsx** → same result (Excel path uses `openpyxl`)
- [ ] Imported items appear on the **Home portfolio with their names visible**
      (not blank / "Untitled" — Home reads `name`, the Items tab reads `title`,
      so an item can look correct on one screen and blank on the other)
- [ ] Open an imported item → purchase price, currency, condition, grade and
      purchase date all match the spreadsheet
- [ ] The purchase date is the **same day** you typed, not the day before
      (timezone off-by-one)
- [ ] Analytics tab → **Cost Basis** reflects the imported purchase prices
- [ ] Import a row priced in a **non-EUR** currency → cost basis shows the
      FX-converted amount, not the raw number relabelled as EUR
- [ ] Watchlist → **"I Got It!"** on an item → converts to a collection item
      without an error toast, and the watchlist row disappears
- [ ] That acquired item's cost basis is in **your** currency, converted —
      set Settings → Currency to USD first to make the bug visible

### Subscription screen (added 2026-07-28)

> The RevenueCat key is injected from the EAS **production** environment, not
> from local `.env`. A dev/Metro run therefore shows "Subscriptions Coming
> Soon" — that is expected locally and proves nothing about this build. On
> TestFlight the offerings should load.

- [ ] Subscription screen shows **plan cards with real prices** (€4.99/mo,
      €39.99/yr), not "Subscriptions Coming Soon". If it says Coming Soon on
      TestFlight, `EXPO_PUBLIC_REVENUECAT_IOS_KEY` did not reach the build or
      the RevenueCat `default` offering is misconfigured.
- [ ] **Settings → Appearance → High Contrast + Dark**, then reopen this
      screen: the Upgrade button label and the RECOMMENDED badge must be
      **readable**. This shipped as white-on-white (invisible) until
      2026-07-28 — it is invisible in exactly one of four palettes, so it must
      be checked in that one.
- [ ] Screen fades/slides in like the rest of the app (it had no enter
      animation before 2026-07-28)
- [ ] Restore / Manage buttons align with the content edges on the screens
      either side of it
- [ ] Buy a plan with the **sandbox account** (`sandbox-merle@sparrowcollect.com`
      — sign in first via iPhone Settings → App Store → Sandbox Account).
      This cannot be tested in the simulator.
- [ ] After purchase, Pro features unlock (Home "Extended Portfolio Insights"
      opens **/analytics**, not the paywall)
- [ ] **Restore Purchases** on a second device / after reinstall re-grants Pro

### Cost basis / P&L (added 2026-07-28)

> Every one of these read a model estimate where it should have read what you
> actually paid. They looked plausible, which is the problem — check them
> against a purchase price you know.

- [ ] Add an item with a purchase price **well above or below** its estimated
      value (e.g. pay €50 for something valued ~€8)
- [ ] Portfolio / P&L shows a gain or loss reflecting **what you paid**, not
      roughly zero. (`unrealized_pl` used to be `current_value − first
      predicted value`, so a stable model always showed ~break-even.)
- [ ] Items list row shows the **"Paid €X"** line with a gain/loss delta —
      this never rendered before 2026-07-28 because the EUR column was empty
      for every item, so it has no prior device coverage
- [ ] "You saved €X" banner: buy something in a **non-EUR** currency below
      market value and confirm the saving is the FX-converted difference, not
      the raw number treated as EUR

### Analytics screen (added 2026-07-28)

> Every endpoint this screen calls was swept live as two users — one with items,
> one without — because an empty section is ambiguous otherwise. The failures
> below were all invisible from the app: an HTTP 200 with an empty body, or a
> total that disagreed with the rows beneath it.

- [ ] Analytics tab opens with **no blank/error sections**
- [ ] The **portfolio total at the top equals the sum of the item rows** below
      it, and equals the sum of the category breakdown. These came from three
      different queries and disagreed (€55 header vs €0 rows).

### Home value consistency (added 2026-07-29)

> Home shows the collection's value in **five** places fed by four different
> queries. They must all agree, and they did not. Check them together, on one
> account, in one sitting — each looks plausible alone.

- [ ] **COLLECTION VALUE** (above the chart) = **Items tab "Portfolio total"**
- [ ] The **chart's last point** matches that same number (the headline is
      derived from the curve, so a wrong curve silently moves the headline)
- [ ] The **change %** is consistent with the curve's first→last points
- [ ] The **stats row** ("Portfolio") matches the headline
- [ ] **Portfolio Insights → Total Value** matches the headline
- [ ] Add a **hand-entered item with an estimated value** (no scan): every one
      of the five updates by that amount. It used to contribute 0 to the chart
      and headline while showing on the Items tab.
- [ ] If any item was priced by **QuickScan**, confirm it also counts on Home —
      there are two prediction tables and each used to be read by only some
      surfaces
- [ ] Add an item **by hand** (no scan, so it has no price prediction) with an
      estimated value → it still contributes its value to the total, the rows
      and the category breakdown, not 0
- [ ] An item with **no category** still appears in the category breakdown
      (as "uncategorized"), so the parts add up to the whole
- [ ] **Risk notes / insights** section renders. It used to 500 whenever the
      account held even one uncategorised item, and again whenever the trending
      query timed out — both showed as a blank section, never an error.
- [ ] **Trending items** show real names and categories (e.g. "Charizard ★ δ",
      `pokemon`) — not raw keys like `base6-base6-8`
- [ ] The screen loads promptly; insights used to take up to 30s and then fail

Sections that are legitimately empty on a fresh account — **not** bugs:

- **Category Health** needs price predictions from the last 30 days
- **Prediction Accuracy** stays at 0 until you mark an item **sold** on its
  detail screen (that is what records ground truth)

### Watchlist reorder (added 2026-07-31)

Failed every time before today — the buttons showed "Could not reorder."

- [ ] Watchlist builder → **move an item up**, then **down**. No error toast
- [ ] Leave the screen and come back — **the order you set is still there**
      (it reverted before, because nothing persisted)

### Barcode scan, unrecognised code (added 2026-07-31)

- [ ] Scan something not in any catalog (any random EAN). The card must say
      **"Not recognised"**, not "Product Found" with a green tick
- [ ] The primary button must read **Add Manually** and open add-manual — it
      previously offered Save, which filed an item called "Unknown item"

### Currency / region / locale (added 2026-07-30)

Until 2026-07-30 five of these values returned a **500** because the DB CHECK
was narrower than the code. Walk every one — a 500 here means a constraint
regressed.

- [ ] Settings → Currency: each of **EUR, USD, GBP, JPY, KRW, AUD, CAD** saves
      and survives a force-quit + relaunch
- [ ] Settings → Region: each of **americas, europe, japan, korea, oceania,
      other** saves. `korea` and `oceania` were the broken ones
- [ ] Number format: **ko-KR** and **en-AU** save (these were broken too)
- [ ] Picking region `korea` should default currency to KRW, `oceania` to AUD —
      and that default must itself save without error

### Price alerts (added 2026-07-30)

The **only** way to create an alert is a watchlist target price. Free plan =
1 alert/week, so do this on a fresh week or expect the limit toast.

- [ ] Wishlist tab → add an item **with a target price** → a toast confirms
      *"Price alert created — we'll notify you when the price drops below …"*.
      A toast reading "Target saved, but the price alert couldn't be created"
      means the plan limit was hit (fine) — a **silent** result is a bug
- [ ] Alerts screen → **Rules** tab → the alert appears as one plain sentence,
      e.g. *"Pokemon drops below €50.00"* with a **Price drop** badge.
      An empty "No alert rules yet" here after the step above is the 2026-07-30
      regression (Rules tab reading the trigger feed) — flag it
- [ ] The **Rules** tab and the **Recent** tab must show **different** content.
      Identical lists = the two have been crossed again
- [ ] Swipe a rule → **Delete** → it disappears and stays gone after
      pull-to-refresh. "Failed to delete alert" means a non-alert id is being
      sent to `DELETE /alerts/mine/{id}`
- [ ] Edit an existing watchlist item's target price → same alert behaviour

---

## Section 5 — Paywall (expectation depends on the BUILD PROFILE)

> **Corrected 2026-07-27.** This section used to say every paywall should be
> UNLOCKED, and that a visible paywall meant `EXPO_PUBLIC_BETA_UNLOCK_ALL`
> had failed to reach the build. That is wrong for any TestFlight build made
> with the `store` profile — which is all of them, since
> `npm run build:ios:local` uses `--profile store`, and that profile pins
> `EXPO_PUBLIC_BETA_UNLOCK_ALL=false`. Following the old text would have you
> file a working build as broken.

Check which profile the build came from, then use the matching column:

| Surface | `store` profile (TestFlight + App Store) | `development` / `preview` (internal) |
|---|---|---|
| Analytics tab | paywall card **shown** | chart UI, no paywall |
| Deal Discovery / Deal Hub | locked state **shown** | deal listings |
| Sets to Complete | "Upgrade to unlock" **shown** | set tracker UI |
| Item detail → Advanced Predictions | lock icon **shown** | q10/q50/q90 charts |
| Settings → Subscription | **plan cards** (€4.99/mo, €39.99/yr) | "every Pro feature unlocked for free" card |

For a `store` build (the normal case):

- [ ] Settings → **Subscription** renders real plan cards with prices, not the beta card
- [ ] At least one gated surface shows its paywall rather than the feature
- [ ] Tapping a plan opens the Apple IAP sheet (sandbox account required — device only, not simulator)

If a `store` build shows **no** paywall anywhere, that is the serious case:
it means the beta flag leaked into a shippable profile. Both `store` and
`production` now pin it to `false` (eas.json), so this should not recur —
but if it does, do not submit that build.

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

## Screen coverage — full sweep completed 2026-07-31

Every route in `app/` was walked against **prod data**, not mocks. Method that
found things: seed a real row, call the exact query the screen issues, compare
the **value** to its meaning. Status codes and types caught none of the bugs.

**Fixed during the sweep** (each has a QA row above or in git):

| Screen | Defect |
|--------|--------|
| Alerts / wishlist | price alerts never created (`direction:'below'` → 422); Rules tab read the trigger feed |
| Leaderboard | XP rendered as currency — 80 XP shown as "€80.00" |
| Categories | raw slugs (`action_figures`) instead of curated names; search matched slugs |
| Settings | currency/region/locale saves failed silently (4 unchecked `fetch` writes) |
| Settings → Edit Profile | `PATCH /settings/profile` did not exist (404); built it |
| MFA | abandoning enrolment bricked 2FA permanently |
| Events | templates 500'd on save and read back empty |
| Barcode scan | "Product Found" + Save on a scan that identified nothing |
| Watchlist builder | reorder threw HTTP 406 every time (empty update payload) |
| sets-to-complete | "Est. value" always 0 — read a field the API never returns |

**Verified correct, no change needed:** catalog browse + set grids (incl.
pagination and 80,720 `tcgplayer:`-keyed rows, all titled), item detail, events
create/RSVP/edit/cancel, chat inbox + DM request, public profiles, gamification
profile/achievements, market movers, deal detail, barcode lookup API,
condition-guide, `home/portfolio` and the `search` tab (both `<Redirect>` stubs).

**Known-empty for correct reasons — do not "fix":** Category Health,
prediction-accuracy, `/sets/auto-progress` below 2 owned items, challenges
(content expired Feb 2026, no generator), RegionalInsights (deliberately
unwired), Twitch (out of scope).

### Pre-launch cleanup items found by the sweep

- [ ] **`COMMUNITY_GATED = false`** exposes social surfaces while 0 of 24 profiles
      are discoverable. Its own comment says flip it back to `true` before public
      launch. Threshold in notes: ~50 public profiles
- [ ] **"Open test chat"** button on the empty Inbox opens `app/chat-demo.tsx`, a
      self-declared local-only placeholder ("remove once real DM threads exist").
      Real users would see it
- [ ] **Sponsor checkout** returns 400 "Subscription price not configured for
      tier: featured" — same unset Stripe prices that block `/pro`. Sponsor CRUD
      (register / list / update) all work
- [ ] **Free plan is allotted 3 mandates it cannot reach** (see MONETIZATION.md)

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
