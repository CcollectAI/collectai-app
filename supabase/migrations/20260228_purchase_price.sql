-- Add purchase_price and purchase_date to items for DCA cost basis tracking

BEGIN;

ALTER TABLE public.items
  ADD COLUMN IF NOT EXISTS purchase_price numeric(12,2),
  ADD COLUMN IF NOT EXISTS purchase_currency text DEFAULT 'EUR',
  ADD COLUMN IF NOT EXISTS purchased_at timestamptz;

COMMENT ON COLUMN public.items.purchase_price IS 'User-entered acquisition cost for DCA tracking';
COMMENT ON COLUMN public.items.purchase_currency IS 'Currency of the purchase price';
COMMENT ON COLUMN public.items.purchased_at IS 'Date the item was acquired';

COMMIT;
