/**
 * A failed block check or profile read must REJECT — never answer "no".
 *
 * 2026-09-17: `isBlocked` returned `false` on any error. chat/new already sets a
 * FAILED state when the check rejects, precisely so a failed block check never
 * reads as "you may message this collector" — but it never rejected, so that
 * branch could not run. In production the RPC was failing for every member
 * (its search_path named a schema that does not exist), so everyone read as
 * not blocked.
 *
 * `getPublicUserProfile` returned null on any error, which users/[userId]
 * renders as "collector not found" — or, on your own profile, "set a username".
 */
const mockRpc = jest.fn();
const mockMaybeSingle = jest.fn();
const mockGetUser = jest.fn();
jest.mock('../../src/lib/supabase', () => ({
  supabase: {
    rpc: (...a: unknown[]) => mockRpc(...a),
    from: () => ({ select: () => ({ eq: () => ({ maybeSingle: () => mockMaybeSingle() }) }) }),
    auth: { getUser: () => mockGetUser() },
  },
}));
jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
}));

import {
  isBlocked,
  getPublicUserProfile,
  getMyProfile,
  clearProfileCache,
} from '../../src/data/providers/userProvider';
import logger from '../../src/utils/logger';

const RELATION_MISSING = { code: '42P01', message: 'relation "user_blocks" does not exist' };

describe('isBlocked', () => {
  beforeEach(() => jest.clearAllMocks());

  it('REJECTS when the RPC fails — a failed check is not "not blocked"', async () => {
    mockRpc.mockResolvedValue({ data: null, error: RELATION_MISSING });
    await expect(isBlocked('other')).rejects.toThrow('user_blocks');
    expect(logger.error).toHaveBeenCalled();
    expect(logger.warn).not.toHaveBeenCalled();
  });

  it('answers true / false when the RPC answers', async () => {
    mockRpc.mockResolvedValue({ data: true, error: null });
    await expect(isBlocked('other')).resolves.toBe(true);
    mockRpc.mockResolvedValue({ data: false, error: null });
    await expect(isBlocked('other')).resolves.toBe(false);
  });
});

describe('getPublicUserProfile', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clearProfileCache();
  });

  it('REJECTS on a failed read — "not found" is a different answer', async () => {
    mockMaybeSingle.mockResolvedValue({ data: null, error: { code: '57014', message: 'canceling statement due to statement timeout' } });
    await expect(getPublicUserProfile('u1')).rejects.toThrow();
  });

  it('does not cache the failure: the next read tries again', async () => {
    mockMaybeSingle.mockResolvedValueOnce({ data: null, error: { code: '57014', message: 'timeout' } });
    await expect(getPublicUserProfile('u1')).rejects.toThrow();
    mockMaybeSingle.mockResolvedValueOnce({ data: { user_id: 'u1', display_handle: 'Lena' }, error: null });
    await expect(getPublicUserProfile('u1')).resolves.toMatchObject({ id: 'u1' });
  });

  it('resolves null for a member with no public profile (no row)', async () => {
    mockMaybeSingle.mockResolvedValue({ data: null, error: null });
    await expect(getPublicUserProfile('u1')).resolves.toBeNull();
  });
});

describe('getMyProfile', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clearProfileCache();
  });

  it('does not remember a signed-out answer for the rest of the session', async () => {
    mockGetUser.mockResolvedValueOnce({ data: { user: null }, error: null });
    await expect(getMyProfile()).resolves.toBeNull();
    mockGetUser.mockResolvedValueOnce({ data: { user: { id: 'u1' } }, error: null });
    mockMaybeSingle.mockResolvedValueOnce({ data: { user_id: 'u1', display_handle: 'Lena' }, error: null });
    await expect(getMyProfile()).resolves.toMatchObject({ id: 'u1' });
  });

  it('REJECTS on an auth error rather than answering "signed out"', async () => {
    mockGetUser.mockResolvedValue({ data: { user: null }, error: { message: 'network request failed' } });
    await expect(getMyProfile()).rejects.toThrow('network');
  });
});
