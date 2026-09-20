/**
 * The realised P/L card, which every member sees EMPTY today.
 *
 * `marketplace_sales` held 0 rows on production when this shipped
 * (measured 2026-09-20), so the empty state is not an edge case — it is the
 * screen. And the exclusions are the feature: `docs/COLLECTOR_DEMAND.md` §5
 * exists because a EUR 956.25 card sold for EUR 1000 looks like EUR 44 of
 * profit and is a EUR 104 LOSS. A card that quietly folded in sales with an
 * unknown basis or unrecorded postage would reproduce that error, so these
 * pin the withholding rather than the styling.
 */
import React from 'react';
import { render, screen } from '@testing-library/react-native';

jest.mock('@expo/vector-icons', () => ({
  Ionicons: ({ name, ...props }: any) => {
    const { View } = require('react-native');
    return <View testID={`icon-${name}`} {...props} />;
  },
}));

import { RealisedPLSection } from '@/components/analytics/RealisedPLSection';
import type { RealisedPL, RealisedSale } from '@/api/portfolioApi';

const sale = (o: Partial<RealisedSale> = {}): RealisedSale => ({
  id: 's1',
  item_id: 'i1',
  item_name: 'Bayou',
  category: 'mtg',
  sold_at: '2026-09-01T00:00:00Z',
  sale_price: 1000,
  currency: 'EUR',
  sale_currency: 'EUR',
  net_proceeds: 900,
  cost_basis: 956.25,
  cost_basis_known: true,
  shipping_known: true,
  profit: -56.25,
  fees: { platform: 85, payment_processing: 0, shipping: 15 },
  ...o,
});

const payload = (o: Partial<RealisedPL> = {}): RealisedPL => ({
  sales: [sale()],
  count: 1,
  total_profit: -56.25,
  total_net_proceeds: 900,
  sales_without_cost_basis: 0,
  sales_without_shipping: 0,
  ...o,
});

describe('RealisedPLSection', () => {
  it('renders nothing while the fetch is in flight — a skeleton here is indistinguishable from "you never sold anything"', () => {
    // `data` is DELIBERATELY populated: with `data={null}` this passes whether
    // or not the loading guard exists, which is a test that pins nothing.
    // Cached data plus `loading` is the real in-flight refetch case.
    const { toJSON } = render(<RealisedPLSection data={payload()} loading />);
    expect(toJSON()).toBeNull();
  });

  it('shows the empty state, not a zero, when nothing has sold', () => {
    render(<RealisedPLSection data={payload({ sales: [], count: 0 })} loading={false} />);
    expect(screen.getByText(/Nothing sold yet/i)).toBeTruthy();
  });

  it('states a LOSS as a loss — the §5 worked example', () => {
    render(<RealisedPLSection data={payload()} loading={false} />);
    // A card that printed the 1000 sale price, or the 900 net, as "profit" is
    // exactly the error this feature exists to prevent. The figure must be
    // NEGATIVE and must not be either of those.
    //
    // CENTS here: this card is the SECOND exception to money()'s 0-decimal
    // default (2026-09-20). §5's example only works with them: a EUR 956.25
    // basis on a EUR 1000 sale looks like a EUR 44 gain and is a EUR 104.05
    // loss. Separator is locale-driven, hence [.,]. Sign leads the symbol.
    // Appears twice — the headline total and the row — so getByText would
    // throw on the ambiguity rather than pass.
    expect(screen.getAllByText(/^-€56[.,]25$/).length).toBe(2);
    expect(screen.queryByText(/^€1000/)).toBeNull();
  });

  it('withholds a profit whose postage is unrecorded rather than showing a net', () => {
    render(
      <RealisedPLSection
        data={payload({
          sales: [sale({ shipping_known: false, profit: null })],
          sales_without_shipping: 1,
        })}
        loading={false}
      />,
    );
    expect(screen.getByText('—')).toBeTruthy();
    // Twice on purpose: once as the excluded-count line, once on the row —
    // getByText would throw on the ambiguity rather than pass.
    expect(screen.getAllByText(/postage not recorded/i).length).toBe(2);
  });

  it('the row shows NET PROCEEDS beside the profit, not the profit twice', () => {
    // Caught by mutation, not by writing it: a bad revert rewrote the subtitle
    // into a copy of the profit expression and all five tests stayed green,
    // so the card showed "-€56 / -€56" with the €900,00 the member was actually
    // paid nowhere on screen. A P/L figure alone is unreadable without what it
    // was measured against — the rule the Positions card states.
    render(<RealisedPLSection data={payload()} loading={false} />);
    // TWICE: once as the headline "Net proceeds", once on the row. The
    // corrupted version rendered it ONCE (the row showed the profit again), so
    // asserting mere presence passes on the bug — count is what discriminates.
    expect(screen.getAllByText(/^€900[.,]00$/).length).toBe(2);
  });

  it('counts the excluded sales instead of folding them into the headline', () => {
    render(
      <RealisedPLSection
        data={payload({
          sales: [sale({ cost_basis_known: false, profit: null })],
          sales_without_cost_basis: 1,
        })}
        loading={false}
      />,
    );
    expect(screen.getByText(/excluded/i)).toBeTruthy();
  });
});
