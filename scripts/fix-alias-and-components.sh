#!/usr/bin/env bash
set -euo pipefail

echo "→ Ensure folders"
mkdir -p "src/components" "app/(tabs)" app/_shelf src/auth

echo "→ Move components into src/components (with backups, non-destructive)"
for f in Card.tsx Segmented.tsx ShieldBadge.tsx LineChart.tsx; do
  if [ -f "components/$f" ]; then
    cp "components/$f" "components/$f.orphan.bak"
    mv -f "components/$f" "src/components/$f"
    echo "   moved components/$f → src/components/$f"
  fi
done

echo "→ Normalize imports to alias '@/components/...'"
# Replace a few common patterns that cause Metro to look for ../../src/components or similar
find app src -type f \( -name "*.tsx" -o -name "*.ts" \) -print0 | while IFS= read -r -d '' file; do
  tmp="${file}.tmp"
  sed -E \
    -e "s#from ['\"]\.\./\.\./src/components/#from '@/components/#g" \
    -e "s#from ['\"]\.\./src/components/#from '@/components/#g" \
    -e "s#from ['\"]src/components/#from '@/components/#g" \
    -e "s#from ['\"]\.\./\.\./components/#from '@/components/#g" \
    -e "s#from ['\"]\.\./components/#from '@/components/#g" \
    "$file" > "$tmp" && mv "$tmp" "$file"
done

echo "→ Ensure theme + session stubs exist"
if [ ! -f "src/theme.ts" ]; then
  cat > "src/theme.ts" <<'TS'
export const theme = {
  colors: {
    brand: { base: "#1ABC9C" },
    navy: "#0B3D91",
    bg: "#E6F7F8",
    card: "#FFFFFF",
    text: "#0B3D91",
    subtext: "#64748B",
    up: "#10B981",
    down: "#EF4444",
    border: "#E5E7EB",
  },
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
};
TS
fi

mkdir -p src/auth
if [ ! -f "src/auth/session.ts" ]; then
  cat > "src/auth/session.ts" <<'TS'
export type SessionState = { ready: boolean; signedIn: boolean };
export function useSession(): SessionState {
  return { ready: true, signedIn: true };
}
TS
fi

echo "→ Ensure tsconfig alias (@ → ./src)"
if [ -f tsconfig.json ]; then cp tsconfig.json tsconfig.json.bak; fi
# Minimal tsconfig with alias; if you have an advanced tsconfig, merge as needed using the .bak
cat > tsconfig.json <<'JSON'
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "jsx": "react",
    "strict": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
JSON

echo "→ Ensure Babel alias for runtime (Metro)"
if [ -f babel.config.js ]; then cp babel.config.js babel.config.js.bak; fi
cat > babel.config.js <<'JS'
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: [
      'expo-router/babel',
      ['module-resolver', {
        root: ['./'],
        alias: { '@': './src' },
        extensions: ['.tsx', '.ts', '.js', '.jsx', '.json']
      }]
    ],
  };
};
JS

echo "→ Install alias plugin + required deps"
# react-native-svg is used by LineChart, module-resolver handles alias at runtime
npx expo install react-native-svg
npm i -D babel-plugin-module-resolver

echo "→ Done. If Metro is running, please restart it."
