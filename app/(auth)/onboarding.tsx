/**
 * Onboarding — 4-slide welcome walkthrough for first-time users.
 * Slide 4 auto-detects the user's region via IP geolocation.
 */

import React, { useRef, useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  ScrollView,
  useWindowDimensions,
  StyleSheet,
  ViewToken,
  ActivityIndicator,
  TouchableOpacity,
  Modal,
  Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useToast } from '@/components/Toast';
import { useSettings, REGION_DEFAULTS } from '@/lib/settings';
import type { Region } from '@/lib/settings';
import { collectorsApi, logActivity } from '@/api/collectorsApi';
import { API_BASE } from '@/api/config';
import { supabase } from '@/lib/supabase';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { CATEGORY_VISUAL, type CategoryId } from '@/data/categories';
import { CATEGORIES as ALL_CATEGORIES } from '@/constants/categories';
import { track } from '@/analytics/track';

const TIFFANY = '#81D8D0';
const TIFFANY_DARK = '#5FBFB6';
const NAVY = '#0F172A';
const MUTED = '#64748B';

const ONBOARDING_KEY = '@collectai/onboarding_complete';

type Slide = {
  id: string;
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle: string;
};

const SLIDES: Slide[] = [
  {
    id: '1',
    icon: 'diamond-outline',
    title: 'Track Your Collection',
    subtitle: 'Organize all your collectibles in one place. Cards, figures, games — everything.',
  },
  {
    id: '2',
    icon: 'camera-outline',
    title: 'Snap a Photo, We Do the Rest',
    subtitle: 'Our AI identifies your items, suggests categories, and fills in the details automatically.',
  },
  {
    id: '3',
    icon: 'trending-up-outline',
    title: 'Know What It\'s Worth',
    subtitle: 'Get real-time valuations powered by marketplace data. Track your portfolio over time.',
  },
  {
    id: '4',
    icon: 'heart-outline',
    title: 'What Do You Collect?',
    subtitle: 'Pick your favorite categories so we can personalize your experience.',
  },
  {
    id: '5',
    icon: 'globe-outline',
    title: 'Set Your Region',
    subtitle: 'We\'ll show prices in your local currency and prioritize nearby marketplaces.',
  },
];

const REGION_OPTIONS: { value: Region; label: string }[] = [
  { value: 'americas', label: 'Americas' },
  { value: 'europe', label: 'Europe' },
  { value: 'japan', label: 'Japan' },
  { value: 'korea', label: 'South Korea' },
  { value: 'oceania', label: 'Australia / Oceania' },
  { value: 'other', label: 'Other' },
];

/** Animated scan demonstration for onboarding slide 2 */
function ScanAnimation() {
  const scanLineY = useRef(new Animated.Value(0)).current;
  const textOpacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Scan line moves up and down inside the viewfinder
    const lineAnim = Animated.loop(
      Animated.sequence([
        Animated.timing(scanLineY, {
          toValue: 1,
          duration: 1600,
          useNativeDriver: true,
        }),
        Animated.timing(scanLineY, {
          toValue: 0,
          duration: 1600,
          useNativeDriver: true,
        }),
      ]),
    );
    lineAnim.start();

    // Pulsing "Identifying..." text
    const textAnim = Animated.loop(
      Animated.sequence([
        Animated.timing(textOpacity, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        }),
        Animated.timing(textOpacity, {
          toValue: 0.2,
          duration: 1000,
          useNativeDriver: true,
        }),
      ]),
    );
    textAnim.start();

    return () => {
      lineAnim.stop();
      textAnim.stop();
    };
  }, [scanLineY, textOpacity]);

  // The viewfinder area is 60x60, so the scan line travels ~56px (with 2px padding)
  const VIEWFINDER_INNER = 56;
  const scanLineTranslate = scanLineY.interpolate({
    inputRange: [0, 1],
    outputRange: [0, VIEWFINDER_INNER],
  });

  return (
    <View style={scanStyles.container}>
      {/* Phone outline */}
      <View style={scanStyles.phoneOutline}>
        {/* Notch / speaker bar */}
        <View style={scanStyles.phoneSpeaker} />

        {/* Screen area */}
        <View style={scanStyles.phoneScreen}>
          {/* Viewfinder frame */}
          <View style={scanStyles.viewfinder}>
            {/* Corner brackets */}
            <View style={[scanStyles.vfCorner, scanStyles.vfCornerTL]} />
            <View style={[scanStyles.vfCorner, scanStyles.vfCornerTR]} />
            <View style={[scanStyles.vfCorner, scanStyles.vfCornerBL]} />
            <View style={[scanStyles.vfCorner, scanStyles.vfCornerBR]} />

            {/* Animated scan line */}
            <Animated.View
              style={[
                scanStyles.scanLine,
                { transform: [{ translateY: scanLineTranslate }] },
              ]}
            />
          </View>
        </View>

        {/* Home indicator bar */}
        <View style={scanStyles.phoneHomeBar} />
      </View>

      {/* Pulsing text */}
      <Animated.Text style={[scanStyles.identifyingText, { opacity: textOpacity }]}>
        Identifying...
      </Animated.Text>
    </View>
  );
}

const scanStyles = StyleSheet.create({
  container: {
    alignItems: 'center',
    marginBottom: 32,
  },
  phoneOutline: {
    width: 88,
    height: 140,
    borderRadius: 16,
    borderWidth: 3,
    borderColor: TIFFANY_DARK,
    backgroundColor: TIFFANY + '10',
    alignItems: 'center',
    paddingTop: 10,
    paddingBottom: 6,
  },
  phoneSpeaker: {
    width: 28,
    height: 4,
    borderRadius: 2,
    backgroundColor: TIFFANY_DARK + '60',
    marginBottom: 8,
  },
  phoneScreen: {
    flex: 1,
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  viewfinder: {
    width: 60,
    height: 60,
    position: 'relative',
  },
  vfCorner: {
    position: 'absolute',
    width: 14,
    height: 14,
    borderColor: TIFFANY_DARK,
  },
  vfCornerTL: {
    top: 0,
    left: 0,
    borderTopWidth: 2,
    borderLeftWidth: 2,
    borderTopLeftRadius: 4,
  },
  vfCornerTR: {
    top: 0,
    right: 0,
    borderTopWidth: 2,
    borderRightWidth: 2,
    borderTopRightRadius: 4,
  },
  vfCornerBL: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 2,
    borderLeftWidth: 2,
    borderBottomLeftRadius: 4,
  },
  vfCornerBR: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 2,
    borderRightWidth: 2,
    borderBottomRightRadius: 4,
  },
  scanLine: {
    position: 'absolute',
    top: 2,
    left: 4,
    right: 4,
    height: 2,
    backgroundColor: TIFFANY,
    borderRadius: 1,
  },
  phoneHomeBar: {
    width: 32,
    height: 4,
    borderRadius: 2,
    backgroundColor: TIFFANY_DARK + '40',
    marginTop: 4,
  },
  identifyingText: {
    marginTop: 14,
    fontSize: 14,
    fontWeight: '600',
    color: TIFFANY_DARK,
    letterSpacing: 0.3,
  },
});

function OnboardingScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const { settings, updateSettings } = useSettings();
  const [currentIndex, setCurrentIndex] = useState(0);
  const flatListRef = useRef<FlatList>(null);
  const [detectedRegion, setDetectedRegion] = useState<Region>('europe');
  const [detecting, setDetecting] = useState(false);
  const [regionPickerVisible, setRegionPickerVisible] = useState(false);
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
  const { showToast } = useToast();

  const toggleCategory = useCallback((catSlug: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(catSlug)) {
        next.delete(catSlug);
      } else {
        next.add(catSlug);
      }
      return next;
    });
  }, [settings.hapticsEnabled]);

  // Auto-detect region on mount
  useEffect(() => {
    let cancelled = false;
    setDetecting(true);
    collectorsApi.detectRegion()
      .then((data) => {
        if (!cancelled && data?.region) {
          const region = data.region as Region;
          setDetectedRegion(region);
        }
      })
      .catch(() => {
        // Fallback to europe
      })
      .finally(() => {
        if (!cancelled) setDetecting(false);
      });
    return () => { cancelled = true; };
  }, []);

  const confirmRegion = useCallback(async (region: Region) => {
    const defaults = REGION_DEFAULTS[region];
    updateSettings({ region, currency: defaults.currency, numberLocale: defaults.numberLocale });
    // Persist to backend (best-effort)
    try {
      const auth = await supabase.auth.getSession();
      if (auth.data?.session) {
        await fetch(`${API_BASE}/settings`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${auth.data.session.access_token}`,
          },
          body: JSON.stringify({ region, currency: defaults.currency, locale: defaults.numberLocale }),
        });
      }
    } catch {}
  }, [updateSettings]);

  const onViewableItemsChanged = useRef(
    ({ viewableItems }: { viewableItems: ViewToken[] }) => {
      if (viewableItems.length > 0 && viewableItems[0].index != null) {
        const idx = viewableItems[0].index;
        setCurrentIndex(idx);
        track({ name: 'onboarding_slide_viewed', properties: { slide: idx } });
      }
    },
  ).current;

  const viewabilityConfig = useRef({ viewAreaCoveragePercentThreshold: 50 }).current;

  async function completeOnboarding() {
    if (!ageConfirmed) {
      showToast({ message: 'You must confirm your age to continue.', type: 'warning' });
      return;
    }
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    await confirmRegion(detectedRegion);

    // Save followed categories (best-effort)
    if (selectedCategories.size > 0) {
      try {
        await collectorsApi.saveFollowedCategories(Array.from(selectedCategories));
      } catch {
        // Non-blocking — categories will be empty on first load
      }
      // Also persist locally for immediate use
      await AsyncStorage.setItem('@collectai/followed_categories', JSON.stringify(Array.from(selectedCategories)));
    }

    await AsyncStorage.setItem(ONBOARDING_KEY, 'true');
    track({ name: 'onboarding_completed', properties: { categories_selected: selectedCategories.size } });

    // Best-effort XP award for completing onboarding
    logActivity({
      activity_type: 'onboarding_completed',
      title: 'Completed onboarding',
      metadata: { categories_selected: selectedCategories.size },
    }).catch(() => {});

    router.replace('/(tabs)/add');
  }

  function handleNext() {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    if (currentIndex < SLIDES.length - 1) {
      flatListRef.current?.scrollToIndex({ index: currentIndex + 1 });
    } else {
      completeOnboarding();
    }
  }

  const isLast = currentIndex === SLIDES.length - 1;
  const isCategorySlide = currentIndex === 3;
  const isRegionSlide = currentIndex === 4;
  // Show skip only on intro slides (0-2), not on category/region slides that need user input
  const showSkip = currentIndex <= 2;

  const handleSkip = useCallback(() => {
    track({ name: 'onboarding_skipped', properties: { skip_slide: currentIndex } });
    // Jump directly to the category selection slide so users still pick categories + region
    flatListRef.current?.scrollToIndex({ index: 3 });
  }, [currentIndex]);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        {showSkip && (
          <AnimatedPressable
            onPress={handleSkip}
            style={styles.skipBtn}
            accessibilityRole="button"
            accessibilityLabel="Skip to category selection"
          >
            <Text style={styles.skipText}>Skip</Text>
          </AnimatedPressable>
        )}
      </View>

      <FlatList
        ref={flatListRef}
        data={SLIDES}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        keyExtractor={(item) => item.id}
        onViewableItemsChanged={onViewableItemsChanged}
        viewabilityConfig={viewabilityConfig}
        renderItem={({ item, index }) => (
          <View style={[styles.slide, { width }]}>
            {index === 1 ? (
              <ScanAnimation />
            ) : (
              <View style={styles.iconCircle}>
                <Ionicons name={item.icon} size={48} color={TIFFANY_DARK} />
              </View>
            )}
            <Text style={styles.slideTitle}>{item.title}</Text>
            <Text style={styles.slideSubtitle}>{item.subtitle}</Text>

            {/* Category picker on slide 4 (index 3) */}
            {index === 3 && (
              <ScrollView
                style={styles.categoryScrollView}
                contentContainerStyle={styles.categoryGrid}
                showsVerticalScrollIndicator={false}
                nestedScrollEnabled
              >
                {ALL_CATEGORIES.map((cat) => {
                  const visual = CATEGORY_VISUAL[cat.slug as CategoryId];
                  const isSelected = selectedCategories.has(cat.slug);
                  return (
                    <TouchableOpacity
                      key={cat.slug}
                      onPress={() => toggleCategory(cat.slug)}
                      activeOpacity={0.7}
                      style={[
                        styles.categoryPill,
                        {
                          borderColor: isSelected ? (visual?.accentColor || TIFFANY) : '#E2E8F0',
                          backgroundColor: isSelected ? (visual?.accentColor || TIFFANY) + '20' : '#F8FAFC',
                        },
                      ]}
                      accessibilityRole="checkbox"
                      accessibilityState={{ checked: isSelected }}
                      accessibilityLabel={`${cat.name}${isSelected ? ', selected' : ''}`}
                    >
                      <Ionicons
                        name={(visual?.iconName || 'cube-outline') as keyof typeof Ionicons.glyphMap}
                        size={16}
                        color={isSelected ? (visual?.accentColor || TIFFANY) : MUTED}
                      />
                      <Text
                        style={[
                          styles.categoryPillText,
                          { color: isSelected ? (visual?.accentColor || TIFFANY_DARK) : NAVY },
                        ]}
                        numberOfLines={1}
                      >
                        {cat.name}
                      </Text>
                      {isSelected && (
                        <Ionicons name="checkmark-circle" size={14} color={visual?.accentColor || TIFFANY} />
                      )}
                    </TouchableOpacity>
                  );
                })}
                {selectedCategories.size > 0 && (
                  <Text style={styles.categoryCountText}>
                    {selectedCategories.size} selected
                  </Text>
                )}
              </ScrollView>
            )}

            {/* Region detection UI on slide 5 (index 4) */}
            {index === 4 && (
              <View style={styles.regionContainer}>
                {detecting ? (
                  <ActivityIndicator size="small" color={TIFFANY} style={{ marginTop: 24 }} />
                ) : (
                  <>
                    <View style={styles.detectedRegionBox}>
                      <Ionicons name="location-outline" size={20} color={TIFFANY_DARK} />
                      <Text style={styles.detectedRegionText}>
                        {REGION_OPTIONS.find((r) => r.value === detectedRegion)?.label ?? 'Europe'}
                      </Text>
                    </View>
                    <TouchableOpacity
                      onPress={() => setRegionPickerVisible(true)}
                      style={styles.changeRegionBtn}
                      accessibilityRole="button"
                      accessibilityLabel="Change region"
                    >
                      <Text style={styles.changeRegionText}>Change</Text>
                    </TouchableOpacity>
                  </>
                )}

                {/* Age confirmation */}
                <TouchableOpacity
                  style={styles.ageRow}
                  onPress={() => setAgeConfirmed(!ageConfirmed)}
                  activeOpacity={0.7}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: ageConfirmed }}
                  accessibilityLabel="Confirm age requirement"
                >
                  <View style={[styles.ageCheckbox, ageConfirmed && styles.ageCheckboxChecked]}>
                    {ageConfirmed && <Ionicons name="checkmark" size={14} color="#FFFFFF" />}
                  </View>
                  <Text style={styles.ageText}>
                    I confirm I am at least 13 years old (16 in the EU)
                  </Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        )}
      />

      {/* Dots */}
      <View style={styles.dots}>
        {SLIDES.map((_, i) => (
          <View
            key={i}
            style={[
              styles.dot,
              i === currentIndex && styles.dotActive,
            ]}
          />
        ))}
      </View>

      {/* Action */}
      <View style={styles.actionContainer}>
        <AnimatedPressable
          style={styles.nextBtn}
          onPress={handleNext}
          accessibilityRole="button"
          accessibilityLabel={isLast ? 'Get Started' : 'Next'}
        >
          <Text style={styles.nextBtnText}>
            {isLast ? 'Get Started' : 'Next'}
          </Text>
          {!isLast && <Ionicons name="arrow-forward" size={18} color="#FFFFFF" />}
        </AnimatedPressable>
      </View>

      {/* Region Picker Modal */}
      <Modal
        visible={regionPickerVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setRegionPickerVisible(false)}
      >
        <SafeAreaView style={styles.regionPickerModal}>
          <View style={styles.regionPickerHeader}>
            <TouchableOpacity onPress={() => setRegionPickerVisible(false)}>
              <Ionicons name="close" size={24} color={NAVY} />
            </TouchableOpacity>
            <Text style={styles.regionPickerTitle}>Select Region</Text>
            <View style={{ width: 24 }} />
          </View>
          {REGION_OPTIONS.map((opt) => (
            <TouchableOpacity
              key={opt.value}
              style={[
                styles.regionPickerRow,
                opt.value === detectedRegion && styles.regionPickerRowActive,
              ]}
              onPress={() => {
                setDetectedRegion(opt.value);
                setRegionPickerVisible(false);
              }}
              accessibilityRole="radio"
              accessibilityState={{ selected: opt.value === detectedRegion }}
            >
              <Text style={styles.regionPickerRowText}>{opt.label}</Text>
              {opt.value === detectedRegion && (
                <Ionicons name="checkmark" size={20} color={TIFFANY_DARK} />
              )}
            </TouchableOpacity>
          ))}
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

export default function OnboardingScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Onboarding">
      <OnboardingScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingHorizontal: 20,
    paddingTop: 8,
    minHeight: 44,
  },
  skipBtn: {
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  skipText: {
    fontSize: 15,
    color: MUTED,
    fontWeight: '600',
  },
  slide: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  iconCircle: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: TIFFANY + '20',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 32,
  },
  slideTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: NAVY,
    textAlign: 'center',
    marginBottom: 12,
  },
  slideSubtitle: {
    fontSize: 16,
    color: MUTED,
    textAlign: 'center',
    lineHeight: 24,
  },
  dots: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 20,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#E2E8F0',
  },
  dotActive: {
    backgroundColor: TIFFANY,
    width: 24,
  },
  actionContainer: {
    paddingHorizontal: 24,
    paddingBottom: 24,
  },
  nextBtn: {
    backgroundColor: TIFFANY,
    borderRadius: 12,
    paddingVertical: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  nextBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  regionContainer: {
    marginTop: 32,
    alignItems: 'center',
    gap: 12,
  },
  detectedRegionBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: TIFFANY + '20',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
  },
  detectedRegionText: {
    fontSize: 18,
    fontWeight: '700',
    color: NAVY,
  },
  changeRegionBtn: {
    paddingVertical: 6,
    paddingHorizontal: 16,
  },
  changeRegionText: {
    fontSize: 14,
    fontWeight: '600',
    color: TIFFANY_DARK,
  },
  regionPickerModal: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  regionPickerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#E2E8F0',
  },
  regionPickerTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: NAVY,
  },
  regionPickerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#E2E8F0',
  },
  regionPickerRowActive: {
    backgroundColor: TIFFANY + '15',
  },
  regionPickerRowText: {
    fontSize: 16,
    fontWeight: '500',
    color: NAVY,
  },
  ageRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginTop: 20,
    paddingHorizontal: 4,
  },
  ageCheckbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#E2E8F0',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  ageCheckboxChecked: {
    backgroundColor: TIFFANY,
    borderColor: TIFFANY,
  },
  ageText: {
    flex: 1,
    fontSize: 13,
    color: MUTED,
    lineHeight: 20,
  },
  // Category grid styles
  categoryScrollView: {
    marginTop: 20,
    maxHeight: 260,
    width: '100%',
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 8,
    paddingHorizontal: 4,
    paddingBottom: 8,
  },
  categoryPill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1.5,
    gap: 6,
  },
  categoryPillText: {
    fontSize: 13,
    fontWeight: '600',
    maxWidth: 100,
  },
  categoryCountText: {
    width: '100%',
    textAlign: 'center',
    fontSize: 13,
    color: TIFFANY_DARK,
    fontWeight: '600',
    marginTop: 4,
  },
});
