-- ============================================================================
-- Deal Desk Fixes — Column name mismatches, missing RLS, indexes, constraints
-- Migration: 20260226_deal_desk_fixes.sql
-- ============================================================================
-- Fixes:
--   1. dm_threads column mismatch: user_a/user_b → requester_id/responder_id
--   2. chat_messages column mismatch: dm_thread_id/body → thread_id/text
--   3. Missing RLS INSERT/DELETE policies
--   4. Missing indexes on offer_evidence and deal_ratings
--   5. Missing ON DELETE CASCADE for deal_ratings.offer_id
--   6. Missing foreign key constraints on user reference columns
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Recreate ALL 6 RPC functions with corrected column names
--    - dm_threads: requester_id / responder_id  (was user_a / user_b)
--    - chat_messages: thread_id / text           (was dm_thread_id / body)
-- ---------------------------------------------------------------------------

-- 1.1 Propose offer (the critical fix — references dm_threads columns directly)
CREATE OR REPLACE FUNCTION rpc_propose_offer_v1(
  p_item_id   uuid,
  p_price     numeric,
  p_message   text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_uid        uuid := auth.uid();
  v_seller_id  uuid;
  v_thread_id  uuid;
  v_offer_id   uuid;
  v_item_title text;
BEGIN
  -- Get item owner (seller)
  SELECT user_id, COALESCE(title, name, 'Untitled')
    INTO v_seller_id, v_item_title
    FROM items
    WHERE id = p_item_id;

  IF v_seller_id IS NULL THEN
    RAISE EXCEPTION 'Item not found';
  END IF;

  IF v_seller_id = v_uid THEN
    RAISE EXCEPTION 'Cannot make an offer on your own item';
  END IF;

  -- Find or create DM thread (FIXED: requester_id/responder_id, not user_a/user_b)
  SELECT id INTO v_thread_id
    FROM dm_threads
    WHERE (requester_id = v_uid AND responder_id = v_seller_id)
       OR (requester_id = v_seller_id AND responder_id = v_uid)
    LIMIT 1;

  IF v_thread_id IS NULL THEN
    INSERT INTO dm_threads (requester_id, responder_id, status)
    VALUES (v_uid, v_seller_id, 'accepted')
    RETURNING id INTO v_thread_id;
  END IF;

  -- Create offer
  INSERT INTO offers (dm_thread_id, item_id, seller_id, buyer_id, status, current_price, currency, buyer_note)
  VALUES (v_thread_id, p_item_id, v_seller_id, v_uid, 'proposed', p_price, 'EUR', p_message)
  RETURNING id INTO v_offer_id;

  -- Insert audit event
  INSERT INTO offer_events (offer_id, actor_id, event_type, price, message)
  VALUES (v_offer_id, v_uid, 'proposed', p_price, p_message);

  -- Send offer message in DM (FIXED: thread_id/text, not dm_thread_id/body)
  INSERT INTO chat_messages (thread_id, author_user_id, text)
  VALUES (v_thread_id, v_uid, format('[OFFER:%s] Offer of %s EUR for %s', v_offer_id, p_price, v_item_title));

  RETURN jsonb_build_object(
    'offer_id', v_offer_id,
    'dm_thread_id', v_thread_id,
    'status', 'proposed'
  );
END;
$$;

-- 1.2 Counter offer (FIXED: chat_messages column names)
CREATE OR REPLACE FUNCTION rpc_counter_offer_v1(
  p_offer_id  uuid,
  p_price     numeric,
  p_message   text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_uid       uuid := auth.uid();
  v_offer     offers%ROWTYPE;
BEGIN
  SELECT * INTO v_offer FROM offers WHERE id = p_offer_id;

  IF v_offer.id IS NULL THEN
    RAISE EXCEPTION 'Offer not found';
  END IF;

  -- Must be the other party
  IF v_uid != v_offer.seller_id AND v_uid != v_offer.buyer_id THEN
    RAISE EXCEPTION 'Not authorized';
  END IF;

  IF v_offer.status NOT IN ('proposed', 'countered') THEN
    RAISE EXCEPTION 'Offer cannot be countered in current status: %', v_offer.status;
  END IF;

  -- Update offer
  UPDATE offers
  SET current_price = p_price,
      status = 'countered',
      updated_at = now()
  WHERE id = p_offer_id;

  -- Insert audit event
  INSERT INTO offer_events (offer_id, actor_id, event_type, price, message)
  VALUES (p_offer_id, v_uid, 'countered', p_price, p_message);

  -- Send counter message in DM (FIXED: thread_id/text)
  INSERT INTO chat_messages (thread_id, author_user_id, text)
  VALUES (v_offer.dm_thread_id, v_uid, format('[OFFER:%s] Counter-offer: %s EUR', p_offer_id, p_price));

  RETURN jsonb_build_object(
    'offer_id', p_offer_id,
    'status', 'countered',
    'current_price', p_price
  );
END;
$$;

-- 1.3 Respond to offer — accept or decline (FIXED: chat_messages column names)
CREATE OR REPLACE FUNCTION rpc_respond_offer_v1(
  p_offer_id  uuid,
  p_accept    boolean,
  p_message   text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_uid       uuid := auth.uid();
  v_offer     offers%ROWTYPE;
  v_new_status text;
BEGIN
  SELECT * INTO v_offer FROM offers WHERE id = p_offer_id;

  IF v_offer.id IS NULL THEN
    RAISE EXCEPTION 'Offer not found';
  END IF;

  IF v_uid != v_offer.seller_id AND v_uid != v_offer.buyer_id THEN
    RAISE EXCEPTION 'Not authorized';
  END IF;

  IF v_offer.status NOT IN ('proposed', 'countered') THEN
    RAISE EXCEPTION 'Offer cannot be responded to in current status: %', v_offer.status;
  END IF;

  v_new_status := CASE WHEN p_accept THEN 'accepted' ELSE 'declined' END;

  UPDATE offers
  SET status = v_new_status,
      accepted_at = CASE WHEN p_accept THEN now() ELSE NULL END,
      updated_at = now()
  WHERE id = p_offer_id;

  -- On accept, mark item as no longer for sale
  IF p_accept THEN
    UPDATE items SET for_sale = false WHERE id = v_offer.item_id;
  END IF;

  INSERT INTO offer_events (offer_id, actor_id, event_type, message)
  VALUES (p_offer_id, v_uid, v_new_status, p_message);

  -- FIXED: thread_id/text
  INSERT INTO chat_messages (thread_id, author_user_id, text)
  VALUES (v_offer.dm_thread_id, v_uid,
    format('[OFFER:%s] Offer %s', p_offer_id, v_new_status));

  RETURN jsonb_build_object(
    'offer_id', p_offer_id,
    'status', v_new_status
  );
END;
$$;

-- 1.4 Cancel offer (FIXED: chat_messages column names)
CREATE OR REPLACE FUNCTION rpc_cancel_offer_v1(
  p_offer_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_uid   uuid := auth.uid();
  v_offer offers%ROWTYPE;
BEGIN
  SELECT * INTO v_offer FROM offers WHERE id = p_offer_id;

  IF v_offer.id IS NULL THEN
    RAISE EXCEPTION 'Offer not found';
  END IF;

  IF v_uid != v_offer.buyer_id THEN
    RAISE EXCEPTION 'Only the proposer can cancel';
  END IF;

  IF v_offer.status NOT IN ('proposed', 'countered') THEN
    RAISE EXCEPTION 'Offer cannot be cancelled in current status: %', v_offer.status;
  END IF;

  UPDATE offers
  SET status = 'cancelled', updated_at = now()
  WHERE id = p_offer_id;

  INSERT INTO offer_events (offer_id, actor_id, event_type)
  VALUES (p_offer_id, v_uid, 'cancelled');

  -- FIXED: thread_id/text
  INSERT INTO chat_messages (thread_id, author_user_id, text)
  VALUES (v_offer.dm_thread_id, v_uid,
    format('[OFFER:%s] Offer cancelled', p_offer_id));

  RETURN jsonb_build_object('offer_id', p_offer_id, 'status', 'cancelled');
END;
$$;

-- 1.5 Mark shipped (FIXED: chat_messages column names)
CREATE OR REPLACE FUNCTION rpc_mark_shipped_v1(
  p_offer_id      uuid,
  p_tracking_info text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_uid   uuid := auth.uid();
  v_offer offers%ROWTYPE;
BEGIN
  SELECT * INTO v_offer FROM offers WHERE id = p_offer_id;

  IF v_offer.id IS NULL THEN
    RAISE EXCEPTION 'Offer not found';
  END IF;

  IF v_uid != v_offer.seller_id THEN
    RAISE EXCEPTION 'Only the seller can mark as shipped';
  END IF;

  IF v_offer.status != 'accepted' THEN
    RAISE EXCEPTION 'Offer must be accepted before shipping';
  END IF;

  UPDATE offers
  SET status = 'accepted', updated_at = now()
  WHERE id = p_offer_id;

  INSERT INTO offer_events (offer_id, actor_id, event_type, metadata)
  VALUES (p_offer_id, v_uid, 'shipped',
    CASE WHEN p_tracking_info IS NOT NULL
      THEN jsonb_build_object('tracking_info', p_tracking_info)
      ELSE '{}'::jsonb
    END);

  -- FIXED: thread_id/text
  INSERT INTO chat_messages (thread_id, author_user_id, text)
  VALUES (v_offer.dm_thread_id, v_uid,
    format('[OFFER:%s] Item shipped%s', p_offer_id,
      CASE WHEN p_tracking_info IS NOT NULL
        THEN ' — Tracking: ' || p_tracking_info
        ELSE ''
      END));

  RETURN jsonb_build_object('offer_id', p_offer_id, 'status', 'shipped');
END;
$$;

-- 1.6 Complete deal — buyer confirms delivery + rates (FIXED: chat_messages column names)
CREATE OR REPLACE FUNCTION rpc_complete_deal_v1(
  p_offer_id uuid,
  p_stars    smallint,
  p_comment  text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_uid   uuid := auth.uid();
  v_offer offers%ROWTYPE;
BEGIN
  SELECT * INTO v_offer FROM offers WHERE id = p_offer_id;

  IF v_offer.id IS NULL THEN
    RAISE EXCEPTION 'Offer not found';
  END IF;

  IF v_uid != v_offer.buyer_id THEN
    RAISE EXCEPTION 'Only the buyer can confirm delivery';
  END IF;

  IF v_offer.status != 'accepted' THEN
    RAISE EXCEPTION 'Offer must be accepted/shipped before completing';
  END IF;

  -- Mark completed
  UPDATE offers
  SET status = 'completed', completed_at = now(), updated_at = now()
  WHERE id = p_offer_id;

  INSERT INTO offer_events (offer_id, actor_id, event_type, metadata)
  VALUES (p_offer_id, v_uid, 'delivered', jsonb_build_object('stars', p_stars));

  -- Insert rating (buyer rates seller)
  INSERT INTO deal_ratings (offer_id, rater_id, rated_id, role, stars, comment)
  VALUES (p_offer_id, v_uid, v_offer.seller_id, 'buyer', p_stars, p_comment);

  -- FIXED: thread_id/text
  INSERT INTO chat_messages (thread_id, author_user_id, text)
  VALUES (v_offer.dm_thread_id, v_uid,
    format('[OFFER:%s] Deal completed! Rated %s stars', p_offer_id, p_stars));

  RETURN jsonb_build_object('offer_id', p_offer_id, 'status', 'completed');
END;
$$;


-- ---------------------------------------------------------------------------
-- 2. Missing RLS INSERT/DELETE policies
-- ---------------------------------------------------------------------------

-- offers: INSERT for buyer
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'offers' AND policyname = 'offers_insert') THEN
    CREATE POLICY offers_insert ON offers FOR INSERT
      WITH CHECK (auth.uid() = buyer_id);
  END IF;
END $$;

-- offers: DELETE for buyer (cancel their own, only in active negotiation states)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'offers' AND policyname = 'offers_delete') THEN
    CREATE POLICY offers_delete ON offers FOR DELETE
      USING (auth.uid() = buyer_id AND status IN ('proposed', 'countered'));
  END IF;
END $$;

-- offer_events: INSERT for users on parent offer
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'offer_events' AND policyname = 'offer_events_insert') THEN
    CREATE POLICY offer_events_insert ON offer_events FOR INSERT
      WITH CHECK (
        EXISTS (
          SELECT 1 FROM offers o
          WHERE o.id = offer_events.offer_id
            AND (o.seller_id = auth.uid() OR o.buyer_id = auth.uid())
        )
      );
  END IF;
END $$;

-- offer_evidence: INSERT for users on parent offer
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'offer_evidence' AND policyname = 'offer_evidence_insert') THEN
    CREATE POLICY offer_evidence_insert ON offer_evidence FOR INSERT
      WITH CHECK (
        EXISTS (
          SELECT 1 FROM offers o
          WHERE o.id = offer_evidence.offer_id
            AND (o.seller_id = auth.uid() OR o.buyer_id = auth.uid())
        )
      );
  END IF;
END $$;

-- deal_ratings: DELETE for rater (retract own rating)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'deal_ratings' AND policyname = 'deal_ratings_delete') THEN
    CREATE POLICY deal_ratings_delete ON deal_ratings FOR DELETE
      USING (rater_id = auth.uid());
  END IF;
END $$;


-- ---------------------------------------------------------------------------
-- 3. Missing indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_offer_evidence_offer ON offer_evidence(offer_id);
CREATE INDEX IF NOT EXISTS idx_deal_ratings_offer ON deal_ratings(offer_id);
CREATE INDEX IF NOT EXISTS idx_deal_ratings_rater ON deal_ratings(rater_id);


-- ---------------------------------------------------------------------------
-- 4. Missing ON DELETE CASCADE for deal_ratings.offer_id
-- ---------------------------------------------------------------------------

ALTER TABLE deal_ratings DROP CONSTRAINT IF EXISTS deal_ratings_offer_id_fkey;
ALTER TABLE deal_ratings ADD CONSTRAINT deal_ratings_offer_id_fkey
  FOREIGN KEY (offer_id) REFERENCES offers(id) ON DELETE CASCADE;


-- ---------------------------------------------------------------------------
-- 5. Missing foreign key constraints on user reference columns
-- ---------------------------------------------------------------------------

DO $$ BEGIN
  ALTER TABLE offers ADD CONSTRAINT offers_seller_id_fkey
    FOREIGN KEY (seller_id) REFERENCES auth.users(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE offers ADD CONSTRAINT offers_buyer_id_fkey
    FOREIGN KEY (buyer_id) REFERENCES auth.users(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE offer_events ADD CONSTRAINT offer_events_actor_id_fkey
    FOREIGN KEY (actor_id) REFERENCES auth.users(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE deal_ratings ADD CONSTRAINT deal_ratings_rater_id_fkey
    FOREIGN KEY (rater_id) REFERENCES auth.users(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE deal_ratings ADD CONSTRAINT deal_ratings_rated_id_fkey
    FOREIGN KEY (rated_id) REFERENCES auth.users(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
