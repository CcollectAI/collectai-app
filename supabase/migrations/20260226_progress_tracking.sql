-- Migration: Reading/Play Progress Tracking
-- Adds progress tracking columns to items table for manga, comic_books, retro_games, board_games

ALTER TABLE public.items
  ADD COLUMN IF NOT EXISTS progress_status TEXT CHECK (progress_status IN ('unread', 'reading', 'read', 'unplayed', 'playing', 'played', 'completed')) DEFAULT NULL;

ALTER TABLE public.items
  ADD COLUMN IF NOT EXISTS progress_pct INT CHECK (progress_pct >= 0 AND progress_pct <= 100) DEFAULT NULL;

ALTER TABLE public.items
  ADD COLUMN IF NOT EXISTS progress_notes TEXT DEFAULT NULL;

-- Index for efficient queries on progress status (only for items that have a status set)
CREATE INDEX IF NOT EXISTS idx_items_progress ON public.items(user_id, progress_status) WHERE progress_status IS NOT NULL;
