/**
 * Where a set/series lands in `items.attrs` (2026-09-25). Set completion
 * (`GET /sets/auto-progress`, set_router.py) reads `attrs->>'set_name'`, but
 * this form saved the category's Set field as `set` and dropped the generic
 * "Set / Series" field entirely, so a manually added card never counted
 * toward its set. Both now reach `set_name`; a Series-shaped category keeps
 * `series`.
 */
export function setAttrs(attrs: Record<string, unknown>, gameOrSeries: string): Record<string, unknown> {
  const out = { ...attrs };
  const typed = gameOrSeries.trim();
  const own = String(out.set_name ?? out.set ?? '').trim();
  if (own) out.set_name = own;
  else if (typed && out.series == null) out.set_name = typed;
  return out;
}
