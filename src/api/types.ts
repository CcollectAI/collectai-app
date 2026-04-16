/**
 * Shared API types used across domain modules.
 */
import type { CurrencyCode } from "@/data/types";

/** Response from the server-side optimized photo upload endpoint */
export type ServerUploadResponse = {
  photo_key: string;
  cdn_url: string;
  blurhash: string;
  width: number;
  height: number;
  original_size: number;
  optimized_size: number;
};

// Intake result type returned by the intake agent endpoints
export type IntakeResultResponse = {
  name: string | null;
  category_id: string | null;
  category_confidence: number;
  subtype_id: string | null;
  attributes: Record<string, unknown>;
  identification_method: string;
  barcode: string | null;
  barcode_type: string | null;
  taxonomy_version: string;
  taxonomy_confidence: number;
  suggested_corrections: {
    from_category: string;
    to_category: string;
    frequency: number;
    user_count: number;
  }[];
  estimated_price: number | null;
  price_source: string | null;
  price_band: {
    q10: number;
    q50: number;
    q90: number;
    confidence: number;
    currency: CurrencyCode;
  } | null;
  image_url: string | null;
  catalog_miss: boolean;
  catalog_match_id: string | null;
  catalog_match_key: string | null;
  alternatives: {
    catalog_item_id: string | null;
    item_key: string | null;
    title: string | null;
    category: string | null;
    brand: string | null;
    rarity: string | null;
    set_code: string | null;
    // R50k: catalog reference images are backend-only
    has_reference_image?: boolean;
    match_score: number;
    match_reason: string | null;
  }[];
  field_confidence: {
    category: number;
    name: number;
    condition: number;
  } | null;
  chain_of_thought: string | null;
  rationale: string[];
  // QuickScan enhancement fields
  scan_session_id: string | null;
  social_proof: {
    collector_count: number;
    is_trending: boolean;
    trend_rank: number | null;
    recent_sold: {
      title: string | null;
      price: number | null;
      currency: string;
      sold_at: string | null;
      source: string | null;
    }[];
    scarcity: {
      listing_count: number;
      supply_trend: string;
      scarcity_score: number;
    } | null;
  } | null;
  duplicate_info: {
    owned_count: number;
    owned_item_ids: string[];
    is_variant: boolean;
    variant_of: string | null;
    set_completion: { owned: number; total: number; pct: number } | null;
  } | null;
  defect_annotations: {
    type: string | null;
    severity: string | null;
    location: string | null;
    description: string | null;
  }[];
  suggested_grade: {
    scale: string | null;
    grade_value: string | null;
    reasoning: string | null;
  } | null;
};

// Billing types
export interface BillingStatus {
  plan: "free" | "pro" | "premium";
  status: "active" | "past_due" | "canceled" | "unpaid" | "trialing";
  current_period_end?: string | null;
  cancel_at_period_end: boolean;
  limits: {
    max_mandates: number;
    deal_discovery: boolean;
    dossier_pdf: boolean;
    advanced_analytics: boolean;
    condition_grading: boolean;
    set_completion: boolean;
    show_ads?: boolean;
  };
}

// Notification types
export type NotificationItem = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  data: Record<string, unknown>;
  deep_link: string | null;
  read_at: string | null;
  created_at: string;
};

export type NotificationHistoryResponse = {
  notifications: NotificationItem[];
  total_count: number;
  unread_count: number;
};
