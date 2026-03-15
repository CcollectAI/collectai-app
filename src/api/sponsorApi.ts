/**
 * Sponsor companies API methods.
 */
import { get, post, del, patch } from "./httpClient";

export const listMySponsorCompanies = () =>
  get("/sponsor-companies/mine");

export const createSponsorCompany = (payload: { name: string; contact_email: string; logo_url?: string; website_url?: string; description?: string }) =>
  post("/sponsor-companies", payload as Record<string, unknown>);

export const getSponsorCompany = (companyId: string) =>
  get(`/sponsor-companies/${encodeURIComponent(companyId)}`);

export const updateSponsorCompany = (companyId: string, payload: Record<string, unknown>) =>
  patch(`/sponsor-companies/${encodeURIComponent(companyId)}`, payload);

export const deleteSponsorCompany = (companyId: string) =>
  del(`/sponsor-companies/${encodeURIComponent(companyId)}`);

export const createSponsorEventCheckout = (companyId: string, payload: Record<string, unknown>) =>
  post(`/sponsor-companies/${encodeURIComponent(companyId)}/create-event-checkout`, payload);

export const createSponsorSubscriptionCheckout = (companyId: string, payload: { tier: string }) =>
  post(`/sponsor-companies/${encodeURIComponent(companyId)}/create-subscription-checkout`, payload as Record<string, unknown>);

export const getSponsorAnalytics = (companyId: string) =>
  get(`/sponsor-companies/${encodeURIComponent(companyId)}/analytics`);
