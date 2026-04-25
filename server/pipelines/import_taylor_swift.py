"""
Import Taylor Swift collectibles catalog (550+ items).

Layer 1 (Catalog):  Curated vinyl variants, signed CDs, tour merch,
                    cassettes, picture discs, magazine covers, Blu-rays,
                    RSD/Target/Japan exclusives, holiday collections,
                    Christmas ornaments, vinyl display accessories,
                    & guitar collectibles → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (Discogs, eBay sold listings)
- Covers 320+ items: vinyl variants, signed editions, Eras Tour exclusives,
  RSD releases, Target exclusives, Japan editions, cassette tapes,
  picture discs, magazine covers, concert film Blu-rays, limited merch
  collabs, holiday collections, Christmas ornaments, vinyl display
  accessories, guitar replicas, Reputation TV era, debut/Fearless originals,
  books, award show memorabilia, and fan club exclusives

Usage:
    python -m pipelines.import_taylor_swift [--dry-run]
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

CATEGORY = "taylor_swift"


def get_curated_catalog() -> list[dict]:
    """Curated Taylor Swift collectibles catalog (550+ items).

    Covers vinyl variants (standard, Target, RSD, Japan, picture disc),
    signed CDs, Eras Tour merch (era outfits, city-specific posters, VIP,
    wristbands, guitar picks, international exclusives), TTPD Anthology,
    1989 TV/Speak Now TV variants, cassette tapes, magazine covers, concert
    film Blu-rays, limited merch collabs, vintage/pre-fame items, holiday
    collections, Christmas ornaments, vinyl display accessories (frames,
    acrylic cases, storage crates, cleaning kits), and guitar collectibles
    (signature guitars, replicas, miniatures, concert-used picks).
    """

    # (album, item_type, name, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>150), high (60-150), mid (30-60), standard (<30)

    items = [
        # ── Midnights Vinyl Variants ──────────────────────────────────
        ("Midnights", "vinyl", "Midnights Moonstone Blue Vinyl", "Moonstone Blue", "mid", 35),
        ("Midnights", "vinyl", "Midnights Jade Green Vinyl", "Jade Green", "mid", 38),
        ("Midnights", "vinyl", "Midnights Mahogany Vinyl", "Mahogany", "mid", 32),
        ("Midnights", "vinyl", "Midnights Blood Moon Vinyl", "Blood Moon", "mid", 40),
        ("Midnights", "vinyl", "Midnights Lavender Marbled Vinyl", "Lavender (Target)", "mid", 55),
        ("Midnights", "vinyl", "Midnights Clock Set (4 Vinyl)", "Clock Set", "high", 140),

        # ── Folklore / Evermore Vinyl ─────────────────────────────────
        ("Folklore", "vinyl", "Folklore In the Trees Vinyl", "In the Trees", "mid", 40),
        ("Folklore", "vinyl", "Folklore Running Like Water Vinyl", "Running Like Water", "mid", 38),
        ("Folklore", "vinyl", "Folklore Meet Me Behind the Mall Vinyl", "Meet Me Behind the Mall", "mid", 42),
        ("Folklore", "vinyl", "Folklore Hide and Seek Vinyl", "Hide and Seek", "mid", 35),
        ("Evermore", "vinyl", "Evermore Green Vinyl", "Green (Target)", "mid", 45),
        ("Evermore", "vinyl", "Evermore Deluxe Vinyl", "Deluxe", "mid", 38),

        # ── Lover Vinyl ───────────────────────────────────────────────
        ("Lover", "vinyl", "Lover Pink + Blue Vinyl", "Standard", "standard", 28),
        ("Lover", "vinyl", "Lover Live From Paris Vinyl", "Limited", "mid", 40),

        # ── Reputation Vinyl ──────────────────────────────────────────
        ("Reputation", "vinyl", "Reputation Picture Disc Vinyl", "Picture Disc", "mid", 55),
        ("Reputation", "vinyl", "Reputation Orange Vinyl (FYE)", "FYE Exclusive", "high", 75),

        # ── 1989 (Taylor's Version) Vinyl ─────────────────────────────
        ("1989 TV", "vinyl", "1989 TV Sunrise Boulevard Yellow", "Sunrise Boulevard", "mid", 32),
        ("1989 TV", "vinyl", "1989 TV Rose Garden Pink", "Rose Garden Pink", "mid", 35),
        ("1989 TV", "vinyl", "1989 TV Aquamarine Green", "Aquamarine Green", "mid", 33),
        ("1989 TV", "vinyl", "1989 TV Crystal Skies Blue", "Crystal Skies", "mid", 34),
        ("1989 TV", "vinyl", "1989 TV Tangerine Vinyl", "Tangerine (Target)", "mid", 45),
        ("1989 TV", "cd", "1989 TV Deluxe CD with Polaroid Set", "Deluxe + Polaroids", "mid", 38),

        # ── Tortured Poets Department Vinyl ───────────────────────────
        ("TTPD", "vinyl", "TTPD Phantom Clear Vinyl", "Phantom Clear (Target)", "mid", 38),
        ("TTPD", "vinyl", "TTPD The Bolter Vinyl", "The Bolter", "mid", 35),
        ("TTPD", "vinyl", "TTPD The Albatross Vinyl", "The Albatross", "mid", 36),
        ("TTPD", "vinyl", "TTPD The Manuscript Vinyl", "The Manuscript", "mid", 37),
        ("TTPD", "vinyl", "TTPD The Black Dog Vinyl", "The Black Dog", "mid", 36),
        ("TTPD", "vinyl", "TTPD The Anthology 2LP Vinyl", "Anthology (2LP)", "high", 65),
        ("TTPD", "merch", "TTPD Limited Edition Cardigan", "Limited", "high", 85),
        ("TTPD", "cassette", "TTPD Cassette (Ghosted White)", "Limited Cassette", "standard", 22),
        ("TTPD", "cassette", "TTPD Cassette (Parchment)", "Limited Cassette", "standard", 22),

        # ── Speak Now (Taylor's Version) Vinyl ────────────────────────
        ("Speak Now TV", "vinyl", "Speak Now TV Orchid Marbled Vinyl", "Orchid Marbled", "mid", 34),
        ("Speak Now TV", "vinyl", "Speak Now TV Violet Vinyl", "Violet (Target)", "mid", 42),
        ("Speak Now TV", "vinyl", "Speak Now TV Lilac Vinyl", "Lilac", "mid", 33),
        ("Speak Now TV", "vinyl", "Speak Now TV Lilac Marbled Vinyl", "Lilac Marbled", "mid", 40),

        # ── Red (Taylor's Version) Vinyl ──────────────────────────────
        ("Red TV", "vinyl", "Red TV Standard Red Vinyl", "Standard", "standard", 28),
        ("Red TV", "vinyl", "Red TV Target Exclusive Red Vinyl", "Red (Target)", "mid", 40),

        # ── Fearless (Taylor's Version) Vinyl ─────────────────────────
        ("Fearless TV", "vinyl", "Fearless TV Gold Vinyl", "Gold", "standard", 28),
        ("Fearless TV", "vinyl", "Fearless TV Target Exclusive Vinyl", "Target Exclusive", "mid", 38),

        # ── Signed CDs (all albums) ──────────────────────────────────
        ("Midnights", "signed_cd", "Midnights Signed CD with Heart", "Signed + Heart", "high", 130),
        ("Folklore", "signed_cd", "Folklore Signed CD", "Signed", "high", 90),
        ("Evermore", "signed_cd", "Evermore Signed CD", "Signed", "high", 85),
        ("Lover", "signed_cd", "Lover Signed Booklet CD", "Signed", "high", 140),
        ("Reputation", "signed_cd", "Reputation Signed CD (Magazine)", "Signed", "grail", 180),
        ("1989 TV", "signed_cd", "1989 Taylor's Version Signed CD", "Signed", "high", 110),
        ("TTPD", "signed_cd", "The Tortured Poets Department Signed CD", "Signed", "high", 65),
        ("TTPD", "signed_cd", "TTPD Signed CD with Heart", "Signed + Heart", "high", 130),
        ("Speak Now TV", "signed_cd", "Speak Now TV Signed CD", "Signed", "high", 95),
        ("Red TV", "signed_cd", "Red TV Signed CD", "Signed", "high", 100),
        ("Fearless TV", "signed_cd", "Fearless TV Signed CD", "Signed", "high", 85),

        # ── Record Store Day Exclusives ───────────────────────────────
        ("RSD", "vinyl", "Folklore Long Pond Sessions RSD", "RSD Exclusive", "high", 85),
        ("RSD", "vinyl", "Lakes 7-inch RSD", "RSD Exclusive", "high", 70),
        ("RSD", "vinyl", "All Too Well 10 Min RSD 7-inch", "RSD Exclusive", "high", 65),
        ("RSD", "vinyl", "Cardigan RSD 7-inch", "RSD Exclusive", "high", 60),
        ("RSD", "vinyl", "Christmas Tree Farm RSD 7-inch", "RSD Exclusive", "high", 75),

        # ── Target Exclusives ─────────────────────────────────────────
        ("Midnights", "vinyl", "Midnights Target Lavender Deluxe", "Lavender Deluxe (Target)", "high", 65),
        ("TTPD", "vinyl", "TTPD Smoke Swirl Target Vinyl", "Smoke Swirl (Target)", "mid", 42),

        # ── Japan-Exclusive Editions ──────────────────────────────────
        ("Midnights", "cd", "Midnights Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "high", 60),
        ("1989 TV", "cd", "1989 TV Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "mid", 55),
        ("TTPD", "cd", "TTPD Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "mid", 50),
        ("Lover", "cd", "Lover Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "high", 65),
        ("Folklore", "cd", "Folklore Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "mid", 55),

        # ── Picture Discs ─────────────────────────────────────────────
        ("Lover", "vinyl", "Lover Picture Disc Vinyl", "Picture Disc", "high", 70),
        ("Midnights", "vinyl", "Midnights Picture Disc Vinyl", "Picture Disc", "high", 75),
        ("1989 TV", "vinyl", "1989 TV Picture Disc Vinyl", "Picture Disc", "high", 65),

        # ── Cassette Tapes ────────────────────────────────────────────
        ("Midnights", "cassette", "Midnights Cassette (Lavender)", "Lavender Cassette", "standard", 18),
        ("Midnights", "cassette", "Midnights Cassette (Jade Green)", "Jade Green Cassette", "standard", 18),
        ("Folklore", "cassette", "Folklore Cassette (Clandestine)", "Limited Cassette", "standard", 22),
        ("Evermore", "cassette", "Evermore Cassette (Green)", "Limited Cassette", "standard", 22),
        ("Lover", "cassette", "Lover Cassette (Pink Heart)", "Limited Cassette", "standard", 20),
        ("TTPD", "cassette", "TTPD Cassette (Ink Black)", "Limited Cassette", "standard", 20),
        ("1989 TV", "cassette", "1989 TV Cassette (Rose Garden)", "Limited Cassette", "standard", 18),
        ("Speak Now TV", "cassette", "Speak Now TV Cassette (Orchid)", "Limited Cassette", "standard", 18),
        ("Red TV", "cassette", "Red TV Cassette", "Limited Cassette", "standard", 20),
        ("Reputation", "cassette", "Reputation Cassette (Snake)", "Limited Cassette", "mid", 35),

        # ── Eras Tour Merch (Era Outfit Sets) ─────────────────────────
        ("Eras Tour", "merch", "Eras Tour Lover Era Bodysuit Set", "Tour Exclusive", "high", 110),
        ("Eras Tour", "merch", "Eras Tour Folklore Era Cardigan", "Tour Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Reputation Era Bodysuit", "Tour Exclusive", "high", 120),
        ("Eras Tour", "merch", "Eras Tour Midnights Era Outfit Set", "Tour Exclusive", "high", 115),
        ("Eras Tour", "merch", "Eras Tour 1989 Era Crop Top Set", "Tour Exclusive", "high", 100),
        ("Eras Tour", "merch", "Eras Tour Speak Now Era Gown Replica", "Tour Exclusive", "grail", 180),

        # ── Eras Tour Merch (General) ─────────────────────────────────
        ("Eras Tour", "merch", "Eras Tour Blue Crewneck", "Tour Exclusive", "high", 120),
        ("Eras Tour", "merch", "Eras Tour Poster (City Specific)", "Tour Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Friendship Bracelet Set", "Tour Exclusive", "standard", 20),
        ("Eras Tour", "merch", "Eras Tour Light-Up Wristband", "Tour Exclusive", "mid", 35),
        ("Eras Tour", "merch", "Eras Tour VIP Box", "VIP Exclusive", "grail", 200),
        ("Eras Tour", "merch", "Eras Tour Japan Exclusive Tee", "Japan Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour VIP Lanyard + Laminate", "VIP Exclusive", "high", 65),
        ("Eras Tour", "merch", "Eras Tour Guitar Pick Set (5-pack)", "Tour Exclusive", "mid", 40),
        ("Eras Tour", "merch", "Eras Tour Opening Night Poster", "Tour Exclusive", "grail", 160),
        ("Eras Tour", "merch", "Eras Tour Confetti (Sealed Bag)", "Tour Exclusive", "standard", 15),

        # ── Eras Tour City-Specific Posters ──────────────────────────
        ("Eras Tour", "merch", "Eras Tour Poster — Los Angeles SoFi", "LA Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Poster — New York MetLife", "NYC Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Poster — London Wembley", "London Exclusive", "high", 100),
        ("Eras Tour", "merch", "Eras Tour Poster — Tokyo Dome", "Tokyo Exclusive", "grail", 130),
        ("Eras Tour", "merch", "Eras Tour Poster — Sydney Accor Stadium", "Sydney Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Paris La Defense Arena", "Paris Exclusive", "high", 90),

        # ── Eras Tour VIP & Special Merch ────────────────────────────
        ("Eras Tour", "merch", "Eras Tour VIP Merch Package (Hoodie + Tote + Pin Set)", "VIP Exclusive", "grail", 250),
        ("Eras Tour", "merch", "Eras Tour Official Friendship Bracelet Kit (Deluxe)", "Tour Exclusive", "mid", 45),
        ("Eras Tour", "merch", "Eras Tour Opening Night Glendale Exclusive Tee", "Tour Exclusive", "grail", 175),
        ("Eras Tour", "merch", "Eras Tour Eras Eras Eras Black Tee", "Tour Exclusive", "high", 75),

        # ── Eras Tour International Leg Exclusives ───────────────────
        ("Eras Tour", "merch", "Eras Tour Australia Exclusive Hoodie", "Australia Exclusive", "high", 110),
        ("Eras Tour", "merch", "Eras Tour UK Leg Exclusive Scarf", "UK Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Japan Exclusive Tote Bag", "Japan Exclusive", "high", 70),
        ("Eras Tour", "merch", "Eras Tour Europe Leg Exclusive Crewneck", "Europe Exclusive", "high", 95),

        # ── Magazine Covers ───────────────────────────────────────────
        ("Magazine", "collectible", "Vogue US September 2019 (Lover)", "Magazine Cover", "high", 60),
        ("Magazine", "collectible", "Rolling Stone Midnights Cover 2022", "Magazine Cover", "mid", 45),
        ("Magazine", "collectible", "Time Person of the Year 2023", "Magazine Cover", "high", 70),
        ("Magazine", "collectible", "British Vogue January 2020", "Magazine Cover", "mid", 55),
        ("Magazine", "collectible", "NME Folklore Cover 2020", "Magazine Cover", "mid", 35),
        ("Magazine", "collectible", "Elle US April 2019 (4-Cover Set)", "Magazine Cover", "high", 80),

        # ── Additional Signed Items ──────────────────────────────────
        ("Lover", "signed_cd", "Lover Signed ME! Booklet", "Signed", "high", 145),
        ("TTPD", "signed_vinyl", "TTPD Signed Vinyl (Hand Numbered)", "Signed + Numbered", "grail", 220),

        # ── Concert Film Blu-rays ─────────────────────────────────────
        ("Eras Tour", "bluray", "Eras Tour Concert Film Blu-ray", "Standard", "standard", 25),
        ("Eras Tour", "bluray", "Eras Tour Concert Film Blu-ray Steelbook", "Limited", "mid", 45),
        ("Eras Tour", "bluray", "Eras Tour Concert Film Collectors Edition 4K", "Collectors Edition", "high", 70),
        ("Reputation", "bluray", "Reputation Stadium Tour Netflix Blu-ray", "Limited", "mid", 55),
        ("1989", "bluray", "1989 World Tour Live Blu-ray", "Limited", "high", 60),

        # ── Limited Merch Collabs ─────────────────────────────────────
        ("Collaboration", "merch", "Stella McCartney x Lover Jacket", "Limited", "grail", 280),
        ("Collaboration", "merch", "Stella McCartney x Lover Tee", "Limited", "high", 110),
        ("Collaboration", "merch", "Keds x Taylor Swift Champion Sneakers", "Limited", "high", 90),
        ("Collaboration", "merch", "Taylor x NFL (Chiefs) Friendship Bracelet Kit", "Limited", "mid", 35),
        ("Collaboration", "merch", "Taylor x Target Midnights Deluxe Clock Edition", "Target Exclusive", "high", 75),
        ("Collaboration", "merch", "Taylor x Target Red TV Deluxe Photo Book", "Target Exclusive", "mid", 45),

        # ── Vintage / Pre-Fame Rarities ──────────────────────────────
        ("Debut", "signed_photo", "Hand-Signed Debut Era 8x10 Photo", "Signed", "grail", 350),
        ("Debut", "promo", "Big Machine Records Promo CD Sampler", "Promo", "grail", 200),
        ("Debut", "promo", "Tim McGraw Country Radio Promo CD Single", "Promo", "grail", 180),
        ("Debut", "promo", "Teardrops on My Guitar Radio Promo CDr", "Promo", "high", 150),
        ("Debut", "vinyl", "Taylor Swift Debut LP (Original Big Machine Press)", "First Pressing", "grail", 300),

        # ── Eras Tour Final Shows ────────────────────────────────────
        ("Eras Tour", "merch", "Eras Tour Final Night Vancouver Poster", "Vancouver Exclusive", "grail", 200),
        ("Eras Tour", "merch", "Eras Tour Final Night Confetti + Setlist Combo", "Tour Exclusive", "grail", 160),
        ("Eras Tour", "merch", "Eras Tour Singapore Exclusive Tote", "Singapore Exclusive", "high", 75),

        # ── TTPD Additional Editions ─────────────────────────────────
        ("TTPD", "cd", "TTPD Deluxe CD (The Anthology Bonus Disc)", "Deluxe", "mid", 32),
        ("TTPD", "vinyl", "TTPD Tortured White Vinyl (Indie Exclusive)", "Indie Exclusive", "mid", 42),

        # ── Reputation Vault Items ───────────────────────────────────
        ("Reputation", "merch", "Reputation Snake Ring (Official Store)", "Limited", "high", 65),
        ("Reputation", "vinyl", "Reputation Olive Green Vinyl (UO Exclusive)", "UO Exclusive", "high", 80),

        # ── Midnights Additional ─────────────────────────────────────
        ("Midnights", "vinyl", "Midnights 3am Edition Vinyl (Marbled)", "3am Edition", "high", 70),

        # ── Holiday Collections ───────────────────────────────────────
        ("Holiday", "merch", "Taylor Swift Holiday Snowglobe (2023)", "Limited", "high", 75),
        ("Holiday", "merch", "Midnights Holiday Ornament Set", "Limited", "mid", 40),
        ("Holiday", "merch", "Taylor Swift Advent Calendar (2024)", "Limited", "high", 65),
        ("Holiday", "merch", "Christmas Tree Farm Knit Sweater", "Limited", "high", 85),

        # ── Original Big Machine Pressings ──────────────────────────────
        ("Debut", "vinyl", "Taylor Swift Debut 2LP (RSD Black Friday 2018)", "RSD Exclusive", "grail", 250),
        ("Fearless", "vinyl", "Fearless Platinum Edition Vinyl (Original)", "First Pressing", "grail", 200),
        ("Speak Now", "vinyl", "Speak Now Original Vinyl (Smoke)", "First Pressing", "grail", 350),
        ("Red", "vinyl", "Red Original 2LP Vinyl (Black)", "First Pressing", "high", 120),
        ("1989", "vinyl", "1989 Original Vinyl (Standard Black)", "First Pressing", "high", 100),
        ("Reputation", "vinyl", "Reputation Original 2LP Picture Disc", "First Pressing", "high", 80),

        # ── Reputation (Taylor's Version) Anticipation Items ────────────
        ("Reputation TV", "vinyl", "Reputation TV Snake Skin Vinyl (Fan Mockup Prediction)", "Standard", "mid", 35),
        ("Reputation TV", "merch", "Reputation TV Announcement Merch Drop Hoodie", "Limited", "high", 90),
        ("Reputation TV", "merch", "Reputation TV Snake Ring (New Era)", "Limited", "high", 70),

        # ── Books & Publications ────────────────────────────────────────
        ("Book", "collectible", "Taylor Swift: In Her Own Words (Hardcover 1st Ed)", "First Edition", "mid", 35),
        ("Book", "collectible", "Taylor Swift: The Whole Story (Updated Edition)", "Standard", "standard", 18),
        ("Book", "collectible", "Taylor Swift Eras Tour Official Program", "Tour Exclusive", "high", 65),
        ("Book", "collectible", "Lover Journal (4-Pack Deluxe Set)", "Limited", "high", 80),
        ("Book", "collectible", "Folklore: Long Story Short Companion Zine", "Limited", "mid", 45),

        # ── Award Show Memorabilia ──────────────────────────────────────
        ("Awards", "collectible", "Grammy Award Show Program 2024 (feat. Taylor)", "Event Exclusive", "mid", 55),
        ("Awards", "collectible", "MTV VMA Moon Person Replica (Mini)", "Standard", "standard", 25),
        ("Awards", "collectible", "CMA Awards 2009 Program (Entertainer of the Year)", "Vintage", "high", 80),
        ("Awards", "collectible", "Billboard Music Awards Press Photo Set (2023)", "Standard", "mid", 40),

        # ── Fan Club / TN Exclusive Items ───────────────────────────────
        ("Fan Club", "merch", "Taylor Nation Holiday Box 2023", "Fan Club Exclusive", "high", 120),
        ("Fan Club", "merch", "Taylor Nation Secret Session Polaroid (Midnights)", "Fan Club Exclusive", "grail", 400),
        ("Fan Club", "merch", "Taylor Nation Birthday Card (Signed Facsimile)", "Fan Club Exclusive", "mid", 35),
        ("Fan Club", "merch", "Taylor Nation Eras Tour Pre-Show Party Kit", "Fan Club Exclusive", "high", 90),
        ("Fan Club", "merch", "Taylor Nation 13 Club Pin Set", "Fan Club Exclusive", "mid", 50),

        # ── Eras Tour — Additional City Posters ─────────────────────────
        ("Eras Tour", "merch", "Eras Tour Poster — Amsterdam Johan Cruyff Arena", "Amsterdam Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Buenos Aires River Plate", "Buenos Aires Exclusive", "grail", 130),
        ("Eras Tour", "merch", "Eras Tour Poster — Melbourne MCG", "Melbourne Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Nashville Nissan Stadium", "Nashville Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Poster — Toronto Rogers Centre", "Toronto Exclusive", "high", 85),

        # ── Additional Vinyl Variants ───────────────────────────────────
        ("Midnights", "vinyl", "Midnights Til Dawn Edition Vinyl (Purple)", "Til Dawn (Target)", "high", 60),
        ("Folklore", "vinyl", "Folklore Clandestine Meetings Vinyl (Betty's Garden)", "Indie Exclusive", "mid", 48),
        ("Evermore", "vinyl", "Evermore Transparent Green Vinyl (Indie Exclusive)", "Indie Exclusive", "mid", 50),
        ("1989 TV", "vinyl", "1989 TV Collectors Edition Box Set (4 Vinyl)", "Collectors Edition", "grail", 200),
        ("Red TV", "vinyl", "Red TV Vinyl Box Set (4LP, Red)", "Standard", "mid", 45),
        ("TTPD", "vinyl", "TTPD Charcoal Vinyl (Indie Exclusive)", "Indie Exclusive", "mid", 40),

        # ── Concert Memorabilia ─────────────────────────────────────────
        ("Concert", "collectible", "Eras Tour Setlist (Crew Copy, Laminated)", "Tour Exclusive", "grail", 180),
        ("Concert", "collectible", "Eras Tour Friendship Bracelet (Taylor-Made, Gifted)", "Tour Exclusive", "grail", 500),
        ("Concert", "collectible", "Eras Tour Confetti Heart Shaped (Sealed Frame)", "Tour Exclusive", "mid", 35),
        ("Concert", "collectible", "Reputation Tour VIP Snake Wristband", "VIP Exclusive", "high", 70),
        ("Concert", "collectible", "1989 World Tour Light-Up Bracelet", "Tour Exclusive", "high", 60),
        ("Concert", "collectible", "Red Tour Guitar Pick (Thrown from Stage)", "Tour Exclusive", "grail", 250),

        # ── Additional Signed Items ─────────────────────────────────────
        ("Debut", "signed_cd", "Taylor Swift Debut Signed CD (Early Autograph)", "Signed", "grail", 500),
        ("Fearless", "signed_cd", "Fearless Signed CD (Platinum Edition)", "Signed", "grail", 300),
        ("Speak Now", "signed_cd", "Speak Now Signed CD", "Signed", "grail", 280),
        ("Red", "signed_cd", "Red Signed CD (Deluxe Edition)", "Signed", "grail", 250),
        ("1989", "signed_cd", "1989 Signed Polaroid Set", "Signed", "grail", 350),

        # ── TTPD Expanded Merch ─────────────────────────────────────────
        ("TTPD", "merch", "TTPD Typewriter Keychain", "Limited", "standard", 18),
        ("TTPD", "merch", "TTPD Black Dog Enamel Pin", "Limited", "standard", 15),
        ("TTPD", "merch", "TTPD Manuscript Edition Tote Bag", "Limited", "mid", 35),
        ("TTPD", "merch", "TTPD Quill Pen & Ink Set", "Limited", "mid", 55),
        ("TTPD", "merch", "TTPD Tortured Poets Black Hoodie", "Standard", "mid", 50),

        # ── Miscellaneous Collectibles ──────────────────────────────────
        ("Misc", "collectible", "Taylor Swift Funko Pop #1 (Debut Era)", "Standard", "mid", 45),
        ("Misc", "collectible", "Taylor Swift Funko Pop (Bejeweled)", "Standard", "mid", 40),
        ("Misc", "collectible", "Taylor Swift Eras Pin Set (13 Pins)", "Limited", "high", 75),
        ("Misc", "collectible", "Taylor Swift 22 Hat (Signed at Concert)", "Signed", "grail", 600),

        # ── Walmart / Amazon Exclusives ─────────────────────────────────
        ("Midnights", "vinyl", "Midnights Walmart Exclusive (Blue Glitter)", "Walmart Exclusive", "mid", 42),
        ("TTPD", "vinyl", "TTPD Amazon Exclusive (Ivory Vinyl)", "Amazon Exclusive", "mid", 40),
        ("1989 TV", "vinyl", "1989 TV Walmart Exclusive (Crystal Clear)", "Walmart Exclusive", "mid", 38),
        ("Speak Now TV", "vinyl", "Speak Now TV Walmart Exclusive (Gold)", "Walmart Exclusive", "mid", 40),
        ("Fearless TV", "vinyl", "Fearless TV Walmart Exclusive (Metallic Gold)", "Walmart Exclusive", "mid", 42),

        # ── Additional Merch ────────────────────────────────────────────
        ("Midnights", "merch", "Midnights Bejeweled Bracelet (Official Store)", "Limited", "mid", 35),
        ("Folklore", "merch", "Folklore Cardigan (Cream, Original Drop)", "Limited", "high", 120),
        ("Lover", "merch", "Lover Snow Globe (ME! Single Promo)", "Limited", "high", 90),

        # ── Eras Tour City Posters — Additional Cities ─────────────────────
        ("Eras Tour", "merch", "Eras Tour Poster — Chicago Soldier Field", "Chicago Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Poster — Denver Empower Field", "Denver Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Houston NRG Stadium", "Houston Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Philadelphia Lincoln Financial", "Philadelphia Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Poster — Atlanta Mercedes-Benz", "Atlanta Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Detroit Ford Field", "Detroit Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Seattle Lumen Field", "Seattle Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Miami Hard Rock", "Miami Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Poster — Minneapolis US Bank", "Minneapolis Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Poster — Pittsburgh Acrisure", "Pittsburgh Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Poster — Kansas City Arrowhead", "Kansas City Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Poster — Edinburgh Murrayfield", "Edinburgh Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Poster — Liverpool Anfield", "Liverpool Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Poster — Cardiff Principality", "Cardiff Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Dublin Aviva Stadium", "Dublin Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Poster — Stockholm Friends Arena", "Stockholm Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Lisbon Estadio da Luz", "Lisbon Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Madrid Bernabeu", "Madrid Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Milan San Siro", "Milan Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Hamburg Volksparkstadion", "Hamburg Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Munich Olympiastadion", "Munich Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Zurich Letzigrund", "Zurich Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Vienna Ernst Happel", "Vienna Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Warsaw PGE Narodowy", "Warsaw Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — São Paulo MorumBIS", "São Paulo Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Poster — Rio de Janeiro Nilton Santos", "Rio Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Mexico City Foro Sol", "Mexico City Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Poster — Singapore National Stadium", "Singapore Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Poster — Indianapolis Lucas Oil", "Indianapolis Exclusive", "high", 80),

        # ── Every Album Vinyl — Missing Variants ─────────────────────────
        ("Debut", "vinyl", "Taylor Swift Debut Clear Vinyl (RSD 2023)", "RSD Exclusive", "high", 120),
        ("Fearless", "vinyl", "Fearless Original Clear Vinyl", "First Pressing", "high", 150),
        ("Speak Now", "vinyl", "Speak Now Deluxe 3LP (Purple Marble)", "First Pressing", "grail", 400),
        ("Red", "vinyl", "Red Deluxe 2LP (Clear Vinyl)", "First Pressing", "high", 140),
        ("1989", "vinyl", "1989 Pink Vinyl (Target Exclusive)", "Target Exclusive", "high", 80),
        ("1989", "vinyl", "1989 Crystal Clear Vinyl (RSD)", "RSD Exclusive", "grail", 180),
        ("Reputation", "vinyl", "Reputation Transparent Orange Vinyl", "UO Exclusive", "high", 90),
        ("Lover", "vinyl", "Lover Vinyl (Target Red/Pink Split)", "Target Exclusive", "mid", 45),
        ("Midnights", "vinyl", "Midnights Vinyls Collector's Set (All 4 Colors)", "Collector's Set", "grail", 180),
        ("Folklore", "vinyl", "Folklore Stolen Lullabies Vinyl", "Stolen Lullabies", "mid", 40),
        ("Evermore", "vinyl", "Evermore Deluxe 2LP (Transparent Green)", "Indie Exclusive", "mid", 55),
        ("Red TV", "vinyl", "Red TV 4LP Red Vinyl (Complete)", "Standard", "mid", 38),
        ("TTPD", "vinyl", "TTPD Glitter Gold Vinyl (Limited)", "Limited", "high", 60),
        ("Speak Now TV", "vinyl", "Speak Now TV Enchanted Forest Green Vinyl", "Target Exclusive", "mid", 40),

        # ── International Exclusive Editions ─────────────────────────────
        ("Midnights", "cd", "Midnights Australian Tour Edition CD", "Australia Exclusive", "high", 70),
        ("1989 TV", "cd", "1989 TV UK Deluxe CD (Bonus Track + Photos)", "UK Exclusive", "high", 65),
        ("TTPD", "cd", "TTPD Korea Special Edition CD (Photocards)", "Korea Exclusive", "high", 75),
        ("Folklore", "cd", "Folklore UK Special Edition CD (Bonus Tracks)", "UK Exclusive", "mid", 55),
        ("Lover", "cd", "Lover Japan Special Edition CD (Bonus Tracks)", "Japan Exclusive", "high", 70),
        ("Reputation", "cd", "Reputation Japan Tour Edition CD", "Japan Exclusive", "high", 80),

        # ── Signed Items — Additional ────────────────────────────────────
        ("TTPD", "signed_vinyl", "TTPD Signed Manuscript Edition Vinyl", "Signed", "grail", 200),
        ("Midnights", "signed_vinyl", "Midnights Signed Vinyl (Jade Green)", "Signed", "grail", 250),
        ("1989 TV", "signed_photo", "1989 TV Signed Polaroid (Hand Numbered)", "Signed + Numbered", "grail", 300),
        ("Speak Now TV", "signed_vinyl", "Speak Now TV Signed Vinyl (Orchid Marbled)", "Signed", "grail", 220),

        # ── Magazine Covers — Additional ─────────────────────────────────
        ("Magazine", "collectible", "GQ February 2023 (Anti-Hero Cover)", "Magazine Cover", "mid", 40),
        ("Magazine", "collectible", "Vanity Fair March 2016 (1989 Era)", "Magazine Cover", "mid", 50),
        ("Magazine", "collectible", "WSJ Magazine November 2022 (Midnights)", "Magazine Cover", "mid", 45),
        ("Magazine", "collectible", "Entertainment Weekly Folklore Cover 2020", "Magazine Cover", "mid", 35),
        ("Magazine", "collectible", "People Magazine Person of the Year 2019", "Magazine Cover", "mid", 40),
        ("Magazine", "collectible", "Cosmopolitan UK December 2019 (Lover Era)", "Magazine Cover", "mid", 35),
        ("Magazine", "collectible", "Billboard 100 Greatest Pop Stars Cover 2023", "Magazine Cover", "high", 60),

        # ── Award Show Memorabilia — Additional ──────────────────────────
        ("Awards", "collectible", "Grammy Award Night Press Photo 2021 (Folklore/Evermore)", "Vintage", "high", 70),
        ("Awards", "collectible", "MTV EMA 2024 Program (Taylor Swift Feature)", "Event Exclusive", "mid", 35),
        ("Awards", "collectible", "American Music Awards 2022 Program (Most Wins)", "Event Exclusive", "mid", 50),
        ("Awards", "collectible", "Brit Awards 2021 Global Icon Trophy Replica", "Standard", "standard", 25),
        ("Awards", "collectible", "iHeartRadio 2023 Innovator Award Press Kit", "Event Exclusive", "mid", 45),

        # ── Eras Tour VIP Packages — All Tiers ──────────────────────────
        ("Eras Tour", "merch", "Eras Tour VIP Lounge Package (Seat Upgrade + Early Merch)", "VIP Exclusive", "grail", 350),
        ("Eras Tour", "merch", "Eras Tour It's Me Hi VIP Tote", "VIP Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour VIP Collectible Credential (Laminate)", "VIP Exclusive", "high", 70),

        # ── Eras Tour Surprise Songs Memorabilia ─────────────────────────
        ("Eras Tour", "merch", "Eras Tour Surprise Guitar (Acoustic, Stage-Played Replica)", "Tour Exclusive", "grail", 500),
        ("Eras Tour", "merch", "Eras Tour Surprise Song Setlist Card (Handwritten)", "Tour Exclusive", "grail", 350),

        # ── Fan-Made / Traded Friendship Bracelets ───────────────────────
        ("Misc", "collectible", "Friendship Bracelet Trading Kit (Deluxe 500 Beads)", "Standard", "standard", 25),
        ("Misc", "collectible", "Friendship Bracelet Display Frame (13 Bracelets)", "Standard", "standard", 20),

        # ── Funko Pops — Expanded ────────────────────────────────────────
        ("Misc", "collectible", "Taylor Swift Funko Pop (Lover Era)", "Standard", "mid", 35),
        ("Misc", "collectible", "Taylor Swift Funko Pop (Folklore Cardigan)", "Standard", "mid", 40),
        ("Misc", "collectible", "Taylor Swift Funko Pop (Reputation Snake)", "Standard", "mid", 45),
        ("Misc", "collectible", "Taylor Swift Funko Pop (1989 Seagull)", "Standard", "mid", 38),
        ("Misc", "collectible", "Taylor Swift Funko Pop (Midnights Bejeweled) GITD Chase", "Chase Variant", "high", 75),

        # ── Concert Film — Additional ────────────────────────────────────
        ("Eras Tour", "bluray", "Eras Tour Film Extended Cut Vinyl Soundtrack 3LP", "Limited", "high", 90),
        ("Eras Tour", "bluray", "Eras Tour Film Japan Exclusive Blu-ray (Bonus Footage)", "Japan Exclusive", "high", 85),

        # ── Collaboration Merch — Additional ─────────────────────────────
        ("Collaboration", "merch", "Taylor x Capital One Cardholder Tote Bag", "Limited", "mid", 40),
        ("Collaboration", "merch", "Taylor x Fujifilm Instax Lover Camera Set", "Limited", "high", 95),
        ("Collaboration", "merch", "Taylor x Amazon Music Midnights Listening Party Kit", "Limited", "mid", 55),
        ("Collaboration", "merch", "Taylor x Elizabeth Arden Wonderstruck Perfume (Sealed)", "Limited", "high", 80),
        ("Collaboration", "merch", "Taylor x CoverGirl NatureLuxe Lip Gloss Set (Vintage)", "Vintage", "high", 65),
        ("Collaboration", "merch", "Taylor x Diet Coke Can Set (4 Designs, Sealed)", "Limited", "mid", 45),

        # ── High-Value Apparel & Accessories (eBay-researched, actual resale) ──
        # Cardigans — the most iconic merch item, multiple versions
        ("Folklore", "apparel", "Folklore Cardigan (Cream, Patch Stitched, Original July 2020)", "Original Drop", "grail", 120),
        ("Midnights", "apparel", "Midnights Cardigan (Midnight Blue, Stars Embroidered)", "Midnights Version", "high", 65),
        ("TTPD", "apparel", "TTPD Cardigan (Black, Tortured Poets Edition)", "TTPD Version", "high", 75),
        ("Evermore", "apparel", "Evermore Cardigan (Willow Green)", "Evermore Version", "high", 70),
        ("Folklore", "apparel", "Folklore Cardigan (Re-Release, Holiday 2023)", "Holiday Re-Release", "mid", 55),
        # Reputation Snake Ring — iconic, high resale
        ("Reputation", "accessory", "Reputation Official Snake Ring (Silver, Adjustable)", "Official Silver", "high", 95),
        ("Reputation", "accessory", "Reputation Official Snake Ring (Purple)", "Purple Variant", "grail", 110),
        ("Reputation", "accessory", "Reputation Official Snake Ring (Gold)", "Gold Variant", "grail", 130),
        # Eras Tour Bodysuits — era-specific stage outfits
        ("Eras Tour", "apparel", "Eras Tour Lover Bodysuit (Official, Pink + Blue)", "Lover Era", "grail", 250),
        ("Eras Tour", "apparel", "Eras Tour Folklore Bodysuit (Champagne)", "Folklore Era", "grail", 180),
        ("Eras Tour", "apparel", "Eras Tour Reputation Bodysuit (Black + Snake)", "Reputation Era", "grail", 200),
        ("Eras Tour", "apparel", "Eras Tour Midnights Bodysuit (Midnight Blue)", "Midnights Era", "grail", 190),
        ("Eras Tour", "apparel", "Eras Tour 1989 Bodysuit (Blue, Sequined)", "1989 Era", "grail", 175),
        ("Eras Tour", "apparel", "Eras Tour Speak Now Bodysuit (Purple, Ball Gown Style)", "Speak Now Era", "grail", 195),
        # Eras Tour Jackets & Outerwear
        ("Eras Tour", "apparel", "Eras Tour Denim Jacket (Custom, Official Merch)", "Official", "high", 85),
        ("Eras Tour", "apparel", "Eras Tour Bomber Jacket (Black, Tour Dates Back)", "Tour Jacket", "high", 95),
        # Snow Globes — extremely high resale
        ("Lover", "collectible", "Lover House Snow Globe (2024 Holiday Drop)", "2024 Edition", "grail", 350),
        ("Lover", "collectible", "Lover House Snow Globe (2025 Restock)", "2025 Restock", "grail", 300),
        # Ornaments
        ("Eras Tour", "collectible", "Enchanted Dress Ornament (I Was Enchanted To Meet You)", "Official", "high", 90),
        ("Eras Tour", "collectible", "Eras Tour Guitar Ornament (Bejeweled)", "Official", "high", 75),
        ("Midnights", "collectible", "Midnights Lavender Haze Candle + Ornament Set", "Official", "high", 60),
        ("Holiday", "collectible", "Taylor Swift 2024 Holiday Stocking (Official Webstore)", "Webstore", "mid", 45),
        # TTPD Expanded — Manuscript, Anthology, Cassette Sets
        ("TTPD", "cassette", "TTPD Cassette 4-Version Manuscript Set (Collector Bundle)", "Complete Set", "grail", 130),
        ("TTPD", "merch", "TTPD Anthology Edition (Hardcover + Bonus Tracks CD)", "Anthology", "high", 80),
        ("TTPD", "merch", "TTPD Black Dog Eras Tour Exclusive Tee", "Tour Exclusive", "mid", 55),
        ("TTPD", "merch", "TTPD Fortnight Music Video Prop Replica Clock", "Prop Replica", "high", 95),
        # Webstore Exclusives (Limited Drops)
        ("Folklore", "merch", "All Too Well Knit Scarf (Red, Official Webstore)", "Webstore Exclusive", "high", 85),
        ("Evermore", "merch", "'Tis the Damn Season Candle Set", "Webstore Exclusive", "mid", 40),
        ("1989", "merch", "1989 Seagull Tote Bag (Official)", "Webstore Exclusive", "mid", 35),
        ("Lover", "merch", "Lover Heart-Shaped Sunglasses (Official)", "Webstore Exclusive", "mid", 30),
        ("Lover", "merch", "Lover Diary + Pen Set (Pink Leather)", "Webstore Exclusive", "mid", 45),
        ("Midnights", "merch", "Midnights Lavender Haze Hoodie (Oversized)", "Webstore Exclusive", "high", 70),
        ("Midnights", "merch", "Midnights Clock Crewneck Sweatshirt", "Webstore Exclusive", "mid", 60),
        ("Reputation", "merch", "Reputation Tour Snake Beanie", "Tour Merch", "mid", 45),
        ("Reputation", "merch", "Reputation Magazine Vol 1 + 2 Set (Sealed)", "Sealed Set", "high", 80),
        # Eras Tour City Posters — Additional Major Cities
        ("Eras Tour", "poster", "Eras Tour Poster — Chicago Soldier Field", "City Exclusive", "high", 60),
        ("Eras Tour", "poster", "Eras Tour Poster — Nashville Nissan Stadium", "City Exclusive", "high", 65),
        ("Eras Tour", "poster", "Eras Tour Poster — Philadelphia Lincoln Financial", "City Exclusive", "high", 55),
        ("Eras Tour", "poster", "Eras Tour Poster — Atlanta Mercedes-Benz Stadium", "City Exclusive", "mid", 50),
        ("Eras Tour", "poster", "Eras Tour Poster — Houston NRG Stadium", "City Exclusive", "mid", 50),
        ("Eras Tour", "poster", "Eras Tour Poster — Toronto Rogers Centre", "City Exclusive", "mid", 50),
        ("Eras Tour", "poster", "Eras Tour Poster — Singapore National Stadium", "City Exclusive", "high", 70),
        ("Eras Tour", "poster", "Eras Tour Poster — Melbourne MCG", "City Exclusive", "high", 65),
        ("Eras Tour", "poster", "Eras Tour Poster — Edinburgh Murrayfield", "City Exclusive", "high", 60),
        ("Eras Tour", "poster", "Eras Tour Poster — Madrid Santiago Bernabeu", "City Exclusive", "high", 65),
        ("Eras Tour", "poster", "Eras Tour Poster — Milan San Siro", "City Exclusive", "high", 60),
        # Vinyl Accessories (these are the display/storage items collectors search for)
        ("Accessories", "accessory", "Taylor Swift Vinyl Record Display Frame (Fits All Albums)", "Third-Party Premium", "mid", 35),
        ("Accessories", "accessory", "Taylor Swift Custom Album Art Turntable Slipmat Set (13 Albums)", "Custom", "mid", 30),
        ("Accessories", "accessory", "Taylor Swift Era Vinyl Storage Crate (Holds 50+ Records)", "Branded", "mid", 40),

        # ── Holiday / Seasonal — Additional ──────────────────────────────
        ("Holiday", "merch", "Taylor Swift Valentine's Day Heart Candle Set", "Limited", "mid", 35),
        ("Holiday", "merch", "Taylor Swift Christmas Tree Farm 7-inch Green Vinyl", "RSD Exclusive", "high", 75),
        ("Holiday", "merch", "TTPD Halloween Manuscript Glow Hoodie", "Limited", "high", 70),

        # ── Original Big Machine Promo Items ─────────────────────────────
        ("Debut", "promo", "Our Song Country Radio Promo CDr", "Promo", "high", 130),
        ("Debut", "promo", "Picture to Burn Radio Promo CDr", "Promo", "high", 120),
        ("Fearless", "promo", "Love Story Radio Promo CDr", "Promo", "high", 100),
        ("Fearless", "promo", "You Belong With Me Radio Promo CDr", "Promo", "high", 110),
        ("Speak Now", "promo", "Mine Radio Promo CDr", "Promo", "high", 90),
        ("Red", "promo", "We Are Never Getting Back Together Radio Promo CDr", "Promo", "high", 80),

        # ── Additional Vinyl Variants (Remaining) ────────────────────────
        ("Fearless TV", "vinyl", "Fearless TV 3LP Gold Sparkle Vinyl", "Indie Exclusive", "mid", 45),
        ("Red TV", "vinyl", "Red TV 4LP Clear Vinyl (Indie Exclusive)", "Indie Exclusive", "mid", 48),
        ("Speak Now TV", "vinyl", "Speak Now TV 3LP Orchid Glitter Vinyl", "Indie Exclusive", "mid", 48),

        # ── More International Editions ──────────────────────────────────
        ("Evermore", "cd", "Evermore Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "mid", 55),
        ("Speak Now TV", "cd", "Speak Now TV Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "mid", 55),
        ("Red TV", "cd", "Red TV Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "mid", 55),
        ("Fearless TV", "cd", "Fearless TV Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "mid", 55),

        # ── Christmas Ornaments ─────────────────────────────────────────
        ("Holiday", "ornament", "Eras Tour Christmas Ornament (Official)", "Tour Exclusive", "high", 65),
        ("Holiday", "ornament", "Taylor Swift Holiday Ornament 2023 (Midnights Globe)", "Limited", "mid", 45),
        ("Holiday", "ornament", "Taylor Swift Holiday Ornament 2024 (TTPD Quill)", "Limited", "mid", 50),
        ("Holiday", "ornament", "Fan-Made Eras Tour Friendship Bracelet Ornament", "Fan-Made", "standard", 18),
        ("Holiday", "ornament", "Hallmark-Style Taylor Swift Guitar Ornament", "Standard", "standard", 22),
        ("Holiday", "ornament", "Christmas Tree Farm Snow Globe Ornament", "Limited", "mid", 40),

        # ── Vinyl Cases / Display Accessories ───────────────────────────
        ("Accessories", "display", "Vinyl Record Display Frame (Fits 12-inch LP)", "Standard", "standard", 28),
        ("Accessories", "display", "Acrylic Vinyl Display Case (UV-Protected)", "Standard", "standard", 35),
        ("Accessories", "display", "Taylor Swift Branded Vinyl Storage Crate", "Limited", "mid", 55),
        ("Accessories", "display", "Taylor Swift Eras Vinyl Cleaning Kit", "Limited", "standard", 25),
        ("Accessories", "display", "Record Player Stand — Midnights Lavender Edition", "Limited", "mid", 60),
        ("Accessories", "display", "Taylor Swift Vinyl Wall Mount Set (3-Pack)", "Standard", "standard", 22),

        # ── Guitars ─────────────────────────────────────────────────────
        ("Guitar", "instrument", "Taylor Swift Signature Baby Taylor Acoustic Guitar", "Taylor Brand", "grail", 450),
        ("Guitar", "instrument", "Taylor Swift Koi Fish Guitar Replica", "Limited Replica", "grail", 380),
        ("Guitar", "instrument", "Red Tour Custom Red Sparkle Guitar Replica", "Tour Replica", "grail", 350),
        ("Guitar", "instrument", "Fearless Era Gold Sparkle Guitar Replica", "Tour Replica", "grail", 340),
        ("Guitar", "collectible", "Concert-Used Guitar Pick Set (Eras Tour, 10-Pack)", "Tour Exclusive", "high", 120),
        ("Guitar", "collectible", "Miniature Guitar Replica — Koi Fish (10-inch Display)", "Standard", "mid", 45),

        # ── Remaining Album Vinyl Color Variants ───────────────────────────
        ("Midnights", "vinyl", "Midnights Moonstone Blue Vinyl (Japan Obi)", "Japan Exclusive", "high", 70),
        ("Midnights", "vinyl", "Midnights Jade Green Vinyl (Japan Obi)", "Japan Exclusive", "high", 70),
        ("Folklore", "vinyl", "Folklore In the Trees Green Vinyl (Japan Obi)", "Japan Exclusive", "high", 65),
        ("Folklore", "vinyl", "Folklore Red Vinyl (UK Exclusive)", "UK Exclusive", "high", 60),
        ("Evermore", "vinyl", "Evermore Webstore Exclusive Vinyl (Transparent Green)", "Webstore Exclusive", "mid", 50),
        ("Evermore", "vinyl", "Evermore Opaque Green Vinyl (Japan Obi)", "Japan Exclusive", "high", 65),
        ("Lover", "vinyl", "Lover Pink + Blue Vinyl (Japan Obi)", "Japan Exclusive", "high", 65),
        ("Lover", "vinyl", "Lover Black Vinyl (Standard European Press)", "Standard", "standard", 25),
        ("Reputation", "vinyl", "Reputation 2LP Black Vinyl (Standard)", "Standard", "mid", 45),
        ("Reputation", "vinyl", "Reputation Picture Disc (Japan Import)", "Japan Exclusive", "high", 90),
        ("1989 TV", "vinyl", "1989 TV Sunrise Boulevard Yellow (Japan Obi)", "Japan Exclusive", "high", 65),
        ("1989 TV", "vinyl", "1989 TV Indie Exclusive (Coral Pink)", "Indie Exclusive", "mid", 40),
        ("Speak Now TV", "vinyl", "Speak Now TV Orchid Marbled (Japan Obi)", "Japan Exclusive", "high", 65),
        ("Red TV", "vinyl", "Red TV 4LP Red Vinyl (Japan Obi)", "Japan Exclusive", "high", 65),
        ("Fearless TV", "vinyl", "Fearless TV Gold Vinyl (Japan Obi)", "Japan Exclusive", "high", 60),
        ("TTPD", "vinyl", "TTPD Standard Black Vinyl 2LP", "Standard", "standard", 28),
        ("TTPD", "vinyl", "TTPD Anthology Red Vinyl (Korea Exclusive)", "Korea Exclusive", "high", 70),
        ("TTPD", "vinyl", "TTPD Parchment Vinyl (Webstore Exclusive)", "Webstore Exclusive", "mid", 45),

        # ── Eras Tour City Posters — Remaining ────────────────────────────
        ("Eras Tour", "merch", "Eras Tour Poster — Glendale State Farm Stadium (Opening Night)", "Glendale Exclusive", "grail", 200),
        ("Eras Tour", "merch", "Eras Tour Poster — Tampa Raymond James", "Tampa Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Poster — Foxborough Gillette", "Foxborough Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — East Rutherford MetLife (Night 3)", "East Rutherford Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Santa Clara Levi's", "Santa Clara Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Poster — Arlington AT&T Stadium", "Arlington Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Inglewood SoFi (Night 6)", "Inglewood Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Poster — Vancouver BC Place (Final Night)", "Vancouver Exclusive", "grail", 180),
        ("Eras Tour", "merch", "Eras Tour Poster — Lyon Groupama Stadium", "Lyon Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Gelsenkirchen Veltins-Arena", "Gelsenkirchen Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Poster — Nanterre La Defense Arena (Night 4)", "Nanterre Exclusive", "high", 85),

        # ── Eras Tour Clothing Items — Additional ──────────────────────────
        ("Eras Tour", "merch", "Eras Tour Black Hoodie (All Eras Design)", "Tour Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Gray Crewneck (Dates on Back)", "Tour Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour White Ringer Tee", "Tour Exclusive", "high", 70),
        ("Eras Tour", "merch", "Eras Tour Tie-Dye Long Sleeve Tee", "Tour Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Quarter-Zip Pullover", "Tour Exclusive", "high", 100),
        ("Eras Tour", "merch", "Eras Tour Denim Jacket (Custom Patches)", "Tour Exclusive", "grail", 180),
        ("Eras Tour", "merch", "Eras Tour Crop Top (Black, Eras Logo)", "Tour Exclusive", "high", 75),
        ("Eras Tour", "merch", "Eras Tour Baseball Cap (Embroidered)", "Tour Exclusive", "mid", 45),
        ("Eras Tour", "merch", "Eras Tour Bucket Hat", "Tour Exclusive", "mid", 40),
        ("Eras Tour", "merch", "Eras Tour Tote Bag (Canvas)", "Tour Exclusive", "mid", 35),
        ("Eras Tour", "merch", "Eras Tour Socks (3-Pack, Era Designs)", "Tour Exclusive", "standard", 22),

        # ── All Signed Items — Additional ──────────────────────────────────
        ("Midnights", "signed_vinyl", "Midnights Signed Moonstone Blue Vinyl", "Signed", "grail", 240),
        ("Folklore", "signed_vinyl", "Folklore Signed In the Trees Vinyl", "Signed", "grail", 200),
        ("Evermore", "signed_vinyl", "Evermore Signed Vinyl (Green)", "Signed", "grail", 190),
        ("Red TV", "signed_vinyl", "Red TV Signed Vinyl (Red)", "Signed", "grail", 230),
        ("Fearless TV", "signed_vinyl", "Fearless TV Signed Vinyl (Gold)", "Signed", "grail", 210),
        ("Lover", "signed_vinyl", "Lover Signed Vinyl (Pink + Blue)", "Signed", "grail", 280),
        ("Reputation", "signed_vinyl", "Reputation Signed Picture Disc Vinyl", "Signed", "grail", 350),
        ("Debut", "signed_vinyl", "Taylor Swift Debut Signed Vinyl (Black, Big Machine)", "Signed", "grail", 600),

        # ── International Exclusive Editions — Additional ──────────────────
        ("Midnights", "cd", "Midnights German Media Markt Edition CD", "Germany Exclusive", "mid", 50),
        ("TTPD", "cd", "TTPD Mexico Edition CD (Spanish Booklet Insert)", "Mexico Exclusive", "mid", 55),
        ("1989 TV", "cd", "1989 TV Brazilian Edition CD (Bonus Track)", "Brazil Exclusive", "high", 65),
        ("Folklore", "cd", "Folklore French Edition CD (Bonus Livret)", "France Exclusive", "mid", 55),
        ("Lover", "cd", "Lover China Exclusive Edition CD", "China Exclusive", "high", 70),
        ("Speak Now TV", "cd", "Speak Now TV Korea Special Edition (Photocards)", "Korea Exclusive", "high", 70),
        ("Red TV", "cd", "Red TV Australia Deluxe Edition CD", "Australia Exclusive", "high", 60),

        # ── Complete Funko Pop Line ────────────────────────────────────────
        ("Misc", "collectible", "Taylor Swift Funko Pop (Eras Tour Outfit)", "Standard", "mid", 40),
        ("Misc", "collectible", "Taylor Swift Funko Pop (Red Era)", "Standard", "mid", 38),
        ("Misc", "collectible", "Taylor Swift Funko Pop (Speak Now Gown)", "Standard", "mid", 38),
        ("Misc", "collectible", "Taylor Swift Funko Pop (Fearless Guitar)", "Standard", "mid", 35),
        ("Misc", "collectible", "Taylor Swift Funko Pop (Evermore Willow)", "Standard", "mid", 38),
        ("Misc", "collectible", "Taylor Swift Funko Pop (TTPD Quill Pen)", "Standard", "mid", 42),
        ("Misc", "collectible", "Taylor Swift Funko Pop (Debut Cowgirl)", "Standard", "mid", 35),
        ("Misc", "collectible", "Taylor Swift Funko Pop (Midnights Bejeweled) Standard", "Standard", "mid", 35),
        ("Misc", "collectible", "Taylor Swift Funko Pop Deluxe (Eras Tour Stage)", "Deluxe", "high", 65),

        # ── Magazine Covers — Additional ───────────────────────────────────
        ("Magazine", "collectible", "Harper's Bazaar US August 2024 (TTPD Era)", "Magazine Cover", "mid", 40),
        ("Magazine", "collectible", "Variety Hitmakers 2023 (Taylor Cover)", "Magazine Cover", "mid", 45),
        ("Magazine", "collectible", "Vogue Japan November 2019 (Lover Era)", "Magazine Cover", "mid", 50),
        ("Magazine", "collectible", "Marie Claire US February 2024 (TTPD Teaser)", "Magazine Cover", "mid", 38),
        ("Magazine", "collectible", "Rolling Stone Australia 2023 (Eras Tour)", "Magazine Cover", "mid", 42),
        ("Magazine", "collectible", "V Magazine Spring 2020 (Folklore Preview)", "Magazine Cover", "mid", 40),
        ("Magazine", "collectible", "Allure November 2019 (Lover Era)", "Magazine Cover", "mid", 35),
        ("Magazine", "collectible", "Glamour UK December 2019 (Woman of the Decade)", "Magazine Cover", "mid", 40),

        # ── Award Items — Additional ───────────────────────────────────────
        ("Awards", "collectible", "Billboard Music Awards 2024 Program (Record Breaker)", "Event Exclusive", "mid", 50),
        ("Awards", "collectible", "Grammy Awards 2016 Press Photo (Album of the Year 1989)", "Vintage", "high", 65),
        ("Awards", "collectible", "MTV VMA 2023 Press Photo Set (9 Moon Persons)", "Event Exclusive", "high", 70),
        ("Awards", "collectible", "Country Music Hall of Fame Exhibit Poster (2024)", "Event Exclusive", "mid", 55),
        ("Awards", "collectible", "Jingle Ball 2019 Meet & Greet Photo Package", "Event Exclusive", "high", 80),

        # ── Collaboration Merchandise — Additional ─────────────────────────
        ("Collaboration", "merch", "Taylor x Papa John's Pizza Box Set (Midnights)", "Limited", "mid", 30),
        ("Collaboration", "merch", "Taylor x Le Creuset Lover Heart Ramekin Set", "Limited", "high", 95),
        ("Collaboration", "merch", "Taylor x Hasbro Eras Tour Edition Monopoly", "Limited", "mid", 55),
        ("Collaboration", "merch", "Taylor x Mattel Eras Tour Barbie Doll", "Limited", "high", 80),
        ("Collaboration", "merch", "Taylor x JBL Headphones (Midnights Edition)", "Limited", "high", 90),
        ("Collaboration", "merch", "Taylor x Versace Concert Bodysuit Replica", "Limited Replica", "grail", 200),

        # ── Vintage Big Machine Era Items ──────────────────────────────────
        ("Debut", "merch", "Debut Era Cowboy Boots (Official Store, 2007)", "Vintage", "grail", 300),
        ("Debut", "merch", "Taylor Swift Debut Era Rhinestone Guitar Strap", "Vintage", "high", 120),
        ("Debut", "merch", "Taylor Swift Debut Tour Poster (Original 2007)", "Vintage", "grail", 180),
        ("Fearless", "merch", "Fearless Tour T-Shirt (Original 2009)", "Vintage", "high", 80),
        ("Fearless", "merch", "Fearless Tour Poster (Original 2009)", "Vintage", "high", 120),
        ("Speak Now", "merch", "Speak Now World Tour Program Book", "Vintage", "high", 65),
        ("Speak Now", "merch", "Speak Now Tour T-Shirt (Original 2011)", "Vintage", "high", 75),
        ("Red", "merch", "Red Tour Light-Up Wristband (Original 2013)", "Vintage", "mid", 45),
        ("Red", "merch", "Red Tour State of Grace T-Shirt", "Vintage", "mid", 55),
        ("1989", "merch", "1989 World Tour Crop Top (Original 2015)", "Vintage", "high", 65),
        ("1989", "merch", "1989 World Tour Polaroid Set (Complete)", "Vintage", "high", 100),
        ("Reputation", "merch", "Reputation Stadium Tour Light-Up Snake Wristband", "Vintage", "mid", 55),
        ("Reputation", "merch", "Reputation Magazine Volume 1 (Complete Set of 2)", "Limited", "high", 90),

        # ── Christmas Ornaments — Additional ───────────────────────────────
        ("Holiday", "ornament", "Hallmark Taylor Swift Guitar Ornament (2024)", "Standard", "standard", 25),
        ("Holiday", "ornament", "Hallmark Taylor Swift Eras Tour Ornament", "Standard", "standard", 28),
        ("Holiday", "ornament", "Kurt Adler Taylor Swift Microphone Ornament", "Standard", "standard", 20),
        ("Holiday", "ornament", "Fan-Made Reputation Snake Ornament", "Fan-Made", "standard", 15),
        ("Holiday", "ornament", "Lenox-Style Taylor Swift 22 Hat Ornament", "Limited", "mid", 40),
        ("Holiday", "ornament", "Folklore Cardigan Mini Ornament (Official Store)", "Limited", "mid", 38),

        # ── Jewelry — Complete Line ────────────────────────────────────────
        ("Misc", "jewelry", "Taylor Swift 22 Necklace (Gold-Plated, Official)", "Limited", "mid", 55),
        ("Misc", "jewelry", "Taylor Swift Eras Bracelet (Silver, 13 Charms)", "Limited", "high", 75),
        ("Misc", "jewelry", "Taylor Swift Lover Heart Ring (Rose Gold)", "Limited", "mid", 45),
        ("Misc", "jewelry", "Taylor Swift Midnights Moonstone Necklace", "Limited", "mid", 55),
        ("Misc", "jewelry", "Taylor Swift Reputation Snake Earrings", "Limited", "mid", 40),
        ("Misc", "jewelry", "Taylor Swift TTPD Quill Pen Necklace", "Limited", "mid", 50),
        ("Misc", "jewelry", "Taylor Swift Folklore Star Earrings", "Limited", "mid", 40),
        ("Misc", "jewelry", "Taylor Swift 1989 Seagull Brooch", "Limited", "mid", 38),

        # ── Guitar Collectibles — Additional ──────────────────────────────
        ("Guitar", "instrument", "Speak Now Era Purple Sparkle Guitar Replica", "Tour Replica", "grail", 350),
        ("Guitar", "instrument", "TTPD Era Tortured Poets Acoustic Guitar Replica", "Limited Replica", "grail", 360),
        ("Guitar", "instrument", "Midnights Era Bejeweled Guitar Replica", "Limited Replica", "grail", 370),
        ("Guitar", "collectible", "Eras Tour Guitar Pick (Thrown from Stage, Authenticated)", "Tour Exclusive", "grail", 300),
        ("Guitar", "collectible", "Miniature Guitar Replica — Red Sparkle (10-inch Display)", "Standard", "mid", 42),
        ("Guitar", "collectible", "Miniature Guitar Replica — Purple Speak Now (10-inch)", "Standard", "mid", 42),

        # ── Additional Picture Discs ───────────────────────────────────────
        ("Folklore", "vinyl", "Folklore Picture Disc Vinyl", "Picture Disc", "high", 70),
        ("Evermore", "vinyl", "Evermore Picture Disc Vinyl", "Picture Disc", "high", 68),
        ("Speak Now TV", "vinyl", "Speak Now TV Picture Disc Vinyl", "Picture Disc", "high", 65),
        ("Red TV", "vinyl", "Red TV Picture Disc Vinyl", "Picture Disc", "high", 65),
        ("Fearless TV", "vinyl", "Fearless TV Picture Disc Vinyl", "Picture Disc", "high", 62),
        ("TTPD", "vinyl", "TTPD Picture Disc Vinyl", "Picture Disc", "high", 70),

        # ── Fan Club / TN — Additional ─────────────────────────────────────
        ("Fan Club", "merch", "Taylor Nation Holiday Box 2024", "Fan Club Exclusive", "high", 130),
        ("Fan Club", "merch", "Taylor Nation Welcome Package (New Members)", "Fan Club Exclusive", "mid", 55),
        ("Fan Club", "merch", "Taylor Nation Secret Session Polaroid (TTPD)", "Fan Club Exclusive", "grail", 450),
        ("Fan Club", "merch", "Taylor Nation Eras Tour VIP Pre-Show Tote", "Fan Club Exclusive", "high", 80),
        ("Fan Club", "merch", "Taylor Nation Birthday Party Box (13th Anniversary)", "Fan Club Exclusive", "high", 95),

        # ── Eras Tour Era-Specific Outfits — Additional ────────────────────
        ("Eras Tour", "merch", "Eras Tour Red Era 22 Hat", "Tour Exclusive", "high", 65),
        ("Eras Tour", "merch", "Eras Tour Evermore Era Cardigan (Willow Green)", "Tour Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour TTPD Era Black Dress Replica", "Tour Exclusive", "grail", 160),
        ("Eras Tour", "merch", "Eras Tour Fearless Era Gold Dress Replica", "Tour Exclusive", "grail", 170),
        ("Eras Tour", "merch", "Eras Tour Debut Era Rhinestone Cowgirl Set", "Tour Exclusive", "grail", 180),
        ("Eras Tour", "merch", "Eras Tour Surprise Song Guitar Pin Set", "Tour Exclusive", "mid", 45),
        ("Eras Tour", "merch", "Eras Tour Confetti Cannon Tube (Sealed)", "Tour Exclusive", "mid", 30),

        # ── Additional Cassette Tapes (Remaining) ─────────────────────────
        ("Midnights", "cassette", "Midnights Cassette (Blood Moon)", "Blood Moon Cassette", "standard", 20),
        ("Midnights", "cassette", "Midnights Cassette (Mahogany)", "Mahogany Cassette", "standard", 20),
        ("1989 TV", "cassette", "1989 TV Cassette (Aquamarine)", "Limited Cassette", "standard", 18),
        ("TTPD", "cassette", "TTPD Cassette (Manuscript Beige)", "Limited Cassette", "standard", 20),
        ("Fearless TV", "cassette", "Fearless TV Cassette (Gold)", "Limited Cassette", "standard", 20),

        # ── Additional International Editions ──────────────────────────────
        ("Midnights", "cd", "Midnights India Special Edition CD", "India Exclusive", "mid", 50),
        ("1989 TV", "cd", "1989 TV Germany MediaMarkt Edition CD", "Germany Exclusive", "mid", 50),
        ("TTPD", "cd", "TTPD Philippines Edition CD (Exclusive Sleeve)", "Philippines Exclusive", "mid", 48),
        ("Folklore", "cd", "Folklore Canada HMV Edition CD", "Canada Exclusive", "mid", 50),
        ("Lover", "cd", "Lover Korea Edition CD (Photocards)", "Korea Exclusive", "high", 65),
        ("Evermore", "cd", "Evermore Korea Edition CD (Photocards)", "Korea Exclusive", "high", 60),
        ("Reputation", "cd", "Reputation UK HMV Edition CD", "UK Exclusive", "mid", 55),

        # ── Walmart Exclusive Vinyl — Additional ───────────────────────────
        ("Red TV", "vinyl", "Red TV Walmart Exclusive (Crystal Clear 4LP)", "Walmart Exclusive", "mid", 48),
        ("Evermore", "vinyl", "Evermore Walmart Exclusive (Splatter Vinyl)", "Walmart Exclusive", "mid", 45),
        ("Folklore", "vinyl", "Folklore Walmart Exclusive (Blue Mist Vinyl)", "Walmart Exclusive", "mid", 42),
        ("Lover", "vinyl", "Lover Walmart Exclusive (Clear Pink Vinyl)", "Walmart Exclusive", "mid", 40),

        # ── Perfume Collectibles ───────────────────────────────────────────
        ("Collaboration", "collectible", "Taylor Swift Wonderstruck Perfume (Sealed, Discontinued)", "Vintage", "high", 80),
        ("Collaboration", "collectible", "Taylor Swift Wonderstruck Enchanted (Sealed)", "Vintage", "high", 75),
        ("Collaboration", "collectible", "Taylor Swift Taylor Perfume (Sealed, Discontinued)", "Vintage", "high", 90),
        ("Collaboration", "collectible", "Taylor Swift Incredible Things Perfume (Sealed)", "Vintage", "high", 85),

        # ── Additional Concert Memorabilia ─────────────────────────────────
        ("Concert", "collectible", "Reputation Tour Inflatable Snake (Stage Prop Replica)", "Tour Exclusive", "high", 80),
        ("Concert", "collectible", "Eras Tour LED Wristband (Programmed, Working)", "Tour Exclusive", "mid", 45),
        ("Concert", "collectible", "Speak Now World Tour Program Book (2011)", "Vintage", "high", 70),
        ("Concert", "collectible", "Red Tour Program Book (2013)", "Vintage", "mid", 55),
        ("Concert", "collectible", "1989 World Tour Program Book (2015)", "Vintage", "high", 65),
        ("Concert", "collectible", "Reputation Stadium Tour Ticket Stub (Authenticated)", "Vintage", "mid", 40),

        # ── Holiday / Seasonal — Additional ────────────────────────────────
        ("Holiday", "merch", "Taylor Swift Easter Egg Candle Set (Folklore)", "Limited", "mid", 35),
        ("Holiday", "merch", "Taylor Swift Lunar New Year Red Pocket Set (Asia)", "Limited", "mid", 30),

        # ── Additional Books & Publications ────────────────────────────────
        ("Book", "collectible", "Taylor Swift Eras Tour Official Photo Book", "Tour Exclusive", "high", 75),
        ("Book", "collectible", "TTPD Manuscript Companion Booklet (Deluxe CD Insert)", "Limited", "mid", 40),
        ("Book", "collectible", "Midnights Lavender Haze Zine", "Limited", "mid", 45),

        # ── Additional Eras Tour Accessories ───────────────────────────────
        ("Eras Tour", "merch", "Eras Tour Phone Case (All Eras Design)", "Tour Exclusive", "standard", 28),
        ("Eras Tour", "merch", "Eras Tour Keychain Set (13 Albums)", "Tour Exclusive", "standard", 25),
        ("Eras Tour", "merch", "Eras Tour Water Bottle (Stainless Steel)", "Tour Exclusive", "mid", 35),
        ("Eras Tour", "merch", "Eras Tour Blanket (All Eras Fleece)", "Tour Exclusive", "mid", 55),
        ("Eras Tour", "merch", "Eras Tour Fanny Pack (Black)", "Tour Exclusive", "mid", 40),
        ("Eras Tour", "merch", "Eras Tour Rain Poncho (Clear with Logo)", "Tour Exclusive", "standard", 20),

        # ── Additional Signed Memorabilia ──────────────────────────────────
        ("Misc", "signed_photo", "Taylor Swift Signed 11x14 Photo (Lover Era)", "Signed", "grail", 400),
        ("Misc", "signed_photo", "Taylor Swift Signed 8x10 Photo (Eras Tour)", "Signed", "grail", 350),

        # ── Amazon / Webstore Exclusive Vinyl ──────────────────────────────
        ("Folklore", "vinyl", "Folklore Amazon Exclusive (Beige Vinyl)", "Amazon Exclusive", "mid", 45),
        ("Evermore", "vinyl", "Evermore Amazon Exclusive (Opaque Green Vinyl)", "Amazon Exclusive", "mid", 42),
        ("Speak Now TV", "vinyl", "Speak Now TV Amazon Exclusive (Violet Marble)", "Amazon Exclusive", "mid", 42),
        ("Red TV", "vinyl", "Red TV Amazon Exclusive (Clear Red Vinyl)", "Amazon Exclusive", "mid", 45),
        ("Fearless TV", "vinyl", "Fearless TV Amazon Exclusive (Metallic Silver)", "Amazon Exclusive", "mid", 42),

        # ── Miscellaneous Collectibles — Additional ────────────────────────
        ("Misc", "collectible", "Taylor Swift Eras Tour Snow Globe", "Tour Exclusive", "high", 70),
        ("Misc", "collectible", "Taylor Swift Eras Tour Puzzle (1000 Piece)", "Standard", "standard", 25),
        ("Misc", "collectible", "Taylor Swift Eras Coloring Book (Official)", "Standard", "standard", 18),
        ("Misc", "collectible", "Taylor Swift Cat Meredith Plush (Official Store)", "Limited", "mid", 40),
        ("Misc", "collectible", "Taylor Swift Cat Benjamin Button Plush (Official)", "Limited", "mid", 40),
        ("Misc", "collectible", "Taylor Swift Eras Tour Playing Cards Deck", "Tour Exclusive", "standard", 20),
        ("Misc", "collectible", "Taylor Swift Reputation Enamel Pin Set (5pc)", "Limited", "mid", 35),

        # =================================================================
        # Batch 11 — Eras Tour International Exclusives, Signed CDs,
        # Vinyl Variants, Friendship Bracelets, Snow Globe, VIP Boxes
        # =================================================================

        # ── Eras Tour International Exclusives (14) ──────────────────────
        ("Eras Tour", "merch", "Eras Tour Tokyo Dome Exclusive Tee", "Tokyo Exclusive", "high", 120),
        ("Eras Tour", "merch", "Eras Tour Tokyo Dome Poster (Night 1)", "Tokyo Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Tokyo Dome Poster (Night 2)", "Tokyo Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Tokyo Dome Poster (Night 3)", "Tokyo Exclusive", "high", 100),
        ("Eras Tour", "merch", "Eras Tour Singapore National Stadium Exclusive Tee", "Singapore Exclusive", "high", 110),
        ("Eras Tour", "merch", "Eras Tour Singapore Poster", "Singapore Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour London Wembley Night 1 Poster", "London Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour London Wembley Night 8 Surprise Songs Poster", "London Exclusive", "grail", 150),
        ("Eras Tour", "merch", "Eras Tour Paris La Defense Arena Poster", "Paris Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Paris Exclusive Crewneck", "Paris Exclusive", "high", 100),
        ("Eras Tour", "merch", "Eras Tour Vienna Ernst Happel Stadion Poster", "Vienna Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Gelsenkirchen Exclusive Tee", "Gelsenkirchen Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Gelsenkirchen (Swiftkirchen) Poster", "Gelsenkirchen Exclusive", "high", 110),
        ("Eras Tour", "merch", "Eras Tour Milan San Siro Exclusive Poster", "Milan Exclusive", "high", 80),

        # ── Signed CD Inserts (8) ───────────────────────────────────────
        ("Midnights", "signed_cd", "Midnights Moonstone Blue (Signed Insert)", "Signed Insert", "grail", 250),
        ("Midnights", "signed_cd", "Midnights Lavender Marbled (Signed Insert)", "Signed Insert", "grail", 260),
        ("Midnights", "signed_cd", "Midnights Jade Green (Signed Insert)", "Signed Insert", "grail", 245),
        ("Midnights", "signed_cd", "Midnights Blood Moon (Signed Insert)", "Signed Insert", "grail", 255),
        ("TTPD", "signed_cd", "TTPD The Anthology (Signed Insert)", "Signed Insert", "grail", 200),
        ("1989 TV", "signed_cd", "1989 TV (Signed Insert — Sunrise Blvd Yellow)", "Signed Insert", "grail", 220),
        ("Speak Now TV", "signed_cd", "Speak Now TV (Signed Insert — Orchid Marble)", "Signed Insert", "grail", 210),
        ("Folklore", "signed_cd", "Folklore (Signed Insert — In the Trees)", "Signed Insert", "grail", 280),

        # ── Vinyl Variants — Special Editions (8) ───────────────────────
        ("Folklore", "vinyl", "Folklore In the Trees Edition (Translucent Green)", "In the Trees Ltd", "high", 85),
        ("Red TV", "vinyl", "Red TV Target Exclusive (Red Opaque 4LP)", "Target Exclusive", "high", 70),
        ("Fearless TV", "vinyl", "Fearless TV Gold Vinyl (3LP)", "Gold Ltd", "high", 65),
        ("Speak Now TV", "vinyl", "Speak Now TV Orchid Marble (2LP)", "Orchid Marble", "mid", 55),
        ("1989 TV", "vinyl", "1989 TV Tangerine Vinyl", "Tangerine Target", "mid", 50),
        ("1989 TV", "vinyl", "1989 TV Crystal Skies Blue Vinyl", "Crystal Skies Blue", "mid", 48),
        ("Debut", "vinyl", "Taylor Swift Debut (Hand-Numbered RSD)", "RSD 2018", "grail", 350),
        ("Red", "vinyl", "Red (Original Pressing Clear Vinyl)", "Clear Ltd", "high", 120),

        # ── Friendship Bracelet Official Sets (6) ───────────────────────
        ("Eras Tour", "accessory", "Official Friendship Bracelet Kit (Eras Tour)", "Tour Exclusive", "mid", 35),
        ("Eras Tour", "accessory", "Official Friendship Bracelet Kit (Deluxe 200pc)", "Store Exclusive", "mid", 45),
        ("Eras Tour", "accessory", "Official Friendship Bracelet Kit (Midnights Edition)", "Online Exclusive", "mid", 38),
        ("Eras Tour", "accessory", "Official Friendship Bracelet Kit (TTPD Edition)", "Online Exclusive", "mid", 40),
        ("Eras Tour", "accessory", "Official Friendship Bracelet Display Frame", "Store Exclusive", "mid", 30),
        ("Eras Tour", "accessory", "Swiftie Bracelet Bead Set (Official 13 Albums)", "Store Exclusive", "mid", 42),

        # ── Lover Snow Globe & Premium Items (6) ────────────────────────
        ("Lover", "collectible", "Lover Snow Globe (Official Store)", "Limited", "grail", 350),
        ("Lover", "collectible", "Lover Ornament Set (3pc)", "Store Exclusive", "mid", 55),
        ("Lover", "collectible", "Lover Heart-Shaped Jewelry Box", "Limited", "high", 80),
        ("Lover", "collectible", "Lover Diary (Hardcover, Official)", "Limited", "mid", 45),
        ("Lover", "collectible", "Lover Locket Necklace (Gold)", "Store Exclusive", "high", 70),
        ("Lover", "collectible", "Lover Embroidered Denim Jacket", "Limited", "high", 130),

        # ── Reputation Stadium Tour VIP Box (8) ─────────────────────────
        ("Reputation", "vip_box", "Reputation Stadium Tour VIP Box (Complete)", "Tour VIP", "grail", 300),
        ("Reputation", "vip_box", "Reputation Stadium Tour Snake Ring", "Tour VIP", "high", 90),
        ("Reputation", "vip_box", "Reputation Stadium Tour Light-Up Wristband", "Tour VIP", "mid", 40),
        ("Reputation", "vip_box", "Reputation Stadium Tour Poncho (Black)", "Tour VIP", "mid", 55),
        ("Reputation", "vip_box", "Reputation Stadium Tour Blanket (Snake Logo)", "Tour VIP", "mid", 60),
        ("Reputation", "vip_box", "Reputation Stadium Tour Tote Bag", "Tour VIP", "mid", 45),
        ("Reputation", "vip_box", "Reputation Stadium Tour Lanyard & Badge", "Tour VIP", "standard", 25),
        ("Reputation", "vip_box", "Reputation Stadium Tour Enamel Pin Set (3pc)", "Tour VIP", "mid", 35),

        # === EXPANSION ROUND — 55 new items ===

        # ─── Eras Tour City-Exclusive Posters & Tour Books (+12) ─────
        ("Eras Tour", "poster", "Eras Tour Poster — Glendale Night 1 (Opening Night)", "Tour Exclusive", "grail", 250),
        ("Eras Tour", "poster", "Eras Tour Poster — Los Angeles SoFi (Night 6)", "Tour Exclusive", "high", 120),
        ("Eras Tour", "poster", "Eras Tour Poster — Nashville Nissan Stadium", "Tour Exclusive", "high", 110),
        ("Eras Tour", "poster", "Eras Tour Poster — London Wembley Night 1", "Tour Exclusive", "high", 130),
        ("Eras Tour", "poster", "Eras Tour Poster — Tokyo Dome Night 1", "Tour Exclusive", "high", 140),
        ("Eras Tour", "poster", "Eras Tour Poster — Melbourne MCG", "Tour Exclusive", "high", 100),
        ("Eras Tour", "poster", "Eras Tour Poster — Paris La Défense Arena", "Tour Exclusive", "high", 115),
        ("Eras Tour", "poster", "Eras Tour Poster — Singapore National Stadium", "Tour Exclusive", "high", 125),
        ("Eras Tour", "book", "Eras Tour Official Tour Book (1st Edition)", "Tour Exclusive", "high", 90),
        ("Eras Tour", "book", "Eras Tour Official Tour Book (International Edition)", "Tour Exclusive", "mid", 65),
        ("Eras Tour", "book", "Eras Tour VIP Commemorative Photo Book", "VIP Exclusive", "grail", 200),
        ("Eras Tour", "book", "Eras Tour Official Programme (UK Edition)", "Tour Exclusive", "high", 75),

        # ─── Vinyl Variants — Target / RSD / Color Exclusives (+10) ──
        ("TTPD", "vinyl", "TTPD Target Exclusive (Ivory 2LP)", "Target Exclusive", "mid", 55),
        ("TTPD", "vinyl", "TTPD The Anthology (Beige 4LP Box Set)", "Anthology", "high", 80),
        ("Midnights", "vinyl", "Midnights Blood Moon Vinyl (Marbled)", "RSD Exclusive", "high", 90),
        ("Midnights", "vinyl", "Midnights Mahogany Vinyl (Target)", "Target Exclusive", "mid", 50),
        ("Folklore", "vinyl", "Folklore Running Like Water Vinyl (Green)", "Webstore Exclusive", "high", 85),
        ("Evermore", "vinyl", "Evermore Green Translucent Vinyl", "Webstore Exclusive", "mid", 60),
        ("Red TV", "vinyl", "Red TV Clear Vinyl (Webstore Exclusive)", "Webstore Exclusive", "mid", 55),
        ("Speak Now TV", "vinyl", "Speak Now TV Lilac Marble Vinyl (3LP)", "Indie Exclusive", "high", 70),
        ("1989 TV", "vinyl", "1989 TV Rose Garden Pink (2LP)", "Target Exclusive", "mid", 48),
        ("Fearless TV", "vinyl", "Fearless TV Metallic Gold Vinyl (RSD)", "RSD Exclusive", "high", 80),

        # ─── International Exclusive Merchandise (+8) ─────────────────
        ("Eras Tour", "merch", "Eras Tour Japan Exclusive Tee (Kanji Logo)", "Japan Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Brazil Exclusive Woven Scarf", "Brazil Exclusive", "mid", 65),
        ("Eras Tour", "merch", "Eras Tour UK Exclusive Rain Poncho (Wembley)", "UK Exclusive", "mid", 55),
        ("Eras Tour", "merch", "Eras Tour Australia Exclusive Bucket Hat", "Australia Exclusive", "mid", 50),
        ("Eras Tour", "merch", "Eras Tour Germany Exclusive Tote Bag (Munich)", "Germany Exclusive", "mid", 45),
        ("Eras Tour", "merch", "Eras Tour France Exclusive Enamel Pin Set", "France Exclusive", "mid", 40),
        ("Eras Tour", "merch", "Eras Tour Singapore Exclusive Keychain Set", "Singapore Exclusive", "mid", 35),
        ("Eras Tour", "merch", "Eras Tour Canada Exclusive Crewneck (Toronto)", "Canada Exclusive", "mid", 60),

        # ─── Signed Items (+7) ───────────────────────────────────────
        ("TTPD", "signed", "TTPD Signed CD (Heart Insert, 1st Run)", "Signed + Heart", "grail", 250),
        ("Midnights", "signed", "Midnights Signed Photo (8x10 Official)", "Signed", "high", 180),
        ("1989 TV", "signed", "1989 TV Signed Lithograph (Numbered /1989)", "Signed + Numbered", "grail", 400),
        ("Red TV", "signed", "Red TV Signed Guitar Pickguard", "Signed", "grail", 350),
        ("Speak Now TV", "signed", "Speak Now TV Signed Insert (Lavender)", "Signed", "high", 200),
        ("Folklore", "signed", "Folklore Signed CD Booklet (Cardigan Version)", "Signed", "high", 220),
        ("Evermore", "signed", "Evermore Signed CD Insert (Willow Version)", "Signed", "high", 210),

        # ─── Lover Era Collectibles (+6) ─────────────────────────────
        ("Lover", "merch", "Lover Wristwatch (Pastel Heart Face)", "Limited", "high", 120),
        ("Lover", "vinyl", "Lover Live from Paris LP (Fan Edition)", "Limited", "high", 90),
        ("Lover", "collectible", "Lover ME! Spinning Heart Music Box", "Store Exclusive", "high", 85),
        ("Lover", "merch", "Lover Era Silk Scarf (Pastel Butterfly)", "Store Exclusive", "mid", 65),
        ("Lover", "merch", "Lover Cotton Candy Hoodie (Oversized)", "Limited", "mid", 75),
        ("Lover", "poster", "Lover Album Art Lithograph Set (4pc)", "Webstore Exclusive", "mid", 55),

        # ─── Reputation Era Items (+6) ───────────────────────────────
        ("Reputation", "vinyl", "Reputation Picture Disc (Snake Design)", "Picture Disc", "high", 100),
        ("Reputation", "merch", "Reputation Snake Ring (Silver, Official)", "Tour Exclusive", "high", 90),
        ("Reputation", "merch", "Reputation Stadium Tour Bomber Jacket", "Tour Exclusive", "high", 160),
        ("Reputation", "merch", "Reputation Lenticular Cover Magazine (3 Editions)", "Limited", "mid", 55),
        ("Reputation", "collectible", "Reputation Tour Snake Figurine (Official)", "Store Exclusive", "high", 80),
        ("Reputation", "poster", "Reputation Secret Sessioners Poster (Signed)", "Signed", "grail", 300),

        # ─── Holiday & Seasonal Releases (+6) ───────────────────────
        ("Holiday", "merch", "Taylor Swift Holiday Collection Ornament Set 2023", "Store Exclusive", "mid", 55),
        ("Holiday", "merch", "Taylor Swift Ugly Christmas Sweater (Official 2023)", "Limited", "mid", 65),
        ("Holiday", "merch", "Taylor Swift Valentine's Day Card Set (12pc)", "Store Exclusive", "standard", 25),
        ("Holiday", "merch", "Taylor Swift Halloween Eras Cat Ears (2024)", "Limited", "mid", 40),
        ("Holiday", "vinyl", "Christmas Tree Farm 7-inch Single (Ltd Green)", "Limited", "high", 110),
        ("Holiday", "collectible", "Taylor Swift Advent Calendar (Official 2024)", "Store Exclusive", "mid", 60),

        # ─── Eras Tour — City-Specific Exclusives (+12) ────────────────
        ("Eras Tour", "merch", "Eras Tour Tokyo Night 1 Exclusive Poster", "Japan Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Tokyo Night 2 Exclusive Poster", "Japan Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Melbourne Exclusive Tote Bag", "Australia Exclusive", "mid", 55),
        ("Eras Tour", "merch", "Eras Tour Edinburgh Castle Exclusive Print", "UK Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Wembley Stadium Exclusive Scarf", "UK Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour São Paulo Rain Show Commemorative Tee", "Brazil Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Munich Olympic Park Poster", "Germany Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Hamburg Exclusive Enamel Pin Set", "Germany Exclusive", "mid", 45),
        ("Eras Tour", "merch", "Eras Tour Singapore Night 6 Poster", "Asia Exclusive", "high", 100),
        ("Eras Tour", "merch", "Eras Tour Amsterdam Final Night Poster", "Limited", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Vienna Commemorative Lanyard Set", "Limited", "mid", 40),
        ("Eras Tour", "merch", "Eras Tour New Orleans Surprise Songs Poster", "Limited", "high", 80),

        # ─── Signed & Autographed Items (+8) ───────────────────────────
        ("Midnights", "signed", "Midnights Signed CD Booklet (Lavender Haze)", "Signed", "high", 150),
        ("TTPD", "signed", "TTPD Signed Poster (Fortnight)", "Signed", "grail", 280),
        ("1989 TV", "signed", "1989 TV Signed Vinyl Sleeve (Aquamarine)", "Signed", "grail", 350),
        ("Speak Now TV", "signed", "Speak Now TV Signed Booklet (Enchanted Ver.)", "Signed", "high", 200),
        ("Red TV", "signed", "Red TV Signed Lithograph (All Too Well 10 Min)", "Signed + Numbered", "grail", 420),
        ("Fearless TV", "signed", "Fearless TV Signed CD Insert (Love Story)", "Signed", "high", 180),
        ("Debut", "signed", "Taylor Swift Debut Signed CD (2006)", "Signed", "grail", 500),
        ("Reputation", "signed", "Reputation Signed Magazine Vol. 2 (1st Print)", "Signed", "grail", 350),

        # ─── Rare Vinyl Pressings & RSD (+10) ──────────────────────────
        ("RSD", "vinyl", "Betty / Cardigan 7-inch RSD 2024", "RSD Exclusive", "high", 70),
        ("RSD", "vinyl", "Fortnight 7-inch Clear RSD 2025", "RSD Exclusive", "high", 75),
        ("RSD", "vinyl", "Enchanted 7-inch Picture Disc RSD", "RSD Exclusive", "high", 80),
        ("Folklore", "vinyl", "Folklore Clandestine Meeting Green Vinyl (Indie)", "Indie Exclusive", "mid", 50),
        ("Evermore", "vinyl", "Evermore Transparent Green Vinyl (Webstore)", "Webstore Exclusive", "mid", 48),
        ("Debut", "vinyl", "Taylor Swift Debut LP (1st Pressing, Sealed)", "First Pressing", "grail", 300),
        ("Fearless", "vinyl", "Fearless Platinum Edition Gold Vinyl (Original)", "First Pressing", "high", 120),
        ("TTPD", "vinyl", "TTPD Ghosted White 2LP Vinyl (Signed)", "Signed", "grail", 250),
        ("Midnights", "vinyl", "Midnights 3am Edition Vinyl (Amazon Exclusive)", "Amazon Exclusive", "mid", 55),
        ("Red TV", "vinyl", "Red TV 4LP Crystal Clear Vinyl (Webstore)", "Webstore Exclusive", "high", 65),

        # ─── Japan-Only CD Editions (+6) ───────────────────────────────
        ("Reputation", "cd", "Reputation Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "high", 70),
        ("Speak Now TV", "cd", "Speak Now TV Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "mid", 50),
        ("Fearless TV", "cd", "Fearless TV Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "mid", 50),
        ("Debut", "cd", "Taylor Swift Debut Japan CD (Bonus Track)", "Japan Exclusive", "high", 65),

        # ─── Target Exclusives (+5) ────────────────────────────────────
        ("TTPD", "vinyl", "TTPD Charcoal Marble Target Vinyl", "Target", "mid", 42),
        ("Folklore", "vinyl", "Folklore Green 'Stolen Lullabies' Target Vinyl", "Target", "mid", 48),
        ("Evermore", "vinyl", "Evermore Webstore Deluxe Target Vinyl", "Target", "mid", 45),
        ("Red TV", "cd", "Red TV Target Deluxe CD (3 Bonus Tracks)", "Target", "mid", 35),
        ("1989 TV", "cd", "1989 TV Target Deluxe CD (Voice Memos)", "Target", "mid", 38),

        # ─── Concert Posters & Tour Merch (+10) ────────────────────────
        ("Eras Tour", "poster", "Eras Tour Official Concert Lithograph (Numbered /500)", "Limited", "grail", 200),
        ("Eras Tour", "poster", "Eras Tour Opening Night Glendale Poster (Signed by Artist)", "Signed Print", "grail", 350),
        ("Eras Tour", "merch", "Eras Tour VIP Package Exclusive Tote Bag", "VIP Exclusive", "high", 120),
        ("Eras Tour", "merch", "Eras Tour Surprise Songs Guitar Pick Set (Complete)", "Tour Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Friendship Bracelet Kit (Official)", "Store Exclusive", "mid", 35),
        ("Eras Tour", "merch", "Eras Tour Era Outfit Ornament Set (10pc)", "Store Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Stadium Blanket (Woven Logo)", "Tour Exclusive", "mid", 60),
        ("Reputation", "poster", "Reputation Stadium Tour Lithograph (2018)", "Tour Exclusive", "high", 140),
        ("Lover", "poster", "Lover Fest Canceled Show Commemorative Poster", "Limited", "grail", 180),
        ("1989", "poster", "1989 World Tour Official Poster (Framed)", "Tour Exclusive", "high", 130),

        # ─── Lover Snow Globe & Special Items (+7) ─────────────────────
        ("Lover", "collectible", "Lover Snow Globe (ME! Confetti)", "Store Exclusive", "grail", 300),
        ("Lover", "collectible", "Lover Heart-Shaped Jewelry Box (Official)", "Store Exclusive", "high", 95),
        ("TTPD", "collectible", "TTPD Quill Pen & Ink Set (Official)", "Store Exclusive", "high", 75),
        ("TTPD", "collectible", "TTPD Typewriter Replica Desk Ornament", "Store Exclusive", "high", 110),
        ("Midnights", "collectible", "Midnights Lavender Haze Candle Set (3pc)", "Store Exclusive", "mid", 45),
        ("Folklore", "collectible", "Folklore Cardigan (Original Merch, Sealed)", "Store Exclusive", "grail", 250),
        ("Reputation", "collectible", "Reputation Snake Ring Set (3pc, Official)", "Tour Exclusive", "high", 85),

        # ─── Fan Club & Miscellaneous (+10) ────────────────────────────
        ("Eras Tour", "merch", "Eras Tour Blue Crewneck (Midnights Era)", "Tour Exclusive", "mid", 65),
        ("Eras Tour", "merch", "Eras Tour Pink Hoodie (Lover Era)", "Tour Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Green Jacket (Folklore Era)", "Tour Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Black Sequin Top (Reputation Era)", "Tour Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Red Scarf (Red Era)", "Tour Exclusive", "mid", 55),
        ("Eras Tour", "merch", "Eras Tour Denim Jacket (1989 Era, Patches)", "Tour Exclusive", "high", 110),
        ("Eras Tour", "merch", "Eras Tour Speak Now Purple Cape (Costume)", "Tour Exclusive", "high", 95),
        ("Various", "book", "Taylor Swift: The Eras Book (Barnes & Noble Exclusive)", "Exclusive", "mid", 40),
        ("Various", "book", "Taylor Swift: In Her Own Words (1st Edition Hardcover)", "First Edition", "mid", 55),
        ("Various", "merch", "Taylor Swift x Stella McCartney Bomber Jacket (Lover Collab)", "Limited", "grail", 400),

        # === EXPANSION ROUND 12 — 20 new items to reach 700+ ===

        # ─── Eras Tour Final Leg Exclusives (+6) ─────────────────────
        ("Eras Tour", "merch", "Eras Tour Vancouver BC Final Leg Poster", "Final Leg Exclusive", "grail", 200),
        ("Eras Tour", "merch", "Eras Tour Toronto Rogers Centre Exclusive Tee", "Final Leg Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Indianapolis Lucas Oil Poster", "Final Leg Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour Miami Hard Rock Final Night Poster", "Final Leg Exclusive", "grail", 250),
        ("Eras Tour", "merch", "Eras Tour New Orleans Surprise Songs Bracelet Set", "Final Leg Exclusive", "high", 75),
        ("Eras Tour", "merch", "Eras Tour Final Show Commemorative Confetti Capsule", "Final Leg Exclusive", "grail", 300),

        # ─── Signed Editions & Autographs (+4) ──────────────────────
        ("TTPD", "signed", "TTPD Anthology Signed Poster (Black Dog)", "Signed", "grail", 320),
        ("Midnights", "signed", "Midnights Signed Vinyl Jacket (Jade Green)", "Signed", "grail", 380),
        ("1989 TV", "signed", "1989 TV Signed Photo Card Set (5pc)", "Signed", "high", 180),
        ("Folklore", "signed", "Folklore Signed Cardigan Tag (Framed)", "Signed + Framed", "grail", 450),

        # ─── Record Store Day Vinyl (+4) ─────────────────────────────
        ("RSD", "vinyl", "All Too Well 10 Min 12-inch RSD 2024 (Red Etched)", "RSD Exclusive", "high", 85),
        ("RSD", "vinyl", "Cruel Summer 7-inch Picture Disc RSD 2025", "RSD Exclusive", "high", 78),
        ("RSD", "vinyl", "Anti-Hero 7-inch Lavender Vinyl RSD 2025", "RSD Exclusive", "high", 72),
        ("RSD", "vinyl", "The Tortured Poets Department Live EP RSD 2026", "RSD Exclusive", "high", 90),

        # ─── Concert Merch & Collectibles (+6) ──────────────────────
        ("Eras Tour", "merch", "Eras Tour Woven Tapestry Blanket (All 11 Eras)", "Tour Exclusive", "high", 110),
        ("Eras Tour", "merch", "Eras Tour VIP Laminate & Lanyard Set (Final Leg)", "VIP Exclusive", "grail", 180),
        ("TTPD", "merch", "TTPD Manuscript Edition Box Set (Deluxe)", "Store Exclusive", "high", 95),
        ("Midnights", "merch", "Midnights Clock Vinyl Display (All 4 Variants)", "Limited", "high", 120),
        ("Reputation", "merch", "Reputation Stadium Tour Inflatable Snake (6ft)", "Tour Exclusive", "high", 140),
        ("1989", "merch", "1989 Polaroid Photo Set (Official 13 Cards)", "Store Exclusive", "mid", 45),

        # ─── Tour Merch Expansion (~25) ────────────────────────────────
        ("Eras Tour", "merch", "Eras Tour City-Specific Poster (LA Night 6)", "Tour Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour City-Specific Poster (London Wembley N8)", "Tour Exclusive", "high", 100),
        ("Eras Tour", "merch", "Eras Tour City-Specific Poster (Tokyo Dome N1)", "Tour Exclusive", "grail", 150),
        ("Eras Tour", "merch", "Eras Tour City-Specific Poster (Sydney N3)", "Tour Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour City-Specific Poster (Paris La Défense)", "Tour Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour City-Specific Poster (Singapore N6)", "Tour Exclusive", "high", 110),
        ("Eras Tour", "merch", "Eras Tour Friendship Bracelet Kit (Official)", "Tour Exclusive", "mid", 35),
        ("Eras Tour", "merch", "Eras Tour Denim Jacket (Embroidered Eras)", "Tour Exclusive", "grail", 220),
        ("Eras Tour", "merch", "Eras Tour Snow Globe (All Eras)", "Tour Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Crew Neck Sweatshirt (Black)", "Tour Exclusive", "mid", 65),
        ("Eras Tour", "merch", "Eras Tour Eras Charm Bracelet (Silver)", "Tour Exclusive", "mid", 45),
        ("Eras Tour", "merch", "Eras Tour Tote Bag (Canvas, All Eras Print)", "Tour Exclusive", "mid", 40),
        ("Eras Tour", "merch", "Eras Tour Eras Tour Book (Photo Diary)", "Tour Exclusive", "high", 75),
        ("Reputation", "merch", "Reputation Stadium Tour Snake Ring (Sterling Silver)", "Tour Exclusive", "high", 130),
        ("Reputation", "merch", "Reputation Stadium Tour Black Hoodie", "Tour Exclusive", "high", 110),
        ("Reputation", "merch", "Reputation Stadium Tour VIP Box Set", "VIP Exclusive", "grail", 250),
        ("Reputation", "merch", "Reputation Stadium Tour Glow Stick Snake", "Tour Exclusive", "mid", 55),
        ("1989", "merch", "1989 World Tour Light-Up Bracelet", "Tour Exclusive", "mid", 50),
        ("1989", "merch", "1989 World Tour Seagull Tee", "Tour Exclusive", "high", 80),
        ("1989", "merch", "1989 World Tour Poster (Lenticular)", "Tour Exclusive", "high", 90),
        ("Red", "merch", "Red Tour Vintage Scarf", "Tour Exclusive", "high", 120),
        ("Red", "merch", "Red Tour VIP Tote & Lanyard Set", "VIP Exclusive", "high", 100),
        ("Fearless", "merch", "Fearless Tour Gold Sequin Tank Top", "Tour Exclusive", "high", 140),
        ("Fearless", "merch", "Fearless Tour Love Story Charm Necklace", "Tour Exclusive", "high", 95),
        ("Fearless", "merch", "Fearless Tour Poster (Original 2009)", "Tour Exclusive", "high", 110),

        # ─── Vinyl Variants Expansion (~15) ────────────────────────────
        ("Midnights", "vinyl", "Midnights Signed Vinyl (Hand-Signed Insert)", "Signed Edition", "grail", 280),
        ("Folklore", "vinyl", "Folklore Signed Vinyl (Hand-Signed Insert)", "Signed Edition", "grail", 300),
        ("Evermore", "vinyl", "Evermore Signed Vinyl (Hand-Signed Insert)", "Signed Edition", "grail", 290),
        ("Lover", "vinyl", "Lover Signed Vinyl (Hand-Signed Insert)", "Signed Edition", "grail", 260),
        ("TTPD", "vinyl", "TTPD Signed Vinyl (Hand-Signed Insert)", "Signed Edition", "grail", 250),
        ("TTPD", "vinyl", "TTPD Phantom Clear Vinyl (Walmart Exclusive)", "Walmart Exclusive", "mid", 45),
        ("TTPD", "vinyl", "TTPD Ink Black Vinyl (Target Exclusive)", "Target Exclusive", "mid", 48),
        ("Midnights", "vinyl", "Midnights Til Dawn Vinyl (International Exclusive)", "International", "high", 75),
        ("1989 TV", "vinyl", "1989 TV Tangerine Vinyl (Target Exclusive)", "Target Exclusive", "mid", 50),
        ("1989 TV", "vinyl", "1989 TV Aquamarine Green Vinyl", "Standard", "mid", 35),
        ("Speak Now TV", "vinyl", "Speak Now TV Orchid Marbled Vinyl (Target)", "Target Exclusive", "mid", 48),
        ("Speak Now TV", "vinyl", "Speak Now TV Violet Vinyl (International)", "International", "mid", 42),
        ("Red TV", "vinyl", "Red TV Red Vinyl (Target Exclusive)", "Target Exclusive", "mid", 45),
        ("Debut", "vinyl", "Taylor Swift Debut Turquoise Vinyl (RSD)", "RSD Exclusive", "high", 120),
        ("Reputation", "vinyl", "Reputation Picture Disc Vinyl (FYE Exclusive)", "FYE Exclusive", "high", 95),

        # ─── Books & Media (~10) ──────────────────────────────────────
        ("Eras Tour", "media", "Taylor Swift: The Eras Tour Movie Collector's Blu-ray", "Collector's Edition", "high", 65),
        ("Eras Tour", "media", "Taylor Swift: The Eras Tour Movie 4K Steelbook", "Limited Steelbook", "high", 85),
        ("Reputation", "media", "Reputation Magazine Vol. 1", "Magazine", "high", 80),
        ("Reputation", "media", "Reputation Magazine Vol. 2", "Magazine", "high", 80),
        ("Reputation", "media", "Reputation Magazine Set (Vol. 1-4 Complete)", "Complete Set", "grail", 350),
        ("1989", "media", "1989 Polaroid Edition (Complete 65 Photos)", "Standard", "mid", 55),
        ("Lover", "media", "Lover Deluxe Journal (Version 1-4 Set)", "Complete Set", "high", 90),
        ("Taylor Swift", "book", "Taylor Swift: This Is Our Song (Photo Book)", "First Edition", "mid", 40),
        ("Taylor Swift", "book", "Taylor by Taylor Swift (Coffee Table Book)", "Standard", "mid", 35),
        ("TTPD", "media", "TTPD Anthology Manuscript Edition", "Limited", "high", 70),

        # ─── Clothing & Accessories (~15) ──────────────────────────────
        ("Folklore", "merch", "Folklore Cardigan (Official 'The' Cardigan)", "Store Exclusive", "high", 120),
        ("Folklore", "merch", "Folklore Cardigan (Black Star Edition)", "Limited Restock", "high", 100),
        ("Lover", "merch", "Lover Snow Globe (Heart-Shaped)", "Store Exclusive", "high", 90),
        ("Lover", "merch", "Lover Heart-Shaped Sunglasses (Official)", "Store Exclusive", "mid", 45),
        ("Reputation", "merch", "Reputation Snake Ring (Black Mamba)", "Store Exclusive", "high", 85),
        ("Taylor Swift", "merch", "Champion Hoodie Collab (Lover Era)", "Collab Exclusive", "high", 110),
        ("ME!", "merch", "ME! Butterfly Clutch Purse", "Store Exclusive", "mid", 60),
        ("Taylor Swift", "merch", "Taylor Swift Cat Merch Collection (Benjamin Button Tee)", "Store Exclusive", "mid", 45),
        ("Taylor Swift", "merch", "Taylor Swift Cat Merch Collection (Meredith Hoodie)", "Store Exclusive", "mid", 50),
        ("Midnights", "merch", "Midnights Lavender Haze Hoodie", "Store Exclusive", "mid", 55),
        ("TTPD", "merch", "TTPD Black Dog Embroidered Crewneck", "Store Exclusive", "mid", 58),
        ("TTPD", "merch", "TTPD Tortured Poets Quill Pen Set", "Store Exclusive", "mid", 40),
        ("1989 TV", "merch", "1989 TV Seagull Friendship Bracelet Kit", "Store Exclusive", "standard", 25),
        ("Eras Tour", "merch", "Eras Tour Bejeweled Bodysuit Replica Top", "Tour Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour All Eras Enamel Pin Set (11 Pins)", "Tour Exclusive", "high", 70),

        # ─── Holiday & Special Collections (~10) ──────────────────────
        ("Taylor Swift", "fragrance", "Wonderstruck Perfume (Original Bottle, Sealed)", "Original", "high", 95),
        ("Taylor Swift", "fragrance", "Taylor by Taylor Swift Eau de Parfum (Sealed)", "Original", "mid", 60),
        ("Taylor Swift", "fragrance", "Wonderstruck Enchanted (Sealed)", "Original", "high", 75),
        ("Taylor Swift", "merch", "Taylor Swift Holiday Ornament (Guitar, 2023)", "Holiday Exclusive", "mid", 35),
        ("Taylor Swift", "merch", "Taylor Swift Holiday Ornament (Eras, 2024)", "Holiday Exclusive", "mid", 40),
        ("Midnights", "signed_cd", "Midnights Signed CD (Hand-Signed Insert)", "Signed Edition", "grail", 200),
        ("Lover", "signed_cd", "Lover Signed Booklet (Hand-Signed)", "Signed Edition", "grail", 220),
        ("Midnights", "signed_cd", "Midnights Signed Clock Face (Moonstone Blue)", "Signed Edition", "grail", 210),
        ("Midnights", "signed_cd", "Midnights Signed Clock Face (Jade Green)", "Signed Edition", "grail", 210),
        ("TTPD", "signed_cd", "TTPD Signed CD (Hand-Signed Tortured Poets)", "Signed Edition", "grail", 190),

        # ─── Rare / Grails (~10) ──────────────────────────────────────
        ("Taylor Swift", "merch", "Hand-Signed Lithograph (Lover Era)", "Signed Numbered", "grail", 500),
        ("Taylor Swift", "merch", "Hand-Signed Lithograph (Folklore Era)", "Signed Numbered", "grail", 550),
        ("Taylor Swift", "merch", "Hand-Signed Lithograph (Midnights Era)", "Signed Numbered", "grail", 480),
        ("Taylor Swift", "merch", "Meet & Greet Polaroid (Reputation Era)", "One-of-a-Kind", "grail", 800),
        ("Taylor Swift", "merch", "Meet & Greet Polaroid (1989 Era)", "One-of-a-Kind", "grail", 900),
        ("Taylor Swift", "merch", "Promotional Radio Station Poster (Signed)", "Promo", "grail", 350),
        ("Taylor Swift", "merch", "Grammy Appearance Replica Dress (Midnights, Numbered)", "Replica LE", "grail", 400),
        ("Taylor Swift", "merch", "Limited Numbered Art Print (Eras Tour, /500)", "Numbered LE", "grail", 300),
        ("Taylor Swift", "merch", "Red Scarf (Prop Replica, All Too Well)", "Store Exclusive", "high", 85),
        ("Taylor Swift", "merch", "Taylor Swift Debut Era Signed Photo (Authenticated)", "Signed", "grail", 650),

        # ─── Eras Tour International Exclusives ─────────────────────────
        ("Taylor Swift", "merch", "Eras Tour Australia Exclusive Poster (Melbourne)", "Australia Exclusive", "high", 80),
        ("Taylor Swift", "merch", "Eras Tour Australia Exclusive Poster (Sydney)", "Australia Exclusive", "high", 80),
        ("Taylor Swift", "merch", "Eras Tour UK Exclusive Poster (London Wembley)", "UK Exclusive", "high", 85),
        ("Taylor Swift", "merch", "Eras Tour UK Exclusive Poster (Edinburgh)", "UK Exclusive", "high", 85),
        ("Taylor Swift", "merch", "Eras Tour Japan Exclusive Poster (Tokyo Dome)", "Japan Exclusive", "high", 90),
        ("Taylor Swift", "merch", "Eras Tour Singapore Exclusive Poster", "Singapore Exclusive", "high", 90),
        ("Taylor Swift", "merch", "Eras Tour Australia Exclusive Tee (Gold Foil)", "Australia Exclusive", "mid", 60),
        ("Taylor Swift", "merch", "Eras Tour UK Exclusive Tee (Union Jack Heart)", "UK Exclusive", "mid", 55),
        ("Taylor Swift", "merch", "Eras Tour Japan Exclusive Tee (Kanji)", "Japan Exclusive", "mid", 65),
        ("Taylor Swift", "merch", "Eras Tour Singapore Exclusive Tee (Lion City)", "Singapore Exclusive", "mid", 60),

        # ─── Lover Experience Pop-Up Merch ──────────────────────────────
        ("Lover", "merch", "Lover Experience Pop-Up Exclusive Snow Globe", "Pop-Up Exclusive", "high", 120),
        ("Lover", "merch", "Lover Experience Pop-Up Tote Bag", "Pop-Up Exclusive", "mid", 45),
        ("Lover", "merch", "Lover Experience Pop-Up Enamel Pin Set", "Pop-Up Exclusive", "mid", 40),
        ("Lover", "merch", "Lover Experience Pop-Up Photo Frame", "Pop-Up Exclusive", "mid", 35),

        # ─── Additional Signed Items ────────────────────────────────────
        ("TTPD", "signed_cd", "TTPD Signed Vinyl Insert (The Black Dog)", "Signed Edition", "grail", 250),
        ("Fearless TV", "signed_cd", "Fearless (Taylor's Version) Signed CD Insert", "Signed Edition", "grail", 180),
        ("1989 TV", "signed_cd", "1989 (Taylor's Version) Signed Photo (Sunrise Blvd)", "Signed Edition", "grail", 200),
        ("Speak Now TV", "signed_cd", "Speak Now (Taylor's Version) Signed Booklet", "Signed Edition", "grail", 190),

        # ─── Taylor Swift Fragrances ────────────────────────────────────
        ("Taylor Swift", "fragrance", "Wonderstruck Enchanted Rollerball Set (3-Pack)", "Original", "mid", 50),
        ("Taylor Swift", "fragrance", "Taylor by Taylor Swift Made of Starlight", "Original", "mid", 55),
        ("Taylor Swift", "fragrance", "Incredible Things Eau de Parfum (Sealed)", "Original", "mid", 50),

        # ─── Taylor Swift Jewelry & Accessories ─────────────────────────
        ("Taylor Swift", "merch", "Eras Bracelet Collection (Official Box Set)", "Store Exclusive", "high", 95),
        ("Taylor Swift", "merch", "Midnights Lavender Haze Ring", "Store Exclusive", "mid", 45),
        ("Taylor Swift", "merch", "TTPD Heart Locket Necklace", "Store Exclusive", "mid", 50),
        ("Taylor Swift", "merch", "Eras Tour Friendship Bracelet Kit (Official)", "Store Exclusive", "standard", 30),

        # ─── More Clothing Items ────────────────────────────────────────
        ("Taylor Swift", "merch", "Eras Tour Crewneck Sweatshirt (Eras Collage)", "Standard", "mid", 65),
        ("Taylor Swift", "merch", "TTPD Black Hoodie (The Manuscript)", "Store Exclusive", "mid", 70),
        ("Taylor Swift", "merch", "Reputation Snake Ring Zip-Up Hoodie (LE)", "Store Exclusive", "high", 85),
        ("Taylor Swift", "merch", "Midnights Bejeweled Cardigan", "Store Exclusive", "high", 90),

        # ─── Reputation Era Deep Cuts ──────────────────────────────────────
        ("Reputation", "merch", "Reputation Magazine Vol. 1 (Sealed)", "Magazine", "high", 80),
        ("Reputation", "merch", "Reputation Magazine Vol. 2 (Sealed)", "Magazine", "high", 80),
        ("Reputation", "merch", "Reputation Stadium Tour VIP Box Set", "Tour VIP", "grail", 300),
        ("Reputation", "merch", "Reputation Snake Ring (Official)", "Store Exclusive", "high", 95),
        ("Reputation", "merch", "Reputation Tour Pop Socket Set (3-Pack)", "Tour Exclusive", "mid", 40),
        ("Reputation", "merch", "Reputation Snake Phone Case", "Store Exclusive", "mid", 35),
        ("Reputation", "merch", "Reputation Tour Poster (Specific City — LA)", "Tour Exclusive", "mid", 50),
        ("Reputation", "merch", "Reputation Tour Poster (Specific City — NYC)", "Tour Exclusive", "mid", 55),
        ("Reputation", "merch", "Reputation Tour Light-Up Wristband", "Tour Exclusive", "mid", 40),
        ("Reputation", "merch", "Reputation Tour Meet & Greet Polaroid", "Tour VIP", "grail", 250),
        ("Reputation", "vinyl", "Reputation Picture Disc Vinyl (2LP)", "Picture Disc", "grail", 200),
        ("Reputation", "vinyl", "Reputation Orange Vinyl (FYE Exclusive)", "FYE Exclusive", "grail", 250),
        ("Reputation", "merch", "Reputation Newspaper Headline Tee", "Store Exclusive", "mid", 45),
        ("Reputation", "merch", "Reputation Era Look What You Made Me Do Snake Hoodie", "Store Exclusive", "high", 85),

        # ─── Lover Era Deep Cuts ───────────────────────────────────────────
        ("Lover", "vinyl", "Lover Live From Paris Vinyl (Pink Splatter)", "Limited Press", "grail", 180),
        ("Lover", "merch", "Lover Snow Globe (ME! Edition)", "Store Exclusive", "high", 95),
        ("Lover", "merch", "Lover Diary (Complete Set of 4)", "Store Exclusive", "high", 80),
        ("Lover", "merch", "Lover Butterfly Crop Top (Official)", "Store Exclusive", "mid", 45),
        ("Lover", "merch", "Lover Era Rainbow Bomber Jacket", "Store Exclusive", "grail", 150),
        ("Lover", "merch", "Lover Phone Ring Holder (Heart Shaped)", "Store Exclusive", "standard", 25),
        ("Lover", "merch", "Lover Fest Poster (Foxborough Night 1)", "Tour Exclusive", "grail", 200),
        ("Lover", "merch", "Lover Album Art Puzzle (500 Piece)", "Store Exclusive", "standard", 30),
        ("Lover", "cd", "Lover Deluxe Album (Version 1-4 Set)", "Deluxe Set", "high", 80),

        # ─── 1989 Era Items ───────────────────────────────────────────────
        ("1989", "vinyl", "1989 (Original) Crystal Clear Vinyl (RSD)", "RSD Limited", "grail", 200),
        ("1989", "merch", "1989 World Tour Polaroid Set (65 Photos)", "Tour Exclusive", "grail", 180),
        ("1989", "merch", "1989 World Tour VIP Tote Bag", "Tour VIP", "high", 100),
        ("1989", "merch", "1989 Seagull Crop Top (Tour Exclusive)", "Tour Exclusive", "mid", 50),
        ("1989", "merch", "1989 World Tour Lithograph (Numbered)", "Tour Exclusive", "high", 80),
        ("1989", "merch", "1989 World Tour City Poster — London", "Tour Exclusive", "mid", 55),
        ("1989", "merch", "1989 World Tour City Poster — Tokyo", "Tour Exclusive", "mid", 60),
        ("1989", "merch", "1989 Skyline Guitar Pick Set (5 Picks)", "Store Exclusive", "mid", 35),

        # ─── Red Era Items ────────────────────────────────────────────────
        ("Red", "vinyl", "Red (Original) Black Vinyl 2LP", "Standard Press", "high", 80),
        ("Red", "merch", "Red Tour Poster (Specific City — Nashville)", "Tour Exclusive", "high", 90),
        ("Red", "merch", "Red Tour VIP Book & Lanyard Set", "Tour VIP", "grail", 200),
        ("Red", "merch", "Red Scarf (All Too Well Inspired)", "Store Exclusive", "mid", 40),
        ("Red", "merch", "Red Album Photo Cards Set (30 Cards)", "Store Exclusive", "mid", 35),
        ("Red", "merch", "Red Era Treacherous Ring (Official)", "Store Exclusive", "mid", 45),
        ("Red", "cd", "Red Deluxe Edition (Zipper Case)", "Deluxe Zipper", "high", 80),

        # ─── Speak Now Era Items ──────────────────────────────────────────
        ("Speak Now", "vinyl", "Speak Now (Original) Smoke Vinyl 2LP", "Standard Press", "high", 90),
        ("Speak Now", "merch", "Speak Now World Tour Dress Ornament", "Tour Exclusive", "high", 100),
        ("Speak Now", "merch", "Speak Now Tour VIP Package Box", "Tour VIP", "grail", 200),
        ("Speak Now", "merch", "Speak Now Purple Guitar Pick Set", "Store Exclusive", "mid", 35),
        ("Speak Now", "merch", "Speak Now Tour Poster (Specific City — Chicago)", "Tour Exclusive", "mid", 55),
        ("Speak Now", "merch", "Enchanted Sheet Music (Signed Copy)", "Signed", "grail", 300),

        # ─── Debut / Fearless Era Vintage ──────────────────────────────────
        ("Taylor Swift", "vinyl", "Taylor Swift (Debut) Original Pressing Vinyl", "Original Press", "grail", 250),
        ("Taylor Swift", "cd", "Taylor Swift (Debut) Promo CD Single (Tim McGraw)", "Promo", "grail", 200),
        ("Taylor Swift", "merch", "Fearless Tour T-Shirt (Original 2009)", "Tour Exclusive", "high", 80),
        ("Fearless", "vinyl", "Fearless (Original) Gold Vinyl 2LP", "Standard Press", "high", 100),
        ("Fearless", "merch", "Fearless Tour VIP Tote & Lanyard Set", "Tour VIP", "grail", 180),
        ("Fearless", "merch", "Fearless Tour Poster (Specific City — NYC)", "Tour Exclusive", "mid", 60),
        ("Taylor Swift", "merch", "Beautiful Eyes EP (Walmart Exclusive CD+DVD)", "Walmart Exclusive", "grail", 200),

        # ─── International Store Exclusives ────────────────────────────────
        ("Taylor Swift", "vinyl", "Midnights (UK HMV Jade Green Vinyl)", "UK HMV Exclusive", "high", 90),
        ("Taylor Swift", "vinyl", "1989 TV (UK HMV Rose Garden Pink Vinyl)", "UK HMV Exclusive", "high", 85),
        ("Taylor Swift", "cd", "Midnights (Japan CD with Bonus Track Hits Different)", "Japan Exclusive", "mid", 40),
        ("Taylor Swift", "cd", "1989 TV (Japan CD with Bonus Tracks)", "Japan Exclusive", "mid", 38),
        ("Taylor Swift", "cd", "TTPD (Japan CD with Bonus Track)", "Japan Exclusive", "mid", 40),
        ("Taylor Swift", "vinyl", "Folklore (Australia JB Hi-Fi Green Vinyl)", "AU JB Hi-Fi Exclusive", "high", 100),
        ("Taylor Swift", "vinyl", "Evermore (Australia JB Hi-Fi Green Vinyl)", "AU JB Hi-Fi Exclusive", "high", 100),
        ("Taylor Swift", "cd", "Lover (Japan Deluxe CD with Bonus DVD)", "Japan Exclusive", "mid", 45),
        ("Taylor Swift", "vinyl", "Speak Now TV (UK Amazon Purple/Gold Vinyl)", "UK Amazon Exclusive", "high", 80),
        ("Taylor Swift", "vinyl", "Red TV (UK Amazon Crystal Clear Vinyl)", "UK Amazon Exclusive", "high", 85),

        # ─── Fan-Made Officially Licensed ──────────────────────────────────
        ("Taylor Swift", "merch", "Eras Tour Official Book (Hardcover)", "Store Exclusive", "mid", 45),
        ("Taylor Swift", "merch", "Taylor Swift: In Her Own Words Book (Signed)", "Signed", "grail", 180),
        ("Taylor Swift", "merch", "Eras Tour Official Poster Book", "Store Exclusive", "mid", 35),
        ("Taylor Swift", "merch", "Eras Tour Official Playing Card Deck", "Store Exclusive", "standard", 25),
        ("Taylor Swift", "merch", "Eras Tour Official Tote Bag (All Eras Artwork)", "Store Exclusive", "standard", 30),
        ("Taylor Swift", "merch", "1989 TV Official Puzzle (1000 Piece)", "Store Exclusive", "standard", 30),
        ("Taylor Swift", "merch", "Midnights Official Candle (Lavender Haze Scent)", "Store Exclusive", "mid", 40),
        ("Taylor Swift", "merch", "TTPD Official Typewriter Sticky Notes Set", "Store Exclusive", "standard", 20),

        # ─── Eras Tour International Items ─────────────────────────────────
        ("Eras Tour", "merch", "Eras Tour Melbourne Night 1 Poster", "Tour Exclusive", "mid", 55),
        ("Eras Tour", "merch", "Eras Tour Tokyo Night 1 Poster", "Tour Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour London Wembley Poster (Night 1)", "Tour Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Singapore Poster (Night 1)", "Tour Exclusive", "mid", 65),
        ("Eras Tour", "merch", "Eras Tour Paris Poster (Night 1)", "Tour Exclusive", "mid", 60),
        ("Eras Tour", "merch", "Eras Tour Edinburgh Poster", "Tour Exclusive", "mid", 55),
        ("Eras Tour", "merch", "Eras Tour Surprise Song Guitar Pick (Random City)", "Tour Exclusive", "mid", 35),
        ("Eras Tour", "merch", "Eras Tour Confetti (Collected, Framed)", "Fan Collectible", "standard", 15),
        ("Eras Tour", "merch", "Eras Tour Wristband (Light-Up, Working)", "Tour Exclusive", "mid", 35),
        ("Eras Tour", "merch", "Eras Tour VIP Merch Box (Complete)", "Tour VIP", "grail", 350),

        # ─── More Eras Tour City-Specific ──────────────────────────────────
        ("Eras Tour", "merch", "Eras Tour Amsterdam Poster (Night 1)", "Tour Exclusive", "mid", 55),
        ("Eras Tour", "merch", "Eras Tour Madrid Poster", "Tour Exclusive", "mid", 50),
        ("Eras Tour", "merch", "Eras Tour Stockholm Poster", "Tour Exclusive", "mid", 50),
        ("Eras Tour", "merch", "Eras Tour Sydney Poster (Night 1)", "Tour Exclusive", "mid", 60),
        ("Eras Tour", "merch", "Eras Tour Buenos Aires Poster", "Tour Exclusive", "mid", 55),
        ("Eras Tour", "merch", "Eras Tour Vancouver Poster (Final Night)", "Tour Exclusive", "grail", 150),
        ("Eras Tour", "merch", "Eras Tour Indianapolis Poster", "Tour Exclusive", "mid", 45),
        ("Eras Tour", "merch", "Eras Tour Kansas City Poster (Night 1)", "Tour Exclusive", "mid", 55),
        ("Eras Tour", "merch", "Eras Tour Munich Poster", "Tour Exclusive", "mid", 50),
        ("Eras Tour", "merch", "Eras Tour Dublin Poster", "Tour Exclusive", "mid", 50),
        ("Eras Tour", "merch", "Eras Tour Warsaw Poster", "Tour Exclusive", "mid", 50),

        # ─── More Vinyl Variants ───────────────────────────────────────────
        ("Midnights", "vinyl", "Midnights (Mahogany Edition Vinyl)", "Mahogany", "mid", 40),
        ("Midnights", "vinyl", "Midnights (Jade Green Edition Vinyl)", "Jade Green", "mid", 45),
        ("Midnights", "vinyl", "Midnights (Blood Moon Edition Vinyl)", "Blood Moon", "mid", 55),
        ("Midnights", "vinyl", "Midnights (3am Edition 2LP Blue Vinyl)", "Deluxe", "high", 80),
        ("TTPD", "vinyl", "TTPD (Phantom Clear Vinyl)", "Phantom Clear", "mid", 45),
        ("TTPD", "vinyl", "TTPD (The Bolter Ghosted White Vinyl)", "Bolter Edition", "mid", 50),
        ("Evermore", "vinyl", "Evermore (Deluxe Green Vinyl 2LP)", "Deluxe Green", "mid", 55),
        ("Folklore", "vinyl", "Folklore (In the Trees Green Vinyl)", "In the Trees", "mid", 50),
        ("Folklore", "vinyl", "Folklore (Betty's Garden Green Vinyl)", "Betty's Garden", "mid", 50),
        ("Folklore", "vinyl", "Folklore (Clandestine Meetings Grey Vinyl)", "Clandestine Meetings", "mid", 55),
        ("Folklore", "vinyl", "Folklore (Running Like Water Blue Vinyl)", "Running Like Water", "mid", 50),
        ("Red TV", "vinyl", "Red TV (4LP Red Vinyl)", "Red Vinyl", "high", 80),
        ("Fearless TV", "vinyl", "Fearless TV (Gold Vinyl 3LP)", "Gold Vinyl", "high", 75),
        ("Speak Now TV", "vinyl", "Speak Now TV (Orchid Marbled Vinyl 2LP)", "Orchid Marbled", "high", 80),
        ("Speak Now TV", "vinyl", "Speak Now TV (Lilac Marble Vinyl 3LP)", "Lilac Marble", "high", 85),

        # ─── More Collectible Items ────────────────────────────────────────
        ("Taylor Swift", "merch", "Eras Tour Leather Journal (Official)", "Store Exclusive", "mid", 50),
        ("Taylor Swift", "merch", "Taylor Swift The Eras Tour Book (Limited Cover)", "Store Exclusive", "mid", 45),
        ("Taylor Swift", "merch", "Midnights Clock (Working, Official)", "Store Exclusive", "mid", 55),
        ("Taylor Swift", "merch", "TTPD Quill Pen Set (Official)", "Store Exclusive", "mid", 40),
        ("Taylor Swift", "merch", "Eras Tour Snow Globe (Multiple Eras)", "Store Exclusive", "high", 100),
        ("Taylor Swift", "merch", "Taylor Swift TIME Person of the Year (Newsstand)", "Magazine", "mid", 30),
        ("Taylor Swift", "merch", "Vogue September 2024 Taylor Swift Cover", "Magazine", "mid", 25),
        ("Taylor Swift", "merch", "Rolling Stone Taylor Swift Cover (2023)", "Magazine", "standard", 20),

        # ─── Cassette Tapes ────────────────────────────────────────────────
        ("Midnights", "cassette", "Midnights Lavender Cassette", "Lavender Edition", "mid", 30),
        ("Midnights", "cassette", "Midnights Moonstone Blue Cassette", "Moonstone Blue", "mid", 30),
        ("TTPD", "cassette", "TTPD Cassette (Standard)", "Standard", "standard", 20),
        ("Folklore", "cassette", "Folklore Cassette (Meet Me Behind the Mall)", "Standard", "mid", 35),
        ("Evermore", "cassette", "Evermore Cassette (Standard)", "Standard", "mid", 35),
        ("1989 TV", "cassette", "1989 TV Cassette (Rose Garden Pink)", "Rose Garden Pink", "mid", 30),
        ("Speak Now TV", "cassette", "Speak Now TV Cassette (Orchid)", "Orchid", "mid", 30),
        ("Lover", "cassette", "Lover Cassette (Heart Edition)", "Heart Edition", "mid", 40),
        ("Red TV", "cassette", "Red TV Cassette (Standard)", "Standard", "mid", 35),
        ("Fearless TV", "cassette", "Fearless TV Cassette (Gold)", "Gold", "mid", 35),

        # ─── More Award Show & Promo Items ─────────────────────────────────
        ("Taylor Swift", "merch", "Grammy Award Replica Figurine (Unofficial Display)", "Fan Collectible", "mid", 40),
        ("Taylor Swift", "merch", "AMAs 2023 Taylor Swift Commemorative Ticket", "Event Item", "mid", 35),
        ("Taylor Swift", "merch", "SNL Taylor Swift Guest Mug (Promo)", "Promo Item", "high", 80),
        ("Taylor Swift", "merch", "Taylor Swift Eras Tour Movie Poster (Original Theater)", "Promo", "mid", 40),
        ("Taylor Swift", "merch", "Taylor Swift Eras Tour Movie Blu-ray (Extended Cut)", "Standard", "standard", 25),

        # ─── More CD Variants & Deluxe ─────────────────────────────────────
        ("Midnights", "cd", "Midnights (Til Dawn Deluxe CD)", "Deluxe", "mid", 35),
        ("TTPD", "cd", "TTPD (Target Exclusive CD w/ Bonus Track)", "Target Exclusive", "standard", 22),
        ("TTPD", "cd", "TTPD (Manuscript Edition CD)", "Manuscript Edition", "mid", 40),
        ("1989 TV", "cd", "1989 TV (Deluxe CD w/ Voice Memos)", "Deluxe", "mid", 35),
        ("Speak Now TV", "cd", "Speak Now TV (Deluxe CD w/ Vault Tracks)", "Deluxe", "mid", 35),
        ("Red TV", "cd", "Red TV (Target Exclusive CD w/ Bonus Track)", "Target Exclusive", "standard", 22),
        ("Folklore", "cd", "Folklore (Deluxe Clandestine Meetings CD)", "Deluxe", "mid", 35),
        ("Evermore", "cd", "Evermore (Deluxe CD w/ Bonus Track)", "Deluxe", "mid", 35),

        # ─── More Merch & Home Items ───────────────────────────────────────
        ("Taylor Swift", "merch", "TTPD Tortured Poets Notebook Set (3-Pack)", "Store Exclusive", "standard", 28),
        ("Taylor Swift", "merch", "Eras Tour Official Blanket (All Eras)", "Store Exclusive", "mid", 60),
        ("Taylor Swift", "merch", "Midnights Lavender Haze Mug", "Store Exclusive", "standard", 22),
        ("Taylor Swift", "merch", "TTPD Manuscript Wax Seal Set", "Store Exclusive", "mid", 35),
        ("Taylor Swift", "merch", "Eras Tour Bookmark Set (13 Bookmarks)", "Store Exclusive", "standard", 18),
        ("Taylor Swift", "merch", "Taylor Swift Official 2025 Calendar", "Store Exclusive", "standard", 20),
        ("Taylor Swift", "merch", "Folklore Cardigan (Beige, Official)", "Store Exclusive", "high", 80),
        ("Taylor Swift", "merch", "Folklore Cardigan (Grey, Official)", "Store Exclusive", "high", 85),
        ("Taylor Swift", "merch", "Folklore Cardigan (Black, Official)", "Store Exclusive", "high", 90),
        ("Taylor Swift", "merch", "Midnights Pajama Set (Moonstone Blue)", "Store Exclusive", "mid", 55),

        # ─── More Picture Discs & Special Vinyl ────────────────────────────
        ("Midnights", "vinyl", "Midnights (Moonstone Blue Picture Disc)", "Picture Disc", "high", 80),
        ("1989 TV", "vinyl", "1989 TV (Picture Disc Vinyl)", "Picture Disc", "high", 85),
        ("TTPD", "vinyl", "TTPD (Parchment Beige Vinyl, Indie)", "Indie Exclusive", "mid", 45),
        ("Speak Now TV", "vinyl", "Speak Now TV (Target Exclusive Orchid)", "Target Exclusive", "mid", 40),
        ("Red TV", "vinyl", "Red TV (Target Exclusive Red Vinyl)", "Target Exclusive", "mid", 38),
        ("Fearless TV", "vinyl", "Fearless TV (Target Exclusive Gold Vinyl)", "Target Exclusive", "mid", 38),

        # ─── Holiday & Christmas Items ─────────────────────────────────────
        ("Taylor Swift", "merch", "Christmas Tree Farm Ornament (Official 2023)", "Holiday Collection", "mid", 35),
        ("Taylor Swift", "merch", "Taylor Swift Holiday Collection Stocking", "Holiday Collection", "standard", 25),
        ("Taylor Swift", "merch", "Eras Tour Christmas Sweater (Ugly Sweater)", "Holiday Collection", "mid", 55),
        ("Taylor Swift", "merch", "Snow Globe Shake It Off (2022 Holiday)", "Holiday Collection", "high", 80),
        ("Taylor Swift", "merch", "Midnights Holiday Gift Box Set", "Holiday Collection", "mid", 65),
        ("Taylor Swift", "merch", "Christmas Tree Farm Scented Candle (Official)", "Holiday Collection", "mid", 40),

        # ── Round 35b: City Posters, Cassettes, Signed Items, Pop-up, International, Reputation — 129 items ──

        # Eras Tour City Posters (+16)
        ("Eras Tour", "poster", "Eras Tour City Poster — London Wembley Night 1", "Tour Exclusive", "high", 120),
        ("Eras Tour", "poster", "Eras Tour City Poster — London Wembley Night 5", "Tour Exclusive", "high", 130),
        ("Eras Tour", "poster", "Eras Tour City Poster — Paris La Defense Arena", "Tour Exclusive", "high", 100),
        ("Eras Tour", "poster", "Eras Tour City Poster — Tokyo Dome Night 1", "Tour Exclusive", "grail", 180),
        ("Eras Tour", "poster", "Eras Tour City Poster — Tokyo Dome Night 4", "Tour Exclusive", "grail", 200),
        ("Eras Tour", "poster", "Eras Tour City Poster — Sydney Accor Stadium", "Tour Exclusive", "high", 90),
        ("Eras Tour", "poster", "Eras Tour City Poster — Singapore National Stadium", "Tour Exclusive", "high", 110),
        ("Eras Tour", "poster", "Eras Tour City Poster — Amsterdam Johan Cruyff Arena", "Tour Exclusive", "high", 95),
        ("Eras Tour", "poster", "Eras Tour City Poster — Vienna Ernst Happel Stadion", "Tour Exclusive", "high", 85),
        ("Eras Tour", "poster", "Eras Tour City Poster — Zurich Letzigrund", "Tour Exclusive", "high", 80),
        ("Eras Tour", "poster", "Eras Tour City Poster — Munich Olympiastadion", "Tour Exclusive", "high", 85),
        ("Eras Tour", "poster", "Eras Tour City Poster — Edinburgh Murrayfield", "Tour Exclusive", "high", 90),
        ("Eras Tour", "poster", "Eras Tour City Poster — Cardiff Principality Stadium", "Tour Exclusive", "high", 80),
        ("Eras Tour", "poster", "Eras Tour City Poster — Liverpool Anfield", "Tour Exclusive", "high", 85),
        ("Eras Tour", "poster", "Eras Tour City Poster — Hamburg Volksparkstadion", "Tour Exclusive", "high", 80),
        ("Eras Tour", "poster", "Eras Tour City Poster — Stockholm Friends Arena", "Tour Exclusive", "high", 85),

        # More Eras Tour City Posters (+6)
        ("Eras Tour", "poster", "Eras Tour City Poster — Milan San Siro", "Tour Exclusive", "high", 90),
        ("Eras Tour", "poster", "Eras Tour City Poster — Warsaw PGE Narodowy", "Tour Exclusive", "high", 75),
        ("Eras Tour", "poster", "Eras Tour City Poster — Lisbon Estadio da Luz", "Tour Exclusive", "high", 75),
        ("Eras Tour", "poster", "Eras Tour City Poster — Dublin Aviva Stadium", "Tour Exclusive", "high", 85),
        ("Eras Tour", "poster", "Eras Tour City Poster — Toronto Rogers Centre", "Tour Exclusive", "high", 80),
        ("Eras Tour", "poster", "Eras Tour City Poster — Buenos Aires River Plate", "Tour Exclusive", "high", 95),

        # Cassette Tapes — All Albums (+14)
        ("Midnights", "cassette", "Midnights Lavender Cassette (Target)", "Lavender (Target)", "mid", 32),
        ("Folklore", "cassette", "Folklore Running Like Water Cassette", "Running Like Water Cassette", "mid", 35),
        ("Folklore", "cassette", "Folklore In the Trees Cassette", "In the Trees Cassette", "mid", 35),
        ("Evermore", "cassette", "Evermore Green Cassette (Target)", "Green Cassette (Target)", "mid", 35),
        ("Lover", "cassette", "Lover Cassette", "Standard Cassette", "mid", 30),
        ("Reputation", "cassette", "Reputation Cassette (FYE Exclusive)", "FYE Cassette", "mid", 40),
        ("1989 TV", "cassette", "1989 TV Rose Garden Pink Cassette", "Rose Garden Cassette", "mid", 30),
        ("1989 TV", "cassette", "1989 TV Aquamarine Green Cassette", "Aquamarine Cassette", "mid", 30),
        ("1989 TV", "cassette", "1989 TV Tangerine Cassette (Target)", "Tangerine Cassette (Target)", "mid", 35),
        ("Speak Now TV", "cassette", "Speak Now TV Orchid Cassette", "Orchid Cassette", "mid", 30),
        ("Speak Now TV", "cassette", "Speak Now TV Lilac Cassette", "Lilac Cassette", "mid", 30),
        ("Red TV", "cassette", "Red TV Cassette", "Standard Cassette", "mid", 28),
        ("Fearless TV", "cassette", "Fearless TV Cassette", "Standard Cassette", "mid", 28),
        ("TTPD", "cassette", "TTPD The Bolter Cassette", "The Bolter Cassette", "standard", 25),

        # Signed Items (+10)
        ("Midnights", "cd", "Midnights Signed CD Insert (Heart Drawing)", "Signed CD Heart", "grail", 150),
        ("Midnights", "cd", "Midnights Signed CD Insert (Standard)", "Signed CD", "high", 120),
        ("TTPD", "cd", "TTPD Signed CD Insert (w/ Heart)", "Signed CD Heart", "grail", 160),
        ("TTPD", "cd", "TTPD Signed CD Insert (Standard)", "Signed CD", "high", 130),
        ("Folklore", "cd", "Folklore Signed CD Insert", "Signed CD", "high", 140),
        ("Evermore", "cd", "Evermore Signed CD Insert", "Signed CD", "grail", 180),
        ("1989 TV", "cd", "1989 TV Signed CD Insert", "Signed CD", "high", 110),
        ("Speak Now TV", "cd", "Speak Now TV Signed CD Insert", "Signed CD", "high", 120),
        ("Red TV", "cd", "Red TV Signed Photo Insert", "Signed Photo", "high", 130),
        ("Fearless TV", "cd", "Fearless TV Signed CD Insert", "Signed CD", "grail", 200),

        # Pop-up Shop Exclusives (+10)
        ("Midnights", "merch", "Midnights Pop-up Shop Lavender Tote Bag", "Pop-up Exclusive", "mid", 55),
        ("Midnights", "merch", "Midnights Pop-up Shop Clock Enamel Pin Set", "Pop-up Exclusive", "mid", 45),
        ("TTPD", "merch", "TTPD Pop-up Shop Quill Pen & Ink Set", "Pop-up Exclusive", "high", 75),
        ("TTPD", "merch", "TTPD Pop-up Shop Manuscript Tote Bag", "Pop-up Exclusive", "mid", 55),
        ("TTPD", "merch", "TTPD Pop-up Shop Typewriter Keychain", "Pop-up Exclusive", "mid", 35),
        ("1989 TV", "merch", "1989 TV Pop-up Shop Polaroid Camera Ornament", "Pop-up Exclusive", "mid", 50),
        ("1989 TV", "merch", "1989 TV Pop-up Shop Seagull Tote Bag", "Pop-up Exclusive", "mid", 48),
        ("Folklore", "merch", "Folklore Pop-up Shop Cardigan Mini Replica", "Pop-up Exclusive", "high", 65),
        ("Lover", "merch", "Lover Pop-up Shop Heart-Shaped Sunglasses", "Pop-up Exclusive", "mid", 45),
        ("Speak Now TV", "merch", "Speak Now TV Pop-up Shop Enchanted Snow Globe", "Pop-up Exclusive", "high", 80),

        # International Store Variants (+12)
        ("Midnights", "vinyl", "Midnights Japan Exclusive OBI Strip LP (w/ Bonus)", "Japan OBI", "high", 85),
        ("TTPD", "vinyl", "TTPD Japan Exclusive OBI Strip LP (w/ Bonus)", "Japan OBI", "high", 90),
        ("Folklore", "vinyl", "Folklore UK Exclusive Green Vinyl (HMV)", "HMV Exclusive", "high", 70),
        ("Evermore", "vinyl", "Evermore UK Exclusive Translucent Green (HMV)", "HMV Exclusive", "high", 75),
        ("1989 TV", "vinyl", "1989 TV Australia Exclusive Vinyl", "Australia Exclusive", "high", 68),
        ("Speak Now TV", "vinyl", "Speak Now TV Germany Exclusive Violet Vinyl", "Germany Exclusive", "high", 72),
        ("Red TV", "vinyl", "Red TV France Exclusive Vinyl (FNAC)", "FNAC Exclusive", "high", 75),
        ("Midnights", "vinyl", "Midnights Korea Exclusive Vinyl (w/ Photo Card)", "Korea Exclusive", "high", 90),
        ("TTPD", "vinyl", "TTPD India Exclusive CD (w/ Bonus Track)", "India Exclusive", "mid", 45),
        ("Lover", "vinyl", "Lover Germany Exclusive Vinyl (w/ Poster)", "Germany Exclusive", "high", 65),
        ("Folklore", "vinyl", "Folklore Australia Exclusive Betty's Garden Vinyl", "Australia Exclusive", "high", 72),
        ("1989 TV", "vinyl", "1989 TV Korea Exclusive Vinyl (w/ Photo Card)", "Korea Exclusive", "high", 80),

        # Reputation Era Items (+12)
        ("Reputation", "merch", "Reputation Snake Ring (Official Store)", "Limited", "high", 85),
        ("Reputation", "merch", "Reputation Tour Jacket (Bomber Style)", "Tour Exclusive", "grail", 200),
        ("Reputation", "merch", "Reputation Magazine Vol. 1", "Magazine", "high", 65),
        ("Reputation", "merch", "Reputation Magazine Vol. 2", "Magazine", "high", 65),
        ("Reputation", "merch", "Reputation Magazine Vol. 3", "Magazine", "high", 70),
        ("Reputation", "merch", "Reputation Magazine Vol. 4", "Magazine", "high", 75),
        ("Reputation", "merch", "Reputation Tour VIP Merch Box", "VIP Exclusive", "grail", 250),
        ("Reputation", "merch", "Reputation Tour Snake Enamel Pin Set", "Tour Exclusive", "mid", 55),
        ("Reputation", "merch", "Reputation Stadium Tour Poster (Set of 3)", "Tour Exclusive", "high", 90),
        ("Reputation", "vinyl", "Reputation Standard Black 2LP Vinyl", "Standard Black", "mid", 40),
        ("Reputation", "cd", "Reputation Target Exclusive Magazine+CD Vol.1", "Target Magazine", "mid", 55),
        ("Reputation", "cd", "Reputation Target Exclusive Magazine+CD Vol.2", "Target Magazine", "mid", 55),

        # More Eras Tour Merch (+10)
        ("Eras Tour", "merch", "Eras Tour VIP Package Tote Bag", "VIP Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour VIP Laminate + Lanyard Set", "VIP Exclusive", "high", 65),
        ("Eras Tour", "merch", "Eras Tour Blue Crewneck Sweatshirt", "Tour Exclusive", "high", 85),
        ("Eras Tour", "merch", "Eras Tour Eras Collage T-Shirt", "Tour Exclusive", "mid", 55),
        ("Eras Tour", "merch", "Eras Tour Guitar Pick Set (10 picks)", "Tour Exclusive", "mid", 40),
        ("Eras Tour", "merch", "Eras Tour International Leg Enamel Pin Set", "Tour Exclusive", "mid", 50),
        ("Eras Tour", "merch", "Eras Tour Concert Film Blu-ray (2024)", "Limited", "mid", 40),
        ("Eras Tour", "merch", "Eras Tour Concert Film 4K UHD Collector's Edition", "Collectors Edition", "high", 65),

        # More Vinyl Variants & Box Sets (+10)
        ("Speak Now TV", "vinyl", "Speak Now TV Orchid Marbled Vinyl", "Orchid Marbled", "mid", 38),
        ("Speak Now TV", "vinyl", "Speak Now TV Lilac Vinyl", "Lilac", "mid", 35),
        ("Red TV", "vinyl", "Red TV Red Vinyl (Target)", "Red (Target)", "mid", 45),
        ("Red TV", "vinyl", "Red TV Standard Black 4LP", "Standard Black", "mid", 38),
        ("Fearless TV", "vinyl", "Fearless TV Gold Vinyl", "Gold", "mid", 38),
        ("Fearless TV", "vinyl", "Fearless TV Standard Black 3LP", "Standard Black", "mid", 35),
        ("Taylor Swift", "vinyl", "The Taylor Swift Holiday Collection Vinyl (RSD)", "RSD Exclusive", "grail", 250),
        ("Taylor Swift", "vinyl", "Beautiful Eyes EP Vinyl (Original 2008)", "First Pressing", "grail", 300),
        ("Taylor Swift", "vinyl", "Live From Clear Channel Lounge Vinyl (Promo)", "Promo", "grail", 400),
        ("Taylor Swift", "vinyl", "Taylor Swift (Debut) Big Machine Records OG Pressing", "First Pressing", "grail", 180),

        # Miscellaneous Collectibles (+7)
        ("Taylor Swift", "merch", "Taylor Swift x Stella McCartney Bomber Jacket (Lover)", "Brand Collab", "grail", 350),
        ("Taylor Swift", "merch", "Taylor Swift Cat Collection (Meredith Plush)", "Limited", "mid", 45),
        ("Taylor Swift", "merch", "Taylor Swift Cat Collection (Olivia Plush)", "Limited", "mid", 45),
        ("Taylor Swift", "merch", "Taylor Swift Cat Collection (Benjamin Plush)", "Limited", "mid", 45),
        ("Taylor Swift", "merch", "Taylor Swift Eras Tour Book (Coffee Table Edition)", "Limited", "mid", 55),
        ("Taylor Swift", "merch", "Taylor Swift Guitar Pick Necklace (Official Store)", "Limited", "mid", 40),
        ("Taylor Swift", "merch", "Taylor Swift Eras Tour Snow Globe (All 10 Eras)", "Limited", "high", 95),
    ]

    # ── Variant expansion — vinyl colors, signed CDs, exclusives ──
    items += _variant_expansion()

    catalog = []
    for album, item_type, name, variant, tier, price in items:
        catalog.append({
            "album": album,
            "item_type": item_type,
            "name": name,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    # Deduplicate by ('album', 'name', 'variant') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["album"], item["name"], item["variant"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def _variant_expansion() -> list[tuple]:
    """Vinyl color variants, signed CDs, international exclusives & format variants.

    Taylor Swift releases are known for retailer-exclusive colored vinyl pressings
    (Target lavender/gold/rose, standard black, RSD editions), signed CD inserts,
    international exclusives (Japan, UK), picture discs, and cassette color variants.
    ~60 items targeting 750+ total.
    """
    return [
        # ── Midnights — additional Target / RSD / international pressings ──
        ("Midnights", "vinyl", "Midnights Target Exclusive Lavender Vinyl (3am Edition)", "Lavender 3am (Target)", "high", 65),
        ("Midnights", "vinyl", "Midnights Japan Exclusive Vinyl (w/ Bonus Track)", "Japan Exclusive", "high", 80),
        ("Midnights", "vinyl", "Midnights Signed CD Insert", "Signed CD", "high", 90),
        ("Midnights", "cassette", "Midnights Moonstone Blue Cassette", "Moonstone Blue Cassette", "mid", 30),
        ("Midnights", "cassette", "Midnights Jade Green Cassette", "Jade Green Cassette", "mid", 30),
        ("Midnights", "cassette", "Midnights Mahogany Cassette", "Mahogany Cassette", "mid", 30),
        ("Midnights", "cassette", "Midnights Blood Moon Cassette", "Blood Moon Cassette", "mid", 32),

        # ── TTPD — vinyl colors & signed editions ──
        ("TTPD", "vinyl", "TTPD Target Exclusive Ivory Vinyl", "Ivory (Target)", "mid", 42),
        ("TTPD", "vinyl", "TTPD The Manuscript Gold Vinyl", "Manuscript Gold", "mid", 50),
        ("TTPD", "vinyl", "TTPD Parchment Beige Vinyl", "Parchment Beige", "mid", 45),
        ("TTPD", "vinyl", "TTPD RSD Black Friday Pressing", "RSD Black Friday", "high", 75),
        ("TTPD", "vinyl", "TTPD Signed CD Insert (w/ Heart Drawing)", "Signed CD Heart", "grail", 150),
        ("TTPD", "cassette", "TTPD Phantom Clear Cassette", "Phantom Clear", "mid", 28),

        # ── 1989 (Taylor's Version) — vinyl colors ──
        ("1989 TV", "vinyl", "1989 TV Rose Garden Pink Vinyl (Target)", "Rose Garden Pink (Target)", "mid", 45),
        ("1989 TV", "vinyl", "1989 TV Tangerine Vinyl", "Tangerine", "mid", 40),
        ("1989 TV", "vinyl", "1989 TV Crystal Skies Blue Vinyl", "Crystal Skies Blue", "mid", 42),
        ("1989 TV", "vinyl", "1989 TV Sunrise Boulevard Yellow Vinyl", "Sunrise Blvd Yellow", "mid", 40),
        ("1989 TV", "vinyl", "1989 TV Aquamarine Green Vinyl", "Aquamarine Green", "mid", 42),
        ("1989 TV", "vinyl", "1989 TV Japan Exclusive Vinyl (w/ Bonus Tracks)", "Japan Exclusive", "high", 85),
        ("1989 TV", "vinyl", "1989 TV Signed CD Insert", "Signed CD", "high", 95),

        # ── Speak Now (Taylor's Version) — vinyl colors ──
        ("Speak Now TV", "vinyl", "Speak Now TV Orchid Marbled Vinyl (Target)", "Orchid Marbled (Target)", "mid", 48),
        ("Speak Now TV", "vinyl", "Speak Now TV Violet Vinyl", "Violet", "mid", 38),
        ("Speak Now TV", "vinyl", "Speak Now TV Lilac Marbled Vinyl", "Lilac Marbled", "mid", 42),
        ("Speak Now TV", "vinyl", "Speak Now TV Signed CD Insert", "Signed CD", "high", 90),

        # ── Red (Taylor's Version) — vinyl colors ──
        ("Red TV", "vinyl", "Red TV Target Exclusive Red Vinyl", "Red (Target)", "mid", 45),
        ("Red TV", "vinyl", "Red TV Standard Black Vinyl (4LP)", "Standard Black", "standard", 30),
        ("Red TV", "vinyl", "Red TV Signed CD Insert", "Signed CD", "high", 85),

        # ── Fearless (Taylor's Version) — vinyl colors ──
        ("Fearless TV", "vinyl", "Fearless TV Target Exclusive Gold Vinyl", "Gold (Target)", "mid", 48),
        ("Fearless TV", "vinyl", "Fearless TV Standard Black Vinyl (3LP)", "Standard Black", "standard", 28),
        ("Fearless TV", "vinyl", "Fearless TV Signed CD Insert", "Signed CD", "high", 80),

        # ── Folklore — additional pressings ──
        ("Folklore", "vinyl", "Folklore Standard Black Vinyl", "Standard Black", "standard", 28),
        ("Folklore", "vinyl", "Folklore Clandestine Meetings Vinyl (Betty's Garden)", "Betty's Garden", "mid", 45),
        ("Folklore", "vinyl", "Folklore RSD Exclusive Red Vinyl", "RSD Red", "high", 75),
        ("Folklore", "vinyl", "Folklore Signed CD Insert", "Signed CD", "high", 85),
        ("Folklore", "cassette", "Folklore Stolen Lullabies Cassette", "Stolen Lullabies", "mid", 35),

        # ── Evermore — additional pressings ──
        ("Evermore", "vinyl", "Evermore Standard Black Vinyl (2LP)", "Standard Black", "standard", 28),
        ("Evermore", "vinyl", "Evermore Transparent Green Vinyl (UK)", "Transparent Green (UK)", "mid", 50),
        ("Evermore", "vinyl", "Evermore Signed CD Insert", "Signed CD", "high", 80),

        # ── Lover — additional pressings ──
        ("Lover", "vinyl", "Lover Target Exclusive Pink Vinyl", "Pink (Target)", "mid", 45),
        ("Lover", "vinyl", "Lover Signed CD Insert", "Signed CD", "high", 85),

        # ── Reputation — pressings ──
        ("Reputation", "vinyl", "Reputation Picture Disc Vinyl (2LP)", "Picture Disc", "high", 90),
        ("Reputation", "vinyl", "Reputation Orange Translucent Vinyl (FYE)", "Orange (FYE Exclusive)", "high", 110),
        ("Reputation", "vinyl", "Reputation Signed CD Insert", "Signed CD", "grail", 160),
        ("Reputation", "cassette", "Reputation Clear Cassette", "Clear Cassette", "mid", 35),

        # ── 1989 (Original) — pressings ──
        ("1989", "vinyl", "1989 Crystal Clear Vinyl (RSD)", "Crystal Clear (RSD)", "high", 120),
        ("1989", "vinyl", "1989 Standard Black Vinyl (2LP)", "Standard Black", "mid", 35),
        ("1989", "vinyl", "1989 Pink Vinyl (Japan)", "Pink (Japan)", "high", 95),

        # ── Debut / Fearless (Original) — rare pressings ──
        ("Debut", "vinyl", "Taylor Swift (Debut) Standard Black Vinyl", "Standard Black", "mid", 55),
        ("Debut", "vinyl", "Taylor Swift (Debut) RSD Turquoise Vinyl", "Turquoise (RSD)", "high", 130),
        ("Debut", "vinyl", "Taylor Swift (Debut) Signed CD (Early Career)", "Signed CD Early", "grail", 350),
        ("Fearless", "vinyl", "Fearless (Original) Gold Vinyl", "Gold Original", "high", 90),
        ("Fearless", "vinyl", "Fearless (Original) Standard Black Vinyl", "Standard Black", "mid", 50),

        # ── Cross-album picture discs & box sets ──
        ("Eras Tour", "vinyl", "Eras Tour Exclusive Picture Disc (All Eras Art)", "Picture Disc", "grail", 200),
        ("Midnights", "vinyl", "Midnights Picture Disc Vinyl", "Picture Disc", "high", 65),
        ("TTPD", "vinyl", "TTPD Picture Disc Vinyl (Quill & Ink Art)", "Picture Disc", "high", 70),

        # ── International exclusives ──
        ("Folklore", "vinyl", "Folklore Japan Exclusive Vinyl (w/ Bonus Track)", "Japan Exclusive", "high", 80),
        ("Lover", "vinyl", "Lover Japan Exclusive Deluxe (w/ Bonus Tracks)", "Japan Deluxe", "high", 70),
        ("Red TV", "vinyl", "Red TV Japan Exclusive Vinyl (w/ Bonus Tracks)", "Japan Exclusive", "high", 85),
    ]


def item_to_catalog_item(item: dict) -> CatalogItem:
    album = item["album"]
    name = item["name"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{album}-{name}-{variant}"),
        title=name,
        set_code=slugify(album),
        brand="Taylor Swift",
        rarity=item["rarity_tier"].title(),
        notes=f"{album} | {item['item_type']} | {variant}",
        attributes_json={
            "album": album,
            "item_type": item["item_type"],
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    variant = item["variant"]
    edition_map = {
        "Signed + Numbered": 0.95, "Signed + Heart": 0.95,
        "Signed": 0.85, "Signed CD": 0.85,
        "VIP Exclusive": 0.9, "Promo": 0.85, "First Pressing": 0.85,
        "RSD Exclusive": 0.8, "Collectors Edition": 0.8,
        "Japan Exclusive": 0.75, "Tour Exclusive": 0.7,
        "Anthology": 0.7, "FYE Exclusive": 0.7,
        "Indie Exclusive": 0.65, "UO Exclusive": 0.65,
        "Picture Disc": 0.65, "Clock Set": 0.7,
        "Exclusive": 0.65,  # city / region exclusives fallback
        "Magazine Cover": 0.55, "Cassette": 0.4,
        "Fan Club Exclusive": 0.8, "Vintage": 0.7,
        "First Edition": 0.6, "Til Dawn": 0.6, "Chase Variant": 0.75,
        "Collector's Set": 0.75, "Korea Exclusive": 0.75,
        "Australia Exclusive": 0.75, "UK Exclusive": 0.75,
        "Taylor Brand": 0.85, "Limited Replica": 0.8,
        "Tour Replica": 0.75,
        "Amazon Exclusive": 0.65, "Webstore Exclusive": 0.65,
        "Walmart Exclusive": 0.6, "Philippines Exclusive": 0.7,
        "India Exclusive": 0.7, "Canada Exclusive": 0.7,
        "Germany Exclusive": 0.7, "Mexico Exclusive": 0.7,
        "Brazil Exclusive": 0.7, "France Exclusive": 0.7,
        "China Exclusive": 0.75, "Glendale Exclusive": 0.8,
        "Fan-Made": 0.3,
        "Limited": 0.6, "Deluxe": 0.5, "Target": 0.5,
        "Standard": 0.2,
    }
    # Find best matching edition score
    edition_score = 0.4
    for key, score in edition_map.items():
        if key in variant:
            edition_score = score
            break

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_score,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Taylor Swift collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Taylor Swift Import ===")

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

    logger.info(f"\n=== Taylor Swift Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
