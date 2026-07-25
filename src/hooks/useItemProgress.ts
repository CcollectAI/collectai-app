/**
 * useItemProgress — manages reading/play progress tracking for manga, comics, games.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { collectorsApi } from '@/api/collectorsApi';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import logger from '@/utils/logger';

const PROGRESS_CATEGORIES: Record<string, { statuses: string[]; label: string; icon: string }> = {
  manga: { statuses: ['unread', 'reading', 'read'], label: 'Reading Progress', icon: 'book-outline' },
  comic_books: { statuses: ['unread', 'reading', 'read'], label: 'Reading Progress', icon: 'book-outline' },
  retro_games: { statuses: ['unplayed', 'playing', 'played', 'completed'], label: 'Play Progress', icon: 'game-controller-outline' },
  board_games: { statuses: ['unplayed', 'playing', 'played', 'completed'], label: 'Play Progress', icon: 'dice-outline' },
};

export function useItemProgress(itemId: string | undefined, isDraft: boolean, categorySlug: string) {
  const { settings } = useSettings();
  const { showToast } = useToast();

  const progressConfig = PROGRESS_CATEGORIES[categorySlug] ?? null;
  const hasProgressTracking = progressConfig !== null;

  const [progressStatus, setProgressStatus] = useState<string | null>(null);
  const [progressPct, setProgressPct] = useState<number | null>(null);
  const [progressNotes, setProgressNotes] = useState('');
  const [progressLoading, setProgressLoading] = useState(false);
  const [progressSaving, setProgressSaving] = useState(false);
  const progressSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!itemId || isDraft || !hasProgressTracking) return;
    setProgressLoading(true);
    collectorsApi.getItemProgress(itemId)
      .then((data) => {
        setProgressStatus(data.progress_status);
        setProgressPct(data.progress_pct);
        setProgressNotes(data.progress_notes || '');
      })
      .catch((err) => logger.warn('[useItemProgress] fetch error:', err))
      .finally(() => setProgressLoading(false));
  }, [itemId, isDraft, hasProgressTracking]);

  const saveProgress = useCallback((status: string | null, pct: number | null, pNotes: string) => {
    if (!itemId || isDraft) return;
    if (progressSaveTimer.current) clearTimeout(progressSaveTimer.current);
    progressSaveTimer.current = setTimeout(async () => {
      setProgressSaving(true);
      try {
        const payload: Record<string, unknown> = {};
        if (status !== undefined) payload.progress_status = status;
        if (pct !== undefined && pct !== null) payload.progress_pct = pct;
        if (pNotes !== undefined) payload.progress_notes = pNotes;
        await collectorsApi.updateItemProgress(itemId, payload as {
          progress_status?: string;
          progress_pct?: number;
          progress_notes?: string;
        });
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      } catch (err) {
        logger.error('[useItemProgress] save error:', err);
        showToast({ message: 'Failed to save progress', type: 'error' });
      } finally {
        setProgressSaving(false);
      }
    }, 600);
  }, [itemId, isDraft, settings.hapticsEnabled]);

  const handleStatusChange = useCallback((newStatus: string) => {
    setProgressStatus(newStatus);
    saveProgress(newStatus, progressPct, progressNotes);
  }, [saveProgress, progressPct, progressNotes]);

  const handlePctChange = useCallback((pct: number) => {
    setProgressPct(pct);
    saveProgress(progressStatus, pct, progressNotes);
  }, [saveProgress, progressStatus, progressNotes]);

  const handleNotesChange = useCallback((text: string) => {
    setProgressNotes(text);
    saveProgress(progressStatus, progressPct, text);
  }, [saveProgress, progressStatus, progressPct]);

  return {
    progressConfig,
    hasProgressTracking,
    progressStatus,
    progressPct,
    progressNotes,
    progressLoading,
    progressSaving,
    handleStatusChange,
    handlePctChange,
    handleNotesChange,
  };
}
