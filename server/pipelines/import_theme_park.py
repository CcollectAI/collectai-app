"""
Import theme park exclusives catalog.

Layer 1 (Catalog):  Curated park-only merch & resale collectibles (500+ items) → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (eBay, Mercari, Yahoo Auctions JP)
- Covers Disney Parks popcorn buckets, Tokyo Disney, Universal Studios Japan,
  pin events, park-exclusive Funko Pops, grand opening merch, EPCOT festivals,
  Disneyland Paris, Shanghai Disney, Hong Kong Disney, LEGOLAND,
  Cedar Point, Six Flags, Disney Cruise Line, Epic Universe

Usage:
    python -m pipelines.import_theme_park [--dry-run]
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

CATEGORY = "theme_park"


def get_curated_catalog() -> list[dict]:
    """Curated theme park exclusives catalog (500+ items)."""

    # (park, subcategory, name, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>150), high (60-150), mid (25-60), standard (<25)

    items = [
        # Disney Parks Popcorn Buckets
        ("Disney Parks", "popcorn_bucket", "Figment Popcorn Bucket (Epcot)", "Limited Release", "high", 120),
        ("Disney Parks", "popcorn_bucket", "Purple Wall Popcorn Bucket", "Park Exclusive", "high", 80),
        ("Disney Parks", "popcorn_bucket", "Mickey Balloon Popcorn Bucket", "Park Exclusive", "mid", 55),
        ("Disney Parks", "popcorn_bucket", "R2-D2 Popcorn Bucket (Galaxy's Edge)", "Park Exclusive", "mid", 45),
        ("Disney Parks", "popcorn_bucket", "Cinderella Carriage Popcorn Bucket (TDL)", "Tokyo Exclusive", "high", 90),
        ("Disney Parks", "popcorn_bucket", "Slinky Dog Popcorn Bucket", "Park Exclusive", "mid", 40),
        ("Disney Parks", "popcorn_bucket", "Haunted Mansion Doom Buggy Popcorn Bucket", "LE", "grail", 150),

        # Tokyo Disney Exclusives
        ("Tokyo Disney", "snack_case", "Duffy Snack Case (TDS)", "Tokyo Exclusive", "mid", 45),
        ("Tokyo Disney", "snack_case", "StellaLou Candy Case", "Tokyo Exclusive", "mid", 40),
        ("Tokyo Disney", "plush", "Duffy 20th Anniversary Plush Set", "Anniversary LE", "high", 130),
        ("Tokyo Disney", "plush", "LinaBell Plush (TDS Exclusive)", "Tokyo Exclusive", "high", 85),
        ("Tokyo Disney", "plush", "Olu Mel Plush (Hawaii Exclusive)", "Park Exclusive", "high", 70),
        ("Tokyo Disney", "pins", "Tokyo Disney 40th Anniversary Pin Set", "Anniversary LE", "high", 95),
        ("Tokyo Disney", "merch", "Fantasy Springs Grand Opening Tee", "Grand Opening", "high", 65),
        ("Tokyo Disney", "merch", "TDL 40th Anniversary Popcorn Tin", "Anniversary LE", "mid", 50),

        # Universal Studios Japan
        ("USJ", "merch", "Super Nintendo World Grand Opening Set", "Grand Opening", "grail", 180),
        ("USJ", "merch", "Mario Power-Up Band (Gold Star)", "Park Exclusive", "mid", 35),
        ("USJ", "merch", "Mario Kart Popcorn Bucket", "Park Exclusive", "mid", 55),
        ("USJ", "merch", "USJ Jujutsu Kaisen Collab Tee", "Collab Exclusive", "mid", 40),
        ("USJ", "merch", "Donkey Kong Country Grand Opening Set", "Grand Opening", "high", 140),
        ("USJ", "figure", "USJ Exclusive Mewtwo Figure", "Park Exclusive", "high", 65),
        ("USJ", "figure", "Nintendo World Pikmin Exclusive Figure Set", "Park Exclusive", "mid", 50),

        # Disney Pin Events
        ("Disney Parks", "pin_event", "Disney Pin Trading Night LE 300", "LE 300", "grail", 180),
        ("Disney Parks", "pin_event", "EPCOT Festival Pin Board Complete Set", "Festival LE", "high", 100),
        ("Disney Parks", "pin_event", "Disneyland AP Exclusive Pin Set (2024)", "AP Exclusive", "high", 70),

        # Park-Exclusive Funko Pops
        ("Disney Parks", "funko", "Funko Pop Haunted Mansion Hitchhiking Ghosts", "Park Exclusive", "high", 85),
        ("Disney Parks", "funko", "Funko Pop Orange Bird (Disney Parks)", "Park Exclusive", "high", 65),
        ("Disney Parks", "funko", "Funko Pop Figment (Epcot)", "Park Exclusive", "mid", 45),
        ("USJ", "funko", "Funko Pop Mario (USJ Exclusive)", "Park Exclusive", "high", 75),

        # Grand Opening / Anniversary
        ("Disney Parks", "anniversary", "Walt Disney World 50th Anniversary Spirit Jersey", "Anniversary LE", "high", 90),
        ("Disney Parks", "anniversary", "Disneyland 70th Anniversary Poster Set", "Anniversary LE", "high", 80),
        ("Disney Parks", "anniversary", "EPCOT 40th Anniversary Figment Figure", "Anniversary LE", "high", 95),
        ("Disney Parks", "anniversary", "Disney100 Platinum Celebration Pin", "D100 Exclusive", "mid", 45),
        ("USJ", "anniversary", "USJ 20th Anniversary Exclusive Pin Set", "Anniversary LE", "high", 70),

        # --- Additional Disney Parks Popcorn Buckets ---
        ("Disney Parks", "popcorn_bucket", "Dumbo Popcorn Bucket (Magic Kingdom)", "Park Exclusive", "high", 75),
        ("Disney Parks", "popcorn_bucket", "Little Mermaid Shell Popcorn Bucket", "Park Exclusive", "mid", 50),
        ("Disney Parks", "popcorn_bucket", "Ratatouille Remy Popcorn Bucket (Epcot)", "Park Exclusive", "high", 65),
        ("Disney Parks", "popcorn_bucket", "Nightmare Before Christmas Popcorn Bucket", "Limited Release", "high", 110),

        # --- Universal Studios (expanded) ---
        ("USJ", "popcorn_bucket", "USJ Jaws Popcorn Bucket", "Park Exclusive", "high", 70),
        ("USJ", "merch", "Super Nintendo World Power Star Popcorn Tin", "Park Exclusive", "mid", 45),
        ("Universal Orlando", "merch", "Wizarding World Butterbeer Stein Mug", "Park Exclusive", "mid", 35),
        ("Universal Orlando", "merch", "Jurassic World Raptor Popcorn Bucket", "Park Exclusive", "mid", 40),
        ("Universal Orlando", "merch", "Halloween Horror Nights 2024 Exclusive Tee", "Limited Release", "high", 60),
        ("Universal Orlando", "merch", "VelociCoaster Grand Opening Pin Set", "Grand Opening", "high", 85),

        # --- Tokyo DisneySea (expanded) ---
        ("Tokyo Disney", "plush", "Duffy Exclusive Plush (TDS 2024)", "Tokyo Exclusive", "high", 95),
        ("Tokyo Disney", "plush", "ShellieMay Plush (TDS Exclusive)", "Tokyo Exclusive", "high", 80),
        ("Tokyo Disney", "plush", "Gelatoni Plush (TDS Exclusive)", "Tokyo Exclusive", "high", 75),
        ("Tokyo Disney", "plush", "StellaLou Plush (TDS Exclusive)", "Tokyo Exclusive", "high", 80),
        ("Tokyo Disney", "merch", "Tokyo DisneySea 20th Anniversary Exclusive Set", "Anniversary LE", "grail", 160),

        # --- Shanghai Disneyland ---
        ("Shanghai Disney", "merch", "Shanghai Disneyland Grand Opening Pin Set (2016)", "Grand Opening", "grail", 200),
        ("Shanghai Disney", "merch", "Zootopia Land Grand Opening Exclusive Set", "Grand Opening", "high", 110),
        ("Shanghai Disney", "merch", "Chinese New Year Exclusive Mickey Plush", "Limited Release", "high", 65),

        # --- Disney Pin Events (expanded) ---
        ("Disney Parks", "pin_event", "Epcot International Food & Wine Festival Pin Set", "Festival LE", "high", 85),
        ("Disney Parks", "pin_event", "Mickey's Not-So-Scary Halloween Party Pin Set", "LE", "high", 95),
        ("Disney Parks", "pin_event", "Disney After Hours BOO Bash Event Pin", "LE", "high", 75),
        ("Disney Parks", "pin_event", "runDisney Marathon Weekend Medal Set", "Limited Release", "high", 110),

        # --- Vintage Park Collectibles ---
        ("Disney Parks", "vintage", "Vintage Disneyland Ticket Book (A-E Tickets)", "Vintage", "grail", 350),
        ("Disney Parks", "vintage", "1971 Walt Disney World Opening Day Guide Map", "Vintage", "grail", 280),
        ("Disney Parks", "vintage", "Vintage Disney Park Souvenir Glass Set (1970s)", "Vintage", "high", 90),
        ("Disney Parks", "vintage", "Disney on Ice Program Booklet (1980s)", "Vintage", "mid", 30),
        ("Disney Parks", "vintage", "Disneyland Hotel Vintage Ashtray (1960s)", "Vintage", "high", 120),

        # --- Grand Opening / Anniversary (expanded) ---
        ("Disney Parks", "anniversary", "Star Wars Galaxy's Edge Grand Opening Pin Set", "Grand Opening", "high", 130),
        ("Disney Parks", "anniversary", "Pandora World of Avatar Grand Opening Banshee Figure", "Grand Opening", "high", 100),
        ("Disney Parks", "anniversary", "Tron Lightcycle Run Grand Opening Tee", "Grand Opening", "high", 70),
        ("Disney Parks", "anniversary", "Guardians Cosmic Rewind Grand Opening Pin", "Grand Opening", "high", 65),
        ("Disney Parks", "anniversary", "Disney100 Celebration Exclusive Collectible Set", "D100 Exclusive", "grail", 175),

        # --- More Disney Popcorn Buckets ---
        ("Disney Parks", "popcorn_bucket", "Ratatouille Chef Remy Popcorn Bucket (Epcot France)", "Park Exclusive", "high", 70),
        ("Disney Parks", "popcorn_bucket", "Figment Dreamfinder Popcorn Bucket (Festival)", "Festival LE", "grail", 160),
        ("Disney Parks", "popcorn_bucket", "Spaceship Earth Popcorn Bucket (EPCOT)", "Park Exclusive", "mid", 50),

        # --- EPCOT Festival Exclusives ---
        ("Disney Parks", "festival", "EPCOT Food & Wine Festival Passholder Pin Set (2024)", "AP Exclusive", "high", 75),
        ("Disney Parks", "festival", "EPCOT Flower & Garden Festival Figment Spike (2024)", "Festival LE", "high", 85),
        ("Disney Parks", "festival", "EPCOT International Festival of the Arts Spirit Jersey", "Festival LE", "high", 70),
        ("Disney Parks", "festival", "EPCOT Food & Wine Festival Chef Mickey Apron", "Festival LE", "mid", 40),

        # --- Magic Kingdom 50th Anniversary ---
        ("Disney Parks", "anniversary", "MK 50th Anniversary Golden Ear Headband", "Anniversary LE", "high", 80),
        ("Disney Parks", "anniversary", "MK 50th Anniversary Spirit Jersey (Gold)", "Anniversary LE", "high", 90),
        ("Disney Parks", "anniversary", "MK 50th Anniversary Loungefly Backpack", "Anniversary LE", "high", 110),
        ("Disney Parks", "anniversary", "MK 50th Anniversary Castle Pin", "Anniversary LE", "mid", 55),

        # --- Disneyland Paris Exclusives ---
        ("Disneyland Paris", "merch", "Disneyland Paris 30th Anniversary Spirit Jersey", "Anniversary LE", "high", 85),
        ("Disneyland Paris", "merch", "Disneyland Paris Ratatouille Exclusive Tee", "Park Exclusive", "mid", 35),
        ("Disneyland Paris", "merch", "Disneyland Paris Exclusive Stitch Pin Set", "Park Exclusive", "mid", 40),
        ("Disneyland Paris", "plush", "Disneyland Paris Exclusive Duffy (French Chef)", "Park Exclusive", "high", 70),

        # --- Universal Studios Japan (expanded) ---
        ("USJ", "merch", "USJ Exclusive One Piece Chopper Plush", "Park Exclusive", "high", 60),
        ("USJ", "merch", "USJ Attack on Titan Collab Exclusive Tee", "Collab Exclusive", "mid", 45),
        ("USJ", "merch", "USJ Demon Slayer Collab Pin Set", "Collab Exclusive", "high", 65),

        # --- Universal Epic Universe (2025) ---
        ("Universal Orlando", "merch", "Epic Universe Grand Opening Commemorative Pin Set", "Grand Opening", "grail", 180),
        ("Universal Orlando", "merch", "Epic Universe Grand Opening Spirit Jersey", "Grand Opening", "high", 80),
        ("Universal Orlando", "merch", "How to Train Your Dragon Isle Grand Opening Plush", "Grand Opening", "high", 65),

        # --- Super Nintendo World ---
        ("USJ", "merch", "Super Nintendo World Power-Up Band (Fire Flower)", "Park Exclusive", "mid", 40),
        ("USJ", "plush", "Super Nintendo World Exclusive Yoshi Plush", "Park Exclusive", "mid", 45),
        ("USJ", "merch", "Super Nintendo World Invincible Star Popcorn Bucket", "Park Exclusive", "high", 65),

        # --- Shanghai Disneyland (expanded) ---
        ("Shanghai Disney", "plush", "Shanghai Disney Exclusive Duffy (Dragon Costume)", "Limited Release", "high", 80),
        ("Shanghai Disney", "merch", "Shanghai Disney LinaBell Lunar New Year Exclusive", "Limited Release", "high", 75),

        # --- Hong Kong Disneyland ---
        ("Hong Kong Disney", "merch", "HKDL Exclusive Cookie Plush (Duffy & Friends)", "Park Exclusive", "high", 65),
        ("Hong Kong Disney", "merch", "HKDL World of Frozen Grand Opening Pin Set", "Grand Opening", "high", 95),

        # --- Tokyo DisneySea Fantasy Springs ---
        ("Tokyo Disney", "merch", "Fantasy Springs Grand Opening Pin Set", "Grand Opening", "high", 110),
        ("Tokyo Disney", "merch", "Fantasy Springs Peter Pan Exclusive Popcorn Bucket", "Park Exclusive", "high", 75),

        # --- Vintage Disneyland ---
        ("Disney Parks", "vintage", "Vintage Disneyland Souvenir Map (1960s)", "Vintage", "grail", 300),
        ("Disney Parks", "vintage", "Vintage Disneyland E-Ticket Stub (1970s)", "Vintage", "high", 120),

        # --- LEGOLAND Exclusives ---
        ("LEGOLAND", "merch", "LEGOLAND Exclusive Dragon Minifigure", "Park Exclusive", "mid", 25),
        ("LEGOLAND", "merch", "LEGOLAND Exclusive Park Model Mini Set", "Park Exclusive", "mid", 30),

        # --- SeaWorld / Busch Gardens ---
        ("SeaWorld", "vintage", "Vintage SeaWorld Shamu Souvenir Mug (1980s)", "Vintage", "mid", 35),
        ("Busch Gardens", "vintage", "Vintage Busch Gardens Souvenir Plate (1970s)", "Vintage", "mid", 40),

        # --- Annual Passholder Exclusives ---
        ("Disney Parks", "passholder", "WDW Annual Passholder Exclusive Magnet Set (2024)", "AP Exclusive", "mid", 30),
        ("Disney Parks", "passholder", "Disneyland AP Exclusive Loungefly Ears", "AP Exclusive", "high", 70),

        # --- EPCOT Festival Exclusives (expanded) ---
        ("Disney Parks", "festival", "EPCOT Food & Wine Festival Passholder Figment Mug (2024)", "Festival LE", "mid", 45),
        ("Disney Parks", "festival", "EPCOT Flower & Garden Festival Spike Topiary Popcorn Bucket", "Festival LE", "high", 90),
        ("Disney Parks", "festival", "EPCOT Festival of the Arts Figment Paint Brush Pin", "Festival LE", "high", 65),
        ("Disney Parks", "festival", "EPCOT Food & Wine Festival Spirit Jersey (2024)", "Festival LE", "high", 75),

        # --- Magic Kingdom 50th Anniversary (expanded) ---
        ("Disney Parks", "anniversary", "MK 50th Anniversary EARidescent Tumbler Set", "Anniversary LE", "mid", 40),
        ("Disney Parks", "anniversary", "MK 50th Anniversary Vault Collection Plush (Mickey)", "Anniversary LE", "high", 65),
        ("Disney Parks", "anniversary", "MK 50th Anniversary Golden Castle Ornament", "Anniversary LE", "mid", 50),

        # --- Disneyland Paris (expanded) ---
        ("Disneyland Paris", "merch", "Disneyland Paris 30th Anniversary Pin Set", "Anniversary LE", "high", 70),
        ("Disneyland Paris", "merch", "Disneyland Paris 30th Anniversary Loungefly Bag", "Anniversary LE", "high", 95),
        ("Disneyland Paris", "plush", "Disneyland Paris Exclusive StellaLou (Parisian)", "Park Exclusive", "high", 75),

        # --- Universal Studios Japan (expanded) ---
        ("USJ", "merch", "USJ Exclusive Minion Popcorn Bucket (Banana)", "Park Exclusive", "mid", 50),
        ("USJ", "merch", "USJ One Piece Premier Summer Exclusive Tee", "Collab Exclusive", "mid", 45),
        ("USJ", "figure", "USJ Exclusive One Piece Thousand Sunny Figure", "Park Exclusive", "high", 80),

        # --- Universal Epic Universe (expanded) ---
        ("Universal Orlando", "merch", "Epic Universe Dark Universe Grand Opening Poster", "Grand Opening", "high", 60),
        ("Universal Orlando", "merch", "Epic Universe Celestial Park Exclusive Pin Set", "Grand Opening", "high", 75),
        ("Universal Orlando", "merch", "Epic Universe Opening Day Commemorative Ticket", "Grand Opening", "grail", 150),

        # --- Super Nintendo World (expanded) ---
        ("USJ", "merch", "Super Nintendo World ? Block Popcorn Bucket", "Park Exclusive", "high", 70),
        ("USJ", "merch", "Super Nintendo World Power-Up Band (Toad)", "Park Exclusive", "mid", 38),
        ("USJ", "merch", "Super Nintendo World Yoshi's Adventure Exclusive Plush", "Park Exclusive", "mid", 45),
        ("USJ", "merch", "Super Nintendo World Bowser's Castle Mug", "Park Exclusive", "mid", 35),

        # --- Shanghai Disneyland (expanded) ---
        ("Shanghai Disney", "plush", "Shanghai Disney Exclusive LinaBell Plush (Springtime)", "Limited Release", "high", 85),
        ("Shanghai Disney", "plush", "Shanghai Disney Exclusive StellaLou Plush (Shanghai Costume)", "Park Exclusive", "high", 70),
        ("Shanghai Disney", "merch", "Shanghai Disney Duffy & Friends Tea Set (Exclusive)", "Park Exclusive", "high", 90),

        # --- Hong Kong Disneyland (expanded) ---
        ("Hong Kong Disney", "merch", "HKDL Exclusive Duffy Bear Plush (Sailor)", "Park Exclusive", "high", 60),
        ("Hong Kong Disney", "merch", "HKDL World of Frozen Elsa Ice Palace Ornament", "Grand Opening", "high", 70),

        # --- Tokyo DisneySea Fantasy Springs (expanded) ---
        ("Tokyo Disney", "merch", "Fantasy Springs Rapunzel Lantern Popcorn Bucket", "Park Exclusive", "high", 85),
        ("Tokyo Disney", "merch", "Fantasy Springs Frozen Arendelle Exclusive Mug", "Park Exclusive", "mid", 40),
        ("Tokyo Disney", "merch", "Fantasy Springs Peter Pan Neverland Exclusive Plush", "Park Exclusive", "high", 65),

        # --- Vintage Disneyland (expanded) ---
        ("Disney Parks", "vintage", "Vintage Disneyland Souvenir Pennant (1960s)", "Vintage", "high", 140),
        ("Disney Parks", "vintage", "Vintage Walt Disney World Souvenir Guide (1971)", "Vintage", "grail", 250),

        # --- LEGOLAND Exclusives (expanded) ---
        ("LEGOLAND", "merch", "LEGOLAND Exclusive Master Builder Minifigure Set", "Park Exclusive", "mid", 35),
        ("LEGOLAND", "merch", "LEGOLAND Exclusive Park Entrance Mini Set", "Park Exclusive", "mid", 28),

        # --- Cedar Point / Six Flags Vintage ---
        ("Cedar Point", "vintage", "Cedar Point Vintage Roller Coaster Poster (1970s)", "Vintage", "high", 90),
        ("Cedar Point", "vintage", "Cedar Point 150th Anniversary Commemorative Coin", "Anniversary LE", "mid", 45),
        ("Six Flags", "vintage", "Six Flags Over Texas Vintage Souvenir Guide (1960s)", "Vintage", "high", 110),

        # --- Disney Cruise Line ---
        ("Disney Cruise Line", "merch", "Disney Cruise Line Castaway Cay Exclusive Pin Set", "Limited Release", "high", 65),
        ("Disney Cruise Line", "merch", "Disney Cruise Line Disney Wish Maiden Voyage Pin", "Grand Opening", "high", 95),
        ("Disney Cruise Line", "merch", "Disney Cruise Line Captain Mickey Plush (Ship Exclusive)", "Park Exclusive", "mid", 45),

        # === ROUND 4 — 68 new items ===

        # --- Walt Disney World — Hollywood Studios ---
        ("Disney Parks", "merch", "Tower of Terror Bellhop Funko Pop", "Park Exclusive", "high", 75),
        ("Disney Parks", "merch", "Toy Story Mania Grand Opening Pin", "Grand Opening", "high", 80),
        ("Disney Parks", "merch", "Star Wars Rise of the Resistance Grand Opening Pin Set", "Grand Opening", "high", 95),
        ("Disney Parks", "merch", "Mickey & Minnie's Runaway Railway Grand Opening Tee", "Grand Opening", "high", 60),

        # --- Walt Disney World — Animal Kingdom ---
        ("Disney Parks", "merch", "Animal Kingdom 25th Anniversary Pin Set", "Anniversary LE", "high", 70),
        ("Disney Parks", "merch", "Expedition Everest Exclusive Yeti Figure", "Park Exclusive", "mid", 45),
        ("Disney Parks", "merch", "Pandora The World of Avatar Na'vi Banshee (Green)", "Park Exclusive", "mid", 55),
        ("Disney Parks", "merch", "Pandora The World of Avatar Na'vi Banshee (Purple)", "Park Exclusive", "mid", 55),

        # --- Disneyland Resort ---
        ("Disney Parks", "merch", "Radiator Springs Racers Grand Opening Pin", "Grand Opening", "high", 85),
        ("Disney Parks", "merch", "Disneyland Haunted Mansion Holiday Gingerbread House Ornament", "Limited Release", "high", 65),
        ("Disney Parks", "merch", "Disneyland Club 33 Exclusive Pin Set (2024)", "LE 300", "grail", 250),
        ("Disney Parks", "merch", "Disneyland Main Street Electrical Parade 50th Anniv. Set", "Anniversary LE", "high", 90),

        # --- Disney Springs / Downtown Disney ---
        ("Disney Parks", "merch", "Disney Springs World of Disney Exclusive Loungefly Bag", "Park Exclusive", "mid", 55),
        ("Disney Parks", "merch", "Disney Springs Coca-Cola Store Exclusive Pin Set", "Park Exclusive", "mid", 30),

        # --- Galaxy's Edge ---
        ("Disney Parks", "merch", "Galaxy's Edge Kyber Crystal (Red — Dark Side)", "Park Exclusive", "mid", 30),
        ("Disney Parks", "merch", "Galaxy's Edge Kyber Crystal (Green)", "Park Exclusive", "mid", 28),
        ("Disney Parks", "merch", "Galaxy's Edge Custom Lightsaber (Savi's Workshop)", "Park Exclusive", "high", 85),
        ("Disney Parks", "merch", "Galaxy's Edge Droid Depot Custom R-Unit", "Park Exclusive", "high", 110),

        # --- Universal Studios Hollywood ---
        ("Universal Hollywood", "merch", "Wizarding World Butterbeer Mug (Hollywood)", "Park Exclusive", "mid", 35),
        ("Universal Hollywood", "merch", "Studio Tour 60th Anniversary Pin", "Anniversary LE", "high", 65),
        ("Universal Hollywood", "merch", "Super Nintendo World Hollywood Grand Opening Set", "Grand Opening", "grail", 160),
        ("Universal Hollywood", "merch", "Universal Hollywood Horror Nights 2024 Tee", "Limited Release", "high", 55),

        # --- Universal Studios Singapore ---
        ("Universal Singapore", "merch", "USS Exclusive Transformers Pin Set", "Park Exclusive", "mid", 40),
        ("Universal Singapore", "merch", "USS Sesame Street Exclusive Plush Set", "Park Exclusive", "mid", 45),

        # --- Universal Studios Beijing ---
        ("Universal Beijing", "merch", "Universal Beijing Grand Opening Pin Set (2021)", "Grand Opening", "grail", 150),
        ("Universal Beijing", "merch", "Kung Fu Panda Land Exclusive Figure", "Park Exclusive", "mid", 50),

        # --- Tokyo Disney (more) ---
        ("Tokyo Disney", "snack_case", "Mickey Ice Bar Candy Case", "Tokyo Exclusive", "mid", 35),
        ("Tokyo Disney", "snack_case", "Baymax Mochi Case", "Tokyo Exclusive", "mid", 38),
        ("Tokyo Disney", "plush", "LinaBell Cherry Blossom Costume Plush (TDS)", "Limited Release", "high", 100),
        ("Tokyo Disney", "plush", "CookieAnn Plush (TDS Exclusive)", "Tokyo Exclusive", "high", 75),
        ("Tokyo Disney", "merch", "Tokyo Disney 41st Anniversary Collectible Medal", "Anniversary LE", "mid", 35),

        # --- Shanghai Disney (more) ---
        ("Shanghai Disney", "merch", "Shanghai Disney Castle Light-Up Ornament", "Park Exclusive", "mid", 40),
        ("Shanghai Disney", "plush", "Shanghai Disney Exclusive Olu Mel Plush (Shanghai Costume)", "Park Exclusive", "high", 70),

        # --- Hong Kong Disney (more) ---
        ("Hong Kong Disney", "merch", "HKDL Exclusive Mystic Manor Figure Set", "Park Exclusive", "high", 80),
        ("Hong Kong Disney", "merch", "HKDL 18th Anniversary Exclusive Pin Set", "Anniversary LE", "high", 65),

        # --- Aulani Hawaii ---
        ("Disney Parks", "merch", "Aulani Exclusive Duffy Plush (Hawaiian Shirt)", "Park Exclusive", "high", 85),
        ("Disney Parks", "merch", "Aulani Exclusive Olu Mel Pin Set", "Park Exclusive", "mid", 40),

        # --- Disney Cruise Line (expanded) ---
        ("Disney Cruise Line", "merch", "Disney Cruise Line Disney Treasure Maiden Voyage Pin", "Grand Opening", "high", 100),
        ("Disney Cruise Line", "merch", "Disney Cruise Line Castaway Cay Exclusive Magnet Set", "Park Exclusive", "standard", 18),
        ("Disney Cruise Line", "merch", "Disney Cruise Line AquaDuck Exclusive Tee", "Park Exclusive", "mid", 35),

        # --- Universal Epic Universe (more) ---
        ("Universal Orlando", "merch", "Epic Universe Super Nintendo World Power Star Pin", "Grand Opening", "high", 55),
        ("Universal Orlando", "merch", "Epic Universe Starfall Racers Grand Opening Poster", "Grand Opening", "high", 50),

        # --- LEGOLAND (expanded) ---
        ("LEGOLAND", "merch", "LEGOLAND Exclusive LEGO City Police Station Mini Set", "Park Exclusive", "mid", 32),
        ("LEGOLAND", "merch", "LEGOLAND Florida Grand Opening Brick", "Grand Opening", "high", 60),

        # --- Knott's Berry Farm ---
        ("Knott's Berry Farm", "vintage", "Knott's Berry Farm Vintage Souvenir Plate (1970s)", "Vintage", "high", 80),
        ("Knott's Berry Farm", "merch", "Knott's Scary Farm 50th Anniversary Pin Set", "Anniversary LE", "high", 65),

        # --- Alton Towers / Thorpe Park (UK) ---
        ("Alton Towers", "merch", "Alton Towers Exclusive Nemesis Reborn Grand Opening Pin", "Grand Opening", "high", 55),
        ("Thorpe Park", "merch", "Thorpe Park Exclusive Stealth Roller Coaster Model", "Park Exclusive", "mid", 40),

        # --- Europa-Park (Germany) ---
        ("Europa-Park", "merch", "Europa-Park Exclusive Ed Euromaus Plush", "Park Exclusive", "mid", 30),
        ("Europa-Park", "merch", "Europa-Park 50th Anniversary Commemorative Coin", "Anniversary LE", "high", 55),

        # --- Vintage Disney Ephemera ---
        ("Disney Parks", "vintage", "Vintage EPCOT Center Opening Day Guidemap (1982)", "Vintage", "grail", 200),
        ("Disney Parks", "vintage", "Vintage Disneyland Souvenir Postcard Set (1950s)", "Vintage", "grail", 350),

        # --- More Pin Trading ---
        ("Disney Parks", "pin_event", "Disneyland 69th Anniversary Pin (2024)", "Anniversary LE", "mid", 40),
        ("Disney Parks", "pin_event", "WDW Marathon Weekend 2025 Finisher Medal Set", "Limited Release", "high", 120),
        ("Disney Parks", "pin_event", "Disney Pin Trading 25th Anniversary Jumbo Pin", "LE 300", "grail", 200),

        # --- More Annual Passholder ---
        ("Disney Parks", "passholder", "WDW Annual Passholder Exclusive Quarterly Pin (Q4 2024)", "AP Exclusive", "mid", 35),
        ("Disney Parks", "passholder", "Disneyland Magic Key Exclusive Loungefly Wallet", "AP Exclusive", "high", 65),

        # --- More Popcorn Buckets ---
        ("Disney Parks", "popcorn_bucket", "Moana Te Fiti Popcorn Bucket", "Park Exclusive", "high", 80),
        ("Disney Parks", "popcorn_bucket", "Villains Maleficent Dragon Popcorn Bucket", "Limited Release", "grail", 130),
        ("Disney Parks", "popcorn_bucket", "Tiana Bayou Popcorn Bucket (New Orleans Square)", "Park Exclusive", "high", 75),

        # === ROUND 5 — Massive expansion to 500+ ===

        # --- Walt Disney World — Magic Kingdom ---
        ("Disney Parks", "merch", "Space Mountain Retro Logo Spirit Jersey", "Park Exclusive", "mid", 55),
        ("Disney Parks", "merch", "Haunted Mansion Butler Gargoyle Figure", "Park Exclusive", "high", 85),
        ("Disney Parks", "merch", "Pirates of the Caribbean Treasure Chest Popcorn Bucket", "Park Exclusive", "high", 70),
        ("Disney Parks", "merch", "Seven Dwarfs Mine Train Grand Opening Pin", "Grand Opening", "high", 95),
        ("Disney Parks", "merch", "Tron Lightcycle Run Identity Disc Replica", "Park Exclusive", "high", 110),
        ("Disney Parks", "popcorn_bucket", "Buzz Lightyear Popcorn Bucket (Space Ranger Spin)", "Park Exclusive", "mid", 45),
        ("Disney Parks", "merch", "Country Bear Jamboree Closing Day Pin Set", "LE", "high", 120),
        ("Disney Parks", "merch", "Carousel of Progress Salt & Pepper Set", "Park Exclusive", "mid", 35),
        ("Disney Parks", "merch", "It's a Small World Clock Ornament", "Park Exclusive", "mid", 40),
        ("Disney Parks", "merch", "Jungle Cruise Skipper Canteen Menu Pin Set", "Park Exclusive", "mid", 30),
        ("Disney Parks", "merch", "Big Thunder Mountain Railroad Dynamite Popcorn Bucket", "Limited Release", "high", 85),
        ("Disney Parks", "merch", "PeopleMover Retro Poster Tee", "Park Exclusive", "mid", 35),

        # --- Walt Disney World — EPCOT ---
        ("Disney Parks", "merch", "Journey Into Imagination Figment Spirit Jersey", "Park Exclusive", "high", 70),
        ("Disney Parks", "merch", "Spaceship Earth Blueprint Poster Print", "Park Exclusive", "mid", 40),
        ("Disney Parks", "merch", "Test Track Speedway Mug", "Park Exclusive", "standard", 22),
        ("Disney Parks", "merch", "Remy's Ratatouille Adventure Grand Opening Pin", "Grand Opening", "high", 80),
        ("Disney Parks", "merch", "Figment Rainbow Spirit Jersey", "Park Exclusive", "high", 75),
        ("Disney Parks", "merch", "World Showcase Passport Holder Set", "Park Exclusive", "mid", 28),
        ("Disney Parks", "merch", "Living with the Land Greenhouse Mug", "Park Exclusive", "standard", 20),
        ("Disney Parks", "merch", "Guardians of the Galaxy Cosmic Rewind Collector Tee", "Park Exclusive", "mid", 40),

        # --- Walt Disney World — Hollywood Studios ---
        ("Disney Parks", "merch", "Tower of Terror Final Check-Out Bell Replica", "Park Exclusive", "high", 90),
        ("Disney Parks", "merch", "Rock 'n' Roller Coaster Backstage Pass Pin", "Park Exclusive", "mid", 35),
        ("Disney Parks", "merch", "Fantasmic! Sorcerer Hat Glow Ears", "Park Exclusive", "mid", 45),
        ("Disney Parks", "merch", "Star Wars Launch Bay Exclusive Lightsaber Pin Set", "Park Exclusive", "mid", 40),
        ("Disney Parks", "merch", "Muppet*Vision 3D Vintage Poster Tee", "Park Exclusive", "mid", 32),
        ("Disney Parks", "merch", "Sunset Boulevard Tower of Terror Spirit Jersey", "Park Exclusive", "high", 65),

        # --- Walt Disney World — Animal Kingdom ---
        ("Disney Parks", "merch", "Kilimanjaro Safaris Retro Poster Pin", "Park Exclusive", "mid", 28),
        ("Disney Parks", "merch", "Tree of Life Light-Up Ornament", "Park Exclusive", "mid", 45),
        ("Disney Parks", "merch", "Dinosaur Ride Photo Frame", "Park Exclusive", "standard", 18),
        ("Disney Parks", "merch", "Pandora Na'vi Banshee (Red Variation)", "Park Exclusive", "mid", 55),
        ("Disney Parks", "merch", "Expedition Everest Yeti Claw Mark Pin", "Park Exclusive", "mid", 30),

        # --- Disneyland Resort ---
        ("Disney Parks", "merch", "Matterhorn Abominable Snowman Figure", "Park Exclusive", "high", 75),
        ("Disney Parks", "merch", "Indiana Jones Adventure Idol Popcorn Bucket", "Park Exclusive", "high", 80),
        ("Disney Parks", "merch", "Haunted Mansion Stretching Room Canvas Set", "Park Exclusive", "high", 95),
        ("Disney Parks", "merch", "Cars Land Neon Poster Print", "Park Exclusive", "mid", 35),
        ("Disney Parks", "merch", "Incredicoaster Grand Opening Pin Set", "Grand Opening", "high", 70),
        ("Disney Parks", "merch", "Pixar Pier Lamppost Light-Up Ornament", "Park Exclusive", "mid", 40),
        ("Disney Parks", "merch", "Guardians Mission Breakout Grand Opening Pin", "Grand Opening", "high", 75),
        ("Disney Parks", "merch", "Splash Mountain Final Ride Cast Member Pin", "LE 300", "grail", 300),
        ("Disney Parks", "merch", "Disneyland Railroad Conductor Hat", "Park Exclusive", "mid", 35),
        ("Disney Parks", "merch", "Main Street U.S.A. Confectionery Candy Box Set", "Park Exclusive", "standard", 22),

        # --- Galaxy's Edge (expanded) ---
        ("Disney Parks", "merch", "Galaxy's Edge Holocron (Jedi)", "Park Exclusive", "mid", 50),
        ("Disney Parks", "merch", "Galaxy's Edge Holocron (Sith)", "Park Exclusive", "mid", 50),
        ("Disney Parks", "merch", "Galaxy's Edge Ronto Roasters Spork Set", "Park Exclusive", "standard", 18),
        ("Disney Parks", "merch", "Galaxy's Edge Oga's Cantina Porg Mug", "Park Exclusive", "mid", 40),
        ("Disney Parks", "merch", "Galaxy's Edge Batuuan Spira Gift Card (Metal)", "Park Exclusive", "mid", 35),
        ("Disney Parks", "merch", "Galaxy's Edge DJ R-3X Figure", "Park Exclusive", "mid", 55),
        ("Disney Parks", "merch", "Galaxy's Edge Legacy Lightsaber (Ahsoka)", "Park Exclusive", "high", 130),
        ("Disney Parks", "merch", "Galaxy's Edge Legacy Lightsaber (Darth Maul)", "Park Exclusive", "high", 120),
        ("Disney Parks", "merch", "Galaxy's Edge Legacy Lightsaber (Mace Windu)", "Park Exclusive", "high", 115),
        ("Disney Parks", "merch", "Galaxy's Edge Thermal Detonator Coca-Cola Bottle", "Park Exclusive", "mid", 30),

        # --- More Disney Popcorn Buckets ---
        ("Disney Parks", "popcorn_bucket", "Haunted Mansion Hearse Popcorn Bucket", "Limited Release", "grail", 140),
        ("Disney Parks", "popcorn_bucket", "Tick-Tock Croc Popcorn Bucket (Peter Pan)", "Park Exclusive", "high", 70),
        ("Disney Parks", "popcorn_bucket", "Wall-E Popcorn Bucket", "Park Exclusive", "high", 65),
        ("Disney Parks", "popcorn_bucket", "Cheshire Cat Popcorn Bucket", "Limited Release", "high", 90),
        ("Disney Parks", "popcorn_bucket", "Stitch Pineapple Popcorn Bucket", "Park Exclusive", "high", 75),
        ("Disney Parks", "popcorn_bucket", "Muppets Swedish Chef Popcorn Bucket", "Limited Release", "high", 80),
        ("Disney Parks", "popcorn_bucket", "Orange Bird Sipper Cup", "Park Exclusive", "mid", 55),
        ("Disney Parks", "popcorn_bucket", "Haunted Mansion Hitchhiking Ghosts Popcorn Bucket", "LE", "grail", 170),
        ("Disney Parks", "popcorn_bucket", "Cinderella Pumpkin Coach Popcorn Bucket", "Limited Release", "high", 85),
        ("Disney Parks", "popcorn_bucket", "Toy Story Alien Claw Machine Popcorn Bucket", "Park Exclusive", "high", 70),

        # --- Disney Ear Headbands ---
        ("Disney Parks", "ears", "Mickey Mouse Main Attraction Ears (Space Mountain)", "Limited Release", "high", 80),
        ("Disney Parks", "ears", "Mickey Mouse Main Attraction Ears (Pirates)", "Limited Release", "high", 85),
        ("Disney Parks", "ears", "Mickey Mouse Main Attraction Ears (Haunted Mansion)", "Limited Release", "high", 90),
        ("Disney Parks", "ears", "Figment Ear Headband", "Park Exclusive", "mid", 40),
        ("Disney Parks", "ears", "Rose Gold Sequin Ear Headband", "Park Exclusive", "mid", 35),
        ("Disney Parks", "ears", "Enchanted Tiki Room Bird Ears", "Park Exclusive", "mid", 38),
        ("Disney Parks", "ears", "Purple Wall Ear Headband", "Park Exclusive", "mid", 32),
        ("Disney Parks", "ears", "Disney100 Ear Headband (Platinum)", "D100 Exclusive", "mid", 45),
        ("Disney Parks", "ears", "Club 33 Exclusive Ear Headband", "LE 300", "grail", 200),
        ("Disney Parks", "ears", "Aulani Resort Plumeria Ear Headband", "Park Exclusive", "mid", 38),
        ("Disney Parks", "ears", "50th Anniversary EARidescent Ear Headband", "Anniversary LE", "high", 65),

        # --- Disney Spirit Jerseys ---
        ("Disney Parks", "spirit_jersey", "Disneyland Tie-Dye Spirit Jersey", "Park Exclusive", "mid", 55),
        ("Disney Parks", "spirit_jersey", "WDW Passholder Spirit Jersey (2024)", "AP Exclusive", "high", 70),
        ("Disney Parks", "spirit_jersey", "Disney Cruise Line Spirit Jersey (Ship Exclusive)", "Park Exclusive", "mid", 60),
        ("Disney Parks", "spirit_jersey", "Epcot International Food & Wine Spirit Jersey", "Festival LE", "high", 75),
        ("Disney Parks", "spirit_jersey", "Haunted Mansion Wallpaper Spirit Jersey", "Park Exclusive", "high", 80),

        # --- Disney Ornaments ---
        ("Disney Parks", "ornament", "Haunted Mansion Stretching Portrait Ornament Set", "Park Exclusive", "high", 70),
        ("Disney Parks", "ornament", "Space Mountain Ornament (Light-Up)", "Park Exclusive", "mid", 35),
        ("Disney Parks", "ornament", "Orange Bird Ornament (EPCOT)", "Park Exclusive", "mid", 28),
        ("Disney Parks", "ornament", "Figment Epcot Festival Ornament", "Festival LE", "mid", 38),

        # --- Disney Mugs ---
        ("Disney Parks", "mug", "Haunted Mansion Doom Buggy Mug", "Park Exclusive", "mid", 30),
        ("Disney Parks", "mug", "Enchanted Tiki Room Jose Tiki Mug", "Park Exclusive", "high", 65),
        ("Disney Parks", "mug", "Trader Sam's Grog Grotto Zombie Tiki Mug", "Park Exclusive", "high", 75),
        ("Disney Parks", "mug", "Oga's Cantina Rancor Tooth Mug", "Park Exclusive", "mid", 50),

        # --- Cast Member Exclusives ---
        ("Disney Parks", "cast_member", "Cast Member Exclusive Name Tag Pin (Vintage)", "LE", "high", 90),
        ("Disney Parks", "cast_member", "Cast Member 50th Anniversary Badge", "LE", "high", 110),
        ("Disney Parks", "cast_member", "Cast Member Holiday Party Pin (2023)", "LE", "mid", 55),
        ("Disney Parks", "cast_member", "Walt Disney Legacy Award Pin", "LE", "grail", 200),

        # --- Disneyland Paris (expanded) ---
        ("Disneyland Paris", "merch", "Disneyland Paris Phantom Manor Spirit Jersey", "Park Exclusive", "high", 80),
        ("Disneyland Paris", "merch", "Disneyland Paris Ratatouille Remy Chef Hat Popcorn Bucket", "Park Exclusive", "high", 70),
        ("Disneyland Paris", "merch", "Disneyland Paris 30th Anniversary Collector Coin", "Anniversary LE", "mid", 40),
        ("Disneyland Paris", "merch", "Disneyland Paris Phantom Manor Exclusive Figure Set", "Park Exclusive", "high", 100),
        ("Disneyland Paris", "merch", "Disneyland Paris Crush's Coaster Grand Opening Pin", "Grand Opening", "high", 65),
        ("Disneyland Paris", "merch", "Disneyland Paris Space Mountain Mission 2 Pin", "Park Exclusive", "mid", 35),
        ("Disneyland Paris", "merch", "Disneyland Paris Avengers Campus Grand Opening Set", "Grand Opening", "high", 95),

        # --- Tokyo Disney (expanded) ---
        ("Tokyo Disney", "snack_case", "LinaBell Heart Snack Case", "Tokyo Exclusive", "mid", 42),
        ("Tokyo Disney", "snack_case", "CookieAnn Macaron Snack Case", "Tokyo Exclusive", "mid", 38),
        ("Tokyo Disney", "snack_case", "Gelatoni Paintbrush Snack Case", "Tokyo Exclusive", "mid", 36),
        ("Tokyo Disney", "plush", "Duffy Heartwarming Days Plush Set", "Limited Release", "high", 110),
        ("Tokyo Disney", "plush", "LinaBell 1st Anniversary Plush", "Anniversary LE", "high", 120),
        ("Tokyo Disney", "plush", "StellaLou Ballet Costume Plush", "Tokyo Exclusive", "high", 85),
        ("Tokyo Disney", "merch", "TDR 40th Anniversary Popcorn Bucket Collection Set", "Anniversary LE", "grail", 180),
        ("Tokyo Disney", "merch", "Tokyo DisneySea Transit Steamer Line Pin Set", "Tokyo Exclusive", "mid", 40),
        ("Tokyo Disney", "merch", "TDL Enchanted Tale of Beauty and Beast Grand Opening Set", "Grand Opening", "high", 130),
        ("Tokyo Disney", "merch", "Tokyo Disney Baymax Happy Ride Pin Set", "Park Exclusive", "mid", 35),
        ("Tokyo Disney", "merch", "Tokyo DisneySea Indiana Jones Exclusive Hat", "Park Exclusive", "mid", 55),
        ("Tokyo Disney", "merch", "TDL Monsters Inc Ride & Go Seek Grand Opening Pin", "Grand Opening", "high", 70),
        ("Tokyo Disney", "pins", "Tokyo Disney 35th Anniversary Pin Set", "Anniversary LE", "high", 80),
        ("Tokyo Disney", "merch", "TDS 15th Anniversary Crystal Sphere Ornament", "Anniversary LE", "grail", 160),

        # --- Shanghai Disneyland (expanded) ---
        ("Shanghai Disney", "merch", "Shanghai Disney Castle of Magical Dreams Light-Up Figure", "Park Exclusive", "high", 85),
        ("Shanghai Disney", "merch", "Shanghai Disney Toy Story Land Alien Swirling Saucers Pin", "Park Exclusive", "mid", 30),
        ("Shanghai Disney", "merch", "Shanghai Disney TRON Realm Grand Opening Pin Set", "Grand Opening", "high", 100),
        ("Shanghai Disney", "plush", "Shanghai Disney Exclusive Duffy (Spring Costume)", "Limited Release", "high", 70),
        ("Shanghai Disney", "merch", "Shanghai Disney 5th Anniversary Spirit Jersey", "Anniversary LE", "high", 75),

        # --- Hong Kong Disneyland (expanded) ---
        ("Hong Kong Disney", "merch", "HKDL Ant-Man Nano Battle Grand Opening Pin", "Grand Opening", "high", 65),
        ("Hong Kong Disney", "merch", "HKDL Castle of Magical Dreams Grand Opening Set", "Grand Opening", "high", 110),
        ("Hong Kong Disney", "merch", "HKDL Exclusive Duffy (Chef Costume)", "Park Exclusive", "mid", 55),
        ("Hong Kong Disney", "merch", "HKDL 17th Anniversary Collector Set", "Anniversary LE", "high", 70),

        # --- Universal Studios Hollywood (expanded) ---
        ("Universal Hollywood", "merch", "Wizarding World Hogwarts Castle Snow Globe", "Park Exclusive", "high", 65),
        ("Universal Hollywood", "merch", "Super Nintendo World Hollywood Mushroom Popcorn Bucket", "Park Exclusive", "high", 60),
        ("Universal Hollywood", "merch", "Universal Hollywood 60th Anniversary Pin Set", "Anniversary LE", "high", 70),
        ("Universal Hollywood", "merch", "Jurassic World Dominion Raptor Pin Set", "Park Exclusive", "mid", 35),
        ("Universal Hollywood", "merch", "Fast & Furious Supercharged Tee", "Park Exclusive", "standard", 25),
        ("Universal Hollywood", "merch", "The Secret Life of Pets Exclusive Plush Set", "Park Exclusive", "mid", 40),

        # --- Universal Orlando (expanded) ---
        ("Universal Orlando", "merch", "Wizarding World Hogwarts Express Popcorn Bucket", "Park Exclusive", "high", 65),
        ("Universal Orlando", "merch", "Hagrid's Motorbike Adventure Grand Opening Pin", "Grand Opening", "high", 90),
        ("Universal Orlando", "merch", "Volcano Bay Grand Opening Pin Set", "Grand Opening", "high", 75),
        ("Universal Orlando", "merch", "Velocicoaster Raptor Popcorn Bucket", "Park Exclusive", "mid", 50),
        ("Universal Orlando", "merch", "Universal Studios Classic Monsters Mug Set", "Park Exclusive", "mid", 45),
        ("Universal Orlando", "merch", "Jurassic World VelociCoaster Tee", "Park Exclusive", "mid", 30),
        ("Universal Orlando", "merch", "Springfield Krusty Burger Tray", "Park Exclusive", "standard", 20),
        ("Universal Orlando", "merch", "Men in Black Alien Attack Grand Opening Pin", "Grand Opening", "high", 85),

        # --- Universal Studios Japan (expanded) ---
        ("USJ", "merch", "USJ Spy x Family Collab Exclusive Tee", "Collab Exclusive", "mid", 45),
        ("USJ", "merch", "USJ Dragon Ball Z Collab Pin Set", "Collab Exclusive", "high", 70),
        ("USJ", "merch", "USJ Final Fantasy Collab Exclusive Figure", "Collab Exclusive", "high", 85),
        ("USJ", "merch", "USJ Chainsaw Man Collab Tee", "Collab Exclusive", "mid", 40),
        ("USJ", "merch", "USJ Sailor Moon Collab Pin Set", "Collab Exclusive", "high", 65),
        ("USJ", "merch", "USJ Monster Hunter World Exclusive Plush", "Park Exclusive", "mid", 50),
        ("USJ", "popcorn_bucket", "USJ Minion Bello Popcorn Bucket", "Park Exclusive", "mid", 45),
        ("USJ", "merch", "USJ Harry Potter Wizarding World Wand Set", "Park Exclusive", "high", 90),
        ("USJ", "merch", "USJ Cool Japan 2024 Exclusive Pin Set", "Limited Release", "high", 60),
        ("USJ", "merch", "USJ Neon Genesis Evangelion Collab Tee", "Collab Exclusive", "mid", 50),

        # --- Universal Studios Singapore (expanded) ---
        ("Universal Singapore", "merch", "USS Battlestar Galactica Grand Opening Pin", "Grand Opening", "high", 75),
        ("Universal Singapore", "merch", "USS Puss in Boots Exclusive Plush", "Park Exclusive", "mid", 35),
        ("Universal Singapore", "merch", "USS Jurassic Park Raptor Egg Popcorn Bucket", "Park Exclusive", "mid", 45),
        ("Universal Singapore", "merch", "USS Madagascar Alex Exclusive Figure", "Park Exclusive", "mid", 30),

        # --- Universal Beijing (expanded) ---
        ("Universal Beijing", "merch", "Universal Beijing Forbidden Journey Grand Opening Pin", "Grand Opening", "high", 80),
        ("Universal Beijing", "merch", "Universal Beijing Minion Land Grand Opening Set", "Grand Opening", "high", 85),
        ("Universal Beijing", "merch", "Universal Beijing Transformers Bumblebee Exclusive Figure", "Park Exclusive", "mid", 55),

        # --- Epic Universe (expanded) ---
        ("Universal Orlando", "merch", "Epic Universe How to Train Your Dragon Toothless Plush", "Grand Opening", "high", 65),
        ("Universal Orlando", "merch", "Epic Universe Ministry of Magic Grand Opening Pin Set", "Grand Opening", "grail", 150),
        ("Universal Orlando", "merch", "Epic Universe Dark Universe Frankenstein Stein Mug", "Grand Opening", "high", 55),
        ("Universal Orlando", "merch", "Epic Universe Super Nintendo World Mario Kart Cup", "Grand Opening", "mid", 40),
        ("Universal Orlando", "merch", "Epic Universe Opening Day Map Print", "Grand Opening", "high", 60),

        # --- Cedar Point ---
        ("Cedar Point", "merch", "Cedar Point Millennium Force 25th Anniversary Pin", "Anniversary LE", "high", 55),
        ("Cedar Point", "merch", "Cedar Point Top Thrill 2 Grand Opening Tee", "Grand Opening", "mid", 40),
        ("Cedar Point", "merch", "Cedar Point Steel Vengeance Grand Opening Pin", "Grand Opening", "high", 65),
        ("Cedar Point", "merch", "Cedar Point Magnum XL-200 Vintage Poster", "Vintage", "high", 80),
        ("Cedar Point", "merch", "Cedar Point Halloweekends Exclusive Tee", "Limited Release", "mid", 35),
        ("Cedar Point", "vintage", "Cedar Point Gemini Opening Year Ticket (1978)", "Vintage", "high", 100),

        # --- Six Flags ---
        ("Six Flags", "merch", "Six Flags Magic Mountain Twisted Colossus Grand Opening Pin", "Grand Opening", "high", 55),
        ("Six Flags", "merch", "Six Flags Great Adventure El Toro Vintage Poster", "Vintage", "high", 70),
        ("Six Flags", "merch", "Six Flags Fiesta Texas Iron Rattler Grand Opening Pin", "Grand Opening", "mid", 45),
        ("Six Flags", "merch", "Six Flags Mr. Six Exclusive Bobblehead", "Limited Release", "high", 60),
        ("Six Flags", "vintage", "Six Flags Over Georgia Opening Year Map (1967)", "Vintage", "grail", 150),
        ("Six Flags", "merch", "Six Flags Great America Raging Bull 25th Anniversary Pin", "Anniversary LE", "mid", 40),
        ("Six Flags", "merch", "Six Flags Discovery Kingdom Medusa Grand Opening Pin", "Grand Opening", "mid", 35),

        # --- Busch Gardens ---
        ("Busch Gardens", "merch", "Busch Gardens Tampa Montu Grand Opening Pin", "Grand Opening", "high", 55),
        ("Busch Gardens", "merch", "Busch Gardens Williamsburg Pantheon Grand Opening Tee", "Grand Opening", "mid", 40),
        ("Busch Gardens", "merch", "Busch Gardens Iron Gwazi Grand Opening Pin", "Grand Opening", "high", 65),
        ("Busch Gardens", "vintage", "Busch Gardens Old Country Opening Guide (1975)", "Vintage", "high", 90),

        # --- Knott's Berry Farm (expanded) ---
        ("Knott's Berry Farm", "merch", "Knott's GhostRider Grand Opening Pin", "Grand Opening", "high", 60),
        ("Knott's Berry Farm", "merch", "Knott's Boysenberry Festival Exclusive Mug", "Festival LE", "mid", 30),
        ("Knott's Berry Farm", "vintage", "Knott's Berry Farm Vintage Park Map (1960s)", "Vintage", "grail", 140),

        # --- SeaWorld (expanded) ---
        ("SeaWorld", "merch", "SeaWorld Mako Grand Opening Pin", "Grand Opening", "high", 55),
        ("SeaWorld", "merch", "SeaWorld Pipeline Grand Opening Tee", "Grand Opening", "mid", 35),
        ("SeaWorld", "vintage", "Vintage SeaWorld Opening Day Program (1973)", "Vintage", "high", 110),

        # --- LEGOLAND (expanded) ---
        ("LEGOLAND", "merch", "LEGOLAND New York Grand Opening Set", "Grand Opening", "high", 75),
        ("LEGOLAND", "merch", "LEGOLAND Windsor Dragon Coaster Mini Set", "Park Exclusive", "mid", 28),
        ("LEGOLAND", "merch", "LEGOLAND Japan Grand Opening Brick", "Grand Opening", "high", 65),
        ("LEGOLAND", "merch", "LEGOLAND Billund Original Park Exclusive Set", "Park Exclusive", "mid", 35),

        # --- Europa-Park (expanded) ---
        ("Europa-Park", "merch", "Europa-Park Silver Star Grand Opening Poster", "Grand Opening", "high", 55),
        ("Europa-Park", "merch", "Europa-Park Blue Fire Grand Opening Pin", "Grand Opening", "high", 60),
        ("Europa-Park", "merch", "Europa-Park Voltron Grand Opening Tee", "Grand Opening", "mid", 40),

        # --- Alton Towers / Thorpe Park (expanded) ---
        ("Alton Towers", "merch", "Alton Towers Wicker Man Grand Opening Pin", "Grand Opening", "high", 55),
        ("Alton Towers", "merch", "Alton Towers Oblivion 25th Anniversary Poster", "Anniversary LE", "high", 50),
        ("Thorpe Park", "merch", "Thorpe Park Hyperia Grand Opening Pin Set", "Grand Opening", "high", 60),
        ("Thorpe Park", "merch", "Thorpe Park The Swarm Grand Opening Tee", "Grand Opening", "mid", 35),

        # --- Efteling (Netherlands) ---
        ("Efteling", "merch", "Efteling Baron 1898 Grand Opening Pin", "Grand Opening", "high", 55),
        ("Efteling", "merch", "Efteling Symbolica Grand Opening Coin", "Grand Opening", "high", 50),
        ("Efteling", "merch", "Efteling Pardoes Mascot Plush", "Park Exclusive", "mid", 30),

        # --- Phantasialand (Germany) ---
        ("Phantasialand", "merch", "Phantasialand F.L.Y. Grand Opening Pin", "Grand Opening", "high", 60),
        ("Phantasialand", "merch", "Phantasialand Taron Grand Opening Poster", "Grand Opening", "high", 55),

        # --- PortAventura (Spain) ---
        ("PortAventura", "merch", "PortAventura Shambhala Grand Opening Pin", "Grand Opening", "high", 50),
        ("PortAventura", "merch", "PortAventura Uncharted Grand Opening Set", "Grand Opening", "high", 65),

        # --- Everland (South Korea) ---
        ("Everland", "merch", "Everland T Express Grand Opening Pin", "Grand Opening", "high", 55),
        ("Everland", "merch", "Everland Exclusive Lenny Lion Plush", "Park Exclusive", "mid", 30),

        # --- Lotte World (South Korea) ---
        ("Lotte World", "merch", "Lotte World Lotty & Lorry Exclusive Plush Set", "Park Exclusive", "mid", 35),
        ("Lotte World", "merch", "Lotte World Adventure Grand Opening Pin", "Grand Opening", "high", 50),

        # --- Ocean Park (Hong Kong) ---
        ("Ocean Park", "merch", "Ocean Park Exclusive Grand Aquarium Pin Set", "Park Exclusive", "mid", 30),
        ("Ocean Park", "vintage", "Vintage Ocean Park Opening Year Postcard Set (1977)", "Vintage", "high", 80),

        # --- Disney Cruise Line (expanded) ---
        ("Disney Cruise Line", "merch", "Disney Cruise Line Disney Destiny Christening Pin", "Grand Opening", "high", 90),
        ("Disney Cruise Line", "merch", "Disney Cruise Line Lighthouse Point Pin Set", "Limited Release", "high", 70),
        ("Disney Cruise Line", "merch", "Disney Cruise Line Castaway Cay 5K Medal", "Limited Release", "mid", 45),
        ("Disney Cruise Line", "merch", "Disney Cruise Line Captain Hook Villain Night Pin", "LE", "high", 60),

        # --- Vintage Disney Ephemera (expanded) ---
        ("Disney Parks", "vintage", "Vintage Space Mountain Opening Day Pin (1975)", "Vintage", "grail", 280),
        ("Disney Parks", "vintage", "Vintage EPCOT Center Horizons Ride Postcard", "Vintage", "high", 80),
        ("Disney Parks", "vintage", "Vintage Disney-MGM Studios Opening Day Map (1989)", "Vintage", "grail", 220),
        ("Disney Parks", "vintage", "Vintage Disneyland Ticket Book Unused (1970s)", "Vintage", "grail", 400),
        ("Disney Parks", "vintage", "Vintage Disney World Magic Kingdom Souvenir Hat (1970s)", "Vintage", "high", 70),
        ("Disney Parks", "vintage", "Vintage Disneyland Monsanto House of the Future Postcard", "Vintage", "high", 100),
        ("Disney Parks", "vintage", "Vintage WDW Discovery Island Map", "Vintage", "high", 90),
        ("Disney Parks", "vintage", "Vintage Captain EO Premiere Night Program", "Vintage", "high", 110),

        # --- More Pin Trading (expanded) ---
        ("Disney Parks", "pin_event", "Disney Pin Trading Night LE 500 (Haunted Mansion)", "LE", "grail", 150),
        ("Disney Parks", "pin_event", "Mickey & Friends Hidden Mickey Pin Complete Set (2024)", "Park Exclusive", "high", 80),
        ("Disney Parks", "pin_event", "Star Wars May the 4th Pin Set (2024)", "Limited Release", "high", 65),
        ("Disney Parks", "pin_event", "Epcot International Festival of the Holidays Pin Set", "Festival LE", "high", 70),
        ("Disney Parks", "pin_event", "Disney Villains After Hours Pin Set (2024)", "LE", "high", 85),

        # --- More Annual Passholder ---
        ("Disney Parks", "passholder", "WDW Annual Passholder Exclusive Tee (2024)", "AP Exclusive", "mid", 35),
        ("Disney Parks", "passholder", "Disneyland Magic Key Terrace Exclusive Ornament", "AP Exclusive", "mid", 32),

        # --- Hersheypark ---
        ("Hersheypark", "merch", "Hersheypark Candymonium Grand Opening Pin", "Grand Opening", "mid", 40),
        ("Hersheypark", "merch", "Hersheypark Wildcat's Revenge Grand Opening Tee", "Grand Opening", "mid", 35),

        # --- Dollywood ---
        ("Dollywood", "merch", "Dollywood Lightning Rod Grand Opening Pin", "Grand Opening", "mid", 45),
        ("Dollywood", "merch", "Dollywood Wild Eagle Grand Opening Poster", "Grand Opening", "mid", 40),

        # --- Silver Dollar City ---
        ("Silver Dollar City", "merch", "Silver Dollar City Outlaw Run Grand Opening Pin", "Grand Opening", "mid", 40),
        ("Silver Dollar City", "merch", "Silver Dollar City Vintage Souvenir Plate (1970s)", "Vintage", "high", 70),

        # --- Kings Island ---
        ("Kings Island", "merch", "Kings Island Orion Grand Opening Pin", "Grand Opening", "mid", 45),
        ("Kings Island", "vintage", "Kings Island Vintage The Beast Opening Year Pin (1979)", "Vintage", "high", 110),

        # --- Carowinds ---
        ("Carowinds", "merch", "Carowinds Fury 325 Grand Opening Pin", "Grand Opening", "mid", 45),
        ("Carowinds", "merch", "Carowinds Copperhead Strike Grand Opening Tee", "Grand Opening", "mid", 35),

        # --- Holiday World ---
        ("Holiday World", "merch", "Holiday World The Voyage Grand Opening Pin", "Grand Opening", "mid", 40),

        # --- Gardaland (Italy) ---
        ("Gardaland", "merch", "Gardaland Oblivion Grand Opening Pin", "Grand Opening", "mid", 45),
        ("Gardaland", "merch", "Gardaland Prezzemolo Mascot Plush", "Park Exclusive", "standard", 22),

        # --- Tivoli Gardens (Denmark) ---
        ("Tivoli Gardens", "vintage", "Tivoli Gardens Vintage Souvenir Program (1950s)", "Vintage", "grail", 180),
        ("Tivoli Gardens", "merch", "Tivoli Gardens Exclusive Peacock Pin", "Park Exclusive", "mid", 30),

        # === ROUND 6 — 70 new items to reach 500+ ===

        # --- Disney Parks — More Popcorn Buckets (2024-2025) ---
        ("Disney Parks", "popcorn_bucket", "Moana Kakamora Popcorn Bucket", "Limited Release", "high", 85),
        ("Disney Parks", "popcorn_bucket", "Tiana's Bayou Adventure Gumbo Pot Bucket", "Grand Opening", "high", 100),
        ("Disney Parks", "popcorn_bucket", "Cheshire Cat Popcorn Bucket (DL)", "Park Exclusive", "high", 75),
        ("Disney Parks", "popcorn_bucket", "Wall-E Popcorn Bucket", "Park Exclusive", "mid", 55),
        ("Disney Parks", "popcorn_bucket", "Madame Leota Crystal Ball Popcorn Bucket", "LE", "grail", 160),

        # --- Disney Parks — Sipper Cups ---
        ("Disney Parks", "sipper", "Haunted Mansion Gargoyle Sipper", "Park Exclusive", "mid", 40),
        ("Disney Parks", "sipper", "Disneyland Matterhorn Abominable Snowman Sipper", "Park Exclusive", "mid", 45),
        ("Disney Parks", "sipper", "Star Wars Rancor Sipper (Galaxy's Edge)", "Park Exclusive", "mid", 38),
        ("Disney Parks", "sipper", "Figment Sipper (Epcot)", "Park Exclusive", "mid", 42),

        # --- Disney Parks — Magic Bands & MagicBand+ ---
        ("Disney Parks", "magicband", "MagicBand+ Haunted Mansion Interactive", "Park Exclusive", "mid", 45),
        ("Disney Parks", "magicband", "MagicBand+ Figment Epcot Exclusive", "Park Exclusive", "mid", 40),
        ("Disney Parks", "magicband", "MagicBand+ 50th Anniversary Vault Collection", "Anniversary LE", "high", 65),
        ("Disney Parks", "magicband", "MagicBand+ Star Wars Lightsaber Interactive", "Park Exclusive", "mid", 42),

        # --- Disney Parks — Ears & Headbands ---
        ("Disney Parks", "ears", "Loungefly Figment Epcot Ear Headband", "Park Exclusive", "mid", 40),
        ("Disney Parks", "ears", "Disney100 Iridescent Ear Headband", "D100 Exclusive", "mid", 45),
        ("Disney Parks", "ears", "Haunted Mansion Bride Ear Headband", "Park Exclusive", "mid", 42),
        ("Disney Parks", "ears", "Disneyland Club 33 Member Ear Headband", "LE", "grail", 200),

        # --- Disney Parks — Spirit Jerseys (more) ---
        ("Disney Parks", "apparel", "Haunted Mansion Spirit Jersey (Glow-in-Dark)", "Park Exclusive", "high", 85),
        ("Disney Parks", "apparel", "Epcot Flower & Garden Festival Spirit Jersey", "Festival LE", "high", 78),
        ("Disney Parks", "apparel", "Galaxy's Edge Batuu Spirit Jersey", "Park Exclusive", "high", 72),

        # --- Tokyo Disney — More Exclusives ---
        ("Tokyo Disney", "snack_case", "Baymax Popcorn Bucket (TDL)", "Tokyo Exclusive", "mid", 50),
        ("Tokyo Disney", "snack_case", "Mike Wazowski Candy Case (TDL)", "Tokyo Exclusive", "mid", 35),
        ("Tokyo Disney", "plush", "CookieAnn Plush (TDS Exclusive)", "Tokyo Exclusive", "high", 75),
        ("Tokyo Disney", "plush", "TDS Fantasy Springs Peter Pan Plush", "Grand Opening", "high", 90),
        ("Tokyo Disney", "merch", "Tokyo Disney 41st Anniversary Mug Set", "Anniversary LE", "mid", 42),
        ("Tokyo Disney", "pins", "TDS 20th Anniversary Celebration Pin Box", "Anniversary LE", "high", 110),

        # --- Universal Studios — Hollywood ---
        ("Universal Hollywood", "merch", "Super Nintendo World Hollywood Grand Opening Tee", "Grand Opening", "high", 65),
        ("Universal Hollywood", "merch", "Super Nintendo World Hollywood Power Star Popcorn", "Grand Opening", "mid", 55),
        ("Universal Hollywood", "figure", "Universal Hollywood Exclusive Jurassic World Figure", "Park Exclusive", "mid", 40),
        ("Universal Hollywood", "merch", "Wizarding World Hollywood Exclusive Wand Set", "Park Exclusive", "high", 85),

        # --- Universal Studios — Orlando (Epic Universe) ---
        ("Epic Universe", "merch", "Epic Universe Grand Opening Spirit Jersey", "Grand Opening", "high", 90),
        ("Epic Universe", "merch", "How to Train Your Dragon Grand Opening Pin Set", "Grand Opening", "high", 75),
        ("Epic Universe", "merch", "Dark Universe Grand Opening Dracula Figure", "Grand Opening", "high", 80),
        ("Epic Universe", "merch", "Celestial Park Exclusive Star Map Poster", "Grand Opening", "mid", 45),
        ("Epic Universe", "popcorn_bucket", "How to Train Your Dragon Toothless Popcorn Bucket", "Grand Opening", "high", 95),

        # --- Universal Studios Japan — More ---
        ("USJ", "merch", "USJ Attack on Titan Collab T-Shirt", "Collab Exclusive", "mid", 42),
        ("USJ", "merch", "USJ Demon Slayer Collab Key Chain Set", "Collab Exclusive", "mid", 38),
        ("USJ", "figure", "USJ One Piece Collab Exclusive Luffy Figure", "Collab Exclusive", "high", 65),
        ("USJ", "popcorn_bucket", "USJ Minion Bob Popcorn Bucket", "Park Exclusive", "mid", 45),

        # --- Shanghai Disney ---
        ("Shanghai Disney", "merch", "Shanghai Disney Zootopia Grand Opening Tee", "Grand Opening", "high", 70),
        ("Shanghai Disney", "merch", "Shanghai Disney Zootopia Judy Hopps Plush", "Grand Opening", "mid", 50),
        ("Shanghai Disney", "pins", "Shanghai Disney 5th Anniversary Pin Set", "Anniversary LE", "high", 80),

        # --- Hong Kong Disneyland ---
        ("Hong Kong Disney", "merch", "HKDL World of Frozen Grand Opening Spirit Jersey", "Grand Opening", "high", 85),
        ("Hong Kong Disney", "merch", "HKDL World of Frozen Elsa Crystal Figure", "Grand Opening", "high", 95),
        ("Hong Kong Disney", "pins", "HKDL 18th Anniversary Celebration Pin", "Anniversary LE", "mid", 45),

        # --- LEGOLAND (expanded) ---
        ("LEGOLAND", "exclusive", "LEGOLAND Exclusive LEGO Dragon Set", "Park Exclusive", "high", 80),
        ("LEGOLAND", "exclusive", "LEGOLAND Exclusive Park Entrance Mini Build", "Park Exclusive", "mid", 35),
        ("LEGOLAND", "exclusive", "LEGOLAND Exclusive Minifigure Factory Custom Fig", "Park Exclusive", "mid", 28),

        # --- SeaWorld / Busch Gardens ---
        ("SeaWorld", "merch", "SeaWorld Exclusive Shamu Vintage Plush (1990s)", "Vintage", "high", 65),
        ("SeaWorld", "merch", "SeaWorld Rescue Pin Set (LE 500)", "LE", "high", 60),
        ("Busch Gardens", "merch", "Busch Gardens Iron Gwazi Grand Opening Poster", "Grand Opening", "mid", 40),
        ("Busch Gardens", "merch", "Busch Gardens Exclusive Coaster Pin Collection", "Park Exclusive", "mid", 35),

        # --- Hersheypark ---
        ("Hersheypark", "merch", "Hersheypark Wildcat's Revenge Grand Opening Pin", "Grand Opening", "mid", 38),
        ("Hersheypark", "merch", "Hersheypark Vintage Entrance Photo (1970s)", "Vintage", "high", 70),

        # --- Dollywood ---
        ("Dollywood", "merch", "Dollywood Exclusive Dolly Parton Signature Mug", "Park Exclusive", "mid", 30),
        ("Dollywood", "merch", "Dollywood Big Bear Mountain Grand Opening Pin", "Grand Opening", "mid", 35),

        # --- Disney Cruise Line (more) ---
        ("Disney Cruise Line", "merch", "DCL Disney Treasure Maiden Voyage Pin Set", "LE", "high", 100),
        ("Disney Cruise Line", "merch", "DCL Disney Wish Captain's Pin", "LE", "high", 80),
        ("Disney Cruise Line", "merch", "DCL Castaway Cay Exclusive Beach Towel", "Park Exclusive", "mid", 42),

        # --- Disney Pin Trading Events (more) ---
        ("Disney Parks", "pin_event", "Epcot Festival of the Arts LE Pin 2025", "Festival LE", "high", 65),
        ("Disney Parks", "pin_event", "Mickey's Not So Scary Halloween Party Pin 2024", "LE", "high", 70),
        ("Disney Parks", "pin_event", "Mickey's Very Merry Christmas Party Pin 2024", "LE", "high", 72),
        ("Disney Parks", "pin_event", "Disney Villains After Hours LE Pin", "LE", "high", 68),

        # --- Disneyland Paris (more) ---
        ("Disneyland Paris", "merch", "DLP 30th Anniversary Castle Snow Globe", "Anniversary LE", "high", 120),
        ("Disneyland Paris", "merch", "DLP Phantom Manor Exclusive Figure Set", "Park Exclusive", "high", 85),
        ("Disneyland Paris", "pins", "DLP Avengers Campus Grand Opening Pin", "Grand Opening", "high", 60),
    ]

    catalog = []
    for park, subcategory, name, edition, tier, price in items:
        catalog.append({
            "park": park,
            "subcategory": subcategory,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })

    # Round 7 expansion — 50 items
    catalog.extend(_expanded_round7_theme_park())
    catalog.extend(_variant_expansion())

    # Deduplicate by ('park', 'name', 'edition') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["park"], item["name"], item["edition"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def _expanded_round7_theme_park() -> list[dict]:
    """50 new theme park items: Fantasy Springs, Zootopia, Frozen area, SNW extras, Europa-Park, Efteling."""
    items = [
        # --- Tokyo DisneySea Fantasy Springs (2024 Opening) ---
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Grand Opening Spirit Jersey", "Grand Opening", "high", 95),
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Rapunzel Lantern Popcorn Bucket", "Grand Opening", "grail", 150),
        ("Tokyo Disney", "pins", "TDS Fantasy Springs Grand Opening Pin Box Set (LE 3000)", "LE", "grail", 130),
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Peter Pan Lost Boys Plush Set", "Grand Opening", "high", 80),
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Anna & Elsa Music Box", "Grand Opening", "high", 110),
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Fairy Tinker Bell Light-Up Wand", "Grand Opening", "mid", 55),
        ("Tokyo Disney", "snack_case", "TDS Fantasy Springs Rapunzel Tower Snack Case", "Grand Opening", "high", 65),
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Opening Day Commemorative Medal", "Grand Opening", "high", 90),
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Tangled Gondola Ornament", "Grand Opening", "mid", 48),
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Frozen Kingdom Crystal Globe", "Grand Opening", "high", 100),

        # --- Shanghai Disneyland Zootopia Area Exclusives (2023 Opening) ---
        ("Shanghai Disney", "merch", "Shanghai Zootopia Land Grand Opening Spirit Jersey", "Grand Opening", "high", 80),
        ("Shanghai Disney", "merch", "Shanghai Zootopia Judy & Nick Interactive Figure Set", "Grand Opening", "high", 70),
        ("Shanghai Disney", "pins", "Shanghai Zootopia Grand Opening Pin Set (LE 2000)", "LE", "grail", 110),
        ("Shanghai Disney", "merch", "Shanghai Zootopia ZPD Police Badge Replica", "Grand Opening", "mid", 45),
        ("Shanghai Disney", "popcorn_bucket", "Shanghai Zootopia Jumbeaux's Cafe Popcorn Bucket", "Grand Opening", "high", 75),
        ("Shanghai Disney", "merch", "Shanghai Zootopia Flash Sloth Plush XL", "Grand Opening", "mid", 42),
        ("Shanghai Disney", "merch", "Shanghai Zootopia Clawhauser Donut Mug", "Grand Opening", "mid", 38),
        ("Shanghai Disney", "merch", "Shanghai Zootopia Mr. Big Iced Tea Sipper", "Grand Opening", "mid", 40),

        # --- Hong Kong Disneyland World of Frozen (2023 Opening) ---
        ("Hong Kong Disney", "merch", "HKDL Frozen Grand Opening Elsa Ice Palace Snow Globe", "Grand Opening", "high", 120),
        ("Hong Kong Disney", "merch", "HKDL Frozen Wandering Oaken's Trading Post Mug Set", "Grand Opening", "mid", 45),
        ("Hong Kong Disney", "pins", "HKDL World of Frozen Grand Opening Pin Box (LE 1500)", "LE", "grail", 120),
        ("Hong Kong Disney", "merch", "HKDL Frozen Olaf Warm Hugs Plush LE", "Grand Opening", "high", 65),
        ("Hong Kong Disney", "merch", "HKDL Frozen Sven Antler Headband", "Grand Opening", "mid", 30),
        ("Hong Kong Disney", "popcorn_bucket", "HKDL Frozen Marshmallow Popcorn Bucket", "Grand Opening", "high", 80),

        # --- Universal Studios Japan Super Nintendo World (expanded) ---
        ("USJ", "merch", "USJ Super Nintendo World Power-Up Band Mario", "Park Exclusive", "mid", 38),
        ("USJ", "merch", "USJ Super Nintendo World Power-Up Band Luigi", "Park Exclusive", "mid", 38),
        ("USJ", "merch", "USJ Super Nintendo World Power-Up Band Peach", "Park Exclusive", "mid", 38),
        ("USJ", "merch", "USJ Super Nintendo World Power-Up Band Toad", "Park Exclusive", "mid", 38),
        ("USJ", "merch", "USJ Super Nintendo World Toad Cafe Question Block Plate Set", "Park Exclusive", "high", 60),
        ("USJ", "merch", "USJ Super Nintendo World Toad Cafe Mushroom Soup Bowl", "Park Exclusive", "mid", 35),
        ("USJ", "merch", "USJ Super Nintendo World Bowser Challenge Medal", "Park Exclusive", "mid", 42),
        ("USJ", "merch", "USJ Super Nintendo World Fire Flower Popcorn Bucket", "Park Exclusive", "high", 55),
        ("USJ", "merch", "USJ Donkey Kong Country Grand Opening Barrel Mug", "Grand Opening", "high", 65),
        ("USJ", "merch", "USJ Donkey Kong Country Grand Opening Pin Set", "Grand Opening", "high", 70),
        ("USJ", "merch", "USJ Super Nintendo World 1-Up Mushroom Light-Up Figure", "Park Exclusive", "mid", 48),
        ("USJ", "merch", "USJ Super Nintendo World Star Power Coin Medallion", "Park Exclusive", "mid", 30),

        # --- Europa-Park Exclusives (Germany) ---
        ("Europa-Park", "merch", "Europa-Park Exclusive Ed Euromaus Plush XL", "Park Exclusive", "mid", 35),
        ("Europa-Park", "merch", "Europa-Park Voltron Nevera Grand Opening Spirit Jersey", "Grand Opening", "high", 65),
        ("Europa-Park", "pins", "Europa-Park Voltron Grand Opening Pin Set (LE 1000)", "LE", "high", 55),
        ("Europa-Park", "merch", "Europa-Park Rulantica Water World Exclusive Towel Set", "Park Exclusive", "mid", 30),
        ("Europa-Park", "merch", "Europa-Park 50th Anniversary Commemorative Coin", "Anniversary LE", "high", 60),
        ("Europa-Park", "merch", "Europa-Park Wodan Timbercoaster Grand Opening Poster", "Grand Opening", "mid", 40),

        # --- Efteling Exclusives (Netherlands) ---
        ("Efteling", "merch", "Efteling Max & Moritz Grand Opening Pin Set", "Grand Opening", "high", 50),
        ("Efteling", "merch", "Efteling Fata Morgana Exclusive Lantern Replica", "Park Exclusive", "high", 65),
        ("Efteling", "merch", "Efteling Droomvlucht Fairy Light-Up Ornament", "Park Exclusive", "mid", 35),
        ("Efteling", "merch", "Efteling Holle Bolle Gijs Talking Waste Bin Replica", "Park Exclusive", "mid", 45),
        ("Efteling", "merch", "Efteling De Vliegende Hollander Grand Opening Coin", "Grand Opening", "high", 50),
        ("Efteling", "merch", "Efteling 70th Anniversary Commemorative Book LE", "Anniversary LE", "high", 55),
        ("Efteling", "merch", "Efteling Baron 1898 Exclusive Mine Cart Figure", "Park Exclusive", "mid", 40),

        # --- Tokyo DisneySea Exclusives ---
        ("Tokyo DisneySea", "merch", "Tokyo DisneySea 20th Anniversary Crystal Sphere Ornament", "Anniversary LE", "grail", 180),
        ("Tokyo DisneySea", "merch", "Tokyo DisneySea Sindbad Storybook Voyage Lamp Replica", "Park Exclusive", "high", 95),
        ("Tokyo DisneySea", "merch", "Tokyo DisneySea Tower of Terror Bellhop Bear Plush LE", "LE", "high", 110),
        ("Tokyo DisneySea", "merch", "Tokyo DisneySea Duffy & Friends Autumn Costume Set", "Tokyo Exclusive", "mid", 55),
        ("Tokyo DisneySea", "merch", "Tokyo DisneySea Journey to the Center of the Earth Vehicle Figure", "Park Exclusive", "high", 85),
        ("Tokyo DisneySea", "merch", "Tokyo DisneySea Fantasy Springs Peter Pan Ship Popcorn Bucket", "Limited Release", "grail", 150),
        ("Tokyo DisneySea", "merch", "Tokyo DisneySea Fantasy Springs Rapunzel Lantern Light-Up Tumbler", "Limited Release", "high", 75),
        ("Tokyo DisneySea", "merch", "Tokyo DisneySea Mediterranean Harbor Gondolier Mickey Figurine", "Park Exclusive", "high", 70),
        ("Tokyo DisneySea", "merch", "Tokyo DisneySea Aquatopia Miniature Ride Vehicle", "Park Exclusive", "mid", 48),
        ("Tokyo DisneySea", "pins", "Tokyo DisneySea Fantasy Springs Grand Opening Pin Set (LE 500)", "LE 300", "grail", 200),

        # --- Universal Studios Japan ---
        ("USJ", "merch", "USJ Wizarding World Butterbeer Mug (2024 Redesign)", "Park Exclusive", "mid", 45),
        ("USJ", "merch", "USJ Jujutsu Kaisen Collaboration Sukuna Finger Replica", "Collab Exclusive", "high", 90),
        ("USJ", "merch", "USJ Demon Slayer Infinity Train Popcorn Bucket", "Collab Exclusive", "high", 80),
        ("USJ", "merch", "USJ Attack on Titan The Real 4D Exclusive Keychain Set", "Collab Exclusive", "mid", 40),
        ("USJ", "merch", "USJ Spy x Family Anya Forger Peanut Popcorn Bucket", "Collab Exclusive", "high", 75),
        ("USJ", "merch", "USJ Super Nintendo World Peach Castle Miniature", "Park Exclusive", "high", 65),
        ("USJ", "merch", "USJ Jurassic World Dominion Raptor Egg Popcorn Bucket", "Limited Release", "high", 70),
        ("USJ", "merch", "USJ Dragon Ball Z Kamehameha Light-Up Figure", "Collab Exclusive", "high", 85),
        ("USJ", "merch", "USJ Monster Hunter Felyne Plush XL Exclusive", "Collab Exclusive", "mid", 50),
        ("USJ", "merch", "USJ One Piece Thousand Sunny Ship Popcorn Bucket", "Collab Exclusive", "high", 80),

        # --- Shanghai Disneyland ---
        ("Shanghai Disney", "merch", "Shanghai Disney Resort Grand Opening Mickey Figure (2016)", "Grand Opening", "grail", 160),
        ("Shanghai Disney", "merch", "Shanghai Disney Zootopia Land Grand Opening Pin Set (LE 800)", "Grand Opening", "high", 85),
        ("Shanghai Disney", "merch", "Shanghai Disney TRON Lightcycle Run Coaster Vehicle Replica", "Park Exclusive", "high", 95),
        ("Shanghai Disney", "merch", "Shanghai Disney StellaLou Exclusive Ballet Costume Plush", "Tokyo Exclusive", "mid", 45),
        ("Shanghai Disney", "merch", "Shanghai Disney Pirates of the Caribbean Ship Lantern", "Park Exclusive", "high", 70),
        ("Shanghai Disney", "merch", "Shanghai Disney Enchanted Storybook Castle Miniature (Crystal Edition)", "LE", "grail", 140),
        ("Shanghai Disney", "merch", "Shanghai Disney Chinese New Year Dragon Mickey Plush LE", "Festival LE", "high", 65),
        ("Shanghai Disney", "merch", "Shanghai Disney Toy Story Land Alien Swirling Saucers Popcorn Bucket", "Park Exclusive", "high", 60),

        # --- Walt Disney World 50th Anniversary ---
        ("Disney Parks", "merch", "WDW 50th Anniversary Cinderella Castle Ornament (Crystal)", "Anniversary LE", "grail", 175),
        ("Disney Parks", "merch", "WDW 50th Anniversary EARidescent Spirit Jersey", "Anniversary LE", "high", 90),
        ("Disney Parks", "merch", "WDW 50th Anniversary Golden Fab 50 Character Statues Set", "Anniversary LE", "high", 120),
        ("Disney Parks", "merch", "WDW 50th Anniversary Vault Collection Retro Ticket Media Pin", "Anniversary LE", "high", 65),
        ("Disney Parks", "merch", "WDW 50th Anniversary Spaceship Earth Light-Up Figurine", "Anniversary LE", "high", 85),
        ("Disney Parks", "merch", "WDW 50th Anniversary Main Street Electrical Parade Ear Headband", "Anniversary LE", "mid", 55),
        ("Disney Parks", "merch", "WDW 50th Anniversary Legacy Poster Set (All 4 Parks)", "Anniversary LE", "high", 70),
        ("Disney Parks", "merch", "WDW 50th Anniversary Mickey & Minnie Sipper Cup Set", "Anniversary LE", "mid", 40),

        # --- Disneyland Paris ---
        ("Disneyland Paris", "merch", "Disneyland Paris 30th Anniversary Sleeping Beauty Castle Snow Globe", "Anniversary LE", "grail", 150),
        ("Disneyland Paris", "merch", "Disneyland Paris Phantom Manor Exclusive Hatbox Ghost Figure", "Park Exclusive", "high", 95),
        ("Disneyland Paris", "merch", "Disneyland Paris Ratatouille Remy Chef Hat & Apron Set", "Park Exclusive", "mid", 45),
        ("Disneyland Paris", "merch", "Disneyland Paris Avengers Campus Spider-Bot Exclusive", "Park Exclusive", "high", 65),
        ("Disneyland Paris", "merch", "Disneyland Paris Main Street Bakery Scented Candle Set", "Park Exclusive", "mid", 50),
        ("Disneyland Paris", "pins", "Disneyland Paris 30th Anniversary Legacy Pin Collection (12 pins)", "Anniversary LE", "high", 110),
        ("Disneyland Paris", "merch", "Disneyland Paris World of Frozen Grand Opening Elsa Crystal Figure", "Grand Opening", "grail", 160),

        # --- Seasonal / Holiday Exclusives ---
        ("Disney Parks", "merch", "Disney Parks Halloween Headless Horseman Popcorn Bucket", "Festival LE", "high", 95),
        ("Disney Parks", "merch", "Disney Parks Mickey's Not-So-Scary Halloween Hocus Pocus Spirit Jersey", "Festival LE", "high", 80),
        ("Disney Parks", "merch", "Disney Parks Christmas Holiday Gingerbread House Ornament (Grand Floridian)", "Festival LE", "high", 70),
        ("Disney Parks", "merch", "Disney Parks EPCOT Festival of the Arts Figment Paint Brush Sipper", "Festival LE", "high", 85),
        ("Disney Parks", "merch", "Disney Parks EPCOT Food & Wine Festival Chef Mickey Pin Set", "Festival LE", "mid", 55),
        ("Disney Parks", "merch", "Disney Parks Valentine's Day Heart Ear Headband LE", "Festival LE", "mid", 45),
        ("Disney Parks", "merch", "Disney Parks Chinese New Year Mushu Dragon Popcorn Bucket", "Festival LE", "high", 90),

        # --- Spirit Jerseys & Ear Headbands ---
        ("Disney Parks", "spirit_jersey", "Disney Parks Haunted Mansion Wallpaper Spirit Jersey", "Park Exclusive", "high", 85),
        ("Disney Parks", "spirit_jersey", "Disney Parks Tomorrowland Space Mountain Spirit Jersey", "Park Exclusive", "mid", 55),
        ("Disney Parks", "ear_headband", "Disney Parks Dole Whip Pineapple Ear Headband", "Park Exclusive", "mid", 40),
        ("Disney Parks", "ear_headband", "Disney Parks Rose Gold Sequin Ear Headband", "Park Exclusive", "mid", 45),
        ("Disney Parks", "ear_headband", "Disney Parks Enchanted Tiki Room Bird Ear Headband", "Park Exclusive", "mid", 42),

        # ── Haunted Mansion Merchandise (Round 5) ─────────────────────────
        ("Disney Parks", "merch", "Haunted Mansion 55th Anniversary Tombstone Figure Set", "Anniversary LE", "grail", 200),
        ("Disney Parks", "merch", "Haunted Mansion Madame Leota Crystal Ball Snow Globe", "Park Exclusive", "high", 95),
        ("Disney Parks", "merch", "Haunted Mansion Hitchhiking Ghosts Light-Up Figurine", "Park Exclusive", "high", 85),
        ("Disney Parks", "merch", "Haunted Mansion Stretching Room Canvas Art Set (4pc)", "Park Exclusive", "high", 120),
        ("Disney Parks", "merch", "Haunted Mansion Wallpaper Kitchen Apron & Towel Set", "Park Exclusive", "mid", 45),
        ("Disney Parks", "merch", "Haunted Mansion Doom Buggy Ride Vehicle Popcorn Bucket", "Limited Release", "high", 130),
        ("Disney Parks", "merch", "Haunted Mansion Hatbox Ghost Glow-in-the-Dark Mug", "Park Exclusive", "mid", 40),
        ("Disney Parks", "pins", "Haunted Mansion 999 Happy Haunts Anniversary Pin Set (5pc)", "Anniversary LE", "high", 80),

        # ── Galaxy's Edge Exclusives (Round 5) ────────────────────────────
        ("Disney Parks", "merch", "Galaxy's Edge Custom Lightsaber (Savi's Workshop Peace & Justice)", "Park Exclusive", "high", 140),
        ("Disney Parks", "merch", "Galaxy's Edge Custom Lightsaber (Savi's Workshop Power & Control)", "Park Exclusive", "high", 140),
        ("Disney Parks", "merch", "Galaxy's Edge Darksaber Replica Hilt", "Park Exclusive", "high", 130),
        ("Disney Parks", "merch", "Galaxy's Edge Droid Depot Custom R-Series Droid Kit", "Park Exclusive", "high", 110),
        ("Disney Parks", "merch", "Galaxy's Edge Droid Depot Custom BB-Series Droid Kit", "Park Exclusive", "high", 120),
        ("Disney Parks", "merch", "Galaxy's Edge Oga's Cantina Rancor Teeth Souvenir Mug", "Park Exclusive", "mid", 55),
        ("Disney Parks", "merch", "Galaxy's Edge First Order Stormtrooper Helmet Replica", "Park Exclusive", "high", 135),
        ("Disney Parks", "merch", "Galaxy's Edge Holocron Jedi Exclusive (with Kyber Crystal)", "Park Exclusive", "high", 90),
        ("Disney Parks", "merch", "Galaxy's Edge Millennium Falcon Popcorn Bucket", "Park Exclusive", "high", 75),
        ("Disney Parks", "pins", "Galaxy's Edge Bounty Hunter Pin Collection (8pc)", "Park Exclusive", "high", 65),

        # ── Super Nintendo World (Round 5) ────────────────────────────────
        ("USJ", "merch", "Super Nintendo World Mario Power Star Trophy", "Park Exclusive", "high", 80),
        ("USJ", "merch", "Super Nintendo World Bowser Castle Popcorn Bucket", "Park Exclusive", "high", 70),
        ("USJ", "merch", "Super Nintendo World Question Block Candy Tin", "Park Exclusive", "mid", 30),
        ("USJ", "merch", "Super Nintendo World Yoshi Egg Sipper Cup", "Park Exclusive", "mid", 35),
        ("USJ", "merch", "Super Nintendo World Luigi Mansion Ghost Figure Set", "Park Exclusive", "high", 65),
        ("USJ", "merch", "Super Nintendo World Princess Peach Tiara Ear Headband", "Park Exclusive", "mid", 40),
        ("USJ", "merch", "Super Nintendo World Piranha Plant Light-Up Figure", "Park Exclusive", "mid", 55),
        ("Universal Orlando", "merch", "Super Nintendo World Universal Orlando Grand Opening Set", "Grand Opening", "grail", 180),
        ("Universal Orlando", "merch", "Super Nintendo World Mario Kart Bowser's Challenge Popcorn Bucket", "Park Exclusive", "high", 65),

        # ── Pandora — The World of Avatar (Round 5) ──────────────────────
        ("Disney Parks", "merch", "Pandora The World of Avatar Banshee Puppet (Blue)", "Park Exclusive", "high", 70),
        ("Disney Parks", "merch", "Pandora The World of Avatar Banshee Puppet (Green)", "Park Exclusive", "high", 70),
        ("Disney Parks", "merch", "Pandora The World of Avatar Banshee Puppet (Purple)", "Park Exclusive", "high", 70),
        ("Disney Parks", "merch", "Pandora Na'vi Ear Headband with Braid", "Park Exclusive", "mid", 42),
        ("Disney Parks", "merch", "Pandora Floating Mountains Light-Up Figurine", "Park Exclusive", "high", 110),
        ("Disney Parks", "merch", "Pandora Way of Water Ilu Sipper Cup", "Park Exclusive", "mid", 45),
        ("Disney Parks", "merch", "Pandora Utility Suit Interactive Costume", "Park Exclusive", "high", 130),

        # ── Disney Parks Anniversary Items (Round 5) ──────────────────────
        ("Disney Parks", "anniversary", "Magic Kingdom 50th Anniversary Castle Figurine LE 2000", "Anniversary LE", "grail", 250),
        ("Disney Parks", "anniversary", "EPCOT 40th Anniversary Spaceship Earth LE Pin", "Anniversary LE", "high", 65),
        ("Disney Parks", "anniversary", "Disneyland 70th Anniversary Sleeping Beauty Castle Ornament", "Anniversary LE", "high", 75),
        ("Disney Parks", "anniversary", "Hollywood Studios 35th Anniversary Tower of Terror Figure", "Anniversary LE", "high", 95),
        ("Disney Parks", "anniversary", "Animal Kingdom 25th Anniversary Tree of Life Snow Globe", "Anniversary LE", "grail", 150),

        # ── Tokyo DisneySea Limited Goods (Round 5) ──────────────────────
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Peter Pan Neverland Popcorn Bucket", "Grand Opening", "high", 120),
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Frozen Kingdom Elsa Figure", "Grand Opening", "high", 90),
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Rapunzel Lantern Sipper Cup", "Grand Opening", "high", 75),
        ("Tokyo Disney", "plush", "TDS CookieAnn Plush (2024 Exclusive)", "Tokyo Exclusive", "high", 85),
        ("Tokyo Disney", "plush", "TDS Linabell New Year 2025 Costume Plush", "Tokyo Exclusive", "high", 90),
        ("Tokyo Disney", "merch", "TDS Duffy & Friends Autumn Sleepover Blanket Set", "Tokyo Exclusive", "mid", 55),
        ("Tokyo Disney", "merch", "TDS 20th Anniversary Journey Poster Art Print Set", "Anniversary LE", "high", 80),
        ("Tokyo Disney", "pins", "TDS Fantasy Springs Grand Opening Pin Set (6pc)", "Grand Opening", "high", 100),

        # ── Universal Studios Japan Expanded (Round 5) ────────────────────
        ("USJ", "merch", "USJ Attack on Titan The Final Collab Exclusive Figure Set", "Collab Exclusive", "high", 90),
        ("USJ", "merch", "USJ Demon Slayer DX Nichirin Blade Replica", "Collab Exclusive", "high", 110),
        ("USJ", "merch", "USJ One Piece Premier Show Exclusive Luffy Figure", "Collab Exclusive", "high", 80),
        ("USJ", "merch", "USJ Spy x Family Collab Anya Exclusive Plush", "Collab Exclusive", "mid", 50),
        ("USJ", "merch", "USJ Detective Conan Mystery Challenge Exclusive Badge Set", "Collab Exclusive", "mid", 45),
        ("USJ", "popcorn_bucket", "USJ Mario Super Star Popcorn Bucket (Gold)", "Park Exclusive", "high", 65),

        # ── Disney Cruise Line Exclusives (Round 5) ──────────────────────
        ("Disney Cruise Line", "merch", "DCL Disney Wish Maiden Voyage Spirit Jersey", "Grand Opening", "high", 95),
        ("Disney Cruise Line", "merch", "DCL Disney Treasure Inaugural Voyage Pin Set", "Grand Opening", "high", 80),
        ("Disney Cruise Line", "merch", "DCL Castaway Cay Exclusive Beach Towel", "Park Exclusive", "mid", 45),
        ("Disney Cruise Line", "merch", "DCL Captain Mickey Plush (Ship Exclusive)", "Park Exclusive", "mid", 55),

        # === EXPANSION ROUND 6 — 35 new items to reach 700+ ===

        # ── Disney Parks — 2025/2026 Exclusives (+8) ────────────────────
        ("Disney Parks", "merch", "Disneyland 70th Anniversary Castle Music Box LE", "Anniversary LE", "grail", 250),
        ("Disney Parks", "merch", "Disneyland 70th Anniversary Opening Day Replica Ticket Framed", "Anniversary LE", "high", 120),
        ("Disney Parks", "merch", "Disneyland 70th Anniversary Walt & Mickey Partners Statue LE", "Anniversary LE", "grail", 300),
        ("Disney Parks", "popcorn_bucket", "Tiana's Bayou Adventure Frog Prince Popcorn Bucket", "Park Exclusive", "high", 95),
        ("Disney Parks", "merch", "Tiana's Bayou Adventure Grand Opening Spirit Jersey", "Grand Opening", "high", 85),
        ("Disney Parks", "pins", "Tiana's Bayou Adventure Grand Opening Pin Set (5pc)", "Grand Opening", "high", 70),
        ("Disney Parks", "merch", "EPCOT Guardians of the Galaxy Cosmic Rewind Ride Vehicle Figure", "Park Exclusive", "high", 80),
        ("Disney Parks", "merch", "Country Bear Musical Jamboree Reimagined Grand Opening Pin", "Grand Opening", "mid", 45),

        # ── Universal Epic Universe — Grand Opening (+7) ────────────────
        ("Epic Universe", "merch", "Epic Universe Grand Opening Commemorative Coin Set", "Grand Opening", "high", 90),
        ("Epic Universe", "merch", "How to Train Your Dragon Hiccup & Toothless Figure Set", "Grand Opening", "high", 85),
        ("Epic Universe", "merch", "Dark Universe Monster Mash Spirit Jersey", "Grand Opening", "high", 80),
        ("Epic Universe", "merch", "Celestial Park Aurora Light-Up Wand", "Grand Opening", "mid", 55),
        ("Epic Universe", "pins", "Epic Universe Grand Opening 5-Worlds Pin Set (LE 2000)", "LE", "grail", 150),
        ("Epic Universe", "popcorn_bucket", "Dark Universe Frankenstein Popcorn Bucket", "Grand Opening", "high", 90),
        ("Epic Universe", "merch", "Wizarding World of Harry Potter Ministry of Magic Interactive Wand", "Park Exclusive", "high", 75),

        # ── Tokyo DisneySea Fantasy Springs Phase 2 (+5) ────────────────
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Frozen Kingdom Anna Coronation Music Box", "Grand Opening", "high", 110),
        ("Tokyo Disney", "pins", "TDS Fantasy Springs 1st Anniversary Pin Box (LE 1000)", "Anniversary LE", "grail", 160),
        ("Tokyo Disney", "snack_case", "TDS Fantasy Springs Tinker Bell Lantern Snack Case", "Grand Opening", "high", 70),
        ("Tokyo Disney", "plush", "TDS Fantasy Springs Peter Pan Shadow Plush LE", "Grand Opening", "high", 80),
        ("Tokyo Disney", "merch", "TDS Fantasy Springs Rapunzel Golden Flower Tiara Replica", "Grand Opening", "high", 95),

        # ── Universal Studios Japan — 2025 Collabs (+5) ─────────────────
        ("USJ", "merch", "USJ Chainsaw Man Collab Pochita Popcorn Bucket", "Collab Exclusive", "high", 85),
        ("USJ", "merch", "USJ Solo Leveling Collab Sung Jin-woo Shadow Figure", "Collab Exclusive", "high", 90),
        ("USJ", "merch", "USJ One Piece Premier Show 2025 Luffy Gear 5 Figure", "Collab Exclusive", "high", 95),
        ("USJ", "merch", "USJ Frieren Collab Exclusive Plush Set (Frieren & Fern)", "Collab Exclusive", "high", 70),
        ("USJ", "popcorn_bucket", "USJ Jujutsu Kaisen Sukuna Finger Popcorn Bucket 2025", "Collab Exclusive", "high", 80),

        # ── Disneyland Paris — Frozen & Avengers (+5) ───────────────────
        ("Disneyland Paris", "merch", "DLP World of Frozen Grand Opening Elsa Ice Castle Snow Globe", "Grand Opening", "grail", 180),
        ("Disneyland Paris", "pins", "DLP World of Frozen Grand Opening Pin Box (LE 1500)", "LE", "grail", 130),
        ("Disneyland Paris", "merch", "DLP Avengers Campus Iron Man Hall of Armor Figure Set", "Park Exclusive", "high", 95),
        ("Disneyland Paris", "merch", "DLP Phantom Manor 30th Anniversary Hatbox Ghost Figure", "Anniversary LE", "high", 110),
        ("Disneyland Paris", "merch", "DLP Main Street Electrical Parade Light-Up Popcorn Bucket", "Park Exclusive", "high", 75),

        # ── Europa-Park & Efteling (+5) ──────────────────────────────────
        ("Europa-Park", "merch", "Europa-Park Voltron Nevera Opening Day Pin (LE 500)", "Grand Opening", "high", 70),
        ("Europa-Park", "merch", "Europa-Park Piraten in Batavia Exclusive Ship Model", "Park Exclusive", "high", 60),
        ("Europa-Park", "merch", "Europa-Park Blue Fire MegaCoaster Light-Up Keychain", "Park Exclusive", "mid", 25),
        ("Efteling", "merch", "Efteling Symbolica Grand Opening Crystal Key Replica", "Grand Opening", "high", 75),
        ("Efteling", "merch", "Efteling Pardoes the Wizard Exclusive 12-inch Plush", "Park Exclusive", "mid", 40),
    ]
    catalog = []
    for park, subcategory, name, edition, tier, price in items:
        catalog.append({
            "park": park,
            "subcategory": subcategory,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def _variant_expansion() -> list[dict]:
    """Park-exclusive / year / seasonal variants for existing theme park items. ~50 items."""
    variants = [
        # Disneyland vs Disney World versions of same item
        ("Disney Parks", "popcorn_bucket", "Figment Popcorn Bucket (WDW Magic Kingdom)", "WDW Exclusive", "high", 100),
        ("Disney Parks", "popcorn_bucket", "Purple Wall Popcorn Bucket (Disneyland)", "DL Exclusive", "high", 75),
        ("Disney Parks", "popcorn_bucket", "Mickey Balloon Popcorn Bucket (DL)", "DL Exclusive", "mid", 50),
        ("Disney Parks", "popcorn_bucket", "Slinky Dog Popcorn Bucket (DL)", "DL Exclusive", "mid", 38),
        # Tokyo Disney vs Shanghai Disney versions
        ("Tokyo Disney", "snack_case", "Duffy Snack Case (TDL)", "TDL Exclusive", "mid", 50),
        ("Shanghai Disney", "snack_case", "Duffy Snack Case (Shanghai)", "Shanghai Exclusive", "high", 65),
        ("Shanghai Disney", "plush", "LinaBell Plush (Shanghai Exclusive)", "Shanghai Exclusive", "high", 90),
        ("Hong Kong Disney", "plush", "LinaBell Plush (HKDL Exclusive)", "HKDL Exclusive", "high", 80),
        ("Shanghai Disney", "merch", "Zootopia Grand Opening Spirit Jersey", "Grand Opening", "high", 85),
        ("Shanghai Disney", "merch", "Shanghai Disney 8th Anniversary Tee", "Anniversary LE", "mid", 45),
        # Annual Passholder exclusives
        ("Disney Parks", "ap_exclusive", "WDW Annual Passholder Magnet Set 2024", "AP Exclusive", "mid", 35),
        ("Disney Parks", "ap_exclusive", "DL Annual Passholder Magnet Set 2024", "AP Exclusive", "mid", 35),
        ("Disney Parks", "ap_exclusive", "WDW AP Exclusive Figment Pin 2024", "AP Exclusive", "high", 60),
        ("Disney Parks", "ap_exclusive", "DL AP Exclusive Haunted Mansion Pin 2024", "AP Exclusive", "high", 65),
        ("Disney Parks", "ap_exclusive", "WDW AP Exclusive Spirit Jersey 2024", "AP Exclusive", "mid", 55),
        ("Tokyo Disney", "ap_exclusive", "TDR Annual Passport Exclusive StellaLou Plush", "AP Exclusive", "high", 70),
        # Seasonal / Holiday overlays
        ("Disney Parks", "seasonal", "Mickey's Not So Scary Halloween Popcorn Bucket 2024", "Halloween LE", "high", 90),
        ("Disney Parks", "seasonal", "Mickey's Very Merry Christmas Party Popcorn Bucket 2024", "Christmas LE", "high", 95),
        ("Disney Parks", "seasonal", "EPCOT Food & Wine Festival Figment Bucket 2024", "Festival LE", "high", 110),
        ("Disney Parks", "seasonal", "EPCOT Flower & Garden Figment Topiary Figure 2024", "Festival LE", "high", 85),
        ("Disney Parks", "seasonal", "WDW 4th of July Spirit Jersey 2024", "Holiday LE", "mid", 50),
        ("Tokyo Disney", "seasonal", "TDL Halloween 2024 Duffy Costume Plush Set", "Halloween LE", "high", 95),
        ("Tokyo Disney", "seasonal", "TDL Christmas 2024 StellaLou Costume Set", "Christmas LE", "high", 90),
        # Opening day vs general release
        ("USJ", "merch", "Super Nintendo World Grand Opening Tee (Staff Only)", "Staff Exclusive", "grail", 250),
        ("USJ", "merch", "Donkey Kong Country Grand Opening Cast Member Pin", "Cast Exclusive", "grail", 180),
        ("Disney Parks", "merch", "Tiana's Bayou Adventure Grand Opening Pin (Cast)", "Cast Exclusive", "grail", 160),
        ("Disney Parks", "merch", "Tiana's Bayou Adventure Grand Opening Ears", "Grand Opening", "high", 80),
        ("Disney Parks", "merch", "Tiana's Bayou Adventure General Release Ears", "Park Exclusive", "mid", 35),
        # Different year variants of annual merchandise
        ("Disney Parks", "pin_event", "Disneyland AP Exclusive Pin Set (2023)", "AP Exclusive 2023", "high", 75),
        ("Disney Parks", "pin_event", "Disneyland AP Exclusive Pin Set (2022)", "AP Exclusive 2022", "high", 80),
        ("Disney Parks", "pin_event", "EPCOT Festival Pin Board Complete Set 2023", "Festival LE 2023", "high", 95),
        ("Disney Parks", "pin_event", "EPCOT Festival Pin Board Complete Set 2022", "Festival LE 2022", "high", 105),
        ("Tokyo Disney", "pins", "Tokyo Disney 35th Anniversary Pin Set", "Anniversary LE 35th", "high", 110),
        # Disneyland Paris exclusives of WDW items
        ("Disneyland Paris", "popcorn_bucket", "Ratatouille Remy Popcorn Bucket", "DLP Exclusive", "high", 85),
        ("Disneyland Paris", "popcorn_bucket", "DLP Castle Popcorn Bucket 30th Anniversary", "Anniversary LE", "high", 100),
        ("Disneyland Paris", "merch", "DLP 30th Anniversary Spirit Jersey", "Anniversary LE", "mid", 55),
        # Epic Universe (Universal Orlando) Grand Opening
        ("Epic Universe", "merch", "Epic Universe Grand Opening Spirit Jersey", "Grand Opening", "high", 75),
        ("Epic Universe", "merch", "Epic Universe Grand Opening Pin Set", "Grand Opening", "high", 85),
        ("Epic Universe", "merch", "How to Train Your Dragon Isle Opening Day Figure", "Grand Opening", "high", 90),
        ("Epic Universe", "merch", "Ministry of Magic Grand Opening Wand Set", "Grand Opening", "grail", 150),
        ("Epic Universe", "merch", "Super Nintendo World Orlando Grand Opening Set", "Grand Opening", "high", 120),
        # Hong Kong Disneyland
        ("Hong Kong Disney", "merch", "HKDL Frozen World Grand Opening Ears", "Grand Opening", "high", 65),
        ("Hong Kong Disney", "merch", "HKDL World of Frozen Elsa Crystal Figure", "Grand Opening", "high", 90),
        ("Hong Kong Disney", "pins", "HKDL 20th Anniversary Celebration Pin Set", "Anniversary LE", "high", 80),
    ]
    catalog = []
    for park, subcategory, name, edition, tier, price in variants:
        catalog.append({
            "park": park,
            "subcategory": subcategory,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    park = item["park"]
    name = item["name"]
    edition = item["edition"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{park}-{name}"),
        title=name,
        set_code=slugify(park),
        brand=park,
        rarity=item["rarity_tier"].title(),
        notes=f"{park} | {item['subcategory']} | {edition}",
        attributes_json={
            "park": park,
            "subcategory": item["subcategory"],
            "edition": edition,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    edition = item["edition"]
    edition_map = {
        "LE 300": 0.95, "LE": 0.85, "Grand Opening": 0.85,
        "Anniversary LE": 0.8, "D100 Exclusive": 0.75,
        "Festival LE": 0.75, "AP Exclusive": 0.7,
        "Tokyo Exclusive": 0.7, "Collab Exclusive": 0.6,
        "Park Exclusive": 0.6, "Limited Release": 0.65,
        "Vintage": 0.9,
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
    parser = argparse.ArgumentParser(description="Import theme park exclusives catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Theme Park Exclusives Import ===")

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

    logger.info(f"\n=== Theme Park Exclusives Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
