/**
 * `userErrorMessage` — every member-facing error string goes through it.
 *
 * WHY THIS TEST EXISTS (2026-09-14): toasts did `err?.message || 'Failed to …'`,
 * and an ApiError's message is "POST /purchase/mandates failed (409): …", so the
 * member read the method, path and status code. The two regressions that
 * matter: plumbing must never pass, and a sentence the server or Supabase wrote
 * for the member must never be swapped for a vaguer fallback.
 */
import { ApiError } from '@/api/httpClient';
import { TimeoutError } from '@/lib/withTimeout';
import { userErrorMessage } from '@/lib/userErrorMessage';
import { logger } from '@/lib/logger';

const FALLBACK = 'Could not save that.';

describe('userErrorMessage', () => {
  it('gives a 4xx ApiError its server-written sentence, without method, path or status', () => {
    const err = new ApiError(
      'POST',
      '/purchase/mandates',
      409,
      'Mandate limit reached (3). Upgrade your plan or delete existing mandates.',
    );
    expect(err.message).toContain('POST /purchase/mandates failed (409)'); // the leak, as built
    const out = userErrorMessage(err, FALLBACK);
    expect(out).toBe('Mandate limit reached (3). Upgrade your plan or delete existing mandates.');
    expect(out).not.toMatch(/POST|\/purchase|409/);
  });

  it("falls back when the ApiError has only the client's synthetic detail", () => {
    const err = new ApiError('POST', '/offers', 400, 'POST /offers failed');
    expect(userErrorMessage(err, FALLBACK)).toBe(FALLBACK);
  });

  it('falls back on any 5xx, whatever its detail says', () => {
    const err = new ApiError('GET', '/items', 503, 'Service temporarily unavailable');
    expect(userErrorMessage(err, FALLBACK)).toBe(FALLBACK);
  });

  it('falls back on timeouts, transport failures and Postgres text', () => {
    expect(userErrorMessage(new TimeoutError(15000, 'categories'), FALLBACK)).toBe(FALLBACK);
    expect(userErrorMessage(new Error('Request timed out after 15000ms'), FALLBACK)).toBe(FALLBACK);
    expect(userErrorMessage(new TypeError('Network request failed'), FALLBACK)).toBe(FALLBACK);
    expect(
      userErrorMessage(new Error('new row violates row-level security policy for table "items"'), FALLBACK),
    ).toBe(FALLBACK);
    expect(userErrorMessage(new Error('GET /collections/user/progress failed (500): x'), FALLBACK)).toBe(FALLBACK);
    expect(userErrorMessage(new TypeError("Cannot read property 'id' of undefined"), FALLBACK)).toBe(FALLBACK);
    // usePhotoUpload's own S3 failure: a status and an XML body, no parentheses
    expect(
      userErrorMessage(new Error('S3 upload failed with status 403: <?xml version="1.0"?><Error>'), FALLBACK),
    ).toBe(FALLBACK);
  });

  it('keeps a sentence written for the member', () => {
    expect(userErrorMessage(new Error('Invalid login credentials'), FALLBACK)).toBe('Invalid login credentials');
    expect(
      userErrorMessage(new Error('Photo upload timed out after 30s — check your connection and try again.'), FALLBACK),
    ).toBe('Photo upload timed out after 30s — check your connection and try again.');
  });

  it('falls back on non-errors and empty messages', () => {
    expect(userErrorMessage(undefined, FALLBACK)).toBe(FALLBACK);
    expect(userErrorMessage('boom', FALLBACK)).toBe(FALLBACK);
    expect(userErrorMessage(new Error('   '), FALLBACK)).toBe(FALLBACK);
  });

  describe('logLabel — the raw text must land somewhere when it is withheld', () => {
    let spy: jest.SpyInstance;
    beforeEach(() => { spy = jest.spyOn(logger, 'error').mockImplementation(() => {}); });
    afterEach(() => spy.mockRestore());

    it('logs the raw text exactly when it withholds it', () => {
      userErrorMessage(new Error('Request timed out after 15000ms'), FALLBACK, 'Items');
      expect(spy).toHaveBeenCalledTimes(1);
      expect(String(spy.mock.calls[0][0])).toContain('[Items]');
      expect(String(spy.mock.calls[0][0])).toContain('Request timed out after 15000ms');
    });

    it('does not log a sentence the member already sees (a wrong password pages no one)', () => {
      userErrorMessage(new Error('Invalid login credentials'), FALLBACK, 'Login');
      expect(spy).not.toHaveBeenCalled();
    });

    it('does not log without a label — that call site already logs, and a second event is noise', () => {
      userErrorMessage(new Error('Request timed out after 15000ms'), FALLBACK);
      expect(spy).not.toHaveBeenCalled();
    });
  });

  it('reads a Supabase error object that is not an Error instance', () => {
    expect(userErrorMessage({ message: 'duplicate key value violates unique constraint "x"' }, FALLBACK)).toBe(
      FALLBACK,
    );
    expect(userErrorMessage({ message: 'That username is taken' }, FALLBACK)).toBe('That username is taken');
  });
});
