# Events API Coverage by Region & Category

Last updated: 2026-04-14

Goal: aggregate real events (conventions, drops, meetups, tournaments, product releases) across 🇺🇸 US, 🇬🇧 UK, 🇪🇺 EU, 🇯🇵 Japan for all 54 collectible categories.

Legend: ⚡ wired | ✅ Free/public | 💰 Paid | 🔑 Key required | 🕸 Scrape only | ❌ No API

## 1. Social meetup platforms

| Platform | Regions | API | Cost | Relevance | Status |
|---|---|---|---|---|---|
| **Meetup.com** | 🇺🇸🇬🇧🇪🇺 Global | GraphQL (new Feb 2025) | Free basic, $30/mo Pro | ⭐⭐⭐⭐⭐ TCG, collector meetups | ❌ Not wired |
| **Eventbrite** | 🇺🇸🇬🇧🇪🇺🇯🇵 Global | REST 500 req/day | Free tier | ⭐⭐⭐⭐ Convention tickets | ❌ Not wired (search-by-location removed 2020) |
| **Luma (lu.ma)** | 🇺🇸🇬🇧🇪🇺 Global | REST, 200-500 req/min | Free | ⭐⭐⭐ Drops/launches trending | ❌ Not wired |
| **Facebook Events** | Global | Deprecated | N/A | ❌ | ❌ Unusable |
| **Discord** | Global | Per-server API | Free | ⭐⭐ Hobby communities | ❌ Needs per-server bot |
| **Peatix** | 🇯🇵 JP + 27 countries | Unclear, no public docs | Unknown | ⭐⭐⭐⭐ 850K events, JP anime/hobby | ❌ Not wired |
| **Connpass** | 🇯🇵 JP only | Has API | Free | ⭐⭐⭐ Mostly tech but some crossover | ❌ Not wired |
| **Doorkeeper** | 🇯🇵 JP only | Limited API | Free | ⭐⭐ Tech-focused | ❌ Not wired |

## 2. Convention / exhibition schedules

| Event | Region | Data source | Status |
|---|---|---|---|
| **SDCC (San Diego Comic-Con)** | 🇺🇸 | comic-con.org RSS ✅ | ⚡ wired |
| **Anime Expo** | 🇺🇸 LA | anime-expo.org RSS ✅ | ⚡ wired |
| **Gen Con** | 🇺🇸 | gencon.com 🕸 (no RSS) | ❌ Scrape |
| **New York Comic Con** | 🇺🇸 | newyorkcomiccon.com 🕸 | ❌ Scrape |
| **MCM Comic Con** | 🇬🇧 London/Birmingham | mcmcomiccon.com 🕸 | ❌ Scrape |
| **Japan Expo Paris** | 🇪🇺 | japan-expo-paris.com 🕸 | ❌ Scrape |
| **Spielwarenmesse (Nuremberg Toy Fair)** | 🇪🇺 DE, Feb 2-6 2027 | spielwarenmesse.de 🕸 (no API) | ❌ Scrape — 2,800 exhibitors, 60 countries |
| **Toy Fair New York** | 🇺🇸 | toyassociation.org 🕸 | ❌ Scrape |
| **Toy Fair London** | 🇬🇧 | toyfair.co.uk 🕸 | ❌ Scrape |
| **Wonder Festival (Makuhari)** | 🇯🇵 Jul 26 + Feb 8, 2026 | mipon.org/wonder-festival 🕸 | ❌ Scrape — biggest figure expo |
| **Comiket (Summer/Winter)** | 🇯🇵 Tokyo Big Sight | comiket.co.jp 🕸 | ❌ Scrape — doujinshi, free |
| **AnimeJapan** | 🇯🇵 March | anime-japan.jp 🕸 | ❌ Scrape |
| **Jump Festa** | 🇯🇵 December | jumpfesta.com 🕸 | ❌ Scrape |
| **Tokyo Game Show** | 🇯🇵 September | expo.nikkeibp.co.jp/tgs 🕸 | ❌ Scrape |
| **AnimeCons.com** | 🌍 Worldwide anime con list | animecons.com 🕸 | ❌ Scrape — aggregator |

## 3. TCG tournaments

| Source | Games | Regions | Status |
|---|---|---|---|
| **Limitless TCG** | Pokemon (all major tournaments) | 🌍 Global | ❌ Not wired — limitlesstcg.com |
| **YGOPRODeck Tournaments** | Yu-Gi-Oh | 🌍 Global | ❌ Not wired — ygoprodeck.com/tournaments |
| **TopDeck.gg** | MTG/Pokemon | 🌍 Global | ❌ Not wired — advanced registration |
| **WPN (Wizards Play Network)** | MTG Regional Championships | 🌍 Global, official | 🔑 Requires store affiliation |
| **YCS (Yu-Gi-Oh Championship Series)** | Yu-Gi-Oh official | 🇺🇸🇪🇺 NA/Central/SA/EU/Oceania | yugioh-card.com 🕸 |
| **Pokedata.ovh** | Pokemon local events | 🇪🇺 | ❌ Not wired |
| **TCGplayer Events** | Pokemon/MTG/Yu-Gi-Oh/Lorcana | 🇺🇸 | ❌ Not wired |

## 4. Product drops & release calendars

### Sneakers
| Source | API | Cost | Status |
|---|---|---|---|
| **SNKRS (Nike)** | ❌ no public API | N/A | Reverse-engineered risky |
| **StockX Upcoming** | ❌ no public API | N/A | 🕸 scrape only |
| **The Drop Date** | 🕸 scrape | Free | ❌ Not wired |
| **Sneaker Crush app** | ❌ mobile only | N/A | ❌ |
| **Sneaks-API** (GitHub) | Aggregates StockX/GOAT/FlightClub | Free OSS | ❌ Not wired |
| **SneakerNews.com** | 🕸 scrape | Free | ❌ Not wired |

### TCG releases
| Source | API | Status |
|---|---|---|
| **Pokémon TCG API** (docs.pokemontcg.io) | ✅ JSON, release dates | ⚡ wired |
| **Scryfall** | ✅ MTG release dates | ⚡ wired |
| **PokéBeach** | ✅ RSS upcoming sets | ⚡ wired (RSS) |
| **JustTCG** | ✅ Pokemon/MTG/Yu-Gi-Oh/Lorcana | ❌ Not wired |

### LEGO releases
| Source | API | Status |
|---|---|---|
| **Brickset** | ✅ 🔑 set release dates | ❌ Not wired |
| **Rebrickable** | ✅ 🔑 catalog | ⚡ wired |
| **LEGO.com Newsroom** | 🕸 scrape | ❌ Not wired |

### Vinyl / Music
| Source | API | Status |
|---|---|---|
| **Record Store Day** | ❌ no API, PDF list only | 🕸 recordstoreday.com |
| **Discogs new releases** | ✅ sortable by date_added | ⚡ wired |
| **MusicBrainz** | ✅ free | ❌ Not wired — better release dates |
| **Vinyl Me Please** | ❌ member-only | N/A |

### Watches
| Source | Data | Status |
|---|---|---|
| **Watches & Wonders Geneva** | Apr 14-20, 2026, 65 brands | 🕸 watchesandwonders.com |
| **Chrono24 Python wrapper** | ✅ marketplace listings | ❌ Not wired |
| **aBlogtoWatch RSS** | ✅ release news | ⚡ wired |
| **Fratello Watches RSS** | ✅ release news | ⚡ wired |
| **Hodinkee** | 🕸 scrape | ❌ feed broken |

### Anime figures
| Source | Data | Status |
|---|---|---|
| **Wonder Festival (Makuhari)** | Biggest figure expo, 2x/year | 🕸 mipon.org |
| **AmiAmi** | 🕸 preorder calendar | ❌ Not wired |
| **Good Smile Company** | 🕸 drop calendar | ❌ Not wired |
| **MyFigureCollection** | 🕸 community DB | ❌ Not wired |
| **Dengeki Hobby RSS** | ✅ JP release news | ⚡ wired |

## 5. Current wired RSS feeds (verified 2026-04-14)

| # | Feed | Region | Categories |
|---|---|---|---|
| 1 | Sideshow Collectibles | 🇺🇸 | hot_toys |
| 2 | Sneaker News | 🇺🇸 | sneakers |
| 3 | Disney Parks Blog | 🇺🇸 | disney |
| 4 | SDCC | 🇺🇸 | conventions |
| 5 | Anime Expo | 🇺🇸 | anime_figures |
| 6 | Kotaku | 🇺🇸 | retro_games |
| 7 | Bell of Lost Souls | 🇺🇸 | warhammer |
| 8 | Brickset | 🇬🇧 | lego |
| 9 | BricksFanz | 🇬🇧 | lego |
| 10 | Fratello Watches | 🇪🇺 NL | watches |
| 11 | aBlogtoWatch | 🇺🇸 | watches |
| 12 | Anime News Network | 🇺🇸 | anime_figures |
| 13 | MyAnimeList | 🇺🇸 | anime/manga |
| 14 | Dengeki Hobby | 🇯🇵 | anime_figures |
| 15 | SoraNews24 | 🇯🇵 | pop culture |
| 16 | Japan Times | 🇯🇵 | culture |
| 17 | Geek Native | 🇬🇧 | tabletop |

**Gap analysis**: We have RSS coverage for ~15 of 54 categories. ~39 categories have zero event data sources wired.

## 6. Regional coverage gaps

| Region | Coverage | Gap |
|---|---|---|
| 🇺🇸 US | ⭐⭐⭐⭐ | Need: Meetup API for local meetups, WPN for MTG tournaments |
| 🇬🇧 UK | ⭐⭐ | Need: Forbidden Planet, MCM Comic Con, London Toy Fair |
| 🇪🇺 EU | ⭐⭐ | Need: Spielwarenmesse, Japan Expo Paris, Catawiki events |
| 🇯🇵 JP | ⭐⭐⭐ | Need: Wonder Festival, Comiket, Peatix, Connpass, AmiAmi |

## 7. Top 10 additions to wire

1. **Meetup.com GraphQL** — covers US/UK/EU hobby meetups for all TCG + LEGO + anime figures
2. **Eventbrite venue API** — convention tickets (SDCC, NYCC, MCM, etc.)
3. **Wahapedia/Depot** — Warhammer events + data
4. **Brickset release calendar** — LEGO drops with dates
5. **Pokémon TCG official event locator** — tournament schedule
6. **Limitless TCG scrape** — Pokemon tournament results
7. **Wonder Festival scrape** — JP figure reveals twice/year
8. **AmiAmi scrape** — JP figure preorders
9. **Sneaks-API** — sneaker drops
10. **MusicBrainz** — vinyl release dates (Discogs lacks real release dates)

## 8. Ecosystem gaps (no API exists)

- **K-pop releases**: Weverse shop discontinued, no official API. Only scraping option.
- **SNKRS drops**: Nike blocks API access. Reverse engineering risky (ToS).
- **Gunpla drops**: Bandai Hobby Site — no API, scrape only.
- **Hot Toys release calendar**: No API, Legends Verse scrape.

## Sources

- [Meetup GraphQL API](https://www.meetup.com/graphql/)
- [Eventbrite Platform](https://www.eventbrite.com/platform/api)
- [Luma API](https://docs.luma.com/reference/getting-started-with-your-api)
- [Connpass](https://connpass.com/)
- [Peatix](https://peatix.com/us/)
- [AnimeCons.com](https://animecons.com/events/)
- [Magical Trip Tokyo events 2026](https://www.magical-trip.com/media/ultimate-guide-to-tokyos-2025-anime-and-manga-events-dates-highlights-and-must-attend-conventions/)
- [Wonder Festival 2026](https://mipon.org/wonder-festival-this-year/)
- [Spielwarenmesse](https://www.spielwarenmesse.de/en/)
- [Limitless TCG](https://limitlesstcg.com/)
- [YGOPRODeck Tournaments](https://ygoprodeck.com/tournaments/)
- [TopDeck.gg](https://topdeck.gg/)
- [The Drop Date](https://thedropdate.com)
- [StockX Upcoming](https://stockx.com/releases/upcoming?category=sneakers)
- [Sneaks API](https://github.com/druv5319/Sneaks-API)
- [Record Store Day](https://recordstoreday.com/)
- [Watches and Wonders 2026](https://www.watchesandwonders.com/en/geneva-2026/event)
- [Chrono24 Python wrapper](https://github.com/irahorecka/chrono24)
- [Brickset](https://brickset.com/)
- [Depot (Warhammer)](https://github.com/fjlaubscher/depot)
