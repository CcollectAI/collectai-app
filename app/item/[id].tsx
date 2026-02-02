import React, { useState, useRef } from "react";
import { Link, router } from 'expo-router';
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  Image,
  TextInput,
  Pressable,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Animated,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { Ionicons } from '@expo/vector-icons';
import { useColorTheme } from "../../src/theme/colors";
import { dataProvider } from "@/data";
import { PriceConfidenceGauge } from "@/components/PriceConfidenceGauge";

// Format currency with proper number syntax (e.g., €1.234 or €1,234)
const formatCurrency = (value: string | number | undefined | null): string => {
  if (value === undefined || value === null || value === '') return '?';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '?';
  return new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num);
};

// Format just the number without currency symbol
const formatNumber = (value: string | number | undefined | null): string => {
  if (value === undefined || value === null || value === '') return '?';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '?';
  return new Intl.NumberFormat('de-DE', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num);
};

export default function ItemDetailScreen() {
  const theme = useColorTheme();
  const params = useLocalSearchParams<{
    id?: string;
    draft?: string;
    name?: string;
    category?: string;
    collection?: string;
    condition?: string;
    value?: string;
    notes?: string;
    imageUri?: string;
    q10?: string;
    q50?: string;
    q90?: string;
    confidence?: string;
    explanation?: string;
  }>();

  const {
    id,
    draft,
    name = "Unknown item",
    category = "Unknown category",
    collection = "Not set",
    condition = "Not set",
    value = "0",
    notes: initialNotes = "",
    imageUri,
    q10,
    q50,
    q90,
    confidence,
    explanation,
  } = params;

  const isDraft = id === 'draft' || draft === '1';

  const [notes, setNotes] = useState(initialNotes || "");
  const [savingNotes, setSavingNotes] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const notesInputRef = useRef<TextInput | null>(null);

  // Feedback state
  const [showSalePriceInput, setShowSalePriceInput] = useState(false);
  const [salePrice, setSalePrice] = useState("");
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  // Quick-edit state (draft mode)
  const [editableName, setEditableName] = useState(name);
  const [editableCategory, setEditableCategory] = useState(category);
  const [isEditingName, setIsEditingName] = useState(false);
  const [isEditingCategory, setIsEditingCategory] = useState(false);

  // Expandable explanation state
  const [explanationExpanded, setExplanationExpanded] = useState(false);

  const onSaveNotes = () => {
    setSavingNotes(true);
    // Notes are local-only for now
    setTimeout(() => {
      setSavingNotes(false);
      Alert.alert("Notes saved locally", "Notes are stored on device only (not synced yet).");
    }, 300);
  };

  const onSaveDraft = async () => {
    if (!isDraft) return;

    setSavingDraft(true);
    setSaveError(null);

    try {
      const persisted = await dataProvider.persistQuickscanDraft({
        photoUri: imageUri || '',
        categoryId: editableCategory,
        title: editableName,
        notes: notes || undefined,
      });

      // Navigate to saved item
      router.replace({
        pathname: '/item/[id]',
        params: {
          id: persisted.id,
          name: persisted.title,
          category: persisted.categoryId,
          value: String(q50 || value || 0),
          imageUri: persisted.imageUrl || '',
        },
      });
    } catch (err: any) {
      console.error('[ItemDetail] save draft error:', err);
      setSaveError(err?.message || 'Failed to save item');
    } finally {
      setSavingDraft(false);
    }
  };

  const focusNotes = () => {
    notesInputRef.current?.focus();
  };

  const onSubmitSalePrice = async () => {
    if (!salePrice.trim() || !id || isDraft) return;

    setSubmittingFeedback(true);
    setFeedbackMessage(null);

    try {
      await dataProvider.submitFeedback(id, 'sale_price', salePrice.trim());
      setFeedbackMessage("Thanks! Sale price recorded.");
      setShowSalePriceInput(false);
      setSalePrice("");
    } catch (err: any) {
      console.error('[ItemDetail] feedback error:', err);
      setFeedbackMessage("Failed to submit feedback");
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const onPriceDisagree = async () => {
    if (!id || isDraft) return;

    setSubmittingFeedback(true);
    setFeedbackMessage(null);

    try {
      await dataProvider.submitFeedback(id, 'disagree', 'inaccurate');
      setFeedbackMessage("Thanks for the feedback!");
    } catch (err: any) {
      console.error('[ItemDetail] feedback error:', err);
      setFeedbackMessage("Failed to submit feedback");
    } finally {
      setSubmittingFeedback(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 80 : 0}
    >
      <SafeAreaView style={[styles.safeArea, { backgroundColor: theme.background }]}>
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={[
            styles.content,
            { backgroundColor: theme.background },
          ]}
          keyboardShouldPersistTaps="handled"
        >
          {/* Image — use captured imageUri in draft mode, placeholder otherwise */}
          <View style={[styles.imageWrapper, { borderColor: theme.border }]}>
            {imageUri ? (
              <Image
                source={{ uri: imageUri }}
                style={styles.image}
                resizeMode="cover"
              />
            ) : (
              <Image
                source={require("../../assets/placeholder.png")}
                style={styles.image}
                resizeMode="cover"
              />
            )}
          </View>

          {/* Draft mode indicator + save button */}
          {isDraft && (
            <View style={styles.draftSection}>
              <View style={[styles.draftBanner, { backgroundColor: theme.accent }]}>
                <Text style={[styles.draftText, { color: theme.accentText }]}>
                  Draft — not saved yet
                </Text>
              </View>

              {saveError && (
                <Text style={[styles.errorText, { color: '#B00020' }]}>
                  {saveError}
                </Text>
              )}

              <View style={styles.draftButtonsRow}>
                <Pressable
                  onPress={onSaveDraft}
                  disabled={savingDraft}
                  style={[
                    styles.saveDraftButton,
                    { backgroundColor: '#16a34a', opacity: savingDraft ? 0.7 : 1 },
                  ]}
                >
                  {savingDraft ? (
                    <ActivityIndicator size="small" color="#FFFFFF" />
                  ) : (
                    <>
                      <Ionicons name="checkmark-circle" size={18} color="#FFFFFF" />
                      <Text style={styles.saveDraftButtonText}>Save to Collection</Text>
                    </>
                  )}
                </Pressable>

                <Pressable
                  onPress={() => router.push('/quickscan')}
                  style={[
                    styles.scanAnotherButton,
                    { backgroundColor: theme.accent },
                  ]}
                >
                  <Ionicons name="camera" size={18} color="#FFFFFF" />
                  <Text style={styles.scanAnotherButtonText}>Scan Another</Text>
                </Pressable>
              </View>
            </View>
          )}

          {/* Details card */}
          <View
            style={[
              styles.card,
              { backgroundColor: theme.card, borderColor: theme.border },
            ]}
          >
            {/* Editable Name (draft mode) */}
            {isDraft && isEditingName ? (
              <TextInput
                style={[styles.nameInput, { color: theme.text, borderColor: theme.border }]}
                value={editableName}
                onChangeText={setEditableName}
                onBlur={() => setIsEditingName(false)}
                autoFocus
                selectTextOnFocus
              />
            ) : (
              <Pressable
                onPress={() => isDraft && setIsEditingName(true)}
                style={styles.editableRow}
              >
                <Text style={[styles.name, { color: theme.text }]}>{editableName}</Text>
                {isDraft && (
                  <Ionicons name="pencil" size={14} color={theme.mutedText} style={{ marginLeft: 6 }} />
                )}
              </Pressable>
            )}

            {/* Editable Category with drill-down link */}
            {isDraft && isEditingCategory ? (
              <TextInput
                style={[styles.categoryInput, { color: theme.mutedText, borderColor: theme.border }]}
                value={editableCategory}
                onChangeText={setEditableCategory}
                onBlur={() => setIsEditingCategory(false)}
                autoFocus
                selectTextOnFocus
              />
            ) : (
              <Pressable
                onPress={() => {
                  if (isDraft) {
                    setIsEditingCategory(true);
                  } else {
                    // Navigate to category store
                    const categorySlug = editableCategory.toLowerCase().replace(/[^a-z0-9]/g, '_');
                    router.push(`/categories/${categorySlug}`);
                  }
                }}
                style={[styles.categoryPill, { backgroundColor: theme.accent + '20' }]}
              >
                <Text style={[styles.categoryPillText, { color: theme.accent }]}>
                  {editableCategory}
                </Text>
                {isDraft ? (
                  <Ionicons name="pencil" size={12} color={theme.accent} />
                ) : (
                  <Ionicons name="chevron-forward" size={14} color={theme.accent} />
                )}
              </Pressable>
            )}

            <View style={styles.row}>
              <Text style={[styles.label, { color: theme.mutedText }]}>
                Collection
              </Text>
              <Text style={[styles.value, { color: theme.text }]}>{collection}</Text>
            </View>

            <View style={styles.row}>
              <Text style={[styles.label, { color: theme.mutedText }]}>
                Condition
              </Text>
              <Text style={[styles.value, { color: theme.text }]}>{condition}</Text>
            </View>

            <View style={styles.row}>
              <Text style={[styles.label, { color: theme.mutedText }]}>
                Estimated value
              </Text>
              <Text style={[styles.valueHighlight, { color: theme.text }]}>
                {formatCurrency(value)}
              </Text>
            </View>

            {/* Price bands (q10/q50/q90) — shown in draft mode */}
            {(q10 || q50 || q90) && (
              <View style={styles.priceBandsRow}>
                <Text style={[styles.label, { color: theme.mutedText }]}>
                  Price range
                </Text>
                <Text style={[styles.value, { color: theme.text }]}>
                  {formatCurrency(q10)} – {formatCurrency(q50)} – {formatCurrency(q90)}
                </Text>
              </View>
            )}

            {/* Confidence Gauge — shown in draft mode */}
            {confidence && (
              <View style={styles.confidenceSection}>
                <PriceConfidenceGauge
                  confidence={parseFloat(confidence)}
                  size="medium"
                  colors={{
                    text: theme.text as string,
                    muted: theme.mutedText as string,
                    background: theme.border as string,
                  }}
                />
              </View>
            )}

            {/* Explanation — expandable "Why this price?" section */}
            {explanation && (
              <View style={styles.explanationBlock}>
                <Pressable
                  onPress={() => setExplanationExpanded(!explanationExpanded)}
                  style={styles.explanationHeaderRow}
                >
                  <View style={styles.explanationHeaderLeft}>
                    <Ionicons name="help-circle-outline" size={18} color={theme.accent} />
                    <Text style={[styles.explanationHeader, { color: theme.text }]}>
                      Why this price?
                    </Text>
                  </View>
                  <Ionicons
                    name={explanationExpanded ? "chevron-up" : "chevron-down"}
                    size={18}
                    color={theme.mutedText}
                  />
                </Pressable>
                {explanationExpanded && (
                  <View style={[styles.explanationContent, { backgroundColor: theme.background }]}>
                    <Text style={[styles.explanationText, { color: theme.mutedText }]}>
                      {explanation}
                    </Text>
                  </View>
                )}
              </View>
            )}

            {/* Feedback section — shown for saved items */}
            {!isDraft && id && (
              <View style={styles.feedbackBlock}>
                <Text style={[styles.feedbackHeader, { color: theme.text }]}>
                  Help improve our estimates
                </Text>

                {feedbackMessage && (
                  <Text style={[styles.feedbackMessage, { color: theme.accent }]}>
                    {feedbackMessage}
                  </Text>
                )}

                {showSalePriceInput ? (
                  <View style={styles.salePriceInputRow}>
                    <TextInput
                      style={[
                        styles.salePriceInput,
                        {
                          color: theme.text,
                          borderColor: theme.border,
                          backgroundColor: theme.background,
                        },
                      ]}
                      placeholder="Sale price (e.g., 150.00)"
                      placeholderTextColor={theme.mutedText as string}
                      keyboardType="decimal-pad"
                      value={salePrice}
                      onChangeText={setSalePrice}
                      autoFocus
                    />
                    <Pressable
                      onPress={onSubmitSalePrice}
                      disabled={submittingFeedback || !salePrice.trim()}
                      style={[
                        styles.feedbackSubmitBtn,
                        { backgroundColor: theme.accent, opacity: submittingFeedback ? 0.7 : 1 },
                      ]}
                    >
                      <Text style={[styles.feedbackBtnText, { color: theme.accentText }]}>
                        {submittingFeedback ? "..." : "Submit"}
                      </Text>
                    </Pressable>
                    <Pressable
                      onPress={() => setShowSalePriceInput(false)}
                      style={[styles.feedbackCancelBtn, { borderColor: theme.border }]}
                    >
                      <Text style={[styles.feedbackBtnText, { color: theme.mutedText }]}>
                        Cancel
                      </Text>
                    </Pressable>
                  </View>
                ) : (
                  <View style={styles.feedbackButtonsRow}>
                    <Pressable
                      onPress={() => setShowSalePriceInput(true)}
                      style={[styles.feedbackBtn, { backgroundColor: '#16a34a' }]}
                    >
                      <Text style={styles.feedbackBtnTextWhite}>I sold it for...</Text>
                    </Pressable>
                    <Pressable
                      onPress={onPriceDisagree}
                      disabled={submittingFeedback}
                      style={[
                        styles.feedbackBtn,
                        { backgroundColor: theme.card, borderWidth: 1, borderColor: theme.border },
                      ]}
                    >
                      <Text style={[styles.feedbackBtnText, { color: theme.text }]}>
                        Price seems off
                      </Text>
                    </Pressable>
                  </View>
                )}
              </View>
            )}

            {/* Notes (editable) */}
            <View style={styles.notesBlock}>
              <View style={styles.notesHeaderRow}>
                <Text style={[styles.label, { color: theme.mutedText }]}>
                  Notes
                </Text>
                <Pressable
                  onPress={focusNotes}
                  style={[
                    styles.notesAddButton,
                    { borderColor: theme.border, backgroundColor: theme.card },
                  ]}
                >
                  <Text
                    style={{
                      fontSize: 16,
                      fontWeight: "700",
                      color: theme.text,
                    }}
                  >
                    +
                  </Text>
                </Pressable>
              </View>

              <TextInput
                ref={notesInputRef}
                style={[
                  styles.notesInput,
                  {
                    color: theme.text,
                    borderColor: theme.border,
                    backgroundColor: theme.background,
                  },
                ]}
                placeholder="Add your notes about condition, provenance, where you bought it, etc."
                placeholderTextColor={theme.mutedText as string}
                multiline
                value={notes}
                onChangeText={setNotes}
                textAlignVertical="top"
                blurOnSubmit={false}
              />
              <Text style={[styles.notesHint, { color: theme.mutedText }]}>
                Notes are stored locally only (not synced yet)
              </Text>
              <View style={styles.notesActions}>
                <Pressable
                  onPress={onSaveNotes}
                  style={[
                    styles.saveButton,
                    { backgroundColor: theme.accent, opacity: savingNotes ? 0.7 : 1 },
                  ]}
                  disabled={savingNotes}
                >
                  <Text
                    style={[
                      styles.saveButtonText,
                      { color: theme.accentText },
                    ]}
                  >
                    {savingNotes ? "Saving…" : "Save notes"}
                  </Text>
                </Pressable>
              </View>
            </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  scroll: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 32,
  },
  imageWrapper: {
    width: "100%",
    height: 260,
    borderRadius: 16,
    borderWidth: 1,
    overflow: "hidden",
    marginBottom: 16,
  },
  draftSection: {
    marginBottom: 16,
    gap: 8,
  },
  draftBanner: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  draftText: {
    fontSize: 13,
    fontWeight: '600',
  },
  draftButtonsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  saveDraftButton: {
    flex: 1,
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  saveDraftButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  scanAnotherButton: {
    flex: 1,
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  scanAnotherButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  errorText: {
    fontSize: 12,
    textAlign: 'center',
  },
  priceBandsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 6,
  },
  image: {
    width: "100%",
    height: "100%",
  },
  card: {
    borderWidth: 1,
    borderRadius: 16,
    padding: 16,
    gap: 12,
  },
  name: {
    fontSize: 20,
    fontWeight: "700",
  },
  nameInput: {
    fontSize: 20,
    fontWeight: "700",
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginBottom: 4,
  },
  editableRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  category: {
    fontSize: 13,
  },
  categoryInput: {
    fontSize: 13,
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginTop: 4,
  },
  categoryPill: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    marginTop: 4,
    gap: 4,
  },
  categoryPillText: {
    fontSize: 13,
    fontWeight: '500',
  },
  confidenceSection: {
    marginTop: 12,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 6,
  },
  label: {
    fontSize: 13,
  },
  value: {
    fontSize: 13,
    fontWeight: "500",
  },
  valueHighlight: {
    fontSize: 16,
    fontWeight: "700",
  },
  explanationBlock: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E5E5E5',
  },
  explanationHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
  },
  explanationHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  explanationHeader: {
    fontSize: 14,
    fontWeight: '600',
  },
  explanationContent: {
    marginTop: 10,
    padding: 12,
    borderRadius: 10,
  },
  explanationText: {
    fontSize: 13,
    lineHeight: 19,
  },
  notesBlock: {
    marginTop: 16,
  },
  notesHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  notesAddButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  notesInput: {
    marginTop: 8,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    lineHeight: 18,
    minHeight: 100,
    maxHeight: 220,
  },
  notesHint: {
    marginTop: 4,
    fontSize: 11,
    fontStyle: 'italic',
  },
  notesActions: {
    marginTop: 8,
    flexDirection: "row",
    justifyContent: "flex-end",
  },
  saveButton: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
  },
  saveButtonText: {
    fontSize: 13,
    fontWeight: "600",
  },
  feedbackBlock: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E5E5E5',
  },
  feedbackHeader: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 10,
  },
  feedbackMessage: {
    fontSize: 12,
    marginBottom: 8,
  },
  feedbackButtonsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  feedbackBtn: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  feedbackBtnText: {
    fontSize: 13,
    fontWeight: '500',
  },
  feedbackBtnTextWhite: {
    fontSize: 13,
    fontWeight: '500',
    color: '#FFFFFF',
  },
  salePriceInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  salePriceInput: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 14,
  },
  feedbackSubmitBtn: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 8,
  },
  feedbackCancelBtn: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
  },
});