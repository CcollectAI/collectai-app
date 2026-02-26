/**
 * Privacy Policy screen — displays CollectAI privacy policy.
 * Uses static text as the primary source; when a hosted URL becomes
 * available, this can be replaced with a WebView.
 */

import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';

const LAST_UPDATED = 'February 23, 2026';

function PrivacyPolicyScreenInner() {
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
        <Text style={[styles.headerTitle, { color: colors.text }]}>Privacy Policy</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={[styles.updated, { color: colors.muted }]}>Last updated: {LAST_UPDATED}</Text>

        <Text style={[styles.body, { color: colors.text }]}>
          CollectAI ("we", "our", "us") operates the CollectAI mobile application (the "Service"). This page informs you of our policies regarding the collection, use, and disclosure of personal data when you use our Service and the choices you have associated with that data.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>1. Information We Collect</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>Account Data:</Text> When you create an account, we collect your email address, display name, handle, and password (securely hashed via Supabase Auth). If you use social login (Google, Apple), we receive your name, email, and profile photo from the identity provider. We never store plain-text passwords.
          {'\n\n'}
          <Text style={styles.bold}>Profile Data:</Text> You may optionally provide a bio, avatar photo, and collecting interests. Your display name and handle are visible to other users.
          {'\n\n'}
          <Text style={styles.bold}>Collection Data:</Text> Items you add to your collection, including titles, descriptions, photos, categories, valuations, condition, and category-specific attributes. This data is stored securely in your private account.
          {'\n\n'}
          <Text style={styles.bold}>Build & Paint Projects:</Text> Project titles, steps, progress, notes, and photos you create to track builds of collectible items (model kits, miniatures, etc.).
          {'\n\n'}
          <Text style={styles.bold}>Messaging Data:</Text> Direct messages you send and receive through the in-app chat feature, including message content and timestamps. Messages are only visible to the participants of each conversation.
          {'\n\n'}
          <Text style={styles.bold}>Event Data:</Text> Events you create, RSVP to, or attend, including event details, announcements, and your attendance status (going/interested).
          {'\n\n'}
          <Text style={styles.bold}>Usage Data:</Text> We collect anonymized analytics about how you use the app (screens visited, features used) to improve the Service. We use Sentry for crash reporting.
          {'\n\n'}
          <Text style={styles.bold}>Device Information:</Text> Device type, operating system version, and push notification tokens to deliver notifications you have opted into.
          {'\n\n'}
          <Text style={styles.bold}>Location Data:</Text> We use your IP address to determine your approximate geographic region (country-level) for currency preferences and regional marketplace features. We do not collect precise GPS location. IP-based region data is cached for 24 hours.
          {'\n\n'}
          <Text style={styles.bold}>Presence Data:</Text> When you are actively using the app, we record a "last seen" timestamp to show online/offline status to other users. You can manage this in your privacy settings.
          {'\n\n'}
          <Text style={styles.bold}>Activity Data:</Text> Certain actions (adding items, completing projects, attending events) are recorded in your activity feed. You control whether activities are visible to other users.
          {'\n\n'}
          <Text style={styles.bold}>Search Data:</Text> Search queries you perform (for items, users, events, categories) are processed in real-time to return results. We do not store individual search queries. Search is subject to per-user rate limits.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>2. How We Use Your Data</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          {'\u2022'} To provide and maintain the Service{'\n'}
          {'\u2022'} To provide price estimates and market insights using machine learning models{'\n'}
          {'\u2022'} To match marketplace listings and detect deals via our Smart Deal Agent{'\n'}
          {'\u2022'} To deliver push notifications for price alerts, event updates, and messages{'\n'}
          {'\u2022'} To detect your region for currency conversion and marketplace preferences{'\n'}
          {'\u2022'} To calculate shipping estimates for cross-border transactions{'\n'}
          {'\u2022'} To facilitate direct messaging between users{'\n'}
          {'\u2022'} To display online presence indicators to connected users{'\n'}
          {'\u2022'} To provide event management features (RSVP, announcements, capacity tracking){'\n'}
          {'\u2022'} To detect and prevent technical issues and abuse{'\n'}
          {'\u2022'} To comply with legal obligations
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>3. Data Storage & Security</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Your data is stored on secure servers managed by Supabase (PostgreSQL) with row-level security (RLS) policies ensuring users can only access their own data. All data is encrypted in transit (TLS 1.2+). Passwords are hashed using industry-standard algorithms. We implement security headers (HSTS, CSP, X-Frame-Options) and JWT-based authentication with audience and issuer validation.
          {'\n\n'}
          Offline data may be cached locally on your device using SQLite for improved performance. This cache is automatically managed and cleared when you log out.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>4. Third-Party Services</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We integrate with the following third-party services:{'\n\n'}
          <Text style={styles.bold}>Infrastructure & Authentication:</Text>{'\n'}
          {'\u2022'} Supabase — authentication, database, and real-time features{'\n'}
          {'\u2022'} Amazon Web Services (AWS) — backend hosting and file storage{'\n'}
          {'\u2022'} Sentry — error and crash reporting{'\n'}
          {'\u2022'} Expo — app distribution and push notifications{'\n\n'}
          <Text style={styles.bold}>Marketplace Data (price comparisons & deal detection):</Text>{'\n'}
          {'\u2022'} eBay, TCGPlayer, Cardmarket, Discogs — market listings and sold prices{'\n'}
          {'\u2022'} PriceCharting, StockX, BrickLink — collectible valuations{'\n'}
          {'\u2022'} Mercari, Yahoo Auctions JP, AmiAmi — regional marketplace data{'\n'}
          {'\u2022'} Firecrawl, Crawl4AI — web content extraction for price data{'\n\n'}
          <Text style={styles.bold}>Payments:</Text>{'\n'}
          {'\u2022'} Stripe — subscription billing and sponsored event payments{'\n\n'}
          <Text style={styles.bold}>Geolocation:</Text>{'\n'}
          {'\u2022'} ip-api.com — IP-based region detection (country-level only){'\n\n'}
          Each service has its own privacy policy governing data they collect. Marketplace links contain affiliate tags where available (eBay, TCGPlayer, Cardmarket, Mercari, Discogs, StockX, BrickLink) which enable us to earn commissions on purchases at no additional cost to you.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>5. Social Features & User Interactions</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>Public Profile:</Text> Your display name, handle, avatar, bio, and collection count are visible to other users. Collection values are only shown if you opt in.
          {'\n\n'}
          <Text style={styles.bold}>Direct Messages:</Text> You can send and receive messages with other users. A DM request system ensures both parties consent before a conversation begins. Message content is only visible to conversation participants.
          {'\n\n'}
          <Text style={styles.bold}>Blocking:</Text> You can block other users to prevent them from messaging you or viewing your profile. Blocking automatically declines any pending DM requests.
          {'\n\n'}
          <Text style={styles.bold}>Events:</Text> When you create an event, your profile is shown as the host. When you RSVP to an event, your attendance is visible to other attendees. Event hosts can send announcements to all attendees.
          {'\n\n'}
          <Text style={styles.bold}>Online Presence:</Text> A "last seen" timestamp indicates your online status to other users. This feature helps facilitate real-time interactions.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>6. Sponsor & Business Features</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          If you register a sponsor company, we collect your company name, logo, website, contact email, and description. Sponsor data is used to facilitate event sponsorships and is visible to event attendees. Payment processing for sponsored events is handled by Stripe.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>7. Data Sharing</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We do not sell your personal data. We only share data:{'\n'}
          {'\u2022'} With your consent{'\n'}
          {'\u2022'} With other users, as described in the Social Features section{'\n'}
          {'\u2022'} With Stripe for payment processing{'\n'}
          {'\u2022'} To comply with legal obligations{'\n'}
          {'\u2022'} To protect against legal liability{'\n'}
          {'\u2022'} Aggregated and anonymized data may be used for analytics and model training
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>8. Currency & Regional Data</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We support 7 currencies (EUR, USD, GBP, JPY, KRW, AUD, CAD) and use IP-based geolocation to auto-detect your region for optimal currency and marketplace defaults. Exchange rates are refreshed every 8 hours. You can override your region and currency in settings at any time.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>9. Caching & Performance</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          To improve performance and reduce server load, we use caching at multiple levels:{'\n'}
          {'\u2022'} Server-side caching (Redis/in-memory) for frequently accessed data such as category analytics, event listings, and exchange rates{'\n'}
          {'\u2022'} Client-side caching for recently viewed items, events, and category data{'\n'}
          {'\u2022'} Offline caching via SQLite for app functionality when internet is unavailable{'\n\n'}
          Cached data is automatically refreshed at regular intervals (typically 2-5 minutes for real-time data, up to 8 hours for exchange rates). You can force a refresh by pulling down on any screen.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>10. Your Rights (GDPR & International)</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Under the GDPR and applicable privacy laws, you have the right to:{'\n'}
          {'\u2022'} Access your personal data{'\n'}
          {'\u2022'} Correct inaccurate data{'\n'}
          {'\u2022'} Request deletion of your account and all associated data{'\n'}
          {'\u2022'} Export your collection data (CSV export available in the app){'\n'}
          {'\u2022'} Restrict processing of your data{'\n'}
          {'\u2022'} Data portability{'\n'}
          {'\u2022'} Object to processing{'\n'}
          {'\u2022'} Withdraw consent at any time{'\n'}
          {'\u2022'} Lodge a complaint with a supervisory authority{'\n\n'}
          To exercise these rights, use the account settings in the app or contact us at privacy@collectai.app. We will respond within 30 days.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>11. Data Retention</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We retain your data for as long as your account is active. When you delete your account, all associated data — including items, projects, messages, events, and activity history — is permanently removed within 30 days. Anonymous aggregated data used for ML model training may be retained after account deletion.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>12. Push Notifications</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We may send push notifications for price alerts, deal discoveries, event updates, direct messages, and announcements. You can manage notification preferences in your device settings and within the app. Push notification tokens are stored securely and deleted when you log out or uninstall the app.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>13. Children's Privacy</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Our Service is not intended for children under 13 (or under 16 in the EU). We do not knowingly collect personal data from children. If you are a parent or guardian and become aware that your child has provided us with personal data, please contact us and we will delete the data promptly.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>14. Changes to This Policy</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We may update this privacy policy from time to time. We will notify you of material changes through in-app notifications and by updating the "Last updated" date. Continued use of the Service after changes constitutes acceptance of the updated policy.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>15. Contact Us</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          If you have questions about this privacy policy, please contact us at:{'\n'}
          privacy@collectai.app{'\n\n'}
          CollectAI{'\n'}
          The Netherlands
        </Text>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

export default function PrivacyPolicyScreen() {
  return (
    <ScreenErrorBoundary screenName="Privacy Policy">
      <PrivacyPolicyScreenInner />
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
