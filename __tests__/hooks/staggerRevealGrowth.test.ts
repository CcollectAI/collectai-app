import { renderHook, act } from '@testing-library/react-native';
import { useStaggerReveal } from '@/motion/useStaggerReveal';

/**
 * The stranded-row regression, found on the sim 2026-08-28.
 *
 * The Items list showed a "LEGO" heading and a "Collection total EUR 900"
 * footer with a row-shaped BLANK between them. The row WAS rendering — it was
 * stuck at opacity 0, because it had been appended to the list after the first
 * stagger reveal had already run. Relaunching the app made it appear, which is
 * what identified the cause rather than the symptom.
 *
 * An item a member owns must never render invisible.
 */
describe('useStaggerReveal — items added after the first reveal', () => {
  const opacityOf = (style: unknown) =>
    // Animated.Value keeps the current value in a private field; both the
    // public getter and the field are checked so this does not silently pass
    // on a shape change.
    (style as { opacity: { __getValue?: () => number; _value?: number } }).opacity.__getValue?.()
      ?? (style as { opacity: { _value: number } }).opacity._value;

  it('does not strand a late arrival at opacity 0', () => {
    const { result, rerender } = renderHook(
      ({ count }) => useStaggerReveal({ count, enabled: true }),
      { initialProps: { count: 1 } },
    );

    // The first batch starts hidden and animates up — that is the stagger.
    // (Animated's timing engine does not advance under jest fake timers, so
    // this asserts the INVARIANT the fix is about rather than the tween: once a
    // reveal has been triggered, anything created afterwards is already
    // visible, because nothing is left that would animate it.)
    expect(opacityOf(result.current.getItemStyle(0))).toBe(0);

    // The list grows. This is the case that shipped broken: index 1 was created
    // at 0, `reveal()` had already latched, and the auto-start effect keys on
    // `count > 0` so it never re-fired. The row stayed invisible forever.
    act(() => { rerender({ count: 2 }); });

    const late = result.current.getItemStyle(1);
    expect(late).toBeDefined();
    expect(opacityOf(late)).toBe(1);
  });

  it('still hides the first batch before it animates, so the stagger is real', () => {
    const { result } = renderHook(() => useStaggerReveal({ count: 3, enabled: true, autoStart: false }));
    // autoStart off: nothing has revealed these yet, so they start hidden.
    expect(opacityOf(result.current.getItemStyle(0))).toBe(0);
  });

  it('never hides anything when animations are disabled', () => {
    const { result, rerender } = renderHook(
      ({ count }) => useStaggerReveal({ count, enabled: false }),
      { initialProps: { count: 1 } },
    );
    // Disabled returns no style at all — the row renders at its natural opacity.
    expect(result.current.getItemStyle(0)).toBeUndefined();
    rerender({ count: 2 });
    expect(result.current.getItemStyle(1)).toBeUndefined();
  });
});
