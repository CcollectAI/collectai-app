// ═══════════════════════════════════════════════════════════════════════════
// Template 3: "Hidden Gem / Thrift Find" — The Hunt
// Aspiration + FOMO. Every collector dreams of finding a grail for cheap.
// Structure: Location context (2s) → Spot item + zoom (3s) → QuickScan animation (3s)
//            → Price reveal "paid $5, worth $800" (4s) → CTA (2s) → End (2s)
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
import { AppLogo, CTABanner, EndCard, NicheBadge } from "../components/Branding";

export interface HiddenGemProps {
  hookText: string;
  nicheEmoji: string;
  nicheLabel: string;
  nicheColor: string;
  locationLabel: string;      // e.g. "Garage Sale", "Thrift Store", "Flea Market"
  itemName: string;
  paidPrice: number;
  realValue: number;
  profitMultiple: string;     // e.g. "160x"
  imageUrl?: string;
  audioUrl?: string;
  ctaText: string;
  language: string;
}

export const HiddenGem: React.FC<HiddenGemProps> = ({
  hookText,
  nicheEmoji,
  nicheLabel,
  nicheColor,
  locationLabel,
  itemName,
  paidPrice,
  realValue,
  profitMultiple,
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

  // Location label slide in (2-3s)
  const locX = interpolate(frame, [fps * 2, fps * 2.5], [-300, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  // Item zoom in (3-5s)
  const itemScale = interpolate(frame, [fps * 3, fps * 5], [0.4, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const itemOpacity = interpolate(frame, [fps * 3, fps * 3.5], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  // QuickScan animation (5-8s)
  const scanLineY = interpolate(frame, [fps * 5, fps * 7.5], [0, 600], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const scanProgress = interpolate(frame, [fps * 5, fps * 7.5], [0, 100], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const scanComplete = frame >= fps * 7.5;

  // Price reveal (8-12s)
  const paidScale = spring({ frame: frame - fps * 8, fps, config: { damping: 12 } });
  const realScale = spring({ frame: frame - fps * 9, fps, config: { damping: 10 } });
  const multipleScale = spring({ frame: frame - fps * 10, fps, config: { damping: 8, stiffness: 120 } });

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

      {/* Location label */}
      <Sequence from={fps * 2} durationInFrames={fps * 6}>
        <div style={{
          position: "absolute", top: 140, left: 0, right: 0,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 12,
          transform: `translateX(${locX}px)`,
        }}>
          <div style={{
            backgroundColor: `${Colors.warning}20`,
            border: `2px solid ${Colors.warning}`,
            borderRadius: 12, padding: "8px 20px",
          }}>
            <span style={{
              fontSize: 20, fontWeight: 700, color: Colors.warning,
              fontFamily: Fonts.heading, textTransform: "uppercase", letterSpacing: 2,
            }}>
              {locationLabel}
            </span>
          </div>
          <NicheBadge emoji={nicheEmoji} label={nicheLabel} color={nicheColor} />
        </div>
      </Sequence>

      {/* Item zoom */}
      <Sequence from={fps * 3} durationInFrames={fps * 9}>
        <AbsoluteFill style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          transform: `scale(${itemScale})`, opacity: itemOpacity,
        }}>
          <div style={{ position: "relative" }}>
            {imageUrl ? (
              <Img src={imageUrl} style={{
                maxWidth: 450, maxHeight: 450, borderRadius: 20,
                boxShadow: `0 8px 30px rgba(0,0,0,0.15)`,
              }} />
            ) : (
              <div style={{
                width: 400, height: 400, borderRadius: 20,
                background: `linear-gradient(135deg, ${nicheColor}20, ${nicheColor}08)`,
                border: `2px solid ${nicheColor}30`,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <span style={{ fontSize: 100 }}>{nicheEmoji}</span>
              </div>
            )}

            {/* Scan line overlay (5-7.5s) */}
            {frame >= fps * 5 && frame < fps * 8 && (
              <>
                <div style={{
                  position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
                  border: `3px solid ${Colors.primary}`,
                  borderRadius: 20,
                  boxShadow: `0 0 20px ${Colors.primary}44`,
                }} />
                <div style={{
                  position: "absolute", left: 0, right: 0,
                  top: scanLineY, height: 3,
                  background: `linear-gradient(90deg, transparent, ${Colors.primary}, transparent)`,
                }} />
                {/* Scan % label */}
                <div style={{
                  position: "absolute", bottom: -40, left: 0, right: 0,
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                }}>
                  <AppLogo size={28} />
                  <span style={{
                    fontSize: 16, fontWeight: 600, color: Colors.primary,
                    fontFamily: Fonts.mono,
                  }}>
                    {scanComplete ? "Identified!" : `Scanning... ${Math.floor(scanProgress)}%`}
                  </span>
                </div>
              </>
            )}
          </div>
        </AbsoluteFill>
      </Sequence>

      {/* Price reveal */}
      <Sequence from={fps * 8} durationInFrames={fps * 6}>
        <div style={{
          position: "absolute", bottom: 340, left: 0, right: 0,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 16,
        }}>
          {/* Paid */}
          <div style={{
            display: "flex", alignItems: "center", gap: 12,
            transform: `scale(${paidScale})`,
          }}>
            <span style={{
              fontSize: 18, color: Colors.textSecondary, fontFamily: Fonts.body,
            }}>
              Paid:
            </span>
            <span style={{
              fontSize: 36, fontWeight: 800, color: Colors.textSecondary,
              fontFamily: Fonts.mono,
            }}>
              ${paidPrice.toLocaleString()}
            </span>
          </div>
          {/* Item name */}
          <span style={{
            fontSize: 22, fontWeight: 600, color: Colors.textPrimary,
            fontFamily: Fonts.heading, textAlign: "center",
          }}>
            {itemName}
          </span>
          {/* Real value */}
          <div style={{
            display: "flex", alignItems: "center", gap: 12,
            transform: `scale(${realScale})`,
          }}>
            <span style={{
              fontSize: 18, color: Colors.success, fontFamily: Fonts.body,
            }}>
              Worth:
            </span>
            <span style={{
              fontSize: 56, fontWeight: 900, color: Colors.primary,
              fontFamily: Fonts.mono, letterSpacing: -2,
            }}>
              ${realValue.toLocaleString()}
            </span>
          </div>
          {/* Multiple badge */}
          <div style={{
            transform: `scale(${multipleScale})`,
            background: `linear-gradient(135deg, ${Colors.success}20, ${Colors.success}10)`,
            border: `2px solid ${Colors.success}`,
            borderRadius: 12, padding: "8px 20px",
          }}>
            <span style={{
              fontSize: 28, fontWeight: 900, color: Colors.success,
              fontFamily: Fonts.heading,
            }}>
              {profitMultiple} return
            </span>
          </div>
        </div>
      </Sequence>

      {/* CTA */}
      <Sequence from={fps * 12} durationInFrames={fps * 4}>
        <div style={{ opacity: ctaOpacity }}>
          <CTABanner text={ctaText} subtext="Spot undervalued collectibles instantly" />
        </div>
      </Sequence>

      {/* End card */}
      <Sequence from={fps * 16} durationInFrames={fps * 2}>
        <EndCard />
      </Sequence>
    </AbsoluteFill>
  );
};
