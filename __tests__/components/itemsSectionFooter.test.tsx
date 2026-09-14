/**
 * The Items tab's per-category footer.
 *
 * Walked on Android 2026-09-14: three of four sections held ONE item and each
 * printed "Collection total €900" directly under that item's own "€900" — the
 * same number twice — in English on every locale. A one-item section now has no
 * footer; a multi-item one says "Total" through i18n.
 */
import React from 'react';
import { render } from '@testing-library/react-native';
import { ItemsSectionFooter } from '@/components/items/ItemsSectionFooter';

jest.mock('@/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: { muted: '#888', text: '#000' } }),
}));

describe('ItemsSectionFooter', () => {
  it('renders nothing for a one-item section (the row already shows that price)', () => {
    const { toJSON } = render(<ItemsSectionFooter total={900} count={1} />);
    expect(toJSON()).toBeNull();
  });

  it('shows the translated total for a section with more than one item', () => {
    const { getByText, queryByText } = render(<ItemsSectionFooter total={145} count={2} />);
    expect(getByText('Total')).toBeTruthy();
    expect(queryByText('Collection total')).toBeNull();
  });
});
