/**
 * The platform's fee, in ONE place.
 *
 * It was written six times (class sweep D, 2026-09-17): twice as
 * `int(x * 0.05)` on the server (the ticket checkout and the webhook that
 * records what was charged), once in the organiser's hint under the ticket
 * price field, and twice in `app/legal/terms.tsx` — legal copy a member can
 * hold us to. Every copy said 5%, which is exactly how this class ships: the
 * rate is right until someone changes one of six.
 *
 * The mirror is `PLATFORM_FEE_PCT` in `server/app/lib/money.py`, and
 * `server/tests/test_platform_fee_parity.py` reads THIS file and fails if the
 * two disagree — the same arrangement as `CURRENCY_SYMBOLS`.
 */
export const PLATFORM_FEE_PCT = 5;
