/**
 * Condition Grading Guide screen.
 * Shows condition grades with category-specific descriptions, visual indicators, and price impact notes.
 */
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import React, { useState, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  StatusBar,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { AnimatedPressable } from '@/motion';

const TIFFANY = '#81D8D0';
const TIFFANY_DARK = '#5FBFB6';

// ─────────────────────────────────────────────────────────────────────────────
// Condition Grade Definitions
// ─────────────────────────────────────────────────────────────────────────────

type ConditionGrade = {
  name: string;
  abbreviation: string;
  color: string;
  priceImpact: string;
};

const CONDITION_GRADES: ConditionGrade[] = [
  { name: 'Mint', abbreviation: 'M', color: '#10B981', priceImpact: '100% of market value' },
  { name: 'Near Mint', abbreviation: 'NM', color: '#10B981', priceImpact: 'Typically 80-90% of mint value' },
  { name: 'Excellent', abbreviation: 'EX', color: '#34D399', priceImpact: 'Typically 65-80% of mint value' },
  { name: 'Very Good', abbreviation: 'VG', color: '#F59E0B', priceImpact: 'Typically 50-65% of mint value' },
  { name: 'Good', abbreviation: 'G', color: '#F59E0B', priceImpact: 'Typically 35-50% of mint value' },
  { name: 'Fair', abbreviation: 'FR', color: '#EF4444', priceImpact: 'Typically 20-35% of mint value' },
  { name: 'Poor', abbreviation: 'PR', color: '#EF4444', priceImpact: 'Typically 5-20% of mint value' },
];

// ─────────────────────────────────────────────────────────────────────────────
// Category-Specific Descriptions
// ─────────────────────────────────────────────────────────────────────────────

type CategoryDescriptions = Record<string, string>;

/** Maps grade abbreviation to description for each category group */
const CATEGORY_DESCRIPTIONS: Record<string, CategoryDescriptions> = {
  // Trading cards: Pokemon, MTG, Yugioh, Lorcana
  cards: {
    M: 'Perfect condition. No whitening, no edge wear, perfectly centered, corners are sharp. As if just pulled from a pack.',
    NM: 'Very minor imperfections only visible upon close inspection. Slight whitening on one edge or minimal corner wear. Centering is slightly off but still within acceptable range.',
    EX: 'Light wear visible on edges and corners. Minor whitening on multiple edges. Centering may be noticeably off. Surface may show very faint scratches under light.',
    VG: 'Moderate wear. Noticeable whitening on edges, minor corner bends or dings. Surface may have light scratches. Card is still structurally sound with no major creases.',
    G: 'Significant wear. Heavy whitening, rounded corners, visible surface scratches. May have minor creases or slight warping. Still fully readable and displayable.',
    FR: 'Heavy wear throughout. Major creases, heavy whitening, worn corners. May have tape residue or writing. Card integrity is compromised but still identifiable.',
    PR: 'Severe damage. Major creases, tears, water damage, or missing pieces. Heavy discoloration. Suitable only for placeholder or collecting completeness.',
  },

  // Warhammer, Gunpla, Scale Models
  models: {
    M: 'Brand new, factory sealed or unbuilt on sprue. All parts present, instruction manual included. Box in excellent condition.',
    NM: 'Assembled with expert-level paint job. No visible defects, clean lines, proper basing. All original parts present. Professional display quality.',
    EX: 'Well-assembled and painted to a good tabletop standard. Minor paint imperfections only visible up close. All parts present and properly attached.',
    VG: 'Assembled with acceptable paint job. Some visible brush strokes, minor paint chips, or slightly thick coats. All major parts present.',
    G: 'Assembled with basic paint or primed. Some parts may be slightly misaligned. Minor chips or touch-ups needed. May be missing non-essential bits.',
    FR: 'Partially assembled or poorly painted. Visible glue marks, significant paint issues. May be missing small parts like weapons or accessories.',
    PR: 'Heavily damaged, broken parts, stripped paint, or significant missing components. May need extensive restoration or be useful only for bits/conversions.',
  },

  // Vinyl Records
  vinyl_records: {
    M: 'Unplayed, factory sealed or absolutely flawless. No surface marks of any kind. Labels are perfect. Sleeve/jacket is pristine with no wear.',
    NM: 'Nearly perfect. May have been played once or twice with no audible defects. Sleeve shows minimal shelf wear. Labels are clean with no writing.',
    EX: 'Shows some signs of play but no skips. Very minor surface marks. Sleeve has light ring wear or minor edge wear. Labels may have minor writing.',
    VG: 'Noticeable surface noise and light scratches that do not cause skipping. Sleeve has ring wear, seam splits under 2 inches. Labels may have writing or stickers.',
    G: 'Plays through without skipping but has significant surface noise. Visible scratches. Sleeve has splits, writing, or tape repairs. Acceptable for casual listening.',
    FR: 'Plays through with difficulty, may skip in places. Deep scratches, warping visible. Sleeve is heavily damaged with splits or missing pieces.',
    PR: 'May not play through. Severe scratches, warping, or cracks. Sleeve is heavily damaged or missing. Suitable only as a filler or wall decoration.',
  },

  // Comic Books
  comic_books: {
    M: 'Perfectly flat cover with no surface wear. Staples are centered and clean. No spine stress, no corner bumps. Pages are white and supple. CGC 9.8-10 equivalent.',
    NM: 'Nearly perfect with only minor imperfections. Very slight spine stress, minimal corner wear. Pages are white to off-white. Cover is flat with full gloss. CGC 9.0-9.6 equivalent.',
    EX: 'Slight wear beginning to show. Minor spine roll, small color-breaking stress marks. Corners may have light bumps. Pages are off-white to cream. CGC 7.0-8.5 equivalent.',
    VG: 'Moderate wear but still an attractive copy. Minor spine roll, small tears or stress marks. Some corner wear. Pages may be tan. Cover may have minor soiling. CGC 5.0-6.5 equivalent.',
    G: 'Significant wear. Spine may be rolled, cover creases visible. Pages are brown/tan. May have small pieces missing from cover edges. Still complete and readable. CGC 2.5-4.5 equivalent.',
    FR: 'Heavy wear. Major creases, spine may be split. Cover may be detached on one staple. Pages are brown and brittle. Pieces may be missing from cover. CGC 1.0-2.0 equivalent.',
    PR: 'Severely damaged. Cover may be detached or mostly missing. Heavy staining or water damage. Pages may be torn or missing. Barely holds together. CGC 0.5 equivalent.',
  },

  // Sneakers
  sneakers: {
    M: 'Deadstock, never worn. Original box, all accessories (extra laces, hang tags). No factory defects. As fresh as the day they were produced.',
    NM: 'Tried on indoors only or worn once briefly. No visible sole wear. No creasing. Original box included. May have very minor handling marks.',
    EX: 'Lightly worn 2-3 times. Minimal sole wear, very slight creasing on toe box. Upper is clean with no scuffs. Box may show minor shelf wear.',
    VG: 'Moderate wear visible. Light creasing, minor sole wear pattern visible. Upper may have light scuffs that are cleanable. Midsole is still white/clean.',
    G: 'Regular wear. Noticeable creasing, visible sole wear, light scuffs on upper. Midsole may show yellowing. Still structurally sound and wearable.',
    FR: 'Heavy wear. Deep creases, significant sole wear, visible scuffs and discoloration. Midsole yellowing. May have minor separation or loose stitching.',
    PR: 'Heavily worn with significant damage. Sole separation, holes, major discoloration. No longer suitable for regular wear. Collector-only value.',
  },

  // Default for all other categories
  default: {
    M: 'Brand new, unused, in original packaging. Perfect condition with no signs of handling. All accessories and documentation included.',
    NM: 'Like new with only the slightest signs of handling. Packaging may have been opened but item is unused. All accessories present.',
    EX: 'Very minor wear from light use or display. No significant defects. All major accessories present. Would pass as new at a glance.',
    VG: 'Light to moderate signs of use. Minor surface wear, light scratches, or small imperfections. Fully functional and presentable.',
    G: 'Noticeable wear from regular use. Visible scratches, minor scuffs, or fading. Fully functional. Shows honest signs of being enjoyed.',
    FR: 'Significant wear and possible minor damage. May have chips, cracks, heavy scratching, or discoloration. Still functional but shows heavy use.',
    PR: 'Major wear or damage. May be broken, heavily stained, or missing parts. Primarily of interest for restoration or as a placeholder in a collection.',
  },
};

/** Map category IDs to the correct description group */
function getCategoryGroup(categoryId: string): string {
  const cardCategories = ['pokemon', 'mtg', 'yugioh', 'lorcana', 'sportscards'];
  const modelCategories = ['warhammer', 'gunpla', 'scale_models', 'lego', 'diecast'];
  const comicCategories = ['comic_books', 'manga'];
  const sneakerCategories = ['sneakers'];
  const vinylCategories = ['vinyl_records', 'anime_ost_vinyl'];

  if (cardCategories.includes(categoryId)) return 'cards';
  if (modelCategories.includes(categoryId)) return 'models';
  if (comicCategories.includes(categoryId)) return 'comic_books';
  if (sneakerCategories.includes(categoryId)) return 'sneakers';
  if (vinylCategories.includes(categoryId)) return 'vinyl_records';
  return 'default';
}

// ─────────────────────────────────────────────────────────────────────────────
// Category Selector Options
// ─────────────────────────────────────────────────────────────────────────────

type CategoryOption = { id: string; label: string };

const CATEGORY_OPTIONS: CategoryOption[] = [
  { id: 'pokemon', label: 'Pokemon TCG' },
  { id: 'mtg', label: 'Magic: The Gathering' },
  { id: 'yugioh', label: 'Yu-Gi-Oh!' },
  { id: 'lorcana', label: 'Disney Lorcana' },
  { id: 'sportscards', label: 'Sports Cards' },
  { id: 'warhammer', label: 'Warhammer' },
  { id: 'gunpla', label: 'Gunpla' },
  { id: 'scale_models', label: 'Scale Models' },
  { id: 'lego', label: 'LEGO' },
  { id: 'diecast', label: 'Diecast' },
  { id: 'vinyl_records', label: 'Vinyl Records' },
  { id: 'comic_books', label: 'Comic Books' },
  { id: 'manga', label: 'Manga' },
  { id: 'sneakers', label: 'Sneakers' },
  { id: 'funko', label: 'Funko Pop' },
  { id: 'retro_games', label: 'Retro Games' },
  { id: 'designer_toys', label: 'Designer Toys' },
  { id: 'anime_figures', label: 'Anime Figures' },
  { id: 'hot_toys', label: 'Hot Toys' },
  { id: 'watches', label: 'Watches' },
  { id: 'kpop_merch', label: 'K-pop Merch' },
  { id: 'default', label: 'Other / General' },
];

// ─────────────────────────────────────────────────────────────────────────────
// Screen Component
// ─────────────────────────────────────────────────────────────────────────────

function ConditionGuideScreen() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const params = useLocalSearchParams<{ categoryId?: string }>();
  const [selectedCategory, setSelectedCategory] = useState(params.categoryId ?? 'default');
  const [showCategoryPicker, setShowCategoryPicker] = useState(!params.categoryId);

  const categoryGroup = useMemo(() => getCategoryGroup(selectedCategory), [selectedCategory]);
  const descriptions = CATEGORY_DESCRIPTIONS[categoryGroup] ?? CATEGORY_DESCRIPTIONS.default;

  const selectedLabel = useMemo(() => {
    return CATEGORY_OPTIONS.find((c) => c.id === selectedCategory)?.label ?? 'General';
  }, [selectedCategory]);

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <StatusBar barStyle="dark-content" />

      {/* Header */}
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.back();
          }}
          style={styles.headerBackBtn}
          accessibilityRole="button"
          accessibilityLabel="Go back"
        >
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <Text style={[styles.headerTitle, { color: colors.text }]}>
          Condition Guide
        </Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Category selector */}
        <Pressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            setShowCategoryPicker((prev) => !prev);
          }}
          style={[styles.categorySelector, { backgroundColor: colors.card, borderColor: colors.border }]}
          accessibilityRole="button"
          accessibilityLabel={`Category: ${selectedLabel}. Tap to change`}
        >
          <View style={styles.categorySelectorLeft}>
            <Ionicons name="grid-outline" size={18} color={TIFFANY_DARK} />
            <Text style={[styles.categorySelectorLabel, { color: colors.muted }]}>
              Category
            </Text>
          </View>
          <View style={styles.categorySelectorRight}>
            <Text style={[styles.categorySelectorValue, { color: colors.text }]}>
              {selectedLabel}
            </Text>
            <Ionicons
              name={showCategoryPicker ? 'chevron-up' : 'chevron-down'}
              size={16}
              color={colors.muted}
            />
          </View>
        </Pressable>

        {/* Category picker dropdown */}
        {showCategoryPicker && (
          <View style={[styles.categoryPicker, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <ScrollView
              style={styles.categoryPickerScroll}
              nestedScrollEnabled
              showsVerticalScrollIndicator={false}
            >
              {CATEGORY_OPTIONS.map((cat) => {
                const isSelected = cat.id === selectedCategory;
                return (
                  <Pressable
                    key={cat.id}
                    onPress={() => {
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                      setSelectedCategory(cat.id);
                      setShowCategoryPicker(false);
                    }}
                    style={[
                      styles.categoryPickerItem,
                      isSelected && { backgroundColor: TIFFANY + '15' },
                    ]}
                    accessibilityRole="radio"
                    accessibilityState={{ selected: isSelected }}
                    accessibilityLabel={cat.label}
                  >
                    <Text
                      style={[
                        styles.categoryPickerItemText,
                        { color: isSelected ? TIFFANY_DARK : colors.text },
                        isSelected && { fontWeight: '600' },
                      ]}
                    >
                      {cat.label}
                    </Text>
                    {isSelected && (
                      <Ionicons name="checkmark" size={18} color={TIFFANY_DARK} />
                    )}
                  </Pressable>
                );
              })}
            </ScrollView>
          </View>
        )}

        {/* Intro text */}
        <Text style={[styles.introText, { color: colors.muted }]}>
          Condition significantly affects the value of collectibles. Use this guide to accurately grade your items.
        </Text>

        {/* Grade cards */}
        {CONDITION_GRADES.map((grade) => (
          <View
            key={grade.abbreviation}
            style={[styles.gradeCard, { backgroundColor: colors.card, borderColor: colors.border }]}
          >
            {/* Grade header row */}
            <View style={styles.gradeHeaderRow}>
              <View style={[styles.gradeDot, { backgroundColor: grade.color }]} />
              <Text style={[styles.gradeName, { color: colors.text }]}>
                {grade.name}
              </Text>
              <View style={[styles.gradeAbbrevBadge, { backgroundColor: grade.color + '18' }]}>
                <Text style={[styles.gradeAbbrevText, { color: grade.color }]}>
                  {grade.abbreviation}
                </Text>
              </View>
            </View>

            {/* Description */}
            <Text style={[styles.gradeDescription, { color: colors.text }]}>
              {descriptions[grade.abbreviation] ?? CATEGORY_DESCRIPTIONS.default[grade.abbreviation]}
            </Text>

            {/* Price impact */}
            <View style={[styles.priceImpactRow, { backgroundColor: colors.background }]}>
              <Ionicons name="trending-down-outline" size={14} color={colors.muted} />
              <Text style={[styles.priceImpactText, { color: colors.muted }]}>
                {grade.priceImpact}
              </Text>
            </View>
          </View>
        ))}

        {/* Bottom spacing */}
        <View style={{ height: 100 }} />
      </ScrollView>

      <QuickNavBar />
    </SafeAreaView>
  );
}

export default function ConditionGuideScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Condition Guide">
      <ConditionGuideScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },

  // ---- Header ----
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  headerBackBtn: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
  },

  // ---- Scroll ----
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 20,
    gap: 12,
  },

  // ---- Category Selector ----
  categorySelector: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderRadius: 14,
    borderWidth: 1,
  },
  categorySelectorLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  categorySelectorLabel: {
    fontSize: 14,
    fontWeight: '500',
  },
  categorySelectorRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  categorySelectorValue: {
    fontSize: 15,
    fontWeight: '600',
  },

  // ---- Category Picker ----
  categoryPicker: {
    borderRadius: 14,
    borderWidth: 1,
    overflow: 'hidden',
    maxHeight: 240,
  },
  categoryPickerScroll: {
    maxHeight: 240,
  },
  categoryPickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 13,
  },
  categoryPickerItemText: {
    fontSize: 15,
    fontWeight: '400',
  },

  // ---- Intro ----
  introText: {
    fontSize: 14,
    fontWeight: '400',
    lineHeight: 20,
    marginBottom: 4,
  },

  // ---- Grade Card ----
  gradeCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    gap: 10,
  },
  gradeHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  gradeDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  gradeName: {
    fontSize: 17,
    fontWeight: '700',
    flex: 1,
  },
  gradeAbbrevBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  gradeAbbrevText: {
    fontSize: 13,
    fontWeight: '700',
  },
  gradeDescription: {
    fontSize: 14,
    fontWeight: '400',
    lineHeight: 21,
  },
  priceImpactRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
  },
  priceImpactText: {
    fontSize: 13,
    fontWeight: '500',
  },
});
