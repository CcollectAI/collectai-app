/**
 * Sell something that isn't in your collection.
 *
 * The marketplace-only seller's entry point. Until 2026-08-07 there wasn't one:
 * `POST /p2p/listings` required an `item_id` and the only route in was the
 * item-detail screen, so someone who wanted to sell one thing had to first
 * build a collection they did not want — friction on exactly the people most
 * likely to bring supply (docs/P2P_MARKETPLACE_SPEC.md §5c).
 *
 * The server creates the item for them (`source='marketplace'`), so everything
 * downstream — photos, the publish supply hook, the sold-comp hook on
 * completion — behaves identically to a listing made from a collection item.
 *
 * ── Built to match the rest of the app, not invented ────────────────────────
 * The first version of this screen used bare TextInputs for everything, which
 * looked nothing like `add-manual`. Anything with a FIXED vocabulary is now an
 * action sheet, the same `showActionSheet` every other screen uses (native
 * ActionSheetIOS on iOS, an Alert on Android):
 *
 *   Photo      -> Take Photo / Choose from Library   (same as add-manual)
 *   Category   -> CATEGORIES, the app's 54-slug list — NOT a free-text box
 *   Condition  -> the CONDITION_CHIPS vocabulary from ConditionValueSection
 *
 * Only genuinely free text stays a TextInput: title, price, description.
 * Reusing the vocabularies matters beyond looks — a typed category would not
 * match `CATEGORY_NAME_TO_SLUG` and the listing would carry a category the
 * catalogue join cannot use (learning_join_vocabulary_slug_vs_display_name).
 *
 * Screen content is wrapped in `Animated.View` + `useEnterReveal`, which
 * docs/motion.md requires of every screen.
 *
 * ── Three things it is careful about ────────────────────────────────────────
 * 1. **The photo is the product.** A second-hand listing without a picture of
 *    the actual item is not a listing (spec §7). Uploaded AFTER creation —
 *    that is when `item_id` exists — which is also why the server contributes
 *    it to the catalogue from the upload endpoint, not from publish.
 * 2. **Catalogue consent is opt-in**, unticked, and shown only once there is a
 *    photo to consent about. ToS §3.
 * 3. **It says when a listing won't reach anyone** before they list, not after.
 *
 * Playbook (docs/ui-playbook.md): AnimatedPressable, theme colours only,
 * `colors.accentText` ONLY on an accent fill, safeGoBack, SafeAreaView from
 * safe-area-context, no iOS-only accessibilityRole.
 */
import React, { useCallback, useMemo, useState } from 'react';
import {
  View, Text, TextInput, StyleSheet, ScrollView, ActivityIndicator, Image, Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';

/** Buyer-facing gallery cap. See the photoUris comment for why 8. */
const MAX_PHOTOS = 8;

import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { showActionSheet } from '@/hooks/useActionSheetPicker';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { collectorsApi } from '@/api/collectorsApi';
import { matchCatalog, type CatalogMatchHit } from '@/api/itemsApi';
import { getCurrencySymbol } from '@/lib/format';
import { safeGoBack } from '@/lib/goBack';
import { CATEGORIES, CATEGORY_SLUG_TO_NAME } from '@/constants/categories';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';
import logger from '@/utils/logger';

/** Same vocabulary as ConditionValueSection. Two condition lists would drift,
 *  and a listing's condition is what a second-hand buyer reads first. */
const CONDITIONS = ['Mint', 'Near Mint', 'Excellent', 'Good', 'PSA 10', 'PSA 9', 'Raw'];

function SellNewScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  // Read BEFORE the state below, because the state is SEEDED from it. Params are
  // available on the first render, so a lazy `useState` initialiser is enough —
  // no effect, and therefore no effect that writes a value it also depends on
  // (see app/offers.tsx and scripts/check-self-cancelling-effects.mjs).
  //
  // `itemId` set = arriving from app/sell/pick.tsx. Its presence switches this
  // screen from "create an item and list it" to "list the item I already own",
  // which is a materially better listing: it inherits canonical_key and category
  // from the item, so the supply hook writes a buyable row and everyone watching
  // is alerted. One composer for both routes — two would drift, and this one
  // already owns the photo, the consent checkbox and the reach notice.
  //
  // The rest are the seed from the card the seller just tapped. The server still
  // derives name/category/canonical_key from `item_id`, so these only spare the
  // seller from retyping what they already told the app once.
  const {
    itemId, itemName, itemCategory, itemImage, itemValue, itemCondition,
  } = useLocalSearchParams<{
    itemId?: string; itemName?: string; itemCategory?: string;
    itemImage?: string; itemValue?: string; itemCondition?: string;
  }>();
  const fromCollection = typeof itemId === 'string' && itemId.length > 0;

  const [title, setTitle] = useState('');
  // Seeded from the item's valuation — the number the seller was already
  // looking at on the card. Empty when the item is unpriced (`itemValue` is
  // only sent when > 0), so the placeholder still reads as "type a price".
  const [price, setPrice] = useState(() => (fromCollection ? itemValue ?? '' : ''));
  const [categorySlug, setCategorySlug] = useState<string | null>(null);
  // The item's own condition, verbatim. It may sit outside CONDITIONS ("PSA 9",
  // a graded slab) and that is fine: `condition_label` is free text server-side,
  // and replacing the seller's real condition with the nearest vocabulary entry
  // would be us editing a factual claim about their item. Tapping the field
  // still offers the standard list.
  const [condition, setCondition] = useState<string | null>(
    () => (fromCollection && itemCondition ? itemCondition : null),
  );
  const [description, setDescription] = useState('');
  // Up to MAX_PHOTOS local files to upload after the listing exists.
  //
  // §8d: listings with 4+ photos sell ~3.5x faster than single-photo ones, and
  // the single `photoUri` this replaced was named there as the CLIENT limit —
  // `item_images` has taken many since 20260801_fix_item_images_schema.sql
  // (§1f: shape, RLS and a probe INSERT all verified; the 0 rows were only
  // because nothing had ever uploaded). 8 sits past the 4+ threshold that
  // drives the number without turning the flow into work on a phone, and well
  // inside the server's 30-uploads/hour rate limit.
  const [photoUris, setPhotoUris] = useState<string[]>([]);
  // The item's existing photo. NOT copied into `photoUris`: those mean "new
  // new local file to upload after creation", and re-uploading a photo the item
  // already has would duplicate the row in `item_images`. The listing inherits
  // this image from the item server-side (`P2PListing.image_url`), so here it
  // only has to be VISIBLE — the seller should see the picture their listing
  // will carry, and only pick a new one if they want a different shot.
  const inheritedImage = fromCollection && itemImage ? itemImage : null;
  const itemLabel = fromCollection ? (itemName ?? 'Your item') : null;
  const itemCategoryName = itemCategory
    ? (CATEGORY_SLUG_TO_NAME[itemCategory] ?? itemCategory)
    : null;

  const [consent, setConsent] = useState(false);
  const [saving, setSaving] = useState(false);
  // The catalogue match. `canonical_key` is what decides whether this listing
  // can EVER fire a Target Hit: `_publish_supply_hook` writes no buyable
  // market_hits row without one, so an unmatched listing reaches browsers only.
  // Measured 2026-08-08: 4 of 16 items carry one, and this screen never sent
  // one at all — so the marketplace's whole reason to exist (spec §1, supply
  // for the paid alert) was unreachable from the marketplace-only seller path.
  const [match, setMatch] = useState<CatalogMatchHit | null>(null);
  const [matching, setMatching] = useState(false);
  const [matchTried, setMatchTried] = useState(false);

  const parsedPrice = useMemo(() => {
    const n = parseFloat(price.replace(/[^0-9.,]/g, '').replace(',', '.'));
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [price]);

  // From the collection the SERVER supplies the name from the item, so a typed
  // title is neither required nor used. Requiring one would block the flow on a
  // field the seller cannot see.
  const canList = (fromCollection || title.trim().length >= 2)
    && parsedPrice != null && !saving;

  const categoryName = useMemo(
    () => CATEGORIES.find((c) => c.slug === categorySlug)?.name ?? null,
    [categorySlug],
  );

  // Resolve the free text against the catalogue. Same endpoint QuickScan,
  // add-manual and ItemCatalogRefresh already use — this is wiring, not a new
  // capability.
  //
  // Fires on BLUR of the title once a category is chosen, not per keystroke:
  // /catalog/match is a real search, and a request per character would be both
  // wasteful and racy (a late response overwriting a newer one).
  const runMatch = useCallback(async () => {
    const t = title.trim();
    if (t.length < 3 || !categorySlug || matching) return;
    setMatching(true);
    try {
      const res = await matchCatalog(t, categorySlug);
      // `best` only. The alternatives list is for a picker; offering five
      // near-identical printings to someone selling one thing is a decision
      // they cannot make from titles alone, and a WRONG canonical_key is worse
      // than none — it would point watchers of a different printing at this
      // listing (learning_keyword_filters_need_per_category_false_positive_audit).
      setMatch(res.best ?? null);
    } catch (e) {
      // Never blocks listing — a catalogue miss costs reach, not the sale.
      //
      // Still logger.ERROR: warn is stripped in release builds, and an
      // unmatched listing is precisely the failure worth seeing in production
      // (it cannot reach Target Hit, spec §8d). Silent in the build that
      // matters is how the canonical_key gap went unmeasured for months.
      logger.error('[sell/new] catalogue match failed:', e);
      setMatch(null);
    } finally {
      setMatching(false);
      setMatchTried(true);
    }
  }, [title, categorySlug, matching]);

  const pickPhoto = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    // Same two options and the same order as add-manual, so the choice is
    // muscle memory rather than a new decision on a new screen.
    showActionSheet('Add Photo', ['Take Photo', 'Choose from Library'], async (index) => {
      try {
        const remaining = MAX_PHOTOS - photoUris.length;
        if (remaining <= 0) return;
        // Not `as const` — ImagePickerOptions wants a MUTABLE MediaType[].
        const opts: ImagePicker.ImagePickerOptions = {
          mediaTypes: ['images'], quality: 0.9, allowsEditing: false,
        };
        // The camera returns one shot; the library takes several at once and
        // is capped to what is still free, so the picker cannot hand back more
        // than the strip will keep.
        const res = index === 0
          ? await ImagePicker.launchCameraAsync(opts)
          : await ImagePicker.launchImageLibraryAsync({
              ...opts,
              allowsMultipleSelection: true,
              selectionLimit: remaining,
            });
        if (res.canceled || !res.assets?.length) return;
        const picked = res.assets.map((a) => a.uri).filter(Boolean).slice(0, remaining);
        if (!picked.length) return;
        setPhotoUris((prev) => [...prev, ...picked].slice(0, MAX_PHOTOS));
      } catch (e) {
        // logger.error, not warn — warn is stripped in release builds, which is
        // where a silently missing photo would matter most.
        logger.error('[sell/new] photo pick failed:', e);
        showToast({ message: 'Could not open the camera or library.', type: 'error' });
      }
    });
  }, [settings.hapticsEnabled, showToast, photoUris.length]);

  const pickCategory = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    showActionSheet('Category', CATEGORIES.map((c) => c.name), (i) => {
      // Store the SLUG. The API takes a slug and the catalogue joins on it;
      // storing the display name is how a join silently matches nothing
      // (learning_join_vocabulary_slug_vs_display_name).
      setCategorySlug(CATEGORIES[i].slug);
    });
  }, [settings.hapticsEnabled]);

  const pickCondition = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    showActionSheet('Condition', CONDITIONS, (i) => setCondition(CONDITIONS[i]));
  }, [settings.hapticsEnabled]);

  const handleList = useCallback(async () => {
    if (!canList || parsedPrice == null) return;
    setSaving(true);
    try {
      // No item_id: the server creates the item. Consent is only sent when
      // there is actually a photo to consent about — sending true with no
      // photo would record a permission the seller never considered.
      const listing = await collectorsApi.createListing({
        // With an item_id the server INHERITS name, category and canonical_key
        // from the item and ignores the free-text fields — so sending them too
        // would be dead weight at best and a contradiction at worst. Ownership
        // is enforced server-side either way.
        ...(fromCollection
          ? { item_id: itemId }
          : {
              title: title.trim(),
              category: categorySlug ?? undefined,
              // The whole point of the match. Without this the server's supply
              // hook skips the listing and `reaches_target_hit` is false.
              canonical_key: match?.item_key ?? undefined,
            }),
        price: parsedPrice,
        currency: settings.currency,
        condition_label: condition ?? undefined,
        description: description.trim() || undefined,
        photo_catalogue_consent: photoUris.length > 0 ? consent : false,
      });

      // Uploaded after creation because that is when item_id exists. A failure
      // here must NOT read as "listing failed" — the listing is live either
      // way, so it degrades to a warning naming what to do next.
      if (photoUris.length > 0 && listing.item_id) {
        // SEQUENTIAL, deliberately — not Promise.all. `item_images.position` is
        // assigned server-side by append order, and that order IS the buyer's
        // gallery order, so racing the uploads would shuffle the seller's
        // photos. A gallery whose first photo is arbitrary is worse than one
        // photo, because the first frame is what the buyer judges the item on.
        let uploaded = 0;
        for (let i = 0; i < photoUris.length; i += 1) {
          try {
            // `item_images.label` is CHECK-constrained to
            // front|back|detail|box|certificate|damage|other (found 2026-08-22
            // when a seed used a marker string and was rejected). Sending
            // `undefined` was ACCEPTED — NULL satisfies a CHECK — but it threw
            // away a field the schema defines: the first photo is the `front`
            // every single-image reader falls back to, and the rest are
            // detail shots. Anything outside that vocabulary is rejected, so
            // do not invent values here.
            await collectorsApi.uploadItemImage(
              listing.item_id, photoUris[i], i === 0 ? 'front' : 'detail',
            );
            uploaded += 1;
          } catch (e) {
            // Keep going. One failed frame must not cost the others — the
            // listing is already live either way.
            logger.error('[sell/new] photo upload failed (index %s):', i, e);
          }
        }
        if (uploaded < photoUris.length) {
          showToast({
            message: uploaded === 0
              ? 'Listed, but the photos did not upload. Add them from the listing.'
              : `Listed with ${uploaded} of ${photoUris.length} photos. Add the rest from the listing.`,
            type: 'warning',
          });
        }
      }

      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({
        message: listing.reaches_target_hit
          ? 'Listed. Members watching this will be alerted.'
          : 'Listed on the marketplace.',
        type: 'success',
      });
      router.replace({ pathname: '/listing/[id]', params: { id: listing.id } });
    } catch (err: unknown) {
      logger.error('[sell/new] create failed:', err);
      showToast({
        message: (err as Error)?.message || 'Could not create the listing.',
        type: 'error',
      });
    } finally {
      setSaving(false);
    }
  }, [canList, parsedPrice, title, categorySlug, condition, description, photoUris,
      consent, settings.currency, settings.hapticsEnabled, showToast, router]);

  /** A tappable field that opens an action sheet. Same visual weight as the
   *  TextInputs beside it so the form reads as one thing. */
  const PickerField = ({
    label, value, placeholder, onPress, a11y,
  }: {
    label: string; value: string | null; placeholder: string;
    onPress: () => void; a11y: string;
  }) => (
    <>
      <Text style={[styles.label, { color: colors.text }]}>{label}</Text>
      <AnimatedPressable
        onPress={onPress}
        style={[styles.field, { borderColor: colors.border, backgroundColor: colors.card }]}
        accessibilityRole="button"
        accessibilityLabel={a11y}
      >
        <Text style={[styles.fieldText, { color: value ? colors.text : colors.muted }]}>
          {value ?? placeholder}
        </Text>
        <Ionicons name="chevron-down" size={16} color={colors.muted} />
      </AnimatedPressable>
    </>
  );

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <AnimatedPressable
          onPress={() => safeGoBack(router)}
          accessibilityRole="button"
          accessibilityLabel="Go back"
        >
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Sell an item</Text>
      </View>

      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Animated.View style={animatedStyle}>
          {/* Only the marketplace-only route needs explaining. From the
              collection the summary card below already says which item is being
              listed, which is the whole message — a paragraph restating it is
              noise (removed 2026-08-09: "self explanatory"). */}
          {!fromCollection ? (
            <Text style={[styles.lede, { color: colors.muted }]}>
              For something you own that isn&apos;t in your collection. We&apos;ll add
              it for you — you don&apos;t have to build a collection to sell.
            </Text>
          ) : null}

          {/* What you picked, shown back to you. Without this the composer gave
              no evidence at all that the selection had carried — same fields as
              the row that was tapped, so it reads as continuous with it. Not
              editable on purpose: these come from the item server-side, and a
              box whose input is silently discarded is worse than no box (the
              same reason Title and Category are hidden below). Change them by
              editing the item. */}
          {fromCollection ? (
            <View style={[styles.pickedRow, { backgroundColor: colors.card, borderColor: colors.border }]}>
              {inheritedImage ? (
                <Image source={{ uri: inheritedImage }} style={styles.pickedThumb} resizeMode="cover" />
              ) : (
                <View style={[styles.pickedThumb, styles.pickedThumbEmpty, { backgroundColor: colors.accent + '12' }]}>
                  <Ionicons name="image-outline" size={18} color={colors.muted} />
                </View>
              )}
              <View style={styles.pickedBody}>
                <Text style={[styles.pickedTitle, { color: colors.text }]} numberOfLines={2}>
                  {itemLabel}
                </Text>
                {itemCategoryName ? (
                  <Text style={[styles.pickedMeta, { color: colors.muted }]} numberOfLines={1}>
                    {itemCategoryName}
                  </Text>
                ) : null}
              </View>
            </View>
          ) : null}

          {/* Photo first: it is the product, and a second-hand listing without
              one is not a listing. From the collection the item's own photo is
              what the listing carries, so this section stops demanding one and
              becomes "use a different shot if you want". */}
          <Text style={[styles.label, { color: colors.text }]}>Photo</Text>
          {photoUris.length === 0 && inheritedImage ? (
            <View>
              <Image source={{ uri: inheritedImage }} style={styles.photo} resizeMode="cover" />
              <View style={styles.photoActions}>
                <AnimatedPressable
                  onPress={pickPhoto}
                  accessibilityRole="button"
                  accessibilityLabel="Add your own photos for this listing"
                >
                  <Text style={[styles.link, { color: colors.accent }]}>Add your own photos</Text>
                </AnimatedPressable>
              </View>
              <Text style={[styles.fine, { color: colors.muted }]}>
                Your item&apos;s photo. The listing uses this unless you add your own.
              </Text>
            </View>
          ) : photoUris.length > 0 ? (
            <View>
              {/* The FIRST photo is the hero: it is the listing thumbnail and
                  the frame a buyer judges the item on, so it gets the size. */}
              <Image source={{ uri: photoUris[0] }} style={styles.photo} resizeMode="cover" />
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.photoStrip}
              >
                {photoUris.map((uri, idx) => (
                  <View key={`${uri}-${idx}`} style={styles.thumbWrap}>
                    <Image source={{ uri }} style={styles.thumb} resizeMode="cover" />
                    {idx === 0 ? (
                      <View style={[styles.thumbBadge, { backgroundColor: colors.accent }]}>
                        <Text style={[styles.thumbBadgeText, { color: colors.accentText }]}>
                          Cover
                        </Text>
                      </View>
                    ) : null}
                    <AnimatedPressable
                      onPress={() => {
                        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                        // Computed OUTSIDE the updater. A state updater has to
                        // be pure — React may invoke it twice (StrictMode) —
                        // and calling setConsent from inside one is how you get
                        // a double-fired side effect that only misbehaves in
                        // dev, or only in prod.
                        const next = photoUris.filter((_, k) => k !== idx);
                        setPhotoUris(next);
                        // Consent is about photos the seller supplied; with
                        // none left there is nothing to consent about.
                        if (next.length === 0) setConsent(false);
                      }}
                      style={styles.thumbRemove}
                      hitSlop={8}
                      accessibilityRole="button"
                      accessibilityLabel={`Remove photo ${idx + 1} of ${photoUris.length}`}
                    >
                      <Ionicons name="close-circle" size={20} color={colors.text} />
                    </AnimatedPressable>
                  </View>
                ))}
                {photoUris.length < MAX_PHOTOS ? (
                  <AnimatedPressable
                    onPress={pickPhoto}
                    style={[styles.addTile, { borderColor: colors.border, backgroundColor: colors.card }]}
                    accessibilityRole="button"
                    accessibilityLabel={`Add another photo. ${photoUris.length} of ${MAX_PHOTOS} added`}
                  >
                    <Ionicons name="add" size={22} color={colors.accent} />
                  </AnimatedPressable>
                ) : null}
              </ScrollView>
              <Text style={[styles.fine, { color: colors.muted }]}>
                {photoUris.length} of {MAX_PHOTOS} photos. The first is the cover.
              </Text>
            </View>
          ) : (
            <AnimatedPressable
              onPress={pickPhoto}
              style={[styles.photoEmpty, { borderColor: colors.border, backgroundColor: colors.card }]}
              accessibilityRole="button"
              accessibilityLabel="Add photos of the item"
            >
              <Ionicons name="camera-outline" size={22} color={colors.muted} />
              <Text style={[styles.photoEmptyText, { color: colors.muted }]}>
                Add photos of the actual item
              </Text>
            </AnimatedPressable>
          )}

          {/* Only once there IS a photo — asking about catalogue reuse before
              one exists is asking about nothing. */}
          {photoUris.length > 0 ? (
            <AnimatedPressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                setConsent((c) => !c);
              }}
              style={[styles.consent, { borderColor: colors.border }]}
              accessibilityRole="checkbox"
              accessibilityState={{ checked: consent }}
              accessibilityLabel="Allow your cover photo to be used as a catalogue reference picture"
            >
              <Ionicons
                name={consent ? 'checkbox' : 'square-outline'}
                size={20}
                color={consent ? colors.accent : colors.muted}
              />
              <Text style={[styles.consentText, { color: colors.muted }]}>
                Let Sparrow use your cover photo as a reference picture for this
                product, shown to other members. Optional, and you can turn it
                off later.
              </Text>
            </AnimatedPressable>
          ) : null}

          {/* Hidden when listing something you already own: the server inherits
              name, category and canonical_key from the item, so showing empty
              fields here would invite the seller to type values that are
              silently ignored — and a field whose input does nothing is worse
              than no field. */}
          {!fromCollection && (
          <>
          <Text style={[styles.label, { color: colors.text }]}>What is it?</Text>
          <TextInput
            value={title}
            onChangeText={setTitle}
            placeholder="e.g. Blue-Eyes White Dragon, 1st edition"
            placeholderTextColor={colors.muted}
            maxLength={200}
            style={[styles.field, styles.fieldText, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
            accessibilityLabel="What are you selling"
            // On blur, not per keystroke: /catalog/match is a real search, and
            // a request per character is wasteful and racy.
            onBlur={runMatch}
          />

          <PickerField
            label="Category"
            value={categoryName}
            placeholder="Choose a category"
            onPress={pickCategory}
            a11y="Choose a category"
          />
          </>
          )}

          <Text style={[styles.label, { color: colors.text }]}>Price</Text>
          <View style={[styles.field, { borderColor: colors.border, backgroundColor: colors.card }]}>
            <Text style={[styles.currency, { color: colors.muted }]}>
              {getCurrencySymbol(settings.currency)}
            </Text>
            <TextInput
              value={price}
              onChangeText={setPrice}
              placeholder="0"
              placeholderTextColor={colors.muted}
              keyboardType="decimal-pad"
              style={[styles.priceInput, { color: colors.text }]}
              accessibilityLabel="Asking price"
            />
          </View>

          <PickerField
            label="Condition"
            value={condition}
            placeholder="Choose a condition"
            onPress={pickCondition}
            a11y="Choose a condition"
          />

          <Text style={[styles.label, { color: colors.text }]}>Description (optional)</Text>
          <TextInput
            value={description}
            onChangeText={setDescription}
            // The item's own description is NOT copied into this box: it is not
            // in ITEMS_SELECT, and widening the app's hottest read to prefill a
            // textarea is not a proportionate trade (same call as sell/pick.tsx
            // makes about canonical_key). The SERVER inherits it from the item
            // when this is left empty, so the placeholder has to say so —
            // otherwise an empty box reads as "your description was lost".
            placeholder={fromCollection
              ? "Using your item's description — type here to replace it"
              : "Anything a buyer should know — flaws, damage, what's included"}
            placeholderTextColor={colors.muted}
            multiline
            maxLength={4000}
            style={[styles.field, styles.multiline, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
            accessibilityLabel="Description"
          />

          {/* Reach, stated BEFORE listing and derived from the ACTUAL match.
              This used to be a static paragraph telling the seller to "add it to
              your collection and match it to a catalogue entry first" — which is
              precisely the friction spec §5c says this screen exists to remove,
              and it was the only advice available because the screen never ran a
              match itself. Now it does, so this reports a fact rather than
              issuing a chore.

              Four distinct states. Empty is NOT loading (docs/ui-playbook.md),
              and "no match" is not the same as "not checked yet" — collapsing
              those would tell a seller their item is unmatchable before anything
              looked. */}
          {matching ? (
            <View style={[styles.notice, { borderColor: colors.border }]}>
              <ActivityIndicator size="small" color={colors.muted} />
              <Text style={[styles.noticeText, { color: colors.muted }]}>
                Checking the catalogue…
              </Text>
            </View>
          ) : match ? (
            <View style={[styles.notice, { borderColor: colors.accent + '55', backgroundColor: colors.accent + '12' }]}>
              <Ionicons name="checkmark-circle" size={16} color={colors.accent} />
              <Text style={[styles.noticeText, { color: colors.text }]}>
                Matched to <Text style={{ fontWeight: fontWeight.bold }}>{match.title}</Text>.
                Members watching this item will be alerted when you list it.
              </Text>
            </View>
          ) : matchTried ? (
            <View style={[styles.notice, { borderColor: colors.border }]}>
              <Ionicons name="information-circle-outline" size={16} color={colors.muted} />
              <Text style={[styles.noticeText, { color: colors.muted }]}>
                No catalogue match for that title. It will still show in browse and
                search — try the exact product name to also reach members watching
                for it.
              </Text>
            </View>
          ) : null}

          {/* accentText ONLY on the accent fill — on a border fill it is
              invisible in high-contrast dark (docs/ui-playbook.md). */}
          <AnimatedPressable
            onPress={handleList}
            disabled={!canList}
            style={[
              styles.cta,
              canList
                ? { backgroundColor: colors.accent }
                : { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
            ]}
            accessibilityRole="button"
            accessibilityState={{ disabled: !canList }}
            accessibilityLabel="List it on the marketplace"
          >
            {saving ? (
              <ActivityIndicator color={canList ? colors.accentText : colors.muted} />
            ) : (
              <Text style={[styles.ctaText, { color: canList ? colors.accentText : colors.muted }]}>
                List it
              </Text>
            )}
          </AnimatedPressable>

          <Text style={[styles.fine, { color: colors.muted }]}>
            Sparrow doesn&apos;t handle payment or delivery — you arrange those with
            the buyer directly.
          </Text>
          <View style={{ height: 40 }} />
        </Animated.View>
      </ScrollView>
    </SafeAreaView>
  );
}

export default function SellNewScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Sell New Item">
      <SellNewScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  header: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  headerTitle: { fontSize: 18, fontWeight: fontWeight.bold },
  // 16 is the app-wide screen gutter (docs/ui-playbook.md).
  content: { padding: 16 },
  lede: { fontSize: textToken.sm, lineHeight: 19, marginBottom: 8 },
  // The picked-item summary. Mirrors the row layout in app/sell/pick.tsx so the
  // handoff reads as the same object, not a new one.
  pickedRow: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md,
    padding: 10, marginBottom: 4,
  },
  pickedThumb: { width: 48, height: 48, borderRadius: radius.sm },
  pickedThumbEmpty: { alignItems: 'center', justifyContent: 'center' },
  pickedBody: { flex: 1, gap: 2 },
  pickedTitle: { fontSize: textToken.md, fontWeight: fontWeight.semibold },
  pickedMeta: { fontSize: textToken.sm },
  label: { fontSize: textToken.sm, fontWeight: fontWeight.semibold, marginTop: 14, marginBottom: 6 },
  // ONE field shape shared by the text inputs and the pickers, so a form of
  // mixed control types still reads as a single form.
  field: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    borderWidth: 1, borderRadius: radius.sm,
    paddingHorizontal: 12, paddingVertical: 12, minHeight: 46,
  },
  fieldText: { flex: 1, fontSize: textToken.md },
  multiline: { minHeight: 88, textAlignVertical: 'top', alignItems: 'flex-start' },
  currency: { fontSize: textToken.md, fontWeight: fontWeight.semibold },
  priceInput: { flex: 1, fontSize: textToken.md, padding: 0 },
  photo: { width: '100%', aspectRatio: 1, borderRadius: radius.md },
  photoActions: { flexDirection: 'row', gap: 16, marginTop: 8 },
  photoEmpty: {
    borderWidth: 1, borderStyle: 'dashed', borderRadius: radius.md,
    alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 34,
  },
  photoEmptyText: { fontSize: textToken.sm },
  // Horizontal strip under the hero. A horizontal scroller nested in the
  // screen's vertical one is fine — different axes, no gesture conflict.
  photoStrip: { flexDirection: 'row', gap: 8, marginTop: 8, paddingRight: 4 },
  thumbWrap: { width: 64, height: 64 },
  thumb: { width: 64, height: 64, borderRadius: radius.sm },
  // The remove control sits ON the thumbnail, so it needs hitSlop rather than
  // padding: padding would shrink the visible glyph inside a 64pt tile.
  thumbRemove: { position: 'absolute', top: -6, right: -6 },
  thumbBadge: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    borderBottomLeftRadius: radius.sm, borderBottomRightRadius: radius.sm,
    alignItems: 'center', paddingVertical: 2,
  },
  // `sm`, not `xs`: 10pt is banned for anything a user reads (ui-playbook).
  thumbBadgeText: { fontSize: textToken.sm, fontWeight: fontWeight.semibold },
  addTile: {
    width: 64, height: 64, borderRadius: radius.sm,
    borderWidth: 1, borderStyle: 'dashed',
    alignItems: 'center', justifyContent: 'center',
  },
  link: { fontSize: textToken.sm, fontWeight: fontWeight.semibold },
  consent: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.sm,
    padding: 11, marginTop: 12,
  },
  consentText: { flex: 1, fontSize: textToken.xs, lineHeight: 17 },
  notice: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 8,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.sm,
    padding: 10, marginTop: 18,
  },
  noticeText: { flex: 1, fontSize: textToken.xs, lineHeight: 17 },
  cta: {
    alignItems: 'center', justifyContent: 'center',
    paddingVertical: 14, borderRadius: radius.md, marginTop: 18,
  },
  ctaText: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  fine: { fontSize: textToken.xs, textAlign: 'center', marginTop: 12, lineHeight: 16 },
});
