export type ConnectionStatus = "none" | "outgoing" | "incoming" | "connected";

type PairKey = string;

function key(a: string, b: string): PairKey {
  const x = String(a || "");
  const y = String(b || "");
  return x < y ? `${x}::${y}` : `${y}::${x}`;
}

// Global in-memory store (safe for Expo Go; replace with Supabase later)
const g: any = globalThis as any;
g.__collectorsConnections = g.__collectorsConnections ?? {
  statusByPair: {} as Record<PairKey, ConnectionStatus>,
  outgoingByUser: {} as Record<string, Set<string>>,
  incomingByUser: {} as Record<string, Set<string>>,
};

const store = g.__collectorsConnections as {
  statusByPair: Record<PairKey, ConnectionStatus>;
  outgoingByUser: Record<string, Set<string>>;
  incomingByUser: Record<string, Set<string>>;
};

function ensureSet(map: Record<string, Set<string>>, id: string) {
  if (!map[id]) map[id] = new Set<string>();
  return map[id];
}

// For now: treat "me" as a single local user.
// Replace later with your auth user id.
export function getLocalUserId(): string {
  return "local-me";
}

export function getConnectionStatus(me: string, other: string): ConnectionStatus {
  const k = key(me, other);
  return store.statusByPair[k] ?? "none";
}

export function requestConnection(me: string, other: string) {
  const k = key(me, other);
  const existing = store.statusByPair[k] ?? "none";
  if (existing === "connected") return;

  store.statusByPair[k] = "outgoing";
  ensureSet(store.outgoingByUser, me).add(other);
  ensureSet(store.incomingByUser, other).add(me);
}

export function acceptConnection(me: string, other: string) {
  const k = key(me, other);
  store.statusByPair[k] = "connected";
  ensureSet(store.incomingByUser, me).delete(other);
  ensureSet(store.outgoingByUser, other).delete(me);
}

export function declineConnection(me: string, other: string) {
  const k = key(me, other);
  store.statusByPair[k] = "none";
  ensureSet(store.incomingByUser, me).delete(other);
  ensureSet(store.outgoingByUser, other).delete(me);
}
