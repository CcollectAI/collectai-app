/**
 * Terms of Service screen — displays CollectAI terms.
 */

import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';

const LAST_UPDATED = 'February 18, 2026';

export default function TermsOfServiceScreen() {
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
        <Text style={[styles.headerTitle, { color: colors.text }]}>Terms of Service</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={[styles.updated, { color: colors.muted }]}>Last updated: {LAST_UPDATED}</Text>

        <Text style={[styles.body, { color: colors.text }]}>
          Please read these Terms of Service ("Terms") carefully before using the CollectAI mobile application (the "Service") operated by CollectAI ("we", "our", "us").
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>1. Acceptance of Terms</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          By creating an account or using the Service, you agree to be bound by these Terms. If you do not agree to these Terms, do not use the Service.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>2. Account Registration</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          You must provide accurate and complete information when creating an account. You are responsible for maintaining the security of your account credentials. You must be at least 13 years old to use the Service.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>3. User Content</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          You retain ownership of all content you upload to the Service (photos, descriptions, collection data). By using the Service, you grant us a limited license to store, display, and process your content solely to provide the Service to you.{'\n\n'}
          You agree not to upload content that is illegal, offensive, or infringes on third-party rights.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>4. Price Estimates & Valuations</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Price estimates provided by CollectAI are for informational purposes only. They are generated using machine learning models and marketplace data, and should not be relied upon as financial advice. Actual market prices may differ significantly. We make no guarantees about the accuracy of any valuation.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>5. Marketplace Integration</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          CollectAI provides links to third-party marketplaces (eBay, TCGPlayer, Cardmarket) for reference. We are not responsible for transactions conducted on these platforms. Some marketplace links may contain affiliate tags.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>6. Prohibited Uses</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          You agree not to:{'\n'}
          {'\u2022'} Use the Service for any unlawful purpose{'\n'}
          {'\u2022'} Attempt to reverse-engineer or exploit the Service{'\n'}
          {'\u2022'} Scrape or harvest data from the Service{'\n'}
          {'\u2022'} Impersonate other users{'\n'}
          {'\u2022'} Upload malicious content or malware{'\n'}
          {'\u2022'} Use automated systems to access the Service without permission
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>7. Account Termination</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          You may delete your account at any time through the app settings. We reserve the right to suspend or terminate accounts that violate these Terms. Upon termination, your data will be deleted in accordance with our Privacy Policy.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>8. Intellectual Property</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The Service, including its design, features, and underlying technology, is owned by CollectAI. You may not copy, modify, or distribute any part of the Service without our written consent.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>9. Limitation of Liability</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The Service is provided "as is" without warranties of any kind. To the maximum extent permitted by law, we shall not be liable for any indirect, incidental, special, or consequential damages arising from your use of the Service.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>10. Changes to Terms</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We reserve the right to modify these Terms at any time. We will notify you of material changes through the app. Continued use of the Service after changes constitutes acceptance of the new Terms.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>11. Governing Law</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          These Terms shall be governed by the laws of the Netherlands. Any disputes arising from these Terms shall be resolved in the courts of the Netherlands.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>12. Contact</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          For questions about these Terms, contact us at:{'\n'}
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
});
