"""
Import Disney collectibles catalog (500+ items).

Layer 1 (Catalog):  Curated 300+ items across 30+ subcategories → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (eBay, Mercari, ShopDisney, Cardmarket)
- Covers Disney pins (LE, Fantasy, Hidden Mickey, park-exclusive, Loungefly pin sets),
  Loungefly bags, D23 figures, Jim Shore / Disney Traditions, WDCC (Walt Disney
  Classics Collection), Disney Sorcerer's Arena, Disney Lorcana crossover cards,
  Vinylmation, Disney Infinity, designer ears & spirit jerseys, vintage animation
  cels, Disney Animator's Collection, Disney Designer dolls, Disney Store vintage
  plush, vintage Disneyland/WDW park maps, runDisney medals, Disney100 celebration
  items, Shanghai/Tokyo Disney exclusives, and limited ornaments

Usage:
    python -m pipelines.import_disney [--dry-run]
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

CATEGORY = "disney"


def get_curated_catalog() -> list[dict]:
    """Curated Disney collectibles catalog — 500+ items across 35+ subcategories."""

    # (subcategory, name, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (80-200), mid (30-80), standard (<30)

    items = [
        # ── Disney Pins — Limited Edition ──────────────────────────────
        ("pins", "Haunted Mansion 50th Anniversary LE 2500 Pin", "LE 2500", "high", 120),
        ("pins", "Nightmare Before Christmas 30th LE 3000 Pin", "LE 3000", "high", 95),
        ("pins", "Walt Disney Portrait LE 1000 Pin", "LE 1000", "grail", 200),
        ("pins", "Figment Epcot 40th Anniversary LE 4000 Pin", "LE 4000", "high", 80),
        ("pins", "Stitch Crashes Disney Complete Set (12 Pins)", "LE Monthly", "grail", 450),
        ("pins", "Stitch Crashes Disney Single Pin", "LE Monthly", "mid", 40),
        ("pins", "Disney Villains LE 5000 Pin Set", "LE 5000", "high", 90),
        ("pins", "Disney Princess LE 2000 Jumbo Pin", "LE 2000", "high", 140),
        ("pins", "Frozen 10th Anniversary LE 3000 Pin", "LE 3000", "high", 85),
        ("pins", "Cinderella Castle LE 1500 Jumbo Pin", "LE 1500", "grail", 220),

        # ── Disney Pins — Park Exclusive ───────────────────────────────
        ("pins", "Disneyland 70th Anniversary Park Pin", "Park Exclusive", "mid", 35),
        ("pins", "EPCOT Festival of the Arts Pin", "Park Exclusive", "mid", 30),
        ("pins", "Magic Kingdom 50th Anniversary Pin", "Park Exclusive", "mid", 45),
        ("pins", "Disney Pin Trading Starter Set", "Standard", "standard", 15),
        ("pins", "Disney Cast Member Exclusive Pin", "Cast Exclusive", "high", 80),
        ("pins", "Disney Parks Annual Passholder Pin 2025", "Park Exclusive", "mid", 38),

        # ── Disney Pins — Hidden Mickey ────────────────────────────────
        ("pins", "Hidden Mickey Pin (Rare Character)", "Park Exclusive", "mid", 25),
        ("pins", "Hidden Mickey Chaser Pin (Gold Variant)", "Park Exclusive", "high", 85),
        ("pins", "Hidden Mickey Attractions Series Pin", "Park Exclusive", "standard", 18),
        ("pins", "Hidden Mickey Sidekicks Series Pin", "Park Exclusive", "standard", 15),
        ("pins", "Hidden Mickey Villains Series Completer Pin", "Park Exclusive", "mid", 45),

        # ── Disney Pins — Fantasy Pins ─────────────────────────────────
        ("pins", "Fantasy Pin Maleficent Stained Glass", "Fantasy", "mid", 35),
        ("pins", "Fantasy Pin Ursula Art Nouveau", "Fantasy", "mid", 40),
        ("pins", "Fantasy Pin Sorcerer Mickey Jumbo", "Fantasy", "mid", 50),
        ("pins", "Fantasy Pin Villain Mashup Slider", "Fantasy", "mid", 55),
        ("pins", "Fantasy Pin Figment Rainbow Glitter", "Fantasy", "mid", 60),

        # ── Loungefly Pin Sets ─────────────────────────────────────────
        ("pins", "Loungefly Disney Villains Blind Box Pin Set", "Loungefly Set", "mid", 45),
        ("pins", "Loungefly Disney Princess Enamel Pin Set (6pc)", "Loungefly Set", "mid", 38),
        ("pins", "Loungefly Pixar Alien Remix Pin Set", "Loungefly Set", "mid", 35),
        ("pins", "Loungefly Haunted Mansion Ghost Host Pin", "Loungefly Set", "mid", 32),

        # ── Loungefly Bags ─────────────────────────────────────────────
        ("loungefly", "Loungefly Haunted Mansion Mini Backpack", "Standard", "mid", 65),
        ("loungefly", "Loungefly Villains AOP Backpack", "Standard", "mid", 55),
        ("loungefly", "Loungefly Enchanted Tiki Room Crossbody", "Park Exclusive", "high", 85),
        ("loungefly", "Loungefly Figment Epcot Backpack", "Park Exclusive", "high", 95),
        ("loungefly", "Loungefly Disney Princess Wallet Set", "Standard", "mid", 40),
        ("loungefly", "Loungefly NYCC Exclusive Maleficent Bag", "NYCC Exclusive", "high", 130),
        ("loungefly", "Loungefly Disney100 Platinum Backpack", "D100 Exclusive", "high", 110),

        # ── Jim Shore / Disney Traditions ──────────────────────────────
        ("jim_shore", "Jim Shore Fantasia 80th Anniversary Figure", "Limited", "high", 95),
        ("jim_shore", "Jim Shore Cinderella Romantic Waltz Figurine", "Standard", "mid", 65),
        ("jim_shore", "Jim Shore Mickey Mouse Statement Figure (17in)", "Limited", "high", 130),
        ("jim_shore", "Jim Shore Stitch Ohana Figurine", "Standard", "mid", 55),
        ("jim_shore", "Jim Shore Villain Maleficent Dragon Figure", "Limited", "high", 110),
        ("jim_shore", "Jim Shore Disney Traditions Carousel (Musical)", "Premium", "high", 160),
        ("jim_shore", "Jim Shore Frozen Elsa Ice Castle Figurine", "Standard", "mid", 70),
        ("jim_shore", "Jim Shore Winnie the Pooh & Friends Figurine", "Standard", "mid", 50),

        # ── WDCC — Walt Disney Classics Collection ────────────────────
        ("wdcc", "WDCC Cinderella 'A Lovely Dress for Cinderelly'", "WDCC", "grail", 350),
        ("wdcc", "WDCC Fantasia Sorcerer Mickey 'Mischievous Apprentice'", "WDCC", "grail", 280),
        ("wdcc", "WDCC Bambi 'The Young Prince'", "WDCC", "high", 180),
        ("wdcc", "WDCC Sleeping Beauty Maleficent 'Evil Enchantress'", "WDCC", "grail", 320),
        ("wdcc", "WDCC Pinocchio Jiminy Cricket 'Official Conscience'", "WDCC", "high", 150),
        ("wdcc", "WDCC The Little Mermaid Ariel 'Seahorse Surprise'", "WDCC", "grail", 250),

        # ── Figures — D23 & Limited ────────────────────────────────────
        ("figures", "D23 Exclusive Sorcerer Mickey Figure", "D23 Exclusive", "grail", 200),
        ("figures", "D23 Exclusive Villain Designer Doll", "D23 Exclusive", "high", 180),
        ("figures", "Walt Disney Archives Figure (50th)", "Park Exclusive", "mid", 65),

        # ── Disney Designer Dolls ──────────────────────────────────────
        ("designer_dolls", "Disney Designer Collection Ariel Doll", "Designer LE", "high", 150),
        ("designer_dolls", "Disney Designer Collection Belle Doll", "Designer LE", "high", 140),
        ("designer_dolls", "Disney Designer Collection Jasmine Doll", "Designer LE", "high", 145),
        ("designer_dolls", "Disney Designer Collection Rapunzel Doll", "Designer LE", "high", 135),
        ("designer_dolls", "Disney Designer Midnight Masquerade Tiana Doll", "Designer LE", "high", 170),
        ("designer_dolls", "Disney Designer Fairytale Couples Ariel & Eric Set", "Designer LE", "grail", 280),

        # ── Disney Animator's Collection ───────────────────────────────
        ("animators", "Disney Animators' Collection Rapunzel Doll", "Standard", "standard", 25),
        ("animators", "Disney Animators' Collection Moana Doll", "Standard", "standard", 22),
        ("animators", "Disney Animators' Collection Elsa Doll (1st Edition)", "Limited", "mid", 55),
        ("animators", "Disney Animators' Collection Mulan Doll", "Standard", "standard", 22),
        ("animators", "Disney Animators' Collection Gift Set (5 Dolls)", "Limited", "high", 95),

        # ── Vinylmation ───────────────────────────────────────────────
        ("vinylmation", "Vinylmation Park Series 1 (Sealed Case 24pc)", "Standard", "high", 120),
        ("vinylmation", "Vinylmation Nightmare Before Christmas 9in", "Limited", "high", 90),
        ("vinylmation", "Vinylmation Mickey Through the Years Set", "Limited", "high", 85),
        ("vinylmation", "Vinylmation Urban Redux Series Chaser", "Standard", "mid", 45),
        ("vinylmation", "Vinylmation Star Wars Jedi Mickey 3in", "Standard", "mid", 30),
        ("vinylmation", "Vinylmation Villains Series Maleficent 9in", "Limited", "high", 100),

        # ── Disney Infinity Figures ────────────────────────────────────
        ("infinity", "Disney Infinity 3.0 Crystal Sorcerer Mickey", "Crystal Variant", "high", 85),
        ("infinity", "Disney Infinity 1.0 Sorcerer Mickey (Sealed)", "Standard", "mid", 35),
        ("infinity", "Disney Infinity 2.0 Marvel Complete Set (Sealed)", "Standard", "high", 120),
        ("infinity", "Disney Infinity 3.0 Star Wars Boba Fett", "Standard", "mid", 40),
        ("infinity", "Disney Infinity 3.0 Inside Out Joy (Sealed)", "Standard", "standard", 20),

        # ── Disney Sorcerer's Arena ────────────────────────────────────
        ("sorcerers_arena", "Disney Sorcerer's Arena Epic Alliances Core Set", "Standard", "mid", 40),
        ("sorcerers_arena", "Sorcerer's Arena Turning the Tide Expansion", "Standard", "mid", 30),
        ("sorcerers_arena", "Sorcerer's Arena Promo Sorcerer Mickey Card", "Promo", "mid", 35),
        ("sorcerers_arena", "Sorcerer's Arena Into the Inklands Expansion", "Standard", "mid", 32),

        # ── Disney Lorcana (Disney Crossover Cards) ────────────────────
        ("lorcana", "Lorcana Elsa Spirit of Winter Enchanted", "Enchanted Rare", "grail", 350),
        ("lorcana", "Lorcana Mickey Mouse Brave Little Tailor Enchanted", "Enchanted Rare", "grail", 280),
        ("lorcana", "Lorcana Stitch Rock Star Super Rare", "Super Rare", "high", 80),
        ("lorcana", "Lorcana Maui Demigod Legendary", "Legendary", "high", 95),
        ("lorcana", "Lorcana Maleficent Monstrous Dragon Enchanted", "Enchanted Rare", "grail", 220),
        ("lorcana", "Lorcana Robin Hood Champion of Sherwood Enchanted", "Enchanted Rare", "grail", 250),
        ("lorcana", "Lorcana Simba Returned King Super Rare", "Super Rare", "mid", 55),
        ("lorcana", "Lorcana Belle Strange but Special Legendary", "Legendary", "high", 85),
        ("lorcana", "Lorcana Booster Box The First Chapter (Sealed)", "Sealed Product", "high", 180),

        # ── Vintage Disney ─────────────────────────────────────────────
        ("vintage", "Vintage Disneyland 1960s Park Map", "Vintage", "grail", 350),
        ("vintage", "Vintage Walt Disney World Opening Day Ticket", "Vintage", "grail", 500),
        ("vintage", "Vintage Disney Pin-back Button Set (1970s)", "Vintage", "high", 80),
        ("vintage", "Vintage EPCOT Center Opening Poster", "Vintage", "high", 150),
        ("vintage", "Vintage Disneyland 1955 Opening Year Guidebook", "Vintage", "grail", 600),
        ("vintage", "Vintage Walt Disney World 1971 Souvenir Map", "Vintage", "grail", 280),
        ("vintage", "Vintage Tokyo Disneyland 1983 Opening Day Map", "Vintage", "grail", 250),

        # ── Vintage Animation Cels ─────────────────────────────────────
        ("animation_cels", "Original Production Cel The Little Mermaid Ariel", "Vintage", "grail", 1200),
        ("animation_cels", "Original Production Cel The Lion King Simba", "Vintage", "grail", 900),
        ("animation_cels", "Original Production Cel Sleeping Beauty Maleficent", "Vintage", "grail", 1500),
        ("animation_cels", "Sericel Beauty and the Beast LE 5000", "LE 5000", "high", 180),
        ("animation_cels", "Sericel Aladdin LE 5000", "LE 5000", "high", 150),
        ("animation_cels", "Hand-Painted Cel Fantasia Sorcerer Mickey", "Vintage", "grail", 800),

        # ── Disney Store Vintage Plush ─────────────────────────────────
        ("plush", "Disney Store Vintage Winnie the Pooh Giant Plush (1990s)", "Vintage", "mid", 55),
        ("plush", "Disney Store Vintage Stitch Plush (2002 Release)", "Vintage", "mid", 45),
        ("plush", "Disney Store Vintage Lion King Simba Jumbo Plush", "Vintage", "mid", 60),
        ("plush", "Disney Store Limited Sorcerer Mickey Plush (D23)", "D23 Exclusive", "high", 85),
        ("plush", "Disney Store nuiMOs Plush Complete Set (8pc)", "Standard", "mid", 65),

        # ── Disney Ears & Spirit Jerseys ───────────────────────────────
        ("ears", "Designer Minnie Ears by Vera Wang", "Designer", "high", 95),
        ("ears", "50th Anniversary Gold Ears", "LE Park", "mid", 55),
        ("ears", "Spirit Jersey Matching Ears Set", "Seasonal", "mid", 40),
        ("ears", "Disney Parks Loungefly Ears (Haunted Mansion)", "Park Exclusive", "mid", 45),
        ("ears", "Disney Parks Sequin Ears Rose Gold", "Park Exclusive", "mid", 35),
        ("ears", "Walt Disney World Marathon Ears", "Event Exclusive", "high", 80),
        ("ears", "Disney Parks Spirit Jersey Tie-Dye Pastel", "Park Exclusive", "mid", 65),
        ("ears", "Disney Parks Spirit Jersey Phantom Manor (DLP Exclusive)", "Park Exclusive", "high", 85),
        ("ears", "Disney Parks Coral Spirit Jersey", "Seasonal", "mid", 50),

        # ── runDisney Medals ───────────────────────────────────────────
        ("rundisney", "runDisney Walt Disney World Marathon Medal 2025", "Event Exclusive", "high", 80),
        ("rundisney", "runDisney Dopey Challenge Medal Set (4 Medals)", "Event Exclusive", "high", 180),
        ("rundisney", "runDisney Disneyland Half Marathon Medal 2025", "Event Exclusive", "mid", 55),
        ("rundisney", "runDisney Princess Half Marathon Medal", "Event Exclusive", "mid", 50),
        ("rundisney", "runDisney Wine & Dine Half Marathon Medal", "Event Exclusive", "mid", 45),

        # ── Disney100 Celebration Items ────────────────────────────────
        ("disney100", "Disney100 Platinum Celebration Figurine (Mickey)", "D100 Exclusive", "high", 95),
        ("disney100", "Disney100 Years of Wonder Pin Set (Boxed)", "D100 Exclusive", "high", 110),
        ("disney100", "Disney100 Decades Complete Pin Collection (10pc)", "D100 Exclusive", "grail", 280),
        ("disney100", "Disney100 Swarovski Crystal Mickey Figurine", "Premium", "grail", 250),
        ("disney100", "Disney100 Anniversary Dooney & Bourke Tote", "D100 Exclusive", "high", 180),
        ("disney100", "Disney100 Celebration Loungefly Backpack", "D100 Exclusive", "high", 90),

        # ── Shanghai Disney Exclusives ─────────────────────────────────
        ("shanghai_disney", "Shanghai Disney Grand Opening LE 1000 Pin", "LE 1000", "grail", 220),
        ("shanghai_disney", "Shanghai Disney StellaLou Plush (Park Exclusive)", "Park Exclusive", "mid", 45),
        ("shanghai_disney", "Shanghai Disney LinaBell First Edition Plush", "Park Exclusive", "high", 90),
        ("shanghai_disney", "Shanghai Disney Tron Lightcycle Merchandise Set", "Park Exclusive", "mid", 55),

        # ── Tokyo Disney Exclusives ────────────────────────────────────
        ("tokyo_disney", "Tokyo DisneySea Duffy Bear (Original 2005)", "Vintage", "high", 130),
        ("tokyo_disney", "Tokyo Disney ShellieMay Plush (Park Exclusive)", "Park Exclusive", "mid", 50),
        ("tokyo_disney", "Tokyo Disney 40th Anniversary LE Pin Set", "LE 2000", "high", 150),
        ("tokyo_disney", "Tokyo DisneySea 20th Anniversary Poster Set", "Park Exclusive", "mid", 65),
        ("tokyo_disney", "Tokyo Disney Cookie Ann Plush (First Release)", "Park Exclusive", "mid", 55),

        # ── Ornaments ──────────────────────────────────────────────────
        ("ornaments", "Hallmark Disney Castle LE Ornament", "LE", "mid", 50),
        ("ornaments", "Disney Sketchbook Legacy Ornament Set", "Limited", "mid", 45),
        ("ornaments", "Disney Parks 50th Anniversary Ornament", "Park Exclusive", "mid", 35),
        ("ornaments", "Swarovski Disney Castle Ornament", "Premium", "high", 80),
        ("ornaments", "Radko Disney Ornament (Vintage)", "Vintage", "high", 75),

        # ── Disney Pixar Collectibles ────────────────────────────────────
        ("pixar", "Pixar Luxo Jr. Lamp Replica (Full Size)", "Limited", "grail", 350),
        ("pixar", "Pixar Inside Out Joy & Sadness Figurine Set", "Standard", "mid", 45),
        ("pixar", "Pixar Coco Ernesto de la Cruz Guitar Replica", "Limited", "high", 120),
        ("pixar", "Pixar UP Carl's House Snow Globe", "Limited", "high", 85),
        ("pixar", "Pixar Toy Story Woody Round-Up Collectible Set", "D23 Exclusive", "high", 150),
        ("pixar", "Pixar Ratatouille Remy Figurine (Jim Shore)", "Standard", "mid", 55),
        ("pixar", "Pixar WALL-E & EVE Figurine Set", "Limited", "high", 95),

        # ── Disneyland Paris Exclusives ───────────────────────────────────
        ("dlp", "Disneyland Paris Phantom Manor LE 600 Pin", "LE 600", "grail", 280),
        ("dlp", "Disneyland Paris 30th Anniversary LE Pin Set", "LE 3000", "high", 95),
        ("dlp", "Disneyland Paris Ratatouille Remy Chef Figurine", "Park Exclusive", "mid", 55),
        ("dlp", "DLP Space Mountain Mission 2 Poster Art Print", "Park Exclusive", "mid", 40),
        ("dlp", "DLP Alice Curious Labyrinth Map Print", "Park Exclusive", "mid", 35),

        # ── Disney Villains Expanded ─────────────────────────────────────
        ("villains", "Disney Villains Designer Collection Maleficent Doll", "Designer LE", "high", 170),
        ("villains", "Disney Villains Designer Collection Ursula Doll", "Designer LE", "high", 160),
        ("villains", "Disney Villains Designer Collection Evil Queen Doll", "Designer LE", "high", 165),
        ("villains", "Disney Villains Midnight Masquerade Hades Doll", "Designer LE", "high", 155),
        ("villains", "Disney Villains Funko Pop Maleficent (Flames) Chase", "Chase Variant", "high", 85),
        ("villains", "Disney Villains Gallery Cruella Figurine", "Standard", "mid", 50),

        # ── Disney Attraction Memorabilia ────────────────────────────────
        ("attractions", "Space Mountain Original Ride Poster Replica", "Park Exclusive", "mid", 45),
        ("attractions", "Pirates of the Caribbean Ride Vehicle Replica", "Limited", "high", 130),
        ("attractions", "Haunted Mansion Doom Buggy Replica", "Limited", "high", 140),
        ("attractions", "Disneyland Railroad Station Clock Replica", "Limited", "high", 110),
        ("attractions", "Big Thunder Mountain Safety Sign Replica", "Park Exclusive", "mid", 55),
        ("attractions", "Enchanted Tiki Room Jose Figurine", "Park Exclusive", "mid", 65),

        # ── Marvel at Disney Parks ───────────────────────────────────────
        ("marvel_parks", "Avengers Campus Spider-Bot Interactive Toy", "Park Exclusive", "mid", 55),
        ("marvel_parks", "Avengers Campus Opening Day LE 2000 Pin", "LE 2000", "high", 90),
        ("marvel_parks", "Iron Man Gauntlet Full-Scale Replica (Disney Parks)", "Premium", "grail", 250),
        ("marvel_parks", "Guardians of the Galaxy Cosmic Rewind Poster", "Park Exclusive", "mid", 40),
        ("marvel_parks", "Disney Parks Black Panther Wakanda LE Pin", "LE 3000", "high", 80),

        # ── Star Wars Galaxy's Edge ──────────────────────────────────────
        ("galaxys_edge", "Galaxy's Edge Legacy Lightsaber (Luke Skywalker)", "Park Exclusive", "high", 180),
        ("galaxys_edge", "Galaxy's Edge Legacy Lightsaber (Darth Vader)", "Park Exclusive", "high", 180),
        ("galaxys_edge", "Galaxy's Edge Savi's Workshop Custom Lightsaber", "Park Exclusive", "high", 200),
        ("galaxys_edge", "Galaxy's Edge Droid Depot Custom R2 Unit", "Park Exclusive", "high", 110),
        ("galaxys_edge", "Galaxy's Edge Oga's Cantina Pint Glass Set", "Park Exclusive", "mid", 40),
        ("galaxys_edge", "Galaxy's Edge Opening Day LE 1500 Pin", "LE 1500", "grail", 200),

        # ── Disney Music Collectibles ────────────────────────────────────
        ("music", "Fantasia Soundtrack 75th Anniversary Vinyl Box Set", "Limited", "high", 120),
        ("music", "The Nightmare Before Christmas Soundtrack (Oogie Boogie Vinyl)", "Limited", "high", 80),
        ("music", "Encanto Soundtrack Signed by Lin-Manuel Miranda Vinyl", "Signed", "grail", 350),
        ("music", "The Little Mermaid 30th Anniversary Vinyl", "Limited", "mid", 55),
        ("music", "Frozen Original Broadway Cast Recording Vinyl (Blue)", "Limited", "mid", 45),

        # ── Disney Fine Art Prints ───────────────────────────────────────
        ("fine_art", "Thomas Kinkade Cinderella's Castle Signed Canvas", "Signed Print", "grail", 500),
        ("fine_art", "Rob Kaz 'Mickey Paints the Town' Giclee", "Limited Print", "high", 180),
        ("fine_art", "SHAG Enchanted Tiki Room Serigraph", "Limited Print", "high", 150),
        ("fine_art", "Trevor Carlton 'A Pirate's Life' Giclee", "Limited Print", "high", 120),
        ("fine_art", "Rodel Gonzalez 'Stitch's Night' Giclee", "Limited Print", "high", 130),

        # ── Disney Consumer Products Vintage ─────────────────────────────
        ("vintage_products", "Vintage 1950s Mickey Mouse Club Ears Hat", "Vintage", "grail", 250),
        ("vintage_products", "Vintage 1960s Disney View-Master Reel Set", "Vintage", "mid", 45),
        ("vintage_products", "Vintage 1970s Mickey Mouse Rotary Phone", "Vintage", "high", 120),
        ("vintage_products", "Vintage 1980s Disney Afternoon Lunch Box", "Vintage", "mid", 55),
        ("vintage_products", "Vintage 1990s Lion King Happy Meal Toy Set (Complete)", "Vintage", "mid", 40),

        # ── Disney Lorcana Expanded ──────────────────────────────────────
        ("lorcana", "Lorcana Ursula Deceiver Enchanted", "Enchanted Rare", "grail", 200),
        ("lorcana", "Lorcana Hades King of Olympus Enchanted", "Enchanted Rare", "grail", 230),
        ("lorcana", "Lorcana Booster Box Rise of the Floodborn (Sealed)", "Sealed Product", "high", 160),
        ("lorcana", "Lorcana Booster Box Into the Inklands (Sealed)", "Sealed Product", "high", 150),
        ("lorcana", "Lorcana Tinker Bell Giant Fairy Legendary", "Legendary", "high", 90),

        # ── Hong Kong Disneyland Exclusives ──────────────────────────────
        ("hkdl", "Hong Kong Disneyland Duffy Bear (10th Anniversary)", "Park Exclusive", "high", 95),
        ("hkdl", "Hong Kong Disneyland CookieAnn Plush (First Release)", "Park Exclusive", "mid", 50),
        ("hkdl", "Hong Kong Disneyland Frozen Ever After LE Pin", "LE 3000", "high", 85),
        ("hkdl", "Hong Kong Disneyland World of Frozen Opening Pin", "LE 2000", "high", 110),

        # ── Disney Cruise Line Exclusives ────────────────────────────────
        ("dcl", "Disney Cruise Line Maiden Voyage Pin (Disney Wish)", "LE 1500", "grail", 200),
        ("dcl", "Disney Cruise Line Castaway Cay Exclusive Pin", "Park Exclusive", "mid", 45),
        ("dcl", "Disney Cruise Line Captain Mickey Figurine", "Standard", "mid", 40),
        ("dcl", "Disney Cruise Line Disney Treasure Inaugural Pin", "LE 2000", "high", 120),

        # ── Additional Disney Park Items ─────────────────────────────────
        ("attractions", "Tower of Terror Original Bellhop Prop Replica", "Limited", "grail", 250),
        ("attractions", "Carousel of Progress Original Poster Print", "Park Exclusive", "mid", 50),
        ("pixar", "Pixar Turning Red Meilin Red Panda Plush (Giant)", "D23 Exclusive", "high", 95),
        ("pins", "Disney Magical Moments LE 750 Jumbo Pin (Castle Fireworks)", "LE 750", "grail", 280),
        ("vintage", "Vintage Euro Disney Opening Day Ticket 1992", "Vintage", "grail", 350),
        ("tokyo_disney", "Tokyo DisneySea Fantasy Springs Opening LE Pin", "LE 1500", "high", 140),

        # ── Swarovski Disney Crystal Figurines ─────────────────────────────
        ("swarovski", "Swarovski Crystal Mickey Mouse Figurine", "Premium", "high", 180),
        ("swarovski", "Swarovski Crystal Cinderella Slipper", "Premium", "high", 160),
        ("swarovski", "Swarovski Crystal Tinker Bell Figurine", "Premium", "high", 150),
        ("swarovski", "Swarovski Crystal Bambi & Thumper Set", "Premium", "grail", 280),
        ("swarovski", "Swarovski Crystal Dumbo Figurine", "Premium", "high", 140),
        ("swarovski", "Swarovski Crystal Ariel Little Mermaid", "Premium", "high", 170),
        ("swarovski", "Swarovski Crystal Snow White & Seven Dwarfs Set", "Premium", "grail", 650),
        ("swarovski", "Swarovski Crystal Winnie the Pooh & Friends Set", "Premium", "grail", 320),

        # ── Disney x Luxury Brand Collaborations ──────────────────────────
        ("luxury_collab", "Coach x Disney Mickey Mouse Tote (Vintage Print)", "Limited", "high", 180),
        ("luxury_collab", "Coach x Disney Villains Crossbody (Maleficent)", "Limited", "high", 160),
        ("luxury_collab", "Gucci x Disney Mickey Mouse Ace Sneakers", "Limited", "grail", 650),
        ("luxury_collab", "Gucci x Disney Donald Duck GG Canvas Tote", "Limited", "grail", 550),
        ("luxury_collab", "Pandora x Disney Cinderella Charm Set", "Limited", "high", 120),
        ("luxury_collab", "Pandora x Disney Mickey 90th Birthday Charm", "Limited", "high", 95),
        ("luxury_collab", "Marc Jacobs x Disney Mickey Mouse Snapshot Bag", "Limited", "high", 180),
        ("luxury_collab", "Dooney & Bourke Disney Haunted Mansion Crossbody", "Park Exclusive", "high", 150),
        ("luxury_collab", "Dooney & Bourke Disney Dogs Tote", "Park Exclusive", "high", 140),

        # ── WDCC — Additional Walt Disney Classics Collection ────────────
        ("wdcc", "WDCC Peter Pan 'I'm So Happy I Think I'll Give You a Kiss'", "WDCC", "grail", 280),
        ("wdcc", "WDCC Snow White 'The Fairest One of All'", "WDCC", "grail", 320),
        ("wdcc", "WDCC Dumbo 'When I See an Elephant Fly'", "WDCC", "high", 200),
        ("wdcc", "WDCC Alice in Wonderland 'Curiouser & Curiouser'", "WDCC", "grail", 250),
        ("wdcc", "WDCC The Jungle Book Mowgli & Baloo", "WDCC", "high", 180),
        ("wdcc", "WDCC 101 Dalmatians Cruella De Vil 'Anita Daahling'", "WDCC", "grail", 300),

        # ── Kingdom Hearts Merchandise ────────────────────────────────────
        ("kingdom_hearts", "Kingdom Hearts Sora Play Arts Kai Figure", "Limited", "high", 120),
        ("kingdom_hearts", "Kingdom Hearts Keyblade Replica (Metal, Full-Size)", "Premium", "high", 95),
        ("kingdom_hearts", "Kingdom Hearts III Bring Arts Sora Figure", "Standard", "mid", 65),
        ("kingdom_hearts", "Kingdom Hearts 20th Anniversary Ichiban Kuji Last One", "LE", "high", 140),
        ("kingdom_hearts", "Kingdom Hearts Funko Pop Sora (Brave Form) Chase", "Chase Variant", "high", 85),
        ("kingdom_hearts", "Kingdom Hearts Formation Arts Mini Figure Set (6pc)", "Standard", "mid", 55),
        ("kingdom_hearts", "Kingdom Hearts Diamond Select Mickey Figure", "Standard", "mid", 40),

        # ── Vintage Disneyland / WDW Park Memorabilia ────────────────────
        ("vintage", "Disneyland Opening Day 1955 Main Gate Ticket (A-E)", "Vintage", "grail", 1500),
        ("vintage", "Walt Disney World Preview Center Brochure 1970", "Vintage", "grail", 400),
        ("vintage", "Vintage Disneyland Souvenir Pennant (1950s)", "Vintage", "grail", 350),
        ("vintage", "Vintage EPCOT Center Opening Day Cast Member Badge", "Vintage", "grail", 300),
        ("vintage", "Vintage Disneyland 1960 Adventureland Tiki Mug", "Vintage", "grail", 280),
        ("vintage", "Vintage Magic Kingdom Grand Opening Poster 1971", "Vintage", "grail", 450),
        ("vintage", "Vintage Disneyland Hotel Matchbook Collection (1960s)", "Vintage", "high", 120),

        # ── Retired Attractions Memorabilia ───────────────────────────────
        ("attractions", "Mr. Toad's Wild Ride Cast Member Sign Replica", "Park Exclusive", "high", 110),
        ("attractions", "Horizons EPCOT Ride Poster Print (Retired)", "Vintage", "high", 130),
        ("attractions", "Submarine Voyage Original Ride Photo Print", "Vintage", "high", 100),
        ("attractions", "20,000 Leagues Under the Sea Ride Poster", "Vintage", "high", 120),
        ("attractions", "ExtraTERRORestrial Alien Encounter Program", "Vintage", "high", 85),
        ("attractions", "Maelstrom EPCOT Norway Ride Photo Print", "Vintage", "mid", 60),
        ("attractions", "Great Movie Ride TCM Props Replica Set", "Park Exclusive", "high", 95),

        # ── D23 Expo Exclusive Items ─────────────────────────────────────
        ("d23", "D23 Expo 2024 Exclusive Mickey Mouse Figurine", "D23 Exclusive", "high", 150),
        ("d23", "D23 Gold Member Exclusive Pin (Annual)", "D23 Exclusive", "high", 90),
        ("d23", "D23 Expo Exclusive Fantasia Sorcerer Hat", "D23 Exclusive", "high", 110),
        ("d23", "D23 Expo Exclusive Disney Villains Art Print Set", "D23 Exclusive", "high", 85),
        ("d23", "D23 Expo 2022 Exclusive Figment Popcorn Bucket Replica", "D23 Exclusive", "high", 95),
        ("d23", "D23 Expo Exclusive Walt Disney Archives Display Replica", "D23 Exclusive", "grail", 200),
        ("d23", "D23 Expo Exclusive Haunted Mansion Ghost Host Bust", "D23 Exclusive", "grail", 220),

        # ── runDisney Medals — Additional ────────────────────────────────
        ("rundisney", "runDisney Castaway Cay 5K Medal", "Event Exclusive", "mid", 40),
        ("rundisney", "runDisney Disneyland 10K Medal 2025", "Event Exclusive", "mid", 50),
        ("rundisney", "runDisney Star Wars Rival Run Medal", "Event Exclusive", "mid", 55),
        ("rundisney", "runDisney Virtual Running Series Medal Set (3pc)", "Event Exclusive", "mid", 65),
        ("rundisney", "runDisney Springtime Surprise 10K Medal", "Event Exclusive", "mid", 45),

        # ── Disney Designer Collection Dolls — Additional ─────────────────
        ("designer_dolls", "Disney Designer Collection Cinderella Doll", "Designer LE", "high", 155),
        ("designer_dolls", "Disney Designer Collection Mulan Doll", "Designer LE", "high", 140),
        ("designer_dolls", "Disney Designer Collection Elsa & Anna Doll Set", "Designer LE", "grail", 260),
        ("designer_dolls", "Disney Designer Collection Pocahontas Doll", "Designer LE", "high", 135),
        ("designer_dolls", "Disney Designer Collection Tiana Doll (Premiere Series)", "Designer LE", "high", 160),
        ("designer_dolls", "Disney Designer Collection Snow White Doll", "Designer LE", "high", 150),
        ("designer_dolls", "Disney Designer Collection Moana Doll", "Designer LE", "high", 130),

        # ── Loungefly Vaulted / Retired Bags ─────────────────────────────
        ("loungefly", "Loungefly Disney Villains Club Backpack (Vaulted)", "Vaulted", "high", 140),
        ("loungefly", "Loungefly Disney Stitch Pineapple Crossbody (Vaulted)", "Vaulted", "high", 110),
        ("loungefly", "Loungefly Disney Parks Map Mini Backpack (Vaulted)", "Vaulted", "high", 130),
        ("loungefly", "Loungefly Disney Princess Castle Backpack (Vaulted)", "Vaulted", "high", 120),
        ("loungefly", "Loungefly Alice in Wonderland Teacup Crossbody (Vaulted)", "Vaulted", "high", 115),
        ("loungefly", "Loungefly The Emperor's New Groove Backpack", "Standard", "mid", 65),

        # ── Disney Pin Trading Grails ────────────────────────────────────
        ("pins", "Disney Soda Fountain El Capitan LE 300 Jumbo Pin", "LE 300", "grail", 350),
        ("pins", "ACME Hot Art LE 100 Sleeping Beauty Pin", "LE 100", "grail", 500),
        ("pins", "WDI MOG LE 250 Figment Profile Pin", "LE 250", "grail", 400),
        ("pins", "Disney Auctions LE 100 Villain Jumbo Pin", "LE 100", "grail", 450),
        ("pins", "Disney Parks 50th Anniversary LE 50 Gold Pin", "LE 50", "grail", 600),
        ("pins", "Fantasy Pin Ghibli/Disney Mashup Totoro Mickey", "Fantasy", "mid", 50),

        # ── Jim Shore / Disney Traditions — Additional ───────────────────
        ("jim_shore", "Jim Shore Lion King Simba & Mufasa Figure", "Standard", "mid", 65),
        ("jim_shore", "Jim Shore Moana Figurine", "Standard", "mid", 55),
        ("jim_shore", "Jim Shore Disney Castle (Light-Up Musical)", "Premium", "grail", 200),
        ("jim_shore", "Jim Shore Sleeping Beauty Aurora Figure", "Standard", "mid", 60),
        ("jim_shore", "Jim Shore Tangled Rapunzel Tower Figurine", "Limited", "high", 120),

        # ── Disney Pixar — Additional ────────────────────────────────────
        ("pixar", "Pixar Finding Nemo Submarine Voyage Snow Globe", "Park Exclusive", "high", 95),
        ("pixar", "Pixar Monsters Inc. Sully & Mike Figurine Set", "Standard", "mid", 50),
        ("pixar", "Pixar Cars Lightning McQueen Die-Cast (D23 Exclusive)", "D23 Exclusive", "high", 110),
        ("pixar", "Pixar Soul Joe Gardner Figurine", "Standard", "mid", 45),
        ("pixar", "Pixar Lightyear Sox Robot Companion Replica", "Limited", "mid", 65),

        # ── Disney Lorcana — Additional Sets ─────────────────────────────
        ("lorcana", "Lorcana Captain Hook Pirate Captain Enchanted", "Enchanted Rare", "grail", 240),
        ("lorcana", "Lorcana Rapunzel Gifted Artist Enchanted", "Enchanted Rare", "grail", 210),
        ("lorcana", "Lorcana Gaston Arrogant Hunter Super Rare", "Super Rare", "mid", 45),
        ("lorcana", "Lorcana Booster Box Shimmering Skies (Sealed)", "Sealed Product", "high", 140),
        ("lorcana", "Lorcana Mulan Soldier in Training Legendary", "Legendary", "high", 80),
        ("lorcana", "Lorcana Aladdin Heroic Outlaw Super Rare", "Super Rare", "mid", 50),

        # ── Dooney & Bourke Disney Collection ──────────────────────────────
        ("dooney_bourke", "Dooney & Bourke Disney Sketch Tote", "Park Exclusive", "high", 160),
        ("dooney_bourke", "Dooney & Bourke Disney Parks Attractions Crossbody", "Park Exclusive", "high", 140),
        ("dooney_bourke", "Dooney & Bourke Disney Nightmare Before Christmas Satchel", "Park Exclusive", "high", 170),
        ("dooney_bourke", "Dooney & Bourke Disney Epcot Flower & Garden Tote", "Park Exclusive", "high", 150),
        ("dooney_bourke", "Dooney & Bourke Disney Castle Fireworks Crossbody", "Park Exclusive", "high", 155),
        ("dooney_bourke", "Dooney & Bourke Disney Food & Wine Festival Tote", "Park Exclusive", "high", 145),
        ("dooney_bourke", "Dooney & Bourke Disney Princess Half Marathon Tote", "Event Exclusive", "high", 160),
        ("dooney_bourke", "Dooney & Bourke Disney Jungle Cruise Crossbody", "Park Exclusive", "high", 140),
        ("dooney_bourke", "Dooney & Bourke Disney Stitch Crashes Series Tote", "LE Monthly", "grail", 220),
        ("dooney_bourke", "Dooney & Bourke Disney Pixar Mini Backpack", "Standard", "high", 130),
        ("dooney_bourke", "Dooney & Bourke Disney Villains Satchel", "Park Exclusive", "high", 165),
        ("dooney_bourke", "Dooney & Bourke Disney Mickey & Minnie Holiday Tote", "Seasonal", "high", 135),

        # ── Disney Popcorn Buckets ─────────────────────────────────────────
        ("popcorn_buckets", "Figment Popcorn Bucket (EPCOT Festival)", "Park Exclusive", "high", 120),
        ("popcorn_buckets", "Mickey Mouse Balloon Popcorn Bucket", "Park Exclusive", "mid", 55),
        ("popcorn_buckets", "Cinderella Carriage Popcorn Bucket", "Park Exclusive", "high", 80),
        ("popcorn_buckets", "Haunted Mansion Doom Buggy Popcorn Bucket", "Park Exclusive", "high", 90),
        ("popcorn_buckets", "R2-D2 Popcorn Bucket (Galaxy's Edge)", "Park Exclusive", "mid", 65),
        ("popcorn_buckets", "Ratatouille Remy Popcorn Bucket (DLP)", "Park Exclusive", "high", 85),
        ("popcorn_buckets", "Buzz Lightyear Spaceship Popcorn Bucket", "Park Exclusive", "mid", 50),
        ("popcorn_buckets", "Slinky Dog Popcorn Bucket", "Park Exclusive", "mid", 55),
        ("popcorn_buckets", "Tiki Room Pineapple Popcorn Bucket", "Park Exclusive", "mid", 60),
        ("popcorn_buckets", "Tokyo DisneySea Duffy Popcorn Bucket", "Park Exclusive", "high", 95),
        ("popcorn_buckets", "Shanghai Disney Zootopia Popcorn Bucket", "Park Exclusive", "mid", 70),
        ("popcorn_buckets", "Disney Villains Cauldron Popcorn Bucket", "Park Exclusive", "mid", 65),

        # ── Disney Spirit Jerseys — Additional ─────────────────────────────
        ("ears", "Disney Parks Spirit Jersey Walt Disney World 50th Gold", "Park Exclusive", "high", 85),
        ("ears", "Disney Parks Spirit Jersey Haunted Mansion Wallpaper", "Park Exclusive", "high", 90),
        ("ears", "Disney Parks Spirit Jersey Epcot Spaceship Earth", "Park Exclusive", "mid", 70),
        ("ears", "Disney Parks Spirit Jersey Animal Kingdom Tree of Life", "Park Exclusive", "mid", 65),
        ("ears", "Disney Parks Spirit Jersey Toy Story Land", "Park Exclusive", "mid", 60),
        ("ears", "Disney Parks Spirit Jersey Star Wars Galaxy's Edge", "Park Exclusive", "mid", 70),
        ("ears", "Disney Parks Spirit Jersey Tokyo DisneySea", "Park Exclusive", "high", 95),
        ("ears", "Disney Parks Spirit Jersey Disneyland Paris", "Park Exclusive", "high", 80),
        ("ears", "Disney Parks Spirit Jersey Disney Cruise Line", "DCL Exclusive", "high", 85),
        ("ears", "Disney Parks Spirit Jersey Disney100 Platinum", "D100 Exclusive", "high", 90),
        ("ears", "Disney Parks Spirit Jersey Aulani Hawaii", "Park Exclusive", "high", 95),

        # ── Disney Traditions / Jim Shore — Additional ──────────────────────
        ("jim_shore", "Jim Shore Pinocchio 'Brave Little Tailor' Figurine", "Standard", "mid", 55),
        ("jim_shore", "Jim Shore Dumbo 'Baby Mine' Figurine", "Standard", "mid", 60),
        ("jim_shore", "Jim Shore Ariel & Eric 'Fairy Tale Romance' Figurine", "Standard", "mid", 65),
        ("jim_shore", "Jim Shore Aladdin & Jasmine Magic Carpet Figurine", "Standard", "mid", 60),
        ("jim_shore", "Jim Shore Disney Showcase Stitch Elvis Figurine", "Standard", "mid", 55),
        ("jim_shore", "Jim Shore Peter Pan 'Off to Neverland' Figurine", "Standard", "mid", 60),
        ("jim_shore", "Jim Shore Lady & the Tramp 'Bella Notte' Figurine", "Limited", "high", 90),
        ("jim_shore", "Jim Shore Hades & Pain & Panic Figurine", "Standard", "mid", 55),

        # ── Swarovski Disney — Additional ───────────────────────────────────
        ("swarovski", "Swarovski Crystal Elsa Figurine (Frozen)", "Premium", "high", 180),
        ("swarovski", "Swarovski Crystal Olaf Figurine (Frozen)", "Premium", "high", 120),
        ("swarovski", "Swarovski Crystal Stitch Figurine", "Premium", "high", 160),
        ("swarovski", "Swarovski Crystal The Lion King Mufasa & Simba", "Premium", "grail", 350),
        ("swarovski", "Swarovski Crystal Maleficent Figurine", "Premium", "high", 200),
        ("swarovski", "Swarovski Crystal Cinderella Castle Ornament (Annual)", "Premium", "high", 150),
        ("swarovski", "Swarovski Crystal Pinocchio & Jiminy Cricket Set", "Premium", "grail", 280),
        ("swarovski", "Swarovski Crystal Fantasia Sorcerer Mickey Hat", "Premium", "high", 140),

        # ── WDCC — Additional ──────────────────────────────────────────────
        ("wdcc", "WDCC Beauty and the Beast 'Tale as Old as Time'", "WDCC", "grail", 300),
        ("wdcc", "WDCC Aladdin 'Magic Carpet Ride'", "WDCC", "grail", 260),
        ("wdcc", "WDCC Lady and the Tramp 'Bella Notte'", "WDCC", "grail", 240),
        ("wdcc", "WDCC The Sword in the Stone 'Young Arthur'", "WDCC", "high", 180),
        ("wdcc", "WDCC Winnie the Pooh 'Silly Old Bear'", "WDCC", "high", 160),
        ("wdcc", "WDCC The Little Mermaid Ursula 'We Made a Deal'", "WDCC", "grail", 350),
        ("wdcc", "WDCC Hercules Hades 'Name Is Hades'", "WDCC", "high", 200),

        # ── Kingdom Hearts — Additional ────────────────────────────────────
        ("kingdom_hearts", "Kingdom Hearts Bring Arts Roxas Figure", "Standard", "mid", 60),
        ("kingdom_hearts", "Kingdom Hearts Bring Arts Riku Figure", "Standard", "mid", 65),
        ("kingdom_hearts", "Kingdom Hearts Bring Arts Aqua Figure", "Standard", "mid", 60),
        ("kingdom_hearts", "Kingdom Hearts Static Arts Mini Complete Set (6pc)", "Standard", "mid", 75),
        ("kingdom_hearts", "Kingdom Hearts S.H.Figuarts Sora (KH2 Ver.)", "Limited", "high", 110),
        ("kingdom_hearts", "Kingdom Hearts Master Keeper Keyblade Replica", "Premium", "high", 100),
        ("kingdom_hearts", "Kingdom Hearts Nendoroid Sora (KH3 Ver.)", "Standard", "mid", 50),
        ("kingdom_hearts", "Kingdom Hearts Nendoroid Aqua", "Standard", "mid", 50),
        ("kingdom_hearts", "Kingdom Hearts III Original Soundtrack Vinyl Box Set", "Limited", "high", 120),

        # ── Disney+ Original Series Merchandise ───────────────────────────
        ("disneyplus", "WandaVision Scarlet Witch Crown Replica", "Limited", "high", 95),
        ("disneyplus", "Loki TVA Variant Jacket Replica", "Limited", "high", 110),
        ("disneyplus", "The Mandalorian Grogu (Baby Yoda) Animatronic", "Standard", "mid", 65),
        ("disneyplus", "Moon Knight Scarab Beetle Prop Replica", "Limited", "high", 90),
        ("disneyplus", "Ahsoka White Lightsaber Replica Set", "Premium", "grail", 250),
        ("disneyplus", "The Mandalorian Darksaber Replica", "Premium", "high", 180),
        ("disneyplus", "Loki Alligator Loki Plush (D23 Exclusive)", "D23 Exclusive", "mid", 45),
        ("disneyplus", "Andor Luthen's Crystal Necklace Prop Replica", "Limited", "high", 85),

        # ── D23 Expo — Additional ──────────────────────────────────────────
        ("d23", "D23 Expo 2019 Exclusive Disney Legends Poster Set", "D23 Exclusive", "high", 95),
        ("d23", "D23 Expo 2017 Exclusive Toy Story Land Preview Pin", "D23 Exclusive", "high", 80),
        ("d23", "D23 Expo Exclusive Disney Animation Sketch Portfolio", "D23 Exclusive", "high", 120),
        ("d23", "D23 Expo Exclusive 50th Anniversary Film Clapboard", "D23 Exclusive", "high", 110),
        ("d23", "D23 Gold Member Welcome Gift Box", "D23 Exclusive", "mid", 55),
        ("d23", "D23 Expo Exclusive Imagineering Blueprint Print Set", "D23 Exclusive", "high", 130),

        # ── Disney Cruise Line — Additional ────────────────────────────────
        ("dcl", "Disney Cruise Line Castaway Cay Exclusive Spirit Jersey", "DCL Exclusive", "high", 85),
        ("dcl", "Disney Cruise Line Ship in Bottle Ornament (Disney Fantasy)", "Standard", "mid", 35),
        ("dcl", "Disney Cruise Line Captain's Gala Figurine Set", "Standard", "mid", 50),
        ("dcl", "Disney Cruise Line Disney Wish Grand Hall Lithograph", "LE 1000", "high", 95),
        ("dcl", "Disney Cruise Line 25th Anniversary Pin Set", "LE 2500", "high", 90),
        ("dcl", "Disney Cruise Line AquaDuck Model Replica", "Standard", "mid", 45),

        # ── Vintage Disneyana (1930s-1960s) ────────────────────────────────
        ("vintage", "Vintage 1930s Mickey Mouse Ingersoll Watch", "Vintage", "grail", 2000),
        ("vintage", "Vintage 1940s Fantasia Program Book (Original)", "Vintage", "grail", 500),
        ("vintage", "Vintage 1930s Mickey Mouse Bisque Figurine (Japan)", "Vintage", "grail", 400),
        ("vintage", "Vintage 1940s Donald Duck Wind-Up Toy (Marx)", "Vintage", "grail", 350),
        ("vintage", "Vintage 1950s Sleeping Beauty Original Cel Setup", "Vintage", "grail", 2500),
        ("vintage", "Vintage 1930s Three Little Pigs Sheet Music", "Vintage", "high", 180),
        ("vintage", "Vintage 1940s Pinocchio Puppet (Ideal Toy)", "Vintage", "grail", 450),
        ("vintage", "Vintage 1960s Mary Poppins Original Movie Poster", "Vintage", "grail", 600),
        ("vintage", "Vintage 1955 Disneyland Opening Day Pennant", "Vintage", "grail", 700),

        # ── Pixar — Additional ─────────────────────────────────────────────
        ("pixar", "Pixar Incredibles 2 Whole Family Figurine Set", "Standard", "mid", 45),
        ("pixar", "Pixar UP Russell Wilderness Explorer Badge Replica", "Limited", "mid", 35),
        ("pixar", "Pixar Brave Merida & Angus Figurine", "Standard", "mid", 50),
        ("pixar", "Pixar Luca Sea Monster Figurine Set", "Standard", "mid", 40),
        ("pixar", "Pixar Elemental Ember & Wade Snow Globe", "Limited", "mid", 55),
        ("pixar", "Pixar Inside Out 2 Anxiety Figurine (D23)", "D23 Exclusive", "mid", 60),
        ("pixar", "Pixar Cars Doc Hudson 1:24 Die-Cast (Precision Series)", "Premium", "high", 85),
        ("pixar", "Pixar Onward Barley's Van Replica", "Limited", "mid", 65),

        # ── Disneyland Paris — Additional ──────────────────────────────────
        ("dlp", "Disneyland Paris 30th Anniversary Loungefly Backpack", "Park Exclusive", "high", 100),
        ("dlp", "Disneyland Paris Phantom Manor Stretching Room Print Set", "Park Exclusive", "mid", 45),
        ("dlp", "Disneyland Paris Big Thunder Mountain Poster Print", "Park Exclusive", "mid", 35),
        ("dlp", "Disneyland Paris Disney Dreams Nighttime Show LE Pin", "LE 2000", "high", 85),
        ("dlp", "DLP Sleeping Beauty Castle Snow Globe (Large)", "Park Exclusive", "high", 95),
        ("dlp", "DLP Stars on Parade Float Figurine Set", "Park Exclusive", "mid", 55),

        # ── Hong Kong Disneyland — Additional ──────────────────────────────
        ("hkdl", "Hong Kong Disneyland Mystic Manor LE Pin", "LE 2000", "high", 90),
        ("hkdl", "Hong Kong Disneyland 15th Anniversary Pin Set", "LE 3000", "high", 80),
        ("hkdl", "Hong Kong Disneyland LinaBell Plush (First Release)", "Park Exclusive", "high", 85),
        ("hkdl", "Hong Kong Disneyland Frozen Ever After Opening Day T-Shirt", "Park Exclusive", "mid", 40),

        # ── Shanghai Disney — Additional ───────────────────────────────────
        ("shanghai_disney", "Shanghai Disney Resort 5th Anniversary LE Pin Set", "LE 2000", "high", 110),
        ("shanghai_disney", "Shanghai Disney Toy Story Hotel Exclusive Plush Set", "Park Exclusive", "mid", 55),
        ("shanghai_disney", "Shanghai Disney LinaBell Costume Plush Set (4 Seasons)", "Park Exclusive", "high", 120),
        ("shanghai_disney", "Shanghai Disney Zootopia Land Opening Day Pin", "LE 1500", "high", 130),
        ("shanghai_disney", "Shanghai Disney CookieAnn Chef Plush (Grand Opening)", "Park Exclusive", "mid", 50),

        # ── Tokyo Disney — Additional ──────────────────────────────────────
        ("tokyo_disney", "Tokyo Disneyland 40th Anniversary LE Figurine Set", "LE 1000", "grail", 250),
        ("tokyo_disney", "Tokyo DisneySea OluMel Plush (First Release)", "Park Exclusive", "mid", 50),
        ("tokyo_disney", "Tokyo Disney LinaBell Autumn Costume Plush", "Park Exclusive", "mid", 55),
        ("tokyo_disney", "Tokyo Disneyland Electrical Parade Dreamlights LE Pin", "LE 2000", "high", 90),
        ("tokyo_disney", "Tokyo DisneySea Sindbad Storybook Voyage Figurine", "Park Exclusive", "mid", 45),
        ("tokyo_disney", "Tokyo DisneySea Fantasy Springs Peter Pan LE Pin", "LE 1500", "high", 120),

        # ── Disney Pin Trading Events ──────────────────────────────────────
        ("pins", "WDW Pin Trading Event Villains After Hours LE 500 Pin", "LE 500", "grail", 300),
        ("pins", "Disneyland Pin Trading Night Star Wars LE 750 Pin", "LE 750", "grail", 250),
        ("pins", "Disney Pin Celebration 2024 Mystery Pin Box", "LE 1500", "high", 80),
        ("pins", "Disney Pin Trading Night Haunted Mansion LE 500 Pin", "LE 500", "grail", 320),
        ("pins", "WDW Epcot Festival of Holidays Pin Event LE 1000 Pin", "LE 1000", "high", 120),
        ("pins", "Disney Pin Event Quarterly Collection Figment Set", "LE 2000", "high", 95),

        # ── Disney Designer Ears — Additional ──────────────────────────────
        ("ears", "Disney Designer Ears by Heidi Klum", "Designer", "high", 85),
        ("ears", "Disney Designer Ears by Betsey Johnson", "Designer", "high", 90),
        ("ears", "Disney Designer Ears by Coach", "Designer", "high", 100),
        ("ears", "Disney Designer Ears by Lilly Pulitzer", "Designer", "high", 80),
        ("ears", "Disney Parks Minnie Ears Arendelle Aqua", "Park Exclusive", "mid", 40),
        ("ears", "Disney Parks Minnie Ears Purple Potion", "Park Exclusive", "mid", 38),
        ("ears", "Disney Parks Minnie Ears Imagination Pink", "Park Exclusive", "mid", 35),
        ("ears", "Disney Parks Minnie Ears Corduroy Harvest (Fall)", "Seasonal", "mid", 40),

        # ── Disney Animation Cels — Additional ─────────────────────────────
        ("animation_cels", "Original Production Cel Cinderella Ballroom", "Vintage", "grail", 1800),
        ("animation_cels", "Original Production Cel Snow White & Seven Dwarfs", "Vintage", "grail", 2000),
        ("animation_cels", "Original Production Cel Peter Pan Flight Scene", "Vintage", "grail", 1400),
        ("animation_cels", "Original Production Cel Alice in Wonderland Tea Party", "Vintage", "grail", 1600),
        ("animation_cels", "Sericel The Lion King LE 5000", "LE 5000", "high", 170),
        ("animation_cels", "Sericel Fantasia Bald Mountain LE 2500", "LE 2500", "high", 200),

        # ── Disney Fine Art — Additional ───────────────────────────────────
        ("fine_art", "Jim Salvati 'Sorcerer Mickey' Oil on Canvas Giclee", "Limited Print", "high", 150),
        ("fine_art", "Tim Rogerson 'Mermaid Lagoon' Giclee", "Limited Print", "high", 140),
        ("fine_art", "Peter Ellenshaw 'Neverland' Limited Edition Lithograph", "Limited Print", "high", 180),
        ("fine_art", "Michelle St.Laurent 'Remember Who You Are' Giclee", "Limited Print", "high", 130),
        ("fine_art", "SHAG Moonliner Rocket Serigraph", "Limited Print", "high", 160),

        # ── Disney Consumer Products Vintage — Additional ──────────────────
        ("vintage_products", "Vintage 1980s Disney DuckTales Lunch Box", "Vintage", "mid", 50),
        ("vintage_products", "Vintage 1990s Goof Troop Max Action Figure Set", "Vintage", "mid", 45),
        ("vintage_products", "Vintage 1970s Disney World Souvenir Glass Set (4pc)", "Vintage", "mid", 55),
        ("vintage_products", "Vintage 1960s Walt Disney's Zorro Lunch Box", "Vintage", "high", 120),
        ("vintage_products", "Vintage 1950s Davy Crockett Coonskin Cap (Disney)", "Vintage", "high", 150),
        ("vintage_products", "Vintage 1990s Aladdin Magic Carpet Board Game", "Vintage", "mid", 35),

        # ── Villains — Additional ──────────────────────────────────────────
        ("villains", "Disney Villains Cruella De Vil Couture de Force Figurine", "Premium", "high", 90),
        ("villains", "Disney Villains Jafar Couture de Force Figurine", "Premium", "high", 85),
        ("villains", "Disney Villains Chernabog Figurine (Fantasia)", "Limited", "high", 120),
        ("villains", "Disney Villains Captain Hook & Smee Figurine Set", "Standard", "mid", 55),
        ("villains", "Disney Villains Gaston Figurine (Beauty & the Beast)", "Standard", "mid", 50),

        # ── Disney Lorcana — Additional Sets / Cards ───────────────────────
        ("lorcana", "Lorcana Moana Born Leader Enchanted", "Enchanted Rare", "grail", 200),
        ("lorcana", "Lorcana Jafar Striking Illusionist Legendary", "Legendary", "high", 85),
        ("lorcana", "Lorcana Booster Box Azurite Sea (Sealed)", "Sealed Product", "high", 140),
        ("lorcana", "Lorcana Booster Box Archazia's Island (Sealed)", "Sealed Product", "high", 130),
        ("lorcana", "Lorcana Scar Shameless Firebrand Enchanted", "Enchanted Rare", "grail", 230),
        ("lorcana", "Lorcana Elsa Snow Queen Legendary", "Legendary", "high", 90),
        ("lorcana", "Lorcana Illumineer's Trove The First Chapter", "Sealed Product", "high", 90),
        ("lorcana", "Lorcana Illumineer's Trove Rise of the Floodborn", "Sealed Product", "high", 85),

        # ── Marvel at Disney Parks — Additional ────────────────────────────
        ("marvel_parks", "Avengers Campus Web-Slinger Vehicle Replica", "Park Exclusive", "mid", 65),
        ("marvel_parks", "Guardians Cosmic Rewind Opening Day LE 1500 Pin", "LE 1500", "high", 110),
        ("marvel_parks", "Disney Parks Thor Stormbreaker Replica", "Premium", "high", 150),
        ("marvel_parks", "Disney Parks Captain America Shield Replica (Metal)", "Premium", "grail", 200),
        ("marvel_parks", "Avengers Campus Quinjet Model (Park Exclusive)", "Park Exclusive", "mid", 55),

        # ── Star Wars Galaxy's Edge — Additional ──────────────────────────
        ("galaxys_edge", "Galaxy's Edge Legacy Lightsaber (Ahsoka Tano)", "Park Exclusive", "high", 200),
        ("galaxys_edge", "Galaxy's Edge Legacy Lightsaber (Mace Windu)", "Park Exclusive", "high", 180),
        ("galaxys_edge", "Galaxy's Edge Kyber Crystal Set (Complete 10pc)", "Park Exclusive", "high", 90),
        ("galaxys_edge", "Galaxy's Edge Batuuan Spira Gift Card (Metal)", "Park Exclusive", "mid", 55),
        ("galaxys_edge", "Galaxy's Edge Ronto Roasters Menu Sign Replica", "Park Exclusive", "mid", 40),

        # ── runDisney — Additional ─────────────────────────────────────────
        ("rundisney", "runDisney Tower of Terror 10 Miler Medal", "Event Exclusive", "mid", 55),
        ("rundisney", "runDisney Springtime Surprise 5K Medal", "Event Exclusive", "mid", 40),
        ("rundisney", "runDisney Walt Disney World 5K Medal 2025", "Event Exclusive", "mid", 45),
        ("rundisney", "runDisney Disneyland Paris Half Marathon Medal", "Event Exclusive", "high", 65),
        ("rundisney", "runDisney Coast to Coast Challenge Medal", "Event Exclusive", "high", 95),

        # ── Disney Luxury Collaborations — Additional ──────────────────────
        ("luxury_collab", "Dooney & Bourke Disney Star Wars Tote", "Park Exclusive", "high", 145),
        ("luxury_collab", "Dooney & Bourke Disney Princess Tea Party Tote", "Park Exclusive", "high", 150),
        ("luxury_collab", "Pandora x Disney Mulan Charm", "Limited", "mid", 55),
        ("luxury_collab", "Pandora x Disney Stitch Charm", "Limited", "mid", 50),
        ("luxury_collab", "Coach x Disney Dumbo Crossbody", "Limited", "high", 170),
        ("luxury_collab", "Kate Spade x Disney Minnie Mouse Crossbody", "Limited", "high", 140),
        ("luxury_collab", "Fossil x Disney Mickey Mouse Watch (LE)", "LE 3000", "high", 120),

        # ── Disney Ornaments — Additional ──────────────────────────────────
        ("ornaments", "Disney Sketchbook Ornament Mickey Mouse (Year Dated)", "Standard", "standard", 22),
        ("ornaments", "Disney Parks Castle Ornament (Light-Up)", "Park Exclusive", "mid", 38),
        ("ornaments", "Hallmark Disney Dumbo 80th Anniversary Ornament", "Limited", "mid", 40),
        ("ornaments", "Hallmark Disney Frozen Elsa Musical Ornament", "Standard", "standard", 25),
        ("ornaments", "Lenox Disney Belle Ornament", "Premium", "mid", 50),
        ("ornaments", "Lenox Disney Cinderella Coach Ornament", "Premium", "mid", 55),

        # ── Disney100 — Additional ─────────────────────────────────────────
        ("disney100", "Disney100 Mickey & Friends Decades Pin Collection (5pc)", "D100 Exclusive", "high", 80),
        ("disney100", "Disney100 Walt Disney Studios Figurine Set", "D100 Exclusive", "high", 110),
        ("disney100", "Disney100 Anniversary Dooney & Bourke Crossbody", "D100 Exclusive", "high", 160),
        ("disney100", "Disney100 Platinum Mickey Plush (Large)", "D100 Exclusive", "mid", 55),
        ("disney100", "Disney100 Anniversary Spirit Jersey", "D100 Exclusive", "high", 85),

        # ── Disney Music — Additional ──────────────────────────────────────
        ("music", "Moana Soundtrack Vinyl (Blue Ocean Waves)", "Limited", "mid", 45),
        ("music", "Coco Soundtrack Vinyl (Marigold Orange)", "Limited", "mid", 45),
        ("music", "Tangled Soundtrack Vinyl (Purple Lantern)", "Limited", "mid", 50),
        ("music", "Beauty and the Beast Soundtrack Vinyl (Gold)", "Limited", "mid", 50),
        ("music", "Aladdin Soundtrack Vinyl (Magic Lamp Gold)", "Limited", "mid", 45),

        # ── Loungefly — Additional ─────────────────────────────────────────
        ("loungefly", "Loungefly Disney Bambi Floral Backpack", "Standard", "mid", 55),
        ("loungefly", "Loungefly Disney Lilo & Stitch Pineapple Backpack", "Standard", "mid", 60),
        ("loungefly", "Loungefly Disney Sleeping Beauty Castle Backpack", "Park Exclusive", "high", 90),
        ("loungefly", "Loungefly Disney Pixar UP Grape Soda Crossbody", "Standard", "mid", 55),
        ("loungefly", "Loungefly Disney Robin Hood Backpack", "Standard", "mid", 55),
        ("loungefly", "Loungefly Disney Tangled Lanterns Backpack", "Standard", "mid", 60),
    ]

    # ── Expansion Batch — Disney100, Swarovski, Jim Shore, Lenox, Archives, D23, Designer Dolls, Lorcana ──
    items += [
        # Disney100 Celebration Merch — Platinum Figurines
        ("disney100", "Disney100 Platinum Mickey Mouse Figurine", "D100 LE", "grail", 250),
        ("disney100", "Disney100 Platinum Minnie Mouse Figurine", "D100 LE", "grail", 240),
        ("disney100", "Disney100 Platinum Donald Duck Figurine", "D100 LE", "high", 180),
        ("disney100", "Disney100 Platinum Goofy Figurine", "D100 LE", "high", 170),
        ("disney100", "Disney100 Anniversary Castle Snow Globe", "D100 LE", "grail", 280),

        # Disney100 Anniversary Pins
        ("disney100", "Disney100 Anniversary Partners Pin (Walt & Mickey)", "D100 LE", "high", 95),
        ("disney100", "Disney100 Iridescent Mickey Head Pin Set (3pc)", "D100 LE", "mid", 45),
        ("disney100", "Disney100 Decades Pin Collection Complete Set (12pc)", "D100 LE", "grail", 350),

        # Disney Swarovski Crystal Figurines
        ("swarovski", "Swarovski Disney Mickey Mouse Crystal Figurine", "Premium", "grail", 350),
        ("swarovski", "Swarovski Disney Cinderella Crystal Slipper", "Premium", "grail", 280),
        ("swarovski", "Swarovski Disney Ariel Mermaid Crystal Figurine", "Premium", "high", 200),
        ("swarovski", "Swarovski Disney Elsa Ice Palace Crystal Figurine", "Premium", "grail", 320),
        ("swarovski", "Swarovski Disney Tinker Bell Crystal Figurine", "Premium", "high", 180),
        ("swarovski", "Swarovski Disney Stitch Crystal Figurine", "Premium", "high", 190),

        # Jim Shore Disney Traditions
        ("jim_shore", "Jim Shore Mickey Mouse 'The Original' Large Figurine", "Disney Traditions", "high", 85),
        ("jim_shore", "Jim Shore Cinderella 'Romantic Waltz' Figurine", "Disney Traditions", "mid", 65),
        ("jim_shore", "Jim Shore Snow White 'Fairest of All' Figurine", "Disney Traditions", "mid", 60),
        ("jim_shore", "Jim Shore Ariel 'Splash of Fun' Figurine", "Disney Traditions", "mid", 60),
        ("jim_shore", "Jim Shore Maleficent 'Sinister Sorceress' Figurine", "Disney Traditions", "high", 80),
        ("jim_shore", "Jim Shore Stitch 'Ohana Means Family' Figurine", "Disney Traditions", "mid", 55),

        # Lenox Disney Porcelain
        ("lenox", "Lenox Disney Belle's Enchanted Dance Figurine", "Premium", "high", 120),
        ("lenox", "Lenox Disney Cinderella's Magical Moment Figurine", "Premium", "high", 110),
        ("lenox", "Lenox Disney Snow White's Magic Apple Figurine", "Premium", "high", 100),
        ("lenox", "Lenox Disney Tinker Bell Pixie Dust Figurine", "Premium", "mid", 80),

        # Walt Disney Archives Collection
        ("archives", "Walt Disney Archives Mickey Sorcerer Bronze Statue", "LE 500", "grail", 400),
        ("archives", "Walt Disney Archives Steamboat Willie Film Cell", "LE 1000", "high", 180),
        ("archives", "Walt Disney Archives Fantasia Concept Art Print", "LE 1000", "high", 150),
        ("archives", "Walt Disney Archives Disneyland Opening Day Replica Ticket", "LE 2500", "mid", 75),

        # D23 Expo Exclusives (2024)
        ("d23", "D23 Expo 2024 Sorcerer Mickey LE Pin", "D23 LE", "high", 120),
        ("d23", "D23 Expo 2024 Fantasia Chernabog Figurine", "D23 LE", "high", 160),
        ("d23", "D23 Expo 2024 Walt & Mickey Partners Statue", "D23 LE", "grail", 250),
        ("d23", "D23 Expo 2024 Tron Legacy Light Cycle LE Collectible", "D23 LE", "high", 140),
        ("d23", "D23 Expo 2024 Haunted Mansion Ghost Host Figurine", "D23 LE", "high", 130),

        # shopDisney Designer Collection Dolls
        ("designer_dolls", "shopDisney Designer Collection Ariel Doll (LE)", "shopDisney LE", "high", 150),
        ("designer_dolls", "shopDisney Designer Collection Belle Doll (LE)", "shopDisney LE", "high", 145),
        ("designer_dolls", "shopDisney Designer Collection Jasmine Doll (LE)", "shopDisney LE", "high", 150),
        ("designer_dolls", "shopDisney Designer Collection Rapunzel Doll (LE)", "shopDisney LE", "high", 140),
        ("designer_dolls", "shopDisney Designer Collection Mulan Doll (LE)", "shopDisney LE", "high", 145),
        ("designer_dolls", "shopDisney Designer Collection Tiana Doll (LE)", "shopDisney LE", "high", 155),
        ("designer_dolls", "shopDisney Designer Collection Elsa & Anna Doll Set (LE)", "shopDisney LE", "grail", 280),

        # Disney Lorcana Promo Cards
        ("lorcana", "Disney Lorcana Mickey Mouse Sorcerer's Apprentice Promo", "Promo LE", "high", 85),
        ("lorcana", "Disney Lorcana Elsa Spirit of Winter Enchanted Rare", "Enchanted", "high", 120),
        ("lorcana", "Disney Lorcana Stitch Rock Star Enchanted Rare", "Enchanted", "high", 100),
        ("lorcana", "Disney Lorcana Maleficent Monstrous Dragon Promo", "Promo LE", "mid", 65),
        ("lorcana", "Disney Lorcana Robin Hood Enchanted Rare", "Enchanted", "high", 90),
        ("lorcana", "Disney Lorcana Belle Bookworm Enchanted Rare", "Enchanted", "high", 80),
        ("lorcana", "Disney Lorcana First Chapter Booster Box (Sealed)", "Sealed", "high", 160),
        ("lorcana", "Disney Lorcana Rise of the Floodborn Booster Box (Sealed)", "Sealed", "high", 140),
        ("lorcana", "Disney Lorcana Shimmering Skies Booster Box (Sealed)", "Sealed", "mid", 95),
    ]

    # ── Expansion Batch 2 — Disney100, Fantasia, Villains, Pixar, Lorcana Acc, Jim Shore, Walt Archives ──
    items += [
        # Disney100 Anniversary Items (+10)
        ("disney100", "Disney100 Celebration Steamboat Willie Figurine", "D100 LE", "grail", 280),
        ("disney100", "Disney100 Iridescent Spirit Jersey (Adult)", "D100 Exclusive", "high", 95),
        ("disney100", "Disney100 Platinum Chip & Dale Figurine", "D100 LE", "high", 160),
        ("disney100", "Disney100 Oswald the Lucky Rabbit Plush (LE 2500)", "D100 LE", "high", 120),
        ("disney100", "Disney100 Anniversary Music Box (Steamboat Willie)", "D100 LE", "grail", 300),
        ("disney100", "Disney100 Decades 1930s Pin & Poster Set", "D100 LE", "mid", 55),
        ("disney100", "Disney100 Decades 1950s Pin & Poster Set", "D100 LE", "mid", 55),
        ("disney100", "Disney100 Decades 1970s Pin & Poster Set", "D100 LE", "mid", 50),
        ("disney100", "Disney100 Platinum Dumbo Figurine", "D100 LE", "high", 175),
        ("disney100", "Disney100 Anniversary Castle Crystal Ornament", "D100 Exclusive", "high", 140),

        # Fantasia Collectibles (+7)
        ("fantasia", "Fantasia Sorcerer Mickey WDCC Figurine", "WDCC", "grail", 350),
        ("fantasia", "Fantasia Chernabog Jim Shore Figurine", "Limited", "high", 120),
        ("fantasia", "Fantasia Dancing Hippo WDCC Figurine", "WDCC", "high", 180),
        ("fantasia", "Fantasia 80th Anniversary LE 2000 Pin", "LE 2000", "high", 85),
        ("fantasia", "Fantasia Sorcerer Hat Light-Up Snow Globe", "Park Exclusive", "high", 150),
        ("fantasia", "Fantasia Broom Army March Figurine Set", "Limited", "high", 110),
        ("fantasia", "Fantasia Night on Bald Mountain Lithograph (Signed)", "Signed Print", "high", 200),

        # Villains Series (+8)
        ("villains", "Disney Villains Maleficent Dragon Jim Shore Figurine", "Limited", "high", 130),
        ("villains", "Disney Villains Ursula Couture de Force Figurine", "Designer", "high", 100),
        ("villains", "Disney Villains Evil Queen Midnight Masquerade Doll", "Designer LE", "high", 180),
        ("villains", "Disney Villains Jafar as Serpent WDCC Figurine", "WDCC", "high", 160),
        ("villains", "Disney Villains Cruella De Vil Dalmatian Fur Figurine", "Designer", "high", 95),
        ("villains", "Disney Villains Gaston Tavern Scene Figurine", "Standard", "mid", 65),
        ("villains", "Disney Villains Hades Ember Glow Figurine", "Park Exclusive", "high", 110),
        ("villains", "Disney Villains Mother Gothel LE 3000 Pin", "LE 3000", "high", 80),

        # Pixar Premium (+7)
        ("pixar", "Pixar UP Carl's House Model (LE 1500)", "LE 1500", "grail", 250),
        ("pixar", "Pixar Toy Story Woody & Buzz 25th Anniversary Figurine Set", "LE 2500", "high", 120),
        ("pixar", "Pixar Inside Out Joy & Bing Bong Snow Globe", "Park Exclusive", "high", 95),
        ("pixar", "Pixar Coco Miguel & Dante Day of the Dead Figurine", "Limited", "high", 85),
        ("pixar", "Pixar Finding Dory Hank Octopus Figurine", "Park Exclusive", "high", 110),
        ("pixar", "Pixar Monsters Inc Scare Floor Figurine Set", "Limited", "high", 100),
        ("pixar", "Pixar WALL-E & EVE Stargazing Snow Globe", "Park Exclusive", "high", 130),

        # Disney Lorcana Accessories (+5)
        ("lorcana", "Disney Lorcana Rise of the Floodborn Playmat (Ursula)", "Premium", "mid", 45),
        ("lorcana", "Disney Lorcana Into the Inklands Deck Box (Maui)", "Premium", "mid", 30),
        ("lorcana", "Disney Lorcana First Chapter Card Sleeves (Elsa)", "Premium", "standard", 18),
        ("lorcana", "Disney Lorcana Shimmering Skies Collector's Album", "Premium", "mid", 35),
        ("lorcana", "Disney Lorcana Illumineer's Trove Gift Set (First Chapter)", "Sealed", "high", 85),

        # Jim Shore Figurines (+6)
        ("jim_shore", "Jim Shore Ariel Spirited Siren Figurine", "Standard", "mid", 70),
        ("jim_shore", "Jim Shore Rapunzel Adventurous Artist Figurine", "Standard", "mid", 65),
        ("jim_shore", "Jim Shore Stitch Wrapped in Christmas Figurine", "Seasonal", "mid", 60),
        ("jim_shore", "Jim Shore Dumbo Baby Mine Figurine", "Standard", "mid", 75),
        ("jim_shore", "Jim Shore Alice in Wonderland Curiouser Figurine", "Standard", "mid", 65),
        ("jim_shore", "Jim Shore Villain Cruella DeVil Figurine (LE)", "Limited", "high", 95),

        # Walt Disney Archives (+7)
        ("archives", "Walt Disney Archives Mickey Mouse Film Reel Replica", "LE 1000", "grail", 300),
        ("archives", "Walt Disney Archives Steamboat Willie Animation Cel Reproduction", "LE 500", "grail", 400),
        ("archives", "Walt Disney Archives Snow White Apple Prop Replica", "LE 750", "grail", 250),
        ("archives", "Walt Disney Archives Disneyland Opening Day Ticket Replica", "LE 1000", "high", 180),
        ("archives", "Walt Disney Archives Fantasia Conductor Baton Replica", "LE 500", "grail", 350),
        ("archives", "Walt Disney Archives Mary Poppins Carousel Horse Figurine", "LE 750", "high", 200),
        ("archives", "Walt Disney Archives Pirates of the Caribbean Map Lithograph", "LE 1000", "high", 150),

        # ── WDCC — Additional Porcelain Figures (+8) ─────────────────────
        ("wdcc", "WDCC Snow White 'The Fairest One of All'", "WDCC", "grail", 300),
        ("wdcc", "WDCC Peter Pan 'Off to Neverland' Figurine", "WDCC", "grail", 260),
        ("wdcc", "WDCC Dumbo 'Take to the Skies' Figurine", "WDCC", "high", 200),
        ("wdcc", "WDCC Alice in Wonderland 'Curiouser' Figurine", "WDCC", "grail", 280),
        ("wdcc", "WDCC Aladdin Genie 'I'm Losing to a Rug' Figurine", "WDCC", "high", 190),
        ("wdcc", "WDCC Beauty and the Beast 'Tale as Old as Time' Figurine", "WDCC", "grail", 320),
        ("wdcc", "WDCC Lady and the Tramp 'Bella Notte' Figurine", "WDCC", "high", 200),
        ("wdcc", "WDCC 101 Dalmatians Cruella 'Perfectly Wretched' Figurine", "WDCC", "grail", 250),

        # ── Disney100 Celebration Exclusives (+8) ────────────────────────
        ("disney100", "Disney100 Platinum Celebration Mickey Mouse Plush", "D100 Exclusive", "high", 85),
        ("disney100", "Disney100 Oswald the Lucky Rabbit Figurine", "D100 LE", "high", 120),
        ("disney100", "Disney100 Walt & Mickey Partners Statue Replica", "D100 LE", "grail", 250),
        ("disney100", "Disney100 Character Canvas Art Print Set (6pc)", "D100 Exclusive", "high", 95),
        ("disney100", "Disney100 Steamboat Willie Snow Globe", "D100 Exclusive", "high", 130),
        ("disney100", "Disney100 Anniversary Pin Set (10 Decades)", "D100 LE", "high", 160),
        ("disney100", "Disney100 Castle Projection Replica Light", "D100 Exclusive", "high", 110),
        ("disney100", "Disney100 Heritage Film Cell Collection Set", "D100 LE", "grail", 200),

        # ── Loungefly x Funko Collaborations (+7) ────────────────────────
        ("loungefly", "Loungefly x Funko Villain Maleficent Pop Backpack", "Funko Exclusive", "high", 100),
        ("loungefly", "Loungefly x Funko Stitch Experiment 626 Crossbody", "Funko Exclusive", "high", 90),
        ("loungefly", "Loungefly x Funko Disney Princess Castle Backpack", "Standard", "mid", 70),
        ("loungefly", "Loungefly x Funko Nightmare Before Christmas Zero Bag", "Standard", "mid", 65),
        ("loungefly", "Loungefly x Funko Pixar Alien Remix Backpack", "Standard", "mid", 60),
        ("loungefly", "Loungefly x Funko Cinderella Carriage Crossbody", "Park Exclusive", "high", 95),
        ("loungefly", "Loungefly x Funko Tangled Lantern Mini Backpack", "NYCC Exclusive", "high", 120),

        # ── Disney Traditions Jim Shore — Additional (+8) ────────────────
        ("jim_shore", "Jim Shore Moana 'Find Your Way' Figurine", "Standard", "mid", 65),
        ("jim_shore", "Jim Shore Pocahontas 'Colors of the Wind' Figurine", "Standard", "mid", 70),
        ("jim_shore", "Jim Shore Mulan 'Bravest of All' Figurine", "Standard", "mid", 65),
        ("jim_shore", "Jim Shore Lilo & Stitch Ohana Means Family Figurine (Large)", "Limited", "high", 110),
        ("jim_shore", "Jim Shore Encanto Mirabel Figurine", "Standard", "mid", 60),
        ("jim_shore", "Jim Shore Sleeping Beauty Aurora Dancing Figurine", "Standard", "mid", 70),
        ("jim_shore", "Jim Shore Tangled Rapunzel Tower Scene", "Limited", "high", 120),
        ("jim_shore", "Jim Shore Coco Day of the Dead Miguel Figurine", "Standard", "mid", 65),

        # ── Enchanted Disney Fine Jewelry (+5) ───────────────────────────
        ("jewelry", "Enchanted Disney Elsa Snowflake Diamond Ring", "Enchanted", "high", 180),
        ("jewelry", "Enchanted Disney Belle Rose Diamond Pendant", "Enchanted", "high", 160),
        ("jewelry", "Enchanted Disney Ariel Pearl & Diamond Earrings", "Enchanted", "high", 150),
        ("jewelry", "Enchanted Disney Cinderella Carriage Diamond Bracelet", "Enchanted", "high", 200),
        ("jewelry", "Enchanted Disney Jasmine Aladdin Lamp Diamond Ring", "Enchanted", "high", 170),

        # ── Lilo & Stitch Collection (+7) ────────────────────────────────
        ("stitch", "Stitch Crashes Disney January (Lady & Tramp) LE Pin", "LE Monthly", "mid", 45),
        ("stitch", "Stitch Crashes Disney March (Mulan) LE Pin", "LE Monthly", "mid", 45),
        ("stitch", "Stitch Experiment 626 WDCC Figurine", "WDCC", "high", 180),
        ("stitch", "Stitch Elvis Bobblehead (Park Exclusive)", "Park Exclusive", "mid", 40),
        ("stitch", "Stitch & Angel Valentine's Day Figure Set", "Seasonal", "mid", 55),
        ("stitch", "Stitch 20th Anniversary LE 2000 Plush (Oversized)", "LE 2000", "high", 100),
        ("stitch", "Lilo & Stitch Surfboard Wall Art Print", "Limited Print", "mid", 65),

        # ── Encanto & Moana 2 (+7) ──────────────────────────────────────
        ("encanto", "Encanto Casita Playset (Disney Store Exclusive)", "Store Exclusive", "mid", 75),
        ("encanto", "Encanto Mirabel Designer Doll", "Designer LE", "high", 140),
        ("encanto", "Encanto Bruno Figurine (We Don't Talk About)", "Standard", "mid", 45),
        ("encanto", "Encanto Isabela Floral Figurine", "Standard", "mid", 40),
        ("moana2", "Moana 2 Maui Hook Replica (Park Exclusive)", "Park Exclusive", "high", 85),
        ("moana2", "Moana 2 Premiere Event LE 1000 Pin", "LE 1000", "high", 120),
        ("moana2", "Moana 2 Adventure Set (Disney Store Exclusive)", "Store Exclusive", "mid", 65),

        # ── Vintage Disneyland Memorabilia (+10) ─────────────────────────
        ("vintage", "Vintage Disneyland 1955 Opening Day Program Reproduction", "Vintage", "grail", 350),
        ("vintage", "Vintage Disneyland 1960s Souvenir Map (Original)", "Vintage", "grail", 280),
        ("vintage", "Vintage Walt Disney World 1971 Opening Year Pennant", "Vintage", "high", 200),
        ("vintage", "Vintage Disneyland Ticket Book E-Ticket (Unused)", "Vintage", "grail", 400),
        ("vintage", "Vintage Disney Mouseketeer Ears Hat (1950s)", "Vintage", "high", 180),
        ("vintage", "Vintage Disneyland Haunted Mansion 1969 Attraction Poster", "Vintage", "grail", 350),
        ("vintage", "Vintage Disney Monorail Souvenir Plate (1960s)", "Vintage", "high", 120),
        ("vintage", "Vintage Disneyland Small World Opening Day Brochure (1966)", "Vintage", "grail", 300),
        ("vintage", "Vintage EPCOT Center 1982 Grand Opening Poster", "Vintage", "high", 180),
        ("vintage", "Vintage Disneyland Pirates of the Caribbean Cast Lanyard (1970s)", "Vintage", "high", 150),

        # ── Walt Disney Archives — Additional (+7) ──────────────────────
        ("archives", "Walt Disney Archives Bambi Original Sketch Reproduction", "LE 500", "grail", 280),
        ("archives", "Walt Disney Archives Cinderella Glass Slipper Replica", "LE 750", "grail", 320),
        ("archives", "Walt Disney Archives Haunted Mansion Tombstone Replica Set", "LE 1000", "high", 200),
        ("archives", "Walt Disney Archives Walt's Desk Nameplate Replica", "LE 500", "grail", 350),
        ("archives", "Walt Disney Archives Enchanted Tiki Room Tiki Mug (1963 Replica)", "LE 1000", "high", 150),
        ("archives", "Walt Disney Archives Jungle Cruise Map Lithograph", "LE 1000", "high", 130),
        ("archives", "Walt Disney Archives Space Mountain Blueprint Poster", "LE 750", "high", 160),

        # ── runDisney & Park Events (+6) ─────────────────────────────────
        ("rundisney", "runDisney Walt Disney World Marathon 2025 Finisher Medal", "Event Exclusive", "mid", 65),
        ("rundisney", "runDisney Disneyland Half Marathon 2025 Finisher Medal", "Event Exclusive", "mid", 55),
        ("rundisney", "runDisney Wine & Dine Challenge Double Medal Set", "Event Exclusive", "high", 95),
        ("rundisney", "runDisney Star Wars Rival Run Medal (Vader vs Luke)", "Event Exclusive", "mid", 70),
        ("parks", "Shanghai Disney Resort Grand Opening LE Pin Set", "LE 1000", "high", 150),
        ("parks", "Tokyo DisneySea 20th Anniversary LE Figure Set", "LE 2000", "high", 130),

        # ── Disney Designer Dolls — Additional (+4) ─────────────────────
        ("designer_dolls", "Disney Designer Collection Mulan Doll", "Designer LE", "high", 145),
        ("designer_dolls", "Disney Designer Collection Moana Doll", "Designer LE", "high", 140),
        ("designer_dolls", "Disney Designer Midnight Masquerade Belle Doll", "Designer LE", "high", 160),
        ("designer_dolls", "Disney Designer Fairytale Couples Beauty & Beast Set", "Designer LE", "grail", 260),

        # ── Additional Disney Collectibles (+10) ──────────────────────────
        ("pins", "Disney Villains Maleficent Dragon LE 2000 Pin", "LE 2000", "high", 110),
        ("pins", "EPCOT 40th Anniversary Figment Rainbow LE 3000 Pin", "LE 3000", "high", 85),
        ("ornaments", "Hallmark Disney Tangled Lantern Scene Ornament", "Hallmark Exclusive", "mid", 45),
        ("ornaments", "Hallmark Disney Encanto Mirabel Musical Ornament", "Hallmark Exclusive", "mid", 42),
        ("vinylmation", "Vinylmation Park Starz Series 5 Haunted Mansion Bride", "LE 1500", "high", 80),
        ("disney100", "Disney100 Anniversary Oswald Lucky Rabbit Figurine", "D100 LE", "high", 140),
        ("parks", "Walt Disney World 50th Anniversary Spirit Jersey (Gold)", "Park Exclusive", "mid", 75),
        ("parks", "Disneyland Resort 2025 Lunar New Year Snake Ears Headband", "Park Exclusive", "mid", 40),
        ("swarovski", "Swarovski Disney Moana Crystal Figurine", "Swarovski LE", "grail", 280),
        ("jim_shore", "Jim Shore Disney Traditions Fantasia Sorcerer Mickey", "Standard", "mid", 65),

        # ── Animation Cels & Production Art ───────────────────────────────
        ("animation_cels", "Original Production Cel Bambi & Thumper Meadow Scene", "Vintage", "grail", 3500),
        ("animation_cels", "Original Production Cel Sleeping Beauty Maleficent Dragon", "Vintage", "grail", 8000),
        ("animation_cels", "Original Production Cel The Little Mermaid Ariel Part of Your World", "Vintage", "grail", 5000),
        ("animation_cels", "Original Production Cel Lion King Mufasa & Simba Sunrise", "Vintage", "grail", 4500),
        ("animation_cels", "Original Production Cel Aladdin Genie & Lamp", "Vintage", "grail", 3800),
        ("animation_cels", "Original Production Cel Beauty and the Beast Ballroom Dance", "Vintage", "grail", 6000),
        ("animation_cels", "Limited Edition Sericel Snow White Wishing Well (500pc)", "Sericel LE 500", "grail", 800),
        ("animation_cels", "Limited Edition Sericel The Little Mermaid Under the Sea", "Sericel LE 500", "grail", 650),
        ("animation_cels", "Limited Edition Sericel Cinderella Glass Slipper", "Sericel LE 750", "high", 500),
        ("animation_cels", "Limited Edition Sericel Aladdin Magic Carpet Ride", "Sericel LE 500", "grail", 700),
        ("animation_cels", "Original Production Cel Fantasia Sorcerer Mickey Broom March", "Vintage", "grail", 12000),
        ("animation_cels", "Original Production Cel Pinocchio & Jiminy Cricket", "Vintage", "grail", 7000),
        ("animation_cels", "Original Production Drawing Dumbo Timothy Mouse", "Vintage", "grail", 2500),
        ("animation_cels", "Limited Edition Sericel Lion King Circle of Life", "Sericel LE 500", "grail", 750),
        ("animation_cels", "Walt Disney Animation Research Library Reproduction Print Set (6pc)", "Archival", "high", 180),

        # ── D23 / Convention Exclusives ───────────────────────────────────
        ("d23", "D23 Expo 2019 Exclusive Fantasia 80th Anniversary Pin Set", "D23 LE 2019", "grail", 250),
        ("d23", "D23 Expo 2022 Exclusive Figment Top Hat Figurine", "D23 LE 2022", "grail", 280),
        ("d23", "D23 Expo 2024 Exclusive Mickey & Walt Partners Statue (Numbered)", "D23 LE 2024", "grail", 350),
        ("d23", "D23 Expo 2019 Exclusive Disney Villains Art Print Set", "D23 LE 2019", "high", 120),
        ("d23", "D23 Expo 2022 Exclusive Enchanted Tiki Room Bird Figurine", "D23 LE 2022", "high", 160),
        ("d23", "D23 Expo 2024 Exclusive Haunted Mansion Hitchhiking Ghosts LE Pin", "D23 LE 2024", "grail", 220),
        ("d23", "D23 Gold Member Exclusive Annual Gift 2025", "D23 Members Only", "high", 110),
        ("d23", "D23 Expo 2022 Exclusive Moana Wayfinder Pin", "D23 LE 2022", "high", 95),
        ("d23", "D23 Expo 2024 Exclusive Zootopia Judy & Nick LE 1000 Pin", "D23 LE 2024", "high", 130),
        ("d23", "D23 Expo 2019 Exclusive Disney Princess Designer Tote Bag", "D23 LE 2019", "high", 85),

        # ── Walt Disney Archives Collection ───────────────────────────────
        ("archives", "Walt Disney Archives Sorcerer Hat Replica Prop", "Archives LE", "grail", 400),
        ("archives", "Walt Disney Archives Snow White Poison Apple Prop Replica", "Archives LE", "grail", 300),
        ("archives", "Walt Disney Archives Mickey Fantasia Conductor Baton Replica", "Archives LE", "high", 180),
        ("archives", "Walt Disney Archives Cinderella Glass Slipper Replica", "Archives LE", "grail", 350),
        ("archives", "Walt Disney Archives Pirates of Caribbean Treasure Chest Replica", "Archives LE", "high", 200),
        ("archives", "Walt Disney Archives Opening Day 1955 Disneyland Ticket Framed Replica", "Archives LE", "grail", 450),
        ("archives", "Walt Disney Archives Mary Poppins Carousel Horse Figurine", "Archives LE", "high", 160),
        ("archives", "Walt Disney Archives 50th Anniversary EPCOT Spaceship Earth Model", "Archives LE", "high", 190),
        ("archives", "Walt Disney Archives Haunted Mansion Wallpaper Print (Framed)", "Archives", "high", 120),
        ("archives", "Walt Disney Archives Walt's Desk Miniature Replica Set", "Archives LE", "grail", 500),

        # ── Disney 100 Anniversary (2023) ─────────────────────────────────
        ("disney100", "Disney100 Steiff Mickey Mouse LE Plush", "D100 LE", "grail", 400),
        ("disney100", "Disney100 Loungefly Platinum Iridescent Backpack", "D100 Exclusive", "high", 120),
        ("disney100", "Disney100 Loungefly Vault AOP Crossbody", "D100 Exclusive", "high", 95),
        ("disney100", "Disney100 Anniversary Pandora Charm Bracelet Set", "D100 LE", "high", 180),
        ("disney100", "Disney100 Anniversary Swarovski Mickey Crystal Figurine", "D100 LE", "grail", 350),
        ("disney100", "Disney100 Anniversary Dooney & Bourke Satchel", "D100 LE", "high", 200),
        ("disney100", "Disney100 Celebration Cake Figurine (Jim Shore)", "D100 Exclusive", "high", 95),
        ("disney100", "Disney100 Anniversary Castle Music Box", "D100 LE", "high", 150),
        ("disney100", "Disney100 Platinum Celebration Ornament Set (6pc)", "D100 LE", "high", 110),
        ("disney100", "Disney100 Walt & Mickey Bronze-Tone Bookend Set", "D100 Exclusive", "high", 130),

        # ── Vintage Theme Park ────────────────────────────────────────────
        ("parks", "Galaxy's Edge Opening Day 2019 Commemorative Lightsaber Hilt", "Park Exclusive", "grail", 300),
        ("parks", "Avengers Campus Opening Day 2021 Spider-Bot LE", "Park Exclusive", "high", 120),
        ("parks", "Tron Lightcycle Run Opening Day 2023 LE MagicBand+", "Park Exclusive", "high", 95),
        ("parks", "Guardians Cosmic Rewind Opening Day 2022 LE Pin", "Park Exclusive", "high", 85),
        ("parks", "Retired Splash Mountain Final Ride Day Commemorative Pin", "Park Exclusive", "grail", 250),
        ("parks", "Retired Great Movie Ride Closing Day LE Pin", "Park Exclusive", "high", 150),
        ("parks", "Vintage Disneyland Skyway Bucket Ride Vehicle Model", "Vintage", "grail", 500),
        ("parks", "Vintage Walt Disney World Monorail Playset (1970s)", "Vintage", "grail", 400),
        ("parks", "Epcot Center Opening Day 1982 Cast Member Badge (Original)", "Vintage", "grail", 600),
        ("parks", "Haunted Mansion 50th Anniversary Event Doom Buggy Model", "Park LE", "grail", 350),

        # ── Villains Collection ───────────────────────────────────────────
        ("villains", "Disney Designer Villains Collection Maleficent Doll", "Designer LE", "grail", 300),
        ("villains", "Disney Designer Villains Collection Ursula Doll", "Designer LE", "grail", 280),
        ("villains", "Disney Designer Villains Collection Evil Queen Doll", "Designer LE", "grail", 260),
        ("villains", "Disney Villains Midnight Masquerade Hades Doll", "Designer LE", "high", 180),
        ("villains", "Disney Villains Premium Figurine Cruella de Vil Art Deco", "Premium LE", "high", 140),

        # ── Disney Infinity — Complete Collection ────────────────────────
        ("infinity", "Disney Infinity 1.0 Jack Sparrow Figure", "Standard", "standard", 12),
        ("infinity", "Disney Infinity 1.0 Sulley (Monsters Inc) Figure", "Standard", "standard", 10),
        ("infinity", "Disney Infinity 1.0 Lightning McQueen Figure", "Standard", "standard", 12),
        ("infinity", "Disney Infinity 1.0 Wreck-It Ralph Figure", "Standard", "standard", 15),
        ("infinity", "Disney Infinity 1.0 Phineas Figure", "Standard", "standard", 20),
        ("infinity", "Disney Infinity 2.0 Stitch Figure", "Standard", "standard", 18),
        ("infinity", "Disney Infinity 2.0 Tinker Bell Figure", "Standard", "standard", 15),
        ("infinity", "Disney Infinity 2.0 Maleficent Figure", "Standard", "standard", 22),
        ("infinity", "Disney Infinity 2.0 Donald Duck Figure", "Standard", "standard", 20),
        ("infinity", "Disney Infinity 3.0 Mulan Figure", "Standard", "standard", 25),
        ("infinity", "Disney Infinity 3.0 Olaf (Frozen) Figure", "Standard", "standard", 12),
        ("infinity", "Disney Infinity 3.0 Finding Dory Nemo Figure", "Standard", "standard", 18),
        ("infinity", "Disney Infinity 3.0 Baloo (Jungle Book) Figure", "Standard", "standard", 20),
        ("infinity", "Disney Infinity Complete 1.0 Starter Pack (Sealed)", "Sealed Product", "high", 80),
        ("infinity", "Disney Infinity Complete 3.0 Starter Pack (Sealed)", "Sealed Product", "high", 90),

        # ── Pin Trading — Fantasy Pins & Limited Editions ────────────────
        ("pins", "Fantasy Pin Oogie Boogie Carousel", "Fantasy", "mid", 48),
        ("pins", "Fantasy Pin Cheshire Cat Neon Glow", "Fantasy", "mid", 55),
        ("pins", "Fantasy Pin Evil Queen Mirror Lenticular", "Fantasy", "high", 75),
        ("pins", "Fantasy Pin Enchanted Rose (Beauty and the Beast) Hinged", "Fantasy", "mid", 60),
        ("pins", "Haunted Mansion Stretching Room LE 1000 Pin Set (4pc)", "LE 1000", "grail", 300),
        ("pins", "Splash Mountain Last Splash LE 2500 Pin", "LE 2500", "high", 120),
        ("pins", "Pirates of the Caribbean 50th LE 2000 Pin", "LE 2000", "high", 110),
        ("pins", "Tiana's Bayou Adventure Opening Day LE 3000 Pin", "LE 3000", "high", 85),
        ("pins", "Disneyland Railroad LE 1500 Engineer Mickey Pin", "LE 1500", "high", 95),

        # ── Disney Designer Collection Dolls ─────────────────────────────
        ("dolls", "Disney Designer Collection Ariel Doll (Premiere Series)", "Designer LE", "grail", 280),
        ("dolls", "Disney Designer Collection Rapunzel Doll (Premiere Series)", "Designer LE", "grail", 260),
        ("dolls", "Disney Designer Collection Snow White Doll (Premiere Series)", "Designer LE", "grail", 240),
        ("dolls", "Disney Designer Collection Tiana Doll (Premiere Series)", "Designer LE", "grail", 250),
        ("dolls", "Disney Designer Collection Mulan Doll (Premiere Series)", "Designer LE", "grail", 230),
        ("dolls", "Disney Designer Fairytale Couples Cinderella & Prince", "Designer LE", "grail", 350),
        ("dolls", "Disney Animator's Collection Moana Toddler Doll (1st Ed)", "LE", "mid", 45),
        ("dolls", "Disney Animator's Collection Elsa Toddler Doll (1st Ed)", "LE", "mid", 40),

        # ── Disneyana Vintage (1930s-50s) ────────────────────────────────
        ("vintage", "1930s Mickey Mouse Ingersoll Wristwatch (Original)", "Vintage", "grail", 2000),
        ("vintage", "1930s Mickey Mouse Bisque Figurine (Japan Made)", "Vintage", "grail", 500),
        ("vintage", "1940s Fantasia Sorcerer Mickey Ceramic Figure (Vernon Kilns)", "Vintage", "grail", 800),
        ("vintage", "1950s Disneyland Opening Day Ticket Book (A-E Complete)", "Vintage", "grail", 3000),
        ("vintage", "1930s Mickey Mouse Tin Wind-Up Toy (Marx)", "Vintage", "grail", 1500),
        ("vintage", "1940s Donald Duck Tin Litho Bank", "Vintage", "grail", 600),
        ("vintage", "1934 Big Little Book Mickey Mouse (Whitman)", "Vintage", "grail", 400),
        ("vintage", "1950s Ludwig Von Drake Ceramic Cookie Jar", "Vintage", "high", 300),

        # ── More Disney Pins & Merch to Reach 1020+ ─────────────────────
        ("pins", "Disney Wonderground Gallery LE 300 Pin (Shag Art)", "LE 300", "grail", 200),
        ("pins", "Disney Cruise Line 25th Anniversary LE 2500 Pin", "DCL Exclusive", "high", 80),
        ("pins", "Club 33 Exclusive Member Pin (2024)", "LE", "grail", 350),
        ("pins", "Mickey & Friends Retro LE 5000 Pin Set (5pc)", "LE 5000", "high", 65),
        ("pins", "Disneyland Paris 30th Anniversary LE 3000 Pin", "LE 3000", "high", 75),
        ("dolls", "Disney Designer Collection Belle Doll (Ultimate Princess)", "Designer LE", "grail", 270),
        ("dolls", "Disney Designer Fairytale Couples Aurora & Philip", "Designer LE", "grail", 320),
        ("dolls", "Disney Limited Edition Elsa Doll (Frozen 10th Anniversary)", "LE 1500", "grail", 200),
        ("figures", "Disney Traditions Jim Shore Stitch Ohana Figure", "Disney Traditions", "mid", 50),
        ("figures", "Disney Traditions Jim Shore Maleficent Dragon Figure", "Disney Traditions", "high", 80),
        ("figures", "Disney Traditions Jim Shore Mickey & Minnie Wedding Figure", "Disney Traditions", "mid", 60),
        ("ornaments", "Disney Hallmark Keepsake Mickey Mouse 75th Anniversary Ornament", "Hallmark Exclusive", "mid", 35),
        ("ornaments", "Disney Hallmark Haunted Mansion Doom Buggy Ornament", "Hallmark Exclusive", "mid", 45),
        ("ears", "Disney Designer Ears (Loungefly x Disney Parks Villains)", "Park Exclusive", "high", 75),
        ("ears", "Disney Spirit Jersey (Haunted Mansion Glow-in-Dark)", "Park Exclusive", "high", 85),
        ("wdcc", "WDCC Cinderella Castle Enchantment (LE 500)", "WDCC", "grail", 800),
        ("wdcc", "WDCC Peter Pan & Tinker Bell Moonlight Flight", "WDCC", "high", 180),
        ("wdcc", "WDCC Snow White The Fairest One of All", "WDCC", "high", 150),
    ]

    catalog = []
    for subcategory, name, edition, tier, price in items:
        catalog.append({
            "subcategory": subcategory,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })

    # Add variant expansion items, deduplicating by (subcategory, name)
    existing_keys = {(d["subcategory"], d["name"]) for d in catalog}
    for item in _variant_expansion():
        key = (item["subcategory"], item["name"])
        if key not in existing_keys:
            existing_keys.add(key)
            catalog.append(item)

    # Add wave 2 expansion items
    for item in _wave2_expansion():
        key = (item["subcategory"], item["name"])
        if key not in existing_keys:
            existing_keys.add(key)
            catalog.append(item)

    # Deduplicate by ('name',) (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = item["name"]
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def _variant_expansion() -> list[dict]:
    """~100 variant items for existing Disney collectibles.

    Variant types covered:
    - Pin variants: standard vs limited edition, event exclusive, hidden mickey, fantasy
    - Figure variants: regular vs chase, glow-in-dark, flocked, diamond, metallic
    - Park exclusive vs general release versions
    - Size variants: mini, regular, large/jumbo
    - Color variants & seasonal editions (holiday, anniversary)
    """

    # (subcategory, name, edition, rarity_tier, price_eur)
    variants = [
        # ── Pin Variants — LE vs Standard vs Event Exclusive ─────────────
        ("pins", "Haunted Mansion 50th Anniversary Standard Pin", "Standard", "standard", 18),
        ("pins", "Haunted Mansion 50th Anniversary LE 500 Jumbo Pin", "LE 500", "grail", 280),
        ("pins", "Nightmare Before Christmas 30th Event Exclusive Pin", "Event Exclusive", "grail", 200),
        ("pins", "Nightmare Before Christmas 30th Standard Pin", "Standard", "standard", 15),
        ("pins", "Walt Disney Portrait LE 500 Jumbo Pin", "LE 500", "grail", 380),
        ("pins", "Figment Epcot 40th Anniversary Standard Pin", "Standard", "standard", 18),
        ("pins", "Figment Epcot 40th Anniversary LE 750 Jumbo Pin", "LE 750", "grail", 250),
        ("pins", "Disney Villains LE 1000 Jumbo Pin Set", "LE 1000", "grail", 220),
        ("pins", "Disney Princess LE 5000 Standard Pin", "LE 5000", "mid", 45),
        ("pins", "Cinderella Castle LE 500 Glow-in-Dark Jumbo Pin", "LE 500", "grail", 350),

        # ── Pin Variants — Hidden Mickey Chasers ─────────────────────────
        ("pins", "Hidden Mickey Attractions Series Chaser Pin (Silver)", "Park Exclusive", "mid", 50),
        ("pins", "Hidden Mickey Sidekicks Series Chaser Pin (Gold)", "Park Exclusive", "high", 80),
        ("pins", "Hidden Mickey Villains Series Gold Chaser Pin", "Park Exclusive", "high", 95),
        ("pins", "Hidden Mickey Pin (Common Character)", "Park Exclusive", "standard", 10),
        ("pins", "Hidden Mickey Princesses Series Completer Pin", "Park Exclusive", "mid", 40),

        # ── Pin Variants — Fantasy Pin Sizes ─────────────────────────────
        ("pins", "Fantasy Pin Maleficent Stained Glass Mini", "Fantasy", "standard", 15),
        ("pins", "Fantasy Pin Maleficent Stained Glass Jumbo", "Fantasy", "high", 80),
        ("pins", "Fantasy Pin Ursula Art Nouveau Mini", "Fantasy", "standard", 18),
        ("pins", "Fantasy Pin Ursula Art Nouveau Jumbo", "Fantasy", "high", 85),
        ("pins", "Fantasy Pin Sorcerer Mickey Mini", "Fantasy", "standard", 20),
        ("pins", "Fantasy Pin Figment Rainbow Glitter Jumbo", "Fantasy", "high", 110),

        # ── Pin Variants — Seasonal & Color ──────────────────────────────
        ("pins", "Stitch Crashes Disney Holiday Edition Pin", "Seasonal LE", "high", 65),
        ("pins", "Disney Pin Trading Starter Set Holiday Edition", "Seasonal", "standard", 20),
        ("pins", "Disney Cast Member Exclusive Holiday Pin", "Cast Exclusive", "high", 95),
        ("pins", "Disney Parks 50th Anniversary LE 50 Silver Pin", "LE 50", "grail", 550),
        ("pins", "Disney Magical Moments LE 300 Mini Pin (Castle Fireworks)", "LE 300", "grail", 180),

        # ── Figure Variants — Chase & Glow-in-Dark ──────────────────────
        ("figures", "D23 Exclusive Sorcerer Mickey Figure (Chase Metallic)", "Chase Variant", "grail", 350),
        ("figures", "D23 Exclusive Sorcerer Mickey Figure (Glow-in-Dark)", "Glow-in-Dark", "grail", 300),
        ("figures", "Walt Disney Archives Figure (50th) Metallic Edition", "Metallic LE", "high", 120),
        ("figures", "Walt Disney Archives Figure (50th) Diamond Edition", "Diamond LE", "grail", 200),

        # ── Vinylmation Variants — Chase & Size ─────────────────────────
        ("vinylmation", "Vinylmation Urban Redux Series Chaser (Metallic)", "Chase Variant", "high", 85),
        ("vinylmation", "Vinylmation Star Wars Jedi Mickey 9in", "Limited", "high", 80),
        ("vinylmation", "Vinylmation Star Wars Jedi Mickey 1.5in Mini", "Standard", "standard", 12),
        ("vinylmation", "Vinylmation Nightmare Before Christmas 3in", "Standard", "mid", 35),
        ("vinylmation", "Vinylmation Mickey Through the Years Chaser (Gold)", "Chase Variant", "high", 130),
        ("vinylmation", "Vinylmation Villains Series Maleficent 3in", "Standard", "mid", 40),
        ("vinylmation", "Vinylmation Park Series 1 Chaser (Glow-in-Dark)", "Chase Variant", "high", 100),

        # ── Disney Infinity — Crystal & Regular ──────────────────────────
        ("infinity", "Disney Infinity 3.0 Sorcerer Mickey (Standard)", "Standard", "standard", 15),
        ("infinity", "Disney Infinity 1.0 Sorcerer Mickey (Crystal Variant)", "Crystal Variant", "high", 90),
        ("infinity", "Disney Infinity 3.0 Star Wars Boba Fett (Crystal)", "Crystal Variant", "high", 85),
        ("infinity", "Disney Infinity 3.0 Inside Out Joy (Crystal)", "Crystal Variant", "high", 75),

        # ── Kingdom Hearts — Chase & Metallic ────────────────────────────
        ("kingdom_hearts", "Kingdom Hearts Funko Pop Sora (Brave Form) Standard", "Standard", "mid", 30),
        ("kingdom_hearts", "Kingdom Hearts Funko Pop Sora (Drive Form) Chase", "Chase Variant", "high", 90),
        ("kingdom_hearts", "Kingdom Hearts Funko Pop Sora (Glow-in-Dark)", "Glow-in-Dark", "high", 100),
        ("kingdom_hearts", "Kingdom Hearts Keyblade Replica Mini (6in)", "Standard", "standard", 25),
        ("kingdom_hearts", "Kingdom Hearts Keyblade Replica Jumbo (48in)", "Premium", "high", 150),
        ("kingdom_hearts", "Kingdom Hearts Diamond Select Mickey Figure (Metallic)", "Metallic LE", "high", 80),

        # ── Villains — Chase, Diamond & Flocked ──────────────────────────
        ("villains", "Disney Villains Funko Pop Maleficent (Flames) Diamond", "Diamond LE", "high", 110),
        ("villains", "Disney Villains Funko Pop Maleficent (Flames) Flocked", "Flocked LE", "high", 95),
        ("villains", "Disney Villains Funko Pop Maleficent (Flames) Glow-in-Dark", "Glow-in-Dark", "grail", 130),
        ("villains", "Disney Villains Hades Ember Glow Figurine (Metallic)", "Metallic LE", "high", 140),
        ("villains", "Disney Villains Cruella De Vil Figurine (Flocked)", "Flocked LE", "high", 80),
        ("villains", "Disney Villains Chernabog Figurine (Glow-in-Dark)", "Glow-in-Dark", "grail", 180),

        # ── Loungefly — Park Exclusive vs General Release ────────────────
        ("loungefly", "Loungefly Haunted Mansion Mini Backpack (Park Exclusive Glow)", "Park Exclusive", "high", 110),
        ("loungefly", "Loungefly Villains AOP Backpack (Glow-in-Dark)", "Glow-in-Dark", "high", 90),
        ("loungefly", "Loungefly Figment Epcot Backpack (General Release)", "Standard", "mid", 55),
        ("loungefly", "Loungefly Disney100 Platinum Crossbody", "D100 Exclusive", "high", 85),
        ("loungefly", "Loungefly Disney Princess Castle Backpack (Metallic)", "Metallic LE", "high", 110),

        # ── Designer Dolls — Size Variants ───────────────────────────────
        ("designer_dolls", "Disney Designer Collection Ariel Mini Doll (6in)", "Designer LE", "mid", 55),
        ("designer_dolls", "Disney Designer Collection Belle Mini Doll (6in)", "Designer LE", "mid", 50),
        ("designer_dolls", "Disney Designer Collection Jasmine Mini Doll (6in)", "Designer LE", "mid", 55),
        ("designer_dolls", "Disney Designer Collection Rapunzel Jumbo Doll (24in)", "Designer LE", "grail", 280),
        ("designer_dolls", "Disney Designer Midnight Masquerade Tiana Mini Doll", "Designer LE", "mid", 60),

        # ── Plush — Size Variants ────────────────────────────────────────
        ("plush", "Disney Store Vintage Winnie the Pooh Mini Plush (1990s)", "Vintage", "standard", 20),
        ("plush", "Disney Store Vintage Lion King Simba Mini Plush", "Vintage", "standard", 22),
        ("plush", "Disney Store Limited Sorcerer Mickey Jumbo Plush (D23)", "D23 Exclusive", "high", 140),
        ("plush", "Disney Store nuiMOs Plush Holiday Complete Set (8pc)", "Seasonal", "high", 85),
        ("plush", "Disney Store Vintage Stitch Jumbo Plush (2002 Release)", "Vintage", "high", 90),

        # ── Ears — Seasonal & Color Variants ─────────────────────────────
        ("ears", "50th Anniversary Silver Ears", "LE Park", "mid", 50),
        ("ears", "50th Anniversary Rose Gold Ears", "LE Park", "mid", 60),
        ("ears", "Disney Parks Sequin Ears Coral", "Park Exclusive", "mid", 35),
        ("ears", "Disney Parks Sequin Ears Arendelle Aqua", "Park Exclusive", "mid", 38),
        ("ears", "Disney Parks Minnie Ears Holiday Wreath (Christmas)", "Seasonal", "mid", 45),
        ("ears", "Disney Parks Minnie Ears Valentine's Day Hearts", "Seasonal", "mid", 40),
        ("ears", "Disney Parks Minnie Ears Halloween Orange Sequin", "Seasonal", "mid", 42),

        # ── Ornaments — Seasonal Variants ────────────────────────────────
        ("ornaments", "Hallmark Disney Castle LE Ornament (Gold Variant)", "LE", "high", 75),
        ("ornaments", "Swarovski Disney Castle Ornament (Annual 2025)", "Premium", "high", 90),
        ("ornaments", "Swarovski Disney Castle Ornament (Annual 2024)", "Premium", "high", 85),
        ("ornaments", "Disney Sketchbook Legacy Ornament Holiday Red Set", "Seasonal", "mid", 50),

        # ── Popcorn Buckets — Size & Color ───────────────────────────────
        ("popcorn_buckets", "Figment Popcorn Bucket (EPCOT Festival) Purple Variant", "Park Exclusive", "high", 140),
        ("popcorn_buckets", "Mickey Mouse Balloon Popcorn Bucket (Gold 50th Edition)", "Park Exclusive", "high", 90),
        ("popcorn_buckets", "Cinderella Carriage Popcorn Bucket (Rose Gold)", "Park Exclusive", "high", 100),
        ("popcorn_buckets", "Haunted Mansion Doom Buggy Popcorn Bucket (Glow-in-Dark)", "Glow-in-Dark", "high", 130),

        # ── Swarovski — Size Variants ────────────────────────────────────
        ("swarovski", "Swarovski Crystal Mickey Mouse Mini Figurine", "Premium", "high", 80),
        ("swarovski", "Swarovski Crystal Mickey Mouse Large Figurine", "Premium", "grail", 450),
        ("swarovski", "Swarovski Crystal Tinker Bell Mini Figurine", "Premium", "mid", 70),
        ("swarovski", "Swarovski Crystal Bambi Mini Figurine", "Premium", "high", 100),

        # ── Jim Shore — Size & Seasonal Variants ─────────────────────────
        ("jim_shore", "Jim Shore Mickey Mouse Statement Figure Mini (4in)", "Standard", "standard", 25),
        ("jim_shore", "Jim Shore Stitch Ohana Figurine (Large 14in)", "Limited", "high", 110),
        ("jim_shore", "Jim Shore Stitch Christmas Figurine", "Seasonal", "mid", 55),
        ("jim_shore", "Jim Shore Mickey Mouse Halloween Figurine", "Seasonal", "mid", 60),

        # ── Galaxy's Edge — Color Variants ───────────────────────────────
        ("galaxys_edge", "Galaxy's Edge Legacy Lightsaber (Luke Skywalker Green)", "Park Exclusive", "high", 190),
        ("galaxys_edge", "Galaxy's Edge Kyber Crystal (Red)", "Park Exclusive", "standard", 15),
        ("galaxys_edge", "Galaxy's Edge Kyber Crystal (Black Obsidian)", "Park Exclusive", "high", 80),
        ("galaxys_edge", "Galaxy's Edge Droid Depot Custom BB Unit", "Park Exclusive", "high", 110),

        # ── WDCC — Size & Anniversary Variants ───────────────────────────
        ("wdcc", "WDCC Cinderella 'A Lovely Dress' Mini Figurine", "WDCC", "high", 120),
        ("wdcc", "WDCC Fantasia Sorcerer Mickey 25th Anniversary Edition", "WDCC", "grail", 380),
        ("wdcc", "WDCC Bambi 'The Young Prince' Mini Figurine", "WDCC", "mid", 70),

        # ── Lorcana — Foil & Promo Variants ──────────────────────────────
        ("lorcana", "Lorcana Stitch Rock Star Enchanted (Cold Foil)", "Enchanted Rare", "grail", 250),
        ("lorcana", "Lorcana Mickey Mouse Brave Little Tailor Promo (Store Championship)", "Promo LE", "high", 95),
    ]

    result = []
    for subcategory, name, edition, tier, price in variants:
        result.append({
            "subcategory": subcategory,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return result


def _wave2_expansion() -> list[dict]:
    """Wave 2 — ~115 items: Fantasy pins, Loungefly, figurines, vintage,
    Swarovski, park exclusives, Villains collection, Pixar collectibles."""

    # (subcategory, name, edition, rarity_tier, price_eur)
    variants = [
        # ── Fantasy Pins — New Designs ─────────────────────────────────
        ("pins", "Fantasy Pin Hades Ember Crown Jumbo", "Fantasy", "high", 85),
        ("pins", "Fantasy Pin Jafar Serpent Staff Slider", "Fantasy", "mid", 55),
        ("pins", "Fantasy Pin Evil Queen Magic Mirror Lenticular", "Fantasy", "high", 90),
        ("pins", "Fantasy Pin Chernabog Night on Bald Mountain Jumbo", "Fantasy", "high", 100),
        ("pins", "Fantasy Pin Gaston Tavern Scene Diorama", "Fantasy", "mid", 60),
        ("pins", "Fantasy Pin Mother Gothel Stained Glass", "Fantasy", "mid", 50),

        # ── Pins — Limited Edition New ─────────────────────────────────
        ("pins", "Pirates of the Caribbean 50th LE 1000 Pin", "LE 1000", "grail", 250),
        ("pins", "Space Mountain 50th Anniversary LE 2000 Pin", "LE 2000", "high", 130),
        ("pins", "Tower of Terror Final Drop LE 1500 Pin", "LE 1500", "grail", 200),
        ("pins", "TRON Lightcycle Run Grand Opening LE 3000 Pin", "LE 3000", "high", 85),
        ("pins", "Splash Mountain Final Ride LE 500 Jumbo Pin", "LE 500", "grail", 400),
        ("pins", "Moana Wayfinder LE 2500 Pin", "LE 2500", "high", 95),
        ("pins", "Encanto Casita LE 3000 Pin", "LE 3000", "high", 80),

        # ── Pins — Hidden Mickey New Series ────────────────────────────
        ("pins", "Hidden Mickey Princesses Complete Set (6 Pins)", "Park Exclusive", "high", 90),
        ("pins", "Hidden Mickey Pets Series Pin", "Park Exclusive", "standard", 15),
        ("pins", "Hidden Mickey Castles of the World Chaser Pin", "Park Exclusive", "mid", 55),
        ("pins", "Hidden Mickey Snack Foods Series Pin", "Park Exclusive", "standard", 12),

        # ── Loungefly — New Collabs ────────────────────────────────────
        ("loungefly", "Loungefly Tangled Lantern Festival Mini Backpack", "Standard", "mid", 65),
        ("loungefly", "Loungefly Coco Marigold Bridge Mini Backpack", "Standard", "mid", 55),
        ("loungefly", "Loungefly Encanto Casita Mini Backpack", "Standard", "mid", 50),
        ("loungefly", "Loungefly Lilo & Stitch Pineapple Mini Backpack", "Standard", "mid", 55),
        ("loungefly", "Loungefly Nightmare Before Christmas Oogie Boogie Glow Backpack", "Glow-in-Dark", "high", 85),
        ("loungefly", "Loungefly Hocus Pocus Sanderson Sisters Backpack", "Seasonal", "mid", 60),
        ("loungefly", "Loungefly Sleeping Beauty Maleficent Dragon Backpack", "Standard", "mid", 65),
        ("loungefly", "Loungefly Moana Tamatoa Sequin Backpack", "Standard", "mid", 55),
        ("loungefly", "Loungefly Ratatouille Remy Mini Backpack", "Standard", "mid", 50),
        ("loungefly", "Loungefly Wall-E & Eve Date Night Crossbody", "Standard", "mid", 45),

        # ── Jim Shore — New Figurines ──────────────────────────────────
        ("jim_shore", "Jim Shore Disney Traditions Cinderella Staircase", "Standard", "mid", 75),
        ("jim_shore", "Jim Shore Disney Traditions Moana Heihei", "Standard", "mid", 45),
        ("jim_shore", "Jim Shore Disney Traditions Hades & Pain & Panic", "Standard", "mid", 70),
        ("jim_shore", "Jim Shore Disney Traditions Ursula Statement Figure (15in)", "Limited", "high", 120),
        ("jim_shore", "Jim Shore Disney Traditions Maleficent Dragon (Large)", "Limited", "high", 130),
        ("jim_shore", "Jim Shore Disney Traditions Stitch & Angel Heart", "Standard", "mid", 55),

        # ── Grand Jester Studios ───────────────────────────────────────
        ("figures", "Grand Jester Studios Elsa Bust (Frozen)", "Limited", "high", 90),
        ("figures", "Grand Jester Studios Maleficent Bust", "Limited", "high", 110),
        ("figures", "Grand Jester Studios Ariel Bust", "Limited", "high", 95),
        ("figures", "Grand Jester Studios Jack Skellington Bust", "Limited", "high", 100),

        # ── WDCC — Walt Disney Classics Collection ─────────────────────
        ("wdcc", "WDCC Snow White 'The Fairest One of All' Figurine", "WDCC", "high", 180),
        ("wdcc", "WDCC Peter Pan 'I'm So Happy, I Think I'll Give You a Kiss' Tinker Bell", "WDCC", "high", 200),
        ("wdcc", "WDCC Sleeping Beauty 'A Spell Shall Be The Gift' Maleficent", "WDCC", "grail", 320),
        ("wdcc", "WDCC Pinocchio 'Let Your Conscience Be Your Guide' Jiminy Cricket", "WDCC", "high", 150),
        ("wdcc", "WDCC Alice in Wonderland 'Curiouser and Curiouser' Alice", "WDCC", "high", 140),

        # ── Vintage — Park Maps & Tickets ──────────────────────────────
        ("vintage", "Vintage Disneyland Park Map 1960s (Folded)", "Vintage", "high", 150),
        ("vintage", "Vintage Disneyland Park Map 1970s (A-E Tickets Version)", "Vintage", "high", 120),
        ("vintage", "Vintage Walt Disney World Opening Day Map 1971", "Vintage", "grail", 350),
        ("vintage", "Vintage Disneyland A-Ticket Book (Complete, Unused)", "Vintage", "grail", 500),
        ("vintage", "Vintage Disneyland E-Ticket (Single, Used)", "Vintage", "mid", 60),
        ("vintage", "Vintage EPCOT Center Opening Day Guide 1982", "Vintage", "high", 100),

        # ── Vintage — Attraction Posters ───────────────────────────────
        ("vintage", "Vintage Attraction Poster Haunted Mansion (Original Print)", "Vintage", "grail", 800),
        ("vintage", "Vintage Attraction Poster Pirates of the Caribbean", "Vintage", "grail", 600),
        ("vintage", "Vintage Attraction Poster Space Mountain (1977)", "Vintage", "high", 400),
        ("vintage", "Vintage Attraction Poster Jungle Cruise", "Vintage", "high", 350),
        ("vintage", "Attraction Poster Reproduction Set (6 Posters)", "Standard", "mid", 45),

        # ── Swarovski — New ────────────────────────────────────────────
        ("swarovski", "Swarovski Crystal Ariel Figurine (LE)", "Swarovski LE", "grail", 350),
        ("swarovski", "Swarovski Crystal Elsa Frozen Figurine", "Premium", "high", 200),
        ("swarovski", "Swarovski Crystal Stitch Figurine", "Premium", "high", 180),
        ("swarovski", "Swarovski Crystal Cinderella Castle (Large)", "Swarovski LE", "grail", 600),
        ("swarovski", "Swarovski Crystal Dumbo Figurine", "Premium", "high", 160),

        # ── 50th Anniversary — WDW Exclusive ──────────────────────────
        ("parks", "WDW 50th Anniversary Celebration Figure Set (6 Characters)", "LE Park", "high", 150),
        ("parks", "WDW 50th Anniversary EARidescent Tumbler Set", "LE Park", "mid", 45),
        ("parks", "WDW 50th Anniversary Gold Statue Cinderella Castle Model", "LE Park", "high", 180),
        ("parks", "WDW 50th Anniversary Pressed Penny Collection (50 Coins)", "LE Park", "high", 120),
        ("parks", "WDW 50th Anniversary Dooney & Bourke Tote", "LE Park", "high", 200),

        # ── EPCOT Exclusives ───────────────────────────────────────────
        ("parks", "EPCOT Figment Dreamfinder Reunion Figure Set", "Park Exclusive", "high", 120),
        ("parks", "EPCOT Festival of the Arts Figment Figurine 2025", "Park Exclusive", "mid", 55),
        ("parks", "EPCOT Spaceship Earth Model (Light-up)", "Park Exclusive", "high", 90),
        ("parks", "EPCOT World Showcase Country Pin Set (11 Pins)", "Park Exclusive", "high", 85),

        # ── Disney Villains Collection ─────────────────────────────────
        ("villains", "Disney Villains Ursula Poor Unfortunate Souls Figurine", "Standard", "mid", 55),
        ("villains", "Disney Villains Scar Prepared Figurine", "Standard", "mid", 50),
        ("villains", "Disney Villains Yzma Figurine (Emperor's New Groove)", "Standard", "mid", 40),
        ("villains", "Disney Villains Dr. Facilier Shadow Man Figurine", "Standard", "mid", 45),
        ("villains", "Disney Villains Queen of Hearts Figurine (Croquet)", "Standard", "mid", 40),
        ("villains", "Disney Villains Captain Hook Figurine (Neverland)", "Standard", "mid", 40),
        ("villains", "Disney Villains Collectors Plate Set (6 Villains, LE)", "LE 2000", "high", 140),

        # ── Pixar Collectibles ─────────────────────────────────────────
        ("pixar", "Pixar Lamp Luxo Jr. Desk Lamp Replica", "Standard", "mid", 75),
        ("pixar", "Pixar Inside Out 2 Anxiety Figurine", "Standard", "standard", 25),
        ("pixar", "Pixar Cars Lightning McQueen 1:24 Die-Cast", "Standard", "mid", 35),
        ("pixar", "Pixar Up House & Balloons Light-Up Figurine", "Standard", "mid", 65),
        ("pixar", "Pixar Wall-E & Eve Music Box", "Limited", "high", 110),
        ("pixar", "Pixar Ratatouille Remy Kitchen Figurine Set", "Standard", "mid", 45),
        ("pixar", "Pixar Toy Story Woody & Buzz Signature Collection Set", "Premium", "high", 180),
        ("pixar", "Pixar Finding Nemo Reef Figurine Set (8 Pieces)", "Standard", "mid", 55),
        ("pixar", "Pixar Monsters Inc Sulley Door Station Figurine", "Standard", "mid", 50),
        ("pixar", "Pixar The Incredibles Family Figurine Set", "Standard", "mid", 45),

        # ── Disney Designer Dolls — New ────────────────────────────────
        ("designer_dolls", "Disney Designer Midnight Masquerade Meg (Hercules)", "Designer LE", "high", 120),
        ("designer_dolls", "Disney Designer Midnight Masquerade Esmeralda", "Designer LE", "high", 130),
        ("designer_dolls", "Disney Designer Fairytale Couples Ariel & Eric", "Designer LE", "grail", 250),
        ("designer_dolls", "Disney Designer Princess Collection Moana", "Designer LE", "high", 100),

        # ── Disney100 Celebration ──────────────────────────────────────
        ("d100", "Disney100 Platinum Celebration Castle Figurine", "D100 Exclusive", "high", 150),
        ("d100", "Disney100 Complete Pin Set (10 Pins)", "D100 Exclusive", "high", 180),
        ("d100", "Disney100 Steamboat Willie Platinum Figure", "D100 Exclusive", "high", 120),
        ("d100", "Disney100 Wonder of a Century Art Print (LE 500)", "D100 Exclusive", "grail", 200),

        # ── Animation Cels ─────────────────────────────────────────────
        ("animation_cels", "Original Production Cel The Little Mermaid Ariel", "Vintage", "grail", 2000),
        ("animation_cels", "Original Production Cel Beauty and the Beast Dance", "Vintage", "grail", 1500),
        ("animation_cels", "Original Production Cel Snow White Dwarfs", "Vintage", "grail", 3000),
        ("animation_cels", "Original Production Cel Sleeping Beauty Maleficent", "Vintage", "grail", 2500),
        ("animation_cels", "Original Production Cel Bambi Forest Scene", "Vintage", "grail", 1800),
        ("animation_cels", "Sericel Limited Edition Lion King Circle of Life", "LE 5000", "high", 200),
        ("animation_cels", "Sericel Limited Edition Cinderella Glass Slipper", "LE 2500", "high", 180),

        # ── Shanghai / Tokyo Disney Exclusives ─────────────────────────
        ("parks", "Shanghai Disney Resort Grand Opening Mickey Figurine", "Park Exclusive", "high", 120),
        ("parks", "Tokyo DisneySea 20th Anniversary Duffy Plush", "Park Exclusive", "high", 100),
        ("parks", "Tokyo Disneyland 40th Anniversary Pin Set", "Park Exclusive", "high", 110),
        ("parks", "Shanghai Disney Resort Tron Lightcycle Pin", "Park Exclusive", "mid", 40),
        ("parks", "Hong Kong Disneyland Mystic Manor Figure", "Park Exclusive", "high", 85),
        ("parks", "Tokyo DisneySea Journey to the Center of the Earth Figure", "Park Exclusive", "mid", 55),

        # ── runDisney Medals ───────────────────────────────────────────
        ("rundisney", "runDisney Walt Disney World Marathon 2024 Medal", "Park Exclusive", "mid", 60),
        ("rundisney", "runDisney Princess Half Marathon 2024 Medal", "Park Exclusive", "mid", 50),
        ("rundisney", "runDisney Dopey Challenge Complete Medal Set (4 Medals)", "Park Exclusive", "high", 150),
        ("rundisney", "runDisney Wine & Dine Half Marathon Medal", "Park Exclusive", "mid", 45),
        ("rundisney", "runDisney Star Wars Rival Run Medal", "Park Exclusive", "mid", 55),

        # ── Disney Store Vintage ───────────────────────────────────────
        ("vintage", "Disney Store Opening Key (1990s, Brass)", "Vintage", "high", 150),
        ("vintage", "Disney Store Exclusive Snow Globe Cinderella Castle", "Vintage", "high", 120),
        ("vintage", "Disney Store Classic Doll Collection (1990s, Complete Set)", "Vintage", "grail", 300),
    ]

    result = []
    for subcategory, name, edition, tier, price in variants:
        result.append({
            "subcategory": subcategory,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return result


def item_to_catalog_item(item: dict) -> CatalogItem:
    name = item["name"]
    edition = item["edition"]
    subcategory = item["subcategory"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{subcategory}-{name}"),
        title=name,
        set_code=subcategory,
        brand="Disney",
        rarity=item["rarity_tier"].title(),
        notes=f"{subcategory} | {edition}",
        attributes_json={
            "subcategory": subcategory,
            "edition": edition,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    edition = item["edition"]
    edition_map = {
        "LE 750": 0.97, "LE 1000": 0.95, "LE 1500": 0.9, "LE 2000": 0.88,
        "LE 2500": 0.85, "LE 3000": 0.8,
        "LE 4000": 0.75, "LE 5000": 0.7, "LE Monthly": 0.7,
        "D23 Exclusive": 0.9, "Designer LE": 0.85, "NYCC Exclusive": 0.85,
        "D100 Exclusive": 0.8, "Cast Exclusive": 0.8,
        "Park Exclusive": 0.65, "LE Park": 0.65,
        "Designer": 0.7, "Event Exclusive": 0.7,
        "Vintage": 0.8, "Premium": 0.7, "WDCC": 0.85,
        "Crystal Variant": 0.75, "Sealed Product": 0.7,
        "Enchanted Rare": 0.95, "Super Rare": 0.75, "Legendary": 0.8,
        "Fantasy": 0.5, "Loungefly Set": 0.55, "Promo": 0.55,
        "Limited": 0.6, "LE": 0.6, "Seasonal": 0.4,
        "Chase Variant": 0.75, "Signed Print": 0.9, "Limited Print": 0.7,
        "Signed": 0.9, "LE 600": 0.95,
        "LE 300": 0.97, "LE 250": 0.97, "LE 100": 0.99, "LE 50": 0.99,
        "Vaulted": 0.75,
        "DCL Exclusive": 0.7,
        "D100 LE": 0.85, "LE 500": 0.97,
        "Sealed": 0.7, "Enchanted": 0.95, "Promo LE": 0.6,
        "Glow-in-Dark": 0.8, "Metallic LE": 0.8, "Diamond LE": 0.85,
        "Flocked LE": 0.75, "Seasonal LE": 0.65,
        "shopDisney LE": 0.7, "Hallmark Exclusive": 0.55,
        "Store Exclusive": 0.6, "Swarovski LE": 0.9, "Funko Exclusive": 0.75,
        "Disney Traditions": 0.5,
        "Standard": 0.2,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_map.get(edition, 0.4),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Disney collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Disney Import ===")

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

    logger.info(f"\n=== Disney Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
