# Event Quality Safeguards — Design Plan

Document the design behind `events.trust_tier` + `events.quality_score` + future signal-driven hiding. Kept here so the rationale survives across sessions and future contributors understand why a "1-attendee" event gets soft-flagged instead of hidden.

Written 2026-04-21 during the Ticketmaster + SeatGeek first-party API rollout.

## Problem

Events flow into `public.events` from four tiers:

1. **First-party APIs** — Ticketmaster, SeatGeek, Bandsintown. Inherently trustworthy.
2. **Publisher scrapes** — pokemon.com, magic.wizards.com, warhammer-community, lego.com, funko blog, taylorswift.com. Trustworthy.
3. **Generic scrapes** — Eventbrite, Crawl4AI over arbitrary URLs. Mixed quality.
4. **User-submitted** (not yet live) — untrusted by default.

Failure mode: a user trusts the app, taps a low-signal event, arrives to find a parking lot / joke / scam. High-cost broken promise.

## Three-dimensional gating

### Dimension 1 — Source trust tier (known at ingest)
New column `events.trust_tier text` ∈ `verified | publisher | unverified | community`.

| Source value | Tier |
|---|---|
| `ticketmaster`, `seatgeek`, `musicbrainz`, `bandsintown` | verified |
| `newsletter`, `rss`, `limitless_tcg`, `pokemon_com`, `wizards_com`, `warhammer_community`, `lego_com`, `funko_blog`, `taylorswift_com` | publisher |
| `firecrawl`, `crawl4ai`, `scraper`, `eventbrite_scrape` | unverified |
| `user_submission`, `community`, `user` (what `POST /events` writes) | community |

Set at ingest time from the `source` string already passed to `EventUpserter.upsert(..., source=...)`.

### Dimension 2 — Automated quality score (0-100, rule-based at ingest)
New column `events.quality_score int`. Computed once per event by `score_event(event, trust_tier) -> (int, reason_str)`.

| Signal | Weight | Rationale |
|---|---|---|
| Title 8-120 chars | +10 | Not empty, not a novel |
| Title caps-ratio < 0.6 and ≤3 emojis | +10 | Basic spam filter |
| Venue string has city+country (comma-separated, >10 chars) | +15 | Real location |
| Date 1-365 days in future | +15 | Not past, not time-travel |
| `source_url` starts with `http` | +10 | Accountable origin |
| `image_url` starts with `http` | +10 | Real listing effort |
| `description` ≥ 50 chars | +10 | Not a stub |
| `description` lacks spam keywords (`free iphone`, `click here`, `100% guaranteed`, `bit.ly`, `tinyurl`, `limited time offer`) | +15 | Heuristic spam |
| `trust_tier` in (`verified`, `publisher`) | +5 | Known host |
| **Maximum** | **100** | |

Thresholds (initial, tunable):
- `< 40` → hide from default feed
- `40-69` → show with "Unverified" label
- `≥ 70` → normal display

### Dimension 3 — Social + runtime signals (Phase 2+)
New table `event_signals`:
```sql
CREATE TABLE event_signals (
  event_id uuid REFERENCES events(id) ON DELETE CASCADE,
  signal_type text NOT NULL,      -- rsvp|save|report|view|report_joke|report_spam
  user_id uuid REFERENCES auth.users(id),
  count int NOT NULL DEFAULT 1,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (event_id, signal_type, user_id)
);
```

Rules:
- `save_count ≥ 3` → boost display
- `save_count < 2 AND days_to_event < 2` → show "Low interest — verify before travelling" banner
- `report_count ≥ 3` → auto-hide, queue for admin review
- User with >1 removed event can't auto-post new events

## UX treatment (three card states map to three pill colors)

| State | Card pill | Detail banner |
|---|---|---|
| Verified | green "Verified" | none |
| Unverified | none | soft: "Community-sourced. Verify venue & date with organizer before travelling." |
| Low-confidence / community | grey "Low info" | strong: "Only 1 person has saved this event. Verify with organizer before going." + "Report inaccurate" button |

The 1-attendee edge case the user called out → **low-confidence banner**. Do not hide (some niche events legitimately have small audiences), but tell the user what we know.

## Implementation phases

### Phase 1 — Ingest-time guardrails (being built 2026-04-21)
- Migration: `supabase/migrations/20260421_events_trust_score.sql` — adds `trust_tier` + `quality_score` columns + indexes.
- New module: `server/app/lib/event_quality.py` — `score_event()` + `map_source_to_trust_tier()`.
- Patch: `server/pipelines/newsletter_scraper.py:EventUpserter._upsert_batch` — compute both at insert time, pass into row dict.
- Backfill: existing 480+ rows get `trust_tier` from existing `source` column; `quality_score` computed from current fields via a one-shot SQL UPDATE that mirrors the rule set.
- Mobile: read `trust_tier` + `quality_score` from `/api/events/*`, branch UX per the three states. (Handled in separate frontend task.)

### Phase 2 — User reports + low-confidence banner (later)
- `event_signals` table.
- `POST /api/events/{id}/report` endpoint (rate-limited, 1 per user per event).
- Mobile report menu (spam / joke / wrong info / cancelled).
- Banner triggered by `quality_score < 70 OR (save_count < 2 AND days_to_event < 2)`.

### Phase 3 — Auto-hide + admin moderation queue (later)
- Cron worker (hourly): events with ≥3 reports OR `quality_score < 20` → `hidden = true`.
- Admin queue in `collectai-admin` lists hidden events; admin can delete or restore+whitelist.

### Phase 4 — User-submitted events (when the feature ships)
- ✅ **Done 2026-07-27.** New submissions default to `trust_tier='community'`, computed score.
  `POST /events` (`events_core.py::create_event`) stamps both on INSERT. Until then this route
  wrote neither, so every event a real user created landed with `trust_tier IS NULL` /
  `quality_score IS NULL` and sat outside every tier filter and both partial indexes from
  Phase 1 — `newsletter_scraper.py` was the only writer.
  The tier is stated outright rather than derived via `map_source_to_trust_tier()`: that
  function keys off the `source` string, and this route writes `source='user'`, which was
  missing from the §Dimension 1 table above. `'user' → community` has since been added to
  `_TRUST_TIER_BY_SOURCE` so the lookup no longer silently answers `unverified`, but the
  route does not depend on it — the tier is a property of the route, not of a string.
- ⬜ Creator needs 1 successful event (≥3 saves, no reports) before their 2nd auto-posts; else admin queue.

## What's intentionally NOT in scope

- No ML model for spam classification — overkill for current scale. Rule-based beats a tiny model at <1k events/day.
- No global reputation system — localized per-event reports are enough.
- No "minimum attendance" hard threshold — soft banners respect niche events.

## Open questions (for future sessions)

1. Should `trust_tier='verified'` events always bypass the score threshold? (Current design: yes — any Ticketmaster event scores ≥50 via the +5 tier bonus and +15 for trusted venue/date/etc., so this is implicit.)
2. When Phase 2 reports arrive, do we decrement `quality_score` or keep score static and use a separate `report_count` field? (Lean: separate field; easier to audit.)
3. Timezone for the "days_to_event" calculation — user local or UTC? (Lean: event local timezone, falls back to UTC.)
