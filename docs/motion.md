# Motion System

Sparrow Collect uses a unified motion system for consistent, polished animations across the app.

## Core Primitives

### Motion Tokens (`src/motion/tokens.ts`)

Centralized timing and easing constants:

```typescript
import { DURATION, EASING, SCALE } from '@/motion';

// Durations (in ms)
DURATION.instant  // 100ms - micro-interactions
DURATION.fast     // 150ms - button presses
DURATION.normal   // 250ms - standard transitions
DURATION.slow     // 400ms - complex animations
DURATION.reveal   // 300ms - enter animations

// Scales
SCALE.pressed     // 0.97 - button press feedback
SCALE.hover       // 1.02 - hover state
```

### AnimatedPressable (`src/motion/AnimatedPressable.tsx`)

Drop-in replacement for `TouchableOpacity` or `Pressable` with built-in scale animation:

```tsx
import { AnimatedPressable } from '@/motion';

<AnimatedPressable
  onPress={() => handleAction()}
  style={styles.button}
>
  <Text>Tap Me</Text>
</AnimatedPressable>
```

Props:
- `scaleValue`: Override default pressed scale (default: 0.97)
- `duration`: Animation duration in ms (default: 150)
- All standard `PressableProps` are supported

### useEnterReveal (`src/motion/useEnterReveal.ts`)

Hook for fade+slide-up entrance animations:

```tsx
import { Animated } from 'react-native';
import { useEnterReveal } from '@/motion';

function MyScreen() {
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  return (
    <ScrollView>
      <Animated.View style={animatedStyle}>
        {/* Content fades in and slides up on mount */}
      </Animated.View>
    </ScrollView>
  );
}
```

Options:
- `duration`: Animation duration (default: 300ms)
- `delay`: Delay before animation starts (default: 0)
- `fromY`: Initial Y offset for slide (default: 20px)
- `autoStart`: Auto-trigger on mount (default: true)

Returns:
- `animatedStyle`: Style object to spread on `Animated.View`
- `reveal()`: Manually trigger animation
- `reset()`: Reset to initial state

## Usage Guidelines

1. **Replace TouchableOpacity/Pressable with AnimatedPressable** for all tappable elements
2. **Wrap screen content in Animated.View with useEnterReveal** for smooth page transitions
3. **Use motion tokens** instead of hardcoded timing values
4. **Keep animations subtle** - the goal is polish, not distraction
