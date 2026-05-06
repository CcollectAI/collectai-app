// ═══════════════════════════════════════════════════════════════════════════
// Sparrow Collect Video Branding Components
// ═══════════════════════════════════════════════════════════════════════════

import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Colors, Fonts } from "../data/theme";

// ─── App Logo ────────────────────────────────────────────────────────────

export const AppLogo: React.FC<{ size?: number }> = ({ size = 80 }) => (
  <div
    style={{
      width: size,
      height: size,
      borderRadius: size * 0.22,
      background: `linear-gradient(135deg, ${Colors.primary} 0%, ${Colors.primaryDark} 100%)`,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      boxShadow: `0 4px 20px ${Colors.primary}44`,
    }}
  >
    <span
      style={{
        fontSize: size * 0.42,
        fontWeight: 800,
        color: Colors.white,
        fontFamily: Fonts.heading,
        letterSpacing: -1,
      }}
    >
      C
    </span>
  </div>
);

// ─── App Name ────────────────────────────────────────────────────────────

export const AppName: React.FC<{ size?: number }> = ({ size = 48 }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
    <span
      style={{
        fontSize: size,
        fontWeight: 800,
        color: Colors.textPrimary,
        fontFamily: Fonts.heading,
        letterSpacing: -1.5,
      }}
    >
      Collect
    </span>
    <span
      style={{
        fontSize: size,
        fontWeight: 800,
        color: Colors.primary,
        fontFamily: Fonts.heading,
        letterSpacing: -1.5,
      }}
    >
      AI
    </span>
  </div>
);

// ─── CTA Banner ──────────────────────────────────────────────────────────

export const CTABanner: React.FC<{
  text: string;
  subtext?: string;
}> = ({ text, subtext }) => {
  const frame = useCurrentFrame();
  const pulse = Math.sin(frame * 0.12) * 0.03 + 1;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 140,
        left: 40,
        right: 40,
        background: `linear-gradient(135deg, ${Colors.primary} 0%, ${Colors.primaryDark} 100%)`,
        borderRadius: 24,
        padding: "28px 36px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        transform: `scale(${pulse})`,
        boxShadow: `0 8px 32px ${Colors.primary}55`,
      }}
    >
      <span
        style={{
          fontSize: 30,
          fontWeight: 700,
          color: Colors.white,
          fontFamily: Fonts.heading,
          textAlign: "center",
        }}
      >
        {text}
      </span>
      {subtext && (
        <span
          style={{
            fontSize: 20,
            color: "rgba(255,255,255,0.85)",
            fontFamily: Fonts.body,
            textAlign: "center",
          }}
        >
          {subtext}
        </span>
      )}
    </div>
  );
};

// ─── Niche Badge ─────────────────────────────────────────────────────────

export const NicheBadge: React.FC<{
  emoji: string;
  label: string;
  color: string;
}> = ({ emoji, label, color }) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      backgroundColor: `${color}22`,
      border: `2px solid ${color}`,
      borderRadius: 16,
      padding: "10px 20px",
    }}
  >
    <span style={{ fontSize: 28 }}>{emoji}</span>
    <span
      style={{
        fontSize: 22,
        fontWeight: 600,
        color,
        fontFamily: Fonts.heading,
      }}
    >
      {label}
    </span>
  </div>
);

// ─── End Card (logo + CTA + download prompt) ─────────────────────────────

export const EndCard: React.FC<{
  ctaText?: string;
}> = ({ ctaText = "Download Sparrow Collect — Free" }) => {
  const frame = useCurrentFrame();
  const logoScale = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });
  const textOpacity = interpolate(frame, [10, 25], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, ${Colors.background} 0%, ${Colors.primary}15 100%)`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 32,
      }}
    >
      <div style={{ transform: `scale(${logoScale})` }}>
        <AppLogo size={120} />
      </div>
      <div style={{ opacity: textOpacity }}>
        <AppName size={56} />
      </div>
      <span
        style={{
          opacity: textOpacity,
          fontSize: 24,
          color: Colors.textSecondary,
          fontFamily: Fonts.body,
          textAlign: "center",
          maxWidth: 600,
        }}
      >
        Track, value & trade your collectibles with AI
      </span>
      <div style={{ opacity: textOpacity }}>
        <CTABanner text={ctaText} subtext="Available on iOS & Android" />
      </div>
    </AbsoluteFill>
  );
};
