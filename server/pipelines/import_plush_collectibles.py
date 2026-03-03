"""
Import Plush Collectibles catalog (500+ items).

Layer 1 (Catalog):  Curated collectible plush → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Squishmallows (Archie Axolotl, Emily Bat, Malcolm Mushroom, Benny Bigfoot,
  select exclusives, HTF, jumbo, clips)
- Jellycat (Bashful Bunny, Amuseable, Bartholomew Bear, retired/discontinued,
  London exclusive)
- Sanrio (Hello Kitty, Cinnamoroll, My Melody, Kuromi, Pompompurin,
  limited/collaboration)
- Build-A-Bear (Pokémon, licensed, limited edition, online exclusive)
- Pokémon Center plush (sitting cuties, special editions, large scale,
  Japanese exclusive)
- Vintage/Grail plush (Beanie Babies grails, TY Princess Diana bear,
  vintage Care Bears, 1980s-90s)
- Disney plush (park exclusives, nuiMOs, Stitch, limited release)
- KAWS art toys, Steiff limited editions, San-X (Rilakkuma, Sumikko Gurashi)
- Squishable, Pusheen, Gund, Ty Beanie Boos

Usage:
    python -m pipelines.import_plush_collectibles [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem, PriceObservation, SupabaseIngest,
    write_training_jsonl, write_catalog_sql,
    log_progress, slugify,
    rarity_score as shared_rarity_score,
    logger,
    close_http_client,
)

CATEGORY = "plush_collectibles"

# ---------------------------------------------------------------------------
# Plush-specific rarity overrides (supplement shared RARITY_SCORE_MAP)
# ---------------------------------------------------------------------------
_PLUSH_RARITY: dict[str, float] = {
    "Common": 0.1,
    "Uncommon": 0.3,
    "Rare": 0.5,
    "HTF": 0.75,       # Hard To Find — between Rare and Grail
    "Grail": 0.95,
}

# Brand prestige scores
_BRAND_SCORE: dict[str, float] = {
    "Jellycat": 0.9,
    "Squishmallows": 0.8,
    "Sanrio": 0.7,
    "Pokémon Center": 0.6,
    "Build-A-Bear": 0.6,
    "Disney": 0.6,
    "TY": 0.6,
    "Care Bears": 0.6,
    "Steiff": 0.6,
    "KAWS": 0.9,
    "San-X": 0.7,
    "Squishable": 0.5,
    "Pusheen": 0.5,
    "Gund": 0.5,
    "Bandai": 0.5,
    "Ghibli": 0.7,
    "Cabbage Patch": 0.6,
    "Kenner": 0.5,
    "Mattel": 0.5,
    "Tonka": 0.5,
    "Coleco": 0.5,
    "Kamar": 0.4,
    "Dakin": 0.4,
    "Molang": 0.4,
    "Line Friends": 0.5,
    "Banpresto": 0.6,
    "Sun Arrow": 0.7,
    "San-ei": 0.6,
}


def _plush_rarity_score(rarity: str) -> float:
    """Map plush rarity to 0-1, using local overrides then shared map."""
    return _PLUSH_RARITY.get(rarity, shared_rarity_score(rarity))


def _additional_plush_2025_expansion() -> list[tuple]:
    """50 more: Steiff, Gund/Pusheen, Aurora/Miyoni, Jellycat, Kapibarasan, Rilakkuma."""
    return [
        # ── Steiff Limited Editions ────────────────────────────────────────
        ("Steiff Classic 1907 Teddy Bear Replica", "Steiff", "Classic Replica", 'Medium 35cm', 250, "Rare", True, "Numbered replica of 1907 original, mohair"),
        ("Steiff Teddy Bear 1902 Replica 55PB", "Steiff", "Classic Replica", 'Large 55cm', 400, "Grail", True, "First Steiff bear replica, museum piece"),
        ("Steiff x Disney Mickey Mouse 1932 Replica", "Steiff", "Disney Collab", 'Medium 30cm', 180, "Rare", True, "Disney x Steiff collab, felt ears"),
        ("Steiff x Disney Winnie the Pooh", "Steiff", "Disney Collab", 'Medium 25cm', 150, "Rare", False, "Classic Pooh mohair, red shirt"),
        ("Steiff x Disney Bambi", "Steiff", "Disney Collab", 'Medium 20cm', 130, "Rare", False, "Airbrush details, spotted fawn"),
        ("Steiff Christmas Teddy Bear 2024", "Steiff", "Annual Christmas", 'Medium 30cm', 120, "Uncommon", False, "2024 annual Christmas bear, gold bow"),
        ("Steiff Christmas Teddy Bear 2023", "Steiff", "Annual Christmas", 'Medium 30cm', 140, "Uncommon", True, "2023 edition, burgundy velvet ribbon"),
        ("Steiff Teddybear Workshop Bear", "Steiff", "Special Edition", 'Small 22cm', 95, "Uncommon", True, "Steiff workshop exclusive, leather apron"),
        ("Steiff Polar Bear Ted", "Steiff", "Wildlife", 'Large 45cm', 200, "Rare", True, "White mohair, glass eyes, LE 1500"),

        # ── Gund — Pusheen Series & Snuffles ──────────────────────────────
        ("Pusheen Classic Plush", "Gund", "Pusheen", 'Medium 30cm', 25, "Common", False, "Classic grey tabby cat Pusheen"),
        ("Pusheen Mermaid", "Gund", "Pusheen", 'Medium 25cm', 28, "Common", False, "Pusheen in mermaid tail costume"),
        ("Pusheen Unicorn (Pusheenicorn)", "Gund", "Pusheen", 'Medium 33cm', 30, "Common", False, "Rainbow horn and wings"),
        ("Pusheen Detective", "Gund", "Pusheen", 'Medium 25cm', 30, "Uncommon", False, "Sherlock hat and magnifying glass"),
        ("Pusheen Dragon (Dragonsheen)", "Gund", "Pusheen", 'Medium 28cm', 30, "Common", False, "Green dragon wings and tail"),
        ("Pusheen Holiday Stocking Set", "Gund", "Pusheen", 'Set 15cm each', 45, "Uncommon", True, "3-piece holiday mini set in stocking"),
        ("Snuffles 40th Anniversary Bear", "Gund", "Snuffles", 'Large 38cm', 60, "Uncommon", True, "40th anniversary gold tag, white fur"),
        ("Snuffles Polar Bear", "Gund", "Snuffles", 'Medium 25cm', 35, "Common", False, "Classic polar white Snuffles bear"),

        # ── Aurora World — Miyoni Realistic Animals ────────────────────────
        ("Miyoni Tabby Cat", "Aurora World", "Miyoni", 'Medium 28cm', 22, "Common", False, "Realistic tabby, weighted paws"),
        ("Miyoni Red Panda", "Aurora World", "Miyoni", 'Medium 25cm', 25, "Common", False, "Realistic red panda, bushy tail"),
        ("Miyoni Fennec Fox", "Aurora World", "Miyoni", 'Medium 23cm', 22, "Common", False, "Large ears, desert fox realistic"),
        ("Miyoni Snow Leopard", "Aurora World", "Miyoni", 'Medium 30cm', 28, "Common", False, "Spotted grey coat, long tail"),
        ("Miyoni Barn Owl", "Aurora World", "Miyoni", 'Medium 22cm', 20, "Common", False, "Heart-shaped face, realistic plumage"),
        ("Miyoni Emperor Penguin Chick", "Aurora World", "Miyoni", 'Medium 20cm', 18, "Common", False, "Grey fluffy baby penguin"),

        # ── Jellycat — Extended Range ──────────────────────────────────────
        ("Jellycat Bashful Dragon (Sage)", "Jellycat", "Bashful", 'Medium 31cm', 30, "Common", False, "Sage green dragon, corduroy wings"),
        ("Jellycat Bashful Dragon (Blush)", "Jellycat", "Bashful", 'Medium 31cm', 30, "Common", False, "Pink blush dragon, suede-feel wings"),
        ("Jellycat Amuseable Doughnut", "Jellycat", "Amuseable", 'Medium 18cm', 25, "Common", False, "Ring doughnut with sprinkles, cord legs"),
        ("Jellycat Amuseable Avocado", "Jellycat", "Amuseable", 'Medium 20cm', 25, "Common", False, "Smiling half avocado with pit"),
        ("Jellycat Amuseable Croissant", "Jellycat", "Amuseable", 'Medium 20cm', 25, "Common", False, "Golden flaky pastry with cord legs"),
        ("Jellycat Odyssey Octopus", "Jellycat", "Odyssey", 'Large 49cm', 45, "Uncommon", False, "Teal octopus, 8 curly tentacles"),
        ("Jellycat Vivacious Vegetable Broccoli", "Jellycat", "Vivacious Vegetable", 'Medium 17cm', 20, "Common", False, "Green broccoli with happy face"),
        ("Jellycat Delaney Diplodocus", "Jellycat", "Dinosaur", 'Large 50cm', 50, "Uncommon", False, "Long-neck dinosaur, corduroy tummy"),
        ("Jellycat Fuddlewuddle Dragon", "Jellycat", "Fuddlewuddle", 'Medium 23cm', 28, "Common", False, "Teal/lime green cuddly dragon"),
        ("Jellycat Retired Bashful Fox (Huge)", "Jellycat", "Bashful Retired", 'Huge 51cm', 90, "HTF", True, "Discontinued huge fox, highly collectible"),

        # ── Kapibarasan (Capybara) ─────────────────────────────────────────
        ("Kapibarasan Classic Plush", "Bandai", "Kapibarasan", 'Medium 25cm', 30, "Common", False, "Classic brown capybara, Tryworks original"),
        ("Kapibarasan White-san", "Bandai", "Kapibarasan", 'Medium 25cm', 32, "Common", False, "White capybara friend White-san"),
        ("Kapibarasan Baby (Kapibaby)", "Bandai", "Kapibarasan", 'Small 15cm', 22, "Common", False, "Baby capybara, smaller round version"),
        ("Kapibarasan Resting Pose XL", "Bandai", "Kapibarasan", 'XL 60cm', 80, "Uncommon", False, "Oversized resting capybara, huggable"),
        ("Kapibarasan Hot Spring Edition", "Bandai", "Kapibarasan", 'Medium 25cm', 38, "Uncommon", True, "Onsen theme with towel accessory, limited"),

        # ── Rilakkuma / San-X Anniversary & Friends ────────────────────────
        ("Rilakkuma 20th Anniversary Plush", "San-X", "Rilakkuma", 'Large 40cm', 75, "Rare", False, "20th anniversary gold ribbon edition"),
        ("Rilakkuma Classic Lying Down", "San-X", "Rilakkuma", 'Medium 30cm', 35, "Common", False, "Classic relaxing bear pose"),
        ("Korilakkuma Classic", "San-X", "Rilakkuma", 'Medium 28cm', 32, "Common", False, "White bear with red button, Rilakkuma friend"),
        ("Korilakkuma Strawberry", "San-X", "Rilakkuma", 'Medium 25cm', 35, "Uncommon", False, "Strawberry costume Korilakkuma"),
        ("Kiiroitori Chick Classic", "San-X", "Rilakkuma", 'Small 18cm', 25, "Common", False, "Yellow chick, Rilakkuma's pet bird"),
        ("Kiiroitori Chef Costume", "San-X", "Rilakkuma", 'Small 18cm', 30, "Uncommon", False, "Chef hat and apron Kiiroitori"),
        ("Rilakkuma Honey Bee", "San-X", "Rilakkuma", 'Medium 28cm', 40, "Uncommon", True, "Bee costume with wings, limited seasonal"),
        ("Rilakkuma Astronaut", "San-X", "Rilakkuma", 'Medium 28cm', 45, "Uncommon", True, "Space suit theme, NASA collab limited"),
        ("Sumikko Gurashi Tokage (Lizard)", "San-X", "Sumikko Gurashi", 'Medium 22cm', 28, "Common", False, "Shy lizard pretending to be dinosaur"),
        ("Sumikko Gurashi Shirokuma (Polar Bear)", "San-X", "Sumikko Gurashi", 'Medium 22cm', 28, "Common", False, "Cold-sensitive polar bear from the north"),
    ]


def get_curated_catalog() -> list[dict]:
    """Curated plush collectibles catalog: 500+ items across 18 sub-categories."""

    # Format: (name, brand, series, size, price_eur, rarity, is_retired, notes)

    items = [
        # ── Squishmallows (22) ──────────────────────────────────────────
        ("Archie the Axolotl", "Squishmallows", "Original Squad", '12"', 35, "Uncommon", False, "Fan-favourite axolotl"),
        ("Emily the Bat", "Squishmallows", "Halloween Squad", '12"', 45, "Uncommon", False, "Halloween 2021 release"),
        ("Malcolm the Mushroom", "Squishmallows", "Original Squad", '12"', 55, "Rare", False, "Highly sought-after design"),
        ("Benny the Bigfoot", "Squishmallows", "Original Squad", '12"', 40, "Uncommon", False, "Brown bigfoot plush"),
        ("Brina the Bigfoot", "Squishmallows", "Original Squad", '12"', 65, "Rare", True, "Pink bigfoot, retired 2021"),
        ("Jack the Black Cat", "Squishmallows", "Halloween Squad", '12"', 70, "Rare", True, "Halloween exclusive, retired"),
        ("Phillipe the Frog", "Squishmallows", "Original Squad", '12"', 80, "HTF", True, "Canadian exclusive, retired"),
        ("Avery the Mallard Duck", "Squishmallows", "Original Squad", '12"', 30, "Uncommon", False, "Green mallard"),
        ("Wendy the Frog", "Squishmallows", "Original Squad", '12"', 25, "Common", False, "Green frog, widely available"),
        ("Connor the Cow", "Squishmallows", "Original Squad", '12"', 55, "Rare", False, "Black and white cow"),
        ("Caedyn the Pink Cow", "Squishmallows", "Valentine Squad", '12"', 90, "HTF", False, "Pink cow, Valentine exclusive"),
        ("Ronnie the Cow", "Squishmallows", "Original Squad", '12"', 45, "Uncommon", False, "Brown spotted cow"),
        ("Reshma the Pink Strawberry", "Squishmallows", "Fruit Squad", '8"', 25, "Common", False, "Small strawberry plush"),
        ("Belana the Cow", "Squishmallows", "Easter Squad", '16"', 60, "Rare", False, "Blue cow, Easter 2022"),
        ("Archie the Axolotl Jumbo", "Squishmallows", "Original Squad", '24" Jumbo', 110, "HTF", False, "Jumbo size, limited stock"),
        ("Emily the Bat Clip", "Squishmallows", "Halloween Squad", 'Clip 3.5"', 12, "Common", False, "Backpack clip version"),
        ("Malcolm the Mushroom Clip", "Squishmallows", "Original Squad", 'Clip 3.5"', 15, "Common", False, "Backpack clip version"),
        ("Benny the Bigfoot Mini", "Squishmallows", "Original Squad", '5"', 8, "Common", False, "Mini size, widely available"),
        ("Santino the Platypus", "Squishmallows", "Learning Squad", '12"', 35, "Uncommon", False, "Teal platypus"),
        ("Fifi the Fox", "Squishmallows", "Original Squad", '12"', 95, "HTF", True, "2018 original run, retired"),
        ("Dawn the Deer", "Squishmallows", "Holiday Squad", '12"', 75, "Rare", True, "2019 holiday exclusive, retired"),
        ("Heather the Dragonfly", "Squishmallows", "Select Series", '12"', 120, "HTF", True, "Five Below exclusive, retired 2020"),

        # ── Jellycat (15) ───────────────────────────────────────────────
        ("Bashful Bunny Beige", "Jellycat", "Bashful", 'Medium 31cm', 28, "Common", False, "Classic Jellycat bunny"),
        ("Bashful Bunny Blush", "Jellycat", "Bashful", 'Medium 31cm', 30, "Common", False, "Pink variant"),
        ("Bashful Bunny Lilac", "Jellycat", "Bashful", 'Medium 31cm', 55, "Uncommon", True, "Retired colour"),
        ("Bartholomew Bear", "Jellycat", "Bartholomew", 'Medium 28cm', 35, "Common", False, "Brown bear with scarf"),
        ("Bartholomew Bear Really Big", "Jellycat", "Bartholomew", 'Really Big 46cm', 80, "Uncommon", False, "Oversized Bartholomew"),
        ("Amuseable Avocado", "Jellycat", "Amuseable", 'Small 20cm', 22, "Common", False, "TikTok-viral avocado"),
        ("Amuseable Toast", "Jellycat", "Amuseable", 'Small 17cm', 22, "Common", False, "Bread slice with face"),
        ("Amuseable Pineapple", "Jellycat", "Amuseable", 'Medium 25cm', 35, "Uncommon", True, "Retired Amuseable"),
        ("Fuddlewuddle Elephant", "Jellycat", "Fuddlewuddle", 'Medium 23cm', 30, "Common", False, "Grey elephant, textured fur"),
        ("Odell Octopus", "Jellycat", "Marine", 'Medium 23cm', 32, "Common", False, "Teal octopus with corduroy tentacles"),
        ("Blossom Bunny Silver", "Jellycat", "Blossom", 'Medium 31cm', 32, "Common", False, "Floral-ear bunny"),
        ("Scrumptious Dragon", "Jellycat", "Scrumptious", 'Medium 26cm', 120, "HTF", True, "Discontinued 2019, collector favourite"),
        ("Bashful Bunny Lavender", "Jellycat", "Bashful", 'Huge 51cm', 95, "Rare", True, "Retired huge size, hard to find"),
        ("London Bus", "Jellycat", "London Collection", 'Medium 17cm', 75, "Rare", False, "London flagship exclusive"),
        ("Jellycat London Bear", "Jellycat", "London Collection", 'Medium 22cm', 85, "Rare", False, "London store-only exclusive"),

        # ── Sanrio (12) ─────────────────────────────────────────────────
        ("Hello Kitty Classic Plush", "Sanrio", "Hello Kitty", 'Medium 25cm', 25, "Common", False, "Classic seated Hello Kitty"),
        ("Hello Kitty 50th Anniversary Gold", "Sanrio", "Hello Kitty", 'Medium 25cm', 65, "Rare", False, "2024 50th anniversary limited"),
        ("Cinnamoroll Large Plush", "Sanrio", "Cinnamoroll", 'Large 40cm', 45, "Uncommon", False, "White puppy with blue eyes"),
        ("Cinnamoroll x Miniso Collab", "Sanrio", "Cinnamoroll", 'Medium 30cm', 35, "Uncommon", False, "Miniso collaboration exclusive"),
        ("My Melody Classic Plush", "Sanrio", "My Melody", 'Medium 25cm', 25, "Common", False, "Pink hood rabbit"),
        ("My Melody x Laduree Paris", "Sanrio", "My Melody", 'Medium 28cm', 85, "Rare", False, "Laduree Paris collaboration"),
        ("Kuromi Gothic Plush", "Sanrio", "Kuromi", 'Medium 25cm', 30, "Common", False, "Black jester hood character"),
        ("Kuromi x Anna Sui Collab", "Sanrio", "Kuromi", 'Medium 28cm', 95, "Rare", False, "Anna Sui fashion collab"),
        ("Pompompurin Classic Plush", "Sanrio", "Pompompurin", 'Medium 25cm', 25, "Common", False, "Golden retriever with beret"),
        ("Pompompurin Pancake Stack", "Sanrio", "Pompompurin", 'Medium 30cm', 55, "Uncommon", False, "Stacking pancake design"),
        ("Little Twin Stars Kiki & Lala Set", "Sanrio", "Little Twin Stars", 'Pair 20cm each', 60, "Uncommon", True, "Retired pair set"),
        ("Sanrio Characters Dream Collab", "Sanrio", "All Stars", 'Large 35cm', 110, "HTF", False, "Sanrio Puroland event exclusive"),

        # ── Build-A-Bear (8) ────────────────────────────────────────────
        ("Pikachu Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 55, "Uncommon", False, "Pokémon collab, online exclusive"),
        ("Eevee Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 55, "Uncommon", False, "Pokémon collab, online exclusive"),
        ("Charmander Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 60, "Uncommon", True, "Retired Pokémon collab"),
        ("Toothless Build-A-Bear", "Build-A-Bear", "How to Train Your Dragon", 'Standard 40cm', 45, "Uncommon", False, "DreamWorks licensed"),
        ("Grogu Build-A-Bear", "Build-A-Bear", "Star Wars", 'Standard 35cm', 50, "Uncommon", False, "The Child / Baby Yoda"),
        ("Baby Yoda Sound Build-A-Bear", "Build-A-Bear", "Star Wars", 'Standard 35cm', 75, "Rare", True, "With sound chip, limited run"),
        ("Spider-Man Build-A-Bear", "Build-A-Bear", "Marvel", 'Standard 40cm', 50, "Uncommon", False, "Marvel licensed"),
        ("Stitch Build-A-Bear", "Build-A-Bear", "Disney", 'Standard 40cm', 65, "Rare", True, "Online exclusive, retired 2023"),

        # ── Pokémon Center Plush (10) ───────────────────────────────────
        ("Pikachu Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 15, "Common", False, "Pokémon Fit / Sitting Cuties line"),
        ("Eevee Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 15, "Common", False, "Pokémon Fit / Sitting Cuties line"),
        ("Snorlax Large Plush", "Pokémon Center", "Large Scale", '60cm', 120, "Rare", False, "Oversized sleeping Snorlax"),
        ("Life-Size Mewtwo Plush", "Pokémon Center", "Life-Size", '150cm', 450, "HTF", False, "Japan-exclusive life-size, limited stock"),
        ("Charizard Premium Plush", "Pokémon Center", "Premium Collection", '35cm', 55, "Uncommon", False, "Detailed premium quality"),
        ("Gengar Night Parade Plush", "Pokémon Center", "Halloween Collection", 'Medium 25cm', 40, "Uncommon", True, "Halloween 2022, retired"),
        ("Mimikyu Special Edition", "Pokémon Center", "Special Edition", 'Medium 25cm', 45, "Uncommon", False, "Ghost-type fan favourite"),
        ("Lucario Poseable Plush", "Pokémon Center", "Poseable Series", '30cm', 60, "Rare", False, "Articulated plush figure"),
        ("Ditto Transform Pikachu", "Pokémon Center", "Ditto Transform", 'Small 15cm', 20, "Common", False, "Ditto-face Pikachu"),
        ("Rayquaza Long Plush", "Pokémon Center", "Japanese Exclusive", '180cm', 350, "HTF", True, "Japan-only mega-size, retired"),

        # ── Vintage / Grail Plush (8) ──────────────────────────────────
        ("Princess Diana Bear (1st Edition)", "TY", "Beanie Babies", '22cm', 5000, "Grail", True, "PVC pellets, 1st edition, no space in poem"),
        ("Peanut the Royal Blue Elephant", "TY", "Beanie Babies", '20cm', 3000, "Grail", True, "1995 colour error, extremely rare"),
        ("Valentino Bear (Brown Nose Error)", "TY", "Beanie Babies", '20cm', 1800, "Grail", True, "Manufacturing error variant"),
        ("Brownie the Bear", "TY", "Beanie Babies", '20cm', 2500, "Grail", True, "Original 1993 name, pre-Cubbie"),
        ("Tenderheart Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 250, "HTF", True, "1983 Kenner original with tag"),
        ("Bedtime Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 200, "Rare", True, "1983 Kenner original"),
        ("Good Luck Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 220, "Rare", True, "1983 Kenner original, green"),
        ("Steiff Teddy Bear 1902 Replica", "Steiff", "Vintage Replica", '35cm', 450, "HTF", True, "Limited numbered replica of the 1902 original"),

        # ── Disney Plush (8) ────────────────────────────────────────────
        ("Stitch Crashes Disney (Beauty and the Beast)", "Disney", "Stitch Crashes Disney", 'Medium 30cm', 65, "Rare", True, "Monthly limited series, retired"),
        ("Stitch Crashes Disney (The Lion King)", "Disney", "Stitch Crashes Disney", 'Medium 30cm', 70, "Rare", True, "Monthly limited series, retired"),
        ("Mickey Mouse nuiMOs Plush", "Disney", "nuiMOs", 'Small 16cm', 28, "Common", False, "Poseable plush with outfit system"),
        ("Stitch nuiMOs Plush", "Disney", "nuiMOs", 'Small 16cm', 30, "Common", False, "Poseable plush with outfit system"),
        ("Spirit Jersey Bear (50th Anniversary)", "Disney", "Walt Disney World 50th", 'Medium 30cm', 85, "Rare", True, "WDW 50th anniversary park exclusive"),
        ("Orange Bird Plush", "Disney", "EPCOT Flower & Garden", 'Medium 25cm', 55, "Uncommon", True, "EPCOT festival exclusive, retired"),
        ("Figment Plush (EPCOT)", "Disney", "EPCOT", 'Medium 30cm', 45, "Uncommon", False, "EPCOT park exclusive dragon"),
        ("Wishables Dumbo (Mystery)", "Disney", "Wishables", 'Micro 12cm', 18, "Common", False, "Blind bag micro plush"),

        # ── Squishmallows — Jumbo / Seasonal / Costco (8) ─────────────────
        ("Benny the Bigfoot Jumbo", "Squishmallows", "Original Squad", '24" Jumbo', 120, "HTF", False, "24-inch jumbo, Costco exclusive"),
        ("Ronnie the Cow Jumbo", "Squishmallows", "Original Squad", '24" Jumbo', 130, "HTF", False, "24-inch jumbo cow, limited Costco stock"),
        ("Emily the Bat Halloween 2024", "Squishmallows", "Halloween Squad", '12"', 50, "Uncommon", False, "2024 Halloween reissue with glow eyes"),
        ("Valentina the Heart Bear", "Squishmallows", "Valentine Squad", '12"', 85, "HTF", True, "Valentine 2021 exclusive, retired"),
        ("Stacy the Squid Costco Exclusive", "Squishmallows", "Costco Exclusive", '20"', 95, "HTF", False, "Costco-only oversized squid"),
        ("Cam the Cat 1st Edition", "Squishmallows", "Original Squad", '12"', 150, "Grail", True, "2017 first generation, calico pattern, extremely rare"),
        ("Filippa the Frog Costco Exclusive", "Squishmallows", "Costco Exclusive", '24" Jumbo', 110, "HTF", False, "Jumbo teal frog, Costco exclusive"),
        ("Hans the Hedgehog Discontinued Print", "Squishmallows", "Original Squad", '12"', 90, "HTF", True, "Original 2019 print, discontinued pattern"),

        # ── Jellycat — Amuseables Food / Seasonal / Retired (8) ──────────
        ("Amuseable Coffee-To-Go", "Jellycat", "Amuseable", 'Small 18cm', 22, "Common", False, "Coffee cup plush, happy face"),
        ("Amuseable Sushi", "Jellycat", "Amuseable", 'Small 12cm', 20, "Common", False, "Nigiri sushi with nori band"),
        ("Amuseable Croissant", "Jellycat", "Amuseable", 'Medium 20cm', 24, "Common", False, "French pastry plush with face"),
        ("Amuseable Pizza Slice", "Jellycat", "Amuseable", 'Medium 21cm', 24, "Common", False, "Pizza slice with melty cheese face"),
        ("Amuseable Watermelon", "Jellycat", "Amuseable", 'Medium 28cm', 65, "Rare", True, "Retired Amuseable, high resale demand"),
        ("Bashful Bunny Moss", "Jellycat", "Bashful", 'Medium 31cm', 75, "Rare", True, "Retired 2020 colour, collector favourite"),
        ("Jellycat Christmas Festive Folly Snowman", "Jellycat", "Festive Folly", 'Small 12cm', 35, "Uncommon", True, "Christmas seasonal 2022, retired"),
        ("Bashful Dragon", "Jellycat", "Bashful", 'Medium 31cm', 130, "HTF", True, "Retired 2018, extremely high resale, legendary Jellycat"),

        # ── Pokemon Center Exclusives (8) ─────────────────────────────────
        ("Costume Pikachu Charizard Poncho", "Pokémon Center", "Costume Pikachu", 'Medium 25cm', 85, "Rare", True, "Pikachu in Charizard hoodie, JP exclusive"),
        ("Costume Pikachu Rayquaza Poncho", "Pokémon Center", "Costume Pikachu", 'Medium 25cm', 95, "Rare", True, "Pikachu in Rayquaza poncho, retired JP exclusive"),
        ("Sitting Cuties Bulbasaur", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 15, "Common", False, "Pokemon Fit line, bean-filled sitting pose"),
        ("Sitting Cuties Jigglypuff", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 15, "Common", False, "Pokemon Fit line, round sitting pose"),
        ("Pikachu Tokyo DX Exclusive", "Pokémon Center", "Regional Exclusive", 'Medium 25cm', 65, "Rare", False, "Tokyo DX Pokémon Center store-only"),
        ("Eevee Kyoto Maiko Exclusive", "Pokémon Center", "Regional Exclusive", 'Medium 22cm', 75, "Rare", False, "Kyoto store-only, Maiko geisha Eevee"),
        ("Gengar Large Mouth Cushion", "Pokémon Center", "Large Scale", '45cm', 90, "Uncommon", False, "Open-mouth cushion plush, JP exclusive"),
        ("Pikachu Pair Plush Wedding Set", "Pokémon Center", "Special Edition", 'Pair 20cm each', 55, "Uncommon", True, "Bride & groom Pikachu pair, retired"),

        # ── San-X: Rilakkuma / Sumikko Gurashi (6) ───────────────────────
        ("Rilakkuma Classic Lying Down", "San-X", "Rilakkuma", 'Medium 30cm', 35, "Common", False, "Classic lazy bear lying pose"),
        ("Rilakkuma x Deli Theme JP Exclusive", "San-X", "Rilakkuma", 'Medium 25cm', 55, "Rare", False, "Japan-only deli sandwich theme"),
        ("Korilakkuma Strawberry Cat", "San-X", "Rilakkuma", 'Medium 25cm', 40, "Uncommon", False, "White bear with strawberry, cat ears"),
        ("Sumikko Gurashi Tokage Plush", "San-X", "Sumikko Gurashi", 'Medium 20cm', 28, "Common", False, "Shy dinosaur pretending to be lizard"),
        ("Sumikko Gurashi Shirokuma Large", "San-X", "Sumikko Gurashi", 'Large 40cm', 55, "Uncommon", False, "Polar bear who dislikes cold, large size"),
        ("Sumikko Gurashi 10th Anniversary Set", "San-X", "Sumikko Gurashi", 'Set 5x 12cm', 85, "Rare", False, "10th anniversary boxed set, JP exclusive"),

        # ── Steiff (5) ────────────────────────────────────────────────────
        ("Steiff Classic Teddy Bear 1920 Replica", "Steiff", "Vintage Replica", '35cm', 380, "HTF", True, "Limited numbered replica of 1920 blonde teddy"),
        ("Steiff Margarete Memorial Bear 2024", "Steiff", "Limited Edition", '28cm', 250, "Rare", False, "Annual Margarete Steiff tribute bear"),
        ("Steiff Elephant Elefaentle Limited", "Steiff", "Limited Edition", '22cm', 195, "Rare", False, "Limited collector elephant, numbered"),
        ("Steiff Polar Bear Ice King", "Steiff", "Limited Edition", '35cm', 320, "HTF", False, "White mohair polar bear, 1500 pieces"),
        ("Steiff Teddy Bear Clown Limited", "Steiff", "Limited Edition", '30cm', 285, "Rare", True, "Retired clown bear, colourful mohair"),

        # ── KAWS Plush Art Toys (5) ───────────────────────────────────────
        ("KAWS Holiday Companion Plush Grey", "KAWS", "Holiday", 'Large 50cm', 320, "HTF", False, "KAWS lying down companion, grey"),
        ("KAWS BFF Plush Pink", "KAWS", "BFF", 'Medium 40cm', 280, "HTF", True, "BFF character plush, pink, retired"),
        ("KAWS BFF Plush Blue", "KAWS", "BFF", 'Medium 40cm', 300, "HTF", True, "BFF character plush, blue, retired"),
        ("KAWS Companion Plush Black 2019", "KAWS", "Companion", 'Large 50cm', 350, "HTF", True, "All-black companion plush, Dior era"),
        ("KAWS Sesame Street Uniqlo Elmo", "KAWS", "Sesame Street", 'Medium 35cm', 120, "Rare", True, "KAWS x Uniqlo x Sesame Street Elmo plush"),

        # ── Squishable (4) ────────────────────────────────────────────────
        ("Squishable Massive Bee", "Squishable", "Massive Round", '38cm', 55, "Common", False, "Giant round bumblebee plush"),
        ("Squishable Massive Plague Doctor", "Squishable", "Massive Round", '38cm', 60, "Uncommon", False, "Popular plague doctor design"),
        ("Squishable Mini Axolotl", "Squishable", "Mini Series", '18cm', 22, "Common", False, "Mini round axolotl plush"),
        ("Squishable Massive Dragon", "Squishable", "Massive Round", '38cm', 55, "Common", False, "Green dragon massive round plush"),

        # ── Disney Store Expanded (4) ─────────────────────────────────────
        ("Stitch Crashes Disney (Aladdin)", "Disney", "Stitch Crashes Disney", 'Medium 30cm', 75, "Rare", True, "Monthly limited series, Aladdin theme, retired"),
        ("nuiMOs Elsa Plush", "Disney", "nuiMOs", 'Small 16cm', 32, "Common", False, "Frozen Elsa poseable with outfit system"),
        ("nuiMOs Spirit Jersey Outfit Set", "Disney", "nuiMOs Outfits", 'Outfit accessory', 18, "Common", False, "Spirit jersey outfit for nuiMOs plush"),
        ("Mickey Mouse Vintage 1930s Replica", "Disney", "Walt Disney Archives", 'Medium 30cm', 95, "Rare", True, "Archive Collection vintage 1930s style replica"),

        # ── Vintage Expanded (5) ──────────────────────────────────────────
        ("Princess Diana Bear (2nd Edition PVC)", "TY", "Beanie Babies", '22cm', 1500, "Grail", True, "2nd edition, PVC pellets, no space in poem"),
        ("Humphrey the Camel", "TY", "Beanie Babies", '20cm', 2000, "Grail", True, "1993 original nine, extremely rare"),
        ("Nana the Monkey (Name Error)", "TY", "Beanie Babies", '20cm', 3500, "Grail", True, "1993 pre-Bongo name error, museum piece"),
        ("Wish Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 230, "Rare", True, "1983 Kenner original, turquoise"),
        ("Birthday Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 210, "Rare", True, "1983 Kenner original with cupcake belly"),

        # ── Squishmallows — Select Series / Store Exclusives (8) ─────────
        ("Zozo the Strawberry Frog", "Squishmallows", "Select Series", '12"', 85, "HTF", False, "Five Below Select Series, strawberry frog"),
        ("Calton the Blue Crab", "Squishmallows", "Sea Life Squad", '12"', 30, "Uncommon", False, "Blue crab plush, Maryland stores"),
        ("Piaxa the Pineapple", "Squishmallows", "Fruit Squad", '12"', 25, "Common", False, "Pineapple plush with leaf top"),
        ("Nixie the Butterfly", "Squishmallows", "Spring Squad", '12"', 45, "Uncommon", False, "Teal butterfly, spring 2023"),
        ("Gordon the Shark", "Squishmallows", "Sea Life Squad", '16"', 35, "Uncommon", False, "Grey shark, popular design"),
        ("Joelle the Bigfoot Valentine", "Squishmallows", "Valentine Squad", '12"', 70, "Rare", True, "Valentine 2022, purple bigfoot, retired"),
        ("Aziza the Strawberry Cow", "Squishmallows", "Fruit Squad", '12"', 95, "HTF", False, "Strawberry print cow, highly sought"),
        ("Bubba the Cow Learning Squad", "Squishmallows", "Learning Squad", '12"', 40, "Uncommon", False, "Purple cow, Learning Squad exclusive"),

        # ── Jellycat — New Releases & Collector Favourites (8) ───────────
        ("Amuseable Boiled Egg", "Jellycat", "Amuseable", 'Small 14cm', 18, "Common", False, "Runny yolk egg plush"),
        ("Amuseable Rainbow", "Jellycat", "Amuseable", 'Medium 24cm', 28, "Common", False, "Soft rainbow arc with face"),
        ("Bashful Bunny Cottontail", "Jellycat", "Bashful", 'Medium 31cm', 30, "Common", False, "Cream cottontail variant"),
        ("Bashful Bunny Forest", "Jellycat", "Bashful", 'Medium 31cm', 80, "Rare", True, "Retired 2019 forest green colour"),
        ("Jellycat Liberty Bunny London", "Jellycat", "London Collection", 'Medium 27cm', 70, "Rare", False, "Liberty London floral fabric ears"),
        ("Jellycat Fuddlewuddle Lion", "Jellycat", "Fuddlewuddle", 'Medium 23cm', 30, "Common", False, "Golden lion with mane"),
        ("Jellycat Storm Octopus", "Jellycat", "Marine", 'Large 49cm', 55, "Uncommon", False, "Inky blue octopus, corduroy tentacles"),
        ("Jellycat Bashful Bunny Plum", "Jellycat", "Bashful", 'Medium 31cm', 90, "Rare", True, "Retired 2018 plum colour, collector grail"),

        # ── Sanrio — Expanded Characters (6) ────────────────────────────
        ("Gudetama Lazy Egg Plush", "Sanrio", "Gudetama", 'Medium 25cm', 28, "Common", False, "Lazy egg character, lying pose"),
        ("Gudetama x Nissin Ramen Collab", "Sanrio", "Gudetama", 'Medium 28cm', 55, "Uncommon", False, "Gudetama in ramen bowl"),
        ("Cinnamoroll 20th Anniversary Plush", "Sanrio", "Cinnamoroll", 'Large 40cm', 75, "Rare", False, "20th anniversary limited with gold ribbon"),
        ("Pochacco Classic Plush", "Sanrio", "Pochacco", 'Medium 25cm', 25, "Common", False, "Sporty dog character"),
        ("Tuxedo Sam Plush", "Sanrio", "Tuxedo Sam", 'Medium 25cm', 30, "Common", False, "Penguin in bowtie"),
        ("Badtz-Maru XO Plush", "Sanrio", "Badtz-Maru", 'Medium 25cm', 28, "Common", False, "Spiky-haired penguin"),

        # ── Build-A-Bear — Additional Licensed (6) ──────────────────────
        ("Snorlax Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 65, "Rare", True, "Pokémon collab, retired"),
        ("Bulbasaur Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 55, "Uncommon", False, "Pokémon collab, online exclusive"),
        ("Sonic the Hedgehog Build-A-Bear", "Build-A-Bear", "Sonic", 'Standard 40cm', 45, "Uncommon", False, "SEGA licensed"),
        ("Super Mario Build-A-Bear", "Build-A-Bear", "Nintendo", 'Standard 40cm', 50, "Uncommon", False, "Nintendo licensed Mario"),
        ("Elsa Frozen Build-A-Bear", "Build-A-Bear", "Disney", 'Standard 40cm', 45, "Uncommon", True, "Disney Frozen collab, retired"),
        ("Harry Potter Hedwig Build-A-Bear", "Build-A-Bear", "Harry Potter", 'Standard 35cm', 55, "Rare", True, "WB licensed owl, retired"),

        # ── Pokémon Center — Expanded JP Exclusives (6) ─────────────────
        ("Slowpoke Paradise Plush", "Pokémon Center", "Regional Exclusive", 'Medium 25cm', 55, "Uncommon", False, "Kagawa Slowpoke Paradise store exclusive"),
        ("Pikachu Okinawa Shisa Exclusive", "Pokémon Center", "Regional Exclusive", 'Medium 22cm', 70, "Rare", False, "Okinawa store-only, Shisa lion Pikachu"),
        ("Pikachu Hokkaido Lavender", "Pokémon Center", "Regional Exclusive", 'Medium 22cm', 65, "Rare", False, "Hokkaido store-only, lavender theme"),
        ("Gengar Plush Cushion Large", "Pokémon Center", "Large Scale", '50cm', 85, "Uncommon", False, "Oversized Gengar face cushion"),
        ("Vaporeon Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 18, "Common", False, "Eeveelution sitting pose"),
        ("Umbreon Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 18, "Common", False, "Dark-type Eeveelution sitting pose"),

        # ── Pusheen (6) ─────────────────────────────────────────────────
        ("Pusheen Classic Plush", "Pusheen", "Classic", 'Medium 25cm', 22, "Common", False, "Grey tabby cat, iconic design"),
        ("Pusheen Pizza Plush", "Pusheen", "Snacktime", 'Medium 25cm', 25, "Common", False, "Pusheen with pizza slice"),
        ("Pusheen Mermaid", "Pusheen", "Mythical", 'Medium 25cm', 28, "Common", False, "Mermaid tail variant"),
        ("Pusheen Dinosaur", "Pusheen", "Costume", 'Medium 25cm', 28, "Common", False, "Green dinosaur costume variant"),
        ("Pusheen Halloween Witch", "Pusheen", "Halloween", 'Medium 25cm', 35, "Uncommon", True, "Halloween 2021, retired"),
        ("Pusheen Jumbo 2ft Plush", "Pusheen", "Jumbo", '60cm', 75, "Rare", False, "Oversized Pusheen plush"),

        # ── Gund (5) ────────────────────────────────────────────────────
        ("Gund Snuffles Bear White", "Gund", "Snuffles", 'Medium 25cm', 25, "Common", False, "Classic polar bear design"),
        ("Gund Snuffles Bear Pink", "Gund", "Snuffles", 'Medium 25cm', 25, "Common", False, "Pink variant of Snuffles"),
        ("Gund Pusheen Chef", "Gund", "Pusheen x Gund", 'Medium 25cm', 30, "Common", False, "Pusheen in chef hat, Gund made"),
        ("Gund Philbin Teddy Bear", "Gund", "Classic", 'Large 45cm', 45, "Uncommon", False, "Traditional teddy bear, tan"),
        ("Gund Sesame Street Elmo", "Gund", "Sesame Street", 'Medium 33cm', 25, "Common", False, "Official Sesame Street Elmo plush"),

        # ── TY Beanie Boos Modern (5) ───────────────────────────────────
        ("TY Beanie Boos Coconut Monkey", "TY", "Beanie Boos", '15cm', 8, "Common", False, "Brown monkey with glitter eyes"),
        ("TY Beanie Boos Glamour Leopard", "TY", "Beanie Boos", '15cm', 8, "Common", False, "Pink leopard, popular design"),
        ("TY Beanie Boos Fantasia Unicorn", "TY", "Beanie Boos", '24cm', 15, "Common", False, "Multicolour unicorn, medium size"),
        ("TY Beanie Boos Dotty Leopard Jumbo", "TY", "Beanie Boos", '40cm', 35, "Uncommon", False, "Jumbo rainbow leopard"),
        ("TY Flippables Tremor Dinosaur", "TY", "Flippables", '15cm', 12, "Common", False, "Sequin flip dinosaur"),

        # ── Steiff — Expanded Collectibles (5) ─────────────────────────
        ("Steiff Paddington Bear", "Steiff", "Licensed", '28cm', 95, "Uncommon", False, "Official Paddington with duffle coat"),
        ("Steiff Fynn Teddy Bear", "Steiff", "Classic", '28cm', 75, "Common", False, "Beige classic teddy, button in ear"),
        ("Steiff Hoppie Rabbit", "Steiff", "Classic", '28cm', 70, "Common", False, "Light grey rabbit, soft plush"),
        ("Steiff Disney Mickey Mouse", "Steiff", "Licensed", '30cm', 120, "Uncommon", False, "Mohair Mickey, button in ear"),
        ("Steiff Teddy Bear 1906 Replica LE", "Steiff", "Vintage Replica", '40cm', 550, "HTF", True, "Limited 1906 replica, gold mohair, numbered"),

        # ── KAWS — Additional Art Plush (4) ─────────────────────────────
        ("KAWS Holiday Companion Plush Brown", "KAWS", "Holiday", 'Large 50cm', 300, "HTF", False, "KAWS lying companion, brown"),
        ("KAWS Seeing/Watching Plush Grey", "KAWS", "Seeing/Watching", 'Medium 40cm', 250, "HTF", True, "Eyes covered figure plush, grey, retired"),
        ("KAWS Holiday Companion Plush Green", "KAWS", "Holiday", 'Large 50cm', 310, "HTF", False, "KAWS lying companion, green variant"),
        ("KAWS Sesame Street Uniqlo Cookie Monster", "KAWS", "Sesame Street", 'Medium 35cm', 130, "Rare", True, "KAWS x Uniqlo x Sesame Street Cookie Monster"),

        # ── San-X — Additional (4) ──────────────────────────────────────
        ("Rilakkuma Honey Forest Theme", "San-X", "Rilakkuma", 'Large 40cm', 50, "Uncommon", False, "Rilakkuma in bee costume with honey pot"),
        ("Korilakkuma Strawberry Party", "San-X", "Rilakkuma", 'Medium 25cm', 45, "Uncommon", False, "White bear with strawberry hat"),
        ("Sumikko Gurashi Neko Cat", "San-X", "Sumikko Gurashi", 'Medium 20cm', 25, "Common", False, "Shy calico cat who hides in corners"),
        ("Sumikko Gurashi Tapioca Set", "San-X", "Sumikko Gurashi", 'Set 5x 8cm', 40, "Uncommon", False, "Five coloured tapioca ball minis"),

        # ── Squishable — Expanded (4) ──────────────────────────────────
        ("Squishable Massive Corgi", "Squishable", "Massive Round", '38cm', 55, "Common", False, "Giant round corgi plush"),
        ("Squishable Mini Mushroom", "Squishable", "Mini Series", '18cm', 22, "Common", False, "Mini toadstool mushroom plush"),
        ("Squishable Massive Baphomet", "Squishable", "Massive Round", '38cm', 60, "Uncommon", False, "Occult-themed plush, cult favourite"),
        ("Squishable Massive Cat (Tabby)", "Squishable", "Massive Round", '38cm', 55, "Common", False, "Orange tabby massive round plush"),

        # ── Vintage / Grail — Expanded (4) ─────────────────────────────
        ("Trap the Mouse (Name Error)", "TY", "Beanie Babies", '20cm', 4000, "Grail", True, "1993 original nine, Korean-made, ultra rare"),
        ("Teddy Old Face Brown", "TY", "Beanie Babies", '20cm', 2200, "Grail", True, "1993 old-face design, extremely rare"),
        ("Funshine Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 240, "Rare", True, "1983 Kenner original, yellow with sun"),
        ("Steiff Teddy Bear 1904 Blank Button", "Steiff", "Vintage", '35cm', 8000, "Grail", True, "1904 original with blank ear button, museum grade"),

        # ── Jellycat — Bashful Range Extended (15) ────────────────────
        ("Bashful Bunny Cinnamon", "Jellycat", "Bashful", 'Medium 31cm', 30, "Common", False, "Warm brown cinnamon variant"),
        ("Bashful Bunny Silver", "Jellycat", "Bashful", 'Medium 31cm', 30, "Common", False, "Silver grey variant"),
        ("Bashful Bunny Toffee", "Jellycat", "Bashful", 'Medium 31cm', 65, "Uncommon", True, "Retired 2020 toffee colour"),
        ("Bashful Bunny Tulip", "Jellycat", "Bashful", 'Medium 31cm', 32, "Common", False, "Pink tulip variant"),
        ("Bashful Bunny Cloud", "Jellycat", "Bashful", 'Medium 31cm', 75, "Rare", True, "Retired light blue, collector favourite"),
        ("Bashful Bunny Elly Irresistible", "Jellycat", "Bashful", 'Medium 31cm', 85, "Rare", True, "Retired 2017 elephant variant"),
        ("Bashful Bunny Sparkly Cassis", "Jellycat", "Bashful", 'Medium 31cm', 45, "Uncommon", False, "Sparkly dark berry colour"),
        ("Bashful Bunny Petal", "Jellycat", "Bashful", 'Medium 31cm', 30, "Common", False, "Soft pink petal variant"),
        ("Bashful Bunny Mineral Blue", "Jellycat", "Bashful", 'Medium 31cm', 70, "Rare", True, "Retired mineral blue 2019"),
        ("Bashful Bunny Luxe Azure", "Jellycat", "Bashful", 'Huge 51cm', 120, "HTF", True, "Retired luxe huge size, blue shimmer"),
        ("Bashful Bunny Dusky Blue", "Jellycat", "Bashful", 'Medium 31cm', 80, "Rare", True, "Retired 2019, muted blue"),
        ("Bashful Bunny Fern", "Jellycat", "Bashful", 'Medium 31cm', 70, "Rare", True, "Retired 2019 green fern"),
        ("Bashful Bunny Grape", "Jellycat", "Bashful", 'Medium 31cm', 75, "Rare", True, "Retired 2018, deep purple"),
        ("Bashful Bunny Oat", "Jellycat", "Bashful", 'Medium 31cm', 30, "Common", False, "Neutral oat tone"),
        ("Bashful Kitten", "Jellycat", "Bashful", 'Medium 31cm', 30, "Common", False, "Grey and white kitten"),

        # ── Jellycat — Amuseable Range Extended (15) ──────────────────
        ("Amuseable Cloud", "Jellycat", "Amuseable", 'Medium 24cm', 24, "Common", False, "White fluffy cloud with face"),
        ("Amuseable Sun", "Jellycat", "Amuseable", 'Medium 27cm', 26, "Common", False, "Yellow sun with rays"),
        ("Amuseable Moon", "Jellycat", "Amuseable", 'Medium 27cm', 26, "Common", False, "Crescent moon with face"),
        ("Amuseable Cactus", "Jellycat", "Amuseable", 'Medium 24cm', 55, "Uncommon", True, "Retired cactus, potted"),
        ("Amuseable Mushroom", "Jellycat", "Amuseable", 'Medium 23cm', 24, "Common", False, "Red spotted toadstool"),
        ("Amuseable Doughnut", "Jellycat", "Amuseable", 'Small 18cm', 22, "Common", False, "Pink frosted doughnut"),
        ("Amuseable Pretzel", "Jellycat", "Amuseable", 'Medium 20cm', 24, "Common", False, "Salted pretzel with face"),
        ("Amuseable Sandwich", "Jellycat", "Amuseable", 'Medium 18cm', 22, "Common", False, "BLT sandwich plush"),
        ("Amuseable Popcorn", "Jellycat", "Amuseable", 'Medium 22cm', 24, "Common", False, "Striped popcorn box"),
        ("Amuseable Lemon", "Jellycat", "Amuseable", 'Small 18cm', 60, "Rare", True, "Retired lemon, collector sought"),
        ("Amuseable Strawberry", "Jellycat", "Amuseable", 'Small 18cm', 22, "Common", False, "Red strawberry with green top"),
        ("Amuseable Ice Cream Cone", "Jellycat", "Amuseable", 'Medium 19cm', 55, "Uncommon", True, "Retired soft serve cone"),
        ("Amuseable Baguette", "Jellycat", "Amuseable", 'Large 35cm', 28, "Common", False, "French baguette with face"),
        ("Amuseable Ramen", "Jellycat", "Amuseable", 'Small 16cm', 22, "Common", False, "Ramen bowl with noodles"),
        ("Amuseable Macaron", "Jellycat", "Amuseable", 'Small 12cm', 18, "Common", False, "Pink macaron with face"),

        # ── Jellycat — Other Lines (12) ──────────────────────────────
        ("Vivacious Vegetable Pea", "Jellycat", "Vivacious Vegetable", 'Medium 17cm', 20, "Common", False, "Pea pod with three peas"),
        ("Vivacious Vegetable Carrot", "Jellycat", "Vivacious Vegetable", 'Medium 17cm', 20, "Common", False, "Orange carrot with green top"),
        ("Vivacious Vegetable Aubergine", "Jellycat", "Vivacious Vegetable", 'Medium 19cm', 20, "Common", False, "Purple aubergine/eggplant"),
        ("Vivacious Vegetable Mushroom", "Jellycat", "Vivacious Vegetable", 'Medium 14cm', 20, "Common", False, "Brown button mushroom"),
        ("Jellycat Peanut Penguin Large", "Jellycat", "Peanut", 'Large 34cm', 45, "Common", False, "Black and white large penguin"),
        ("Jellycat Perry Polar Bear", "Jellycat", "Perry", 'Medium 26cm', 35, "Common", False, "White polar bear, soft fur"),
        ("Jellycat Fossilly T-Rex", "Jellycat", "Fossilly", 'Medium 28cm', 32, "Common", False, "Green dinosaur skeleton plush"),
        ("Jellycat Fossilly Triceratops", "Jellycat", "Fossilly", 'Medium 17cm', 25, "Common", False, "Beige triceratops"),
        ("Jellycat Cordy Roy Fox", "Jellycat", "Cordy Roy", 'Medium 26cm', 32, "Common", False, "Orange corduroy fox"),
        ("Jellycat Dexter Dragon", "Jellycat", "Dragon", 'Medium 26cm', 35, "Common", False, "Green dragon with wings"),
        ("Jellycat Merry Mouse Sleighing", "Jellycat", "Merry Mouse", 'Small 18cm', 40, "Uncommon", True, "Christmas seasonal, retired 2023"),
        ("Jellycat Woodland Bunny", "Jellycat", "Woodland", 'Medium 31cm', 95, "Rare", True, "Discontinued 2017 woodland series"),

        # ── Jellycat — Huge & Really Big Sizes (6) ────────────────────
        ("Bartholomew Bear Really Really Big", "Jellycat", "Bartholomew", 'Really Really Big 57cm', 130, "HTF", False, "Largest Bartholomew available"),
        ("Bashful Bunny Huge Beige", "Jellycat", "Bashful", 'Huge 51cm', 60, "Uncommon", False, "Huge classic beige bunny"),
        ("Bashful Bunny Huge Blush", "Jellycat", "Bashful", 'Huge 51cm', 62, "Uncommon", False, "Huge pink blush bunny"),
        ("Amuseable Avocado Huge", "Jellycat", "Amuseable", 'Huge 30cm', 45, "Uncommon", False, "Large avocado, TikTok viral"),
        ("Odell Octopus Really Big", "Jellycat", "Marine", 'Really Big 49cm', 65, "Uncommon", False, "Large teal octopus"),
        ("Fuddlewuddle Elephant Huge", "Jellycat", "Fuddlewuddle", 'Huge 44cm', 70, "Uncommon", False, "Huge grey elephant"),

        # ── Squishmallows — More Rare & Exclusive (14) ────────────────
        ("Babs the Blue Jay", "Squishmallows", "Original Squad", '12"', 40, "Uncommon", False, "Blue jay with crest"),
        ("Omar the Bear", "Squishmallows", "Original Squad", '12"', 35, "Uncommon", False, "Brown bear with bandana"),
        ("Herb the Turtle", "Squishmallows", "Original Squad", '12"', 30, "Common", False, "Green sea turtle"),
        ("Silvina the Snail", "Squishmallows", "Original Squad", '12"', 25, "Common", False, "Pink snail with shell"),
        ("Monica the Axolotl", "Squishmallows", "Original Squad", '12"', 40, "Uncommon", False, "Pink axolotl variant"),
        ("Treyton the Tiger", "Squishmallows", "Original Squad", '12"', 35, "Uncommon", False, "Orange tiger plush"),
        ("Hailey the Bigfoot", "Squishmallows", "Original Squad", '14"', 50, "Rare", False, "Teal bigfoot, hot topic exclusive"),
        ("Evangelica the Cow", "Squishmallows", "Original Squad", '12"', 80, "HTF", True, "Pink highland cow, retired"),
        ("Patty the Cow", "Squishmallows", "Original Squad", '12"', 55, "Rare", False, "Pink and white spotted cow"),
        ("Charity the Chicken", "Squishmallows", "Easter Squad", '12"', 45, "Uncommon", True, "Easter chicken, retired 2021"),
        ("Bernice the Boba Tea", "Squishmallows", "Food Squad", '12"', 35, "Uncommon", False, "Boba tea cup plush"),
        ("Ludwig the Frog", "Squishmallows", "Original Squad", '12"', 45, "Uncommon", False, "Blue frog, Hot Topic exclusive"),
        ("Rutabaga the Cat", "Squishmallows", "Select Series", '14"', 70, "Rare", False, "Purple cat, Walgreens exclusive"),
        ("Della the Duck", "Squishmallows", "Easter Squad", '12"', 60, "Rare", True, "Floral duck, Easter 2021, retired"),

        # ── Squishmallows — HugMees & Stackables (6) ─────────────────
        ("Connor the Cow HugMee", "Squishmallows", "HugMees", '14"', 45, "Uncommon", False, "Elongated cow hugging shape"),
        ("Wendy the Frog HugMee", "Squishmallows", "HugMees", '14"', 40, "Uncommon", False, "Elongated frog hugging shape"),
        ("Emily the Bat HugMee", "Squishmallows", "HugMees", '14"', 50, "Uncommon", False, "Elongated bat hugging shape"),
        ("Connor the Cow Stackable", "Squishmallows", "Stackables", '12"', 30, "Common", False, "Flat stackable cow shape"),
        ("Archie the Axolotl Micromallow", "Squishmallows", "Micromallows", '2.5"', 5, "Common", False, "Tiny capsule axolotl"),
        ("Malcolm the Mushroom Micromallow", "Squishmallows", "Micromallows", '2.5"', 8, "Common", False, "Tiny capsule mushroom"),

        # ── Pokemon Center — Sitting Cuties Extended (12) ─────────────
        ("Charmander Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 15, "Common", False, "Fire starter sitting pose"),
        ("Squirtle Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 15, "Common", False, "Water starter sitting pose"),
        ("Gengar Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 18, "Common", False, "Ghost type sitting pose"),
        ("Dragonite Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 18, "Common", False, "Dragon type sitting pose"),
        ("Togepi Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 15, "Common", False, "Egg pokemon sitting pose"),
        ("Mew Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 20, "Common", False, "Mythical pink sitting pose"),
        ("Sylveon Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 18, "Common", False, "Fairy Eeveelution sitting pose"),
        ("Espeon Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 18, "Common", False, "Psychic Eeveelution sitting pose"),
        ("Glaceon Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 18, "Common", False, "Ice Eeveelution sitting pose"),
        ("Leafeon Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 18, "Common", False, "Grass Eeveelution sitting pose"),
        ("Flareon Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 18, "Common", False, "Fire Eeveelution sitting pose"),
        ("Jolteon Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 18, "Common", False, "Electric Eeveelution sitting pose"),

        # ── Pokemon Center — More JP Exclusives (8) ──────────────────
        ("Pikachu Yokohama Exclusive", "Pokémon Center", "Regional Exclusive", 'Medium 25cm', 60, "Rare", False, "Yokohama sailor Pikachu"),
        ("Pikachu Osaka Takoyaki Exclusive", "Pokémon Center", "Regional Exclusive", 'Medium 22cm', 65, "Rare", False, "Osaka store-only, takoyaki theme"),
        ("Pikachu Hiroshima Momiji Exclusive", "Pokémon Center", "Regional Exclusive", 'Medium 22cm', 65, "Rare", False, "Hiroshima store-only, maple leaf"),
        ("Pikachu Nagoya Exclusive", "Pokémon Center", "Regional Exclusive", 'Medium 22cm', 65, "Rare", False, "Nagoya store-only, golden shachihoko"),
        ("Mimikyu Halloween 2023", "Pokémon Center", "Halloween Collection", 'Medium 25cm', 45, "Uncommon", True, "Halloween limited 2023, retired"),
        ("Fuecoco Plush", "Pokémon Center", "Scarlet & Violet", 'Medium 25cm', 30, "Common", False, "Gen 9 fire starter"),
        ("Sprigatito Plush", "Pokémon Center", "Scarlet & Violet", 'Medium 25cm', 30, "Common", False, "Gen 9 grass starter"),
        ("Quaxly Plush", "Pokémon Center", "Scarlet & Violet", 'Medium 25cm', 30, "Common", False, "Gen 9 water starter"),

        # ── Anime Plush (12) ─────────────────────────────────────────
        ("Pochita Chainsaw Man Plush", "Bandai", "Chainsaw Man", 'Medium 20cm', 28, "Common", False, "Pochita chainsaw dog"),
        ("Chopper One Piece Plush", "Bandai", "One Piece", 'Medium 25cm', 25, "Common", False, "Tony Tony Chopper"),
        ("Kon Bleach Plush", "Bandai", "Bleach", 'Medium 20cm', 22, "Common", False, "Kon lion mod soul plush"),
        ("Totoro My Neighbor Totoro Plush Medium", "Ghibli", "Studio Ghibli", 'Medium 25cm', 35, "Common", False, "Classic grey Totoro plush"),
        ("Totoro Large Size", "Ghibli", "Studio Ghibli", 'Large 45cm', 70, "Uncommon", False, "Oversized grey Totoro"),
        ("Catbus My Neighbor Totoro Plush", "Ghibli", "Studio Ghibli", 'Medium 30cm', 45, "Uncommon", False, "Catbus with opening door"),
        ("Jiji Kiki's Delivery Service Plush", "Ghibli", "Studio Ghibli", 'Medium 20cm', 30, "Common", False, "Black cat Jiji"),
        ("No-Face Spirited Away Plush", "Ghibli", "Studio Ghibli", 'Medium 22cm', 35, "Common", False, "No-Face kaonashi plush"),
        ("Demon Slayer Nezuko Plush", "Bandai", "Demon Slayer", 'Medium 20cm', 25, "Common", False, "Nezuko in box form"),
        ("My Hero Academia Deku Plush", "Bandai", "My Hero Academia", 'Medium 20cm', 22, "Common", False, "Izuku Midoriya chibi plush"),
        ("Naruto Kurama Plush", "Bandai", "Naruto", 'Medium 25cm', 28, "Common", False, "Nine-tails fox Kurama"),
        ("Spy x Family Anya Plush", "Bandai", "Spy x Family", 'Medium 20cm', 25, "Common", False, "Anya Forger chibi plush"),

        # ── TY Beanie Babies — More Vintage & Error Variants (10) ────
        ("Garcia the Bear", "TY", "Beanie Babies", '20cm', 1800, "Grail", True, "1995 tie-dye bear, original retired"),
        ("Peace the Bear", "TY", "Beanie Babies", '20cm', 800, "HTF", True, "Tie-dye peace sign, 1996 retired"),
        ("Lefty the Donkey (1996)", "TY", "Beanie Babies", '20cm', 1200, "Grail", True, "1996 political donkey, old face"),
        ("Righty the Elephant (1996)", "TY", "Beanie Babies", '20cm', 1200, "Grail", True, "1996 political elephant, old face"),
        ("Slither the Snake", "TY", "Beanie Babies", '20cm', 1500, "Grail", True, "1993 original nine, rare"),
        ("Spot the Dog (No Spot)", "TY", "Beanie Babies", '20cm', 2000, "Grail", True, "1993 original without spot on back, error"),
        ("Teddy Old Face Cranberry", "TY", "Beanie Babies", '20cm', 1800, "Grail", True, "1993 old-face cranberry, extremely rare"),
        ("Teddy Old Face Jade", "TY", "Beanie Babies", '20cm', 1800, "Grail", True, "1993 old-face jade, extremely rare"),
        ("Teddy Old Face Magenta", "TY", "Beanie Babies", '20cm', 1800, "Grail", True, "1993 old-face magenta, extremely rare"),
        ("Teddy Old Face Violet", "TY", "Beanie Babies", '20cm', 1800, "Grail", True, "1993 old-face violet, extremely rare"),

        # ── TY Beanie Boos — More Modern (6) ────────────────────────
        ("TY Beanie Boos Kiwi Bird", "TY", "Beanie Boos", '15cm', 8, "Common", False, "Green kiwi bird with glitter eyes"),
        ("TY Beanie Boos Ty Blue Husky", "TY", "Beanie Boos", '24cm', 15, "Common", False, "Blue husky medium size"),
        ("TY Beanie Boos Coral Fish", "TY", "Beanie Boos", '15cm', 8, "Common", False, "Multi-coloured fish"),
        ("TY Beanie Boos Enchanted Owl", "TY", "Beanie Boos", '15cm', 10, "Common", False, "Purple owl with glitter eyes"),
        ("TY Beanie Boos Twiggy Owl Large", "TY", "Beanie Boos", '40cm', 35, "Uncommon", False, "Large pink owl"),
        ("TY Beanie Boos Duke Dog", "TY", "Beanie Boos", '15cm', 8, "Common", False, "Brown and white puppy"),

        # ── Care Bears — More Vintage + Modern (8) ───────────────────
        ("Love-a-Lot Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 200, "Rare", True, "1983 Kenner original, pink with hearts"),
        ("Grumpy Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 220, "Rare", True, "1983 Kenner original, blue rainy cloud"),
        ("Cheer Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 210, "Rare", True, "1983 Kenner original, pink rainbow"),
        ("Share Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 200, "Rare", True, "1983 Kenner original, lavender milkshake"),
        ("Secret Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 250, "HTF", True, "1983 Kenner original, rare heart padlock"),
        ("Care Bears 40th Anniversary Set", "Care Bears", "Modern Care Bears", 'Set 5x 25cm', 120, "Rare", False, "2023 40th anniversary boxed set"),
        ("Unlock the Magic Grumpy Bear", "Care Bears", "Modern Care Bears", 'Medium 30cm', 25, "Common", False, "Modern Grumpy Bear plush"),
        ("Care Bears x Universal Monsters Franken-Bear", "Care Bears", "Modern Care Bears", 'Medium 30cm', 45, "Uncommon", True, "Universal collab, retired"),

        # ── Build-A-Bear — More Licensed (6) ────────────────────────
        ("Gengar Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 70, "Rare", True, "Pokémon ghost collab, retired"),
        ("Psyduck Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 55, "Uncommon", False, "Pokémon collab, yellow duck"),
        ("Bluey Build-A-Bear", "Build-A-Bear", "Bluey", 'Standard 40cm', 50, "Uncommon", False, "ABC Kids licensed Bluey"),
        ("Bingo Build-A-Bear", "Build-A-Bear", "Bluey", 'Standard 40cm', 50, "Uncommon", False, "ABC Kids licensed Bingo"),
        ("Wednesday Addams Build-A-Bear", "Build-A-Bear", "Wednesday", 'Standard 40cm', 55, "Uncommon", True, "Netflix licensed, retired"),
        ("My Little Pony Twilight Sparkle BAB", "Build-A-Bear", "My Little Pony", 'Standard 40cm', 45, "Uncommon", True, "Hasbro licensed, retired"),

        # ── Sanrio — More Characters & Collabs (8) ───────────────────
        ("Hello Kitty x Godiva Collab", "Sanrio", "Hello Kitty", 'Medium 25cm', 75, "Rare", True, "Godiva chocolate collab, retired"),
        ("Cinnamoroll x Mister Donut", "Sanrio", "Cinnamoroll", 'Medium 25cm', 45, "Uncommon", False, "Japan Mister Donut collaboration"),
        ("My Melody x Kuromi Pair Set", "Sanrio", "My Melody", 'Pair 20cm each', 55, "Uncommon", False, "BFF pair set boxed"),
        ("Aggretsuko Rage Mode", "Sanrio", "Aggretsuko", 'Medium 25cm', 30, "Common", False, "Red panda death metal pose"),
        ("Kerokerokeroppi Classic", "Sanrio", "Kerokerokeroppi", 'Medium 25cm', 28, "Common", False, "Classic green frog with V-shaped mouth"),
        ("Hangyodon Deep Sea", "Sanrio", "Hangyodon", 'Medium 20cm', 30, "Common", False, "Fish creature character"),
        ("Sanrio Characters Café Collab Set", "Sanrio", "All Stars", 'Set 5x 12cm', 65, "Uncommon", False, "Café theme mini set"),
        ("Kuromi 20th Anniversary", "Sanrio", "Kuromi", 'Large 40cm', 70, "Rare", False, "20th anniversary limited edition"),

        # ── Disney — More Park Exclusives (8) ────────────────────────
        ("Stitch Crashes Disney (Mulan)", "Disney", "Stitch Crashes Disney", 'Medium 30cm', 70, "Rare", True, "Monthly limited series, Mulan, retired"),
        ("Stitch Crashes Disney (Pinocchio)", "Disney", "Stitch Crashes Disney", 'Medium 30cm', 65, "Rare", True, "Monthly limited series, Pinocchio, retired"),
        ("Stitch Crashes Disney (Snow White)", "Disney", "Stitch Crashes Disney", 'Medium 30cm', 75, "Rare", True, "Monthly limited series, Snow White, retired"),
        ("Lotso Bear Scented", "Disney", "Toy Story", 'Medium 30cm', 40, "Uncommon", False, "Strawberry-scented Lotso"),
        ("Duffy the Disney Bear", "Disney", "Duffy & Friends", 'Medium 30cm', 55, "Uncommon", False, "Tokyo Disney Sea exclusive bear"),
        ("ShellieMay the Disney Bear", "Disney", "Duffy & Friends", 'Medium 30cm', 55, "Uncommon", False, "Tokyo Disney Sea exclusive girl bear"),
        ("LinaBell Fox", "Disney", "Duffy & Friends", 'Medium 30cm', 85, "Rare", False, "Shanghai Disney exclusive fox, highly popular"),
        ("Olu the Sea Turtle", "Disney", "Duffy & Friends", 'Medium 30cm', 60, "Uncommon", False, "Aulani Hawaii exclusive turtle"),

        # ── Pusheen — More Variants (6) ──────────────────────────────
        ("Pusheen Sloth Costume", "Pusheen", "Costume", 'Medium 25cm', 28, "Common", False, "Pusheen in sloth onesie"),
        ("Pusheen Ice Cream", "Pusheen", "Snacktime", 'Medium 25cm', 25, "Common", False, "Pusheen with ice cream cone"),
        ("Pusheen 10th Anniversary", "Pusheen", "Anniversary", 'Large 40cm', 65, "Rare", False, "10th anniversary gold limited edition"),
        ("Pusheen Stormy Cat", "Pusheen", "Stormy", 'Medium 20cm', 22, "Common", False, "Pusheen's sister Stormy"),
        ("Pusheen Squisheen Large", "Pusheen", "Squisheen", '40cm', 55, "Uncommon", False, "Squishy jumbo version"),
        ("Pusheen Nap Time", "Pusheen", "Classic", 'Medium 25cm', 22, "Common", False, "Sleeping Pusheen with mask"),

        # ── KAWS — More Art Plush (4) ────────────────────────────────
        ("KAWS Holiday Indonesia Plush", "KAWS", "Holiday", 'Large 50cm', 280, "HTF", False, "KAWS Indonesia lying companion"),
        ("KAWS Holiday Japan Mt Fuji Plush", "KAWS", "Holiday", 'Large 50cm', 340, "HTF", True, "Japan Mt Fuji companion, retired"),
        ("KAWS Companion Plush 20th Anniversary", "KAWS", "Companion", 'Large 50cm', 380, "HTF", True, "20th anniversary black/grey, limited"),
        ("KAWS Sesame Street Uniqlo Big Bird", "KAWS", "Sesame Street", 'Large 45cm', 140, "Rare", True, "KAWS x Uniqlo Big Bird plush"),

        # ── Squishable — More Designs (6) ────────────────────────────
        ("Squishable Massive Narwhal", "Squishable", "Massive Round", '38cm', 55, "Common", False, "Giant round narwhal plush"),
        ("Squishable Mini Frog", "Squishable", "Mini Series", '18cm', 22, "Common", False, "Mini round frog plush"),
        ("Squishable Massive Ghost", "Squishable", "Massive Round", '38cm', 55, "Common", False, "White ghost massive round"),
        ("Squishable Massive Fox", "Squishable", "Massive Round", '38cm', 55, "Common", False, "Orange fox massive round"),
        ("Squishable Mini Avocado Toast", "Squishable", "Mini Series", '18cm', 22, "Common", False, "Avocado on toast mini plush"),
        ("Squishable Food Fight Taco vs Burrito", "Squishable", "Food Fight", 'Pair 15cm each', 30, "Common", False, "Taco and burrito pair set"),

        # ── San-X — More Rilakkuma & Sumikko (6) ────────────────────
        ("Rilakkuma Kiiroitori Chick", "San-X", "Rilakkuma", 'Medium 20cm', 25, "Common", False, "Yellow chick companion"),
        ("Rilakkuma 20th Anniversary", "San-X", "Rilakkuma", 'Large 40cm', 65, "Rare", False, "20th anniversary gold ribbon edition"),
        ("Sumikko Gurashi Penguin Real", "San-X", "Sumikko Gurashi", 'Medium 20cm', 28, "Common", False, "Penguin who questions its identity"),
        ("Sumikko Gurashi Tonkatsu", "San-X", "Sumikko Gurashi", 'Medium 20cm', 25, "Common", False, "Pork cutlet left uneaten"),
        ("Sumikko Gurashi Christmas Set", "San-X", "Sumikko Gurashi", 'Set 5x 12cm', 55, "Uncommon", True, "Christmas 2022 boxed set, retired"),
        ("Rilakkuma x Kaoru Netflix Plush", "San-X", "Rilakkuma", 'Medium 28cm', 50, "Uncommon", True, "Netflix anime collaboration, retired"),

        # ── Steiff — More Collector Bears (4) ────────────────────────
        ("Steiff Musical Bear", "Steiff", "Limited Edition", '28cm', 220, "Rare", False, "Wind-up music box mechanism inside"),
        ("Steiff Polar Bear Club Annual", "Steiff", "Annual Edition", '25cm', 150, "Uncommon", False, "Annual collector's club edition"),
        ("Steiff Cosy Friends Elephant", "Steiff", "Cosy Friends", '30cm', 65, "Common", False, "Soft plush elephant"),
        ("Steiff Original Teddy Caramel 1951 Replica", "Steiff", "Vintage Replica", '35cm', 420, "HTF", True, "1951 replica, limited numbered"),

        # ── Gund — More Designs (4) ──────────────────────────────────
        ("Gund Toothpick Bear", "Gund", "Toothpick", 'Medium 25cm', 22, "Common", False, "Slender bear design"),
        ("Gund Fuzzy Duck", "Gund", "Fuzzy", 'Medium 25cm', 20, "Common", False, "Fuzzy yellow duckling"),
        ("Gund Boo World's Cutest Dog", "Gund", "Boo", 'Medium 23cm', 25, "Common", False, "Internet-famous Pomeranian Boo"),
        ("Gund Moosetache Moose", "Gund", "Fun", 'Medium 28cm', 25, "Common", False, "Moose with mustache"),

        # ── Cabbage Patch Kids Vintage (6) ───────────────────────────
        ("Cabbage Patch Kid 1983 Xavier Roberts", "Cabbage Patch", "Vintage", '40cm', 150, "HTF", True, "1983 Xavier Roberts signed original"),
        ("Cabbage Patch Kid 1984 Bald Baby", "Cabbage Patch", "Vintage", '40cm', 80, "Rare", True, "1984 bald baby variant"),
        ("Cabbage Patch Kid 1985 Red Hair", "Cabbage Patch", "Vintage", '40cm', 70, "Rare", True, "1985 red yarn hair variant"),
        ("Cabbage Patch Kid World Traveler Spain", "Cabbage Patch", "World Traveler", '35cm', 90, "Rare", True, "World Traveler Spain, retired 1986"),
        ("Cabbage Patch Kid Preemie", "Cabbage Patch", "Vintage", '35cm', 60, "Uncommon", True, "Smaller preemie variant, 1985"),
        ("Cabbage Patch Kid Koosas", "Cabbage Patch", "Koosas", '35cm', 55, "Uncommon", True, "Animal Koosas companion, 1984"),

        # ── Jellycat — Even More Retired & Limited (12) ──────────────
        ("Jellycat Bumbly Bear", "Jellycat", "Bumbly", 'Medium 28cm', 35, "Common", False, "Tousled brown bear"),
        ("Jellycat Bumbly Elephant", "Jellycat", "Bumbly", 'Medium 28cm', 35, "Common", False, "Tousled grey elephant"),
        ("Jellycat Smudge Puppy", "Jellycat", "Smudge", 'Medium 30cm', 35, "Common", False, "Floppy spotted puppy"),
        ("Jellycat Merryday Cat Grey", "Jellycat", "Merryday", 'Medium 41cm', 45, "Uncommon", False, "Large grey cat"),
        ("Jellycat Tumbletuft Cow", "Jellycat", "Tumbletuft", 'Medium 20cm', 28, "Common", False, "Small black and white cow"),
        ("Jellycat Huggady Elephant", "Jellycat", "Huggady", 'Medium 22cm', 30, "Common", False, "Huggable grey elephant"),
        ("Jellycat Shooshu Bunny Soother", "Jellycat", "Soother", 'Medium 25cm', 22, "Common", False, "Baby soother with bunny"),
        ("Jellycat Noodoll Ricecake", "Jellycat", "Noodoll", 'Small 14cm', 18, "Common", False, "Japanese collaboration rice cake"),
        ("Jellycat Kitten Caboodle Grey", "Jellycat", "Kitten Caboodle", 'Medium 11cm', 16, "Common", False, "Small kitten in bed"),
        ("Jellycat Topsy Turvy Bunny", "Jellycat", "Topsy Turvy", 'Medium 28cm', 95, "Rare", True, "Reversible plush, retired 2016"),
        ("Jellycat Big Spottie Puppy", "Jellycat", "Big", 'Large 48cm', 75, "Rare", True, "Retired large spotted dog"),
        ("Jellycat Squiggles Puppy", "Jellycat", "Squiggles", 'Medium 30cm', 85, "Rare", True, "Retired 2017, wavy fur puppy"),

        # ── Squishmallows — More Store Exclusives (12) ───────────────
        ("Isis the Sea Cow", "Squishmallows", "Sea Life Squad", '12"', 30, "Common", False, "Teal manatee/sea cow"),
        ("Martine the Dragon", "Squishmallows", "Fantasy Squad", '12"', 35, "Uncommon", False, "Pink dragon"),
        ("Jaelyn the Purple Octopus", "Squishmallows", "Sea Life Squad", '12"', 30, "Uncommon", False, "Purple octopus"),
        ("Dante the Dog Day of Dead", "Squishmallows", "Halloween Squad", '12"', 45, "Uncommon", True, "Dia de los Muertos dog, retired"),
        ("Harrison the Dog", "Squishmallows", "Original Squad", '12"', 25, "Common", False, "Brown basset hound"),
        ("Sunny the Bee", "Squishmallows", "Original Squad", '12"', 30, "Common", False, "Yellow and black bee"),
        ("Baron the Bear Learning Squad", "Squishmallows", "Learning Squad", '12"', 35, "Uncommon", False, "Brown bear with glasses"),
        ("Kervena the Alien", "Squishmallows", "Space Squad", '12"', 40, "Uncommon", False, "Green alien, Target exclusive"),
        ("Cam the Cat Easter Basket", "Squishmallows", "Easter Squad", '8"', 20, "Common", False, "Easter variant calico cat"),
        ("Bop the Bunny Valentine", "Squishmallows", "Valentine Squad", '12"', 35, "Uncommon", False, "Pink bunny with hearts"),
        ("Meadow the Horse", "Squishmallows", "Original Squad", '12"', 25, "Common", False, "Brown horse plush"),
        ("Laura the Cat", "Squishmallows", "Original Squad", '12"', 30, "Common", False, "Black and white tuxedo cat"),

        # ── Squishmallows — Disney & Licensed (8) ────────────────────
        ("Stitch Squishmallow", "Squishmallows", "Disney", '14"', 35, "Uncommon", False, "Disney Stitch blue alien"),
        ("Baby Yoda Grogu Squishmallow", "Squishmallows", "Star Wars", '10"', 30, "Common", False, "The Child Star Wars"),
        ("Hello Kitty Squishmallow", "Squishmallows", "Sanrio", '14"', 35, "Uncommon", False, "Sanrio Hello Kitty collab"),
        ("Pikachu Squishmallow", "Squishmallows", "Pokémon", '14"', 40, "Uncommon", False, "Pokémon electric mouse"),
        ("Nightmare Before Christmas Jack Skellington Squish", "Squishmallows", "Disney", '12"', 35, "Uncommon", False, "Jack Skellington collab"),
        ("Mickey Mouse Squishmallow", "Squishmallows", "Disney", '14"', 30, "Common", False, "Classic Mickey Mouse"),
        ("Cinnamoroll Squishmallow", "Squishmallows", "Sanrio", '14"', 35, "Uncommon", False, "Sanrio Cinnamoroll collab"),
        ("My Melody Squishmallow", "Squishmallows", "Sanrio", '14"', 35, "Uncommon", False, "Sanrio My Melody collab"),

        # ── Pokemon Center — More Special (10) ───────────────────────
        ("Ditto Transform Eevee", "Pokémon Center", "Ditto Transform", 'Small 15cm', 20, "Common", False, "Ditto-face Eevee"),
        ("Ditto Transform Snorlax", "Pokémon Center", "Ditto Transform", 'Small 15cm', 20, "Common", False, "Ditto-face Snorlax"),
        ("Mewtwo Premium Plush", "Pokémon Center", "Premium Collection", '35cm', 55, "Uncommon", False, "Detailed premium quality Mewtwo"),
        ("Gardevoir Plush", "Pokémon Center", "Standard", 'Medium 25cm', 30, "Common", False, "Psychic/Fairy type plush"),
        ("Lapras Large Plush", "Pokémon Center", "Large Scale", '50cm', 95, "Rare", False, "Oversized water/ice Lapras"),
        ("Magikarp Full Body Plush", "Pokémon Center", "Special Edition", '60cm', 120, "Rare", True, "Oversized flopping Magikarp, retired JP exclusive"),
        ("Wooloo Plush", "Pokémon Center", "Sword & Shield", 'Medium 25cm', 25, "Common", False, "Sheep pokemon round plush"),
        ("Alcremie Plush Ruby Swirl", "Pokémon Center", "Sword & Shield", 'Medium 20cm', 28, "Common", False, "Cream pokemon decorative"),
        ("Piplup Holiday 2023", "Pokémon Center", "Holiday Collection", 'Medium 25cm', 40, "Uncommon", True, "Holiday scarf Piplup, retired"),
        ("Lechonk Plush", "Pokémon Center", "Scarlet & Violet", 'Medium 20cm', 25, "Common", False, "Gen 9 pig pokemon"),

        # ── More Anime Plush (10) ────────────────────────────────────
        ("Kirby Classic Plush", "Bandai", "Kirby", 'Medium 15cm', 20, "Common", False, "Pink puffball Nintendo character"),
        ("Kirby Star Allies Large", "Bandai", "Kirby", 'Large 35cm', 45, "Uncommon", False, "Oversized Star Allies Kirby"),
        ("Isabelle Animal Crossing Plush", "Bandai", "Animal Crossing", 'Medium 20cm', 25, "Common", False, "Isabelle Shizue yellow shih tzu"),
        ("Tom Nook Animal Crossing Plush", "Bandai", "Animal Crossing", 'Medium 20cm', 25, "Common", False, "Tom Nook raccoon shopkeeper"),
        ("Jujutsu Kaisen Gojo Satoru Plush", "Bandai", "Jujutsu Kaisen", 'Medium 20cm', 28, "Common", False, "Gojo with blindfold chibi"),
        ("Attack on Titan Colossal Titan Plush", "Bandai", "Attack on Titan", 'Medium 25cm', 30, "Uncommon", False, "Chibi colossal titan"),
        ("Dragon Ball Z Goku Plush", "Bandai", "Dragon Ball Z", 'Medium 25cm', 25, "Common", False, "Goku chibi orange gi"),
        ("Haikyuu Hinata Plush", "Bandai", "Haikyuu!!", 'Medium 20cm', 25, "Common", False, "Shoyo Hinata chibi volleyball"),
        ("Frieren Plush", "Bandai", "Frieren", 'Medium 20cm', 30, "Common", False, "Frieren elf mage chibi"),
        ("Bocchi the Rock Hitori Plush", "Bandai", "Bocchi the Rock!", 'Medium 20cm', 28, "Common", False, "Hitori Gotoh guitar girl"),

        # ── More Build-A-Bear (6) ───────────────────────────────────
        ("Vulpix Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 60, "Uncommon", False, "Pokémon fire fox collab"),
        ("Meowth Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 55, "Uncommon", True, "Pokémon collab, retired"),
        ("Paw Patrol Marshall Build-A-Bear", "Build-A-Bear", "Paw Patrol", 'Standard 35cm', 40, "Uncommon", False, "Nickelodeon licensed"),
        ("Peppa Pig Build-A-Bear", "Build-A-Bear", "Peppa Pig", 'Standard 35cm', 40, "Uncommon", False, "eOne licensed"),
        ("Deadpool Build-A-Bear", "Build-A-Bear", "Marvel", 'Standard 40cm', 55, "Uncommon", True, "Marvel licensed, retired"),
        ("Groot Build-A-Bear", "Build-A-Bear", "Marvel", 'Standard 40cm', 50, "Uncommon", False, "Marvel Guardians licensed"),

        # ── More TY Beanie Babies Classic (8) ────────────────────────
        ("Speedy the Turtle", "TY", "Beanie Babies", '20cm', 400, "HTF", True, "1993 original nine turtle"),
        ("Chocolate the Moose", "TY", "Beanie Babies", '20cm', 350, "HTF", True, "1993 original nine moose"),
        ("Pinchers the Lobster", "TY", "Beanie Babies", '20cm', 350, "HTF", True, "1993 original nine lobster"),
        ("Legs the Frog", "TY", "Beanie Babies", '20cm', 350, "HTF", True, "1993 original nine frog"),
        ("Flash the Dolphin", "TY", "Beanie Babies", '20cm', 350, "HTF", True, "1993 original nine dolphin"),
        ("Squealer the Pig", "TY", "Beanie Babies", '20cm', 350, "HTF", True, "1993 original nine pig"),
        ("Cubbie the Bear (Renamed Brownie)", "TY", "Beanie Babies", '20cm', 300, "HTF", True, "1993 original nine, renamed from Brownie"),
        ("Splash the Whale", "TY", "Beanie Babies", '20cm', 350, "HTF", True, "1993 original nine whale"),

        # ── More Vintage Plush (8) ──────────────────────────────────
        ("Cabbage Patch Kid Astronaut", "Cabbage Patch", "Vintage", '40cm', 120, "HTF", True, "1986 Young Astronaut series"),
        ("Strawberry Shortcake 1980 Original", "Kenner", "Vintage", '30cm', 100, "Rare", True, "1980 Kenner original ragdoll"),
        ("Rainbow Brite 1983 Original", "Mattel", "Vintage", '30cm', 90, "Rare", True, "1983 Mattel original"),
        ("Pound Puppies 1985 Original", "Tonka", "Vintage", '40cm', 60, "Uncommon", True, "1985 Tonka original adoption set"),
        ("Popples 1986 Original", "Mattel", "Vintage", '30cm', 70, "Rare", True, "1986 Mattel ball-folding plush"),
        ("ALF Plush 1986 Coleco", "Coleco", "Vintage", '45cm', 55, "Uncommon", True, "1986 Coleco talking ALF"),
        ("E.T. Extra-Terrestrial Plush 1982", "Kamar", "Vintage", '30cm', 80, "Rare", True, "1982 original movie plush"),
        ("Garfield Plush 1981 Dakin", "Dakin", "Vintage", '25cm', 50, "Uncommon", True, "1981 Dakin original Garfield"),

        # ── Jellycat — Even More Retired Collector Pieces (10) ────────
        ("Jellycat Truffles Sheep Large", "Jellycat", "Truffles", 'Large 38cm', 90, "Rare", True, "Retired 2017, woolly sheep"),
        ("Jellycat Sweetie Bunny", "Jellycat", "Sweetie", 'Medium 30cm', 32, "Common", False, "Candy-striped ear bunny"),
        ("Jellycat Dainty Kitten", "Jellycat", "Dainty", 'Medium 20cm', 28, "Common", False, "Small calico kitten"),
        ("Jellycat Lottie Bunny Party", "Jellycat", "Lottie", 'Medium 17cm', 22, "Common", False, "Bunny in party dress"),
        ("Jellycat Blossom Tulip Bunny", "Jellycat", "Blossom", 'Medium 31cm', 32, "Common", False, "Floral-ear tulip bunny"),
        ("Jellycat Fabian Frog Prince", "Jellycat", "Fabian", 'Medium 17cm', 25, "Common", False, "Frog with crown"),
        ("Jellycat Knitted Triceratops", "Jellycat", "Best Knits", 'Medium 20cm', 40, "Uncommon", False, "Knitted dinosaur"),
        ("Jellycat Nesting Chickies", "Jellycat", "Nesting", 'Set 3x 10cm', 30, "Common", False, "Three nesting chicks"),
        ("Jellycat Toasty Cutie Bunny", "Jellycat", "Toasty Cutie", 'Small 14cm', 18, "Common", False, "Small seasonal bunny"),
        ("Jellycat Roberto Frog", "Jellycat", "Roberto", 'Medium 27cm', 110, "HTF", True, "Retired 2016, extremely sought after"),

        # ── Squishmallows — More 2024/2025 Releases (10) ─────────────
        ("Wren the Butterfly 2024", "Squishmallows", "Spring Squad", '12"', 28, "Common", False, "Purple butterfly spring 2024"),
        ("Noemi the Narwhal", "Squishmallows", "Sea Life Squad", '12"', 25, "Common", False, "Pink narwhal"),
        ("Devita the Vampire", "Squishmallows", "Halloween Squad", '12"', 45, "Uncommon", False, "Purple vampire Halloween 2024"),
        ("Tangie the Tangerine", "Squishmallows", "Fruit Squad", '12"', 20, "Common", False, "Orange tangerine plush"),
        ("Magela the Cat", "Squishmallows", "Original Squad", '12"', 30, "Uncommon", False, "Calico cat with bow"),
        ("Puff the Pufferfish", "Squishmallows", "Sea Life Squad", '12"', 28, "Common", False, "Blue pufferfish"),
        ("Maxie the Mushroom Green", "Squishmallows", "Original Squad", '12"', 40, "Uncommon", False, "Green mushroom variant"),
        ("Andreina the Axolotl 2024", "Squishmallows", "Original Squad", '12"', 30, "Common", False, "Purple axolotl variant 2024"),
        ("Cayden the Tiger Shark", "Squishmallows", "Sea Life Squad", '12"', 25, "Common", False, "Grey tiger shark"),
        ("Yuri the Yeti", "Squishmallows", "Winter Squad", '12"', 35, "Uncommon", False, "White yeti with rainbow fur"),

        # ── More Sanrio Characters (6) ───────────────────────────────
        ("Hello Kitty Dear Daniel Pair", "Sanrio", "Hello Kitty", 'Pair 20cm each', 55, "Uncommon", False, "Hello Kitty and boyfriend pair"),
        ("Cinnamoroll Cafe Plush", "Sanrio", "Cinnamoroll", 'Medium 25cm', 30, "Common", False, "Cafe apron variant"),
        ("Kuromi Baku Form", "Sanrio", "Kuromi", 'Medium 25cm', 35, "Uncommon", False, "Dream-eating Baku form"),
        ("My Sweet Piano", "Sanrio", "My Sweet Piano", 'Medium 25cm', 28, "Common", False, "White lamb with pink bow"),
        ("Corocorokuririn Hamster", "Sanrio", "Corocorokuririn", 'Medium 18cm', 35, "Uncommon", True, "Retired hamster character"),
        ("Wish Me Mell Plush", "Sanrio", "Wish Me Mell", 'Medium 20cm', 30, "Common", False, "Fairy rabbit character"),

        # ── More Disney Plush (6) ────────────────────────────────────
        ("Gelatoni Cat Tokyo Disney", "Disney", "Duffy & Friends", 'Medium 30cm', 55, "Uncommon", False, "Tokyo Disney Sea painter cat"),
        ("CookieAnn Dog", "Disney", "Duffy & Friends", 'Medium 30cm', 55, "Uncommon", False, "Tokyo Disney Sea baker dog"),
        ("Baby Moana nuiMOs", "Disney", "nuiMOs", 'Small 16cm', 30, "Common", False, "Poseable Moana plush"),
        ("Winnie the Pooh Classic Large", "Disney", "Winnie the Pooh", 'Large 45cm', 45, "Uncommon", False, "Classic Pooh oversized"),
        ("Baymax Big Hero 6 Plush", "Disney", "Big Hero 6", 'Medium 30cm', 35, "Common", False, "Squishy healthcare robot"),
        ("Tsum Tsum Mickey Mouse", "Disney", "Tsum Tsum", 'Small 10cm', 10, "Common", False, "Stackable cylinder Mickey"),

        # ── More Modern Licensed (8) ─────────────────────────────────
        ("Kirby Waddle Dee Plush", "Bandai", "Kirby", 'Medium 18cm', 20, "Common", False, "Orange Waddle Dee companion"),
        ("Meta Knight Kirby Plush", "Bandai", "Kirby", 'Medium 18cm', 22, "Common", False, "Dark knight rival plush"),
        ("Sumikko x Jellycat Style Tokage", "San-X", "Sumikko Gurashi", 'Medium 22cm', 32, "Common", False, "Premium quality Tokage"),
        ("Molang Bunny Plush White", "Molang", "Classic", 'Medium 25cm', 25, "Common", False, "Korean round bunny character"),
        ("BT21 Chimmy Plush", "Line Friends", "BT21", 'Medium 25cm', 28, "Common", False, "BTS x Line Friends yellow puppy"),
        ("BT21 Tata Plush", "Line Friends", "BT21", 'Medium 25cm', 28, "Common", False, "BTS x Line Friends heart alien"),
        ("BT21 Cooky Plush", "Line Friends", "BT21", 'Medium 25cm', 28, "Common", False, "BTS x Line Friends pink rabbit"),
        ("BT21 Koya Plush", "Line Friends", "BT21", 'Medium 25cm', 28, "Common", False, "BTS x Line Friends blue koala"),

        # ── ROUND 7 — 45+ new items to exceed 507 ──

        # ── Squishmallows — More HTF & Size Variants (10) ──────────────
        ("Brina the Bigfoot Pink", "Squishmallows", "Original Squad", '16"', 55, "HTF", True, "Pink bigfoot, discontinued 2022"),
        ("Joelle the Bigfoot Purple", "Squishmallows", "Original Squad", '12"', 40, "Uncommon", False, "Purple bigfoot with bow"),
        ("Avery the Mallard Duck", "Squishmallows", "Original Squad", '12"', 30, "Common", False, "Green mallard duck"),
        ("Gordon the Shark", "Squishmallows", "Sea Life Squad", '16"', 35, "Common", False, "Grey shark with grin"),
        ("Omar the Bear", "Squishmallows", "Original Squad", '12"', 25, "Common", False, "Brown bear with scarf"),
        ("Heather the Dragonfly", "Squishmallows", "Original Squad", '12"', 30, "Common", False, "Purple dragonfly"),
        ("Luther the Shark Tie-Dye", "Squishmallows", "Tie-Dye Squad", '12"', 40, "Uncommon", False, "Tie-dye shark exclusive"),
        ("Orin the Orange Worm", "Squishmallows", "Original Squad", '12"', 25, "Common", False, "Orange worm caterpillar"),
        ("Aziza the Strawberry", "Squishmallows", "Fruit Squad", '12"', 28, "Common", False, "Pink strawberry with face"),
        ("Ricky the Clownfish", "Squishmallows", "Sea Life Squad", '12"', 25, "Common", False, "Orange clownfish"),

        # ── Jellycat — New 2024/2025 Releases (10) ─────────────────────
        ("Jellycat Amuseable Sourdough", "Jellycat", "Amuseable", 'Medium 27cm', 30, "Common", False, "Bread loaf with scored top"),
        ("Jellycat Amuseable Croissant", "Jellycat", "Amuseable", 'Medium 20cm', 28, "Common", False, "Golden flaky croissant"),
        ("Jellycat Amuseable Pretzel", "Jellycat", "Amuseable", 'Medium 18cm', 25, "Common", False, "Twisted pretzel shape"),
        ("Jellycat Vivacious Vegetable Leek", "Jellycat", "Vivacious Vegetable", 'Medium 22cm', 28, "Common", False, "Green leek with legs"),
        ("Jellycat Vivacious Vegetable Mushroom", "Jellycat", "Vivacious Vegetable", 'Medium 17cm', 25, "Common", False, "Brown capped mushroom"),
        ("Jellycat Bashful Blush Bunny Huge", "Jellycat", "Bashful", 'Huge 51cm', 75, "Uncommon", False, "Oversized blush pink bunny"),
        ("Jellycat Bashful Luxe Willow Bunny", "Jellycat", "Bashful Luxe", 'Medium 31cm', 45, "Uncommon", False, "Premium green tonal bunny"),
        ("Jellycat Cordy Roy Fox", "Jellycat", "Cordy Roy", 'Medium 26cm', 85, "Rare", True, "Retired 2018, corduroy fox"),
        ("Jellycat Odyssey Octopus Large", "Jellycat", "Odyssey", 'Large 49cm', 55, "Uncommon", False, "Long tentacle octopus"),
        ("Jellycat Amuseable Sports Cricket Ball", "Jellycat", "Amuseable Sports", 'Small 9cm', 18, "Common", False, "Red cricket ball with legs"),

        # ── Build-A-Bear — More Licensed (5) ──────────────────────────
        ("Snorlax Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 65, "Uncommon", False, "Pokémon sleeping giant collab"),
        ("Toothless Build-A-Bear", "Build-A-Bear", "How to Train Your Dragon", 'Standard 40cm', 55, "Uncommon", True, "DreamWorks Night Fury, retired"),
        ("Sonic the Hedgehog Build-A-Bear", "Build-A-Bear", "Sonic", 'Standard 40cm', 50, "Uncommon", False, "SEGA licensed blue hedgehog"),
        ("Spider-Man Build-A-Bear", "Build-A-Bear", "Marvel", 'Standard 40cm', 50, "Uncommon", False, "Marvel web-slinger licensed"),
        ("Stitch Build-A-Bear", "Build-A-Bear", "Disney", 'Standard 40cm', 55, "Uncommon", False, "Disney experiment 626"),

        # ── Pokemon Center — More Exclusives (5) ──────────────────────
        ("Sylveon Plush", "Pokémon Center", "Standard", 'Medium 25cm', 30, "Common", False, "Fairy eeveelution ribbon plush"),
        ("Mimikyu Plush", "Pokémon Center", "Standard", 'Medium 25cm', 32, "Common", False, "Ghost disguised as Pikachu"),
        ("Lucario Plush", "Pokémon Center", "Standard", 'Medium 30cm', 35, "Common", False, "Aura pokemon fighting/steel"),
        ("Rayquaza Large Plush", "Pokémon Center", "Large Scale", '120cm', 180, "Rare", True, "Oversized legendary sky dragon, retired"),
        ("Fuecoco Plush", "Pokémon Center", "Scarlet & Violet", 'Medium 20cm', 25, "Common", False, "Gen 9 fire croc starter"),

        # ── Sanrio — More Characters (5) ──────────────────────────────
        ("Pochacco Classic Plush", "Sanrio", "Pochacco", 'Medium 25cm', 28, "Common", False, "Athletic white dog character"),
        ("Tuxedosam Classic Plush", "Sanrio", "Tuxedosam", 'Medium 22cm', 28, "Common", False, "Penguin in tuxedo from 1978"),
        ("Little Twin Stars Kiki & Lala Set", "Sanrio", "Little Twin Stars", 'Pair 20cm each', 50, "Uncommon", False, "Twin star siblings pair set"),
        ("Badtz-Maru Large Plush", "Sanrio", "Badtz-Maru", 'Large 35cm', 35, "Common", False, "Mischievous penguin character"),
        ("Hello Kitty 50th Anniversary", "Sanrio", "Hello Kitty", 'Large 40cm', 85, "Rare", False, "2024 golden 50th anniversary edition"),

        # ── More Disney Plush (5) ─────────────────────────────────────
        ("StellaLou Rabbit", "Disney", "Duffy & Friends", 'Medium 30cm', 60, "Uncommon", False, "Tokyo Disney Sea ballet rabbit"),
        ("Spirit Jersey Stitch Plush", "Disney", "Spirit Jersey", 'Medium 30cm', 45, "Uncommon", False, "Stitch in park spirit jersey"),
        ("Figment Plush Large", "Disney", "EPCOT", 'Large 45cm', 50, "Uncommon", False, "EPCOT purple dragon mascot"),
        ("Orange Bird Plush", "Disney", "Magic Kingdom", 'Medium 25cm', 40, "Uncommon", True, "Adventureland citrus bird, retired"),
        ("Pascal Tangled Plush", "Disney", "Tangled", 'Small 18cm', 20, "Common", False, "Color-changing chameleon"),

        # ── More Ghibli Plush (5) ─────────────────────────────────────
        ("Totoro Grey Large", "Ghibli", "My Neighbor Totoro", 'Large 40cm', 55, "Uncommon", False, "Grey Totoro oversized forest spirit"),
        ("Cat Bus Plush", "Ghibli", "My Neighbor Totoro", 'Medium 30cm', 45, "Uncommon", False, "12-legged cat bus plush"),
        ("Jiji Cat Kiki's Delivery", "Ghibli", "Kiki's Delivery Service", 'Medium 25cm', 35, "Common", False, "Black cat companion Jiji"),
        ("No-Face Kaonashi Plush", "Ghibli", "Spirited Away", 'Medium 25cm', 40, "Uncommon", False, "Masked spirit No-Face"),
        ("Calcifer Flame Plush", "Ghibli", "Howl's Moving Castle", 'Small 15cm', 30, "Common", False, "Fire demon Calcifer"),
    ]

    # ── Batch: Steiff, Gund, Aurora, Jellycat, Kapibarasan, Rilakkuma (50 items) ──
    items += _additional_plush_2025_expansion()

    catalog = []
    for name, brand, series, size, price, rarity, is_retired, notes in items:
        catalog.append({
            "name": name,
            "brand": brand,
            "series": series,
            "size": size,
            "price_eur": price,
            "rarity": rarity,
            "is_retired": is_retired,
            "notes": notes,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    series = item["series"]
    name = item["name"]
    size = item["size"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{series}-{name}"),
        title=f"{name} ({size})",
        set_code=slugify(series),
        brand=brand,
        rarity=item["rarity"],
        notes=f"{brand} | {series}" + (f" | {item['notes']}" if item["notes"] else ""),
        attributes_json={
            "brand": brand,
            "series": series,
            "size": size,
            "is_retired": item["is_retired"],
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    rarity = item["rarity"]
    brand = item["brand"]

    brand_score = _BRAND_SCORE.get(brand, 0.6)

    return PriceObservation(
        features={
            "condition_score": 0.85,           # most plush NWT (New With Tags)
            "rarity_score": _plush_rarity_score(rarity),
            "brand_score": brand_score,
            "is_retired": 1.0 if item["is_retired"] else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Plush Collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Plush Collectibles Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()

    all_items = [item_to_catalog_item(i) for i in catalog]
    all_observations = [item_to_price_observation(i) for i in catalog]

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== Plush Collectibles Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
