/**
 * useItemGrading — manages grading service lookup, cert verification, and population reports.
 */

import { useState, useCallback } from 'react';
import { collectorsApi } from '@/api/collectorsApi';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import logger from '@/utils/logger';
import type { GradingLookupResult, PopulationReport, GradingServiceInfo } from '@/components/GradingSection';

export function useItemGrading(categorySlug: string, itemName: string) {
  const { settings } = useSettings();
  const { showToast } = useToast();

  const [gradingExpanded, setGradingExpanded] = useState(false);
  const [gradingLookupResult, setGradingLookupResult] = useState<GradingLookupResult | null>(null);
  const [gradingLookupLoading, setGradingLookupLoading] = useState(false);
  const [gradingPopulation, setGradingPopulation] = useState<PopulationReport | null>(null);
  const [gradingPopLoading, setGradingPopLoading] = useState(false);
  const [gradingServices, setGradingServices] = useState<GradingServiceInfo[]>([]);
  const [gradingModalVisible, setGradingModalVisible] = useState(false);
  const [gradingCertInput, setGradingCertInput] = useState('');
  const [gradingServicePick, setGradingServicePick] = useState<'psa' | 'cgc' | 'bgs' | 'beckett'>('psa');

  const loadGradingServices = useCallback(async () => {
    if (gradingServices.length > 0) return;
    try {
      const data = await collectorsApi.gradingServices(categorySlug);
      setGradingServices(data.services || []);
    } catch (err) {
      logger.error('[useItemGrading] services fetch error:', err);
    }
  }, [categorySlug, gradingServices.length]);

  const handleGradingLookup = useCallback(async () => {
    if (!gradingCertInput.trim()) {
      showToast({ message: 'Please enter a certification number', type: 'warning' });
      return;
    }
    setGradingLookupLoading(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    try {
      const result = await collectorsApi.gradingLookup(gradingCertInput.trim(), gradingServicePick);
      setGradingLookupResult(result);
      setGradingModalVisible(false);
      if (result.cert_verified) {
        showToast({ message: `Verified: ${result.service_name} ${result.grade}`, type: 'success' });
      } else {
        showToast({ message: 'Certificate not found or not verified', type: 'warning' });
      }
    } catch (err) {
      logger.error('[useItemGrading] lookup error:', err);
      showToast({ message: 'Failed to look up certificate', type: 'error' });
    } finally {
      setGradingLookupLoading(false);
    }
  }, [gradingCertInput, gradingServicePick, settings.hapticsEnabled, showToast]);

  const loadGradingPopulation = useCallback(async () => {
    if (!itemName || gradingPopulation) return;
    setGradingPopLoading(true);
    try {
      const data = await collectorsApi.gradingPopulation(itemName, categorySlug);
      setGradingPopulation(data);
    } catch (err) {
      logger.error('[useItemGrading] population error:', err);
    } finally {
      setGradingPopLoading(false);
    }
  }, [itemName, categorySlug, gradingPopulation]);

  return {
    gradingExpanded, setGradingExpanded,
    gradingLookupResult, setGradingLookupResult,
    gradingLookupLoading,
    gradingPopulation, setGradingPopulation,
    gradingPopLoading,
    gradingServices,
    gradingModalVisible, setGradingModalVisible,
    gradingCertInput, setGradingCertInput,
    gradingServicePick, setGradingServicePick,
    loadGradingServices,
    handleGradingLookup,
    loadGradingPopulation,
  };
}
