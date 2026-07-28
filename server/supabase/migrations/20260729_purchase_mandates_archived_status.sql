-- Give purchase_mandates a real "deleted" state.
--
-- DELETE /purchase/mandates/{id} is a soft delete: it set status='paused',
-- because the status CHECK only allowed active|paused|exhausted|expired and
-- there was nowhere else to put a deleted row. Three consequences, all
-- user-visible, none of which raise an error:
--
--   1. GET /purchase/mandates has no status filter, so the "deleted" mandate
--      stayed in the list. From the user's side, delete did nothing.
--   2. The create-limit counts `status IN ('active','paused')`, so the slot was
--      never freed. A free user (limit 3) who deleted all three mandates was
--      PERMANENTLY locked out of creating another — verified on prod
--      2026-07-29: three mandates deleted (all became 'paused'), the next
--      create still returned 409.
--   3. That 409 reads "Mandate limit reached (3). Upgrade your plan or delete
--      existing mandates." — advice that cannot work, with no in-app recovery.
--
-- It also conflated two different things: a mandate the user PAUSED (still
-- theirs, still listed, resumable, should keep its slot) and one they DELETED
-- (gone, should free the slot). Those need separate statuses.
--
-- 'archived' is deliberately outside the ('active','paused') set the limit
-- counts, so the existing count query needs no change.

ALTER TABLE public.purchase_mandates
  DROP CONSTRAINT IF EXISTS purchase_mandates_status_check;

ALTER TABLE public.purchase_mandates
  ADD CONSTRAINT purchase_mandates_status_check
  CHECK (status = ANY (ARRAY[
    'active'::text,
    'paused'::text,
    'exhausted'::text,
    'expired'::text,
    'archived'::text
  ]));
