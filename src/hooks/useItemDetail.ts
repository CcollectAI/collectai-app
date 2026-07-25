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
  initialNotes: string;
  imageUri: string | undefined;
  categorySlug: string;
  q50: string | undefined;
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
    initialCondition, initialValue, initialNotes, imageUri, categorySlug, q50,
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
  const onSaveNotes = useCallback(() => {
    setSavingNotes(true);
    setTimeout(() => {
      setSavingNotes(false);
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Notes saved locally', type: 'info' });
    }, 300);
  }, [settings.hapticsEnabled, showToast]);

  // ── Save draft handler ─────────────────────────────────────────────────
  const onSaveDraft = useCallback(async () => {
    if (!isDraft) return;
    setSavingDraft(true);
    setSaveError(null);
    try {
      const persisted = await dataProvider.persistQuickscanDraft({
        photoUri: imageUri || '',
        categoryId: editableCategory,
        title: editableName,
        notes: notes || undefined,
        attributes: initialAttributes ?? undefined,
        canonicalKey: catalogKey ?? null,
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
  }, [isDraft, imageUri, editableCategory, editableName, notes, editableCollection, editableCondition, editableValue, q50, initialValue, settings.hapticsEnabled, showToast, initialAttributes, catalogKey]);

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
      if (editableCollection && editableCollection !== 'Not set') extraPatch.collection = editableCollection;
      if (editableCondition && editableCondition !== 'Not set') extraPatch.condition = editableCondition;
      const numericValue = parseFloat(editableValue);
      if (!isNaN(numericValue) && numericValue > 0) extraPatch.user_value = numericValue;
      if (Object.keys(extraPatch).length > 0) {
        // Check the error: this used to discard the result, so a failed or
        // timed-out write fell straight through to "Changes saved" — a false
        // success, which is worse than an error. supabase-js resolves rather
        // than throws, so the only way to notice is to look.
        const { error: patchError } = await supabase.from('items').update(extraPatch).eq('id', id);
        if (patchError) throw new Error(patchError.message);
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
  }, [id, isDraft, editableName, editableCategory, editableCollection, editableCondition, editableValue, settings.hapticsEnabled, showToast]);

  // ── Feedback handlers ──────────────────────────────────────────────────
  const onSubmitSalePrice = useCallback(async () => {
    if (!salePrice.trim() || !id || isDraft) return;
    setSubmittingFeedback(true);
    setFeedbackMessage(null);
    try {
      await dataProvider.submitFeedback(id, 'sale_price', salePrice.trim());
      const parsedPrice = parseFloat(salePrice.trim().replace(/[^\d.]/g, ''));
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
    const price = parseFloat(askingPriceValue);
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
