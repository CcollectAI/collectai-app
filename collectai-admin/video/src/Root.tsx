// ═══════════════════════════════════════════════════════════════════════════
// CollectAI Video — Remotion Root (registers all 5 collector-native compositions)
// ═══════════════════════════════════════════════════════════════════════════

import React from "react";
import { Composition } from "remotion";
import { VIDEO } from "./data/theme";

import { PullReveal } from "./compositions/PullReveal";
import { WhatsItWorth } from "./compositions/WhatsItWorth";
import { HiddenGem } from "./compositions/HiddenGem";
import { MarketAlert } from "./compositions/MarketAlert";
import { CollectionFlex } from "./compositions/CollectionFlex";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="PullReveal"
      component={PullReveal}
      durationInFrames={450}
      fps={VIDEO.fps}
      width={VIDEO.width}
      height={VIDEO.height}
      defaultProps={{
        hookText: "This $3 pack had a $2,000 card inside",
        nicheEmoji: "\u{1F4A0}",
        nicheLabel: "Pokemon TCG",
        nicheColor: "#FFD700",
        itemName: "Illustrator Pikachu #CoroCoro",
        gradeLabel: "PSA 10",
        revealValue: 5275000,
        ctaText: "Scan your pulls — know what they're worth",
        language: "EN",
      }}
    />

    <Composition
      id="WhatsItWorth"
      component={WhatsItWorth}
      durationInFrames={540}
      fps={VIDEO.fps}
      width={VIDEO.width}
      height={VIDEO.height}
      defaultProps={{
        hookText: "How much is this ACTUALLY worth?",
        nicheEmoji: "\u{1F47E}",
        nicheLabel: "Funko Pop",
        nicheColor: "#EC4899",
        itemName: "Holographic Darth Maul #09",
        wrongGuess: 200,
        realValue: 8500,
        marketplaceHits: 14,
        priceRange: { low: 4000, high: 13300 },
        ctaText: "Scan any collectible. Get the real price.",
        language: "EN",
      }}
    />

    <Composition
      id="HiddenGem"
      component={HiddenGem}
      durationInFrames={540}
      fps={VIDEO.fps}
      width={VIDEO.width}
      height={VIDEO.height}
      defaultProps={{
        hookText: "I found this at a garage sale for $5...",
        nicheEmoji: "\u{1F9F1}",
        nicheLabel: "LEGO",
        nicheColor: "#81D8D0",
        locationLabel: "Garage Sale",
        itemName: "LEGO Cafe Corner 10182 (sealed)",
        paidPrice: 5,
        realValue: 4200,
        profitMultiple: "840x",
        ctaText: "Never miss an undervalued find",
        language: "EN",
      }}
    />

    <Composition
      id="MarketAlert"
      component={MarketAlert}
      durationInFrames={480}
      fps={VIDEO.fps}
      width={VIDEO.width}
      height={VIDEO.height}
      defaultProps={{
        hookText: "If you own this, check your portfolio NOW",
        nicheEmoji: "\u{1F0CF}",
        nicheLabel: "Yu-Gi-Oh!",
        nicheColor: "#81D8D0",
        alertType: "vaulted",
        itemName: "Ghost Rare 1st Ed Stardust Dragon",
        priceFrom: 800,
        priceTo: 2400,
        changePercent: 200,
        contextText: "OOP Ghost Rares have historically tripled within 60 days of discontinuation. Set alerts now.",
        ctaText: "Set price alerts — never miss a move",
        language: "EN",
      }}
    />

    <Composition
      id="CollectionFlex"
      component={CollectionFlex}
      durationInFrames={600}
      fps={VIDEO.fps}
      width={VIDEO.width}
      height={VIDEO.height}
      defaultProps={{
        hookText: "My $142K collection in 15 seconds",
        nicheEmoji: "\u{231A}",
        nicheLabel: "Watches",
        nicheColor: "#14B8A6",
        totalItems: 28,
        portfolioValue: 142000,
        topItems: [
          { name: "Rolex Daytona 116500LN", value: 38000 },
          { name: "Omega Speedmaster Pro", value: 7200 },
          { name: "Tudor Black Bay 58", value: 3800 },
        ],
        timeCollecting: "3 years",
        ctaText: "Track & flex your collection",
        language: "EN",
      }}
    />
  </>
);
