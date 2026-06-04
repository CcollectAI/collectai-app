/**
 * CategoryBrandHeader — branded "store" header shown when a brand sponsors a
 * category (the future "brands run their category as a marketing channel" model).
 *
 * STUB: renders nothing until a `sponsor` is supplied. No category has a sponsor
 * today, so this is dark by default — the component is here so the surface exists
 * and can be lit up per-category later (a `category_sponsors` record drives it).
 */
import React from 'react';
import { View, Text, Image, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import type { AppTheme } from '@/hooks/useAppTheme';

export type CategorySponsor = {
  name: string;
  logoUrl?: string | null;
  initial?: string;
  coverColors?: [string, string]; // gradient ends
  itemCount?: number;
  followers?: number;
  storeUrl?: string | null;
};

type Props = {
  sponsor: CategorySponsor | null | undefined;
  colors: AppTheme['colors'];
  onFollow?: () => void;
};

function fmtCount(n?: number): string | null {
  if (n == null) return null;
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
  return String(n);
}

function CategoryBrandHeader({ sponsor, colors, onFollow }: Props) {
  if (!sponsor) return null;
  const cover = sponsor.coverColors ?? ['#312e81', '#db2777'];
  const followers = fmtCount(sponsor.followers);
  const meta = [
    sponsor.itemCount != null ? `${sponsor.itemCount.toLocaleString()} items` : null,
    followers ? `${followers} followers` : null,
  ].filter(Boolean).join(' · ');

  return (
    <View style={styles.hero}>
      <View style={[styles.cover, { backgroundColor: cover[0] }]}>
        {/* simple two-stop gradient fake via overlay block */}
        <View style={[StyleSheet.absoluteFill, { backgroundColor: cover[1], opacity: 0.55 }]} />
        <View style={styles.officialTag}><Text style={styles.officialText}>OFFICIAL</Text></View>
      </View>
      <View style={styles.row}>
        {sponsor.logoUrl ? (
          <Image source={{ uri: sponsor.logoUrl }} style={styles.logo} accessibilityIgnoresInvertColors />
        ) : (
          <View style={[styles.logo, styles.logoFallback]}>
            <Text style={styles.logoInitial}>{sponsor.initial ?? sponsor.name.charAt(0)}</Text>
          </View>
        )}
        <View style={styles.text}>
          <View style={styles.nameRow}>
            <Text style={[styles.name, { color: colors.text }]} numberOfLines={1}>{sponsor.name}</Text>
            <View style={styles.vcheck}><Ionicons name="checkmark" size={10} color="#fff" /></View>
          </View>
          {!!meta && <Text style={[styles.meta, { color: colors.muted }]} numberOfLines={1}>{meta}</Text>}
        </View>
        <AnimatedPressable style={styles.followBtn} onPress={onFollow} accessibilityRole="button" accessibilityLabel="Follow brand">
          <Text style={styles.followText}>Follow</Text>
        </AnimatedPressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { backgroundColor: '#fff' },
  cover: { height: 48, position: 'relative', overflow: 'hidden' },
  officialTag: { position: 'absolute', left: 14, top: 14, backgroundColor: 'rgba(255,255,255,0.22)', borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  officialText: { color: '#fff', fontSize: 9, fontWeight: '800', letterSpacing: 0.4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 11, paddingHorizontal: 14, paddingTop: 10, paddingBottom: 12 },
  logo: { width: 48, height: 48, borderRadius: 13, borderWidth: 1, borderColor: '#E2E8F0' },
  logoFallback: { backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  logoInitial: { fontSize: 23, fontWeight: '900', color: '#3b2c7a' },
  text: { flex: 1, minWidth: 0 },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  name: { fontSize: 17, fontWeight: '900', flexShrink: 1 },
  vcheck: { width: 16, height: 16, borderRadius: 8, backgroundColor: '#3B82F6', alignItems: 'center', justifyContent: 'center' },
  meta: { fontSize: 11, marginTop: 1 },
  followBtn: { backgroundColor: '#3b2c7a', borderRadius: 999, paddingHorizontal: 18, paddingVertical: 8 },
  followText: { color: '#fff', fontSize: 13, fontWeight: '800' },
});

export default React.memo(CategoryBrandHeader);
