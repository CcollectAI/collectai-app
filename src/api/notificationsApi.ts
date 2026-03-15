/**
 * Push notifications and notification history API methods.
 */
import { get, post, put, patch, getAuthHeaders, fetchWithRetry, parseErrorResponse, API_BASE } from "./httpClient";
import type { NotificationHistoryResponse } from "./types";

export const registerPushToken = (token: string, platform: string) =>
  post("/notifications/register", { push_token: token, platform });

export const getNotificationPreferences = () =>
  get("/notifications/preferences");

export const updateNotificationPreferences = (prefs: Record<string, boolean>) =>
  put("/notifications/preferences", prefs);

export const unregisterPushToken = async (token: string) => {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}/notifications/register`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify({ push_token: token }),
  });
  if (!res.ok) throw await parseErrorResponse("DELETE", "/notifications/register", res);
  return res.json();
};

// Notification History
export async function getNotificationHistory(params?: {
  limit?: number;
  offset?: number;
  unread_only?: boolean;
}): Promise<NotificationHistoryResponse> {
  const sp = new URLSearchParams();
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.offset) sp.set("offset", String(params.offset));
  if (params?.unread_only) sp.set("unread_only", "true");
  const qs = sp.toString();
  return get(`/notifications/history${qs ? `?${qs}` : ""}`);
}

export async function markNotificationRead(notificationId: string) {
  return patch(`/notifications/${notificationId}/read`, {});
}

export async function markAllNotificationsRead() {
  return post("/notifications/mark-all-read", {});
}
