#!/bin/bash
# JS-only Android APK in minutes instead of a ~25-minute Gradle build.
#
# Puts a freshly bundled, Hermes-compiled index.android.bundle into an ALREADY
# BUILT release APK and re-signs it with the local debug key. Valid ONLY when
# nothing native changed since that APK was built (no new native dep, icon,
# permission, app.json plugin/config change) — the native code is the base
# APK's, byte for byte. See docs/ANDROID_LAUNCH.md "JS-only APK".
#
#   scripts/android_jsswap.sh bundle           export + hermes-compile the working tree
#   scripts/android_jsswap.sh pack [HBC]       swap the bundle into the base APK, align, sign
#   scripts/android_jsswap.sh install [SERIAL] uninstall + install (the signature differs)
#
# Env: BASE_APK (default builds/sparrow-android-apk.apk), OUT_APK
# (default builds/sparrow-android-jsswap.apk).
#
# ⚠️ The install UNINSTALLS first: a debug-signed APK cannot replace the
# Expo-keystore-signed one. The session is lost — sign in again.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${TMPDIR:-/tmp}/sparrow-jsswap"
BASE_APK="${BASE_APK:-$REPO/builds/sparrow-android-apk.apk}"
OUT_APK="${OUT_APK:-$REPO/builds/sparrow-android-jsswap.apk}"
SDK=/usr/local/share/android-commandlinetools
BT=$SDK/build-tools/36.0.0
export JAVA_HOME=/usr/local/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
mkdir -p "$WORK"

case "${1:-}" in
  bundle)
    rm -rf "$WORK/js" && mkdir -p "$WORK/js"
    cd "$REPO"
    # The env the android-apk profile builds with: the EAS "production"
    # environment, then that profile's pinned overrides (eas.json) — paywall ON
    # (BETA_UNLOCK_ALL=false) and strict data mode. EXPO_PUBLIC_* are inlined at
    # bundle time, so a bundle made without them points at nothing.
    npx eas env:exec production --non-interactive \
      "EXPO_PUBLIC_SUPABASE_MODE=strict EXPO_PUBLIC_BETA_UNLOCK_ALL=false npx expo export:embed --platform android --dev false --reset-cache --entry-file node_modules/expo-router/entry.js --bundle-output $WORK/js/index.android.bundle --assets-dest $WORK/js/res" \
      > "$WORK/bundle.log" 2>&1 || { tail -30 "$WORK/bundle.log"; exit 1; }
    "$REPO/node_modules/react-native/sdks/hermesc/osx-bin/hermesc" -O -emit-binary \
      -out="$WORK/js/index.android.bundle.hbc" "$WORK/js/index.android.bundle"
    ls -la "$WORK/js/index.android.bundle.hbc"
    ;;
  pack)
    HBC="${2:-$WORK/js/index.android.bundle.hbc}"
    rm -rf "$WORK/stage" && mkdir -p "$WORK/stage/assets"
    cp "$HBC" "$WORK/stage/assets/index.android.bundle"
    cp "$BASE_APK" "$WORK/unsigned.apk"
    zip -q -d "$WORK/unsigned.apk" 'META-INF/*.SF' 'META-INF/*.RSA' 'META-INF/*.MF' 2>/dev/null || true
    # -0: the base APK STORES the bundle uncompressed (Hermes mmaps it). A plain
    # `zip` deflates it — match the original instead.
    (cd "$WORK/stage" && zip -q -0 "$WORK/unsigned.apk" assets/index.android.bundle)
    "$BT/zipalign" -p -f 4 "$WORK/unsigned.apk" "$WORK/aligned.apk"
    "$BT/apksigner" sign --ks ~/.android/debug.keystore --ks-pass pass:android \
      --key-pass pass:android --out "$OUT_APK" "$WORK/aligned.apk"
    "$BT/apksigner" verify "$OUT_APK"
    echo "signed: $OUT_APK"
    ;;
  install)
    ADB="$SDK/platform-tools/adb -s ${2:-emulator-5560}"
    $ADB uninstall io.sparrowcollect.app || true
    $ADB install "$OUT_APK"
    ;;
  *)
    sed -n 2,18p "$0"; exit 1;;
esac
