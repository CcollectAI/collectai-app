import { useSyncExternalStore } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";

// Adjust this import if your PortfolioItem type lives elsewhere
import type { PortfolioItem } from "../services/collectorsClient";

export type AlertDirection = "below" | "above";

export interface ItemAlert {
  itemId: string;
  threshold: number;
  currency: string;
  direction: AlertDirection;
}

type WatchlistState = {
  items: Record<string, PortfolioItem>;
  alerts: Record<string, ItemAlert>;
};

const STORAGE_KEY = "@collectai_watchlist_v1";

let state: WatchlistState = {
  items: {},
  alerts: {},
};

const listeners = new Set<() => void>();

function emitChange() {
  for (const listener of listeners) {
    listener();
  }
}

// --- Persistence helpers ---

let hydrationStarted = false;

async function loadFromStorage() {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Partial<WatchlistState>;

    state = {
      items: parsed.items ?? {},
      alerts: parsed.alerts ?? {},
    };
    emitChange();
  } catch (err) {
    console.warn("[watchlistStore] Failed to load from storage", err);
  }
}

async function saveToStorage(next: WatchlistState) {
  try {
    const payload = JSON.stringify(next);
    await AsyncStorage.setItem(STORAGE_KEY, payload);
  } catch (err) {
    console.warn("[watchlistStore] Failed to save to storage", err);
  }
}

// Kick off hydration once on module load
if (!hydrationStarted) {
  hydrationStarted = true;
  // Fire and forget; when it finishes, emitChange() will notify subscribers
  loadFromStorage();
}

// --- Internal state mutators ---

function setState(partial: Partial<WatchlistState>) {
  const next: WatchlistState = {
    ...state,
    ...partial,
  };
  state = next;
  emitChange();
  void saveToStorage(next);
}

function getSnapshot(): WatchlistState {
  return state;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

// --- Public API exposed via hook ---

function isInWatchlistInternal(id: string): boolean {
  return Boolean(state.items[id]);
}

function toggleItemInternal(item: PortfolioItem) {
  const items = { ...state.items };
  if (items[item.id]) {
    delete items[item.id];
  } else {
    items[item.id] = item;
  }
  setState({ items });
}

function getAlertInternal(itemId: string): ItemAlert | undefined {
  return state.alerts[itemId];
}

function setAlertInternal(alert: ItemAlert) {
  const alerts = { ...state.alerts, [alert.itemId]: alert };
  setState({ alerts });
}

function clearAlertInternal(itemId: string) {
  const alerts = { ...state.alerts };
  delete alerts[itemId];
  setState({ alerts });
}

function clearAllInternal() {
  setState({
    items: {},
    alerts: {},
  });
}

// Hook used in components
export function useWatchlist() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot);

  const itemsArray = Object.values(snapshot.items);

  return {
    // data
    items: itemsArray,
    alerts: snapshot.alerts,
    raw: snapshot,

    // selectors
    isInWatchlist: (id: string) => Boolean(snapshot.items[id]),
    getAlert: (itemId: string) => snapshot.alerts[itemId],

    // actions
    toggleItem: (item: PortfolioItem) => toggleItemInternal(item),
    setAlert: (alert: ItemAlert) => setAlertInternal(alert),
    clearAlert: (itemId: string) => clearAlertInternal(itemId),
    clear: () => clearAllInternal(),
  };
}
