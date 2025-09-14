import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = process.cwd();

const SRC_DIR = path.join(ROOT, "src");
const APP_DIR = path.join(ROOT, "app");

/** config */
const exts = [".ts", ".tsx", ".js", ".jsx"];
const ignoreDirs = new Set([
  "node_modules", ".git", ".expo", ".next", "dist", "build",
  "app/_shelf"
]);

/** utilities */
const exists = (p) => {
  try { fs.statSync(p); return true; } catch { return false; }
};
const isFile = (p) => {
  try { return fs.statSync(p).isFile(); } catch { return false; }
};
const walk = (dir) => {
  /** depth-first file list, skipping ignored */
  let out = [];
  let entries = [];
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return out; }
  for (const e of entries) {
    if (ignoreDirs.has(e.name)) continue;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) out = out.concat(walk(full));
    else out.push(full);
  }
  return out;
};
const looksLikeSource = (fp) => exts.some((x) => fp.endsWith(x)) && (fp.startsWith(APP_DIR) || fp.startsWith(SRC_DIR));

/** collect files */
const files = [APP_DIR, SRC_DIR].flatMap((d) => exists(d) ? walk(d) : []).filter(looksLikeSource);

/** capture problems */
const problems = {
  alias: [],
  imports: [],
  missing: [],
  routes: [],
  theme: [],
  session: [],
};

const note = (bucket, file, msg) => problems[bucket].push({ file, msg });

/** 1) Alias sanity (babel + tsconfig) */
const babelCfgPath = path.join(ROOT, "babel.config.js");
const tsCfgPath = path.join(ROOT, "tsconfig.json");

const checkBabelAlias = () => {
  if (!exists(babelCfgPath)) {
    note("alias", "babel.config.js", "Not found (expected module-resolver alias '@' → './src').");
    return;
  }
  const s = fs.readFileSync(babelCfgPath, "utf8");
  const hasPlugin = /module-resolver/.test(s);
  const hasAlias = /['"]@['"]\s*:\s*['"]\.\/src['"]/.test(s);
  if (!hasPlugin || !hasAlias) {
    note("alias", "babel.config.js", "Missing module-resolver or alias '@' → './src'.");
  }
};

const checkTsAlias = () => {
  if (!exists(tsCfgPath)) return; // optional
  try {
    const j = JSON.parse(fs.readFileSync(tsCfgPath, "utf8"));
    const paths = j?.compilerOptions?.paths || {};
    const ok = paths["@/*"] && Array.isArray(paths["@/*"]) && paths["@/*"].some((v) => v.replace(/\\/g,"/").startsWith("src/"));
    if (!ok) {
      note("alias", "tsconfig.json", "Missing paths mapping '@/*' → ['src/*'].");
    }
  } catch {
    note("alias", "tsconfig.json", "JSON invalid; cannot verify '@/*' mapping.");
  }
};

checkBabelAlias();
checkTsAlias();

/** 2) Import hygiene + resolve */
const importRe = /\bimport(?:["'\s]*([\w*{}\n, ]+)from\s*)?["']([^"']+)["'];?/g;
const exportFromRe = /\bexport\s+[^;]*\s+from\s+["']([^"']+)["']/g;
const requireRe = /\brequire\(\s*["']([^"']+)["']\s*\)/g;

const resolveSpec = (fromFile, spec) => {
  // Skip packages (bare imports)
  if (!spec.startsWith(".") && !spec.startsWith("@/")) return { ok: true };

  const base = spec.startsWith("@/")
    ? path.join(SRC_DIR, spec.slice(2))
    : path.resolve(path.dirname(fromFile), spec);

  // Candidate files: direct, with extensions, index files
  const cands = [base, ...exts.map((e) => base + e), ...exts.map((e) => path.join(base, "index" + e))];
  for (const c of cands) {
    if (isFile(c)) return { ok: true };
  }
  return { ok: false, hint: base };
};

for (const fp of files) {
  const code = fs.readFileSync(fp, "utf8");

  // Hygiene: forbid "../../src/..." and "@/src/..."
  if (/\.\.\/(?:\.\.\/)*src\//.test(code)) {
    note("imports", fp, "Use '@/...' instead of '../../src/...'.");
  }
  if (/from\s+['"]@\/src\//.test(code)) {
    note("imports", fp, "Use '@/...' (already points to 'src'); don't write '@/src/...'.");
  }

  // Collect specs
  const specs = [];
  let m;
  while ((m = importRe.exec(code))) specs.push(m[2]);
  while ((m = exportFromRe.exec(code))) specs.push(m[1]);
  while ((m = requireRe.exec(code))) specs.push(m[1]);

  for (const s of specs) {
    const r = resolveSpec(fp, s);
    if (!r.ok) note("missing", fp, `Module not found '${s}' (tried '${path.relative(ROOT, r.hint)}')`);
  }
}

/** 3) Route default exports (app/* .tsx files) */
const appRouteFiles = files.filter((f) => f.startsWith(APP_DIR) && f.endsWith(".tsx"));
for (const fp of appRouteFiles) {
  const name = path.basename(fp);
  // Some leaf files must export default component
  const code = fs.readFileSync(fp, "utf8");
  // ignore type-only files (rare), but simple heuristic: must have React-ish default export
  if (!/export\s+default\s+/.test(code)) {
    note("routes", fp, "Route file missing 'export default' component.");
  }
}

/** 4) Theme + session presence */
const themePath = path.join(SRC_DIR, "theme.ts");
if (!exists(themePath)) {
  note("theme", "src/theme.ts", "Missing theme file (colors, spacing, etc).");
}

const sessionPath = path.join(SRC_DIR, "auth", "session.ts");
if (!exists(sessionPath)) {
  note("session", "src/auth/session.ts", "Missing auth session stub (export function useSession()).");
}

/** Report */
const sections = [
  ["alias", "Alias / Babel config issues"],
  ["imports", "Import hygiene issues"],
  ["missing", "Unresolved modules"],
  ["routes", "Route files missing default export"],
  ["theme", "Theme missing"],
  ["session", "Auth session missing"],
];

let count = 0;
for (const [key, title] of sections) {
  const list = problems[key];
  if (list.length) {
    console.log(`\n❌ ${title}`);
    for (const p of list) {
      console.log(`  - ${p.file.replace(ROOT + path.sep, "")}: ${p.msg}`);
      count++;
    }
  }
}
if (!count) {
  console.log("✅ Precheck passed — no blocking issues found.");
  process.exit(0);
} else {
  console.log(`\n✖ Precheck failed (${count} issues). Fix & re-run.\n`);
  process.exit(1);
}
