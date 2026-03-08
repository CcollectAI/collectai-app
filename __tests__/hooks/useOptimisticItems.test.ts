import { renderHook, act, waitFor } from '@testing-library/react-native';
import {
  useOptimisticArchive,
  useOptimisticDelete,
  useOptimisticBulkArchive,
  useOptimisticBulkDelete,
} from '../../src/hooks/useOptimisticItems';

const mockArchiveItem = jest.fn();
const mockDeleteItem = jest.fn();

jest.mock('../../src/data', () => ({
  dataProvider: {
    archiveItem: (...args: unknown[]) => mockArchiveItem(...args),
    deleteItem: (...args: unknown[]) => mockDeleteItem(...args),
    createItem: jest.fn(),
  },
}));

jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { warn: jest.fn(), info: jest.fn(), error: jest.fn() },
}));

jest.mock('../../src/lib/logger', () => ({
  logger: { warn: jest.fn(), info: jest.fn(), error: jest.fn() },
}));

type MockItem = { id: string; name: string; [key: string]: unknown };

function createSetItems() {
  let items: MockItem[] = [
    { id: '1', name: 'Alpha' },
    { id: '2', name: 'Beta' },
    { id: '3', name: 'Gamma' },
  ];

  const setItems: React.Dispatch<React.SetStateAction<MockItem[]>> = (action) => {
    if (typeof action === 'function') {
      items = action(items);
    } else {
      items = action;
    }
  };

  return {
    setItems,
    getItems: () => items,
  };
}

describe('useOptimisticArchive', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('optimistically removes the item from the list immediately', async () => {
    mockArchiveItem.mockResolvedValue(undefined);
    const { setItems, getItems } = createSetItems();
    const reloadItems = jest.fn();

    const { result } = renderHook(() => useOptimisticArchive(setItems, reloadItems));

    await act(async () => {
      await result.current.mutate('2');
    });

    const remaining = getItems();
    expect(remaining.find((i) => i.id === '2')).toBeUndefined();
    expect(remaining).toHaveLength(2);
  });

  it('calls reloadItems on API failure (rollback)', async () => {
    mockArchiveItem.mockRejectedValue(new Error('Server error'));
    const { setItems } = createSetItems();
    const reloadItems = jest.fn();

    const { result } = renderHook(() => useOptimisticArchive(setItems, reloadItems));

    await act(async () => {
      await result.current.mutate('1');
    });

    expect(reloadItems).toHaveBeenCalled();
    expect(result.current.error).toBeTruthy();
  });

  it('calls dataProvider.archiveItem with the correct item ID', async () => {
    mockArchiveItem.mockResolvedValue(undefined);
    const { setItems } = createSetItems();
    const reloadItems = jest.fn();

    const { result } = renderHook(() => useOptimisticArchive(setItems, reloadItems));

    await act(async () => {
      await result.current.mutate('3');
    });

    expect(mockArchiveItem).toHaveBeenCalledWith('3');
  });

  it('sets isLoading during mutation', async () => {
    let resolveArchive: () => void;
    mockArchiveItem.mockReturnValue(
      new Promise<void>((resolve) => { resolveArchive = resolve; }),
    );
    const { setItems } = createSetItems();
    const reloadItems = jest.fn();

    const { result } = renderHook(() => useOptimisticArchive(setItems, reloadItems));

    act(() => {
      result.current.mutate('1');
    });
    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      resolveArchive!();
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });
});

describe('useOptimisticDelete', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('optimistically removes the item from the list', async () => {
    mockDeleteItem.mockResolvedValue(undefined);
    const { setItems, getItems } = createSetItems();
    const reloadItems = jest.fn();

    const { result } = renderHook(() => useOptimisticDelete(setItems, reloadItems));

    await act(async () => {
      await result.current.mutate('1');
    });

    expect(getItems().find((i) => i.id === '1')).toBeUndefined();
    expect(getItems()).toHaveLength(2);
  });

  it('rolls back on error by calling reloadItems', async () => {
    mockDeleteItem.mockRejectedValue(new Error('Delete failed'));
    const { setItems } = createSetItems();
    const reloadItems = jest.fn();

    const { result } = renderHook(() => useOptimisticDelete(setItems, reloadItems));

    await act(async () => {
      await result.current.mutate('2');
    });

    expect(reloadItems).toHaveBeenCalled();
  });
});

describe('useOptimisticBulkArchive', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('optimistically removes multiple items at once', async () => {
    mockArchiveItem.mockResolvedValue(undefined);
    const { setItems, getItems } = createSetItems();
    const reloadItems = jest.fn();

    const { result } = renderHook(() => useOptimisticBulkArchive(setItems, reloadItems));

    await act(async () => {
      await result.current.mutate(['1', '3']);
    });

    const remaining = getItems();
    expect(remaining).toHaveLength(1);
    expect(remaining[0].id).toBe('2');
  });

  it('calls archiveItem for each item sequentially', async () => {
    mockArchiveItem.mockResolvedValue(undefined);
    const { setItems } = createSetItems();
    const reloadItems = jest.fn();

    const { result } = renderHook(() => useOptimisticBulkArchive(setItems, reloadItems));

    await act(async () => {
      await result.current.mutate(['1', '2']);
    });

    expect(mockArchiveItem).toHaveBeenCalledTimes(2);
    expect(mockArchiveItem).toHaveBeenCalledWith('1');
    expect(mockArchiveItem).toHaveBeenCalledWith('2');
  });

  it('rolls back all items on partial failure', async () => {
    mockArchiveItem
      .mockResolvedValueOnce(undefined) // first succeeds
      .mockRejectedValueOnce(new Error('Partial fail')); // second fails
    const { setItems } = createSetItems();
    const reloadItems = jest.fn();

    const { result } = renderHook(() => useOptimisticBulkArchive(setItems, reloadItems));

    await act(async () => {
      await result.current.mutate(['1', '2']);
    });

    expect(reloadItems).toHaveBeenCalled();
    expect(result.current.error).toBeTruthy();
  });
});

describe('useOptimisticBulkDelete', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('optimistically removes multiple items', async () => {
    mockDeleteItem.mockResolvedValue(undefined);
    const { setItems, getItems } = createSetItems();
    const reloadItems = jest.fn();

    const { result } = renderHook(() => useOptimisticBulkDelete(setItems, reloadItems));

    await act(async () => {
      await result.current.mutate(['2', '3']);
    });

    const remaining = getItems();
    expect(remaining).toHaveLength(1);
    expect(remaining[0].id).toBe('1');
  });

  it('rolls back on error', async () => {
    mockDeleteItem.mockRejectedValue(new Error('Bulk delete failed'));
    const { setItems } = createSetItems();
    const reloadItems = jest.fn();

    const { result } = renderHook(() => useOptimisticBulkDelete(setItems, reloadItems));

    await act(async () => {
      await result.current.mutate(['1']);
    });

    expect(reloadItems).toHaveBeenCalled();
  });
});
