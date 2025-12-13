#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/items.tsx"

if [ ! -f "$TARGET" ]; then
  echo "Items screen not found at $TARGET, creating directory."
  mkdir -p "app/(tabs)"
fi

echo "Backing up $TARGET"
cp "$TARGET" "$TARGET.bak.feedback_pass2.$(date +%s)" || true

cat <<'EOF' > "$TARGET"
import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  ScrollView,
  Pressable,
  Button,
  ActivityIndicator,
  Share,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
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
  { id: "pokemon", label: "Pokémon", tier: "Gold" },
  { id: "funko", label: "Funko Pops", tier: "Silver" },
  { id: "gunpla", label: "Gunpla & model kits", tier: "Gold" },
  { id: "mtg", label: "Magic: The Gathering", tier: "Platinum" },
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

function formatEuro(value: number | undefined | null): string {
  if (typeof value !== "number" || isNaN(value)) {
    return "€0.00";
  }
  const fixed = value.toFixed(2);
  const parts = fixed.split(".");
  let intPart = parts[0];
  const decPart = parts[1];
  const rgx = /(\d+)(\d{3})/;
  while (rgx.test(intPart)) {
    intPart = intPart.replace(rgx, "$1" + "," + "$2");
  }
  return "€" + intPart + "." + decPart;
}

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
        setWatchlistItems([]);
      }
    } catch (e: any) {
      const msg = e && e.message ? e.message : String(e);
      setWatchlistError("Error loading watchlist from backend: " + msg);
      setFallbackWatchlist();
    } finally {
      setWatchlistLoading(false);
    }
  };

  const handleDownload = async function () {
    setDownloadStatus("Loading…");
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

  const handleShare = async function () {
    try {
      const url = API_BASE + "/items-export/overview";
      const res = await fetch(url);
      const text = await res.text();

      let csv = text;
      try {
        const parsed = JSON.parse(text) as { csv_inline?: string };
        if (parsed && parsed.csv_inline) {
          csv = parsed.csv_inline;
        }
      } catch (e) {
        csv = text;
      }

      await Share.share({
        message: "My collection export:\n\n" + csv,
      });
    } catch (e: any) {
      const msg = e && e.message ? e.message : String(e);
      await Share.share({
        message: "Could not fetch export from backend.\n\n" + msg,
      });
    }
  };

  const handleAddDemoToWatchlist = async function () {
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
      const okText =
        "Backend sync done (status=" + String(res.status) + ", ok=" + String(res.ok) + ")";
      setWatchlistActionStatus(okText + " • " + text);

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
    loadWatchlist();
  }, []);

  const renderCategoryCard = function (catId: string, label: string, tier: string, idx: number) {
    const isLast = idx === MOCK_CATEGORIES.length - 1;
    const isExpanded = expandedCategory === catId;
    const itemsInCat = MOCK_ITEMS.filter(function (item) {
      return item.category === catId;
    });
    const totalValue = itemsInCat.reduce(function (sum, item) {
      return sum + item.value;
    }, 0);

    return (
      <View
        key={catId}
        style={{
          borderBottomWidth: isLast ? 0 : 1,
          borderBottomColor: "#f0f3f7",
          paddingHorizontal: 12,
          paddingVertical: 8,
        }}
      >
        <Pressable
          onPress={function () {
            toggleCategory(catId);
          }}
          style={{
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 4,
          }}
        >
          <View>
            <Text
              style={{
                color: "#103b5c",
                fontWeight: "700",
                fontSize: 16,
                marginBottom: 2,
              }}
            >
              {label}
            </Text>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <View
                style={{
                  paddingHorizontal: 8,
                  paddingVertical: 2,
                  borderRadius: 999,
                  backgroundColor: "#e6f2ff",
                }}
              >
                <Text style={{ fontSize: 10, color: "#103b5c", fontWeight: "500" }}>
                  Tier: {tier}
                </Text>
              </View>
            </View>
          </View>
          {/* Blue pill for item count instead of (2) text */}
          <View
            style={{
              paddingHorizontal: 10,
              paddingVertical: 4,
              borderRadius: 999,
              backgroundColor: "#e6f2ff",
            }}
          >
            <Text style={{ color: "#103b5c", fontSize: 11, fontWeight: "500" }}>
              {itemsInCat.length} items
            </Text>
          </View>
        </Pressable>

        {isExpanded && itemsInCat.length > 0 && (
          <View
            style={{
              marginTop: 4,
              borderRadius: 6,
              borderWidth: 1,
              borderColor: "#eef2f7",
              backgroundColor: "#f9fcff",
            }}
          >
            {itemsInCat.map(function (item, rowIndex) {
              const isLastRow = rowIndex === itemsInCat.length - 1;
              return (
                <View
                  key={item.id}
                  style={{
                    paddingHorizontal: 8,
                    paddingVertical: 6,
                    flexDirection: "row",
                    justifyContent: "space-between",
                    borderBottomWidth: isLastRow ? 0 : 1,
                    borderBottomColor: "#eef2f7",
                  }}
                >
                  <Text style={{ color: "#103b5c", fontSize: 13 }}>{item.name}</Text>
                  <Text style={{ color: "#4a647a", fontSize: 13 }}>
                    {formatEuro(item.value)}
                  </Text>
                </View>
              );
            })}

            {/* Category total summary row */}
            <View
              style={{
                paddingHorizontal: 8,
                paddingVertical: 6,
                flexDirection: "row",
                justifyContent: "space-between",
                borderTopWidth: 1,
                borderTopColor: "#dde6ee",
                backgroundColor: "#eef6ff",
              }}
            >
              <Text
                style={{
                  color: "#103b5c",
                  fontWeight: "600",
                  fontSize: 12,
                }}
              >
                Total in this category
              </Text>
              <Text
                style={{
                  color: "#103b5c",
                  fontWeight: "600",
                  fontSize: 12,
                }}
              >
                {formatEuro(totalValue)}
              </Text>
            </View>
          </View>
        )}
      </View>
    );
  };

  const renderWatchlistItemRow = function (
    item: WatchlistItem,
    idx: number
  ): JSX.Element {
    const key = item.id || item.item_id || String(idx);
    const label = item.name || "Watchlist item";
    const value = item.predicted_value;

    return (
      <View
        key={key}
        style={{
          paddingHorizontal: 8,
          paddingVertical: 6,
          flexDirection: "row",
          justifyContent: "space-between",
          borderBottomWidth: 1,
          borderBottomColor: "#eef2f7",
        }}
      >
        <Text style={{ color: "#103b5c", fontSize: 13 }}>{label}</Text>
        <Text style={{ color: "#4a647a", fontSize: 13 }}>
          {formatEuro(value)}
        </Text>
      </View>
    );
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: "#e6f7fb" }}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 8, paddingBottom: 32 }}
      >
        {/* Header with title + share */}
        <View
          style={{
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 16,
          }}
        >
          <Text style={{ fontSize: 26, fontWeight: "700", color: "#103b5c" }}>Items</Text>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <Button title="Share" onPress={handleShare} />
          </View>
        </View>

        {/* Categories overview */}
        <Text
          style={{ fontSize: 18, fontWeight: "600", marginBottom: 8, color: "#103b5c" }}
        >
          Categories
        </Text>
        <View
          style={{
            borderRadius: 10,
            borderWidth: 1,
            borderColor: "#dde6ee",
            backgroundColor: "#ffffff",
            marginBottom: 16,
          }}
        >
          {MOCK_CATEGORIES.map(function (cat, idx) {
            return renderCategoryCard(cat.id, cat.label, cat.tier, idx);
          })}
        </View>

        {/* Watchlist */}
        <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 8, color: "#103b5c" }}>
          Watchlist
        </Text>
        <View
          style={{
            borderRadius: 10,
            borderWidth: 1,
            borderColor: "#dde6ee",
            backgroundColor: "#ffffff",
            marginBottom: 8,
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
            <View>
              <Text style={{ color: "#103b5c", fontWeight: "600", fontSize: 15 }}>
                My watchlist
              </Text>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 2 }}>
                <View
                  style={{
                    paddingHorizontal: 8,
                    paddingVertical: 2,
                    borderRadius: 999,
                    backgroundColor: "#e9f7ef",
                  }}
                >
                  <Text style={{ fontSize: 10, color: "#1f7a3d" }}>
                    {watchlistItems.length} items
                  </Text>
                </View>
                {watchlistOfflineNote && (
                  <View
                    style={{
                      paddingHorizontal: 8,
                      paddingVertical: 2,
                      borderRadius: 999,
                      backgroundColor: "#fff4e6",
                    }}
                  >
                    <Text style={{ fontSize: 10, color: "#c26b00" }}>Offline demo</Text>
                  </View>
                )}
              </View>
            </View>
            <View
              style={{
                paddingHorizontal: 10,
                paddingVertical: 4,
                borderRadius: 999,
                backgroundColor: "#e6f2ff",
              }}
            >
              <Text style={{ color: "#103b5c", fontSize: 11, fontWeight: "500" }}>
                {watchlistItems.length} items
              </Text>
            </View>
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
                watchlistItems.length > 0 && (
                  <View
                    style={{
                      marginTop: 4,
                      borderRadius: 6,
                      borderWidth: 1,
                      borderColor: "#eef2f7",
                      backgroundColor: "#f9fcff",
                    }}
                  >
                    {watchlistItems.map(function (item, idx) {
                      return renderWatchlistItemRow(item, idx);
                    })}
                  </View>
                )}

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

        {/* Download section under watchlist */}
        <View style={{ marginTop: 4 }}>
          <Button title="Download overview (CSV)" onPress={handleDownload} />
          {downloadStatus && (
            <Text style={{ marginTop: 4, color: "#4a647a", fontSize: 12 }}>
              Export status: {downloadStatus}
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
          reachable, and falls back to a local demo list when offline. Download and Share
          use the same backend export stub.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}
EOF

echo "Items tab updated (feedback pass 2)."
