-- 2026-05-18: replace the onboarding age checkbox with a per-user
-- seller-side age gate.
--
-- Before: onboarding asked "I confirm I am 13+"; value was never persisted
-- and the check was purely cosmetic. App Store Age Rating + parental
-- controls already cover the consumer-collection use case.
--
-- After: age verification is required only before financial transactions
-- (creating a marketplace listing, connecting an eBay seller account, etc.).
-- This column records when the user attested to being of legal selling age
-- in their region (default 18). Backend /marketplace/listings/* endpoints
-- refuse with 403 if this is null at create-account / publish time.
--
-- Idempotent.

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS seller_age_verified_at timestamptz;

COMMENT ON COLUMN public.profiles.seller_age_verified_at IS
  'Timestamp of user attestation that they are of legal age to sell in their region. NULL = unverified, /marketplace/listings/* mutating endpoints reject.';

-- RLS: existing profile-self read/write policy covers this column.
-- No new policy needed.
