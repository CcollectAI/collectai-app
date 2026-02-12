/**
 * Central export barrel for hooks.
 * Add actual hooks here as they are implemented.
 */

// Example placeholder hook to avoid empty file issues
export const usePlaceholderHook = () => {
  return null;
};

// Optimistic mutation hooks
export { useOptimisticMutation } from './useOptimisticMutation';
export {
  useOptimisticArchive,
  useOptimisticDelete,
  useOptimisticBulkArchive,
  useOptimisticBulkDelete,
  useOptimisticCreate,
} from './useOptimisticItems';
export {
  useOptimisticRsvpList,
  useOptimisticRsvpDetail,
} from './useOptimisticRsvp';

// Pagination
export { usePaginatedList } from './usePaginatedList';
export type {
  PaginatedFetcher,
  UsePaginatedListOptions,
  UsePaginatedListReturn,
} from './usePaginatedList';
