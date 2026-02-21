/**
 * Onboarding — 4-slide welcome walkthrough for first-time users.
 * Slide 4 auto-detects the user's region via IP geolocation.
 */

import React, { useRef, useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  useWindowDimensions,
  StyleSheet,
  ViewToken,
  ActivityIndicator,
  TouchableOpacity,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings, REGION_DEFAULTS } from '@/lib/settings';
import type { Region } from '@/lib/settings';
import { collectorsApi } from '@/api/collectorsApi';
import { API_BASE } from '@/api/config';
import { supabase } from '@/lib/supabase';

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

export default function OnboardingScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const { settings, updateSettings } = useSettings();
  const [currentIndex, setCurrentIndex] = useState(0);
  const flatListRef = useRef<FlatList>(null);
  const [detectedRegion, setDetectedRegion] = useState<Region>('europe');
  const [detecting, setDetecting] = useState(false);
  const [regionPickerVisible, setRegionPickerVisible] = useState(false);

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
        setCurrentIndex(viewableItems[0].index);
      }
    },
  ).current;

  const viewabilityConfig = useRef({ viewAreaCoveragePercentThreshold: 50 }).current;

  async function completeOnboarding() {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    await confirmRegion(detectedRegion);
    await AsyncStorage.setItem(ONBOARDING_KEY, 'true');
    router.replace('/(tabs)');
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
  const isRegionSlide = currentIndex === 3;

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        {!isLast && (
          <AnimatedPressable
            onPress={completeOnboarding}
            style={styles.skipBtn}
            accessibilityRole="button"
            accessibilityLabel="Skip onboarding"
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
            <View style={styles.iconCircle}>
              <Ionicons name={item.icon} size={48} color={TIFFANY_DARK} />
            </View>
            <Text style={styles.slideTitle}>{item.title}</Text>
            <Text style={styles.slideSubtitle}>{item.subtitle}</Text>

            {/* Region detection UI on slide 4 */}
            {index === 3 && (
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
});
