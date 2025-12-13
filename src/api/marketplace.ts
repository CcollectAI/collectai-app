const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8081";
const API_KEY =
  process.env.EXPO_PUBLIC_API_KEY ?? "dev-local-secret-collectai";

async function doGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "X-API-Key": API_KEY,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`GET ${path} failed: ${res.status} - ${text}`);
  }
  return res.json() as Promise<T>;
}

async function doPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "X-API-Key": API_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`POST ${path} failed: ${res.status} - ${text}`);
  }
  return res.json() as Promise<T>;
}

// ---------------- Types ----------------

export type MarketplaceListingStatus = "active" | "inactive" | "sold";

export interface MarketplaceListing {
  id: string;
  owner_id: string;
  title: string;
  description: string | null;
  price_eur: number;
  category_slug: string | null;
  external_link: string | null;
  status: MarketplaceListingStatus;
  created_at: string;
}

export interface BuyerIntent {
  id: string;
  user_id: string;
  category_slug: string | null;
  query_text: string;
  max_price_eur: number | null;
  is_active: boolean;
  created_at: string;
}

export interface Agreement {
  id: string;
  buyer_id: string;
  seller_id: string;
  listing_id: string;
  price_eur: number;
  status: string;
  created_at: string;
}

export interface Rating {
  id: string;
  agreement_id: string;
  rater_id: string;
  rated_id: string;
  stars: number;
  comment: string | null;
  created_at: string;
}

export interface ChatRoom {
  id: string;
  name: string;
}

export interface ChatMessage {
  id: string;
  room_id: string;
  sender_id: string;
  content: string;
}

// ---------------- Listings (Sell tab) ----------------

export async function getMarketplaceListings(): Promise<MarketplaceListing[]> {
  return doGet<MarketplaceListing[]>("/marketplace/listings");
}

export async function createMarketplaceListing(input: {
  owner_id: string;
  title: string;
  description?: string;
  price_eur: number;
  category_slug?: string;
  external_link?: string;
}): Promise<MarketplaceListing> {
  return doPost<MarketplaceListing>("/marketplace/listings", input);
}

// ---------------- Buyer Intents (Buy / Looking for) ----------------

export async function getBuyerIntents(): Promise<BuyerIntent[]> {
  return doGet<BuyerIntent[]>("/marketplace/buyer-intents");
}

export async function createBuyerIntent(input: {
  user_id: string;
  query_text: string;
  category_slug?: string;
  max_price_eur?: number;
}): Promise<BuyerIntent> {
  return doPost<BuyerIntent>("/marketplace/buyer-intents", input);
}

// ---------------- Agreements & Ratings ----------------

export async function getAgreements(): Promise<Agreement[]> {
  return doGet<Agreement[]>("/marketplace/agreements");
}

export async function createAgreement(input: {
  buyer_id: string;
  seller_id: string;
  listing_id: string;
  price_eur: number;
}): Promise<Agreement> {
  return doPost<Agreement>("/marketplace/agreements", input);
}

export async function getRatings(): Promise<Rating[]> {
  return doGet<Rating[]>("/marketplace/ratings");
}

export async function createRating(input: {
  agreement_id: string;
  rater_id: string;
  rated_id: string;
  stars: number;
  comment?: string;
}): Promise<Rating> {
  return doPost<Rating>("/marketplace/ratings", input);
}

// ---------------- Chat (Chat tab) ----------------

export async function getChatRooms(): Promise<ChatRoom[]> {
  return doGet<ChatRoom[]>("/marketplace/chat/rooms");
}

export async function getChatMessages(
  room_id: string,
): Promise<ChatMessage[]> {
  const qs = new URLSearchParams({ room_id });
  return doGet<ChatMessage[]>(`/marketplace/chat/messages?${qs.toString()}`);
}

export async function sendChatMessage(input: {
  room_id: string;
  sender_id: string;
  content: string;
}): Promise<ChatMessage> {
  return doPost<ChatMessage>("/marketplace/chat/messages", input);
}
