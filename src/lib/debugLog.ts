// On-device debug log buffer for the tab-bar regression (saga in
// memory/project_tab_bar_bug_saga.md). User can't get Console.app or Xcode
// to see the iPhone, so we mirror the [TAB] console.logs into a small
// in-memory ring buffer that DebugOverlay renders on screen.
//
// Remove this file + DebugOverlay + DEBUG_TAB_BAR flag once the tab bug
// is verified fixed.

type Listener = (lines: string[]) => void;

const MAX_LINES = 30;
const buffer: string[] = [];
const listeners = new Set<Listener>();

export function pushDebugLog(line: string): void {
  const ts = new Date().toISOString().slice(11, 19);
  buffer.push(`${ts} ${line}`);
  while (buffer.length > MAX_LINES) buffer.shift();
  const snapshot = [...buffer];
  listeners.forEach((l) => l(snapshot));
}

export function subscribeDebugLog(l: Listener): () => void {
  listeners.add(l);
  l([...buffer]);
  return () => {
    listeners.delete(l);
  };
}

export function clearDebugLog(): void {
  buffer.length = 0;
  listeners.forEach((l) => l([]));
}
