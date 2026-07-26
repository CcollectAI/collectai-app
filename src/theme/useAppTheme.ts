import { useCallback, useMemo } from "react";
import { radius, spacing, shadow, gap, iconSize, fontWeight, text, statusColors, statusColorsDark } from "./tokens";
import { useSettings } from "../lib/settings";

/**
 * Light and dark color palettes.
 */
const LIGHT_COLORS = {
  background: "#FFFFFF",
  text: "#0F172A",
  muted: "#64748B",
  border: "#E2E8F0",
  card: "#F8FAFC",
  accent: "#40C9C6", // Tiffany
  brand: {
    base: "#81D8D0",
    dark: "#5FBFB6",
    darker: "#44A9A1",
    light: "#AEE6E1",
    lighter: "#E6F7F5",
  },
  // Tiffany → cobalt scale for category tiles
  tileScale: ["#B5E8E2", "#81D8D0", "#5AA3B8", "#3E8FA8"],
  // Light grey backdrop for QuickScan section
  quickscanBackdrop: "#F1F5F9",
  success: "#059669",
  warning: "#F59E0B",
  danger: "#EF4444",
  error: "#EF4444",
  info: "#3B82F6",
  // Semantic colors for components
  skeleton: "#E2E8F0",
  skeletonCard: "#FFFFFF",
  overlay: "rgba(0,0,0,0.5)",
  offlineBanner: "#F59E0B",
  offlineBannerText: "#FFFFFF",
  // Chart colors
  chartLine: "#40C9C6",
  chartFill: "#E0F2F1",
  chartDot: "#14B8A6",
  // Toast backgrounds (intentionally dark for readability)
  toastSuccess: "#1B5E20",
  toastError: "#B71C1C",
  toastWarning: "#E65100",
  toastInfo: "#0D47A1",
  // Semantic surface colors for badges/pills
  successBg: "#DCFCE7",
  warningBg: "#FEF3C7",
  dangerBg: "#FEE2E2",
  infoBg: "#DBEAFE",
  // Button text on accent/colored backgrounds
  accentText: "#FFFFFF",
  // Tier badge colors (gamification)
  tier: {
    bronze: "#CD7F32",
    silver: "#C0C0C0",
    gold: "#FFD700",
    platinum: "#E5E4E2",
  },
  // Aliases for legacy components
  primary: "#40C9C6",
};

const DARK_COLORS = {
  background: "#020617",
  text: "#F9FAFB",
  muted: "#9CA3AF",
  border: "#1F2937",
  card: "#0F172A",
  accent: "#40C9C6", // Tiffany stays same
  brand: {
    base: "#81D8D0",
    dark: "#5FBFB6",
    darker: "#44A9A1",
    light: "#AEE6E1",
    lighter: "#1E3A3A",
  },
  // Tiffany → cobalt scale for category tiles (darker variants for dark mode)
  tileScale: ["#1E3A3A", "#2D5A5A", "#3A6B7A", "#1E40AF"],
  // Dark backdrop for QuickScan section
  quickscanBackdrop: "#0F172A",
  success: "#10B981",
  warning: "#FBBF24",
  danger: "#F87171",
  error: "#F87171",
  info: "#60A5FA",
  // Semantic colors for components
  skeleton: "#1F2937",
  skeletonCard: "#0F172A",
  overlay: "rgba(0,0,0,0.7)",
  offlineBanner: "#92400E",
  offlineBannerText: "#FEF3C7",
  // Chart colors
  chartLine: "#40C9C6",
  chartFill: "#1E3A3A",
  chartDot: "#14B8A6",
  // Toast backgrounds
  toastSuccess: "#1B5E20",
  toastError: "#B71C1C",
  toastWarning: "#E65100",
  toastInfo: "#0D47A1",
  // Semantic surface colors for badges/pills
  successBg: "#064E3B",
  warningBg: "#78350F",
  dangerBg: "#7F1D1D",
  infoBg: "#1E3A5F",
  // Button text on accent/colored backgrounds
  accentText: "#FFFFFF",
  // Tier badge colors (gamification)
  tier: {
    bronze: "#CD7F32",
    silver: "#C0C0C0",
    gold: "#FFD700",
    platinum: "#E5E4E2",
  },
  // Aliases for legacy components
  primary: "#40C9C6",
};

/**
 * Theme hook with dark mode support.
 * Uses global settings for persistence.
 */
export function useAppTheme() {
  const { settings, updateSettings, ready } = useSettings();
  const isDark = settings.isDark;

  const colors = isDark ? DARK_COLORS : LIGHT_COLORS;

  const toggleTheme = useCallback(() => {
    updateSettings({ isDark: !isDark });
  }, [isDark, updateSettings]);

  const status = isDark ? statusColorsDark : statusColors;

  return {
    colors,
    radius,
    spacing,
    shadow,
    gap,
    iconSize,
    fontWeight,
    text,
    status,
    isDark,
    toggleTheme,
    ready,
  };
}

export type AppTheme = ReturnType<typeof useAppTheme>;

/**
 * QuickScan runs against a full-bleed black camera viewfinder, so its result
 * and analyzing screens must stay black too — otherwise the flow flashes from
 * black to white mid-scan. This forces the dark palette regardless of the
 * user's light/dark setting, with the surfaces pushed to true black so they
 * match the viewfinder (`#000`) rather than the app's dark navy.
 */
const QUICKSCAN_COLORS = {
  ...DARK_COLORS,
  background: "#000000",
  card: "#101114",
  border: "#24262B",
  skeletonCard: "#101114",
};

export function useQuickScanTheme() {
  const base = useAppTheme();
  return useMemo(
    () => ({
      ...base,
      colors: QUICKSCAN_COLORS,
      status: statusColorsDark,
      isDark: true,
    }),
    [base],
  );
}
