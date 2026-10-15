/**
 * The "How Scores Work" sheet must not score what the card refuses to score.
 * Walked 2026-10-15: the Portfolio Tier card showed Completeness "—" (no set we
 * hold a catalogue entry for) while this sheet showed "0/100 Getting started",
 * two lines above its own rule "Skipped, not counted as 0%".
 */
import React from 'react';
import { render } from '@testing-library/react-native';

jest.mock('@expo/vector-icons', () => ({ Ionicons: () => null }));
jest.mock('@/haptics', () => ({ fireHaptic: jest.fn(), HapticIntent: { CONFIRMATION_LIGHT: 'x' } }));
jest.mock('@/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: { text: '#000', muted: '#888', card: '#fff', border: '#ddd', accent: '#0aa', success: '#0a0', warning: '#fa0', background: '#fff' },
  }),
}));
jest.mock('../../src/components/BottomSheetModal', () => ({
  BottomSheetModal: ({ children }: { children: React.ReactNode }) => children,
}));

import { ScoreExplanationSheet } from '@/components/ScoreExplanationSheet';

it('shows an unscored score as a dash, never 0/100', () => {
  const { getAllByText, queryByText } = render(
    <ScoreExplanationSheet
      visible
      onClose={jest.fn()}
      rarityScore={0.87}
      completenessScore={0}
      diversificationScore={0.56}
      unscored={{ completeness: true }}
      tier="Silver"
    />,
  );
  expect(getAllByText('—')).toHaveLength(1);
  expect(queryByText('Not scored yet')).not.toBeNull();
  expect(queryByText('0')).toBeNull();
  expect(queryByText('87')).not.toBeNull();
});

it('still shows a real 0 when the score was measured', () => {
  const { queryByText } = render(
    <ScoreExplanationSheet visible onClose={jest.fn()} rarityScore={0.87} completenessScore={0} diversificationScore={0.56} />,
  );
  expect(queryByText('0')).not.toBeNull();
  expect(queryByText('Not scored yet')).toBeNull();
});
