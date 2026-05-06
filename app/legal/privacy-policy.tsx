/**
 * Privacy Policy screen — displays Sparrow Collect privacy policy.
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

const LAST_UPDATED = 'April 11, 2026';

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
          Sparrow Collect ("we", "our", "us") operates the Sparrow Collect mobile application (the "Service"). This page informs you of our policies regarding the collection, use, and disclosure of personal data when you use our Service and the choices you have associated with that data.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>1. Information We Collect</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>Account Data:</Text> When you create an account, we collect your email address, display name, handle, and password (securely hashed via Supabase Auth). If you use social login (Google, Apple), we receive your name, email, and profile photo from the identity provider. We never store plain-text passwords.
          {'\n\n'}
          <Text style={styles.bold}>Profile Data:</Text> You may optionally provide a bio, avatar photo, and collecting interests. Your display name and handle are visible to other users.
          {'\n\n'}
          <Text style={styles.bold}>Collection Data:</Text> Items you add to your collection, including titles, descriptions, photos, categories (across 54 collectible categories), valuations, condition, and category-specific structured attributes. Structured attributes include fields extracted from AI scans (e.g., set name, card number, reference number, year, brand, material, edition) and are stored in a JSON attributes field alongside each item to enable features such as set completion tracking, smarter catalog matching, and more accurate price predictions. This data is stored securely in your private account.
          {'\n\n'}
          <Text style={styles.bold}>Build & Paint Projects:</Text> Project titles, steps, progress, notes, and photos you create to track builds of collectible items (model kits, miniatures, etc.).
          {'\n\n'}
          <Text style={styles.bold}>Messaging Data:</Text> Direct messages you send and receive through the in-app chat feature, including message content and timestamps. Messages are only visible to the participants of each conversation.
          {'\n\n'}
          <Text style={styles.bold}>Event Data:</Text> Events you create, RSVP to, or attend, including event details, announcements, your attendance status (going/interested), and ticket purchases for paid events.
          {'\n\n'}
          <Text style={styles.bold}>Usage Data:</Text> We collect anonymized analytics about how you use the app (screens visited, features used, sponsor interactions) via PostHog to improve the Service. We use Sentry for crash reporting. Analytics events are typed and do not contain personally identifiable information.
          {'\n\n'}
          <Text style={styles.bold}>Device Information:</Text> Device type, operating system version, and push notification tokens to deliver notifications you have opted into.
          {'\n\n'}
          <Text style={styles.bold}>Presence Data:</Text> When you are actively using the app, we record a "last seen" timestamp to show online/offline status to other users. You can manage this in your privacy settings.
          {'\n\n'}
          <Text style={styles.bold}>Activity Data:</Text> Certain actions (adding items, completing projects, attending events) are recorded in your activity feed. You control whether activities are visible to other users.
          {'\n\n'}
          <Text style={styles.bold}>Search Data:</Text> Search queries you perform (for items, users, events, categories) are processed in real-time to return results. We do not store individual search queries. Search is subject to per-user rate limits.
          {'\n\n'}
          <Text style={styles.bold}>Watchlist Data:</Text> Items and categories you add to your watchlist are monitored for price changes. Watchlist preferences, alert thresholds, and notification settings are stored in your account.
          {'\n\n'}
          <Text style={styles.bold}>Export Data:</Text> When you use the CSV export feature, your collection data is compiled on-device. Exported files are not stored on our servers.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>2. Camera & Image Data</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>QuickScan (AI Camera Scanning):</Text> When you use the QuickScan feature, your device camera captures photos of collectible items. These images are processed using OpenAI Vision API for item identification and CLIP (Contrastive Language-Image Pre-Training) embeddings for catalog matching. Images are transmitted securely to our servers and to OpenAI for analysis. Image data is not retained after processing unless you explicitly save the identified item to your collection.
          {'\n\n'}
          <Text style={styles.bold}>Multi-Item Detection:</Text> When scanning a group of items, our system uses bounding box detection to identify individual items within a single photo. The same image processing and retention policies apply as for single-item QuickScan.
          {'\n\n'}
          <Text style={styles.bold}>Screenshot Intelligence:</Text> You may choose photos from your device gallery (including screenshots) for analysis. These images are processed identically to camera captures and are not retained after processing unless you save the item.
          {'\n\n'}
          <Text style={styles.bold}>Comparison Scan:</Text> The side-by-side comparison feature processes two photos to compare items. Both images follow the same processing and retention policies.
          {'\n\n'}
          <Text style={styles.bold}>Condition Grading:</Text> When you use the AI condition grading feature, your item photos are analyzed for wear, defects, and overall condition. The AI generates a condition assessment with PSA/CGC grade mapping where applicable. Defect annotations are generated during processing and stored only if you save the grading result to your item.
          {'\n\n'}
          <Text style={styles.bold}>Camera Permission:</Text> Camera access requires your explicit device permission. You can revoke camera access at any time through your device settings without affecting other app functionality.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>3. AI & Machine Learning</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>Vision Classification:</Text> We use OpenAI Vision API and on-device classifiers to identify collectible items from photos. Classification results include item name, category, and confidence scores. Per-field confidence levels are provided so you can assess accuracy.
          {'\n\n'}
          <Text style={styles.bold}>CLIP Embeddings:</Text> We generate CLIP embeddings from your item images to match against our catalog of 46,500+ curated items across 54 categories. Embeddings are numerical representations of visual features and cannot be used to reconstruct the original image. Cached embeddings may be retained to improve matching speed.
          {'\n\n'}
          <Text style={styles.bold}>Price Prediction Models:</Text> We use Ridge regression machine learning models to predict item values with q10/q50/q90 quantile estimates (low/median/high). Models are trained on aggregated, anonymized marketplace data and are periodically retrained to reflect current market conditions.
          {'\n\n'}
          <Text style={styles.bold}>Condition Grading AI:</Text> Our condition assessment AI analyzes item photos to detect defects and estimate grades on standard scales (PSA 1-10, CGC 0.5-10.0, generic condition tiers). AI grades are estimates and should not substitute for professional grading services.
          {'\n\n'}
          <Text style={styles.bold}>Feedback & Corrections:</Text> When you correct an AI identification or condition grade, your correction is used to improve the AI for all users. Corrections are anonymized before being used for model improvement — they are not linked to your account or personal information. You may submit corrections at any time through the inline editing interface on scan results.
          {'\n\n'}
          <Text style={styles.bold}>Scarcity & Demand Analysis:</Text> We analyze aggregated marketplace data to generate scarcity scores and demand heat signals for collectible items. These signals are derived from anonymized supply and demand metrics and do not contain personal user data.
          {'\n\n'}
          <Text style={styles.bold}>Structured Attribute Extraction:</Text> When QuickScan identifies an item, our vision pipeline extracts category-specific structured attributes (e.g. for a watch: brand, model name, reference number, movement, case material; for a Pokemon card: set name, card number, rarity, holo status). These structured attributes are saved to your item record so the app can automatically compute set completion, match duplicates, and surface category-specific filters. Attribute extraction runs on the same image data processed by the QuickScan vision pipeline and follows the same retention policy (images not retained after processing unless you save the item).
          {'\n\n'}
          <Text style={styles.bold}>Catalog Vocabulary & Canonicalization:</Text> We maintain a per-category vocabulary of canonical brand names, set names, and other attribute values derived from our curated catalog. When AI extracts an attribute, it is "snapped" to the canonical form if a close match exists (e.g. "rolex" → "Rolex") to keep your collection data clean and consistent. The vocabulary is built from public catalog data — it does not contain any user-specific information.
          {'\n\n'}
          <Text style={styles.bold}>Attribute-Based Catalog Matching:</Text> In addition to visual matching via CLIP embeddings, we also match scanned items to catalog entries by exact-match on structured identifiers (card number, reference number, SKU, barcode). This improves identification accuracy, especially for items with weak visual signals, without transmitting any additional data beyond what QuickScan already processes.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>4. Geolocation</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>IP-Based Region Detection:</Text> We use your IP address to determine your approximate geographic region (country-level) for currency preferences and regional marketplace features via ip-api.com. IP-based region data is cached for 24 hours.
          {'\n\n'}
          <Text style={styles.bold}>Precise GPS Location (Nearby Events):</Text> The "Nearby Events" feature uses precise GPS location via expo-location to find collector events near you. This requires a separate, explicit location permission on your device. Precise location data is used only to calculate distances to events and is not stored on our servers or shared with other users. You can use the app fully without granting location permission — the Nearby Events feature will simply be unavailable. You can revoke location permission at any time through your device settings.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>5. How We Use Your Data</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          {'\u2022'} To provide and maintain the Service{'\n'}
          {'\u2022'} To identify collectible items via AI-powered camera scanning (QuickScan){'\n'}
          {'\u2022'} To provide AI condition grading and defect detection{'\n'}
          {'\u2022'} To provide price estimates and market insights using machine learning models{'\n'}
          {'\u2022'} To match items against our catalog using CLIP embeddings{'\n'}
          {'\u2022'} To generate scarcity scores and demand signals for collectibles{'\n'}
          {'\u2022'} To match marketplace listings and detect deals via our Smart Deal Agent{'\n'}
          {'\u2022'} To monitor watchlist items and send automated price alerts{'\n'}
          {'\u2022'} To deliver push notifications for price alerts, event updates, and messages{'\n'}
          {'\u2022'} To detect your region for currency conversion and marketplace preferences{'\n'}
          {'\u2022'} To find nearby events using precise GPS location (with your permission){'\n'}
          {'\u2022'} To calculate shipping estimates for cross-border transactions{'\n'}
          {'\u2022'} To facilitate direct messaging between users{'\n'}
          {'\u2022'} To facilitate multi-marketplace selling and listing management{'\n'}
          {'\u2022'} To display online presence indicators to connected users{'\n'}
          {'\u2022'} To provide event management features (RSVP, announcements, capacity tracking, ticket sales){'\n'}
          {'\u2022'} To track gamification progress (XP, levels, streaks, achievements, leaderboard){'\n'}
          {'\u2022'} To display social proof indicators (collector counts, trending items){'\n'}
          {'\u2022'} To improve AI accuracy using anonymized user corrections{'\n'}
          {'\u2022'} To detect and prevent technical issues and abuse{'\n'}
          {'\u2022'} To comply with legal obligations
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>6. Gamification</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>XP, Levels & Streaks:</Text> Certain actions within the app (adding items, scanning, completing trades, attending events) earn experience points (XP). Your XP total, level, and activity streaks are tracked in your account.
          {'\n\n'}
          <Text style={styles.bold}>Achievements:</Text> You may earn achievements for reaching milestones (e.g., adding a certain number of items, completing trades). Achievement badges are displayed on your profile and are visible to other users.
          {'\n\n'}
          <Text style={styles.bold}>Leaderboard:</Text> Your display name, level, XP total, and achievement count may appear on the public leaderboard, which is visible to all users. If you prefer not to appear on the leaderboard, you can adjust this in your privacy settings.
          {'\n\n'}
          <Text style={styles.bold}>Social Proof:</Text> Aggregated data such as how many collectors own a particular item, trending items, and recent sold prices are displayed to provide market context. This data is derived from anonymized, aggregated usage and does not identify individual users.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>7. Data Storage & Security</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Your data is stored on secure servers managed by Supabase (PostgreSQL) with row-level security (RLS) policies ensuring users can only access their own data. All data is encrypted in transit (TLS 1.2+). Passwords are hashed using industry-standard algorithms. We implement security headers (HSTS, CSP, X-Frame-Options) and JWT-based authentication with audience and issuer validation. Authentication tokens are stored securely on-device using platform-native secure storage (SecureStore).
          {'\n\n'}
          Offline data may be cached locally on your device using SQLite for improved performance. This cache is automatically managed and cleared when you log out. Offline caching enables core app functionality (viewing your collection, queued edits) when internet is unavailable. Queued mutations are automatically replayed when connectivity is restored.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>8. Third-Party Services</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We integrate with the following third-party services:{'\n\n'}
          <Text style={styles.bold}>Infrastructure & Authentication:</Text>{'\n'}
          {'\u2022'} Supabase — authentication, database, and real-time features{'\n'}
          {'\u2022'} Amazon Web Services (AWS) — backend hosting and file storage{'\n'}
          {'\u2022'} Sentry — error and crash reporting{'\n'}
          {'\u2022'} Expo — app distribution and push notifications{'\n\n'}
          <Text style={styles.bold}>AI & Image Processing:</Text>{'\n'}
          {'\u2022'} OpenAI — Vision API for item identification and condition grading{'\n'}
          {'\u2022'} fal.ai — CLIP text embedding generation for catalog matching{'\n\n'}
          <Text style={styles.bold}>Marketplace Data (37 sources across 54 categories):</Text>{'\n'}
          <Text style={styles.bold}>General (all categories):</Text>{'\n'}
          {'\u2022'} eBay, Firecrawl, Crawl4AI, Mercari US, Vinted, Mavin.io, Scrape.do, Google Shopping, Etsy{'\n\n'}
          <Text style={styles.bold}>Trading cards & TCGs:</Text>{'\n'}
          {'\u2022'} TCGPlayer, Cardmarket{'\n\n'}
          <Text style={styles.bold}>Music & media:</Text>{'\n'}
          {'\u2022'} Discogs{'\n\n'}
          <Text style={styles.bold}>Sneakers, streetwear & fashion:</Text>{'\n'}
          {'\u2022'} StockX{'\n\n'}
          <Text style={styles.bold}>LEGO & bricks:</Text>{'\n'}
          {'\u2022'} BrickLink, BrickEconomy{'\n\n'}
          <Text style={styles.bold}>Video games & retro:</Text>{'\n'}
          {'\u2022'} PriceCharting{'\n\n'}
          <Text style={styles.bold}>Live auctions & multi-category:</Text>{'\n'}
          {'\u2022'} WhatNot, Catawiki, Yahoo Auctions JP{'\n\n'}
          <Text style={styles.bold}>Japanese collectibles:</Text>{'\n'}
          {'\u2022'} AmiAmi, Mandarake{'\n\n'}
          <Text style={styles.bold}>Watches & luxury:</Text>{'\n'}
          {'\u2022'} Bezel, Chrono24{'\n\n'}
          <Text style={styles.bold}>Spirits:</Text>{'\n'}
          {'\u2022'} WhiskyAuctioneer, MasterOfMalt{'\n\n'}
          <Text style={styles.bold}>Cameras & photography:</Text>{'\n'}
          {'\u2022'} KEH, MPB{'\n\n'}
          <Text style={styles.bold}>Specialty:</Text>{'\n'}
          {'\u2022'} PopMart (blind boxes), Booth.pm (VTuber/doujin), ScaleMates (scale models), Drop (keycaps), GouletPens (pens), KTown4U (K-pop), ComicBookRealm (comics){'\n\n'}
          <Text style={styles.bold}>Payments:</Text>{'\n'}
          {'\u2022'} Stripe — subscription billing, sponsored event payments, and event ticket purchases{'\n\n'}
          <Text style={styles.bold}>Geolocation:</Text>{'\n'}
          {'\u2022'} ip-api.com — IP-based region detection (country-level only){'\n\n'}
          <Text style={styles.bold}>Analytics:</Text>{'\n'}
          {'\u2022'} PostHog — product analytics and feature usage tracking (no PII collected){'\n\n'}
          Each service has its own privacy policy governing data they collect. Marketplace links contain affiliate tags where available (eBay, TCGPlayer, Cardmarket, Mercari, Discogs, StockX, BrickLink) which enable us to earn commissions on purchases at no additional cost to you.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>9. Social Features & User Interactions</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          <Text style={styles.bold}>Public Profile:</Text> Your display name, handle, avatar, bio, collection count, level, and achievements are visible to other users. Collection values are only shown if you opt in.
          {'\n\n'}
          <Text style={styles.bold}>Direct Messages:</Text> You can send and receive messages with other users. A DM request system ensures both parties consent before a conversation begins. Message content is only visible to conversation participants.
          {'\n\n'}
          <Text style={styles.bold}>Blocking:</Text> You can block other users to prevent them from messaging you or viewing your profile. Blocking automatically declines any pending DM requests.
          {'\n\n'}
          <Text style={styles.bold}>Events:</Text> When you create an event, your profile is shown as the host. When you RSVP to an event, your attendance is visible to other attendees. Event hosts can send announcements to all attendees.
          {'\n\n'}
          <Text style={styles.bold}>Online Presence:</Text> A "last seen" timestamp indicates your online status to other users. This feature helps facilitate real-time interactions.
          {'\n\n'}
          <Text style={styles.bold}>Franchise Browsing:</Text> Browsing franchise collections (e.g., Star Wars, Marvel) is a read-only feature that does not collect additional personal data beyond standard usage analytics.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>10. Sponsor & Business Features</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          If you register a sponsor company, we collect your company name, logo, website, contact email, and description. Sponsor data is used to facilitate event sponsorships and is visible to event attendees. Payment processing for sponsored events and sponsor subscriptions is handled by Stripe.
          {'\n\n'}
          <Text style={styles.bold}>Payment Data:</Text> When you purchase event tickets or sponsor subscriptions, we collect payment information through Stripe. We do not store credit card numbers — all payment processing is handled securely by Stripe. We retain transaction records (amount, date, event/tier) for billing and support purposes.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>11. Data Sharing</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We do not sell your personal data. We only share data:{'\n'}
          {'\u2022'} With your consent{'\n'}
          {'\u2022'} With other users, as described in the Social Features section{'\n'}
          {'\u2022'} With OpenAI for image processing (QuickScan, condition grading){'\n'}
          {'\u2022'} With Stripe for payment processing{'\n'}
          {'\u2022'} With ad-mediation networks (only when ads are activated — see Section 20 for details and conditions){'\n'}
          {'\u2022'} To comply with legal obligations{'\n'}
          {'\u2022'} To protect against legal liability{'\n'}
          {'\u2022'} Aggregated and anonymized data may be used for analytics and model training{'\n'}
          {'\u2022'} Anonymized user corrections are used to improve AI models for all users
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>12. Webhook Notifications</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We use webhooks to deliver real-time notifications for events such as price alerts, deal discoveries, watchlist updates, and payment confirmations. Webhook payloads contain only the minimum data necessary (e.g., item ID, alert type) and do not include sensitive personal information. Webhook endpoints are secured with signature verification.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>13. Currency & Regional Data</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We support 7 currencies (EUR, USD, GBP, JPY, KRW, AUD, CAD) and use IP-based geolocation to auto-detect your region for optimal currency and marketplace defaults. Exchange rates are refreshed every 8 hours. You can override your region and currency in settings at any time.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>14. Caching & Performance</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          To improve performance and reduce server load, we use caching at multiple levels:{'\n'}
          {'\u2022'} Server-side caching (Redis/in-memory) for frequently accessed data such as category analytics, event listings, and exchange rates{'\n'}
          {'\u2022'} Client-side caching for recently viewed items, events, and category data{'\n'}
          {'\u2022'} Offline caching via SQLite for app functionality when internet is unavailable{'\n'}
          {'\u2022'} CLIP embedding cache to reduce redundant image processing calls{'\n'}
          {'\u2022'} Marketplace search cache (6-12 hour TTL) to reduce API calls{'\n\n'}
          Cached data is automatically refreshed at regular intervals (typically 2-5 minutes for real-time data, up to 8 hours for exchange rates). You can force a refresh by pulling down on any screen.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>15. Your Rights (GDPR & International)</Text>
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
          To exercise these rights, use the account settings in the app or contact us at privacy@sparrowcollect.com. We will respond within 30 days.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>16. Data Retention</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We retain your data for as long as your account is active. When you delete your account, all associated data — including items, projects, messages, events, gamification progress, and activity history — is permanently removed within 30 days. Anonymous aggregated data used for ML model training (including anonymized corrections) may be retained after account deletion.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>17. Push Notifications</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We may send push notifications for price alerts, deal discoveries, watchlist updates, event updates, direct messages, and announcements. Notification frequency is subject to tier-based caps: free accounts receive up to 5 notifications per 24-hour period, Pro accounts up to 15 per 24-hour period, and Premium accounts up to 30 per 24-hour period. You can manage notification preferences in your device settings and within the app. Push notification tokens are stored securely and deleted when you log out or uninstall the app.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>18. Children's Privacy</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Our Service is not intended for children under 13 (or under 16 in the EU). We do not knowingly collect personal data from children. If you are a parent or guardian and become aware that your child has provided us with personal data, please contact us and we will delete the data promptly.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>19. Automatic Set Completion Tracking</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          When you save items with structured attributes (see Section 3), the app automatically computes set completion progress by joining your collection against our catalog on fields such as <Text style={styles.bold}>set_name</Text> and <Text style={styles.bold}>card_number</Text>. For example, if you own 47 items tagged as "Pokemon Base Set" and our catalog has 102 items in that set, the app will show "Base Set: 47/102 (46%)". This feature is computed server-side on demand and requires no additional data collection — it works entirely from data you have already saved to your collection. Set progress is visible only to you unless you explicitly share your collection publicly. You can prevent auto-detection for a specific item by clearing its structured attributes in the item detail screen.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>20. Advertising (Future Activation)</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Sparrow Collect is a freemium product. The free tier may, in the future, include non-intrusive advertising in certain placements (e.g., banner ads at the bottom of catalog browse screens, occasional interstitial ads after significant actions). Ad infrastructure is currently installed in the app but <Text style={styles.bold}>dark</Text> — no ads are shown to any user as of this policy's "Last updated" date.
          {'\n\n'}
          <Text style={styles.bold}>When ads are enabled, the following applies:</Text>{'\n'}
          {'\u2022'} Ads will be served via a third-party mediation network (planned: AppLovin MAX). The exact provider will be disclosed here prior to activation.{'\n'}
          {'\u2022'} Paid subscribers (Pro, Premium) will not see ads — ad-free is a benefit of the paid tiers.{'\n'}
          {'\u2022'} Free users will see ads throttled to prevent overwhelming the experience (maximum 5 interstitials per session, 3-minute cooldown between interstitials, one banner per screen).{'\n'}
          {'\u2022'} Ad networks may use device identifiers (IDFA on iOS, AAID on Android) subject to your device-level tracking permission. On iOS 14.5+, you will be asked via the App Tracking Transparency prompt before any tracking occurs.{'\n'}
          {'\u2022'} We do not share your collection data, search queries, or any other account information with ad networks. Ads are served based only on generic, non-PII signals from the ad network itself.{'\n'}
          {'\u2022'} You can upgrade to a paid tier at any time to remove ads.{'\n\n'}
          When ads are activated, we will update this policy and notify users in-app.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>21. Changes to This Policy</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          We may update this privacy policy from time to time. We will notify you of material changes through in-app notifications and by updating the "Last updated" date. Continued use of the Service after changes constitutes acceptance of the updated policy.
        </Text>

        <Text style={[styles.heading, { color: colors.text }]}>22. Contact Us</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          If you have questions about this privacy policy, please contact us at:{'\n'}
          privacy@sparrowcollect.com{'\n\n'}
          Sparrow Collect{'\n'}
          Ertskade 74, 1019 BB Amsterdam{'\n'}The Netherlands{'\n'}KvK: 99596326
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
