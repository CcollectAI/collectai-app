/**
 * Items domain provider — CRUD operations on collection items + quickscan.
 */

import { API_LIMITS } from '@/constants/apiLimits';
import type {
  CurrencyCode,
  PaginationParams,
  Item,
  CreateItemInput,
  QuickScanResult,
  QuickscanDraft,
  PersistedItem,
} from '../types';
import { supabase } from '../../lib/supabase';
import { collectorsApi } from '../../api/collectorsApi';
import { withTimeout, TimeoutError } from '../../lib/withTimeout';
import logger from '../../utils/logger';

// The Items tab gates its skeleton on this query resolving. supabase-js ships
// NO per-request timeout, so a stalled TLS handshake / captive portal / server
// hang leaves the promise pending forever — usePaginatedList only clears
// isLoading in its `finally`, so the skeleton stays up with no error and no
// retry. That is the "stuck on skeleton" report, and it is exactly what
// src/lib/withTimeout.ts was written for: "Use on direct supabase queries in
// loading-gating paths." chatProvider / categoryProvider / userProvider /
// watchlistProvider all do this; itemsProvider was the one that did not.
const ITEMS_READ_TIMEOUT_MS = 8_000;

// Shared row types used by listItems and searchItems.
// items has the columns id/title/category/updated_at/attrs/image_url/
// collection_name. The earlier shape referenced `images` (plural array),
// `collections` (plural), `taxonomy_version`, `subtype_id` — none of which
// exist on the items table. PostgREST returned a 400 on every listItems
// call and the catch silently returned []. Found by audit_full_chain.py
// 2026-05-01. subtype_id and taxonomy_version live in items.attrs (jsonb)
// when present, so we read them out of attrs in mapItemRow instead of
// asking PostgREST for them as bare columns.
// quick_predictions is the per-item-id prediction table. It IS FK-linked to
// items.id, so PostgREST can resolve the embed. The richer price_predictions
// table joins by item_ref/canonical_key with no FK and can't be embedded —
// PostgREST returned PGRST200 "Could not find a relationship" for months,
// silently making listItems return []. Confirmed via live probe 2026-05-01.
// q10/q90/asof aren't available here; the list view only consumes q50, so
// the loss is invisible. Detail screens that need the band query
// price_predictions separately by canonical_key.
type PredRow = { q50_eur: number | null; confidence: number | null; created_at: string | null };
type ItemRow = {
  id: string;
  title?: string | null;
  category?: string | null;
  updated_at?: string | null;
  attrs?: Record<string, unknown> | null;
  collection_name?: string | null;
  image_url?: string | null;
  // Rich detail columns (schema-lock-confirmed). Written by POST /items and
  // the add-manual insert (2026-07-15 enrichment); surfaced on the card so an
  // enriched item lands as a full card instead of just name + price.
  condition?: string | null;
  brand?: string | null;
  year?: number | null;
  series?: string | null;
  edition_label?: string | null;
  // Acquisition columns. Schema-lock-confirmed (scripts/schema.lock.json):
  // items has both purchase_price (raw, in purchase_currency) and
  // purchase_price_eur (FX-normalized for analytics). We only need the EUR
  // form on the list row; raw + currency are kept for the future detail view.
  purchase_price_eur?: number | null;
  purchase_currency?: string | null;
  purchased_at?: string | null;
  purchase_notes?: string | null;
  // The item's own value, captured by the add flow (user estimate / scan /
  // catalog). The card shows quick_predictions.q50_eur when a model valuation
  // exists, and falls back to these so a just-added item shows its value
  // immediately instead of 0.
  estimated_value?: number | null;
  predicted_price_eur?: number | null;
  quick_predictions?: PredRow[];
};

function mapItemRow(r: ItemRow): Item {
  // Prefer the most recently generated quick_prediction. created_at is an
  // ISO string so a string compare gives the right order.
  const preds = (r.quick_predictions ?? []).sort(
    (a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''),
  );
  const latest = preds[0];
  // Card value: prefer a model prediction; fall back to the value the add
  // flow captured so every method shows a price immediately (quick_predictions
  // is populated asynchronously / for canonical-linked items).
  const fallbackValue = (r.predicted_price_eur ?? r.estimated_value) ?? undefined;
  const cardValue = (typeof latest?.q50_eur === 'number' ? latest.q50_eur : undefined) ?? fallbackValue ?? 0;
  const attrs = r.attrs ?? undefined;
  // subtype_id + taxonomy_version were originally bare columns; they now
  // live inside the attrs jsonb when set. Fall back to undefined when missing.
  const attrsObj = (attrs as Record<string, unknown> | undefined) ?? undefined;
  const subtypeId = (attrsObj?.subtype_id as string | undefined) ?? undefined;
  const taxonomyVersion = (attrsObj?.taxonomy_version as string | undefined) ?? undefined;
  // The collection_name column is a single string; the FE type expects an
  // array `collections`. Wrap when present.
  const collections = r.collection_name ? [r.collection_name] : undefined;

  return {
    id: r.id,
    name: r.title ?? 'Untitled',
    category: r.category || 'Uncategorized',
    subtypeId,
    taxonomyVersion,
    collections,
    attributesJson: attrs,
    price: cardValue,
    // quick_predictions only stores a single point estimate (q50_eur), not
    // a quantile band. Synthesize a degenerate band from q50 alone so
    // downstream consumers that check `priceBand?.confidence` still work.
    // Detail screens needing the real band fetch from price_predictions
    // by canonical_key separately.
    priceBand: latest && typeof latest.q50_eur === 'number'
      ? { q10: latest.q50_eur, q50: latest.q50_eur, q90: latest.q50_eur, confidence: latest.confidence ?? 0, currency: 'EUR' }
      : typeof fallbackValue === 'number'
        ? { q10: fallbackValue, q50: fallbackValue, q90: fallbackValue, confidence: 0, currency: 'EUR' }
        : undefined,
    imageUrl: r.image_url ?? undefined,
    updatedAt: r.updated_at ?? undefined,
    condition: r.condition ?? undefined,
    brand: r.brand ?? undefined,
    year: typeof r.year === 'number' ? r.year : undefined,
    series: r.series ?? undefined,
    editionLabel: r.edition_label ?? undefined,
    purchasePriceEur: r.purchase_price_eur ?? null,
    purchaseCurrency: (r.purchase_currency as Item['purchaseCurrency']) ?? null,
    purchasedAt: r.purchased_at ?? null,
    purchaseNotes: r.purchase_notes ?? null,
  };
}

const ITEMS_SELECT = 'id, title, category, updated_at, attrs, collection_name, image_url, condition, brand, year, series, edition_label, estimated_value, predicted_price_eur, purchase_price_eur, purchase_currency, purchased_at, purchase_notes, quick_predictions(q50_eur, confidence, created_at)';

export async function listItems(pagination?: PaginationParams): Promise<Item[]> {
  const limit = pagination?.limit ?? API_LIMITS.ITEMS_DEFAULT;
  const offset = pagination?.offset ?? 0;
  let data: unknown;
  let error: unknown;
  try {
    const res = await withTimeout(
      supabase
        .from('items')
        .select(ITEMS_SELECT)
        .order('updated_at', { ascending: false })
        .range(offset, offset + limit - 1),
      ITEMS_READ_TIMEOUT_MS,
      'listItems',
    );
    data = res.data;
    error = res.error;
  } catch (e) {
    if (e instanceof TimeoutError) {
      // Surface as an ERROR, not a warn: logger.info/warn are stripped in
      // TestFlight/production builds, so a warn here would be invisible on the
      // exact build where this matters most.
      logger.error('[SupabaseDataProvider] listItems timed out after %dms', ITEMS_READ_TIMEOUT_MS);
      return [];
    }
    throw e;
  }

  if (error) {
    logger.warn('[SupabaseDataProvider] listItems error:', error);
    return [];
  }

  return ((data ?? []) as ItemRow[]).map(mapItemRow);
}

export async function createItem(input: CreateItemInput): Promise<Item> {
  // Server contract (ItemCreateRequest): name, category?, collection_name?,
  // estimated_value?, notes?, canonical_key?, image_url?, brand?, condition?,
  // year?, series?, edition_label?, attrs?. Server stores `name` as
  // items.title internally. `attrs` carries the category-specific attributes
  // (rarity/set_code/edition/…) plus subtype_id/taxonomy_version (which the
  // read path maps back out of attrs).
  const attrs: Record<string, unknown> = {
    ...(input.attributes ?? {}),
    ...(input.subtypeId ? { subtype_id: input.subtypeId } : {}),
    ...(input.taxonomyVersion ? { taxonomy_version: input.taxonomyVersion } : {}),
  };
  let row: Record<string, unknown>;
  try {
    row = await collectorsApi.post<Record<string, unknown>>('/items', {
      name: input.name,
      category: input.category,
      estimated_value: input.price || undefined,
      collection_name: input.collections?.[0],
      notes: input.notes,
      canonical_key: input.canonicalKey,
      image_url: input.imageUrl,
      brand: input.brand,
      condition: input.condition,
      year: input.year,
      series: input.series,
      edition_label: input.editionLabel,
      attrs: Object.keys(attrs).length ? attrs : undefined,
    });
  } catch (e) {
    logger.error('[SupabaseDataProvider] createItem error:', e);
    throw e instanceof Error ? e : new Error('Failed to create item');
  }
  // Server's ItemResponse returns `image_url` (singular). The earlier
  // `images` array was never populated; readers got `undefined`.
  const imageUrl = (row.image_url as string | null) ?? null;
  const itemId = row.id as string;

  // Push-engagement loop: if the user added this item shortly after
  // tapping a notification (e.g. drop alert → "I got it"), attribute the
  // outcome back. emitOutcome no-ops when no recent tap exists.
  try {
    // Lazy import to keep this provider tree-shakeable.
    const { emitOutcome } = await import('@/lib/notificationOutcomeTracker');
    emitOutcome('added', { item_id: itemId });
  } catch (e) {
    logger.error('[silent-catch] itemsProvider.ts:219:', e);
    // Tracker import failed — best-effort, ignore.
  }

  return {
    // Server's ItemResponse returns `name` (API field), not `title`.
    id: itemId,
    name: (row.name as string | null) ?? input.name,
    category: (row.category as string | null) ?? input.category,
    price: 0,
    imageUrl: imageUrl ?? undefined,
    updatedAt: (row.updated_at as string | null) ?? undefined,
  };
}

export async function deleteItem(itemId: string): Promise<void> {
  const { error } = await supabase
    .from('items')
    .delete()
    .eq('id', itemId);

  if (error) {
    logger.error('[SupabaseDataProvider] deleteItem error:', error);
    throw new Error(error.message || 'Failed to delete item');
  }
}

export async function updateItem(itemId: string, patch: Partial<Pick<Item, 'name' | 'category' | 'price' | 'imageUrl'>> & { notes?: string | null }): Promise<Item> {
  const updatePayload: Record<string, unknown> = {};
  // BOTH halves. items carries name and title as a pair and different readers
  // key on different ones (docs/ARCHITECTURE.md). Writing only `title` left
  // `name` at its old value, so renaming an item made the two diverge — the
  // Home portfolio kept showing the old name. trg_items_sync_paired_columns
  // only fills a half that is NULL, so it cannot repair an UPDATE like this.
  if (patch.name !== undefined) {
    updatePayload.title = patch.name;
    updatePayload.name = patch.name;
  }
  if (patch.category !== undefined) updatePayload.category = patch.category;
  // items has `image_url` (singular text), not `images` (array). The earlier
  // shape wrote `images: [url]` which silently failed on every save.
  if (patch.imageUrl !== undefined) updatePayload.image_url = patch.imageUrl ?? null;
  // notes added 2026-08-07. The item-detail notes editor previously called an
  // onSaveNotes that was a 300ms setTimeout writing NOTHING, while toasting
  // "Notes saved locally" — so every note a user typed was lost on unmount.
  // Empty string is stored as NULL so "cleared" and "never set" are the same
  // state rather than two.
  if (patch.notes !== undefined) updatePayload.notes = patch.notes?.trim() ? patch.notes : null;

  const { data, error } = await supabase
    .from('items')
    .update(updatePayload)
    .eq('id', itemId)
    .select('id, title, category, updated_at, image_url')
    .single();

  if (error || !data) {
    logger.error('[SupabaseDataProvider] updateItem error:', error);
    throw new Error(error?.message || 'Failed to update item');
  }

  return {
    id: data.id,
    name: (data as Record<string, unknown>).title as string ?? 'Untitled',
    category: data.category,
    price: 0,
    imageUrl: ((data as Record<string, unknown>).image_url as string | null) ?? undefined,
    updatedAt: (data as Record<string, unknown>).updated_at as string,
  };
}

// items.archived is a dedicated boolean column; flip it directly under
// RLS. (The earlier RPC + jsonb-stuffing fallback referenced columns
// that don't exist on this table — see commit fixing items.attrs.)
export async function archiveItem(itemId: string): Promise<void> {
  const { error } = await supabase
    .from('items')
    .update({ archived: true })
    .eq('id', itemId);

  if (error) {
    logger.error('[SupabaseDataProvider] archiveItem error:', error);
    throw new Error(error.message || 'Failed to archive item');
  }
}

export async function unarchiveItem(itemId: string): Promise<void> {
  const { error } = await supabase
    .from('items')
    .update({ archived: false })
    .eq('id', itemId);

  if (error) {
    logger.error('[SupabaseDataProvider] unarchiveItem error:', error);
    throw new Error(error.message || 'Failed to unarchive item');
  }
}

export async function persistQuickscanDraft(input: QuickscanDraft): Promise<PersistedItem> {
  // Server contract: ItemCreateRequest takes `name` (not `title`),
  // category, collection_name, estimated_value, notes, canonical_key.
  // attributes go through a follow-up PATCH /items/{id}/attributes;
  // images via POST /items/{id}/images. Sending `title`/`image_url`/`attrs`
  // here was rejected with 422 (missing `name`).
  // canonical_key (catalog-match key) is forwarded so downstream Premium
  // JOINs (price_trend, item_history, dossier) can find the catalog row.
  let row: Record<string, unknown>;
  try {
    row = await collectorsApi.post<Record<string, unknown>>('/items', {
      name: input.title ?? 'Untitled Scan',
      category: input.categoryId ?? 'uncategorized',
      notes: input.notes ?? null,
      canonical_key: input.canonicalKey ?? null,
    });
  } catch (e) {
    logger.error('[SupabaseDataProvider] persistQuickscanDraft error:', e);
    throw e instanceof Error ? e : new Error('Failed to persist QuickScan draft');
  }
  const itemId = row.id as string;

  // Land any captured attributes onto items.attrs via the PATCH
  // endpoint (the server's POST /items doesn't accept attrs).
  if (input.attributes && Object.keys(input.attributes).length > 0) {
    try {
      await collectorsApi.patch(`/items/${encodeURIComponent(itemId)}/attributes`, {
        attributes: input.attributes,
      });
    } catch (e) {
      logger.error('[SupabaseDataProvider] persistQuickscanDraft attrs PATCH failed (non-fatal):', e);
    }
  }

  const images = (row.images as string[] | null) ?? null;
  return {
    id: row.id as string,
    title: (row.title as string | null) ?? input.title ?? 'Untitled Scan',
    categoryId: (row.category as string | null) ?? input.categoryId ?? 'uncategorized',
    createdAt: (row.created_at as string | null) ?? new Date().toISOString(),
    imageUrl: images?.[0] ?? null,
  };
}

export async function quickscanSingle(imageUri?: string): Promise<QuickScanResult> {
  // ── Vision pipeline path (preferred when image is available) ────────
  if (imageUri) {
    const intake = await collectorsApi.intakeImageOnly(imageUri);

    const priceBand = intake.price_band;
    const q10 = priceBand?.q10 ?? 0;
    const q50 = priceBand?.q50 ?? (intake.estimated_price ?? 0);
    const q90 = priceBand?.q90 ?? 0;
    const confidence = priceBand?.confidence ?? intake.category_confidence ?? 0;
    const currency = (priceBand?.currency as CurrencyCode) ?? 'EUR';

    const condition = (intake.attributes?.condition as string | undefined)
      ?? (intake.attributes?.condition_guess as string | undefined)
      ?? null;

    const alternatives = (intake.alternatives ?? []).map((alt) => ({
      catalogItemId: alt.catalog_item_id ?? null,
      itemKey: alt.item_key ?? null,
      title: alt.title ?? null,
      category: alt.category ?? null,
      brand: alt.brand ?? null,
      rarity: alt.rarity ?? null,
      setCode: alt.set_code ?? null,
      hasReferenceImage: alt.has_reference_image ?? false,
      matchScore: alt.match_score ?? 0,
      matchReason: alt.match_reason ?? null,
    }));

    const fieldConfidence = intake.field_confidence
      ? {
          category: intake.field_confidence.category ?? 0,
          name: intake.field_confidence.name ?? 0,
          condition: intake.field_confidence.condition ?? 0,
        }
      : null;

    const internalKeys = new Set(['chain_of_thought', 'search_keywords', 'condition', 'condition_guess', 'name_confidence', 'clip_hint']);
    const extractedDetails: Record<string, string | number | boolean | null> = {};
    if (intake.attributes && typeof intake.attributes === 'object') {
      for (const [k, v] of Object.entries(intake.attributes)) {
        if (internalKeys.has(k)) continue;
        if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean' || v === null) {
          extractedDetails[k] = v;
        }
      }
    }

    return {
      itemId: null,
      attributes: {
        category: intake.category_id ?? '',
        editionGuess: (intake.attributes?.edition as string | undefined) ?? null,
        conditionGuess: condition,
        rarityScore: (intake.attributes?.rarity_score as number | undefined) ?? null,
        extractedDetails: Object.keys(extractedDetails).length > 0 ? extractedDetails : null,
      },
      prediction: {
        name: intake.name ?? '',
        estimatedLow: q10,
        estimatedMid: q50,
        estimatedHigh: q90,
        currency,
        confidence,
        explanation: intake.rationale?.length ? intake.rationale.join(' ') : null,
      },
      catalogMatchId: intake.catalog_match_id ?? null,
      catalogMatchKey: intake.catalog_match_key ?? null,
      alternatives,
      fieldConfidence,
      scanSessionId: intake.scan_session_id ?? null,
      socialProof: intake.social_proof ? {
        collectorCount: intake.social_proof.collector_count ?? 0,
        isTrending: intake.social_proof.is_trending ?? false,
        trendRank: intake.social_proof.trend_rank ?? null,
        recentSold: (intake.social_proof.recent_sold ?? []).map((s) => ({
          title: (s.title as string) ?? '',
          price: (s.price as number) ?? 0,
          currency: ((s.currency ?? 'EUR') as CurrencyCode),
          soldAt: (s.sold_at as string) ?? null,
          source: (s.source as string) ?? '',
        })),
        recentListings: (intake.social_proof.recent_listings ?? []).map((s: any) => ({
          title: (s.title as string) ?? '',
          price: (s.price as number) ?? 0,
          currency: ((s.currency ?? 'USD') as CurrencyCode),
          seenAt: (s.seen_at as string) ?? null,
          source: (s.source as string) ?? '',
          url: (s.url as string) ?? null,
        })),
        scarcity: {
          listingCount: intake.social_proof.scarcity?.listing_count ?? 0,
          supplyTrend: ((intake.social_proof.scarcity?.supply_trend ?? 'stable') as 'increasing' | 'stable' | 'decreasing'),
          scarcityScore: intake.social_proof.scarcity?.scarcity_score ?? 0,
        },
      } : null,
      duplicateInfo: intake.duplicate_info ? {
        ownedCount: intake.duplicate_info.owned_count ?? 0,
        ownedItemIds: intake.duplicate_info.owned_item_ids ?? [],
        isVariant: intake.duplicate_info.is_variant ?? false,
        variantOf: intake.duplicate_info.variant_of ?? null,
        setCompletion: intake.duplicate_info.set_completion ?? null,
      } : null,
      defectAnnotations: (intake.defect_annotations ?? []).map((d) => ({
        type: (d.type as string) ?? '',
        severity: ((d.severity ?? 'minor') as 'minor' | 'moderate' | 'major' | 'severe'),
        location: (d.location as string) ?? '',
        description: (d.description as string) ?? '',
      })),
      suggestedGrade: intake.suggested_grade ? {
        scale: ((intake.suggested_grade.scale ?? 'generic') as 'psa' | 'cgc' | 'generic'),
        gradeValue: (intake.suggested_grade.grade_value as string) ?? '',
        reasoning: (intake.suggested_grade.reasoning as string) ?? '',
      } : null,
    };
  }

  // ── Legacy fallback (no image) ─────────────────────────────────────
  const res = await collectorsApi.quickscanSingle() as Record<string, unknown>;

  const attrs = (res.attributes ?? {}) as Record<string, unknown>;
  const pred = (res.prediction ?? {}) as Record<string, unknown>;

  return {
    itemId: (res.item_id as string | null) ?? null,
    attributes: {
      category: (attrs.category as string | null) ?? '',
      editionGuess: (attrs.edition_guess as string | null) ?? null,
      conditionGuess: (attrs.condition_guess as string | null) ?? null,
      rarityScore: (attrs.rarity_score as number | null) ?? null,
    },
    prediction: {
      name: (pred.name as string | null) ?? '',
      estimatedLow: (pred.estimated_low as number | null) ?? 0,
      estimatedMid: (pred.estimated_mid as number | null) ?? 0,
      estimatedHigh: (pred.estimated_high as number | null) ?? 0,
      currency: (pred.currency as CurrencyCode | null) ?? 'EUR',
      confidence: (pred.confidence as number | null) ?? 0,
      explanation: (pred.explanation as string | null) ?? null,
    },
  };
}

export async function searchItems(query: string): Promise<Item[]> {
  if (!query.trim()) return [];

  const escaped = query.replace(/%/g, '\\%').replace(/_/g, '\\_');

  const { data, error } = await supabase
    .from('items')
    .select(ITEMS_SELECT)
    .ilike('title', `%${escaped}%`)
    .order('updated_at', { ascending: false })
    .limit(API_LIMITS.RECENT_ITEMS);

  if (error) {
    // logger.error, not warn: info/warn are STRIPPED in release builds, so a
    // search that silently returns [] would be invisible in exactly the builds
    // where it matters. Returning [] renders as "no results", which is
    // indistinguishable from a genuinely empty search unless this is logged.
    logger.error('[SupabaseDataProvider] searchItems error:', error);
    return [];
  }

  return ((data ?? []) as ItemRow[]).map(mapItemRow);
}
