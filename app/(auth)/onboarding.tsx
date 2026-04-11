/**
 * Onboarding — 5-slide welcome walkthrough for first-time users.
 * Pro-grade: gradient bg, animated dots, slide reveals, category stagger, gradient button.
 */

import React, { useRef, useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  ScrollView,
  Image,
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
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AnimatedPressable } from '@/motion';
import { useStaggerReveal } from '@/motion/useStaggerReveal';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useToast } from '@/components/Toast';
import { useSettings, REGION_DEFAULTS } from '@/lib/settings';
import type { Region } from '@/lib/settings';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@/hooks/useAppTheme';
import { collectorsApi, logActivity } from '@/api/collectorsApi';
import { API_BASE } from '@/api/config';
import { supabase } from '@/lib/supabase';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { CATEGORY_VISUAL, type CategoryId } from '@/data/categories';
import { CATEGORIES as ALL_CATEGORIES } from '@/constants/categories';
import { track } from '@/analytics/track';
import { GradientBackground } from '@/components/auth/GradientBackground';
import { fonts } from '@/theme/tokens';

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
function ScanAnimation({ colors }: { colors: ReturnType<typeof useAppTheme>['colors'] }) {
  const scanLineY = useRef(new Animated.Value(0)).current;
  const textOpacity = useRef(new Animated.Value(0)).current;
  const checkOpacity = useRef(new Animated.Value(0)).current;
  const loopCount = useRef(0);

  useEffect(() => {
    const runScanLoop = () => {
      loopCount.current++;
      const showCheck = loopCount.current % 3 === 0; // checkmark after every 2 loops

      Animated.sequence([
        Animated.timing(scanLineY, { toValue: 1, duration: 1600, useNativeDriver: true }),
        Animated.timing(scanLineY, { toValue: 0, duration: 1600, useNativeDriver: true }),
        ...(showCheck
          ? [
              Animated.timing(checkOpacity, { toValue: 1, duration: 300, useNativeDriver: true }),
              Animated.delay(600),
              Animated.timing(checkOpacity, { toValue: 0, duration: 300, useNativeDriver: true }),
            ]
          : []),
      ]).start(() => runScanLoop());
    };

    runScanLoop();

    const textAnim = Animated.loop(
      Animated.sequence([
        Animated.timing(textOpacity, { toValue: 1, duration: 1000, useNativeDriver: true }),
        Animated.timing(textOpacity, { toValue: 0.2, duration: 1000, useNativeDriver: true }),
      ]),
    );
    textAnim.start();

    return () => {
      textAnim.stop();
    };
  }, []);

  const VIEWFINDER_INNER = 56;
  const scanLineTranslate = scanLineY.interpolate({
    inputRange: [0, 1],
    outputRange: [0, VIEWFINDER_INNER],
  });

  return (
    <View style={scanStyles.container}>
      <View style={[scanStyles.phoneOutline, { borderColor: colors.brand.dark, backgroundColor: colors.brand.base + '10' }]}>
        <View style={[scanStyles.phoneSpeaker, { backgroundColor: colors.brand.dark + '60' }]} />
        <View style={scanStyles.phoneScreen}>
          <View style={scanStyles.viewfinder}>
            <View style={[scanStyles.vfCorner, scanStyles.vfCornerTL, { borderColor: colors.brand.dark }]} />
            <View style={[scanStyles.vfCorner, scanStyles.vfCornerTR, { borderColor: colors.brand.dark }]} />
            <View style={[scanStyles.vfCorner, scanStyles.vfCornerBL, { borderColor: colors.brand.dark }]} />
            <View style={[scanStyles.vfCorner, scanStyles.vfCornerBR, { borderColor: colors.brand.dark }]} />
            <Animated.View
              style={[
                scanStyles.scanLine,
                {
                  backgroundColor: colors.brand.base,
                  height: 4,
                  shadowColor: colors.brand.base,
                  shadowOpacity: 0.6,
                  shadowRadius: 6,
                  shadowOffset: { width: 0, height: 0 },
                  transform: [{ translateY: scanLineTranslate }],
                },
              ]}
            />
            {/* Brief checkmark overlay */}
            <Animated.View style={[scanStyles.checkOverlay, { opacity: checkOpacity }]}>
              <Ionicons name="checkmark-circle" size={28} color={colors.success} />
            </Animated.View>
          </View>
        </View>
        <View style={[scanStyles.phoneHomeBar, { backgroundColor: colors.brand.dark + '40' }]} />
      </View>
      <Animated.Text style={[scanStyles.identifyingText, { opacity: textOpacity, color: colors.brand.dark }]}>
        Identifying...
      </Animated.Text>
    </View>
  );
}

const scanStyles = StyleSheet.create({
  container: { alignItems: 'center', marginBottom: 32 },
  phoneOutline: {
    width: 88, height: 140, borderRadius: 16, borderWidth: 3,
    alignItems: 'center', paddingTop: 10, paddingBottom: 6,
  },
  phoneSpeaker: { width: 28, height: 4, borderRadius: 2, marginBottom: 8 },
  phoneScreen: { flex: 1, width: '100%', alignItems: 'center', justifyContent: 'center' },
  viewfinder: { width: 60, height: 60, position: 'relative' },
  vfCorner: { position: 'absolute', width: 14, height: 14 },
  vfCornerTL: { top: 0, left: 0, borderTopWidth: 2, borderLeftWidth: 2, borderTopLeftRadius: 4 },
  vfCornerTR: { top: 0, right: 0, borderTopWidth: 2, borderRightWidth: 2, borderTopRightRadius: 4 },
  vfCornerBL: { bottom: 0, left: 0, borderBottomWidth: 2, borderLeftWidth: 2, borderBottomLeftRadius: 4 },
  vfCornerBR: { bottom: 0, right: 0, borderBottomWidth: 2, borderRightWidth: 2, borderBottomRightRadius: 4 },
  scanLine: { position: 'absolute', top: 2, left: 4, right: 4, borderRadius: 2 },
  checkOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
  },
  phoneHomeBar: { width: 32, height: 4, borderRadius: 2, marginTop: 4 },
  identifyingText: { marginTop: 14, fontSize: 14, fontWeight: '600', letterSpacing: 0.3 },
});

function OnboardingScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const { settings, updateSettings } = useSettings();
  const { t } = useTranslation();
  const { colors, isDark } = useAppTheme();
  const [currentIndex, setCurrentIndex] = useState(0);
  const flatListRef = useRef<FlatList>(null);
  const [detectedRegion, setDetectedRegion] = useState<Region>('europe');
  const [detecting, setDetecting] = useState(false);
  const [regionPickerVisible, setRegionPickerVisible] = useState(false);
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
  const { showToast } = useToast();

  // Animated dot widths (5 dots)
  const dotWidths = useRef(SLIDES.map((_, i) => new Animated.Value(i === 0 ? 24 : 8))).current;

  // Stagger for category pills (first 20)
  const { getItemStyle: getCategoryStyle } = useStaggerReveal({
    count: 20,
    staggerMs: 30,
    autoStart: false,
  });
  const categoryRevealTriggered = useRef(false);

  // Icon bounce animation
  const iconScale = useRef(new Animated.Value(0.5)).current;

  useEffect(() => {
    Animated.spring(iconScale, {
      toValue: 1,
      friction: 5,
      tension: 50,
      useNativeDriver: true,
    }).start();
  }, []);

  const toggleCategory = useCallback((catSlug: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(catSlug)) next.delete(catSlug);
      else next.add(catSlug);
      return next;
    });
  }, [settings.hapticsEnabled]);

  useEffect(() => {
    let cancelled = false;
    setDetecting(true);
    collectorsApi.detectRegion()
      .then((data) => {
        if (!cancelled && data?.region) setDetectedRegion(data.region as Region);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setDetecting(false); });
    return () => { cancelled = true; };
  }, []);

  const confirmRegion = useCallback(async (region: Region) => {
    const defaults = REGION_DEFAULTS[region];
    updateSettings({ region, currency: defaults.currency, numberLocale: defaults.numberLocale });
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

        // Animate dot widths
        dotWidths.forEach((dw, i) => {
          Animated.spring(dw, {
            toValue: i === idx ? 24 : 8,
            friction: 8,
            tension: 80,
            useNativeDriver: false,
          }).start();
        });

        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: true });
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

    if (selectedCategories.size > 0) {
      try {
        await collectorsApi.saveFollowedCategories(Array.from(selectedCategories));
      } catch {}
      await AsyncStorage.setItem('@collectai/followed_categories', JSON.stringify(Array.from(selectedCategories)));
    }

    await AsyncStorage.setItem(ONBOARDING_KEY, 'true');
    track({ name: 'onboarding_completed', properties: { categories_selected: selectedCategories.size } });

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
  const showSkip = currentIndex <= 2;

  const handleSkip = useCallback(() => {
    track({ name: 'onboarding_skipped', properties: { skip_slide: currentIndex } });
    flatListRef.current?.scrollToIndex({ index: 3 });
  }, [currentIndex]);

  // Slide text entrance animations
  const slideOpacities = useRef(SLIDES.map(() => new Animated.Value(0))).current;
  const slideTranslates = useRef(SLIDES.map(() => new Animated.Value(20))).current;

  useEffect(() => {
    // Animate current slide text
    Animated.parallel([
      Animated.timing(slideOpacities[currentIndex], { toValue: 1, duration: 300, useNativeDriver: true }),
      Animated.timing(slideTranslates[currentIndex], { toValue: 0, duration: 300, useNativeDriver: true }),
    ]).start();

    // Trigger category stagger on slide 4
    if (currentIndex === 3 && !categoryRevealTriggered.current) {
      categoryRevealTriggered.current = true;
    }
  }, [currentIndex]);

  return (
    <GradientBackground>
      <SafeAreaView style={styles.safe}>
        <View style={styles.header}>
          {showSkip && (
            <AnimatedPressable
              onPress={handleSkip}
              style={styles.skipBtn}
              accessibilityRole="button"
              accessibilityLabel={t('onboarding.skip_a11y')}
            >
              <Text style={[styles.skipText, { color: colors.muted }]}>Skip</Text>
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
                <ScanAnimation colors={colors} />
              ) : (
                <Animated.View
                  style={[
                    styles.iconCircle,
                    {
                      backgroundColor: colors.brand.base + '20',
                      transform: [{ scale: index === currentIndex ? iconScale : 1 }],
                    },
                  ]}
                >
                  {/* Gradient ring */}
                  <View style={[styles.iconRing, { borderColor: colors.brand.base + '40' }]}>
                    {item.icon === 'diamond-outline' ? (
                      <Image source={require('../../assets/images/logo.png')} style={{ width: 64, height: 64 }} resizeMode="contain" />
                    ) : (
                      <Ionicons name={item.icon} size={48} color={colors.brand.dark} />
                    )}
                  </View>
                </Animated.View>
              )}

              <Animated.View
                style={{
                  opacity: slideOpacities[index],
                  transform: [{ translateY: slideTranslates[index] }],
                  alignItems: 'center',
                }}
              >
                <Text style={[styles.slideTitle, { color: colors.text, fontFamily: fonts.bold }]}>
                  {item.title}
                </Text>
                <Text style={[styles.slideSubtitle, { color: colors.muted }]}>
                  {item.subtitle}
                </Text>
              </Animated.View>

              {/* Category picker on slide 4 (index 3) */}
              {index === 3 && (
                <ScrollView
                  style={styles.categoryScrollView}
                  contentContainerStyle={styles.categoryGrid}
                  showsVerticalScrollIndicator={false}
                  nestedScrollEnabled
                >
                  {ALL_CATEGORIES.map((cat, catIdx) => {
                    const visual = CATEGORY_VISUAL[cat.slug as CategoryId];
                    const isSelected = selectedCategories.has(cat.slug);
                    const pillStyle = getCategoryStyle(catIdx);
                    return (
                      <AnimatedPressable
                        key={cat.slug}
                        onPress={() => toggleCategory(cat.slug)}
                        style={[
                          styles.categoryPill,
                          {
                            borderColor: isSelected ? (visual?.accentColor || colors.brand.base) : colors.border,
                            backgroundColor: isSelected
                              ? (visual?.accentColor || colors.brand.base) + '20'
                              : colors.card,
                          },
                          pillStyle,
                        ]}
                        accessibilityRole="checkbox"
                        accessibilityState={{ checked: isSelected }}
                        accessibilityLabel={`${cat.name}${isSelected ? ', selected' : ''}`}
                      >
                        <Ionicons
                          name={(visual?.iconName || 'cube-outline') as keyof typeof Ionicons.glyphMap}
                          size={16}
                          color={isSelected ? (visual?.accentColor || colors.brand.base) : colors.muted}
                        />
                        <Text
                          style={[
                            styles.categoryPillText,
                            { color: isSelected ? (visual?.accentColor || colors.brand.dark) : colors.text },
                          ]}
                          numberOfLines={1}
                        >
                          {cat.name}
                        </Text>
                        {isSelected && (
                          <Ionicons name="checkmark-circle" size={14} color={visual?.accentColor || colors.brand.base} />
                        )}
                      </AnimatedPressable>
                    );
                  })}
                  {selectedCategories.size > 0 && (
                    <Text style={[styles.categoryCountText, { color: colors.brand.dark }]}>
                      {selectedCategories.size} selected
                    </Text>
                  )}
                </ScrollView>
              )}

              {/* Region detection UI on slide 5 (index 4) */}
              {index === 4 && (
                <View style={styles.regionContainer}>
                  {detecting ? (
                    <ActivityIndicator size="small" color={colors.brand.base} style={{ marginTop: 24 }} />
                  ) : (
                    <>
                      <View style={[styles.detectedRegionBox, { backgroundColor: colors.brand.base + '20' }]}>
                        <Ionicons name="location-outline" size={20} color={colors.brand.dark} />
                        <Text style={[styles.detectedRegionText, { color: colors.text }]}>
                          {REGION_OPTIONS.find((r) => r.value === detectedRegion)?.label ?? 'Europe'}
                        </Text>
                      </View>
                      <TouchableOpacity
                        onPress={() => setRegionPickerVisible(true)}
                        style={styles.changeRegionBtn}
                        accessibilityRole="button"
                        accessibilityLabel={t('onboarding.change_region_a11y')}
                      >
                        <Text style={[styles.changeRegionText, { color: colors.brand.dark }]}>Change</Text>
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
                    accessibilityLabel={t('onboarding.confirm_age_a11y')}
                  >
                    <View
                      style={[
                        styles.ageCheckbox,
                        {
                          borderColor: ageConfirmed ? colors.brand.base : colors.border,
                          backgroundColor: ageConfirmed ? colors.brand.base : 'transparent',
                        },
                      ]}
                    >
                      {ageConfirmed && <Ionicons name="checkmark" size={14} color="#FFFFFF" />}
                    </View>
                    <Text style={[styles.ageText, { color: colors.muted }]}>
                      I confirm I am at least 13 years old (16 in the EU)
                    </Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          )}
        />

        {/* Animated Dots */}
        <View style={styles.dots}>
          {SLIDES.map((_, i) => (
            <Animated.View
              key={i}
              style={[
                styles.dot,
                {
                  width: dotWidths[i],
                  backgroundColor: i === currentIndex ? colors.brand.base : colors.border,
                },
              ]}
            />
          ))}
        </View>

        {/* Action */}
        <View style={styles.actionContainer}>
          <AnimatedPressable
            style={styles.gradientBtnWrap}
            onPress={handleNext}
            accessibilityRole="button"
            accessibilityLabel={isLast ? 'Get Started' : 'Next'}
          >
            <LinearGradient
              colors={[colors.brand.dark, colors.brand.base]}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={styles.gradientBtn}
            >
              <Text style={styles.gradientBtnText}>
                {isLast ? 'Get Started' : 'Next'}
              </Text>
              {!isLast && <Ionicons name="arrow-forward" size={18} color="#FFFFFF" />}
            </LinearGradient>
          </AnimatedPressable>
        </View>

        {/* Region Picker Modal */}
        <Modal
          visible={regionPickerVisible}
          animationType="slide"
          presentationStyle="pageSheet"
          onRequestClose={() => setRegionPickerVisible(false)}
        >
          <SafeAreaView style={[styles.regionPickerModal, { backgroundColor: colors.background }]}>
            <View style={[styles.regionPickerHeader, { borderBottomColor: colors.border }]}>
              <TouchableOpacity onPress={() => setRegionPickerVisible(false)}>
                <Ionicons name="close" size={24} color={colors.text} />
              </TouchableOpacity>
              <Text style={[styles.regionPickerTitle, { color: colors.text }]}>{t('onboarding.select_region')}</Text>
              <View style={{ width: 24 }} />
            </View>
            {REGION_OPTIONS.map((opt) => (
              <TouchableOpacity
                key={opt.value}
                style={[
                  styles.regionPickerRow,
                  { borderBottomColor: colors.border },
                  opt.value === detectedRegion && { backgroundColor: colors.brand.base + '15' },
                ]}
                onPress={() => {
                  setDetectedRegion(opt.value);
                  setRegionPickerVisible(false);
                }}
                accessibilityRole="radio"
                accessibilityState={{ selected: opt.value === detectedRegion }}
              >
                <Text style={[styles.regionPickerRowText, { color: colors.text }]}>{opt.label}</Text>
                {opt.value === detectedRegion && (
                  <Ionicons name="checkmark" size={20} color={colors.brand.dark} />
                )}
              </TouchableOpacity>
            ))}
          </SafeAreaView>
        </Modal>
      </SafeAreaView>
    </GradientBackground>
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
    fontWeight: '600',
  },
  slide: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  iconCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 32,
  },
  iconRing: {
    width: 120,
    height: 120,
    borderRadius: 60,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  slideTitle: {
    fontSize: 24,
    fontWeight: '800',
    textAlign: 'center',
    marginBottom: 12,
  },
  slideSubtitle: {
    fontSize: 16,
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
    height: 8,
    borderRadius: 4,
  },
  actionContainer: {
    paddingHorizontal: 24,
    paddingBottom: 24,
  },
  gradientBtnWrap: {
    borderRadius: 16,
    shadowColor: '#44A9A1',
    shadowOpacity: 0.3,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  gradientBtn: {
    borderRadius: 16,
    paddingVertical: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    minHeight: 54,
  },
  gradientBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontFamily: fonts.bold,
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
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
  },
  detectedRegionText: {
    fontSize: 18,
    fontWeight: '700',
  },
  changeRegionBtn: {
    paddingVertical: 6,
    paddingHorizontal: 16,
  },
  changeRegionText: {
    fontSize: 14,
    fontWeight: '600',
  },
  regionPickerModal: {
    flex: 1,
  },
  regionPickerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  regionPickerTitle: {
    fontSize: 17,
    fontWeight: '700',
  },
  regionPickerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  regionPickerRowText: {
    fontSize: 16,
    fontWeight: '500',
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
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  ageText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 20,
  },
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
    fontWeight: '600',
    marginTop: 4,
  },
});
