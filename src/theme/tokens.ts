export const colors = {
  brand: {
    base: "#81D8D0",   // Tiffany blue
    dark: "#5FBFB6",
    darker: "#44A9A1",
    // Deep tiffany — the category-page mockup's price/active-chip color
    // (web/category-redesign-preview.html --tiffDark). Use for text that
    // must hold contrast on white where `base` washes out.
    deep: "#2C7873",
    light: "#AEE6E1",
    lighter: "#E6F7F5",
  },
  bg: "#F7FAF9",
  card: "#FFFFFF",
  text: "#0F172A",
  muted: "#64748B",
  border: "#E2E8F0",
  success: "#10B981",
  warning: "#F59E0B",
  danger:  "#EF4444",
  navy: "#0F172A",
  subtext: "#64748B",
};

/** @deprecated Use `colors` instead */
export const color = colors;

export const radius = { xs: 6, sm: 10, md: 16, lg: 20, xl: 24, "2xl": 28, pill: 48 };
export const spacing = { xxs: 4, xs: 6, sm: 10, md: 14, lg: 18, xl: 24, "2xl": 32 };

/** @deprecated Use `spacing` instead */
export const space = spacing;

/** Font size tokens */
export const text = { xs: 10, sm: 12, md: 14, lg: 16, xl: 20, "2xl": 24 };

/** Font weight tokens */
export const fontWeight = {
  regular: "400" as const,
  medium: "500" as const,
  semibold: "600" as const,
  bold: "700" as const,
  extrabold: "800" as const,
};

/** Icon size tokens */
export const iconSize = { xs: 12, sm: 14, md: 16, lg: 20, xl: 24, "2xl": 32, avatar: 48 };

/** Gap tokens for flex containers */
export const gap = { xxs: 2, xs: 4, sm: 6, md: 8, lg: 10, xl: 12, "2xl": 16 };

/** Font family tokens — Roboto via @expo-google-fonts */
export const fonts = {
  regular: "Roboto_400Regular",
  medium: "Roboto_500Medium",
  bold: "Roboto_700Bold",
  black: "Roboto_900Black",
};

export const shadow = {
  card: {
    shadowColor: "#000",
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  elevated: {
    shadowColor: "#000",
    shadowOpacity: 0.1,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 4,
  },
  floating: {
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 8,
  },
};

/** Status badge semantic colors (light mode) */
export const statusColors = {
  draft: { bg: "#F3F4F6", fg: "#6B7280" },
  active: { bg: "#D1FAE5", fg: "#065F46" },
  sold: { bg: "#DBEAFE", fg: "#1E40AF" },
  expired: { bg: "#FEF3C7", fg: "#92400E" },
  delisted: { bg: "#F3F4F6", fg: "#6B7280" },
  error: { bg: "#FEE2E2", fg: "#991B1B" },
  proposed: { bg: "#FEF3C7", fg: "#92400E" },
  countered: { bg: "#DBEAFE", fg: "#1E40AF" },
  accepted: { bg: "#D1FAE5", fg: "#065F46" },
  declined: { bg: "#FEE2E2", fg: "#991B1B" },
  completed: { bg: "#D1FAE5", fg: "#065F46" },
  cancelled: { bg: "#F3F4F6", fg: "#6B7280" },
};

/** Dark mode status badge colors */
export const statusColorsDark = {
  draft: { bg: "#1F2937", fg: "#9CA3AF" },
  active: { bg: "#064E3B", fg: "#6EE7B7" },
  sold: { bg: "#1E3A5F", fg: "#93C5FD" },
  expired: { bg: "#78350F", fg: "#FDE68A" },
  delisted: { bg: "#1F2937", fg: "#9CA3AF" },
  error: { bg: "#7F1D1D", fg: "#FCA5A5" },
  proposed: { bg: "#78350F", fg: "#FDE68A" },
  countered: { bg: "#1E3A5F", fg: "#93C5FD" },
  accepted: { bg: "#064E3B", fg: "#6EE7B7" },
  declined: { bg: "#7F1D1D", fg: "#FCA5A5" },
  completed: { bg: "#064E3B", fg: "#6EE7B7" },
  cancelled: { bg: "#1F2937", fg: "#9CA3AF" },
};
