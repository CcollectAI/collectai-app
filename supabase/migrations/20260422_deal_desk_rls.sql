-- 2026-04-22: Enable RLS on the 3 deal-desk tables that were wide-open.
-- Without these policies, any authenticated Supabase client could SELECT
-- every offer_event, evidence snapshot, or rating in the DB (since the
-- frontend uses a Supabase anon JWT, not the service role).

-- ---------------------------------------------------------------------------
-- offer_events — participant-visible only.
-- ---------------------------------------------------------------------------
ALTER TABLE public.offer_events ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='offer_events' AND policyname='offer_events_participant_read') THEN
    CREATE POLICY offer_events_participant_read ON public.offer_events
      FOR SELECT USING (
        EXISTS (
          SELECT 1 FROM public.offers o
          WHERE o.id = offer_events.offer_id
            AND (o.seller_id = auth.uid() OR o.buyer_id = auth.uid())
        )
      );
  END IF;
END $$;

-- Writers go through SECURITY DEFINER RPCs; block direct INSERTs from anon.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='offer_events' AND policyname='offer_events_no_direct_write') THEN
    CREATE POLICY offer_events_no_direct_write ON public.offer_events
      FOR INSERT WITH CHECK (false);
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- offer_evidence — participant-visible only (dossier snapshot).
-- ---------------------------------------------------------------------------
ALTER TABLE public.offer_evidence ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='offer_evidence' AND policyname='offer_evidence_participant_read') THEN
    CREATE POLICY offer_evidence_participant_read ON public.offer_evidence
      FOR SELECT USING (
        EXISTS (
          SELECT 1 FROM public.offers o
          WHERE o.id = offer_evidence.offer_id
            AND (o.seller_id = auth.uid() OR o.buyer_id = auth.uid())
        )
      );
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='offer_evidence' AND policyname='offer_evidence_no_direct_write') THEN
    CREATE POLICY offer_evidence_no_direct_write ON public.offer_evidence
      FOR INSERT WITH CHECK (false);
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- deal_ratings — ratings are public-read (build trust score UI) but only
-- the rater can insert, and only on offers they participated in.
-- ---------------------------------------------------------------------------
ALTER TABLE public.deal_ratings ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='deal_ratings' AND policyname='deal_ratings_public_read') THEN
    CREATE POLICY deal_ratings_public_read ON public.deal_ratings
      FOR SELECT USING (true);
  END IF;
END $$;

-- Writes are done through rpc_complete_deal_v1; block anon INSERTs.
-- The RPC uses SECURITY DEFINER and bypasses RLS.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='deal_ratings' AND policyname='deal_ratings_no_direct_write') THEN
    CREATE POLICY deal_ratings_no_direct_write ON public.deal_ratings
      FOR INSERT WITH CHECK (false);
  END IF;
END $$;
