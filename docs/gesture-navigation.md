# Gesture-First & Thumb-Zone Navigation

This document describes the gesture-based navigation and thumb-zone optimization implemented in Sparrow Collect.

## Overview

Modern phones have large screens, making it important to place primary actions within comfortable reach. This feature adds:

- **Swipe actions** on list rows (watchlist, share, delete)
- **Long-press context menus** as accessible alternatives
- **Thumb-zone optimized** action placement

## Components

### SwipeableRow

A wrapper component that adds swipe-to-reveal actions to any list item.

```tsx
import { SwipeableRow, SwipeActions } from '@/components/SwipeableRow';

<SwipeableRow
  leftActions={[SwipeActions.watchlist(() => handleWatchlist(item.id))]}
  rightActions={[
    SwipeActions.share(() => handleShare(item)),
    SwipeActions.delete(() => handleDelete(item.id)),
  ]}
  onLongPress={() => setContextMenuVisible(true)}
>
  <YourItemContent />
</SwipeableRow>
```

#### Props

| Prop | Type | Description |
|------|------|-------------|
| `children` | ReactNode | The row content |
| `leftActions` | SwipeAction[] | Actions revealed on swipe right |
| `rightActions` | SwipeAction[] | Actions revealed on swipe left |
| `onLongPress` | () => void | Long-press callback (accessibility) |
| `disabled` | boolean | Disable swipe gestures |
| `enableHaptics` | boolean | Enable haptic feedback (default: true) |

### Pre-built Actions

```tsx
import { SwipeActions } from '@/components/SwipeableRow';

// Available action creators:
SwipeActions.watchlist(onPress)      // Blue "Watch" button
SwipeActions.removeWatchlist(onPress) // Gray "Unwatch" button
SwipeActions.share(onPress)          // Green "Share" button
SwipeActions.delete(onPress)         // Red "Delete" button
SwipeActions.edit(onPress)           // Orange "Edit" button
SwipeActions.favorite(onPress)       // Pink "Favorite" button
```

### ContextMenu

An accessible alternative to swipe actions, displayed as a bottom sheet.

```tsx
import { ContextMenu } from '@/components/ContextMenu';

<ContextMenu
  visible={contextMenuVisible}
  onClose={() => setContextMenuVisible(false)}
  actions={allActions}
  title="Item Name"
  subtitle="Category"
/>
```

### SwipeableItemRow

A ready-to-use component that combines SwipeableRow with item display logic.

```tsx
import { SwipeableItemRow } from '@/components/SwipeableItemRow';

<SwipeableItemRow
  item={item}
  onPress={() => navigateToDetail(item)}
  onAddToWatchlist={(id) => addToWatchlist(id)}
  onDelete={(id) => deleteItem(id)}
  colors={colors}
/>
```

## Feature Flag

The gesture navigation is controlled by the `FEATURE_GESTURE_THUMB_NAVIGATION` feature flag:

```tsx
import { featureFlags } from '@/config/featureFlags';

if (featureFlags.FEATURE_GESTURE_THUMB_NAVIGATION) {
  // Use swipeable rows
}
```

## Thumb-Zone Guidelines

For optimal ergonomics:

1. **Primary actions** (Scan, Add) should be in the lower 40% of the screen
2. **Secondary actions** revealed via swipe gestures
3. **Destructive actions** (Delete) require confirmation
4. **Long-press** provides accessibility alternative to swipe

## Accessibility

- Swipe actions have `accessibilityRole="button"` and `accessibilityLabel`
- Long-press opens a context menu with all available actions
- Context menu items are keyboard-navigable
- Haptic feedback can be disabled for users with vestibular disorders

## Best Practices

1. **Consistent placement**: Always put watchlist on left swipe, delete on right
2. **Visual feedback**: Use haptics and animations to confirm actions
3. **Confirm destructive actions**: Always show an alert before delete
4. **Graceful degradation**: If gestures fail, long-press always works
