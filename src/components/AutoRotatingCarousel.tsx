/**
 * AutoRotatingCarousel — horizontal slideshow that auto-advances and supports
 * swipe-to-control. Pauses rotation while the user is dragging.
 *
 * Each child becomes one slide. Use a wrapper View with a fixed height if
 * the slides are not naturally sized.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  useWindowDimensions,
  NativeSyntheticEvent,
  NativeScrollEvent,
} from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';

type Props = {
  children: React.ReactNode;
  intervalMs?: number;
  showDots?: boolean;
  /** Horizontal padding of the parent container; subtracted from slide width. */
  horizontalInset?: number;
  /** Optional fixed height; otherwise each slide sizes to its content. */
  slideHeight?: number;
  testID?: string;
};

export function AutoRotatingCarousel({
  children,
  intervalMs = 5000,
  showDots = true,
  horizontalInset = 0,
  slideHeight,
  testID,
}: Props) {
  const { colors } = useAppTheme();
  const { width: screenWidth } = useWindowDimensions();
  const slideWidth = screenWidth - horizontalInset * 2;

  const slides = React.Children.toArray(children).filter(Boolean);
  const listRef = useRef<FlatList>(null);
  const indexRef = useRef(0);
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  // Auto-advance loop. Pauses while the user is interacting so a manual swipe
  // doesn't fight the timer.
  useEffect(() => {
    if (slides.length <= 1 || paused) return;
    const timer = setInterval(() => {
      const next = (indexRef.current + 1) % slides.length;
      indexRef.current = next;
      setActive(next);
      listRef.current?.scrollToIndex({ index: next, animated: true });
    }, intervalMs);
    return () => clearInterval(timer);
  }, [slides.length, paused, intervalMs]);

  const onMomentumScrollEnd = useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>) => {
      const i = Math.round(e.nativeEvent.contentOffset.x / slideWidth);
      indexRef.current = i;
      setActive(i);
    },
    [slideWidth],
  );

  if (slides.length === 0) return null;
  if (slides.length === 1) {
    return (
      <View testID={testID} style={slideHeight ? { height: slideHeight } : undefined}>
        {slides[0]}
      </View>
    );
  }

  return (
    <View testID={testID}>
      <FlatList
        ref={listRef}
        data={slides}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        keyExtractor={(_, i) => `slide-${i}`}
        renderItem={({ item }) => (
          <View style={{ width: slideWidth, height: slideHeight }}>{item as React.ReactElement}</View>
        )}
        getItemLayout={(_, i) => ({ length: slideWidth, offset: slideWidth * i, index: i })}
        onScrollBeginDrag={() => setPaused(true)}
        onScrollEndDrag={() => setPaused(false)}
        onMomentumScrollEnd={onMomentumScrollEnd}
        decelerationRate="fast"
      />
      {showDots && (
        <View style={styles.dotsRow}>
          {slides.map((_, i) => (
            <View
              key={i}
              style={[
                styles.dot,
                {
                  backgroundColor: i === active ? colors.accent : colors.border,
                  width: i === active ? 18 : 6,
                },
              ]}
            />
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  dotsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
  },
  dot: {
    height: 6,
    borderRadius: 3,
  },
});
