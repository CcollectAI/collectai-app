/**
 * Terms of Service screen — displays Sparrow Collect terms.
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

const LAST_UPDATED = 'April 11, 2026';

function TermsOfServiceScreenInner() {
  const router = useRouter();
  const { colors } = useAppTheme();

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <AnimatedPressable
          onPress={() => safeGoBack(router)}
          accessibilityRole="button"
          accessibilityLabel="Go back"
          style={styles.backBtn}
        >
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Terms of Service</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={[styles.updated, { color: colors.muted }]}>Last updated: {LAST_UPDATED}</Text>

        <Text style={[styles.body, { color: colors.text }]}>
          Please read these Terms of Service ("Terms") carefully before using the Sparrow Collect mobile application (the "Service") operated by Sparrow Collect ("we", "our", "us").
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>1. Acceptance of Terms</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          By creating an account or using the Service, you agree to be bound by these Terms, our Privacy Policy, and our Acceptable Use Policy. If you do not agree, do not use the Service.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>2. Account Registration</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          You must provide accurate and complete information when creating an account. You are responsible for maintaining the security of your account credentials, including any multi-factor authentication (MFA) settings. You must be at least 13 years old (or 16 in the EU) to use the Service. You may register using email/password or social login (Google, Apple).
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>3. User Content</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          You retain ownership of all content you upload to the Service, including photos, descriptions, collection data, project notes, and messages. By using the Service, you grant us a limited, non-exclusive license to store, display, and process your content solely to provide the Service to you.{'\n\n'}
          You agree not to upload content that:{'\n'}
          {'\u2022'} Is illegal, offensive, defamatory, or harassing{'\n'}
          {'\u2022'} Infringes on third-party intellectual property rights{'\n'}
          {'\u2022'} Contains malware, viruses, or malicious code{'\n'}
          {'\u2022'} Is deceptive, fraudulent, or misleading{'\n'}
          {'\u2022'} Violates the privacy of other individuals
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>4. AI Scanning & Image Analysis</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>QuickScan:</Text> The QuickScan feature uses AI (OpenAI Vision API and CLIP embeddings) to identify collectible items from photos. QuickScan results, including item name, category, and estimated value, are AI-generated and may contain errors. You are solely responsible for verifying the accuracy of any AI identification before relying on it.
          {'\n\n'}
          <Text style={styles.bold}>Multi-Item Detection:</Text> When scanning multiple items in a single photo, bounding box detection is used to isolate individual items. Detection accuracy depends on photo quality, lighting, and item arrangement. Not all items may be detected in a group photo.
          {'\n\n'}
          <Text style={styles.bold}>Condition Grading:</Text> AI-generated condition grades (including PSA/CGC scale mappings) are estimates only and should not be treated as equivalent to professional grading services. AI condition assessments may differ significantly from grades assigned by professional grading companies (PSA, CGC, Beckett, etc.). We strongly recommend professional grading for high-value items. We are not liable for any losses incurred from relying on AI condition assessments.
          {'\n\n'}
          <Text style={styles.bold}>Screenshot Analysis:</Text> Analyzing screenshots or gallery photos is subject to the same accuracy limitations as camera scanning. Results depend on image quality and clarity.
          {'\n\n'}
          <Text style={styles.bold}>Comparison Scan:</Text> The side-by-side comparison feature is provided for informational purposes. Comparison results are AI-generated and should be independently verified.
          {'\n\n'}
          <Text style={styles.bold}>Accuracy Disclaimer:</Text> While we strive to improve AI accuracy continuously, all AI features are provided "as is." We make no guarantees regarding the correctness of item identification, categorization, condition assessment, or valuation. AI confidence scores indicate model certainty, not objective accuracy.
          {'\n\n'}
          <Text style={styles.bold}>Structured Attribute Extraction:</Text> QuickScan extracts category-specific structured attributes from scanned items (e.g. brand, reference number, set name, card number, year). These attributes are saved to your item record alongside the AI-identified name and category. Extracted attributes are AI-generated estimates and may contain errors. You can edit or remove any extracted attribute from the item detail screen. You are responsible for verifying and correcting attributes before relying on them for insurance, sale, or valuation purposes.
          {'\n\n'}
          <Text style={styles.bold}>Attribute Canonicalization:</Text> Extracted attribute values may be automatically "snapped" to canonical forms from our catalog vocabulary (e.g. "rolex" → "Rolex") to keep your collection consistent. Canonicalization is performed on extraction only — it does not retroactively modify items you previously saved.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>5. Price Estimates & Valuations</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Price estimates provided by Sparrow Collect are for informational purposes only. They are generated using machine learning models (Ridge regression with q10/q50/q90 quantile predictions) and aggregated marketplace data from 37 sources across 54 collectible categories. These estimates should not be relied upon as financial advice, appraisals, or insurance valuations. Actual market prices may differ significantly. We make no guarantees about the accuracy of any valuation.{'\n\n'}
          Scarcity scores, demand heat signals, and social proof indicators (collector counts, trending status) are derived from aggregated data and are for informational purposes only. They should not be the sole basis for purchasing or selling decisions.{'\n\n'}
          Currency conversions are approximate and based on exchange rates refreshed every 8 hours. Shipping cost estimates are approximations and may differ from actual shipping costs.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>6. Marketplace Integration & Affiliate Links</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Sparrow Collect aggregates data from 37 third-party marketplace sources for reference and price comparison, including but not limited to: eBay, TCGPlayer, Cardmarket, Discogs, StockX, BrickLink, BrickEconomy, Mercari, PriceCharting, Yahoo Auctions JP, AmiAmi, WhatNot, Vinted, Catawiki, Mandarake, Bezel, Chrono24, WhiskyAuctioneer, MasterOfMalt, KEH, MPB, PopMart, Booth.pm, ScaleMates, Drop, GouletPens, KTown4U, ComicBookRealm, Firecrawl, Crawl4AI, Mavin.io, Scrape.do, Google Shopping, and Etsy. We are not responsible for:{'\n'}
          {'\u2022'} Transactions conducted on these platforms{'\n'}
          {'\u2022'} The accuracy of third-party listing information{'\n'}
          {'\u2022'} Disputes between buyers and sellers{'\n'}
          {'\u2022'} Changes to third-party platform terms or availability{'\n\n'}
          Marketplace links contain affiliate tags where available (currently eBay, TCGPlayer, Cardmarket, Mercari, Discogs, StockX, and BrickLink). When you purchase through an affiliate link, we may receive a commission at no additional cost to you. Affiliate links appear on item detail pages, watchlist, category browse, marketplace search results, and deal notifications.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>7. Multi-Marketplace Selling</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The Service allows you to create listings to sell items from your collection across multiple marketplaces. By creating a listing, you acknowledge that:{'\n'}
          {'\u2022'} Sparrow Collect facilitates listing creation but is not a party to any sale transaction{'\n'}
          {'\u2022'} You are solely responsible for the accuracy of your listing information, including item description, condition, photos, and pricing{'\n'}
          {'\u2022'} You are responsible for fulfilling orders, handling shipping, and resolving disputes with buyers{'\n'}
          {'\u2022'} Marketplace-specific rules and fees apply in addition to Sparrow Collect terms{'\n'}
          {'\u2022'} A platform fee may apply to sales facilitated through the Service — current fee schedules are displayed at listing creation{'\n'}
          {'\u2022'} We reserve the right to modify fee structures with 30 days advance notice{'\n\n'}
          We are not liable for failed transactions, shipping issues, buyer disputes, or any losses arising from peer-to-peer sales. The Deal Desk feature facilitates offers and counteroffers between users but does not guarantee completion of any transaction.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>8. User Corrections & Feedback</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          When you correct an AI identification, category assignment, or condition grade, your correction may be used to improve the AI models that power the Service for all users. By submitting a correction, you grant us a perpetual, irrevocable, royalty-free license to use the correction data for model training and improvement.{'\n\n'}
          Corrections are anonymized before being incorporated into training data — they are stripped of any association with your account or personal information. You may submit corrections at any time through the scan result interface. We are not obligated to implement any specific correction, and corrections may be aggregated with other data sources before being used for training.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>9. Gamification & Leaderboard</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The Service includes gamification features such as experience points (XP), levels, daily streaks, achievements, and a public leaderboard. These features are provided for entertainment and engagement purposes only.{'\n\n'}
          {'\u2022'} XP, levels, achievements, and streaks have no monetary value and cannot be exchanged, traded, or redeemed for real-world currency or goods{'\n'}
          {'\u2022'} Your leaderboard position, XP total, level, and achievements may be visible to other users{'\n'}
          {'\u2022'} We reserve the right to adjust XP values, level thresholds, achievement criteria, and leaderboard calculations at any time without prior notice{'\n'}
          {'\u2022'} Attempts to manipulate gamification metrics (e.g., creating fake items to earn XP, exploiting bugs) may result in XP resets and account restrictions{'\n'}
          {'\u2022'} Gamification data is deleted when you delete your account
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>10. Smart Deal Agent</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The Smart Deal Agent feature automatically scans marketplaces based on your purchase mandates (search criteria, price limits, budget). By creating a mandate, you authorize the Service to monitor marketplace listings on your behalf. The Deal Agent does not make purchases automatically — it notifies you of matching deals for your review. You are solely responsible for any purchase decisions.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>11. Watchlist & Price Alerts</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The watchlist feature monitors items for price changes and sends automated alerts when prices cross your configured thresholds. Price monitoring relies on data from third-party marketplaces and may not capture all price changes in real-time. We do not guarantee the timeliness or completeness of price alerts. Alert notifications are subject to push notification delivery by your device and operating system.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>12. Events & Social Features</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>Events:</Text> Users may create, host, and attend collector events. Event hosts are responsible for the accuracy of event information. RSVP attendance may be limited by capacity settings. Events may require paid tickets — ticket purchases are processed through Stripe and are non-refundable unless the event is cancelled by the host. A platform fee of 5% is applied to ticket sales. We are not responsible for the conduct of event hosts or attendees, or for events that are cancelled or modified.{'\n\n'}
          <Text style={styles.bold}>Nearby Events:</Text> The Nearby Events feature uses precise GPS location (with your permission) to show events near your current location. Location data is processed in real-time and not stored.{'\n\n'}
          <Text style={styles.bold}>Direct Messaging:</Text> Users may send direct messages to other users via the DM request system. Both parties must consent to a conversation. You agree not to use messaging for spam, harassment, or solicitation. We reserve the right to moderate or restrict messaging for users who violate these Terms.{'\n\n'}
          <Text style={styles.bold}>User Blocking:</Text> You may block other users to prevent them from contacting you. Blocking is mutual — blocked users cannot view your profile or send you messages.{'\n\n'}
          <Text style={styles.bold}>Announcements:</Text> Event hosts and sponsors may send announcements to event attendees. These are one-way communications for event-related information only.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>13. Sponsor Companies</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Businesses may register as sponsor companies to sponsor collector events. Sponsor registration requires a company name, contact email, and optional details. Sponsors may choose per-event payments or monthly subscription billing — both processed through Stripe. Sponsors agree to:{'\n'}
          {'\u2022'} Provide accurate company information{'\n'}
          {'\u2022'} Comply with all applicable advertising and consumer protection laws{'\n'}
          {'\u2022'} Not use sponsor features for deceptive or misleading promotions{'\n\n'}
          Sponsor subscriptions auto-renew monthly until cancelled. Cancellation takes effect at the end of the current billing period. We reserve the right to remove sponsor companies that violate these Terms.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>14. Subscriptions & Payments</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Certain features of the Service require a paid subscription. Payments are processed through Stripe. Subscription terms, pricing, and renewal conditions are presented at the time of purchase. You may cancel your subscription at any time through the app settings. Refunds are handled in accordance with applicable laws and Stripe's policies.{'\n\n'}
          <Text style={styles.bold}>Event Tickets:</Text> Some events require paid tickets. Ticket prices are set by event hosts and include a 5% platform fee. Ticket purchases are one-time payments processed through Stripe. Tickets are non-transferable and tied to your account. If an event is cancelled by the host, refunds will be issued to the original payment method.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>15. Search & Discovery</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The Service provides unified search across items, users, events, categories, and franchises (e.g., Star Wars, Marvel). Search functionality is rate-limited to ensure fair usage. Search results are based on data available within the Service and may not include all collectibles or users. We do not guarantee the completeness or accuracy of search results.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>16. Activity Feed & Profile</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Certain actions you take (adding items, attending events, completing projects, earning achievements) may be displayed in your public activity feed. You can control activity visibility in your privacy settings. Other users may view your public profile, collection statistics, gamification level, and activity feed when not restricted.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>17. Rate Limits & Fair Usage</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          To maintain Service quality for all users, certain features are subject to rate limits (e.g., search queries, photo uploads, QuickScan requests, marketplace lookups, push token registration, event announcements). Exceeding these limits may result in temporary throttling. Persistent abuse may lead to account restrictions.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>18. Prohibited Uses</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          You agree not to:{'\n'}
          {'\u2022'} Use the Service for any unlawful purpose{'\n'}
          {'\u2022'} Attempt to reverse-engineer, decompile, or exploit the Service{'\n'}
          {'\u2022'} Scrape, harvest, or systematically extract data from the Service{'\n'}
          {'\u2022'} Impersonate other users or misrepresent your identity{'\n'}
          {'\u2022'} Upload malicious content, malware, or viruses{'\n'}
          {'\u2022'} Use automated systems, bots, or scripts to access the Service without permission{'\n'}
          {'\u2022'} Circumvent rate limits, security measures, or access controls{'\n'}
          {'\u2022'} Use the messaging system for spam, harassment, or unsolicited commercial messages{'\n'}
          {'\u2022'} Create fake accounts or fraudulent listings{'\n'}
          {'\u2022'} Manipulate gamification metrics or leaderboard rankings{'\n'}
          {'\u2022'} Submit false AI corrections to degrade model quality{'\n'}
          {'\u2022'} Interfere with or disrupt the Service or its infrastructure
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>19. Account Termination</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          You may delete your account at any time through the app settings. Account deletion is permanent and will remove all associated data (collection, projects, messages, events, gamification progress, marketplace listings) within 30 days, in accordance with our Privacy Policy.{'\n\n'}
          We reserve the right to suspend or terminate accounts that:{'\n'}
          {'\u2022'} Violate these Terms or our Acceptable Use Policy{'\n'}
          {'\u2022'} Engage in abusive behavior toward other users{'\n'}
          {'\u2022'} Attempt to exploit or compromise the Service{'\n'}
          {'\u2022'} Are inactive for an extended period (with prior notice)
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>20. Intellectual Property</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The Service, including its design, features, machine learning models, AI classifiers, CLIP embeddings, category taxonomy, and underlying technology, is owned by Sparrow Collect. The Sparrow Collect name, logo, and brand elements are our trademarks. You may not copy, modify, distribute, or create derivative works of any part of the Service without our written consent.{'\n\n'}
          Collectible product names, images, and trademarks referenced within the Service belong to their respective owners and are used for identification purposes only.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>21. Limitation of Liability</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The Service is provided "as is" and "as available" without warranties of any kind, express or implied. To the maximum extent permitted by law, we shall not be liable for:{'\n'}
          {'\u2022'} Any indirect, incidental, special, or consequential damages{'\n'}
          {'\u2022'} Loss of profits, data, or business opportunities{'\n'}
          {'\u2022'} Inaccurate price estimates, valuations, or AI identifications{'\n'}
          {'\u2022'} Inaccurate AI condition grades or defect assessments{'\n'}
          {'\u2022'} Failed or delayed marketplace transactions{'\n'}
          {'\u2022'} Service interruptions or data loss{'\n'}
          {'\u2022'} Actions of other users (messages, events, transactions, sales){'\n'}
          {'\u2022'} Losses arising from peer-to-peer selling or buying{'\n\n'}
          Our total liability to you for any claims arising from the Service shall not exceed the amount you paid us in the 12 months preceding the claim.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>22. Indemnification</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          You agree to indemnify and hold harmless Sparrow Collect from any claims, damages, or expenses arising from your use of the Service, your violation of these Terms, your marketplace listings or sales, or your infringement of any third-party rights.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>23. Automatic Set Completion</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The Service includes an automatic set completion feature that computes your progress toward completing collectible sets (e.g. Pokemon Base Set, LEGO City) by comparing structured attributes on your saved items against our catalog. Set completion percentages are informational only and depend on:
          {'\n'}
          {'\u2022'} The accuracy of structured attributes on your saved items (which you can edit){'\n'}
          {'\u2022'} The completeness of our catalog for a given set{'\n'}
          {'\u2022'} Our interpretation of what constitutes a complete set (which may change as catalogs are refined){'\n\n'}
          Automatic set completion is not authoritative. For serious collection valuation or insurance purposes, consult a professional appraiser.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>24. Advertising</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Sparrow Collect is a freemium product. The free tier may, in the future, display non-intrusive advertising in the app. As of this Terms' "Last updated" date, <Text style={styles.bold}>advertising infrastructure is installed but inactive</Text> — no ads are shown to any user.
          {'\n\n'}
          When ads are activated:{'\n'}
          {'\u2022'} Ads will only appear for users on the free tier. Paid subscribers (Pro, Premium) receive an ad-free experience as a benefit of their subscription.{'\n'}
          {'\u2022'} Ad frequency is throttled: a maximum of 5 interstitial ads per session, a 3-minute cooldown between interstitials, and at most one banner ad per screen.{'\n'}
          {'\u2022'} Ads are served via a third-party mediation network (planned: AppLovin MAX). When activated, the ad provider will be disclosed in the Privacy Policy.{'\n'}
          {'\u2022'} You can remove ads by upgrading to Pro or Premium at any time.{'\n'}
          {'\u2022'} We do not share your collection data, search queries, or account information with ad networks. See the Privacy Policy for details on what data (if any) is shared with ad networks.{'\n\n'}
          You agree that using the free tier may, in the future, include viewing ads. If you object to ads, you may upgrade to a paid tier or discontinue use of the Service.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>25. Changes to Terms</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We reserve the right to modify these Terms at any time. We will notify you of material changes through in-app notifications and by updating the "Last updated" date. Continued use of the Service after changes constitutes acceptance of the new Terms. If you do not agree with the changes, you should stop using the Service.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>26. Governing Law & Disputes</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          These Terms shall be governed by the laws of the Netherlands. Any disputes arising from these Terms or the Service shall be resolved in the courts of the Netherlands. For EU consumers, this does not affect your rights under mandatory consumer protection laws of your country of residence.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>27. Severability</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          If any provision of these Terms is found to be unenforceable, the remaining provisions shall continue in full force and effect.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>28. Contact</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          For questions about these Terms, contact us at:{'\n'}
          legal@sparrowcollect.com{'\n\n'}
          Sparrow Collect{'\n'}
          Ertskade 74, 1019 BB Amsterdam{'\n'}The Netherlands{'\n'}KvK: 99596326
        </Text>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

export default function TermsOfServiceScreen() {
  return (
    <ScreenErrorBoundary screenName="Terms of Service">
      <TermsOfServiceScreenInner />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  backBtn: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  content: {
    paddingHorizontal: 20,
    paddingVertical: 24,
  },
  updated: {
    fontSize: 13,
    marginBottom: 20,
  },
  heading: {
    fontSize: 17,
    fontWeight: '700',
    marginTop: 24,
    marginBottom: 8,
  },
  body: {
    fontSize: 15,
    lineHeight: 24,
  },
  bold: {
    fontWeight: '700',
  },
});
