# Sparrow Collect — Android / Play Store via fastlane supply

> Generated 2026-05-12 alongside the iOS App Store launch infra. Android
> ships 1-2 weeks after iOS per `docs/PUBLIC_LAUNCH_CHECKLIST.md`.
> Everything here is pre-staged so the Android cutover is a 2-step
> action when iOS launch validates.

## What's in this directory

```
android/fastlane/
├── Appfile                              — package_name + service-account key path
├── Fastfile                             — three lanes: internal, beta, metadata
├── README.md                            — this file
└── metadata/android/en-US/
    ├── title.txt                        — "Sparrow Collect" (30 char cap)
    ├── short_description.txt            — 80 char tagline
    ├── full_description.txt             — 4000 char Play description
    ├── privacy_url.txt                  — https://sparrowcollect.com/privacy
    ├── changelogs/default.txt           — release notes per-version
    └── images/
        ├── icon/icon.png                — 512×512 app icon
        ├── featureGraphic/featureGraphic.png — 1024×500 Play hero graphic
        └── phoneScreenshots/1-6.png     — iPhone-rendered screenshots
                                           (Play accepts them as Android too)
```

## Before first upload — one-time Google Play setup

1. **Enrol in Google Play Console** ($25 one-time):
   https://play.google.com/console → Create developer account →
   verify identity (<24h).

2. **Create the app**:
   - Name: `Sparrow Collect`
   - Package name: `io.sparrowcollect.app` (must match `app.json` android.package)
   - Default language: English (United States)
   - App or game: App
   - Free or paid: Free

3. **Create a service account for `fastlane supply`** (so uploads don't
   need interactive Google login each time):
   - https://console.cloud.google.com → IAM & Admin → Service Accounts
   - Create → name `sparrow-eas-supply` → grant **Service Account User**
   - Click the new SA → Keys → Add Key → JSON → download
   - Save as `~/secure/sparrow-play-service-account.json` (or any path
     outside this repo — keep it out of git)
   - In Play Console → Setup → API access → Link the service account →
     grant "Release apps to testing tracks" + "Manage testing tracks"

4. **Export the path** so fastlane finds it:
   ```bash
   export FASTLANE_PLAY_JSON_KEY=~/secure/sparrow-play-service-account.json
   ```

## Building + uploading

EAS does the build. Fastlane does the upload. Single flow:

```bash
# 1. Build AAB on EAS cloud (~15 min)
cd /Users/merle/GitHub/CcollectAI
eas build -p android --profile production

# 2. Download the AAB locally
eas build:download --platform android --latest --output sparrow.aab

# 3. Upload to Play Internal Testing
cd android
bundle exec fastlane internal aab:../sparrow.aab
```

Or push metadata-only updates (no new build) — useful for fixing typos
in the listing without re-publishing the binary:

```bash
cd android
bundle exec fastlane metadata
```

## Promoting to closed beta or production

After validating an Internal build, promote without re-uploading:

```bash
cd android
bundle exec fastlane beta   # internal → closed beta
```

Production promotion is intentionally NOT scripted — do that one
through the Play Console UI so you don't accidentally publish a broken
build. Edit `Fastfile` to add a `lane :production` once the manual
muscle-memory is built.

## Updating the listing copy

All English text lives in `metadata/android/en-US/`. To add other
languages:

```bash
mkdir -p metadata/android/{nl-NL,de-DE,fr-FR}
# Copy en-US files, translate each .txt
# `fastlane supply` uploads them all on next run.
```

## Updating the feature graphic

The `featureGraphic.png` was rendered via headless Chrome from
`/tmp/play_feature_graphic.html` (committed by the launch infra commit
of 2026-05-12). To regenerate:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless --disable-gpu --hide-scrollbars --window-size=1024,500 \
  --screenshot=android/fastlane/metadata/android/en-US/images/featureGraphic/featureGraphic.png \
  /path/to/play_feature_graphic.html
```

Min dimensions: 1024×500. Max: same. PNG or JPEG. Under 15 MB.

## What fastlane explicitly does NOT do here

- **It does not build APKs / AABs.** EAS does. Don't add `gradle` or
  `build` lanes — that drifts from the iOS flow.
- **It does not manage signing keys.** EAS handles upload signing via
  the same Apple-Developer-style server-side keychain. To rotate:
  `eas credentials -p android`.
- **It does not handle Play Console policy attestations.** New apps
  must answer Apple-Privacy-style questionnaires (data safety form,
  content rating, target audience). Do those in the Play Console UI
  on first submission — they don't change often.

## Reference

- `docs/PUBLIC_LAUNCH_CHECKLIST.md` — full launch sequence (iOS first,
  then Android)
- `docs/app-store-aso.md` — the source of all listing copy (Apple +
  Google). When you change copy there, copy to the relevant
  `metadata/*.txt` here.
- `docs/ASC_API_KEY.md` — companion doc for the iOS submit key
