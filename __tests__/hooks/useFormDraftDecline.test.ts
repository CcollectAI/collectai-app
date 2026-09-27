/**
 * A form can DECLINE a stored draft (2026-09-27): Add manually's fresh scan
 * hand-off was overwritten by the previous item's draft, because the restore
 * lands after the hand-off and the callback's "return false" was ignored.
 */
import { renderHook, waitFor, act } from '@testing-library/react-native';

const mockGetItem = jest.fn();
jest.mock('@react-native-async-storage/async-storage', () => ({
  __esModule: true,
  default: { getItem: (...a: unknown[]) => mockGetItem(...a), setItem: jest.fn(async () => {}), removeItem: jest.fn(async () => {}) },
}));
import { useFormDraft } from '../../src/hooks/useFormDraft';

beforeEach(() => mockGetItem.mockResolvedValue(JSON.stringify({ name: 'Old item', category: 'Nintendo Merch' })));

it('restores and announces a draft when the form accepts it', async () => {
  const onRestore = jest.fn(() => undefined);
  const { result } = renderHook(() => useFormDraft({ draftKey: 'k', formState: {}, onRestore }));
  await waitFor(() => expect(onRestore).toHaveBeenCalled());
  await waitFor(() => expect(result.current.draftRestored).toBe(true));
});

it('a declined draft is not announced as restored', async () => {
  const onRestore = jest.fn(() => false as const);
  const { result } = renderHook(() => useFormDraft({ draftKey: 'k', formState: {}, onRestore }));
  await waitFor(() => expect(onRestore).toHaveBeenCalled());
  // Let any state update from the restore render before asserting its absence.
  await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
  expect(result.current.draftRestored).toBe(false);
  expect(result.current.hasDraft).toBe(false);
});
