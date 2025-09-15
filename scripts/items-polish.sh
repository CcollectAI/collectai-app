#!/usr/bin/env bash
set -euo pipefail

file="app/(tabs)/items.tsx"
[ -f "$file" ] && cp "$file" "$file.bak"

cat > "$file" <<'TSX'
import { View, Text, ScrollView, Pressable, Share } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Card from '@/components/Card';
import ShieldBadge, { Tier } from '@/components/ShieldBadge';
import { theme } from '@/theme';

type Item = { name: string; pct: number; price: number };
type Group = { category: string; tier: Tier; items: Item[] };

const fmtEUR0 = (n: number) =>
  new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n);

// Demo data (now with "tier" at category level)
const GROUPS: Group[] = [
  {
    category: 'Pokémon',
    tier: 'platinum',
    items: [
      { name: 'PSA 9 Charizard', pct: 2.4, price: 1820 },
      { name: 'Pikachu VMAX', pct: -0.8, price: 210 },
    ],
  },
  {
    category: 'Funko',
    tier: 'gold',
    items: [{ name: 'Freddy Funko LE', pct: 1.1, price: 320 }],
  },
];

export default function Items() {
  const onShare = async () => {
    try {
      await Share.share({ message: 'My collection snapshot from Collect AI' });
    } catch {}
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: theme.colors.bg }}
      contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}
    >
      {/* Top-right Share button */}
      <View style={{ alignItems: 'flex-end' }}>
        <Pressable
          onPress={onShare}
          style={{ flexDirection: 'row', alignItems: 'center', gap: theme.spacing.xs }}
        >
          <Ionicons name="share-outline" size={18} color={theme.colors.navy} />
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Share</Text>
        </Pressable>
      </View>

      {GROUPS.map((g) => {
        const total = g.items.reduce((s, it) => s + it.price, 0);

        return (
          <Card key={g.category} style={{ gap: theme.spacing.md, padding: theme.spacing.md }}>
            {/* Category header: title left, shield right */}
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingBottom: theme.spacing.sm,
                borderBottomWidth: 1,
                borderColor: theme.colors.border,
              }}
            >
              <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>
                {g.category}
              </Text>
              <ShieldBadge tier={g.tier} />
            </View>

            {/* Table header with extra divider line */}
            <View
              style={{
                flexDirection: 'row',
                paddingTop: theme.spacing.sm,
                paddingBottom: theme.spacing.sm,
                borderBottomWidth: 1,
                borderColor: theme.colors.border,
                alignItems: 'center',
              }}
            >
              <Text style={{ flex: 1, color: theme.colors.subtext, fontWeight: '700' }}>
                Name
              </Text>
              {/* vertical separator */}
              <View
                style={{
                  width: 1,
                  alignSelf: 'stretch',
                  backgroundColor: theme.colors.border,
                  marginHorizontal: theme.spacing.md,
                }}
              />
              <Text
                style={{
                  width: 70,
                  textAlign: 'right',
                  color: theme.colors.subtext,
                  fontWeight: '700',
                }}
              >
                %
              </Text>
              {/* vertical separator */}
              <View
                style={{
                  width: 1,
                  alignSelf: 'stretch',
                  backgroundColor: theme.colors.border,
                  marginHorizontal: theme.spacing.md,
                }}
              />
              <Text
                style={{
                  width: 100,
                  textAlign: 'right',
                  color: theme.colors.subtext,
                  fontWeight: '700',
                }}
              >
                Price
              </Text>
            </View>

            {/* Rows with tidy spacing and internal separators */}
            {g.items.map((it, idx) => (
              <View
                key={idx}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  paddingVertical: theme.spacing.md,
                  borderBottomWidth: idx < g.items.length - 1 ? 1 : 0,
                  borderColor: theme.colors.border,
                }}
              >
                {/* Name column is the longest */}
                <View style={{ flex: 1, paddingRight: theme.spacing.md }}>
                  <Text style={{ color: theme.colors.navy, fontWeight: '600' }}>{it.name}</Text>
                  <Text
                    style={{
                      fontSize: 12,
                      marginTop: 2,
                      color: it.pct >= 0 ? theme.colors.up : theme.colors.down,
                    }}
                  >
                    {(it.pct >= 0 ? '+' : '') + it.pct.toFixed(2)}%
                  </Text>
                </View>

                {/* vertical separator */}
                <View
                  style={{
                    width: 1,
                    alignSelf: 'stretch',
                    backgroundColor: theme.colors.border,
                    marginHorizontal: theme.spacing.md,
                  }}
                />

                {/* Empty visual % column (label already under name, keep right spacing tidy) */}
                <Text style={{ width: 70, textAlign: 'right', color: theme.colors.subtext }}>
                  {/* intentionally blank since % is below name */}
                </Text>

                {/* vertical separator */}
                <View
                  style={{
                    width: 1,
                    alignSelf: 'stretch',
                    backgroundColor: theme.colors.border,
                    marginHorizontal: theme.spacing.md,
                  }}
                />

                {/* Price w/o decimals */}
                <Text
                  style={{
                    width: 100,
                    textAlign: 'right',
                    color: theme.colors.navy,
                    fontWeight: '700',
                  }}
                >
                  {fmtEUR0(it.price)}
                </Text>
              </View>
            ))}

            {/* Category total row (subtle) */}
            <View style={{ alignItems: 'flex-end', marginTop: theme.spacing.sm }}>
              <Text style={{ color: theme.colors.subtext, fontWeight: '700' }}>
                Total {fmtEUR0(total)}
              </Text>
            </View>
          </Card>
        );
      })}

      {/* Bottom-centered Download Overview */}
      <View style={{ alignItems: 'center', marginBottom: theme.spacing.xl }}>
        <Pressable
          onPress={() => {}}
          style={{
            borderWidth: 1,
            borderColor: theme.colors.navy,
            paddingVertical: theme.spacing.sm,
            paddingHorizontal: theme.spacing.xl,
          }}
        >
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Download overview</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
TSX

echo "→ Items page polished."
