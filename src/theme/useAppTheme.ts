import { useCallback, useMemo } from "react";
import { radius, spacing, shadow } from "./tokens";
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
  tileScale: ["#E6F7F5", "#81D8D0", "#5AA3B8", "#1D4ED8"],
  // Light grey backdrop for QuickScan section
  quickscanBackdrop: "#F1F5F9",
  success: "#10B981",
  warning: "#F59E0B",
  danger: "#EF4444",
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
  warning: "#F59E0B",
  danger: "#EF4444",
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

  return {
    colors,
    radius,
    spacing,
    shadow,
    isDark,
    toggleTheme,
    ready,
  };
}

export type AppTheme = ReturnType<typeof useAppTheme>;
