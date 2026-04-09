/**
 * Tiny pluralization helper for count strings.
 *
 * Usage:
 *   pluralize(1, 'item')          → '1 item'
 *   pluralize(3, 'item')          → '3 items'
 *   pluralize(0, 'category', 'categories') → '0 categories'
 *
 * Pass an explicit plural for irregular nouns; otherwise the helper appends 's'.
 */
export function pluralize(count: number, singular: string, plural?: string): string {
  const word = count === 1 ? singular : (plural ?? `${singular}s`);
  return `${count} ${word}`;
}
