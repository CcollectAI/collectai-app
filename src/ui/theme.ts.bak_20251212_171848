import { featureFlags } from "../_featureFlags";

export type AppColors = {
  background: string;
  card: string;
  text: string;
  muted: string;
  accent: string;
  border: string;
  positive: string;
  negative: string;
  chipBg: string;
};

const getLightColors = (): AppColors => ({
  // Global light theme – Tiffany blue + white + navy
  background: "#FFFFFF",
  card: "#FFFFFF",
  text: "#0C2233",
  muted: "#647589",
  accent: "#19A7AE",   // Tiffany-ish accent
  border: "#D6E4EC",
  positive: "#0BA86C",
  negative: "#D64545",
  chipBg: "#F3F6F8",
});

const getDarkColors = (): AppColors => ({
  // Optional dark mode if we ever flip the feature flag
  background: "#05080C",
  card: "#0C2233",
  text: "#E5F1FF",
  muted: "#9FB2C8",
  accent: "#4CD3E0",
  border: "#1F3547",
  positive: "#30D88B",
  negative: "#FF6B6B",
  chipBg: "#122536",
});

export const useAppColors = (): AppColors => {
  if (featureFlags.darkMode) {
    return getDarkColors();
  }
  return getLightColors();
};
