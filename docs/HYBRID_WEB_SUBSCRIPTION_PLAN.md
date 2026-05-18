# Hybrid Web Subscription Plan — Phase 1 (Pre-Launch)

**Status:** Phase 1 in progress, 2026-05-18
**Goal:** Let users subscribe to Pro via sparrowcollect.com using Stripe, bypassing Apple's 15% cut for the slice of users acquired through marketing/SEO rather than App Store discovery.

---

## Decision: "Web checkout only, pre-launch"

We build the web subscription path now. We do NOT modify the iOS app's IAP flow before App Store submission. Web-acquired users get Pro on iOS via a Supabase flag that the iOS entitlement check reads alongside RevenueCat.

**Why this scope:**
- Doesn't touch iOS IAP code → no App Store rejection risk
- Web checkout is self-contained → can ship + iterate without rebuilding iOS
- Users acquired via marketing → 3% fee (Stripe) instead of 15% (Apple SBP)
- Users acquired via App Store discovery → still IAP, no change

**Apple compliance notes (Guideline 3.1.3):**
- ✅ Allowed: Web subscription exists; iOS app unlocks Pro for users who paid on web and sign in
- ❌ NOT allowed inside iOS app: links, buttons, prices, or any mention pushing users to the web checkout
- ❌ NOT allowed: auto-routing from app to web checkout flow

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│ Marketing channel (Twitter / TikTok / blog) → sparrowcollect.com │
└─────────────────────┬────────────────────────────────────────────┘
                      ↓
            ┌─────────────────────────┐
            │  sparrowcollect.com/pro │   ← New page, this plan
            │  Stripe Checkout button │
            └────────────┬────────────┘
                         ↓
            ┌─────────────────────────┐
            │  Stripe hosted Checkout │   ← Stripe-managed, no custom UI
            │  collects email + card  │
            └────────────┬────────────┘
                         ↓
                  successful payment
                         ↓
            ┌─────────────────────────────────────┐
            │ Stripe webhook → Vercel function    │   ← New endpoint
            │ POST /api/stripe/webhook            │
            │   - verify signature                │
            │   - upsert profiles.web_pro_active  │
            └────────────┬────────────────────────┘
                         ↓
            ┌─────────────────────────────────────┐
            │ Supabase: profiles.web_pro_active   │   ← New column
            │ + profiles.stripe_customer_id       │
            └────────────┬────────────────────────┘
                         ↓
            User downloads iOS app, signs in with same email
                         ↓
            ┌─────────────────────────────────────────────────┐
            │ iOS app: useBillingLimits() check              │
            │   isPro = revenueCat.proActive                  │
            │            || supabase.profiles.web_pro_active  │
            └─────────────────────────────────────────────────┘
```

---

## Build checklist

### Stripe setup (user hands — 15 min)
- [ ] Sign up at stripe.com (or log in to existing account)
- [ ] **Test mode** initially. Switch to Live for launch.
- [ ] Create product: `Sparrow Pro Monthly` → **€4.74/mo** recurring (5% off iOS €4.99)
- [ ] Create product: `Sparrow Pro Yearly` → **€37.99/yr** recurring (5% off iOS €39.99)
- [ ] Pricing rationale: web subscribers save ~5%, you save ~10% (Apple 15% → Stripe 3% + 5% discount = 8% effective). Win-win on the marketing-acquired slice.
- [ ] Note the Price IDs (start with `price_`)
- [ ] Stripe → Developers → API Keys → grab Publishable + Secret keys

### Vercel env vars
```bash
cd /Users/merle/GitHub/CcollectAI/web
vercel env add STRIPE_PUBLISHABLE_KEY production
vercel env add STRIPE_SECRET_KEY production
vercel env add STRIPE_WEBHOOK_SECRET production
vercel env add STRIPE_PRICE_MONTHLY production
vercel env add STRIPE_PRICE_YEARLY production
vercel env add SUPABASE_SERVICE_ROLE_KEY production
```
(SUPABASE_URL + SUPABASE_ANON_KEY already set for the web project)

### Supabase migration
- [ ] Add columns:
  ```sql
  ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS web_pro_active boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS stripe_customer_id text,
    ADD COLUMN IF NOT EXISTS stripe_subscription_id text,
    ADD COLUMN IF NOT EXISTS web_pro_expires_at timestamptz;
  CREATE INDEX IF NOT EXISTS idx_profiles_stripe_customer ON public.profiles(stripe_customer_id);
  ```
- [ ] RLS: existing profile-self-read covers it. No new policies needed.

### Web subscription page (`web/pro.html`)
- [ ] Pricing UI: monthly + yearly tiles, "Subscribe" button each
- [ ] Email collection (or sign-in via Supabase magic link first → recommended for account linking)
- [ ] On click → fetch `/api/stripe/checkout-session` → returns Stripe Checkout URL → window.location
- [ ] Success page `/pro/success.html` → "Welcome to Pro. Sign in to the app with the same email to unlock."
- [ ] Cancel page `/pro/cancel.html` → "No worries. [Try again]"

### Vercel API routes
**`web/api/stripe/checkout-session.ts`** (POST)
- Body: `{ priceId, email }`
- Creates Stripe Checkout Session with `mode: 'subscription'`
- `customer_email: email` (or `customer: existing_customer_id` if user already has one)
- `success_url: https://sparrowcollect.com/pro/success?session_id={CHECKOUT_SESSION_ID}`
- `cancel_url: https://sparrowcollect.com/pro/cancel`
- `client_reference_id: supabase_user_id` if signed in
- Returns: `{ url }`

**`web/api/stripe/webhook.ts`** (POST)
- Verify `stripe-signature` header against `STRIPE_WEBHOOK_SECRET`
- Handle events:
  - `checkout.session.completed` → match by client_reference_id or email → upsert profile with stripe_customer_id + stripe_subscription_id + web_pro_active=true + web_pro_expires_at
  - `customer.subscription.updated` → update web_pro_expires_at, web_pro_active based on status
  - `customer.subscription.deleted` → web_pro_active=false
- Use Supabase service role key to write across users
- Return 200 quickly (Stripe retries on non-2xx)

### Stripe dashboard
- [ ] Developers → Webhooks → Add endpoint
- [ ] URL: `https://sparrowcollect.com/api/stripe/webhook`
- [ ] Events to listen for:
  - `checkout.session.completed`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
- [ ] Copy the signing secret → `STRIPE_WEBHOOK_SECRET` env var

### iOS app entitlement read (single-file change, ships in next build)
- [ ] `src/hooks/useBillingLimits.ts` (or wherever entitlement is computed):
  ```ts
  // existing
  const rcPro = customerInfo?.entitlements?.active?.pro != null;

  // NEW: also check Supabase profile for web subscribers
  const { data: profile } = useQuery(...);
  const webPro = profile?.web_pro_active === true &&
                 (!profile?.web_pro_expires_at ||
                  new Date(profile.web_pro_expires_at) > new Date());

  const isPro = rcPro || webPro;
  ```
- [ ] No UI change. No links to web. Just a silent unlock.

### Testing checklist
- [ ] Stripe test mode: complete a subscription with test card `4242 4242 4242 4242`
- [ ] Verify webhook fires (Stripe → Webhooks → recent deliveries → 200)
- [ ] Verify `profiles.web_pro_active` flips to true for the test email
- [ ] iOS dev build: sign in with that email → confirm Pro features unlock
- [ ] Cancel subscription in Stripe → verify web_pro_active goes false → confirm Pro locks again on next iOS app launch

---

## Phase 2 — post-launch (NOT in this plan)
- RevenueCat Stripe integration (unify both purchase paths under RC's customer model)
- "Manage subscription" portal link from iOS app (allowed: Apple lets you link to manage existing subs, not new ones)
- Web app (vs. landing page) so subscribers get value on web too
- Annual plan promotions, free trial via Stripe
- Tax compliance: Stripe Tax for EU VAT

---

## Risks & open questions
- **Account linking**: if a user pays on web with email A, then signs up in the iOS app with email B, they don't get Pro. Mitigation: require Supabase login BEFORE Stripe checkout (recommended) so we know the user_id upfront.
- **Stripe Tax**: enable Stripe Tax to handle EU VAT automatically (mandatory for EU sales over €10k/yr)
- **Subscription expiry race**: web_pro_expires_at must be checked client-side too in case webhook lags
- **Refunds**: Stripe refund → webhook → web_pro_active false. Make sure iOS app handles "I had Pro, now I don't" gracefully (already does via RC)

---

## Effort estimate

| Task | Effort |
|---|---|
| Stripe setup (your hands) | 15 min |
| Web subscription page UI | 1.5 hr |
| Vercel API routes (checkout + webhook) | 2 hr |
| Supabase migration | 10 min |
| iOS entitlement read change | 30 min |
| Stripe test mode E2E test | 30 min |
| Switch to Live mode + final test | 30 min |
| **Total** | **~5.5 hr** |

Can be done in a day. Recommended to ship the web checkout BEFORE the App Store launch so first marketing-driven users have a path that avoids Apple's cut.
