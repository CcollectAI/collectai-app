
// --- Compatibility shims (non-destructive) ---
(() => {
  const anyTheme: any = theme;

  // Colors
  const c = anyTheme.colors ?? {};
  anyTheme.colors = {
    ...c,
    // common aliases
    bg: c.bg ?? c.background ?? "#ffffff",
    textMuted: c.textMuted ?? c.subtext ?? "#6b7280",
    border: c.border ?? "#e5e7eb",
    muted: c.muted ?? "#f3f4f6",
    success: c.success ?? "#22c55e",
    danger: c.danger ?? "#ef4444",
    // brand as nested object with .base
    brand: (typeof c.brand === "object" && c.brand)
      ? c.brand
      : { base: c.brand ?? "#0ea5e9" },
    // sometimes used in buttons
    accentStrong: c.accentStrong ?? ((typeof c.brand === "object" && c.brand?.base) ? c.brand.base : (c.brand ?? "#0ea5e9")),
  };

  // Spacing tokens
  const s = anyTheme.space ?? {};
  anyTheme.space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, ...s };
  anyTheme.spacing = anyTheme.spacing ?? anyTheme.space; // alias

  // Typography sizes
  const t = anyTheme.text ?? {};
  anyTheme.text = { sm: 12, md: 14, lg: 16, xl: 20, "2xl": 24, ...t };
})();
