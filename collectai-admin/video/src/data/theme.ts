// ═══════════════════════════════════════════════════════════════════════════
// CollectAI Video Theme — Tiffany Blue brand identity
// ═══════════════════════════════════════════════════════════════════════════

export const Colors = {
  // Brand
  primary: "#81D8D0",          // Tiffany Blue
  primaryDark: "#5FBFB6",      // Hover / accents
  secondary: "#1E3A8A",        // Navy — charts, headers

  // Neutrals
  white: "#FFFFFF",
  black: "#0B0C0F",
  background: "#F8FFFE",       // Slight tiffany tint
  surface: "#FFFFFF",
  textPrimary: "#0B0C0F",
  textSecondary: "#6B7280",

  // Status
  success: "#10B981",
  error: "#EF4444",
  warning: "#F59E0B",

  // Category pod accent palette (matches admin.config.ts pods)
  pokemon: "#FFD700",
  mtg: "#8B5CF6",
  funko: "#EC4899",
  warhammer: "#EF4444",
  sneakers: "#3B82F6",
  watches: "#14B8A6",
  vinyl: "#F97316",
  general: "#81D8D0",
};

export const VIDEO = {
  width: 1080,
  height: 1920,
  fps: 30,
  durations: {
    short: 300,       // 10 seconds
    medium: 480,      // 16 seconds
    standard: 630,    // 21 seconds — TikTok sweet spot
    long: 900,        // 30 seconds — tutorials
  },
};

export const Fonts = {
  heading: "Roboto, Inter, sans-serif",
  body: "Roboto, Inter, sans-serif",
  mono: "Roboto Mono, monospace",
};
