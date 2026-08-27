/**
 * useItemMarketplace — manages marketplace search results, affiliate links, and dossier data.
 */

import { useState, useEffect, useCallback } from 'react';
import { collectorsApi } from '@/api/collectorsApi';
import { useToast } from '@/components/Toast';
import logger from '@/utils/logger';
import type { MarketHit } from '@/components/MarketplacePricesSection';
import type { DossierData } from '@/components/DossierReportSection';
import { filterComps } from '@/lib/marketHitSanity';

type AffiliateLink = { source: string; url: string; affiliate_url: string; label: string };

export function useItemMarketplace(
  itemId: string | undefined,
  isDraft: boolean,
  itemName: string,
  category: string,
  /** The item's own valuation, used ONLY as a sanity reference for comps.
   *  Optional: an unpriced item must still get its comp list. */
  itemValue?: number | null,
) {
  const { showToast } = useToast();

  // Marketplace state
  const [marketResults, setMarketResults] = useState<MarketHit[]>([]);
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketExpanded, setMarketExpanded] = useState(false);
  const [marketScannedAt, setMarketScannedAt] = useState<string | null>(null);
  const [marketError, setMarketError] = useState(false);

  // Affiliate links
  const [affiliateLinks, setAffiliateLinks] = useState<AffiliateLink[]>([]);

  // Dossier state
  const [dossierData, setDossierData] = useState<DossierData | null>(null);
  const [dossierLoading, setDossierLoading] = useState(false);
  const [dossierExpanded, setDossierExpanded] = useState(false);
  const [dossierError, setDossierError] = useState(false);

  // Provenance ("Item History") removed 2026-07-22 — the standalone section was
  // a subset of the dossier (which already returns provenance[]) and empty for
  // virtually every item, so we no longer fetch it here. The /provenance BE
  // endpoint stays; restore the state + fetch + return if the section comes back.

  // Fetch affiliate links on mount
  useEffect(() => {
    if (!itemId || isDraft || !itemName || itemName === 'Unknown item') return;
    collectorsApi.getAffiliateLinks(itemName, category)
      .then((data) => setAffiliateLinks(data.links))
      .catch((err) => logger.warn('[useItemMarketplace] affiliate links error:', err));
  }, [itemId, isDraft, itemName, category]);

  const loadMarketResults = useCallback(async () => {
    if (!itemName) return;
    setMarketLoading(true);
    setMarketError(false);
    try {
      const data = await collectorsApi.marketplaceSearch(itemName, { category }) as { results?: MarketHit[]; hits?: MarketHit[] };
      const raw = data.results || data.hits || [];
      // A member must never be the thing that catches a scraped page counter
      // filed as a price. Reported 2026-08-27: a crawl4ai row titled "Site
      // Statistics" rendered at EUR 1,620,277,371 in this very section, on the
      // Pro tier. This path had no bound of any kind — it rendered whatever
      // the endpoint returned.
      // SANITY *and* RELEVANCE. `marketplaceSearch` is a keyword search, so it
      // returns other products: the reported screen showed five suruga_ya rows
      // under a Japanese vinyl record, three of which were entirely different
      // records, beneath an EUR 8,015 estimate that every visible row
      // contradicted. Comps shown under a valuation are read as EVIDENCE for
      // it, so anything that is not this item has to go.
      const { kept: results, droppedImplausiblePrice, droppedIrrelevant } =
        filterComps(raw, itemName, itemValue);
      if (droppedImplausiblePrice > 0) {
        // logger.error, not warn: warn is stripped in release builds, and a
        // silently-filtered row is exactly the signal that tells us an adapter
        // is producing junk. The display is fixed here; the SOURCE is not.
        logger.error(
          `[useItemMarketplace] dropped ${droppedImplausiblePrice} implausible comp(s) of ${raw.length} for "${itemName}" — an adapter is returning non-prices`,
        );
      }
      // Separate line, separate cause: this one is the SEARCH returning other
      // products, not an adapter emitting non-prices. Collapsing them would
      // hide which is happening.
      if (droppedIrrelevant > 0) {
        logger.error(
          `[useItemMarketplace] dropped ${droppedIrrelevant} irrelevant comp(s) of ${raw.length} for "${itemName}" — keyword search returned other products`,
        );
      }
      setMarketResults(results);
      setMarketScannedAt(new Date().toISOString());
      setMarketExpanded(true);
    } catch (err) {
      logger.error('[useItemMarketplace] search error:', err);
      setMarketResults([]);
      setMarketError(true);
      setMarketScannedAt(new Date().toISOString());
      setMarketExpanded(true);
    } finally {
      setMarketLoading(false);
    }
  }, [itemName, category, itemValue]);

  const loadDossier = useCallback(async () => {
    if (!itemId || isDraft) return;
    setDossierLoading(true);
    setDossierError(false);
    try {
      const data = await collectorsApi.getDossier(itemId);
      setDossierData(data || null);
      setDossierExpanded(true);
    } catch (err) {
      logger.error('[useItemMarketplace] dossier error:', err);
      setDossierData(null);
      setDossierError(true);
      setDossierExpanded(true);
    } finally {
      setDossierLoading(false);
    }
  }, [itemId, isDraft]);

  return {
    // Marketplace
    marketResults, marketLoading, marketExpanded, setMarketExpanded,
    marketScannedAt, marketError, loadMarketResults,
    // Affiliate
    affiliateLinks,
    // Dossier
    dossierData, dossierLoading, dossierExpanded, setDossierExpanded,
    dossierError, loadDossier,
  };
}
