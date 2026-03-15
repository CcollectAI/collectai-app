/**
 * Events API methods: CRUD, RSVP, ticketing, announcements, templates, nearby, categories, drop alerts.
 */
import { get, post, del, patch } from "./httpClient";

// Core CRUD
export const createEvent = (payload: Record<string, unknown>) =>
  post("/events", payload);

export const getEventById = (eventId: string) =>
  get(`/events/${encodeURIComponent(eventId)}`);

export const updateEvent = (eventId: string, updates: Record<string, unknown>) =>
  patch(`/events/${encodeURIComponent(eventId)}`, updates);

export const deleteEvent = (eventId: string) =>
  del(`/events/${encodeURIComponent(eventId)}`);

export const duplicateEvent = (eventId: string) =>
  post(`/events/${encodeURIComponent(eventId)}/duplicate`);

// RSVP
export const rsvpEvent = (eventId: string, status: string = "going") =>
  post(`/events/${encodeURIComponent(eventId)}/rsvp`, { status });

export const unrsvpEvent = (eventId: string) =>
  del(`/events/${encodeURIComponent(eventId)}/rsvp`);

// Ticketing
export const createTicketCheckout = (eventId: string) =>
  post(`/events/${encodeURIComponent(eventId)}/ticket-checkout`);

// Announcements
export const listEventAnnouncements = (eventId: string) =>
  get(`/events/${encodeURIComponent(eventId)}/announcements`);

export const postEventAnnouncement = (eventId: string, payload: { body: string; title?: string; image_url?: string }) =>
  post(`/events/${encodeURIComponent(eventId)}/announcements`, payload as Record<string, unknown>);

export const markAnnouncementRead = (eventId: string, announcementId: string) =>
  post(`/events/${encodeURIComponent(eventId)}/announcements/${encodeURIComponent(announcementId)}/read`);

export const batchMarkAnnouncementsRead = (eventId: string, announcementIds: string[]) =>
  post(`/events/${encodeURIComponent(eventId)}/announcements/batch-read`, { announcement_ids: announcementIds });

export const getUnreadAnnouncementCount = () =>
  get<{ unread_count: number }>("/events/my-announcements/unread-count");

// Templates
export const listEventTemplates = () =>
  get("/events/templates");

export const createEventTemplate = (name: string, fromEventId: string) =>
  post("/events/templates", { name, from_event_id: fromEventId });

export const deleteEventTemplate = (templateId: string) =>
  del(`/events/templates/${encodeURIComponent(templateId)}`);

// Drop Alerts & Nearby & Categories
export const subscribeDropAlert = (eventId: string, notifyBeforeHours = 24) =>
  post<{
    user_id: string;
    event_id: string;
    notify_before_hours: number;
    created_at: string | null;
  }>(`/events/${encodeURIComponent(eventId)}/alert`, {
    notify_before_hours: notifyBeforeHours,
  });

export const unsubscribeDropAlert = (eventId: string) =>
  del(`/events/${encodeURIComponent(eventId)}/alert`);

export const listMyDropAlerts = () =>
  get<Array<{
    user_id: string;
    event_id: string;
    notify_before_hours: number;
    created_at: string | null;
  }>>("/events/my-alerts");

export const getNearbyEvents = (lat?: number, lng?: number, radiusKm = 50) => {
  const sp = new URLSearchParams();
  if (lat != null) sp.set("lat", String(lat));
  if (lng != null) sp.set("lng", String(lng));
  sp.set("radius_km", String(radiusKm));
  return get(`/events/nearby?${sp.toString()}`);
};

export const getFollowedEventCategories = () =>
  get<{ categories: string[] }>("/events/categories/followed");

export const followEventCategory = (categoryId: string) =>
  post(`/events/categories/${encodeURIComponent(categoryId)}/follow`);

export const unfollowEventCategory = (categoryId: string) =>
  del(`/events/categories/${encodeURIComponent(categoryId)}/follow`);
