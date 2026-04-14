# Event API Setup — User Actions Required

Last updated: 2026-04-14

## What's already wired (no action needed)

| Source | Status | Events |
|---|---|---|
| 17 RSS feeds (Sideshow, SneakerNews, Brickset, ANN, Dengeki, etc.) | ✅ Live | ~200 |
| MusicBrainz (vinyl releases, free/no-key) | ✅ Live | ~55 |
| Firecrawl event pages (40+ brand sites) | ⚠️ Rate-limited (402) | 0 |
| Crawl4AI event pages | ⚠️ Eventbrite blocks | 0 |

**Current total**: 330 events across 11 categories.

---

## APIs requiring user action to activate

To unlock these, sign up at the URLs below and paste credentials into `/opt/collectors/.env` on EC2 (or share them with Claude to do it).

### 1. Meetup.com GraphQL — HIGHEST priority

**Why**: Covers US/UK/EU hobby meetups for Pokemon TCG, MTG, LEGO, anime figures, sneakers. Biggest source for actual collector meetups.

**Cost**: Free for read access.

**Signup**:
1. Go to https://secure.meetup.com/meetup_api/oauth_consumers/
2. Create a new OAuth consumer (name it "CollectAI")
3. Choose "Client credentials" flow
4. Copy the Client ID and Client Secret

**Env vars to set**:
```
MEETUP_CLIENT_ID=<your_client_id>
MEETUP_CLIENT_SECRET=<your_client_secret>
```

Docs: https://www.meetup.com/graphql/authentication/

---

### 2. Eventbrite Platform API — HIGH priority

**Why**: Convention tickets (SDCC, NYCC, MCM Comic Con, Japan Expo Paris, etc.). Supports venue-based search even after the 2020 location-search removal.

**Cost**: Free tier = 500 requests/day. Enough for 4-hourly cycles.

**Signup**:
1. Go to https://www.eventbrite.com/platform/api
2. Sign in with your Eventbrite account (create one if needed)
3. Go to "Account Settings" → "Developer Links" → "API Keys"
4. Copy the Private Token

**Env var to set**:
```
EVENTBRITE_PRIVATE_TOKEN=<your_token>
```

Docs: https://www.eventbrite.com/platform/docs/

---

### 3. Brickset API — MEDIUM priority

**Why**: Official LEGO release calendar with precise set release dates (Brickset feed has this too but API has structured data).

**Cost**: Free.

**Signup**:
1. Go to https://brickset.com/tools/webservices/requestkey
2. Fill out the form (project = "CollectAI — collectibles tracking app")
3. You get an API key by email

**Env var to set**:
```
BRICKSET_API_KEY=<your_api_key>
```

Docs: https://brickset.com/article/52664/api-version-3-documentation

---

### 4. IGDB / Twitch API — MEDIUM priority

**Why**: Retro games release calendar (supplements Kotaku RSS).

**Cost**: Free with Twitch account.

**Signup**:
1. Go to https://dev.twitch.tv/console/apps
2. Log in with your Twitch account
3. "Register Your Application" → name "CollectAI" → redirect URL `http://localhost` → category "Application Integration"
4. Copy Client ID + generate Client Secret

**Env vars to set**:
```
TWITCH_CLIENT_ID=<your_client_id>
TWITCH_CLIENT_SECRET=<your_client_secret>
```

Docs: https://api-docs.igdb.com/#getting-started

---

### 5. BoardGameGeek API (recently closed)

**Status**: BGG XML API started requiring auth tokens in Feb 2025. Free registration still possible.

**Signup**:
1. Create a BGG account at https://boardgamegeek.com/
2. Go to https://boardgamegeek.com/collection-developer (API registration)
3. Register your app

**Env var**:
```
BGG_AUTH_TOKEN=<your_token>
```

---

### 6. Luma (lu.ma) — LOW priority

**Why**: Drops/launches trending (used by NBA, Stripe, hobby communities).

**Cost**: Free.

**Signup**:
1. Go to https://lu.ma/api
2. Request developer access
3. Generate API key

**Env var**:
```
LUMA_API_KEY=<your_key>
```

Rate limit: 200-500 requests/minute.

---

## Quick-add via EC2

Once you have the keys, either:

**Option A — manually edit EC2 .env**:
```bash
ssh collectai
nano /opt/collectors/.env
# paste the keys, save
bash /tmp/restart_bake.sh
```

**Option B — give Claude the keys** in the next chat and I'll add them via:
```bash
ssh collectai "echo 'MEETUP_CLIENT_ID=xxx' >> /opt/collectors/.env"
ssh collectai "bash /tmp/restart_bake.sh"
```

---

## What I'll build autonomously once you add each key

For each API, I've pre-planned the adapter. When you add the key, I can wire it end-to-end (adapter → scheduler → DB → category mapping → test run) in ~30 minutes per source.

**Priority order** if you want to add them one at a time:
1. Meetup.com → unlocks local meetups across US/UK/EU for all TCG categories
2. Eventbrite → unlocks convention tickets worldwide
3. Brickset → precise LEGO release dates
4. IGDB → retro game releases
5. BGG → board game conventions
6. Luma → drops/launches
