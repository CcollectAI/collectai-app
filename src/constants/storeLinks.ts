/**
 * Where "get the app" points.
 *
 * Invite copy lived twice — CategoryHeaderCard and FriendsFollowSection had
 * byte-identical Share.share() calls — so a change to one silently left the
 * other pointing somewhere else. One source, both callers.
 *
 * ⚠️ THESE LISTINGS ARE NOT PUBLIC YET.
 * The App Store id is real (ascAppId 6767359453 in eas.json) but the app is on
 * TestFlight, not sale, and Play enrolment has not happened at all — so the
 * Android URL resolves to nothing today. Until both are live, invites use
 * `WEBSITE_URL` (STORE_LISTINGS_LIVE below).
 */
import { Platform } from 'react-native';

/** ascAppId from eas.json — the same id `eas submit` uploads against. */
export const APP_STORE_URL = 'https://apps.apple.com/app/id6767359453';

/** `android.package` from app.json. */
export const PLAY_STORE_URL =
  'https://play.google.com/store/apps/details?id=io.sparrowcollect.app';

export const WEBSITE_URL = 'https://sparrowcollect.com';

/**
 * The store for the platform the SHARER is on.
 *
 * Note the limitation: this is the sender's platform, not the recipient's, so
 * an iPhone owner inviting an Android friend sends an App Store link. A single
 * smart link on sparrowcollect.com that redirects by user-agent is the real
 * fix, and belongs on the website rather than here.
 */
export function storeUrl(): string {
  return Platform.OS === 'android' ? PLAY_STORE_URL : APP_STORE_URL;
}

/**
 * Whether the store listings are public. false until launch: both URLs above
 * returned 404 on 2026-09-26, so every invite sent until now was a dead link.
 * Flip to true once both listings resolve — check both URLs return 200 when you do.
 */
export const STORE_LISTINGS_LIVE = false;

/** The one invite message, used by every "Invite friends" control. */
export function inviteMessage(): string {
  return `Track and value your collection with me on Sparrow Collect — ${STORE_LISTINGS_LIVE ? storeUrl() : WEBSITE_URL}`;
}
