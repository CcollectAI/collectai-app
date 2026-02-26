-- ============================================================================
-- Deal Desk — P2P Offer / Negotiation Layer
-- Migration: 20260225_deal_desk.sql
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. New tables
-- ---------------------------------------------------------------------------

-- Core offer tracking
CREATE TABLE IF NOT EXISTS offers (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dm_thread_id  uuid NOT NULL REFERENCES dm_threads(id),
  item_id       uuid NOT NULL REFERENCES items(id),
  seller_id     uuid NOT NULL,
  buyer_id      uuid NOT NULL,
  status        text NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed','countered','accepted','declined','expired','completed','cancelled')),
  current_price numeric NOT NULL CHECK (current_price > 0),
  currency      text NOT NULL DEFAULT 'EUR',
  seller_note   text,
  buyer_note    text,
  expires_at    timestamptz,
  accepted_at   timestamptz,
  completed_at  timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

-- Negotiation history (append-only audit log)
CREATE TABLE IF NOT EXISTS offer_events (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id      uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  actor_id      uuid NOT NULL,
  event_type    text NOT NULL
                CHECK (event_type IN ('proposed','countered','accepted','declined','expired','cancelled','shipped','delivered','rated')),
  price         numeric,
  message       text,
  metadata      jsonb DEFAULT '{}',
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Immutable dossier + comps snapshot at offer time
CREATE TABLE IF NOT EXISTS offer_evidence (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id        uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  dossier_json    jsonb NOT NULL,
  market_comps    jsonb,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- Post-deal mutual ratings
CREATE TABLE IF NOT EXISTS deal_ratings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id      uuid NOT NULL REFERENCES offers(id),
  rater_id      uuid NOT NULL,
  rated_id      uuid NOT NULL,
  role          text NOT NULL CHECK (role IN ('buyer','seller')),
  stars         smallint NOT NULL CHECK (stars BETWEEN 1 AND 5),
  comment       text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE(offer_id, rater_id)
);

-- Add for_sale columns to items
ALTER TABLE items ADD COLUMN IF NOT EXISTS for_sale boolean DEFAULT false;
ALTER TABLE items ADD COLUMN IF NOT EXISTS asking_price numeric;
ALTER TABLE items ADD COLUMN IF NOT EXISTS asking_currency text DEFAULT 'EUR';

-- ---------------------------------------------------------------------------
-- 2. Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_offers_seller ON offers(seller_id, status);
CREATE INDEX IF NOT EXISTS idx_offers_buyer ON offers(buyer_id, status);
CREATE INDEX IF NOT EXISTS idx_offers_item ON offers(item_id);
CREATE INDEX IF NOT EXISTS idx_offers_thread ON offers(dm_thread_id);
CREATE INDEX IF NOT EXISTS idx_offer_events_offer ON offer_events(offer_id, created_at);
CREATE INDEX IF NOT EXISTS idx_deal_ratings_rated ON deal_ratings(rated_id);
CREATE INDEX IF NOT EXISTS idx_items_for_sale ON items(for_sale) WHERE for_sale = true;

-- ---------------------------------------------------------------------------
-- 3. RLS Policies
-- ---------------------------------------------------------------------------

ALTER TABLE offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE offer_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE offer_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE deal_ratings ENABLE ROW LEVEL SECURITY;

-- offers: SELECT/UPDATE for seller or buyer
CREATE POLICY offers_select ON offers FOR SELECT
  USING (auth.uid() = seller_id OR auth.uid() = buyer_id);

CREATE POLICY offers_update ON offers FOR UPDATE
  USING (auth.uid() = seller_id OR auth.uid() = buyer_id);

-- offer_events: SELECT for users on parent offer
CREATE POLICY offer_events_select ON offer_events FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM offers o
      WHERE o.id = offer_events.offer_id
        AND (o.seller_id = auth.uid() OR o.buyer_id = auth.uid())
    )
  );

-- offer_evidence: SELECT for users on parent offer
CREATE POLICY offer_evidence_select ON offer_evidence FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM offers o
      WHERE o.id = offer_evidence.offer_id
        AND (o.seller_id = auth.uid() OR o.buyer_id = auth.uid())
    )
  );

-- deal_ratings: SELECT public, INSERT only rater_id = auth.uid()
CREATE POLICY deal_ratings_select ON deal_ratings FOR SELECT
  USING (true);

CREATE POLICY deal_ratings_insert ON deal_ratings FOR INSERT
  WITH CHECK (rater_id = auth.uid());

-- ---------------------------------------------------------------------------
-- 4. RPC Functions
-- ---------------------------------------------------------------------------

-- 4.1 Propose offer
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

  -- Find or create DM thread
  SELECT id INTO v_thread_id
    FROM dm_threads
    WHERE (user_a = v_uid AND user_b = v_seller_id)
       OR (user_a = v_seller_id AND user_b = v_uid)
    LIMIT 1;

  IF v_thread_id IS NULL THEN
    INSERT INTO dm_threads (user_a, user_b, status)
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

  -- Send offer message in DM
  INSERT INTO chat_messages (dm_thread_id, author_user_id, body)
  VALUES (v_thread_id, v_uid, format('[OFFER:%s] Offer of %s EUR for %s', v_offer_id, p_price, v_item_title));

  RETURN jsonb_build_object(
    'offer_id', v_offer_id,
    'dm_thread_id', v_thread_id,
    'status', 'proposed'
  );
END;
$$;

-- 4.2 Counter offer
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

  -- Send counter message in DM
  INSERT INTO chat_messages (dm_thread_id, author_user_id, body)
  VALUES (v_offer.dm_thread_id, v_uid, format('[OFFER:%s] Counter-offer: %s EUR', p_offer_id, p_price));

  RETURN jsonb_build_object(
    'offer_id', p_offer_id,
    'status', 'countered',
    'current_price', p_price
  );
END;
$$;

-- 4.3 Respond to offer (accept or decline)
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

  INSERT INTO chat_messages (dm_thread_id, author_user_id, body)
  VALUES (v_offer.dm_thread_id, v_uid,
    format('[OFFER:%s] Offer %s', p_offer_id, v_new_status));

  RETURN jsonb_build_object(
    'offer_id', p_offer_id,
    'status', v_new_status
  );
END;
$$;

-- 4.4 Cancel offer
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

  INSERT INTO chat_messages (dm_thread_id, author_user_id, body)
  VALUES (v_offer.dm_thread_id, v_uid,
    format('[OFFER:%s] Offer cancelled', p_offer_id));

  RETURN jsonb_build_object('offer_id', p_offer_id, 'status', 'cancelled');
END;
$$;

-- 4.5 Mark shipped
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

  INSERT INTO chat_messages (dm_thread_id, author_user_id, body)
  VALUES (v_offer.dm_thread_id, v_uid,
    format('[OFFER:%s] Item shipped%s', p_offer_id,
      CASE WHEN p_tracking_info IS NOT NULL
        THEN ' — Tracking: ' || p_tracking_info
        ELSE ''
      END));

  RETURN jsonb_build_object('offer_id', p_offer_id, 'status', 'shipped');
END;
$$;

-- 4.6 Complete deal (buyer confirms delivery + rates)
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

  INSERT INTO chat_messages (dm_thread_id, author_user_id, body)
  VALUES (v_offer.dm_thread_id, v_uid,
    format('[OFFER:%s] Deal completed! Rated %s stars', p_offer_id, p_stars));

  RETURN jsonb_build_object('offer_id', p_offer_id, 'status', 'completed');
END;
$$;

-- ---------------------------------------------------------------------------
-- 5. Views
-- ---------------------------------------------------------------------------

-- Offer summary with item info and other party details
CREATE OR REPLACE VIEW v_offer_summary_v1 AS
SELECT
  o.id AS offer_id,
  o.item_id,
  COALESCE(i.title, i.name, 'Untitled') AS item_title,
  i.image_url AS item_image_url,
  o.status,
  o.current_price,
  o.currency,
  o.seller_id,
  o.buyer_id,
  o.dm_thread_id,
  o.expires_at,
  o.accepted_at,
  o.completed_at,
  o.created_at,
  o.updated_at,
  -- Seller profile
  sp.display_name AS seller_name,
  sp.avatar_url AS seller_avatar_url,
  -- Buyer profile
  bp.display_name AS buyer_name,
  bp.avatar_url AS buyer_avatar_url
FROM offers o
JOIN items i ON i.id = o.item_id
LEFT JOIN user_public_profiles sp ON sp.user_id = o.seller_id
LEFT JOIN user_public_profiles bp ON bp.user_id = o.buyer_id;

-- Aggregated user reputation
CREATE OR REPLACE VIEW v_user_reputation_v1 AS
SELECT
  dr.rated_id AS user_id,
  ROUND(AVG(dr.stars)::numeric, 1) AS avg_stars,
  COUNT(*)::int AS total_ratings,
  COUNT(DISTINCT dr.offer_id)::int AS completed_deals
FROM deal_ratings dr
GROUP BY dr.rated_id;
