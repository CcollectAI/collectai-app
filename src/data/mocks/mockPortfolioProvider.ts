/**
 * Mock portfolio domain provider.
 */

import type { PortfolioSummary } from '../types';
import {
  MOCK_ANALYTICS_SUMMARY,
} from '../../mockData';

export async function getPortfolioSummary(): Promise<PortfolioSummary> {
  return {
    total: MOCK_ANALYTICS_SUMMARY.totalValue,
    deltaPct: MOCK_ANALYTICS_SUMMARY.avgChangePct7d,
    itemCount: MOCK_ANALYTICS_SUMMARY.totalItems,
  };
}
