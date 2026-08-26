/**
 * useItemDetail — consolidates local state management for the item detail screen.
 *
 * Groups: edit state, notes/save, feedback, keyboard, for-sale, AI refresh,
 * UI toggles, evidence data, scarcity/comps, and associated handlers.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { Platform, Keyboard } from 'react-native';
import { router } from 'expo-router';
import { dataProvider } from '@/data';
import { supabase } from '@/lib/supabase';
import { collectorsApi } from '@/api/collectorsApi';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import logger from '@/utils/logger';
import { parseMoney } from '@/lib/format';

// ── Types ──────────────────────────────────────────────────────────────────

interface EvidenceData {
  explanation: string | null;
  evidence_summary: {
    sources: { source: string; count: number; avg_price: number; date_range?: string }[];
    total_comps: number;
  } | null;
  evidence_hit_ids: string[];
  prediction_at: string | null;
}

interface ScarcityData {
  scarcity_score: number;
  listing_count: number;
  supply_trend: string;
}

interface MarketComp {
  source: string;
  title: string;
  price: number;
  currency: string;
}

interface UseItemDetailParams {
  id: string | undefined;
  isDraft: boolean;
  initialName: string;
  initialCategory: string;
  initialCollection: string;
  initialCondition: string;
  initialValue: string;
  /** RAW purchase price as typed, in `initialPurchaseCurrency`. '' when unset. */
  initialPurchasePrice: string;
  /** The currency that raw figure is in. Falls back to the member's setting. */
  initialPurchaseCurrency?: string | null;
  initialNotes: string;
  imageUri: string | undefined;
  categorySlug: string;
  q50: string | undefined;
  /** The rest of the scan's prediction band. Persisted into `attrs.scan` on
   *  save so the evidence survives — deliberately NOT into quick_predictions,
   *  which is link 1 of the value chain and would let a vision guess outrank
   *  the catalogue model for an identified product. */
  q10?: string;
  q90?: string;
  confidence?: string;
  /** Structured attributes extracted by QuickScan vision pipeline */
  initialAttributes?: Record<string, unknown> | null;
  /** Catalog match key from QuickScan (intake.catalog_match_key). When set,
   * persistQuickscanDraft writes it to items.canonical_key so downstream
   * Premium JOINs (price_trend, item_history, dossier) work. */
  catalogKey?: string;
}

export function useItemDetail(params: UseItemDetailParams) {
  const {
    id, isDraft, initialName, initialCategory, initialCollection,
    initialCondition, initialValue, initialPurchasePrice, initialPurchaseCurrency,
    initialNotes, imageUri, categorySlug, q50,
    q10, q90, confidence,
    initialAttributes, catalogKey,
  } = params;

  const { settings } = useSettings();
  const { showToast } = useToast();

  // ── Edit state ─────────────────────────────────────────────────────────
  const [isEditing, setIsEditing] = useState(false);
  const [editableName, setEditableName] = useState(initialName);
  const [editableCategory, setEditableCategory] = useState(initialCategory);
  const [editableCollection, setEditableCollection] = useState(initialCollection);
  const [editableCondition, setEditableCondition] = useState(initialCondition);
  const [editableValue, setEditableValue] = useState(initialValue);
  // COST BASIS. Seeded from the RAW half, never from purchase_price_eur: the
  // field is denominated in `initialPurchaseCurrency`, so putting the EUR
  // normalisation in it would show a JPY buyer a euro figure labelled JPY.
  const [editablePurchasePrice, setEditablePurchasePrice] = useState(initialPurchasePrice);

  // ── Notes & save state ─────────────────────────────────────────────────
  const [notes, setNotes] = useState(initialNotes || '');
  const [savingNotes, setSavingNotes] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // ── Feedback state ─────────────────────────────────────────────────────
  const [showSalePriceInput, setShowSalePriceInput] = useState(false);
  const [salePrice, setSalePrice] = useState('');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  /**
   * WHICH action produced `feedbackMessage`.
   *
   * The two feedback controls were split across the screen on 2026-08-23 —
   * "Price seems off?" sits against the figure in the valuation card, "I sold
   * it for…" sits last — but they still share ONE message state. Without a
   * source, "Thanks for the feedback!" would render in both places at once, or
   * (worse) under the control that did not cause it. Set on every write to
   * `feedbackMessage`, including the failure paths.
   */
  const [feedbackSource, setFeedbackSource] = useState<'sale' | 'disagree' | null>(null);

  // ── Keyboard state ─────────────────────────────────────────────────────
  const [keyboardVisible, setKeyboardVisible] = useState(false);
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    const showEvent = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const showSub = Keyboard.addListener(showEvent, (e) => {
      setKeyboardVisible(true);
      setKeyboardHeight(e.endCoordinates.height);
    });
    const hideSub = Keyboard.addListener(hideEvent, () => {
      setKeyboardVisible(false);
      setKeyboardHeight(0);
    });
    return () => { showSub.remove(); hideSub.remove(); };
  }, []);

  // ── UI toggles ─────────────────────────────────────────────────────────
  const [explanationExpanded, setExplanationExpanded] = useState(false);
  const [showPriceExplanation, setShowPriceExplanation] = useState(false);
  const [showStickyButton, setShowStickyButton] = useState(false);

  // ── AI refresh state ───────────────────────────────────────────────────
  const [aiRefreshing, setAiRefreshing] = useState(false);
  const [pullRefreshing, setPullRefreshing] = useState(false);

  // ── For-sale state ─────────────────────────────────────────────────────
  const [isForSale, setIsForSale] = useState(false);
  const [askingPriceValue, setAskingPriceValue] = useState('');
  const [forSaleLoading, setForSaleLoading] = useState(false);

  // ── Evidence data ──────────────────────────────────────────────────────
  const [evidenceData, setEvidenceData] = useState<EvidenceData | null>(null);

  useEffect(() => {
    if (!id || isDraft) return;
    let cancelled = false;
    collectorsApi.getPriceEvidence(id)
      .then((data) => { if (!cancelled) setEvidenceData(data); })
      .catch((err) => logger.warn('[ItemDetail] evidence fetch error:', err));
    const evidenceInterval = setInterval(() => {
      collectorsApi.getPriceEvidence(id)
        .then((data) => { if (!cancelled) setEvidenceData(data); })
        .catch((err) => logger.warn('[ItemDetail] fetch error:', err));
    }, 300000); // 5 min
    return () => { cancelled = true; clearInterval(evidenceInterval); };
  }, [id, isDraft]);

  // ── Item attributes & for-sale status ──────────────────────────────────
  const [itemAttributes, setItemAttributes] = useState<Record<string, unknown> | null>(null);
  const [taxonomyVersion, setTaxonomyVersion] = useState<string | undefined>();
  const [subtypeId, setSubtypeId] = useState<string | undefined>();
  const [itemCollections, setItemCollections] = useState<string[]>([]);

  useEffect(() => {
    if (!id || isDraft) return;
    dataProvider.listItems().then((items) => {
      const item = items.find((i) => i.id === id);
      if (item) {
        setItemAttributes(item.attributesJson || null);
        setTaxonomyVersion(item.taxonomyVersion);
        setSubtypeId(item.subtypeId);
        setItemCollections(item.collections || []);
      }
    }).catch((err) => logger.warn('[ItemDetail] item attributes fetch error:', err));

    supabase
      .from('items')
      .select('for_sale, asking_price')
      .eq('id', id)
      .single()
      .then(({ data, error: fsErr }) => {
        if (fsErr) { logger.warn('[ItemDetail] for-sale status fetch error:', fsErr); return; }
        if (data) {
          if (data.for_sale) setIsForSale(true);
          if (data.asking_price != null) setAskingPriceValue(String(data.asking_price));
        }
      });
  }, [id, isDraft]);

  // ── Scarcity + Market Comps ────────────────────────────────────────────
  const [scarcityData, setScarcityData] = useState<ScarcityData | null>(null);
  const [marketComps, setMarketComps] = useState<MarketComp[]>([]);

  useEffect(() => {
    if (isDraft || !categorySlug) return;
    let cancelled = false;
    collectorsApi.getScarcityScores(categorySlug).then((data) => {
      if (cancelled) return;
      const resp = data as { items?: { item_key: string; scarcity_score: number; listing_count: number; supply_trend: string }[] } | undefined;
      const match = resp?.items?.find((i) => i.item_key?.toLowerCase().includes(editableName.toLowerCase().slice(0, 20)));
      if (match) setScarcityData(match);
    }).catch((err) => logger.warn('[ItemDetail] fetch error:', err));
    collectorsApi.marketplaceComps(editableName, categorySlug).then((data) => {
      if (cancelled) return;
      const resp = data as { comps?: { source: string; title: string; price: number; currency: string }[] } | undefined;
      const comps = resp?.comps;
      if (Array.isArray(comps) && comps.length) setMarketComps(comps.slice(0, 5));
    }).catch((err) => logger.warn('[ItemDetail] fetch error:', err));
    return () => { cancelled = true; };
  }, [isDraft, categorySlug, editableName]);

  // ── Linked build project ───────────────────────────────────────────────
  const [linkedProject, setLinkedProject] = useState<{ id: string; title: string; pct: number } | null>(null);

  // ── Notes handler ──────────────────────────────────────────────────────
  //
  // This used to be a 300ms setTimeout that wrote NOTHING and toasted "Notes
  // saved locally". Nothing was saved anywhere — not the DB, not AsyncStorage
  // — so every note was lost on unmount while the user was told it was safe.
  // The house silent-failure pattern: a writer that never writes, wearing a
  // success message.
  const onSaveNotes = useCallback(async () => {
    if (!id || isDraft) {
      // A draft has no items row yet, so there is nothing to write to. Say so
      // rather than implying a save happened.
      showToast({ message: 'Save the item first, then add notes', type: 'info' });
      return;
    }
    setSavingNotes(true);
    try {
      await dataProvider.updateItem(id, { notes });
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Notes saved', type: 'success' });
    } catch (err: unknown) {
      logger.error('[useItemDetail] save notes failed:', err);
      // Never claim success on a failed write — that is the bug this replaced.
      showToast({
        message: (err as Error)?.message || "Couldn't save your notes",
        type: 'error',
      });
    } finally {
      setSavingNotes(false);
    }
  }, [id, isDraft, notes, settings.hapticsEnabled, showToast]);

  // ── Save draft handler ─────────────────────────────────────────────────
  const onSaveDraft = useCallback(async () => {
    if (!isDraft) return;
    setSavingDraft(true);
    setSaveError(null);
    try {
      // The scan's own numbers go WITH the draft. Until 2026-08-19 this call
      // sent four fields and the estimate and condition were simply lost, so a
      // scanned item was saved with no value and the member had to retype the
      // figure the app had just shown them.
      const num = (v: string | undefined) => {
        if (v === undefined || v === '') return null;
        const n = parseFloat(v);
        return Number.isNaN(n) ? null : n;
      };
      const scanValue = num(editableValue) ?? num(q50) ?? num(initialValue);
      const persisted = await dataProvider.persistQuickscanDraft({
        photoUri: imageUri || '',
        categoryId: editableCategory,
        title: editableName,
        notes: notes || undefined,
        attributes: initialAttributes ?? undefined,
        canonicalKey: catalogKey ?? null,
        estimatedValue: scanValue,
        condition:
          editableCondition && editableCondition !== 'Not set'
            ? editableCondition
            : null,
        scanBand: {
          q10: num(q10),
          q50: num(q50),
          q90: num(q90),
          // Stored as the 0-1 fraction the pipeline produced, not the rounded
          // percentage the screen displays.
          confidence: num(confidence) != null ? num(confidence)! / 100 : null,
        },
      });
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Item saved to collection', type: 'success' });
      router.replace({
        pathname: '/item/[id]',
        params: {
          id: persisted.id,
          name: persisted.title,
          category: persisted.categoryId,
          collection: editableCollection,
          condition: editableCondition,
          value: editableValue || String(q50 || initialValue || 0),
          imageUri: persisted.imageUrl || '',
        },
      });
    } catch (err: unknown) {
      logger.error('[ItemDetail] save draft error:', err);
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
      setSaveError(err instanceof Error ? err.message : 'Failed to save item');
    } finally {
      setSavingDraft(false);
    }
  }, [isDraft, imageUri, editableCategory, editableName, notes, editableCollection, editableCondition, editableValue, q50, q10, q90, confidence, initialValue, settings.hapticsEnabled, showToast, initialAttributes, catalogKey]);

  // ── Save edits handler ─────────────────────────────────────────────────
  const onSaveEdits = useCallback(async () => {
    if (!id || isDraft) return;
    setSavingNotes(true);
    try {
      await dataProvider.updateItem(id, {
        name: editableName,
        category: editableCategory,
      });
      const extraPatch: Record<string, unknown> = {};
      // Column names verified against the live schema 2026-07-29. These were
      // `collection` and `user_value`; items has NEITHER — the real columns are
      // collection_name and estimated_value. Postgres rejects the unknown key,
      // so editing Collection or Estimated value failed the whole patch and
      // showed "Failed to save changes" — AFTER updateItem had already written
      // the name/category, leaving a partial save behind an error toast.
      if (editableCollection && editableCollection !== 'Not set') extraPatch.collection_name = editableCollection;
      if (editableCondition && editableCondition !== 'Not set') extraPatch.condition = editableCondition;
      const numericValue = parseFloat(editableValue);
      if (!isNaN(numericValue) && numericValue > 0) extraPatch.estimated_value = numericValue;
      if (Object.keys(extraPatch).length > 0) {
        // Check the error: this used to discard the result, so a failed or
        // timed-out write fell straight through to "Changes saved" — a false
        // success, which is worse than an error. supabase-js resolves rather
        // than throws, so the only way to notice is to look.
        const { error: patchError } = await supabase.from('items').update(extraPatch).eq('id', id);
        if (patchError) throw new Error(patchError.message);
      }
      // COST BASIS goes through the SERVER, not into `extraPatch`.
      //
      // `items` carries purchase_price (raw) AND purchase_price_eur, every EUR
      // reader sums the second, and `trg_items_sync_paired_columns` only copies
      // raw -> eur for the identity case — its guard is
      // `COALESCE(UPPER(BTRIM(purchase_currency)), 'EUR') = 'EUR'`, so a NULL
      // currency is treated AS EUR. Adding purchase_price to the PostgREST
      // patch above would therefore file a JPY amount as euros: the ~170x error
      // this repo has already shipped from this exact column pair. The database
      // cannot call FX (docs/ARCHITECTURE.md); the server can, and does.
      //
      // Only sent when it actually CHANGED — an unrelated rename must not
      // rewrite the cost basis, and must not re-convert it at today's rate.
      const trimmedPurchase = editablePurchasePrice.trim();
      if (trimmedPurchase !== (initialPurchasePrice ?? '').trim()) {
        const parsedPurchase = trimmedPurchase === ''
          ? null
          : parseFloat(trimmedPurchase.replace(',', '.'));
        if (parsedPurchase !== null && (isNaN(parsedPurchase) || parsedPurchase < 0)) {
          throw new Error('Enter a purchase price of 0 or more, or leave it blank');
        }
        await collectorsApi.updateItemPurchase(
          id,
          parsedPurchase,
          // The currency the FIELD is in: the one it was stored in if we have
          // it, else the member's current setting. Never inferred server-side.
          (initialPurchaseCurrency || settings.currency || 'EUR') as string,
        );
      }

      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Changes saved', type: 'success' });
      setIsEditing(false);
    } catch (err: unknown) {
      logger.error('[ItemDetail] save edits error:', err);
      showToast({ message: 'Failed to save changes', type: 'error' });
    } finally {
      setSavingNotes(false);
    }
  }, [id, isDraft, editableName, editableCategory, editableCollection, editableCondition, editableValue, editablePurchasePrice, initialPurchasePrice, initialPurchaseCurrency, settings.currency, settings.hapticsEnabled, showToast]);

  // ── Feedback handlers ──────────────────────────────────────────────────
  const onSubmitSalePrice = useCallback(async () => {
    if (!salePrice.trim() || !id || isDraft) return;
    setSubmittingFeedback(true);
    setFeedbackMessage(null);
    setFeedbackSource('sale');
    try {
      await dataProvider.submitFeedback(id, 'sale_price', salePrice.trim());
      const parsedPrice = parseFloat(salePrice.trim().replace(/[^0-9.,]/g, '').replace(',', '.'));
      if (parsedPrice > 0) {
        collectorsApi.submitVerifiedSale({
          item_id: id,
          sale_price: parsedPrice,
          currency: settings.currency,
          sale_date: new Date().toISOString(),
        }).catch((err) => { logger.warn('[ItemDetail] verified sale submission failed:', err); });
      }
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Sale price recorded — thanks!', type: 'success' });
      setFeedbackMessage('Thanks! Sale price recorded.');
      setShowSalePriceInput(false);
      setSalePrice('');
    } catch (err: unknown) {
      logger.error('[ItemDetail] feedback error:', err);
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
      setFeedbackMessage('Failed to submit feedback');
    } finally {
      setSubmittingFeedback(false);
    }
  }, [id, isDraft, salePrice, settings.currency, settings.hapticsEnabled, showToast]);

  const onPriceDisagree = useCallback(async () => {
    if (!id || isDraft) return;
    setSubmittingFeedback(true);
    setFeedbackMessage(null);
    setFeedbackSource('disagree');
    try {
      await dataProvider.submitFeedback(id, 'disagree', 'inaccurate');
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      setFeedbackMessage('Thanks for the feedback!');
    } catch (err: unknown) {
      logger.error('[ItemDetail] feedback error:', err);
      setFeedbackMessage('Failed to submit feedback');
    } finally {
      setSubmittingFeedback(false);
    }
  }, [id, isDraft, settings.hapticsEnabled]);

  // ── For-sale handlers ──────────────────────────────────────────────────
  const handleListForSale = useCallback(async () => {
    if (!id || isDraft || forSaleLoading) return;
    const price = parseMoney(askingPriceValue) ?? NaN;
    if (isNaN(price) || price <= 0) {
      showToast({ message: 'Enter a valid asking price', type: 'error' });
      return;
    }
    setForSaleLoading(true);
    try {
      await dataProvider.toggleForSale(id, true, price);
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Item listed for sale!', type: 'success' });
      setIsForSale(true);
    } catch (err: unknown) {
      logger.error('[ItemDetail] list for sale error:', err);
      showToast({ message: 'Failed to list item for sale', type: 'error' });
    } finally {
      setForSaleLoading(false);
    }
  }, [id, isDraft, forSaleLoading, askingPriceValue, settings.hapticsEnabled, showToast]);

  const handleUnlist = useCallback(async () => {
    if (!id || isDraft || forSaleLoading) return;
    setForSaleLoading(true);
    try {
      await dataProvider.toggleForSale(id, false);
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Item unlisted', type: 'info' });
      setIsForSale(false);
      setAskingPriceValue('');
    } catch (err: unknown) {
      logger.error('[ItemDetail] unlist error:', err);
      showToast({ message: 'Failed to unlist item', type: 'error' });
    } finally {
      setForSaleLoading(false);
    }
  }, [id, isDraft, forSaleLoading, settings.hapticsEnabled, showToast]);

  return {
    // Edit state
    isEditing, setIsEditing,
    editableName, setEditableName,
    editableCategory, setEditableCategory,
    editableCollection, setEditableCollection,
    editableCondition, setEditableCondition,
    editableValue, setEditableValue,
    editablePurchasePrice, setEditablePurchasePrice,

    // Notes & save
    notes, setNotes,
    savingNotes,
    savingDraft,
    saveError,
    onSaveNotes,
    onSaveDraft,
    onSaveEdits,

    // Feedback
    showSalePriceInput, setShowSalePriceInput,
    salePrice, setSalePrice,
    submittingFeedback,
    feedbackMessage,
    feedbackSource,
    onSubmitSalePrice,
    onPriceDisagree,

    // Keyboard
    keyboardVisible,
    keyboardHeight,

    // UI toggles
    explanationExpanded, setExplanationExpanded,
    showPriceExplanation, setShowPriceExplanation,
    showStickyButton, setShowStickyButton,

    // AI refresh
    aiRefreshing, setAiRefreshing,
    pullRefreshing, setPullRefreshing,

    // For-sale
    isForSale, setIsForSale,
    askingPriceValue, setAskingPriceValue,
    forSaleLoading,
    handleListForSale,
    handleUnlist,

    // Evidence data
    evidenceData, setEvidenceData,

    // Item attributes
    itemAttributes, setItemAttributes,
    taxonomyVersion, setTaxonomyVersion,
    subtypeId, setSubtypeId,
    itemCollections, setItemCollections,

    // Scarcity + comps
    scarcityData,
    marketComps,

    // Linked project
    linkedProject, setLinkedProject,
  };
}
