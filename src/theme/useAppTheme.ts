import { useMemo } from "react";
import { colors, radius, spacing, shadow } from "./tokens";

/**
 * Minimal theme hook.
 * IMPORTANT: do NOT import from "./index" here (circular import risk).
 */
export function useAppTheme() {
  return useMemo(() => {
    return {
      colors,
      radius,
      spacing,
      shadow,
    };
  }, []);
}

export type AppTheme = ReturnType<typeof useAppTheme>;
