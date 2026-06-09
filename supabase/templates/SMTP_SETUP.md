# Custom SMTP for Sparrow Collect auth emails — Resend + Cloudflare

Goal: send Supabase auth emails from **`noreply@sparrowcollect.com`** (instead of
`noreply@mail.app.supabase.io`) with SPF/DKIM/DMARC passing, so they land in the
inbox and stop looking like phishing. This is the companion to the branded
templates in this folder (`README.md`).

Time: ~20 min of work + up to a few hours for DNS to propagate.
Cost: Resend free tier = 3,000 emails/mo (100/day) — ample for launch. $20/mo for 50k.

---

## ⚠️ Read first — your existing DNS (verified 2026-06-09)

DNS is on **Cloudflare** (NS: `braelyn`/`fred.ns.cloudflare.com`). These records
already exist and **must NOT be changed** — they run your inbound mail:

| Record | Current value | Owner |
|---|---|---|
| `sparrowcollect.com` MX | `mx1/mx2.simplelogin.co` | SimpleLogin (inbound, e.g. support@) |
| `sparrowcollect.com` TXT (SPF) | `v=spf1 include:simplelogin.co ~all` | SimpleLogin |
| `_dmarc.sparrowcollect.com` TXT | `v=DMARC1; p=quarantine; pct=100; adkim=s; aspf=s` | **strict — see Step 7** |

Resend's records live on the **`send.`** and **`resend._domainkey.`** subdomains, so
they don't collide with SimpleLogin's root records. The one interaction that matters
is the **strict DMARC** (`adkim=s; aspf=s`) — handled in Step 7.

---

## Step 1 — Create the Resend domain

1. Sign up at https://resend.com (use a Sparrow-owned login).
2. **Domains → Add Domain → `sparrowcollect.com`** (the root, so you can send from
   `noreply@sparrowcollect.com`). Pick the region closest to your users (EU if
   available, since you're EU-based — it affects the `feedback-smtp` MX host).
3. Resend shows you a set of DNS records to add. They look like this (your DKIM key
   and region will differ — **copy Resend's exact values**, don't use these):

   | Type | Name (Cloudflare "Name" field) | Value |
   |---|---|---|
   | MX | `send` | `feedback-smtp.<region>.amazonses.com` (priority 10) |
   | TXT | `send` | `v=spf1 include:amazonses.com ~all` |
   | TXT | `resend._domainkey` | `p=<long DKIM public key>` |

   (Resend may also suggest a DMARC record — **skip it, you already have one.**)

---

## Step 2 — Add the records in Cloudflare

Cloudflare dashboard → `sparrowcollect.com` → **DNS → Records → Add record**, once per
row above. Gotchas:

- **Name auto-append:** Cloudflare appends the zone automatically. When Resend says
  `send.sparrowcollect.com`, type just **`send`**. For the DKIM record type
  **`resend._domainkey`** (Cloudflare turns it into `resend._domainkey.sparrowcollect.com`).
  Don't type the full domain or you'll get `send.sparrowcollect.com.sparrowcollect.com`.
- **DKIM TXT value** is long — paste it whole, exactly, no added quotes/line breaks.
- **Proxy:** MX and TXT can't be proxied (no orange cloud option — correct). If Resend
  ever gives a **CNAME**, set it to **DNS only (grey cloud)**, never proxied.
- **Don't touch** the existing root MX/SPF (SimpleLogin) or you'll break inbound mail.

---

## Step 3 — Verify in Resend

Back in Resend → **Domains → sparrowcollect.com → Verify**. Cloudflare usually
propagates in minutes; can take up to a few hours. All three (MX, SPF, DKIM) must show
**Verified** before sending.

---

## Step 4 — Create the API key (this is your SMTP password)

Resend → **API Keys → Create API Key** → name it `supabase-auth`, permission
**Sending access**, restrict to domain `sparrowcollect.com`. Copy the `re_…` key now
(shown once). This key is the SMTP password in Step 5.

---

## Step 5 — Point Supabase at Resend SMTP

Supabase → project `ykqrruipzmrrvjcvwfgp` → **Authentication → Emails → SMTP Settings**
→ enable **Custom SMTP**:

| Field | Value |
|---|---|
| Sender email | `noreply@sparrowcollect.com` |
| Sender name | `Sparrow Collect` |
| Host | `smtp.resend.com` |
| Port | `465` (SSL; `587` STARTTLS also works) |
| Username | `resend` |
| Password | the `re_…` API key from Step 4 |

Save. The sender domain **must** match the verified Resend domain — `@sparrowcollect.com`
is fine because you verified the root in Step 1.

---

## Step 6 — Raise the auth rate limit

Supabase's default email rate limit is tiny (a few/hour) because it assumes the shared
sender. With your own SMTP you can lift it: **Authentication → Rate Limits → emails**
→ raise to a sane value (e.g. 30–100/hour). Otherwise real signups can hit
"email rate limit exceeded."

---

## Step 7 — Test, and confirm DMARC actually passes (critical here)

Your DMARC is **strict** (`adkim=s; aspf=s`), so alignment is not automatic:
- **SPF** will be evaluated against Resend's Return-Path `send.sparrowcollect.com`.
  Under `aspf=s` (strict) that does **not** align with the root From → SPF alignment **fails**.
- **DKIM** is signed `d=sparrowcollect.com` (root) → under `adkim=s` it **aligns** → DKIM
  carries DMARC. DMARC passes if *either* aligns, so **you're relying on DKIM here.**

So you must verify DKIM is actually aligning:

1. Trigger a real email — sign up a test account in the app (or Resend → send a test).
2. In Gmail, open the message → **Show original** → check **Authentication-Results**:
   you want `dkim=pass` **and** `dmarc=pass`. (`spf` may say `pass` for
   `send.sparrowcollect.com` but not align — that's expected and fine as long as
   `dmarc=pass` via DKIM.)
3. Run one through https://www.mail-tester.com — aim **9–10/10**.

**If `dmarc=fail`** (mail quarantined to spam — happens if Resend signs DKIM with a
subdomain instead of the root): relax DMARC alignment from strict to **relaxed**. Edit
`_dmarc.sparrowcollect.com` in Cloudflare to:

```
v=DMARC1; p=quarantine; pct=100; adkim=r; aspf=r; rua=mailto:dmarc@sparrowcollect.com
```

Relaxed alignment accepts subdomains of `sparrowcollect.com` (so `send.` aligns) while
still blocking spoofing from unrelated domains — it's the DMARC default and stays
protective. SimpleLogin mail keeps passing under relaxed too. (The added `rua=` gives
you aggregate reports; create that alias in SimpleLogin or drop it.)

---

## Done when
- Resend domain = Verified (MX + SPF + DKIM green)
- Supabase custom SMTP saved, sender `noreply@sparrowcollect.com`
- A real signup email arrives **in the inbox** from "Sparrow Collect", renders the
  branded template, and shows `dkim=pass; dmarc=pass` in headers
- mail-tester ≥ 9/10

After this + the branded templates applied (see `README.md`), the auth emails are
fully branded, authenticated, and off the phishing radar.
