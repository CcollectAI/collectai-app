/**
 * Shared mock data used across screens so the app feels coherent.
 * Later we can swap this for real Supabase queries.
 */

export type CategorySummary = {
  id: string;
  name: string;
  items: number;
  value: number;
};

export type AnalyticsSummary = {
  totalValue: number;
  totalItems: number;
  watchlistCount: number;
  alertCount: number;
  avgChangePct7d: number;
};

export type TopMover = {
  id: string;
  name: string;
  category: string;
  value: number;
  changePct: number;
};

export type EventType = "twitch" | "drop" | "local";

export type CollectionEvent = {
  id: string;
  title: string;
  type: EventType;
  date: string; // ISO or friendly
  time: string;
  platform: string;
  // e.g. "Pokémon", "Funko", etc.
  tags: string[];
  // short description
  description: string;
};

export type TwitchCreator = {
  id: string;
  name: string;
  mainCategory: string;
  liveNow: boolean;
  viewers: number;
  rankThisWeek: number;
  // how relevant they are to the user's collection
  relevanceScore: number; // 0-100
  scheduleNote?: string;
};

export const MOCK_ANALYTICS_SUMMARY: AnalyticsSummary = {
  totalValue: 890, // EUR
  totalItems: 4,
  watchlistCount: 2,
  alertCount: 2,
  avgChangePct7d: 2.1,
};

export const MOCK_CATEGORY_SUMMARY: CategorySummary[] = [
  {
    id: "cat-pokemon",
    name: "Pokémon",
    items: 1,
    value: 420,
  },
  {
    id: "cat-funko",
    name: "Funko Pop",
    items: 1,
    value: 190,
  },
  {
    id: "cat-diecast",
    name: "Diecast",
    items: 1,
    value: 160,
  },
  {
    id: "cat-lego",
    name: "LEGO",
    items: 1,
    value: 120,
  },
];

export const MOCK_TOP_MOVERS: TopMover[] = [
  {
    id: "m1",
    name: "Hot Wheels RLC Skyline",
    category: "Diecast",
    value: 160,
    changePct: 5.4,
  },
  {
    id: "m2",
    name: "Charizard GX (Alt Art)",
    category: "Pokémon",
    value: 420,
    changePct: 3.8,
  },
  {
    id: "m3",
    name: "Luffy – NYCC Exclusive",
    category: "Funko Pop",
    value: 190,
    changePct: -1.2,
  },
];

export const MOCK_EVENTS: CollectionEvent[] = [
  {
    id: "ev1",
    title: "Pokémon TCG Live Box Break",
    type: "twitch",
    date: "Fri, Dec 12",
    time: "20:00 CET",
    platform: "Twitch",
    tags: ["Pokémon", "Box break"],
    description: "Live ripping Scarlet & Violet booster boxes with giveaways for viewers.",
  },
  {
    id: "ev2",
    title: "Funko Holiday Drop – Limited Vinyl",
    type: "drop",
    date: "Sat, Dec 13",
    time: "18:00 CET",
    platform: "Funko.com",
    tags: ["Funko", "Drop"],
    description: "Timed online drop with limited holiday editions and chase variants.",
  },
  {
    id: "ev3",
    title: "Local Gunpla Build Meetup",
    type: "local",
    date: "Sun, Dec 14",
    time: "14:00 CET",
    platform: "Local store (mock)",
    tags: ["Gunpla", "Meetup"],
    description: "In-store build session, bring your own kit or buy one on site.",
  },
  {
    id: "ev4",
    title: "Disney Lorcana Set 4 Preview Stream",
    type: "twitch",
    date: "Wed, Dec 17",
    time: "21:00 CET",
    platform: "Twitch",
    tags: ["Disney Lorcana", "Preview"],
    description: "Early gameplay and card reveals from upcoming Lorcana set.",
  },
];

export const MOCK_TWITCH_CREATORS: TwitchCreator[] = [
  {
    id: "tw1",
    name: "CardboardCastle",
    mainCategory: "Pokémon TCG",
    liveNow: true,
    viewers: 1123,
    rankThisWeek: 1,
    relevanceScore: 94,
    scheduleNote: "Box breaks Wed/Fri/Sun",
  },
  {
    id: "tw2",
    name: "BrickByBrickTV",
    mainCategory: "LEGO & MOCs",
    liveNow: false,
    viewers: 0,
    rankThisWeek: 2,
    relevanceScore: 88,
    scheduleNote: "Build streams Sat afternoon",
  },
  {
    id: "tw3",
    name: "MiniMetalGarage",
    mainCategory: "Diecast & RLC",
    liveNow: true,
    viewers: 327,
    rankThisWeek: 3,
    relevanceScore: 82,
    scheduleNote: "Weekly RLC hunt + trades",
  },
  {
    id: "tw4",
    name: "PopShelfStudio",
    mainCategory: "Funko & designer toys",
    liveNow: false,
    viewers: 0,
    rankThisWeek: 4,
    relevanceScore: 76,
    scheduleNote: "Shelf tours & collection audits",
  },
];
