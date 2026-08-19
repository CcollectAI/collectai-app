/**
 * The paywall's diagnostic must name the cause it actually has.
 *
 * `isPurchasesAvailable()` is a boolean, and `app/subscription.tsx` turned every
 * `false` into one log line: "reason=no-key — EXPO_PUBLIC_REVENUECAT_IOS_KEY
 * missing from this build". That sentence is an assertion about the build, and
 * it was emitted in a case where it is simply untrue — when the key IS present
 * and `Purchases.configure()` throws, `configured` stays false and the screen
 * blamed a missing env var.
 *
 * It cost real time on 2026-08-17: "plans couldn't load" was triaged against
 * EAS environment variables and the App Store Connect dashboards, when the app
 * under test was a dev-client build whose eas.json profile carries no
 * RevenueCat key at all — a build that cannot sell no matter what Apple is
 * configured to do.
 *
 * A wrong diagnostic is worse than none, because it is believed. So the three
 * states are now distinct and asserted here:
 *
 *   no-key            no key for this platform in this build
 *   configure-failed  key present, the SDK rejected it — OURS
 *   ready             configured; anything after this is Apple/StoreKit
 *
 * Note the module holds `status` in module scope, so each case needs a fresh
 * module registry — a stale `ready` from a previous test would make every
 * later assertion pass for the wrong reason.
 */
const mockConfigure = jest.fn();

jest.mock('react-native-purchases', () => ({
  __esModule: true,
  default: {
    configure: (...args: unknown[]) => mockConfigure(...args),
    setLogLevel: jest.fn(),
  },
  LOG_LEVEL: { DEBUG: 'debug', WARN: 'warn' },
}));

jest.mock('@/lib/logger', () => ({
  logger: { error: jest.fn(), warn: jest.fn(), info: jest.fn() },
}));

type PurchasesModule = typeof import('@/lib/purchases');

function loadWithKey(key: string | undefined): PurchasesModule {
  let mod!: PurchasesModule;
  jest.isolateModules(() => {
    const prev = process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY;
    if (key === undefined) delete process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY;
    else process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY = key;
    mod = require('@/lib/purchases') as PurchasesModule;
    if (prev === undefined) delete process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY;
    else process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY = prev;
  });
  return mod;
}

describe('purchasesStatus distinguishes the three failures', () => {
  beforeEach(() => mockConfigure.mockReset());

  it('reports no-key when the build carries no RevenueCat key', () => {
    const mod = loadWithKey(undefined);
    mod.initPurchases();
    expect(mod.purchasesStatus()).toBe('no-key');
    expect(mod.isPurchasesAvailable()).toBe(false);
    expect(mockConfigure).not.toHaveBeenCalled();
  });

  it('reports configure-failed when a key IS present but configure() throws', () => {
    // The case that used to be reported as "key missing from this build".
    mockConfigure.mockImplementation(() => {
      throw new Error('invalid api key');
    });
    const mod = loadWithKey('appl_testkeyvalue');
    mod.initPurchases();
    expect(mod.purchasesStatus()).toBe('configure-failed');
    expect(mod.isPurchasesAvailable()).toBe(false);
  });

  it('reports ready when configure() succeeds', () => {
    const mod = loadWithKey('appl_testkeyvalue');
    mod.initPurchases();
    expect(mod.purchasesStatus()).toBe('ready');
    expect(mod.isPurchasesAvailable()).toBe(true);
  });

  it('every gated call is a no-op until configure succeeds', () => {
    // getOfferings returning null on an unconfigured SDK is what makes the
    // screen render its unavailable state instead of throwing. If a guard were
    // dropped, the native module would be called with no configuration.
    const mod = loadWithKey(undefined);
    mod.initPurchases();
    return Promise.all([
      expect(mod.getOfferings()).resolves.toBeNull(),
      expect(mod.getCustomerInfo()).resolves.toBeNull(),
      expect(mod.restorePurchases()).resolves.toBeNull(),
    ]);
  });
});

describe('the screen reads the status, not the boolean', () => {
  it('app/subscription.tsx branches on purchasesStatus()', () => {
    // A revert to `if (!isPurchasesAvailable())` compiles and passes every
    // other test, and silently restores the one-message-for-two-causes bug.
    const src = require('node:fs').readFileSync(
      require('node:path').join(__dirname, '../../app/subscription.tsx'),
      'utf8',
    ) as string;
    expect(src).toMatch(/purchasesStatus\(\)/);
    expect(src).toMatch(/reason=configure-failed/);
    expect(src).not.toMatch(/isPurchasesAvailable/);
  });
});
