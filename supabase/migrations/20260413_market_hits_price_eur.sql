-- Add price_eur column for EUR-normalized pricing
-- Original price + currency preserved for localized deal display
-- price_eur used by training pipeline and valuation worker
ALTER TABLE public.market_hits ADD COLUMN IF NOT EXISTS price_eur numeric;

-- Backfill existing data
UPDATE market_hits SET price_eur = price WHERE currency = 'EUR' AND price_eur IS NULL;
UPDATE market_hits SET price_eur = price * 0.92 WHERE currency = 'USD' AND price_eur IS NULL;
UPDATE market_hits SET price_eur = price * 0.85 WHERE currency = 'GBP' AND price_eur IS NULL;
UPDATE market_hits SET price_eur = price * 0.006 WHERE currency = 'JPY' AND price_eur IS NULL;
UPDATE market_hits SET price_eur = price WHERE price_eur IS NULL AND price IS NOT NULL;

NOTIFY pgrst, 'reload schema';
