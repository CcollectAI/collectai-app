/**
 * useItemDetail hook tests.
 *
 * Validates that the hook:
 * - Initializes state from params
 * - Manages keyboard state
 * - Handles save notes/draft/edits
 * - Handles feedback submission
 * - Reads every amount BEFORE the first write, so a price it cannot read
 *   leaves nothing half-saved (class sweep K, 2026-09-17)
 *
 * `isForSale` is read-only here — the for-sale WRITE chain (forSaleLoading,
 * handleListForSale, handleUnlist) was deleted in dabfc32 and its tests went
 * with it. This suite is named in `verify:prebuild`; an unnamed suite rots.
 */
import { renderHook, act, waitFor } from '@testing-library/react-native';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockShowToast = jest.fn();
const mockSettings = { hapticsEnabled: true, currency: 'EUR', isDark: false };

jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({
    settings: mockSettings,
    updateSettings: jest.fn(),
    ready: true,
  }),
}));

jest.mock('../../src/components/Toast', () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

jest.mock('../../src/haptics', () => ({
  fireHaptic: jest.fn(),
  HapticIntent: {
    JUDGMENT_LOCKED: 'JUDGMENT_LOCKED',
    ALERT_TRIGGERED: 'ALERT_TRIGGERED',
    CONFIRMATION_LIGHT: 'CONFIRMATION_LIGHT',
  },
}));

jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
}));

const mockPersistQuickscanDraft = jest.fn();
const mockUpdateItem = jest.fn();
const mockSubmitFeedback = jest.fn();
const mockToggleForSale = jest.fn();
const mockListItems = jest.fn();

jest.mock('../../src/data', () => ({
  dataProvider: {
    persistQuickscanDraft: (...args: unknown[]) => mockPersistQuickscanDraft(...args),
    updateItem: (...args: unknown[]) => mockUpdateItem(...args),
    submitFeedback: (...args: unknown[]) => mockSubmitFeedback(...args),
    toggleForSale: (...args: unknown[]) => mockToggleForSale(...args),
    listItems: (...args: unknown[]) => mockListItems(...args),
  },
}));

// Captures the PostgREST patch so a test can assert what was — and was not —
// written. The estimated-value bugs (class sweep K) were both invisible to a
// mock that only resolved: one wrote the model's number on an unrelated save,
// the other dropped the field and still reported success.
const mockItemsPatch = jest.fn();

jest.mock('../../src/lib/supabase', () => ({
  supabase: {
    from: () => ({
      select: () => ({
        eq: () => ({
          single: () => Promise.resolve({ data: null, error: null }),
        }),
      }),
      update: (patch: Record<string, unknown>) => {
        mockItemsPatch(patch);
        return { eq: () => Promise.resolve({ data: null, error: null }) };
      },
    }),
  },
}));

const mockGetPriceEvidence = jest.fn().mockResolvedValue(null);
const mockGetScarcityScores = jest.fn().mockResolvedValue({ items: [] });
const mockMarketplaceComps = jest.fn().mockResolvedValue({ comps: [] });
const mockSubmitVerifiedSale = jest.fn().mockResolvedValue({});
const mockUpdateItemPurchase = jest.fn().mockResolvedValue({});

jest.mock('../../src/api/collectorsApi', () => ({
  collectorsApi: {
    getPriceEvidence: (...args: unknown[]) => mockGetPriceEvidence(...args),
    getScarcityScores: (...args: unknown[]) => mockGetScarcityScores(...args),
    marketplaceComps: (...args: unknown[]) => mockMarketplaceComps(...args),
    submitVerifiedSale: (...args: unknown[]) => mockSubmitVerifiedSale(...args),
    updateItemPurchase: (...args: unknown[]) => mockUpdateItemPurchase(...args),
  },
}));

jest.mock('expo-router', () => ({
  router: { replace: jest.fn(), push: jest.fn() },
}));

// Capture Keyboard listener callbacks
let keyboardShowCallback: ((e: { endCoordinates: { height: number } }) => void) | null = null;
let keyboardHideCallback: (() => void) | null = null;

// Patch Keyboard.addListener to capture callbacks (without replacing the full RN module)
jest.mock('react-native/Libraries/Components/Keyboard/Keyboard', () => ({
  __esModule: true,
  default: {
    addListener: jest.fn((event: string, cb: (...args: unknown[]) => void) => {
      if (event === 'keyboardWillShow') keyboardShowCallback = cb as typeof keyboardShowCallback;
      if (event === 'keyboardWillHide') keyboardHideCallback = cb as typeof keyboardHideCallback;
      return { remove: jest.fn() };
    }),
    dismiss: jest.fn(),
  },
}));

import { useItemDetail } from '../../src/hooks/useItemDetail';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const defaultParams = {
  id: 'item-1',
  isDraft: false,
  initialName: 'Charizard Base Set',
  initialCategory: 'pokemon_tcg',
  initialCollection: 'My Collection',
  initialCondition: 'Near Mint',
  initialValue: '350',
  initialNotes: 'Some notes',
  imageUri: 'https://example.com/image.jpg',
  categorySlug: 'pokemon_tcg',
  q50: '300',
  // Required by the hook (UseItemDetailParams). Omitted until 2026-09-17, which
  // left editablePurchasePrice undefined and made every onSaveEdits test throw
  // on .trim() — the suite gates nothing, so it stayed red unnoticed.
  initialPurchasePrice: '',
  initialAcquisitionFees: '',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
  mockListItems.mockResolvedValue([]);
  keyboardShowCallback = null;
  keyboardHideCallback = null;
});

afterEach(() => {
  jest.useRealTimers();
});

describe('useItemDetail', () => {
  describe('initial state', () => {
    it('initializes edit state from params', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));

      expect(result.current.editableName).toBe('Charizard Base Set');
      expect(result.current.editableCategory).toBe('pokemon_tcg');
      expect(result.current.editableCollection).toBe('My Collection');
      expect(result.current.editableCondition).toBe('Near Mint');
      expect(result.current.editableValue).toBe('350');
      expect(result.current.notes).toBe('Some notes');
    });

    it('initializes with isEditing=false', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));
      expect(result.current.isEditing).toBe(false);
    });

    it('initializes save states as idle', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));
      expect(result.current.savingNotes).toBe(false);
      expect(result.current.savingDraft).toBe(false);
      expect(result.current.saveError).toBeNull();
    });

    it('initializes keyboard state as hidden', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));
      expect(result.current.keyboardVisible).toBe(false);
      expect(result.current.keyboardHeight).toBe(0);
    });

    it('initializes for-sale state as not for sale', () => {
      // `isForSale` is READ from the item and drives the Listed badge. The app
      // never writes it: the trg_sync_item_for_sale trigger does, and listing
      // goes through app/sell/new. forSaleLoading/handleListForSale/handleUnlist
      // were deleted with that chain in dabfc32.
      const { result } = renderHook(() => useItemDetail(defaultParams));
      expect(result.current.isForSale).toBe(false);
      expect(result.current.askingPriceValue).toBe('');
    });
  });

  describe('verified sale payload', () => {
    /**
     * Pydantic ignores unknown keys, so a client key the model does not declare
     * is dropped and answered 200. This call sent `sale_date` where
     * `VerifiedSaleRequest` declares `sold_at`, so the date of every verified
     * sale was discarded in silence — the member read "Sale price recorded —
     * thanks!", `tsc` was satisfied because the client's own type declared the
     * field, and production's only `verified_sales` row has `sold_at` NULL
     * (class V, 2026-09-19).
     *
     * Asserted at the CALL SITE on purpose. A test on the api wrapper cannot
     * catch this: TypeScript types are erased, so renaming the wrapper's field
     * back does not change what a hand-written call passes through — the first
     * attempt at this test passed against both versions.
     */
    it('sends the sale date as `sold_at`, the name the server reads', async () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));

      act(() => { result.current.setSalePrice('20'); });
      await act(async () => { await result.current.onSubmitSalePrice(); });

      expect(mockSubmitVerifiedSale).toHaveBeenCalledTimes(1);
      const payload = mockSubmitVerifiedSale.mock.calls[0][0];
      expect(payload).toHaveProperty('sold_at');
      expect(payload).not.toHaveProperty('sale_date');
      expect(typeof payload.sold_at).toBe('string');
      expect(payload.sale_price).toBe(20);
    });
  });

  describe('keyboard state', () => {
    it('updates keyboardVisible and keyboardHeight on keyboard show', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));

      expect(keyboardShowCallback).not.toBeNull();

      act(() => {
        keyboardShowCallback!({ endCoordinates: { height: 336 } });
      });

      expect(result.current.keyboardVisible).toBe(true);
      expect(result.current.keyboardHeight).toBe(336);
    });

    it('resets keyboard state on keyboard hide', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));

      act(() => {
        keyboardShowCallback!({ endCoordinates: { height: 336 } });
      });
      expect(result.current.keyboardVisible).toBe(true);

      act(() => {
        keyboardHideCallback!();
      });
      expect(result.current.keyboardVisible).toBe(false);
      expect(result.current.keyboardHeight).toBe(0);
    });
  });

  describe('onSaveNotes', () => {
    // This used to assert `message: 'Notes saved locally'` off a 300ms
    // setTimeout that wrote NOTHING — a test pinning a stub, so it stayed
    // green while every note a user typed was lost on unmount. It now
    // asserts the write actually happens.
    it('persists the note to the item', async () => {
      mockUpdateItem.mockResolvedValue({ id: 'item-1' });
      const { result } = renderHook(() => useItemDetail(defaultParams));

      await act(async () => {
        await result.current.onSaveNotes();
      });

      expect(mockUpdateItem).toHaveBeenCalledWith('item-1', { notes: 'Some notes' });
      expect(result.current.savingNotes).toBe(false);
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Notes saved', type: 'success' })
      );
    });

    it('reports failure instead of claiming success', async () => {
      // The whole point of the rewrite: never toast success on a failed write.
      mockUpdateItem.mockRejectedValue(new Error('network down'));
      const { result } = renderHook(() => useItemDetail(defaultParams));

      await act(async () => {
        await result.current.onSaveNotes();
      });

      expect(result.current.savingNotes).toBe(false);
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'error' })
      );
    });

    it('does not pretend to save a draft', async () => {
      // A draft has no items row to write to.
      const { result } = renderHook(() =>
        useItemDetail({ ...defaultParams, isDraft: true, id: undefined }),
      );

      await act(async () => {
        await result.current.onSaveNotes();
      });

      expect(mockUpdateItem).not.toHaveBeenCalled();
    });
  });

  describe('onSaveDraft', () => {
    it('calls persistQuickscanDraft and shows success toast', async () => {
      mockPersistQuickscanDraft.mockResolvedValue({
        id: 'new-id',
        title: 'Charizard Base Set',
        categoryId: 'pokemon_tcg',
        imageUrl: 'https://example.com/image.jpg',
      });

      const { result } = renderHook(() =>
        useItemDetail({ ...defaultParams, isDraft: true })
      );

      await act(async () => {
        await result.current.onSaveDraft();
      });

      expect(mockPersistQuickscanDraft).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Charizard Base Set',
          categoryId: 'pokemon_tcg',
        })
      );
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Item saved to collection', type: 'success' })
      );
    });

    it('does nothing when isDraft is false', async () => {
      const { result } = renderHook(() =>
        useItemDetail({ ...defaultParams, isDraft: false })
      );

      await act(async () => {
        await result.current.onSaveDraft();
      });

      expect(mockPersistQuickscanDraft).not.toHaveBeenCalled();
    });

    it('sets saveError on failure', async () => {
      mockPersistQuickscanDraft.mockRejectedValue(new Error('Network failure'));

      const { result } = renderHook(() =>
        useItemDetail({ ...defaultParams, isDraft: true })
      );

      await act(async () => {
        await result.current.onSaveDraft();
      });

      expect(result.current.saveError).toBe('Network failure');
      expect(result.current.savingDraft).toBe(false);
    });
  });

  describe('onSaveEdits', () => {
    it('calls updateItem and shows success toast', async () => {
      mockUpdateItem.mockResolvedValue({});

      const { result } = renderHook(() => useItemDetail(defaultParams));

      act(() => {
        result.current.setIsEditing(true);
      });

      await act(async () => {
        await result.current.onSaveEdits();
      });

      expect(mockUpdateItem).toHaveBeenCalledWith('item-1', {
        name: 'Charizard Base Set',
        category: 'pokemon_tcg',
      });
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Changes saved', type: 'success' })
      );
      expect(result.current.isEditing).toBe(false);
    });

    it('writes NOTHING when an amount cannot be read', async () => {
      // The partial-save class (sweep K). The cost-basis parse used to run after
      // updateItem and the PostgREST patch had already landed, so an unreadable
      // price saved the name and then said "Failed to save changes" — with no
      // way for the member to tell which half had happened. Every amount is now
      // read BEFORE the first write.
      mockUpdateItem.mockResolvedValue({});

      const { result } = renderHook(() => useItemDetail(defaultParams));

      act(() => {
        result.current.setIsEditing(true);
        result.current.setEditableName('Renamed');
        result.current.setEditablePurchasePrice('not a price');
      });

      await act(async () => {
        await result.current.onSaveEdits();
      });

      expect(mockUpdateItem).not.toHaveBeenCalled();
      // …and the toast names the field, rather than the generic save failure.
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.objectContaining({
          message: 'Enter a purchase price of 0 or more, or leave it blank',
          type: 'error',
        })
      );
      // Still in edit mode: there is a field to fix.
      expect(result.current.isEditing).toBe(true);
    });

    it('does not write estimated_value when the field was not touched', async () => {
      // The field is seeded with the value the SCREEN shows, which can come from
      // the model chain (q50 → predicted_price_eur → estimated_value). Writing
      // it back on an unrelated rename filed the catalogue's number as the
      // member's own estimate (class sweep K, 2026-09-17).
      mockUpdateItem.mockResolvedValue({});

      const { result } = renderHook(() => useItemDetail(defaultParams));

      act(() => {
        result.current.setIsEditing(true);
        result.current.setEditableName('Just a rename');
      });

      await act(async () => {
        await result.current.onSaveEdits();
      });

      const patches = mockItemsPatch.mock.calls.map(([p]) => p);
      for (const p of patches) expect(p).not.toHaveProperty('estimated_value');
    });

    it('clears estimated_value when the member empties the field', async () => {
      // NULL is meaningful: docs/ARCHITECTURE.md — "NULL means we do not know",
      // which hands the value back to the model chain. The old `> 0` test made
      // an estimate impossible to withdraw.
      mockUpdateItem.mockResolvedValue({});

      const { result } = renderHook(() => useItemDetail(defaultParams));

      act(() => {
        result.current.setIsEditing(true);
        result.current.setEditableValue('');
      });

      await act(async () => {
        await result.current.onSaveEdits();
      });

      const patch = mockItemsPatch.mock.calls.map(([p]) => p).find((p) => 'estimated_value' in p);
      expect(patch).toBeDefined();
      expect(patch!.estimated_value).toBeNull();
    });

    it('refuses to save when the estimated value cannot be read', async () => {
      mockUpdateItem.mockResolvedValue({});

      const { result } = renderHook(() => useItemDetail(defaultParams));

      act(() => {
        result.current.setIsEditing(true);
        result.current.setEditableValue('about three fifty');
      });

      await act(async () => {
        await result.current.onSaveEdits();
      });

      expect(mockUpdateItem).not.toHaveBeenCalled();
      expect(mockItemsPatch).not.toHaveBeenCalled();
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.objectContaining({
          message: 'Enter an estimated value of 0 or more, or leave it blank',
          type: 'error',
        })
      );
    });

    it('accepts a comma decimal in the purchase price', async () => {
      // parseMoney, not parseFloat: "1.250,00" is 1250, not 1.25.
      mockUpdateItem.mockResolvedValue({});

      const { result } = renderHook(() => useItemDetail(defaultParams));

      act(() => {
        result.current.setIsEditing(true);
        result.current.setEditablePurchasePrice('1.250,00');
      });

      await act(async () => {
        await result.current.onSaveEdits();
      });

      expect(mockUpdateItemPurchase).toHaveBeenCalledWith(
        'item-1', 1250, 'EUR', undefined, undefined,
      );
    });

    it('does nothing for draft items', async () => {
      const { result } = renderHook(() =>
        useItemDetail({ ...defaultParams, isDraft: true })
      );

      await act(async () => {
        await result.current.onSaveEdits();
      });

      expect(mockUpdateItem).not.toHaveBeenCalled();
    });
  });

  describe('evidence data', () => {
    it('fetches evidence data for non-draft items', async () => {
      mockGetPriceEvidence.mockResolvedValue({
        explanation: 'Based on 5 recent sales',
        evidence_summary: { sources: [], total_comps: 5 },
        evidence_hit_ids: [],
        prediction_at: '2026-03-15',
      });

      renderHook(() => useItemDetail(defaultParams));

      await waitFor(() => {
        expect(mockGetPriceEvidence).toHaveBeenCalledWith('item-1');
      });
    });

    it('does not fetch evidence for draft items', async () => {
      renderHook(() => useItemDetail({ ...defaultParams, isDraft: true }));

      // Let async effects run
      await act(async () => {
        jest.advanceTimersByTime(0);
      });

      expect(mockGetPriceEvidence).not.toHaveBeenCalled();
    });
  });
});
