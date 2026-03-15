/**
 * ConditionGradeSelector — Feature-flag-gated wrapper for ConditionGradeSection
 * on the QuickScan result screen. Displays condition grade with defect annotations.
 */

import React from 'react';
import { featureFlags } from '@/config/featureFlags';
import { ConditionGradeSection } from '@/components/ConditionGradeSection';
import type { DefectAnnotation, SuggestedGrade } from '@/data/types';

type Props = {
  defects: DefectAnnotation[];
  grade: SuggestedGrade | null;
};

function ConditionGradeSelectorInner({ defects, grade }: Props) {
  if (!featureFlags.FEATURE_CONDITION_GRADING) return null;

  return <ConditionGradeSection defects={defects} grade={grade} />;
}

export const ConditionGradeSelector = React.memo(ConditionGradeSelectorInner);
