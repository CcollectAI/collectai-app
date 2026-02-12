/**
 * useItemActions Hook
 * Provides standardized item actions for swipe gestures and context menus.
 * Includes watchlist, share, edit, and delete actions with proper callbacks.
 */

import { useState, useCallback, useMemo } from 'react';
import { Share, Alert } from 'react-native';
import { SwipeAction, SwipeActions } from '@/components/SwipeableRow';
import { logger } from '@/lib/logger';

type ItemData = {
  id: string;
  name: string;
  category?: string;
  value?: number;
  imageUri?: string;
};

type UseItemActionsOptions = {
  /** Item data for actions */
  item: ItemData;
  /** Callback when item is added to watchlist */
  onAddToWatchlist?: (itemId: string) => void;
  /** Callback when item is removed from watchlist */
  onRemoveFromWatchlist?: (itemId: string) => void;
  /** Whether item is currently in watchlist */
  isInWatchlist?: boolean;
  /** Callback when item is deleted */
  onDelete?: (itemId: string) => void;
  /** Callback when item is edited */
  onEdit?: (itemId: string) => void;
  /** Callback when item is favorited */
  onFavorite?: (itemId: string) => void;
  /** Whether item is currently favorited */
  isFavorited?: boolean;
  /** Custom share URL template */
  shareUrlTemplate?: string;
};

export function useItemActions({
  item,
  onAddToWatchlist,
  onRemoveFromWatchlist,
  isInWatchlist = false,
  onDelete,
  onEdit,
  onFavorite,
  isFavorited = false,
  shareUrlTemplate,
}: UseItemActionsOptions) {
  const [contextMenuVisible, setContextMenuVisible] = useState(false);

  const handleShare = useCallback(async () => {
    try {
      const shareUrl = shareUrlTemplate
        ? shareUrlTemplate.replace('{id}', item.id)
        : `https://ccollect.ai/item/${item.id}`;

      await Share.share({
        title: item.name,
        message: `Check out ${item.name} on CcollectAI: ${shareUrl}`,
        url: shareUrl,
      });
    } catch (error) {
      logger.error('[useItemActions] Share failed:', error);
    }
  }, [item, shareUrlTemplate]);

  const handleWatchlist = useCallback(() => {
    if (isInWatchlist) {
      onRemoveFromWatchlist?.(item.id);
    } else {
      onAddToWatchlist?.(item.id);
    }
  }, [item.id, isInWatchlist, onAddToWatchlist, onRemoveFromWatchlist]);

  const handleDelete = useCallback(() => {
    Alert.alert(
      'Delete Item',
      `Are you sure you want to delete "${item.name}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => onDelete?.(item.id),
        },
      ]
    );
  }, [item, onDelete]);

  const handleEdit = useCallback(() => {
    onEdit?.(item.id);
  }, [item.id, onEdit]);

  const handleFavorite = useCallback(() => {
    onFavorite?.(item.id);
  }, [item.id, onFavorite]);

  const openContextMenu = useCallback(() => {
    setContextMenuVisible(true);
  }, []);

  const closeContextMenu = useCallback(() => {
    setContextMenuVisible(false);
  }, []);

  // Build right swipe actions (revealed on swipe left)
  const rightActions = useMemo((): SwipeAction[] => {
    const actions: SwipeAction[] = [];

    // Share action
    actions.push(SwipeActions.share(handleShare));

    // Delete action (if callback provided)
    if (onDelete) {
      actions.push(SwipeActions.delete(handleDelete));
    }

    return actions;
  }, [handleShare, handleDelete, onDelete]);

  // Build left swipe actions (revealed on swipe right)
  const leftActions = useMemo((): SwipeAction[] => {
    const actions: SwipeAction[] = [];

    // Watchlist action
    if (onAddToWatchlist || onRemoveFromWatchlist) {
      actions.push(
        isInWatchlist
          ? SwipeActions.removeWatchlist(handleWatchlist)
          : SwipeActions.watchlist(handleWatchlist)
      );
    }

    // Favorite action
    if (onFavorite) {
      actions.push(SwipeActions.favorite(handleFavorite));
    }

    return actions;
  }, [
    isInWatchlist,
    handleWatchlist,
    handleFavorite,
    onAddToWatchlist,
    onRemoveFromWatchlist,
    onFavorite,
  ]);

  // All actions for context menu
  const allActions = useMemo((): SwipeAction[] => {
    return [...leftActions, ...rightActions];
  }, [leftActions, rightActions]);

  return {
    // Swipe action arrays
    leftActions,
    rightActions,
    // Context menu
    allActions,
    contextMenuVisible,
    openContextMenu,
    closeContextMenu,
    // Individual action handlers
    handleShare,
    handleWatchlist,
    handleDelete,
    handleEdit,
    handleFavorite,
  };
}

export default useItemActions;
