// ═══════════════════════════════════════════════════════════════════════════
// Template 5: "Collection Flex" — Showcase / Portfolio
// Social proof + aspiration. Core collector TikTok content.
// Structure: Grid of items animate in (3s) → Total counter (3s) → Top 3 spotlight (5s)
//            → Portfolio value reveal (3s) → CTA (2s) → End (2s)
// ═══════════════════════════════════════════════════════════════════════════

import React from "react";
import {
  AbsoluteFill,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Audio,
} from "remotion";
import { Colors, Fonts } from "../data/theme";
import { AppLogo, AppName, CTABanner, EndCard, NicheBadge } from "../components/Branding";

export interface CollectionFlexProps {
  hookText: string;
  nicheEmoji: string;
  nicheLabel: string;
  nicheColor: string;
  totalItems: number;
  portfolioValue: number;
  topItems: { name: string; value: number; emoji?: string }[];
  timeCollecting: string;     // e.g. "3 years"
  audioUrl?: string;
  ctaText: string;
  language: string;
}

export const CollectionFlex: React.FC<CollectionFlexProps> = ({
  hookText,
  nicheEmoji,
  nicheLabel,
  nicheColor,
  totalItems,
  portfolioValue,
  topItems,
  timeCollecting,
  audioUrl,
  ctaText,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Hook (0-2s)
  const hookOpacity = interpolate(frame, [0, 8, fps * 2 - 8, fps * 2], [0, 1, 1, 0], {
    extrapolateRight: "clamp",
  });

  // Grid items animate in (2-5s) — 12 cells staggered
  const gridCells = 12;

  // Total counter (5-8s)
  const totalCounter = Math.floor(
    interpolate(frame, [fps * 5, fps * 7.5], [0, totalItems], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    }),
  );

  // Top 3 spotlight (8-13s) — staggered reveals
  const topItemScales = topItems.slice(0, 3).map((_, i) =>
    spring({ frame: frame - fps * (8 + i * 1.2), fps, config: { damping: 10, stiffness: 150 } }),
  );

  // Portfolio value reveal (11-14s)
  const portfolioCounter = Math.floor(
    interpolate(frame, [fps * 11, fps * 13.5], [0, portfolioValue], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    }),
  );
  const portfolioScale = spring({ frame: frame - fps * 11, fps, config: { damping: 12 } });

  // CTA (14-16s)
  const ctaOpacity = interpolate(frame, [fps * 14, fps * 15], [0, 1], {
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

      {/* Niche badge + time */}
      <Sequence from={fps * 2} durationInFrames={fps * 6}>
        <div style={{
          position: "absolute", top: 140, left: 0, right: 0,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 10,
        }}>
          <NicheBadge emoji={nicheEmoji} label={nicheLabel} color={nicheColor} />
          <span style={{
            fontSize: 18, color: Colors.textSecondary, fontFamily: Fonts.body,
          }}>
            {timeCollecting} of collecting
          </span>
        </div>
      </Sequence>

      {/* Animated grid (2-5s) */}
      <Sequence from={fps * 2} durationInFrames={fps * 3.5}>
        <div style={{
          position: "absolute", top: 300, left: 60, right: 60,
          display: "flex", flexWrap: "wrap", gap: 12, justifyContent: "center",
        }}>
          {Array.from({ length: gridCells }).map((_, i) => {
            const cellScale = spring({
              frame: frame - fps * 2 - i * 3,
              fps,
              config: { damping: 12, stiffness: 200 },
            });
            return (
              <div key={i} style={{
                width: 140, height: 140, borderRadius: 16,
                background: `linear-gradient(135deg, ${nicheColor}${(20 + i * 5).toString(16)}, ${nicheColor}${(10 + i * 3).toString(16)})`,
                border: `2px solid ${nicheColor}30`,
                transform: `scale(${cellScale})`,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <span style={{ fontSize: 40, opacity: 0.6 }}>{nicheEmoji}</span>
              </div>
            );
          })}
        </div>
      </Sequence>

      {/* Total items counter (5-8s) */}
      <Sequence from={fps * 5} durationInFrames={fps * 3.5}>
        <AbsoluteFill style={{
          display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", gap: 8,
        }}>
          <span style={{
            fontSize: 96, fontWeight: 900, color: nicheColor,
            fontFamily: Fonts.mono, letterSpacing: -3,
          }}>
            {totalCounter.toLocaleString()}
          </span>
          <span style={{
            fontSize: 24, fontWeight: 500, color: Colors.textSecondary,
            fontFamily: Fonts.body, textTransform: "uppercase", letterSpacing: 4,
          }}>
            items tracked
          </span>
        </AbsoluteFill>
      </Sequence>

      {/* Top 3 most valuable (8-13s) */}
      <Sequence from={fps * 8} durationInFrames={fps * 6}>
        <div style={{
          position: "absolute", top: 250, left: 40, right: 40,
          display: "flex", flexDirection: "column", gap: 16,
        }}>
          <span style={{
            fontSize: 18, fontWeight: 600, color: Colors.textSecondary,
            fontFamily: Fonts.body, textTransform: "uppercase", letterSpacing: 3,
            textAlign: "center",
          }}>
            Most Valuable
          </span>
          {topItems.slice(0, 3).map((item, i) => (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 16,
              backgroundColor: Colors.surface,
              borderRadius: 16, padding: "16px 20px",
              border: i === 0 ? `2px solid ${Colors.primary}` : `1px solid ${Colors.textSecondary}20`,
              boxShadow: i === 0 ? `0 4px 16px ${Colors.primary}20` : "none",
              transform: `scale(${topItemScales[i]})`,
            }}>
              <span style={{
                fontSize: 28, fontWeight: 900, color: i === 0 ? Colors.primary : Colors.textSecondary,
                fontFamily: Fonts.heading, width: 36,
              }}>
                #{i + 1}
              </span>
              <span style={{ fontSize: 28 }}>{item.emoji ?? nicheEmoji}</span>
              <div style={{ flex: 1 }}>
                <span style={{
                  fontSize: 18, fontWeight: 600, color: Colors.textPrimary,
                  fontFamily: Fonts.heading,
                }}>
                  {item.name}
                </span>
              </div>
              <span style={{
                fontSize: 24, fontWeight: 800,
                color: i === 0 ? Colors.primary : Colors.textPrimary,
                fontFamily: Fonts.mono,
              }}>
                ${item.value.toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      </Sequence>

      {/* Portfolio total (11-14s) */}
      <Sequence from={fps * 11} durationInFrames={fps * 5}>
        <div style={{
          position: "absolute", bottom: 340, left: 0, right: 0,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
          transform: `scale(${portfolioScale})`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <AppLogo size={36} />
            <span style={{
              fontSize: 16, color: Colors.textSecondary, fontFamily: Fonts.body,
              textTransform: "uppercase", letterSpacing: 2,
            }}>
              Total Portfolio Value
            </span>
          </div>
          <span style={{
            fontSize: 72, fontWeight: 900, color: Colors.primary,
            fontFamily: Fonts.mono, letterSpacing: -3,
          }}>
            ${portfolioCounter.toLocaleString()}
          </span>
        </div>
      </Sequence>

      {/* CTA */}
      <Sequence from={fps * 14} durationInFrames={fps * 4}>
        <div style={{ opacity: ctaOpacity }}>
          <CTABanner text={ctaText} subtext="Track and flex your collection with AI" />
        </div>
      </Sequence>

      {/* End card */}
      <Sequence from={fps * 18} durationInFrames={fps * 2}>
        <EndCard />
      </Sequence>
    </AbsoluteFill>
  );
};
