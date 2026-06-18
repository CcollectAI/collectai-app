/**
 * Regression tests for the auth-header path in httpClient.
 *
 * Bug: Follow-category and Add-to-watchlist failed with 401 "Authentication
 * required" because supabase-js v2 getSession() returns the STORED session
 * without refreshing, so an expired access_token was attached verbatim.
 * readAccessToken now force-refreshes an expired token before sending.
 */

import { getAuthHeaders } from '@/api/httpClient';

const mockGetSession = jest.fn();
const mockRefreshSession = jest.fn();

// jest.mock is hoisted above the import by babel-jest, so the mock applies even
// though it's written below. The mock* vars are referenced lazily.
jest.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: () => mockGetSession(),
      refreshSession: () => mockRefreshSession(),
    },
  },
}));

const nowSec = () => Math.floor(Date.now() / 1000);

describe('getAuthHeaders — token expiry handling', () => {
  beforeEach(() => {
    mockGetSession.mockReset();
    mockRefreshSession.mockReset();
  });

  it('attaches a still-valid token as-is (no refresh)', async () => {
    mockGetSession.mockResolvedValue({
      data: { session: { access_token: 'good', expires_at: nowSec() + 3600 } },
    });
    expect(await getAuthHeaders()).toEqual({ Authorization: 'Bearer good' });
    expect(mockRefreshSession).not.toHaveBeenCalled();
  });

  it('refreshes an expired token and attaches the fresh one', async () => {
    mockGetSession.mockResolvedValue({
      data: { session: { access_token: 'stale', expires_at: nowSec() - 10 } },
    });
    mockRefreshSession.mockResolvedValue({
      data: { session: { access_token: 'fresh' } },
      error: null,
    });
    expect(await getAuthHeaders()).toEqual({ Authorization: 'Bearer fresh' });
    expect(mockRefreshSession).toHaveBeenCalledTimes(1);
  });

  it('sends NO auth header when the session is expired and refresh fails', async () => {
    mockGetSession.mockResolvedValue({
      data: { session: { access_token: 'stale', expires_at: nowSec() - 10 } },
    });
    mockRefreshSession.mockResolvedValue({
      data: { session: null },
      error: { message: 'invalid refresh token' },
    });
    // No header beats a known-401 token — caller surfaces a clean error.
    expect(await getAuthHeaders()).toEqual({});
  });

  it('sends no auth header when there is no session', async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });
    expect(await getAuthHeaders()).toEqual({});
    expect(mockRefreshSession).not.toHaveBeenCalled();
  });
});
