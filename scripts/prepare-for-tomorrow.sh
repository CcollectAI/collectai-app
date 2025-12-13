#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/collectors-merge-recovered}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
RETENTION="${RETENTION:-7}"

echo "→ Project: $PROJECT_DIR"
[ -f "$PROJECT_DIR/package.json" ] || { echo "❌ package.json not found in $PROJECT_DIR"; exit 1; }

echo "→ Stop Expo/Metro & free ports (safe)"
pkill -f "expo start" 2>/dev/null || true
pkill -f "[m]etro" 2>/dev/null || true
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true

cd "$PROJECT_DIR"

# -------------------------------------------------------------------
# 1) Align icons with Expo SDK 53 (vector-icons 14.x + expo-font 13.x)
# -------------------------------------------------------------------
echo "→ Aligning @expo/vector-icons for SDK 53"
# Bring package.json in line *before* install to avoid ERESOLVE
node - <<'JS'
const fs = require('fs');
const p = 'package.json';
const pkg = JSON.parse(fs.readFileSync(p,'utf8'));
pkg.dependencies = pkg.dependencies || {};
// Pin vector-icons to ^14.1.0 (SDK53 line)
pkg.dependencies['@expo/vector-icons'] = '^14.1.0';
// Keep expo-font on ~13.3.x if present or missing
if (!pkg.dependencies['expo-font'] || !/^~13\./.test(pkg.dependencies['expo-font'])) {
  pkg.dependencies['expo-font'] = '~13.3.2';
}
fs.writeFileSync(p, JSON.stringify(pkg, null, 2));
console.log('package.json updated: @expo/vector-icons ^14.1.0, expo-font ~13.3.2');
JS

# -------------------------------------------------------------------
# 2) Install deps cleanly (ci → fallback to lock sync → install)
# -------------------------------------------------------------------
echo "→ Installing dependencies (ci → fallback)"
if npm ci --no-audit --no-fund; then
  echo "✓ npm ci ok"
else
  echo "⚠️ npm ci failed — syncing lockfile"
  npm install --package-lock-only --no-audit --no-fund || true
  if npm ci --no-audit --no-fund; then
    echo "✓ npm ci ok after lock sync"
  else
    echo "⚠️ Fallback to npm install"
    npm install --no-audit --no-fund
  fi
fi

# Ensure expo-router is resolvable (common after recovery)
node -e "require.resolve('expo-router/package.json')" 2>/dev/null || npm i expo-router --no-audit --no-fund

# -------------------------------------------------------------------
# 3) Patch LineChart.tsx (fixes the 'Invalid shorthand property initializer')
# -------------------------------------------------------------------
echo "→ Patching src/components/LineChart.tsx (idempotent)"
python3 - <<'PY'
from pathlib import Path
p=Path("src/components/LineChart.tsx")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(r'''import React, { useMemo, useRef, useState } from 'react';
import { View, Text, PanResponder, LayoutChangeEvent, GestureResponderEvent } from 'react-native';
import Svg, { Path, Rect, Defs, ClipPath, G, Line, Circle } from 'react-native-svg';
import { theme } from '@/theme';

export type Point = { t: number; y: number };

export default function LineChart({
  data,
  height = 160,
  padding = 16,
  gridY = 4,
  gridX = 6,
}: {
  data: Point[];
  height?: number;
  padding?: number;
  gridY?: number;
  gridX?: number;
}) {
  const [w, setW] = useState(0);
  const [cursor, setCursor] = useState<{ x: number; y: number; i: number } | null>(null);

  const onLayout = (e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width);

  const { path, scaleX, scaleY, hi, lo } = useMemo(() => {
    const xs = data.map(d => d.t), ys = data.map(d => d.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY0 = Math.min(...ys), maxY0 = Math.max(...ys);
    const padY = (maxY0 - minY0) * 0.08 || 1;
    const minY = minY0 - padY, maxY = maxY0 + padY;

    const scaleX = (x: number) =>
      padding + (w > 0 ? ((x - minX) / (maxX - minX || 1)) * (w - padding * 2) : 0);

    const scaleY = (y: number) => {
      const h = height - padding * 2;
      const v = padding + (1 - (y - minY) / (maxY - minY || 1)) * h;
      return Math.max(padding, Math.min(height - padding, v));
    };

    let d = '';
    data.forEach((p, i) => {
      const X = scaleX(p.t), Y = scaleY(p.y);
      d += i === 0 ? `M ${X} ${Y}` : ` L ${X} ${Y}`;
    });

    let hiI = 0, loI = 0;
    for (let i = 1; i < data.length; i++) {
      if (data[i].y > data[hiI].y) hiI = i;
      if (data[i].y < data[loI].y) loI = i;
    }

    return { path: d, scaleX, scaleY, hi: hiI, lo: loI };
  }, [data, w, height, padding]);

  const move = (x: number) => {
    if (w <= 0 || data.length === 0) return;
    let nearest = 0, best = Infinity;
    const span = (data[data.length - 1].t - data[0].t) || 1;
    data.forEach((p, i) => {
      const px = padding + (w - padding * 2) * ((p.t - data[0].t) / span);
      const d = Math.abs(px - x);
      if (d < best) { best = d; nearest = i; }
    });
    const p = data[nearest];
    setCursor({ x: scaleX(p.t), y: scaleY(p.y), i: nearest });
  };

  const pan = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onPanResponderGrant: (e: GestureResponderEvent) => move(e.nativeEvent.locationX),
      onPanResponderMove: (e: GestureResponderEvent) => move(e.nativeEvent.locationX),
      onPanResponderRelease: () => setCursor(null),
      onPanResponderTerminate: () => setCursor(null),
    })
  ).current;

  const fmt = (n: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(n);

  return (
    <View onLayout={onLayout} style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border }}>
      <Svg height={height} width="100%" {...pan.panHandlers}>
        <Defs>
          <ClipPath id="clip">
            <Rect x={padding} y={padding} width={Math.max(0, w - padding * 2)} height={height - padding * 2} />
          </ClipPath>
        </Defs>
        <G>
          {Array.from({ length: gridY + 1 }).map((_, i) => {
            const y = padding + (i * (height - padding * 2)) / gridY;
            return <Line key={'gy' + i} x1={padding} x2={Math.max(padding, w - padding)} y1={y} y2={y} stroke={theme.colors.border} strokeWidth={1} />;
          })}
          {Array.from({ length: gridX + 1 }).map((_, i) => {
            const x = padding + (i * Math.max(0, w - padding * 2)) / gridX;
            return <Line key={'gx' + i} y1={padding} y2={height - padding} x1={x} x2={x} stroke={theme.colors.border} strokeWidth={1} />;
          })}
        </G>
        <G clipPath="url(#clip)">
          <Path d={path} stroke={theme.colors.navy} strokeWidth={2} fill="none" />
        </G>
        {data.length > 0 && (
          <>
            <Circle cx={scaleX(data[hi].t)} cy={scaleY(data[hi].y)} r={3} fill={theme.colors.up} />
            <Circle cx={scaleX(data[lo].t)} cy={scaleY(data[lo].y)} r={3} fill={theme.colors.down} />
          </>
        )}
        {cursor && (
          <G pointerEvents="none">
            <Line x1={cursor.x} x2={cursor.x} y1={padding} y2={height - padding} stroke={theme.colors.navy} strokeDasharray="3 3" />
            <Circle cx={cursor.x} cy={cursor.y} r={4} fill="#fff" stroke={theme.colors.navy} />
          </G>
        )}
      </Svg>
      {cursor && (
        <View
          style={{
            position: 'absolute',
            left: Math.max(padding, Math.min(cursor.x - 48, (w - 96))),
            top: 6,
            backgroundColor: '#fff',
            borderWidth: 1,
            borderColor: theme.colors.border,
            paddingHorizontal: 8,
            paddingVertical: 4,
          }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{fmt(data[cursor.i].y)}</Text>
        </View>
      )}
    </View>
  );
}
''')
print("Patched: src/components/LineChart.tsx")
PY

# -------------------------------------------------------------------
# 4) Add quick diagnostic routes (icon-test, health)
# -------------------------------------------------------------------
echo "→ Writing /_shelf routes (icon-test, health)"
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
Path("app/_shelf/health.tsx").write_text(r'''
import { View, Text } from 'react-native';
import { theme } from '@/theme';
export default function Health(){
  return (
    <View style={{flex:1,justifyContent:'center',alignItems:'center',backgroundColor:theme.colors.bg}}>
      <Text style={{backgroundColor:'#fff',padding:10,borderWidth:1,borderColor:theme.colors.border,color:theme.colors.navy,fontWeight:'800'}}>
        ✅ Expo Router up & rendering
      </Text>
    </View>
  );
}
''')
print("Wrote: app/_shelf/icon-test.tsx, app/_shelf/health.tsx")
PY

# -------------------------------------------------------------------
# 5) Create helper scripts (dev, backup-now) & cron
# -------------------------------------------------------------------
echo "→ Creating scripts/dev.sh"
mkdir -p scripts
cat > scripts/dev.sh <<'BASH'
#!/usr/bin/env bash
set -euo pipefail
pkill -f "expo start" 2>/dev/null || true
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true
# Optional: clear caches
rm -rf .expo /tmp/metro-* ~/.cache/expo ~/.expo 2>/dev/null || true
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
BASH
chmod +x scripts/dev.sh

echo "→ Creating scripts/backup-now.sh (keeps last 7)"
cat > scripts/backup-now.sh <<'BASH'
#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="${PROJECT_DIR:-$HOME/collectors-merge-recovered}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
RETENTION="${RETENTION:-7}"
mkdir -p "$BACKUP_DIR"
ts="$(date -u +%Y%m%d-%H%M%S)"
tarball="$BACKUP_DIR/collectors-merge-$ts.tar.gz"
tar -C "$PROJECT_DIR" --exclude=node_modules --exclude=.expo -czf "$tarball" .
echo "✓ Backup: $tarball"
(ls -1t "$BACKUP_DIR"/collectors-merge-*.tar.gz 2>/dev/null | sed -n "$((RETENTION+1)),999p" | xargs -r rm -f) || true
BASH
chmod +x scripts/backup-now.sh

echo "→ Installing nightly backup cron (02:00 UTC)"
job='0 2 * * * bash '"$PROJECT_DIR"'/scripts/backup-now.sh # collectors-nightly'
( crontab -l 2>/dev/null | grep -v 'collectors-nightly' ; echo "$job" ) | crontab -

# -------------------------------------------------------------------
# 6) Do one backup right now
# -------------------------------------------------------------------
echo "→ Running backup-now"
bash scripts/backup-now.sh

echo "✓ All set. Tomorrow, run:  bash scripts/dev.sh"
echo "Open in Expo Go:  /_shelf/icon-test  and  /_shelf/health"
