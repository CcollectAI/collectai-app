/**
 * Shared API and utility types used across the frontend codebase.
 * Avoids 'any' by providing concrete shapes for common patterns.
 */

/** Helper to extract error message from unknown catch clause values */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  if (
    error !== null &&
    typeof error === 'object' &&
    'message' in error &&
    typeof (error as { message: unknown }).message === 'string'
  ) {
    return (error as { message: string }).message;
  }
  return String(error);
}

/** Supabase/Postgres error shape (for code-based checks) */
export interface PostgresError {
  message: string;
  code?: string;
  details?: string;
  hint?: string;
}

/** Check if an unknown error has a Postgres-style code */
export function hasPostgresCode(
  error: unknown,
  code: string,
): boolean {
  if (
    error !== null &&
    typeof error === 'object' &&
    'code' in error &&
    (error as { code: unknown }).code === code
  ) {
    return true;
  }
  return false;
}

/** Shape of a marketplace search hit from the edge function */
export interface MarketplaceSearchHit {
  price_eur: number;
  [key: string]: unknown;
}

/** Shape returned by the add-prefill edge function */
export interface PrefillData {
  title: string | null;
  category: string;
  guess_confidence: number;
  attrs: Record<string, unknown>;
}

/** Shape returned by the predict-price edge function */
export interface PredictPriceResult {
  ok: true;
  price_eur: number;
}

/** Prediction session shape from predict-sessions edge function */
export interface PredictionSession {
  id: string;
  category: string;
  status: string;
  prediction?: {
    name?: string;
    estimated_low?: number;
    estimated_mid?: number;
    estimated_high?: number;
    currency?: string;
    confidence?: number;
  };
  [key: string]: unknown;
}

/** Calendar entry from expo-calendar */
export interface ExpoCalendarEntry {
  id: string;
  source?: { type: string };
  allowsModifications: boolean;
  isPrimary?: boolean;
}

/** Raw item from the collectors API client for portfolio analytics */
export interface RawPortfolioTimeseriesPoint {
  t?: string;
  timestamp?: string;
  v?: number;
  value?: number;
}

export interface RawPortfolioTimeseriesResponse {
  points?: RawPortfolioTimeseriesPoint[];
  [key: string]: unknown;
}

export interface RawPortfolioItem {
  id?: string;
  item_id?: string;
  name?: string;
  title?: string;
  category?: string;
  category_slug?: string;
  collection?: string;
  set_name?: string;
  quantity?: number;
  current_value?: number;
  estimated_value?: number;
  value?: number;
  cost_basis?: number;
  realized_pl?: number;
  unrealized_pl?: number;
  change_1d_pct?: number;
  change_7d_pct?: number;
  liquidity_score?: number;
  rarity_score?: number;
  completeness_score?: number;
  fraud_risk_score?: number;
  purchasePrice?: number;
  [key: string]: unknown;
}

export interface RawPortfolioItemsResponse {
  items?: RawPortfolioItem[];
  [key: string]: unknown;
}

export interface RawPortfolioSet {
  set_id?: string;
  id?: string;
  set_name?: string;
  name?: string;
  owned_count?: number;
  owned?: number;
  total_count?: number;
  total?: number;
}

export interface RawPortfolioOverviewResponse {
  sets?: RawPortfolioSet[];
  set_completion?: RawPortfolioSet[];
  [key: string]: unknown;
}

/** Expo-haptics module shape (for optional dependency) */
export interface ExpoHapticsModule {
  impactAsync: (style: unknown) => Promise<void>;
  notificationAsync: (type: unknown) => Promise<void>;
  selectionAsync: () => Promise<void>;
  ImpactFeedbackStyle: {
    Light: unknown;
    Medium: unknown;
    Heavy: unknown;
  };
  NotificationFeedbackType: {
    Success: unknown;
    Warning: unknown;
    Error: unknown;
  };
}

/** Sentry module shape (for optional dependency) */
export interface SentryModule {
  setUser: (user: { id: string } | null) => void;
  captureException: (error: Error, extra?: { extra?: Record<string, unknown> }) => void;
}

/** Collectors API client shape (for optional dependency in analytics store) */
export interface CollectorsClient {
  getPortfolioTimeseries?: () => Promise<RawPortfolioTimeseriesResponse | RawPortfolioTimeseriesPoint[] | null>;
  getPortfolioItems?: () => Promise<RawPortfolioItemsResponse | RawPortfolioItem[] | null>;
  getPortfolioOverview?: () => Promise<RawPortfolioOverviewResponse | null>;
}

/** Items with extended fields that may come from different sources */
export interface ExtendedPortfolioItem {
  id: string;
  name: string;
  category: string;
  currentValue: number;
  costBasis?: number;
  purchasePrice?: number;
  estimatedValue?: number;
  change1dPct?: number;
  change7dPct?: number;
  collection?: string;
  quantity?: number;
  realizedPL?: number;
  unrealizedPL?: number;
  liquidityScore?: number;
  rarityScore?: number;
  completenessScore?: number;
  fraudRiskScore?: number;
}

/** Route params for screen components using React Navigation */
export interface ListingDetailRouteParams {
  listing: {
    id: string;
    title: string;
    price: number;
    currency: string;
    seller_id: string;
    image_url?: string;
    condition?: string;
    description?: string;
  };
}

export interface PostDetailRouteParams {
  post: {
    id: string;
    content: string;
  };
}

/** Import summary for batch import result */
export interface ImportSummary {
  total: number;
  success: number;
  failed: number;
  errors?: string[];
}

/** Item with optional blurhash for image placeholders */
export interface ItemWithBlurhash {
  blurhash?: string;
  [key: string]: unknown;
}

/** Collection status input used for sets-to-complete and items-status */
export interface CollectionStatusInput {
  id: string;
  title: string;
  owned: boolean;
  [key: string]: unknown;
}

/** Raw collection status item from API */
export interface RawCollectionStatusItem {
  id?: string;
  title?: string;
  owned?: boolean;
  [key: string]: unknown;
}
