// ═══════════════════════════════════════════════════════════════════════════
// Template 1: "Pull Reveal" — Pack Opening / Grading Reveal
// The #1 format in collectibles TikTok. Suspense + dopamine.
// Structure: Dramatic countdown (2s) → Item zoom with blur (3s) → REVEAL flash + price (4s)
//            → "Scan it" CTA (4s) → End card (2s)
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

export interface PullRevealProps {
  hookText: string;
  nicheEmoji: string;
  nicheLabel: string;
  nicheColor: string;
  itemName: string;
  gradeLabel: string;         // e.g. "PSA 10" or "CGC 9.8" or "Mint"
  revealValue: number;        // Dollar value revealed
  /** Optional catalog image URL */
  imageUrl?: string;
  /** Optional audio S3 URL */
  audioUrl?: string;
  ctaText: string;
  language: string;
}

export const PullReveal: React.FC<PullRevealProps> = ({
  hookText,
  nicheEmoji,
  nicheLabel,
  nicheColor,
  itemName,
  gradeLabel,
  revealValue,
  imageUrl,
  audioUrl,
  ctaText,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Phase 1: Hook text (0-2s)
  const hookOpacity = interpolate(frame, [0, 8, fps * 2 - 8, fps * 2], [0, 1, 1, 0], {
    extrapolateRight: "clamp",
  });

  // Phase 2: Item zoom with blur → sharp (2-5s)
  const blurAmount = interpolate(frame, [fps * 2, fps * 4.5], [20, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const itemScale = interpolate(frame, [fps * 2, fps * 5], [0.6, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Phase 3: REVEAL flash (5s) + price counter (5-9s)
  const flashOpacity = interpolate(frame, [fps * 5, fps * 5 + 4, fps * 5 + 8], [0, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const priceCounterValue = Math.floor(
    interpolate(frame, [fps * 5.5, fps * 8], [0, revealValue], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );
  const gradeScale = spring({
    frame: frame - fps * 5.5,
    fps,
    config: { damping: 8, stiffness: 150 },
  });

  // Phase 4: CTA (9-13s)
  const ctaOpacity = interpolate(frame, [fps * 9, fps * 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: Colors.black }}>
      {audioUrl && (
        <Audio src={audioUrl} volume={0.6} />
      )}

      {/* Hook */}
      <Sequence from={0} durationInFrames={fps * 2.5}>
        <AbsoluteFill
          style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: 60, opacity: hookOpacity,
          }}
        >
          <span style={{
            fontSize: 50, fontWeight: 800, color: Colors.white,
            fontFamily: Fonts.heading, textAlign: "center", lineHeight: 1.2,
            textShadow: "0 4px 20px rgba(0,0,0,0.6)",
          }}>
            {hookText}
          </span>
        </AbsoluteFill>
      </Sequence>

      {/* Niche badge */}
      <Sequence from={fps * 2} durationInFrames={fps * 7}>
        <div style={{
          position: "absolute", top: 140, left: 0, right: 0,
          display: "flex", justifyContent: "center",
        }}>
          <NicheBadge emoji={nicheEmoji} label={nicheLabel} color={nicheColor} />
        </div>
      </Sequence>

      {/* Item with blur → reveal */}
      <Sequence from={fps * 2} durationInFrames={fps * 7}>
        <AbsoluteFill style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          filter: `blur(${blurAmount}px)`,
          transform: `scale(${itemScale})`,
        }}>
          {imageUrl ? (
            <Img src={imageUrl} style={{
              maxWidth: 600, maxHeight: 700, borderRadius: 24,
              boxShadow: `0 0 60px ${nicheColor}66`,
            }} />
          ) : (
            <div style={{
              width: 500, height: 600, borderRadius: 24,
              background: `linear-gradient(135deg, ${nicheColor}40, ${nicheColor}20)`,
              border: `3px solid ${nicheColor}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              boxShadow: `0 0 60px ${nicheColor}44`,
            }}>
              <span style={{ fontSize: 120 }}>{nicheEmoji}</span>
            </div>
          )}
        </AbsoluteFill>
      </Sequence>

      {/* REVEAL flash */}
      <Sequence from={fps * 5} durationInFrames={12}>
        <AbsoluteFill style={{
          backgroundColor: Colors.white,
          opacity: flashOpacity,
        }} />
      </Sequence>

      {/* Grade badge */}
      <Sequence from={fps * 5.5} durationInFrames={fps * 8}>
        <div style={{
          position: "absolute", top: 260, right: 80,
          transform: `scale(${gradeScale}) rotate(-8deg)`,
        }}>
          <div style={{
            background: `linear-gradient(135deg, ${Colors.primary}, ${Colors.primaryDark})`,
            borderRadius: 16, padding: "12px 24px",
            boxShadow: `0 4px 20px ${Colors.primary}66`,
          }}>
            <span style={{
              fontSize: 32, fontWeight: 900, color: Colors.white,
              fontFamily: Fonts.heading, letterSpacing: 2,
            }}>
              {gradeLabel}
            </span>
          </div>
        </div>
      </Sequence>

      {/* Item name + price counter */}
      <Sequence from={fps * 5.5} durationInFrames={fps * 8}>
        <div style={{
          position: "absolute", bottom: 340, left: 0, right: 0,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 12,
        }}>
          <span style={{
            fontSize: 28, fontWeight: 600, color: Colors.white,
            fontFamily: Fonts.heading, textAlign: "center",
            textShadow: "0 2px 10px rgba(0,0,0,0.8)",
          }}>
            {itemName}
          </span>
          <span style={{
            fontSize: 80, fontWeight: 900, color: Colors.primary,
            fontFamily: Fonts.mono, letterSpacing: -2,
            textShadow: `0 0 40px ${Colors.primary}88`,
          }}>
            ${priceCounterValue.toLocaleString()}
          </span>
        </div>
      </Sequence>

      {/* CTA */}
      <Sequence from={fps * 9} durationInFrames={fps * 4}>
        <div style={{ opacity: ctaOpacity }}>
          <CTABanner text={ctaText} subtext="Know what your pulls are really worth" />
        </div>
      </Sequence>

      {/* End card */}
      <Sequence from={fps * 13} durationInFrames={fps * 2}>
        <EndCard />
      </Sequence>
    </AbsoluteFill>
  );
};
