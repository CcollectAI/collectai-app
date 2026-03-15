/**
 * UserCollectionPreview — interests pills + bio card for user profiles.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';
import type { PublicUserProfile } from '@/data';

// ─────────────────────────────────────────────────────────────────────────────
// SectionCard (local helper)
// ─────────────────────────────────────────────────────────────────────────────
const SectionCard = React.memo(function SectionCard({ title, icon, children }: {
  title: string;
  icon?: keyof typeof Ionicons.glyphMap;
  children: React.ReactNode;
}) {
  const { colors } = useAppTheme();

  return (
    <View style={[styles.sectionCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.sectionHeader}>
        {icon && <Ionicons name={icon} size={16} color={colors.accent} />}
        <Text style={[styles.sectionTitle, { color: colors.muted }]}>{title}</Text>
      </View>
      {children}
    </View>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Props
// ─────────────────────────────────────────────────────────────────────────────
interface UserCollectionPreviewProps {
  profile: PublicUserProfile;
}

export const UserCollectionPreview = React.memo(function UserCollectionPreview({
  profile,
}: UserCollectionPreviewProps) {
  const { colors } = useAppTheme();
  const router = useRouter();

  return (
    <>
      {/* Bio Card */}
      {profile.bio && (
        <SectionCard title="About" icon="person-outline">
          <Text style={[styles.bioText, { color: colors.text }]}>{profile.bio}</Text>
        </SectionCard>
      )}

      {/* Interests Card */}
      {profile.interests && profile.interests.length > 0 && (
        <SectionCard title="Interests" icon="heart-outline">
          <View style={styles.interestsRow}>
            {profile.interests.map((interest, idx) => (
              <AnimatedPressable
                key={idx}
                style={[styles.interestPill, { backgroundColor: colors.accent + '10', borderColor: colors.accent + '30' }]}
                onPress={() => router.push(`/categories/${encodeURIComponent(interest)}`)}
                accessibilityRole="button"
                accessibilityLabel={`Browse ${interest}`}
              >
                <Text style={[styles.interestText, { color: colors.accent }]}>{interest}</Text>
              </AnimatedPressable>
            ))}
          </View>
        </SectionCard>
      )}
    </>
  );
});

const styles = StyleSheet.create({
  // Section card
  sectionCard: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: 16,
    marginTop: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: textToken.sm,
    fontWeight: fw.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },

  // Bio
  bioText: {
    fontSize: textToken.md,
    lineHeight: 20,
  },

  // Interests
  interestsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  interestPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  interestText: {
    fontSize: textToken.md,
    fontWeight: fw.medium,
  },
});
