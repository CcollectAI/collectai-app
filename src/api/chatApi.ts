/**
 * Chat / DM API methods: threads, messages, read, unread.
 */
import { get, post, del, put, patch } from "./httpClient";

export const getChatThreads = () =>
  get<
    {
      id: string;
      other_user_id: string;
      other_user_name: string;
      other_user_avatar_url: string | null;
      status: string;
      last_message_preview: string | null;
      last_message_at: string | null;
      unread_count: number;
    }[]
  >("/chat/threads");

export const getChatMessages = (
  threadId: string,
  params?: { limit?: number; offset?: number },
) =>
  get<
    {
      id: string;
      thread_id: string;
      author_user_id: string;
      text: string;
      created_at: string;
      read_at: string | null;
    }[]
  >(
    `/chat/threads/${threadId}/messages${params ? `?limit=${params.limit ?? 50}&offset=${params.offset ?? 0}` : ""}`,
  );

export const sendChatMessage = (threadId: string, text: string) =>
  post<{
    id: string;
    thread_id: string;
    author_user_id: string;
    text: string;
    created_at: string;
  }>(`/chat/threads/${threadId}/messages`, { text });

export const markChatThreadRead = (threadId: string) =>
  patch<{ success: boolean }>(`/chat/threads/${threadId}/read`, {});

export const deleteChatMessage = (messageId: string) =>
  del<{ success: boolean }>(`/chat/messages/${messageId}`);

export const editChatMessage = (messageId: string, text: string) =>
  put<{ id: string; text: string; edited_at: string }>(
    `/chat/messages/${messageId}`,
    { text },
  );

export const getChatUnreadCount = () =>
  get<{ unread_count: number }>("/chat/unread-count");
