/**
 * Mock events domain provider — events, templates, sponsors, announcements.
 */

import type { CollectorsEvent, CreateEventInput, EventTemplate, EventAnnouncement, SponsorCompany } from '../events';
import { EVENTS } from '../events';
import { logger } from '@/lib/logger';
import { mockFollowedCategories, mockEventAttendees, mockSponsorCompanies } from './mockState';

export async function getEventById(eventId: string): Promise<CollectorsEvent | null> {
  const event = EVENTS.find((e) => e.id === eventId);
  return event ?? null;
}

export async function listEvents(pagination?: { limit?: number; offset?: number }): Promise<CollectorsEvent[]> {
  const followed = mockFollowedCategories;
  const all = [...EVENTS]
    .filter((e) => !e.categoryId || followed.has(e.categoryId))
    .map((e) => ({
      ...e,
      attendeeCount: e.attendeeIds?.length ?? 0,
      isAttending: mockEventAttendees.has(e.id),
      myRsvpStatus: mockEventAttendees.get(e.id),
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
  if (pagination) {
    const offset = pagination.offset ?? 0;
    const limit = pagination.limit ?? all.length;
    return all.slice(offset, offset + limit);
  }
  return all;
}

export function createEvent(input: CreateEventInput, sponsorCompanies: SponsorCompany[]): CollectorsEvent {
  const event: CollectorsEvent = {
    id: `event-mock-${Date.now()}`,
    title: input.title,
    kind: input.kind,
    date: input.date,
    time: input.time,
    endDate: input.endDate,
    location: input.location,
    onlineUrl: input.onlineUrl,
    description: input.description,
    categoryId: input.categoryId,
    hostUserId: 'collector-aurora',
    attendeeIds: ['collector-aurora'],
    attendeeCount: 1,
    isAttending: true,
    myRsvpStatus: 'going',
    source: 'user',
    createdBy: 'collector-aurora',
    format: input.format,
    isPublic: input.isPublic,
    latitude: input.latitude,
    longitude: input.longitude,
    ...(input.sponsorCompanyId ? {
      isSponsored: true,
      sponsorCompanyId: input.sponsorCompanyId,
      sponsorTier: input.sponsorTier ?? 'featured',
      sponsorName: sponsorCompanies.find((c) => c.id === input.sponsorCompanyId)?.name,
      sponsorLogoUrl: sponsorCompanies.find((c) => c.id === input.sponsorCompanyId)?.logoUrl,
    } : {}),
  };
  EVENTS.push(event);
  logger.info('[MockDataProvider] createEvent', { id: event.id, title: event.title });
  return event;
}

export async function rsvpEvent(
  eventId: string,
  status: 'going' | 'interested' | 'not_going' = 'going',
): Promise<{ status: string; waitlisted: boolean }> {
  mockEventAttendees.set(eventId, status);
  logger.info('[MockDataProvider] rsvpEvent', { eventId, status });
  return { status, waitlisted: false };
}

export async function unrsvpEvent(eventId: string): Promise<void> {
  mockEventAttendees.delete(eventId);
  logger.info('[MockDataProvider] unrsvpEvent', { eventId });
}

export async function shareEventViaDm(eventId: string, recipientUserId: string): Promise<void> {
  logger.info('[MockDataProvider] shareEventViaDm (no-op)', { eventId, recipientUserId });
}

export async function updateEvent(eventId: string, patch: Partial<CreateEventInput & { status?: string }>): Promise<CollectorsEvent> {
  const event = EVENTS.find((e) => e.id === eventId);
  if (!event) throw new Error(`Event not found: ${eventId}`);
  Object.assign(event, patch);
  logger.info('[MockDataProvider] updateEvent', { eventId });
  return event;
}

export async function cancelEvent(eventId: string): Promise<void> {
  const idx = EVENTS.findIndex((e) => e.id === eventId);
  if (idx >= 0) EVENTS.splice(idx, 1);
  logger.info('[MockDataProvider] cancelEvent', { eventId });
}

export async function duplicateEvent(eventId: string): Promise<CollectorsEvent> {
  const event = EVENTS.find((e) => e.id === eventId);
  if (!event) throw new Error(`Event not found: ${eventId}`);
  const dup: CollectorsEvent = { ...event, id: `event-dup-${Date.now()}`, title: `${event.title} (Copy)` };
  EVENTS.push(dup);
  return dup;
}

export async function listEventTemplates(): Promise<EventTemplate[]> {
  return [];
}

export async function createEventTemplate(name: string, _fromEventId?: string): Promise<EventTemplate> {
  return { id: `tpl-mock-${Date.now()}`, name, templateData: {}, useCount: 0 };
}

export async function deleteEventTemplate(_templateId: string): Promise<void> {}

export async function searchEvents(params: {
  q?: string;
  category?: string;
  eventType?: string;
  location?: string;
  upcomingOnly?: boolean;
  limit?: number;
  offset?: number;
}): Promise<CollectorsEvent[]> {
  let results = [...EVENTS];
  if (params.q) {
    const q = params.q.toLowerCase();
    results = results.filter((e) => e.title.toLowerCase().includes(q) || (e.description || '').toLowerCase().includes(q));
  }
  if (params.category) {
    results = results.filter((e) => e.categoryId === params.category);
  }
  return results.slice(params.offset || 0, (params.offset || 0) + (params.limit || 20));
}

// ─── Sponsor Companies ──────────────────────────────────────────────────────

export async function registerSponsorCompany(input: {
  name: string; logoUrl?: string; websiteUrl?: string;
  contactEmail: string; description?: string;
}): Promise<SponsorCompany> {
  const company: SponsorCompany = {
    id: `sponsor-mock-${Date.now()}`,
    name: input.name,
    logoUrl: input.logoUrl,
    websiteUrl: input.websiteUrl,
    contactEmail: input.contactEmail,
    description: input.description,
    adminUserId: 'collector-aurora',
    isVerified: false,
  };
  mockSponsorCompanies.push(company);
  return company;
}

export async function getMySponsorCompanies(): Promise<SponsorCompany[]> {
  return mockSponsorCompanies;
}

export async function updateSponsorCompany(id: string, patch: Partial<{
  name: string; logoUrl: string; websiteUrl: string;
  contactEmail: string; description: string;
}>): Promise<SponsorCompany> {
  const idx = mockSponsorCompanies.findIndex((c) => c.id === id);
  if (idx >= 0) {
    mockSponsorCompanies[idx] = { ...mockSponsorCompanies[idx], ...patch };
    return mockSponsorCompanies[idx];
  }
  return { id, name: patch.name ?? 'Mock Company', contactEmail: patch.contactEmail ?? 'mock@test.com', adminUserId: 'collector-aurora', isVerified: false };
}

export async function createSponsorEventCheckout(_companyId: string, _tier: string, _eventData: CreateEventInput): Promise<{ url: string; sessionId: string; eventId: string }> {
  const eventId = `event-sponsor-${Date.now()}`;
  return { url: '', sessionId: 'cs_demo_bypass', eventId };
}

export async function createTicketCheckout(_eventId: string): Promise<{ url: string; sessionId: string }> {
  return { url: '', sessionId: 'cs_demo_ticket' };
}

export async function createSponsorSubscriptionCheckout(_companyId: string, _tier: string): Promise<{ url: string; sessionId: string }> {
  return { url: '', sessionId: 'cs_demo_sub' };
}

// ─── Event Announcements ────────────────────────────────────────────────────

export async function listEventAnnouncements(_eventId: string): Promise<EventAnnouncement[]> {
  return [];
}

export async function postEventAnnouncement(eventId: string, body: string, title?: string, imageUrl?: string): Promise<EventAnnouncement> {
  return { id: `ann-mock-${Date.now()}`, eventId, authorUserId: 'collector-aurora', body, title, imageUrl, isRead: false };
}

export async function markAnnouncementRead(_eventId: string, _announcementId: string): Promise<void> {}

export async function getUnreadAnnouncementCount(): Promise<number> {
  return 0;
}
