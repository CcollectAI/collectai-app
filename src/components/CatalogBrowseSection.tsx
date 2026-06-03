/**
 * CatalogBrowseSection — full category_items database browser.
 *
 * Collapsible section with search, pagination, "Add to Collection"
 * and "Add to Watchlist" buttons per catalog item.
 *
 * Extracted from app/categories/[categoryId].tsx to reduce file size.
 */
import React from 'react';
import {
  View,
  Text,
  TextInput,
  ActivityIndicator,
  Image,
  StyleSheet,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { formatPrice } from '@/lib/format';
import { useAppTheme } from '@/hooks/useAppTheme';

// ── Types ──────────────────────────────────────────────────────────────

export type CatalogItemData = {
  id: string;
  category: string;
  item_key: string;
  title: string;
  brand: string | null;
  rarity: string | null;
  notes: string | null;
  has_reference_image?: boolean;
  // Canonical card-CDN thumbnail; null when the catalog row has none.
  image_url?: string | null;
  external_id: string | null;
  set_code: string | null;
  estimated_price: number | null;
};

export interface CatalogBrowseSectionProps {
  /** Whether the section is currently expanded */
  catalogExpanded: boolean;
  /** Toggle expanded/collapsed */
  onToggleExpanded: () => void;
  /** Total number of catalog items */
  catalogTotal: number;
  /** Current search query */
  catalogSearch: string;
  /** Handle search text change (debounced in parent) */
  onSearchChange: (text: string) => void;
  /** Clear search and reload */
  onClearSearch: () => void;
  /** Whether the initial catalog load is in progress */
  catalogLoading: boolean;
  /** Whether more items are being loaded */
  catalogLoadingMore: boolean;
  /** The currently loaded catalog items */
  catalogItems: CatalogItemData[];
  /** Load more items (pagination) */
  onLoadMore: () => void;
  /** Called when user taps "Add to Collection" on a catalog item */
  onAddToCollection: (item: CatalogItemData) => void;
  /** Called when user taps "Add to Watchlist" on a catalog item */
  onAddToWatchlist: (item: CatalogItemData) => void;
  /** Called when user taps the card body — opens the catalog "museum" detail */
  onItemPress?: (item: CatalogItemData) => void;
  /** Accent color for the category */
  accentColor: string;
  /** Theme colors */
  colors: {
    text: string;
    muted: string;
    card: string;
    border: string;
  };
}

// ── Component ──────────────────────────────────────────────────────────

function CatalogBrowseSectionInner({
  catalogExpanded,
  onToggleExpanded,
  catalogTotal,
  catalogSearch,
  onSearchChange,
  onClearSearch,
  catalogLoading,
  catalogLoadingMore,
  catalogItems,
  onLoadMore,
  onAddToCollection,
  onAddToWatchlist,
  onItemPress,
  accentColor,
  colors,
}: CatalogBrowseSectionProps) {
  const { colors: themeColors } = useAppTheme();
  return (
    <View style={s.section}>
      <AnimatedPressable
        style={s.catalogHeaderRow}
        onPress={onToggleExpanded}
        accessibilityRole="button"
        accessibilityLabel={`Browse catalog, ${catalogExpanded ? 'collapse' : 'expand'}`}
      >
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Ionicons name="library-outline" size={18} color={accentColor} />
          <Text style={[s.sectionTitle, { color: colors.text, marginBottom: 0 }]}>Browse Catalog</Text>
          {catalogTotal > 0 && (
            <View style={[s.catalogCountBadge, { backgroundColor: accentColor + '20' }]}>
              <Text style={[s.catalogCountText, { color: accentColor }]}>{catalogTotal}</Text>
            </View>
          )}
        </View>
        <Ionicons
          name={catalogExpanded ? 'chevron-up' : 'chevron-down'}
          size={18}
          color={colors.muted}
        />
      </AnimatedPressable>

      {!!catalogExpanded && (
        <View style={s.catalogBrowser}>
          {/* Search bar */}
          <View style={[s.catalogSearchBar, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Ionicons name="search" size={16} color={colors.muted} />
            <TextInput
              style={[s.catalogSearchInput, { color: colors.text }]}
              placeholder="Search catalog items..."
              placeholderTextColor={colors.muted}
              value={catalogSearch}
              onChangeText={onSearchChange}
              returnKeyType="search"
              accessibilityLabel="Search catalog items"
            />
            {catalogSearch.length > 0 && (
              <AnimatedPressable
                onPress={onClearSearch}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityLabel="Clear search"
              >
                <Ionicons name="close-circle" size={16} color={colors.muted} />
              </AnimatedPressable>
            )}
          </View>

          {/* Catalog items list */}
          {catalogLoading ? (
            <ActivityIndicator size="small" color={accentColor} style={{ marginVertical: 16 }} />
          ) : catalogItems.length === 0 ? (
            <Text style={[s.emptyText, { color: colors.muted, marginTop: 8 }]}>
              {catalogSearch ? 'No items matching your search.' : 'No catalog items for this category.'}
            </Text>
          ) : (
            <>
              {catalogItems.map((cItem) => (
                <AnimatedPressable
                  key={cItem.id}
                  style={[s.catalogItemCard, { backgroundColor: colors.card, borderColor: colors.border }]}
                  onPress={() => onItemPress?.(cItem)}
                  accessibilityRole="button"
                  accessibilityLabel={`View ${cItem.title}`}
                >
                  {/* Reference thumbnail (canonical card CDN); placeholder when absent */}
                  {cItem.image_url ? (
                    <Image
                      source={{ uri: cItem.image_url }}
                      style={s.catalogItemThumb}
                      resizeMode="contain"
                      accessibilityIgnoresInvertColors
                    />
                  ) : (
                    <View style={[s.catalogItemThumb, s.catalogItemThumbPlaceholder, { backgroundColor: accentColor + '12' }]}>
                      <Ionicons name="image-outline" size={18} color={accentColor} />
                    </View>
                  )}

                  {/* Item info */}
                  <View style={s.catalogItemInfo}>
                    <Text style={[s.catalogItemTitle, { color: colors.text }]} numberOfLines={1}>
                      {cItem.title}
                    </Text>
                    <View style={s.catalogItemMetaRow}>
                      {cItem.estimated_price != null && (
                        <Text style={[s.catalogItemPrice, { color: colors.text }]}>
                          {formatPrice(cItem.estimated_price)}
                        </Text>
                      )}
                      {!!cItem.rarity && (
                        <View style={[s.catalogRarityBadge, {
                          backgroundColor:
                            cItem.rarity === 'grail' ? '#F59E0B20' :
                            cItem.rarity === 'high' ? themeColors.danger + '20' :
                            cItem.rarity === 'mid' ? '#3B82F620' :
                            colors.border,
                        }]}>
                          <Text style={[s.catalogRarityText, {
                            color:
                              cItem.rarity === 'grail' ? '#D97706' :
                              cItem.rarity === 'high' ? '#DC2626' :
                              cItem.rarity === 'mid' ? '#2563EB' :
                              colors.muted,
                          }]}>
                            {cItem.rarity}
                          </Text>
                        </View>
                      )}
                      {!!cItem.brand && (
                        <Text style={[s.catalogItemBrand, { color: colors.muted }]} numberOfLines={1}>
                          {cItem.brand}
                        </Text>
                      )}
                    </View>
                  </View>

                  {/* Action: single "add to want list" button. The category
                      page is a catalog of what EXISTS, so the action here is
                      "I want this" (watchlist), not "I own this" (collection).
                      Previously there were duplicate plus + heart buttons. */}
                  <View style={s.catalogItemActions}>
                    <AnimatedPressable
                      style={[s.catalogActionBtn, { backgroundColor: accentColor }]}
                      onPress={() => onAddToWatchlist(cItem)}
                      accessibilityRole="button"
                      accessibilityLabel={`Add ${cItem.title} to want list`}
                    >
                      <Ionicons name="heart-outline" size={16} color="#fff" />
                    </AnimatedPressable>
                  </View>
                </AnimatedPressable>
              ))}

              {/* Load more / infinite scroll trigger */}
              {catalogItems.length < catalogTotal && (
                <AnimatedPressable
                  style={[s.catalogLoadMoreBtn, { borderColor: accentColor }]}
                  onPress={onLoadMore}
                  disabled={catalogLoadingMore}
                  accessibilityRole="button"
                  accessibilityLabel="Load more catalog items"
                >
                  {catalogLoadingMore ? (
                    <ActivityIndicator size="small" color={accentColor} />
                  ) : (
                    <Text style={[s.catalogLoadMoreText, { color: accentColor }]}>
                      Load more ({catalogItems.length} of {catalogTotal})
                    </Text>
                  )}
                </AnimatedPressable>
              )}
            </>
          )}
        </View>
      )}
    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  emptyText: {
    fontSize: 13,
  },
  catalogHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  catalogCountBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  catalogCountText: {
    fontSize: 11,
    fontWeight: '700',
  },
  catalogBrowser: {
    marginTop: 4,
  },
  catalogSearchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 8,
    gap: 8,
    marginBottom: 10,
  },
  catalogSearchInput: {
    flex: 1,
    fontSize: 14,
    padding: 0,
    margin: 0,
  },
  catalogItemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    padding: 10,
    marginBottom: 8,
  },
  catalogItemThumb: {
    width: 44,
    height: 44,
    borderRadius: 8,
    marginRight: 10,
  },
  catalogItemThumbPlaceholder: {
    width: 44,
    height: 44,
    borderRadius: 8,
    marginRight: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  catalogItemInfo: {
    flex: 1,
    marginRight: 8,
  },
  catalogItemTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  catalogItemMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 3,
    flexWrap: 'wrap',
  },
  catalogItemPrice: {
    fontSize: 13,
    fontWeight: '700',
  },
  catalogRarityBadge: {
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 6,
  },
  catalogRarityText: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  catalogItemBrand: {
    fontSize: 11,
  },
  catalogItemActions: {
    flexDirection: 'column',
    gap: 4,
  },
  catalogActionBtn: {
    width: 30,
    height: 30,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  catalogLoadMoreBtn: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginTop: 4,
  },
  catalogLoadMoreText: {
    fontSize: 13,
    fontWeight: '600',
  },
});

export const CatalogBrowseSection = React.memo(CatalogBrowseSectionInner);
