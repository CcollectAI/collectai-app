#!/usr/bin/env tsx
// ═══════════════════════════════════════════════════════════════════════════
// CollectAI Video Script Generator — collector-native templates
//
// Usage:
//   npx tsx scripts/generate.ts --template pull-reveal --niche pokemon --lang EN
//   npx tsx scripts/generate.ts --smart --niche funko
//   npx tsx scripts/generate.ts --smart --bootstrap
// ═══════════════════════════════════════════════════════════════════════════

import * as fs from "fs";
import * as path from "path";
import { NICHES, getNiche, type NicheInfo } from "../src/data/niches";
import { getHooksForFormat, renderHook, type Hook } from "../src/data/hooks";
import {
  getRecommendation,
  getTopHooksForNiche,
  bootstrapFromCodebase,
  type LearningStore,
} from "../src/data/learning";

const args = process.argv.slice(2);
function getArg(name: string): string | undefined {
  const idx = args.indexOf(`--${name}`);
  return idx >= 0 ? args[idx + 1] : undefined;
}
const hasFlag = (name: string) => args.includes(`--${name}`);

const templateArg = getArg("template") ?? "pull-reveal";
const nicheArg = getArg("niche");
const langArg = getArg("lang") ?? "EN";
const useSmart = hasFlag("smart");
const doBootstrap = hasFlag("bootstrap");

const TEMPLATE_MAP: Record<string, { compositionId: string; format: string }> = {
  "pull-reveal": { compositionId: "PullReveal", format: "pull_reveal" },
  "whats-it-worth": { compositionId: "WhatsItWorth", format: "whats_it_worth" },
  "hidden-gem": { compositionId: "HiddenGem", format: "hidden_gem" },
  "market-alert": { compositionId: "MarketAlert", format: "market_alert" },
  "collection-flex": { compositionId: "CollectionFlex", format: "collection_flex" },
};

const OUT_DIR = path.resolve(__dirname, "../out/scripts");
fs.mkdirSync(OUT_DIR, { recursive: true });

const STORE_PATH = path.resolve(__dirname, "../out/learning-store.json");

function loadStore(): LearningStore {
  if (fs.existsSync(STORE_PATH)) return JSON.parse(fs.readFileSync(STORE_PATH, "utf-8"));
  return { videos: [], hookScores: {}, templateScores: {}, nicheScores: {} };
}
function saveStore(store: LearningStore): void {
  fs.mkdirSync(path.dirname(STORE_PATH), { recursive: true });
  fs.writeFileSync(STORE_PATH, JSON.stringify(store, null, 2));
}

function pickRandom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

// ─── Generators ──────────────────────────────────────────────────────────

function generatePullReveal(niche: NicheInfo, hook: Hook) {
  const priceEx = pickRandom(niche.priceExamples);
  const grades = ["PSA 10", "PSA 9", "CGC 9.8", "BGS 10", "Mint", "Near Mint"];
  return {
    hookText: renderHook(hook, { niche: niche.label, item: priceEx.item, stat: priceEx.high.toLocaleString() }),
    nicheEmoji: niche.emoji,
    nicheLabel: niche.label,
    nicheColor: niche.color,
    itemName: priceEx.item,
    gradeLabel: pickRandom(grades),
    revealValue: priceEx.high,
    ctaText: "Scan your pulls — know what they're worth",
    language: langArg,
  };
}

function generateWhatsItWorth(niche: NicheInfo, hook: Hook) {
  const priceEx = pickRandom(niche.priceExamples);
  const wrongGuess = Math.round(priceEx.high * (0.05 + Math.random() * 0.15));
  return {
    hookText: renderHook(hook, { niche: niche.label, item: priceEx.item }),
    nicheEmoji: niche.emoji,
    nicheLabel: niche.label,
    nicheColor: niche.color,
    itemName: priceEx.item,
    wrongGuess,
    realValue: priceEx.high,
    marketplaceHits: Math.floor(Math.random() * 20) + 5,
    priceRange: { low: priceEx.low, high: priceEx.high },
    ctaText: "Scan any collectible. Get the real price.",
    language: langArg,
  };
}

function generateHiddenGem(niche: NicheInfo, hook: Hook) {
  const priceEx = pickRandom(niche.priceExamples);
  const paidPrice = Math.round(2 + Math.random() * 18);
  const multiple = Math.round(priceEx.high / paidPrice);
  const locations = ["Garage Sale", "Thrift Store", "Flea Market", "Estate Sale", "Goodwill", "Facebook Marketplace"];
  return {
    hookText: renderHook(hook, { niche: niche.label, item: priceEx.item }),
    nicheEmoji: niche.emoji,
    nicheLabel: niche.label,
    nicheColor: niche.color,
    locationLabel: pickRandom(locations),
    itemName: priceEx.item,
    paidPrice,
    realValue: priceEx.high,
    profitMultiple: `${multiple}x`,
    ctaText: "Never miss an undervalued find",
    language: langArg,
  };
}

function generateMarketAlert(niche: NicheInfo, hook: Hook) {
  const priceEx = pickRandom(niche.priceExamples);
  const alertTypes: Array<"surge" | "crash" | "vaulted" | "drop"> = ["surge", "crash", "vaulted", "drop"];
  const alertType = pickRandom(alertTypes);
  const changePct = alertType === "crash" ? -(Math.floor(Math.random() * 40) + 20)
    : Math.floor(Math.random() * 200) + 50;
  const priceFrom = alertType === "crash" ? priceEx.high : priceEx.low;
  const priceTo = alertType === "crash"
    ? Math.round(priceEx.high * (1 + changePct / 100))
    : Math.round(priceEx.low * (1 + changePct / 100));
  return {
    hookText: renderHook(hook, { niche: niche.label, item: priceEx.item, stat: String(Math.abs(changePct)) }),
    nicheEmoji: niche.emoji,
    nicheLabel: niche.label,
    nicheColor: niche.color,
    alertType,
    itemName: priceEx.item,
    priceFrom,
    priceTo: Math.abs(priceTo),
    changePercent: changePct,
    contextText: pickRandom(niche.facts) + " Set alerts on CollectAI to track every move.",
    ctaText: "Set price alerts — never miss a move",
    language: langArg,
  };
}

function generateCollectionFlex(niche: NicheInfo, hook: Hook) {
  const totalItems = Math.floor(Math.random() * 200) + 20;
  const totalValue = niche.priceExamples.reduce((s, p) => s + p.high, 0) + Math.floor(Math.random() * 50000);
  return {
    hookText: renderHook(hook, { niche: niche.label, stat: `$${totalValue.toLocaleString()}` }),
    nicheEmoji: niche.emoji,
    nicheLabel: niche.label,
    nicheColor: niche.color,
    totalItems,
    portfolioValue: totalValue,
    topItems: niche.priceExamples.slice(0, 3).map((p) => ({
      name: p.item, value: p.high, emoji: niche.emoji,
    })),
    timeCollecting: `${Math.floor(Math.random() * 5) + 1} years`,
    ctaText: "Track & flex your collection",
    language: langArg,
  };
}

const GENERATORS: Record<string, (niche: NicheInfo, hook: Hook) => Record<string, unknown>> = {
  pull_reveal: generatePullReveal,
  whats_it_worth: generateWhatsItWorth,
  hidden_gem: generateHiddenGem,
  market_alert: generateMarketAlert,
  collection_flex: generateCollectionFlex,
};

// ─── Main ────────────────────────────────────────────────────────────────

function main() {
  let store = loadStore();

  if (doBootstrap) {
    console.log("[bootstrap] Scanning CollectAI codebase...");
    store = bootstrapFromCodebase(store);
    saveStore(store);
    console.log(`[bootstrap] Found ${Object.keys(store.nicheScores).length} niches, ${Object.keys(store.hookScores).length} hooks`);
  }

  const template = TEMPLATE_MAP[templateArg];
  if (!template) {
    console.error(`Unknown template: ${templateArg}. Available: ${Object.keys(TEMPLATE_MAP).join(", ")}`);
    process.exit(1);
  }

  let targetNiches: NicheInfo[];
  if (nicheArg === "all") {
    targetNiches = NICHES;
  } else if (nicheArg) {
    const niche = getNiche(nicheArg);
    if (!niche) {
      console.error(`Unknown niche: ${nicheArg}. Available: ${NICHES.map(n => n.id).join(", ")}`);
      process.exit(1);
    }
    targetNiches = [niche];
  } else {
    targetNiches = NICHES.slice(0, 3);
  }

  let generatedCount = 0;
  for (const niche of targetNiches) {
    let hook: Hook;
    if (useSmart) {
      const rec = getRecommendation(store, niche.id, template.format);
      if (rec.action === "retire") {
        console.log(`[smart] Skipping ${template.format} for ${niche.id} — retired`);
        continue;
      }
      const smartHooks = getTopHooksForNiche(store, niche.id, template.format);
      hook = smartHooks[0] ?? getHooksForFormat(template.format)[0];
      console.log(`[smart] ${rec.action}: ${niche.id} / ${template.format} — ${rec.reason}`);
    } else {
      hook = getHooksForFormat(template.format)[0];
    }
    if (!hook) { console.error(`No hooks for format: ${template.format}`); continue; }

    const generator = GENERATORS[template.format];
    const props = generator(niche, hook);
    const filename = `${templateArg}_${niche.id}_${langArg.toLowerCase()}.json`;
    const outPath = path.join(OUT_DIR, filename);
    fs.writeFileSync(outPath, JSON.stringify(props, null, 2));
    console.log(`[generated] ${outPath}`);
    generatedCount++;
  }

  console.log(`\nDone! Generated ${generatedCount} script(s).`);
  console.log(`\nTo render:\n  npx remotion render Root ${template.compositionId} out/video.mp4 --props=out/scripts/<file>.json`);
}

main();
