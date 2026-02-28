/**
 * useMultiSelect - Hook for managing multi-selection state.
 * Provides selection tracking, toggle functions, and bulk action helpers.
 */

import { useState, useCallback, useMemo } from 'react';
import { fireHaptic, HapticIntent } from '@/haptics';

interface UseMultiSelectOptions<T> {
  items: T[];
  keyExtractor: (item: T) => string;
  onSelectionChange?: (selectedIds: Set<string>) => void;
}

interface UseMultiSelectResult<T> {
  // State
  isMultiSelectMode: boolean;
  selectedIds: Set<string>;
  selectedCount: number;
  selectedItems: T[];

  // Actions
  enterMultiSelectMode: () => void;
  exitMultiSelectMode: () => void;
  toggleMultiSelectMode: () => void;
  toggleItem: (id: string) => void;
  selectAll: () => void;
  deselectAll: () => void;
  isSelected: (id: string) => boolean;

  // Bulk action helpers
  getSelectedItems: () => T[];
  clearSelection: () => void;
}

export function useMultiSelect<T>({
  items,
  keyExtractor,
  onSelectionChange,
}: UseMultiSelectOptions<T>): UseMultiSelectResult<T> {
  const [isMultiSelectMode, setIsMultiSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Update selection and notify
  const updateSelection = useCallback(
    (newSelection: Set<string>) => {
      setSelectedIds(newSelection);
      onSelectionChange?.(newSelection);
    },
    [onSelectionChange]
  );

  // Enter multi-select mode
  const enterMultiSelectMode = useCallback(() => {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED);
    setIsMultiSelectMode(true);
  }, []);

  // Exit multi-select mode and clear selection
  const exitMultiSelectMode = useCallback(() => {
    setIsMultiSelectMode(false);
    updateSelection(new Set());
  }, [updateSelection]);

  // Toggle multi-select mode
  const toggleMultiSelectMode = useCallback(() => {
    if (isMultiSelectMode) {
      exitMultiSelectMode();
    } else {
      enterMultiSelectMode();
    }
  }, [isMultiSelectMode, enterMultiSelectMode, exitMultiSelectMode]);

  // Toggle individual item selection
  const toggleItem = useCallback(
    (id: string) => {
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
      const newSelection = new Set(selectedIds);
      if (newSelection.has(id)) {
        newSelection.delete(id);
      } else {
        newSelection.add(id);
      }
      updateSelection(newSelection);
    },
    [selectedIds, updateSelection]
  );

  // Select all items
  const selectAll = useCallback(() => {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED);
    const allIds = new Set(items.map(keyExtractor));
    updateSelection(allIds);
  }, [items, keyExtractor, updateSelection]);

  // Deselect all items
  const deselectAll = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    updateSelection(new Set());
  }, [updateSelection]);

  // Check if item is selected
  const isSelected = useCallback(
    (id: string) => selectedIds.has(id),
    [selectedIds]
  );

  // Get selected items
  const getSelectedItems = useCallback(() => {
    return items.filter((item) => selectedIds.has(keyExtractor(item)));
  }, [items, selectedIds, keyExtractor]);

  // Clear selection without exiting mode
  const clearSelection = useCallback(() => {
    updateSelection(new Set());
  }, [updateSelection]);

  // Memoized selected items
  const selectedItems = useMemo(
    () => items.filter((item) => selectedIds.has(keyExtractor(item))),
    [items, selectedIds, keyExtractor]
  );

  return {
    isMultiSelectMode,
    selectedIds,
    selectedCount: selectedIds.size,
    selectedItems,
    enterMultiSelectMode,
    exitMultiSelectMode,
    toggleMultiSelectMode,
    toggleItem,
    selectAll,
    deselectAll,
    isSelected,
    getSelectedItems,
    clearSelection,
  };
}

export default useMultiSelect;
