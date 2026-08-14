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
import { useSettings, REGION_DEFAULTS, type Region, type SkillLevel } from '@/lib/settings';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@/hooks/useAppTheme';
import { collectorsApi, logActivity } from '@/api/collectorsApi';
import { updateUserSettings, saveFollowedCategories } from '@/api/settingsApi';
import { supabase } from '@/lib/supabase';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { CATEGORY_VISUAL, type CategoryId } from '@/data/categories';
import { CATEGORIES as ALL_CATEGORIES } from '@/constants/categories';
import { track } from '@/analytics/track';
import { GradientBackground } from '@/components/auth/GradientBackground';
import { fonts } from '@/theme/tokens';
import { logger } from '@/lib/logger';

const ONBOARDING_KEY = '@sparrowcollect/onboarding_complete';

type Slide = {
  id: string;
  /**
   * What this slide IS, so the renderer never keys off position.
   *
   * The region block used to render on `index === 3`, with a comment warning
   * that "dropping a slide above it silently shifts every index below" — which
   * is exactly what adding the categories and skill steps would have done. An
   * identity cannot shift.
   */
  kind: 'value' | 'scan' | 'categories' | 'skill' | 'region';
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle: string;
};

const SLIDES: Slide[] = [
  {
    id: '1',
    kind: 'value',
    icon: 'diamond-outline',
    title: 'Track Your Collection',
    subtitle: 'Organize all your collectibles in one place. Cards, figures, games — everything.',
  },
  {
    id: '2',
    kind: 'scan',
    icon: 'camera-outline',
    title: 'Snap a Photo, We Do the Rest',
    subtitle: 'Our AI identifies your items, suggests categories, and fills in the details automatically.',
  },
  {
    id: '3',
    kind: 'value',
    icon: 'trending-up-outline',
    title: 'Know What It\'s Worth',
    subtitle: 'Get real-time valuations powered by marketplace data. Track your portfolio over time.',
  },
  {
    // Restored 2026-08-14. The picker was removed on 2026-08-11, which left
    // NOTHING seeding followed categories at signup — the preference was still
    // read by quickscan, market movers, events and purchase, so every new
    // member started unpersonalised and those five features had no signal to
    // work with.
    id: '4',
    kind: 'categories',
    icon: 'heart-outline',
    title: 'What Do You Collect?',
    subtitle: 'Pick a few. We put these first in search, events and scanning — you can change them any time.',
  },
  {
    id: '5',
    kind: 'skill',
    icon: 'school-outline',
    title: 'How Long Have You Been Collecting?',
    subtitle: 'This only changes what we show you first. Nothing is locked behind it.',
  },
  {
    // Was id '5'; renumbered when the category and skill steps landed. Its
    // renderer keys off `kind`, not this position.
    id: '6',
    kind: 'region',
    icon: 'globe-outline',
    title: 'Set Your Region',
    subtitle: 'We\'ll show prices in your local currency and prioritize nearby marketplaces.',
  },
];

/** Copy is deliberately about TIME SPENT, not self-assessed expertise: people
 *  under-rate themselves when asked how good they are, and the app only needs
 *  to know whether to offer the basics. */
const SKILL_OPTIONS: {
  value: SkillLevel;
  label: string;
  blurb: string;
  icon: keyof typeof Ionicons.glyphMap;
}[] = [
  { value: 'beginner', label: 'Just starting', blurb: 'New to this — show me how it works', icon: 'leaf-outline' },
  { value: 'intermediate', label: 'A while now', blurb: 'I know the basics, still learning the market', icon: 'trending-up-outline' },
  { value: 'advanced', label: 'Years of it', blurb: 'I know what I am doing — skip the basics', icon: 'ribbon-outline' },
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
  // Both steps are OPTIONAL. Skipping leaves followed categories empty and
  // skill level null, which is exactly the state every member was in before
  // these steps existed — no feature depends on an answer.
  const [pickedCategories, setPickedCategories] = useState<Set<string>>(new Set());
  const [pickedSkill, setPickedSkill] = useState<SkillLevel | null>(null);
  const { showToast } = useToast();

  // Animated dot widths, one per slide (derived, so adding a slide adds a dot)
  const dotWidths = useRef(SLIDES.map((_, i) => new Animated.Value(i === 0 ? 24 : 8))).current;

  // Stagger for category pills (first 20)
  const { getItemStyle: getCategoryStyle, reveal: startCategoryReveal } = useStaggerReveal({
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

  /**
   * Persist the two optional answers. Local FIRST, server fire-and-forget.
   *
   * That order is the scar on this screen: the completion handler used to sync
   * before writing its local flag, so one hung request meant the flag never
   * landed and the gate looped new users back into onboarding forever
   * (reported 2026-06-11). Anything here that can hang must not sit between
   * the user tapping and the app letting them in.
   */
  const persistPicks = useCallback(() => {
    if (pickedSkill) {
      // Local write is synchronous and is what every reader uses.
      updateSettings({ skillLevel: pickedSkill });
      // Typed as SkillLevel, so the value cannot drift from VALID_SKILL_LEVELS
      // and the CHECK behind it — the currency/region/locale 23514 story.
      updateUserSettings({ skill_level: pickedSkill }).catch((e) =>
        logger.error('[onboarding] skill level persist failed:', e),
      );
    }
    if (pickedCategories.size > 0) {
      // saveFollowedCategories diffs against the server's current set and
      // converges; it is NOT part of PUT /settings, which silently dropped
      // `followed_categories` and is why the old picker saved nothing.
      saveFollowedCategories(Array.from(pickedCategories)).catch((e) =>
        logger.error('[onboarding] followed categories persist failed:', e),
      );
    }
  }, [pickedSkill, pickedCategories, updateSettings]);

  const confirmRegion = useCallback(async (region: Region) => {
    const defaults = REGION_DEFAULTS[region];
    updateSettings({ region, currency: defaults.currency, numberLocale: defaults.numberLocale });
    try {
      const auth = await supabase.auth.getSession();
      if (auth.data?.session) {
        // Via settingsApi (not a raw fetch): `put` throws on a non-2xx, so this
        // catch actually fires. The hand-rolled fetch here never read res.ok,
        // and fetch resolves on 5xx — so a rejected region/currency/locale was
        // applied locally and silently lost server-side.
        await updateUserSettings({
          region,
          currency: defaults.currency,
          locale: defaults.numberLocale,
        });
      }
    } catch (e) {
      logger.error('[onboarding] region persist failed:', e);
    }
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
    // Age confirmation moved to a point-of-sale gate (2026-05-18 rework) —
    // App Store Age Rating covers the consumer/collection use case.
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });

    // Persist completion + picks LOCALLY first, before any network call. The
    // server syncs below use raw fetch with no timeout; in the old order, if one
    // hung (slow/unreachable backend on a flaky connection) execution never
    // reached the flag write, so the gate looped new users back into onboarding
    // forever (reported 2026-06-11). Local writes can't hang the user.
    await AsyncStorage.setItem(ONBOARDING_KEY, 'true');
    // The category picker is back (2026-08-14) and seeds
    // '@sparrowcollect/followed_categories' again, so quickscan, market movers,
    // events and purchase have a signal from the first session instead of
    // starting unpersonalised. Skill level rides along the same way.
    // `persistPicks` writes locally and fires its network calls without await,
    // for the same reason the flag above is written first.
    persistPicks();

    // Fire-and-forget the server syncs — they must never block leaving onboarding.
    // (confirmRegion applies region/currency locally and synchronously before its fetch.)
    confirmRegion(detectedRegion).catch(() => {});

    track({ name: 'onboarding_completed' });

    logActivity({
      activity_type: 'onboarding_completed',
      title: 'Completed onboarding',
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
  // Skip stays available through the two OPTIONAL steps. It used to vanish
  // after slide index 2, which was fine when everything after it was the
  // region auto-detect — but categories and skill are questions, and a
  // question you cannot decline is not optional. Hidden only on the last
  // slide, where the primary button already says "Get Started".
  const showSkip = currentIndex < SLIDES.length - 1;

  const handleSkip = useCallback(async () => {
    track({ name: 'onboarding_skipped', properties: { skip_slide: currentIndex } });
    // Persist completion LOCALLY first; confirmRegion's network PUT has no timeout
    // and must never block the user from leaving onboarding (same trap as complete).
    await AsyncStorage.setItem(ONBOARDING_KEY, 'true');
    // Skipping still keeps whatever was picked before the skip. Someone who
    // chose three categories on slide 4 and then hit Skip meant to skip the
    // REST, not to discard the answer they already gave.
    persistPicks();
    confirmRegion(detectedRegion).catch(() => {});
    router.replace('/(tabs)/add');
  }, [currentIndex, confirmRegion, detectedRegion, router, persistPicks]);

  // Slide text entrance animations
  const slideOpacities = useRef(SLIDES.map(() => new Animated.Value(0))).current;
  const slideTranslates = useRef(SLIDES.map(() => new Animated.Value(20))).current;

  useEffect(() => {
    // Animate current slide text
    Animated.parallel([
      Animated.timing(slideOpacities[currentIndex], { toValue: 1, duration: 300, useNativeDriver: true }),
      Animated.timing(slideTranslates[currentIndex], { toValue: 0, duration: 300, useNativeDriver: true }),
    ]).start();

    // Trigger the category stagger when the CATEGORIES slide arrives. Was
    // `currentIndex === 3`, which pointed at the region slide after the picker
    // was removed — so the stagger it exists to drive fired on a screen with
    // no pills on it.
    if (SLIDES[currentIndex]?.kind === 'categories' && !categoryRevealTriggered.current) {
      categoryRevealTriggered.current = true;
      startCategoryReveal();
    }
  }, [currentIndex, startCategoryReveal]);

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
              {item.kind === 'scan' ? (
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
                      <Image source={require('../../assets/icon.png')} style={{ width: 64, height: 64 }} resizeMode="contain" />
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

              {item.kind === 'categories' && (
                <View style={styles.categoryWrap}>
                  <ScrollView
                    style={styles.categoryScrollView}
                    contentContainerStyle={styles.categoryGrid}
                    showsVerticalScrollIndicator={false}
                  >
                    {ALL_CATEGORIES.map((c, i) => {
                      const on = pickedCategories.has(c.slug);
                      return (
                        <Animated.View key={c.slug} style={getCategoryStyle(i)}>
                          <TouchableOpacity
                            onPress={() => {
                              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, {
                                enabled: settings.hapticsEnabled,
                              });
                              setPickedCategories((prev) => {
                                const next = new Set(prev);
                                if (next.has(c.slug)) next.delete(c.slug);
                                else next.add(c.slug);
                                return next;
                              });
                            }}
                            style={[
                              styles.categoryPill,
                              {
                                backgroundColor: on ? c.tint + '30' : colors.card,
                                borderColor: on ? c.tint : colors.border,
                              },
                            ]}
                            accessibilityRole="button"
                            accessibilityState={{ selected: on }}
                            accessibilityLabel={c.name}
                          >
                            <Text
                              style={[styles.categoryPillText, { color: on ? colors.text : colors.muted }]}
                              numberOfLines={1}
                            >
                              {c.name}
                            </Text>
                          </TouchableOpacity>
                        </Animated.View>
                      );
                    })}
                  </ScrollView>
                  <Text style={[styles.categoryCountText, { color: colors.muted }]}>
                    {pickedCategories.size === 0
                      ? 'Optional — skip if you are still deciding'
                      : `${pickedCategories.size} selected`}
                  </Text>
                </View>
              )}

              {item.kind === 'skill' && (
                <View style={styles.skillWrap}>
                  {SKILL_OPTIONS.map((opt) => {
                    const on = pickedSkill === opt.value;
                    return (
                      <TouchableOpacity
                        key={opt.value}
                        onPress={() => {
                          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, {
                            enabled: settings.hapticsEnabled,
                          });
                          // Tapping the selected one clears it — the answer is
                          // optional, and a picker you cannot un-answer forces
                          // a claim out of someone who would rather not make one.
                          setPickedSkill((prev) => (prev === opt.value ? null : opt.value));
                        }}
                        style={[
                          styles.skillCard,
                          {
                            backgroundColor: on ? colors.brand.base + '20' : colors.card,
                            borderColor: on ? colors.brand.dark : colors.border,
                          },
                        ]}
                        accessibilityRole="button"
                        accessibilityState={{ selected: on }}
                        accessibilityLabel={`${opt.label}. ${opt.blurb}`}
                      >
                        <Ionicons
                          name={opt.icon}
                          size={22}
                          color={on ? colors.brand.dark : colors.muted}
                        />
                        <View style={{ flex: 1 }}>
                          <Text style={[styles.skillLabel, { color: colors.text }]}>{opt.label}</Text>
                          <Text style={[styles.skillBlurb, { color: colors.muted }]}>{opt.blurb}</Text>
                        </View>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              )}

              {/* Keyed on `kind`, not on position — see the Slide type. */}
              {item.kind === 'region' && (
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
  // Wrapper the old picker never had: its ScrollView sat directly in the slide.
  categoryWrap: { width: '100%', alignItems: 'center' },
  skillWrap: { width: '100%', marginTop: 20, gap: 10, paddingHorizontal: 4 },
  skillCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderWidth: 1.5,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 13,
  },
  skillLabel: { fontSize: 15, fontWeight: '700' },
  skillBlurb: { fontSize: 13, marginTop: 2 },
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
