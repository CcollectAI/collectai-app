-- 2026-04-22: events.ticket_price_cents was missing — POST /events INSERT
-- referenced it (event_core.py:285,307), every paid-ticket event creation
-- 500'd. Surfaced by autonomous E2E batch 4.
-- Stored in cents (Stripe convention) so we never deal with float currency.
ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS ticket_price_cents integer NOT NULL DEFAULT 0;
