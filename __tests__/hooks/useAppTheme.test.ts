/**
 * useAppTheme hook tests.
 *
 * Validates that the hook:
 * - Returns colors object with expected keys
 * - Returns design token objects (radius, spacing, shadow, etc.)
 * - Respects dark mode setting
 * - toggleTheme flips isDark
 */
import { renderHook, act } from '@testing-library/react-native';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockSettings = { isDark: false, hapticsEnabled: true, currency: 'EUR' };
const mockUpdateSettings = jest.fn((patch: Record<string, unknown>) => {
  mockSettings = { ...mockSettings, ...patch };
});

jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({
    settings: mockSettings,
    updateSettings: mockUpdateSettings,
    ready: true,
  }),
}));

import { useAppTheme } from '../../src/theme/useAppTheme';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockSettings = { isDark: false, hapticsEnabled: true, currency: 'EUR' };
  mockUpdateSettings.mockClear();
});

describe('useAppTheme', () => {
  it('returns colors object with expected keys', () => {
    const { result } = renderHook(() => useAppTheme());
    const { colors } = result.current;

    expect(colors).toHaveProperty('background');
    expect(colors).toHaveProperty('text');
    expect(colors).toHaveProperty('muted');
    expect(colors).toHaveProperty('border');
    expect(colors).toHaveProperty('card');
    expect(colors).toHaveProperty('accent');
    expect(colors).toHaveProperty('success');
    expect(colors).toHaveProperty('warning');
    expect(colors).toHaveProperty('danger');
    expect(colors).toHaveProperty('error');
    expect(colors).toHaveProperty('info');
    expect(colors).toHaveProperty('accentText');
    expect(colors).toHaveProperty('brand');
  });

  it('returns brand sub-object with base/dark/darker/light/lighter', () => {
    const { result } = renderHook(() => useAppTheme());
    const { colors } = result.current;

    expect(colors.brand).toHaveProperty('base');
    expect(colors.brand).toHaveProperty('dark');
    expect(colors.brand).toHaveProperty('darker');
    expect(colors.brand).toHaveProperty('light');
    expect(colors.brand).toHaveProperty('lighter');
  });

  it('returns design token objects', () => {
    const { result } = renderHook(() => useAppTheme());

    expect(result.current).toHaveProperty('radius');
    expect(result.current).toHaveProperty('spacing');
    expect(result.current).toHaveProperty('shadow');
    expect(result.current).toHaveProperty('gap');
    expect(result.current).toHaveProperty('iconSize');
    expect(result.current).toHaveProperty('fontWeight');
    expect(result.current).toHaveProperty('text');
    expect(result.current).toHaveProperty('status');
  });

  it('returns isDark=false by default (light mode)', () => {
    const { result } = renderHook(() => useAppTheme());
    expect(result.current.isDark).toBe(false);
  });

  it('returns light colors when isDark=false', () => {
    const { result } = renderHook(() => useAppTheme());
    expect(result.current.colors.background).toBe('#FFFFFF');
  });

  it('returns dark colors when isDark=true', () => {
    mockSettings = { ...mockSettings, isDark: true };
    const { result } = renderHook(() => useAppTheme());
    expect(result.current.colors.background).toBe('#020617');
    expect(result.current.isDark).toBe(true);
  });

  it('toggleTheme calls updateSettings with flipped isDark', () => {
    const { result } = renderHook(() => useAppTheme());

    act(() => {
      result.current.toggleTheme();
    });

    expect(mockUpdateSettings).toHaveBeenCalledWith({ isDark: true });
  });

  it('returns ready flag from settings', () => {
    const { result } = renderHook(() => useAppTheme());
    expect(result.current.ready).toBe(true);
  });

  it('accent color is consistent between light and dark mode', () => {
    const { result: lightResult } = renderHook(() => useAppTheme());
    const lightAccent = lightResult.current.colors.accent;

    mockSettings = { ...mockSettings, isDark: true };
    const { result: darkResult } = renderHook(() => useAppTheme());
    const darkAccent = darkResult.current.colors.accent;

    expect(lightAccent).toBe(darkAccent);
  });

  it('tier colors exist for gamification badges', () => {
    const { result } = renderHook(() => useAppTheme());
    const { tier } = result.current.colors;

    expect(tier).toHaveProperty('bronze');
    expect(tier).toHaveProperty('silver');
    expect(tier).toHaveProperty('gold');
    expect(tier).toHaveProperty('platinum');
  });
});
