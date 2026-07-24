/**
 * Zod runtime validation schemas for high-risk API response types.
 *
 * These schemas provide a safety net against malformed backend responses,
 * ensuring the app degrades gracefully instead of crashing on bad data.
 */
import { z } from "zod";
import { logger } from "@/lib/logger";

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

/** Single marketplace search hit */
export const MarketplaceHitSchema = z.object({
  source: z.string(),
  title: z.string(),
  price: z.number().positive(),
  currency: z.string(),
  url: z.string().optional(),
  image_url: z.string().optional(),
  sold_date: z.string().optional(),
  condition: z.string().optional(),
});
export type MarketplaceHit = z.infer<typeof MarketplaceHitSchema>;

/** Marketplace search response (array of hits) */
export const MarketplaceSearchResponseSchema = z.object({
  results: z.array(MarketplaceHitSchema).optional(),
  hits: z.array(MarketplaceHitSchema).optional(),
});
export type MarketplaceSearchResponse = z.infer<typeof MarketplaceSearchResponseSchema>;

/** Portfolio category breakdown entry */
const PortfolioCategorySchema = z.object({
  category: z.string(),
  value: z.number(),
  count: z.number(),
});

/** Portfolio overview item — the backend (portfolio_router.py) returns
 *  snake_case current_value / change_1d_pct. `.passthrough()` keeps any extra
 *  or alternately-named fields so extractItems' fallback chains still resolve. */
const PortfolioOverviewItemSchema = z
  .object({
    id: z.union([z.string(), z.number()]).nullable().optional(),
    // name IS nullable — items can be saved with a null name (the backend reads
    // items.name, which is NULL for catalog-matched adds). A non-nullable
    // z.string() here fails the WHOLE snapshot parse → safeParse returns the
    // empty fallback → Home falsely shows "add your first item" while the Items
    // tab lists them. Verified via [DIAG] 2026-07-24.
    name: z.string().nullable().optional(),
    category: z.string().nullable().optional(),
    current_value: z.number().nullable().optional(),
    change_1d_pct: z.number().nullable().optional(),
  })
  .passthrough();

/** Portfolio overview snapshot.
 *  NOTE: `items` MUST be declared here. Zod strips undeclared keys by default,
 *  so without it the backend's `items` array was silently deleted during
 *  safeParse and Home's extractItems (which reads raw.items) always got [] —
 *  the Portfolio tab showed "add your first item" while the Items tab (Supabase)
 *  correctly listed the items. FE/BE contract bug, fixed 2026-07-24. */
export const PortfolioSnapshotSchema = z.object({
  total_value: z.number(),
  item_count: z.number(),
  categories: z.array(PortfolioCategorySchema).optional(),
  items: z.array(PortfolioOverviewItemSchema).optional(),
});
export type PortfolioSnapshot = z.infer<typeof PortfolioSnapshotSchema>;

/** Price prediction response */
export const PricePredictionSchema = z.object({
  q10: z.number(),
  q50: z.number(),
  q90: z.number(),
  confidence: z.number().min(0).max(1),
  model_version: z.string().optional(),
});
export type PricePrediction = z.infer<typeof PricePredictionSchema>;

/** QuickScan / intake result */
export const IntakeResultSchema = z.object({
  name: z.string(),
  category: z.string(),
  estimated_value: z.number().optional(),
  confidence: z.number().min(0).max(1).optional(),
  condition: z.string().optional(),
});
export type IntakeResult = z.infer<typeof IntakeResultSchema>;

/** Chat message */
export const ChatMessageSchema = z.object({
  id: z.string(),
  thread_id: z.string(),
  sender_id: z.string(),
  body: z.string(),
  created_at: z.string(),
});
export type ChatMessage = z.infer<typeof ChatMessageSchema>;

// ---------------------------------------------------------------------------
// Safe parse wrapper
// ---------------------------------------------------------------------------

/**
 * Validate `data` against `schema`, returning the parsed value on success
 * or `fallback` on failure (with a warning log).
 */
export function safeParse<T>(schema: z.ZodType<T>, data: unknown, fallback: T): T {
  const result = schema.safeParse(data);
  if (result.success) return result.data;
  logger.warn("[api] Response validation failed:", result.error.issues);
  return fallback;
}
