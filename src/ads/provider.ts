/**
 * Ad Provider Abstraction
 *
 * Abstract interface for ad networks (AppLovin MAX, AdMob, etc.).
 * The app codes against this interface; the concrete provider is
 * swapped in via setAdProvider() once SDK credentials are available.
 *
 * Default: NoOpAdProvider (renders nothing, returns false for all checks).
 * This ensures zero ads appear until a real provider is wired in AND
 * the FEATURE_ADS flag is enabled.
 */

// ── Ad Types ──────────────────────────────────────────────────────────

export type AdFormat = 'banner' | 'interstitial' | 'native';

export type BannerSize = 'standard' | 'large' | 'mrec';

export interface AdConfig {
  /** AppLovin / AdMob ad unit ID */
  unitId: string;
  /** Ad format */
  format: AdFormat;
  /** Optional placement name for analytics */
  placement?: string;
}

export interface AdImpression {
  format: AdFormat;
  placement?: string;
  revenue?: number;
  network?: string;
  timestamp: number;
}

// ── Provider Interface ──────────────────────────────────────────────

export interface AdProvider {
  /** Human-readable name (e.g. "AppLovin MAX") */
  readonly name: string;

  /** Initialize the SDK. Call once at app start. */
  initialize(): Promise<boolean>;

  /** Whether the SDK is ready to serve ads */
  isInitialized(): boolean;

  /** Preload an interstitial for a given ad unit */
  loadInterstitial(unitId: string): Promise<boolean>;

  /** Show a preloaded interstitial. Returns true if shown. */
  showInterstitial(unitId: string): Promise<boolean>;

  /** Whether an interstitial is ready to show */
  isInterstitialReady(unitId: string): boolean;

  /** Called when the app receives an ad impression (for analytics) */
  onImpression?: (impression: AdImpression) => void;
}

// ── No-Op Provider (default) ────────────────────────────────────────

class NoOpAdProvider implements AdProvider {
  readonly name = 'noop';

  async initialize(): Promise<boolean> {
    return false;
  }

  isInitialized(): boolean {
    return false;
  }

  async loadInterstitial(): Promise<boolean> {
    return false;
  }

  async showInterstitial(): Promise<boolean> {
    return false;
  }

  isInterstitialReady(): boolean {
    return false;
  }
}

// ── Singleton ───────────────────────────────────────────────────────

let _provider: AdProvider = new NoOpAdProvider();

/** Get the current ad provider */
export function getAdProvider(): AdProvider {
  return _provider;
}

/** Set a concrete ad provider (call at app startup when SDK is ready) */
export function setAdProvider(provider: AdProvider): void {
  _provider = provider;
}

/** Reset to no-op (useful for testing) */
export function resetAdProvider(): void {
  _provider = new NoOpAdProvider();
}
