/**
 * A found name is "not in our catalogue", not "unrecognised" (walk 2026-09-27:
 * an ISBN read as "Product Found — Harry Potter…" opened a sheet saying
 * "We don't recognize this item yet").
 */
import React from 'react';
import { render } from '@testing-library/react-native';
jest.mock('@/components/Toast', () => ({ useToast: () => ({ showToast: jest.fn() }) }));
jest.mock('@/api/collectorsApi', () => ({ collectorsApi: {} }));
import CatalogSuggestionModal from '../../src/components/CatalogSuggestionModal';

it('with a found name: "Not in our catalogue yet"', () => {
  const { queryByText } = render(
    <CatalogSuggestionModal visible onDismiss={jest.fn()} source="barcode" prefillName="Harry Potter and the sorcerer's stone" />,
  );
  expect(queryByText('Not in our catalogue yet')).not.toBeNull();
  expect(queryByText("We don't recognize this item yet")).toBeNull();
});

it('with nothing found: "We don\'t recognize this item yet"', () => {
  const { queryByText } = render(<CatalogSuggestionModal visible onDismiss={jest.fn()} source="barcode" />);
  expect(queryByText("We don't recognize this item yet")).not.toBeNull();
});
