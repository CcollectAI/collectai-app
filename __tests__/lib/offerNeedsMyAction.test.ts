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
