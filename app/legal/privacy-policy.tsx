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

const NAVY = '#0F172A';
const MUTED = '#64748B';
const TIFFANY = '#81D8D0';

const LAST_UPDATED = 'February 18, 2026';

export default function PrivacyPolicyScreen() {
  const router = useRouter();

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <AnimatedPressable
          onPress={() => router.back()}
          accessibilityRole="button"
          accessibilityLabel="Go back"
          style={styles.backBtn}
        >
          <Ionicons name="arrow-back" size={24} color={NAVY} />
        </AnimatedPressable>
        <Text style={styles.headerTitle}>Privacy Policy</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.updated}>Last updated: {LAST_UPDATED}</Text>

        <Text style={styles.body}>
          CollectAI ("we", "our", "us") operates the CollectAI mobile application (the "Service"). This page informs you of our policies regarding the collection, use, and disclosure of personal data when you use our Service and the choices you have associated with that data.
        </Text>

        <Text style={styles.heading}>Information We Collect</Text>
        <Text style={styles.body}>
          <Text style={styles.bold}>Account Data:</Text> When you create an account, we collect your email address, username, and password (securely hashed). We never store plain-text passwords.
          {'\n\n'}
          <Text style={styles.bold}>Collection Data:</Text> Items you add to your collection, including titles, descriptions, photos, categories, and valuations. This data is stored securely in your private account.
          {'\n\n'}
          <Text style={styles.bold}>Usage Data:</Text> We collect anonymized analytics about how you use the app (screens visited, features used) to improve the Service. We use Sentry for crash reporting.
          {'\n\n'}
          <Text style={styles.bold}>Device Information:</Text> We may collect device type, operating system version, and push notification tokens to deliver notifications you have opted into.
        </Text>

        <Text style={styles.heading}>How We Use Your Data</Text>
        <Text style={styles.body}>
          {'\u2022'} To provide and maintain the Service{'\n'}
          {'\u2022'} To notify you about changes to the Service{'\n'}
          {'\u2022'} To provide price estimates and market insights for your collection{'\n'}
          {'\u2022'} To detect and prevent technical issues{'\n'}
          {'\u2022'} To comply with legal obligations
        </Text>

        <Text style={styles.heading}>Data Storage & Security</Text>
        <Text style={styles.body}>
          Your data is stored on secure servers managed by Supabase (PostgreSQL) with row-level security policies. All data is encrypted in transit (TLS 1.2+). We implement industry-standard security measures to protect your personal information.
        </Text>

        <Text style={styles.heading}>Third-Party Services</Text>
        <Text style={styles.body}>
          We use the following third-party services:{'\n'}
          {'\u2022'} Supabase — authentication and database{'\n'}
          {'\u2022'} Sentry — error and crash reporting{'\n'}
          {'\u2022'} eBay, TCGPlayer, Cardmarket — marketplace data for price comparisons{'\n'}
          {'\u2022'} Expo — app distribution and push notifications{'\n\n'}
          These services have their own privacy policies governing data they collect.
        </Text>

        <Text style={styles.heading}>Data Sharing</Text>
        <Text style={styles.body}>
          We do not sell your personal data. We only share data:{'\n'}
          {'\u2022'} With your consent{'\n'}
          {'\u2022'} To comply with legal obligations{'\n'}
          {'\u2022'} To protect against legal liability{'\n'}
          {'\u2022'} Aggregated and anonymized data may be used for analytics
        </Text>

        <Text style={styles.heading}>Your Rights</Text>
        <Text style={styles.body}>
          You have the right to:{'\n'}
          {'\u2022'} Access your personal data{'\n'}
          {'\u2022'} Correct inaccurate data{'\n'}
          {'\u2022'} Request deletion of your account and data{'\n'}
          {'\u2022'} Export your collection data{'\n'}
          {'\u2022'} Withdraw consent at any time{'\n\n'}
          To exercise these rights, use the account settings in the app or contact us at support@collectai.app.
        </Text>

        <Text style={styles.heading}>Data Retention</Text>
        <Text style={styles.body}>
          We retain your data for as long as your account is active. When you delete your account, all associated data is permanently removed within 30 days.
        </Text>

        <Text style={styles.heading}>Children's Privacy</Text>
        <Text style={styles.body}>
          Our Service is not intended for children under 13. We do not knowingly collect personal data from children under 13. If you are a parent or guardian and become aware that your child has provided us with personal data, please contact us.
        </Text>

        <Text style={styles.heading}>Changes to This Policy</Text>
        <Text style={styles.body}>
          We may update this privacy policy from time to time. We will notify you of changes by posting the new policy in the app and updating the "Last updated" date.
        </Text>

        <Text style={styles.heading}>Contact Us</Text>
        <Text style={styles.body}>
          If you have questions about this privacy policy, please contact us at:{'\n'}
          support@collectai.app
        </Text>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  backBtn: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: NAVY,
  },
  content: {
    paddingHorizontal: 20,
    paddingVertical: 24,
  },
  updated: {
    fontSize: 13,
    color: MUTED,
    marginBottom: 20,
  },
  heading: {
    fontSize: 17,
    fontWeight: '700',
    color: NAVY,
    marginTop: 24,
    marginBottom: 8,
  },
  body: {
    fontSize: 15,
    color: NAVY,
    lineHeight: 24,
  },
  bold: {
    fontWeight: '700',
  },
});
