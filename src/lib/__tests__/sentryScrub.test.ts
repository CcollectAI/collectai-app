/**
 * Sentry PII scrub tests.
 *
 * These tests are the contract for what does + doesn't get sent to
 * Sentry. If you add a new sensitive field type, add a test here first
 * and watch it fail, then fix the scrubber until it passes.
 */
import { scrubSentryEvent, scrubSentryBreadcrumb } from '../sentryScrub';

describe('scrubSentryEvent — user identity', () => {
  it('keeps user.id, drops user.email', () => {
    const event = {
      user: { id: 'uuid-1234', email: 'merle@example.com', username: 'merle' },
    };
    const out = scrubSentryEvent(event)!;
    expect(out.user).toEqual({ id: 'uuid-1234' });
  });

  it('survives missing user', () => {
    const out = scrubSentryEvent({ exception: { values: [] } });
    expect(out).toBeTruthy();
  });
});

describe('scrubSentryEvent — request data', () => {
  it('strips query string from request.url', () => {
    const event = {
      request: { url: 'https://api.sparrowcollect.com/items?token=abc&user=me' },
    };
    const out = scrubSentryEvent(event)!;
    expect(out.request.url).toBe('https://api.sparrowcollect.com/items');
  });

  it('removes request.data, cookies, headers', () => {
    const event = {
      request: {
        url: 'https://api/foo',
        data: { email: 'merle@x.com', password: 'p' },
        cookies: { session: 'xyz' },
        headers: { Authorization: 'Bearer abc' },
      },
    };
    const out = scrubSentryEvent(event)!;
    expect(out.request.data).toBeUndefined();
    expect(out.request.cookies).toBeUndefined();
    expect(out.request.headers).toBeUndefined();
  });
});

describe('scrubSentryEvent — extras + tags', () => {
  it('redacts sensitive-keyed extras', () => {
    const event = {
      extra: {
        userId: 'safe',
        email: 'should-be-redacted@x.com',
        api_key: 'sk_live_abc',
        nested: { token: 'jwt-here', innocuous: 'hi' },
      },
    };
    const out = scrubSentryEvent(event)!;
    expect(out.extra.userId).toBe('safe');
    expect(out.extra.email).toBe('[REDACTED]');
    expect(out.extra.api_key).toBe('[REDACTED]');
    expect(out.extra.nested.token).toBe('[REDACTED]');
    expect(out.extra.nested.innocuous).toBe('hi');
  });

  it('redacts keys ending in _email / _token / _password', () => {
    const event = {
      extra: {
        user_email: 'leak@x.com',
        access_token: 'eyJabc',
        old_password: 'p',
      },
    };
    const out = scrubSentryEvent(event)!;
    expect(out.extra.user_email).toBe('[REDACTED]');
    expect(out.extra.access_token).toBe('[REDACTED]');
    expect(out.extra.old_password).toBe('[REDACTED]');
  });
});

describe('scrubSentryEvent — string-level scrubbing', () => {
  it('scrubs emails from exception messages', () => {
    const event = {
      exception: {
        values: [{ type: 'Error', value: 'Failed for merle@example.com — retry?' }],
      },
    };
    const out = scrubSentryEvent(event)!;
    expect(out.exception.values[0].value).toBe('Failed for [REDACTED_EMAIL] — retry?');
  });

  it('scrubs JWTs from string fields', () => {
    const event = {
      message: 'token expired: eyJabc.def123_-Z.ghi456_-Z please refresh',
    };
    const out = scrubSentryEvent(event)!;
    expect(out.message).toBe('token expired: [REDACTED_JWT] please refresh');
  });

  it('scrubs Bearer/Basic auth headers from strings', () => {
    const event = {
      message: 'header: Bearer abc123def_-ABC',
    };
    const out = scrubSentryEvent(event)!;
    expect(out.message).toBe('header: [REDACTED_TOKEN]');
  });

  it('scrubs known API key prefixes (sk_, pk_, appl_, etc.)', () => {
    const event = { message: 'config: sk_live_abcdefghijklmnopqrstuv' };
    const out = scrubSentryEvent(event)!;
    expect(out.message).toBe('config: [REDACTED_API_KEY]');
  });
});

describe('scrubSentryEvent — depth guard', () => {
  it('does not stack-overflow on deeply nested objects', () => {
    let nested: Record<string, unknown> = { leaf: 'merle@x.com' };
    for (let i = 0; i < 100; i++) nested = { wrap: nested };
    const event = { extra: nested };
    expect(() => scrubSentryEvent(event)).not.toThrow();
  });
});

describe('scrubSentryBreadcrumb', () => {
  it('drops console breadcrumbs entirely', () => {
    expect(scrubSentryBreadcrumb({ category: 'console', message: 'merle@x.com' })).toBeNull();
  });

  it('scrubs query strings from http breadcrumbs', () => {
    const out = scrubSentryBreadcrumb({
      category: 'http',
      data: { url: 'https://api/x?token=abc' },
    });
    expect(out!.data.url).toBe('https://api/x');
  });

  it('scrubs sensitive keys in breadcrumb.data', () => {
    const out = scrubSentryBreadcrumb({
      category: 'http',
      data: { email: 'merle@x.com', method: 'POST' },
    });
    expect(out!.data.email).toBe('[REDACTED]');
    expect(out!.data.method).toBe('POST');
  });

  it('passes innocuous breadcrumbs through', () => {
    const out = scrubSentryBreadcrumb({
      category: 'navigation',
      message: 'navigated to /items',
    });
    expect(out!.message).toBe('navigated to /items');
  });
});
