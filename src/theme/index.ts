import { colors, color, radius, spacing, space, shadow, text } from "./tokens";

export * from "./colors";
export * from "./tokens";

/** Non-hook theme object */
export const theme = { colors, color, radius, spacing, space, shadow, text };

export { useAppTheme } from "./useAppTheme";

/** Back-compat alias */
export { useAppTheme as useTheme } from "./useAppTheme";
