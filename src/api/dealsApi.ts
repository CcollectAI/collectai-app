/**
 * Deal Desk (P2P offers), mandates, deals, and risk flags API methods.
 */
import { get, post, del, patch } from "./httpClient";

/**
 * The /purchase/* endpoints return snake_case; PurchaseMandate and MandateDeal
 * (src/data/types.ts) are camelCase. Nothing mapped between them, and the
 * screen cast the raw response to the typed shape — so TypeScript was happy
 * while EVERY camelCase field read `undefined` at runtime.
 *
 * On the Agent Hub that meant a mandate card rendered its name and status
 * (those keys happen to match) above a blank search query, "spotted" with no
 * number, and a cap of "—" from formatPrice(undefined). It looked like a
 * styling bug; the data was simply never there. Found 2026-07-29 by seeding a
 * mandate and reading the card.
 *
 * Converting here rather than in the screen means every caller of these
 * endpoints gets the shape its types promise.
 */
function toCamel(key: string): string {
  return key.replace(/_([a-z0-9])/g, (_m, c: string) => c.toUpperCase());
}

function camelizeDeep<T>(input: unknown): T {
  if (Array.isArray(input)) return input.map((v) => camelizeDeep(v)) as unknown as T;
  if (input && typeof input === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(input as Record<string, unknown>)) {
      out[toCamel(k)] = camelizeDeep(v);
    }
    return out as T;
  }
  return input as T;
}

// Mandates
export const createMandate = (payload: {
  name: string;
  search_query: string;
  category?: string | null;
  condition_filter?: string[];
  min_trust_score?: number;
  max_price: number;
  max_total_budget?: number | null;
  cooldown_hours?: number;
  allowed_sources?: string[];
  region?: string | null;
  expires_at?: string | null;
}) => post("/purchase/mandates", payload as Record<string, unknown>);

export const listMandates = async (limit = 20, offset = 0) => {
  const raw = await get<{ mandates?: unknown[]; total?: number }>(
    `/purchase/mandates?limit=${limit}&offset=${offset}`,
  );
  return camelizeDeep<{ mandates?: unknown[]; total?: number }>(raw);
};

export const getMandate = async (id: string) =>
  camelizeDeep(await get(`/purchase/mandates/${encodeURIComponent(id)}`));

export const updateMandate = (id: string, payload: Record<string, unknown>) =>
  patch(`/purchase/mandates/${encodeURIComponent(id)}`, payload);

export const deleteMandate = (id: string) =>
  del(`/purchase/mandates/${encodeURIComponent(id)}`);

// Deals
export const listDeals = (params?: { status?: string; limit?: number; offset?: number }) => {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const query = qs.toString();
  return get<{ deals?: unknown[] }>(`/purchase/deals${query ? `?${query}` : ""}`).then(
    (raw) => camelizeDeep<{ deals?: unknown[] }>(raw),
  );
};

export const getDeal = (id: string) =>
  get(`/purchase/deals/${encodeURIComponent(id)}`);

export const clickDeal = (id: string) =>
  post(`/purchase/deals/${encodeURIComponent(id)}/click`);

export const confirmDeal = (id: string, confirmedPrice?: number) =>
  post(`/purchase/deals/${encodeURIComponent(id)}/confirm`, {
    confirmed_price: confirmedPrice,
  });

export const declineDeal = (id: string) =>
  post(`/purchase/deals/${encodeURIComponent(id)}/decline`);

export const getDealStats = () => get("/purchase/stats");

export const getMandateForecast = (mandateId: string) =>
  get(`/purchase/mandates/${encodeURIComponent(mandateId)}/forecast`);

// Deal Desk (P2P Offers)
export const proposeOffer = (payload: { item_id: string; price: number; message?: string }) =>
  post("/deals/offer", payload as Record<string, unknown>);

export const counterOffer = (offerId: string, payload: { price: number; message?: string }) =>
  post(`/deals/${encodeURIComponent(offerId)}/counter`, payload as Record<string, unknown>);

export const respondToOffer = (offerId: string, payload: { accept: boolean; message?: string }) =>
  post(`/deals/${encodeURIComponent(offerId)}/respond`, payload as Record<string, unknown>);

export const cancelOffer = (offerId: string) =>
  post(`/deals/${encodeURIComponent(offerId)}/cancel`);

export const markShipped = (offerId: string, payload: { tracking_info?: string }) =>
  post(`/deals/${encodeURIComponent(offerId)}/ship`, payload as Record<string, unknown>);

export const completeDeal = (offerId: string, payload: { stars: number; comment?: string }) =>
  post(`/deals/${encodeURIComponent(offerId)}/complete`, payload as Record<string, unknown>);

export const listActiveOffers = () => get("/deals/active");

export const listDealHistory = () => get("/deals/history");

export const getOfferDetail = (offerId: string) =>
  get(`/deals/${encodeURIComponent(offerId)}`);

export const getOfferEvidence = (offerId: string) =>
  get(`/deals/${encodeURIComponent(offerId)}/evidence`);

export const getUserReputation = (userId: string) =>
  get(`/deals/reputation/${encodeURIComponent(userId)}`);

export const getDealRiskFlags = (offerId: string) =>
  get(`/deals/${encodeURIComponent(offerId)}/risk-flags`);
