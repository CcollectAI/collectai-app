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
