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
import logger from '../../utils/logger';

// Shared row types used by listItems and searchItems
type PredRow = { q10: number | null; q50: number | null; q90: number | null; conf_score: number | null; asof: string | null };
type ItemRow = {
  id: string;
  title?: string | null;
  category?: string | null;
  updated_at?: string | null;
  // items.attrs (jsonb) — exposed to the FE as `attributesJson` for
  // historical reasons; the DB column was renamed but the public name
  // wasn't, so callers don't need to change.
  attrs?: Record<string, unknown> | null;
  taxonomy_version?: string | null;
  subtype_id?: string | null;
  collections?: string[] | null;
  images?: string[] | null;
  price_predictions?: PredRow[];
};

function mapItemRow(r: ItemRow): Item {
  const preds = (r.price_predictions ?? []).sort(
    (a, b) => (b.asof ?? '').localeCompare(a.asof ?? ''),
  );
  const latest = preds[0];

  return {
    id: r.id,
    name: r.title ?? 'Untitled',
    category: r.category || 'Uncategorized',
    subtypeId: r.subtype_id ?? undefined,
    taxonomyVersion: r.taxonomy_version ?? undefined,
    collections: r.collections ?? undefined,
    attributesJson: r.attrs ?? undefined,
    price: latest?.q50 ?? 0,
    priceBand: latest
      ? { q10: latest.q10 ?? 0, q50: latest.q50 ?? 0, q90: latest.q90 ?? 0, confidence: latest.conf_score ?? 0, currency: 'EUR' }
      : undefined,
    imageUrl: r.images?.[0] ?? undefined,
    updatedAt: r.updated_at ?? undefined,
  };
}

const ITEMS_SELECT = 'id, title, category, updated_at, attrs, taxonomy_version, subtype_id, collections, images, price_predictions(q10, q50, q90, conf_score, asof)';

export async function listItems(pagination?: PaginationParams): Promise<Item[]> {
  const limit = pagination?.limit ?? API_LIMITS.ITEMS_DEFAULT;
  const offset = pagination?.offset ?? 0;
  const { data, error } = await supabase
    .from('items')
    .select(ITEMS_SELECT)
    .order('updated_at', { ascending: false })
    .range(offset, offset + limit - 1);

  if (error) {
    logger.warn('[SupabaseDataProvider] listItems error:', error);
    return [];
  }

  return ((data ?? []) as ItemRow[]).map(mapItemRow);
}

export async function createItem(input: CreateItemInput): Promise<Item> {
  // Server contract (ItemCreateRequest): name, category?, collection_name?,
  // estimated_value?, notes?. Sending `title` (the DB column name) was
  // wrong — server expects `name` (the API field) and stores it as
  // items.title internally. Image URLs are NOT a body field; images are
  // attached separately via POST /items/{id}/images.
  let row: Record<string, unknown>;
  try {
    row = await collectorsApi.post<Record<string, unknown>>('/items', {
      name: input.name,
      category: input.category,
    });
  } catch (e) {
    logger.error('[SupabaseDataProvider] createItem error:', e);
    throw e instanceof Error ? e : new Error('Failed to create item');
  }
  const images = (row.images as string[] | null) ?? null;
  const itemId = row.id as string;

  // Push-engagement loop: if the user added this item shortly after
  // tapping a notification (e.g. drop alert → "I got it"), attribute the
  // outcome back. emitOutcome no-ops when no recent tap exists.
  try {
    // Lazy import to keep this provider tree-shakeable.
    const { emitOutcome } = await import('@/lib/notificationOutcomeTracker');
    emitOutcome('added', { item_id: itemId });
  } catch {
    // Tracker import failed — best-effort, ignore.
  }

  return {
    // Server's ItemResponse returns `name` (API field), not `title`.
    id: itemId,
    name: (row.name as string | null) ?? input.name,
    category: (row.category as string | null) ?? input.category,
    price: 0,
    imageUrl: images?.[0] ?? undefined,
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

export async function updateItem(itemId: string, patch: Partial<Pick<Item, 'name' | 'category' | 'price' | 'imageUrl'>>): Promise<Item> {
  const updatePayload: Record<string, unknown> = {};
  if (patch.name !== undefined) updatePayload.title = patch.name;
  if (patch.category !== undefined) updatePayload.category = patch.category;
  if (patch.imageUrl !== undefined) updatePayload.images = patch.imageUrl ? [patch.imageUrl] : [];

  const { data, error } = await supabase
    .from('items')
    .update(updatePayload)
    .eq('id', itemId)
    .select('id, title, category, updated_at, images')
    .single();

  if (error || !data) {
    logger.error('[SupabaseDataProvider] updateItem error:', error);
    throw new Error(error?.message || 'Failed to update item');
  }

  const images = (data as Record<string, unknown>).images as string[] | null;

  return {
    id: data.id,
    name: (data as Record<string, unknown>).title as string ?? 'Untitled',
    category: data.category,
    price: 0,
    imageUrl: images?.[0] ?? (data as Record<string, unknown>).image_url as string ?? undefined,
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
  // category, collection_name, estimated_value, notes. attributes go
  // through a follow-up PATCH /items/{id}/attributes; images via
  // POST /items/{id}/images. Sending `title`/`image_url`/`attrs` here
  // was rejected with 422 (missing `name`).
  let row: Record<string, unknown>;
  try {
    row = await collectorsApi.post<Record<string, unknown>>('/items', {
      name: input.title ?? 'Untitled Scan',
      category: input.categoryId ?? 'uncategorized',
      notes: input.notes ?? null,
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
      logger.warn('[SupabaseDataProvider] persistQuickscanDraft attrs PATCH failed (non-fatal):', e);
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
    logger.warn('[SupabaseDataProvider] searchItems error:', error);
    return [];
  }

  return ((data ?? []) as ItemRow[]).map(mapItemRow);
}
