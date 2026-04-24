/**
 * PaintRecipesCard — Paint recipe management for Warhammer, Gunpla, Scale Models projects.
 */

import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import type { PaintEntry, PaintRecipe } from "@/data/types";

const PAINT_TYPES = ["base", "layer", "shade", "technical", "contrast", "dry", "texture", "spray"] as const;

function getPaintTypeColor(type: string): string {
  const map: Record<string, string> = {
    base: "#3B82F6",
    layer: "#22C55E",
    shade: "#8B5CF6",
    technical: "#F59E0B",
    contrast: "#EC4899",
    dry: "#94A3B8",
    texture: "#D97706",
    spray: "#6366F1",
  };
  return map[type] || "#94A3B8";
}

export interface PaintRecipesCardProps {
  paintRecipes: PaintRecipe[];
  accentColor: string;
  savingRecipes: boolean;
  onSaveRecipes: (recipes: PaintRecipe[]) => void;
  onDeleteRecipe: (idx: number) => void;
}

export const PaintRecipesCard = React.memo(function PaintRecipesCard({
  paintRecipes,
  accentColor,
  savingRecipes,
  onSaveRecipes,
  onDeleteRecipe,
}: PaintRecipesCardProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  // Local form state
  const [addingRecipe, setAddingRecipe] = useState(false);
  const [newRecipeName, setNewRecipeName] = useState("");
  const [newRecipePaints, setNewRecipePaints] = useState<PaintEntry[]>([]);
  const [newRecipeNotes, setNewRecipeNotes] = useState("");
  const [newPaintBrand, setNewPaintBrand] = useState("");
  const [newPaintColor, setNewPaintColor] = useState("");
  const [newPaintType, setNewPaintType] = useState<string>("base");

  const handleAddRecipe = () => {
    if (!newRecipeName.trim()) return;
    const recipe: PaintRecipe = {
      name: newRecipeName.trim(),
      paints: newRecipePaints,
      notes: newRecipeNotes.trim(),
    };
    onSaveRecipes([...paintRecipes, recipe]);
    setNewRecipeName("");
    setNewRecipePaints([]);
    setNewRecipeNotes("");
    setAddingRecipe(false);
  };

  const handleAddPaintToRecipe = () => {
    if (!newPaintBrand.trim() || !newPaintColor.trim()) return;
    setNewRecipePaints((prev) => [
      ...prev,
      { brand: newPaintBrand.trim(), color: newPaintColor.trim(), type: newPaintType },
    ]);
    setNewPaintBrand("");
    setNewPaintColor("");
    setNewPaintType("base");
  };

  const handleRemovePaintFromRecipe = (paintIdx: number) => {
    setNewRecipePaints((prev) => prev.filter((_, i) => i !== paintIdx));
  };

  const handleCancelRecipe = () => {
    setAddingRecipe(false);
    setNewRecipeName("");
    setNewRecipePaints([]);
    setNewRecipeNotes("");
  };

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.cardHeader}>
        <Text style={[styles.cardTitle, { color: colors.text }]}>{t('projects.paint_recipes')}</Text>
        <Text style={[styles.cardSubtitle, { color: colors.muted }]}>{paintRecipes.length} recipes</Text>
      </View>

      {paintRecipes.length === 0 && !addingRecipe ? (
        <Text style={[styles.emptyText, { color: colors.muted }]}>
          No paint recipes yet. Add your paint lists and technique notes.
        </Text>
      ) : (
        <View style={styles.recipesList}>
          {paintRecipes.map((recipe, idx) => (
            <View
              key={idx}
              style={[
                styles.recipeItem,
                idx < paintRecipes.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.border },
              ]}
            >
              <View style={styles.recipeHeader}>
                <View style={styles.recipeHeaderLeft}>
                  <Ionicons name="color-palette-outline" size={16} color={accentColor} />
                  <Text style={[styles.recipeName, { color: colors.text }]}>{recipe.name}</Text>
                </View>
                <AnimatedPressable
                  onPress={() => onDeleteRecipe(idx)}
                  hitSlop={8}
                  accessibilityRole="button"
                  accessibilityLabel={`Delete recipe: ${recipe.name}`}
                >
                  <Ionicons name="close-circle-outline" size={18} color={colors.muted} />
                </AnimatedPressable>
              </View>
              {recipe.paints.length > 0 && (
                <View style={styles.paintsList}>
                  {recipe.paints.map((paint, pIdx) => (
                    <View key={pIdx} style={styles.paintRow}>
                      <View style={[styles.paintTypeDot, { backgroundColor: getPaintTypeColor(paint.type) }]} />
                      <Text style={[styles.paintText, { color: colors.text }]}>
                        {paint.brand} — {paint.color}
                      </Text>
                      <Text style={[styles.paintTypeLabel, { color: colors.muted }]}>
                        {paint.type}
                      </Text>
                    </View>
                  ))}
                </View>
              )}
              {recipe.notes ? (
                <Text style={[styles.recipeNotes, { color: colors.muted }]}>{recipe.notes}</Text>
              ) : null}
            </View>
          ))}
        </View>
      )}

      {/* Add recipe form */}
      {addingRecipe ? (
        <View style={[styles.addRecipeForm, { borderColor: colors.border }]}>
          <TextInput
            value={newRecipeName}
            onChangeText={setNewRecipeName}
            placeholder={t('projects.recipe_name_placeholder')}
            placeholderTextColor={colors.muted}
            style={[styles.addInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
            accessibilityLabel={t('projects.recipe_name_a11y')}
          />

          {/* Paints added so far */}
          {newRecipePaints.length > 0 && (
            <View style={styles.paintsList}>
              {newRecipePaints.map((paint, pIdx) => (
                <View key={pIdx} style={styles.paintRow}>
                  <View style={[styles.paintTypeDot, { backgroundColor: getPaintTypeColor(paint.type) }]} />
                  <Text style={[styles.paintText, { color: colors.text }]}>
                    {paint.brand} — {paint.color}
                  </Text>
                  <Text style={[styles.paintTypeLabel, { color: colors.muted }]}>{paint.type}</Text>
                  <AnimatedPressable
                    onPress={() => handleRemovePaintFromRecipe(pIdx)}
                    hitSlop={8}
                    accessibilityRole="button"
                    accessibilityLabel={`Remove ${paint.color}`}
                  >
                    <Ionicons name="close" size={14} color={colors.muted} />
                  </AnimatedPressable>
                </View>
              ))}
            </View>
          )}

          {/* Add paint entry row */}
          <View style={styles.addPaintRow}>
            <View style={{ flex: 1 }}>
              <TextInput
                value={newPaintBrand}
                onChangeText={setNewPaintBrand}
                placeholder="Brand"
                placeholderTextColor={colors.muted}
                style={[styles.paintInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
                accessibilityLabel={t('projects.paint_brand_a11y')}
              />
            </View>
            <View style={{ flex: 1 }}>
              <TextInput
                value={newPaintColor}
                onChangeText={setNewPaintColor}
                placeholder={t('projects.color_name_placeholder')}
                placeholderTextColor={colors.muted}
                style={[styles.paintInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
                accessibilityLabel={t('projects.paint_color_a11y')}
              />
            </View>
          </View>

          {/* Paint type pills */}
          <View style={styles.paintTypePillsRow}>
            {PAINT_TYPES.map((pt) => (
              <AnimatedPressable
                key={pt}
                onPress={() => setNewPaintType(pt)}
                style={[
                  styles.paintTypePill,
                  {
                    backgroundColor: newPaintType === pt ? accentColor : colors.background,
                    borderColor: newPaintType === pt ? accentColor : colors.border,
                  },
                ]}
                accessibilityRole="button"
                accessibilityState={{ selected: newPaintType === pt }}
                accessibilityLabel={`Paint type: ${pt}`}
              >
                <Text
                  style={[
                    styles.paintTypePillText,
                    { color: newPaintType === pt ? colors.accentText : colors.muted },
                  ]}
                >
                  {pt}
                </Text>
              </AnimatedPressable>
            ))}
          </View>

          <AnimatedPressable
            onPress={handleAddPaintToRecipe}
            disabled={!newPaintBrand.trim() || !newPaintColor.trim()}
            style={[
              styles.addPaintBtn,
              {
                backgroundColor:
                  newPaintBrand.trim() && newPaintColor.trim() ? accentColor + "15" : colors.background,
                borderColor:
                  newPaintBrand.trim() && newPaintColor.trim() ? accentColor : colors.border,
              },
            ]}
            accessibilityRole="button"
            accessibilityLabel={t('projects.add_paint_a11y')}
          >
            <Ionicons
              name="add"
              size={16}
              color={newPaintBrand.trim() && newPaintColor.trim() ? accentColor : colors.muted}
            />
            <Text
              style={[
                styles.addPaintBtnText,
                { color: newPaintBrand.trim() && newPaintColor.trim() ? accentColor : colors.muted },
              ]}
            >
              Add Paint
            </Text>
          </AnimatedPressable>

          {/* Technique notes */}
          <TextInput
            value={newRecipeNotes}
            onChangeText={setNewRecipeNotes}
            placeholder={t('projects.technique_notes_placeholder')}
            placeholderTextColor={colors.muted}
            multiline
            style={[styles.addNoteInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
            accessibilityLabel={t('projects.technique_notes_a11y')}
          />

          {/* Save / Cancel */}
          <View style={styles.addRow}>
            <AnimatedPressable
              onPress={handleCancelRecipe}
              style={[styles.cancelBtn, { borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel="Cancel"
            >
              <Text style={[styles.cancelBtnText, { color: colors.muted }]}>Cancel</Text>
            </AnimatedPressable>
            <AnimatedPressable
              onPress={handleAddRecipe}
              disabled={!newRecipeName.trim() || savingRecipes}
              style={[
                styles.saveBtn,
                {
                  backgroundColor: newRecipeName.trim() ? accentColor : colors.border,
                  opacity: savingRecipes ? 0.7 : 1,
                },
              ]}
              accessibilityRole="button"
              accessibilityLabel={t('projects.save_recipe_a11y')}
            >
              {savingRecipes ? (
                <ActivityIndicator size="small" color={colors.accentText} />
              ) : (
                <Text style={[styles.saveBtnText, { color: colors.accentText }]}>{t('projects.save_recipe')}</Text>
              )}
            </AnimatedPressable>
          </View>
        </View>
      ) : (
        <AnimatedPressable
          onPress={() => setAddingRecipe(true)}
          style={[styles.applyTemplateBtn, { backgroundColor: accentColor + "15", borderColor: accentColor }]}
          accessibilityRole="button"
          accessibilityLabel={t('projects.add_recipe_a11y')}
        >
          <Ionicons name="add-circle-outline" size={18} color={accentColor} />
          <View style={{ flex: 1, marginLeft: 8 }}>
            <Text style={[styles.applyTemplateTitle, { color: accentColor }]}>{t('projects.add_paint_recipe')}</Text>
            <Text style={[styles.applyTemplateHint, { color: colors.muted }]}>
              Track paints, brands, and techniques
            </Text>
          </View>
        </AnimatedPressable>
      )}
    </View>
  );
});

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "700",
  },
  cardSubtitle: {
    fontSize: 12,
  },
  emptyText: {
    fontSize: 13,
    fontStyle: "italic",
    marginBottom: 12,
  },
  recipesList: {
    marginBottom: 12,
  },
  recipeItem: {
    paddingVertical: 12,
  },
  recipeHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  recipeHeaderLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flex: 1,
  },
  recipeName: {
    fontSize: 15,
    fontWeight: "700",
    flex: 1,
  },
  paintsList: {
    marginTop: 6,
    gap: 4,
  },
  paintRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 3,
  },
  paintTypeDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  paintText: {
    fontSize: 13,
    flex: 1,
  },
  paintTypeLabel: {
    fontSize: 11,
    fontWeight: "600",
    textTransform: "capitalize" as const,
  },
  recipeNotes: {
    fontSize: 12,
    lineHeight: 17,
    marginTop: 6,
    fontStyle: "italic" as const,
  },
  addRecipeForm: {
    marginTop: 8,
    gap: 8,
    borderTopWidth: 1,
    paddingTop: 12,
  },
  addInput: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  addPaintRow: {
    flexDirection: "row",
    gap: 8,
  },
  paintInput: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
  },
  paintTypePillsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  paintTypePill: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
    borderWidth: 1,
  },
  paintTypePillText: {
    fontSize: 11,
    fontWeight: "600",
    textTransform: "capitalize" as const,
  },
  addPaintBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
  },
  addPaintBtnText: {
    fontSize: 13,
    fontWeight: "600",
  },
  addNoteInput: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    minHeight: 60,
    textAlignVertical: "top",
  },
  addRow: {
    flexDirection: "row",
    gap: 8,
  },
  cancelBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    flex: 1,
    alignItems: "center" as const,
  },
  cancelBtnText: {
    fontSize: 13,
    fontWeight: "600",
  },
  saveBtn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  saveBtnText: {
    fontSize: 13,
    fontWeight: "600",
  },
  applyTemplateBtn: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 12,
  },
  applyTemplateTitle: {
    fontSize: 14,
    fontWeight: "600",
  },
  applyTemplateHint: {
    fontSize: 12,
    marginTop: 2,
  },
});
