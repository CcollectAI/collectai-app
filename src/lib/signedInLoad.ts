/**
 * May a signed-in screen load its data now? (2026-09-27)
 *
 * The tab screens are mounted under the root Stack even while the auth gate is
 * deciding where to send a member. A screen that loaded as soon as auth had
 * RESOLVED loaded for a signed-OUT member too: opened from the email-confirm
 * link, the Watchlist tab read with no user while the link's sign-in held the
 * auth lock, timed out after 5 s and greeted every new member with "Couldn't
 * load your watchlist". Signed out = wait; the screen reloads when the user id
 * arrives (its loader depends on it).
 *
 * `gateExpired` keeps the existing escape hatch: if auth never resolves, load
 * anyway rather than spin forever.
 */
export function mayLoadSignedInData(authLoading: boolean, gateExpired: boolean, hasUser: boolean): boolean {
  if (authLoading) return gateExpired;
  return hasUser;
}
