/**
 * "Sell on Sparrow" — list an item you own on the member marketplace.
 *
 * Stage 1 of docs/P2P_MARKETPLACE_SPEC.md: listings only, no payments.
 *
 * Two deliberate behaviours:
 *
 * 1. **Price is prefilled from the predicted value.** This is where the
 *    valuation work becomes visible to the user — the alternative is a blank
 *    box and a guess, which produces mispriced listings that never sell.
 * 2. **An unmatched item warns before listing.** A listing with no
 *    `canonical_key` cannot join Target Hit's exact-identity arm, so nobody
 *    watching that item gets alerted. Saying nothing would leave the seller to
 *    wonder why their listing gets no views — the silent-failure pattern this
 *    codebase keeps paying for. The warning is not a blocker: unmatched items
 *    are still worth listing, they just travel further if matched first.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, TextInput, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useToast } from '@/components/Toast';
import { collectorsApi } from '@/api/collectorsApi';
import { getCurrencySymbol } from '@/lib/format';
import type { CurrencyCode } from '@/data/types';
import type { DemandPreview } from '@/api/p2pApi';
import { formatPrice } from '@/lib/format';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';
import logger from '@/utils/logger';

type ThemeColors = {
  text: string; muted: string; card: string; border: string;
  background: string; accent: string; accentText: string; warning: string;
};

type Props = {
  itemId: string;
  colors: ThemeColors;
  currency: CurrencyCode;
  hapticsEnabled: boolean;
  /** Suggested price — the model's mid estimate, when we have one. */
  suggestedPrice?: number | null;
  /** Bare canonical key. Null/undefined means the item is not catalog-matched,
   *  which is what limits the listing's reach — see the file header. */
  canonicalKey?: string | null;
  /** Opens the catalog re-match flow (ItemCatalogRefresh already exists). */
  onRequestCatalogMatch?: () => void;
  /** Does this item have a photo of its own? The catalogue-consent question is
   *  only meaningful when there is a photo to consent about — asking otherwise
   *  is asking about nothing. */
  hasPhoto?: boolean;
};

export function SellOnSparrowSection({
  itemId,
  colors,
  currency,
  hapticsEnabled,
  suggestedPrice,
  canonicalKey,
  onRequestCatalogMatch,
  hasPhoto,
}: Props) {
  const { showToast } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [price, setPrice] = useState(
    suggestedPrice != null && suggestedPrice > 0 ? suggestedPrice.toFixed(2) : '',
  );
  const [condition, setCondition] = useState('');
  const [saving, setSaving] = useState(false);
  const [listed, setListed] = useState(false);
  const [demand, setDemand] = useState<DemandPreview | null>(null);
  // Opt-in, unticked. ToS §3 grants catalogue reuse only if the seller says so.
  const [catalogueConsent, setCatalogueConsent] = useState(false);

  // Demand is fetched when the form OPENS, not on mount: it costs a request
  // and most item views never reach the sell flow.
  useEffect(() => {
    if (!expanded) return;
    let cancelled = false;
    collectorsApi
      .getDemandPreview(itemId, parsedPriceRef.current ?? undefined)
      .then((d) => { if (!cancelled) setDemand(d); })
      .catch((e) => logger.error('[SellOnSparrow] demand fetch failed:', e));
    return () => { cancelled = true; };
    // Price deliberately NOT a dependency — refetching on every keystroke
    // would hammer the endpoint. The above-price count is recomputed
    // client-side from top_target instead.
  }, [expanded, itemId]);

  const isMatched = Boolean(canonicalKey);

  const parsedPrice = useMemo(() => {
    const n = parseFloat(price.replace(/[^0-9.]/g, ''));
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [price]);
  const parsedPriceRef = React.useRef<number | null>(null);
  parsedPriceRef.current = parsedPrice;

  // Would this price reach the top watcher? Recomputed locally as the seller
  // types, so the number responds instantly without a request per keystroke.
  const reachesTopTarget =
    demand?.top_target != null && parsedPrice != null && demand.top_target >= parsedPrice;

  const handleList = useCallback(async () => {
    if (!parsedPrice) {
      showToast({ message: 'Enter a price above 0.', type: 'warning' });
      return;
    }
    setSaving(true);
    try {
      await collectorsApi.createListing({
        item_id: itemId,
        price: parsedPrice,
        currency,
        condition_label: condition.trim() || undefined,
        // Only when there IS a photo — sending true otherwise would record a
        // permission the seller had no reason to consider.
        photo_catalogue_consent: hasPhoto ? catalogueConsent : false,
      });
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: hapticsEnabled });
      setListed(true);
      showToast({
        message: isMatched
          ? 'Listed. Members watching this will be alerted.'
          : 'Listed on the marketplace.',
        type: 'success',
      });
    } catch (err: unknown) {
      // 409 ALREADY_LISTED is a normal outcome, not a failure — surface the
      // server's message rather than a generic error.
      const msg = (err as Error)?.message || 'Could not create the listing.';
      logger.error('[SellOnSparrow] create failed:', err);
      showToast({ message: msg, type: 'error' });
    } finally {
      setSaving(false);
    }
  }, [parsedPrice, itemId, currency, condition, hapticsEnabled, isMatched, showToast,
      hasPhoto, catalogueConsent]);

  if (listed) {
    return (
      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.row}>
          <Ionicons name="checkmark-circle" size={18} color={colors.accent} />
          <Text style={[styles.title, { color: colors.text }]}>Listed on the marketplace</Text>
        </View>
      </View>
    );
  }

  if (!expanded) {
    return (
      <AnimatedPressable
        onPress={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
          setExpanded(true);
        }}
        style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
        accessibilityRole="button"
        accessibilityLabel="Sell this on the Sparrow marketplace"
      >
        <View style={styles.row}>
          <View style={[styles.icon, { backgroundColor: colors.accent + '18' }]}>
            <Ionicons name="pricetag-outline" size={16} color={colors.accent} />
          </View>
          <View style={styles.grow}>
            <Text style={[styles.title, { color: colors.text }]}>Sell this</Text>
            <Text style={[styles.sub, { color: colors.muted }]}>
              List it for other members to buy
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </View>
      </AnimatedPressable>
    );
  }

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.row}>
        <Text style={[styles.title, { color: colors.text }]}>Sell this</Text>
        <View style={styles.grow} />
        <AnimatedPressable
          onPress={() => setExpanded(false)}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          accessibilityRole="button"
          accessibilityLabel="Cancel"
        >
          <Ionicons name="close" size={18} color={colors.muted} />
        </AnimatedPressable>
      </View>

      {/* Reach warning. Not a blocker — see the file header. */}
      {!isMatched ? (
        <View style={[styles.warn, { borderColor: colors.warning + '55', backgroundColor: colors.warning + '12' }]}>
          <Ionicons name="alert-circle-outline" size={15} color={colors.warning} />
          <View style={styles.grow}>
            <Text style={[styles.warnText, { color: colors.text }]}>
              This item isn&apos;t matched to the catalog, so members watching it
              won&apos;t be alerted when you list.
            </Text>
            {onRequestCatalogMatch ? (
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                  onRequestCatalogMatch();
                }}
                accessibilityRole="button"
                accessibilityLabel="Match this item to the catalog"
              >
                <Text style={[styles.warnLink, { color: colors.accent }]}>Match it first</Text>
              </AnimatedPressable>
            ) : null}
          </View>
        </View>
      ) : null}

      {/* THE seller-acquisition line. No generic marketplace can show this:
          they infer intent from a feed or wait for a search, we know what
          members want before they look. Rendered only when there is real
          demand — "0 members watching" is discouraging AND uninformative. */}
      {demand && demand.is_catalog_matched && demand.watchers > 0 ? (
        <View style={[styles.demand, { backgroundColor: colors.accent + '12', borderColor: colors.accent + '44' }]}>
          <Ionicons name="eye-outline" size={15} color={colors.accent} />
          <View style={styles.grow}>
            <Text style={[styles.demandText, { color: colors.text }]}>
              {demand.watchers} member{demand.watchers === 1 ? '' : 's'} watching this
              {demand.top_target != null
                ? ` · highest target ${formatPrice(demand.top_target, currency)}`
                : ''}
            </Text>
            {reachesTopTarget ? (
              <Text style={[styles.demandHit, { color: colors.accent }]}>
                At this price they&apos;ll be alerted the moment you list.
              </Text>
            ) : demand.top_target != null && parsedPrice != null ? (
              <Text style={[styles.demandMiss, { color: colors.muted }]}>
                Price at or below {formatPrice(demand.top_target, currency)} to alert them.
              </Text>
            ) : null}
          </View>
        </View>
      ) : null}

      <Text style={[styles.label, { color: colors.muted }]}>Price ({currency})</Text>
      <View style={[styles.priceRow, { borderColor: colors.border, backgroundColor: colors.background }]}>
        <Text style={[styles.currency, { color: colors.muted }]}>{getCurrencySymbol(currency)}</Text>
        <TextInput
          style={[styles.priceInput, { color: colors.text }]}
          value={price}
          onChangeText={setPrice}
          keyboardType="decimal-pad"
          placeholder="0.00"
          placeholderTextColor={colors.muted}
          accessibilityLabel={`Asking price in ${currency}`}
        />
      </View>
      {suggestedPrice != null && suggestedPrice > 0 ? (
        <Text style={[styles.hint, { color: colors.muted }]}>
          Prefilled from our estimate. Adjust to what you&apos;d accept.
        </Text>
      ) : null}

      <Text style={[styles.label, { color: colors.muted }]}>Condition (optional)</Text>
      <TextInput
        style={[styles.input, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
        value={condition}
        onChangeText={setCondition}
        placeholder="e.g. Near Mint"
        placeholderTextColor={colors.muted}
        maxLength={64}
        accessibilityLabel="Condition"
      />

      {/* Catalogue contribution. 54,115 of 221,391 catalogue items have no
          image; a seller photographing a real copy can close that gap. Opt-in
          and revocable (ToS §3), and shown only when there is a photo. */}
      {hasPhoto ? (
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
            setCatalogueConsent((c) => !c);
          }}
          style={[styles.consent, { borderColor: colors.border }]}
          accessibilityRole="checkbox"
          accessibilityState={{ checked: catalogueConsent }}
          accessibilityLabel="Allow this photo to be used as a catalogue reference picture"
        >
          <Ionicons
            name={catalogueConsent ? 'checkbox' : 'square-outline'}
            size={19}
            color={catalogueConsent ? colors.accent : colors.muted}
          />
          <Text style={[styles.consentText, { color: colors.muted }]}>
            Let Sparrow use your photo as a reference picture for this product,
            shown to other members. Optional, and you can turn it off later.
          </Text>
        </AnimatedPressable>
      ) : null}

      <AnimatedPressable
        onPress={handleList}
        disabled={saving || !parsedPrice}
        style={[
          styles.cta,
          { backgroundColor: parsedPrice ? colors.accent : colors.border },
          saving && styles.ctaSaving,
        ]}
        accessibilityRole="button"
        accessibilityState={{ disabled: saving || !parsedPrice }}
        accessibilityLabel={saving ? 'Listing' : 'List on the marketplace'}
      >
        {saving ? (
          <ActivityIndicator size="small" color={colors.accentText} />
        ) : (
          <Text style={[styles.ctaText, { color: parsedPrice ? colors.accentText : colors.muted }]}>
            List on the marketplace
          </Text>
        )}
      </AnimatedPressable>

      {/* Set expectations before the tap, not after. */}
      <Text style={[styles.hint, { color: colors.muted }]}>
        Buyers message you directly. Sparrow doesn&apos;t handle payment or delivery.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  consent: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.sm,
    padding: 11, marginTop: 14,
  },
  consentText: { flex: 1, fontSize: textToken.xs, lineHeight: 17 },
  card: { borderWidth: 1, borderRadius: radius.md, padding: 14, marginTop: 16, gap: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  grow: { flex: 1 },
  icon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  sub: { fontSize: textToken.xs, marginTop: 1 },
  label: { fontSize: textToken.xs, marginTop: 6 },
  priceRow: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    borderWidth: 1, borderRadius: radius.sm, paddingHorizontal: 10,
  },
  currency: { fontSize: textToken.md },
  priceInput: { flex: 1, fontSize: textToken.lg, fontWeight: fontWeight.bold, paddingVertical: 10 },
  input: { borderWidth: 1, borderRadius: radius.sm, paddingHorizontal: 10, paddingVertical: 9, fontSize: textToken.md },
  demand: {
    flexDirection: 'row', gap: 8, alignItems: 'flex-start',
    borderWidth: 1, borderRadius: radius.sm, padding: 10, marginTop: 4,
  },
  demandText: { fontSize: textToken.xs, lineHeight: 17, fontWeight: fontWeight.semibold },
  demandHit: { fontSize: textToken.xs, lineHeight: 17, marginTop: 3, fontWeight: fontWeight.bold },
  demandMiss: { fontSize: textToken.xs, lineHeight: 17, marginTop: 3 },
  warn: {
    flexDirection: 'row', gap: 8, alignItems: 'flex-start',
    borderWidth: 1, borderRadius: radius.sm, padding: 10, marginTop: 4,
  },
  warnText: { fontSize: textToken.xs, lineHeight: 17 },
  warnLink: { fontSize: textToken.xs, fontWeight: fontWeight.bold, marginTop: 4 },
  hint: { fontSize: textToken.xs, lineHeight: 16, marginTop: 2 },
  cta: { marginTop: 10, paddingVertical: 12, borderRadius: radius.md, alignItems: 'center' },
  ctaSaving: { opacity: 0.8 },
  ctaText: { fontSize: textToken.md, fontWeight: fontWeight.bold },
});
