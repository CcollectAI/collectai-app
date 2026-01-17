import * as React from "react";

/**
 * Simple global color mode store (light | dark) using useSyncExternalStore
 * so it works anywhere without a Provider.
 */

export type ColorMode = "light" | "dark";

let currentMode: ColorMode = "light";
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): ColorMode {
  return currentMode;
}

function setColorMode(mode: ColorMode) {
  if (currentMode === mode) return;
  currentMode = mode;
  listeners.forEach((listener) => listener());
}

function toggleColorMode() {
// DISABLED: was auto-toggling color mode and could cause infinite re-render loops
// setColorMode(currentMode === "light" ? "dark" : "light");
}

export function useColorMode() {
  const mode = React.useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  return {
    mode,
    setMode: setColorMode,
    toggle: toggleColorMode,
  };
}

/**
 * App theme tokens for light & dark modes.
 */

export type AppTheme = {
  background: string;
  card: string;
  border: string;
  text: string;
  mutedText: string;
  accent: string;
  accentText: string;
  inputBackground: string;
  inputBorder: string;
};

const lightTheme: AppTheme = {
  background: "#e6f7fb",      // light Tiffany-ish blue
  card: "#ffffff",
  border: "#d0e7f3",
  text: "#102a43",
  mutedText: "rgba(15, 23, 42, 0.7)",
  accent: "#1fb6ff",
  accentText: "#ffffff",
  inputBackground: "#f8fbfd",
  inputBorder: "#c4d7e3",
};

const darkTheme: AppTheme = {
  background: "#06111a",      // soft navy, not harsh black
  card: "#0f2433",
  border: "#17354a",
  text: "#e3f3ff",
  mutedText: "rgba(226, 232, 240, 0.7)",
  accent: "#38bdf8",
  accentText: "#0b1120",
  inputBackground: "#0b1b28",
  inputBorder: "#1e3a4c",
};

export function useColorTheme(): AppTheme {
  const { mode } = useColorMode();
  return mode === "dark" ? darkTheme : lightTheme;
}
