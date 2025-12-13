#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/collectors-merge-recovered}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
RETENTION="${RETENTION:-7}"

echo "→ Using project: $PROJECT_DIR"
[ -f "$PROJECT_DIR/package.json" ] || { echo "❌ package.json not found in $PROJECT_DIR"; exit 1; }

echo "→ Stop Expo/Metro & free ports"
pkill -f "expo start" 2>/dev/null || true
pkill -f "[m]etro" 2>/dev/null || true
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true

cd "$PROJECT_DIR"

echo "→ Align @expo/vector-icons with Expo SDK 53"
npm remove @expo/vector-icons >/dev/null 2>&1 || true
npm install @expo/vector-icons@^14.1.0 --save --no-audit --no-fund

# Ensure expo-font exists (SDK 53 uses ~13.3.x). Only install if missing.
if ! node -p "try{require('./package.json').dependencies['expo-font']||''}catch(e){''}" | grep -q .; then
  npm install expo-font@~13.3.2 --save --no-audit --no-fund
fi

echo "→ Write Icon Test route"
python3 - <<'PY'
from pathlib import Path
Path("app/_shelf").mkdir(parents=True, exist_ok=True)
Path("app/_shelf/icon-test.tsx").write_text(r'''
import { View, Text } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { theme } from '@/theme';
export default function IconTest(){
  return (
    <View style={{flex:1,justifyContent:'center',alignItems:'center',gap:12,backgroundColor:theme.colors.bg}}>
      <Text style={{backgroundColor:'#fff',padding:8,borderWidth:1,borderColor:theme.colors.border,color:theme.colors.navy,fontWeight:'800'}}>Icon Test</Text>
      <Ionicons name="pie-chart-outline" size={28} color={theme.colors.navy} />
      <Ionicons name="albums-outline" size={28} color={theme.colors.navy} />
      <Ionicons name="add-circle-outline" size={28} color={theme.colors.navy} />
      <Ionicons name="storefront-outline" size={28} color={theme.colors.navy} />
      <Ionicons name="settings-outline" size={28} color={theme.colors.navy} />
    </View>
  );
}
''')
print("Wrote app/_shelf/icon-test.tsx")
PY

echo "→ Make timestamped backup & prune to last $RETENTION"
mkdir -p "$BACKUP_DIR"
ts="$(date -u +%Y%m%d-%H%M%S)"
tarball="$BACKUP_DIR/collectors-merge-$ts.tar.gz"
tar -C "$PROJECT_DIR" --exclude=node_modules --exclude=.expo -czf "$tarball" .
echo "✓ Backup: $tarball"
# prune older than retention
(ls -1t "$BACKUP_DIR"/collectors-merge-*.tar.gz 2>/dev/null | sed -n "$((RETENTION+1)),999p" | xargs -r rm -f) || true

echo "→ Install nightly backup cron (02:00 UTC)"
job='0 2 * * * tar -C '"$PROJECT_DIR"' --exclude=node_modules --exclude=.expo -czf '"$BACKUP_DIR"'/collectors-merge-$(date -u +\%Y\%m\%d-\%H\%M\%S).tar.gz . && (ls -1t '"$BACKUP_DIR"'/collectors-merge-*.tar.gz | sed -n '"$((RETENTION+1))"',$p | xargs -r rm -f) # collectors-nightly'
( crontab -l 2>/dev/null | grep -v 'collectors-nightly' ; echo "$job" ) | crontab -

echo "→ Start Expo (tunnel + clear)"
npx expo start --tunnel --clear
