/**
 * UserStatsSection — items / value / categories, as a row inside the profile
 * card rather than a bordered box within it.
 *
 * De-boxed 2026-08-20. The 2026-08-19 pass took the border and fill off the
 * TRADING section for exactly this reason — "three visual languages before the
 * first CTA" — and left this one framed, so the card still opened with a box
 * inside a box. The stats did not need a container to be a group: three
 * columns and a hairline above them say the same thing with none of the
 * chrome, and they now share an alignment with the sections below.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { formatPrice } from '@/lib/format';
import { GAMIFICATION_UI_ENABLED } from '@/config/featureFlags';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';
import type { PublicUserProfile } from '@/data';

interface UserStatsSectionProps {
  profile: PublicUserProfile;
  gamProfile: { xp: number; level: number; streak_days: number } | null;
}

export const UserStatsSection = React.memo(function UserStatsSection({
  profile,
  gamProfile,
}: UserStatsSectionProps) {
  const { colors } = useAppTheme();

  return (
    <>
      {/* Quick stats row */}
      <View style={[styles.quickStatsRow, { borderTopColor: colors.border }]}>
        <View style={styles.quickStat}>
          <Text style={[styles.quickStatValue, { color: colors.text }]}>{profile.collectionCount ?? 0}</Text>
          <Text style={[styles.quickStatLabel, { color: colors.muted }]}>Items</Text>
        </View>
        <View style={[styles.quickStatDivider, { backgroundColor: colors.border }]} />
        <View style={styles.quickStat}>
          {/* The ACTUAL total, not a thousands-rounded one. `Math.round(v/1000)}k`
              rendered a €450 collection as "€0k" and €1,600 as "€2k" — it never
              matched the sum of the items on any collection under five figures.
              Compact form only kicks in where it genuinely helps readability.

              `== null`, not falsy: the view returns NULL when the owner turned
              off "Show collection value" in Privacy, and 0 is a real answer for
              a collection of unpriced items. Showing "—" for a true zero would
              read as "hidden". */}
          <Text style={[styles.quickStatValue, { color: colors.text }]}>
            {profile.collectionValueEur == null
              ? '\u2014'
              : profile.collectionValueEur >= 100000
                ? `\u20AC${Math.round(profile.collectionValueEur / 1000)}k`
                : formatPrice(profile.collectionValueEur, 'EUR')}
          </Text>
          <Text style={[styles.quickStatLabel, { color: colors.muted }]}>Value</Text>
        </View>
        {/* The divider belongs to the tile after it: with the third stat gone,
            a hairline hanging off the right of "Value" reads as a column that
            failed to load rather than as one that does not apply. */}
        {(GAMIFICATION_UI_ENABLED && gamProfile && gamProfile.xp > 0) || profile.interests ? (
          <View style={[styles.quickStatDivider, { backgroundColor: colors.border }]} />
        ) : null}
        {/* Either they have XP or they don't. `gamProfile` exists for everyone the
            moment the row is created, so this used to show "Lv.1 / 0 XP" on a
            brand-new profile — a stat that says nothing, dressed as an
            achievement. Below the first point it falls back to Categories, which
            is a fact about them either way.

            2026-08-10: gated off entirely behind GAMIFICATION_UI_ENABLED — XP is
            not a launch priority. The Categories tile is now what everyone sees,
            so this row never renders a level. No layout change: the fallback
            branch already existed and occupied the same slot. */}
        {GAMIFICATION_UI_ENABLED && gamProfile && gamProfile.xp > 0 ? (
          <View style={styles.quickStat}>
            <Text style={[styles.quickStatValue, { color: colors.text }]}>Lv.{gamProfile.level}</Text>
            <Text style={[styles.quickStatLabel, { color: colors.muted }]}>{gamProfile.xp} XP</Text>
          </View>
        ) : profile.interests ? (
          /* Only when `interests` is a real array. It arrives NULL from
             `getPublicProfile` — `user_public_profile_v1` has no such column —
             and `?? 0` turned that into a confident "0 Categories" sitting
             directly above a Collects list naming six of them. Seen on the sim
             2026-08-20. "We did not ask" is not "none"
             ([[learning_empty_answer_rendered_as_zero]]); the row simply drops
             to the two stats it can actually answer. */
          <View style={styles.quickStat}>
            <Text style={[styles.quickStatValue, { color: colors.text }]}>{profile.interests.length}</Text>
            <Text style={[styles.quickStatLabel, { color: colors.muted }]}>Categories</Text>
          </View>
        ) : null}
      </View>

      {/* Streak badge */}
      {gamProfile && gamProfile.streak_days > 0 && (
        <View style={[styles.streakBadge, { backgroundColor: colors.tier.gold + '15', borderColor: colors.tier.gold + '30' }]}>
          <Ionicons name="flame-outline" size={14} color={colors.tier.gold} />
          <Text style={[styles.streakText, { color: colors.tier.gold }]}>
            {gamProfile.streak_days} day streak
          </Text>
        </View>
      )}
    </>
  );
});

const styles = StyleSheet.create({
  quickStatsRow: {
    flexDirection: 'row',
    marginTop: 16,
    paddingTop: 14,
    borderTopWidth: StyleSheet.hairlineWidth,
    width: '100%',
  },
  quickStat: {
    flex: 1,
    alignItems: 'center',
  },
  quickStatDivider: {
    width: StyleSheet.hairlineWidth,
    height: 28,
    alignSelf: 'center',
    marginHorizontal: 8,
  },
  quickStatValue: {
    fontSize: textToken.xl,
    fontWeight: fw.bold,
  },
  quickStatLabel: {
    fontSize: textToken.sm,
    marginTop: 2,
  },
  streakBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    // flex-start, not center: it used to be the one centred element in a card
    // whose every other line is left-aligned, so it read as a floating chip.
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.md,
    borderWidth: 1,
    marginTop: 12,
  },
  streakText: {
    fontSize: textToken.sm,
    fontWeight: fw.semibold,
  },
});
