/**
 * Cancelling an item edit must put the fields back, and edits must count as
 * unsaved.
 *
 * Walked on Android 2026-09-14: typing "ZZ" into the name and tapping Cancel
 * left the title reading "Rayquaza ex (Emerald 097)ZZ". The tap-to-edit pickers
 * call onSaveEdits, which writes editableName — so the next unrelated edit would
 * have saved the name the member took back. Back/swipe discarded edits with no
 * warning at all.
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

jest.mock('../../src/lib/supabase', () => ({
  supabase: {
    from: () => ({
      select: () => ({
        eq: () => ({
          single: () => Promise.resolve({ data: null, error: null }),
        }),
      }),
      update: () => ({
        eq: () => Promise.resolve({ data: null, error: null }),
      }),
    }),
  },
}));

const mockGetPriceEvidence = jest.fn().mockResolvedValue(null);
const mockGetScarcityScores = jest.fn().mockResolvedValue({ items: [] });
const mockMarketplaceComps = jest.fn().mockResolvedValue({ comps: [] });
const mockSubmitVerifiedSale = jest.fn().mockResolvedValue({});

jest.mock('../../src/api/collectorsApi', () => ({
  collectorsApi: {
    getPriceEvidence: (...args: unknown[]) => mockGetPriceEvidence(...args),
    getScarcityScores: (...args: unknown[]) => mockGetScarcityScores(...args),
    marketplaceComps: (...args: unknown[]) => mockMarketplaceComps(...args),
    submitVerifiedSale: (...args: unknown[]) => mockSubmitVerifiedSale(...args),
  },
}));

jest.mock('expo-router', () => ({
  router: { replace: jest.fn(), push: jest.fn() },
}));

// Patch Keyboard.addListener to capture callbacks (without replacing the full RN module)
jest.mock('react-native/Libraries/Components/Keyboard/Keyboard', () => ({
  __esModule: true,
  default: {
    addListener: jest.fn(() => ({ remove: jest.fn() })),
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
};


beforeEach(() => {
  jest.clearAllMocks();
  mockListItems.mockResolvedValue([]);
  mockUpdateItem.mockResolvedValue({});
});

describe('item edit cancel', () => {
  it('restores every edit field to what it held when edit mode opened', async () => {
    const { result } = renderHook(() => useItemDetail({ ...defaultParams, initialPurchasePrice: '58' }));
    act(() => { result.current.setIsEditing(true); });
    await waitFor(() => expect(result.current.isEditing).toBe(true));

    act(() => {
      result.current.setEditableName('Charizard Base SetZZ');
      result.current.setEditableCondition('Damaged');
      result.current.setEditablePurchasePrice('999');
    });
    expect(result.current.editsDirty).toBe(true);

    act(() => { result.current.cancelEdits(); });
    expect(result.current.isEditing).toBe(false);
    expect(result.current.editableName).toBe('Charizard Base Set');
    expect(result.current.editableCondition).toBe('Near Mint');
    expect(result.current.editablePurchasePrice).toBe('58');
    expect(result.current.editsDirty).toBe(false);
  });

  it('is not dirty just for opening edit mode', async () => {
    const { result } = renderHook(() => useItemDetail(defaultParams));
    act(() => { result.current.setIsEditing(true); });
    await waitFor(() => expect(result.current.isEditing).toBe(true));
    expect(result.current.editsDirty).toBe(false);
  });

  it('treats values that load while editing as the baseline, not as edits', async () => {
    // The item screen fills cost basis in when the saved row arrives. If the
    // member opened Edit first, that must not read as unsaved, and Cancel must
    // not put the blank back.
    const { result } = renderHook(() => useItemDetail({ ...defaultParams, initialPurchasePrice: '' }));
    act(() => { result.current.setIsEditing(true); });
    await waitFor(() => expect(result.current.isEditing).toBe(true));
    act(() => { result.current.adoptLoadedValues({ purchasePrice: '58', name: 'Charizard Base Set' }); });
    expect(result.current.editsDirty).toBe(false);
    act(() => { result.current.cancelEdits(); });
    expect(result.current.editablePurchasePrice).toBe('58');
  });

  it('snapshots again on the next edit session, not the first one', async () => {
    const { result } = renderHook(() => useItemDetail(defaultParams));
    act(() => { result.current.setIsEditing(true); });
    act(() => { result.current.setEditableName('Renamed'); });
    // A SAVE closes edit mode with the new value kept.
    act(() => { result.current.setIsEditing(false); });
    act(() => { result.current.setIsEditing(true); });
    act(() => { result.current.setEditableName('RenamedZZ'); });
    act(() => { result.current.cancelEdits(); });
    expect(result.current.editableName).toBe('Renamed');
  });
});
