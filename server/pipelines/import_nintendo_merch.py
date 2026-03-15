"""
Import Nintendo & Pokemon merchandise data (non-cards).

Layer 1 (Catalog):  Curated plush, amiibo, figures, exclusives → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of 80+ items across all major Nintendo franchises
- Pokemon Center exclusives (plush, figures, TCG accessories)
- Amiibo (common + rare/out-of-print: Gold Mario, Qbby, Mega Yarn Yoshi, etc.)
- Zelda collectibles (Master Sword replicas, Hyrule Historia, steelbooks)
- Mario merchandise (Super Nintendo World, movie merch)
- Animal Crossing, Splatoon, Kirby, Fire Emblem, Metroid collectibles
- Club Nintendo & My Nintendo physical rewards
- Nintendo Store Tokyo/NY exclusives

Usage:
    python -m pipelines.import_nintendo_merch [--dry-run]
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
    RARITY_SCORE_MAP,
    logger,
    close_http_client,
)

CATEGORY = "nintendo_merch"


def _additional_nintendo_2025_expansion() -> list[tuple]:
    """55 more items: store exclusives, movie merch, OLED editions, new franchise items."""
    return [
        # ── Nintendo Store Exclusives (Tokyo/Osaka/Kyoto) ──────────────────
        ("Mario", "Store Exclusive", "Nintendo Kyoto Store Grand Opening Mario Pin Set", "Nintendo Store Kyoto", "high", 85),
        ("Zelda", "Store Exclusive", "Nintendo Tokyo Hylian Shield Wall Art", "Nintendo Store Tokyo", "high", 95),
        ("Kirby", "Store Exclusive", "Nintendo Osaka Kirby Dotonbori Plush", "Nintendo Store Osaka", "mid", 48),
        ("Splatoon", "Store Exclusive", "Nintendo Tokyo Splatoon 3 Inkling Figure Set", "Nintendo Store Tokyo", "mid", 55),
        ("Animal Crossing", "Store Exclusive", "Nintendo Kyoto Isabelle Maiko Plush", "Nintendo Store Kyoto", "high", 75),
        ("Mario", "Store Exclusive", "Nintendo Tokyo Mario Kabuki Figurine", "Nintendo Store Tokyo", "high", 90),
        ("Pokemon", "Store Exclusive", "Nintendo Osaka Pikachu Takoyaki Keychain Set", "Nintendo Store Osaka", "mid", 35),
        ("Zelda", "Store Exclusive", "Nintendo Kyoto Master Sword Letter Opener", "Nintendo Store Kyoto", "mid", 42),
        ("Kirby", "Store Exclusive", "Nintendo Tokyo Kirby Cafe Parfait Plush", "Nintendo Store Tokyo", "mid", 40),
        ("Mario", "Store Exclusive", "Nintendo Osaka Super Mario Power-Up Mug Set", "Nintendo Store Osaka", "mid", 38),

        # ── Super Mario Bros. Movie Merchandise ────────────────────────────
        ("Mario", "Movie Merch", "Super Mario Bros. Movie Mario 10in Plush", "", "mid", 32),
        ("Mario", "Movie Merch", "Super Mario Bros. Movie Luigi 10in Plush", "", "mid", 32),
        ("Mario", "Movie Merch", "Super Mario Bros. Movie Princess Peach 12in Plush", "", "mid", 35),
        ("Mario", "Movie Merch", "Super Mario Bros. Movie Bowser Fire Breathing Figure", "", "mid", 45),
        ("Mario", "Movie Merch", "Super Mario Bros. Movie Toad Plush 8in", "", "standard", 22),
        ("Mario", "Movie Merch", "Super Mario Bros. Movie DK Barrel Playset", "", "mid", 55),
        ("Mario", "Movie Merch", "Super Mario Bros. Movie Kart Racers Set", "", "mid", 48),
        ("Mario", "Movie Merch", "Super Mario Bros. Movie Rainbow Road Track Set", "", "high", 85),
        ("Mario", "Movie Merch", "Super Mario Bros. Movie Luma Star Plush", "", "standard", 18),

        # ── Pikmin Bloom Merchandise ───────────────────────────────────────
        ("Pikmin", "Plush", "Pikmin Bloom Red Pikmin Flower Plush", "", "standard", 20),
        ("Pikmin", "Plush", "Pikmin Bloom Blue Pikmin Plush", "", "standard", 20),
        ("Pikmin", "Plush", "Pikmin Bloom Yellow Pikmin Plush", "", "standard", 20),
        ("Pikmin", "Plush", "Pikmin Bloom Purple Pikmin Plush", "", "standard", 22),
        ("Pikmin", "Plush", "Pikmin Bloom White Pikmin Plush", "", "standard", 22),
        ("Pikmin", "Plush", "Pikmin Bloom Rock Pikmin Plush", "", "standard", 22),
        ("Pikmin", "Figure", "Pikmin Bloom Ice Pikmin Figure Set", "", "mid", 35),
        ("Pikmin", "Figure", "Pikmin 4 Oatchi & Red Pikmin Figure", "", "mid", 38),

        # ── Splatoon 3 Amiibo (Big Run & Side Order) ──────────────────────
        ("Splatoon", "Amiibo", "Splatoon 3 Big Run Inkling (Yellow)", "", "mid", 25),
        ("Splatoon", "Amiibo", "Splatoon 3 Big Run Octoling (Teal)", "", "mid", 25),
        ("Splatoon", "Amiibo", "Splatoon 3 Side Order Agent 8 (Pearlescent)", "", "mid", 30),
        ("Splatoon", "Amiibo", "Splatoon 3 Shiver Amiibo", "", "mid", 28),
        ("Splatoon", "Amiibo", "Splatoon 3 Frye Amiibo", "", "mid", 28),
        ("Splatoon", "Amiibo", "Splatoon 3 Big Man Amiibo", "", "mid", 30),

        # ── Fire Emblem Engage Merchandise ─────────────────────────────────
        ("Fire Emblem", "Figure", "Fire Emblem Engage Alear (Divine Dragon) Figure", "", "mid", 55),
        ("Fire Emblem", "Figure", "Fire Emblem Engage Veyle Figure", "", "mid", 50),
        ("Fire Emblem", "Amiibo", "Fire Emblem Engage Alear Amiibo", "", "mid", 35),
        ("Fire Emblem", "Plush", "Fire Emblem Engage Sommie Plush", "", "mid", 38),
        ("Fire Emblem", "Book", "The Art of Fire Emblem Engage", "", "mid", 42),

        # ── Xenoblade Chronicles 3 Collector Items ─────────────────────────
        ("Xenoblade", "Figure", "Xenoblade Chronicles 3 Noah Figure", "", "mid", 55),
        ("Xenoblade", "Figure", "Xenoblade Chronicles 3 Mio Figure", "", "mid", 55),
        ("Xenoblade", "Plush", "Xenoblade Chronicles 3 Riku & Manana Plush Set", "", "mid", 48),
        ("Xenoblade", "Amiibo", "Xenoblade Chronicles 3 Noah Amiibo", "", "mid", 30),
        ("Xenoblade", "Amiibo", "Xenoblade Chronicles 3 Mio Amiibo", "", "mid", 30),
        ("Xenoblade", "Soundtrack", "Xenoblade Chronicles 3 Original Soundtrack (8-CD Box)", "", "high", 120),

        # ── Nintendo Switch OLED Special Editions ──────────────────────────
        ("Splatoon", "Console", "Nintendo Switch OLED Splatoon 3 Edition", "", "high", 380),
        ("Zelda", "Console", "Nintendo Switch OLED Zelda: Tears of the Kingdom Edition", "", "high", 400),
        ("Pokemon", "Console", "Nintendo Switch OLED Pokemon Scarlet & Violet Edition", "", "high", 390),
        ("Zelda", "Controller", "Nintendo Switch Pro Controller Zelda TOTK Edition", "", "mid", 75),
        ("Splatoon", "Controller", "Nintendo Switch Pro Controller Splatoon 3 Edition", "", "mid", 70),
        ("Pokemon", "Controller", "Nintendo Switch Pro Controller Pokemon SV Edition", "", "mid", 70),
        ("Mario", "Console", "Nintendo Switch OLED Mario Red Edition", "", "high", 350),
        ("Zelda", "Carrying Case", "Nintendo Switch TOTK Sheikah Eye Carrying Case", "", "mid", 35),
        ("Pokemon", "Carrying Case", "Nintendo Switch SV Koraidon & Miraidon Case", "", "mid", 32),
    ]


def get_curated_catalog() -> list[dict]:
    """Curated Nintendo / Pokemon merchandise catalog (500+ items).

    Covers all major franchises: Pokemon, Mario, Zelda, Kirby, Splatoon,
    Animal Crossing, Fire Emblem, Metroid, Xenoblade, Pikmin, Star Fox,
    F-Zero, EarthBound, Monster Hunter, Dark Souls.  Includes complete
    amiibo collection (Smash Bros, Super Mario, Animal Crossing, Zelda
    30th, Monster Hunter, Splatoon, Shovel Knight series), Pokemon Center
    exclusives (plush, figures, costume Pikachu, regional exclusives, TCG
    accessories), Club Nintendo / My Nintendo physical rewards, Nintendo
    Store Tokyo/NY/Osaka/Kyoto exclusives, limited event items, special
    edition consoles & hardware, themed controllers, carrying cases, art
    books, soundtracks, and First 4 Figures premium statues.
    """

    # Format: (franchise, product_type, name, exclusive, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (80-200), mid (30-80), standard (<30)

    merch = [
        # ── Pokemon Center Plush - Standard ──────────────────────────────
        ("Pokemon", "Plush", "Pikachu Sitting Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Eevee Sitting Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Charizard Plush 12in", "", "standard", 28),
        ("Pokemon", "Plush", "Gengar Plush 8in", "", "standard", 20),
        ("Pokemon", "Plush", "Snorlax Plush 12in", "", "standard", 25),

        # ── Pokemon Center Plush - Exclusive / Limited ────────────────────
        ("Pokemon", "Plush", "Pikachu Halloween Costume Plush", "Pokemon Center", "mid", 45),
        ("Pokemon", "Plush", "Mimikyu Giant Plush 24in", "Pokemon Center", "high", 120),
        ("Pokemon", "Plush", "Snorlax Bean Bag Chair 60in", "Pokemon Center", "grail", 280),
        ("Pokemon", "Plush", "Life-Size Arcanine Plush", "Pokemon Center JP", "grail", 300),
        ("Pokemon", "Plush", "Ditto Transform Pikachu Plush", "Pokemon Center", "mid", 35),
        ("Pokemon", "Plush", "Eeveelution Collection Box Set", "Pokemon Center", "high", 180),
        ("Pokemon", "Plush", "Sitting Cuties Full Kanto Set", "Pokemon Center", "grail", 250),
        ("Pokemon", "Plush", "Scarlet & Violet Starter Set", "Pokemon Center", "mid", 50),

        # ── Pokemon Center Exclusive Figures ──────────────────────────────
        ("Pokemon", "Figure", "Charizard Premium Figure", "Pokemon Center", "mid", 65),
        ("Pokemon", "Figure", "Mewtwo Gallery Figure DX", "Pokemon Center", "mid", 55),
        ("Pokemon", "Figure", "Pikachu VMAX Premium Figure", "Pokemon Center", "mid", 45),
        ("Pokemon", "Figure", "Rayquaza Gallery Figure", "Pokemon Center", "mid", 60),
        ("Pokemon", "Figure", "Legendary Birds Articuno Set", "Pokemon Center", "high", 80),

        # ── Pokemon Center TCG Accessories ────────────────────────────────
        ("Pokemon", "TCG Accessory", "Pikachu Leather Deck Box", "Pokemon Center", "mid", 38),
        ("Pokemon", "TCG Accessory", "Eevee Evolution Premium Sleeves 65ct", "Pokemon Center", "standard", 12),
        ("Pokemon", "TCG Accessory", "Charizard Playmat Premium", "Pokemon Center", "mid", 32),
        ("Pokemon", "TCG Accessory", "Ultra Ball Flip Deck Box", "Pokemon Center", "standard", 22),
        ("Pokemon", "TCG Accessory", "Scarlet & Violet Elite Trainer Box Plus", "Pokemon Center", "mid", 55),

        # ── Amiibo - Common ───────────────────────────────────────────────
        ("Mario", "Amiibo", "Mario (Super Smash Bros.)", "", "standard", 15),
        ("Zelda", "Amiibo", "Link (Breath of the Wild)", "", "standard", 18),
        ("Pokemon", "Amiibo", "Pikachu (Super Smash Bros.)", "", "standard", 15),
        ("Splatoon", "Amiibo", "Inkling Girl (Splatoon 3)", "", "standard", 14),
        ("Kirby", "Amiibo", "Kirby (Kirby Series)", "", "standard", 16),

        # ── Amiibo - Rare / Out of Print ──────────────────────────────────
        ("Mario", "Amiibo", "Gold Mario", "Walmart Exclusive", "high", 80),
        ("Mario", "Amiibo", "Silver Mario", "Exclusive", "high", 90),
        ("Animal Crossing", "Amiibo", "Villager (1st Print)", "", "high", 100),
        ("Zelda", "Amiibo", "Guardian (Breath of the Wild)", "", "high", 90),
        ("Splatoon", "Amiibo", "Callie & Marie 2-Pack", "", "high", 120),
        ("Zelda", "Amiibo", "Link (Skyward Sword)", "", "mid", 50),
        ("Kirby", "Amiibo", "Meta Knight", "Best Buy Exclusive", "high", 80),
        ("Pokemon", "Amiibo", "Mewtwo (Super Smash Bros.)", "", "mid", 45),
        ("Metroid", "Amiibo", "Samus (Metroid Dread)", "", "mid", 40),
        ("Zelda", "Amiibo", "Zelda & Loftwing", "", "high", 85),
        ("Zelda", "Amiibo", "Link (Tears of the Kingdom)", "", "mid", 35),
        ("Mario", "Amiibo", "Qbby (BoxBoy!)", "JP Exclusive", "grail", 250),
        ("Mario", "Amiibo", "Mega Yarn Yoshi", "Toys R Us Exclusive", "grail", 220),
        ("Monster Hunter", "Amiibo", "Navirou (Monster Hunter Stories)", "JP Exclusive", "high", 150),
        ("Dark Souls", "Amiibo", "Solaire of Astora", "", "high", 110),
        ("Monster Hunter", "Amiibo", "Rathalos & Rider (Monster Hunter Stories)", "JP Exclusive", "high", 130),

        # ── Zelda Collectibles ────────────────────────────────────────────
        ("Zelda", "Merch", "Master Sword Replica Light", "Nintendo Store", "mid", 55),
        ("Zelda", "Replica", "Master Sword Full-Size Metal Replica", "", "high", 180),
        ("Zelda", "Replica", "Hylian Shield Replica Wall Mount", "", "high", 160),
        ("Zelda", "Book", "Hyrule Historia Collector's Edition", "", "high", 85),
        ("Zelda", "Book", "Art & Artifacts Limited Edition", "", "high", 95),
        ("Zelda", "Book", "Creating a Champion Hero's Edition", "", "mid", 70),
        ("Zelda", "Steelbook", "Tears of the Kingdom Steelbook", "Nintendo Store", "mid", 45),
        ("Zelda", "Steelbook", "Breath of the Wild Steelbook", "Limited Edition", "mid", 60),
        ("Zelda", "Steelbook", "Skyward Sword HD Steelbook", "Nintendo Store", "mid", 40),
        ("Zelda", "Merch", "Tears of the Kingdom Collector Pin Set", "Nintendo Store", "mid", 50),

        # ── Mario Merchandise ─────────────────────────────────────────────
        ("Mario", "Merch", "Super Mario Odyssey Coin Set", "Nintendo Store", "mid", 40),
        ("Mario", "Merch", "Mario Red Joy-Con Set", "Nintendo Store", "mid", 65),
        ("Mario", "Merch", "Super Nintendo World Mario Hat", "Universal Studios JP", "mid", 60),
        ("Mario", "Merch", "Super Nintendo World Power-Up Band Mario", "Universal Studios", "mid", 42),
        ("Mario", "Merch", "Super Nintendo World Bowser Popcorn Bucket", "Universal Studios JP", "mid", 55),
        ("Mario", "Figure", "Super Mario Movie 5in Mario Figure", "", "standard", 18),
        ("Mario", "Figure", "Super Mario Movie 7in DK Figure", "", "standard", 22),
        ("Mario", "Figure", "Super Mario Movie Peach Castle Playset", "", "mid", 45),
        ("Mario", "Merch", "Mario Kart Trophy Replica", "Nintendo Store", "mid", 75),

        # ── Animal Crossing Merchandise ───────────────────────────────────
        ("Animal Crossing", "Merch", "Tom Nook Ceramic Mug Set", "Nintendo Store", "standard", 25),
        ("Animal Crossing", "Figure", "K.K. Slider Totakeke Figure", "Nintendo Store", "mid", 48),
        ("Animal Crossing", "Plush", "Isabelle Plush 10in", "", "standard", 22),
        ("Animal Crossing", "Plush", "Tom Nook Plush 12in", "", "standard", 24),
        ("Animal Crossing", "Merch", "Animal Crossing New Horizons Journal & Pen Set", "Nintendo Store", "standard", 28),

        # ── Splatoon Merchandise ──────────────────────────────────────────
        ("Splatoon", "Merch", "Splatoon 3 Tableturf Battle Cards", "Nintendo Store", "mid", 30),
        ("Splatoon", "Plush", "Splatoon 3 Smallfry Plush", "", "standard", 20),
        ("Splatoon", "Merch", "Splatoon Squid Sisters Concert Poster Set", "Nintendo JP", "mid", 35),
        ("Splatoon", "Figure", "Splatoon 3 Shiver Figma", "", "mid", 65),

        # ── Kirby Merchandise ─────────────────────────────────────────────
        ("Kirby", "Merch", "Kirby Cafe Menu Plate Set", "Nintendo Store JP", "high", 85),
        ("Kirby", "Plush", "Kirby 30th Anniversary Plush Set", "Nintendo Store JP", "mid", 55),
        ("Kirby", "Plush", "Waddle Dee Plush 8in", "", "standard", 18),
        ("Kirby", "Figure", "Kirby Nendoroid 30th Anniversary", "", "mid", 50),
        ("Kirby", "Merch", "Kirby Cafe Ceramic Mug & Saucer", "Kirby Cafe JP", "mid", 38),

        # ── Fire Emblem Figures ───────────────────────────────────────────
        ("Fire Emblem", "Figure", "Marth Figma", "", "mid", 65),
        ("Fire Emblem", "Figure", "Byleth (Male) 1/7 Scale Figure", "", "high", 140),
        ("Fire Emblem", "Figure", "Edelgard von Hresvelg 1/7 Scale Figure", "", "high", 150),
        ("Fire Emblem", "Figure", "Lucina Figma", "", "mid", 70),
        ("Fire Emblem", "Amiibo", "Corrin Player 2 (Female)", "Exclusive", "high", 95),

        # ── Metroid Collectibles ──────────────────────────────────────────
        ("Metroid", "Figure", "Samus Aran Varia Suit Figma", "", "high", 90),
        ("Metroid", "Replica", "Metroid Dread Special Edition Artbook + Steelbook", "", "mid", 75),
        ("Metroid", "Figure", "Metroid Prime Samus 1/4 Scale Statue", "First 4 Figures", "grail", 450),
        ("Metroid", "Merch", "Baby Metroid Prop Replica Light", "", "mid", 55),

        # ── Club Nintendo Rewards (Retired) ───────────────────────────────
        ("Mario", "Club Nintendo", "Club Nintendo Gold Nunchuk", "Club Nintendo", "grail", 350),
        ("Zelda", "Club Nintendo", "Zelda 25th Anniversary Poster Set", "Club Nintendo", "high", 90),
        ("Mario", "Club Nintendo", "Super Mario Galaxy Original Soundtrack", "Club Nintendo", "high", 85),
        ("Mario", "Club Nintendo", "Hanafuda Playing Cards Mario Edition", "Club Nintendo", "mid", 60),
        ("Zelda", "Club Nintendo", "Majora's Mask Soundtrack CD", "Club Nintendo", "high", 100),
        ("Mario", "Club Nintendo", "Club Nintendo Platinum Playing Cards", "Club Nintendo", "mid", 45),

        # ── My Nintendo Physical Rewards ──────────────────────────────────
        ("Mario", "My Nintendo", "My Nintendo Mario Pin Set", "My Nintendo", "mid", 35),
        ("Zelda", "My Nintendo", "My Nintendo Zelda TOTK Poster Set", "My Nintendo", "mid", 30),
        ("Animal Crossing", "My Nintendo", "My Nintendo AC Tote Bag", "My Nintendo", "standard", 25),
        ("Splatoon", "My Nintendo", "My Nintendo Splatoon 3 Sticker Sheet", "My Nintendo", "standard", 15),

        # ── Nintendo Store Tokyo / NY Exclusives ──────────────────────────
        ("Mario", "Store Exclusive", "Nintendo Tokyo Grand Opening Mario Tee", "Nintendo Store Tokyo", "high", 80),
        ("Zelda", "Store Exclusive", "Nintendo NY Hyrule Crest Hoodie", "Nintendo Store NY", "mid", 65),
        ("Pokemon", "Store Exclusive", "Nintendo Tokyo Pikachu Mascot Plush", "Nintendo Store Tokyo", "mid", 40),
        ("Mario", "Store Exclusive", "Nintendo Store Tokyo 1st Anniversary Pin Badge Set", "Nintendo Store Tokyo", "high", 95),
        ("Kirby", "Store Exclusive", "Nintendo Store Tokyo Kirby Bento Box Set", "Nintendo Store Tokyo", "mid", 48),

        # ── Limited Event Items ───────────────────────────────────────────
        ("Pokemon", "Event", "Worlds 2023 Pikachu Plush", "Pokemon Worlds", "high", 150),
        ("Pokemon", "Event", "Pokemon Center 25th Anniversary Box", "Pokemon Center", "grail", 250),
        ("Pokemon", "Event", "GO Fest 2023 Exclusive Plush", "Pokemon GO Fest", "high", 100),
        ("Splatoon", "Event", "Splatoon Koshien Trophy Replica", "Nintendo JP", "grail", 200),

        # ── Amiibo - Zelda Tears of the Kingdom Series ──────────────────
        ("Zelda", "Amiibo", "Zelda (Tears of the Kingdom)", "", "mid", 30),
        ("Zelda", "Amiibo", "Ganondorf (Tears of the Kingdom)", "", "mid", 35),

        # ── Amiibo - Splatoon 3 Series ──────────────────────────────────
        ("Splatoon", "Amiibo", "Shiver (Splatoon 3)", "", "standard", 16),
        ("Splatoon", "Amiibo", "Frye (Splatoon 3)", "", "standard", 16),
        ("Splatoon", "Amiibo", "Big Man (Splatoon 3)", "", "standard", 18),
        ("Splatoon", "Amiibo", "Octoling Girl (Splatoon 3)", "", "standard", 16),

        # ── Amiibo - Rare Smash Bros ────────────────────────────────────
        ("Mario", "Amiibo", "Gold Mega Man (Smash Bros.)", "Exclusive", "high", 110),
        ("Mario", "Amiibo", "Poochy (Yoshi's Woolly World)", "Toys R Us", "high", 95),

        # ── Nintendo Store Exclusives (Tokyo / Osaka / Kyoto) ────────────
        ("Mario", "Store Exclusive", "Nintendo Osaka Grand Opening Pin Set", "Nintendo Store Osaka", "high", 90),
        ("Mario", "Store Exclusive", "Nintendo Kyoto Opening Day Tote Bag", "Nintendo Store Kyoto", "mid", 55),
        ("Zelda", "Store Exclusive", "Nintendo Tokyo Hylian Shield Backpack", "Nintendo Store Tokyo", "mid", 70),
        ("Splatoon", "Store Exclusive", "Nintendo Osaka Splatoon Ink Bottle Set", "Nintendo Store Osaka", "mid", 45),

        # ── Club Nintendo Platinum Rewards (Vintage) ────────────────────
        ("Mario", "Club Nintendo", "Club Nintendo Platinum Statue Mario & Luigi", "Club Nintendo", "grail", 400),
        ("Zelda", "Club Nintendo", "Club Nintendo Zelda Messenger Bag", "Club Nintendo", "high", 120),
        ("Mario", "Club Nintendo", "Club Nintendo Game & Watch Ball Reissue", "Club Nintendo", "grail", 300),

        # ── Super Nintendo World Merch ──────────────────────────────────
        ("Mario", "Merch", "Super Nintendo World Power-Up Band Full Set (5 Bands)", "Universal Studios JP", "high", 150),
        ("Mario", "Merch", "Toad Cafe Mushroom Soup Bowl Set", "Universal Studios JP", "mid", 48),
        ("Mario", "Merch", "Bowser's Castle Exclusive Koopa Shell Backpack", "Universal Studios JP", "mid", 65),
        ("Mario", "Merch", "Super Nintendo World Star Cup Popcorn Bucket", "Universal Studios JP", "mid", 40),
        ("Mario", "Merch", "Donkey Kong Country Barrel Mug", "Universal Studios JP", "mid", 35),

        # ── Pokemon Center x Nintendo Collaborations ────────────────────
        ("Pokemon", "Merch", "Pikachu x Mario Plush Set", "Pokemon Center JP", "high", 95),
        ("Pokemon", "Merch", "Mario Pikachu Cosplay Plush", "Pokemon Center JP", "high", 110),

        # ── Splatoon Merch - Figures & Plush ────────────────────────────
        ("Splatoon", "Figure", "Squid Sisters Callie & Marie amiibo 2-Pack Reissue", "Nintendo Store", "mid", 50),
        ("Splatoon", "Plush", "Inkling Boy Neon Green Plush 10in", "", "standard", 22),
        ("Splatoon", "Plush", "Judd & Li'l Judd Plush Set", "Nintendo Store JP", "mid", 38),

        # ── Fire Emblem Engage / Three Houses Limited ───────────────────
        ("Fire Emblem", "Figure", "Alear (Fire Emblem Engage) 1/7 Scale", "", "high", 145),
        ("Fire Emblem", "Merch", "Three Houses Officer's Academy Pin Set", "Nintendo Store", "mid", 42),

        # ── Xenoblade Chronicles Collector's Items ──────────────────────
        ("Xenoblade", "Figure", "Pyra 1/7 Scale Figure (Xenoblade 2)", "", "high", 180),
        ("Xenoblade", "Figure", "Mythra 1/7 Scale Figure (Xenoblade 2)", "", "high", 175),
        ("Xenoblade", "Merch", "Xenoblade Chronicles 3 Collector's Edition Artbook + Steelbook", "Nintendo Store", "mid", 75),

        # ── Kirby 30th Anniversary Merchandise ──────────────────────────
        ("Kirby", "Merch", "Kirby 30th Anniversary Medal Collection", "Nintendo Store JP", "mid", 60),
        ("Kirby", "Plush", "Kirby 30th Anniversary Giant Plush 18in", "Nintendo Store JP", "high", 85),
        ("Kirby", "Figure", "Kirby & the Forgotten Land Mouthful Mode Figure Set", "", "mid", 45),

        # ── Nintendo Switch Special Edition Consoles ────────────────────
        ("Zelda", "Console", "Nintendo Switch OLED Zelda TotK Edition", "Limited Edition", "high", 380),
        ("Pokemon", "Console", "Nintendo Switch Lite Pokemon Dialga & Palkia Edition", "Limited Edition", "high", 250),
        ("Animal Crossing", "Console", "Nintendo Switch Animal Crossing New Horizons Edition", "Limited Edition", "high", 350),
        ("Splatoon", "Console", "Nintendo Switch OLED Splatoon 3 Edition", "Limited Edition", "high", 320),
        ("Pokemon", "Console", "Nintendo Switch OLED Pokemon Scarlet & Violet Edition", "Limited Edition", "high", 340),

        # ── Vintage Nintendo Collectibles ───────────────────────────────
        ("Mario", "Vintage", "Game & Watch Gallery Complete Set (4 Games)", "", "grail", 280),
        ("Mario", "Vintage", "Nintendo Hanafuda Playing Cards Miyako no Hana", "", "high", 120),
        ("Mario", "Vintage", "Nintendo Hanafuda Cards Mario Edition (Red)", "", "mid", 65),

        # ── Pikmin Merchandise ─────────────────────────────────────────────
        ("Pikmin", "Plush", "Red Pikmin Plush 8in", "", "standard", 16),
        ("Pikmin", "Plush", "Blue Pikmin Plush 8in", "", "standard", 16),
        ("Pikmin", "Plush", "Yellow Pikmin Plush 8in", "", "standard", 16),
        ("Pikmin", "Plush", "Purple Pikmin Plush 8in", "", "standard", 18),
        ("Pikmin", "Plush", "White Pikmin Plush 8in", "", "standard", 18),
        ("Pikmin", "Plush", "Rock Pikmin Plush 6in", "", "standard", 14),
        ("Pikmin", "Plush", "Winged Pikmin Plush 8in", "", "standard", 18),
        ("Pikmin", "Plush", "Ice Pikmin Plush 6in (Pikmin 4)", "Nintendo Store", "mid", 22),
        ("Pikmin", "Figure", "Pikmin Bloom Flower Pot Set", "Nintendo Store", "mid", 42),
        ("Pikmin", "Merch", "Pikmin 4 Oatchi & Pikmin Ceramic Mug", "Nintendo Store", "standard", 28),

        # ── Pokemon Center - Additional Plush ──────────────────────────────
        ("Pokemon", "Plush", "Jigglypuff Sitting Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Mewtwo Plush 10in", "", "standard", 22),
        ("Pokemon", "Plush", "Lucario Plush 10in", "", "standard", 22),
        ("Pokemon", "Plush", "Dragonite Sitting Plush 8in", "", "standard", 20),
        ("Pokemon", "Plush", "Mimikyu Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Piplup Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Sylveon Plush 10in", "", "standard", 22),
        ("Pokemon", "Plush", "Mew Plush Floating 8in", "Pokemon Center", "mid", 35),
        ("Pokemon", "Plush", "Rayquaza Plush 30in", "Pokemon Center JP", "high", 150),
        ("Pokemon", "Plush", "Gigantamax Pikachu Plush 24in", "Pokemon Center", "high", 120),

        # ── Pokemon Center - Additional Figures ────────────────────────────
        ("Pokemon", "Figure", "Greninja Gallery Figure DX", "Pokemon Center", "mid", 55),
        ("Pokemon", "Figure", "Gardevoir Premium Figure", "Pokemon Center", "mid", 60),
        ("Pokemon", "Figure", "Lucario Gallery Figure", "Pokemon Center", "mid", 50),
        ("Pokemon", "Figure", "Eevee & Friends Premium Figure Set", "Pokemon Center", "high", 95),

        # ── Zelda Additional Collectibles ──────────────────────────────────
        ("Zelda", "Book", "Tears of the Kingdom Collector's Edition Guide", "", "mid", 55),
        ("Zelda", "Replica", "Champion's Tunic Cosplay Set", "", "high", 140),
        ("Zelda", "Merch", "Breath of the Wild Sheikah Slate Case", "Nintendo Store", "mid", 48),
        ("Zelda", "Merch", "Ocarina of Time Ceramic Ocarina Replica", "", "mid", 45),
        ("Zelda", "Figure", "Link Nendoroid Tears of the Kingdom", "", "mid", 55),
        ("Zelda", "Figure", "Zelda Nendoroid Breath of the Wild", "", "mid", 55),

        # ── Mario Additional Merchandise ───────────────────────────────────
        ("Mario", "Figure", "Bowser Nendoroid", "", "mid", 55),
        ("Mario", "Merch", "Super Mario Bros. Wonder Collector Coin Set", "Nintendo Store", "mid", 40),
        ("Mario", "Merch", "Super Mario 3D World Cat Mario Plush 10in", "", "standard", 24),
        ("Mario", "Merch", "Piranha Plant Puppet Plush", "Nintendo Store", "mid", 35),
        ("Mario", "Figure", "Mario & Luigi Dream Team Figure Set", "", "mid", 65),

        # ── Animal Crossing Additional ─────────────────────────────────────
        ("Animal Crossing", "Plush", "Celeste Plush 10in", "", "standard", 22),
        ("Animal Crossing", "Plush", "Blathers Plush 12in", "", "standard", 24),
        ("Animal Crossing", "Merch", "Nook Inc. Aloha Shirt (Adult)", "Nintendo Store", "mid", 45),
        ("Animal Crossing", "Merch", "K.K. Slider Vinyl Record Set", "Nintendo Store JP", "high", 85),

        # ── Splatoon Additional ────────────────────────────────────────────
        ("Splatoon", "Merch", "Splatoon 3 Ink Tank Backpack", "Nintendo Store", "mid", 55),
        ("Splatoon", "Figure", "Off the Hook Pearl & Marina Figure Set", "", "mid", 70),

        # ── Kirby Additional ──────────────────────────────────────────────
        ("Kirby", "Plush", "King Dedede Plush 12in", "", "standard", 24),
        ("Kirby", "Figure", "Kirby & the Forgotten Land Bandana Waddle Dee Figure", "", "mid", 38),
        ("Kirby", "Merch", "Kirby Star Allies Dream Friend Pin Set", "Nintendo Store JP", "mid", 35),

        # ── Star Fox / F-Zero / Other Franchises ──────────────────────────
        ("Star Fox", "Figure", "Fox McCloud Figma", "", "mid", 70),
        ("Star Fox", "Amiibo", "Fox (Star Fox Series)", "", "standard", 18),
        ("F-Zero", "Merch", "Captain Falcon Helmet Replica", "", "high", 120),
        ("EarthBound", "Figure", "Ness Nendoroid", "", "mid", 65),

        # ── Additional Amiibo - Rare/Vintage ──────────────────────────────
        ("Mario", "Amiibo", "Wolf Link (Twilight Princess HD)", "", "mid", 50),
        ("Zelda", "Amiibo", "Toon Link & Zelda 2-Pack (Wind Waker)", "", "mid", 55),
        ("Splatoon", "Amiibo", "Inkling Squid (Orange)", "", "mid", 40),
        ("Pokemon", "Amiibo", "Detective Pikachu", "", "mid", 45),
        ("Kirby", "Amiibo", "King Dedede (Kirby Series)", "", "mid", 45),
        ("Mario", "Amiibo", "Bowser (Wedding Outfit)", "", "standard", 22),
        ("Mario", "Amiibo", "Peach (Wedding Outfit)", "", "standard", 22),

        # ── Nintendo Switch Pro Controllers (Themed) ──────────────────────
        ("Zelda", "Controller", "Pro Controller Zelda TotK Edition", "Limited Edition", "high", 85),
        ("Splatoon", "Controller", "Pro Controller Splatoon 3 Edition", "Limited Edition", "mid", 75),
        ("Xenoblade", "Controller", "Pro Controller Xenoblade 3 Edition", "Limited Edition", "mid", 75),
        ("Monster Hunter", "Controller", "Pro Controller Monster Hunter Rise Edition", "Limited Edition", "mid", 80),

        # === ROUND 2 — Amiibo Complete Collection ===

        # ── Amiibo - Super Smash Bros. Series (Complete) ─────────────────
        ("Mario", "Amiibo", "Luigi (Super Smash Bros.)", "", "standard", 15),
        ("Mario", "Amiibo", "Peach (Super Smash Bros.)", "", "standard", 15),
        ("Mario", "Amiibo", "Bowser (Super Smash Bros.)", "", "standard", 16),
        ("Mario", "Amiibo", "Yoshi (Super Smash Bros.)", "", "standard", 15),
        ("Mario", "Amiibo", "Rosalina & Luma (Smash Bros.)", "Target Exclusive", "high", 85),
        ("Mario", "Amiibo", "Wario (Super Smash Bros.)", "", "standard", 18),
        ("Mario", "Amiibo", "Donkey Kong (Super Smash Bros.)", "", "standard", 16),
        ("Mario", "Amiibo", "Diddy Kong (Super Smash Bros.)", "", "standard", 18),
        ("Mario", "Amiibo", "Toad (Super Smash Bros.)", "", "standard", 15),
        ("Mario", "Amiibo", "Captain Falcon (Super Smash Bros.)", "", "mid", 40),
        ("Mario", "Amiibo", "Little Mac (Super Smash Bros.)", "", "mid", 50),
        ("Mario", "Amiibo", "Pit (Super Smash Bros.)", "", "mid", 35),
        ("Mario", "Amiibo", "Palutena (Super Smash Bros.)", "", "mid", 40),
        ("Mario", "Amiibo", "Dark Pit (Super Smash Bros.)", "Best Buy Exclusive", "mid", 55),
        ("Mario", "Amiibo", "Ike (Super Smash Bros.)", "", "mid", 45),
        ("Mario", "Amiibo", "Robin (Super Smash Bros.)", "", "mid", 50),
        ("Mario", "Amiibo", "Lucina (Super Smash Bros.)", "", "mid", 55),
        ("Mario", "Amiibo", "Roy (Super Smash Bros.)", "", "mid", 35),
        ("Mario", "Amiibo", "R.O.B. (Super Smash Bros.)", "", "mid", 30),
        ("Mario", "Amiibo", "R.O.B. Famicom Colors (Smash Bros.)", "JP Exclusive", "high", 85),
        ("Mario", "Amiibo", "Mr. Game & Watch (Super Smash Bros.)", "", "mid", 45),
        ("Mario", "Amiibo", "Duck Hunt (Super Smash Bros.)", "", "mid", 35),
        ("Mario", "Amiibo", "Pac-Man (Super Smash Bros.)", "", "standard", 20),
        ("Mario", "Amiibo", "Mega Man (Super Smash Bros.)", "", "standard", 22),
        ("Mario", "Amiibo", "Sonic (Super Smash Bros.)", "", "standard", 22),
        ("Mario", "Amiibo", "Ryu (Super Smash Bros.)", "", "standard", 20),
        ("Mario", "Amiibo", "Cloud (Super Smash Bros.)", "", "standard", 22),
        ("Mario", "Amiibo", "Cloud Player 2 (Super Smash Bros.)", "", "mid", 40),
        ("Mario", "Amiibo", "Bayonetta (Super Smash Bros.)", "", "standard", 22),
        ("Mario", "Amiibo", "Bayonetta Player 2 (Smash Bros.)", "", "mid", 45),
        ("Mario", "Amiibo", "Incineroar (Super Smash Bros.)", "", "standard", 18),
        ("Mario", "Amiibo", "Simon Belmont (Super Smash Bros.)", "", "standard", 18),
        ("Mario", "Amiibo", "Richter (Super Smash Bros.)", "", "standard", 18),
        ("Mario", "Amiibo", "Chrom (Super Smash Bros.)", "", "standard", 20),
        ("Mario", "Amiibo", "Dark Samus (Super Smash Bros.)", "", "standard", 20),
        ("Mario", "Amiibo", "King K. Rool (Super Smash Bros.)", "", "standard", 18),
        ("Mario", "Amiibo", "Ice Climbers (Super Smash Bros.)", "", "standard", 18),
        ("Mario", "Amiibo", "Piranha Plant (Super Smash Bros.)", "", "standard", 18),
        ("Mario", "Amiibo", "Isabelle (Super Smash Bros.)", "", "standard", 16),
        ("Mario", "Amiibo", "Ken (Super Smash Bros.)", "", "standard", 18),
        ("Mario", "Amiibo", "Young Link (Super Smash Bros.)", "", "standard", 20),
        ("Mario", "Amiibo", "Joker (Super Smash Bros.)", "", "mid", 35),
        ("Mario", "Amiibo", "Hero (Super Smash Bros.)", "", "mid", 30),
        ("Mario", "Amiibo", "Banjo & Kazooie (Super Smash Bros.)", "", "mid", 35),
        ("Mario", "Amiibo", "Terry Bogard (Super Smash Bros.)", "", "mid", 30),
        ("Mario", "Amiibo", "Byleth (Super Smash Bros.)", "", "standard", 22),
        ("Mario", "Amiibo", "Min Min (Super Smash Bros.)", "", "standard", 20),
        ("Mario", "Amiibo", "Steve (Super Smash Bros.)", "", "mid", 35),
        ("Mario", "Amiibo", "Alex (Super Smash Bros.)", "", "mid", 35),
        ("Mario", "Amiibo", "Sephiroth (Super Smash Bros.)", "", "mid", 40),
        ("Mario", "Amiibo", "Kazuya (Super Smash Bros.)", "", "mid", 35),
        ("Mario", "Amiibo", "Sora (Super Smash Bros.)", "", "mid", 45),

        # ── Amiibo - Super Mario Series ─────────────────────────────────
        ("Mario", "Amiibo", "Mario (Super Mario Series)", "", "standard", 14),
        ("Mario", "Amiibo", "Luigi (Super Mario Series)", "", "standard", 14),
        ("Mario", "Amiibo", "Peach (Super Mario Series)", "", "standard", 14),
        ("Mario", "Amiibo", "Toad (Super Mario Series)", "", "standard", 14),
        ("Mario", "Amiibo", "Bowser (Super Mario Series)", "", "standard", 16),
        ("Mario", "Amiibo", "Yoshi (Super Mario Series)", "", "standard", 14),
        ("Mario", "Amiibo", "Rosalina (Super Mario Series)", "", "standard", 18),
        ("Mario", "Amiibo", "Donkey Kong (Super Mario Series)", "", "standard", 16),
        ("Mario", "Amiibo", "Diddy Kong (Super Mario Series)", "", "standard", 16),
        ("Mario", "Amiibo", "Daisy (Super Mario Series)", "", "standard", 16),
        ("Mario", "Amiibo", "Waluigi (Super Mario Series)", "", "standard", 18),
        ("Mario", "Amiibo", "Boo (Super Mario Series)", "", "mid", 35),
        ("Mario", "Amiibo", "Goomba (Super Mario Series)", "", "standard", 16),
        ("Mario", "Amiibo", "Koopa Troopa (Super Mario Series)", "", "standard", 16),
        ("Mario", "Amiibo", "Bowser Jr. (Super Mario Series)", "", "standard", 18),

        # ── Amiibo - Animal Crossing Series ──────────────────────────────
        ("Animal Crossing", "Amiibo", "Isabelle (Animal Crossing Series)", "", "standard", 14),
        ("Animal Crossing", "Amiibo", "K.K. Slider (Animal Crossing)", "", "standard", 16),
        ("Animal Crossing", "Amiibo", "Tom Nook (Animal Crossing)", "", "standard", 14),
        ("Animal Crossing", "Amiibo", "Mabel (Animal Crossing)", "", "standard", 14),
        ("Animal Crossing", "Amiibo", "Blathers (Animal Crossing)", "", "standard", 14),
        ("Animal Crossing", "Amiibo", "Celeste (Animal Crossing)", "", "standard", 16),
        ("Animal Crossing", "Amiibo", "Resetti (Animal Crossing)", "", "standard", 14),
        ("Animal Crossing", "Amiibo", "Kicks (Animal Crossing)", "", "standard", 14),
        ("Animal Crossing", "Amiibo", "Rover (Animal Crossing)", "", "mid", 30),
        ("Animal Crossing", "Amiibo", "Timmy & Tommy (Animal Crossing)", "", "standard", 18),

        # ── Amiibo - Zelda 30th Anniversary ─────────────────────────────
        ("Zelda", "Amiibo", "8-Bit Link (30th Anniversary)", "", "mid", 40),
        ("Zelda", "Amiibo", "Ocarina of Time Link (30th Anniversary)", "", "mid", 45),
        ("Zelda", "Amiibo", "Wind Waker Link (30th Anniversary)", "", "mid", 40),
        ("Zelda", "Amiibo", "Toon Zelda (Wind Waker)", "", "mid", 35),
        ("Zelda", "Amiibo", "Majora's Mask Link", "", "mid", 55),
        ("Zelda", "Amiibo", "Twilight Princess Link", "", "mid", 45),

        # ── Amiibo - Monster Hunter Series ───────────────────────────────
        ("Monster Hunter", "Amiibo", "One-Eyed Rathalos & Rider (Boy)", "JP Exclusive", "high", 120),
        ("Monster Hunter", "Amiibo", "Qurupeco & Dan (MH Stories)", "JP Exclusive", "high", 110),
        ("Monster Hunter", "Amiibo", "Palamute (MH Rise)", "", "mid", 35),
        ("Monster Hunter", "Amiibo", "Palico (MH Rise)", "", "mid", 35),
        ("Monster Hunter", "Amiibo", "Magnamalo (MH Rise)", "", "mid", 40),

        # ── Amiibo - Shovel Knight / Misc ────────────────────────────────
        ("Mario", "Amiibo", "Shovel Knight", "", "mid", 35),
        ("Mario", "Amiibo", "Shovel Knight Gold Edition", "Best Buy Exclusive", "high", 90),

        # === ROUND 3 — Pokemon Center Deep Dive ===

        # ── Pokemon Center - Plush Waves ─────────────────────────────────
        ("Pokemon", "Plush", "Umbreon Plush 10in", "", "standard", 22),
        ("Pokemon", "Plush", "Espeon Plush 10in", "", "standard", 22),
        ("Pokemon", "Plush", "Glaceon Plush 10in", "", "standard", 22),
        ("Pokemon", "Plush", "Leafeon Plush 10in", "", "standard", 22),
        ("Pokemon", "Plush", "Flareon Plush 10in", "", "standard", 22),
        ("Pokemon", "Plush", "Vaporeon Plush 10in", "", "standard", 22),
        ("Pokemon", "Plush", "Jolteon Plush 10in", "", "standard", 22),
        ("Pokemon", "Plush", "Fuecoco Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Sprigatito Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Quaxly Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Bulbasaur Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Squirtle Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Charmander Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Meowth Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Togepi Plush 6in", "", "standard", 16),
        ("Pokemon", "Plush", "Psyduck Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Magikarp Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Ditto Plush 6in", "", "standard", 16),
        ("Pokemon", "Plush", "Alcremie Plush 8in", "Pokemon Center", "mid", 30),
        ("Pokemon", "Plush", "Wooloo Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Corviknight Plush 10in", "", "standard", 22),
        ("Pokemon", "Plush", "Dragapult Plush 12in", "", "standard", 25),
        ("Pokemon", "Plush", "Cetitan Plush 10in", "", "standard", 22),

        # ── Pokemon Center - Costume Pikachu Series ─────────────────────
        ("Pokemon", "Plush", "Pikachu Mega Charizard X Poncho Plush", "Pokemon Center JP", "high", 130),
        ("Pokemon", "Plush", "Pikachu Mega Charizard Y Poncho Plush", "Pokemon Center JP", "high", 130),
        ("Pokemon", "Plush", "Pikachu Mega Lucario Poncho Plush", "Pokemon Center JP", "high", 120),
        ("Pokemon", "Plush", "Pikachu Mega Audino Poncho Plush", "Pokemon Center JP", "high", 110),
        ("Pokemon", "Plush", "Pikachu Gyarados Poncho Plush", "Pokemon Center JP", "high", 120),

        # ── Pokemon Center - Regional Exclusives ─────────────────────────
        ("Pokemon", "Plush", "Pikachu Yokohama Sailor Plush", "Pokemon Center Yokohama", "high", 85),
        ("Pokemon", "Plush", "Pikachu Osaka Takoyaki Plush", "Pokemon Center Osaka", "high", 80),
        ("Pokemon", "Plush", "Pikachu Sapporo Snow Festival Plush", "Pokemon Center Sapporo", "high", 90),
        ("Pokemon", "Plush", "Pikachu Kyoto Maiko Plush", "Pokemon Center Kyoto", "high", 85),
        ("Pokemon", "Plush", "Pikachu Okinawa Kariyushi Plush", "Pokemon Center Okinawa", "high", 80),
        ("Pokemon", "Plush", "Pikachu Singapore Plush", "Pokemon Center Singapore", "high", 75),

        # ── Pokemon Center - Event Exclusive Plush ───────────────────────
        ("Pokemon", "Event", "Worlds 2022 Pikachu Plush London", "Pokemon Worlds", "high", 140),
        ("Pokemon", "Event", "Worlds 2024 Pikachu Plush Honolulu", "Pokemon Worlds", "high", 160),
        ("Pokemon", "Event", "Pikachu Outbreak Yokohama 2023 Plush", "Pokemon Center JP", "high", 100),
        ("Pokemon", "Event", "Pokemon Day 2024 Special Pikachu", "Pokemon Center", "mid", 65),

        # ── Pokemon Center - Trainer Accessories ─────────────────────────
        ("Pokemon", "TCG Accessory", "Eeveelutions Premium Playmat", "Pokemon Center", "mid", 38),
        ("Pokemon", "TCG Accessory", "Gengar Halloween Premium Sleeves 65ct", "Pokemon Center", "standard", 14),
        ("Pokemon", "TCG Accessory", "Pikachu Leather Binder 9-Pocket", "Pokemon Center", "mid", 45),
        ("Pokemon", "TCG Accessory", "Paldea Starters Deck Box", "Pokemon Center", "standard", 18),
        ("Pokemon", "TCG Accessory", "Charizard ex Premium Collection Box", "Pokemon Center", "mid", 55),

        # ── Pokemon Center - Figures Additional ──────────────────────────
        ("Pokemon", "Figure", "Pikachu VMAX Climax Figure", "Pokemon Center JP", "mid", 50),
        ("Pokemon", "Figure", "Mewtwo Strikes Back Evolution Premium Figure", "Pokemon Center", "mid", 65),
        ("Pokemon", "Figure", "Arceus 1/7 Scale Figure", "", "high", 180),
        ("Pokemon", "Figure", "Red & Charizard Premium Statue", "Pokemon Center", "grail", 250),

        # === ROUND 4 — All Franchises Deep Dive ===

        # ── Zelda - Complete Merch Collection ────────────────────────────
        ("Zelda", "Book", "The Legend of Zelda Encyclopedia", "", "mid", 45),
        ("Zelda", "Book", "Breath of the Wild Master Works", "", "mid", 55),
        ("Zelda", "Book", "Majora's Mask 3D Collector's Guide", "", "mid", 40),
        ("Zelda", "Replica", "Master Sword 1:1 Scale First 4 Figures", "First 4 Figures", "grail", 350),
        ("Zelda", "Replica", "Goddess Sword Skyward Sword Replica", "", "high", 140),
        ("Zelda", "Replica", "Fierce Deity Sword Replica", "", "high", 160),
        ("Zelda", "Figure", "Link on Horseback First 4 Figures", "First 4 Figures", "grail", 500),
        ("Zelda", "Figure", "Skull Kid Majora's Mask First 4 Figures", "First 4 Figures", "grail", 400),
        ("Zelda", "Figure", "Urbosa Breath of the Wild First 4 Figures", "First 4 Figures", "grail", 380),
        ("Zelda", "Figure", "Daruk Breath of the Wild First 4 Figures", "First 4 Figures", "grail", 360),
        ("Zelda", "Figure", "Mipha Breath of the Wild First 4 Figures", "First 4 Figures", "grail", 380),
        ("Zelda", "Figure", "Revali Breath of the Wild First 4 Figures", "First 4 Figures", "grail", 370),
        ("Zelda", "Merch", "Sheikah Eye Night Light", "Nintendo Store", "standard", 28),
        ("Zelda", "Merch", "Triforce LED Lamp", "", "mid", 40),
        ("Zelda", "Merch", "Korok Seed Keychain Set (8pc)", "Nintendo Store", "mid", 35),
        ("Zelda", "Merch", "Hylian Shield Backpack", "Nintendo Store", "mid", 65),
        ("Zelda", "Merch", "Breath of the Wild Map Poster Canvas", "Nintendo Store", "mid", 45),
        ("Zelda", "Soundtrack", "Zelda 25th Anniversary Orchestra CD", "Club Nintendo", "high", 95),
        ("Zelda", "Soundtrack", "Breath of the Wild Original Soundtrack 5-CD Set", "", "high", 120),
        ("Zelda", "Soundtrack", "Tears of the Kingdom Soundtrack", "", "mid", 55),
        ("Zelda", "Steelbook", "Link's Awakening Steelbook", "Limited Edition", "mid", 45),
        ("Zelda", "Steelbook", "Majora's Mask 3D Steelbook", "Limited Edition", "mid", 50),

        # ── Mario - Complete Merch Collection ────────────────────────────
        ("Mario", "Figure", "Mario Nendoroid", "", "mid", 55),
        ("Mario", "Figure", "Luigi Nendoroid", "", "mid", 55),
        ("Mario", "Figure", "Princess Peach Nendoroid", "", "mid", 55),
        ("Mario", "Figure", "Toad Nendoroid", "", "mid", 50),
        ("Mario", "Figure", "Bowser First 4 Figures", "First 4 Figures", "grail", 450),
        ("Mario", "Figure", "Mario on Yoshi First 4 Figures", "First 4 Figures", "grail", 400),
        ("Mario", "Plush", "Chain Chomp Plush 8in", "", "standard", 20),
        ("Mario", "Plush", "Boo Plush 8in", "", "standard", 18),
        ("Mario", "Plush", "Bob-omb Plush 6in", "", "standard", 16),
        ("Mario", "Plush", "Goomba Plush 6in", "", "standard", 16),
        ("Mario", "Plush", "Koopa Troopa Plush 8in", "", "standard", 18),
        ("Mario", "Plush", "Toad Plush 8in", "", "standard", 16),
        ("Mario", "Plush", "Bowser Jr. Plush 8in", "", "standard", 20),
        ("Mario", "Plush", "Yoshi Green Plush 12in", "", "standard", 24),
        ("Mario", "Plush", "Princess Peach Plush 10in", "", "standard", 22),
        ("Mario", "Merch", "Mario Kart 8 Deluxe Red Shell Replica", "Nintendo Store", "mid", 45),
        ("Mario", "Merch", "Super Star LED Lamp", "", "mid", 38),
        ("Mario", "Merch", "? Block Lamp with Sound", "", "mid", 42),
        ("Mario", "Merch", "Bullet Bill Desk Lamp", "", "mid", 40),
        ("Mario", "Merch", "Mario Movie Collector's Edition Poster Set", "", "mid", 35),
        ("Mario", "Soundtrack", "Super Mario Galaxy Original Soundtrack Platinum", "", "high", 80),
        ("Mario", "Soundtrack", "Super Mario Odyssey Original Soundtrack 4-CD", "", "mid", 65),
        ("Mario", "Soundtrack", "Super Mario Bros. Movie Soundtrack Vinyl", "", "mid", 40),
        ("Mario", "Controller", "Joy-Con Super Mario Movie Edition", "Limited Edition", "mid", 75),
        ("Mario", "Carrying Case", "Nintendo Switch Mario Kart Carrying Case", "", "standard", 25),

        # ── Animal Crossing - Deep Dive ──────────────────────────────────
        ("Animal Crossing", "Plush", "Brewster Plush 10in", "", "standard", 22),
        ("Animal Crossing", "Plush", "Pascal Plush 8in", "", "standard", 20),
        ("Animal Crossing", "Plush", "Flick Plush 10in", "", "standard", 22),
        ("Animal Crossing", "Plush", "CJ Plush 10in", "", "standard", 22),
        ("Animal Crossing", "Plush", "Daisy Mae Plush 8in", "", "standard", 20),
        ("Animal Crossing", "Plush", "Leif Plush 8in", "", "standard", 20),
        ("Animal Crossing", "Figure", "Isabelle Nendoroid", "", "mid", 50),
        ("Animal Crossing", "Figure", "Tom Nook Nendoroid", "", "mid", 50),
        ("Animal Crossing", "Figure", "Villager Nendoroid", "", "mid", 55),
        ("Animal Crossing", "Merch", "Museum Fish Model Set", "Nintendo Store", "mid", 55),
        ("Animal Crossing", "Merch", "Nook's Cranny Premium Ceramic Set", "Nintendo Store JP", "high", 85),
        ("Animal Crossing", "Merch", "Animal Crossing Island Life Tote Bag", "Nintendo Store", "standard", 28),
        ("Animal Crossing", "Merch", "Brewster Coffee Mug & Saucer", "Nintendo Store", "standard", 28),
        ("Animal Crossing", "Merch", "Animal Crossing Amiibo Card Album", "", "standard", 18),
        ("Animal Crossing", "Soundtrack", "Animal Crossing NH Original Soundtrack 7-CD Set", "", "high", 120),

        # ── Splatoon - Deep Dive ─────────────────────────────────────────
        ("Splatoon", "Plush", "Octopus Plush (Red)", "", "standard", 20),
        ("Splatoon", "Plush", "Squid Plush (Purple)", "", "standard", 20),
        ("Splatoon", "Plush", "Squid Plush (Neon Green)", "", "standard", 20),
        ("Splatoon", "Plush", "Little Buddy Plush 6in", "", "standard", 16),
        ("Splatoon", "Figure", "Inkling Girl Figma", "", "mid", 65),
        ("Splatoon", "Figure", "Inkling Boy Figma", "", "mid", 65),
        ("Splatoon", "Figure", "Agent 3 Figma", "", "mid", 70),
        ("Splatoon", "Merch", "Splatoon 3 Splat Roller Pen", "Nintendo Store", "standard", 18),
        ("Splatoon", "Merch", "Splatoon 3 Squid Band Tee Shirt", "Nintendo Store", "standard", 28),
        ("Splatoon", "Merch", "Splatoon 3 Deep Cut Poster Set", "Nintendo Store JP", "mid", 35),
        ("Splatoon", "Soundtrack", "Splatoon 3 Original Soundtrack Splatune 3", "", "mid", 55),
        ("Splatoon", "Controller", "Joy-Con Splatoon 3 Gradient Edition", "Limited Edition", "mid", 75),

        # ── Kirby - Deep Dive ────────────────────────────────────────────
        ("Kirby", "Plush", "Meta Knight Plush 10in", "", "standard", 22),
        ("Kirby", "Plush", "Bandana Waddle Dee Plush 8in", "", "standard", 18),
        ("Kirby", "Plush", "Kirby Sleeping Plush 10in", "", "standard", 20),
        ("Kirby", "Plush", "Kirby Star Allies Friends Set (4 Plush)", "Nintendo Store JP", "mid", 55),
        ("Kirby", "Plush", "Marx Plush 8in", "", "standard", 22),
        ("Kirby", "Plush", "Magolor Plush 8in", "", "standard", 22),
        ("Kirby", "Figure", "Kirby Nendoroid Ice", "", "mid", 50),
        ("Kirby", "Figure", "Meta Knight Nendoroid", "", "mid", 55),
        ("Kirby", "Figure", "King Dedede Nendoroid", "", "mid", 55),
        ("Kirby", "Figure", "Kirby Discovery Figure Collection Set", "", "mid", 45),
        ("Kirby", "Merch", "Kirby Cafe Plate & Cutlery Set", "Kirby Cafe JP", "mid", 55),
        ("Kirby", "Merch", "Kirby Cafe Menu Drink Bottle", "Kirby Cafe JP", "mid", 30),
        ("Kirby", "Merch", "Kirby 30th Anniversary Coin Set", "Nintendo Store JP", "mid", 45),
        ("Kirby", "Merch", "Warp Star Lamp", "", "mid", 42),
        ("Kirby", "Soundtrack", "Kirby and the Forgotten Land Soundtrack", "", "mid", 45),

        # ── Fire Emblem - Deep Dive ──────────────────────────────────────
        ("Fire Emblem", "Figure", "Dimitri 1/7 Scale Figure", "", "high", 150),
        ("Fire Emblem", "Figure", "Claude 1/7 Scale Figure", "", "high", 145),
        ("Fire Emblem", "Figure", "Lyn Figma", "", "mid", 75),
        ("Fire Emblem", "Figure", "Celica Figma", "", "mid", 65),
        ("Fire Emblem", "Figure", "Alear (Female) 1/7 Scale Figure", "", "high", 145),
        ("Fire Emblem", "Amiibo", "Alm (Fire Emblem Echoes)", "", "mid", 40),
        ("Fire Emblem", "Amiibo", "Celica (Fire Emblem Echoes)", "", "mid", 40),
        ("Fire Emblem", "Amiibo", "Tiki (Fire Emblem)", "", "mid", 45),
        ("Fire Emblem", "Amiibo", "Chrom (Fire Emblem)", "", "mid", 35),
        ("Fire Emblem", "Book", "Fire Emblem Art Book: 25th Anniversary", "", "high", 85),
        ("Fire Emblem", "Book", "Fire Emblem Heroes Character Design Book", "", "mid", 45),
        ("Fire Emblem", "Merch", "Fire Emblem Engage Emblem Ring Replica Set", "Nintendo Store", "high", 120),

        # ── Metroid - Deep Dive ──────────────────────────────────────────
        ("Metroid", "Figure", "Samus Aran Light Suit Figma", "", "high", 95),
        ("Metroid", "Figure", "Samus Zero Suit Figma", "", "mid", 75),
        ("Metroid", "Figure", "Metroid Prime 2 Dark Samus Statue", "First 4 Figures", "grail", 350),
        ("Metroid", "Figure", "Samus Returns Special Edition Figure", "", "mid", 65),
        ("Metroid", "Amiibo", "Samus Aran (Super Smash Bros.)", "", "standard", 18),
        ("Metroid", "Amiibo", "Zero Suit Samus (Super Smash Bros.)", "", "mid", 35),
        ("Metroid", "Amiibo", "Samus & E.M.M.I. 2-Pack (Metroid Dread)", "", "mid", 50),
        ("Metroid", "Replica", "Metroid Dread E.M.M.I. Statue", "First 4 Figures", "grail", 300),
        ("Metroid", "Soundtrack", "Metroid Dread Original Soundtrack", "", "mid", 45),
        ("Metroid", "Steelbook", "Metroid Dread Steelbook", "Limited Edition", "mid", 40),

        # ── Xenoblade - Deep Dive ────────────────────────────────────────
        ("Xenoblade", "Figure", "Shulk 1/7 Scale Figure", "", "high", 160),
        ("Xenoblade", "Figure", "Mio 1/7 Scale Figure (Xenoblade 3)", "", "high", 170),
        ("Xenoblade", "Figure", "Rex 1/7 Scale Figure (Xenoblade 2)", "", "high", 165),
        ("Xenoblade", "Figure", "Pneuma 1/7 Scale Figure (Xenoblade 2)", "", "high", 180),
        ("Xenoblade", "Figure", "Nia 1/7 Scale Figure (Xenoblade 2)", "", "high", 160),
        ("Xenoblade", "Amiibo", "Shulk (Super Smash Bros.)", "", "mid", 40),
        ("Xenoblade", "Amiibo", "Pyra (Super Smash Bros.)", "", "mid", 35),
        ("Xenoblade", "Amiibo", "Mythra (Super Smash Bros.)", "", "mid", 35),
        ("Xenoblade", "Amiibo", "Noah (Xenoblade 3)", "", "mid", 30),
        ("Xenoblade", "Amiibo", "Mio (Xenoblade 3)", "", "mid", 30),
        ("Xenoblade", "Merch", "Xenoblade 2 Collector's Edition Artbook", "Nintendo Store", "mid", 60),
        ("Xenoblade", "Soundtrack", "Xenoblade Chronicles Definitive Soundtrack", "", "mid", 55),
        ("Xenoblade", "Soundtrack", "Xenoblade Chronicles 3 Original Soundtrack 6-CD", "", "high", 80),

        # ── Pikmin - Deep Dive ───────────────────────────────────────────
        ("Pikmin", "Plush", "Glow Pikmin Plush 6in (Pikmin 4)", "Nintendo Store", "mid", 22),
        ("Pikmin", "Plush", "Bulbmin Plush 6in", "Nintendo Store JP", "mid", 28),
        ("Pikmin", "Plush", "Oatchi Plush 8in (Pikmin 4)", "Nintendo Store", "standard", 22),
        ("Pikmin", "Plush", "Pikmin Full Set (All 9 Types)", "Nintendo Store JP", "high", 120),
        ("Pikmin", "Figure", "Pikmin 4 Ice Onion Figure Set", "Nintendo Store", "mid", 48),
        ("Pikmin", "Figure", "Captain Olimar Nendoroid", "", "mid", 55),
        ("Pikmin", "Merch", "Pikmin Terrarium Collection Full Set", "", "mid", 65),
        ("Pikmin", "Merch", "Pikmin Bloom 1st Anniversary Pin Set", "Nintendo Store", "mid", 30),
        ("Pikmin", "Merch", "Pikmin 4 Ice Pikmin LED Light", "Nintendo Store", "standard", 28),

        # ── Star Fox / F-Zero / EarthBound - Deep Dive ───────────────────
        ("Star Fox", "Figure", "Arwing Ship Model", "", "high", 95),
        ("Star Fox", "Amiibo", "Falco (Star Fox Series)", "", "standard", 18),
        ("Star Fox", "Merch", "Star Fox Zero Premium Pin Set", "Nintendo Store", "mid", 35),
        ("F-Zero", "Merch", "Blue Falcon Model Kit", "", "high", 110),
        ("F-Zero", "Merch", "F-Zero GX Soundtrack Vinyl Repress", "", "high", 85),
        ("F-Zero", "Figure", "Captain Falcon Nendoroid", "", "mid", 65),
        ("EarthBound", "Figure", "Lucas Nendoroid", "", "mid", 65),
        ("EarthBound", "Merch", "Mr. Saturn Plush 6in", "", "mid", 35),
        ("EarthBound", "Merch", "EarthBound Player's Guide Reprint", "", "high", 85),
        ("EarthBound", "Merch", "Mother 3 Handbook (JP)", "", "mid", 55),

        # === ROUND 5 — Special Editions, Controllers, Carrying Cases ===

        # ── Special Edition Consoles / Hardware ──────────────────────────
        ("Mario", "Console", "Nintendo Switch OLED Mario Red Edition", "Limited Edition", "high", 350),
        ("Pokemon", "Console", "Nintendo Switch Lite Zacian & Zamazenta", "Limited Edition", "high", 240),
        ("Mario", "Console", "Nintendo 2DS XL Super Mario Maker Edition", "Limited Edition", "high", 200),
        ("Zelda", "Console", "New Nintendo 3DS XL Majora's Mask Edition", "Limited Edition", "grail", 350),
        ("Zelda", "Console", "New Nintendo 3DS XL Hyrule Gold Edition", "Limited Edition", "high", 280),
        ("Pokemon", "Console", "New Nintendo 3DS XL Solgaleo Lunala", "Limited Edition", "high", 250),
        ("Mario", "Console", "Nintendo Switch Super Mario Odyssey Bundle", "Limited Edition", "high", 300),

        # ── Themed Controllers ───────────────────────────────────────────
        ("Mario", "Controller", "Joy-Con Pastel Purple & Green", "Limited Edition", "mid", 75),
        ("Zelda", "Controller", "GameCube Controller Smash Bros. Ultimate", "Limited Edition", "mid", 60),
        ("Pokemon", "Controller", "PowerA Enhanced Wireless Pikachu Gold", "", "standard", 28),
        ("Pokemon", "Controller", "Hori Split Pad Pro Pikachu & Eevee", "", "standard", 35),
        ("Animal Crossing", "Controller", "Pro Controller Animal Crossing Edition", "Limited Edition", "mid", 75),
        ("Mario", "Controller", "N64 Controller for Switch (NSO)", "Nintendo Store", "mid", 50),

        # ── Carrying Cases & Accessories ─────────────────────────────────
        ("Zelda", "Carrying Case", "Nintendo Switch Zelda TotK Travel Case", "", "standard", 25),
        ("Pokemon", "Carrying Case", "Nintendo Switch Pokemon Legends Arceus Case", "", "standard", 22),
        ("Splatoon", "Carrying Case", "Nintendo Switch Splatoon 3 Splat Pack Case", "", "standard", 25),
        ("Animal Crossing", "Carrying Case", "Nintendo Switch AC Aloha Edition Case", "", "standard", 22),
        ("Mario", "Carrying Case", "Nintendo Switch Super Mario Odyssey Traveler Case", "", "standard", 22),

        # ── Art Books & Coffee Table Books ───────────────────────────────
        ("Mario", "Book", "Super Mario Bros. Encyclopedia", "", "mid", 40),
        ("Mario", "Book", "The Art of Super Mario Odyssey", "", "mid", 45),
        ("Splatoon", "Book", "The Art of Splatoon", "", "mid", 40),
        ("Splatoon", "Book", "The Art of Splatoon 2", "", "mid", 40),
        ("Splatoon", "Book", "The Art of Splatoon 3", "", "mid", 45),
        ("Kirby", "Book", "Kirby Art & Style Collection", "", "mid", 40),
        ("Pokemon", "Book", "Pokemon Visual Companion Complete Edition", "", "mid", 35),
        ("Pokemon", "Book", "Pokemon Adventures Box Set (Vol 1-7)", "", "mid", 55),

        # ── Nintendo Store Exclusives - Additional ───────────────────────
        ("Mario", "Store Exclusive", "Nintendo Store Tokyo 5th Anniversary Coin Set", "Nintendo Store Tokyo", "high", 90),
        ("Zelda", "Store Exclusive", "Nintendo Store NY Sheikah Slate Notebook", "Nintendo Store NY", "mid", 35),
        ("Kirby", "Store Exclusive", "Nintendo Store Osaka Kirby Takoyaki Plush", "Nintendo Store Osaka", "mid", 45),
        ("Splatoon", "Store Exclusive", "Nintendo Store Tokyo Splatoon 3 Tee", "Nintendo Store Tokyo", "mid", 40),
        ("Animal Crossing", "Store Exclusive", "Nintendo Store NY Nook Inc. Hoodie", "Nintendo Store NY", "mid", 55),
        ("Pokemon", "Store Exclusive", "Nintendo Store Tokyo Pokemon Trainer Backpack", "Nintendo Store Tokyo", "mid", 65),

        # ── My Nintendo Physical Rewards - Additional ────────────────────
        ("Mario", "My Nintendo", "My Nintendo Mario Hanafuda Cards", "My Nintendo", "mid", 40),
        ("Zelda", "My Nintendo", "My Nintendo Zelda Tote Bag", "My Nintendo", "standard", 25),
        ("Kirby", "My Nintendo", "My Nintendo Kirby Keychain Set", "My Nintendo", "standard", 18),
        ("Splatoon", "My Nintendo", "My Nintendo Splatoon 3 Poster Set", "My Nintendo", "standard", 20),
        ("Pokemon", "My Nintendo", "My Nintendo Pokemon Memo Pad Set", "My Nintendo", "standard", 15),
        ("Animal Crossing", "My Nintendo", "My Nintendo AC Calendar 2024", "My Nintendo", "standard", 18),

        # ── Club Nintendo Vintage Rewards - Additional ───────────────────
        ("Mario", "Club Nintendo", "Club Nintendo SNES Classic Controller", "Club Nintendo", "high", 120),
        ("Zelda", "Club Nintendo", "Club Nintendo Fierce Deity Link Figure", "Club Nintendo", "grail", 250),
        ("Mario", "Club Nintendo", "Club Nintendo Mario Kart Trophy Set (Gold/Silver)", "Club Nintendo", "grail", 280),
        ("Mario", "Club Nintendo", "Club Nintendo Doc Louis Punch-Out!! Code", "Club Nintendo", "high", 150),

        # === ROUND 6 — Tears of the Kingdom, Splatoon 3, Kirby Premium, Metroid Dread, Pikmin, Fire Emblem ===

        # ── Zelda: Tears of the Kingdom Merch ──────────────────────────────
        ("Zelda", "Figure", "Link Tears of the Kingdom Figma (Paraglider)", "", "mid", 70),
        ("Zelda", "Figure", "Ganondorf Demon King First 4 Figures", "First 4 Figures", "grail", 480),
        ("Zelda", "Merch", "Tears of the Kingdom Purah Pad Replica Case", "Nintendo Store", "mid", 55),
        ("Zelda", "Merch", "Tears of the Kingdom Zonai Device Keychain Set (6pc)", "Nintendo Store", "mid", 38),
        ("Zelda", "Merch", "Tears of the Kingdom Ultrahand Grabber Toy", "Nintendo Store", "mid", 45),
        ("Zelda", "Merch", "Tears of the Kingdom Korok Puzzle Cube Set", "Nintendo Store JP", "mid", 42),
        ("Zelda", "Merch", "Tears of the Kingdom Master Sword Glowing Letter Opener", "Nintendo Store", "mid", 50),
        ("Zelda", "Plush", "Tears of the Kingdom Construct Plush 8in", "Nintendo Store", "standard", 24),

        # ── Splatoon 3 Expansion Merch ─────────────────────────────────────
        ("Splatoon", "Plush", "Splatoon 3 Side Order Agent 8 Plush", "Nintendo Store", "mid", 30),
        ("Splatoon", "Figure", "Splatoon 3 Deep Cut Band Figure Set", "Nintendo Store JP", "mid", 65),
        ("Splatoon", "Merch", "Splatoon 3 Side Order Pearl Plush (Order Form)", "Nintendo Store JP", "mid", 48),
        ("Splatoon", "Merch", "Splatoon 3 Splatfest Tee Physical Replica", "Nintendo Store", "standard", 28),
        ("Splatoon", "Merch", "Splatoon 3 Booyah Bomb Stress Ball Set", "Nintendo Store", "standard", 18),
        ("Splatoon", "Soundtrack", "Splatoon 3 Expansion Pass Soundtrack CD", "", "mid", 40),

        # ── Kirby Premium Items ────────────────────────────────────────────
        ("Kirby", "Figure", "Kirby and the Forgotten Land Mouthful Car Nendoroid", "", "mid", 58),
        ("Kirby", "Merch", "Kirby Cafe Exclusive Anniversary Teapot Set", "Kirby Cafe JP", "high", 95),
        ("Kirby", "Plush", "Kirby Planet Robobot Armor Plush 10in", "Nintendo Store JP", "mid", 42),
        ("Kirby", "Figure", "Kirby Return to Dream Land Deluxe Magolor Figure", "", "mid", 48),
        ("Kirby", "Merch", "Kirby Cafe Waddle Dee Baker Apron Set", "Kirby Cafe JP", "mid", 55),

        # ── Metroid Dread Merch ────────────────────────────────────────────
        ("Metroid", "Figure", "Samus Aran Metroid Dread Figma", "", "high", 85),
        ("Metroid", "Figure", "E.M.M.I. White Nendoroid", "", "mid", 55),
        ("Metroid", "Merch", "Metroid Dread Collector Art Print Set (4pc)", "Nintendo Store", "mid", 42),
        ("Metroid", "Merch", "Metroid Dread Samus Arm Cannon Stress Toy", "Nintendo Store", "standard", 22),
        ("Metroid", "Figure", "Metroid Dread Chozo Soldier Statue", "First 4 Figures", "grail", 320),

        # ── Pikmin Items ───────────────────────────────────────────────────
        ("Pikmin", "Plush", "Pikmin 4 Glow Pikmin Night Light Plush", "Nintendo Store", "mid", 32),
        ("Pikmin", "Figure", "Pikmin 4 All Types Terrarium Box Set (9 Figures)", "Nintendo Store JP", "high", 85),
        ("Pikmin", "Merch", "Pikmin 4 Dandori Challenge Timer Clock", "Nintendo Store JP", "mid", 38),

        # ── Fire Emblem Items ──────────────────────────────────────────────
        ("Fire Emblem", "Figure", "Byleth (Female) 1/7 Scale Figure", "", "high", 155),
        ("Fire Emblem", "Merch", "Fire Emblem Three Houses Golden Deer Pin Set", "Nintendo Store", "mid", 38),
        ("Fire Emblem", "Book", "The Art of Fire Emblem: Three Houses", "", "mid", 48),

        # === ROUND 7 — 700+ Expansion: Amiibo, Store Exclusives, Club Nintendo, Game & Watch, Mario Kart, Pikmin, Animal Crossing ===

        # ── Splatoon 3 Amiibo (New Waves) ──────────────────────────────────
        ("Splatoon", "Amiibo", "Splatoon 3 Smallfry Amiibo", "", "mid", 25),
        ("Splatoon", "Amiibo", "Splatoon 3 Inkling (Blue) Amiibo", "", "standard", 18),
        ("Splatoon", "Amiibo", "Splatoon 3 Octoling (Red) Amiibo", "", "standard", 18),
        ("Splatoon", "Amiibo", "Splatoon 3 Idol Trio Amiibo 3-Pack", "Nintendo Store", "high", 85),

        # ── Zelda TotK Amiibo ──────────────────────────────────────────────
        ("Zelda", "Amiibo", "Link (Tears of the Kingdom) Amiibo", "", "mid", 30),
        ("Zelda", "Amiibo", "Ganondorf (Tears of the Kingdom) Amiibo", "", "mid", 35),
        ("Zelda", "Amiibo", "Zelda & Loftwing Amiibo (Skyward Sword HD)", "", "mid", 45),
        ("Zelda", "Amiibo", "Guardian (Breath of the Wild) Amiibo", "", "high", 95),
        ("Zelda", "Amiibo", "Link (Majora's Mask) Amiibo", "", "mid", 55),

        # ── Metroid Dread Amiibo ───────────────────────────────────────────
        ("Metroid", "Amiibo", "Samus (Metroid Dread) Amiibo", "", "mid", 40),
        ("Metroid", "Amiibo", "E.M.M.I. (Metroid Dread) Amiibo", "", "mid", 42),

        # ── Nintendo Tokyo / Osaka / NY Exclusives (More) ──────────────────
        ("Mario", "Store Exclusive", "Nintendo Tokyo 6th Anniversary Gold Mario Coin", "Nintendo Store Tokyo", "high", 110),
        ("Pokemon", "Store Exclusive", "Nintendo Tokyo Pikachu x Tokyo Tower Figure", "Nintendo Store Tokyo", "high", 95),
        ("Zelda", "Store Exclusive", "Nintendo NY Hyrule Warriors Link Poster Set", "Nintendo Store NY", "mid", 45),
        ("Kirby", "Store Exclusive", "Nintendo Osaka Kirby x Dotonbori Tee", "Nintendo Store Osaka", "mid", 38),
        ("Animal Crossing", "Store Exclusive", "Nintendo Tokyo Isabelle Tokyo Edition Plush", "Nintendo Store Tokyo", "mid", 55),
        ("Mario", "Store Exclusive", "Nintendo NY Super Mario World Diorama Figure", "Nintendo Store NY", "high", 85),
        ("Splatoon", "Store Exclusive", "Nintendo Osaka Splatoon 3 Takoyaki Squid Keychain", "Nintendo Store Osaka", "standard", 22),
        ("Pokemon", "Store Exclusive", "Nintendo Kyoto Pikachu Geisha Plush", "Nintendo Store Kyoto", "high", 80),
        ("Zelda", "Store Exclusive", "Nintendo Tokyo Master Sword Ice Tray Mold", "Nintendo Store Tokyo", "standard", 25),
        ("Mario", "Store Exclusive", "Nintendo Osaka Mario Kushikatsu Plush", "Nintendo Store Osaka", "mid", 42),

        # ── Club Nintendo Prizes (Vintage) ─────────────────────────────────
        ("Mario", "Club Nintendo", "Club Nintendo Gold Nunchuk", "Club Nintendo", "grail", 320),
        ("Mario", "Club Nintendo", "Club Nintendo Platinum Mario Hat", "Club Nintendo", "high", 180),
        ("Zelda", "Club Nintendo", "Club Nintendo Zelda Poster Set (25th Anniversary)", "Club Nintendo", "high", 120),
        ("Mario", "Club Nintendo", "Club Nintendo Mario Playing Cards Set (Hanafuda)", "Club Nintendo", "high", 95),
        ("Mario", "Club Nintendo", "Club Nintendo Super Mario Bros. 25th Anniversary Pin Set", "Club Nintendo", "high", 140),
        ("Mario", "Club Nintendo", "Club Nintendo Luigi's Mansion Dark Moon Diorama", "Club Nintendo", "high", 160),
        ("Zelda", "Club Nintendo", "Club Nintendo Zelda 3DS Pouch Set", "Club Nintendo", "mid", 55),
        ("Mario", "Club Nintendo", "Club Nintendo Game & Watch Ball Reissue", "Club Nintendo", "grail", 280),

        # ── Game & Watch Special Editions ──────────────────────────────────
        ("Mario", "Game & Watch", "Game & Watch Super Mario Bros. (2020)", "Limited Edition", "high", 80),
        ("Zelda", "Game & Watch", "Game & Watch The Legend of Zelda (2021)", "Limited Edition", "high", 85),
        ("Mario", "Game & Watch", "Game & Watch Super Mario Bros. (Gold Edition JP)", "Nintendo Store JP", "high", 150),
        ("Mario", "Game & Watch", "Game & Watch Ball (Club Nintendo Reissue)", "Club Nintendo", "grail", 250),

        # ── Mario Kart Merchandise ─────────────────────────────────────────
        ("Mario", "Mario Kart", "Mario Kart Live: Home Circuit Mario Set", "", "mid", 65),
        ("Mario", "Mario Kart", "Mario Kart Live: Home Circuit Luigi Set", "", "mid", 65),
        ("Mario", "Mario Kart", "Mario Kart 8 Deluxe Collector Pin Set (12 Pins)", "Nintendo Store", "mid", 55),
        ("Mario", "Mario Kart", "Mario Kart Trophy Replica (Gold)", "Super Nintendo World", "high", 120),
        ("Mario", "Mario Kart", "Mario Kart Hot Wheels Set (8 Cars)", "", "mid", 48),
        ("Mario", "Mario Kart", "Mario Kart Blue Shell Plush", "Nintendo Store", "mid", 35),
        ("Mario", "Mario Kart", "Mario Kart Rainbow Road LED Lamp", "Nintendo Store JP", "mid", 65),
        ("Mario", "Mario Kart", "Mario Kart Banana Peel Stress Toy Set", "", "standard", 18),
        ("Mario", "Mario Kart", "Mario Kart 8 Sound Drop Collection Full Set", "Nintendo Store JP", "mid", 58),

        # ── Animal Crossing Sanrio Cards ───────────────────────────────────
        ("Animal Crossing", "Amiibo Card", "Animal Crossing Sanrio Collaboration Pack (6 Cards)", "", "mid", 35),
        ("Animal Crossing", "Amiibo Card", "Animal Crossing Sanrio Rilla Card (Single)", "", "mid", 12),
        ("Animal Crossing", "Amiibo Card", "Animal Crossing Sanrio Marty Card (Single)", "", "mid", 12),
        ("Animal Crossing", "Amiibo Card", "Animal Crossing Sanrio Chelsea Card (Single)", "", "mid", 12),
        ("Animal Crossing", "Amiibo Card", "Animal Crossing Sanrio Etoile Card (Single)", "", "mid", 15),
        ("Animal Crossing", "Amiibo Card", "Animal Crossing Sanrio Chai Card (Single)", "", "mid", 12),
        ("Animal Crossing", "Amiibo Card", "Animal Crossing Sanrio Toby Card (Single)", "", "mid", 12),
        ("Animal Crossing", "Amiibo Card", "Animal Crossing Series 5 Pack (6 Cards)", "", "standard", 8),
        ("Animal Crossing", "Amiibo Card", "Animal Crossing Series 5 Complete Set (48 Cards)", "", "high", 120),

        # ── Pikmin Merch (More) ────────────────────────────────────────────
        ("Pikmin", "Plush", "Pikmin 4 Winged Pikmin Plush 6in", "Nintendo Store", "standard", 22),
        ("Pikmin", "Figure", "Pikmin 4 Oatchi Nendoroid", "", "mid", 52),
        ("Pikmin", "Merch", "Pikmin 4 Pellet Posy Desk Plant Figure", "Nintendo Store JP", "mid", 38),
        ("Pikmin", "Merch", "Pikmin Bloom Seedling Bottle Keychain Set", "Nintendo Store", "standard", 24),
        ("Pikmin", "Merch", "Pikmin 4 Dandori Battle Board Game", "Nintendo Store JP", "mid", 45),
        ("Pikmin", "Plush", "Pikmin 4 Bulborb Plush 10in", "Nintendo Store", "mid", 35),

        # ── Super Nintendo World Merchandise ───────────────────────────────
        ("Mario", "Theme Park", "Super Nintendo World Power-Up Band (Mario)", "Super Nintendo World", "mid", 40),
        ("Mario", "Theme Park", "Super Nintendo World Power-Up Band (Luigi)", "Super Nintendo World", "mid", 40),
        ("Mario", "Theme Park", "Super Nintendo World Power-Up Band (Peach)", "Super Nintendo World", "mid", 40),
        ("Mario", "Theme Park", "Super Nintendo World ? Block Popcorn Bucket", "Super Nintendo World", "mid", 55),
        ("Mario", "Theme Park", "Super Nintendo World Mario Kart Bowser Shell Cup", "Super Nintendo World", "mid", 45),
        ("Mario", "Theme Park", "Super Nintendo World 1-UP Mushroom Sipper", "Super Nintendo World", "mid", 38),
        ("Mario", "Theme Park", "Super Nintendo World Opening Day Pin Set", "Super Nintendo World", "high", 95),
        ("Mario", "Theme Park", "Super Nintendo World Hollywood Opening Tee", "Super Nintendo World", "mid", 42),

        # ── Additional Amiibo (Smash Bros. Wave) ───────────────────────────
        ("Sora", "Amiibo", "Sora (Kingdom Hearts) Amiibo (Smash Bros.)", "", "mid", 35),
        ("Kazuya", "Amiibo", "Kazuya Mishima Amiibo (Smash Bros.)", "", "mid", 30),
        ("Steve", "Amiibo", "Steve (Minecraft) Amiibo (Smash Bros.)", "", "mid", 28),
        ("Sephiroth", "Amiibo", "Sephiroth Amiibo (Smash Bros.)", "", "mid", 35),
        ("Pyra", "Amiibo", "Pyra & Mythra 2-Pack Amiibo (Smash Bros.)", "", "mid", 50),
        ("Terry", "Amiibo", "Terry Bogard Amiibo (Smash Bros.)", "", "mid", 28),
        ("Min Min", "Amiibo", "Min Min Amiibo (Smash Bros.)", "", "mid", 25),

        # ── Nintendo Soundtracks & Media ───────────────────────────────────
        ("Mario", "Soundtrack", "Super Mario Galaxy Original Soundtrack (Platinum Edition)", "Club Nintendo", "high", 140),
        ("Zelda", "Soundtrack", "Zelda 25th Anniversary Special Orchestra CD", "Club Nintendo", "high", 95),
        ("Zelda", "Soundtrack", "Zelda Tears of the Kingdom OST (5-CD Box)", "", "high", 90),
        ("Pokemon", "Soundtrack", "Pokemon Scarlet & Violet OST (4-CD Set)", "", "mid", 65),
        ("Mario", "Soundtrack", "Super Mario Odyssey OST (4-CD Set)", "", "mid", 55),

        # ── Donkey Kong Country Merch ──────────────────────────────────────
        ("Donkey Kong", "Figure", "Donkey Kong Country Returns HD DK Figure", "", "mid", 45),
        ("Donkey Kong", "Plush", "Diddy Kong Plush 8in", "Nintendo Store", "standard", 22),
        ("Donkey Kong", "Amiibo", "Donkey Kong (Super Mario Series) Amiibo", "", "standard", 18),
        ("Donkey Kong", "Amiibo", "Diddy Kong (Super Mario Series) Amiibo", "", "standard", 18),
        ("Donkey Kong", "Merch", "Donkey Kong Country Returns HD Banana Pouch", "Nintendo Store JP", "standard", 22),

        # ── Kirby Extra Items ──────────────────────────────────────────────
        ("Kirby", "Plush", "Kirby 30th Anniversary Large Plush 14in", "Nintendo Store JP", "mid", 65),
        ("Kirby", "Figure", "Kirby Nendoroid (Ice Ver.)", "", "mid", 52),
        ("Kirby", "Merch", "Kirby Star Allies Dream Friends Pin Set (8 Pins)", "Nintendo Store", "mid", 42),

        # ── Pokemon Center International Exclusives ────────────────────────
        ("Pokemon", "Plush", "Pokemon Center London Exclusive Galarian Ponyta Plush", "Pokemon Center London", "mid", 48),
        ("Pokemon", "Plush", "Pokemon Center Paris Exclusive Furfrou Pharaoh Plush", "Pokemon Center Paris", "mid", 45),
        ("Pokemon", "Figure", "Pokemon Center Taipei Mimikyu Figure", "Pokemon Center Taipei", "mid", 52),
        ("Pokemon", "Merch", "Pokemon Center Singapore Pikachu Merlion Keychain", "Pokemon Center Singapore", "mid", 35),
        ("Pokemon", "Plush", "Pokemon Center Kanazawa Pikachu Goldleaf Plush", "Pokemon Center Kanazawa", "high", 80),
        ("Pokemon", "Plush", "Pokemon Center Okinawa Pikachu Shisa Plush", "Pokemon Center Okinawa", "mid", 55),

        # === EXPANSION ROUND 13 — 60 new items for 700+ ===

        # ── Xenoblade Chronicles Merch ───────────────────────────────────
        ("Xenoblade", "Figure", "Pyra 1/7 Scale Figure (Good Smile)", "", "high", 180),
        ("Xenoblade", "Figure", "Mythra 1/7 Scale Figure (Good Smile)", "", "high", 175),
        ("Xenoblade", "Figure", "Shulk Nendoroid", "", "mid", 55),
        ("Xenoblade", "Figure", "Rex & Pyra Figma Set", "", "high", 130),
        ("Xenoblade", "Figure", "Pneuma 1/7 Scale Figure", "", "high", 200),
        ("Xenoblade", "Plush", "Nopon Riki Plush 8in", "Nintendo Store JP", "mid", 38),

        # ── Fire Emblem Merch ────────────────────────────────────────────
        ("Fire Emblem", "Figure", "Byleth (Male) Figma", "", "mid", 65),
        ("Fire Emblem", "Figure", "Byleth (Female) Figma", "", "mid", 70),
        ("Fire Emblem", "Figure", "Edelgard von Hresvelg 1/7 Scale", "", "high", 160),
        ("Fire Emblem", "Figure", "Dimitri Alexandre Blaiddyd 1/7 Scale", "", "high", 155),
        ("Fire Emblem", "Figure", "Lucina Figma", "", "mid", 75),
        ("Fire Emblem", "Figure", "Lyn 1/7 Scale Figure (Intelligent Systems)", "", "high", 170),
        ("Fire Emblem", "Amiibo", "Corrin (Player 2 Female) Amiibo", "", "high", 85),
        ("Fire Emblem", "Art Book", "Fire Emblem Engage Art Book (JP)", "", "mid", 48),

        # ── Metroid Merch ────────────────────────────────────────────────
        ("Metroid", "Figure", "Samus Aran (Varia Suit) Figma", "", "mid", 75),
        ("Metroid", "Figure", "Samus Aran (Zero Suit) Figma", "", "mid", 70),
        ("Metroid", "Figure", "Metroid Dread Samus Nendoroid", "", "mid", 55),
        ("Metroid", "Figure", "Dark Samus Amiibo (Smash Bros.)", "", "mid", 45),
        ("Metroid", "Merch", "Metroid Dread E.M.M.I. Model Kit", "", "mid", 62),
        ("Metroid", "Merch", "Metroid Prime Remastered Steelbook (EU)", "", "mid", 35),

        # ── F-Zero / Star Fox Merch ──────────────────────────────────────
        ("F-Zero", "Figure", "Captain Falcon Amiibo (Smash Bros.)", "", "mid", 30),
        ("Star Fox", "Figure", "Fox McCloud Amiibo (Smash Bros.)", "", "mid", 28),
        ("Star Fox", "Figure", "Arwing First4Figures Statue", "", "high", 200),
        ("F-Zero", "Merch", "Blue Falcon Die-Cast Model (Club Nintendo)", "Club Nintendo", "high", 120),

        # ── Earthbound / Mother Merch ────────────────────────────────────
        ("Earthbound", "Figure", "Ness Nendoroid", "", "mid", 60),
        ("Earthbound", "Plush", "Mr. Saturn Plush 6in", "Nintendo Store JP", "mid", 35),
        ("Earthbound", "Merch", "Earthbound Beginnings Franklin Badge Replica", "Hobonichi", "high", 95),
        ("Earthbound", "Art Book", "Mother 2 Illustration Book (Hobonichi)", "Hobonichi", "mid", 45),

        # ── Nintendo Hardware Collectibles ───────────────────────────────
        ("Nintendo", "Console", "Game & Watch: Super Mario Bros. (2020)", "", "mid", 55),
        ("Nintendo", "Console", "Game & Watch: The Legend of Zelda (2021)", "", "mid", 60),
        ("Nintendo", "Console", "Nintendo Switch Lite Hyrule Edition", "", "mid", 230),
        ("Nintendo", "Console", "Nintendo Switch OLED Zelda TotK Edition", "", "high", 380),
        ("Nintendo", "Console", "Nintendo 64 Funtastic Ice Blue (CIB)", "", "high", 250),
        ("Nintendo", "Console", "Nintendo 64 Funtastic Watermelon Red (CIB)", "", "high", 280),
        ("Nintendo", "Console", "Game Boy Micro Famicom Edition (JP)", "", "high", 320),
        ("Nintendo", "Console", "GBA SP Famicom 20th Anniversary Edition", "", "high", 280),
        ("Nintendo", "Console", "DS Lite Zelda Phantom Hourglass Gold Edition", "", "high", 200),

        # ── My Nintendo Rewards (Physical) ───────────────────────────────
        ("Mario", "My Nintendo", "My Nintendo Mario Pin Set (2024)", "My Nintendo", "mid", 30),
        ("Zelda", "My Nintendo", "My Nintendo Zelda Carrying Case", "My Nintendo", "mid", 35),
        ("Splatoon", "My Nintendo", "My Nintendo Splatoon 3 Poster Set", "My Nintendo", "standard", 20),
        ("Pikmin", "My Nintendo", "My Nintendo Pikmin 4 Tote Bag", "My Nintendo", "standard", 22),
        ("Mario", "My Nintendo", "My Nintendo Mario Hanafuda Cards", "My Nintendo", "mid", 40),

        # ── Japanese Region Exclusives ───────────────────────────────────
        ("Pokemon", "Figure", "Pokemon Center Mega Tokyo Pikachu Charizard Poncho Plush", "Pokemon Center Mega Tokyo", "high", 120),
        ("Pokemon", "Merch", "Pokemon Center Yokohama Lapras Sailing Plush", "Pokemon Center Yokohama", "mid", 55),
        ("Mario", "Figure", "Super Mario 35th Anniversary Pin Set (Complete)", "Nintendo Store JP", "high", 150),
        ("Zelda", "Figure", "Zelda 35th Anniversary Game & Watch", "Nintendo Store JP", "mid", 65),
        ("Kirby", "Merch", "Kirby Cafe Tokyo Exclusive Menu Plate Set", "Kirby Cafe Tokyo", "mid", 58),

        # ── Additional Pokemon Center Plush ──────────────────────────────
        ("Pokemon", "Plush", "Eevee Sitting Cuties Plush 6in", "Pokemon Center", "standard", 15),
        ("Pokemon", "Plush", "Snorlax Bean Bag Plush 24in", "Pokemon Center", "high", 150),
        ("Pokemon", "Plush", "Gengar Squishy Plush 12in", "Pokemon Center", "mid", 35),
        ("Pokemon", "Plush", "Dragonite Sitting Cuties Plush 6in", "Pokemon Center", "standard", 15),
        ("Pokemon", "Figure", "Pokemon Center 25th Anniversary Pikachu Figure", "Pokemon Center", "high", 95),
        ("Pokemon", "Merch", "Pokemon Center Eeveelution Premium Collection Box", "Pokemon Center", "high", 120),
    ]

    # ── Batch 12: Store Exclusives, Movie Merch, OLED Editions (55 items) ──
    merch += _additional_nintendo_2025_expansion()

    catalog = []
    for franchise, product_type, name, exclusive, tier, price in merch:
        catalog.append({
            "franchise": franchise,
            "product_type": product_type,
            "name": name,
            "exclusive": exclusive,
            "rarity_tier": tier,
            "price_eur": price,
        })
    # Deduplicate by ('franchise', 'name', 'product_type') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["franchise"], item["name"], item["product_type"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def item_to_catalog_item(item: dict) -> CatalogItem:
    franchise = item["franchise"]
    product_type = item["product_type"]
    name = item["name"]
    exclusive = item["exclusive"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{franchise}-{product_type}-{name}"),
        title=name,
        set_code=franchise.lower().replace(" ", "-"),
        brand="Pokemon Company" if franchise == "Pokemon" else "Nintendo",
        rarity=item["rarity_tier"].title(),
        notes=f"{franchise} | {product_type}" + (f" | {exclusive}" if exclusive else ""),
        attributes_json={
            "franchise": franchise,
            "product_type": product_type,
            "exclusive": exclusive,
            "is_amiibo": product_type == "Amiibo",
            "is_plush": product_type == "Plush",
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    exclusive_score = 0.85 if item["exclusive"] else 0.3

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": exclusive_score,
            "is_amiibo": 1.0 if item["product_type"] == "Amiibo" else 0.0,
            "is_plush": 1.0 if item["product_type"] == "Plush" else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Nintendo / Pokemon merch catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Nintendo Merch Import ===")

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

    logger.info(f"\n=== Nintendo Merch Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
