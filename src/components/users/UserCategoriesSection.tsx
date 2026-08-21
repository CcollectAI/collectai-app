/**
 * UserCategoriesSection — what this collector collects, and where they place.
 *
 * The profile showed totals and achievements, so two members with completely
 * different collections read almost identically: same badges, different
 * numbers. "What are they into?" is the first thing anyone actually wants from
 * a collector's profile, and the app knew the answer the whole time.
 *
 * Each row is a category the member holds, ordered by how much of it they have,
 * with their rank inside that category's leaderboard and a tap through to the
 * board itself.
 *
 * THREE STATES, NOT TWO
 * ---------------------
 * `rank === null` means NOT RANKED and is rendered as its own thing, never as a
 * number. It happens when the member is not discoverable, or hides their item
 * count — and it is the COMMON case, not an edge one, because discovery is off
 * by default. Printing "#— of —" or falling back to the row position would
 * invent a placement the server deliberately refused to compute
 * (learning_empty_answer_rendered_as_zero).
 *
 * Likewise a hidden value arrives as `0` with `valueVisible: false` on the
 * response, and "€0.00" is a claim about a collection while "hidden" is a
 * statement about a setting. They get different text.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import type { Href } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { formatPrice, formatNumber } from '@/lib/format';
import { getCollectorCategories, type CollectorCategoryStanding } from '@/api/socialApi';
import { getCategoryById } from '@/data/categories';
import logger from '@/utils/logger';

type Props = {
  userId: string;
  /** True when this is the signed-in member's own profile. Only changes copy. */
  isSelf?: boolean;
};

export const UserCategoriesSection = React.memo(function UserCategoriesSection({
  userId,
  isSelf = false,
}: Props) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const router = useRouter();

  const [rows, setRows] = useState<CollectorCategoryStanding[] | null>(null);
  const [valueVisible, setValueVisible] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setFailed(false);
    getCollectorCategories(userId)
      .then((d) => {
        if (cancelled) return;
        setRows(d?.categories ?? []);
        setValueVisible(d?.value_visible ?? true);
      })
      .catch((e) => {
        if (cancelled) return;
        // logger.error, not warn: warn is stripped in release builds, which is
        // where a silently missing profile section would never be noticed.
        logger.error('[UserCategories] fetch failed:', e);
        setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  // A failed request and an empty collection are different facts. Neither is
  // rendered as the other, and neither is rendered as nothing at all — a
  // section that silently disappears on error is indistinguishable from a
  // member who collects nothing.
  if (rows !== null && rows.length === 0 && !failed) {
    return (
      <View style={styles.section}>
        <Text style={[styles.heading, { color: colors.text }]}>Collects</Text>
        <Text style={[styles.empty, { color: colors.muted }]}>
          {isSelf
            ? 'Nothing here yet. Add something to your collection and your categories will appear.'
            : 'This collector has not added anything yet.'}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.section}>
      <Text style={[styles.heading, { color: colors.text }]}>Collects</Text>

      {failed ? (
        <Text style={[styles.empty, { color: colors.muted }]}>
          Couldn&apos;t load categories right now.
        </Text>
      ) : rows === null ? (
        <ActivityIndicator style={{ marginTop: 12 }} color={colors.accent} />
      ) : (
        // TWO COLUMNS, not six stacked rows — see `grid` below.
        <View style={styles.grid}>
        {rows.map((r) => {
          const name = getCategoryById(r.category_id)?.name ?? r.category_id;
          const ranked = r.rank !== null && r.total_ranked !== null;
          return (
            <AnimatedPressable
              key={r.category_id}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                router.push(`/leaderboard?categoryId=${encodeURIComponent(r.category_id)}` as Href);
              }}
              style={[styles.tile, { borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel={
                `${name}, ${r.item_count} ${r.item_count === 1 ? 'item' : 'items'}` +
                (ranked ? `, ranked ${r.rank} of ${r.total_ranked}` : ', not ranked')
              }
              accessibilityHint={`Double tap to open the ${name} leaderboard`}
            >
              <Text style={[styles.catName, { color: colors.text }]} numberOfLines={1}>
                {name}
              </Text>
              <Text style={[styles.catMeta, { color: colors.muted }]} numberOfLines={1}>
                {formatNumber(r.item_count, settings.numberLocale)}{' '}
                {r.item_count === 1 ? 'item' : 'items'}
                {valueVisible
                  ? ` · ${formatPrice(r.value_eur, settings.currency, settings.numberLocale)}`
                  : ' · value hidden'}
              </Text>
              {/* Rank on its own line INSIDE the tile. In a half-width tile a
                  trailing pill plus a chevron would take the room the category
                  name needs, and the name is what identifies the tile. The
                  whole tile is the tap target, so the chevron is gone too — a
                  chevron per tile, twelve times, is decoration. */}
              {ranked ? (
                <View style={[styles.rankPill, { backgroundColor: colors.accent + '15' }]}>
                  <Ionicons name="trophy-outline" size={12} color={colors.accent} />
                  <Text style={[styles.rankText, { color: colors.accent }]} numberOfLines={1}>
                    #{r.rank}
                    <Text style={[styles.rankOf, { color: colors.muted }]}> of {r.total_ranked}</Text>
                  </Text>
                </View>
              ) : (
                <Text style={[styles.unranked, { color: colors.muted }]} numberOfLines={1}>Not ranked</Text>
              )}
            </AnimatedPressable>
          );
        })}
        </View>
      )}

      {/* Only on your own profile, and only when something is actually being
          withheld — telling a stranger why THIS member has no rank would be
          reporting their privacy settings to someone else. */}
      {isSelf && rows?.some((r) => r.rank === null) ? (
        <Text style={[styles.hint, { color: colors.muted }]}>
          Turn on Allow discovery in Settings → Privacy to be ranked on category
          leaderboards.
        </Text>
      ) : null}
    </View>
  );
});

const styles = StyleSheet.create({
  // Same as the trading strip: the card's padding IS the gutter, so this adds
  // none of its own. It used to add 16 on top of the card's, indenting the
  // whole collects list past everything else in the card.
  section: { marginTop: 20 },
  heading: { fontSize: 16, fontWeight: '700', marginBottom: 10 },
  /**
   * ONE bordered container holding hairline-separated rows.
   *
   * Reported 2026-08-19 as *"the collects is stacked on top of each other"*,
   * and that is exactly what it was: every category rendered its OWN
   * `borderWidth: 1, borderRadius: 12` box with an 8pt gap, so a collector in
   * six categories got six stacked outlines. Same failure the watchlist card
   * had — a list of framed boxes reads as a wall, not as a list
   * (docs/ui-playbook.md, "a list card is a reference row").
   *
   * One frame, N rows, separators between them. Each row is still tappable and
   * still opens that category's leaderboard.
   */
  /**
   * TWO COLUMNS (2026-08-20).
   *
   * The history of this block is a straight line of the same mistake at
   * decreasing severity: six framed boxes → one framed list → six unframed
   * full-width rows. Reported each time as stacking, and the last version was
   * still ~90pt per category, so a collector in six categories spent an entire
   * screen on them and the CTA row fell off the bottom.
   *
   * A category is a SMALL fact — a name, a count, a rank. It does not need the
   * full width of the phone, and giving it that width is what forced the
   * stack. Two columns halve the height with nothing hidden and no horizontal
   * scroll (which would hide half of them behind a gesture nobody is told
   * about).
   *
   * `flexBasis: '47%'` rather than a computed width: the card's padding is not
   * this component's business, and a percentage of whatever width it is handed
   * survives being moved.
   */
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tile: {
    // flexGrow: 0. With `flexGrow: 1` an ODD number of categories stretched the
    // last tile across the full width, so a collector in five categories got
    // four half tiles and one wide one — a layout that looks like a bug. Lena
    // V. has six, which is exactly the data that cannot show this
    // (CLAUDE.md, "the happy path is verified against data that CANNOT
    // DISCRIMINATE"). 48% + the 8pt gap fills the row without growing.
    flexGrow: 0,
    flexBasis: '48%',
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 9,
    gap: 3,
  },
  catName: { fontSize: 14, fontWeight: '600' },
  // 12, not 11: docs/ui-playbook.md puts captions at `sm` and bans anything
  // below it for text a user reads.
  catMeta: { fontSize: 12, lineHeight: 16, marginTop: 2 },
  rankPill: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
  },
  rankText: { fontSize: 12, fontWeight: '700' },
  rankOf: { fontSize: 11, fontWeight: '500' },
  unranked: { fontSize: 11 },
  empty: { fontSize: 13, lineHeight: 19 },
  hint: { fontSize: 11, lineHeight: 16, marginTop: 4 },
});
