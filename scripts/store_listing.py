"""Store listing — single source of truth for App Store + Google Play text (v2, 2026-10-12).
Every claim was checked against the code/prod the same day (docs/app-store-aso.md → Listing v2).
Run: python3 scripts/store_listing.py /tmp/listing.json  (exit 1 on any limit or banned claim).
Writes listing_v2.json and fails if any store limit is exceeded."""
import json, re, sys

name = "Sparrow Collect: Value Scanner"          # iOS name / Play title, 30 max
subtitle = "Card & Collectible Price Guide"     # iOS subtitle, 30 max
# iOS keywords: 100 max, comma-separated, no spaces, no word already in name/subtitle,
# no third-party trademarks (guideline 2.3.7).
keywords = "collection,tracker,worth,appraisal,tcg,trading,figure,vinyl,record,watch,comic,manga,sneaker,hobby"
promo = ("Point your camera at a card, figure, record or watch and see what it is worth — "
         "with the prices behind every value. 56 categories, one collection.")  # 170 max
play_short = "Scan trading cards, figures, vinyl & watches. See what your collection is worth."  # 80 max

description = """Snap a photo. Know what it's worth.

Sparrow Collect is a collectibles scanner, price guide and collection tracker in one app. Point your camera at a trading card, figure, vinyl record, LEGO set or watch: Sparrow identifies it and shows a low, mid and high value, with the prices that value rests on.

SCAN AND IDENTIFY
Point your camera at an item, or scan its barcode or ISBN. The AI identifies the item, its edition and variant, and suggests a condition from the photo. 56 categories, from Pokémon and Magic: The Gathering cards to Funko Pops, anime figures, retro games and watches.

A VALUE THAT SHOWS ITS WORKING
Most apps give you one confident number. Sparrow shows how many market prices a value rests on, which sources they came from and which market (US, European or both). When there is not enough data to be confident, the app says so instead of guessing.

Where the prices come from: TCGplayer and Cardmarket card prices for trading card games, Scryfall for Magic: The Gathering, Discogs for vinyl, and eBay listings across the other categories.

YOUR COLLECTION, VALUED
See the total value of your collection and your biggest movers. Record what you actually paid, including tax and shipping, and compare it with what it is worth now. Export everything as CSV for insurance documentation.

WATCHLIST AND TARGET PRICES
Hunting for a grail? Add it to your watchlist with a target price and get a notification when a listing reaches it.

CONDITION THAT FITS WHAT YOU COLLECT
A sealed LEGO set and an opened one are not the same thing. Condition options match the category: sealed or opened for boxed items, Goldmine grades for vinyl, card grades for trading cards, fill level for spirits.

56 CATEGORIES, INCLUDING
• Trading cards: Pokémon, Magic: The Gathering, Yu-Gi-Oh!, One Piece, Lorcana, Digimon, sports cards
• Figures: Funko Pop, anime figures, Hot Toys, Marvel Legends, Gunpla, designer toys
• Media: vinyl records, manga, comic books, Blu-ray steelbooks, retro games
• Luxury: watches, jewellery, fragrances, fountain pens, whisky
• Building: LEGO, Warhammer, scale models
• Lifestyle: sneakers, K-pop, Disney, Studio Ghibli, Loungefly, keycaps

SPARROW PRO
Free to download and use: scan, catalogue and value your items. Sparrow Pro (monthly or yearly subscription) adds unlimited watchlist and target-price alerts, deal discovery, set completion for trading card sets and advanced analytics. Prices are shown in the app before you subscribe.

Prices in EUR, USD, GBP, JPY, KRW, AUD or CAD. Dark mode included.

Sparrow Collect is an independent app and is not affiliated with or endorsed by The Pokémon Company, Wizards of the Coast, Konami, Funko, the LEGO Group or any other brand named here. All trademarks belong to their owners.

Built for collectors, whether you have 10 items or 10,000."""

# App Store only — guideline 3.1.2 (rejected 2026-10-13 for exactly this): the
# product page must carry a FUNCTIONAL link to the Terms of Use (EULA). We use
# Apple's standard EULA; the privacy link and renewal terms sit beside it.
ios_legal = """

Sparrow Pro is an auto-renewable subscription (monthly or yearly). Payment is charged to your Apple ID at confirmation of purchase. The subscription renews automatically unless it is cancelled at least 24 hours before the end of the current period. Manage or cancel it in your App Store account settings.

Terms of Use (EULA): https://www.apple.com/legal/internet-services/itunes/dev/stdeula/
Privacy Policy: https://sparrowcollect.com/privacy"""
ios_description = description + ios_legal

LIMITS = {"name": (name, 30), "subtitle": (subtitle, 30), "keywords": (keywords, 100),
          "promo": (promo, 170), "play_short": (play_short, 80), "description": (description, 4000),
          "ios_description": (ios_description, 4000)}
bad = [f"{k}: {len(v)} > {m}" for k, (v, m) in LIMITS.items() if len(v) > m]
if " " in keywords: bad.append("keywords contain a space")
kw = keywords.split(",")
if len(kw) != len(set(kw)): bad.append("duplicate keyword")
indexed = set(re.findall(r"[a-z]+", (name + " " + subtitle).lower()))
dup = [k for k in kw if k in indexed]
if dup: bad.append(f"keywords repeat name/subtitle words: {dup}")
for banned in ["real time", "real-time", "live listings", "psa", "cgc", "grading service", "#1", "best "]:
    if banned in description.lower() + promo.lower(): bad.append(f"banned claim: {banned}")
for tm in ["pokemon", "funko", "lego", "mtg", "magic"]:
    if tm in kw: bad.append(f"trademark in keywords: {tm}")
for k, (v, m) in LIMITS.items(): print(f"{k:12} {len(v):4}/{m}")
if "apple.com/legal/internet-services/itunes/dev/stdeula" not in ios_description:
    bad.append("ios_description lacks the EULA link (3.1.2)")
if bad: sys.exit("FAIL: " + "; ".join(bad))
json.dump({k: v for k, (v, _) in LIMITS.items()}, open(sys.argv[1] if len(sys.argv) > 1 else "listing_v2.json", "w"), ensure_ascii=False, indent=1)
print("OK")
