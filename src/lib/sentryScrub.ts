/**
 * Sentry PII scrubbing — strip emails, tokens, passwords, auth headers,
 * and any user-provided text fields from events before they leave the
 * device.
 *
 * Privacy nutrition labels declare we don't transmit PII for tracking.
 * The Sentry SDK's defaults can leak PII via:
 *   - Breadcrumb messages that quote URL query strings (?token=abc)
 *   - HTTP breadcrumbs that include request/response bodies
 *   - Exception messages that include user input
 *   - extras objects we attach via Sentry.captureException(e, { extra: ... })
 *
 * This module is the single chokepoint that every captured event passes
 * through. If you find PII in a Sentry event in production, the bug is
 * here.
 *
 * Whitelist for kept user data:
 *   - user.id (UUID, not email — set via Sentry.setUser({id}))
 *   - exception.type and exception.message (scrubbed for emails/tokens)
 *   - breadcrumb.category and breadcrumb.type
 *
 * Everything else (request bodies, URL query strings, form data, extras
 * named like 'email' / 'token' / 'password') is removed or redacted.
 *
 * Tests in __tests__/sentryScrub.test.ts.
 */

const EMAIL_RX = /\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b/g;
const JWT_RX = /\bey[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g;
const BEARER_RX = /\b(?:Bearer|Basic)\s+[A-Za-z0-9._\-=+/]+\b/gi;
const UUID_AS_API_KEY_RX = /\b(?:sk|pk|appl|rcat|sntry|whsec)[_-][A-Za-z0-9_-]{20,}\b/g;

const SENSITIVE_KEYS = new Set([
  'email',
  'password',
  'token',
  'auth',
  'authorization',
  'api_key',
  'apikey',
  'secret',
  'session',
  'access_token',
  'refresh_token',
  'id_token',
  'phone',
  'cookie',
  'set-cookie',
  // Forms
  'pin',
  'otp',
  'cvv',
  'card_number',
  'cardnumber',
]);

/** Replace any string-typed PII in `value` with redaction markers. */
function scrubString(value: string): string {
  if (!value) return value;
  return value
    .replace(EMAIL_RX, '[REDACTED_EMAIL]')
    .replace(JWT_RX, '[REDACTED_JWT]')
    .replace(BEARER_RX, '[REDACTED_TOKEN]')
    .replace(UUID_AS_API_KEY_RX, '[REDACTED_API_KEY]');
}

/** Deep-walk an object; redact sensitive keys, scrub string leaves. */
function scrubDeep(value: unknown, depth = 0): unknown {
  if (value == null) return value;
  if (depth > 6) return '[REDACTED_DEPTH]'; // pathological nesting guard
  if (typeof value === 'string') return scrubString(value);
  if (typeof value === 'number' || typeof value === 'boolean') return value;
  if (Array.isArray(value)) return value.map((v) => scrubDeep(v, depth + 1));
  if (typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      const lower = k.toLowerCase();
      if (SENSITIVE_KEYS.has(lower) || lower.endsWith('_email') || lower.endsWith('_token') || lower.endsWith('_password')) {
        out[k] = '[REDACTED]';
      } else {
        out[k] = scrubDeep(v, depth + 1);
      }
    }
    return out;
  }
  return value;
}

/** Scrub a Sentry event before send. */
export function scrubSentryEvent(event: Record<string, any>): Record<string, any> | null {
  if (!event || typeof event !== 'object') return event ?? null;

  // user — keep only id, drop email/ip_address/username
  if (event.user && typeof event.user === 'object') {
    event.user = { id: event.user.id };
  }

  // request — kill body + cookies + headers other than method/url-path
  if (event.request && typeof event.request === 'object') {
    const req = event.request as Record<string, any>;
    delete req.cookies;
    delete req.data;
    delete req.headers;
    if (typeof req.query_string === 'string') {
      req.query_string = scrubString(req.query_string);
    }
    if (typeof req.url === 'string') {
      // strip query string entirely — preserve only path
      req.url = req.url.split('?')[0];
    }
  }

  // contexts — keep device/os/runtime but scrub any custom contexts
  if (event.contexts && typeof event.contexts === 'object') {
    event.contexts = scrubDeep(event.contexts) as Record<string, any>;
  }

  // extras — fully scrub
  if (event.extra) {
    event.extra = scrubDeep(event.extra) as Record<string, any>;
  }
  if (event.tags) {
    event.tags = scrubDeep(event.tags) as Record<string, any>;
  }

  // exception messages — scrub for inline emails/tokens
  if (event.exception?.values && Array.isArray(event.exception.values)) {
    event.exception.values = event.exception.values.map((exc: Record<string, any>) => {
      if (typeof exc?.value === 'string') exc.value = scrubString(exc.value);
      return exc;
    });
  }

  // message — scrub
  if (typeof event.message === 'string') {
    event.message = scrubString(event.message);
  } else if (event.message?.message && typeof event.message.message === 'string') {
    event.message.message = scrubString(event.message.message);
  }

  // breadcrumbs — defensive scrub (also handled separately via beforeBreadcrumb)
  if (Array.isArray(event.breadcrumbs)) {
    event.breadcrumbs = event.breadcrumbs.map(scrubSentryBreadcrumb).filter(Boolean);
  } else if (event.breadcrumbs?.values && Array.isArray(event.breadcrumbs.values)) {
    event.breadcrumbs.values = event.breadcrumbs.values
      .map(scrubSentryBreadcrumb)
      .filter(Boolean);
  }

  return event;
}

/** Scrub a single breadcrumb. Return null to drop it entirely. */
export function scrubSentryBreadcrumb(
  breadcrumb: Record<string, any> | null,
): Record<string, any> | null {
  if (!breadcrumb || typeof breadcrumb !== 'object') return breadcrumb ?? null;

  // Drop console breadcrumbs entirely in production — too easy for a
  // logger.warn(email) to slip through. We still capture exceptions
  // separately via Sentry.captureException.
  if (breadcrumb.category === 'console') {
    return null;
  }

  // Scrub message + data
  if (typeof breadcrumb.message === 'string') {
    breadcrumb.message = scrubString(breadcrumb.message);
  }
  if (breadcrumb.data && typeof breadcrumb.data === 'object') {
    breadcrumb.data = scrubDeep(breadcrumb.data) as Record<string, any>;

    // HTTP breadcrumb: strip query string from URL
    if (typeof (breadcrumb.data as Record<string, unknown>).url === 'string') {
      const url = (breadcrumb.data as Record<string, unknown>).url as string;
      (breadcrumb.data as Record<string, unknown>).url = url.split('?')[0];
    }
  }
  return breadcrumb;
}
