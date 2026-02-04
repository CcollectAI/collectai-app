# Accessibility Guide

Guidelines and implementation details for accessibility in CcollectAI.

## Overview

This app follows WCAG 2.1 AA guidelines to ensure all users can access and use the app comfortably.

## Features

### High Contrast Mode

Provides increased color contrast for users with visual impairments.

**Enable in:** Settings → Accessibility → High Contrast Mode

```typescript
import { useHighContrast } from '@/lib/accessibilityContext';

function MyComponent() {
  const highContrast = useHighContrast();
  // Theme colors automatically adjust
}
```

**Contrast Ratios (WCAG 2.1 AA):**
- Normal text: 4.5:1 minimum
- Large text (18px+): 3:1 minimum
- UI components: 3:1 minimum

### Reduce Motion

Minimizes animations for users sensitive to motion.

**Enable in:** Settings → Accessibility → Reduce Motion
**Also respects:** iOS/Android system "Reduce Motion" setting

```typescript
import { useShouldReduceMotion } from '@/lib/accessibilityContext';

function MyAnimatedComponent() {
  const reduceMotion = useShouldReduceMotion();

  if (reduceMotion) {
    // Skip animation, show final state immediately
    return <StaticView />;
  }

  return <AnimatedView />;
}
```

### Large Text

Scales text throughout the app for users who need larger fonts.

**Enable in:** Settings → Accessibility → Large Text

```typescript
import { AccessibleText } from '@/components/AccessibleText';

// Automatically scales with large text setting
<AccessibleText size="medium">Hello</AccessibleText>
<AccessibleText size="large" weight="600">Title</AccessibleText>
```

### VoiceOver / Screen Reader Support

All interactive elements include accessibility labels.

```typescript
import { AccessiblePressable } from '@/components/AccessiblePressable';

<AccessiblePressable
  accessibilityLabel="Add item to collection"
  accessibilityHint="Opens the add item form"
  onPress={handleAdd}
>
  <Text>Add</Text>
</AccessiblePressable>
```

## Components

### AccessibleText

Text component that scales with large text setting.

```typescript
<AccessibleText
  size="medium"      // xs | small | medium | large | xl | xxl | xxxl
  color={colors.text}
  weight="600"       // normal | 500 | 600 | 700 | bold
>
  Content
</AccessibleText>
```

### AccessiblePressable

Pressable with required accessibility props.

```typescript
<AccessiblePressable
  accessibilityLabel="Button description"  // Required
  accessibilityHint="What happens on press" // Optional
  accessibilityRole="button"               // Default: button
  onPress={handlePress}
>
  <Text>Press me</Text>
</AccessiblePressable>
```

### AccessibilitySettings

Settings UI component for accessibility options.

```typescript
import { AccessibilitySettings } from '@/components/AccessibilitySettings';

// In your settings screen
<AccessibilitySettings />
```

## Provider Setup

Wrap your app with the AccessibilityProvider:

```typescript
import { AccessibilityProvider } from '@/lib/accessibilityContext';

function App() {
  return (
    <AccessibilityProvider>
      <YourApp />
    </AccessibilityProvider>
  );
}
```

## Development Guidelines

### 1. Always use theme colors

```typescript
// Good
<Text style={{ color: colors.text }}>Hello</Text>

// Bad - hardcoded colors break high contrast
<Text style={{ color: '#333' }}>Hello</Text>
```

### 2. Add accessibility labels to all interactive elements

```typescript
// Good
<Pressable
  accessibilityLabel="Save item"
  accessibilityHint="Saves the current item to your collection"
>

// Bad - no accessibility label
<Pressable onPress={save}>
```

### 3. Use semantic accessibilityRole

```typescript
<View accessibilityRole="header">  // For section headers
<View accessibilityRole="list">    // For lists
<View accessibilityRole="button">  // For buttons
<View accessibilityRole="link">    // For navigation
```

### 4. Respect reduce motion

```typescript
const reduceMotion = useShouldReduceMotion();
const duration = reduceMotion ? 0 : 300;

Animated.timing(value, {
  toValue: 1,
  duration,
  useNativeDriver: true,
}).start();
```

### 5. Test with assistive technologies

- **iOS:** Enable VoiceOver in Settings → Accessibility
- **Android:** Enable TalkBack in Settings → Accessibility
- **Both:** Test with "Reduce Motion" enabled

## Feature Flag

Accessibility features are gated behind:

```typescript
featureFlags.FEATURE_ACCESSIBILITY_ENHANCEMENTS
```

## Testing Checklist

- [ ] All buttons have accessibilityLabel
- [ ] High contrast mode provides sufficient contrast
- [ ] Animations skip when reduce motion enabled
- [ ] Text scales properly with large text mode
- [ ] VoiceOver can navigate all interactive elements
- [ ] Screen reader announces all state changes
