/**
 * Picking a date must leave the field VALID.
 *
 * 2026-09-24, walked on Android: the first date picked showed "30-09-2026" with
 * "Date is required" beneath it and Create Event stayed disabled. The picker
 * called onChange(iso) then onBlur(), and onBlur validated the value from the
 * render BEFORE the change — still "". It now calls setValue(iso), which
 * validates the value it is given.
 */
import { renderHook, act } from '@testing-library/react-native';
import { useFormField } from '@/hooks/useFormField';
import { compose, required, dateYMD } from '@/lib/validate';

const dateValidator = compose(required('Date'), dateYMD('Date'));

describe('event date field', () => {
  it('setValue leaves a freshly picked date valid (the fix)', () => {
    const { result } = renderHook(() => useFormField(dateValidator));
    act(() => { result.current.setValue('2026-09-30'); });
    expect(result.current.value).toBe('2026-09-30');
    expect(result.current.error).toBeNull();
  });

  it('onChange then onBlur in one tick validates the STALE value (the bug)', () => {
    const { result } = renderHook(() => useFormField(dateValidator));
    act(() => {
      result.current.onChange('2026-09-30');
      result.current.onBlur();
    });
    // Pinned so the trap stays visible: this is why the picker must not do it.
    expect(result.current.error).not.toBeNull();
  });
});
