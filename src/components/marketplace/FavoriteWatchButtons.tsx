/**
 * The heart and the eye, side by side on a listing card.
 *
 * TWO CONTROLS BECAUSE THERE ARE TWO INTENTS, and the whole reason this
 * component exists is to keep them from collapsing back into one:
 *
 *   ♥  favourite  → saved. Free, unlimited, promises nothing.
 *   👁  watch      → a TARGET PRICE and a Target Hit alert. Plan-gated.
 *
 * A single heart that wrote a watchlist row was built on the marketplace grid
 * 2026-08-08 and removed the same day. It called `addWatchlistItem` with no
 * `targetPrice`, and `_check_watchlist_snipes` filters
 * `WHERE target_price IS NOT NULL AND target_price > 0` — so every row it wrote
 * was inert, while the control's own accessibility label promised the member
 * they would "get alerted on price drops". docs/alerts-and-insights.md records
 * it as the FOURTH instance of that writer bug and sets the rule this component
 * obeys: **a one-tap watch control must either set a target price or say
 * plainly that it has not.**
 *
 * This one sets it. The target is the listing's CURRENT price, which makes the
 * promise literally true — "tell me if it drops below what it is listed at now"
 * — and produces a row that satisfies all three conditions a snipe-capable row
 * needs: `target_price > 0`, a SLUG category, and an `item_id`.
 */
import React, { useState } from 'react';
import { View, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useFavorites } from '@/hooks/useFavorites';
import { dataProvider } from '@/data';
import { useToast } from '@/components/Toast';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import type { CurrencyCode } from '@/data/types';
import logger from '@/utils/logger';

type Props = {
  /** `marketplace_listings.id`. */
  listingId: string;
  /** Bare canonical key — what the watchlist row points AT
   *  (`watchlist_items.item_id` is TEXT and holds catalog keys, not items.id). */
  canonicalKey: string | null;
  /** SLUG ('mtg'), never a display name. The watchlist join compares this
   *  against `market_hits.category`, which is slug vocabulary. */
  category: string | null;
  /** Asking price — becomes the watchlist target verbatim. */
  price: number;
  /** The listing's own currency, for the confirmation toast.
   *
   *  NOTE the known cross-currency gap this sits next to: `target_price` is
   *  written in the member's display currency but COMPARED as EUR by both
   *  `_check_watchlist_snipes` and `GET /p2p/watchlist-matches`. That bug
   *  belongs to the alert and must be fixed on both sides at once — see
   *  docs/alerts-and-insights.md. Formatting the toast honestly is the most
   *  this control can do about it. */
  currency?: string | null;
  title: string;
};

export function FavoriteWatchButtons({
  listingId,
  canonicalKey,
  category,
  price,
  currency,
  title,
}: Props) {
  const { colors } = useAppTheme();
  const { t } = useTranslation();
  const { showToast } = useToast();
  const { settings } = useSettings();
  const { isFavorite, toggle } = useFavorites();
  const [watching, setWatching] = useState(false);
  const [watchPending, setWatchPending] = useState(false);

  const favorited = isFavorite({ listing_id: listingId });

  const onHeart = async () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    try {
      const nowFavorite = await toggle({ listing_id: listingId }, category);
      showToast({ message: nowFavorite ? t('favorites.saved') : t('favorites.removed') });
    } catch {
      // useFavorites already rolled the optimistic flip back and logged it.
      // Say so — a heart that silently snaps back reads as a broken button.
      showToast({ message: t('favorites.save_failed'), type: 'error' });
    }
  };

  const onEye = async () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });

    // A watchlist row with no category can never match: the snipe joins
    // `mh.category = w.category`, so an empty category matches nothing and the
    // row is inert. Refuse rather than write one — five prod rows were written
    // exactly this way by watchlist-builder's hardcoded `category: ''`.
    if (!category) {
      showToast({ message: t('favorites.watch_needs_category'), type: 'error' });
      return;
    }

    setWatchPending(true);
    try {
      await dataProvider.addWatchlistItem({
        title,
        category,
        // THE POINT OF THIS CONTROL. Without it the row never fires.
        targetPrice: price,
        // Bare canonical key. Nullable: a listing with no catalogue match still
        // gets a row, it just falls to the fuzzy title arm instead of the exact
        // one — which is why `title` above must be real, never '(unnamed)'.
        itemId: canonicalKey ?? undefined,
      });
      setWatching(true);
      showToast({
        message: t('favorites.watching', {
          price: formatPrice(price, (currency as CurrencyCode) || 'EUR', settings.numberLocale),
        }),
      });
    } catch (err) {
      logger.error('[favorites] watch failed:', err);
      showToast({ message: t('favorites.watch_failed'), type: 'error' });
    } finally {
      setWatchPending(false);
    }
  };

  return (
    <View style={styles.row}>
      <AnimatedPressable
        onPress={onHeart}
        style={styles.btn}
        hitSlop={8}
        accessibilityRole="button"
        // Says "save", never "alert" — this control does not alert, and the
        // removed version's label claiming otherwise is the documented defect.
        accessibilityLabel={favorited ? t('favorites.a11y_unsave') : t('favorites.a11y_save')}
        accessibilityState={{ selected: favorited }}
      >
        <Ionicons
          name={favorited ? 'heart' : 'heart-outline'}
          size={20}
          color={favorited ? colors.accent : colors.muted}
        />
      </AnimatedPressable>

      <AnimatedPressable
        onPress={onEye}
        disabled={watchPending}
        style={styles.btn}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel={
          watching ? t('favorites.a11y_watching') : t('favorites.a11y_watch')
        }
        accessibilityState={{ selected: watching, disabled: watchPending }}
      >
        {watchPending ? (
          <ActivityIndicator size="small" color={colors.muted} />
        ) : (
          <Ionicons
            name={watching ? 'eye' : 'eye-outline'}
            size={20}
            color={watching ? colors.accent : colors.muted}
          />
        )}
      </AnimatedPressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    // The two sit together as one cluster, per the Vinted-style card.
    gap: 4,
  },
  btn: {
    // 32pt of touch target around a 20pt glyph, plus hitSlop. Icon-only
    // controls on a dense card are the ones that end up untappable.
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
