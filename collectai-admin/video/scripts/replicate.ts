#!/usr/bin/env tsx
// ═══════════════════════════════════════════════════════════════════════════
// CollectAI Video Replicator — Content Velocity Multiplier
// Takes a winning video script and replicates it across all niches/languages
//
// Usage:
//   npx tsx scripts/replicate.ts --template pull-reveal --niche pokemon
//   npx tsx scripts/replicate.ts --template all --niche all
//   npx tsx scripts/replicate.ts --source out/scripts/pull-reveal_pokemon_en.json --niches mtg,funko,lego
//
// 1 idea × 12 niches × 5 templates = 60 script files
// ═══════════════════════════════════════════════════════════════════════════

import * as fs from "fs";
import * as path from "path";
import { execSync } from "child_process";
import { NICHES } from "../src/data/niches";

// ─── CLI Args ────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
function getArg(name: string): string | undefined {
  const idx = args.indexOf(`--${name}`);
  return idx >= 0 ? args[idx + 1] : undefined;
}

const templateArg = getArg("template") ?? "all";
const nicheArg = getArg("niche") ?? "all";
const langArg = getArg("lang") ?? "EN";

const ALL_TEMPLATES = ["pull-reveal", "whats-it-worth", "hidden-gem", "market-alert", "collection-flex"];

// ─── Main ────────────────────────────────────────────────────────────────

function main() {
  const templates = templateArg === "all" ? ALL_TEMPLATES : [templateArg];
  const nicheIds = nicheArg === "all"
    ? NICHES.map((n) => n.id)
    : nicheArg.split(",").map((s) => s.trim());

  const total = templates.length * nicheIds.length;
  console.log(`\n[replicate] Generating ${total} scripts (${templates.length} templates x ${nicheIds.length} niches)\n`);

  let count = 0;

  for (const template of templates) {
    for (const niche of nicheIds) {
      try {
        const cmd = `npx tsx scripts/generate.ts --template ${template} --niche ${niche} --lang ${langArg}`;
        execSync(cmd, { cwd: path.resolve(__dirname, ".."), stdio: "pipe" });
        count++;
        const pct = Math.round((count / total) * 100);
        process.stdout.write(`\r  [${pct}%] ${count}/${total} — ${template} / ${niche}`);
      } catch (err) {
        console.error(`\n  [error] ${template} / ${niche}: ${(err as Error).message}`);
      }
    }
  }

  console.log(`\n\n[replicate] Done! Generated ${count}/${total} scripts.`);
  console.log(`\nScripts saved to: out/scripts/`);
  console.log(`\nEstimated render cost: ~EUR ${(count * 0.03).toFixed(2)} (${count} x EUR 0.03)`);

  // Summary table
  console.log("\n--- Render commands ---");
  const COMP_MAP: Record<string, string> = {
    "pull-reveal": "PullReveal",
    "whats-it-worth": "WhatsItWorth",
    "hidden-gem": "HiddenGem",
    "market-alert": "MarketAlert",
    "collection-flex": "CollectionFlex",
  };
  for (const template of templates) {
    const compId = COMP_MAP[template];
    const exNiche = nicheIds[0];
    console.log(`  npx remotion render Root ${compId} out/${template}_${exNiche}.mp4 --props=out/scripts/${template}_${exNiche}_${langArg.toLowerCase()}.json`);
  }
}

main();
