import { useState, useCallback } from 'react';

/**
 * Lightweight modal visibility hook.
 * Returns [visible, open, close, toggle] — drop-in replacement for
 * `const [visible, setVisible] = useState(false)`.
 */
export function useModal(initial = false) {
  const [visible, setVisible] = useState(initial);
  const open = useCallback(() => setVisible(true), []);
  const close = useCallback(() => setVisible(false), []);
  const toggle = useCallback(() => setVisible((v) => !v), []);
  return [visible, open, close, toggle] as const;
}
