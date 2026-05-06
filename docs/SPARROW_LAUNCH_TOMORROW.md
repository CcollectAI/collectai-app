# Sparrow Collect — Tomorrow's User Actions

Generated 2026-05-04. Code-side rebrand is in this commit; the rest is on
you. Steps are ordered so each one unblocks the next. Do them in order.

---

## 0. Quick reality check before starting

You'll need browser access to:
- **Cloudflare** (you already have the account; sparrowcollect.com is yours)
- **Apple Developer Portal** (developer.apple.com/account) — once enrolled
- **Google Play Console** (play.google.com/console)
- **Google Cloud Console** (console.cloud.google.com) — for OAuth credentials
- **Stripe Dashboard** (stripe.com/dashboard)
- **Supabase Dashboard** (supabase.com/dashboard, project `ykqrruipzmrrvjcvwfgp`)

Have your **EC2 SSH key** (~/.ssh/collectai-ec2) handy — some steps run on
the server.

---

## 1. Cloudflare DNS records (~5 min)

Log into Cloudflare → sparrowcollect.com → DNS.

Add:

| Type | Name | Content | Proxy | TTL |
|---|---|---|---|---|
| A | `api` | `51.21.210.195` | **DNS only** (grey cloud) | Auto |
| A | `@` | `76.76.21.21` (Vercel) OR your landing IP | Proxied (orange) | Auto |
| CNAME | `www` | `sparrowcollect.com` | Proxied (orange) | Auto |

**Critical**: `api.sparrowcollect.com` MUST be DNS-only (grey cloud).
Cloudflare proxy mode breaks Let's Encrypt's HTTP-01 challenge and
rate-limits asyncpg connections from EC2. The other records can be proxied.

After adding, verify propagation:
```bash
dig api.sparrowcollect.com +short
# Expect: 51.21.210.195
dig sparrowcollect.com +short
# Expect: your A record value
```

When `dig` resolves correctly, ping me (next session) so I can run step 2.

---

## 2. EC2 server-side SSL + nginx + .env (~10 min, I'll do this)

Once `api.sparrowcollect.com` resolves, ssh in and run (I'll handle):
```bash
ssh collectai
sudo certbot --nginx -d api.sparrowcollect.com
sudo nginx -t && sudo systemctl reload nginx
# Update /opt/collectors/.env: CORS_ORIGINS, TRUSTED_HOSTS
sudo systemctl restart collectai-bake
```

This requires DNS to have propagated, so it's gated on step 1.

---

## 3. Apple Developer enrollment (~10 days external wait)

1. Go to **developer.apple.com/programs/enroll**.
2. Choose individual or organization. **Organization** if you want
   "Sparrow Collect" as the App Store seller line; requires D-U-N-S number
   (free, takes 5–14 days). Individual enrolls today and the seller line
   is your name.
3. Pay $99/year.
4. Wait for approval (1–10 days; sometimes same-day for individual).

**While you wait**, you can do steps 4–7. Apple's part is the gating
external dependency.

---

## 4. App Store Connect record (after Apple Dev approves)

In **appstoreconnect.apple.com → My Apps → +**:

- **Platforms**: iOS
- **Name**: `Sparrow Collect` (30 char max — fits at 15)
- **Primary language**: English (U.S.)
- **Bundle ID**: `com.sparrowcollect.app` (must match `app.json`; if not in
  the dropdown yet, register it at developer.apple.com → Identifiers
  first)
- **SKU**: `sparrowcollect-1` (any unique string)
- **User Access**: Full Access

Note the **App Store ID (numeric)** that gets assigned — you'll paste it
into `eas.json` as `ascAppId`. Also note your **Apple Team ID** (top-right
of developer.apple.com) for `appleTeamId`.

---

## 5. Sign In with Apple service ID

Developer portal → **Identifiers → Service IDs → +**:
- **Description**: Sparrow Collect Sign In
- **Identifier**: `com.sparrowcollect.app.auth`
- Enable **Sign In with Apple**, configure → Primary App ID =
  `com.sparrowcollect.app`
- **Return URLs**: `https://ykqrruipzmrrvjcvwfgp.supabase.co/auth/v1/callback`
- Save.

Then **Keys → +**:
- **Key Name**: Sparrow Sign In Key
- Enable **Sign In with Apple**, configure → primary App ID
- Generate. Download the `.p8` key file ONCE — Apple won't show it again.
- Note the **Key ID** (10-char string).

Hold onto: `.p8` file, Key ID, Team ID, Service ID. You'll paste them into
Supabase in step 9.

---

## 6. Google Cloud OAuth (~15 min)

console.cloud.google.com → create project "Sparrow Collect" if not exists.

**APIs & Services → Credentials → + Create credentials → OAuth client ID**:

Three clients to create (one per platform):

**Web application** (for Supabase Auth):
- Name: Sparrow Collect Web
- Authorized redirect URIs:
  `https://ykqrruipzmrrvjcvwfgp.supabase.co/auth/v1/callback`
- Note **Client ID** + **Client Secret**.

**iOS**:
- Name: Sparrow Collect iOS
- Bundle ID: `com.sparrowcollect.app`
- Note **Client ID**.

**Android**:
- Name: Sparrow Collect Android
- Package name: `com.sparrowcollect.app`
- SHA-1 certificate fingerprint: get from EAS after first Android build
  (`eas credentials -p android` → show signing keystore SHA-1). Defer
  this until you've run an EAS build at least once.
- Note **Client ID**.

---

## 7. Google Play Console enrollment ($25 one-time, ~15 min + 24h verify)

play.google.com/console → enroll. Pay $25. Wait for ID verification
(typically <24h).

After approval:
- Create app → **App name**: Sparrow Collect
- **Package name**: `com.sparrowcollect.app` (must match `app.json`)
- Default language: English (United States)
- App or game: App
- Free or paid: Free (with in-app purchases via Play Billing)

Create a **service account** for `eas submit`:
- console.cloud.google.com → IAM → Service Accounts → +
- Name: sparrow-eas-submit
- Grant **Service Account User** role
- Keys → Add Key → JSON → download
- Save the JSON file as `~/secure/sparrow-play-service-account.json`
  (path goes into `eas.json`).

---

## 8. Stripe Live Mode (~30 min)

stripe.com/dashboard → toggle to **Live Mode** (top-right).

**Products & Prices** (create fresh in live mode; test products don't
carry over):

- Product 1: **Sparrow Collect Pro** → Price €4.99/month recurring →
  copy the `price_...` ID for `STRIPE_PRICE_ID_PRO`.
- Product 2: **Sparrow Collect Premium** → Price €9.99/month recurring →
  copy for `STRIPE_PRICE_ID_PREMIUM`.

**Webhook endpoint**:
- URL: `https://api.sparrowcollect.com/billing/webhook`
- Events:
  - `checkout.session.completed`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_failed`
- Copy the **Signing secret** (`whsec_...`) → `STRIPE_WEBHOOK_SECRET`.

**Customer Portal** (Settings → Billing → Customer Portal):
- Enable: Cancel subscription, Switch plans, Update payment method
- Return URL: `sparrow://settings` (note the new scheme — was `collectai://`).

**Live API keys**: Developers → API keys → reveal **Secret key** (`sk_live_...`).

Hand the four values to me next session and I'll plug them into EC2:
- `sk_live_...` → `STRIPE_SECRET_KEY`
- `whsec_...` → `STRIPE_WEBHOOK_SECRET`
- two `price_...` IDs.

---

## 9. Supabase Auth dashboard (~10 min, after steps 5–6)

supabase.com/dashboard → project `ykqrruipzmrrvjcvwfgp`:

**Authentication → URL Configuration**:
- **Site URL**: `https://sparrowcollect.com`
- **Redirect URLs** (add both, keep old `collectai://` for one release of
  back-compat):
  - `sparrow://reset-password`
  - `sparrow://subscription`

**Authentication → Providers → Apple**:
- Enable
- Service ID: `com.sparrowcollect.app.auth` (from step 5)
- Team ID: from step 4
- Key ID + Private key (.p8 contents) from step 5

**Authentication → Providers → Google**:
- Enable
- Web Client ID + Client Secret from step 6 (Web client)

**Authentication → Email Templates** (rebrand at your leisure):
- Confirm signup, reset password, magic link — replace any "CollectAI"
  with "Sparrow Collect" / "Sparrow"; replace `#81D8D0` brand colour
  blocks if you change palette later.

---

## 10. Three Supabase dashboard hardening toggles

Pre-launch security advisor flagged these. They're switches, not code:
- **Authentication → Settings → Have I Been Pwned** → enable
- **Authentication → Settings → OTP Expiry** → set to 3600s (1h) max
- **Database → Postgres** → upgrade to latest minor version

---

## 11. EAS Secrets update (after steps 6 + 9, I'll do this)

```bash
# I'll run these next session once you've handed me the values
eas secret:create --name EXPO_PUBLIC_API_BASE_URL --value https://api.sparrowcollect.com --force
eas secret:create --name EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID --value <web-client-id> --force
eas secret:create --name EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID --value <ios-client-id> --force
eas secret:create --name EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID --value <android-client-id> --force
```

---

## 12. EAS submit credentials (eas.json, I'll do this)

After step 4, I'll fill in `eas.json`:
- `appleId`: your Apple ID email
- `ascAppId`: numeric App Store Connect ID
- `appleTeamId`: 10-char Team ID

---

## 13. App Store metadata (last mile, I'll prep)

I'll re-render the 6 Remotion screenshot compositions with Sparrow
branding once the new logo asset is in place. I'll also rebrand
`app-store-aso.md` from CollectAI to Sparrow — keywords, description,
subtitle, promo text.

You'll paste the result into App Store Connect after step 4.

---

## What I've already done in code (no action needed)

- `app.json` rebranded fully (name, scheme, bundle, package, permission
  prompts, universal links, intent-filter hosts)
- 68 files in `src/`, `app/`, `web/` swept for "CollectAI" → "Sparrow Collect"
- Deep-link scheme references fixed (`collectai://` → `sparrow://`)
- Legal pages reviewed; entity references cleaned
- `.env.example` and `server/main.py` rebranded
- Logo recolored to `#81D8D0` (Tiffany Blue) and placed at
  `assets/icon.png` (1024×1024), `assets/splash.png`, and
  `assets/adaptive-icon.png` (512×512)
- Universal-link hosts in `app.json` updated to `sparrowcollect.com`
- Bake hardening (today's earlier work): supervisor self-heal + heavy
  gate + bounded timeouts + ExecStop cancel hook + sustained-error
  paging + circuit breaker. See
  `learning_bake_hardening_2026_05_04.md`.

---

## What's still on the roadmap (post-launch)

- Phase 3 query rewrites (`docs/PHASE_3_QUERY_REWRITES.md`) — gated on
  DB recovery for EXPLAIN ANALYZE
- Re-enable disabled workers in waves (see `GO_LIVE_CHECKLIST.md`)
- Etsy adapter re-enable (API approved 2026-05-04)
- Address line in legal docs — currently "Sparrow Collect / The
  Netherlands" placeholder; add your real registered address before
  App Store submission

---

## Decisions I made today on your behalf (override if wrong)

- **Home-screen label**: `Sparrow Collect` (matches App Store name).
- **Deep-link scheme**: `sparrow` (short, conversational).
- **Bundle ID**: `com.sparrowcollect.app`.
- **Brand color**: kept `#81D8D0` Tiffany Blue.
- **In-app permission prompts**: "Sparrow needs camera access…"
  (conversational, not "Sparrow Collect needs…").
- **Conversational vs formal copy in `src/`**: defaulted bulk replace to
  the formal `Sparrow Collect`. Some user-facing strings (toasts, push
  copy, welcome screens) might read warmer as just "Sparrow" — flag any
  you spot and I'll tweak.

---

## Order summary

| When | Who | Step |
|---|---|---|
| Tomorrow morning | You | 1. Cloudflare DNS |
| Tomorrow (after DNS propagates) | Me | 2. EC2 SSL + nginx |
| Tomorrow morning | You | 3. Apple Dev enrollment (then wait) |
| Tomorrow | You | 6. Google Cloud OAuth |
| Tomorrow | You | 7. Play Console enrollment (then wait <24h) |
| Tomorrow | You | 8. Stripe live mode |
| Tomorrow | You | 10. Supabase hardening toggles |
| When Apple approves | You | 4. App Store Connect record |
| When Apple approves | You | 5. Sign In with Apple service ID + key |
| When 5+6 done | You | 9. Supabase Auth providers |
| When 4 done | Me | 11. EAS Secrets + 12. eas.json + 13. metadata |

Ping me once Cloudflare is set and Apple Dev is in flight.
