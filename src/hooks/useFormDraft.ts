/**
 * useFormDraft — auto-save form state to AsyncStorage with debounce.
 *
 * Usage:
 *   const { hasDraft, clearDraft } = useFormDraft('add-manual', formState, setters);
 *
 * - Debounces saving every 5 seconds when form is dirty.
 * - On mount, loads existing draft and populates fields via setters.
 * - `clearDraft()` removes draft from storage (call after successful save).
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import logger from '@/utils/logger';

const DRAFT_PREFIX = 'form_draft:';
const DEBOUNCE_MS = 5_000;

export interface FormDraftState {
  [key: string]: string | boolean | Record<string, string | boolean>;
}

interface UseFormDraftOptions {
  /** Unique key for this form's draft */
  draftKey: string;
  /** Current form values to persist */
  formState: FormDraftState;
  /** Called once on mount with restored draft (if any). Return true if draft was applied. */
  onRestore: (draft: FormDraftState) => void;
}

export function useFormDraft({ draftKey, formState, onRestore }: UseFormDraftOptions) {
  const [hasDraft, setHasDraft] = useState(false);
  const [draftRestored, setDraftRestored] = useState(false);
  const storageKey = DRAFT_PREFIX + draftKey;
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onRestoreRef = useRef(onRestore);
  onRestoreRef.current = onRestore;
  const restoredRef = useRef(false);

  // Load draft on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(storageKey);
        if (raw && !cancelled && !restoredRef.current) {
          const draft = JSON.parse(raw) as FormDraftState;
          // Check if draft has any non-empty values
          const hasContent = Object.values(draft).some((v) => {
            if (typeof v === 'string') return v.length > 0;
            if (typeof v === 'object' && v !== null) return Object.keys(v).length > 0;
            return Boolean(v);
          });
          if (hasContent) {
            restoredRef.current = true;
            onRestoreRef.current(draft);
            setHasDraft(true);
            setDraftRestored(true);
          }
        }
      } catch (err) {
        logger.warn('[useFormDraft] failed to load draft:', err);
      }
    })();
    return () => { cancelled = true; };
  }, [storageKey]);

  // Debounced save
  useEffect(() => {
    // Skip saving until initial restore attempt completes (or there's nothing to restore)
    if (timerRef.current) clearTimeout(timerRef.current);

    timerRef.current = setTimeout(() => {
      const hasContent = Object.values(formState).some((v) => {
        if (typeof v === 'string') return v.length > 0;
        if (typeof v === 'object' && v !== null) return Object.keys(v).length > 0;
        return Boolean(v);
      });

      if (hasContent) {
        AsyncStorage.setItem(storageKey, JSON.stringify(formState)).catch((err) =>
          logger.warn('[useFormDraft] failed to save draft:', err),
        );
        setHasDraft(true);
      }
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [formState, storageKey]);

  const clearDraft = useCallback(async () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    try {
      await AsyncStorage.removeItem(storageKey);
    } catch (err) {
      logger.warn('[useFormDraft] failed to clear draft:', err);
    }
    setHasDraft(false);
    setDraftRestored(false);
  }, [storageKey]);

  return { hasDraft, draftRestored, clearDraft };
}
