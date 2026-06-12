# Haptics System

Semantic haptic feedback for meaningful UI state changes in Sparrow Collect.

## Overview

The haptics system provides consistent, purposeful tactile feedback that reinforces user actions without being intrusive. All haptics respect user preferences and accessibility settings.

## Haptic Intents

| Intent | When to Use | Haptic Pattern |
|--------|-------------|----------------|
| `CONFIRMATION_LIGHT` | Toggles, selections, minor actions | Light impact |
| `JUDGMENT_LOCKED` | Saves, commits, confirmations | Success notification |
| `CONFIDENCE_HIGH` | Scan confidence ≥ 0.8 | Medium + Light (double tap) |
| `UNCERTAINTY_PRESENT` | Scan confidence < 0.5 | Light impact |
| `ALERT_TRIGGERED` | Errors, critical alerts | Warning notification |

## Usage

### Basic Usage

```typescript
import { fireHaptic, HapticIntent } from '@/haptics';

// Fire a single haptic
fireHaptic(HapticIntent.CONFIRMATION_LIGHT);

// Fire on save action
fireHaptic(HapticIntent.JUDGMENT_LOCKED);
```

### With Options

```typescript
// Respect user settings
fireHaptic(HapticIntent.CONFIRMATION_LIGHT, {
  enabled: settings.hapticsEnabled
});

// Force bypass debounce (use sparingly)
fireHaptic(HapticIntent.ALERT_TRIGGERED, { force: true });
```

### Confidence-Based Haptics

```typescript
import { confidenceToIntent, fireHaptic } from '@/haptics';

// Automatically map confidence to appropriate haptic
const intent = confidenceToIntent(0.92); // Returns CONFIDENCE_HIGH
fireHaptic(intent);
```

### React Hooks

```typescript
import { useHapticsEffect, useConfidenceHaptic } from '@/hooks/useHapticsEffect';

// Fire haptic when scanId changes
useHapticsEffect({
  intents: [HapticIntent.JUDGMENT_LOCKED],
  stableKey: scanId,
  skip: !isComplete,
});

// Convenience hook for scan flows
useConfidenceHaptic(scanResult?.confidence, scanResult?.id);
```

## Debouncing

Haptics are automatically debounced to prevent overwhelming the user:

- **Standard intents**: 800ms debounce
- **ALERT_TRIGGERED**: 2500ms debounce

Use `force: true` to bypass debouncing when absolutely necessary.

## Accessibility

The haptics system respects:

1. **User Settings**: `settings.hapticsEnabled` toggle in app settings
2. **System Reduce Motion**: Detected via `AccessibilityInfo.isReduceMotionEnabled()`
3. **Platform Support**: Gracefully no-ops on unsupported platforms

### Checking Reduce Motion

```typescript
import { useReduceMotion } from '@/lib/accessibility';

function MyComponent() {
  const reduceMotion = useReduceMotion();

  // Skip animations when reduce motion is enabled
  if (!reduceMotion) {
    // animate...
  }
}
```

## Feature Flag

Gate haptics behind the feature flag for gradual rollout:

```typescript
import { featureFlags } from '@/config/featureFlags';

if (featureFlags.FEATURE_HAPTICS_MICRO_ANIMATIONS) {
  fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
}
```

## Components

### ProgressRing

Animated circular progress indicator:

```tsx
import { ProgressRing } from '@/components/ProgressRing';

<ProgressRing
  progress={0.75}
  size={48}
  strokeWidth={4}
/>
```

### ConfettiBurst

Celebration particle animation:

```tsx
import { ConfettiBurst, ConfettiBurstRef } from '@/components/ConfettiBurst';

const confettiRef = useRef<ConfettiBurstRef>(null);

// Trigger burst
confettiRef.current?.burst();

<ConfettiBurst ref={confettiRef} />
```

## Guidelines

1. **Be purposeful**: Only use haptics for meaningful state changes
2. **Don't overuse**: Too many haptics become noise
3. **Match intensity to importance**: Light for minor, strong for significant
4. **Always respect preferences**: Check `hapticsEnabled` setting
5. **Test on device**: Haptics must be tested on physical iOS/Android devices

## Testing

Run haptics tests:

```bash
npm test src/haptics
```

Tests cover:
- Intent deduplication
- Confidence threshold mapping
- Debounce behavior
- Enable/disable options
