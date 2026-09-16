/**
 * useItemDetail — consolidates local state management for the item detail screen.
 *
 * Groups: edit state, notes/save, feedback, keyboard, for-sale, AI refresh,
 * UI toggles, evidence data, scarcity/comps, and associated handlers.
 */

import { useState, useEffect, useCallback } from 'react';
import { memberAmountToEUR } from '@/lib/fx';
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
import { userErrorMessage } from '@/lib/userErrorMessage';

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
  /** RAW acquisition fees as typed, in the SAME currency. '' when unset. */
  initialAcquisitionFees?: string;
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
    initialCondition, initialValue, initialPurchasePrice, initialAcquisitionFees, initialPurchaseCurrency,
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
  // Same currency as the price by construction — the save path sends ONE
  // currency for both, because a fee in one currency against a price in another
  // is not a shape a single purchase has.
  const [editableAcquisitionFees, setEditableAcquisitionFees] = useState(initialAcquisitionFees ?? '');

  // What the fields held when edit mode OPENED. Cancel restores it.
  //
  // Cancel used to only flip `isEditing` off, so the abandoned values stayed in
  // state: walked on Android 2026-09-14, typing "ZZ" into the name and tapping
  // Cancel left the title reading "Rayquaza ex (Emerald 097)ZZ" — and the
  // tap-to-edit pickers call onSaveEdits, which writes `editableName`, so the
  // NEXT unrelated edit would have saved the name the member took back.
  //
  // Taken in an effect on `isEditing` so every way into edit mode is covered —
  // the Edit button and the three inline pickers — and before any field can
  // change (a change needs a later event than the render that opened it).
  type EditSnapshot = {
    name: string; category: string; collection: string; condition: string;
    value: string; purchasePrice: string; acquisitionFees: string;
  };
  const [editSnapshot, setEditSnapshot] = useState<EditSnapshot | null>(null);
  useEffect(() => {
    if (!isEditing) { setEditSnapshot(null); return; }
    setEditSnapshot((prev) => prev ?? {
      name: editableName, category: editableCategory, collection: editableCollection,
      condition: editableCondition, value: editableValue,
      purchasePrice: editablePurchasePrice, acquisitionFees: editableAcquisitionFees,
    });
    // Only the open/close transition matters; the field values are read at
    // that moment on purpose.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditing]);

  const editsDirty = isEditing && editSnapshot !== null && (
    editableName !== editSnapshot.name ||
    editableCategory !== editSnapshot.category ||
    editableCollection !== editSnapshot.collection ||
    editableCondition !== editSnapshot.condition ||
    editableValue !== editSnapshot.value ||
    editablePurchasePrice !== editSnapshot.purchasePrice ||
    editableAcquisitionFees !== editSnapshot.acquisitionFees
  );

  // The item screen fills name / category / condition / value / cost basis in
  // once the saved row arrives, and only into fields that are still empty. If
  // that lands AFTER edit mode opened, a plain setter would make the form look
  // dirty (a false "unsaved changes" prompt) and Cancel would restore the
  // pre-load blanks.
  // Loaded values are the baseline, not an edit, so they move the snapshot too.
  const adoptLoadedValues = useCallback((v: {
    name?: string; category?: string; collection?: string;
    condition?: string; value?: string; purchasePrice?: string; acquisitionFees?: string;
  }) => {
    if (v.name !== undefined) setEditableName(v.name);
    if (v.category !== undefined) setEditableCategory(v.category);
    if (v.collection !== undefined) setEditableCollection(v.collection);
    if (v.condition !== undefined) setEditableCondition(v.condition);
    if (v.value !== undefined) setEditableValue(v.value);
    if (v.purchasePrice !== undefined) setEditablePurchasePrice(v.purchasePrice);
    if (v.acquisitionFees !== undefined) setEditableAcquisitionFees(v.acquisitionFees);
    setEditSnapshot((prev) => prev && {
      ...prev,
      ...(v.name !== undefined ? { name: v.name } : {}),
      ...(v.category !== undefined ? { category: v.category } : {}),
      ...(v.collection !== undefined ? { collection: v.collection } : {}),
      ...(v.condition !== undefined ? { condition: v.condition } : {}),
      ...(v.value !== undefined ? { value: v.value } : {}),
      ...(v.purchasePrice !== undefined ? { purchasePrice: v.purchasePrice } : {}),
      ...(v.acquisitionFees !== undefined ? { acquisitionFees: v.acquisitionFees } : {}),
    });
  }, []);

  const cancelEdits = useCallback(() => {
    if (editSnapshot) {
      setEditableName(editSnapshot.name);
      setEditableCategory(editSnapshot.category);
      setEditableCollection(editSnapshot.collection);
      setEditableCondition(editSnapshot.condition);
      setEditableValue(editSnapshot.value);
      setEditablePurchasePrice(editSnapshot.purchasePrice);
      setEditableAcquisitionFees(editSnapshot.acquisitionFees);
    }
    setIsEditing(false);
  }, [editSnapshot]);

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
        message: userErrorMessage(err, "Couldn't save your notes"),
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
      // parseMoney, not parseFloat: this field is typed by a member, and on a
      // nl/de/fr keyboard "12,50" parses as 12 — the cents vanish silently
      // (class sweep, 2026-09-16). parseMoney treats the LAST separator as the
      // decimal point, so "1.250,00" is 1250 rather than 1.25.
      const num = (v: string | undefined) => (v === undefined || v === '' ? null : parseMoney(v));
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
      setSaveError(userErrorMessage(err, 'Failed to save item'));
    } finally {
      setSavingDraft(false);
    }
  }, [isDraft, imageUri, editableCategory, editableName, notes, editableCollection, editableCondition, editableValue, q50, q10, q90, confidence, initialValue, settings.hapticsEnabled, showToast, initialAttributes, catalogKey]);

  // ── Save edits handler ─────────────────────────────────────────────────
  const onSaveEdits = useCallback(async () => {
    if (!id || isDraft) return;
    setSavingNotes(true);
    try {
      // EVERY amount is read BEFORE the first write.
      //
      // The cost-basis parse used to run after `updateItem` and the PostgREST
      // patch had already landed, and it THROWS on a malformed amount — so
      // typing a price this app could not read saved the name and the condition
      // and then showed "Failed to save changes". The member had no way to tell
      // which half happened (class sweep K, 2026-09-16). Reading first makes the
      // only remaining partial-save cause a network failure between two writes,
      // which no client-side ordering can remove.
      const trimmedPurchase = editablePurchasePrice.trim();
      const trimmedFees = editableAcquisitionFees.trim();
      const purchaseChanged = trimmedPurchase !== (initialPurchasePrice ?? '').trim();
      const feesChanged = trimmedFees !== (initialAcquisitionFees ?? '').trim();

      /** `null` CLEARS the amount; a message means the text was not a number.
       *  Returned rather than thrown: a throw here lands in the catch below,
       *  which says "Failed to save changes" — and the member needs to be told
       *  WHICH field, not that everything failed. */
      const readAmount = (raw: string, label: string):
        { ok: true; value: number | null } | { ok: false; message: string } => {
        if (raw === '') return { ok: true, value: null };
        // The canonical parser. A local copy used to shadow it and only did
        // `replace(',', '.')`, so a typed "1.250,00" became 1.25 — a cost basis
        // 1000x low (class sweep, 2026-09-16).
        const n = parseMoney(raw);
        if (n === null || n < 0) return { ok: false, message: `Enter ${label} of 0 or more, or leave it blank` };
        return { ok: true, value: n };
      };

      const purchaseRead = purchaseChanged ? readAmount(trimmedPurchase, 'a purchase price') : null;
      const feesRead = feesChanged ? readAmount(trimmedFees, 'fees') : null;
      const unreadable = [purchaseRead, feesRead].find((r) => r !== null && !r.ok);
      if (unreadable && !unreadable.ok) {
        showToast({ message: unreadable.message, type: 'error' });
        return; // nothing written yet, and nothing will be
      }

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
      const numericValue = parseMoney(editableValue) ?? NaN;
      // EUR for storage: the member types in their own currency and the server
      // sums `estimated_value` as EUR (item_value_v1, `value_choice = 'mine'`).
      // Writing it raw filed $100 as EUR 100 (class sweep, 2026-09-16); the
      // add-manual writer has always normalised its purchase price this way.
      if (!isNaN(numericValue) && numericValue > 0) {
        extraPatch.estimated_value = memberAmountToEUR(numericValue, settings);
      }
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
      // Both amounts were already read at the top, before anything was written.
      if (purchaseChanged || feesChanged) {
        // UNDEFINED for a field that did not change, so the server omits it
        // entirely. Resending an unchanged price makes it re-convert through
        // convert_to_eur at TODAY'S rate, so a non-EUR cost basis would drift
        // every time an unrelated field was saved — and it is what lets fees be
        // edited on their own. `null` still CLEARS; the two are different
        // states and the route distinguishes them via model_fields_set.
        await collectorsApi.updateItemPurchase(
          id,
          purchaseRead?.ok ? purchaseRead.value : undefined,
          // The currency the FIELD is in: the one it was stored in if we have
          // it, else the member's current setting. Never inferred server-side.
          (initialPurchaseCurrency || settings.currency || 'EUR') as string,
          undefined,
          feesRead?.ok ? feesRead.value : undefined,
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
  }, [id, isDraft, editableName, editableCategory, editableCollection, editableCondition, editableValue, editablePurchasePrice, initialPurchasePrice, editableAcquisitionFees, initialAcquisitionFees, initialPurchaseCurrency, settings, showToast]);

  // ── Feedback handlers ──────────────────────────────────────────────────
  const onSubmitSalePrice = useCallback(async () => {
    if (!salePrice.trim() || !id || isDraft) return;
    setSubmittingFeedback(true);
    setFeedbackMessage(null);
    setFeedbackSource('sale');
    try {
      await dataProvider.submitFeedback(id, 'sale_price', salePrice.trim());
      const parsedPrice = parseMoney(salePrice);
      if (parsedPrice !== null && parsedPrice > 0) {
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

  // For-sale handlers removed 2026-09-08. `items.for_sale` is owned by the
  // `trg_sync_item_for_sale` trigger on `marketplace_listings`, so the app
  // never writes it: listing goes through app/sell/new -> p2pApi.createListing
  // and unlisting through p2pApi.delistListing on the listing detail screen.
  // `isForSale` below is READ from the item and drives the "Listed" badge.

  return {
    // Edit state
    isEditing, setIsEditing,
    editableName, setEditableName,
    editableCategory, setEditableCategory,
    editableCollection, setEditableCollection,
    editableCondition, setEditableCondition,
    editableValue, setEditableValue,
    editablePurchasePrice, setEditablePurchasePrice,
    editableAcquisitionFees, setEditableAcquisitionFees,
    editsDirty, cancelEdits, adoptLoadedValues,

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
