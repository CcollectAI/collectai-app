/**
 * Date conversion helpers for the event form's tap-to-pick calendar.
 *
 * The form STORES dates as ISO `YYYY-MM-DD` (the backend contract) but DISPLAYS
 * them as `DD-MM-YYYY`. These helpers convert between the two and to/from the
 * native picker's Date object. All parsing/formatting is done in LOCAL time so
 * the calendar day the user taps is the day that gets stored (no UTC off-by-one).
 */

const ISO_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** 'YYYY-MM-DD' → Date at local midnight, or null if not a valid calendar date. */
export function parseIso(iso: string): Date | null {
  const m = ISO_RE.exec(iso.trim());
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const da = Number(m[3]);
  const d = new Date(y, mo - 1, da);
  if (isNaN(d.getTime())) return null;
  // Reject out-of-range values that JS Date silently rolls over (e.g. month 13,
  // or Feb 29 in a non-leap year → March 1). Better to fall back to "today" in
  // the picker than to silently store a shifted date.
  if (d.getFullYear() !== y || d.getMonth() !== mo - 1 || d.getDate() !== da) return null;
  return d;
}

/** Date → local 'YYYY-MM-DD' (what the backend expects). */
export function toIso(d: Date): string {
  const y = d.getFullYear();
  const mo = String(d.getMonth() + 1).padStart(2, '0');
  const da = String(d.getDate()).padStart(2, '0');
  return `${y}-${mo}-${da}`;
}

/** 'YYYY-MM-DD' → 'DD-MM-YYYY' for display; '' if empty/invalid. */
export function formatDMY(iso: string): string {
  const m = ISO_RE.exec(iso.trim());
  return m ? `${m[3]}-${m[2]}-${m[1]}` : '';
}

const DMY_RE = /^(\d{2})-(\d{2})-(\d{4})$/;

/**
 * 'DD-MM-YYYY' (what the user types) → ISO 'YYYY-MM-DD' (the backend contract).
 * Returns '' when empty or not a real calendar date, so a malformed entry is
 * stored as no-date rather than a shifted/garbage value.
 */
export function dmyToIso(dmy: string): string {
  const m = DMY_RE.exec(dmy.trim());
  if (!m) return '';
  const iso = `${m[3]}-${m[2]}-${m[1]}`;
  return parseIso(iso) ? iso : '';
}
