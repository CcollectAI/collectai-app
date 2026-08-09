/**
 * Whose turn is it? — the rule behind the marketplace offers badge.
 *
 * This is worth pinning because the wrong version is plausible and silent: if
 * `pending` counted for both sides, a SELLER would be badged for a counter-offer
 * they themselves sent and are waiting on the buyer for. A badge that nags about
 * someone else's turn trains people to ignore the badge, which costs exactly the
 * sales the badge exists to save.
 *
 * `can_confirm` / `can_grade` are computed server-side; the client must not
 * re-derive the state machine (see app/offers.tsx header).
 */

import { offerNeedsMyAction, countOffersNeedingAction, type P2POffer } from '@/api/p2pApi';

const offer = (over: Partial<P2POffer>): P2POffer => ({
  id: 'o1',
  listing_id: 'l1',
  listing_title: 'A card',
  buyer_id: 'b',
  seller_id: 's',
  amount: 10,
  currency: 'EUR',
  status: 'pending',
  message: null,
  counter_count: 0,
  created_at: null,
  seller_confirmed_at: null,
  buyer_confirmed_at: null,
  i_am_buyer: false,
  can_confirm: false,
  can_grade: false,
  already_graded: false,
  ...over,
});

describe('offerNeedsMyAction', () => {
  it('badges the SELLER for a pending offer — it waits on them', () => {
    expect(offerNeedsMyAction(offer({ status: 'pending', i_am_buyer: false }))).toBe(true);
  });

  it('does NOT badge the buyer for their own pending offer', () => {
    expect(offerNeedsMyAction(offer({ status: 'pending', i_am_buyer: true }))).toBe(false);
  });

  it('badges the BUYER for a counter — the counter waits on them', () => {
    expect(offerNeedsMyAction(offer({ status: 'countered', i_am_buyer: true }))).toBe(true);
  });

  it('does NOT badge the seller for the counter they sent', () => {
    expect(offerNeedsMyAction(offer({ status: 'countered', i_am_buyer: false }))).toBe(false);
  });

  it('badges whenever the server says the exchange can be confirmed', () => {
    // Regardless of side: confirmation is genuinely each party's own step.
    expect(offerNeedsMyAction(offer({ status: 'accepted', can_confirm: true, i_am_buyer: true }))).toBe(true);
    expect(offerNeedsMyAction(offer({ status: 'accepted', can_confirm: true, i_am_buyer: false }))).toBe(true);
  });

  it('badges an ungraded gradable trade, but not one already graded', () => {
    expect(offerNeedsMyAction(offer({ status: 'completed', can_grade: true, already_graded: false }))).toBe(true);
    expect(offerNeedsMyAction(offer({ status: 'completed', can_grade: true, already_graded: true }))).toBe(false);
  });

  it.each(['declined', 'cancelled', 'expired', 'completed', 'shipped', 'accepted'])(
    'does not badge a %s offer with nothing actionable on it',
    (status) => {
      expect(offerNeedsMyAction(offer({ status }))).toBe(false);
    },
  );

  it('ignores an unknown status rather than badging it', () => {
    // A status added server-side must not silently start badging every user.
    expect(offerNeedsMyAction(offer({ status: 'some_future_state' }))).toBe(false);
  });
});

describe('countOffersNeedingAction', () => {
  it('counts only the actionable ones', () => {
    expect(
      countOffersNeedingAction([
        offer({ id: '1', status: 'pending', i_am_buyer: false }),   // yes
        offer({ id: '2', status: 'pending', i_am_buyer: true }),    // no
        offer({ id: '3', status: 'countered', i_am_buyer: true }),  // yes
        offer({ id: '4', status: 'declined' }),                     // no
        offer({ id: '5', status: 'completed', can_grade: true }),    // yes
      ]),
    ).toBe(3);
  });

  it('is 0 for an empty list, so the badge simply does not render', () => {
    expect(countOffersNeedingAction([])).toBe(0);
  });
});
