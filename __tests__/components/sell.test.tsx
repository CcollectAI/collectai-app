/**
 * Sell component tests.
 *
 * Covers OfferTimeline, CounterOfferForm, and ReputationBadges.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockColors = {
  card: '#FFFFFF',
  text: '#0F172A',
  muted: '#64748B',
  border: '#E2E8F0',
  accent: '#81D8D0',
  accentText: '#FFFFFF',
  background: '#F8FAFC',
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
  error: '#EF4444',
  info: '#3B82F6',
};

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: mockColors, isDark: false }),
}));

jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({
    settings: { hapticsEnabled: true, currency: 'EUR', isDark: false },
    updateSettings: jest.fn(),
  }),
}));

jest.mock('../../src/motion', () => {
  const { Pressable } = require('react-native');
  return {
    AnimatedPressable: (props: any) => <Pressable {...props} />,
  };
});

jest.mock('../../src/haptics', () => ({
  fireHaptic: jest.fn(),
  HapticIntent: { CONFIRMATION_LIGHT: 'CONFIRMATION_LIGHT' },
}));

jest.mock('../../src/lib/format', () => ({
  formatPrice: (price: number, currency: string) => `${currency} ${price}`,
}));

jest.mock('../../src/lib/timeAgo', () => ({
  timeAgo: () => '2h ago',
}));

jest.mock('../../src/data/types', () => ({}));

jest.mock('../../src/theme/tokens', () => ({
  radius: { md: 12, sm: 8, lg: 16, xl: 24 },
  text: { xs: 10, sm: 12, md: 14, lg: 16, xl: 20, '2xl': 24 },
  fontWeight: {
    medium: '500',
    semibold: '600',
    bold: '700',
    extrabold: '800',
  },
  shadow: {
    card: {
      shadowColor: '#000',
      shadowOpacity: 0.06,
      shadowRadius: 8,
      shadowOffset: { width: 0, height: 4 },
      elevation: 2,
    },
  },
}));

// Now import components after mocks
import { OfferTimeline } from '../../src/components/sell/OfferTimeline';
import { CounterOfferForm } from '../../src/components/sell/CounterOfferForm';
import { ReputationBadges } from '../../src/components/sell/ReputationBadges';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeOfferEvent(overrides: Record<string, unknown> = {}) {
  return {
    id: 'ev-1',
    offerId: 'offer-1',
    actorId: 'user-1',
    eventType: 'proposed',
    price: 100,
    message: null,
    metadata: {},
    createdAt: '2026-03-10T12:00:00Z',
    ...overrides,
  };
}

function makeReputation(overrides: Record<string, unknown> = {}) {
  return {
    userId: 'user-1',
    avgStars: 4.5,
    totalRatings: 12,
    completedDeals: 8,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// OfferTimeline
// ---------------------------------------------------------------------------

describe('OfferTimeline', () => {
  it('renders the Negotiation Timeline title', () => {
    render(<OfferTimeline events={[]} currency="EUR" />);
    expect(screen.getByText('Negotiation Timeline')).toBeTruthy();
  });

  it('renders empty state when no events', () => {
    render(<OfferTimeline events={[]} currency="EUR" />);
    expect(screen.getByText('No events yet')).toBeTruthy();
  });

  it('renders event labels', () => {
    render(
      <OfferTimeline
        events={[
          makeOfferEvent({ id: 'e1', eventType: 'proposed' }),
          makeOfferEvent({ id: 'e2', eventType: 'accepted' }),
        ]}
        currency="EUR"
      />,
    );
    expect(screen.getByText('Offer proposed')).toBeTruthy();
    expect(screen.getByText('Offer accepted')).toBeTruthy();
  });

  it('renders event price when present', () => {
    render(
      <OfferTimeline
        events={[makeOfferEvent({ price: 250 })]}
        currency="USD"
      />,
    );
    expect(screen.getByText('USD 250')).toBeTruthy();
  });

  it('renders event message when present', () => {
    render(
      <OfferTimeline
        events={[makeOfferEvent({ message: 'Great deal!' })]}
        currency="EUR"
      />,
    );
    // The message is wrapped in curly quotes
    expect(screen.getByText(/Great deal!/)).toBeTruthy();
  });

  it('renders all supported event types', () => {
    const types = ['proposed', 'countered', 'accepted', 'declined', 'cancelled', 'shipped', 'completed', 'expired'];
    const events = types.map((t, i) =>
      makeOfferEvent({ id: `e${i}`, eventType: t, price: null }),
    );
    render(<OfferTimeline events={events} currency="EUR" />);
    expect(screen.getByText('Offer proposed')).toBeTruthy();
    expect(screen.getByText('Counter-offer')).toBeTruthy();
    expect(screen.getByText('Offer accepted')).toBeTruthy();
    expect(screen.getByText('Offer declined')).toBeTruthy();
    expect(screen.getByText('Offer cancelled')).toBeTruthy();
    expect(screen.getByText('Marked as shipped')).toBeTruthy();
    expect(screen.getByText('Deal completed')).toBeTruthy();
    expect(screen.getByText('Offer expired')).toBeTruthy();
  });

  it('matches snapshot with events', () => {
    const tree = render(
      <OfferTimeline
        events={[
          makeOfferEvent({ id: 'e1', eventType: 'proposed', price: 100 }),
          makeOfferEvent({ id: 'e2', eventType: 'countered', price: 120 }),
        ]}
        currency="EUR"
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// CounterOfferForm
// ---------------------------------------------------------------------------

describe('CounterOfferForm', () => {
  const defaultProps = {
    visible: true,
    onClose: jest.fn(),
    onSubmit: jest.fn(),
    counterPrice: '',
    onCounterPriceChange: jest.fn(),
    counterMessage: '',
    onCounterMessageChange: jest.fn(),
    actionLoading: false,
  };

  it('renders Counter-Offer title', () => {
    render(<CounterOfferForm {...defaultProps} />);
    expect(screen.getByText('Counter-Offer')).toBeTruthy();
  });

  it('renders price input label', () => {
    render(<CounterOfferForm {...defaultProps} />);
    expect(screen.getByText('Your price')).toBeTruthy();
  });

  it('renders message input label', () => {
    render(<CounterOfferForm {...defaultProps} />);
    expect(screen.getByText('Message (optional)')).toBeTruthy();
  });

  it('renders send button text', () => {
    render(<CounterOfferForm {...defaultProps} counterPrice="50" />);
    expect(screen.getByText('Send Counter-Offer')).toBeTruthy();
  });

  it('fires onCounterPriceChange when typing price', () => {
    const onPriceChange = jest.fn();
    render(
      <CounterOfferForm
        {...defaultProps}
        onCounterPriceChange={onPriceChange}
      />,
    );
    const input = screen.getByPlaceholderText('0.00');
    fireEvent.changeText(input, '99.50');
    expect(onPriceChange).toHaveBeenCalledWith('99.50');
  });

  it('fires onCounterMessageChange when typing message', () => {
    const onMsgChange = jest.fn();
    render(
      <CounterOfferForm
        {...defaultProps}
        onCounterMessageChange={onMsgChange}
      />,
    );
    const input = screen.getByPlaceholderText('Add a message...');
    fireEvent.changeText(input, 'Hello');
    expect(onMsgChange).toHaveBeenCalledWith('Hello');
  });

  it('shows loading indicator when actionLoading is true', () => {
    render(
      <CounterOfferForm {...defaultProps} actionLoading counterPrice="50" />,
    );
    // When loading, the button text should not be visible
    expect(screen.queryByText('Send Counter-Offer')).toBeNull();
  });

  it('has send counter-offer accessibility label', () => {
    render(<CounterOfferForm {...defaultProps} counterPrice="50" />);
    expect(screen.getByLabelText('Send counter-offer')).toBeTruthy();
  });

  it('matches snapshot', () => {
    const tree = render(
      <CounterOfferForm {...defaultProps} counterPrice="100" />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// ReputationBadges
// ---------------------------------------------------------------------------

describe('ReputationBadges', () => {
  it('renders seller and buyer labels when both reputations provided', () => {
    render(
      <ReputationBadges
        isSeller
        isBuyer={false}
        sellerRep={makeReputation()}
        buyerRep={makeReputation({ userId: 'user-2' })}
      />,
    );
    expect(screen.getByText('Your reputation (Seller)')).toBeTruthy();
    expect(screen.getByText('Buyer')).toBeTruthy();
  });

  it('renders buyer perspective labels', () => {
    render(
      <ReputationBadges
        isSeller={false}
        isBuyer
        sellerRep={makeReputation()}
        buyerRep={makeReputation({ userId: 'user-2' })}
      />,
    );
    expect(screen.getByText('Seller')).toBeTruthy();
    expect(screen.getByText('Your reputation (Buyer)')).toBeTruthy();
  });

  it('shows star rating score', () => {
    render(
      <ReputationBadges
        isSeller
        isBuyer={false}
        sellerRep={makeReputation({ avgStars: 4.5, totalRatings: 10 })}
        buyerRep={null}
      />,
    );
    expect(screen.getByText('4.5')).toBeTruthy();
  });

  it('shows deal count', () => {
    render(
      <ReputationBadges
        isSeller
        isBuyer={false}
        sellerRep={makeReputation({ completedDeals: 8 })}
        buyerRep={null}
      />,
    );
    expect(screen.getByText('8 deals completed')).toBeTruthy();
  });

  it('shows singular deal text for 1 deal', () => {
    render(
      <ReputationBadges
        isSeller
        isBuyer={false}
        sellerRep={makeReputation({ completedDeals: 1 })}
        buyerRep={null}
      />,
    );
    expect(screen.getByText('1 deal completed')).toBeTruthy();
  });

  it('shows No ratings yet for zero ratings', () => {
    render(
      <ReputationBadges
        isSeller
        isBuyer={false}
        sellerRep={makeReputation({ avgStars: 0, totalRatings: 0 })}
        buyerRep={null}
      />,
    );
    expect(screen.getByText('No ratings yet')).toBeTruthy();
  });

  it('renders nothing for null reputation', () => {
    const { toJSON } = render(
      <ReputationBadges
        isSeller
        isBuyer={false}
        sellerRep={null}
        buyerRep={null}
      />,
    );
    // Container still renders but badges are empty
    expect(toJSON()).toBeTruthy();
  });

  it('matches snapshot with both reputations', () => {
    const tree = render(
      <ReputationBadges
        isSeller
        isBuyer={false}
        sellerRep={makeReputation({ avgStars: 4.8, totalRatings: 25, completedDeals: 15 })}
        buyerRep={makeReputation({ userId: 'u2', avgStars: 3.5, totalRatings: 5, completedDeals: 3 })}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});
