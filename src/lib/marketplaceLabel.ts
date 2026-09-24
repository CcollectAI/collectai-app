/**
 * The name to SHOW for a marketplace. Brand names are proper nouns and stay as
 * they are ("eBay", "Cardmarket"); Sparrow's own marketplace is a description,
 * so it is translated: "Sparrow Collect Marketplace" / "Sparrow Collect
 * Marktplaats" / … (Merle, 2026-09-24 — it was "Sparrow P2P").
 */
type TFn = (key: string, opts?: Record<string, unknown>) => string;

const SPARROW_IDS = new Set(['sparrow', 'sparrow_p2p', 'collectai']);

export function marketplaceLabel(id: string | null | undefined, fallback: string | undefined, t: TFn): string {
  if (id && SPARROW_IDS.has(id)) {
    return t('marketplace.sparrow_name', { defaultValue: 'Sparrow Collect Marketplace' });
  }
  return fallback ?? id ?? '';
}
