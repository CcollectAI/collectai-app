# App Review Notes

Notes for Apple App Store Review and Google Play Review teams.

## Demo Account

```
Email:    reviewer@sparrowcollect.com
Password: Sparrow Collect-Review-2026!
```

This account is pre-loaded with:
- 25+ collection items across 6 categories (Pokemon, LEGO, Manga, Vinyl, Anime Figures, K-pop)
- Portfolio value tracked over 30 days
- 2 active purchase mandates (deal discovery)
- 1 active build & paint project (Warhammer)
- Connection with 2 other demo users for chat testing

## Feature Walkthrough

### 1. Add an Item (2 min)

1. Tap the **+** button on the bottom tab bar
2. Choose **Scan Barcode** — point at any barcode (or tap "Enter manually")
3. Alternatively, tap **Add Manually**:
   - Select category (e.g. "Pokemon Cards")
   - Enter item name (e.g. "Charizard Base Set")
   - Add a photo (optional)
   - Save

### 2. View Portfolio (1 min)

1. Tap **Portfolio** tab (home screen)
2. See total collection value with interactive chart
3. Switch time ranges: 1D / 7D / 30D / 90D / 1Y / ALL
4. Scroll down to see category breakdown and top movers

### 3. Item Detail & Valuation (1 min)

1. Tap any item in the collection
2. See low/mid/high price estimates from marketplace data
3. Tap **"View all N results"** to see marketplace comparables
4. Use the edit (pencil) icon to update condition, notes, etc.

### 4. Deal Discovery (1 min)

1. Tap **Deals** tab (or "Deal Agent" card on portfolio home)
2. View existing purchase mandates
3. Tap **Create Mandate** to set a new deal alert
4. Set: item name, max budget, preferred condition

### 5. Events (1 min)

1. Tap **Events** tab
2. Browse upcoming collector events
3. Tap an event to see details, RSVP, announcements
4. Events with countdown timers show days remaining

### 6. Chat / Social (1 min)

1. Tap the **inbox** icon (top-right)
2. View existing conversations
3. Tap a conversation to see message history
4. Start a new chat by finding a user and tapping "Message"

### 7. Build & Paint (30 sec)

1. From any buildable category item, tap **"Start Build Project"**
2. Or navigate to Build & Paint from the category detail screen
3. Apply a step template (e.g. Warhammer 12-step workflow)

## Marketplace Affiliate Links

Sparrow Collect shows marketplace prices from multiple sources. When users tap a marketplace link, they are taken to the external marketplace via affiliate URLs. This is standard practice and is disclosed:

- **eBay**: eBay Partner Network (EPN)
- **TCGPlayer**: TCGPlayer affiliate program
- **Cardmarket**: Cardmarket affiliate program
- **Mercari**: Mercari affiliate program
- **Discogs**: Discogs affiliate program
- **StockX**: StockX affiliate program
- **BrickLink**: BrickLink affiliate program

No purchases happen within the app. All marketplace transactions occur on the respective marketplace websites/apps.

## Subscription Model

Sparrow Collect uses Apple/Google in-app subscriptions (StoreKit / Play Billing):

| Tier | Price | Features |
|------|-------|----------|
| Free | $0 | Collection tracking, valuations, 3 purchase mandates |
| Pro | $4.99/mo | 10 mandates, deal alerts, dossier PDF export |
| Premium | $9.99/mo | 50 mandates, advanced analytics, everything in Pro |

- Auto-renewal terms are clearly displayed before purchase
- Users can manage/cancel via device Settings (linked from in-app settings)
- No external payment methods for digital goods

## Data Privacy

- **Authentication**: Email/password, Apple Sign In, Google Sign In
- **Two-Factor Authentication**: Optional TOTP-based 2FA
- **Data storage**: Supabase (PostgreSQL) with row-level security
- **Encryption**: All data in transit via HTTPS/TLS
- **Crash reporting**: Sentry (anonymized crash data only)
- **Location**: Approximate location used for event discovery (coarse, not precise)
- **Camera**: Used for barcode scanning and item photos only
- **No third-party advertising or tracking SDKs**

Privacy Policy: https://sparrowcollect.com/privacy
Terms of Service: https://sparrowcollect.com/terms

## Age Verification

- Registration screen includes age confirmation checkbox: "I confirm I am at least 13 years old (16 in the EU)"
- Social login users see the same age gate during onboarding
- Registration is blocked without confirmation (COPPA/GDPR Art. 8 compliance)
- App is not marketed to children and is not in the Kids category

## Technical Notes

- Built with React Native (Expo SDK 54)
- Backend: FastAPI on AWS EC2 with Docker
- Database: Supabase (PostgreSQL)
- 3,284 backend tests, 516 frontend tests, 0 TypeScript errors
- OTA updates enabled via expo-updates for non-native patches
