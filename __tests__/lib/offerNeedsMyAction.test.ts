/**
 * `offerNeedsMyAction` is the single definition of "waiting on you".
 *
 * Three surfaces read it: the badge on `app/listings.tsx`, the "N bids need
 * you" row on Home, and the offers screen's own ranking, sections and YOUR
 * MOVE pill. docs/ui-playbook.md — "a count in a badge is a promise the
 * destination has to keep" — requires all three to use this exact function
 * rather than a re-implementation, so a change here changes all three at once
 * and this is the only place that can pin it.
 */
import { offerNeedsMyAction, countOffersNeedingAction, type P2POffer } from '@/api/p2pApi';

const offer = (o: Partial<P2POffer>): P2POffer => ({
  id: 'o1',
  listing_id: 'L1',
  listing_title: 'Charizard',
  buyer_id: 'b',
  seller_id: 's',
  amount: 40,
  currency: 'EUR',
  listing_price: 50,
  status: 'pending',
  message: null,
  counter_count: 0,
  created_at: null,
  seller_confirmed_at: null,
  buyer_confirmed_at: null,
  tracking_carrier: null,
  tracking_carrier_label: null,
  tracking_code: null,
  tracking_set_at: null,
  tracking_url: null,
  i_am_buyer: false,
  i_withdrew: null,
  can_confirm: false,
  can_grade: false,
  already_graded: false,
  can_add_tracking: false,
  ...o,
} as P2POffer);

describe('offerNeedsMyAction', () => {
  it('a bid you received is yours to answer', () => {
    expect(offerNeedsMyAction(offer({ status: 'pending', i_am_buyer: false }))).toBe(true);
  });

  it('a bid you MADE is not', () => {
    expect(offerNeedsMyAction(offer({ status: 'pending', i_am_buyer: true }))).toBe(false);
  });

  it('a counter is answered by whoever did not set the number', () => {
    // §1d-bis: `counter` overwrites `amount` with the seller's figure, so a
    // countered offer is the SELLER's offer sitting in front of the BUYER.
    expect(offerNeedsMyAction(offer({ status: 'countered', i_am_buyer: true }))).toBe(true);
    expect(offerNeedsMyAction(offer({ status: 'countered', i_am_buyer: false }))).toBe(false);
  });

  it('an unrated completed trade still needs you, and a rated one does not', () => {
    expect(offerNeedsMyAction(offer({
      status: 'completed', can_grade: true, already_graded: false }))).toBe(true);
    expect(offerNeedsMyAction(offer({
      status: 'completed', can_grade: true, already_graded: true }))).toBe(false);
  });

  describe('a rival bid on a listing that already accepted another', () => {
    /**
     * §1d keeps these ALIVE on purpose: accept is an agreement, not a lock, and
     * a seller whose buyer ghosts needs the fallback. `_settle_completed_trade`
     * only closes them at completion, which can be a week of shipping later —
     * so until 2026-08-19 every rival kept stamping YOUR MOVE and inflating the
     * badge for an object already promised to somebody else.
     */
    it('is not your move', () => {
      expect(offerNeedsMyAction(offer({
        status: 'pending', i_am_buyer: false, superseded: true }))).toBe(false);
    });

    it('does not count in the badge', () => {
      const offers = [
        offer({ id: 'winner', status: 'pending', i_am_buyer: false }),
        offer({ id: 'rival', status: 'pending', i_am_buyer: false, superseded: true }),
      ];
      expect(countOffersNeedingAction(offers)).toBe(1);
    });

    it('never hides the ACCEPTED trade, which genuinely does need you', () => {
      // `superseded` is checked BELOW can_confirm/can_grade for this reason: a
      // flag placed above them would silence the confirm prompt on the very
      // trade the seller accepted.
      expect(offerNeedsMyAction(offer({
        status: 'accepted', can_confirm: true, superseded: true }))).toBe(true);
      expect(offerNeedsMyAction(offer({
        status: 'completed', can_grade: true, already_graded: false, superseded: true })))
        .toBe(true);
    });
  });

  it('treats a missing superseded flag as "not superseded"', () => {
    // An older server build does not send the field. Undefined must read as
    // "no reservation", never as "on hold" — that would silently empty the
    // needs-you section for every seller on the old build.
    const o = offer({ status: 'pending', i_am_buyer: false });
    delete (o as { superseded?: boolean }).superseded;
    expect(offerNeedsMyAction(o)).toBe(true);
  });
});

/**
 * "Does this need me?" and "may I answer this?" are DIFFERENT questions, and
 * conflating them was a real bug on the trade screen (2026-08-19).
 *
 * `offerNeedsMyAction` answers the first — it drives the badge, the Home row
 * and the "needs you" section — and it deliberately returns FALSE for a
 * `superseded` bid, because a rival on a listing you already promised is not
 * urgent.
 *
 * `app/offer/[offerId].tsx` used it to gate Accept / Counter / Decline, which
 * removed those controls from a bid §1d keeps alive SPECIFICALLY so it can be
 * accepted when the first buyer ghosts. `app/offers.tsx` gates on
 * `isSeller && open` and still showed them, so the two screens disagreed about
 * what was legal.
 *
 * The trade screen now derives `mayRespond` from §1d-bis's table directly.
 * This pins the distinction the bug erased.
 */
describe('needs-me vs may-answer', () => {
  const rival = offer({ status: 'pending', i_am_buyer: false, superseded: true });

  it('a superseded bid does NOT need you — it is not urgent', () => {
    expect(offerNeedsMyAction(rival)).toBe(false);
  });

  it('...but the SELLER may still answer it, which is the whole point of §1d', () => {
    // The rule the trade screen applies: pending -> the seller answers.
    const mayRespond = (o: P2POffer) =>
      (o.status === 'pending' || o.status === 'countered')
      && (o.i_am_buyer ? o.status === 'countered' : o.status === 'pending');

    expect(mayRespond(rival)).toBe(true);
    // If these two ever agree for a superseded bid, the fallback is
    // unanswerable again.
    expect(mayRespond(rival)).not.toBe(offerNeedsMyAction(rival));
  });

  it('may-answer follows §1d-bis: pending is the seller, countered is the buyer', () => {
    const mayRespond = (o: P2POffer) =>
      (o.status === 'pending' || o.status === 'countered')
      && (o.i_am_buyer ? o.status === 'countered' : o.status === 'pending');

    expect(mayRespond(offer({ status: 'pending', i_am_buyer: false }))).toBe(true);
    expect(mayRespond(offer({ status: 'pending', i_am_buyer: true }))).toBe(false);
    expect(mayRespond(offer({ status: 'countered', i_am_buyer: true }))).toBe(true);
    expect(mayRespond(offer({ status: 'countered', i_am_buyer: false }))).toBe(false);
    // A settled trade is answerable by nobody.
    for (const status of ['accepted', 'completed', 'declined', 'cancelled']) {
      expect(mayRespond(offer({ status, i_am_buyer: false }))).toBe(false);
    }
  });
});
