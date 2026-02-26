/**
 * Watchlist Tab Screen — track prices and drops for items you want.
 * No custom header (Stack header is unified).
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TextInput,
  Modal,
  Alert,
  ActivityIndicator,
  Animated,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type WatchlistItem } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useAuthContext } from '@/providers/useAuthContext';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { formatPrice } from '@/lib/format';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { collectorsApi } from '@/api/collectorsApi';
import MarketplacePickerSheet from '@/components/MarketplacePickerSheet';
import { getMarketplacesForCategory } from '@/data/categories';
import logger from '@/utils/logger';

// Pull from single source of truth — all 36 categories + "Other"
import { CATEGORIES as ALL_CATS } from '@/constants/categories';
const CATEGORIES = [...ALL_CATS.map((c) => c.name), 'Other'];

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default function WatchlistTabScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { user } = useAuthContext();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form state
  const [formTitle, setFormTitle] = useState('');
  const [formCategory, setFormCategory] = useState('');
  const [formTargetPrice, setFormTargetPrice] = useState('');
  const [formNotes, setFormNotes] = useState('');
  const [categoryPickerVisible, setCategoryPickerVisible] = useState(false);

  // Edit target price state
  const [editTargetModalVisible, setEditTargetModalVisible] = useState(false);
  const [editTargetItem, setEditTargetItem] = useState<WatchlistItem | null>(null);
  const [editTargetValue, setEditTargetValue] = useState('');
  const [editTargetSaving, setEditTargetSaving] = useState(false);

  // "I Got It!" acquisition state
  const [acquireModalVisible, setAcquireModalVisible] = useState(false);
  const [acquireItem, setAcquireItem] = useState<WatchlistItem | null>(null);
  const [acquirePrice, setAcquirePrice] = useState('');
  const [acquireNotes, setAcquireNotes] = useState('');
  const [acquiring, setAcquiring] = useState(false);
  const [showCongrats, setShowCongrats] = useState(false);
  const congratsScale = useRef(new Animated.Value(0)).current;
  const congratsOpacity = useRef(new Animated.Value(0)).current;

  // Shop sheet state
  const [shopItem, setShopItem] = useState<WatchlistItem | null>(null);
  const [shopSheetVisible, setShopSheetVisible] = useState(false);

  const loadItems = useCallback(async () => {
    try {
      const data = await dataProvider.listWatchlist(user?.id ?? 'current-user');
      setItems(data);
    } catch (err) {
      logger.warn('[Watchlist] loadItems error:', err);
      showToast({ message: 'Failed to load watchlist. Pull down to retry.', type: 'error' });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?.id]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    loadItems();
  }, [loadItems]);

  const resetForm = () => {
    setFormTitle('');
    setFormCategory('');
    setFormTargetPrice('');
    setFormNotes('');
  };

  const handleAdd = async () => {
    if (!formTitle.trim()) {
      showToast({ message: 'Please enter a title.', type: 'warning' });
      return;
    }
    if (!formCategory) {
      showToast({ message: 'Please select a category.', type: 'warning' });
      return;
    }

    setSaving(true);
    try {
      const targetPrice = formTargetPrice.trim()
        ? parseFloat(formTargetPrice.replace(/[^0-9.]/g, ''))
        : null;

      await dataProvider.addWatchlistItem({
        title: formTitle.trim(),
        category: formCategory,
        targetPrice: targetPrice && !isNaN(targetPrice) ? targetPrice : null,
        notes: formNotes.trim() || undefined,
      });

      // Auto-create price alert when a target price is set
      if (targetPrice && !isNaN(targetPrice) && targetPrice > 0) {
        try {
          await collectorsApi.createAlert({
            category: formCategory,
            trigger_type: 'below_threshold',
            threshold_value: targetPrice,
            direction: 'below',
            metadata: { watchlist_title: formTitle.trim() },
          });
          showToast({
            message: `Price alert created \u2014 we'll notify you when the price drops below ${formatPrice(targetPrice, settings.currency)}`,
            type: 'success',
          });
        } catch (alertErr: unknown) {
          logger.warn('[Watchlist] auto-alert creation failed:', alertErr);
          // Don't fail the add if alert creation fails
        }
      }

      setModalVisible(false);
      resetForm();
      loadItems();
    } catch (err: unknown) {
      showToast({ message: err?.message || 'Failed to add item.', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = (item: WatchlistItem) => {
    Alert.alert(
      'Remove from Watchlist',
      `Remove "${item.title}" from your watchlist?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            try {
              await dataProvider.removeWatchlistItem(item.id);
              loadItems();
            } catch (err: unknown) {
              showToast({ message: err?.message || 'Failed to remove item.', type: 'error' });
            }
          },
        },
      ]
    );
  };

  // Edit target price flow
  const handleEditTarget = (item: WatchlistItem) => {
    setEditTargetItem(item);
    setEditTargetValue(item.targetPrice?.toString() || '');
    setEditTargetModalVisible(true);
  };

  const handleSaveTargetPrice = async () => {
    if (!editTargetItem) return;
    setEditTargetSaving(true);
    try {
      const newTarget = editTargetValue.trim()
        ? parseFloat(editTargetValue.replace(/[^0-9.]/g, ''))
        : null;

      await dataProvider.updateWatchlistItem(editTargetItem.id, {
        targetPrice: newTarget && !isNaN(newTarget) ? newTarget : null,
      });

      // Auto-create price alert when target price is set
      if (newTarget && !isNaN(newTarget) && newTarget > 0) {
        try {
          await collectorsApi.createAlert({
            category: editTargetItem.category || undefined,
            trigger_type: 'below_threshold',
            threshold_value: newTarget,
            direction: 'below',
            metadata: { watchlist_title: editTargetItem.title, watchlist_id: editTargetItem.id },
          });
          fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
          showToast({
            message: `Price alert created \u2014 we'll notify you when the price drops below ${formatPrice(newTarget, settings.currency)}`,
            type: 'success',
          });
        } catch (alertErr: unknown) {
          logger.warn('[Watchlist] auto-alert creation failed:', alertErr);
          showToast({ message: 'Target price saved', type: 'success' });
        }
      } else {
        showToast({ message: 'Target price updated', type: 'success' });
      }

      setEditTargetModalVisible(false);
      setEditTargetItem(null);
      setEditTargetValue('');
      loadItems();
    } catch (err: unknown) {
      showToast({ message: err?.message || 'Failed to update target price.', type: 'error' });
    } finally {
      setEditTargetSaving(false);
    }
  };

  // Shop flow
  const handleShop = async (item: WatchlistItem) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const marketplaces = getMarketplacesForCategory(item.category);

    if (marketplaces.length === 1) {
      // Single marketplace — go directly via affiliate link
      try {
        const res = await collectorsApi.getAffiliateLinks(item.title, item.category);
        const url = res.links?.[0]?.affiliate_url || `https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(item.title)}`;
        Linking.openURL(url).catch(() => {});
      } catch {
        Linking.openURL(`https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(item.title)}`).catch(() => {});
      }
    } else {
      // Multiple marketplaces — show picker sheet
      setShopItem(item);
      setShopSheetVisible(true);
    }
  };

  // "I Got It!" flow
  const handleGotIt = (item: WatchlistItem) => {
    setAcquireItem(item);
    setAcquirePrice(item.targetPrice?.toString() || '');
    setAcquireNotes('');
    setAcquireModalVisible(true);
  };

  const playCongrats = () => {
    setShowCongrats(true);
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });

    // Animate in
    Animated.parallel([
      Animated.spring(congratsScale, {
        toValue: 1,
        tension: 50,
        friction: 7,
        useNativeDriver: true,
      }),
      Animated.timing(congratsOpacity, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start();

    // Animate out after delay
    setTimeout(() => {
      Animated.parallel([
        Animated.timing(congratsScale, {
          toValue: 0,
          duration: 300,
          useNativeDriver: true,
        }),
        Animated.timing(congratsOpacity, {
          toValue: 0,
          duration: 300,
          useNativeDriver: true,
        }),
      ]).start(() => {
        setShowCongrats(false);
        congratsScale.setValue(0);
        congratsOpacity.setValue(0);
      });
    }, 2000);
  };

  const handleConfirmAcquire = async () => {
    if (!acquireItem) return;

    setAcquiring(true);
    try {
      const actualPrice = acquirePrice.trim()
        ? parseFloat(acquirePrice.replace(/[^0-9.]/g, ''))
        : undefined;

      await dataProvider.convertWatchlistToItem(
        acquireItem.id,
        actualPrice && !isNaN(actualPrice) ? actualPrice : undefined,
        acquireNotes.trim() || undefined
      );

      setAcquireModalVisible(false);
      setAcquireItem(null);
      setAcquirePrice('');
      setAcquireNotes('');

      // Show congrats animation
      playCongrats();

      // Reload list
      loadItems();
    } catch (err: unknown) {
      showToast({ message: err?.message || 'Failed to add to collection.', type: 'error' });
    } finally {
      setAcquiring(false);
    }
  };

  const renderItem = ({ item }: { item: WatchlistItem }) => {
    const priorityColor =
      item.priority === 'high'
        ? '#ef4444'
        : item.priority === 'medium'
        ? '#f59e0b'
        : '#22c55e';

    return (
      <View style={[styles.itemCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.itemHeader}>
          <View style={styles.itemTitleRow}>
            <View style={[styles.priorityDot, { backgroundColor: priorityColor }]} />
            <Text style={[styles.itemTitle, { color: colors.text }]} numberOfLines={1}>
              {item.title}
            </Text>
          </View>
          <AnimatedPressable onPress={() => handleRemove(item)} style={styles.removeBtn} accessibilityRole="button" accessibilityLabel={`Remove ${item.title} from watchlist`}>
            <Ionicons name="close-circle" size={22} color={colors.muted} />
          </AnimatedPressable>
        </View>

        <View style={styles.itemMeta}>
          {item.category && (
            <View style={[styles.categoryBadge, { backgroundColor: colors.accent + '20' }]}>
              <Text style={[styles.categoryText, { color: colors.accent }]}>{item.category}</Text>
            </View>
          )}
          <AnimatedPressable
            onPress={() => handleEditTarget(item)}
            style={styles.targetPressable}
            accessibilityRole="button"
            accessibilityLabel={item.targetPrice !== null ? `Target: ${formatPrice(item.targetPrice, settings.currency)}. Tap to edit` : 'Set target price'}
          >
            {item.targetPrice !== null ? (
              <Text style={[styles.targetPrice, { color: colors.text }]}>
                Target: {formatPrice(item.targetPrice, settings.currency)}
              </Text>
            ) : (
              <Text style={[styles.setTargetText, { color: colors.accent }]}>
                Set target price
              </Text>
            )}
            <Ionicons name="pencil-outline" size={12} color={colors.muted} />
          </AnimatedPressable>
        </View>

        {item.notes && (
          <Text style={[styles.notes, { color: colors.muted }]} numberOfLines={2}>
            {item.notes}
          </Text>
        )}

        {item.createdAt && (
          <Text style={[styles.dateAdded, { color: colors.muted }]}>
            Added {formatDate(item.createdAt)}
          </Text>
        )}

        {/* Action buttons */}
        <View style={styles.cardActions}>
          <AnimatedPressable
            style={[styles.shopBtn, { borderColor: colors.accent }]}
            onPress={() => handleShop(item)}
            accessibilityRole="button"
            accessibilityLabel={`Shop for ${item.title}`}
          >
            <Ionicons name="cart-outline" size={16} color={colors.accent} />
            <Text style={[styles.shopBtnText, { color: colors.accent }]}>Shop</Text>
          </AnimatedPressable>
          <AnimatedPressable
            style={[styles.gotItBtn, { backgroundColor: colors.accent }]}
            onPress={() => handleGotIt(item)}
            accessibilityRole="button"
            accessibilityLabel={`Mark ${item.title} as acquired`}
          >
            <Ionicons name="checkmark-circle" size={18} color="#fff" />
            <Text style={styles.gotItBtnText}>I Got It!</Text>
          </AnimatedPressable>
        </View>
      </View>
    );
  };

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <View style={[styles.emptyIconWrap, { backgroundColor: colors.accent + '15' }]}>
        <Ionicons name="eye-outline" size={40} color={colors.accent} />
      </View>
      <Text style={[styles.emptyTitle, { color: colors.text }]}>Start your watchlist</Text>
      <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
        Track prices, get alerts when items drop, and never miss a deal on items you want.
      </Text>
      <AnimatedPressable
        style={[styles.emptyBtn, { backgroundColor: colors.accent }]}
        onPress={() => setModalVisible(true)}
        accessibilityRole="button"
        accessibilityLabel="Add your first watchlist item"
      >
        <Ionicons name="add" size={18} color="#fff" />
        <Text style={styles.emptyBtnText}>Add your first item</Text>
      </AnimatedPressable>
      <View style={styles.emptyFeatures}>
        <View style={styles.emptyFeatureRow}>
          <Ionicons name="notifications-outline" size={16} color={colors.muted} />
          <Text style={[styles.emptyFeatureText, { color: colors.muted }]}>Price drop alerts</Text>
        </View>
        <View style={styles.emptyFeatureRow}>
          <Ionicons name="trending-down-outline" size={16} color={colors.muted} />
          <Text style={[styles.emptyFeatureText, { color: colors.muted }]}>Target price tracking</Text>
        </View>
        <View style={styles.emptyFeatureRow}>
          <Ionicons name="flash-outline" size={16} color={colors.muted} />
          <Text style={[styles.emptyFeatureText, { color: colors.muted }]}>Restock notifications</Text>
        </View>
      </View>
    </View>
  );

  const renderHeader = () => (
    <View style={styles.actionRow}>
      <AnimatedPressable
        style={[styles.alertsPill, { backgroundColor: colors.card, borderColor: colors.border }]}
        onPress={() => router.push('/alerts')}
        accessibilityRole="button"
        accessibilityLabel="View price alerts"
      >
        <Ionicons name="notifications-outline" size={16} color={colors.accent} />
        <Text style={[styles.alertsPillText, { color: colors.accent }]}>Alerts</Text>
      </AnimatedPressable>

      <AnimatedPressable
        style={[styles.addPill, { backgroundColor: colors.accent }]}
        onPress={() => setModalVisible(true)}
        accessibilityRole="button"
        accessibilityLabel="Add item to watchlist"
      >
        <Ionicons name="add" size={18} color="#fff" />
        <Text style={styles.addPillText}>Add</Text>
      </AnimatedPressable>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      <Animated.View style={[{ flex: 1 }, animatedStyle]}>
        <FlatList
          data={items}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          ListHeaderComponent={renderHeader}
          contentContainerStyle={[
            styles.listContent,
            items.length === 0 && styles.listContentEmpty,
          ]}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor="#81D8D0" />}
          ListEmptyComponent={renderEmpty}
        />
      </Animated.View>

      {/* Add Modal */}
      <Modal visible={modalVisible} animationType="slide" transparent onRequestClose={() => { setModalVisible(false); resetForm(); }}>
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Add to Watchlist</Text>
              <AnimatedPressable onPress={() => { setModalVisible(false); resetForm(); }} accessibilityRole="button" accessibilityLabel="Close add to watchlist form">
                <Ionicons name="close" size={24} color={colors.muted} />
              </AnimatedPressable>
            </View>

            {/* Title */}
            <Text style={[styles.label, { color: colors.text }]}>Title *</Text>
            <TextInput
              value={formTitle}
              onChangeText={setFormTitle}
              placeholder="e.g. Charizard VMAX Rainbow"
              placeholderTextColor={colors.muted}
              style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
              accessibilityLabel="Item title"
            />

            {/* Category */}
            <Text style={[styles.label, { color: colors.text }]}>Category *</Text>
            <AnimatedPressable
              style={[styles.input, styles.pickerBtn, { backgroundColor: colors.background, borderColor: colors.border }]}
              onPress={() => setCategoryPickerVisible(true)}
              accessibilityRole="button"
              accessibilityLabel={formCategory ? `Category: ${formCategory}. Tap to change` : "Select category"}
            >
              <Text style={{ color: formCategory ? colors.text : colors.muted }}>
                {formCategory || 'Select category'}
              </Text>
              <Ionicons name="chevron-down" size={18} color={colors.muted} />
            </AnimatedPressable>

            {/* Target Price */}
            <Text style={[styles.label, { color: colors.text }]}>Target Price ({settings.currency})</Text>
            <TextInput
              value={formTargetPrice}
              onChangeText={setFormTargetPrice}
              placeholder="e.g. 350"
              placeholderTextColor={colors.muted}
              keyboardType="numeric"
              style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
              accessibilityLabel="Target price in euros"
            />

            {/* Notes */}
            <Text style={[styles.label, { color: colors.text }]}>Notes</Text>
            <TextInput
              value={formNotes}
              onChangeText={setFormNotes}
              placeholder="e.g. Looking for PSA 9 or higher"
              placeholderTextColor={colors.muted}
              multiline
              numberOfLines={3}
              style={[styles.input, styles.textArea, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
              accessibilityLabel="Notes"
            />

            {/* Save Button */}
            <AnimatedPressable
              style={[styles.saveBtn, { backgroundColor: colors.accent }]}
              onPress={handleAdd}
              disabled={saving}
              accessibilityRole="button"
              accessibilityLabel="Add to watchlist"
            >
              {saving ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <Text style={styles.saveBtnText}>Add to Watchlist</Text>
              )}
            </AnimatedPressable>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Category Picker Modal */}
      <Modal visible={categoryPickerVisible} animationType="slide" transparent onRequestClose={() => setCategoryPickerVisible(false)}>
        <AnimatedPressable
          style={styles.pickerOverlay}
          onPress={() => setCategoryPickerVisible(false)}
        >
          <View style={[styles.pickerContent, { backgroundColor: colors.card }]}>
            <Text style={[styles.pickerTitle, { color: colors.text }]}>Select Category</Text>
            {CATEGORIES.map((cat) => (
              <AnimatedPressable
                key={cat}
                style={[
                  styles.pickerItem,
                  formCategory === cat && { backgroundColor: colors.accent + '20' },
                ]}
                onPress={() => {
                  setFormCategory(cat);
                  setCategoryPickerVisible(false);
                }}
                accessibilityRole="button"
                accessibilityLabel={`${cat}${formCategory === cat ? ', selected' : ''}`}
              >
                <Text style={[styles.pickerItemText, { color: colors.text }]}>{cat}</Text>
                {formCategory === cat && (
                  <Ionicons name="checkmark" size={20} color={colors.accent} />
                )}
              </AnimatedPressable>
            ))}
          </View>
        </AnimatedPressable>
      </Modal>

      {/* "I Got It!" Acquisition Modal */}
      <Modal visible={acquireModalVisible} animationType="slide" transparent onRequestClose={() => { setAcquireModalVisible(false); setAcquireItem(null); }}>
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Add to Collection</Text>
              <AnimatedPressable onPress={() => { setAcquireModalVisible(false); setAcquireItem(null); }} accessibilityRole="button" accessibilityLabel="Close acquisition form">
                <Ionicons name="close" size={24} color={colors.muted} />
              </AnimatedPressable>
            </View>

            {acquireItem && (
              <>
                <View style={[styles.acquireItemPreview, { backgroundColor: colors.background }]}>
                  <Text style={[styles.acquireItemTitle, { color: colors.text }]} numberOfLines={2}>
                    {acquireItem.title}
                  </Text>
                  {acquireItem.category && (
                    <View style={[styles.categoryBadge, { backgroundColor: colors.accent + '20' }]}>
                      <Text style={[styles.categoryText, { color: colors.accent }]}>{acquireItem.category}</Text>
                    </View>
                  )}
                </View>

                <Text style={[styles.label, { color: colors.text }]}>What did you pay? ({settings.currency})</Text>
                <TextInput
                  value={acquirePrice}
                  onChangeText={setAcquirePrice}
                  placeholder={acquireItem.targetPrice ? `Target was €${acquireItem.targetPrice}` : 'e.g. 150'}
                  placeholderTextColor={colors.muted}
                  keyboardType="numeric"
                  style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
                  accessibilityLabel="Price paid in euros"
                />
                <Text style={[styles.helperText, { color: colors.muted }]}>
                  This helps improve price predictions for everyone
                </Text>

                <Text style={[styles.label, { color: colors.text }]}>Notes (optional)</Text>
                <TextInput
                  value={acquireNotes}
                  onChangeText={setAcquireNotes}
                  placeholder="e.g. Found at local shop, great condition"
                  placeholderTextColor={colors.muted}
                  multiline
                  numberOfLines={2}
                  style={[styles.input, styles.textArea, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
                  accessibilityLabel="Acquisition notes"
                />

                <AnimatedPressable
                  style={[styles.acquireBtn, { backgroundColor: colors.accent }]}
                  onPress={handleConfirmAcquire}
                  disabled={acquiring}
                  accessibilityRole="button"
                  accessibilityLabel="Add to my collection"
                >
                  {acquiring ? (
                    <ActivityIndicator size="small" color="#fff" />
                  ) : (
                    <>
                      <Ionicons name="checkmark-circle" size={20} color="#fff" />
                      <Text style={styles.acquireBtnText}>Add to My Collection</Text>
                    </>
                  )}
                </AnimatedPressable>
              </>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Edit Target Price Modal */}
      <Modal visible={editTargetModalVisible} animationType="slide" transparent onRequestClose={() => { setEditTargetModalVisible(false); setEditTargetItem(null); }}>
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Set Target Price</Text>
              <AnimatedPressable onPress={() => { setEditTargetModalVisible(false); setEditTargetItem(null); }} accessibilityRole="button" accessibilityLabel="Close target price editor">
                <Ionicons name="close" size={24} color={colors.muted} />
              </AnimatedPressable>
            </View>

            {editTargetItem && (
              <>
                <View style={[styles.acquireItemPreview, { backgroundColor: colors.background }]}>
                  <Text style={[styles.acquireItemTitle, { color: colors.text }]} numberOfLines={2}>
                    {editTargetItem.title}
                  </Text>
                  {editTargetItem.category && (
                    <View style={[styles.categoryBadge, { backgroundColor: colors.accent + '20' }]}>
                      <Text style={[styles.categoryText, { color: colors.accent }]}>{editTargetItem.category}</Text>
                    </View>
                  )}
                </View>

                <Text style={[styles.label, { color: colors.text }]}>Target Price ({settings.currency})</Text>
                <TextInput
                  value={editTargetValue}
                  onChangeText={setEditTargetValue}
                  placeholder="e.g. 350"
                  placeholderTextColor={colors.muted}
                  keyboardType="numeric"
                  autoFocus
                  style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
                  accessibilityLabel="Target price"
                />
                <Text style={[styles.helperText, { color: colors.muted }]}>
                  A price alert will be created automatically when you set a target price.
                </Text>

                <AnimatedPressable
                  style={[styles.saveBtn, { backgroundColor: colors.accent }]}
                  onPress={handleSaveTargetPrice}
                  disabled={editTargetSaving}
                  accessibilityRole="button"
                  accessibilityLabel="Save target price"
                >
                  {editTargetSaving ? (
                    <ActivityIndicator size="small" color="#fff" />
                  ) : (
                    <Text style={styles.saveBtnText}>Save Target Price</Text>
                  )}
                </AnimatedPressable>
              </>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Marketplace Picker Sheet */}
      <MarketplacePickerSheet
        visible={shopSheetVisible}
        onClose={() => { setShopSheetVisible(false); setShopItem(null); }}
        itemTitle={shopItem?.title ?? ''}
        categoryId={shopItem?.category ?? undefined}
      />

      {/* Congrats Overlay */}
      {showCongrats && (
        <View style={styles.congratsOverlay}>
          <Animated.View
            style={[
              styles.congratsContent,
              {
                backgroundColor: colors.card,
                transform: [{ scale: congratsScale }],
                opacity: congratsOpacity,
              },
            ]}
          >
            <View style={[styles.congratsIconWrap, { backgroundColor: '#22c55e20' }]}>
              <Ionicons name="trophy" size={48} color="#22c55e" />
            </View>
            <Text style={[styles.congratsTitle, { color: colors.text }]}>Congrats!</Text>
            <Text style={[styles.congratsSubtitle, { color: colors.muted }]}>
              Added to your collection
            </Text>
          </Animated.View>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  actionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  alertsPill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
    gap: 6,
  },
  alertsPillText: {
    fontSize: 13,
    fontWeight: '600',
  },
  addPill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    gap: 6,
  },
  addPillText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  listContent: {
    padding: 16,
    gap: 12,
  },
  listContentEmpty: {
    flex: 1,
  },
  itemCard: {
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
  },
  itemHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  itemTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    marginRight: 8,
  },
  priorityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  itemTitle: {
    fontSize: 15,
    fontWeight: '600',
    flex: 1,
  },
  removeBtn: {
    padding: 4,
  },
  itemMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 10,
  },
  categoryBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
  },
  categoryText: {
    fontSize: 12,
    fontWeight: '500',
  },
  targetPrice: {
    fontSize: 13,
    fontWeight: '600',
  },
  targetPressable: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  setTargetText: {
    fontSize: 12,
    fontWeight: '500',
  },
  notes: {
    fontSize: 13,
    marginTop: 8,
    lineHeight: 18,
  },
  dateAdded: {
    fontSize: 11,
    marginTop: 6,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
    paddingTop: 60,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20,
  },
  emptyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 24,
    marginTop: 24,
    gap: 6,
  },
  emptyBtnText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
  },
  emptyIconWrap: {
    width: 80,
    height: 80,
    borderRadius: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyFeatures: {
    marginTop: 32,
    gap: 12,
  },
  emptyFeatureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  emptyFeatureText: {
    fontSize: 14,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 6,
    marginTop: 12,
  },
  input: {
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    borderWidth: 1,
  },
  textArea: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  pickerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  saveBtn: {
    marginTop: 24,
    paddingVertical: 14,
    borderRadius: 24,
    alignItems: 'center',
  },
  saveBtnText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  pickerOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  pickerContent: {
    width: '100%',
    borderRadius: 16,
    padding: 16,
  },
  pickerTitle: {
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 12,
    textAlign: 'center',
  },
  pickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 8,
  },
  pickerItemText: {
    fontSize: 15,
  },
  // Action button row
  cardActions: {
    flexDirection: 'row',
    marginTop: 12,
    gap: 8,
  },
  shopBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 20,
    borderWidth: 1,
    gap: 6,
  },
  shopBtnText: {
    fontSize: 14,
    fontWeight: '600',
  },
  gotItBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 20,
    gap: 6,
  },
  gotItBtnText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  // Acquire modal styles
  acquireItemPreview: {
    padding: 14,
    borderRadius: 12,
    marginBottom: 16,
  },
  acquireItemTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  acquireBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
    paddingVertical: 14,
    borderRadius: 24,
    gap: 8,
  },
  acquireBtnText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  helperText: {
    fontSize: 12,
    marginTop: 4,
    marginBottom: 8,
  },
  // Congrats overlay styles
  congratsOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1000,
  },
  congratsContent: {
    alignItems: 'center',
    padding: 32,
    borderRadius: 24,
    minWidth: 240,
  },
  congratsIconWrap: {
    width: 88,
    height: 88,
    borderRadius: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  congratsTitle: {
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 4,
  },
  congratsSubtitle: {
    fontSize: 14,
  },
});
