/**
 * eventsProvider — RSVP visibility seam.
 *
 * RSVPs were written correctly (event_attendees held real rows) and rendered
 * as if they had never happened. Four readers all returned zero, and none of
 * them errored — each produced a plausible answer:
 *
 *  - getEventById read v_events_with_attendees_v1 through supabase-js. The
 *    view is security_invoker=true and event_attendees carries a deny-all RLS
 *    policy, so the LEFT JOIN matched nothing and COALESCE(...,0) turned that
 *    into "0 going, 0 interested". It also has no user_rsvp_status column, so
 *    the RSVP buttons could add an RSVP but never show or remove one — and it
 *    bypassed the backend's is_public gate entirely.
 *  - mapEventApiResponse derived isAttending from `user_rsvp_status != null`,
 *    which labelled a `not_going` RSVP as attending and drove a button that
 *    literally renders the word "Going".
 *  - createEvent dropped image_url / ticket_price_cents / the sponsor fields
 *    before they reached the wire; Pydantic ignores unknown keys and defaults
 *    absent ones, so the POST succeeded and the data was simply gone.
 *  - rsvpEvent returned void, so the caller could not learn that the server
 *    had downgraded a 'going' on a full event to 'interested' + waitlisted.
 *
 * These pin all four. A regression here is invisible on screen, so it has to
 * be visible in CI.
 */

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockDelete = jest.fn();

jest.mock('../../src/api/collectorsApi', () => ({
  collectorsApi: {
    get: (...a: unknown[]) => mockGet(...a),
    post: (...a: unknown[]) => mockPost(...a),
    delete: (...a: unknown[]) => mockDelete(...a),
    patch: jest.fn(),
  },
  searchEvents: jest.fn(),
}));

// If any of these are ever touched again the test fails loudly rather than
// silently hitting a real client.
jest.mock('../../src/lib/supabase', () => ({
  supabase: {
    from: () => {
      throw new Error('eventsProvider must not read supabase-js directly');
    },
  },
}));

jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { error: jest.fn(), warn: jest.fn(), info: jest.fn(), debug: jest.fn() },
}));

import {
  getEventById,
  createEvent,
  rsvpEvent,
  mapEventApiResponse,
} from '../../src/data/providers/eventsProvider';

/** The shape GET /events/{id} actually returns (EventResponse). */
function apiEvent(overrides: Record<string, unknown> = {}) {
  return {
    id: 'ev-1',
    title: 'Amsterdam TCG Meetup',
    kind: 'meetup',
    date: '2026-09-01',
    description: 'Monthly meetup',
    attendee_count: 3,
    going_count: 2,
    interested_count: 1,
    is_full: false,
    max_attendees: 10,
    user_rsvp_status: null,
    ticket_price_cents: 0,
    source: 'user',
    ...overrides,
  };
}

beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();
  mockDelete.mockReset();
});

describe('getEventById — reads the backend, not the RLS-blocked view', () => {
  it('calls GET /events/{id}', async () => {
    mockGet.mockResolvedValue(apiEvent());
    await getEventById('ev-1');
    expect(mockGet).toHaveBeenCalledWith('/events/ev-1');
  });

  it('url-encodes the id', async () => {
    mockGet.mockResolvedValue(apiEvent({ id: 'a/b' }));
    await getEventById('a/b');
    expect(mockGet).toHaveBeenCalledWith('/events/a%2Fb');
  });

  it('surfaces the real going / interested counts', async () => {
    mockGet.mockResolvedValue(apiEvent());
    const ev = await getEventById('ev-1');
    // The view path returned 0/0/0 here for every signed-in user.
    expect(ev?.goingCount).toBe(2);
    expect(ev?.interestedCount).toBe(1);
    expect(ev?.attendeeCount).toBe(3);
  });

  it('surfaces the caller RSVP status so the toggle can un-RSVP', async () => {
    mockGet.mockResolvedValue(apiEvent({ user_rsvp_status: 'going' }));
    const ev = await getEventById('ev-1');
    expect(ev?.myRsvpStatus).toBe('going');
    expect(ev?.isAttending).toBe(true);
  });

  it('returns null (not a throw) when the event is missing or private', async () => {
    mockGet.mockRejectedValue(new Error('404 Event not found'));
    await expect(getEventById('nope')).resolves.toBeNull();
  });
});

describe('mapEventApiResponse — isAttending means going', () => {
  it('is true only for going', () => {
    expect(mapEventApiResponse(apiEvent({ user_rsvp_status: 'going' })).isAttending).toBe(true);
  });

  it('is false for interested — the button it drives says "Going"', () => {
    expect(mapEventApiResponse(apiEvent({ user_rsvp_status: 'interested' })).isAttending).toBe(false);
  });

  it('is false for not_going (the old `!= null` test said true)', () => {
    expect(mapEventApiResponse(apiEvent({ user_rsvp_status: 'not_going' })).isAttending).toBe(false);
  });

  it('is false when there is no RSVP', () => {
    expect(mapEventApiResponse(apiEvent()).isAttending).toBe(false);
  });

  it('carries ticket price through so paid events can reach checkout', () => {
    expect(mapEventApiResponse(apiEvent({ ticket_price_cents: 1500 })).ticketPriceCents).toBe(1500);
  });
});

describe('createEvent — every collected field reaches the wire', () => {
  it('sends image_url, ticket_price_cents, max_attendees and sponsor fields', async () => {
    mockPost.mockResolvedValue(apiEvent());
    await createEvent({
      title: 'T',
      kind: 'meetup',
      date: '2026-09-01',
      description: 'd',
      imageUrl: 'https://example.com/i.jpg',
      ticketPriceCents: 2500,
      maxAttendees: 40,
      sponsorCompanyId: 'sc-1',
      sponsorTier: 'featured',
    });
    const [path, body] = mockPost.mock.calls[0];
    expect(path).toBe('/events');
    // Each of these was dropped before reaching the server.
    expect(body.image_url).toBe('https://example.com/i.jpg');
    expect(body.ticket_price_cents).toBe(2500);
    expect(body.max_attendees).toBe(40);
    expect(body.sponsor_company_id).toBe('sc-1');
    expect(body.sponsor_tier).toBe('featured');
  });
});

describe('rsvpEvent — reports what the server actually stored', () => {
  it('returns the server status and waitlisted flag', async () => {
    // Full event: the server downgrades going -> interested and flags it.
    mockPost.mockResolvedValue({ success: true, status: 'interested', waitlisted: true });
    await expect(rsvpEvent('ev-1', 'going')).resolves.toEqual({
      status: 'interested',
      waitlisted: true,
    });
  });

  it('defaults waitlisted to false on a normal RSVP', async () => {
    mockPost.mockResolvedValue({ success: true, status: 'going', waitlisted: false });
    await expect(rsvpEvent('ev-1', 'going')).resolves.toEqual({
      status: 'going',
      waitlisted: false,
    });
  });

  it('never sends a status the API pattern rejects', async () => {
    // going|interested|not_going is the whole of RsvpRequest's pattern; the
    // detail screen used to send 'waitlist' here, which 422'd silently.
    mockPost.mockResolvedValue({ success: true, status: 'going', waitlisted: false });
    await rsvpEvent('ev-1', 'going');
    const [, body] = mockPost.mock.calls[0];
    expect(['going', 'interested', 'not_going']).toContain(body.status);
  });
});
