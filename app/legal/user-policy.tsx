/**
 * Acceptable Use Policy screen — displays CollectAI community guidelines
 * and acceptable use rules.
 */

import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';

const LAST_UPDATED = 'March 27, 2026';

function UserPolicyScreenInner() {
  const router = useRouter();
  const { colors } = useAppTheme();

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <AnimatedPressable
          onPress={() => router.back()}
          accessibilityRole="button"
          accessibilityLabel="Go back"
          style={styles.backBtn}
        >
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Acceptable Use Policy</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={[styles.updated, { color: colors.muted }]}>Last updated: {LAST_UPDATED}</Text>

        <Text style={[styles.body, { color: colors.text }]}>
          This Acceptable Use Policy ("Policy") governs your conduct when using the CollectAI mobile application (the "Service"). By using the Service, you agree to follow these guidelines. This Policy supplements our Terms of Service and Privacy Policy.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>1. Community Guidelines</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          CollectAI is a community of collectors. We expect all users to:{'\n'}
          {'\u2022'} Treat other users with respect and courtesy{'\n'}
          {'\u2022'} Engage in good faith when buying, selling, or trading{'\n'}
          {'\u2022'} Provide accurate information about items, conditions, and valuations{'\n'}
          {'\u2022'} Respect the diverse collecting interests of our community{'\n'}
          {'\u2022'} Help maintain a welcoming environment for collectors of all experience levels{'\n'}
          {'\u2022'} Use the AI feedback and correction features constructively
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>2. Prohibited Content</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The following content is strictly prohibited on CollectAI:{'\n\n'}
          <Text style={styles.bold}>Illegal Content:</Text> Any content that violates applicable laws, including but not limited to stolen goods, counterfeit items, illegal weapons, controlled substances, or items that violate import/export restrictions.{'\n\n'}
          <Text style={styles.bold}>Counterfeit & Fraudulent Items:</Text> Listing, promoting, or knowingly selling counterfeit, replica, or bootleg items as authentic. If you are selling reproductions or custom items, they must be clearly labeled as such.{'\n\n'}
          <Text style={styles.bold}>Offensive Content:</Text> Content that promotes hate, violence, discrimination, or harassment based on race, ethnicity, gender, sexual orientation, religion, disability, or any other protected characteristic.{'\n\n'}
          <Text style={styles.bold}>Explicit Content:</Text> Sexually explicit material, graphic violence, or content unsuitable for a general audience. CollectAI is intended for users aged 13+ (16+ in the EU).{'\n\n'}
          <Text style={styles.bold}>Private Information:</Text> Posting other people's personal information (doxxing), including real names, addresses, phone numbers, or financial information without their consent.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>3. Harassment & Bullying</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We have zero tolerance for harassment. The following behaviors are prohibited:{'\n'}
          {'\u2022'} Threatening, intimidating, or bullying other users{'\n'}
          {'\u2022'} Sending unwanted, repeated, or aggressive messages{'\n'}
          {'\u2022'} Stalking or monitoring another user's activity to harass them{'\n'}
          {'\u2022'} Creating multiple accounts to circumvent a block or ban{'\n'}
          {'\u2022'} Coordinated attacks or brigading against specific users{'\n'}
          {'\u2022'} Public shaming or targeting users on the leaderboard or in events{'\n'}
          {'\u2022'} Deliberately sabotaging another user's listings, events, or reputation
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>4. Spam & Manipulation</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The following activities are prohibited:{'\n'}
          {'\u2022'} Sending unsolicited commercial messages or advertisements via DMs{'\n'}
          {'\u2022'} Creating bulk or automated accounts{'\n'}
          {'\u2022'} Using bots or scripts to interact with the Service{'\n'}
          {'\u2022'} Manipulating search results, trending data, or social proof metrics{'\n'}
          {'\u2022'} Artificially inflating XP, achievements, or leaderboard rankings{'\n'}
          {'\u2022'} Submitting false AI corrections to degrade model quality{'\n'}
          {'\u2022'} Click fraud on affiliate links{'\n'}
          {'\u2022'} Excessive or abusive use of the QuickScan, watchlist, or alert features beyond normal collecting activity
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>5. Marketplace Listing Guidelines</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          When listing items for sale through CollectAI's multi-marketplace selling feature:{'\n\n'}
          <Text style={styles.bold}>Accuracy:</Text> Item descriptions, photos, and condition grades must accurately represent the item being sold. Do not use AI-generated condition grades as a substitute for honest assessment.{'\n\n'}
          <Text style={styles.bold}>Pricing:</Text> Prices must reflect genuine asking prices. Artificially inflated prices intended to manipulate valuation data or market signals are prohibited.{'\n\n'}
          <Text style={styles.bold}>Availability:</Text> Only list items you actually possess and intend to sell. Phantom listings (listing items you do not have) are prohibited.{'\n\n'}
          <Text style={styles.bold}>Fulfillment:</Text> You are responsible for shipping items promptly and as described. Failure to fulfill sales may result in account restrictions.{'\n\n'}
          <Text style={styles.bold}>Multiple Platforms:</Text> When listing across multiple marketplaces, you are responsible for managing inventory to prevent overselling. Remove or update listings promptly when an item is sold.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>6. Price Manipulation</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The following price manipulation activities are prohibited:{'\n'}
          {'\u2022'} Shill bidding or creating fake sale records to inflate perceived value{'\n'}
          {'\u2022'} Coordinated buying or selling to manipulate scarcity signals{'\n'}
          {'\u2022'} Listing items at extreme prices to distort market data{'\n'}
          {'\u2022'} Using multiple accounts to create artificial demand{'\n'}
          {'\u2022'} Submitting false ground truth price data{'\n'}
          {'\u2022'} Any activity intended to manipulate the price prediction models or demand heat signals
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>7. Event Hosting Responsibilities</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Event hosts must:{'\n'}
          {'\u2022'} Provide accurate event details (date, time, location, description){'\n'}
          {'\u2022'} Manage capacity and RSVP limits responsibly{'\n'}
          {'\u2022'} Communicate changes or cancellations promptly via announcements{'\n'}
          {'\u2022'} Ensure events comply with local laws and venue policies{'\n'}
          {'\u2022'} Handle ticket refunds for cancelled events in accordance with our Terms{'\n'}
          {'\u2022'} Not use events for purposes unrelated to collecting (e.g., political campaigning, MLM recruiting){'\n'}
          {'\u2022'} Moderate event discussions and report violations{'\n'}
          {'\u2022'} Ensure sponsor involvement is transparent and clearly labeled
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>8. Messaging Etiquette</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          When using direct messaging:{'\n'}
          {'\u2022'} Respect the DM request system — if someone declines your request, do not send further requests{'\n'}
          {'\u2022'} Keep messages relevant to collecting, trading, or event coordination{'\n'}
          {'\u2022'} Do not send unsolicited links, advertisements, or promotional content{'\n'}
          {'\u2022'} Do not pressure users to complete transactions or accept offers{'\n'}
          {'\u2022'} Do not share screenshots of private conversations without consent{'\n'}
          {'\u2022'} Report suspicious messages (potential scams, phishing) rather than engaging
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>9. Reporting Violations</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          If you encounter content or behavior that violates this Policy:{'\n'}
          {'\u2022'} Use the in-app reporting feature on the relevant content, user profile, listing, or message{'\n'}
          {'\u2022'} Block users who are harassing you — blocking is immediate and mutual{'\n'}
          {'\u2022'} Contact us at support@collectai.app for issues not covered by in-app reporting{'\n'}
          {'\u2022'} Provide as much context as possible (screenshots, message history, item links) to help us investigate{'\n\n'}
          We review all reports and take appropriate action. False or malicious reports intended to harm other users are themselves a violation of this Policy.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>10. Enforcement Actions</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Violations of this Policy may result in one or more of the following actions, depending on severity:{'\n\n'}
          <Text style={styles.bold}>Warning:</Text> A notification informing you of the violation and requesting compliance. Most first-time minor violations result in a warning.{'\n\n'}
          <Text style={styles.bold}>Content Removal:</Text> Violating content (listings, messages, event details) may be removed without prior notice.{'\n\n'}
          <Text style={styles.bold}>Feature Restriction:</Text> Specific features may be restricted (e.g., messaging, listing, event creation) for a defined period.{'\n\n'}
          <Text style={styles.bold}>Temporary Suspension:</Text> Your account may be suspended for a defined period (typically 7-30 days) for serious or repeated violations.{'\n\n'}
          <Text style={styles.bold}>Permanent Ban:</Text> Your account may be permanently terminated for severe violations (e.g., fraud, counterfeit sales, harassment, illegal activity). Permanent bans also result in forfeiture of any remaining subscription time and gamification progress.{'\n\n'}
          <Text style={styles.bold}>XP & Achievement Reset:</Text> Gamification metrics may be reset for users who manipulate XP, achievements, or leaderboard rankings.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>11. Appeals Process</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          If you believe an enforcement action was applied in error, you may appeal:{'\n'}
          {'\u2022'} Send an appeal to support@collectai.app within 30 days of the action{'\n'}
          {'\u2022'} Include your username, the action taken, and your explanation of why you believe it was in error{'\n'}
          {'\u2022'} Appeals are reviewed by a different team member than the one who issued the original action{'\n'}
          {'\u2022'} You will receive a response within 14 business days{'\n'}
          {'\u2022'} The appeal decision is final{'\n\n'}
          During an appeal, the enforcement action remains in effect unless otherwise communicated.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>12. Changes to This Policy</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We may update this Policy from time to time. We will notify you of material changes through in-app notifications and by updating the "Last updated" date. Continued use of the Service after changes constitutes acceptance of the updated Policy.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>13. Contact</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          For questions about this Policy or to report violations, contact us at:{'\n'}
          support@collectai.app{'\n\n'}
          CollectAI{'\n'}
          The Netherlands
        </Text>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

export default function UserPolicyScreen() {
  return (
    <ScreenErrorBoundary screenName="Acceptable Use Policy">
      <UserPolicyScreenInner />
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
