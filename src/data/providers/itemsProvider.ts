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
  attributes_json?: Record<string, unknown> | null;
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
    attributesJson: r.attributes_json ?? undefined,
    price: latest?.q50 ?? 0,
    priceBand: latest
      ? { q10: latest.q10 ?? 0, q50: latest.q50 ?? 0, q90: latest.q90 ?? 0, confidence: latest.conf_score ?? 0, currency: 'EUR' }
      : undefined,
    imageUrl: r.images?.[0] ?? undefined,
    updatedAt: r.updated_at ?? undefined,
  };
}

const ITEMS_SELECT = 'id, title, category, updated_at, attributes_json, taxonomy_version, subtype_id, collections, images, price_predictions(q10, q50, q90, conf_score, asof)';

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
  const { data, error } = await supabase.rpc('rpc_create_item_v1', {
    p_title: input.name,
    p_category: input.category,
    p_image_url: input.imageUrl ?? null,
    p_attributes: {},
    p_notes: null,
  });

  if (error) {
    logger.error('[SupabaseDataProvider] createItem RPC error:', error);
    throw new Error(error.message || 'Failed to create item');
  }

  const row = data as Record<string, unknown>;
  const images = row.images as string[] | null;

  return {
    id: row.id as string,
    name: (row.title as string | null) ?? input.name,
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

export async function archiveItem(itemId: string): Promise<void> {
  const { error } = await supabase.rpc('rpc_archive_item_v1', {
    p_item_id: itemId,
  });

  if (error) {
    logger.warn('[SupabaseDataProvider] archiveItem RPC unavailable, trying direct update:', error);
    const { data: current } = await supabase
      .from('items')
      .select('attributes_json')
      .eq('id', itemId)
      .single();

    const attrs = (current?.attributes_json as Record<string, unknown>) ?? {};
    const { error: updateError } = await supabase
      .from('items')
      .update({ attributes_json: { ...attrs, _archived: true } })
      .eq('id', itemId);

    if (updateError) {
      logger.error('[SupabaseDataProvider] archiveItem error:', updateError);
      throw new Error(updateError.message || 'Failed to archive item');
    }
  }
}

export async function unarchiveItem(itemId: string): Promise<void> {
  const { error } = await supabase.rpc('rpc_unarchive_item_v1', {
    p_item_id: itemId,
  });

  if (error) {
    logger.warn('[SupabaseDataProvider] unarchiveItem RPC unavailable, trying direct update:', error);
    const { data: current } = await supabase
      .from('items')
      .select('attributes_json')
      .eq('id', itemId)
      .single();

    const attrs = { ...((current?.attributes_json as Record<string, unknown>) ?? {}) };
    delete attrs._archived;
    const { error: updateError } = await supabase
      .from('items')
      .update({ attributes_json: attrs })
      .eq('id', itemId);

    if (updateError) {
      logger.error('[SupabaseDataProvider] unarchiveItem error:', updateError);
      throw new Error(updateError.message || 'Failed to unarchive item');
    }
  }
}

export async function persistQuickscanDraft(input: QuickscanDraft): Promise<PersistedItem> {
  const { data, error } = await supabase.rpc('rpc_create_item_v1', {
    p_title: input.title ?? 'Untitled Scan',
    p_category: input.categoryId ?? 'uncategorized',
    p_image_url: input.photoUri ?? null,
    p_attributes: input.attributes ?? {},
    p_notes: input.notes ?? null,
  });

  if (error) {
    logger.error('[SupabaseDataProvider] persistQuickscanDraft RPC error:', error);
    throw new Error(error.message || 'Failed to persist QuickScan draft');
  }

  const row = data as Record<string, unknown>;
  const images = row.images as string[] | null;

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
