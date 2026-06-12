# Category API Coverage Matrix

Last updated: 2026-04-14

Legend: ⚡ wired | ✅ Free/public | 💰 Paid | 🔑 Key required | 🕸 Scrape only | ❌ No API

## By category

| Category | Primary API | Secondary | Status |
|---|---|---|---|
| **Pokemon** | pokemontcg.io ✅ | PokéBeach RSS ✅, Scrydex 💰 | ⚡ wired |
| **MTG** | Scryfall ✅ | JustTCG ✅, Cardmarket 🔑 | ⚡ wired |
| **Yu-Gi-Oh** | YGOPRODeck ✅ free, v7 | Scrydex 💰 | ⚡ wired |
| **Lorcana** | lorcana-api.com ✅ free, open source | Lorcast ✅, Scrydex 💰 | ⚡ wired |
| **LEGO** | Rebrickable ✅ 🔑 + Brickset ✅ 🔑 + BrickLink 🔑 | BrickEconomy ✅ 🔑 pricing | ⚡ Rebrickable wired |
| **Funko** | [funko-pop-data GitHub](https://github.com/kennymkchan/funko-pop-data) ✅ 23K+ JSON | PPG scrape 🕸 | ❌ Not wired |
| **Sneakers** | Sneaks-API ✅ (StockX/Goat/FlightClub) | The Sneaker Database RapidAPI ✅/💰 | ❌ Not wired |
| **Vinyl records** | Discogs ✅ 🔑 | MusicBrainz ✅ | ⚡ Discogs wired |
| **Sportscards** | PSA Public API ✅ 🔑 | GemRate 🔑 (multi-grader), 130point 🕸 | ❌ Not wired |
| **Watches** | Chrono24 Python wrapper ✅ | aBlogtoWatch RSS | ⚡ RSS only |
| **Comic books** | Comic Vine ✅ 🔑 | Metron ✅ free, GCD (comics.org) 🕸 | ❌ Not wired |
| **Retro games** | IGDB ✅ free (Twitch auth) | MobyGames 💰 (720/hr free tier) | ❌ Not wired |
| **Manga** | MyAnimeList + Jikan | Kitsu ✅, AniList ✅ | ⚡ RSS wired |
| **Anime figures** | Dengeki Hobby RSS | MyFigureCollection 🕸, AmiAmi 🕸 | ⚡ RSS wired |
| **Warhammer** | Wahapedia/Depot ✅ | Bell of Lost Souls RSS, Lexicanum MediaWiki ✅ | ⚡ partial |
| **Board games** | BoardGameGeek XML API ✅ free | bgg-api Python wrapper | ❌ Not wired |
| **Fragrances** | Fragella ✅ 💰 (74K) | FragDB (127K+) 🔑, Fragrantica scrape 💰 | ❌ Not wired |
| **Whiskey** | Whiskybase ✅ (new releases) | WhiskyHunter ✅ free auction data | ❌ Not wired |
| **Scale models** | Scalemates ✅ 666K kits 🕸 | Hyperscale news 🕸 | ❌ Scrape only |
| **Keycaps** | KeycapLendar ✅ (IC/GB tracker) | KeebFinder 🕸, Matrix docs | ❌ Not wired |
| **Diecast** | DiecastDB ✅, HotGrid ✅ | Hot Wheels Wiki 🕸 | ❌ Not wired |
| **K-pop** | ❌ no official API | Weverse scrape 🕸, Kprofiles scrape 🕸 | ❌ Scrape only |
| **Hot Toys** | ❌ no API | Legends Verse database 🕸, Sideshow RSS | ⚡ RSS only |
| **Gunpla** | ❌ no official | Bandai Hobby scrape 🕸 | ❌ Scrape only |

## Immediate wins (free, easy to wire)

1. **Funko** — Clone [kennymkchan/funko-pop-data](https://github.com/kennymkchan/funko-pop-data). 23K+ entries, 0 cost.
2. **Board games** (oop_board_games) — BGG XML API, free, unlimited.
3. **Comics** — Metron API, free, modern Comic Vine alternative.
4. **Retro games** — IGDB, free w/ Twitch auth.
5. **Warhammer** — Wahapedia/Depot JSON, free, already powers apps.
6. **Watches** — Chrono24 Python wrapper, live marketplace data.
7. **Sneakers** — Sneaks-API, StockX/GOAT/FlightClub aggregator.
8. **Keycaps** — KeycapLendar JSON export.
9. **Yu-Gi-Oh** — YGOPRODeck v7 (free, 1 API key).

## Paid but worth it

- **Sportscards** — PSA Public API. Authoritative population data.
- **Fragrances** — FragDB (127K perfumes) or Fragella ($74K JSON).
- **MobyGames** — for retro gaming edge cases.

## Dead ends (scrape only)

- **K-pop** — Weverse discontinued as separate shop; no public API.
- **Hot Toys / Prime 1 / Sideshow** — no official API, only Legends Verse scrape.
- **Scale models** — Scalemates has the data but no public API.
- **Gunpla** — Bandai doesn't expose anything.

## Top 5 to wire first

1. Funko (JSON dataset exists, 23K items free)
2. IGDB (retro_games)
3. BoardGameGeek (oop_board_games)
4. Sneaks-API (sneakers)
5. Chrono24 wrapper (watches)

Each is free and can be wired in a day.

## Sources

- [Scrydex TCG API](https://scrydex.com/)
- [YGOPRODeck API](https://ygoprodeck.com/api-guide/)
- [Lorcana API](https://lorcana-api.com/)
- [Funko Pop Data GitHub](https://github.com/kennymkchan/funko-pop-data)
- [Sneaks API GitHub](https://github.com/druv5319/Sneaks-API)
- [PSA Public API](https://www.psacard.com/publicapi)
- [IGDB API](https://www.igdb.com/api)
- [BoardGameGeek XML API](https://boardgamegeek.com/xmlapi2/)
- [Comic Vine API](https://comicvine.gamespot.com/api/)
- [Metron Project](https://metron-project.github.io/)
- [Chrono24 Python wrapper](https://github.com/irahorecka/chrono24)
- [Fragella API](https://api.fragella.com/)
- [WhiskyHunter API](https://whiskyhunter.net/api/)
- [Whiskybase new releases](https://www.whiskybase.com/whiskies/new-releases)
- [Wahapedia Depot](https://github.com/fjlaubscher/depot)
- [BrickEconomy API](https://www.brickeconomy.com/api-reference)
- [KeycapLendar](https://keycaplendar.firebaseapp.com/)
- [Scalemates kits database](https://www.scalemates.com/kits/)
