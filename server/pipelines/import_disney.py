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

    catalog = []
    for subcategory, name, edition, tier, price in items:
        catalog.append({
            "subcategory": subcategory,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


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
