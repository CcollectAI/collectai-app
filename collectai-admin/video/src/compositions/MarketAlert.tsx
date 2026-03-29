// ═══════════════════════════════════════════════════════════════════════════
// Template 4: "Market Alert" — Price Crash / Surge / Vault
// FOMO + urgency. 5-7% engagement on drop announcements (3x avg).
// Structure: Alert siren + item (2s) → Price chart animation (4s) → Context (4s)
//            → "Set alerts" (3s) → CTA (2s) → End (2s)
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
import { NicheBadge, CTABanner, EndCard } from "../components/Branding";

export interface MarketAlertProps {
  hookText: string;
  nicheEmoji: string;
  nicheLabel: string;
  nicheColor: string;
  alertType: "surge" | "crash" | "vaulted" | "drop";
  itemName: string;
  priceFrom: number;
  priceTo: number;
  changePercent: number;       // positive = up, negative = down
  contextText: string;
  audioUrl?: string;
  ctaText: string;
  language: string;
}

export const MarketAlert: React.FC<MarketAlertProps> = ({
  hookText,
  nicheEmoji,
  nicheLabel,
  nicheColor,
  alertType,
  itemName,
  priceFrom,
  priceTo,
  changePercent,
  contextText,
  audioUrl,
  ctaText,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const isPositive = changePercent > 0;
  const alertColor = alertType === "crash" ? Colors.error
    : alertType === "surge" ? Colors.success
    : alertType === "vaulted" ? Colors.warning
    : Colors.primary;

  const alertLabel = alertType === "crash" ? "PRICE CRASH"
    : alertType === "surge" ? "PRICE SURGE"
    : alertType === "vaulted" ? "VAULTED"
    : "NEW DROP";

  // Hook (0-2s) with flash
  const hookOpacity = interpolate(frame, [0, 6, fps * 2 - 6, fps * 2], [0, 1, 1, 0], {
    extrapolateRight: "clamp",
  });
  const alertPulse = frame < fps * 6 ? Math.sin(frame * 0.4) * 0.15 + 1 : 1;

  // Alert badge (1.5-6s)
  const alertBadgeScale = spring({ frame: frame - fps * 1.5, fps, config: { damping: 8 } });

  // Price chart animation (2-6s) — simple line going up or down
  const chartPoints = 12;
  const chartProgress = interpolate(frame, [fps * 2, fps * 6], [0, chartPoints], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  // Context text (6-10s)
  const contextOpacity = interpolate(frame, [fps * 6, fps * 7], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const contextY = interpolate(frame, [fps * 6, fps * 7], [30, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  // Price labels (6-10s)
  const priceCounter = Math.floor(
    interpolate(frame, [fps * 6.5, fps * 8], [priceFrom, priceTo], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    }),
  );

  // CTA (10-12s)
  const ctaOpacity = interpolate(frame, [fps * 10, fps * 11], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  // Generate chart path
  const generateChartPath = () => {
    const width = 800;
    const height = 300;
    const points: string[] = [];
    const visible = Math.min(Math.floor(chartProgress), chartPoints);

    for (let i = 0; i <= visible; i++) {
      const x = (i / chartPoints) * width;
      const progress = i / chartPoints;
      let y: number;
      if (isPositive) {
        // Upward trend with some jitter
        y = height - progress * height * 0.7 - Math.sin(i * 1.5) * 20;
      } else {
        // Downward trend
        y = progress * height * 0.7 + Math.sin(i * 1.5) * 20 + height * 0.15;
      }
      points.push(`${x},${y}`);
    }
    return points.join(" ");
  };

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
            fontSize: 46, fontWeight: 800, color: Colors.textPrimary,
            fontFamily: Fonts.heading, textAlign: "center", lineHeight: 1.2,
          }}>
            {hookText}
          </span>
        </AbsoluteFill>
      </Sequence>

      {/* Alert type badge + niche */}
      <Sequence from={fps * 1.5} durationInFrames={fps * 5}>
        <div style={{
          position: "absolute", top: 140, left: 0, right: 0,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 12,
          transform: `scale(${alertBadgeScale * alertPulse})`,
        }}>
          <div style={{
            backgroundColor: alertColor,
            borderRadius: 14, padding: "10px 28px",
            boxShadow: `0 4px 20px ${alertColor}55`,
          }}>
            <span style={{
              fontSize: 24, fontWeight: 900, color: Colors.white,
              fontFamily: Fonts.heading, letterSpacing: 4,
            }}>
              {alertLabel}
            </span>
          </div>
          <NicheBadge emoji={nicheEmoji} label={nicheLabel} color={nicheColor} />
          <span style={{
            fontSize: 24, fontWeight: 600, color: Colors.textPrimary,
            fontFamily: Fonts.heading, textAlign: "center",
          }}>
            {itemName}
          </span>
        </div>
      </Sequence>

      {/* Price chart */}
      <Sequence from={fps * 2} durationInFrames={fps * 8}>
        <div style={{
          position: "absolute", top: 420, left: 60, right: 60,
          height: 320,
        }}>
          <svg viewBox="0 0 800 300" style={{ width: "100%", height: "100%" }}>
            {/* Grid lines */}
            {[0, 1, 2, 3].map((i) => (
              <line
                key={i}
                x1={0} y1={i * 100} x2={800} y2={i * 100}
                stroke={Colors.textSecondary} strokeOpacity={0.1} strokeWidth={1}
              />
            ))}
            {/* Chart line */}
            <polyline
              points={generateChartPath()}
              fill="none"
              stroke={alertColor}
              strokeWidth={4}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {/* Glow effect */}
            <polyline
              points={generateChartPath()}
              fill="none"
              stroke={alertColor}
              strokeWidth={12}
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity={0.2}
            />
          </svg>
        </div>
      </Sequence>

      {/* Price labels + change % */}
      <Sequence from={fps * 6} durationInFrames={fps * 6}>
        <div style={{
          position: "absolute", bottom: 380, left: 0, right: 0,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 12,
        }}>
          <span style={{
            fontSize: 60, fontWeight: 900, color: Colors.textPrimary,
            fontFamily: Fonts.mono, letterSpacing: -2,
          }}>
            ${priceCounter.toLocaleString()}
          </span>
          <div style={{
            backgroundColor: `${alertColor}20`,
            borderRadius: 10, padding: "6px 16px",
          }}>
            <span style={{
              fontSize: 28, fontWeight: 800, color: alertColor,
              fontFamily: Fonts.mono,
            }}>
              {isPositive ? "\u2191" : "\u2193"} {Math.abs(changePercent)}%
            </span>
          </div>
        </div>
      </Sequence>

      {/* Context */}
      <Sequence from={fps * 6} durationInFrames={fps * 4}>
        <div style={{
          position: "absolute", bottom: 260, left: 60, right: 60,
          opacity: contextOpacity, transform: `translateY(${contextY}px)`,
        }}>
          <div style={{
            backgroundColor: `${alertColor}10`,
            border: `1px solid ${alertColor}30`,
            borderRadius: 16, padding: "14px 20px",
          }}>
            <span style={{
              fontSize: 20, fontWeight: 500, color: Colors.textPrimary,
              fontFamily: Fonts.body, lineHeight: 1.4, textAlign: "center",
            }}>
              {contextText}
            </span>
          </div>
        </div>
      </Sequence>

      {/* CTA */}
      <Sequence from={fps * 10} durationInFrames={fps * 4}>
        <div style={{ opacity: ctaOpacity }}>
          <CTABanner text={ctaText} subtext="Get price alerts on any collectible" />
        </div>
      </Sequence>

      {/* End card */}
      <Sequence from={fps * 14} durationInFrames={fps * 2}>
        <EndCard />
      </Sequence>
    </AbsoluteFill>
  );
};
