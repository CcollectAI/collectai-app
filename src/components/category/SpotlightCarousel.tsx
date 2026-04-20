import React from 'react';
import { View, Text, FlatList, Image, StyleSheet, Dimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import type { AppTheme } from '@/hooks/useAppTheme';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

export type SpotlightSlideType = 'trend' | 'release' | 'deal' | 'milestone' | 'event';

type SpotlightSlide = {
  id: string;
  title: string;
  subtitle?: string;
  imageUrl?: string;
  slideType?: SpotlightSlideType;
};

// Gradient + icon mapping per slide type. Keeps the carousel visually
// distinct per topic without depending on photo coverage (R50e lesson).
const SLIDE_THEMES: Record<SpotlightSlideType, {
  gradient: [string, string];
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
}> = {
  trend:     { gradient: ['#81D8D0', '#2D8A84'], icon: 'trending-up',   label: 'TRENDING' },
  release:   { gradient: ['#A78BFA', '#EC4899'], icon: 'sparkles',      label: 'NEW RELEASE' },
  deal:      { gradient: ['#F97316', '#EF4444'], icon: 'pricetag',      label: 'DEAL' },
  milestone: { gradient: ['#10B981', '#059669'], icon: 'trophy',        label: 'MILESTONE' },
  event:     { gradient: ['#F59E0B', '#D97706'], icon: 'calendar',      label: 'EVENT' },
};

function inferSlideType(slide: SpotlightSlide): SpotlightSlideType {
  if (slide.slideType) return slide.slideType;
  const text = `${slide.title} ${slide.subtitle || ''}`.toLowerCase();
  if (/deal|drop|off|%|price/.test(text))     return 'deal';
  if (/new|release|launch|just/.test(text))   return 'release';
  if (/event|con|meetup|stream/.test(text))   return 'event';
  if (/trend|rising|hot|demand/.test(text))   return 'trend';
  return 'milestone';
}

type Props = {
  slides: SpotlightSlide[];
  spotlightIndex: number;
  spotlightRef: React.RefObject<FlatList | null>;
  onScrollEnd: (index: number) => void;
  colors: AppTheme['colors'];
};

const SpotlightCarousel: React.FC<Props> = ({
  slides,
  spotlightIndex,
  spotlightRef,
  onScrollEnd,
  colors,
}) => {
  if (slides.length === 0) return null;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>Spotlight</Text>
      <FlatList
        ref={spotlightRef}
        data={slides}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        keyExtractor={(slide) => slide.id}
        onMomentumScrollEnd={(e) => {
          const index = Math.round(e.nativeEvent.contentOffset.x / (SCREEN_WIDTH - 32));
          onScrollEnd(index);
        }}
        renderItem={({ item: slide }) => {
          const slideType = inferSlideType(slide);
          const theme = SLIDE_THEMES[slideType];
          return (
            <View
              style={[styles.spotlightSlide, { borderColor: colors.border }]}
              accessibilityLabel={`Spotlight ${theme.label.toLowerCase()}: ${slide.title}`}
            >
              <LinearGradient
                colors={theme.gradient}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={styles.spotlightHero}
              >
                {slide.imageUrl ? (
                  <>
                    <Image source={{ uri: slide.imageUrl }} style={styles.spotlightHeroPhoto} />
                    <View style={styles.spotlightHeroPhotoShade} />
                  </>
                ) : null}
                <View style={styles.spotlightHeroContent}>
                  <View style={styles.spotlightTypeBadge}>
                    <Ionicons name={theme.icon} size={12} color="#fff" />
                    <Text style={styles.spotlightTypeBadgeText}>{theme.label}</Text>
                  </View>
                  <Ionicons
                    name={theme.icon}
                    size={32}
                    color="rgba(255,255,255,0.95)"
                    style={styles.spotlightHeroIcon}
                  />
                </View>
              </LinearGradient>
              <View style={[styles.spotlightBody, { backgroundColor: colors.card }]}>
                <Text style={[styles.spotlightTitle, { color: colors.text }]} numberOfLines={2}>
                  {slide.title}
                </Text>
                {slide.subtitle && (
                  <Text style={[styles.spotlightSubtitle, { color: colors.muted }]} numberOfLines={2}>
                    {slide.subtitle}
                  </Text>
                )}
              </View>
            </View>
          );
        }}
      />
      {slides.length > 1 && (
        <View style={styles.dotsRow}>
          {slides.map((_, idx) => (
            <View
              key={idx}
              style={[
                styles.dot,
                { backgroundColor: colors.border },
                idx === spotlightIndex && { backgroundColor: colors.accent },
              ]}
            />
          ))}
        </View>
      )}
    </View>
  );
};

export default React.memo(SpotlightCarousel);

const styles = StyleSheet.create({
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  spotlightSlide: {
    width: SCREEN_WIDTH - 32,
    borderRadius: 16,
    borderWidth: 1,
    overflow: 'hidden',
  },
  spotlightHero: {
    height: 96,
    justifyContent: 'flex-end',
  },
  spotlightHeroPhoto: {
    ...StyleSheet.absoluteFillObject,
    resizeMode: 'cover',
  },
  spotlightHeroPhotoShade: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.28)',
  },
  spotlightHeroContent: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    padding: 10,
  },
  spotlightTypeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: 'rgba(0,0,0,0.35)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 10,
  },
  spotlightTypeBadgeText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.6,
  },
  spotlightHeroIcon: {
    textShadowColor: 'rgba(0,0,0,0.25)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  spotlightBody: {
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  spotlightTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  spotlightSubtitle: {
    marginTop: 2,
    fontSize: 12,
    lineHeight: 16,
  },
  dotsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 10,
    gap: 6,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
});
