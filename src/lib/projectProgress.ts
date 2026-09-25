/** Share of steps done, as a whole percent. */
export function stepsProgressPercent(steps: ReadonlyArray<{ isDone?: boolean | null }>): number {
  if (steps.length === 0) return 0;
  return Math.round((steps.filter((st) => !!st.isDone).length / steps.length) * 100);
}
