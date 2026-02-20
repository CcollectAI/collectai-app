/**
 * Category Chat — mock room data for category-level chat rooms.
 * Used by app/chat/category/[categoryId].tsx.
 */

export type CategoryChatMessage = {
  id: string;
  roomId: string;
  authorUserId: string;
  text: string;
  createdAt: string;
};

export type CategoryChatRoom = {
  id: string;
  categoryId: string;
  title: string;
  description: string;
};

// Mock rooms keyed by categoryId
const ROOMS: CategoryChatRoom[] = [
  {
    id: 'room-pokemon',
    categoryId: 'pokemon',
    title: 'Pokemon Collectors',
    description: 'Discuss pulls, trades, and grading tips for Pokemon TCG.',
  },
  {
    id: 'room-mtg',
    categoryId: 'mtg',
    title: 'Magic: The Gathering',
    description: 'Deck building, card values, and set releases.',
  },
  {
    id: 'room-kpop',
    categoryId: 'kpop_merch',
    title: 'K-pop Collectors',
    description: 'Photocards, albums, lightsticks, and group buys.',
  },
  {
    id: 'room-warhammer',
    categoryId: 'warhammer',
    title: 'Warhammer Enthusiasts',
    description: 'Minis, paints, books, and army lists.',
  },
  {
    id: 'room-lego',
    categoryId: 'lego',
    title: 'LEGO Builders',
    description: 'Sets, MOCs, retired sets, and investment tips.',
  },
  {
    id: 'room-funko',
    categoryId: 'funko',
    title: 'Funko Pop Collectors',
    description: 'Chases, exclusives, vaulted pops, and collection showcases.',
  },
];

// Mock messages
const MESSAGES: CategoryChatMessage[] = [
  {
    id: 'msg-1',
    roomId: 'room-pokemon',
    authorUserId: 'collector-aurora',
    text: 'Just pulled a Charizard VMAX from a random pack! 🔥',
    createdAt: '2025-12-15T10:30:00Z',
  },
  {
    id: 'msg-2',
    roomId: 'room-pokemon',
    authorUserId: 'collector-kai',
    text: 'Nice pull! Are you going to get it graded?',
    createdAt: '2025-12-15T10:45:00Z',
  },
  {
    id: 'msg-3',
    roomId: 'room-kpop',
    authorUserId: 'collector-miko',
    text: 'Anyone doing a group order for the new SEVENTEEN album?',
    createdAt: '2025-12-14T16:00:00Z',
  },
];

export function getCategoryRoomById(categoryId: string | null): CategoryChatRoom | undefined {
  if (!categoryId) return undefined;
  return ROOMS.find((r) => r.categoryId === categoryId);
}

export function getMessagesForRoom(roomId: string): CategoryChatMessage[] {
  return MESSAGES.filter((m) => m.roomId === roomId).sort(
    (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
  );
}
