import * as React from "react";

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
