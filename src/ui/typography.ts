/**
 * Typography tokens (single source of truth)
 * Goal: match Items tab feel across the app.
 *
 * NOTE: We intentionally only standardize weight/size/spacing here.
 * Colors come from your existing theme.
 */
export const typography = {
  // Titles
  h1: { fontSize: 20, fontWeight: "900" as const, letterSpacing: -0.2 },
  h2: { fontSize: 16, fontWeight: "900" as const, letterSpacing: -0.2 },
  h3: { fontSize: 13, fontWeight: "900" as const },

  // Body
  body: { fontSize: 12, fontWeight: "600" as const, lineHeight: 17 },
  meta: { fontSize: 11, fontWeight: "700" as const },

  // UI labels/buttons
  label: { fontSize: 12, fontWeight: "900" as const },
};
