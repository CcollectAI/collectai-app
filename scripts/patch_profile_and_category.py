#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime

ROOT = Path(".")
PORTFOLIO = ROOT / "app/(tabs)/index.tsx"
USER_ROUTE = ROOT / "app/users/[userId].tsx"
CARD = ROOT / "src/components/UserProfileSummaryCard.tsx"

def backup(p: Path) -> None:
    if not p.exists():
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    b = p.with_suffix(p.suffix + f".bak.{ts}")
    b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

def ensure_import_named(src: str, module: str, names: list[str]) -> str:
    # If import { ... } from "module" exists, add names
    pat = rf'^\s*import\s+\{{([^}}]+)\}}\s+from\s+[\'"]{re.escape(module)}[\'"];\s*$'
    m = re.search(pat, src, flags=re.M)
    if m:
        items = [x.strip() for x in m.group(1).split(",") if x.strip()]
        changed = False
        for n in names:
            if n not in items:
                items.append(n)
                changed = True
        if changed:
            repl = f'import {{ {", ".join(items)} }} from "{module}";'
            src = re.sub(pat, repl, src, flags=re.M)
        return src

    # Otherwise insert after last import
    lines = src.splitlines(True)
    insert_at = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("import "):
            insert_at = i + 1
    lines.insert(insert_at, f'import {{ {", ".join(names)} }} from "{module}";\n')
    return "".join(lines)

def ensure_react_native_imports(src: str, names: list[str]) -> str:
    return ensure_import_named(src, "react-native", names)

def ensure_expo_router_imports(src: str, names: list[str]) -> str:
    return ensure_import_named(src, "expo-router", names)

def fix_portfolio_category_button() -> None:
    if not PORTFOLIO.exists():
        print(f"[skip] missing {PORTFOLIO}")
        return

    backup(PORTFOLIO)
    src = PORTFOLIO.read_text(encoding="utf-8")

    # Ensure imports
    src = ensure_expo_router_imports(src, ["useRouter"])
    src = ensure_react_native_imports(src, ["Pressable"])

    # Ensure router const near component start
    if "const router = useRouter();" not in src:
        # Insert after first function component opening brace
        src = re.sub(
            r'(export\s+default\s+function\s+\w+\s*\([^)]*\)\s*\{\s*)',
            r'\1\n  const router = useRouter();\n',
            src,
            count=1,
            flags=re.S
        )

    # Replace existing Link-based button block (if present) with Pressable that uses router.push
    # If not found, we inject a fresh one after first <SafeAreaView ...> line.
    button_block = """\
      {/* DEV: quick access */}
      <Pressable
        onPress={() => router.push("/category-card")}
        style={{
          position: "absolute",
          top: 12,
          right: 12,
          zIndex: 9999,
          paddingHorizontal: 10,
          paddingVertical: 6,
          backgroundColor: "#ffffff",
          borderWidth: 1,
          borderColor: "#d7e6f2",
          borderRadius: 0,
        }}
      >
        <Text style={{ fontSize: 12, fontWeight: "900", color: "#0b1f3a" }}>
          Category Card
        </Text>
      </Pressable>
"""

    # Remove any previous injected Link href="/category-card" blocks
    src2 = re.sub(
        r'\s*\{\/\*\s*DEV:\s*quick access\s*\*\/\}\s*<Link[\s\S]*?<\/Link>\s*',
        "\n",
        src,
        flags=re.M
    )
    src = src2

    if 'router.push("/category-card")' in src:
        PORTFOLIO.write_text(src, encoding="utf-8")
        print(f"[ok] updated category nav in {PORTFOLIO}")
        return

    # Inject after SafeAreaView line
    lines = src.splitlines(True)
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if (not inserted) and ("<SafeAreaView" in line):
            indent = re.match(r'^(\s*)', line).group(1)
            block = "".join(indent + l if l.strip() else l for l in button_block.splitlines(True))
            out.append(block)
            inserted = True

    if not inserted:
        print("[warn] Could not find <SafeAreaView ...> to inject button; leaving file unchanged.")
        PORTFOLIO.write_text(src, encoding="utf-8")
        return

    PORTFOLIO.write_text("".join(out), encoding="utf-8")
    print(f"[ok] injected reliable category button into {PORTFOLIO}")

def write_user_profile_summary_card() -> None:
    CARD.parent.mkdir(parents=True, exist_ok=True)
    backup(CARD)

    CARD.write_text(
        """import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

type Props = {
  title?: string;
  subtitle?: string;
  totalValueEur: number;
  itemsCount: number;
  dayChangePct?: number | null;
  onRequestChat?: () => void;
};

/**
 * User Profile Summary Card
 * Styled to match the "event card" vibe: clean white square card, bold navy, concise rows.
 */
export default function UserProfileSummaryCard({
  title = "Collector Profile",
  subtitle,
  totalValueEur,
  itemsCount,
  dayChangePct = null,
  onRequestChat,
}: Props) {
  const changeText =
    typeof dayChangePct === "number" && isFinite(dayChangePct)
      ? `${dayChangePct >= 0 ? "+" : ""}${dayChangePct.toFixed(2)}%`
      : "—";

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>{title}</Text>
        <View style={styles.pill}>
          <Text style={styles.pillText}>{itemsCount} items</Text>
        </View>
      </View>

      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}

      <View style={styles.valueRow}>
        <Text style={styles.valueLabel}>Total value</Text>
        <Text style={styles.value}>
          €{Number(totalValueEur || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </Text>
      </View>

      <View style={styles.metaRow}>
        <Text style={styles.metaLabel}>24h change</Text>
        <Text
          style={[
            styles.metaValue,
            typeof dayChangePct === "number"
              ? dayChangePct >= 0
                ? styles.pos
                : styles.neg
              : null,
          ]}
        >
          {changeText}
        </Text>
      </View>

      <View style={styles.divider} />

      <Pressable
        disabled={!onRequestChat}
        onPress={onRequestChat}
        style={({ pressed }) => [
          styles.chatBtn,
          pressed ? styles.chatBtnPressed : null,
          !onRequestChat ? styles.chatBtnDisabled : null,
        ]}
      >
        <Text style={styles.chatBtnText}>Request to Chat</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#d7e6f2",
    borderRadius: 0,
    padding: 14,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
  },
  title: {
    color: "#0b1f3a",
    fontSize: 16,
    fontWeight: "900",
  },
  subtitle: {
    marginTop: 6,
    color: "#23405c",
    fontSize: 12,
    fontWeight: "700",
  },
  pill: {
    borderWidth: 1,
    borderColor: "#d7e6f2",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 0,
    backgroundColor: "#f7fbff",
  },
  pillText: {
    color: "#0b1f3a",
    fontSize: 12,
    fontWeight: "900",
  },
  valueRow: {
    marginTop: 12,
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
  },
  valueLabel: {
    color: "#23405c",
    fontSize: 12,
    fontWeight: "800",
  },
  value: {
    color: "#0b1f3a",
    fontSize: 20,
    fontWeight: "900",
  },
  metaRow: {
    marginTop: 8,
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
  },
  metaLabel: {
    color: "#23405c",
    fontSize: 12,
    fontWeight: "800",
  },
  metaValue: {
    color: "#0b1f3a",
    fontSize: 12,
    fontWeight: "900",
  },
  pos: { color: "#0b7a3b" },
  neg: { color: "#b00020" },
  divider: {
    marginTop: 12,
    height: 1,
    backgroundColor: "#d7e6f2",
  },
  chatBtn: {
    marginTop: 12,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#0b1f3a",
    borderRadius: 0,
    paddingVertical: 10,
    alignItems: "center",
  },
  chatBtnPressed: {
    transform: [{ scale: 0.99 }],
  },
  chatBtnDisabled: {
    opacity: 0.5,
  },
  chatBtnText: {
    color: "#0b1f3a",
    fontSize: 13,
    fontWeight: "900",
  },
});
""",
        encoding="utf-8",
    )
    print(f"[ok] wrote {CARD}")

def write_user_route() -> None:
    USER_ROUTE.parent.mkdir(parents=True, exist_ok=True)
    backup(USER_ROUTE)

    USER_ROUTE.write_text(
        """import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, SafeAreaView, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import UserProfileSummaryCard from "@/components/UserProfileSummaryCard";
import { getPortfolioItems } from "@/services/collectorsClient";

/**
 * User Profile Screen
 * - Shows a portfolio summary card (event-card style)
 * - Includes "Request to Chat" button (hook it to your chat request function)
 */
export default function UserProfileScreen() {
  const params = useLocalSearchParams();
  const userId = String((params as any)?.userId ?? "me");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<any[]>([]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getPortfolioItems();
        if (!cancelled) setItems(Array.isArray(data) ? data : []);
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? "Failed to load portfolio");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = True as any; // keep TS happy in some configs
    };
  }, []);

  const totals = useMemo(() => {
    const arr = Array.isArray(items) ? items : [];
    const values = arr
      .map((it) => {
        const v =
          it?.value ??
          it?.current_value ??
          it?.currentValue ??
          it?.price ??
          it?.market_value ??
          it?.marketValue;
        return typeof v === "number" && isFinite(v) ? v : 0;
      });

    const totalValue = values.reduce((a, b) => a + b, 0);
    const count = arr.length;

    // If an item has a dayChangePct, average-weight it lightly; otherwise null
    const dayPcts = arr
      .map((it) => it?.dayChangePct ?? it?.change24hPct ?? it?.pct_24h)
      .filter((x: any) => typeof x === "number" && isFinite(x));

    const dayChangePct = dayPcts.length ? (dayPcts.reduce((a: number, b: number) => a + b, 0) / dayPcts.length) : null;

    return { totalValue, count, dayChangePct };
  }, [items]);

  const requestToChat = () => {
    // TODO: connect this to your real "request to chat" action.
    // Example: requestChat({ userId })
    console.log("requestToChat:", { userId });
  };

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.pageTitle}>Profile</Text>

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator />
            <Text style={styles.muted}>Loading…</Text>
          </View>
        ) : error ? (
          <View style={styles.center}>
            <Text style={styles.error}>{error}</Text>
          </View>
        ) : (
          <UserProfileSummaryCard
            title={userId === "me" ? "Your Collector Profile" : "Collector Profile"}
            subtitle={userId === "me" ? "Portfolio overview" : `User: ${userId}`}
            totalValueEur={totals.totalValue}
            itemsCount={totals.count}
            dayChangePct={totals.dayChangePct}
            onRequestChat={requestToChat}
          />
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#cfefff" }, // tiffany-ish background
  container: { padding: 14, gap: 12 },
  pageTitle: { color: "#0b1f3a", fontSize: 18, fontWeight: "900" },
  center: { padding: 14, alignItems: "center", gap: 8 },
  muted: { color: "#23405c", fontSize: 12, fontWeight: "700" },
  error: { color: "#b00020", fontSize: 12, fontWeight: "900" },
});
""",
        encoding="utf-8",
    )
    print(f"[ok] wrote {USER_ROUTE}")

def main() -> None:
    fix_portfolio_category_button()
    write_user_profile_summary_card()
    write_user_route()

if __name__ == "__main__":
    main()
