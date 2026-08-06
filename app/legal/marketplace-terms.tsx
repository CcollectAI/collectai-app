/**
 * Marketplace Terms — member-to-member listings (Stage 1).
 *
 * These are SEPARATE from the main Terms of Service on purpose. The main terms
 * cover Sparrow as a collection tracker and price-reference tool; this covers
 * a fundamentally different relationship — members transacting with each
 * other, with Sparrow as a neutral host.
 *
 * Everything here reflects what the code ACTUALLY does. Specifically:
 *  - Sparrow never touches funds (there is no payment endpoint — enforced by a
 *    test, see server/tests/test_p2p_listing_router.py).
 *  - Reports go to `listing_reports` with a status and a resolution note, which
 *    is what makes a statement of reasons possible.
 *  - Nothing is authenticated or vetted by us, and we do not claim otherwise.
 *
 * ⚠️ NOT legal advice and NOT a substitute for review. Before Stage 3
 * (payments/escrow) a Dutch lawyer must review this — PSD2, DAC7 reporting and
 * consumer-withdrawal rights all change the moment money flows through us.
 * See docs/P2P_MARKETPLACE_SPEC.md §5.
 */
import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { safeGoBack } from '@/lib/goBack';

const LAST_UPDATED = 'August 7, 2026';

function MarketplaceTermsInner() {
  const router = useRouter();
  const { colors } = useAppTheme();

  const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
    <View style={styles.section}>
      <Text style={[styles.h2, { color: colors.text }]}>{title}</Text>
      <Text style={[styles.body, { color: colors.muted }]}>{children}</Text>
    </View>
  );

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <AnimatedPressable
          onPress={() => safeGoBack(router)}
          accessibilityRole="button"
          accessibilityLabel="Go back"
        >
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Marketplace Terms</Text>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={[styles.updated, { color: colors.muted }]}>Last updated: {LAST_UPDATED}</Text>

        <Section title="1. What the marketplace is">
          Sparrow Collect lets members list collectibles they own and contact each
          other about them. Sparrow is a neutral host: we publish listings and
          pass messages. We are not a party to any sale.{'\n\n'}
          <Text style={{ color: colors.text }}>
            We do not process payments, hold funds, ship items, or verify that any
            item is genuine, accurately described, or owned by the person listing it.
          </Text>{' '}
          Buyers and sellers arrange payment and delivery entirely between themselves,
          using whatever method they agree on, at their own risk.
        </Section>

        <Section title="2. There is no buyer protection">
          Because we never handle payment, we cannot refund you, reverse a transfer,
          hold money in escrow, or intervene in a dispute. Protections you may be
          used to on other marketplaces do not exist here. If a transaction goes
          wrong, your recourse is with the other member and, where applicable, your
          payment provider or the police.
        </Section>

        <Section title="3. Your responsibilities as a seller">
          You may only list items you own and are legally entitled to sell. Your
          listing must describe the item honestly, including flaws, damage,
          restoration and whether it is a reproduction.{'\n\n'}
          Photos: where a listing has no photo of your own, we may show a catalogue
          image of the same product. That image is labelled &quot;Catalog photo&quot;
          and is not a picture of your item. You are responsible for making the
          actual condition clear.{'\n\n'}
          If you sell in the course of a business rather than as a private
          individual, you are a trader under EU consumer law and take on additional
          obligations — including a 14-day right of withdrawal — that Sparrow does
          not administer for you. You must identify yourself as a trader if you are one.
        </Section>

        <Section title="4. Prohibited items">
          You may not list: counterfeit, replica or unauthorised reproductions
          presented as genuine; stolen goods; items you do not have; weapons;
          hazardous materials; anything whose sale is restricted where you or the
          buyer live; or any item that infringes someone else&apos;s trade mark or
          copyright.{'\n\n'}
          Graded or authenticated items must show the real certification and grader.
          Do not describe an item as authenticated by Sparrow — we authenticate nothing.
        </Section>

        <Section title="5. Reporting and enforcement">
          Every listing has a Report action. Reports are recorded with a reason and
          reviewed. Where we act on a report we will remove or restrict the listing
          and record the reason for that decision, and we will inform the affected
          member.{'\n\n'}
          We may remove listings, restrict marketplace access, or close accounts
          where these terms are breached. Repeated or serious breaches — in
          particular counterfeits — will end marketplace access.
        </Section>

        <Section title="6. Taxes">
          You are responsible for any tax arising from your sales, including income
          tax and VAT where it applies to you. Sparrow does not withhold, collect,
          or report tax on your behalf at this stage. If we later introduce payment
          processing, reporting obligations may apply to us and to you, and we will
          tell you before that happens.
        </Section>

        <Section title="7. Your data">
          Listing a item publishes its title, photo, price, condition, category and
          your display name to other members. Messages you send are delivered to the
          member you contact. See the Privacy Policy for how we handle personal data
          and how to request deletion.
        </Section>

        <Section title="8. Liability">
          To the fullest extent permitted by law, Sparrow Collect is not liable for
          loss arising from a transaction between members, including items that are
          not delivered, not as described, counterfeit, or payment that is not
          received. Nothing in these terms limits liability that cannot be limited
          by law, including for death or personal injury caused by negligence, or
          your statutory rights as a consumer against a trader.
        </Section>

        <Section title="9. Changes">
          We may update these terms as the marketplace develops — in particular if
          payment processing is introduced, which would materially change the
          relationship between you, the other member, and us. Material changes will
          be notified in the app before they take effect.
        </Section>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

export default function MarketplaceTermsScreen() {
  return (
    <ScreenErrorBoundary screenName="Marketplace Terms">
      <MarketplaceTermsInner />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  header: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1,
  },
  headerTitle: { fontSize: 18, fontWeight: '700' },
  content: { padding: 20 },
  updated: { fontSize: 12, marginBottom: 20 },
  section: { marginBottom: 22 },
  h2: { fontSize: 16, fontWeight: '700', marginBottom: 8 },
  body: { fontSize: 14, lineHeight: 21 },
});
