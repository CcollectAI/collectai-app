import React from 'react';
import { View, Text, FlatList, Image, StyleSheet, Dimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { AppTheme } from '@/hooks/useAppTheme';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

type SpotlightSlide = {
  id: string;
  title: string;
  subtitle?: string;
  imageUrl?: string;
};

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
        renderItem={({ item: slide }) => (
          <View
            style={[styles.spotlightSlide, { backgroundColor: colors.card, borderColor: colors.border }]}
            accessibilityLabel={`Spotlight: ${slide.title}`}
          >
            {slide.imageUrl ? (
              <View style={styles.spotlightImageWrap}>
                <Image source={{ uri: slide.imageUrl }} style={styles.spotlightImage} />
                <View style={styles.spotlightImageOverlay} />
              </View>
            ) : (
              <View style={[styles.spotlightImagePlaceholder, { backgroundColor: colors.background }]}>
                <Ionicons name="sparkles" size={32} color={colors.accent} />
              </View>
            )}
            <Text style={[styles.spotlightTitle, { color: colors.text }]}>{slide.title}</Text>
            {slide.subtitle && (
              <Text style={[styles.spotlightSubtitle, { color: colors.muted }]}>{slide.subtitle}</Text>
            )}
          </View>
        )}
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
    padding: 16,
    alignItems: 'center',
  },
  spotlightImageWrap: {
    width: '100%',
    height: 100,
    borderRadius: 12,
    overflow: 'hidden',
    marginBottom: 12,
  },
  spotlightImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  spotlightImageOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.15)',
  },
  spotlightImagePlaceholder: {
    width: '100%',
    height: 100,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  spotlightTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  spotlightSubtitle: {
    marginTop: 2,
    fontSize: 12,
    textAlign: 'center',
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
