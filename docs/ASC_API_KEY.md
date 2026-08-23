# App Store Connect API Key — Sparrow Collect

> Reference for the ASC API key that `eas submit` uses to upload `.ipa`
> files to TestFlight. EAS auto-generated this key during the first
> production build on 2026-05-12. **The key is stored on EAS servers,
> not in this repo.** Document below covers: what it is, how to inspect
> it, how to revoke / rotate, and what to do if something breaks.

## What the key is

An **App Store Connect API key** is a `.p8` private key + Key ID +
Issuer ID triple that authenticates against Apple's App Store Connect
API. It's distinct from:

- **Apple Developer auth** (your Apple ID `slendebroekmerle@gmail.com`
  + password + 2FA) — used at *build time* by EAS to provision
  distribution certificates.
- **In-App Purchase API key** — a *separate* `.p8` key for RevenueCat
  (or any IAP server) to read receipt validation data. Created
  separately in ASC → Users and Access → Integrations → In-App Purchase.

The submission key only does one thing: upload finished builds to App
Store Connect / TestFlight via the `eas submit` step.

## Where the current key lives

EAS auto-created **`[Expo] EAS Submit CA3AAMCGiZ`** during the first
`eas build --auto-submit` run on 2026-05-12 against build
`ee9f647a-e88b-4737-a540-d93ea35efbe2`. The key:

- Is stored **server-side on EAS** — you don't have the `.p8` locally
- Is **scoped to one role**: Developer (write access to apps + builds,
  no banking/agreements access)
- Is **valid until manually revoked** — no expiry by default
- Is **specific to this Apple Developer account** (Team ID `3DX8FBF7S6`)

To inspect:
```bash
eas credentials -p ios
# Pick "production" → "App Store Connect API Key" section shows the
# Key ID, Issuer ID, and EAS-managed status.
```

Or in App Store Connect:
- [Users and Access → Integrations → App Store Connect API](https://appstoreconnect.apple.com/access/integrations/api)
- Key Name: `[Expo] EAS Submit CA3AAMCGiZ`
- Key ID: **`AM32RK7DAY`** — observed in a live `eas submit` on 2026-08-09
  (*"App Store Connect API Key already set up. Using Api Key ID: AM32RK7DAY"*).
  This doc previously said `VT5SJZ3AUH`; the key was rotated at some point after
  it was written. **Read the key ID off the submit output, not from here** — EAS
  holds the key server-side, so this file is a record, not the source of truth.

## Querying the ASC API directly (2026-08-23)

**This is possible, and a doc in this repo said for three months that it was
not.** `docs/MONETIZATION.md` recorded ASC as *"not checkable from here"*
because the Issuer ID *"is recorded nowhere"* — true of the key it was looking
at (`AuthKey_LAU7D8HU29.p8` in `~/.appstoreconnect/private_keys/`), and false
for the account, which cost several sessions of guessing at Apple-side state.

Everything needed is already on this machine:

| item | value / location |
|---|---|
| Key ID | `AM32RK7DAY` (Admin, created 2026-05-20) |
| Issuer ID | `215c3feb-76f3-4399-a0bb-d2385003e1b1` — a non-secret UUID |
| Private key | `~/Documents/Sparrow/Keys/AuthKey_AM32RK7DAY.p8` |
| App ID | `6767359453` (`io.sparrowcollect.app`) |

The Issuer ID is held by **EAS**, not only by Apple — `POST https://api.expo.dev/graphql`
with the existing `~/.expo/state.json` session, querying
`account.byName("collectai").appStoreConnectApiKeys`, returns both
`keyIdentifier` and `issuerIdentifier`. Sign an ES256 JWT with the `.p8` and
every `api.appstoreconnect.apple.com` endpoint answers 200.

⚠️ **What the API still does NOT expose: the agreements.** There is no endpoint
returning whether the **Paid Applications Agreement** is active. That one needs
a human on `appstoreconnect.apple.com/business`. Do not go looking again.

⚠️ **And a subscription's `state` is NOT a proxy for it.** Both products read
`READY_TO_SUBMIT` — and `docs/PUBLIC_LAUNCH_CHECKLIST.md` records them at
exactly that status on **2026-05-20**, three months before the agreement
question was raised. An unchanged value is not evidence of a change. Check the
timeline of any "status" before treating it as a signal
([[learning_validate_values_not_just_structure]]).

## When you'd revoke / rotate

Three reasons to rotate this key:

1. **Suspected compromise** — if you think someone outside your team
   has had access to your EAS account or terminal history. Apple
   recommends rotating annually as standard practice.
2. **Migrating to a different ASC account** — e.g. moving from
   individual to organization Apple Developer enrolment. The old key
   stops working once the team changes; create a new one in the new
   team and re-link in EAS.
3. **EAS recommends it** — periodically EAS surfaces a "key is X months
   old, consider rotating" prompt on `eas credentials`. Following it is
   low-risk and takes 60 seconds.

## How to rotate

```bash
# Step 1 — revoke the old key (run from anywhere)
# Open https://appstoreconnect.apple.com/access/integrations/api
# Find "[Expo] EAS Submit CA3AAMCGiZ" → click → "Revoke" → confirm.

# Step 2 — let EAS generate a fresh one on the next submit
cd /Users/merle/GitHub/CcollectAI
eas build -p ios --profile production --auto-submit
# When prompted "Generate a new App Store Connect API Key?" → Y
```

After Y, EAS provisions a fresh key + uploads the binary using it. Old
key is dead, new one is live. No code changes needed.

## What to do if `eas submit` fails with key errors

Error message: `Authentication failed (403)` or `Apple API key invalid`:

1. Confirm the key still exists in ASC → Users and Access →
   Integrations. If revoked or missing, go to "How to rotate" above.
2. Confirm `eas.json` submit config still references the right
   `appleTeamId` (`3DX8FBF7S6`) and `ascAppId` (`6767359453`).
3. If you've recently changed Apple Developer team or transferred the
   app: the key is team-scoped, you need a new one.

## Why we don't manage a `.p8` file locally

A common Stack Overflow tutorial says "create a `.p8` API key yourself
and check it into `~/.appstoreconnect/`". For us, EAS handles this
server-side — your laptop doesn't need the secret, and rotating in ASC
+ re-running `eas build` is the whole rotation flow. The trade-off is
slight: EAS becomes part of your trust chain (anyone with write access
to your EAS account can use this key). For a solo founder repo that's
fine; an enterprise team may prefer manually-managed keys with
hardware-token rotation.

## Related infrastructure

| Key / secret | Where it lives | Used for |
|---|---|---|
| ASC API Key (this doc) | EAS servers, key ID in `eas credentials` | `eas submit` upload to TestFlight |
| Apple ID + 2FA | Your Apple Developer account | `eas build` cert provisioning prompts |
| Distribution Certificate (.p12) | EAS-managed Apple Developer entry | Signing the iOS binary at build time |
| Provisioning Profile | EAS-managed Apple Developer entry | Embedded in `.ipa` for signing verification |
| In-App Purchase API Key | (Not yet created — see Phase 1.4 of `docs/PUBLIC_LAUNCH_CHECKLIST.md`) | RevenueCat / IAP server-to-server receipt validation |
