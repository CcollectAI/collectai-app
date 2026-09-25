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
export function catalogIdentityLabel(setCode?: string | null, itemKey?: string | null, title?: string | null): string | null {
  const set = setCode?.trim();
  if (!set) return null;
  const last = itemKey?.split('-').pop() ?? '';
  let num = /^[a-z]{0,3}\d{1,4}[a-z]?$/i.test(last) && last.toLowerCase() !== set.toLowerCase()
    ? last.replace(/^0+(?=\d)/, '')
    : '';
  // With a title, the number must ALSO be a card number there ("#185",
  // "SVP - 161", "4/102") and not a price: "wotc-…-psa-10-420k" is from
  // "PSA 10 ~$420K" and printed as "#420k" in search (2026-09-25).
  if (num && title && !titleHasCardNumber(title, last)) num = '';
  // A short code reads as a set ("SVP"); a slug such as "pokemon-tcg" or
  // "pokemon-collab" does not, so only the number is shown for those.
  const setLabel = /^[a-z0-9]{1,8}$/i.test(set) ? set.toUpperCase() : null;
  if (setLabel && num) return `${setLabel} · #${num}`;
  if (num) return `#${num}`;
  return setLabel;
}

/** `token` appears in the title as a number, not straight after a price sign. */
function titleHasCardNumber(title: string, token: string): boolean {
  const esc = token.replace(/^0+(?=\d)/, '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`(^|[^\\w$€£¥~.,])0*${esc}(?![\\w])`, 'i');
  return re.test(title);
}

/** Identity plus brand, without "WOTC · WOTC" when the set code IS the brand. */
export function catalogIdentityWithBrand(
  setCode?: string | null, itemKey?: string | null, title?: string | null, brand?: string | null,
): string[] {
  const identity = catalogIdentityLabel(setCode, itemKey, title);
  const sameAsSet = !!brand && !!identity && identity.split(' · ')[0].toUpperCase() === brand.trim().toUpperCase();
  return [identity, sameAsSet ? null : brand?.trim() || null].filter((x): x is string => !!x);
}
