/**
 * Pluggable seller-age-gate hook for httpClient.
 *
 * The SellerAgeGateProvider registers a function that pops the confirm modal
 * and resolves with true (confirmed + verified backend-side) or false (user
 * cancelled). httpClient consults this function whenever a /marketplace/listings/*
 * mutating endpoint returns 412 with `detail.error === 'seller_age_verification_required'`.
 *
 * Decoupled into its own module so httpClient doesn't import from src/components/*
 * (which would create a cycle through the React tree).
 */

type GateFn = () => Promise<boolean>;

let _gate: GateFn | null = null;

export function registerSellerAgeGate(fn: GateFn | null) {
  _gate = fn;
}

/**
 * Called by httpClient on a matching 412. Returns true if the user confirmed
 * and the server-side verification succeeded; the caller should then retry
 * the original request. Returns false if no gate is registered or the user
 * declined — caller should surface the original error.
 */
export async function popSellerAgeGate(): Promise<boolean> {
  if (!_gate) return false;
  return _gate();
}
