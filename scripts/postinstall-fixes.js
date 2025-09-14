const fs = require('fs');
const path = require('path');

function ensureSchemaUtilsBuildShim() {
  const root = process.cwd();
  const mod = path.join(root, 'node_modules', '@expo', 'schema-utils');
  const dist = path.join(mod, 'dist');
  const build = path.join(mod, 'build');
  const distIndex = path.join(dist, 'index.js');
  const buildIndex = path.join(build, 'index.js');

  if (!fs.existsSync(mod)) return; // package not installed; nothing to do yet

  // If build/index.js exists, great.
  if (fs.existsSync(buildIndex)) return;

  // If dist/index.js exists but build/ doesn't, create a compatibility shim.
  if (fs.existsSync(distIndex)) {
    try {
      if (!fs.existsSync(build)) fs.mkdirSync(build, { recursive: true });
      // simple CJS re-export; works for expo-router/plugin require()
      fs.writeFileSync(buildIndex, "module.exports = require('../dist');\n", 'utf8');
      console.log('[@expo/schema-utils] Created build/index.js shim → dist/.');
    } catch (e) {
      console.warn('[@expo/schema-utils] Failed to create build shim:', e?.message || e);
    }
  }
}

try {
  ensureSchemaUtilsBuildShim();
} catch (e) {
  console.warn('[postinstall-fixes] error:', e?.message || e);
}
