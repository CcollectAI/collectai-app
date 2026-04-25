-- 2026-04-25: per-account marketplace publish defaults.
-- eBay's Sell API requires every listing to reference a categoryId plus
-- 3 policy IDs (fulfillment, payment, return). These are seller-account-
-- scoped, not per-listing, so we cache them once after the user connects
-- their account.
--
-- Same shape can later cover other marketplaces (Discogs returns policy,
-- StockX shipping defaults, etc.) via the marketplace_id discriminator.

CREATE TABLE IF NOT EXISTS public.marketplace_account_defaults (
    user_id                uuid NOT NULL,
    marketplace_id         text NOT NULL,
    ebay_category_id       text,
    fulfillment_policy_id  text,
    payment_policy_id      text,
    return_policy_id       text,
    location_key           text DEFAULT 'default',
    extra                  jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at             timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, marketplace_id)
);

ALTER TABLE public.marketplace_account_defaults ENABLE ROW LEVEL SECURITY;
CREATE POLICY mp_account_defaults_owner_select ON public.marketplace_account_defaults
  FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY mp_account_defaults_owner_upsert ON public.marketplace_account_defaults
  FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY mp_account_defaults_owner_update ON public.marketplace_account_defaults
  FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
