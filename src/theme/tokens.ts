export const colors = {
  brand: {
    base: "#81D8D0",   // Tiffany blue
    dark: "#5FBFB6",
    darker: "#44A9A1",
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

export const radius = { sm: 10, md: 16, lg: 20, xl: 24, "2xl": 28, pill: 48 };
export const spacing = { xs: 6, sm: 10, md: 14, lg: 18, xl: 24, "2xl": 32 };

/** @deprecated Use `spacing` instead */
export const space = spacing;

/** Font size tokens */
export const text = { sm: 12, md: 14, lg: 16, xl: 20, "2xl": 24 };

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
};
