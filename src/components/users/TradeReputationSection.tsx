/**
 * TradeReputationSection — a member's trading record, on their profile.
 *
 * `GET /p2p/members/{id}/reputation` has existed since Stage 2 and had ZERO
 * callers until 2026-08-18: built, exported through
 * `collectorsApi.p2pMemberReputation`, reached from nowhere. The listing DETAIL
 * screen showed the same facts by a different route, so a rating you left was
 * visible on the seller's items and nowhere on the seller
 * (learning_complete_feature_reachable_from_nowhere).
 *
 * What it may say is fixed by P2P spec §5b: `completed_trades` and a positive
 * percentage are FACTS about platform history and are allowed. "Verified
 * seller" is a representation about a person and is never rendered here, by
 * anything, at any threshold.
 *
 * Not stars. Grades are thumbs (`member_grades.verdict`), and a 4.7/5 painted
 * over a binary vote implies a precision the data cannot carry.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useAppTheme } from '@/hooks/useAppTheme';
import { useAsync } from '@/hooks/useAsync';
import { collectorsApi } from '@/api/collectorsApi';
import { text as textToken, fontWeight as fw } from '@/theme/tokens';

interface TradeReputationSectionProps {
  userId: string;
  /** Your own profile — changes the supporting line, never the numbers. */
  isSelf?: boolean;
}

export const TradeReputationSection = React.memo(function TradeReputationSection({
  userId,
  isSelf = false,
}: TradeReputationSectionProps) {
  const { colors } = useAppTheme();

  const { data: rep } = useAsync(
    () => collectorsApi.p2pMemberReputation(userId),
    [userId],
  );

  // Render NOTHING until there is something true to say. A bordered card
  // holding "0 trades" does not read as "this member has not traded yet", it
  // reads as a component that failed to load (ui-playbook: an always-rendered
  // card is an empty grey box when its field is null) — and on a pre-launch
  // marketplace that would be every profile in the app.
  if (!rep) return null;
  const trades = rep.completed_trades ?? 0;
  const grades = rep.total_grades ?? 0;
  if (trades === 0 && grades === 0) return null;

  // `positive_pct` is null below the server's threshold (3 grades) and that is
  // deliberate: "0% positive" off one grade is a smear, "100%" off one is not
  // credibility. The client must NOT divide positive_grades by total_grades to
  // fill the gap — that re-derives a rule the server owns and publishes
  // exactly what the threshold exists to withhold.
  const pct = rep.positive_pct;
  const tradeLabel = `${trades} completed trade${trades === 1 ? '' : 's'}`;

  return (
    <View style={styles.strip}>

      {pct != null ? (
        <View style={styles.figureRow}>
          {/* The glyph carries the verdict, so it is information rather than
              decoration — the one case the prose-page "no icon per heading"
              rule leaves open. */}
          <Ionicons
            name="thumbs-up"
            size={15}
            color={pct >= 80 ? colors.success : colors.text}
          />
          <Text style={[styles.figure, { color: colors.text }]}>{pct}% positive</Text>
          <Text style={[styles.sub, { color: colors.muted }]}>· {tradeLabel}</Text>
        </View>
      ) : (
        <View style={styles.figureRow}>
          {/* The trade COUNT is a fact and is meaningful at n=1, so it shows
              from the first trade while the percentage waits. Saying which is
              which beats a blank, which reads as "badly rated" rather than
              "not enough ratings yet". */}
          <Text style={[styles.figure, { color: colors.text }]}>{tradeLabel}</Text>
          <Text style={[styles.sub, { color: colors.muted }]}>
            · {grades === 0
              ? 'no ratings yet'
              : `${grades} rating${grades === 1 ? '' : 's'}, too few to score`}
          </Text>
        </View>
      )}

      {rep.withdrawn_count > 0 ? (
        <Text style={[styles.sub, { color: colors.muted }]}>
          Walked away from {rep.withdrawn_count} agreed trade
          {rep.withdrawn_count === 1 ? '' : 's'}
        </Text>
      ) : null}

      {isSelf ? (
        <Text style={[styles.selfNote, { color: colors.muted }]}>
          Buyers see this on every item you list.
        </Text>
      ) : null}
    </View>
  );
});

const styles = StyleSheet.create({
  /**
   * A STRIP under the stats row, not a card of its own — reported 2026-08-19
   * as *"the trading section is not well integrated"*, and it was: the profile
   * opened with three different card idioms in a row. `UserStatsSection`'s
   * bordered stats box, then this bordered box with a small muted "Trading"
   * label, then "Collects" as a 16/700 section heading. Three visual languages
   * before the first CTA.
   *
   * Trading belongs to the same question the stats row answers — who is this
   * collector — so it now reads as the last line OF that block rather than as
   * the first line of a new one. No border, no fill, no heading of its own:
   * the numbers are the content, and the row above already frames them.
   */
  strip: {
    marginHorizontal: 16,   // the screen gutter, same as every other block here
    marginTop: 10,
    gap: 4,
  },
  // flexWrap, so a long percentage plus trade count on a narrow phone wraps
  // instead of truncating the half that carries the credibility.
  figureRow: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  figure: { fontSize: textToken.md, fontWeight: fw.bold },
  sub: { fontSize: textToken.sm },
  // `sm`, not `xs`: 10pt is banned for anything a user reads (ui-playbook,
  // "Type scale"). Italic already marks it as an aside.
  selfNote: { fontSize: textToken.sm, lineHeight: 17, fontStyle: 'italic' },
});

export default TradeReputationSection;
