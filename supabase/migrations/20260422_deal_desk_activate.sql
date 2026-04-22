-- 2026-04-22: Activate the Deal Desk feature.
-- Schema additions + 4 RPCs + summary view. Mirrors eBay/Mercari patterns:
-- * 48h response window per action; counter resets the clock
-- * Hard cap at 5 counter rounds per offer (StockX-style)
-- * Separate `expired` status (auto-set by offer_expiry_worker, distinct from cancelled)
-- * SECURITY DEFINER RPCs because the router uses raw asyncpg (no RLS context).
--   Caller MUST do an IDOR pre-flight ownership check (learnings.md §13).

-- ---------------------------------------------------------------------------
-- 1. Schema additions on offers
-- ---------------------------------------------------------------------------
ALTER TABLE public.offers
  ADD COLUMN IF NOT EXISTS seller_id     uuid,
  ADD COLUMN IF NOT EXISTS message       text,
  ADD COLUMN IF NOT EXISTS counter_count integer     NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS expires_at    timestamptz,
  ADD COLUMN IF NOT EXISTS updated_at    timestamptz NOT NULL DEFAULT now();

-- Backfill seller_id from listings (one-time, idempotent).
UPDATE public.offers o
   SET seller_id = l.seller_id
  FROM public.listings l
 WHERE o.listing_id = l.id
   AND o.seller_id IS NULL;

-- Now safe to require seller_id going forward.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'offers' AND column_name = 'seller_id' AND is_nullable = 'YES'
  ) THEN
    ALTER TABLE public.offers ALTER COLUMN seller_id SET NOT NULL;
  END IF;
END $$;

-- State-machine: enforce status whitelist (8 values per offer_events check).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'offers_status_chk'
  ) THEN
    ALTER TABLE public.offers
      ADD CONSTRAINT offers_status_chk
      CHECK (status IN ('pending','countered','accepted','declined','cancelled','expired','shipped','completed'));
  END IF;
END $$;

-- Bump updated_at on every UPDATE.
CREATE OR REPLACE FUNCTION public.offers_set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'offers_set_updated_at_trg') THEN
    CREATE TRIGGER offers_set_updated_at_trg
      BEFORE UPDATE ON public.offers
      FOR EACH ROW EXECUTE FUNCTION public.offers_set_updated_at();
  END IF;
END $$;

-- Useful indexes for the GET /deals/active list.
CREATE INDEX IF NOT EXISTS idx_offers_seller_status_updated
  ON public.offers (seller_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_offers_buyer_status_updated
  ON public.offers (buyer_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_offers_expires_at
  ON public.offers (expires_at)
  WHERE expires_at IS NOT NULL AND status IN ('pending','countered');

-- ---------------------------------------------------------------------------
-- 2. v_offer_summary_v1 — one row per offer with listing context
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS public.v_offer_summary_v1;
CREATE VIEW public.v_offer_summary_v1 AS
SELECT
  o.id,
  o.id AS offer_id,    -- router queries v_offer_summary_v1.offer_id directly
  o.listing_id,
  o.seller_id,
  o.buyer_id,
  o.amount,
  o.status,
  o.message,
  o.counter_count,
  o.expires_at,
  o.created_at,
  o.updated_at,
  l.title       AS listing_title,
  l.image_url   AS listing_image_url,
  l.price       AS listing_price,
  l.currency    AS listing_currency
FROM public.offers o
JOIN public.listings l ON l.id = o.listing_id;

GRANT SELECT ON public.v_offer_summary_v1 TO authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 3. RPCs (4 — propose / counter / respond / cancel)
-- ---------------------------------------------------------------------------

-- Constants — duplicated below in workers/offer_expiry_worker.py.
--   RESPONSE_WINDOW = 48h
--   MAX_COUNTERS    = 5

-- 3a. rpc_propose_offer_v1(item_id, amount, message, buyer_id) → jsonb
-- Router passes item_id (user-facing concept); RPC resolves to the active
-- listing for that item and validates seller ≠ buyer.
DROP FUNCTION IF EXISTS public.rpc_propose_offer_v1(uuid, numeric, text, uuid);
CREATE FUNCTION public.rpc_propose_offer_v1(
  p_item_id  uuid,
  p_amount   numeric,
  p_message  text,
  p_buyer_id uuid
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_listing_id uuid;
  v_seller_id  uuid;
  v_offer      public.offers%ROWTYPE;
BEGIN
  IF p_amount IS NULL OR p_amount <= 0 THEN
    RAISE EXCEPTION 'amount must be positive';
  END IF;

  -- Resolve the active listing for this item. If the owner has multiple
  -- listings for the same item, take the most recent.
  SELECT id, seller_id INTO v_listing_id, v_seller_id
  FROM public.listings
  WHERE item_id = p_item_id AND status = 'active'
  ORDER BY created_at DESC
  LIMIT 1;

  IF v_listing_id IS NULL THEN
    RAISE EXCEPTION 'listing not found';
  END IF;
  IF v_seller_id = p_buyer_id THEN
    RAISE EXCEPTION 'cannot offer on own item';
  END IF;

  INSERT INTO public.offers (
    listing_id, seller_id, buyer_id, amount, status, message, counter_count, expires_at
  ) VALUES (
    v_listing_id, v_seller_id, p_buyer_id, p_amount, 'pending', p_message, 0,
    now() + interval '48 hours'
  )
  RETURNING * INTO v_offer;

  INSERT INTO public.offer_events (offer_id, actor_id, event_type, price, message)
  VALUES (v_offer.id, p_buyer_id, 'proposed', p_amount, p_message);

  RETURN to_jsonb(v_offer);
END;
$$;

-- 3b. rpc_counter_offer_v1(offer_id, amount, message, actor_id) → jsonb
DROP FUNCTION IF EXISTS public.rpc_counter_offer_v1(uuid, numeric, text, uuid);
CREATE FUNCTION public.rpc_counter_offer_v1(
  p_offer_id uuid,
  p_amount   numeric,
  p_message  text,
  p_actor_id uuid
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_offer public.offers%ROWTYPE;
BEGIN
  IF p_amount IS NULL OR p_amount <= 0 THEN
    RAISE EXCEPTION 'amount must be positive';
  END IF;

  SELECT * INTO v_offer FROM public.offers WHERE id = p_offer_id FOR UPDATE;
  IF v_offer.id IS NULL THEN
    RAISE EXCEPTION 'offer not found';
  END IF;
  IF v_offer.status NOT IN ('pending','countered') THEN
    RAISE EXCEPTION 'offer is %, cannot counter', v_offer.status;
  END IF;
  IF v_offer.counter_count >= 5 THEN
    RAISE EXCEPTION 'counter limit reached (max 5 rounds per offer)';
  END IF;
  IF p_actor_id NOT IN (v_offer.seller_id, v_offer.buyer_id) THEN
    RAISE EXCEPTION 'not a participant';
  END IF;

  UPDATE public.offers SET
    amount        = p_amount,
    status        = 'countered',
    message       = p_message,
    counter_count = counter_count + 1,
    expires_at    = now() + interval '48 hours'
  WHERE id = p_offer_id
  RETURNING * INTO v_offer;

  INSERT INTO public.offer_events (offer_id, actor_id, event_type, price, message)
  VALUES (p_offer_id, p_actor_id, 'countered', p_amount, p_message);

  RETURN to_jsonb(v_offer);
END;
$$;

-- 3c. rpc_respond_offer_v1(offer_id, accept, message, actor_id) → jsonb
DROP FUNCTION IF EXISTS public.rpc_respond_offer_v1(uuid, boolean, text, uuid);
CREATE FUNCTION public.rpc_respond_offer_v1(
  p_offer_id uuid,
  p_accept   boolean,
  p_message  text,
  p_actor_id uuid
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_offer    public.offers%ROWTYPE;
  v_new_st   text;
  v_event    text;
BEGIN
  SELECT * INTO v_offer FROM public.offers WHERE id = p_offer_id FOR UPDATE;
  IF v_offer.id IS NULL THEN
    RAISE EXCEPTION 'offer not found';
  END IF;
  IF v_offer.status NOT IN ('pending','countered') THEN
    RAISE EXCEPTION 'offer is %, cannot respond', v_offer.status;
  END IF;
  IF p_actor_id NOT IN (v_offer.seller_id, v_offer.buyer_id) THEN
    RAISE EXCEPTION 'not a participant';
  END IF;

  v_new_st := CASE WHEN p_accept THEN 'accepted' ELSE 'declined' END;
  v_event  := v_new_st;

  UPDATE public.offers SET
    status     = v_new_st,
    message    = COALESCE(p_message, message),
    expires_at = NULL  -- decision made, no more clock
  WHERE id = p_offer_id
  RETURNING * INTO v_offer;

  INSERT INTO public.offer_events (offer_id, actor_id, event_type, price, message)
  VALUES (p_offer_id, p_actor_id, v_event, v_offer.amount, p_message);

  RETURN to_jsonb(v_offer);
END;
$$;

-- 3d. rpc_cancel_offer_v1(offer_id, actor_id) → jsonb
DROP FUNCTION IF EXISTS public.rpc_cancel_offer_v1(uuid, uuid);
CREATE FUNCTION public.rpc_cancel_offer_v1(
  p_offer_id uuid,
  p_actor_id uuid
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_offer public.offers%ROWTYPE;
BEGIN
  SELECT * INTO v_offer FROM public.offers WHERE id = p_offer_id FOR UPDATE;
  IF v_offer.id IS NULL THEN
    RAISE EXCEPTION 'offer not found';
  END IF;
  IF v_offer.status NOT IN ('pending','countered') THEN
    RAISE EXCEPTION 'offer is %, cannot cancel', v_offer.status;
  END IF;
  IF p_actor_id NOT IN (v_offer.seller_id, v_offer.buyer_id) THEN
    RAISE EXCEPTION 'not a participant';
  END IF;

  UPDATE public.offers SET status = 'cancelled', expires_at = NULL
  WHERE id = p_offer_id
  RETURNING * INTO v_offer;

  INSERT INTO public.offer_events (offer_id, actor_id, event_type, message)
  VALUES (p_offer_id, p_actor_id, 'cancelled', NULL);

  RETURN to_jsonb(v_offer);
END;
$$;

-- ---------------------------------------------------------------------------
-- 4. Permissions
-- ---------------------------------------------------------------------------
REVOKE ALL ON FUNCTION public.rpc_propose_offer_v1(uuid, numeric, text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.rpc_counter_offer_v1(uuid, numeric, text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.rpc_respond_offer_v1(uuid, boolean, text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.rpc_cancel_offer_v1(uuid, uuid)                  FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.rpc_propose_offer_v1(uuid, numeric, text, uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.rpc_counter_offer_v1(uuid, numeric, text, uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.rpc_respond_offer_v1(uuid, boolean, text, uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.rpc_cancel_offer_v1(uuid, uuid)                  TO authenticated, service_role;
