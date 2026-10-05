/**
 * Market Provider Adapters
 *
 * Exports individual adapter classes and a factory function
 * that instantiates all adapters whose API keys are configured.
 */

import Constants from 'expo-constants';
import { logger } from '@/lib/logger';
import type { MarketProviderAdapter } from '../types';
import { TCGPlayerAdapter } from './tcgplayer-adapter';

// Re-export adapter classes
export { TCGPlayerAdapter } from './tcgplayer-adapter';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getEnv(key: string): string | undefined {
  const extra = Constants.expoConfig?.extra as Record<string, unknown> | undefined;
  if (extra && typeof extra[key] === 'string') {
    return extra[key] as string;
  }
  try {
    return (process.env as Record<string, string | undefined>)[key];
  } catch (e) {
    logger.error('[silent-catch] index.ts:29:', e);
    return undefined;
  }
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Create all available market provider adapters.
 *
 * Only adapters whose required API keys are present in the environment
 * will be included. Adapters without credentials are silently skipped.
 *
 * @returns Array of configured MarketProviderAdapter instances.
 *
 * @example
 * ```typescript
 * import { createAdapters } from '@/lib/marketProviders/adapters';
 *
 * const adapters = createAdapters();
 * // adapters will contain only those providers with API keys set
 * ```
 */
export function createAdapters(): MarketProviderAdapter[] {
  const adapters: MarketProviderAdapter[] = [];

  // eBay: deliberately NOT a client adapter (removed 2026-10-05). It minted
  // OAuth tokens with EBAY_CLIENT_SECRET, which must never ship in the app
  // bundle. eBay is queried server-side only (server/app/agents/adapters/ebay_caller.py).

  // TCGPlayer — requires TCGPLAYER_BEARER_TOKEN
  const tcgToken = getEnv('TCGPLAYER_BEARER_TOKEN');
  if (tcgToken) {
    adapters.push(new TCGPlayerAdapter(tcgToken));
    logger.info('[MarketAdapters] TCGPlayer adapter registered');
  } else {
    logger.debug('[MarketAdapters] TCGPlayer adapter skipped (missing credentials)');
  }

  logger.info(`[MarketAdapters] ${adapters.length} adapter(s) registered`);
  return adapters;
}
