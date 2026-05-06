# Sparrow Collect — Solo Launch Guide

**Self-contained step-by-step. Don't need to check in with Claude between steps.**

Work the items in any order — each is independent. After each, send Claude the result so they can plug values into code (`eas.json`, EC2 `.env`, EAS Secrets).

---

## Status as of 2026-05-06

**Already done in code:**
- Brand rename to Sparrow Collect everywhere (app.json, src/, web/, legal docs)
- Logo recolored to `#81D8D0` and placed at `assets/icon.png`, `splash.png`, `adaptive-icon.png`
- Bake hardening (supervisor, manifest cut, heavy gate, bounded timeouts, ExecStop cancel hook, sustained-error paging, circuit breaker)
- Account deletion + privacy nutrition labels accurate in `app.json`
- Email aliases wired via SimpleLogin (`support@`, `privacy@`, `legal@`, `dpo@`)
- `web/support.html` created (Apple-required Support URL)
- `https://api.sparrowcollect.com` LIVE with valid SSL — `/healthz` returns OK
- Legal docs include real KvK number `99596326` + Ertskade 74 1019 BB Amsterdam

**Already done by you:**
- Cloudflare DNS (api A record + apex/www records) ✓
- SimpleLogin domain verified, 4 aliases live ✓
- KvK address + identity confirmed: Merle Slendebroek, eenmanszaak, KvK 99596326, Ertskade 74, 1019 BB Amsterdam ✓
- Adding "Sparrow Collect" as second handelsnaam at KvK (in progress, 1-3 days) ⏳

**Waiting on KvK confirmation, then:**
- D-U-N-S lookup
- Apple Developer Program enrollment (Organization)
- Sign in with Apple Service ID + .p8 key
- App Store Connect record

---

# Self-serve tasks (do in any order)

## TASK 1 — Stripe Live Mode (30 min)

**Goal:** Switch Stripe from test to live, recreate "Sparrow Collect Pro" / "Premium" products, set webhook to the live API URL.

### Where
dashboard.stripe.com → top-right toggle **Test mode → Live mode**

### Step-by-step

**1.1 Create live products**

1. Left sidebar → **Products** → **+ Add product**
2. Product 1:
   - Name: `Sparrow Collect Pro`
   - Description: `Unlock 10 deal mandates, dossier PDF export, and advanced price alerts.`
   - Pricing: **Recurring**
   - Price: **€4.99 / month**
   - Currency: **EUR**
   - Click **Save product**
   - **Copy the Price ID** (starts with `price_...`) → save it for Claude as `STRIPE_PRICE_ID_PRO`
3. Click **+ Add another product**
4. Product 2:
   - Name: `Sparrow Collect Premium`
   - Description: `Unlock 50 mandates, advanced analytics, on-demand fresh comps, and everything in Pro.`
   - Recurring, **€9.99 / month**, EUR
   - Save → **Copy the Price ID** → save as `STRIPE_PRICE_ID_PREMIUM`

**1.2 Create webhook endpoint**

1. Left sidebar → **Developers → Webhooks** → **+ Add endpoint**
2. Endpoint URL: `https://api.sparrowcollect.com/billing/webhook`
3. Description: `Sparrow Collect bake — subscription events`
4. Events to send (search and check 4):
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
5. Click **Add endpoint**
6. On the endpoint detail page → click **Reveal signing secret** → **Copy** the `whsec_...` value → save as `STRIPE_WEBHOOK_SECRET`

**1.3 Configure Customer Portal**

1. Left sidebar → **Settings** (gear icon) → **Billing → Customer Portal**
2. Enable:
   - ☑ Cancel subscription
   - ☑ Switch plans
   - ☑ Update payment method
3. **Default return URL**: `sparrow://settings` (note the new scheme — was `collectai://`)
4. Save

**1.4 Get the live API key**

1. Left sidebar → **Developers → API keys**
2. **Reveal** the **Secret key** (starts with `sk_live_...`)
3. Copy → save as `STRIPE_SECRET_KEY`

### Send to Claude

Four values:
```
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_PREMIUM=price_...
```

Claude updates `/opt/collectors/.env` on EC2 + restarts bake. Stripe live billing goes live immediately.

---

## TASK 2 — Google Cloud OAuth (15 min)

**Goal:** Three OAuth Client IDs (Web, iOS, Android) for Google Sign In integration. Bundle/package = `com.sparrowcollect.app`.

### Where
console.cloud.google.com

### Step-by-step

**2.1 Create / select project**

1. Top-left project dropdown → **New Project** (if no project exists, otherwise select existing)
2. Name: `Sparrow Collect`
3. Organization: skip (no Google Workspace)
4. **Create**

**2.2 Configure OAuth consent screen**

1. Left sidebar → **APIs & Services → OAuth consent screen**
2. User Type: **External** → **Create**
3. App information:
   - App name: `Sparrow Collect`
   - User support email: `support@sparrowcollect.com`
   - App logo: upload `/Users/merle/GitHub/CcollectAI/assets/icon.png`
4. App domain:
   - Application home page: `https://sparrowcollect.com`
   - Privacy policy: `https://sparrowcollect.com/privacy.html`
   - Terms of service: `https://sparrowcollect.com/terms.html`
5. Authorized domains: `sparrowcollect.com`
6. Developer contact: `slendebroekmerle@gmail.com`
7. **Save and continue** through Scopes (skip), Test users (skip), back to Dashboard
8. Click **Publish App** → "In production" mode (Google won't review at this stage; just makes it externally usable)

**2.3 Create OAuth Client ID #1 — Web**

1. Left sidebar → **APIs & Services → Credentials** → **+ Create credentials → OAuth client ID**
2. Application type: **Web application**
3. Name: `Sparrow Collect Web`
4. **Authorized redirect URIs**: `https://ykqrruipzmrrvjcvwfgp.supabase.co/auth/v1/callback`
5. **Create**
6. Copy popup values:
   - **Client ID** → save as `GOOGLE_WEB_CLIENT_ID`
   - **Client secret** → save as `GOOGLE_WEB_CLIENT_SECRET`

**2.4 Create OAuth Client ID #2 — iOS**

1. Credentials → **+ Create credentials → OAuth client ID**
2. Application type: **iOS**
3. Name: `Sparrow Collect iOS`
4. Bundle ID: `com.sparrowcollect.app`
5. App Store ID: leave blank (will fill after App Store Connect record exists)
6. Team ID: leave blank for now
7. **Create**
8. Copy **Client ID** → save as `GOOGLE_IOS_CLIENT_ID`

**2.5 Create OAuth Client ID #3 — Android**

1. Credentials → **+ Create credentials → OAuth client ID**
2. Application type: **Android**
3. Name: `Sparrow Collect Android`
4. Package name: `com.sparrowcollect.app`
5. SHA-1 certificate fingerprint: **leave blank for now** — get after first EAS Android build
6. **Create**
7. Copy **Client ID** → save as `GOOGLE_ANDROID_CLIENT_ID`

### Send to Claude

Four values:
```
GOOGLE_WEB_CLIENT_ID=<long string>.apps.googleusercontent.com
GOOGLE_WEB_CLIENT_SECRET=<value>
GOOGLE_IOS_CLIENT_ID=<long string>.apps.googleusercontent.com
GOOGLE_ANDROID_CLIENT_ID=<long string>.apps.googleusercontent.com
```

Claude pushes them as EAS Secrets and into Supabase Auth → Google provider config.

---

## TASK 3 — Google Play Console enrollment ($25, ~24h verify)

**Goal:** Pay $25 and start the developer account approval. Doesn't unblock anything urgent (iOS-first launch), but the 24h wait runs in parallel.

### Step-by-step

1. play.google.com/console → **Get started**
2. Sign in with the Google account that owns the OAuth project from Task 2
3. **Developer agreement** → accept
4. **Account type**: **Organization** (matches Apple side; KvK-registered)
5. Pay **$25** (one-time)
6. Identity verification:
   - Upload government ID (passport or rijbewijs)
   - Address verification: a code mailed to your address (Ertskade 74) — usually arrives within 1-2 weeks. **Note: this is a slow step.** Do this NOW so the postal mail lands in time.
7. Submit

After verification arrives:
1. Create app → **Create app**
2. App name: `Sparrow Collect`
3. Default language: English (United States)
4. App or game: App
5. Free or paid: Free (in-app subscriptions via Play Billing)
6. Create

### Service account for `eas submit`

1. console.cloud.google.com → IAM & Admin → Service Accounts → **+ Create**
2. Name: `sparrow-eas-submit`
3. → next → grant role: **Service Account User**
4. → next → done
5. Click on the new service account → **Keys** → **Add Key → Create new key → JSON**
6. JSON file downloads → save as `~/.config/sparrow/play-service-account.json`
7. Send Claude the path

---

## TASK 4 — Apple ID for business (5 min, only if rate-limit cleared)

**Goal:** Create `apple@sparrowcollect.com` Apple ID for clean separation between personal and Sparrow Collect identities. Required only if the previous attempt's rate-limit has cleared.

### Step-by-step

1. Open **incognito / private** browser window (clears Apple's session cookies)
2. **https://appleid.apple.com → Create Your Apple ID**
3. Form:
   - First name / Last name: **Merle Slendebroek** (must match government ID)
   - Country: Netherlands
   - Birthday: real DOB
   - Email: **`apple@sparrowcollect.com`** (the SimpleLogin alias forwards to gmail)
   - Password: strong, save in password manager
   - Phone: your real number — Apple may text + may call later for Dev verification
4. Apple emails verification code to `apple@sparrowcollect.com` → forwards to gmail → enter
5. SMS code → enter
6. Account created

### Enable 2FA (required for Apple Dev)

1. Sign in at appleid.apple.com with new account
2. **Sign-In Security → Two-Factor Authentication → Turn On**
3. Add same phone as trusted device
4. Confirm

If the rate-limit error still appears: skip this task tonight. Use existing personal Apple ID for Apple Dev when KvK approval lands. The business Apple ID can be added as Admin role later, no urgency.

---

# Tasks blocked on KvK (do in order, after KvK confirms)

## TASK 5 — D-U-N-S Number lookup (when KvK shows "Sparrow Collect" as handelsnaam)

### Step-by-step

1. Open **https://developer.apple.com/enroll/duns-lookup/**
2. Sign in with personal Apple ID (just for the lookup — doesn't tie to anything)
3. Click **Look up your D-U-N-S Number**
4. Form:
   - Country: **Netherlands**
   - Legal Entity Name: `Sparrow Collect` (the new handelsnaam, exactly as on uittreksel)
   - Address: `Ertskade 74, 1019 BB, Amsterdam`
   - Phone: your number `+31 6 ...`
   - Email: `apple@sparrowcollect.com` (or gmail)
5. Submit

### Outcome A — D-U-N-S found
- 9-digit number on screen
- Save it
- Send to Claude
- Skip to Task 6

### Outcome B — D-U-N-S not found
- Click the **Request a D-U-N-S Number** link
- Same form → submit
- Wait 5–14 business days for D&B email
- When email arrives, send the D-U-N-S Number to Claude
- Then go to Task 6

---

## TASK 6 — Apple Developer Program enrollment (Organization)

**Prerequisites:** D-U-N-S Number from Task 5, Apple ID with 2FA from Task 4 (or personal).

### Pre-flight on the Apple ID being used (5 min)

1. appleid.apple.com → sign in
2. **Sign-In Security**: Two-Factor Authentication = ON
3. **Personal Information**: Name = **Merle Slendebroek** exactly as on government ID

### Enrollment (10 min)

1. **https://developer.apple.com/programs/enroll/** → **Start Your Enrollment**
2. Sign in with the Apple ID
3. Choose: **Organization / Company / Educational Institution**
4. **Organization Information**:
   - Legal Entity Name: `Sparrow Collect` (exact handelsnaam from KvK)
   - D-U-N-S: 9-digit from Task 5
   - Country: Netherlands
   - Headquarters Address: `Ertskade 74, 1019 BB, Amsterdam`
   - Headquarters Phone: your number
5. **Website**: `https://sparrowcollect.com` (must resolve — apex DNS is set)
6. **Person of Authority**:
   - You (sole proprietor)
   - Job title: `Owner` or `Founder`
   - Work email: `apple@sparrowcollect.com` (or gmail)
   - Work phone: your number
7. Read License Agreement → tick **I agree** → Continue
8. **Pay $99**
9. Confirmation email lands within minutes

### Apple's verification (1–7 days typical)

- D&B validation: automatic, usually instant
- Person of Authority call: an Apple rep may call your phone (US number, sometimes flagged as spam by Dutch carriers — answer it). They confirm your name and that you authorized the enrollment. ~5 min, English.

After approval: **Welcome to the Apple Developer Program** email arrives. Send a screenshot to Claude. That triggers Task 7.

---

## TASK 7 — App Store Connect record + Sign in with Apple keys (after Apple Dev approval)

**Prerequisites:** Apple Dev approval email.

### 7.1 Note your Team ID
- developer.apple.com → top-right corner → 10-character Team ID (e.g., `A1B2C3D4E5`)
- Send to Claude

### 7.2 Register App ID
1. developer.apple.com → **Certificates, Identifiers & Profiles → Identifiers → +**
2. Type: **App IDs** → Continue
3. Type: **App** → Continue
4. Description: `Sparrow Collect`
5. Bundle ID: **Explicit** → `com.sparrowcollect.app`
6. Capabilities (check):
   - Sign In with Apple
   - Push Notifications
   - Associated Domains
7. Continue → Register

### 7.3 Create Sign in with Apple Service ID
1. Identifiers → **+** → **Services IDs** → Continue
2. Description: `Sparrow Collect Sign In`
3. Identifier: `com.sparrowcollect.app.auth`
4. **Configure** → enable Sign In with Apple
5. Primary App ID: `com.sparrowcollect.app`
6. Domains and Subdomains: `ykqrruipzmrrvjcvwfgp.supabase.co`
7. Return URLs: `https://ykqrruipzmrrvjcvwfgp.supabase.co/auth/v1/callback`
8. Save → Continue → Register

### 7.4 Generate Sign in with Apple Key (.p8)
1. **Certificates, Identifiers & Profiles → Keys → +**
2. Key Name: `Sparrow Collect Sign In Key`
3. Enable: Sign In with Apple
4. Configure → Primary App ID: `com.sparrowcollect.app` → Save
5. Continue → Register
6. **Download the `.p8` file** — Apple shows it ONCE. Save it as `~/Downloads/AuthKey_<KeyID>.p8`
7. Note the **Key ID** (10 characters)
8. Send Claude:
   - Team ID
   - Key ID
   - The contents of the `.p8` file (open in TextEdit, paste the whole `-----BEGIN PRIVATE KEY-----...-----END PRIVATE KEY-----` block)

### 7.5 Create App Store Connect app record
1. **https://appstoreconnect.apple.com → My Apps → +**
2. Platforms: iOS
3. Name: `Sparrow Collect`
4. Primary language: English (U.S.)
5. Bundle ID: `com.sparrowcollect.app` (from dropdown — registered in 7.2)
6. SKU: `sparrowcollect-1`
7. User Access: Full Access
8. Create
9. Note the **App Store ID** (numeric, top of the app page)
10. Send Claude the App Store ID

That gives Claude everything needed to populate `eas.json` and Supabase Auth → Apple provider.

---

# Reference: where each value goes (just for awareness)

| Value | Location |
|---|---|
| Stripe live keys | EC2 `/opt/collectors/.env`, restart bake |
| Stripe Price IDs | EC2 `.env` (STRIPE_PRICE_ID_*) |
| Stripe webhook secret | EC2 `.env` (STRIPE_WEBHOOK_SECRET) |
| Google OAuth Web Client ID + Secret | Supabase Auth → Providers → Google |
| Google OAuth iOS/Android Client IDs | EAS Secrets → `EXPO_PUBLIC_GOOGLE_*_CLIENT_ID` |
| Apple Team ID | `eas.json` (submit.ios.appleTeamId) |
| Apple App Store ID | `eas.json` (submit.ios.ascAppId) |
| Apple Sign In Key ID + .p8 | Supabase Auth → Providers → Apple |
| Apple Sign In Service ID | Supabase Auth → Providers → Apple |
| D-U-N-S Number | Apple Developer enrollment form (one-time use) |
| KvK number | Already in legal docs |
| Real address | Already in legal docs |
| Phone | Apple Dev enrollment + Stripe + Google Cloud (input only, no code) |

# How to print this as PDF

Open this `.md` file in any markdown previewer (e.g. Typora, MacDown, or VS Code with Cmd+Shift+V). Then **File → Print → Save as PDF** in the print dialog.

Or in Terminal:
```bash
brew install pandoc
pandoc docs/SPARROW_LAUNCH_SOLO_GUIDE.md -o ~/Desktop/sparrow-launch-guide.pdf
```

# What's expected back from you (summary)

You'll send Claude these batches as you complete each task. None are blocking each other.

- **Task 1 done** → 4 Stripe values
- **Task 2 done** → 4 Google OAuth values
- **Task 3 done** → service account JSON path + Play app exists
- **Task 4 done** → "business Apple ID created" or "rate-limit still blocking, using personal"
- **Task 5 done** → D-U-N-S Number
- **Task 6 done** → Apple Dev approval email screenshot
- **Task 7 done** → Team ID, App Store ID, Key ID, .p8 contents
