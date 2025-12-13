-- Recreate the view atomically: drop first, then create with the desired shape.
DROP VIEW IF EXISTS public.v_label_events;

CREATE VIEW public.v_label_events AS
SELECT
  le.id,
  le.user_id,
  le.session_uuid,
  ps.id   AS session_id,
  ps.category,
  ps.status AS session_status,
  le.corrected_title,
  le.corrected_condition,
  le.corrected_price_eur,
  le.created_at
FROM public.label_events le
LEFT JOIN public.predict_sessions ps
  ON ps.uuid_id = le.session_uuid;

GRANT SELECT ON public.v_label_events TO authenticated;

-- Refresh PostgREST schema cache
NOTIFY pgrst, 'reload schema';
