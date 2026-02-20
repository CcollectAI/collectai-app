# Motion Usage Examples

Real-world examples of how motion primitives are used throughout CollectAI.

## Screen Entrance Animation

Every screen uses `useEnterReveal` for a polished fade+slide entrance:

```tsx
// app/(tabs)/index.tsx
import { Animated } from 'react-native';
import { useEnterReveal } from '@/motion';

export default function PortfolioScreen() {
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  return (
    <SafeAreaView>
      <ScrollView>
        <Animated.View style={animatedStyle}>
          {/* All screen content wrapped here */}
        </Animated.View>
      </ScrollView>
    </SafeAreaView>
  );
}
```

## Card Press Animation

Cards and list items use `AnimatedPressable` for tactile feedback:

```tsx
// app/(tabs)/events.tsx
import { AnimatedPressable } from '@/motion';

{events.map((event) => (
  <AnimatedPressable
    key={event.id}
    onPress={() => router.push(`/events/${event.id}`)}
    style={{
      borderRadius: 16,
      backgroundColor: colors.card,
      padding: 10,
      marginBottom: 10,
    }}
  >
    <Text>{event.title}</Text>
  </AnimatedPressable>
))}
```

## Button Press Animation

Primary action buttons with scale feedback:

```tsx
// app/(tabs)/add.tsx
<AnimatedPressable
  onPress={handleQuickScanPress}
  style={{
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 20,
  }}
>
  <Text style={{ fontWeight: '700' }}>QuickScan (beta)</Text>
  <Text style={{ color: colors.muted }}>
    Snap a photo and we prefill the details.
  </Text>
</AnimatedPressable>
```

## Toggle Buttons (Range Selector)

```tsx
// app/(tabs)/index.tsx
{rangeButtons.map((k) => {
  const active = k === range;
  return (
    <AnimatedPressable
      key={k}
      onPress={() => setRange(k)}
      style={[
        styles.rangeBtn,
        { backgroundColor: colors.card, borderColor: colors.border },
        active && { backgroundColor: colors.accent + '20', borderColor: colors.accent },
      ]}
    >
      <Text style={[styles.rangeText, { color: colors.muted }, active && { color: colors.text }]}>
        {k}
      </Text>
    </AnimatedPressable>
  );
})}
```

## Icon Button

```tsx
// app/inbox.tsx
<AnimatedPressable
  onPress={() => router.back()}
  style={styles.backBtn}
>
  <Ionicons name="chevron-back" size={24} color={colors.text} />
</AnimatedPressable>
```

## Category Tiles

Grid tiles with press animation:

```tsx
// app/(tabs)/marketplace.tsx
{CATEGORIES.map((cat, index) => (
  <AnimatedPressable
    key={cat}
    style={[styles.categoryTile, { backgroundColor: tileColor }]}
    onPress={() => handleOpenCategory(cat)}
  >
    <Text style={styles.categoryTileText}>{cat}</Text>
  </AnimatedPressable>
))}
```

## Staggered List Animation

For more complex entrance effects, use multiple `useEnterReveal` with different delays:

```tsx
const { animatedStyle: headerStyle } = useEnterReveal({ delay: 0 });
const { animatedStyle: listStyle } = useEnterReveal({ delay: 100 });
const { animatedStyle: footerStyle } = useEnterReveal({ delay: 200 });

return (
  <ScrollView>
    <Animated.View style={headerStyle}>
      {/* Header */}
    </Animated.View>
    <Animated.View style={listStyle}>
      {/* List content */}
    </Animated.View>
    <Animated.View style={footerStyle}>
      {/* Footer */}
    </Animated.View>
  </ScrollView>
);
```

## Error/Retry Button

```tsx
// app/(tabs)/index.tsx
if (error) {
  return (
    <View style={styles.centerContainer}>
      <Ionicons name="alert-circle-outline" size={48} color={colors.error} />
      <Text style={styles.errorText}>{error}</Text>
      <AnimatedPressable style={styles.retryBtn} onPress={loadData}>
        <Text style={styles.retryText}>Retry</Text>
      </AnimatedPressable>
    </View>
  );
}
```
