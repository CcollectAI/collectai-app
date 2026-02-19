import type { CategoryId } from './categories';
import type { UserId } from './users';

export type EventKind = 'collection_drop' | 'meetup' | 'stream' | 'convention' | 'release';
export type EventStatus = 'draft' | 'published' | 'cancelled';

export type SponsorTier = 'featured' | 'promoted' | 'spotlight';

export type CollectorsEvent = {
  id: string;
  title: string;
  kind: EventKind;
  date: string;           // ISO date "2026-03-22"
  time?: string;          // "19:30 CET"
  endDate?: string;       // for multi-day events
  location?: string;
  onlineUrl?: string;
  description: string;
  categoryId?: string;    // was CategoryId, keep as string for flexibility
  hostUserId?: string;    // was UserId
  attendeeIds: string[];  // kept for backwards compat with mock
  attendeeCount?: number; // real count from DB
  isAttending?: boolean;  // current user's attendance status
  myRsvpStatus?: string;  // 'going' | 'interested' | null
  source?: string;        // 'user' | 'admin' | 'scraper' | 'newsletter'
  sourceUrl?: string;
  imageUrl?: string;
  createdBy?: string;
  format?: 'in_person' | 'online' | 'hybrid';
  status?: EventStatus;   // 'draft' | 'published' | 'cancelled'
  isPublic?: boolean;
  latitude?: number;
  longitude?: number;
  // Sponsor fields
  isSponsored?: boolean;
  sponsorName?: string;
  sponsorLogoUrl?: string;
  sponsorTier?: SponsorTier;
};

export type CreateEventInput = {
  title: string;
  kind: EventKind;
  categoryId?: string;
  date: string;
  time?: string;
  endDate?: string;
  location?: string;
  onlineUrl?: string;
  description: string;
  format?: 'in_person' | 'online' | 'hybrid';
  status?: EventStatus;
  isPublic?: boolean;
  imageUrl?: string;
  latitude?: number;
  longitude?: number;
};

export const EVENTS: CollectorsEvent[] = [
  {
    id: 'meetup-rotterdam-pokemon',
    title: 'Rotterdam Pokemon TCG Tournament',
    kind: 'meetup',
    date: '2026-02-08',
    time: '12:00 CET',
    location: 'Rotterdam, Netherlands - Gaming Cafe De Dobbelaar',
    description:
      'Upcoming Pokemon TCG tournament with prize support! Bring your best decks and trade binders. Side events include grading showcase and portfolio comparison.',
    categoryId: 'pokemon',
    hostUserId: 'collector-aurora',
    attendeeIds: ['collector-aurora', 'collector-rune'],
  },
  {
    id: 'drop-aurora-modern-grails',
    title: 'Aurora Modern Grails Drop',
    kind: 'collection_drop',
    date: '2025-12-21',
    time: '20:00 CET',
    onlineUrl: 'https://www.cardmarket.com',
    description:
      'Live sale of high-end modern Pokemon slabs from Aurora Modern Grails collection. Great for price discovery on chase cards.',
    categoryId: 'pokemon',
    hostUserId: 'collector-aurora',
    attendeeIds: ['collector-rune', 'collector-mini'],
  },
  {
    id: 'meetup-amsterdam-tcg',
    title: 'Amsterdam TCG & Collectors Meetup',
    kind: 'meetup',
    date: '2025-12-27',
    time: '14:00 CET',
    location: 'Amsterdam, Netherlands - central cafe (TBA)',
    description:
      'In-person meetup for TCG, Funko, and designer toy collectors. Trade, show off grails, and compare portfolios IRL.',
    categoryId: 'pokemon',
    hostUserId: 'collector-aurora',
    attendeeIds: ['collector-aurora', 'collector-rune', 'collector-mini'],
  },
  {
    id: 'stream-mini-martian-paint',
    title: 'Mini Martian Painting Stream - Plague Marines',
    kind: 'stream',
    date: '2025-12-19',
    time: '19:30 CET',
    onlineUrl: 'https://www.twitch.tv',
    description:
      'Live Warhammer painting session focused on Death Guard plague marines. Good for understanding how paint work can add value.',
    categoryId: 'warhammer',
    hostUserId: 'collector-mini',
    attendeeIds: ['collector-aurora'],
  },
];
