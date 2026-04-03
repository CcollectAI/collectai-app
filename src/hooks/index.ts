/**
 * Central export barrel for hooks.
 */

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
