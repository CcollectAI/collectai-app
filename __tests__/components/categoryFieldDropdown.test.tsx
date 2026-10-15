/**
 * Category select fields are dropdowns, not chip rows (2026-10-15, Merle:
 * "add manual should have a dropdown menu not just listed chips").
 */
import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: { accent: '#81D8D0', text: '#000', muted: '#666', border: '#eee', background: '#fff', card: '#fff' } }),
}));
jest.mock('../../src/motion', () => {
  const { Pressable } = require('react-native');
  return { AnimatedPressable: (props: any) => <Pressable {...props} /> };
});
jest.mock('../../src/haptics', () => ({ fireHaptic: jest.fn(), HapticIntent: { CONFIRMATION_LIGHT: 'x' } }));

import { CategorySpecificFields } from '../../src/components/add-manual/CategorySpecificFields';

const fields = [{ key: 'language', label: 'Language', type: 'select' as const, options: ['English', 'Japanese', 'Korean'] }];

describe('CategorySpecificFields — select fields', () => {
  it('shows one dropdown, not a chip per option', () => {
    const r = render(<CategorySpecificFields categoryLabel="Pokémon" fields={fields as any} values={{}} onChange={jest.fn()} />);
    expect(r.getByText('Select…')).toBeTruthy();
    expect(r.queryByText('Japanese')).toBeNull();   // options are in the closed sheet
  });

  it('opens the sheet and reports the chosen option', () => {
    const onChange = jest.fn();
    const r = render(<CategorySpecificFields categoryLabel="Pokémon" fields={fields as any} values={{}} onChange={onChange} />);
    fireEvent.press(r.getByLabelText('Language: Select…'));
    fireEvent.press(r.getByText('Japanese'));
    expect(onChange).toHaveBeenCalledWith('language', 'Japanese');
  });

  it('shows the chosen value in the field', () => {
    const r = render(<CategorySpecificFields categoryLabel="Pokémon" fields={fields as any} values={{ language: 'Korean' }} onChange={jest.fn()} />);
    expect(r.getByText('Korean')).toBeTruthy();
  });
});
