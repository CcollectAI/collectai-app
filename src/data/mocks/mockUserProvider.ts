/**
 * Mock user domain provider — profiles, search, blocking.
 */

import type { PublicUserProfile } from '../types';
import { logger } from '@/lib/logger';
import {
  mockBlockedUsers,
  mockDmRequests,
  mockDmStatusByUser,
} from './mockState';

const mockProfiles: Record<string, PublicUserProfile> = {
  'collector-aurora': {
    id: 'collector-aurora',
    displayName: 'Aurora',
    handle: 'aurora.cards',
    avatarUrl: null,
    bio: 'Modern + vintage Pokémon with a side of Disney Lorcana. Collecting like a portfolio, not a pile.',
    interests: ['Pokémon Cards', 'Disney Lorcana', 'Funko Pops'],
    collectionCount: 186,
    collectionValueEur: 12450,
  },
  'collector-rune': {
    id: 'collector-rune',
    displayName: 'Rune',
    handle: 'rune.mtgguy',
    avatarUrl: null,
    bio: 'MTG reserve list and Flesh and Blood legendaries. Plays Commander, collects like a CFO.',
    interests: ['Magic: The Gathering', 'Flesh and Blood'],
    collectionCount: 210,
    collectionValueEur: 18400,
  },
  'collector-mini': {
    id: 'collector-mini',
    displayName: 'Mini Martian',
    handle: 'mini.martian',
    avatarUrl: null,
    bio: 'Warhammer and Gunpla painter. Tracks hobby time and build value as part of the portfolio.',
    interests: ['Warhammer Minis', 'Gunpla & Model Kits'],
    collectionCount: 95,
    collectionValueEur: 6200,
  },
};

const allSearchProfiles: PublicUserProfile[] = [
  mockProfiles['collector-aurora'],
  mockProfiles['collector-rune'],
  mockProfiles['collector-mini'],
  {
    id: 'collector-alex',
    displayName: 'Alex TCG',
    handle: 'alex.tcg',
    avatarUrl: null,
    bio: 'Trading card games enthusiast.',
    interests: ['Pokemon Cards', 'Magic: The Gathering'],
    collectionCount: 340,
    collectionValueEur: 22000,
  },
  {
    id: 'collector-kai',
    displayName: 'Kai Bricks',
    handle: 'kai.bricks',
    avatarUrl: null,
    bio: 'LEGO builder and collector.',
    interests: ['LEGO', 'Hot Wheels'],
    collectionCount: 120,
    collectionValueEur: 8900,
  },
];

export async function getPublicUserProfile(userId: string): Promise<PublicUserProfile | null> {
  return mockProfiles[userId] ?? null;
}

export async function getMyProfile(): Promise<PublicUserProfile | null> {
  return getPublicUserProfile('collector-aurora');
}

export async function searchUsers(query: string): Promise<PublicUserProfile[]> {
  if (!query.trim()) return [];

  const lowerQuery = query.toLowerCase();

  return allSearchProfiles.filter(
    (p) =>
      p.displayName.toLowerCase().includes(lowerQuery) ||
      (p.handle && p.handle.toLowerCase().includes(lowerQuery))
  );
}

export async function blockUser(userId: string): Promise<void> {
  mockBlockedUsers.add(userId);
  for (const [threadId, req] of mockDmRequests.entries()) {
    if (req.fromUserId === userId) {
      mockDmRequests.delete(threadId);
      mockDmStatusByUser.set(userId, 'declined');
    }
  }
  logger.info('[MockDataProvider] blockUser', { userId });
}

export async function unblockUser(userId: string): Promise<void> {
  mockBlockedUsers.delete(userId);
  logger.info('[MockDataProvider] unblockUser', { userId });
}

export async function listBlockedUsers(): Promise<{ id: string; name: string }[]> {
  const results: { id: string; name: string }[] = [];
  for (const userId of mockBlockedUsers) {
    const profile = await getPublicUserProfile(userId);
    results.push({ id: userId, name: profile?.displayName ?? 'Unknown' });
  }
  return results;
}

export async function isBlocked(userId: string): Promise<boolean> {
  return mockBlockedUsers.has(userId);
}
