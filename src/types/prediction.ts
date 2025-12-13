export type PredictionSession = {
  id: string;
  user_id: string | null;
  item_id: string | null;
  category: 'pokemon'|'funko'|'diecast';
  status: 'pending'|'processing'|'done'|'error';
  confidence: number | null;
  price_low_eur: number | null;
  price_mid_eur: number | null;
  price_high_eur: number | null;
  features: Record<string, unknown> | null;
  comps: Array<Record<string, unknown>> | null;
  created_at: string;
  updated_at: string;
};
export type LabelEvent = {
  id: string;
  session_id: string;
  user_id: string | null;
  corrected_title?: string | null;
  corrected_variant?: string | null;
  corrected_condition?: string | null;
  corrected_price_eur?: number | null;
  notes?: string | null;
  created_at: string;
};
