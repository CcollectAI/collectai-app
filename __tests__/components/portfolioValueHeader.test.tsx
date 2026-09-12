import { render, screen } from '@testing-library/react-native';
import React from 'react';
jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: { success:'#0a0', danger:'#a00', text:'#000', muted:'#666' } }),
}));
import { PortfolioValueHeader } from '../../src/components/home/PortfolioValueHeader';
const fp = (n: number) => `€${Math.round(n)}`;
const theme = { text: '#000', muted: '#666' };
it('leads a loss with the sign, not the currency symbol', () => {
  render(<PortfolioValueHeader theme={theme} total={1348} delta={-10} deltaPct={-0.0077} currency={'EUR' as any} formatPrice={fp as any} />);
  expect(screen.getByText('-€10 (-0.77%)')).toBeTruthy();
});
it('renders a dash and no delta line when the value is unknown', () => {
  render(<PortfolioValueHeader theme={theme} total={null} delta={0} deltaPct={0} currency={'EUR' as any} formatPrice={fp as any} />);
  expect(screen.getByText('—')).toBeTruthy();
  expect(screen.queryByText(/\(0\.00%\)/)).toBeNull();
});
