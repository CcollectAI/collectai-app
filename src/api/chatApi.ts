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

// EC2 POST /chat/threads/{id}/messages takes `content` (SendMessageRequest at
// chat_router.py:48-49) and returns `{ message: { id, thread_id, sender_id,
// body, created_at, edited_at, deleted_at } }`. Calling EC2 (instead of the
// equivalent Supabase RPC) is what fires `_notify_new_message` → push
// notification to the recipient. RPC path bypasses push entirely.
export const sendChatMessage = (threadId: string, text: string) =>
  post<{
    message: {
      id: string;
      thread_id: string;
      sender_id: string;
      body: string;
      created_at: string;
      edited_at: string | null;
      deleted_at: string | null;
    };
  }>(`/chat/threads/${threadId}/messages`, { content: text });

export const markChatThreadRead = (threadId: string) =>
  patch<{ success: boolean }>(`/chat/threads/${threadId}/read`, {});

export const deleteChatMessage = (messageId: string) =>
  del<{ success: boolean }>(`/chat/messages/${messageId}`);

// Server route is PATCH /chat/messages/{id} (chat_router.py:452); the
// EditMessageRequest model takes `content` (not `text`). FE callers
// keep the `text` arg name for ergonomic continuity; we map at the
// boundary. Verified end-to-end 2026-04-30.
export const editChatMessage = (messageId: string, text: string) =>
  patch<{ id: string; text: string; edited_at: string }>(
    `/chat/messages/${messageId}`,
    { content: text },
  );

export const getChatUnreadCount = () =>
  get<{ unread_count: number }>("/chat/unread-count");
