/**
 * Mock chat/DM domain provider.
 */

import type {
  DmThread,
  DmRequest,
  DmMessage,
  DmThreadStatus,
} from '../types';
import { logger } from '@/lib/logger';
import {
  mockDmThreads,
  mockDmRequests,
  mockDmMessages,
  mockDmStatusByUser,
} from './mockState';

export async function listInboxThreads(): Promise<DmThread[]> {
  const threads = Array.from(mockDmThreads.values())
    .filter((t) => t.status === 'accepted' || (t.status === 'pending' && !t.isIncoming))
    .sort((a, b) => {
      const aTime = a.lastMessageAt || '';
      const bTime = b.lastMessageAt || '';
      return bTime.localeCompare(aTime);
    });
  return threads;
}

export async function listIncomingRequests(): Promise<DmRequest[]> {
  return Array.from(mockDmRequests.values()).sort((a, b) =>
    b.requestedAt.localeCompare(a.requestedAt)
  );
}

export async function requestDm(toUserId: string, message?: string): Promise<string> {
  const threadId = `thread-mock-${Date.now()}`;

  const thread: DmThread = {
    id: threadId,
    otherUserId: toUserId,
    otherUserName: toUserId,
    otherUserHandle: null,
    otherUserAvatarUrl: null,
    otherUserAvatarColor: '#6b7280',
    status: 'pending',
    lastMessagePreview: message || null,
    lastMessageAt: new Date().toISOString(),
    unreadCount: 0,
    isIncoming: false,
  };

  mockDmThreads.set(threadId, thread);
  mockDmStatusByUser.set(toUserId, 'pending_outgoing');

  logger.info('[MockDataProvider] requestDm', { threadId, toUserId, message });
  return threadId;
}

export async function decideDmRequest(threadId: string, accept: boolean): Promise<void> {
  const request = mockDmRequests.get(threadId);
  if (request) {
    mockDmRequests.delete(threadId);

    if (accept) {
      const thread: DmThread = {
        id: threadId,
        otherUserId: request.fromUserId,
        otherUserName: request.fromUserName,
        otherUserHandle: request.fromUserHandle,
        otherUserAvatarUrl: request.fromUserAvatarUrl,
        otherUserAvatarColor: request.fromUserAvatarColor,
        status: 'accepted',
        lastMessagePreview: request.requestMessage,
        lastMessageAt: request.requestedAt,
        unreadCount: 1,
        isIncoming: true,
      };
      mockDmThreads.set(threadId, thread);
      mockDmStatusByUser.set(request.fromUserId, 'accepted');

      mockDmMessages.set(threadId, [{
        id: `msg-${Date.now()}`,
        threadId,
        authorUserId: request.fromUserId,
        text: request.requestMessage || 'Hi!',
        createdAt: request.requestedAt,
      }]);
    } else {
      mockDmStatusByUser.set(request.fromUserId, 'declined');
    }
  }

  logger.info('[MockDataProvider] decideDmRequest', { threadId, accept });
}

export async function markThreadRead(threadId: string): Promise<void> {
  const thread = mockDmThreads.get(threadId);
  if (thread) {
    thread.unreadCount = 0;
    mockDmThreads.set(threadId, thread);
  }
  logger.info('[MockDataProvider] markThreadRead', { threadId });
}

export async function getThreadMessages(threadId: string): Promise<DmMessage[]> {
  return mockDmMessages.get(threadId) || [];
}

export async function sendMessage(threadId: string, body: string): Promise<DmMessage> {
  const newMessage: DmMessage = {
    id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    threadId,
    authorUserId: 'collector-aurora',
    text: body,
    createdAt: new Date().toISOString(),
  };

  const existing = mockDmMessages.get(threadId) || [];
  mockDmMessages.set(threadId, [...existing, newMessage]);

  const thread = mockDmThreads.get(threadId);
  if (thread) {
    thread.lastMessagePreview = body;
    thread.lastMessageAt = newMessage.createdAt;
    mockDmThreads.set(threadId, thread);
  }

  logger.info('[MockDataProvider] sendMessage', { threadId, body, messageId: newMessage.id });
  return newMessage;
}

export async function setTyping(_threadId: string): Promise<void> {
  // No-op in mock
}

export async function clearTyping(_threadId: string): Promise<void> {
  // No-op in mock
}

export async function isOtherUserTyping(_threadId: string): Promise<boolean> {
  return false;
}

export async function getDmStatus(otherUserId: string): Promise<'none' | 'pending_outgoing' | 'pending_incoming' | 'accepted' | 'declined'> {
  return mockDmStatusByUser.get(otherUserId) || 'none';
}

export async function getInboxUnreadCount(): Promise<number> {
  const threadUnread = Array.from(mockDmThreads.values())
    .filter((t) => t.status === 'accepted')
    .reduce((sum, t) => sum + t.unreadCount, 0);
  const requestCount = mockDmRequests.size;
  return threadUnread + requestCount;
}
