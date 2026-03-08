import { renderHook, act } from '@testing-library/react-native';
import { useMultiSelect } from '../../src/hooks/useMultiSelect';

jest.mock('../../src/haptics', () => ({
  fireHaptic: jest.fn(),
  HapticIntent: {
    CONFIRMATION_LIGHT: 'light',
    JUDGMENT_LOCKED: 'locked',
  },
}));

type TestItem = { id: string; name: string };

const ITEMS: TestItem[] = [
  { id: '1', name: 'Alpha' },
  { id: '2', name: 'Beta' },
  { id: '3', name: 'Gamma' },
];

const KEY_EXTRACTOR = (item: TestItem) => item.id;

describe('useMultiSelect', () => {
  it('starts with empty selection and multi-select mode off', () => {
    const { result } = renderHook(() =>
      useMultiSelect({ items: ITEMS, keyExtractor: KEY_EXTRACTOR }),
    );

    expect(result.current.isMultiSelectMode).toBe(false);
    expect(result.current.selectedIds.size).toBe(0);
    expect(result.current.selectedCount).toBe(0);
    expect(result.current.selectedItems).toEqual([]);
  });

  it('enters multi-select mode', () => {
    const { result } = renderHook(() =>
      useMultiSelect({ items: ITEMS, keyExtractor: KEY_EXTRACTOR }),
    );

    act(() => {
      result.current.enterMultiSelectMode();
    });

    expect(result.current.isMultiSelectMode).toBe(true);
  });

  it('exits multi-select mode and clears selection', () => {
    const { result } = renderHook(() =>
      useMultiSelect({ items: ITEMS, keyExtractor: KEY_EXTRACTOR }),
    );

    act(() => {
      result.current.enterMultiSelectMode();
      result.current.toggleItem('1');
    });
    expect(result.current.selectedCount).toBe(1);

    act(() => {
      result.current.exitMultiSelectMode();
    });

    expect(result.current.isMultiSelectMode).toBe(false);
    expect(result.current.selectedCount).toBe(0);
  });

  it('toggles individual item selection (select then deselect)', () => {
    const { result } = renderHook(() =>
      useMultiSelect({ items: ITEMS, keyExtractor: KEY_EXTRACTOR }),
    );

    // Select item '2'
    act(() => {
      result.current.toggleItem('2');
    });
    expect(result.current.selectedIds.has('2')).toBe(true);
    expect(result.current.selectedCount).toBe(1);

    // Deselect item '2'
    act(() => {
      result.current.toggleItem('2');
    });
    expect(result.current.selectedIds.has('2')).toBe(false);
    expect(result.current.selectedCount).toBe(0);
  });

  it('selectAll selects all items from the list', () => {
    const { result } = renderHook(() =>
      useMultiSelect({ items: ITEMS, keyExtractor: KEY_EXTRACTOR }),
    );

    act(() => {
      result.current.selectAll();
    });

    expect(result.current.selectedCount).toBe(3);
    expect(result.current.selectedIds.has('1')).toBe(true);
    expect(result.current.selectedIds.has('2')).toBe(true);
    expect(result.current.selectedIds.has('3')).toBe(true);
    expect(result.current.selectedItems).toEqual(ITEMS);
  });

  it('deselectAll clears all selections', () => {
    const { result } = renderHook(() =>
      useMultiSelect({ items: ITEMS, keyExtractor: KEY_EXTRACTOR }),
    );

    act(() => {
      result.current.selectAll();
    });
    expect(result.current.selectedCount).toBe(3);

    act(() => {
      result.current.deselectAll();
    });
    expect(result.current.selectedCount).toBe(0);
    expect(result.current.selectedItems).toEqual([]);
  });

  it('isSelected returns correct boolean for each item', () => {
    const { result } = renderHook(() =>
      useMultiSelect({ items: ITEMS, keyExtractor: KEY_EXTRACTOR }),
    );

    act(() => {
      result.current.toggleItem('1');
    });
    act(() => {
      result.current.toggleItem('3');
    });

    expect(result.current.isSelected('1')).toBe(true);
    expect(result.current.isSelected('2')).toBe(false);
    expect(result.current.isSelected('3')).toBe(true);
  });

  it('calls onSelectionChange callback when selection updates', () => {
    const onSelectionChange = jest.fn();
    const { result } = renderHook(() =>
      useMultiSelect({ items: ITEMS, keyExtractor: KEY_EXTRACTOR, onSelectionChange }),
    );

    act(() => {
      result.current.toggleItem('1');
    });

    expect(onSelectionChange).toHaveBeenCalledTimes(1);
    const calledWith = onSelectionChange.mock.calls[0][0] as Set<string>;
    expect(calledWith.has('1')).toBe(true);
  });

  it('toggleMultiSelectMode toggles the mode on and off', () => {
    const { result } = renderHook(() =>
      useMultiSelect({ items: ITEMS, keyExtractor: KEY_EXTRACTOR }),
    );

    act(() => {
      result.current.toggleMultiSelectMode();
    });
    expect(result.current.isMultiSelectMode).toBe(true);

    act(() => {
      result.current.toggleMultiSelectMode();
    });
    expect(result.current.isMultiSelectMode).toBe(false);
  });

  it('getSelectedItems returns the correct subset', () => {
    const { result } = renderHook(() =>
      useMultiSelect({ items: ITEMS, keyExtractor: KEY_EXTRACTOR }),
    );

    act(() => {
      result.current.toggleItem('1');
    });
    act(() => {
      result.current.toggleItem('3');
    });

    const selected = result.current.getSelectedItems();
    expect(selected).toEqual([
      { id: '1', name: 'Alpha' },
      { id: '3', name: 'Gamma' },
    ]);
  });

  it('clearSelection clears without exiting multi-select mode', () => {
    const { result } = renderHook(() =>
      useMultiSelect({ items: ITEMS, keyExtractor: KEY_EXTRACTOR }),
    );

    act(() => {
      result.current.enterMultiSelectMode();
      result.current.toggleItem('1');
    });
    expect(result.current.isMultiSelectMode).toBe(true);
    expect(result.current.selectedCount).toBe(1);

    act(() => {
      result.current.clearSelection();
    });
    expect(result.current.isMultiSelectMode).toBe(true);
    expect(result.current.selectedCount).toBe(0);
  });
});
