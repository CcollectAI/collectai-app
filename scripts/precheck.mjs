import fs from "fs"; import path from "path";
const ROOT = process.cwd();
const SRC_DIRS = [path.join(ROOT,"app"), path.join(ROOT,"src")];
const IGNORE = [/node_modules/, /_shelf/];
const problems = [];
function walk(d){for(const f of fs.readdirSync(d)){const p=path.join(d,f); if(IGNORE.some(r=>r.test(p))) continue; const st=fs.statSync(p); if(st.isDirectory()) walk(p); else if(/\.(tsx?|jsx?)$/.test(f)) scan(p);}}
function scan(fp){const s=fs.readFileSync(fp,"utf8");
  if(/\.\.\/(?:\.\.\/)*src\//.test(s)) problems.push({t:"imports",f:fp,d:"Use '@/...' not '../../src/...'"});
  const specs=[...s.matchAll(/\bfrom\s+["']([^"']+)["']/g)].map(m=>m[1]);
  for(const spec of specs){
    if(!spec.startsWith("@/")) continue;
    const rel = spec.replace(/^@\//,"src/");
    const cand = path.join(ROOT, rel);
    const exts=["",".ts",".tsx",".js",".jsx","/index.ts","/index.tsx","/index.js","/index.jsx"];
    if(!exts.some(e=>fs.existsSync(cand+e))){
      problems.push({t:"missing",f:fp,d:`Module not found '${spec}' → tried '${rel}'`});
    }
  }
}
for(const d of SRC_DIRS) if(fs.existsSync(d)) walk(d);
if(problems.length){
  const by={}; for(const p of problems){(by[p.t]=by[p.t]||[]).push(p);}
  if(by.imports){console.log("❌ Import hygiene issues"); for(const p of by.imports) console.log("  -",p.f+":",p.d);}
  if(by.missing){console.log("\n❌ Unresolved modules"); for(const p of by.missing) console.log("  -",p.f+":",p.d);}
  console.log(`\n✖ Precheck failed (${problems.length} issues). Fix & re-run.`); process.exit(1);
}
console.log("✅ Precheck passed.");
