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
 * Android URL resolves to nothing today. Until both are live an invite link is
 * a dead link, which is why `WEBSITE_URL` is kept here: swap `inviteMessage()`
 * back to it if invites go out before launch.
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

/** The one invite message, used by every "Invite friends" control. */
export function inviteMessage(): string {
  return `Track and value your collection with me on Sparrow Collect — ${storeUrl()}`;
}
