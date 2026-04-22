-- 2026-04-22: Activate ship/complete leg of the Deal Desk flow.
-- Sister migration to 20260422_deal_desk_activate.sql; same conventions
-- (SECURITY DEFINER, caller-side IDOR pre-flight per learnings.md §13).

-- Add 'delivered' status alias is unnecessary — completed is the terminal state.
-- Status transitions allowed by these RPCs:
--   accepted → shipped   (rpc_mark_shipped_v1, seller-only)
--   shipped  → completed (rpc_complete_deal_v1, buyer-only, optional rating)

-- ---------------------------------------------------------------------------
-- 1. rpc_mark_shipped_v1(offer_id, tracking_info) → jsonb
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.rpc_mark_shipped_v1(uuid, text);
CREATE FUNCTION public.rpc_mark_shipped_v1(
  p_offer_id      uuid,
  p_tracking_info text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_offer public.offers%ROWTYPE;
BEGIN
  SELECT * INTO v_offer FROM public.offers WHERE id = p_offer_id FOR UPDATE;
  IF v_offer.id IS NULL THEN
    RAISE EXCEPTION 'offer not found';
  END IF;
  IF v_offer.status <> 'accepted' THEN
    RAISE EXCEPTION 'offer is %, must be accepted before shipping', v_offer.status;
  END IF;

  UPDATE public.offers SET status = 'shipped'
  WHERE id = p_offer_id
  RETURNING * INTO v_offer;

  -- offer_events.actor_id NOT NULL; seller is the actor for shipping.
  -- tracking info goes into metadata jsonb so analytics can pull it.
  INSERT INTO public.offer_events (offer_id, actor_id, event_type, message, metadata)
  VALUES (
    p_offer_id, v_offer.seller_id, 'shipped',
    NULLIF(p_tracking_info, ''),
    jsonb_build_object('tracking_info', NULLIF(p_tracking_info, ''))
  );

  RETURN to_jsonb(v_offer);
END;
$$;

-- ---------------------------------------------------------------------------
-- 2. rpc_complete_deal_v1(offer_id, stars, comment) → jsonb
--    Caller (router) has already verified buyer == auth user. Function
--    transitions shipped → completed and (if stars >= 1) inserts a
--    deal_ratings row from buyer rating seller.
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.rpc_complete_deal_v1(uuid, smallint, text);
CREATE FUNCTION public.rpc_complete_deal_v1(
  p_offer_id uuid,
  p_stars    smallint,
  p_comment  text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_offer public.offers%ROWTYPE;
BEGIN
  SELECT * INTO v_offer FROM public.offers WHERE id = p_offer_id FOR UPDATE;
  IF v_offer.id IS NULL THEN
    RAISE EXCEPTION 'offer not found';
  END IF;
  IF v_offer.status <> 'shipped' THEN
    RAISE EXCEPTION 'offer is %, must be shipped before completion', v_offer.status;
  END IF;
  IF p_stars IS NOT NULL AND (p_stars < 1 OR p_stars > 5) THEN
    RAISE EXCEPTION 'stars must be 1..5';
  END IF;

  UPDATE public.offers SET status = 'completed'
  WHERE id = p_offer_id
  RETURNING * INTO v_offer;

  -- 'delivered' event recorded by buyer (the one calling complete).
  INSERT INTO public.offer_events (offer_id, actor_id, event_type, message)
  VALUES (p_offer_id, v_offer.buyer_id, 'delivered', p_comment);

  -- Optional: buyer-rates-seller. ON CONFLICT no-ops on double-call so the
  -- endpoint is idempotent (UNIQUE(offer_id, rater_id) on deal_ratings).
  IF p_stars IS NOT NULL AND p_stars >= 1 THEN
    INSERT INTO public.deal_ratings (offer_id, rater_id, rated_id, role, stars, comment)
    VALUES (p_offer_id, v_offer.buyer_id, v_offer.seller_id, 'seller', p_stars, p_comment)
    ON CONFLICT (offer_id, rater_id) DO NOTHING;

    -- Surface the rating event too so the timeline is complete.
    INSERT INTO public.offer_events (offer_id, actor_id, event_type, message, metadata)
    VALUES (
      p_offer_id, v_offer.buyer_id, 'rated', p_comment,
      jsonb_build_object('stars', p_stars, 'role', 'seller')
    );
  END IF;

  RETURN to_jsonb(v_offer);
END;
$$;

-- ---------------------------------------------------------------------------
-- Permissions
-- ---------------------------------------------------------------------------
REVOKE ALL ON FUNCTION public.rpc_mark_shipped_v1(uuid, text)             FROM PUBLIC;
REVOKE ALL ON FUNCTION public.rpc_complete_deal_v1(uuid, smallint, text)  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.rpc_mark_shipped_v1(uuid, text)             TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.rpc_complete_deal_v1(uuid, smallint, text)  TO authenticated, service_role;
