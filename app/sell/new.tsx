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
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';

import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { showActionSheet } from '@/hooks/useActionSheetPicker';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { collectorsApi } from '@/api/collectorsApi';
import { getCurrencySymbol } from '@/lib/format';
import { safeGoBack } from '@/lib/goBack';
import { CATEGORIES } from '@/constants/categories';
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

  const [title, setTitle] = useState('');
  const [price, setPrice] = useState('');
  const [categorySlug, setCategorySlug] = useState<string | null>(null);
  const [condition, setCondition] = useState<string | null>(null);
  const [description, setDescription] = useState('');
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [saving, setSaving] = useState(false);

  const parsedPrice = useMemo(() => {
    const n = parseFloat(price.replace(/[^0-9.]/g, ''));
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [price]);

  const canList = title.trim().length >= 2 && parsedPrice != null && !saving;

  const categoryName = useMemo(
    () => CATEGORIES.find((c) => c.slug === categorySlug)?.name ?? null,
    [categorySlug],
  );

  const pickPhoto = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    // Same two options and the same order as add-manual, so the choice is
    // muscle memory rather than a new decision on a new screen.
    showActionSheet('Add Photo', ['Take Photo', 'Choose from Library'], async (index) => {
      try {
        // Not `as const` — ImagePickerOptions wants a MUTABLE MediaType[].
        const opts: ImagePicker.ImagePickerOptions = {
          mediaTypes: ['images'], quality: 0.9, allowsEditing: false,
        };
        const res = index === 0
          ? await ImagePicker.launchCameraAsync(opts)
          : await ImagePicker.launchImageLibraryAsync(opts);
        if (res.canceled || !res.assets?.[0]?.uri) return;
        setPhotoUri(res.assets[0].uri);
      } catch (e) {
        // logger.error, not warn — warn is stripped in release builds, which is
        // where a silently missing photo would matter most.
        logger.error('[sell/new] photo pick failed:', e);
        showToast({ message: 'Could not open the camera or library.', type: 'error' });
      }
    });
  }, [settings.hapticsEnabled, showToast]);

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
        title: title.trim(),
        price: parsedPrice,
        currency: settings.currency,
        category: categorySlug ?? undefined,
        condition_label: condition ?? undefined,
        description: description.trim() || undefined,
        photo_catalogue_consent: photoUri ? consent : false,
      });

      // Uploaded after creation because that is when item_id exists. A failure
      // here must NOT read as "listing failed" — the listing is live either
      // way, so it degrades to a warning naming what to do next.
      if (photoUri && listing.item_id) {
        try {
          await collectorsApi.uploadItemImage(listing.item_id, photoUri, 'front');
        } catch (e) {
          logger.error('[sell/new] photo upload failed:', e);
          showToast({
            message: 'Listed, but the photo did not upload. Add it from the listing.',
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
  }, [canList, parsedPrice, title, categorySlug, condition, description, photoUri,
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
          <Text style={[styles.lede, { color: colors.muted }]}>
            For something you own that isn&apos;t in your collection. We&apos;ll add
            it for you — you don&apos;t have to build a collection to sell.
          </Text>

          {/* Photo first: it is the product, and a second-hand listing without
              one is not a listing. */}
          <Text style={[styles.label, { color: colors.text }]}>Photo</Text>
          {photoUri ? (
            <View>
              <Image source={{ uri: photoUri }} style={styles.photo} resizeMode="cover" />
              <View style={styles.photoActions}>
                <AnimatedPressable
                  onPress={pickPhoto}
                  accessibilityRole="button"
                  accessibilityLabel="Choose a different photo"
                >
                  <Text style={[styles.link, { color: colors.accent }]}>Change</Text>
                </AnimatedPressable>
                <AnimatedPressable
                  onPress={() => { setPhotoUri(null); setConsent(false); }}
                  accessibilityRole="button"
                  accessibilityLabel="Remove the photo"
                >
                  <Text style={[styles.link, { color: colors.muted }]}>Remove</Text>
                </AnimatedPressable>
              </View>
            </View>
          ) : (
            <AnimatedPressable
              onPress={pickPhoto}
              style={[styles.photoEmpty, { borderColor: colors.border, backgroundColor: colors.card }]}
              accessibilityRole="button"
              accessibilityLabel="Add a photo of the item"
            >
              <Ionicons name="camera-outline" size={22} color={colors.muted} />
              <Text style={[styles.photoEmptyText, { color: colors.muted }]}>
                Add a photo of the actual item
              </Text>
            </AnimatedPressable>
          )}

          {/* Only once there IS a photo — asking about catalogue reuse before
              one exists is asking about nothing. */}
          {photoUri ? (
            <AnimatedPressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                setConsent((c) => !c);
              }}
              style={[styles.consent, { borderColor: colors.border }]}
              accessibilityRole="checkbox"
              accessibilityState={{ checked: consent }}
              accessibilityLabel="Allow this photo to be used as a catalogue reference picture"
            >
              <Ionicons
                name={consent ? 'checkbox' : 'square-outline'}
                size={20}
                color={consent ? colors.accent : colors.muted}
              />
              <Text style={[styles.consentText, { color: colors.muted }]}>
                Let Sparrow use this photo as a reference picture for this product,
                shown to other members. Optional, and you can turn it off later.
              </Text>
            </AnimatedPressable>
          ) : null}

          <Text style={[styles.label, { color: colors.text }]}>What is it?</Text>
          <TextInput
            value={title}
            onChangeText={setTitle}
            placeholder="e.g. Blue-Eyes White Dragon, 1st edition"
            placeholderTextColor={colors.muted}
            maxLength={200}
            style={[styles.field, styles.fieldText, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
            accessibilityLabel="What are you selling"
          />

          <PickerField
            label="Category"
            value={categoryName}
            placeholder="Choose a category"
            onPress={pickCategory}
            a11y="Choose a category"
          />

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
            placeholder="Anything a buyer should know — flaws, damage, what's included"
            placeholderTextColor={colors.muted}
            multiline
            maxLength={4000}
            style={[styles.field, styles.multiline, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
            accessibilityLabel="Description"
          />

          {/* Honest about reach BEFORE they list. A free-text listing has no
              canonical_key, so the supply hook skips it and nobody watching
              the item is alerted. */}
          <View style={[styles.notice, { borderColor: colors.border }]}>
            <Ionicons name="information-circle-outline" size={16} color={colors.muted} />
            <Text style={[styles.noticeText, { color: colors.muted }]}>
              This listing will show in browse and search. To also alert members
              watching for this exact item, add it to your collection and match it
              to a catalogue entry first.
            </Text>
          </View>

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
