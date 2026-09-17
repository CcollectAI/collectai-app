/**
 * getDmStatus must speak the DATABASE's words, and reject when it cannot read.
 *
 * 2026-09-17: rpc_decide_dm_request_v1 writes 'approved' / 'denied'; this
 * function compared against 'accepted' / 'declined'. On production 41 of 46
 * requests were 'approved' and none 'accepted', so every connected pair read as
 * 'none' — "Message" reopened the request composer, and each send filed another
 * pending request. A failed read also returned 'none', which chat/new renders
 * as the composer instead of its failed state.
 */
const mockMaybeSingle = jest.fn();
jest.mock('../../src/lib/supabase', () => ({
  supabase: {
    auth: { getUser: () => Promise.resolve({ data: { user: { id: 'me' } } }) },
    from: () => {
      const chain = {
        select: () => chain,
        or: () => chain,
        order: () => chain,
        limit: () => chain,
        maybeSingle: () => mockMaybeSingle(),
      };
      return chain;
    },
  },
}));
jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
}));

import { getDmStatus } from '../../src/data/providers/chatProvider';

const row = (status: string, requester = 'me', target = 'other') => ({
  data: { status, requester_id: requester, target_user_id: target, created_at: '2026-09-17' },
  error: null,
});

describe('getDmStatus', () => {
  beforeEach(() => jest.clearAllMocks());

  it("maps the database's 'approved' to accepted", async () => {
    mockMaybeSingle.mockResolvedValue(row('approved'));
    await expect(getDmStatus('other')).resolves.toBe('accepted');
  });

  it("maps the database's 'denied' to declined", async () => {
    mockMaybeSingle.mockResolvedValue(row('denied'));
    await expect(getDmStatus('other')).resolves.toBe('declined');
  });

  it('still accepts the legacy spellings', async () => {
    mockMaybeSingle.mockResolvedValue(row('accepted'));
    await expect(getDmStatus('other')).resolves.toBe('accepted');
    mockMaybeSingle.mockResolvedValue(row('declined'));
    await expect(getDmStatus('other')).resolves.toBe('declined');
  });

  it('pending is directional', async () => {
    mockMaybeSingle.mockResolvedValue(row('pending', 'me', 'other'));
    await expect(getDmStatus('other')).resolves.toBe('pending_outgoing');
    mockMaybeSingle.mockResolvedValue(row('pending', 'other', 'me'));
    await expect(getDmStatus('other')).resolves.toBe('pending_incoming');
  });

  it("no request row is 'none'", async () => {
    mockMaybeSingle.mockResolvedValue({ data: null, error: null });
    await expect(getDmStatus('other')).resolves.toBe('none');
  });

  it("REJECTS on a failed read — never 'none', which opens the composer", async () => {
    mockMaybeSingle.mockResolvedValue({ data: null, error: { message: 'JWT expired' } });
    await expect(getDmStatus('other')).rejects.toThrow('JWT expired');
  });
});
