/**
 * The scan's condition grade is an ESTIMATE and must say so (2026-09-26).
 * A bare "PSA 7" under a shield icon read as an official grade, and the model
 * produced one for a flawless digital scan.
 */
import React from 'react';
import { render } from '@testing-library/react-native';
import { ConditionGradeSection } from '../../src/components/ConditionGradeSection';

it('labels the grade as an approximate AI estimate with a caveat', () => {
  const { getByText, queryByText } = render(
    <ConditionGradeSection defects={[]} grade={{ scale: 'psa', gradeValue: '7', reasoning: 'minor wear' }} />,
  );
  expect(getByText('≈ PSA')).toBeTruthy();
  expect(queryByText('PSA')).toBeNull();
  expect(getByText(/not a graded result/)).toBeTruthy();
  expect(getByText('AI condition estimate')).toBeTruthy();
});
