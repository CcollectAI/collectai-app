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
 *  - The statement of reasons in §5 is real: POST /ops/listing-reports/{id}/action
 *    writes it to notification_history in the same transaction as the takedown,
 *    so a listing cannot be removed with the seller un-notified.
 *  - Blocking in §5 really is service-wide (app/lib/blocks.py). It was chat-only
 *    until 2026-08-07, and this section would have overstated it before then.
 *  - Nothing is authenticated or vetted by us, and we do not claim otherwise.
 *
 * Updated 2026-08-07 after checking the regulations rather than recalling them
 * (docs/P2P_MARKETPLACE_SPEC.md §5a-§5c):
 *  - §3/§3a: GPSR covers second-hand goods. A private seller owes nothing under
 *    it; a trader does. Our exemption from the GPSR/DSA *marketplace* regimes
 *    rests on being C2C, which is why §3 now asks traders to identify
 *    themselves and reserves the right to withdraw access if they don't.
 *  - §6: the old text said reporting obligations would only arise "if we later
 *    introduce payment processing". That was wrong — DAC7 turns on the
 *    consideration being KNOWN, which it already is.
 *
 * ⚠️ NOT legal advice and NOT a substitute for review. A Dutch lawyer should
 * review this before real users, not only before Stage 3.
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
          individual, you are a trader, and most countries impose additional
          obligations on traders — commonly a cooling-off period for the buyer and
          product-safety duties. In the EU and UK that includes a 14-day right of
          withdrawal. Those obligations are yours; Sparrow does not administer them
          for you, and which ones apply depends on where you and your buyer are.{' '}
          <Text style={{ color: colors.text }}>
            The marketplace is for private individuals selling from their own
            collection. You must tell us if you are a trader.
          </Text>{' '}
          We may ask you to confirm your status, and may withdraw marketplace access
          from a trader who does not identify themselves.
        </Section>

        <Section title="3a. Product safety">
          Product-safety law generally applies to second-hand goods as well as new
          ones — the EU General Product Safety Regulation is one example, and most
          countries have an equivalent. A private individual selling from their own
          collection usually has no obligations under it; a trader does, and those
          obligations are theirs, not ours.{'\n\n'}
          <Text style={{ color: colors.text }}>
            Sparrow does not inspect, test or verify the safety of any item.
          </Text>{' '}
          You must not list an item you know to be unsafe, subject to a safety
          recall, or withdrawn from sale. If you learn that something you have sold
          is subject to a recall, tell the buyer and tell us. If you tell us a listed
          item is unsafe, we will remove it and inform the seller of the reason.
        </Section>

        <Section title="4. Prohibited items">
          You may not list: counterfeit, replica or unauthorised reproductions
          presented as genuine; stolen goods; items you do not have; weapons;
          hazardous materials; items subject to a safety recall or otherwise known
          to be unsafe; anything whose sale is restricted where you or the
          buyer live; or any item that infringes someone else&apos;s trade mark or
          copyright.{'\n\n'}
          Graded or authenticated items must show the real certification and grader.
          Do not describe an item as authenticated by Sparrow — we authenticate nothing.
        </Section>

        <Section title="5. Reporting and enforcement">
          Every listing has a Report action. Reports are recorded with a reason and
          reviewed.{' '}
          <Text style={{ color: colors.text }}>
            We act on reports of objectionable or unlawful content within 24 hours
            of receiving them.
          </Text>{'\n\n'}
          Where we decide on a reported listing, we tell the seller: what we
          decided, the ground we relied on, whether the decision was made
          automatically or by a person, and how to contest it. You will receive
          that notice in the app. To contest a decision, contact
          support@sparrowcollect.com and it will be looked at again.{'\n\n'}
          You can also block another member. Blocking is immediate and works in
          both directions across the whole service — their listings stop appearing
          for you, they cannot make you an offer, and neither of you can message
          the other.{'\n\n'}
          We may remove listings, restrict marketplace access, or close accounts
          where these terms are breached. Repeated or serious breaches — in
          particular counterfeits — will end marketplace access.
        </Section>

        <Section title="6. Taxes">
          You are responsible for any tax arising from your sales, including income
          tax and VAT where it applies to you. Sparrow does not withhold or collect
          tax on your behalf.{'\n\n'}
          <Text style={{ color: colors.text }}>
            Many countries require marketplaces to report seller information to
            their tax authority.
          </Text>{' '}
          The EU rules (DAC7) and the equivalent OECD model rules adopted by the UK,
          Canada, Australia, New Zealand, Japan and others work the same way, and
          they can apply to us because we know the agreed price of a trade — even
          though no money passes through us.{'\n\n'}
          Sparrow is established in the Netherlands, so where we report, we report
          to the Belastingdienst, which passes the information to the tax authority
          of the country you live in. Where you live determines what that authority
          then does with it.{'\n\n'}
          <Text style={{ color: colors.text }}>
            Most members are never reported.
          </Text>{' '}
          Under these rules a seller is excluded while they stay under both limits
          in a calendar year: fewer than 30 sales, and no more than EUR 2,000 in
          total. Passing either one — not both — makes a seller reportable.{'\n\n'}
          We count this for you automatically. If you pass either limit we will
          notify you in the app at the time it happens, ask you for the details the
          rules require, and tell you before anything about you is sent. We will not
          report you without telling you first.
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
