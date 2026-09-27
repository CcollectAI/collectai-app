/**
 * An unrecognised barcode offers "Identify from a photo" (2026-09-26, free
 * barcode plan option 3). A recognised one does not.
 */
import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { BarcodeResultCard } from '../../src/components/barcode/BarcodeResultCard';

const props = (title: string | null) => ({
  lookupResult: { title, categoryId: title ? 'lego' : null, missingRequired: title ? [] : ['title'], collections: [] } as never,
  intakeResult: null,
  scannedCode: { type: 'ean13', value: '5702015869935' },
  affiliateLink: null,
  isSaving: false,
  currency: 'EUR' as never,
  hapticsEnabled: false,
  onRescan: jest.fn(),
  onSave: jest.fn(),
  onAddManually: jest.fn(),
  onAddToWatchlist: jest.fn(),
});

it('unrecognised: offers the photo fallback and calls it', () => {
  const onIdentifyByPhoto = jest.fn();
  const { getByLabelText } = render(<BarcodeResultCard {...props(null)} onIdentifyByPhoto={onIdentifyByPhoto} />);
  fireEvent.press(getByLabelText('Identify this item from a photo instead'));
  expect(onIdentifyByPhoto).toHaveBeenCalled();
});

it('recognised: no photo fallback', () => {
  const { queryByLabelText } = render(<BarcodeResultCard {...props('LEGO Millennium Falcon')} onIdentifyByPhoto={jest.fn()} />);
  expect(queryByLabelText('Identify this item from a photo instead')).toBeNull();
});

it('unrecognised: no "Identified via" line (it read "Identified via: manual", walk 2026-09-27)', () => {
  const p = { ...props(null), intakeResult: { identification_method: 'manual' } as never };
  const { queryByText } = render(<BarcodeResultCard {...p} onIdentifyByPhoto={jest.fn()} />);
  expect(queryByText(/Identified via/)).toBeNull();
});

it('recognised: says how it was identified', () => {
  const p = { ...props('LEGO Millennium Falcon'), intakeResult: { identification_method: 'barcode_learned' } as never };
  const { queryByText } = render(<BarcodeResultCard {...p} onIdentifyByPhoto={jest.fn()} />);
  expect(queryByText(/Identified via: barcode learned/)).not.toBeNull();
});
