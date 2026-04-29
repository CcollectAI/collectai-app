/**
 * Events domain provider — events, templates, announcements, sponsor companies, ticketing.
 */

import { API_LIMITS } from '@/constants/apiLimits';
import type { PaginationParams } from '../types';
import type { CollectorsEvent, CreateEventInput, EventTemplate, EventAnnouncement, SponsorCompany } from '../events';
import { supabase } from '../../lib/supabase';
import {
  collectorsApi,
  searchEvents as apiSearchEvents,
} from '../../api/collectorsApi';
import logger from '../../utils/logger';

// ── Helpers ────────────────────────────────────────────────────────────────────

function mapEventRow(row: Record<string, unknown>): CollectorsEvent {
  return {
    id: row.id as string,
    title: row.title as string,
    kind: row.kind as CollectorsEvent['kind'],
    date: row.date as string,
    time: (row.time as string | null) ?? undefined,
    endDate: (row.end_date as string | null) ?? undefined,
    location: (row.location as string | null) ?? undefined,
    onlineUrl: (row.online_url as string | null) ?? undefined,
    description: (row.description as string | null) ?? '',
    categoryId: (row.category_id as string | null) ?? undefined,
    hostUserId: (row.created_by as string | null) ?? undefined,
    attendeeIds: [],
    attendeeCount: (row.attendee_count as number | null) ?? 0,
    goingCount: (row.going_count as number | null) ?? 0,
    interestedCount: (row.interested_count as number | null) ?? 0,
    maxAttendees: (row.max_attendees as number | null) ?? undefined,
    isFull: (row.is_full as boolean | null) ?? false,
    isAttending: (row.is_attending as boolean | null) ?? false,
    myRsvpStatus: (row.my_rsvp_status as string | null) ?? undefined,
    source: (row.source as string | null) ?? undefined,
    sourceUrl: (row.source_url as string | null) ?? undefined,
    imageUrl: (row.image_url as string | null) ?? undefined,
    createdBy: (row.created_by as string | null) ?? undefined,
    format: (row.format as CollectorsEvent['format']) ?? undefined,
    isPublic: (row.is_public as boolean | null) ?? undefined,
    latitude: (row.latitude as number | null) ?? undefined,
    longitude: (row.longitude as number | null) ?? undefined,
    isSponsored: (row.is_sponsored as boolean | null) ?? false,
    sponsorName: (row.sponsor_name as string | null) ?? undefined,
    sponsorLogoUrl: (row.sponsor_logo_url as string | null) ?? undefined,
    sponsorTier: (row.sponsor_tier as CollectorsEvent['sponsorTier']) ?? undefined,
    sponsorCompanyId: (row.sponsor_company_id as string | null) ?? undefined,
  };
}

function mapEventApiResponse(row: Record<string, unknown>): CollectorsEvent {
  return {
    id: row.id as string,
    title: row.title as string,
    kind: row.kind as CollectorsEvent['kind'],
    date: row.date as string,
    time: (row.time as string | null) ?? undefined,
    endDate: (row.end_date as string | null) ?? undefined,
    location: (row.location as string | null) ?? undefined,
    onlineUrl: (row.online_url as string | null) ?? undefined,
    description: (row.description as string | null) ?? '',
    categoryId: (row.category_id as string | null) ?? undefined,
    hostUserId: (row.created_by as string | null) ?? undefined,
    attendeeIds: [],
    attendeeCount: (row.attendee_count as number | null) ?? 0,
    goingCount: (row.going_count as number | null) ?? 0,
    interestedCount: (row.interested_count as number | null) ?? 0,
    maxAttendees: (row.max_attendees as number | null) ?? undefined,
    isFull: (row.is_full as boolean | null) ?? false,
    isAttending: (row.user_rsvp_status as string | null) != null,
    myRsvpStatus: (row.user_rsvp_status as string | null) ?? undefined,
    source: (row.source as string | null) ?? undefined,
    imageUrl: (row.image_url as string | null) ?? undefined,
    createdBy: (row.created_by as string | null) ?? undefined,
    format: (row.format as CollectorsEvent['format']) ?? undefined,
    status: (row.status as CollectorsEvent['status']) ?? undefined,
    isPublic: (row.is_public as boolean | null) ?? undefined,
    latitude: (row.latitude as number | null) ?? undefined,
    longitude: (row.longitude as number | null) ?? undefined,
    isSponsored: (row.is_sponsored as boolean | null) ?? false,
    sponsorName: (row.sponsor_name as string | null) ?? undefined,
    sponsorLogoUrl: (row.sponsor_logo_url as string | null) ?? undefined,
    sponsorTier: (row.sponsor_tier as CollectorsEvent['sponsorTier']) ?? undefined,
    sponsorCompanyId: (row.sponsor_company_id as string | null) ?? undefined,
  };
}

function mapSponsorCompany(r: Record<string, unknown>): SponsorCompany {
  return {
    id: r.id as string,
    name: r.name as string,
    logoUrl: (r.logo_url as string | null) ?? undefined,
    websiteUrl: (r.website_url as string | null) ?? undefined,
    contactEmail: r.contact_email as string,
    description: (r.description as string | null) ?? undefined,
    adminUserId: r.admin_user_id as string,
    isVerified: (r.is_verified as boolean) ?? false,
    createdAt: (r.created_at as string | null) ?? undefined,
  };
}

// ── Events CRUD ────────────────────────────────────────────────────────────────

export async function getEventById(eventId: string): Promise<CollectorsEvent | null> {
  // v_events_with_attendees_v1 columns verified 2026-04-29 against live
  // schema. is_attending / my_rsvp_status are not on the view; mapEventRow
  // defaults them. organizer_id → created_by; cover_image_url → image_url;
  // event_date → date; venue_name → location.
  const { data, error } = await supabase
    .from('v_events_with_attendees_v1')
    .select('id, title, kind, description, category_id, date, time, end_date, ends_at, starts_at, location, online_url, image_url, created_by, status, max_attendees, attendee_count, going_count, interested_count, is_full, is_public, is_sponsored, format, latitude, longitude, source, source_url, sponsor_name, sponsor_logo_url, sponsor_tier, created_at, updated_at')
    .eq('id', eventId)
    .maybeSingle();

  if (error || !data) {
    logger.warn('[SupabaseDataProvider] getEventById error:', error);
    return null;
  }

  return mapEventRow(data);
}

// Events CRUD lives on the EC2 backend under /events/*. The Supabase
// RPC counterparts (rpc_create_event_v1, rpc_rsvp_event_v1 etc.)
// were never deployed; calls used to fail silently. mapEventApiResponse
// maps the EC2-shaped response (with user_rsvp_status etc.) instead of
// the view-shaped row.

export async function listEvents(pagination?: PaginationParams): Promise<CollectorsEvent[]> {
  const limit = pagination?.limit ?? API_LIMITS.ALERTS_DEFAULT;
  const offset = pagination?.offset ?? 0;
  try {
    const data = await collectorsApi.get<{ events?: Record<string, unknown>[] } | Record<string, unknown>[]>(
      '/events',
    );
    const rows = Array.isArray(data) ? data : ((data as { events?: Record<string, unknown>[] })?.events ?? []);
    return rows.slice(offset, offset + limit).map(mapEventApiResponse);
  } catch (e) {
    logger.warn('[SupabaseDataProvider] listEvents error:', e);
    throw e instanceof Error ? e : new Error('Failed to load events');
  }
}

export async function createEvent(input: CreateEventInput): Promise<CollectorsEvent> {
  try {
    const data = await collectorsApi.post<Record<string, unknown>>('/events', {
      title: input.title,
      kind: input.kind,
      category_id: input.categoryId ?? null,
      date: input.date,
      time: input.time ?? null,
      end_date: input.endDate ?? null,
      location: input.location ?? null,
      online_url: input.onlineUrl ?? null,
      description: input.description,
      format: input.format ?? null,
      is_public: input.isPublic ?? null,
      latitude: input.latitude ?? null,
      longitude: input.longitude ?? null,
    });
    return mapEventApiResponse(data);
  } catch (e) {
    logger.error('[SupabaseDataProvider] createEvent error:', e);
    throw e instanceof Error ? e : new Error('Failed to create event');
  }
}

export async function rsvpEvent(eventId: string, status: string = 'going'): Promise<void> {
  try {
    await collectorsApi.post(`/events/${encodeURIComponent(eventId)}/rsvp`, { status });
  } catch (e) {
    logger.error('[SupabaseDataProvider] rsvpEvent error:', e);
    throw e instanceof Error ? e : new Error('Failed to RSVP');
  }
}

export async function unrsvpEvent(eventId: string): Promise<void> {
  try {
    await collectorsApi.delete(`/events/${encodeURIComponent(eventId)}/rsvp`);
  } catch (e) {
    logger.error('[SupabaseDataProvider] unrsvpEvent error:', e);
    throw e instanceof Error ? e : new Error('Failed to un-RSVP');
  }
}

export { mapEventRow, mapEventApiResponse, mapSponsorCompany };

// shareEventViaDm depends on chat methods, so it stays in SupabaseDataProvider

// ── Event Host Actions ─────────────────────────────────────────────────────────

export async function updateEvent(eventId: string, patch: Partial<CreateEventInput & { status?: string }>): Promise<CollectorsEvent> {
  const snakePatch: Record<string, unknown> = {};
  if (patch.title !== undefined) snakePatch.title = patch.title;
  if (patch.description !== undefined) snakePatch.description = patch.description;
  if (patch.location !== undefined) snakePatch.location = patch.location;
  if (patch.onlineUrl !== undefined) snakePatch.online_url = patch.onlineUrl;
  if (patch.imageUrl !== undefined) snakePatch.image_url = patch.imageUrl;
  if (patch.date !== undefined) snakePatch.date = patch.date;
  if (patch.time !== undefined) snakePatch.time = patch.time;
  if (patch.endDate !== undefined) snakePatch.end_date = patch.endDate;
  if (patch.format !== undefined) snakePatch.format = patch.format;
  if (patch.isPublic !== undefined) snakePatch.is_public = patch.isPublic;
  if (patch.status !== undefined) snakePatch.status = patch.status;
  if (patch.maxAttendees !== undefined) snakePatch.max_attendees = patch.maxAttendees;

  const resp = await collectorsApi.patch(`/events/${eventId}`, snakePatch);
  return mapEventApiResponse(resp as Record<string, unknown>);
}

export async function cancelEvent(eventId: string): Promise<void> {
  await collectorsApi.delete(`/events/${eventId}`);
}

export async function duplicateEvent(eventId: string): Promise<CollectorsEvent> {
  const resp = await collectorsApi.post(`/events/${eventId}/duplicate`);
  return mapEventApiResponse(resp as Record<string, unknown>);
}

// ── Event Templates ────────────────────────────────────────────────────────────

export async function listEventTemplates(): Promise<EventTemplate[]> {
  const resp = await collectorsApi.get('/events/templates') as Record<string, unknown>[];
  return resp.map((r) => ({
    id: r.id as string,
    name: r.name as string,
    templateData: (r.template_data as Record<string, unknown>) ?? {},
    useCount: (r.use_count as number) ?? 0,
    createdAt: (r.created_at as string | null) ?? undefined,
  }));
}

export async function createEventTemplate(name: string, fromEventId?: string): Promise<EventTemplate> {
  const body: Record<string, unknown> = { name };
  if (fromEventId) body.from_event_id = fromEventId;
  const r = await collectorsApi.post('/events/templates', body) as Record<string, unknown>;
  return {
    id: r.id as string,
    name: r.name as string,
    templateData: (r.template_data as Record<string, unknown>) ?? {},
    useCount: (r.use_count as number) ?? 0,
    createdAt: (r.created_at as string | null) ?? undefined,
  };
}

export async function deleteEventTemplate(templateId: string): Promise<void> {
  await collectorsApi.delete(`/events/templates/${templateId}`);
}

// ── Sponsor Companies ──────────────────────────────────────────────────────────

export async function registerSponsorCompany(input: {
  name: string; logoUrl?: string; websiteUrl?: string;
  contactEmail: string; description?: string;
}): Promise<SponsorCompany> {
  const body = {
    name: input.name,
    logo_url: input.logoUrl,
    website_url: input.websiteUrl,
    contact_email: input.contactEmail,
    description: input.description,
  };
  const r = await collectorsApi.post('/sponsor-companies', body) as Record<string, unknown>;
  return mapSponsorCompany(r);
}

export async function getMySponsorCompanies(): Promise<SponsorCompany[]> {
  const resp = await collectorsApi.get('/sponsor-companies/mine') as Record<string, unknown>[];
  return resp.map((r) => mapSponsorCompany(r));
}

export async function updateSponsorCompany(id: string, patch: Partial<{
  name: string; logoUrl: string; websiteUrl: string;
  contactEmail: string; description: string;
}>): Promise<SponsorCompany> {
  const body: Record<string, unknown> = {};
  if (patch.name !== undefined) body.name = patch.name;
  if (patch.logoUrl !== undefined) body.logo_url = patch.logoUrl;
  if (patch.websiteUrl !== undefined) body.website_url = patch.websiteUrl;
  if (patch.contactEmail !== undefined) body.contact_email = patch.contactEmail;
  if (patch.description !== undefined) body.description = patch.description;
  const r = await collectorsApi.patch(`/sponsor-companies/${id}`, body) as Record<string, unknown>;
  return mapSponsorCompany(r);
}

export async function createSponsorEventCheckout(companyId: string, tier: string, eventData: CreateEventInput) {
  const body = {
    tier,
    event_title: eventData.title,
    event_kind: eventData.kind,
    event_category_id: eventData.categoryId,
    event_date: eventData.date,
    event_time: eventData.time,
    event_end_date: eventData.endDate,
    event_location: eventData.location,
    event_online_url: eventData.onlineUrl,
    event_description: eventData.description,
    event_image_url: eventData.imageUrl,
    event_format: eventData.format,
    event_max_attendees: eventData.maxAttendees,
  };
  const r = await collectorsApi.post(`/sponsor-companies/${companyId}/create-event-checkout`, body) as Record<string, unknown>;
  return {
    url: r.url as string,
    sessionId: r.session_id as string,
    eventId: r.event_id as string,
  };
}

export async function createTicketCheckout(eventId: string): Promise<{ url: string; sessionId: string }> {
  const r = await collectorsApi.post(`/events/${eventId}/ticket-checkout`) as Record<string, unknown>;
  return {
    url: r.url as string,
    sessionId: r.session_id as string,
  };
}

export async function createSponsorSubscriptionCheckout(companyId: string, tier: string): Promise<{ url: string; sessionId: string }> {
  const r = await collectorsApi.post(`/sponsor-companies/${companyId}/create-subscription-checkout`, { tier }) as Record<string, unknown>;
  return {
    url: r.url as string,
    sessionId: r.session_id as string,
  };
}

// ── Event Announcements ────────────────────────────────────────────────────────

export async function listEventAnnouncements(eventId: string): Promise<EventAnnouncement[]> {
  const resp = await collectorsApi.get(`/events/${eventId}/announcements`) as Record<string, unknown>[];
  return resp.map((r) => ({
    id: r.id as string,
    eventId: r.event_id as string,
    authorUserId: r.author_user_id as string,
    title: (r.title as string | null) ?? undefined,
    body: r.body as string,
    imageUrl: (r.image_url as string | null) ?? undefined,
    isRead: (r.is_read as boolean) ?? false,
    createdAt: (r.created_at as string | null) ?? undefined,
  }));
}

export async function postEventAnnouncement(eventId: string, body: string, title?: string, imageUrl?: string): Promise<EventAnnouncement> {
  const payload: Record<string, unknown> = { body };
  if (title) payload.title = title;
  if (imageUrl) payload.image_url = imageUrl;
  const r = await collectorsApi.post(`/events/${eventId}/announcements`, payload) as Record<string, unknown>;
  return {
    id: r.id as string,
    eventId: r.event_id as string,
    authorUserId: r.author_user_id as string,
    title: (r.title as string | null) ?? undefined,
    body: r.body as string,
    imageUrl: (r.image_url as string | null) ?? undefined,
    isRead: false,
    createdAt: (r.created_at as string | null) ?? undefined,
  };
}

export async function markAnnouncementRead(eventId: string, announcementId: string): Promise<void> {
  await collectorsApi.post(`/events/${eventId}/announcements/${announcementId}/read`);
}

export async function getUnreadAnnouncementCount(): Promise<number> {
  const r = await collectorsApi.get('/events/my-announcements/unread-count') as Record<string, unknown>;
  return (r.unread_count as number) ?? 0;
}

// ── Event Search ───────────────────────────────────────────────────────────────

export async function searchEvents(params: {
  q?: string;
  category?: string;
  eventType?: string;
  location?: string;
  upcomingOnly?: boolean;
  limit?: number;
  offset?: number;
}): Promise<CollectorsEvent[]> {
  try {
    const resp = await apiSearchEvents(params) as Record<string, unknown>;
    return ((resp.events as Record<string, unknown>[]) || []).map((e) => ({
      id: e.id as string,
      title: e.title as string,
      description: (e.description ?? '') as string,
      kind: (e.event_type ?? e.eventType ?? e.kind ?? 'meetup') as string,
      date: (e.start_date ?? e.startDate ?? e.date ?? '') as string,
      endDate: (e.end_date ?? e.endDate ?? undefined) as string | undefined,
      location: (e.location ?? '') as string,
      categoryId: (e.category ?? e.categoryId ?? undefined) as string | undefined,
      hostUserId: (e.organizer_id ?? e.organizerId ?? undefined) as string | undefined,
      attendeeIds: [],
      attendeeCount: (e.attendee_count ?? e.attendeeCount ?? 0) as number,
      interestedCount: (e.interested_count ?? e.interestedCount ?? 0) as number,
      maxAttendees: (e.max_attendees ?? e.maxAttendees ?? null) as number | null,
      isAttending: false,
    })) as CollectorsEvent[];
  } catch {
    return [];
  }
}
