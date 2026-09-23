/**
 * An incoming message request must show WHO sent it.
 *
 * 2026-09-22, walked on Android: a request from "Merle" rendered as "Unknown".
 * listIncomingRequests hard-coded `fromUserName: 'Unknown'` and never looked a
 * name up. It now reads the per-member profile view in one batch; a failed
 * lookup must still return the requests (with the placeholder), never hide them.
 */
const mockRequests = jest.fn();
const mockProfiles = jest.fn();
const mockProfileTable = jest.fn();
jest.mock('../../src/lib/supabase', () => ({
  supabase: {
    auth: { getSession: () => Promise.resolve({ data: { session: { user: { id: 'me' } } } }) },
    from: (table: string) => {
      if (table === 'chat_dm_requests_v1') {
        const chain = { select: () => chain, eq: () => chain, order: () => mockRequests() };
        return chain;
      }
      mockProfileTable(table);
      const chain = { select: () => chain, in: () => mockProfiles() };
      return chain;
    },
  },
}));
jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
}));

import { listIncomingRequests } from '../../src/data/providers/chatProvider';

const requests = {
  data: [
    { id: 'r1', thread_id: 't1', requester_id: 'u-merle', context: { message: 'still available?' }, created_at: '2026-09-22' },
    { id: 'r2', thread_id: 't2', requester_id: 'u-ghost', context: null, created_at: '2026-09-21' },
  ],
  error: null,
};

describe('listIncomingRequests — requester names', () => {
  beforeEach(() => jest.clearAllMocks());

  it('shows the sender name from the per-member profile view', async () => {
    mockRequests.mockResolvedValue(requests);
    mockProfiles.mockResolvedValue({
      data: [{ user_id: 'u-merle', display_handle: 'Merle', avatar_url: 'https://x/a.png' }],
      error: null,
    });
    const out = await listIncomingRequests();
    expect(out[0]).toMatchObject({ fromUserId: 'u-merle', fromUserName: 'Merle', fromUserAvatarUrl: 'https://x/a.png' });
    // A member with no public profile keeps the placeholder.
    expect(out[1].fromUserName).toBe('Unknown');
  });

  it('reads the per-member view, NOT the search view that hides non-discoverable members', async () => {
    mockRequests.mockResolvedValue(requests);
    mockProfiles.mockResolvedValue({ data: [], error: null });
    await listIncomingRequests();
    expect(mockProfileTable).toHaveBeenCalledWith('user_public_profile_v1');
    expect(mockProfileTable).not.toHaveBeenCalledWith('user_public_profiles');
  });

  it('a failed name lookup still returns every request', async () => {
    mockRequests.mockResolvedValue(requests);
    mockProfiles.mockResolvedValue({ data: null, error: { message: 'boom' } });
    const out = await listIncomingRequests();
    expect(out).toHaveLength(2);
    expect(out.map((r) => r.fromUserName)).toEqual(['Unknown', 'Unknown']);
  });
});
