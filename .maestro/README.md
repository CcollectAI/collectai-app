# CollectAI E2E Tests (Maestro)

End-to-end tests for critical user journeys, powered by [Maestro](https://maestro.mobile.dev/).

## Why Maestro?

- **Zero build step** — YAML flows run against any Expo dev client or production build.
- **Cross-platform** — same flow runs on iOS simulator, Android emulator, and physical devices.
- **CI-friendly** — Maestro Cloud runs flows on real devices, integrates with GitHub Actions.
- **Debuggable** — `maestro studio` records flows interactively by tapping through your app.

## Prerequisites

```bash
# Install Maestro CLI (macOS / Linux)
curl -Ls "https://get.maestro.mobile.dev" | bash

# Verify
maestro --version
```

You'll also need:

- **iOS:** Xcode + a running simulator (`xcrun simctl list devices`)
- **Android:** Android Studio + running emulator (`adb devices`)
- **App built & installed** — either `eas build --profile development` or `npx expo run:ios` / `run:android`

## Running the flows

```bash
# Single flow
maestro test .maestro/flows/01_login.yaml

# Whole suite (runs alphabetically)
maestro test .maestro/flows/

# Interactive recorder (for building new flows)
maestro studio
```

## Env vars

Flows use placeholders like `${MAESTRO_TEST_EMAIL}`. Provide them via `--env`:

```bash
maestro test .maestro/flows/01_login.yaml \
  --env MAESTRO_TEST_EMAIL=qa+login@collectai.app \
  --env MAESTRO_TEST_PASSWORD=testpass123
```

Or create `.maestro/.env` (gitignored) with:

```
MAESTRO_TEST_EMAIL=qa+login@collectai.app
MAESTRO_TEST_PASSWORD=testpass123
```

## Current flow coverage

| File | Flow | What it verifies |
|------|------|------------------|
| `01_login.yaml` | Existing user login | Welcome screen, form submission, navigation to home |
| `02_signup.yaml` | New user signup | Form validation, terms checkbox, verify-email screen |
| `03_quickscan.yaml` | First item scan | Add tab → QuickScan → gallery picker → identification → save |
| `04_language_switch.yaml` | i18n language picker | Settings → Language → tab bar relocalizes |

## Adding testID hooks

Flows reference elements by `id:` (React Native `testID` prop). If a flow
fails with "no element found," add a `testID` to the relevant component:

```tsx
<TextInput
  testID="email"
  accessibilityLabel={t('auth.email')}
  ...
/>
```

Current testIDs in use:
- `email`, `password`, `username` — auth form fields (not yet added)
- `gallery-scan-btn` — QuickScan gallery picker (not yet added)
- `open-settings-btn` — home header settings icon (not yet added)

**TODO:** Wire these `testID` props into the actual screens. Without them, the
flows fall back to text-based matching which works but is more brittle.

## CI integration (future)

Once flows are stable locally:

1. Sign up for [Maestro Cloud](https://cloud.mobile.dev/)
2. Push the app build:
   ```bash
   maestro cloud --apiKey=$MAESTRO_API_KEY ./CollectAI.app .maestro/flows/
   ```
3. Add a GitHub Actions job on PR that runs the same command.

## Debugging flows

- `maestro test --debug-output ./debug` — saves screenshots at each step
- `maestro studio` — records a new flow interactively
- `maestro hierarchy` — prints the view hierarchy so you can see what testIDs exist
