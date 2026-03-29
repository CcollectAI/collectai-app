// ═══════════════════════════════════════════════════════════════════════════
// Template 2: "What's It Worth?" — Price Reveal / Valuation
// Curiosity gap format. Ties directly to CollectAI QuickScan.
// Structure: Show item blurred price (2s) → Wrong guess (3s) → Real price + marketplace data (4s)
//            → "37 marketplaces" proof (3s) → CTA (2s) → End (2s)
// ═══════════════════════════════════════════════════════════════════════════

import React from "react";
import {
  AbsoluteFill,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Img,
  Audio,
} from "remotion";
import { Colors, Fonts } from "../data/theme";
import { NicheBadge, CTABanner, EndCard } from "../components/Branding";

export interface WhatsItWorthProps {
  hookText: string;
  nicheEmoji: string;
  nicheLabel: string;
  nicheColor: string;
  itemName: string;
  wrongGuess: number;         // What "most people think"
  realValue: number;          // Actual market value
  marketplaceHits: number;    // e.g. "Found on 14 of 37 marketplaces"
  priceRange: { low: number; high: number };
  imageUrl?: string;
  audioUrl?: string;
  ctaText: string;
  language: string;
}

export const WhatsItWorth: React.FC<WhatsItWorthProps> = ({
  hookText,
  nicheEmoji,
  nicheLabel,
  nicheColor,
  itemName,
  wrongGuess,
  realValue,
  marketplaceHits,
  priceRange,
  imageUrl,
  audioUrl,
  ctaText,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Hook (0-2s)
  const hookOpacity = interpolate(frame, [0, 8, fps * 2 - 8, fps * 2], [0, 1, 1, 0], {
    extrapolateRight: "clamp",
  });

  // Item display (2-5s) with question mark price
  const questionPulse = Math.sin(frame * 0.2) * 0.08 + 1;

  // Wrong guess strikethrough (5-7s)
  const wrongScale = spring({ frame: frame - fps * 5, fps, config: { damping: 12 } });
  const strikeWidth = interpolate(frame, [fps * 6, fps * 6.5], [0, 100], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  // Real price reveal (7-11s)
  const realPriceCounter = Math.floor(
    interpolate(frame, [fps * 7, fps * 9.5], [0, realValue], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    }),
  );
  const realPriceScale = spring({ frame: frame - fps * 7, fps, config: { damping: 10 } });

  // Marketplace proof bar (9-12s)
  const barWidth = interpolate(frame, [fps * 9, fps * 11], [0, (marketplaceHits / 37) * 100], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  // Range bar (10-12s)
  const rangeOpacity = interpolate(frame, [fps * 10, fps * 10.5], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  // CTA (12-14s)
  const ctaOpacity = interpolate(frame, [fps * 12, fps * 13], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: Colors.background }}>
      {audioUrl && <Audio src={audioUrl} volume={0.5} />}

      {/* Hook */}
      <Sequence from={0} durationInFrames={fps * 2.5}>
        <AbsoluteFill style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          padding: 60, opacity: hookOpacity,
        }}>
          <span style={{
            fontSize: 48, fontWeight: 800, color: Colors.textPrimary,
            fontFamily: Fonts.heading, textAlign: "center", lineHeight: 1.2,
          }}>
            {hookText}
          </span>
        </AbsoluteFill>
      </Sequence>

      {/* Item + niche badge */}
      <Sequence from={fps * 2} durationInFrames={fps * 10}>
        <div style={{
          position: "absolute", top: 140, left: 0, right: 0,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 16,
        }}>
          <NicheBadge emoji={nicheEmoji} label={nicheLabel} color={nicheColor} />
          {imageUrl ? (
            <Img src={imageUrl} style={{
              maxWidth: 400, maxHeight: 400, borderRadius: 20,
              boxShadow: `0 8px 30px ${nicheColor}30`,
            }} />
          ) : (
            <div style={{
              width: 350, height: 350, borderRadius: 20,
              background: `linear-gradient(135deg, ${nicheColor}25, ${nicheColor}10)`,
              border: `2px solid ${nicheColor}40`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <span style={{ fontSize: 100 }}>{nicheEmoji}</span>
            </div>
          )}
          <span style={{
            fontSize: 26, fontWeight: 600, color: Colors.textPrimary,
            fontFamily: Fonts.heading, textAlign: "center", maxWidth: 600,
          }}>
            {itemName}
          </span>
        </div>
      </Sequence>

      {/* Question mark price (2-5s) */}
      <Sequence from={fps * 2.5} durationInFrames={fps * 2.5}>
        <div style={{
          position: "absolute", bottom: 450, left: 0, right: 0,
          display: "flex", justifyContent: "center",
          transform: `scale(${questionPulse})`,
        }}>
          <span style={{
            fontSize: 72, fontWeight: 900, color: Colors.textSecondary,
            fontFamily: Fonts.mono, opacity: 0.5,
          }}>
            $???
          </span>
        </div>
      </Sequence>

      {/* Wrong guess with strikethrough (5-7s) */}
      <Sequence from={fps * 5} durationInFrames={fps * 2.5}>
        <div style={{
          position: "absolute", bottom: 440, left: 0, right: 0,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
          transform: `scale(${wrongScale})`,
        }}>
          <span style={{
            fontSize: 18, fontWeight: 500, color: Colors.textSecondary,
            fontFamily: Fonts.body, textTransform: "uppercase", letterSpacing: 3,
          }}>
            Most people think
          </span>
          <div style={{ position: "relative", display: "inline-block" }}>
            <span style={{
              fontSize: 56, fontWeight: 900, color: Colors.error,
              fontFamily: Fonts.mono, opacity: 0.7,
            }}>
              ${wrongGuess.toLocaleString()}
            </span>
            <div style={{
              position: "absolute", top: "50%", left: 0,
              width: `${strikeWidth}%`, height: 4,
              backgroundColor: Colors.error, borderRadius: 2,
              transform: "translateY(-50%) rotate(-5deg)",
            }} />
          </div>
        </div>
      </Sequence>

      {/* Real price reveal (7-12s) */}
      <Sequence from={fps * 7} durationInFrames={fps * 7}>
        <div style={{
          position: "absolute", bottom: 360, left: 0, right: 0,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 16,
          transform: `scale(${realPriceScale})`,
        }}>
          <span style={{
            fontSize: 18, fontWeight: 500, color: Colors.success,
            fontFamily: Fonts.body, textTransform: "uppercase", letterSpacing: 3,
          }}>
            Real market value
          </span>
          <span style={{
            fontSize: 72, fontWeight: 900, color: Colors.primary,
            fontFamily: Fonts.mono, letterSpacing: -2,
          }}>
            ${realPriceCounter.toLocaleString()}
          </span>
        </div>
      </Sequence>

      {/* Marketplace proof (9-12s) */}
      <Sequence from={fps * 9} durationInFrames={fps * 5}>
        <div style={{
          position: "absolute", bottom: 240, left: 60, right: 60,
          display: "flex", flexDirection: "column", gap: 8,
        }}>
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <span style={{ fontSize: 16, color: Colors.textSecondary, fontFamily: Fonts.body }}>
              Found on {marketplaceHits} of 37 marketplaces
            </span>
          </div>
          <div style={{
            height: 12, borderRadius: 6, backgroundColor: `${Colors.primary}20`,
            overflow: "hidden",
          }}>
            <div style={{
              height: "100%", width: `${barWidth}%`, borderRadius: 6,
              background: `linear-gradient(90deg, ${Colors.primary}, ${Colors.primaryDark})`,
            }} />
          </div>
          {/* Price range */}
          <div style={{
            opacity: rangeOpacity,
            display: "flex", justifyContent: "space-between",
            fontSize: 14, fontFamily: Fonts.mono, color: Colors.textSecondary,
          }}>
            <span>Low: ${priceRange.low.toLocaleString()}</span>
            <span>High: ${priceRange.high.toLocaleString()}</span>
          </div>
        </div>
      </Sequence>

      {/* CTA */}
      <Sequence from={fps * 12} durationInFrames={fps * 4}>
        <div style={{ opacity: ctaOpacity }}>
          <CTABanner text={ctaText} subtext="Scan any collectible. Get the real price." />
        </div>
      </Sequence>

      {/* End card */}
      <Sequence from={fps * 16} durationInFrames={fps * 2}>
        <EndCard />
      </Sequence>
    </AbsoluteFill>
  );
};
