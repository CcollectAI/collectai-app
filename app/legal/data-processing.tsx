/**
 * Data Processing Agreement screen — displays Sparrow Collect data processing terms.
 */

import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';

const LAST_UPDATED = 'April 11, 2026';

function DataProcessingScreenInner() {
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
        <Text style={[styles.headerTitle, { color: colors.text }]}>Data Processing Agreement</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={[styles.updated, { color: colors.muted }]}>Last updated: {LAST_UPDATED}</Text>

        <Text style={[styles.body, { color: colors.text }]}>
          This Data Processing Agreement ("DPA") describes how Sparrow Collect ("we", "our", "us") processes personal data in connection with the Sparrow Collect mobile application (the "Service"). This DPA supplements our Privacy Policy and Terms of Service.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>1. Data Controller</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>Controller:</Text> Sparrow Collect{'\n'}
          <Text style={styles.bold}>Location:</Text> Amsterdam, The Netherlands{'\n'}
          <Text style={styles.bold}>Contact:</Text> dpo@sparrowcollect.com{'\n\n'}
          Sparrow Collect acts as the data controller for all personal data processed through the Service. We determine the purposes and means of processing personal data as described in this DPA.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>2. Types of Data Processed</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>Collection Data:</Text> Item titles, descriptions, categories (across 54 collectible categories), valuations, condition grades, category-specific attributes, and 46,500+ curated catalog items used for matching and identification.{'\n\n'}
          <Text style={styles.bold}>Image Data:</Text> Photos captured via QuickScan or uploaded from your device gallery for AI identification, condition grading, and catalog matching. Images are processed using OpenAI Vision API and CLIP embeddings.{'\n\n'}
          <Text style={styles.bold}>Structured Attribute Data:</Text> Category-specific attributes (e.g., brand, reference number, set name, card number, year, material) extracted from scanned items by the AI vision pipeline. These attributes are stored alongside each item to enable features like set completion tracking, duplicate detection, and improved price prediction. Structured attributes are normalized against a catalog vocabulary for consistency.{'\n\n'}
          <Text style={styles.bold}>Marketplace Data:</Text> Aggregated pricing, availability, and listing data from 37 third-party marketplace sources used for price estimates, deal detection, and market analysis.{'\n\n'}
          <Text style={styles.bold}>Chat & Messaging Data:</Text> Direct messages, DM requests, and conversation metadata between users via Supabase Realtime.{'\n\n'}
          <Text style={styles.bold}>Event Data:</Text> Event details, RSVP records, attendance data, announcements, ticket purchases, and sponsor information for collector events.{'\n\n'}
          <Text style={styles.bold}>Account & Profile Data:</Text> Email address, display name, handle, avatar, bio, collecting interests, authentication credentials (hashed), and subscription tier.{'\n\n'}
          <Text style={styles.bold}>Usage & Analytics Data:</Text> Anonymized analytics events (screens visited, features used), crash reports, and device information.{'\n\n'}
          <Text style={styles.bold}>Gamification Data:</Text> XP totals, levels, streaks, achievements, and leaderboard rankings.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>3. Processing Purposes</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>Service Delivery:</Text> Providing core app functionality including collection management, item tracking, search, social features, events, and multi-marketplace selling.{'\n\n'}
          <Text style={styles.bold}>AI & Machine Learning:</Text> Item identification via OpenAI Vision API, catalog matching via CLIP embeddings and exact-match on structured attributes (reference number, card number, SKU, barcode), price prediction using Ridge regression models (q10/q50/q90 quantiles) with brand-tier and attribute-derived features, AI condition grading, scarcity scoring, demand analysis, and automatic set completion computation. Anonymized user corrections are used to improve model accuracy.{'\n\n'}
          <Text style={styles.bold}>Catalog Aggregation:</Text> Our catalog currently contains 123,872 curated items across 54 categories with approximately 166,000 market hits observed from 37+ public marketplace sources. Catalog data is public reference information and does not contain personal data.{'\n\n'}
          <Text style={styles.bold}>Marketplace Aggregation:</Text> Collecting and normalizing pricing data from 37 sources across 54 categories to provide price estimates, deal detection, watchlist monitoring, and market insights.{'\n\n'}
          <Text style={styles.bold}>Notifications:</Text> Delivering push notifications for price alerts, deal discoveries, watchlist updates, event updates, direct messages, and announcements. Notifications are subject to tier-based frequency caps (free: 5/day, Pro: 15/day, Premium: 30/day) and user preference settings.{'\n\n'}
          <Text style={styles.bold}>Analytics & Improvement:</Text> Anonymized usage analytics via PostHog and crash reporting via Sentry to improve service quality and reliability.{'\n\n'}
          <Text style={styles.bold}>Payment Processing:</Text> Subscription billing, event ticket purchases, and sponsor payments via Stripe.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>4. Sub-Processors</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We engage the following sub-processors to deliver the Service:{'\n\n'}
          {'\u2022'} <Text style={styles.bold}>Supabase</Text> — Authentication, PostgreSQL database, row-level security, real-time messaging{'\n'}
          {'\u2022'} <Text style={styles.bold}>Amazon Web Services (AWS)</Text> — Backend hosting (EC2), file storage (S3), infrastructure{'\n'}
          {'\u2022'} <Text style={styles.bold}>OpenAI</Text> — Vision API for item identification and condition grading{'\n'}
          {'\u2022'} <Text style={styles.bold}>fal.ai</Text> — CLIP text embedding generation for catalog matching{'\n'}
          {'\u2022'} <Text style={styles.bold}>Stripe</Text> — Payment processing for subscriptions, event tickets, and sponsor billing{'\n'}
          {'\u2022'} <Text style={styles.bold}>PostHog</Text> — Product analytics and feature usage tracking (anonymized){'\n'}
          {'\u2022'} <Text style={styles.bold}>Sentry</Text> — Error monitoring and crash reporting{'\n'}
          {'\u2022'} <Text style={styles.bold}>Expo</Text> — App distribution, OTA updates, and push notification delivery{'\n\n'}
          <Text style={styles.bold}>Potential future sub-processors (not yet active):</Text>{'\n'}
          {'\u2022'} <Text style={styles.bold}>AppLovin MAX</Text> (ad mediation) — will be engaged if and when we activate advertising for free-tier users. Currently installed in the app but dark (no data shared). We will update this DPA and notify users in-app before any activation.{'\n\n'}
          Each sub-processor is contractually bound to process data only for the purposes specified and in accordance with applicable data protection laws. We maintain an up-to-date list of sub-processors and will notify users of material changes.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>5. Data Transfer Safeguards</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Where personal data is transferred outside the European Economic Area (EEA), we ensure appropriate safeguards are in place:{'\n\n'}
          {'\u2022'} EU Standard Contractual Clauses (SCCs) are incorporated into agreements with sub-processors located outside the EEA where applicable{'\n'}
          {'\u2022'} We assess the data protection laws of recipient countries and implement supplementary measures where necessary{'\n'}
          {'\u2022'} Sub-processors in the United States operate under data processing agreements that include SCCs{'\n'}
          {'\u2022'} Data transfers are limited to what is strictly necessary for the processing purpose{'\n\n'}
          You may request a copy of the applicable transfer safeguards by contacting dpo@sparrowcollect.com.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>6. Security Measures</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We implement the following technical and organizational security measures:{'\n\n'}
          <Text style={styles.bold}>Encryption:</Text>{'\n'}
          {'\u2022'} Data encrypted in transit via TLS 1.2+{'\n'}
          {'\u2022'} Data encrypted at rest in Supabase (PostgreSQL) and AWS S3{'\n'}
          {'\u2022'} Authentication tokens stored in platform-native secure storage (SecureStore){'\n\n'}
          <Text style={styles.bold}>Access Control:</Text>{'\n'}
          {'\u2022'} Row-Level Security (RLS) policies ensuring users can only access their own data{'\n'}
          {'\u2022'} JWT-based authentication with audience and issuer validation{'\n'}
          {'\u2022'} IDOR (Insecure Direct Object Reference) pre-flight ownership checks on all mutation operations{'\n'}
          {'\u2022'} Multi-factor authentication (MFA) available for user accounts{'\n\n'}
          <Text style={styles.bold}>Infrastructure Security:</Text>{'\n'}
          {'\u2022'} Security headers: HSTS, CSP, X-Frame-Options, CORS{'\n'}
          {'\u2022'} Per-user and per-endpoint rate limiting to prevent abuse{'\n'}
          {'\u2022'} Circuit breakers on all external marketplace API integrations{'\n'}
          {'\u2022'} GZip compression for API responses{'\n'}
          {'\u2022'} Non-root Docker containers with resource limits and health checks{'\n'}
          {'\u2022'} SQL injection prevention via parameterized queries
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>7. Data Breach Notification</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          In the event of a personal data breach:{'\n\n'}
          <Text style={styles.bold}>To Supervisory Authority:</Text> We will notify the relevant data protection authority within 72 hours of becoming aware of a breach that is likely to result in a risk to the rights and freedoms of individuals, as required by GDPR Article 33.{'\n\n'}
          <Text style={styles.bold}>To Affected Users:</Text> We will notify affected users without undue delay when a breach is likely to result in a high risk to their rights and freedoms, as required by GDPR Article 34. Notifications will be sent via email and in-app notification.{'\n\n'}
          <Text style={styles.bold}>Breach Response:</Text> Our breach response procedures include identifying and containing the breach, assessing the scope and impact, implementing remediation measures, documenting the incident, and cooperating with supervisory authorities.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>8. Data Subject Rights</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Under the GDPR and applicable data protection laws, you have the following rights:{'\n\n'}
          {'\u2022'} <Text style={styles.bold}>Right of Access</Text> — Request a copy of the personal data we hold about you{'\n'}
          {'\u2022'} <Text style={styles.bold}>Right to Rectification</Text> — Request correction of inaccurate or incomplete personal data{'\n'}
          {'\u2022'} <Text style={styles.bold}>Right to Erasure</Text> — Request deletion of your personal data (account deletion available in app settings){'\n'}
          {'\u2022'} <Text style={styles.bold}>Right to Data Portability</Text> — Receive your data in a structured, machine-readable format (CSV export available in the app){'\n'}
          {'\u2022'} <Text style={styles.bold}>Right to Restriction</Text> — Request that we restrict the processing of your personal data in certain circumstances{'\n'}
          {'\u2022'} <Text style={styles.bold}>Right to Object</Text> — Object to processing of your personal data for specific purposes, including direct marketing{'\n\n'}
          To exercise any of these rights, use the account settings in the app or contact our Data Protection Officer at dpo@sparrowcollect.com. We will respond to your request within 30 days.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>9. Retention Periods</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>Active Account:</Text> Personal data is retained for as long as your account remains active and is necessary to provide the Service.{'\n\n'}
          <Text style={styles.bold}>Post-Deletion:</Text> When you delete your account, all associated personal data — including collection items, projects, messages, events, gamification progress, marketplace listings, and activity history — is permanently removed within 30 days.{'\n\n'}
          <Text style={styles.bold}>Anonymized ML Data:</Text> Anonymized and aggregated data used for machine learning model training (including anonymized user corrections, aggregated price data, and model training datasets) may be retained indefinitely after account deletion, as this data cannot be linked back to individual users.{'\n\n'}
          <Text style={styles.bold}>Legal Obligations:</Text> Certain data may be retained beyond the standard retention period where required by applicable law (e.g., financial transaction records for tax compliance).
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>10. Contact</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          For questions about this Data Processing Agreement or to exercise your data subject rights, contact our Data Protection Officer:{'\n\n'}
          dpo@sparrowcollect.com{'\n\n'}
          Sparrow Collect{'\n'}          Ertskade 74, 1019 BB Amsterdam{'\n'}          The Netherlands{'\n'}          KvK: 99596326
        </Text>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

export default function DataProcessingScreen() {
  return (
    <ScreenErrorBoundary screenName="Data Processing Agreement">
      <DataProcessingScreenInner />
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
