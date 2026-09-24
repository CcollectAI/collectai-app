/**
 * The short label that tells catalog rows with the SAME title apart:
 * "SVP · #161". Search listed five pokemon "Charizard ex" as five identical
 * rows (2026-09-24), and the card they opened did not say which one it was —
 * while the identity picked there decides which listings alert the member.
 *
 * The number comes from the key's last segment ("svp-svp-161" -> "161"), and
 * only when it looks like a card number, so a non-TCG key is never mangled
 * into a fake "#...".
 */
export function catalogIdentityLabel(setCode?: string | null, itemKey?: string | null): string | null {
  const set = setCode?.trim();
  if (!set) return null;
  const last = itemKey?.split('-').pop() ?? '';
  const num = /^[a-z]{0,3}\d{1,4}[a-z]?$/i.test(last) && last.toLowerCase() !== set.toLowerCase()
    ? last.replace(/^0+(?=\d)/, '')
    : '';
  // A short code reads as a set ("SVP"); a slug such as "pokemon-tcg" or
  // "pokemon-collab" does not, so only the number is shown for those.
  const setLabel = /^[a-z0-9]{1,8}$/i.test(set) ? set.toUpperCase() : null;
  if (setLabel && num) return `${setLabel} · #${num}`;
  if (num) return `#${num}`;
  return setLabel;
}
