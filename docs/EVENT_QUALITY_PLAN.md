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

## The events feed is ~95 upcoming rows, and one source explains why (2026-08-22)

Measured before deciding what to fix:

| source | total | **upcoming** | avg lead time at ingest |
|---|---|---|---|
| limitless_tcg | 1,986 | **0** | **-12.3 hours** |
| ticketmaster | 555 | 14 | +62 days |
| seatgeek | 176 | 81 | +56 days |
| musicbrainz | 120 | 5 | — |
| newsletter | 17 | 8 | +45 days |

**2,859 events; 108 upcoming.** The feature is effectively SeatGeek plus a bit
of Ticketmaster.

### limitless_tcg: the docstring and the code disagreed

`limitless_tcg_events.py` has always said *"Only upcoming tournaments (date >=
now)"*. The code said:

```python
if (now - dt).total_seconds() > 3 * 86400: return None   # "not too stale"
```

That admits anything that happened in the last three days and **never requires
the future**. Every one of the 1,986 rows it has written was already past at
insert time — average −12.3 hours, zero even a day ahead.

**Fixing the filter admits nothing, and that is the honest result.** Limitless
is a RESULTS feed, not a schedule: `/api/tournaments` returned 60 rows with 0
future, and `?upcoming=true`, `?status=upcoming` and `?type=upcoming` each
returned 20 rows with 0 future. There is no upcoming endpoint. The pipeline is
left wired with a note to DELETE it if it is still writing zero rows in a month,
rather than carry a source that cannot serve the feature.

The rows are untouched — all past, so already invisible to the feed, and
deleting prod data is a separate decision.

### The newsletter source had no newsletters

The 17 `source='newsletter'` rows were never a parser problem in the way the
2026-07-27 note assumed. The configured inbox (`ccollect.ai@gmail.com`) holds
**949 messages since April and not one collectibles newsletter** — the recent
ones are entirely GitHub CI failure notifications plus Google and Vercel service
mail. "Site Navigation", "Performance Cookies" and "Stay Connected" are what you
get when a newsletter parser is pointed at service email.

So the extractor was being blamed for output it could not have produced well.
Both are true: the extractor is weak AND it was fed nothing to extract.

⚠️ That mailbox also reports **"Your Gmail storage is full"**, so it can no
longer receive mail at all. Subscribing publishers to it will silently do
nothing until that is cleared.

### The replacement extractor, and why the GATE is the deliverable

`pipelines/newsletter_llm_extract.py` — LLM extraction with a deterministic
gate in front of it. §"NOT in scope" below still says no ML model for spam
CLASSIFICATION, and that stands. This is a different job: turning prose into
fields at all, which rules have now failed at twice.

**An LLM's failure mode is the inverse of the regex's.** The regex emitted
obvious garbage — `ic/media/pcenLogo` as a venue — which is exactly what
`event_quality.score_event`'s penalties catch (`markup_in_title`,
`location_not_place_shaped`). A model emits CLEAN, PLAUSIBLE fields, so every
one of those penalties scores a hallucinated event as fine. Swapping the
extractor without a new gate trades visible junk for invisible junk.

So the model is never trusted for content; it is asked to POINT AT text:

| gate | rejects |
|---|---|
| grounding | `evidence` not present verbatim in the email |
| title-in-source | a summarised headline nobody sent |
| **date grounding** | the YEAR of `starts_at` absent from the evidence span |
| chrome | a denylist built only from rows that actually shipped |
| date sanity | unparseable, past, or >800 days out |
| confidence | last and lowest-weight — it may reject, never rescue |

Date grounding was added by auditing the gate against itself: steps 1–2 ground
the PROSE and say nothing about `starts_at`, which the model composes rather
than copies. Demonstrated before fixing — real title, verbatim evidence,
invented date — **accepted, zero reasons**. It is the field with the highest
cost of being wrong, because it is the one that makes somebody travel.

`extract()` returns **None for could-not-ask** and a list for asked; collapsing
both to `[]` would score a dead API as a perfect precision run.

**Nothing is wired in and the source-level quarantine stays ON** until a dry run
over a real inbox is measured. The 2026-07-27 version shipped 9 junk rows into
the live feed; the number comes before the wiring this time.

## What's intentionally NOT in scope

- No ML model for spam classification — overkill for current scale. Rule-based beats a tiny model at <1k events/day.
- No global reputation system — localized per-event reports are enough.
- No "minimum attendance" hard threshold — soft banners respect niche events.

## Open questions (for future sessions)

1. Should `trust_tier='verified'` events always bypass the score threshold? (Current design: yes — any Ticketmaster event scores ≥50 via the +5 tier bonus and +15 for trusted venue/date/etc., so this is implicit.)
2. When Phase 2 reports arrive, do we decrement `quality_score` or keep score static and use a separate `report_count` field? (Lean: separate field; easier to audit.)
3. Timezone for the "days_to_event" calculation — user local or UTC? (Lean: event local timezone, falls back to UTC.)
