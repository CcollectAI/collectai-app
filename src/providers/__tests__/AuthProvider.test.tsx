/**
 * AuthProvider unit tests.
 *
 * Verifies the core auth flow contract:
 *   - Initial mount: loading=true, then resolves to session-or-null
 *   - onAuthStateChange propagates to context state
 *   - signOut clears state + calls Supabase + resets analytics
 *   - Profile loads from `profiles` table on user mount
 *   - Sentry.setUser receives only the id (PII scrub contract)
 *   - RevenueCat identifyUser fires on session change
 *
 * These tests are the contract — if you change AuthProvider behavior,
 * either the test is wrong OR a downstream caller is now broken. Both
 * are worth investigating before just updating the assertion.
 */
import React from 'react';
import { render, act, waitFor } from '@testing-library/react-native';
import { Text } from 'react-native';

import { AuthContext, AuthProvider } from '../AuthProvider';
import type { Session, User } from '@supabase/supabase-js';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockGetSession = jest.fn();
const mockSignOut = jest.fn();
const mockOnAuthStateChange = jest.fn();
const mockUnsubscribe = jest.fn();
const mockProfileSelect = jest.fn();

jest.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: () => mockGetSession(),
      signOut: () => mockSignOut(),
      onAuthStateChange: (cb: (event: string, session: Session | null) => void) =>
        mockOnAuthStateChange(cb),
    },
    from: (_table: string) => ({
      select: () => ({
        eq: () => ({
          single: () => mockProfileSelect(),
        }),
      }),
    }),
  },
}));

const mockIdentifyUser = jest.fn();
const mockResetAnalytics = jest.fn();
const mockTrack = jest.fn();
jest.mock('@/analytics/track', () => ({
  identifyUser: (...args: unknown[]) => mockIdentifyUser(...args),
  resetAnalytics: () => mockResetAnalytics(),
  track: (...args: unknown[]) => mockTrack(...args),
}));

const mockInitPurchases = jest.fn();
const mockIdentifyPurchasesUser = jest.fn((..._args: unknown[]) => Promise.resolve());
jest.mock('@/lib/purchases', () => ({
  initPurchases: () => mockInitPurchases(),
  identifyUser: (arg: unknown) => mockIdentifyPurchasesUser(arg),
}));

const mockSentrySetUser = jest.fn();
jest.mock(
  '@sentry/react-native',
  () => ({ setUser: (...args: unknown[]) => mockSentrySetUser(...args) }),
  { virtual: true },
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeUser(id = 'uuid-abc-123'): User {
  return {
    id,
    email: 'merle@example.com',
    app_metadata: {},
    user_metadata: {},
    aud: 'authenticated',
    created_at: '2026-01-01T00:00:00Z',
  } as unknown as User;
}

function makeSession(user?: User): Session {
  return {
    access_token: 'eyJabc.def.ghi',
    refresh_token: 'rt-abc',
    expires_in: 3600,
    token_type: 'bearer',
    user: user ?? makeUser(),
  } as unknown as Session;
}

function Consumer({ onValue }: { onValue: (v: unknown) => void }) {
  const value = React.useContext(AuthContext);
  React.useEffect(() => {
    onValue(value);
  }, [value, onValue]);
  return <Text>consumer</Text>;
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  mockOnAuthStateChange.mockImplementation(() => ({
    data: { subscription: { unsubscribe: mockUnsubscribe } },
  }));
  mockProfileSelect.mockResolvedValue({
    data: { id: 'uuid-abc-123', username: 'merle', created_at: '2026-01-01' },
    error: null,
  });
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AuthProvider — unauthenticated mount', () => {
  it('starts in loading state and resolves to null user when no session', async () => {
    mockGetSession.mockResolvedValueOnce({ data: { session: null }, error: null });
    const values: any[] = [];
    render(
      <AuthProvider>
        <Consumer onValue={(v) => values.push(v)} />
      </AuthProvider>,
    );
    await waitFor(() => {
      const last = values[values.length - 1];
      expect(last?.loading).toBe(false);
    });
    const final = values[values.length - 1];
    expect(final.user).toBeNull();
    expect(final.session).toBeNull();
    expect(final.profile).toBeNull();
  });

  it('calls initPurchases once on mount', async () => {
    mockGetSession.mockResolvedValueOnce({ data: { session: null }, error: null });
    render(
      <AuthProvider>
        <Text>x</Text>
      </AuthProvider>,
    );
    await waitFor(() => expect(mockInitPurchases).toHaveBeenCalledTimes(1));
  });

  it('passes only user.id to Sentry.setUser (PII scrub contract)', async () => {
    mockGetSession.mockResolvedValueOnce({ data: { session: null }, error: null });
    render(
      <AuthProvider>
        <Text>x</Text>
      </AuthProvider>,
    );
    await waitFor(() => expect(mockSentrySetUser).toHaveBeenCalled());
    expect(mockSentrySetUser).toHaveBeenCalledWith(null);
  });
});

describe('AuthProvider — authenticated mount', () => {
  it('resolves to the session user and loads profile', async () => {
    const user = makeUser('uuid-1');
    mockGetSession.mockResolvedValueOnce({
      data: { session: makeSession(user) },
      error: null,
    });
    mockProfileSelect.mockResolvedValueOnce({
      data: { id: 'uuid-1', username: 'merle', created_at: '2026-01-01' },
      error: null,
    });

    const values: any[] = [];
    render(
      <AuthProvider>
        <Consumer onValue={(v) => values.push(v)} />
      </AuthProvider>,
    );

    await waitFor(() => {
      const last = values[values.length - 1];
      expect(last?.user?.id).toBe('uuid-1');
      expect(last?.profile?.username).toBe('merle');
      expect(last?.loading).toBe(false);
    });
  });

  it('passes only {id} to Sentry.setUser when a user is present', async () => {
    const user = makeUser('uuid-2');
    mockGetSession.mockResolvedValueOnce({
      data: { session: makeSession(user) },
      error: null,
    });
    render(
      <AuthProvider>
        <Text>x</Text>
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(mockSentrySetUser).toHaveBeenCalledWith({ id: 'uuid-2' });
    });
  });

  it('calls analytics + RevenueCat identifyUser with the user id', async () => {
    const user = makeUser('uuid-3');
    mockGetSession.mockResolvedValueOnce({
      data: { session: makeSession(user) },
      error: null,
    });
    render(
      <AuthProvider>
        <Text>x</Text>
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(mockIdentifyUser).toHaveBeenCalledWith('uuid-3');
      expect(mockIdentifyPurchasesUser).toHaveBeenCalledWith('uuid-3');
    });
  });
});

describe('AuthProvider — onAuthStateChange propagation', () => {
  it('updates context when supabase fires SIGNED_IN', async () => {
    mockGetSession.mockResolvedValueOnce({ data: { session: null }, error: null });

    let stateChangeCb: ((event: string, session: Session | null) => void) | null = null;
    mockOnAuthStateChange.mockImplementation((cb) => {
      stateChangeCb = cb;
      return { data: { subscription: { unsubscribe: mockUnsubscribe } } };
    });

    const values: any[] = [];
    render(
      <AuthProvider>
        <Consumer onValue={(v) => values.push(v)} />
      </AuthProvider>,
    );

    // Wait for initial mount to settle
    await waitFor(() => expect(values[values.length - 1]?.loading).toBe(false));

    // Now simulate a SIGNED_IN event
    const newUser = makeUser('uuid-after-signin');
    mockProfileSelect.mockResolvedValueOnce({
      data: { id: 'uuid-after-signin', username: 'newuser', created_at: '2026' },
      error: null,
    });
    await act(async () => {
      await stateChangeCb!('SIGNED_IN', makeSession(newUser));
    });

    await waitFor(() => {
      const last = values[values.length - 1];
      expect(last?.user?.id).toBe('uuid-after-signin');
    });
  });

  it('clears RevenueCat identity when session goes null', async () => {
    mockGetSession.mockResolvedValueOnce({
      data: { session: makeSession(makeUser('u1')) },
      error: null,
    });
    let stateChangeCb: ((event: string, session: Session | null) => void) | null = null;
    mockOnAuthStateChange.mockImplementation((cb) => {
      stateChangeCb = cb;
      return { data: { subscription: { unsubscribe: mockUnsubscribe } } };
    });

    render(
      <AuthProvider>
        <Text>x</Text>
      </AuthProvider>,
    );
    await waitFor(() => expect(mockIdentifyPurchasesUser).toHaveBeenCalledWith('u1'));

    mockIdentifyPurchasesUser.mockClear();
    await act(async () => {
      await stateChangeCb!('SIGNED_OUT', null);
    });
    await waitFor(() => {
      expect(mockIdentifyPurchasesUser).toHaveBeenCalledWith(null);
    });
  });
});

describe('AuthProvider — signOut', () => {
  it('clears state, calls supabase.auth.signOut, tracks event', async () => {
    mockGetSession.mockResolvedValueOnce({
      data: { session: makeSession(makeUser('u-signout')) },
      error: null,
    });
    mockSignOut.mockResolvedValueOnce({ error: null });

    let ctxValue: any = null;
    render(
      <AuthProvider>
        <Consumer onValue={(v) => (ctxValue = v)} />
      </AuthProvider>,
    );
    await waitFor(() => expect(ctxValue?.user?.id).toBe('u-signout'));

    await act(async () => {
      await ctxValue.signOut();
    });

    expect(mockSignOut).toHaveBeenCalled();
    expect(mockTrack).toHaveBeenCalledWith({ name: 'user_logged_out' });
    expect(mockResetAnalytics).toHaveBeenCalled();
    await waitFor(() => expect(ctxValue?.user).toBeNull());
  });

  it('swallows signOut errors without throwing', async () => {
    mockGetSession.mockResolvedValueOnce({ data: { session: null }, error: null });
    mockSignOut.mockRejectedValueOnce(new Error('network down'));

    let ctxValue: any = null;
    render(
      <AuthProvider>
        <Consumer onValue={(v) => (ctxValue = v)} />
      </AuthProvider>,
    );
    await waitFor(() => expect(ctxValue?.loading).toBe(false));

    // Should not throw
    await expect(ctxValue.signOut()).resolves.toBeUndefined();
  });
});


describe('AuthProvider — profile load failure', () => {
  it('leaves profile null without throwing when profiles row missing', async () => {
    mockGetSession.mockResolvedValueOnce({
      data: { session: makeSession(makeUser('u-noprofile')) },
      error: null,
    });
    mockProfileSelect.mockResolvedValueOnce({
      data: null,
      error: { message: 'no rows' },
    });

    let ctxValue: any = null;
    render(
      <AuthProvider>
        <Consumer onValue={(v) => (ctxValue = v)} />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(ctxValue?.user?.id).toBe('u-noprofile');
      expect(ctxValue?.profile).toBeNull();
      expect(ctxValue?.loading).toBe(false);
    });
  });
});
