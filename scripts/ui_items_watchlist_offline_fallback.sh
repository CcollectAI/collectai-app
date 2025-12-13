#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/items.tsx"

if [ ! -f "$TARGET" ]; then
  echo "Items screen not found at $TARGET, creating directory."
  mkdir -p "app/(tabs)"
fi

echo "Backing up $TARGET"
cp "$TARGET" "$TARGET.bak.watchlist_offline_fallback.$(date +%s)" || true

cat <<'EOF' > "$TARGET"
import React, { useState, useEffect } from "react";
import { View, Text, ScrollView, Pressable, Button, ActivityIndicator } from "react-native";
import { API_BASE } from "../../src/api/config";

type ItemRow = {
  id: string;
  name: string;
  category: string;
  value: number;
  currency: string;
};

const MOCK_ITEMS: ItemRow[] = [
  { id: "p1", name: "Demo Charizard", category: "pokemon", value: 124.0, currency: "EUR" },
  { id: "p2", name: "Pikachu EX", category: "pokemon", value: 60.0, currency: "EUR" },
  { id: "f1", name: "Grail Funko Pop", category: "funko", value: 45.0, currency: "EUR" },
  { id: "g1", name: "Wave 1 RX-78 (Launch)", category: "gunpla", value: 220.0, currency: "EUR" },
  { id: "m1", name: "MTG Demo Mythic", category: "mtg", value: 80.0, currency: "EUR" },
];

const MOCK_CATEGORIES = [
  { id: "pokemon", label: "Pokémon" },
  { id: "funko", label: "Funko Pops" },
  { id: "gunpla", label: "Gunpla & model kits" },
  { id: "mtg", label: "Magic: The Gathering" },
];

type WatchlistItem = {
  id?: string;
  user_id?: string;
  item_id?: string;
  name?: string;
  category?: string;
  created_at?: string;
  predicted_value?: number;
  currency?: string;
};

type WatchlistResponse = {
  items?: WatchlistItem[];
};

export default function ItemsScreen() {
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);

  const [watchlistExpanded, setWatchlistExpanded] = useState<boolean>(false);
  const [watchlistLoading, setWatchlistLoading] = useState<boolean>(false);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);
  const [watchlistOfflineNote, setWatchlistOfflineNote] = useState<string | null>(null);
  const [watchlistItems, setWatchlistItems] = useState<WatchlistItem[]>([]);
  const [watchlistActionStatus, setWatchlistActionStatus] = useState<string | null>(null);

  const [downloadStatus, setDownloadStatus] = useState<string | null>(null);
  const [downloadBody, setDownloadBody] = useState<string | null>(null);

  const toggleCategory = function (catId: string) {
    if (expandedCategory === catId) {
      setExpandedCategory(null);
    } else {
      setExpandedCategory(catId);
    }
  };

  const setFallbackWatchlist = function () {
    setWatchlistItems([
      {
        id: "offline-1",
        item_id: "demo-item-1",
        name: "Demo Charizard (offline)",
        category: "pokemon",
        predicted_value: 124.0,
        currency: "EUR",
      },
    ]);
    setWatchlistOfflineNote("Offline mode: showing local demo watchlist.");
  };

  const loadWatchlist = async function () {
    setWatchlistLoading(true);
    setWatchlistError(null);
    setWatchlistOfflineNote(null);
    setWatchlistItems([]);
    try {
      const url = API_BASE + "/watchlist/mine";
      const res = await fetch(url);
      const text = await res.text();

      let json: WatchlistResponse | null = null;
      try {
        json = JSON.parse(text);
      } catch (e) {
        json = null;
      }

      if (json && json.items && Array.isArray(json.items) && json.items.length > 0) {
        setWatchlistItems(json.items);
      } else {
        // Backend reachable but empty -> start from empty list, no error.
        setWatchlistItems([]);
      }
    } catch (e: any) {
      const msg = e && e.message ? e.message : String(e);
      setWatchlistError("Error loading watchlist from backend: " + msg);
      // Offline fallback so UI is still useful
      setFallbackWatchlist();
    } finally {
      setWatchlistLoading(false);
    }
  };

  const handleDownload = async function () {
    setDownloadStatus("Loading...");
    setDownloadBody(null);
    try {
      const url = API_BASE + "/items-export/overview";
      const res = await fetch(url);
      const text = await res.text();
      const statusText = "Done (status=" + String(res.status) + ", ok=" + String(res.ok) + ")";
      setDownloadStatus(statusText);
      setDownloadBody(text);
    } catch (e: any) {
      setDownloadStatus("Error while fetching export");
      const msg = e && e.message ? e.message : String(e);
      setDownloadBody(msg);
    }
  };

  const handleAddDemoToWatchlist = async function () {
    // Always update local list immediately so the user sees a change
    setWatchlistItems(function (prev) {
      const next: WatchlistItem[] = prev.slice();
      next.push({
        id: "local-" + String(prev.length + 1),
        item_id: "demo-item-1",
        name: "Demo Charizard (local add)",
        category: "pokemon",
        predicted_value: 124.0,
        currency: "EUR",
      });
      return next;
    });
    setWatchlistActionStatus("Added locally. Syncing with backend…");

    try {
      const url = API_BASE + "/watchlist/mine";
      const payload = JSON.stringify({
        item_id: "demo-item-1",
        name: "Demo Charizard",
        category: "pokemon",
        predicted_value: 124.0,
      });

      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: payload,
      });

      const text = await res.text();
      const okText = "Backend sync done (status=" + String(res.status) + ", ok=" + String(res.ok) + ")";
      setWatchlistActionStatus(okText + " • " + text);

      // Try reloading from backend to reflect real state (if reachable)
      await loadWatchlist();
    } catch (e: any) {
      const msg = e && e.message ? e.message : String(e);
      setWatchlistActionStatus("Offline: kept local add. Backend sync failed: " + msg);
      if (!watchlistOfflineNote) {
        setWatchlistOfflineNote("Offline mode: watchlist changes are local only.");
      }
    }
  };

  useEffect(function () {
    // Load watchlist once when screen mounts
    loadWatchlist();
  }, []);

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: "#e6f7fb" }}
      contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 32, paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 26, fontWeight: "700", marginBottom: 16, color: "#103b5c" }}>
        Items
      </Text>

      {/* Categories overview with expandable rows */}
      <Text
        style={{ fontSize: 18, fontWeight: "600", marginBottom: 8, color: "#103b5c" }}
      >
        Categories
      </Text>
      <View
        style={{
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#dde6ee",
          backgroundColor: "#ffffff",
          marginBottom: 16,
        }}
      >
        {MOCK_CATEGORIES.map(function (cat, idx) {
          const isLast = idx === MOCK_CATEGORIES.length - 1;
          const isExpanded = expandedCategory === cat.id;
          const itemsInCat = MOCK_ITEMS.filter(function (item) {
            return item.category === cat.id;
          });

          return (
            <View
              key={cat.id}
              style={{
                borderBottomWidth: isLast ? 0 : 1,
                borderBottomColor: "#f0f3f7",
              }}
            >
              <Pressable
                onPress={function () {
                  toggleCategory(cat.id);
                }}
                style={{
                  paddingVertical: 10,
                  paddingHorizontal: 12,
                  flexDirection: "row",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <Text style={{ color: "#103b5c", fontWeight: "500" }}>{cat.label}</Text>
                <Text style={{ color: "#4a647a", fontSize: 12 }}>
                  {isExpanded ? "Hide" : "Show"} items ({itemsInCat.length})
                </Text>
              </Pressable>

              {isExpanded && itemsInCat.length > 0 && (
                <View
                  style={{
                    paddingHorizontal: 12,
                    paddingBottom: 8,
                  }}
                >
                  {itemsInCat.map(function (item) {
                    return (
                      <View
                        key={item.id}
                        style={{
                          paddingVertical: 4,
                          flexDirection: "row",
                          justifyContent: "space-between",
                        }}
                      >
                        <Text style={{ color: "#103b5c" }}>{item.name}</Text>
                        <Text style={{ color: "#4a647a" }}>
                          {item.value} {item.currency}
                        </Text>
                      </View>
                    );
                  })}
                </View>
              )}
            </View>
          );
        })}
      </View>

      {/* Watchlist (backend + offline fallback) */}
      <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 8, color: "#103b5c" }}>
        Watchlist
      </Text>
      <View
        style={{
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#dde6ee",
          backgroundColor: "#ffffff",
          marginBottom: 16,
        }}
      >
        <Pressable
          onPress={function () {
            setWatchlistExpanded(!watchlistExpanded);
          }}
          style={{
            paddingVertical: 10,
            paddingHorizontal: 12,
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <Text style={{ color: "#103b5c", fontWeight: "500" }}>My watchlist</Text>
          <Text style={{ color: "#4a647a", fontSize: 12 }}>
            {watchlistExpanded ? "Hide" : "Show"} items ({watchlistItems.length})
          </Text>
        </Pressable>

        {watchlistExpanded && (
          <View
            style={{
              paddingHorizontal: 12,
              paddingBottom: 12,
              gap: 4,
            }}
          >
            {watchlistLoading && (
              <View
                style={{
                  paddingVertical: 8,
                  flexDirection: "row",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <ActivityIndicator size="small" color="#103b5c" />
                <Text style={{ color: "#4a647a" }}>Loading watchlist…</Text>
              </View>
            )}

            {watchlistError && !watchlistLoading && (
              <Text style={{ color: "#c0392b", fontSize: 12 }}>{watchlistError}</Text>
            )}

            {watchlistOfflineNote && (
              <Text style={{ color: "#7a8b9a", fontSize: 11, marginTop: 4 }}>
                {watchlistOfflineNote}
              </Text>
            )}

            {!watchlistLoading &&
              watchlistItems.length === 0 &&
              !watchlistOfflineNote && (
                <Text style={{ color: "#4a647a", fontSize: 12 }}>
                  No items in your watchlist yet.
                </Text>
              )}

            {!watchlistLoading &&
              watchlistItems.length > 0 &&
              watchlistItems.map(function (item, idx) {
                const key = item.id || item.item_id || String(idx);
                const label = item.name || "Watchlist item";
                const value = item.predicted_value;
                const currency = item.currency || "EUR";
                return (
                  <View
                    key={key}
                    style={{
                      paddingVertical: 4,
                      flexDirection: "row",
                      justifyContent: "space-between",
                    }}
                  >
                    <Text style={{ color: "#103b5c" }}>{label}</Text>
                    {typeof value === "number" ? (
                      <Text style={{ color: "#4a647a" }}>
                        {value} {currency}
                      </Text>
                    ) : (
                      <Text style={{ color: "#4a647a", fontSize: 12 }}>no price</Text>
                    )}
                  </View>
                );
              })}

            <View style={{ marginTop: 8 }}>
              <Button title="Add demo Charizard to watchlist" onPress={handleAddDemoToWatchlist} />
              {watchlistActionStatus && (
                <Text style={{ marginTop: 4, color: "#4a647a", fontSize: 11 }}>
                  {watchlistActionStatus}
                </Text>
              )}
            </View>
          </View>
        )}
      </View>

      {/* Download overview card */}
      <View
        style={{
          padding: 16,
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#dde6ee",
          backgroundColor: "#ffffff",
        }}
      >
        <Text
          style={{
            fontSize: 16,
            fontWeight: "600",
            marginBottom: 8,
            color: "#103b5c",
          }}
        >
          Download overview
        </Text>
        <Text style={{ color: "#4a647a", marginBottom: 8 }}>
          Tap to fetch an export of your items from the backend. For now this
          returns stub CSV text in JSON, which you can preview below.
        </Text>
        <Button title="Download overview" onPress={handleDownload} />

        {downloadStatus && (
          <Text style={{ marginTop: 8, color: "#4a647a", fontSize: 12 }}>
            Status: {downloadStatus}
          </Text>
        )}
        {downloadBody && (
          <View
            style={{
              marginTop: 8,
              padding: 8,
              borderRadius: 4,
              borderWidth: 1,
              borderColor: "#dde6ee",
              backgroundColor: "#f8fcff",
            }}
          >
            <Text
              style={{
                fontFamily: "monospace",
                fontSize: 11,
                color: "#103b5c",
              }}
            >
              {downloadBody}
            </Text>
          </View>
        )}
      </View>

      <Text style={{ marginTop: 16, color: "#7a8b9a", fontSize: 12 }}>
        Demo mode: categories are local mock data. Watchlist talks to the backend if
        reachable, and falls back to a local demo list when offline.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Items tab updated: watchlist now has backend wiring + offline fallback."
