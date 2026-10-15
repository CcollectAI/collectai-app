/**
 * Check a TYPED book / product code before it is looked up (2026-10-15).
 *
 * A scanner never delivers a wrong check digit; a typed code does. Walked on
 * Android: a one-digit typo in the manual ISBN box went to /intake/barcode-only
 * (Open Library, Google Books, market lookup), then to /barcode/lookup, and
 * came back "Could not find product information" — the same words as a real
 * book we have no data for. Same rule as the server's `_gs1_check_ok`
 * (server/app/features/barcode_lookup_router.py).
 *
 * Accepted: ISBN-10 (last character may be X), and the GS1 shapes a back
 * cover can carry — EAN-13 (incl. ISBN-13) and UPC-A (12 digits).
 */
export type TypedCodeCheck = 'ok' | 'length' | 'check_digit';

export function cleanTypedCode(raw: string): string {
  return raw.replace(/[\s-]/g, '').toUpperCase();
}

export function checkTypedCode(cleaned: string): TypedCodeCheck {
  if (/^\d{9}[\dX]$/.test(cleaned)) {
    const total = cleaned
      .split('')
      .reduce((sum, ch, i) => sum + (ch === 'X' ? 10 : Number(ch)) * (10 - i), 0);
    return total % 11 === 0 ? 'ok' : 'check_digit';
  }
  if (!/^\d+$/.test(cleaned) || (cleaned.length !== 12 && cleaned.length !== 13)) return 'length';
  const digits = cleaned.split('').map(Number);
  const check = digits.pop() as number;
  // GS1: weights 3,1,3,1… counted from the digit next to the check digit.
  const total = digits.reverse().reduce((sum, d, i) => sum + d * (i % 2 === 0 ? 3 : 1), 0);
  return (10 - (total % 10)) % 10 === check ? 'ok' : 'check_digit';
}
