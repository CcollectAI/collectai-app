/**
 * Tests for the auth path in httpClient.
 *
 * Behaviour after the 2026-06-20 rework:
 *  - getAuthHeaders returns whatever supabase has stored (supabase-js keeps it
 *    fresh via autoRefresh); it does NOT refresh per-request (that raced and
 *    could trip refresh-token reuse detection).
 *  - Recovery is centralized: a 401 on an authenticated request triggers ONE
 *    refresh + retry; if the refresh fails the session is signed out.
 */

import { getAuthHeaders, post } from '@/api/httpClient';

const mockGetSession = jest.fn();
const mockRefreshSession = jest.fn();
const mockSignOut = jest.fn();

jest.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: () => mockGetSession(),
      refreshSession: () => mockRefreshSession(),
      signOut: () => mockSignOut(),
    },
  },
}));

const nowSec = () => Math.floor(Date.now() / 1000);
const okResp = (body: unknown) => ({ ok: true, status: 200, json: async () => body });
const unauthorizedResp = () => ({ ok: false, status: 401, json: async () => ({ detail: 'Authentication required' }) });

describe('getAuthHeaders', () => {
  beforeEach(() => {
    mockGetSession.mockReset();
    mockRefreshSession.mockReset();
    mockSignOut.mockReset();
  });

  it('attaches the stored token (does not refresh per-request)', async () => {
    mockGetSession.mockResolvedValue({
      data: { session: { access_token: 'stored', expires_at: nowSec() + 3600 } },
    });
    expect(await getAuthHeaders()).toEqual({ Authorization: 'Bearer stored' });
    expect(mockRefreshSession).not.toHaveBeenCalled();
  });

  it('returns no header when there is no session', async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });
    expect(await getAuthHeaders()).toEqual({});
  });
});

describe('401 recovery on authenticated requests', () => {
  const realFetch = global.fetch;
  beforeEach(() => {
    mockGetSession.mockReset();
    mockRefreshSession.mockReset();
    mockSignOut.mockReset();
  });
  afterAll(() => { global.fetch = realFetch; });

  it('refreshes once and retries the request with the fresh token', async () => {
    mockGetSession.mockResolvedValue({ data: { session: { access_token: 'expired' } } });
    mockRefreshSession.mockResolvedValue({ data: { session: { access_token: 'fresh' } }, error: null });
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(unauthorizedResp())
      .mockResolvedValueOnce(okResp({ id: 'w1' }));
    global.fetch = fetchMock as unknown as typeof fetch;

    const out = await post('/watchlist/mine', { name: 'x' });

    expect(mockRefreshSession).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const retryHeaders = (fetchMock.mock.calls[1][1] as RequestInit).headers as Record<string, string>;
    expect(retryHeaders.Authorization).toBe('Bearer fresh');
    expect(out).toEqual({ id: 'w1' });
    expect(mockSignOut).not.toHaveBeenCalled();
  });

  it('signs out when the refresh fails (unrecoverable session)', async () => {
    mockGetSession.mockResolvedValue({ data: { session: { access_token: 'expired' } } });
    mockRefreshSession.mockResolvedValue({ data: { session: null }, error: { message: 'refresh_token_not_found' } });
    mockSignOut.mockResolvedValue({ error: null });
    const fetchMock = jest.fn().mockResolvedValueOnce(unauthorizedResp());
    global.fetch = fetchMock as unknown as typeof fetch;

    await expect(post('/watchlist/mine', { name: 'x' })).rejects.toBeTruthy();

    expect(mockRefreshSession).toHaveBeenCalledTimes(1);
    expect(mockSignOut).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1); // no retry — session dead
  });
});
