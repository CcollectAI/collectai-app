# Sparrow Collect — Branded auth email templates

Branded, anti-phishing replacements for Supabase's default auth emails.
Project ref: **`ykqrruipzmrrvjcvwfgp`**.

| File | Supabase template | When it sends |
|---|---|---|
| `confirmation.html` | **Confirm signup** | New account (primary onboarding email) |
| `magic_link.html` | **Magic Link** | Passwordless sign-in |
| `recovery.html` | **Reset Password** | Password reset request |
| `invite.html` | **Invite user** | Admin-invited user |
| `email_change.html` | **Change Email Address** | User changes their email |
| `reauthentication.html` | **Reauthentication** | OTP step-up (shows `{{ .Token }}`) |

## Why these look legit (and the defaults don't)

The defaults are a bare link with no branding from `noreply@mail.app.supabase.io` —
which trips spam filters and reads as phishing. These templates fix the **content**
half:
- Text-first wordmark (brand shows even when images are blocked, as security-aware clients do)
- A real CTA button **plus the full URL in plain text** — phishing hides its links; we show ours
- "You're receiving this because `{{ .Email }}` signed up" — clear reason-for-receipt
- Expiry + single-use notice, "ignore if you didn't request this", and an explicit
  "we'll never ask for your password/payment by email" line
- Brand palette (deep tiffany `#2C7873` for AA-contrast white button text; `#81D8D0` is too light), `support@sparrowcollect.com`, `sparrowcollect.com` footer
- Bulletproof table layout + inline styles (Gmail / Outlook / Apple Mail safe)

## Suggested subject lines (set alongside each template)

- Confirm signup: `Confirm your email — Sparrow Collect`
- Magic Link: `Your Sparrow Collect sign-in link`
- Reset Password: `Reset your Sparrow Collect password`
- Invite: `You're invited to Sparrow Collect`
- Change Email: `Confirm your new email — Sparrow Collect`
- Reauthentication: `Your Sparrow Collect verification code`

## How to apply

### Option A — Dashboard (simplest; Merle)
Supabase → project `ykqrruipzmrrvjcvwfgp` → **Authentication → Email Templates**.
For each template: paste the matching file's HTML into the message body and set the
subject above. Save. Send yourself a test from the app.

### Option B — Management API (scriptable)
Needs `SUPABASE_ACCESS_TOKEN` (present on EC2 `/opt/collectors/.env`). Fields:
`mailer_subjects_confirmation`, `mailer_templates_confirmation_content`, and the
`magic_link` / `recovery` / `invite` / `email_change` / `reauthentication` variants.
```
PATCH https://api.supabase.com/v1/projects/ykqrruipzmrrvjcvwfgp/config/auth
Authorization: Bearer $SUPABASE_ACCESS_TOKEN
Content-Type: application/json
{ "mailer_templates_confirmation_content": "<...confirmation.html...>",
  "mailer_subjects_confirmation": "Confirm your email — Sparrow Collect", ... }
```

## ⚠️ The other half of "not phishing" — the SENDER (needs Merle's decision)

Branded HTML from `noreply@mail.app.supabase.io` still looks off and can land in spam.
To send from a Sparrow Collect address you need **custom SMTP + DNS auth**:

1. Pick an SMTP provider (Resend / Postmark / Amazon SES — Resend is simplest).
2. Verify domain `sparrowcollect.com` there → it gives **SPF**, **DKIM**, and
   (recommended) **DMARC** DNS records to add at the domain's DNS (Cloudflare).
3. Supabase → **Authentication → SMTP Settings**: enter the provider's host/port/
   user/pass, sender name `Sparrow Collect`, sender email `noreply@sparrowcollect.com`.

> Per project memory, DNS/email changes are Merle's call — do not add DNS records or
> pick a provider without confirming. The templates above work with the default sender
> too; the SMTP step is what gets them out of spam and fully off the phishing radar.

## Also verify (so the confirmation link resolves)
Supabase → **Authentication → URL Configuration**: Site URL + Redirect allowlist must
include the app deep link (`io.sparrowcollect.app` / `sparrow://`) and
`https://sparrowcollect.com`, or `{{ .ConfirmationURL }}` will dead-end.

## Test before trusting
- Send each type from the app / dashboard.
- Render-check Gmail (web + iOS) and Apple Mail.
- Run one through https://www.mail-tester.com (aim 9–10/10) — flags missing SPF/DKIM.
