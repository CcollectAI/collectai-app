/**
 * Favourites — everything the member has hearted.
 *
 * This screen is the CONSUMER half of the heart. A save control with no place
 * to see what you saved is capture-without-consume, which is the shape this
 * codebase keeps having to delete.
 *
 * What it deliberately is NOT: a watchlist. Nothing here has a target price and
 * nothing here alerts. The watchlist lives on `(tabs)/wishlist.tsx` and is
 * reached with the eye, not the heart — see the note at the top of
 * src/api/favoritesApi.ts for the bug that conflating the two produced.
 *
 * Two playbook rules it is built around (docs/ui-playbook.md):
 *
 * 1. **The header is OUTSIDE the list** — FlashList v2 absolutely-positions
 *    every cell including ListHeaderComponent, so a tall header renders and
 *    silently stops receiving touches. FlatList here regardless.
 * 2. **No `useTabBarInset`.** This comment used to say QuickNavBar is absolute
 *    and needs one. It is not: QuickNavBar is an in-flow row that reserves its
 *    own height (see its styles, and docs/ui-playbook.md "The newest screens
 *    keep shipping without the nav bar"). `useTabBarInset` is for `(tabs)`
 *    screens under the absolute ExternalTabBar, and here it only added ~90pt of
 *    blank space above the bar. Corrected 2026-09-13.
 *
 * And a failed load is not an empty list. "Nothing saved yet" is a claim about
 * the member's favourites; after a request that never came back it is a false
 * one, so failure gets its own sentence and a retry.
 */
import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { Image } from 'expo-image';
import { useRouter, type Href } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import ScreenHeader from '@/components/ScreenHeader';
import { QuickNavBar } from '@/components/QuickNavBar';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { EmptyState } from '@/components/EmptyState';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import type { CurrencyCode } from '@/data/types';
import { listFavorites, removeFavorite, type Favorite } from '@/api/favoritesApi';
import logger from '@/utils/logger';

/** A listing that is no longer buyable. The row STAYS — the member saved it,
 *  and silently dropping it would be the app deciding what they meant. */
function isUnavailable(f: Favorite): boolean {
  return !!f.listing_id && f.listing_status !== null && f.listing_status !== 'active';
}

function FavoritesScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { t } = useTranslation();

  const [rows, setRows] = useState<Favorite[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  // The last load failed. Rows are KEPT on failure (a refresh that fails must
  // not blank a list that was right a minute ago), so this only changes what
  // an EMPTY list says: could-not-ask, not asked-and-there-are-none.
  const [loadFailed, setLoadFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await listFavorites());
      setLoadFailed(false);
    } catch (err) {
      // logger.error, not warn — info/warn are stripped from release builds.
      logger.error('[favorites] load failed:', err);
      setLoadFailed(true);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Refetch on focus: the heart lives on other screens, so this list is stale
  // the moment the member unsaves something and comes back.
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    load();
  }, [load]);

  // double-tap-ok: the row is removed from `rows` before the await, so the
  // control the member tapped no longer exists; a failure puts it back.
  const onUnsave = useCallback(async (f: Favorite) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const target = f.listing_id
      ? { listing_id: f.listing_id }
      : { canonical_key: f.canonical_key! };
    const prev = rows;
    setRows((r) => r.filter((x) => x.id !== f.id));
    try {
      await removeFavorite(target);
    } catch (err) {
      logger.error('[favorites] unsave failed:', err);
      setRows(prev); // Put it back rather than lie about the delete.
    }
  }, [rows, settings.hapticsEnabled]);

  const onOpen = useCallback((f: Favorite) => {
    if (isUnavailable(f)) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    if (f.listing_id) {
      router.push({ pathname: '/listing/[id]', params: { id: f.listing_id } });
    } else if (f.canonical_key) {
      // Catalogue favourites open the catalogue item, not a listing — WITH the
      // fields the row already carries. catalog-item/[key] takes its title,
      // image and category ONLY from params (a bare key cannot be resolved:
      // keys are bare, the category is what disambiguates them), so the old
      // key-only push opened "Catalog item" with no image, searched the
      // marketplaces for the words "Catalog item", and wrote a watchlist row
      // with that title and an empty category. Same param shape as
      // category-browse.tsx and catalog-set/[setCode].tsx.
      router.push({
        pathname: '/catalog-item/[key]',
        params: {
          key: f.canonical_key,
          category: f.category ?? '',
          title: f.title ?? '',
          image_url: f.image_url ?? '',
        },
      } as unknown as Href);
    }
  }, [router, settings.hapticsEnabled]);

  const renderItem = useCallback(({ item }: { item: Favorite }) => {
    const unavailable = isUnavailable(item);
    return (
      <AnimatedPressable
        onPress={() => onOpen(item)}
        disabled={unavailable}
        style={[
          styles.card,
          { backgroundColor: colors.card, borderColor: colors.border },
          unavailable && { opacity: 0.55 },
        ]}
        accessibilityRole="button"
        accessibilityLabel={item.title ?? ''}
      >
        {item.image_url ? (
          <Image source={{ uri: item.image_url }} style={styles.thumb} contentFit="cover" />
        ) : (
          <View style={[styles.thumb, styles.thumbEmpty, { backgroundColor: colors.accent + '15' }]}>
            <Ionicons name="image-outline" size={18} color={colors.muted} />
          </View>
        )}

        <View style={styles.body}>
          <Text style={[styles.title, { color: colors.text }]} numberOfLines={2}>
            {item.title ?? '—'}
          </Text>
          {unavailable ? (
            <Text style={[styles.meta, { color: colors.muted }]}>
              {t('favorites.unavailable')}
            </Text>
          ) : item.price != null ? (
            <Text style={[styles.price, { color: colors.text }]}>
              {formatPrice(item.price, (item.currency as CurrencyCode) || 'EUR', settings.numberLocale)}
            </Text>
          ) : null}
        </View>

        <AnimatedPressable
          onPress={() => onUnsave(item)}
          hitSlop={8}
          style={styles.heart}
          accessibilityRole="button"
          accessibilityLabel={t('favorites.a11y_unsave')}
        >
          <Ionicons name="heart" size={20} color={colors.accent} />
        </AnimatedPressable>
      </AnimatedPressable>
    );
  }, [colors, onOpen, onUnsave, settings.numberLocale, t]);

  return (
    // Plain View, NOT SafeAreaView: ScreenHeader applies insets.top itself,
    // so wrapping in one too pads the top twice (same note as app/listings.tsx).
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScreenHeader title={t('favorites.title')} />

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.accent} />
        </View>
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(f) => f.id}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
          }
          ListEmptyComponent={
            loadFailed ? (
              <EmptyState
                icon="cloud-offline-outline"
                title={t('favorites.load_failed', { defaultValue: "Couldn't load your favourites" })}
                subtitle={t('favorites.load_failed_hint', { defaultValue: 'Your saved items are safe — we just could not reach them.' })}
                colors={colors}
                action={
                  <AnimatedPressable
                    onPress={onRefresh}
                    style={[styles.retryBtn, { backgroundColor: colors.accent }]}
                    accessibilityRole="button"
                    accessibilityLabel={t('common.try_again', { defaultValue: 'Try again' })}
                  >
                    <Text style={[styles.retryText, { color: colors.accentText }]}>
                      {t('common.try_again', { defaultValue: 'Try again' })}
                    </Text>
                  </AnimatedPressable>
                }
              />
            ) : (
              <EmptyState
                icon="heart-outline"
                title={t('favorites.empty')}
                subtitle={t('favorites.empty_hint')}
                colors={colors}
              />
            )
          }
        />
      )}

      <QuickNavBar />
    </View>
  );
}

export default function FavoritesScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Favorites">
      <FavoritesScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  // paddingBottom is plain spacing: QuickNavBar below the list reserves its
  // own height, so no tab-bar inset belongs here (see the file header).
  listContent: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 16, gap: 10 },
  retryBtn: { paddingHorizontal: 20, paddingVertical: 10, borderRadius: 999, minHeight: 44, justifyContent: 'center' },
  retryText: { fontSize: 14, fontWeight: '700' },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    padding: 10,
    gap: 10,
  },
  thumb: { width: 56, height: 56, borderRadius: 8 },
  thumbEmpty: { alignItems: 'center', justifyContent: 'center' },
  body: { flex: 1 },
  // Body copy floor is `sm`; `xs` (10pt) is banned for anything a user reads.
  title: { fontSize: 14, fontWeight: '600' },
  meta: { fontSize: 12, marginTop: 2 },
  price: { fontSize: 14, fontWeight: '700', marginTop: 2 },
  heart: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center' },
});
