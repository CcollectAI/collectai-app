/**
 * useOptimisticItems
 *
 * Provides optimistic mutation wrappers for item list operations:
 *  - archiveItem: removes item from local list immediately, reverts on error
 *  - deleteItem: same pattern as archive
 *  - createItem: adds item with temp ID immediately, replaces with server ID on success
 *
 * Works with any component that manages an items array via setState.
 */

import { useCallback } from 'react';
import { useOptimisticMutation } from './useOptimisticMutation';
import { dataProvider } from '@/data';
import type { Item, CreateItemInput } from '@/data/types';
import logger from '@/utils/logger';

type ItemListSetter = React.Dispatch<React.SetStateAction<Array<{ id: string; name?: string; category?: string; _isTemp?: boolean; [key: string]: unknown }>>>;

// Generic id-keyed setter for bulk ops — works with any item shape that has an `id`.
type IdSetter<T extends { id: string }> = React.Dispatch<React.SetStateAction<T[]>>;

/**
 * Hook for optimistically archiving items.
 *
 * @param setItems - State setter for the items array
 * @param reloadItems - Function to reload items from server (used as rollback)
 */
export function useOptimisticArchive(
  setItems: ItemListSetter,
  reloadItems: () => void,
) {
  return useOptimisticMutation<string>({
    mutationFn: (itemId) => dataProvider.archiveItem(itemId),

    onOptimisticUpdate: (itemId) => {
      setItems((prev) => prev.filter((item) => item.id !== itemId));
    },

    onRollback: (_itemId, error) => {
      logger.warn('[useOptimisticArchive] Archive failed, reloading list:', error.message);
      reloadItems();
    },
  });
}

/**
 * Hook for optimistically deleting items.
 *
 * @param setItems - State setter for the items array
 * @param reloadItems - Function to reload items from server (used as rollback)
 */
export function useOptimisticDelete(
  setItems: ItemListSetter,
  reloadItems: () => void,
) {
  return useOptimisticMutation<string>({
    mutationFn: (itemId) => dataProvider.deleteItem(itemId),

    onOptimisticUpdate: (itemId) => {
      setItems((prev) => prev.filter((item) => item.id !== itemId));
    },

    onRollback: (_itemId, error) => {
      logger.warn('[useOptimisticDelete] Delete failed, reloading list:', error.message);
      reloadItems();
    },
  });
}

/**
 * Bulk archive: removes all selected items optimistically, reverts on error.
 *
 * @param setItems - State setter for the items array
 * @param reloadItems - Function to reload items from server (used as rollback)
 */
export function useOptimisticBulkArchive<T extends { id: string }>(
  setItems: IdSetter<T>,
  reloadItems: () => void,
) {
  return useOptimisticMutation<string[]>({
    mutationFn: async (itemIds) => {
      // Archive all items sequentially (server-side)
      for (const id of itemIds) {
        await dataProvider.archiveItem(id);
      }
    },

    onOptimisticUpdate: (itemIds) => {
      const idSet = new Set(itemIds);
      setItems((prev) => prev.filter((item) => !idSet.has(item.id)));
    },

    onRollback: (_itemIds, error) => {
      logger.warn('[useOptimisticBulkArchive] Bulk archive failed, reloading list:', error.message);
      reloadItems();
    },
  });
}

/**
 * Bulk delete: removes all selected items optimistically, reverts on error.
 *
 * @param setItems - State setter for the items array
 * @param reloadItems - Function to reload items from server (used as rollback)
 */
export function useOptimisticBulkDelete<T extends { id: string }>(
  setItems: IdSetter<T>,
  reloadItems: () => void,
) {
  return useOptimisticMutation<string[]>({
    mutationFn: async (itemIds) => {
      for (const id of itemIds) {
        await dataProvider.deleteItem(id);
      }
    },

    onOptimisticUpdate: (itemIds) => {
      const idSet = new Set(itemIds);
      setItems((prev) => prev.filter((item) => !idSet.has(item.id)));
    },

    onRollback: (_itemIds, error) => {
      logger.warn('[useOptimisticBulkDelete] Bulk delete failed, reloading list:', error.message);
      reloadItems();
    },
  });
}

/**
 * Hook for optimistically creating an item.
 * Adds a temporary item to the list immediately, then replaces it with the
 * server-created item on success.
 *
 * @param setItems - State setter for the items array
 * @param reloadItems - Function to reload items from server (used as rollback)
 */
export function useOptimisticCreate(
  setItems: ItemListSetter,
  reloadItems: () => void,
) {
  return useOptimisticMutation<CreateItemInput, Item>({
    mutationFn: (input) => dataProvider.createItem(input),

    onOptimisticUpdate: (input) => {
      const tempItem = {
        id: `temp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: input.name,
        category: input.category,
        collectionName: '',
        value: input.price ?? 0,
        condition: undefined,
        notes: undefined,
        _isTemp: true, // internal flag so screens can style differently if needed
      };
      setItems((prev) => [tempItem, ...prev]);
    },

    onRollback: (_input, error) => {
      logger.warn('[useOptimisticCreate] Create failed, reloading list:', error.message);
      // Remove temp item by filtering _isTemp entries and reload
      setItems((prev) => prev.filter((item) => !item._isTemp));
      reloadItems();
    },

    onSuccess: (input, serverItem) => {
      // Replace the temp item with the real server item
      setItems((prev) =>
        prev.map((item) => {
          if (item._isTemp && item.name === input.name && item.category === input.category) {
            return {
              id: serverItem.id,
              name: serverItem.name,
              category: serverItem.category,
              collectionName: '',
              value: serverItem.price ?? 0,
              condition: undefined,
              notes: undefined,
            };
          }
          return item;
        }),
      );
    },
  });
}
