/**
 * Split a chat message into text and link segments.
 *
 * WHY THIS EXISTS
 *
 * `app/chat/[threadId].tsx` renders a message as one `<Text>{item.text}</Text>`.
 * React Native does NOT auto-link inside `<Text>` (`dataDetectorType` is
 * Android-only and applies to the whole element), so every url a member sends
 * arrives as dead characters.
 *
 * That made the share sheet half a feature: `ShareToChatSheet` puts a listing
 * into a DM as `Title — €80\nhttps://sparrowcollect.com/l/<uuid>`, and the
 * recipient could read the link but not follow it. Sending is not sharing until
 * the other end can open it.
 *
 * Pure and string-only on purpose: the routing decision (our own link → an
 * in-app route via `inAppListingHref`, anything else → the browser) belongs to
 * the caller, and this stays testable without a renderer.
 */

/**
 * Matches http(s) and our own `sparrow://` scheme.
 *
 * Trailing `.,;:!?` and a closing bracket are excluded from the match — "see
 * https://sparrowcollect.com/l/<id>." must not swallow the full stop into the
 * url, which would break `inAppListingHref`'s exact-match regex and send the
 * tap to a browser instead of the listing screen.
 */
const URL_RE = /\b(?:https?:\/\/|sparrow:\/\/)[^\s<>"']+[^\s<>"'.,;:!?)\]]/gi;

export type LinkSegment = { text: string; isLink: boolean };

export function splitTextLinks(input: string | null | undefined): LinkSegment[] {
  if (typeof input !== 'string' || input === '') return [];

  const out: LinkSegment[] = [];
  let last = 0;
  // `exec` in a loop rather than `matchAll` so the lastIndex reset below is
  // explicit: URL_RE is module-level and /g, so a leaked lastIndex would make
  // the SECOND message on screen skip its first link.
  URL_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = URL_RE.exec(input)) !== null) {
    if (m.index > last) out.push({ text: input.slice(last, m.index), isLink: false });
    out.push({ text: m[0], isLink: true });
    last = m.index + m[0].length;
  }
  if (last < input.length) out.push({ text: input.slice(last), isLink: false });
  return out;
}
