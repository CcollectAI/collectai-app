/**
 * Watchlist Builder — Track items you want with price alerts
 *
 * Features:
 * - Clean, focused UI for adding watchlist items
 * - Priority badges (High/Medium/Low)
 * - Price targets with alert settings
 * - Quick add flow
 * - SafeAreaView for notch support
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TextInput,
  Alert,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Animated,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Stack, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import logger from "@/utils/logger";
import { formatPrice } from "@/lib/format";

import { useSession } from "@/hooks/useSession";
import {
  fetchWatchlistForUser,
  upsertWatchlistItem,
  deleteWatchlistItem,
  type WatchlistItem,
  type WatchlistPriority,
} from "@/services/watchlistAndAlerts";

// ─────────────────────────────────────────────────────────────────────────────
// Design Tokens (Collectr)
// ─────────────────────────────────────────────────────────────────────────────

const COLORS = {
  tiffany: "#81D8D0",
  tiffanyDark: "#5FBFB6",
  tiffanyLight: "#E6F7F5",
  background: "#F7FAF9",
  card: "#FFFFFF",
  navy: "#0F172A",
  muted: "#64748B",
  border: "#E2E8F0",
  success: "#10B981",
  warning: "#F59E0B",
  danger: "#EF4444",
  inputBg: "#F8FAFC",
};

const PRIORITY_CONFIG: Record<WatchlistPriority, { label: string; color: string; bg: string }> = {
  high: { label: "High", color: "#DC2626", bg: "#FEF2F2" },
  medium: { label: "Medium", color: "#D97706", bg: "#FFFBEB" },
  low: { label: "Low", color: "#059669", bg: "#ECFDF5" },
};

// ─────────────────────────────────────────────────────────────────────────────
// Formatting helpers
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export default function WatchlistBuilderScreen() {
  const router = useRouter();
  const { user } = useSession();
  const userId = user?.id ?? "";
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();

  // State
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Add form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newTargetPrice, setNewTargetPrice] = useState("");
  const [newPriority, setNewPriority] = useState<WatchlistPriority>("high");
  const [newNotes, setNewNotes] = useState("");

  // Load watchlist
  const loadWatchlist = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWatchlistForUser(userId);
      setItems(data);
    } catch (err: unknown) {
      logger.warn("[watchlist-builder] load error", err);
      setError(err?.message ?? "Unable to load your watchlist.");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadWatchlist();
  }, [loadWatchlist]);

  // Sort items by priority then by created date
  const sortedItems = useMemo(() => {
    const priorityOrder: Record<WatchlistPriority, number> = { high: 0, medium: 1, low: 2 };
    return [...items].sort((a, b) => {
      const pa = priorityOrder[a.priority] ?? 1;
      const pb = priorityOrder[b.priority] ?? 1;
      if (pa !== pb) return pa - pb;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [items]);

  // Stats
  const stats = useMemo(() => {
    const high = items.filter((i) => i.priority === "high").length;
    const withTarget = items.filter((i) => i.target_price != null).length;
    return { total: items.length, high, withTarget };
  }, [items]);

  // Reset form
  const resetForm = () => {
    setNewTitle("");
    setNewTargetPrice("");
    setNewPriority("high");
    setNewNotes("");
    setShowAddForm(false);
  };

  // Save new item
  const handleSave = useCallback(async () => {
    if (!userId) {
      Alert.alert("Not signed in", "Please sign in to save watchlist items.");
      return;
    }

    const title = newTitle.trim();
    if (!title) {
      Alert.alert("Missing title", "Please enter a name for this item.");
      return;
    }

    let targetPrice: number | null = null;
    if (newTargetPrice.trim()) {
      const parsed = parseFloat(newTargetPrice.replace(/[€,]/g, "").trim());
      if (Number.isFinite(parsed) && parsed > 0) {
        targetPrice = parsed;
      }
    }

    setSaving(true);
    try {
      const created = await upsertWatchlistItem({
        user_id: userId,
        title,
        target_price: targetPrice,
        priority: newPriority,
        notes: newNotes.trim() || null,
        owned: false,
        currency: "EUR",
      });

      if (!created) {
        Alert.alert("Save failed", "Could not save this item. Please try again.");
        return;
      }

      resetForm();
      await loadWatchlist();
    } catch (err: unknown) {
      logger.warn("[watchlist-builder] save error", err);
      Alert.alert("Save error", err?.message ?? "Unable to save this item.");
    } finally {
      setSaving(false);
    }
  }, [userId, newTitle, newTargetPrice, newPriority, newNotes, loadWatchlist]);

  // Delete item
  const handleDelete = useCallback(
    async (item: WatchlistItem) => {
      Alert.alert(
        "Remove from watchlist?",
        `"${item.title}" will be removed from your watchlist.`,
        [
          { text: "Cancel", style: "cancel" },
          {
            text: "Remove",
            style: "destructive",
            onPress: async () => {
              const ok = await deleteWatchlistItem(item.id);
              if (!ok) {
                Alert.alert("Delete failed", "Could not remove this item.");
                return;
              }
              await loadWatchlist();
            },
          },
        ]
      );
    },
    [loadWatchlist]
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
      <Stack.Screen options={{ headerShown: false }} />
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        {/* Header */}
        <View style={styles.header}>
          <AnimatedPressable
            style={styles.backBtn}
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); router.back(); }}
            accessibilityLabel="Go back"
          >
            <Ionicons name="chevron-back" size={24} color={COLORS.navy} />
          </AnimatedPressable>
          <View style={styles.headerText}>
            <Text style={styles.headerLabel}>COLLECTOR</Text>
            <Text style={styles.headerTitle}>Watchlist</Text>
          </View>
          <AnimatedPressable
            style={styles.addHeaderBtn}
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setShowAddForm(true); }}
            accessibilityLabel="Add item"
          >
            <Ionicons name="add" size={24} color={COLORS.tiffanyDark} />
          </AnimatedPressable>
        </View>

        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
          {/* Stats Banner */}
          <View style={styles.statsBanner}>
            <View style={styles.statItem}>
              <Text style={styles.statValue}>{stats.total}</Text>
              <Text style={styles.statLabel}>Items</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text style={styles.statValue}>{stats.high}</Text>
              <Text style={styles.statLabel}>High Priority</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text style={styles.statValue}>{stats.withTarget}</Text>
              <Text style={styles.statLabel}>With Targets</Text>
            </View>
          </View>

          {/* Error */}
          {error && (
            <View style={styles.errorBanner}>
              <Ionicons name="warning-outline" size={16} color={COLORS.danger} />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          {/* Loading */}
          {loading && (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="small" color={COLORS.tiffany} />
              <Text style={styles.loadingText}>Loading watchlist...</Text>
            </View>
          )}

          {/* Add Form (Expanded) */}
          {showAddForm && (
            <View style={styles.addFormCard}>
              <View style={styles.addFormHeader}>
                <Text style={styles.addFormTitle}>Add to Watchlist</Text>
                <AnimatedPressable onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); resetForm(); }} style={styles.closeFormBtn} accessibilityRole="button" accessibilityLabel="Close add form">
                  <Ionicons name="close" size={20} color={COLORS.muted} />
                </AnimatedPressable>
              </View>

              {/* Title Input */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Item Name *</Text>
                <TextInput
                  style={styles.textInput}
                  value={newTitle}
                  onChangeText={setNewTitle}
                  placeholder="e.g., PSA 10 Charizard Base Set"
                  placeholderTextColor={COLORS.muted}
                  autoFocus
                  accessibilityLabel="Item name"
                />
              </View>

              {/* Target Price Input */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Target Price (optional)</Text>
                <TextInput
                  style={styles.textInput}
                  value={newTargetPrice}
                  onChangeText={setNewTargetPrice}
                  placeholder="e.g., 500"
                  placeholderTextColor={COLORS.muted}
                  keyboardType="decimal-pad"
                  accessibilityLabel="Target price"
                />
                <Text style={styles.inputHint}>Get notified when price hits your target</Text>
              </View>

              {/* Priority Selector */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Priority</Text>
                <View style={styles.priorityRow}>
                  {(["high", "medium", "low"] as WatchlistPriority[]).map((p) => {
                    const config = PRIORITY_CONFIG[p];
                    const active = newPriority === p;
                    return (
                      <AnimatedPressable
                        key={p}
                        style={[
                          styles.priorityBtn,
                          active && { backgroundColor: config.bg, borderColor: config.color },
                        ]}
                        onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setNewPriority(p); }}
                        accessibilityRole="button"
                        accessibilityLabel={`${config.label} priority${active ? ', selected' : ''}`}
                      >
                        <Text
                          style={[
                            styles.priorityBtnText,
                            active && { color: config.color, fontWeight: "700" },
                          ]}
                        >
                          {config.label}
                        </Text>
                      </AnimatedPressable>
                    );
                  })}
                </View>
              </View>

              {/* Notes Input */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Notes (optional)</Text>
                <TextInput
                  style={[styles.textInput, styles.textInputMultiline]}
                  value={newNotes}
                  onChangeText={setNewNotes}
                  placeholder="Any notes about this item..."
                  placeholderTextColor={COLORS.muted}
                  multiline
                  numberOfLines={2}
                  accessibilityLabel="Notes"
                />
              </View>

              {/* Save Button */}
              <AnimatedPressable
                style={[styles.saveBtn, saving && styles.saveBtnDisabled]}
                onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED); handleSave(); }}
                disabled={saving}
                accessibilityRole="button"
                accessibilityLabel={saving ? 'Saving' : 'Add to watchlist'}
              >
                {saving ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <>
                    <Ionicons name="add-circle" size={20} color="#FFFFFF" />
                    <Text style={styles.saveBtnText}>Add to Watchlist</Text>
                  </>
                )}
              </AnimatedPressable>
            </View>
          )}

          {/* Empty State */}
          {!loading && items.length === 0 && !showAddForm && (
            <AnimatedPressable style={styles.emptyState} onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setShowAddForm(true); }} accessibilityRole="button" accessibilityLabel="Start your watchlist, add your first item">
              <View style={styles.emptyIconWrap}>
                <Ionicons name="eye-outline" size={32} color={COLORS.tiffany} />
              </View>
              <Text style={styles.emptyTitle}>Start Your Watchlist</Text>
              <Text style={styles.emptySubtitle}>
                Track items you want to buy and set price targets to get notified when
                they hit your budget.
              </Text>
              <View style={styles.emptyAddBtn}>
                <Ionicons name="add" size={18} color={COLORS.tiffanyDark} />
                <Text style={styles.emptyAddText}>Add Your First Item</Text>
              </View>
            </AnimatedPressable>
          )}

          {/* Watchlist Items */}
          {!loading && sortedItems.length > 0 && (
            <View style={styles.listSection}>
              <Text style={styles.listTitle}>
                {sortedItems.length} {sortedItems.length === 1 ? "item" : "items"}
              </Text>

              {sortedItems.map((item) => {
                const priorityConfig = PRIORITY_CONFIG[item.priority] ?? PRIORITY_CONFIG.medium;
                return (
                  <View key={item.id} style={styles.itemCard}>
                    <View style={styles.itemCardMain}>
                      <View style={styles.itemCardLeft}>
                        <View style={styles.itemTitleRow}>
                          <Text style={styles.itemTitle} numberOfLines={2}>
                            {item.title}
                          </Text>
                          <View
                            style={[
                              styles.priorityBadge,
                              { backgroundColor: priorityConfig.bg },
                            ]}
                          >
                            <Text
                              style={[styles.priorityBadgeText, { color: priorityConfig.color }]}
                            >
                              {priorityConfig.label}
                            </Text>
                          </View>
                        </View>

                        {item.target_price != null && (
                          <View style={styles.targetRow}>
                            <Ionicons name="flag" size={14} color={COLORS.tiffanyDark} />
                            <Text style={styles.targetText}>
                              Target: {formatPrice(item.target_price)}
                            </Text>
                          </View>
                        )}

                        {item.notes && (
                          <Text style={styles.itemNotes} numberOfLines={2}>
                            {item.notes}
                          </Text>
                        )}
                      </View>

                      <AnimatedPressable
                        style={styles.deleteBtn}
                        onPress={() => { fireHaptic(HapticIntent.ALERT_TRIGGERED); handleDelete(item); }}
                        accessibilityRole="button"
                        accessibilityLabel={`Remove ${item.title} from watchlist`}
                      >
                        <Ionicons name="trash-outline" size={18} color={COLORS.muted} />
                      </AnimatedPressable>
                    </View>
                  </View>
                );
              })}
            </View>
          )}

          {/* Floating Add Button (when form is closed and list exists) */}
          {!showAddForm && items.length > 0 && (
            <AnimatedPressable style={styles.floatingAddBtn} onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setShowAddForm(true); }} accessibilityRole="button" accessibilityLabel="Add item to watchlist">
              <Ionicons name="add" size={20} color="#FFFFFF" />
              <Text style={styles.floatingAddText}>Add Item</Text>
            </AnimatedPressable>
          )}

          {/* Bottom spacing */}
          <View style={{ height: 32 }} />
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────

const styles = {
  safe: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },

  // Header
  header: {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: COLORS.background,
  },
  backBtn: {
    width: 40,
    height: 40,
    alignItems: "center" as const,
    justifyContent: "center" as const,
    marginLeft: -8,
  },
  headerText: {
    flex: 1,
    marginLeft: 4,
  },
  headerLabel: {
    fontSize: 11,
    fontWeight: "600" as const,
    color: COLORS.muted,
    letterSpacing: 0.5,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: "800" as const,
    color: COLORS.navy,
  },
  addHeaderBtn: {
    width: 40,
    height: 40,
    alignItems: "center" as const,
    justifyContent: "center" as const,
    backgroundColor: COLORS.tiffanyLight,
    borderRadius: 12,
  },

  // Stats Banner
  statsBanner: {
    flexDirection: "row" as const,
    backgroundColor: COLORS.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 16,
    marginBottom: 16,
  },
  statItem: {
    flex: 1,
    alignItems: "center" as const,
  },
  statValue: {
    fontSize: 24,
    fontWeight: "800" as const,
    color: COLORS.navy,
  },
  statLabel: {
    fontSize: 11,
    color: COLORS.muted,
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    backgroundColor: COLORS.border,
    marginHorizontal: 8,
  },

  // Error
  errorBanner: {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    gap: 8,
    backgroundColor: "#FEF2F2",
    padding: 12,
    borderRadius: 12,
    marginBottom: 16,
  },
  errorText: {
    color: COLORS.danger,
    fontSize: 13,
    flex: 1,
  },

  // Loading
  loadingContainer: {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    justifyContent: "center" as const,
    padding: 20,
    gap: 10,
  },
  loadingText: {
    color: COLORS.muted,
    fontSize: 14,
  },

  // Add Form
  addFormCard: {
    backgroundColor: COLORS.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 16,
    marginBottom: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  addFormHeader: {
    flexDirection: "row" as const,
    justifyContent: "space-between" as const,
    alignItems: "center" as const,
    marginBottom: 16,
  },
  addFormTitle: {
    fontSize: 18,
    fontWeight: "700" as const,
    color: COLORS.navy,
  },
  closeFormBtn: {
    width: 32,
    height: 32,
    alignItems: "center" as const,
    justifyContent: "center" as const,
  },

  // Inputs
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: "600" as const,
    color: COLORS.navy,
    marginBottom: 6,
  },
  inputHint: {
    fontSize: 11,
    color: COLORS.muted,
    marginTop: 4,
  },
  textInput: {
    backgroundColor: COLORS.inputBg,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: COLORS.navy,
  },
  textInputMultiline: {
    minHeight: 60,
    textAlignVertical: "top" as const,
  },

  // Priority
  priorityRow: {
    flexDirection: "row" as const,
    gap: 8,
  },
  priorityBtn: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.card,
    alignItems: "center" as const,
  },
  priorityBtnText: {
    fontSize: 13,
    fontWeight: "500" as const,
    color: COLORS.muted,
  },

  // Save Button
  saveBtn: {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    justifyContent: "center" as const,
    gap: 8,
    backgroundColor: COLORS.tiffany,
    borderRadius: 12,
    paddingVertical: 14,
    marginTop: 4,
  },
  saveBtnDisabled: {
    opacity: 0.7,
  },
  saveBtnText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700" as const,
  },

  // Empty State
  emptyState: {
    alignItems: "center" as const,
    paddingVertical: 40,
    paddingHorizontal: 24,
  },
  emptyIconWrap: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: COLORS.tiffanyLight,
    alignItems: "center" as const,
    justifyContent: "center" as const,
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: "700" as const,
    color: COLORS.navy,
    marginBottom: 8,
    textAlign: "center" as const,
  },
  emptySubtitle: {
    fontSize: 14,
    color: COLORS.muted,
    textAlign: "center" as const,
    lineHeight: 20,
    marginBottom: 20,
  },
  emptyAddBtn: {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 16,
    backgroundColor: COLORS.tiffanyLight,
    borderRadius: 20,
  },
  emptyAddText: {
    fontSize: 14,
    fontWeight: "600" as const,
    color: COLORS.tiffanyDark,
  },

  // List Section
  listSection: {
    marginTop: 8,
  },
  listTitle: {
    fontSize: 13,
    fontWeight: "600" as const,
    color: COLORS.muted,
    marginBottom: 12,
    textTransform: "uppercase" as const,
    letterSpacing: 0.5,
  },

  // Item Card
  itemCard: {
    backgroundColor: COLORS.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 14,
    marginBottom: 10,
  },
  itemCardMain: {
    flexDirection: "row" as const,
  },
  itemCardLeft: {
    flex: 1,
  },
  itemTitleRow: {
    flexDirection: "row" as const,
    alignItems: "flex-start" as const,
    gap: 8,
    marginBottom: 6,
  },
  itemTitle: {
    flex: 1,
    fontSize: 15,
    fontWeight: "600" as const,
    color: COLORS.navy,
    lineHeight: 20,
  },
  priorityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  priorityBadgeText: {
    fontSize: 11,
    fontWeight: "700" as const,
  },
  targetRow: {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    gap: 6,
    marginBottom: 4,
  },
  targetText: {
    fontSize: 13,
    fontWeight: "600" as const,
    color: COLORS.tiffanyDark,
  },
  itemNotes: {
    fontSize: 12,
    color: COLORS.muted,
    marginTop: 4,
    lineHeight: 16,
  },
  deleteBtn: {
    width: 36,
    height: 36,
    alignItems: "center" as const,
    justifyContent: "center" as const,
    marginLeft: 8,
  },

  // Floating Add Button
  floatingAddBtn: {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    justifyContent: "center" as const,
    gap: 6,
    backgroundColor: COLORS.tiffany,
    borderRadius: 24,
    paddingVertical: 12,
    paddingHorizontal: 20,
    alignSelf: "center" as const,
    marginTop: 8,
    shadowColor: COLORS.tiffany,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  floatingAddText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700" as const,
  },
};
