import fs from "fs"; import path from "path";
const ROOT = process.cwd();
const SCAN = ["app","src"];
const EXCLUDE = [path.join("app","_shelf")];
const EXT = [".tsx",".ts",".js",".jsx"];
const problems = [];

const isExcluded = (p)=> EXCLUDE.some(x => p === x || p.startsWith(x + path.sep));
const list = (dir)=> {
  const out=[]; for (const e of fs.readdirSync(dir)) {
    const p=path.join(dir,e); const st=fs.statSync(p);
    if (st.isDirectory()) { if (!isExcluded(p)) out.push(...list(p)); }
    else if (EXT.some(x=>p.endsWith(x))) out.push(p);
  } return out;
};
const files = SCAN.flatMap(d => fs.existsSync(d) ? list(d) : []);

function note(t,f,d){problems.push({t,f,d});}

function checkImports(fp){
  const s=fs.readFileSync(fp,"utf8");
  if (/\.\.\/(?:\.\.\/)*src\//.test(s)) note("imports",fp,"Use '@/...' not '../../src/...'");
  if (/from\s+['"]@\/src\//.test(s)) note("imports",fp,"Use '@/...' not '@/src/...'");

  const specs=[]; const re=/\bimport(?:["'\s]*([\w*{}\n, ]+)from\s*)?["']([^"']+)["'];?/g;
  let m; while ((m=re.exec(s))) specs.push(m[2]);

  const tryResolve=(spec)=>{
    if (spec.startsWith("@/")) {
      const base = path.join(ROOT,"src",spec.slice(2));
      const cand = [base,...EXT.map(e=>base+e),...EXT.map(e=>path.join(base,"index"+e))];
      for (const c of cand){ if (fs.existsSync(c)) return true; }
      note("missing",fp,`Module not found '${spec}' -> tried '${base}'`);
      return false;
    }
    if (spec.startsWith(".") || spec.startsWith("/")) {
      const base = path.resolve(path.dirname(fp),spec);
      const cand = [base,...EXT.map(e=>base+e),...EXT.map(e=>path.join(base,"index"+e))];
      for (const c of cand){ if (fs.existsSync(c)) return true; }
      note("missing",fp,`Module not found '${spec}' -> tried '${base}'`);
      return false;
    }
    return true; // package import → ignore
  };
  specs.forEach(tryResolve);
}

files.forEach(checkImports);

if (problems.length) {
  const by = {};
  for (const p of problems) { (by[p.t]=by[p.t]||[]).push(p); }
  if (by["imports"]) {
    console.log("\n❌ Import hygiene issues");
    for (const p of by["imports"]) console.log(`  - ${p.f}: ${p.d}`);
  }
  if (by["missing"]) {
    console.log("\n❌ Unresolved modules");
    for (const p of by["missing"]) console.log(`  - ${p.f}: ${p.d}`);
  }
  console.log(`\n✖ Precheck failed (${problems.length} issues). Fix & re-run.`);
  process.exit(1);
} else {
  console.log("✅ Precheck passed.");
}
