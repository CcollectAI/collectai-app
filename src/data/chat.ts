import type { CategoryId } from './categories';
import type { UserId } from './users';

export type CategoryChatRoom = {
  id: string;          // same as categoryId for now
  categoryId: CategoryId;
  title: string;
  description: string;
};

export type CategoryChatMessage = {
  id: string;
  roomId: string;      // categoryId
  authorUserId: UserId;
  text: string;
  createdAt: string;   // ISO
};

export const CATEGORY_CHAT_ROOMS: CategoryChatRoom[] = [
  {
    id: 'pokemon',
    categoryId: 'pokemon',
    title: 'Pokémon collectors chat',
    description:
      'Talk about modern & vintage Pokémon, grails, grading, and upcoming drops.',
  },
  {
    id: 'warhammer',
    categoryId: 'warhammer',
    title: 'Warhammer minis & painting',
    description:
      'Share paint schemes, build logs, and discuss how hobby time affects collection value.',
  },
];

export const CATEGORY_CHAT_MESSAGES: CategoryChatMessage[] = [
  {
    id: 'msg-1',
    roomId: 'pokemon',
    authorUserId: 'collector-aurora',
    text: 'Anyone tracking the next wave of modern alt arts? Curious how they might affect Moonbreon prices.',
    createdAt: '2025-12-10T20:00:00Z',
  },
  {
    id: 'msg-2',
    roomId: 'pokemon',
    authorUserId: 'collector-rune',
    text: 'Watching prices closely, but I think high-end slabs will hold as long as print runs stay sane.',
    createdAt: '2025-12-10T20:10:00Z',
  },
  {
    id: 'msg-3',
    roomId: 'warhammer',
    authorUserId: 'collector-mini',
    text: 'What is everyone using to track the value of fully painted squads? Feels weird to price hours of work.',
    createdAt: '2025-12-09T18:30:00Z',
  },
];

export function getCategoryRoomById(categoryId: CategoryId | undefined | null) {
  if (!categoryId) return undefined;
  return CATEGORY_CHAT_ROOMS.find((r) => r.categoryId === categoryId);
}

export function getMessagesForRoom(roomId: string): CategoryChatMessage[] {
  return CATEGORY_CHAT_MESSAGES.filter((m) => m.roomId === roomId).sort((a, b) =>
    a.createdAt.localeCompare(b.createdAt),
  );
}
