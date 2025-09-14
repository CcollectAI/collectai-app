import fs from "fs";
import path from "path";

const ROOT = process.cwd();
const IGNORE_DIRS = [path.join(ROOT, "app/_shelf"), path.join(ROOT, "components")];
const SCAN_DIRS = [path.join(ROOT, "app"), path.join(ROOT, "src")];

const problems = [];
const add = (t,f,d)=>problems.push({t,f,d});
const isIgnored = (fp) => IGNORE_DIRS.some(d => fp.startsWith(d));

const read = (fp)=> fs.readFileSync(fp,"utf8");
const exists = (p)=> {
  const exts = ["", ".tsx", ".ts", ".js", ".jsx", "/index.tsx", "/index.ts", "/index.js", "/index.jsx"];
  for (const e of exts) { try { if (fs.statSync(p+e).isFile()) return true; } catch {} }
  return false;
};

const files = [];
(function walk(dir){
  for (const name of fs.readdirSync(dir)) {
    const fp = path.join(dir, name);
    if (isIgnored(fp)) continue;
    const st = fs.statSync(fp);
    if (st.isDirectory()) walk(fp);
    else if (/\.(tsx?|jsx?)$/.test(name)) files.push(fp);
  }
})(ROOT);

for (const fp of files) {
  const s = read(fp);

  // Import hygiene: '../../src/...'
  if (/\.\.\/(?:\.\.\/)*src\//.test(s)) add("imports", fp, "Use '@/...' not '../../src/...'");
  if (/@\/src\//.test(s)) add("imports", fp, "Use '@/...' not '@/src/...'");

  // Unresolved '@/...' modules (skip assets)
  const specs = [];
  const re = /\bimport(?:["'\s]*([\w*{}\n, ]+)from\s*)?["']([^"']+)["'];?/g;
  let m; while ((m = re.exec(s))) specs.push(m[2]);
  for (const spec of specs) {
    if (!spec.startsWith("@/")) continue;
    if (spec.includes("/assets/")) continue;
    const local = path.join(ROOT, "src", spec.slice(2));
    if (!exists(local)) add("missing", fp, `Module not found '${spec}' (tried '${local}')`);
  }
}

const group = problems.reduce((acc,p)=>(acc[p.t]=(acc[p.t]||[]).concat(p),acc),{});
const order = ["imports","missing"];
if (problems.length) {
  for (const k of order) if (group[k]) {
    const title = k==="imports" ? "Import hygiene issues" : "Unresolved modules";
    console.log(`\n❌ ${title}`);
    for (const p of group[k]) console.log(`  - ${p.f}: ${p.d}`);
  }
  console.log(`\n✖ Precheck failed (${problems.length} issues). Fix & re-run.`);
  process.exit(1);
} else {
  console.log("✅ Precheck passed.");
}
