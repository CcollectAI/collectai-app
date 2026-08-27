/**
 * CategorySpecificSection — the gate must admit exactly what the body draws.
 *
 * Reported from a screenshot: a bordered "LEGO Details" heading with a yellow
 * cube icon and nothing under it. The block was gated on the category alone
 * while both of its children were gated on attributes the item did not have.
 *
 * Rendered, not reasoned about: a gate is only proven by mounting it with the
 * attributes absent and finding no heading.
 */
import React from 'react';
import { render } from '@testing-library/react-native';
import { CategorySpecificSection } from '@/components/CategorySpecificSection';

jest.mock('@/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
      background: '#fff', card: '#fff', text: '#000', muted: '#888', border: '#ddd',
      accent: '#40C9C6', success: '#059669', danger: '#EF4444', warning: '#F59E0B',
      warningBg: '#FEF3C7', error: '#EF4444',
      brand: { base: '#81D8D0', dark: '#5FBFB6', darker: '#44A9A1', light: '#AEE6E1', lighter: '#E6F7F5' },
    },
  }),
}));
jest.mock('@/lib/settings', () => ({
  useSettings: () => ({ settings: { hapticsEnabled: false }, updateSettings: jest.fn(), ready: true }),
}));

const theme = {
  text: '#000', muted: '#888', border: '#ddd', accent: '#40C9C6',
  card: '#fff', background: '#fff', success: '#059669', error: '#EF4444', warning: '#F59E0B',
} as never;

const base = { theme, notes: '', hapticsEnabled: false } as never;

describe('category sections do not render an empty heading', () => {
  it('LEGO: no heading when the item has neither attribute', () => {
    const { queryByText } = render(
      <CategorySpecificSection {...base} categorySlug="lego" itemAttributes={{}} />,
    );
    expect(queryByText('LEGO Details')).toBeNull();
  });

  it('LEGO: heading DOES appear once an attribute exists', () => {
    // The other half of the gate — a rule that only ever hides is not a gate.
    const { queryByText } = render(
      <CategorySpecificSection {...base} categorySlug="lego" itemAttributes={{ set_number: '75192' }} />,
    );
    expect(queryByText('LEGO Details')).toBeTruthy();
  });

  it('Comics: no heading when the item has none of its attributes', () => {
    const { queryByText } = render(
      <CategorySpecificSection {...base} categorySlug="comic_books" itemAttributes={{}} />,
    );
    expect(queryByText('Comic Details')).toBeNull();
  });

  it('Comics: heading appears for a graded issue', () => {
    const { queryByText } = render(
      <CategorySpecificSection {...base} categorySlug="comic_books" itemAttributes={{ grade: '9.8' }} />,
    );
    expect(queryByText('Comic Details')).toBeTruthy();
  });

  it('an unknown category renders nothing at all', () => {
    const { toJSON } = render(
      <CategorySpecificSection {...base} categorySlug="not_a_category" itemAttributes={{}} />,
    );
    const tree = toJSON();
    // Either null, or a wrapper with no children — never a bordered shell.
    expect(tree === null || (Array.isArray(tree) ? tree : [tree]).every((n) => !n?.children?.length)).toBe(true);
  });
});
