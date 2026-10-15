/**
 * Android's Alert.alert shows at most three buttons. Walked 2026-10-15: the
 * carrier picker offered 3 of 10 carriers and no Cancel; the sell form's
 * Category picker the first 3 of 50+.
 */
import React from 'react';
import { Alert, Platform } from 'react-native';
import { render, fireEvent, act } from '@testing-library/react-native';

jest.mock('@/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: { card: '#fff', text: '#000', border: '#ddd', accent: '#0aa' } }),
}));

import { ActionSheetHost } from '@/components/ActionSheetHost';
import { showActionSheet } from '@/hooks/useActionSheetPicker';

const CARRIERS = ['PostNL', 'DPD', 'GLS', 'bpost', 'DHL', 'UPS', 'Hermes', 'Colissimo', 'Correos', 'Poste'];

beforeAll(() => { Object.defineProperty(Platform, 'OS', { get: () => 'android' }); });

it('offers every option and a Cancel, not the three an Alert can show', () => {
  const alertSpy = jest.spyOn(Alert, 'alert');
  const onSelect = jest.fn();
  const { getByText, queryByText } = render(<ActionSheetHost />);
  act(() => { showActionSheet('Carrier', CARRIERS, onSelect); });
  for (const c of CARRIERS) expect(getByText(c)).toBeTruthy();
  expect(getByText('Cancel')).toBeTruthy();
  fireEvent.press(getByText('Hermes'));
  expect(onSelect).toHaveBeenCalledWith(6);
  expect(alertSpy).not.toHaveBeenCalled();
  expect(queryByText('DHL')).toBeNull(); // closed after the pick
});

it('Cancel calls onCancel and picks nothing', () => {
  const onSelect = jest.fn();
  const onCancel = jest.fn();
  const { getByText } = render(<ActionSheetHost />);
  act(() => { showActionSheet('Condition', ['Mint', 'Near Mint', 'Played', 'Damaged'], onSelect, onCancel); });
  fireEvent.press(getByText('Cancel'));
  expect(onCancel).toHaveBeenCalled();
  expect(onSelect).not.toHaveBeenCalled();
});
