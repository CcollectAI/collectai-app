-- Distinguishes "currently listed" (asking price) from "sold" market_hits.
-- Needed because Discogs API only exposes lowest_price of current listings
-- (not sold comps). Without this flag, valuation_worker would treat
-- asking prices as transactions and bias predictions 20-40% high.
--
-- Default false so existing rows (all scraped sold comps) keep their
-- current semantics. New `discogs_listing` provider rows set true.

ALTER TABLE public.market_hits
  ADD COLUMN IF NOT EXISTS is_listing boolean DEFAULT false;

-- Partial index — we only query the true subset (listings) to exclude
-- them from training/trends. Full-table index would be wasteful.
CREATE INDEX IF NOT EXISTS idx_market_hits_is_listing
  ON public.market_hits (is_listing)
  WHERE is_listing = true;

NOTIFY pgrst, 'reload schema';
