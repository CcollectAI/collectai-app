/**
 * Notification outcome tracker.
 *
 * The push interaction (tap) tells us a user *opened* a notification, but
 * conversion data — did they actually take the action the push suggested?
 * — only surfaces in the next minute or two while the user is mid-flow.
 *
 * Pattern:
 *   1. trackTap(notification_id) is called from the push response listener.
 *   2. Subsequent user actions (item add, watchlist add, deal accept,
 *      ticket purchase) call emitOutcome(action_type, action_ref).
 *   3. emitOutcome checks the in-memory map of recent taps; if any are
 *      within OUTCOME_WINDOW_MS, fires /notifications/feedback/outcome
 *      and removes the matching tap entries.
 *
 * Best-effort: lives in process memory, lost on app kill, capped to avoid
 * unbounded growth. The backend tolerates missing or duplicate outcomes.
 */
import { recordPushOutcome } from "@/api/intelligenceApi";

const OUTCOME_WINDOW_MS = 30 * 60 * 1000; // 30 min — generous for "did this push lead to X"
const MAX_RECENT_TAPS = 20; // hard cap on map size

const recentTaps = new Map<string, number>(); // notification_id → tappedAt epoch ms

function gc(now: number): void {
  for (const [id, t] of recentTaps) {
    if (now - t > OUTCOME_WINDOW_MS) recentTaps.delete(id);
  }
  if (recentTaps.size > MAX_RECENT_TAPS) {
    // Evict oldest first — Map preserves insertion order
    const overflow = recentTaps.size - MAX_RECENT_TAPS;
    let i = 0;
    for (const id of recentTaps.keys()) {
      if (i++ >= overflow) break;
      recentTaps.delete(id);
    }
  }
}

export function trackTap(notificationId: string): void {
  if (!notificationId) return;
  const now = Date.now();
  recentTaps.set(notificationId, now);
  gc(now);
}

export function emitOutcome(
  actionType: "bought" | "followed" | "sold" | "added" | "ignored" | "other",
  actionRef?: Record<string, unknown>,
): void {
  if (recentTaps.size === 0) return;
  const now = Date.now();
  gc(now);
  // Snapshot then clear matching entries — at most 5 per emit to avoid burst
  const entries = Array.from(recentTaps.entries()).slice(0, 5);
  for (const [notificationId, tappedAt] of entries) {
    recordPushOutcome({
      notification_id: notificationId,
      outcome: actionType === "ignored" ? "ignored" : "converted",
      action_type: actionType,
      action_ref: actionRef,
      latency_seconds: Math.floor((now - tappedAt) / 1000),
    });
    recentTaps.delete(notificationId);
  }
}

// Test-only helper — not used at runtime
export function _resetForTests(): void {
  recentTaps.clear();
}
