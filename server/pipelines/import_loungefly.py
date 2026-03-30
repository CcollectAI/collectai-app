"""
Import Loungefly bags & accessories catalog.

Layer 1 (Catalog):  Curated Loungefly items → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Disney exclusive backpacks (active & vaulted)
- BoxLunch exclusives
- Hot Topic exclusives
- Marvel / Star Wars lines
- Halloween / holiday limited editions
- Funko Shop exclusives
- Vintage pre-Funko era Loungefly
- Sanrio lines
- Pixar collections
- Horror franchise collections
- Pokemon collections
- Wallets & crossbody bags
- Seasonal & vaulted exclusives

Usage:
    python -m pipelines.import_loungefly [--dry-run]
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

CATEGORY = "loungefly"


def get_curated_catalog() -> list[dict]:
    """Curated Loungefly bags & accessories catalog (500+ items)."""

    # (franchise, name, item_type, exclusive, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (100-200), mid (50-100), standard (<50)

    items = [
        # Disney exclusive backpacks – active
        ("Disney", "Cinderella Castle Sequin Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 75),
        ("Disney", "Sleeping Beauty Castle Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 70),
        ("Disney", "Mickey Mouse Holographic Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 65),
        ("Disney", "Stitch Shoppe Ariel Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Disney", "Bambi Scenes Mini Backpack", "Mini Backpack", "Standard", "standard", 45),

        # Disney exclusive backpacks – vaulted
        ("Disney", "Villains Scene AOP Mini Backpack", "Mini Backpack", "Vaulted", "high", 180),
        ("Disney", "Fantasia Sorcerer Mickey Sequin Mini Backpack", "Mini Backpack", "Vaulted", "high", 200),
        ("Disney", "Snow White Evil Queen Sequin Mini Backpack", "Mini Backpack", "Vaulted", "high", 160),
        ("Disney", "Haunted Mansion Black Widow Bride Mini Backpack", "Mini Backpack", "Vaulted", "grail", 280),
        ("Disney", "Orange Bird Disney Parks Exclusive Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 250),

        # BoxLunch exclusives
        ("Disney", "Wall-E & Eve Boot Plant Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 70),
        ("Disney", "Up Adventure Book Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Studio Ghibli", "Spirited Away No-Face Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 72),
        ("Studio Ghibli", "My Neighbor Totoro Catbus Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 68),
        ("Pokemon", "Eevee Evolutions Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),

        # Hot Topic exclusives
        ("Disney", "Maleficent Dragon Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Sanrio", "Hello Kitty Monster Costumes Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 50),
        ("Disney", "Nightmare Before Christmas Blacklight Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Disney", "Ursula Iridescent Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),

        # Marvel / Star Wars lines
        ("Marvel", "Iron Man Mark 85 Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Marvel", "Spider-Verse Miles Morales Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Marvel", "Thanos Infinity Gauntlet Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Star Wars", "Grogu (Baby Yoda) Cradle Mini Backpack", "Mini Backpack", "Standard", "standard", 49),
        ("Star Wars", "Darth Vader Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Star Wars", "Princess Leia Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 45),

        # Halloween / holiday limited editions
        ("Disney", "Mickey & Minnie Halloween Candy Corn Mini Backpack", "Mini Backpack", "Halloween LE", "high", 100),
        ("Disney", "Nightmare Before Christmas Pumpkin King LE Mini Backpack", "Mini Backpack", "Halloween LE", "high", 110),
        ("Disney", "Mickey Mouse Christmas Ugly Sweater Mini Backpack", "Mini Backpack", "Holiday LE", "mid", 85),
        ("Disney", "Stitch Holiday Gingerbread Mini Backpack", "Mini Backpack", "Holiday LE", "mid", 80),

        # Funko Shop exclusives
        ("Funko", "Freddy Funko Cosplay Mini Backpack", "Mini Backpack", "Funko Shop", "high", 120),
        ("Disney", "Fantasia Sorcerer Mickey Funko Pop! Mini Backpack", "Mini Backpack", "Funko Shop", "high", 130),
        ("Marvel", "Venom Blacklight Mini Backpack", "Mini Backpack", "Funko Shop", "high", 100),
        ("Disney", "Alice in Wonderland Blacklight Mini Backpack", "Mini Backpack", "Funko Shop", "high", 140),

        # Vintage pre-Funko era Loungefly
        ("Disney", "Vintage Mickey Embossed Denim Bag", "Shoulder Bag", "Pre-Funko", "grail", 220),
        ("Hello Kitty", "Hello Kitty Vintage Studded Crossbody", "Crossbody Bag", "Pre-Funko", "high", 150),
        ("Disney", "Vintage Tinker Bell Patent Leather Bag", "Shoulder Bag", "Pre-Funko", "high", 180),
        ("Skull & Roses", "Loungefly OG Skull Roses Embroidered Bag", "Shoulder Bag", "Pre-Funko", "grail", 250),
        ("Hello Kitty", "Hello Kitty Quilted Vintage Tote", "Tote Bag", "Pre-Funko", "high", 130),

        # ── NEW ITEMS BELOW ──────────────────────────────────────────

        # More Disney (+8)
        ("Disney", "Cinderella Carriage Sequin Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 72),
        ("Disney", "Rapunzel Tangled Tower Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Disney", "Moana Kakamora AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "Lilo & Stitch Pineapple AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Disney", "Bambi Flower & Thumper Spring Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "Dumbo Circus Tent Mini Backpack", "Mini Backpack", "Standard", "standard", 44),
        ("Disney", "Fantasia Chernabog Glow Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 62),
        ("Disney", "Alice in Wonderland Tea Party AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 47),

        # Marvel (+6)
        ("Marvel", "Spider-Man Japanese TV Series Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Marvel", "Iron Man Arc Reactor Glow Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Marvel", "Captain America 80th Anniversary Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Marvel", "Loki President Loki Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Marvel", "Scarlet Witch Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Marvel", "Black Panther Wakanda Forever Mini Backpack", "Mini Backpack", "Standard", "standard", 46),

        # Star Wars (+6)
        ("Star Wars", "Grogu Ramen Bowl Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Star Wars", "Boba Fett Jetpack Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 49),
        ("Star Wars", "Darth Vader Floral AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Star Wars", "Princess Leia Hoth Cosplay Mini Backpack", "Mini Backpack", "Vaulted", "high", 110),
        ("Star Wars", "Ahsoka Tano Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Star Wars", "Ewok Celebration AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),

        # Sanrio (+5)
        ("Sanrio", "Hello Kitty 50th Anniversary Sequin Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Sanrio", "My Melody Floral AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 42),
        ("Sanrio", "Cinnamoroll Cloudscape Mini Backpack", "Mini Backpack", "Standard", "standard", 40),
        ("Sanrio", "Kuromi & My Melody Blacklight Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Sanrio", "Pompompurin Pudding AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 38),

        # Pixar (+5)
        ("Pixar", "Toy Story Aliens Claw Machine Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 68),
        ("Pixar", "Monsters Inc Sully Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Pixar", "Up Ellie Badge Adventure Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Pixar", "Wall-E & Eve Galaxy Date Night Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Pixar", "Inside Out Core Memories AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 44),

        # Horror (+4)
        ("Horror", "Chucky Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Horror", "Beetlejuice Sandworm Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Horror", "Nightmare on Elm Street Freddy Krueger Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Horror", "Friday the 13th Camp Crystal Lake Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 56),

        # Pokemon (+4)
        ("Pokemon", "Eevee Evolutions Floral AOP Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Pokemon", "Pikachu Lightning Bolt Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Pokemon", "Bulbasaur Botanical Garden Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Pokemon", "Snorlax Sleeping AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),

        # Wallets & Crossbody (+5)
        ("Disney", "Mickey & Minnie Date Night Crossbody Bag", "Crossbody Bag", "Standard", "standard", 42),
        ("Disney", "Villains AOP Zip-Around Wallet", "Wallet", "Standard", "standard", 32),
        ("Sanrio", "Hello Kitty 50th Anniversary Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 35),
        ("Marvel", "Spider-Man Miles Morales Card Holder", "Card Holder", "Standard", "standard", 22),
        ("Star Wars", "Grogu Precious Cargo Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 40),

        # Seasonal / Vaulted (+5)
        ("Disney", "Minnie Mouse Witch Halloween Sequin Mini Backpack", "Mini Backpack", "Halloween LE", "high", 120),
        ("Disney", "Mickey Mouse Santa Christmas Mini Backpack", "Mini Backpack", "Holiday LE", "high", 105),
        ("Disney", "Mickey & Minnie Valentine Heart AOP Mini Backpack", "Mini Backpack", "Valentine LE", "mid", 78),
        ("Disney", "Daisy Duck Easter Egg Mini Backpack", "Mini Backpack", "Easter LE", "mid", 72),
        ("Disney", "Walt Disney World 50th Anniversary Sequin Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 320),

        # === ROUND 2 — 37 new items ===

        # Sanrio — Exclusive Patterns
        ("Sanrio", "Cinnamoroll Plush Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Sanrio", "Pompompurin Cafe AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 42),
        ("Sanrio", "Kuromi Halloween Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Sanrio", "Cinnamoroll x My Melody Dreamy Sky Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),

        # Studio Ghibli
        ("Studio Ghibli", "My Neighbor Totoro Forest Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 70),
        ("Studio Ghibli", "Kiki's Delivery Service Jiji Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 68),
        ("Studio Ghibli", "Spirited Away Bath House Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 75),

        # Nintendo
        ("Nintendo", "Super Mario Bros. Question Block Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Nintendo", "Legend of Zelda Hyrule Map AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Nintendo", "Animal Crossing New Horizons Characters AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 48),

        # Halloween / Christmas Seasonals
        ("Disney", "Nightmare Before Christmas Zero Glow Mini Backpack", "Mini Backpack", "Halloween LE", "high", 115),
        ("Disney", "Hocus Pocus Sanderson Sisters Mini Backpack", "Mini Backpack", "Halloween LE", "high", 125),
        ("Disney", "Nightmare Before Christmas Mayor Two-Face Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Disney", "Mickey & Friends Holiday Caroling Mini Backpack", "Mini Backpack", "Holiday LE", "mid", 82),

        # Universal Monsters
        ("Universal Monsters", "Bride of Frankenstein Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Universal Monsters", "Creature from the Black Lagoon Scene Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 62),
        ("Universal Monsters", "Dracula Classic Poster Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),

        # Nickelodeon
        ("Nickelodeon", "Rugrats Reptar Bar AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Nickelodeon", "Avatar: The Last Airbender Appa Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Nickelodeon", "Avatar: The Last Airbender Four Nations AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 48),

        # BoxLunch / Hot Topic Exclusives
        ("Disney", "Encanto Mirabel Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "Coco Land of the Dead Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),

        # Jurassic Park
        ("Jurassic Park", "Jurassic Park Logo Amber AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Jurassic Park", "Jurassic Park Gates Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 48),

        # Wallets — Matching Sets
        ("Disney", "Haunted Mansion Wallpaper Zip-Around Wallet", "Wallet", "Disney Parks", "mid", 52),
        ("Sanrio", "Kuromi & My Melody Blacklight Zip-Around Wallet", "Wallet", "Hot Topic", "standard", 38),
        ("Studio Ghibli", "Spirited Away No-Face Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),

        # Crossbody Bags
        ("Disney", "Cinderella Carriage Crossbody Bag", "Crossbody Bag", "Disney Parks", "mid", 65),
        ("Pokemon", "Pikachu Pokeball Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),

        # Disney Parks Exclusive
        ("Disney", "Haunted Mansion Hitchhiking Ghosts Mini Backpack", "Mini Backpack", "Disney Parks", "high", 110),
        ("Disney", "Space Mountain Retro Poster Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 78),
        ("Disney", "EPCOT Spaceship Earth Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 72),

        # Convention Exclusives (SDCC, NYCC, D23)
        ("Disney", "Sorcerer Mickey Fantasia SDCC Exclusive Mini Backpack", "Mini Backpack", "SDCC", "grail", 280),
        ("Marvel", "Iron Man Mark I SDCC Exclusive Mini Backpack", "Mini Backpack", "SDCC", "grail", 250),
        ("Disney", "Villains Stained Glass NYCC Exclusive Mini Backpack", "Mini Backpack", "NYCC", "grail", 260),
        ("Disney", "100 Years of Disney D23 Exclusive Mini Backpack", "Mini Backpack", "D23", "grail", 300),
        ("Star Wars", "Ahsoka Tano Clone Wars NYCC Exclusive Mini Backpack", "Mini Backpack", "NYCC", "grail", 240),

        # === ROUND 3 — 20 new items ===

        # DC Comics
        ("DC Comics", "Batman Arkham Asylum Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("DC Comics", "Harley Quinn Animated Series Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("DC Comics", "Wonder Woman Golden Armor Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 46),

        # Harry Potter
        ("Harry Potter", "Hogwarts Castle Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Harry Potter", "Marauder's Map AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Harry Potter", "Hedwig Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Harry Potter", "Diagon Alley Scene Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),

        # Dreamworks / Misc Franchises
        ("Dreamworks", "Shrek Fairytale Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Dreamworks", "How to Train Your Dragon Toothless Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 45),

        # Disney Villains
        ("Disney", "Cruella de Vil Dalmatian Spots AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Disney", "Jafar Snake Staff Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),

        # More Wallets & Accessories
        ("Disney", "Sleeping Beauty Aurora Sequin Zip-Around Wallet", "Wallet", "Disney Parks", "mid", 48),
        ("Pokemon", "Gengar Ghost Type AOP Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 35),
        ("Marvel", "Avengers Endgame Group Crossbody Bag", "Crossbody Bag", "Standard", "standard", 40),

        # Vaulted Grails
        ("Disney", "Main Street Electrical Parade Glow Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 350),
        ("Disney", "Enchanted Tiki Room 60th Anniversary Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 275),

        # Anime / Pop Culture
        ("Demon Slayer", "Tanjiro Kamado Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("One Piece", "Straw Hat Crew AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Naruto", "Akatsuki Cloud AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),

        # Backpack Pencil Case / Cardholder
        ("Disney", "Mickey Mouse Rainbow Sequin Card Holder", "Card Holder", "Disney Parks", "standard", 25),

        # === ROUND 4 — 67 new items ===

        # Disney Princess (+6)
        ("Disney", "Snow White Apple Sequin Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 68),
        ("Disney", "Belle Enchanted Rose Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Disney", "Jasmine Magic Carpet Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Disney", "Mulan Warrior Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 56),
        ("Disney", "Pocahontas Colors of the Wind Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Disney", "Tiana Princess & the Frog Bayou Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),

        # Disney Rides & Attractions (+5)
        ("Disney", "Splash Mountain Last Ride Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 340),
        ("Disney", "Pirates of the Caribbean Map AOP Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 75),
        ("Disney", "Jungle Cruise Vintage Poster Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 70),
        ("Disney", "It's a Small World Clockface Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 72),
        ("Disney", "Big Thunder Mountain Railroad Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 68),

        # Marvel Expanded (+5)
        ("Marvel", "Deadpool & Wolverine Best Buds Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Marvel", "Moon Knight Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Marvel", "Doctor Strange Multiverse Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Marvel", "Groot Floral AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Marvel", "X-Men '97 Retro AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),

        # Star Wars Expanded (+4)
        ("Star Wars", "Padme Amidala Queen Outfit Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Star Wars", "R2-D2 & C-3PO Tatooine Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Star Wars", "Mandalorian Helmet Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 49),
        ("Star Wars", "Chewbacca Fur Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),

        # Sanrio Expanded (+4)
        ("Sanrio", "Keroppi Pond Scene AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 40),
        ("Sanrio", "Badtz-Maru Attitude AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 50),
        ("Sanrio", "Little Twin Stars Galaxy Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Sanrio", "Gudetama Lazy Egg AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 42),

        # Horror Expanded (+4)
        ("Horror", "Ghostface Scream Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Horror", "Pennywise IT Chapter Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Horror", "Texas Chainsaw Massacre Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 56),
        ("Horror", "Bride of Chucky Heart Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),

        # Pokemon Expanded (+4)
        ("Pokemon", "Charizard Fire Blast Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Pokemon", "Gengar Glow-in-Dark Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Pokemon", "Eeveelutions Stained Glass Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Pokemon", "Psyduck Headache AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 45),

        # Pixar Expanded (+3)
        ("Pixar", "Ratatouille Little Chef Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Pixar", "Finding Nemo Ocean Scene AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 44),
        ("Pixar", "Coco Miguel Guitar Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),

        # Studio Ghibli Expanded (+3)
        ("Studio Ghibli", "Princess Mononoke Forest Spirit Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 72),
        ("Studio Ghibli", "Howl's Moving Castle Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 75),
        ("Studio Ghibli", "Ponyo Sea Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),

        # Harry Potter Expanded (+3)
        ("Harry Potter", "Sorting Hat Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Harry Potter", "Honeydukes Sweet Shop AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Harry Potter", "Quidditch World Cup AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 48),

        # Nickelodeon Expanded (+3)
        ("Nickelodeon", "SpongeBob SquarePants Pineapple House Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Nickelodeon", "Fairly OddParents Cosmo & Wanda Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Nickelodeon", "Invader Zim GIR Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),

        # Wallets & Accessories Round 2 (+6)
        ("Disney", "Tinker Bell Iridescent Zip-Around Wallet", "Wallet", "Disney Parks", "mid", 48),
        ("Marvel", "Thor Mjolnir Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),
        ("Star Wars", "Lightsaber Duel Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Pokemon", "Jigglypuff Microphone Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 40),
        ("Sanrio", "Hello Kitty Strawberry Milk Card Holder", "Card Holder", "Standard", "standard", 22),
        ("Disney", "Aristocats Marie Floral Crossbody Bag", "Crossbody Bag", "Standard", "standard", 38),

        # Convention Exclusives Round 2 (+4)
        ("Marvel", "Spider-Man 2099 SDCC Exclusive Mini Backpack", "Mini Backpack", "SDCC", "grail", 260),
        ("Disney", "Tinker Bell Peter Pan NYCC Exclusive Mini Backpack", "Mini Backpack", "NYCC", "grail", 230),
        ("Star Wars", "Darth Maul Duel of the Fates SDCC Mini Backpack", "Mini Backpack", "SDCC", "grail", 270),
        ("Sanrio", "Hello Kitty x Tokidoki D23 Exclusive Mini Backpack", "Mini Backpack", "D23", "grail", 290),

        # Vaulted Grails Round 2 (+3)
        ("Disney", "Club 33 Exclusive Sequin Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 400),
        ("Disney", "Tower of Terror Final Drop Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 310),
        ("Disney", "20,000 Leagues Under the Sea Nautilus Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 290),

        # Anime / Pop Culture Round 2 (+5)
        ("Jujutsu Kaisen", "Gojo Satoru Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("My Hero Academia", "Deku Full Cowling AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Dragon Ball Z", "Shenron Dragon Balls AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Sailor Moon", "Sailor Moon Compact Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Cowboy Bebop", "Spike Spiegel Silhouette AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),

        # Nintendo Expanded (+4)
        ("Nintendo", "Kirby Floating Star AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Nintendo", "Yoshi Egg Pattern AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Nintendo", "Donkey Kong Retro Barrel Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Nintendo", "Splatoon Splat AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 48),

        # === ROUND 5 — Disney Deep Dive (Every Princess, Villain, Pixar) ===

        # Disney Princesses — Additional
        ("Disney", "Ariel Underwater Grotto Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "Ariel Pink Dress Transformation Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 72),
        ("Disney", "Merida Brave Celtic Knot AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Disney", "Rapunzel Floating Lanterns Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Disney", "Moana Te Fiti Heart Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "Aurora Blue/Pink Dress Reversible Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 68),
        ("Disney", "Cinderella Glass Slipper Iridescent Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 75),
        ("Disney", "Snow White Poison Apple Glow Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Disney", "Tiana Naveen Frog Kiss Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "Raya and the Last Dragon Sisu Mini Backpack", "Mini Backpack", "Standard", "standard", 45),

        # Disney Villains — Complete
        ("Disney", "Maleficent Flames Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Disney", "Evil Queen Magic Mirror Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Disney", "Hades Ember Glow Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Disney", "Captain Hook Pirate Ship Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Disney", "Gaston Mirror Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "Scar Pride Rock Scene Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 56),
        ("Disney", "Mother Gothel Tower Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Disney", "Yzma & Kronk Poison Lab Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "Dr. Facilier Tarot Cards AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Disney", "Cruella de Vil Car Chase Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),

        # Pixar — All Major Films
        ("Pixar", "Brave Merida Bear Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Pixar", "Turning Red Mei Panda Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Pixar", "Luca Sea Monster Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Pixar", "Soul Joe Gardner Jazz AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Pixar", "Cars Lightning McQueen Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 44),
        ("Pixar", "The Incredibles Logo AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 44),
        ("Pixar", "A Bug's Life Flik Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Pixar", "Toy Story Pizza Planet Truck Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Pixar", "Elemental Ember & Wade Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Pixar", "Inside Out 2 Anxiety AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 48),

        # Disney Parks Attractions — Additional
        ("Disney", "Tower of Terror Hollywood Tower Hotel Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 78),
        ("Disney", "Haunted Mansion Wallpaper AOP Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 75),
        ("Disney", "Carousel of Progress Scene Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 70),
        ("Disney", "Tiki Room Jose Parrot Cosplay Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 68),
        ("Disney", "Country Bear Jamboree Scene Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 68),
        ("Disney", "Expedition Everest Yeti Scene Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 72),
        ("Disney", "Figment EPCOT Imagination Institute Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 78),
        ("Disney", "Star Tours C-3PO Cosplay Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 72),

        # === ROUND 6 — All Other Licenses ===

        # Marvel — Expanded
        ("Marvel", "Wolverine Classic Yellow Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Marvel", "Hulk Smash AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Marvel", "Ms. Marvel Kamala Khan Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Marvel", "She-Hulk Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Marvel", "Loki Alligator Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Marvel", "Guardians of the Galaxy Cassette Tape Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Marvel", "Captain Marvel Binary Glow Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Marvel", "Ant-Man Quantumania AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Marvel", "Daredevil Red Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Marvel", "Punisher Skull Logo Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 50),

        # Star Wars — All Eras
        ("Star Wars", "Rey Scavenger Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Star Wars", "Kylo Ren Helmet Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Star Wars", "Han Solo Vest Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Star Wars", "Lando Calrissian Cape Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Star Wars", "Obi-Wan Kenobi Clone Wars Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Star Wars", "Yoda Dagobah Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Star Wars", "Emperor Palpatine Dark Side Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Star Wars", "Jabba's Palace Scene AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Star Wars", "AT-AT Walker Scene Hoth Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Star Wars", "Stormtrooper Floral AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),

        # Sanrio — All Characters
        ("Sanrio", "Aggretsuko Rage AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Sanrio", "Chococat Skateboard AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 42),
        ("Sanrio", "Tuxedo Sam Penguin Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 40),
        ("Sanrio", "Hangyodon Deep Sea AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Sanrio", "Hello Kitty and Friends Carnival AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Sanrio", "My Melody Kuromi Flower Crown Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Sanrio", "Cinnamoroll Clouds Sequin Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Sanrio", "Hello Kitty Town AOP Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 45),

        # Pokemon — All Generations
        ("Pokemon", "Mewtwo Strikes Back Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Pokemon", "Umbreon & Espeon Eeveelutions Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Pokemon", "Starter Pokemon Gen 1 AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Pokemon", "Legendary Birds Trio AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Pokemon", "Togepi & Cleffa Baby Pokemon AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Pokemon", "Ghost Type Halloween AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Pokemon", "Paldea Starters AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Pokemon", "Ditto Transform AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),

        # Harry Potter — Expanded
        ("Harry Potter", "Hogwarts Houses Four Panel Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Harry Potter", "Gryffindor Crest Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Harry Potter", "Slytherin Crest Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Harry Potter", "Ravenclaw Crest Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Harry Potter", "Hufflepuff Crest Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Harry Potter", "Dobby Sock Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Harry Potter", "Platform 9 3/4 Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Harry Potter", "Dumbledore's Army AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Harry Potter", "Diagon Alley Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Harry Potter", "Draco Malfoy Mini Backpack", "Mini Backpack", "Exclusive", "high", 138),
        ("Harry Potter", "Yule Ball Mini Backpack", "Mini Backpack", "Limited", "high", 110),

        # Lord of the Rings
        ("Lord of the Rings", "The One Ring Script AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Lord of the Rings", "The Shire Map Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Lord of the Rings", "Gandalf Staff Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Lord of the Rings", "Fellowship Silhouette AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),

        # Horror — Full Collection
        ("Horror", "Michael Myers Halloween Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Horror", "Exorcist Regan Scene Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Horror", "Hellraiser Pinhead Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Horror", "Scream TV Static Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Horror", "Alien Xenomorph Egg Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Horror", "Predator Camouflage AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),

        # DC Comics — Expanded
        ("DC Comics", "Superman Daily Planet Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("DC Comics", "Joker Ha Ha Ha AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("DC Comics", "Catwoman Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("DC Comics", "Poison Ivy Botanical AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("DC Comics", "Aquaman CollectAI Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("DC Comics", "Flash Lightning Bolt Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("DC Comics", "Teen Titans Go! AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 50),

        # Anime — Additional Series
        ("Attack on Titan", "Survey Corps Wings AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Chainsaw Man", "Pochita Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Spy x Family", "Anya Forger Peanuts AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Hunter x Hunter", "Gon & Killua Scene Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Sailor Moon", "Luna & Artemis Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Inuyasha", "Inuyasha Robe of the Fire Rat Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Fullmetal Alchemist", "Transmutation Circle AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Tokyo Ghoul", "Kaneki Mask Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),

        # Nickelodeon — Full Lineup
        ("Nickelodeon", "Rugrats Tommy Pickles Reptar AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Nickelodeon", "Hey Arnold! Football Head AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Nickelodeon", "Danny Phantom Ghost Zone Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Nickelodeon", "Catdog Split Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Nickelodeon", "Wild Thornberrys Donnie AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Nickelodeon", "Ren & Stimpy Space Madness Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),

        # === ROUND 7 — All Product Types (Wallets, Crossbodies, Totes, Pins) ===

        # Wallets — Full Collection
        ("Disney", "Cinderella Castle Sequin Zip-Around Wallet", "Wallet", "Disney Parks", "mid", 52),
        ("Disney", "Villains Icons AOP Zip-Around Wallet", "Wallet", "Hot Topic", "standard", 36),
        ("Disney", "Stitch Pineapple Flap Wallet", "Wallet", "Standard", "standard", 32),
        ("Disney", "Bambi Scenes Zip-Around Wallet", "Wallet", "Standard", "standard", 32),
        ("Marvel", "Spider-Man Web Shooter Zip-Around Wallet", "Wallet", "Standard", "standard", 34),
        ("Marvel", "Avengers Endgame AOP Zip-Around Wallet", "Wallet", "Standard", "standard", 34),
        ("Star Wars", "Mandalorian Beskar Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Star Wars", "Grogu Snack Time Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Pokemon", "Pikachu Thunderbolt AOP Zip-Around Wallet", "Wallet", "Standard", "standard", 34),
        ("Pokemon", "Eevee Evolutions Panel Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Harry Potter", "Hogwarts Express Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Sanrio", "Pompompurin Cafe Zip-Around Wallet", "Wallet", "Standard", "standard", 32),
        ("Sanrio", "Cinnamoroll Cloud Zip-Around Wallet", "Wallet", "Standard", "standard", 32),
        ("Horror", "Ghostface Scream Zip-Around Wallet", "Wallet", "Hot Topic", "standard", 36),
        ("Studio Ghibli", "Totoro Forest Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 38),

        # Crossbody Bags — Full Collection
        ("Disney", "Rapunzel Tower Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),
        ("Disney", "Ariel Dinglehopper Crossbody Bag", "Crossbody Bag", "Standard", "standard", 38),
        ("Disney", "Haunted Mansion Doom Buggy Crossbody Bag", "Crossbody Bag", "Disney Parks", "mid", 55),
        ("Disney", "Enchanted Rose Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),
        ("Marvel", "Spider-Man Mask Crossbody Bag", "Crossbody Bag", "Standard", "standard", 38),
        ("Star Wars", "R2-D2 Cosplay Crossbody Bag", "Crossbody Bag", "Standard", "standard", 40),
        ("Star Wars", "Death Star Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),
        ("Sanrio", "Cinnamoroll Cloud Crossbody Bag", "Crossbody Bag", "Standard", "standard", 36),
        ("Sanrio", "Kuromi Skull Crossbody Bag", "Crossbody Bag", "Hot Topic", "standard", 38),
        ("Pokemon", "Great Ball Crossbody Bag", "Crossbody Bag", "Standard", "standard", 38),
        ("Harry Potter", "Golden Snitch Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),
        ("Studio Ghibli", "Spirited Away Soot Sprite Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),

        # Tote Bags
        ("Disney", "Haunted Mansion Canvas Tote Bag", "Tote Bag", "Disney Parks", "mid", 52),
        ("Disney", "Mickey Mouse Retro AOP Canvas Tote", "Tote Bag", "Standard", "standard", 35),
        ("Disney", "Stitch Aloha AOP Canvas Tote", "Tote Bag", "Standard", "standard", 35),
        ("Marvel", "Marvel Comics AOP Canvas Tote", "Tote Bag", "Standard", "standard", 32),
        ("Sanrio", "Hello Kitty Strawberry Fields Tote", "Tote Bag", "Standard", "standard", 32),
        ("Pokemon", "Pikachu & Eevee Canvas Tote", "Tote Bag", "Standard", "standard", 32),

        # Enamel Pin Sets
        ("Disney", "Haunted Mansion Hitchhiking Ghosts Enamel Pin Set", "Pin Set", "Disney Parks", "mid", 28),
        ("Disney", "Nightmare Before Christmas Glow Pin Set", "Pin Set", "Hot Topic", "standard", 22),
        ("Disney", "Disney Villains Tarot Enamel Pin Set", "Pin Set", "BoxLunch", "standard", 24),
        ("Disney", "Disney Princesses Floral Enamel Pin Set", "Pin Set", "BoxLunch", "standard", 22),
        ("Marvel", "Avengers Icons Enamel Pin Set", "Pin Set", "Standard", "standard", 20),
        ("Star Wars", "Lightsaber Collection Enamel Pin Set", "Pin Set", "BoxLunch", "standard", 22),
        ("Sanrio", "Hello Kitty 50th Anniversary Pin Set", "Pin Set", "BoxLunch", "standard", 24),
        ("Pokemon", "Starter Pokemon Enamel Pin Set", "Pin Set", "BoxLunch", "standard", 22),
        ("Harry Potter", "Hogwarts Crest Enamel Pin Set", "Pin Set", "Standard", "standard", 20),
        ("Studio Ghibli", "Totoro & Soot Sprites Enamel Pin Set", "Pin Set", "BoxLunch", "standard", 24),

        # === ROUND 8 — SDCC / Convention / Amazon / Loungefly Exclusives ===

        # SDCC Exclusives — Additional
        ("Disney", "Cheshire Cat Blacklight SDCC Mini Backpack", "Mini Backpack", "SDCC", "grail", 275),
        ("Marvel", "Venom Carnage Maximum Carnage SDCC Mini Backpack", "Mini Backpack", "SDCC", "grail", 260),
        ("Star Wars", "Mace Windu Lightsaber SDCC Mini Backpack", "Mini Backpack", "SDCC", "grail", 245),
        ("DC Comics", "Batman Beyond SDCC Exclusive Mini Backpack", "Mini Backpack", "SDCC", "grail", 250),

        # Amazon Exclusives
        ("Disney", "Mickey Mouse Rainbow Pride AOP Mini Backpack", "Mini Backpack", "Amazon", "mid", 55),
        ("Marvel", "Black Widow Silhouette Mini Backpack", "Mini Backpack", "Amazon", "mid", 52),
        ("Star Wars", "Grogu Force Levitate Mini Backpack", "Mini Backpack", "Amazon", "mid", 55),
        ("Pokemon", "Pikachu Pokeball Logo Mini Backpack", "Mini Backpack", "Amazon", "mid", 52),

        # Loungefly Website Exclusives
        ("Disney", "Stitch Angel Love AOP Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 58),
        ("Disney", "Tinker Bell Fairy Dust Sequin Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 62),
        ("Disney", "Minnie Mouse Polka Dot Sequin Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 60),
        ("Marvel", "Spider-Gwen Glow Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 58),
        ("Sanrio", "Hello Kitty 50th Metallic Gold Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 65),
        ("Pokemon", "Pikachu Electric Glow Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 58),

        # Vaulted Grails — Additional
        ("Disney", "Toontown Roger Rabbit Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 310),
        ("Disney", "Discovery Island Extinct Attraction Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 330),
        ("Disney", "Mr. Toad's Wild Ride Scene Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 290),
        ("Disney", "Alien Encounter Stitch Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 320),

        # === ROUND 9 — More Licenses & Product Types ===

        # Disney Classic Films
        ("Disney", "Lady and the Tramp Spaghetti Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "101 Dalmatians Puppy Pile AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Disney", "The Fox and the Hound Best Friends Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "Robin Hood OO-De-Lally Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "Oliver & Company NYC Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Disney", "The Rescuers Down Under Albatross Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "Hercules Mt Olympus Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "Emperor's New Groove Llama AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Disney", "Tarzan Jungle Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Disney", "CollectAI Crystal Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "Treasure Planet Map AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "Wreck-It Ralph Sugar Rush AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Disney", "Zootopia City Scene AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Disney", "Big Hero 6 Baymax Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Disney", "Frozen Elsa Ice Castle Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "Frozen 2 Enchanted Forest Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Disney", "The Jungle Book Baloo & Mowgli Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "The Aristocats Piano Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "Peter Pan Neverland Map Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Disney", "Pinocchio Jiminy Cricket Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "The Sword in the Stone Merlin Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "Winnie the Pooh Hundred Acre Wood AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Disney", "Winnie the Pooh Honey Pot Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),

        # Studio Ghibli — All Films
        ("Studio Ghibli", "Nausicaa Valley of the Wind Ohmu Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 72),
        ("Studio Ghibli", "Castle in the Sky Laputa Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 70),
        ("Studio Ghibli", "Grave of the Fireflies Candy Tin Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 68),
        ("Studio Ghibli", "Porco Rosso Plane Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 70),
        ("Studio Ghibli", "The Cat Returns Baron Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 68),
        ("Studio Ghibli", "Arrietty Borrower Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Studio Ghibli", "My Neighbor Totoro Catbus Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),
        ("Studio Ghibli", "Spirited Away No-Face Train Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 38),
        ("Studio Ghibli", "Kiki's Delivery Service Bakery Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 72),

        # Dreamworks / Universal — Expanded
        ("Dreamworks", "Kung Fu Panda Dragon Warrior Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Dreamworks", "Puss in Boots Last Wish Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Dreamworks", "Madagascar Penguins Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 44),
        ("Dreamworks", "Spirit Stallion of the Cimarron Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),

        # Jurassic Park / World — Full
        ("Jurassic Park", "Jurassic Park T-Rex Attack Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Jurassic Park", "Jurassic Park Dilophosaurus Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Jurassic Park", "Jurassic World Blue Raptor Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),

        # Universal Monsters — Full
        ("Universal Monsters", "Invisible Man Bandage Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Universal Monsters", "Phantom of the Opera Mask Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Universal Monsters", "Wolfman Full Moon Scene Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Universal Monsters", "The Mummy Tomb Scene Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 56),

        # Lord of the Rings — Expanded
        ("Lord of the Rings", "Mordor Eye of Sauron Glow Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Lord of the Rings", "Rivendell Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Lord of the Rings", "The One Ring Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 48),
        ("Lord of the Rings", "Arwen Evenstar Zip-Around Wallet", "Wallet", "Standard", "standard", 38),

        # Additional Wallets Matching Sets
        ("Disney", "Ariel Underwater Grotto Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Disney", "Rapunzel Lanterns Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Disney", "Cruella de Vil Dalmatian Zip-Around Wallet", "Wallet", "Standard", "standard", 32),
        ("Disney", "Maleficent Dragon Zip-Around Wallet", "Wallet", "Hot Topic", "standard", 36),
        ("Disney", "Hades Ember Zip-Around Wallet", "Wallet", "Hot Topic", "standard", 36),
        ("Marvel", "Deadpool Chimichanga Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Marvel", "Moon Knight Cosplay Zip-Around Wallet", "Wallet", "Hot Topic", "standard", 34),
        ("Star Wars", "Ahsoka Tano Fulcrum Zip-Around Wallet", "Wallet", "Standard", "standard", 34),
        ("Pokemon", "Snorlax Sleeping Face Zip-Around Wallet", "Wallet", "Standard", "standard", 34),
        ("Pokemon", "Bulbasaur Botanical Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 34),
        ("Sanrio", "Gudetama Lazy Egg Zip-Around Wallet", "Wallet", "Standard", "standard", 30),
        ("Harry Potter", "Marauder's Map Zip-Around Wallet", "Wallet", "Standard", "standard", 34),
        ("Horror", "Beetlejuice Sandworm Zip-Around Wallet", "Wallet", "Hot Topic", "standard", 36),
        ("Horror", "Chucky Good Guys Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 34),

        # Additional Crossbody Bags
        ("Disney", "Mulan Mushu Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 40),
        ("Disney", "Belle Book Crossbody Bag", "Crossbody Bag", "Standard", "standard", 38),
        ("Disney", "Figment Rainbow Crossbody Bag", "Crossbody Bag", "Disney Parks", "mid", 52),
        ("Disney", "Orange Bird Crossbody Bag", "Crossbody Bag", "Disney Parks", "mid", 50),
        ("Marvel", "Groot Baby Face Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 38),
        ("Marvel", "Loki Helmet Crossbody Bag", "Crossbody Bag", "Hot Topic", "standard", 40),
        ("Star Wars", "Ewok Face Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 40),
        ("Sanrio", "My Melody Face Crossbody Bag", "Crossbody Bag", "Standard", "standard", 36),
        ("Pokemon", "Squirtle Squad Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 40),
        ("Harry Potter", "Hedwig Letter Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),

        # Additional Card Holders
        ("Disney", "Stitch Aloha Card Holder", "Card Holder", "Standard", "standard", 22),
        ("Disney", "Cinderella Glass Slipper Card Holder", "Card Holder", "Disney Parks", "standard", 24),
        ("Marvel", "Captain America Shield Card Holder", "Card Holder", "Standard", "standard", 22),
        ("Star Wars", "Mandalorian Helmet Card Holder", "Card Holder", "Standard", "standard", 22),
        ("Pokemon", "Pikachu Face Card Holder", "Card Holder", "Standard", "standard", 20),
        ("Sanrio", "Cinnamoroll Face Card Holder", "Card Holder", "Standard", "standard", 20),
        ("Harry Potter", "Hogwarts Acceptance Letter Card Holder", "Card Holder", "BoxLunch", "standard", 24),

        # Additional Pin Sets
        ("Disney", "Mickey & Friends Birthday Enamel Pin Set", "Pin Set", "Disney Parks", "standard", 26),
        ("Disney", "Stitch Experiments AOP Enamel Pin Set", "Pin Set", "BoxLunch", "standard", 22),
        ("Marvel", "Spider-Man Rogues Gallery Enamel Pin Set", "Pin Set", "BoxLunch", "standard", 24),
        ("Star Wars", "Bounty Hunter Collection Enamel Pin Set", "Pin Set", "BoxLunch", "standard", 24),
        ("Pokemon", "Eeveelution Enamel Pin Set", "Pin Set", "BoxLunch", "standard", 24),
        ("Sanrio", "Sanrio Characters AOP Enamel Pin Set", "Pin Set", "Standard", "standard", 22),
        ("Horror", "Horror Icons Enamel Pin Set", "Pin Set", "Hot Topic", "standard", 22),

        # Additional Convention Exclusives
        ("Disney", "Mickey Sorcerer Blacklight D23 Mini Backpack", "Mini Backpack", "D23", "grail", 310),
        ("Marvel", "Venom Symbiote Planet SDCC Mini Backpack", "Mini Backpack", "SDCC", "grail", 265),
        ("Star Wars", "Boba Fett Prototype Armor SDCC Mini Backpack", "Mini Backpack", "SDCC", "grail", 255),
        ("Disney", "Haunted Mansion 50th Anniversary D23 Mini Backpack", "Mini Backpack", "D23", "grail", 320),

        # === ROUND 10 — Final Batch to 500+ ===

        # Disney Channel / Disney+ Shows
        ("Disney", "Gravity Falls Bill Cipher AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Disney", "Phineas and Ferb Agent P Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "Kim Possible Communicator Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Disney", "Gargoyles Goliath Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "Darkwing Duck Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "DuckTales Scrooge McDuck Money Bin Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "Chip 'n Dale Rescue Rangers Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Disney", "The Owl House Luz Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Disney", "Amphibia Hop Pop AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),

        # Sesame Street / Jim Henson
        ("Sesame Street", "Elmo & Cookie Monster AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Sesame Street", "Oscar the Grouch Trash Can Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Muppets", "Kermit the Frog Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Muppets", "Miss Piggy Sequin Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Labyrinth", "Labyrinth Jareth Crystal Ball Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Dark Crystal", "Dark Crystal Gelfling AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),

        # Cartoon Network
        ("Cartoon Network", "Powerpuff Girls AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 52),
        ("Cartoon Network", "Adventure Time Finn & Jake AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Cartoon Network", "Steven Universe Crystal Gems Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Cartoon Network", "Courage the Cowardly Dog Scene Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Cartoon Network", "Dexter's Laboratory Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Cartoon Network", "Samurai Jack Scene AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),

        # Warner Bros / Looney Tunes
        ("Warner Bros", "Looney Tunes Characters AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
        ("Warner Bros", "Space Jam A New Legacy Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Warner Bros", "Scooby-Doo Mystery Machine Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Warner Bros", "Tom and Jerry Chase Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 44),
        ("Warner Bros", "Gremlins Gizmo Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Warner Bros", "Beetlejuice Handbook for the Recently Deceased Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),

        # Hasbro / Mattel
        ("Hasbro", "My Little Pony Friendship AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 50),
        ("Hasbro", "Transformers Optimus Prime Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Mattel", "Barbie Dream House Pink Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Mattel", "Hot Wheels Racing Flames AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 44),
        ("Lisa Frank", "Lisa Frank Rainbow Tiger AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Lisa Frank", "Lisa Frank Unicorn Galaxy AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),

        # === ROUND 6 — Additional items to reach 510+ ===

        # Disney Afternoon / Classic Animation
        ("Disney", "DuckTales Money Bin Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "Chip 'n Dale Rescue Rangers Gadget Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Disney", "TaleSpin Baloo Pilot Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Disney", "Darkwing Duck Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),

        # More Wallets & Accessories
        ("Disney", "Stitch Elvis Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 38),
        ("Marvel", "Deadpool Chimichanga Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),
        ("Sanrio", "Cinnamoroll Angel Wings Card Holder", "Card Holder", "Standard", "standard", 22),
        ("Pokemon", "Ditto Transform AOP Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Star Wars", "BB-8 Cosplay Crossbody Bag", "Crossbody Bag", "Standard", "standard", 38),
        ("Disney", "Winnie the Pooh Honey Pot Crossbody Bag", "Crossbody Bag", "Disney Parks", "mid", 55),
    ]

    # === ROUND 7 — Stitch, Sanrio, NBC, Pixar, Harry Potter, Pokemon, Studio Ghibli (50 items) ===

    # Stitch Collection
    items += [
        ("Disney", "Stitch Angel Celestial AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Disney", "Stitch Elvis Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "Stitch Holiday Gingerbread Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Disney", "Stitch Pineapple Flip Sequin Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Disney", "Stitch Halloween Vampire Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 62),
        ("Disney", "Stitch Angel Valentine Hearts AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "Stitch Frog Rainy Day Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 56),

        # Sanrio Collection
        ("Sanrio", "Cinnamoroll Cloud AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Sanrio", "Cinnamoroll Latte Cup Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 52),
        ("Sanrio", "Kuromi Skull AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Sanrio", "Kuromi & My Melody Opposites AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Sanrio", "My Melody Flower Bouquet Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 52),
        ("Sanrio", "My Melody Strawberry AOP Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Sanrio", "Hello Kitty 50th Anniversary Gold Mini Backpack", "Mini Backpack", "BoxLunch", "high", 75),
        ("Sanrio", "Pochacco Sneaker Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),

        # Nightmare Before Christmas
        ("Disney", "NBC Oogie Boogie Glow-In-The-Dark Mini Backpack", "Mini Backpack", "BoxLunch", "high", 72),
        ("Disney", "NBC Jack as Santa Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 62),
        ("Disney", "NBC Jack & Sally Graveyard Scene Mini Backpack", "Mini Backpack", "Disney Parks", "high", 80),
        ("Disney", "NBC Spiral Hill Scene Mini Backpack", "Mini Backpack", "Standard", "mid", 58),
        ("Disney", "NBC Zero Glow-In-The-Dark Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 52),
        ("Disney", "NBC Oogie Boogie Blacklight AOP Mini Backpack", "Mini Backpack", "Hot Topic", "high", 70),

        # Pixar Collection
        ("Pixar", "Toy Story Aliens Pizza Planet AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Pixar", "WALL-E & EVE Date Night Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Pixar", "Up Grape Soda Cap Zip-Around Wallet", "Wallet", "Standard", "standard", 38),
        ("Pixar", "Up House Balloons Sequin Mini Backpack", "Mini Backpack", "Standard", "mid", 62),
        ("Pixar", "Ratatouille Remy Cosplay Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Pixar", "Inside Out 2 Emotions AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),

        # Harry Potter Collection
        ("Harry Potter", "Marauder's Map AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Harry Potter", "Honeydukes Sweet Shop AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Harry Potter", "Diagon Alley Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 72),
        ("Harry Potter", "Hedwig Cosplay Mini Backpack", "Mini Backpack", "Standard", "mid", 58),
        ("Harry Potter", "Deathly Hallows Glow-In-The-Dark Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Harry Potter", "Hogwarts Express Platform 9 3/4 Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 52),

        # Pokemon Collection
        ("Pokemon", "Eeveelutions AOP Mini Backpack", "Mini Backpack", "BoxLunch", "high", 75),
        ("Pokemon", "Pikachu Holiday Stocking Cosplay Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Pokemon", "Gengar Glow-In-The-Dark Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 62),
        ("Pokemon", "Umbreon & Espeon Celestial AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Pokemon", "Snorlax Sleeping AOP Mini Backpack", "Mini Backpack", "Standard", "mid", 58),
        ("Pokemon", "Bulbasaur Floral AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),

        # Studio Ghibli Collection
        ("Studio Ghibli", "My Neighbor Totoro Forest Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 72),
        ("Studio Ghibli", "Totoro Catbus Cosplay Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 58),
        ("Studio Ghibli", "Kiki's Delivery Service Jiji Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "high", 70),
        ("Studio Ghibli", "Spirited Away No-Face Mini Backpack", "Mini Backpack", "BoxLunch", "high", 72),
        ("Studio Ghibli", "Princess Mononoke Forest Spirit AOP Mini Backpack", "Mini Backpack", "BoxLunch", "high", 75),
        ("Studio Ghibli", "Howl's Moving Castle Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 78),
        ("Studio Ghibli", "Ponyo Sosuke & Ponyo Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Studio Ghibli", "Totoro Soot Sprites AOP Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 38),
        ("Studio Ghibli", "Castle in the Sky Robot Soldier Mini Backpack", "Mini Backpack", "BoxLunch", "high", 72),
        ("Studio Ghibli", "Kiki's Delivery Service Bakery Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 70),
    ]

    # === ROUND 8 — Disney Parks, Horror, Marvel, Star Wars, Sanrio, Anime, Convention Exclusives (50 items) ===

    # Disney Parks Exclusives (+10)
    items += [
        ("Disney", "50th Anniversary EARidescent Sequin Mini Backpack", "Mini Backpack", "Disney Parks", "high", 120),
        ("Disney", "Enchanted Tiki Room Barker Bird Crossbody Bag", "Crossbody Bag", "Disney Parks", "high", 110),
        ("Disney", "Haunted Mansion Stretching Portraits AOP Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 85),
        ("Disney", "Space Mountain Galaxy Sequin Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 78),
        ("Disney", "Cinderella Castle Fireworks Sequin Mini Backpack", "Mini Backpack", "Disney Parks", "high", 105),
        ("Disney", "Main Street USA Confectionery Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 82),
        ("Disney", "Figment Imagination Institute Crossbody Bag", "Crossbody Bag", "Disney Parks", "high", 95),
        ("Disney", "Orange Bird Citrus Swirl Mini Backpack", "Mini Backpack", "Disney Parks", "high", 115),
        ("Disney", "Walt Disney World 50th Vault Collection Mini Backpack", "Mini Backpack", "Disney Parks", "high", 130),
        ("Disney", "Polynesian Village Resort Tiki Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 88),

        # Horror Series (+8)
        ("Horror", "Friday the 13th Jason Mask Glow Mini Backpack", "Mini Backpack", "Hot Topic", "high", 95),
        ("Horror", "Nightmare on Elm Street Freddy Sweater Mini Backpack", "Mini Backpack", "Hot Topic", "high", 90),
        ("Horror", "Halloween Michael Myers AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 75),
        ("Horror", "Chucky Good Guys Cereal Box Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 68),
        ("Horror", "The Shining Twins Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "high", 100),
        ("Horror", "Beetlejuice Recently Deceased Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 72),
        ("Horror", "Scream Ghostface Glow-in-the-Dark Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 78),
        ("Horror", "Texas Chainsaw Massacre Leatherface Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "high", 85),

        # Marvel (+8)
        ("Marvel", "Scarlet Witch Chaos Magic Sequin Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Marvel", "Loki Helmet Cosplay Mini Backpack", "Mini Backpack", "Standard", "mid", 52),
        ("Marvel", "Black Panther Wakanda Forever Sequin Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Marvel", "Groot Guardians of the Galaxy Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Marvel", "Captain America Shield Crossbody Bag", "Crossbody Bag", "Standard", "standard", 45),
        ("Marvel", "Thor Love & Thunder Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Marvel", "Moon Knight Crescent Dart Glow Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Marvel", "Doctor Strange Multiverse Madness AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),

        # Star Wars (+7)
        ("Star Wars", "Ahsoka Tano White Lightsaber Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Star Wars", "Boba Fett Helmet Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Star Wars", "Padme Amidala Queen Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Star Wars", "Mandalorian Beskar Armor Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Star Wars", "Ewok Endor Celebration Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Star Wars", "R2-D2 Sequin Cosplay Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 72),
        ("Star Wars", "Millennium Falcon Blueprint AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),

        # Sanrio (+7)
        ("Sanrio", "Pompompurin Pancake Cosplay Crossbody Bag", "Crossbody Bag", "Hot Topic", "mid", 52),
        ("Sanrio", "Keroppi Matcha AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Sanrio", "Badtz-Maru Punk Rock Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Sanrio", "Little Twin Stars Galaxy AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Sanrio", "Tuxedosam Sailor Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Sanrio", "Pochacco Athletic Club AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 56),
        ("Sanrio", "Hello Kitty 50th Anniversary Gold Bow Mini Backpack", "Mini Backpack", "Hot Topic", "high", 85),

        # Anime Collabs (+5)
        ("Anime", "Sailor Moon Luna & Artemis Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "high", 75),
        ("Anime", "Attack on Titan Survey Corps Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Anime", "Demon Slayer Tanjiro Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Anime", "Jujutsu Kaisen Gojo AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Anime", "One Piece Straw Hat Pirates Map Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),

        # Convention Exclusives (+5)
        ("Disney", "SDCC 2024 Exclusive Sorcerer Mickey Holographic Mini Backpack", "Mini Backpack", "SDCC", "grail", 220),
        ("Disney", "NYCC 2024 Exclusive Villains Tarot Mini Backpack", "Mini Backpack", "NYCC", "grail", 200),
        ("Marvel", "SDCC 2024 Exclusive Venom Symbiote Glow Mini Backpack", "Mini Backpack", "SDCC", "grail", 210),
        ("Disney", "D23 2024 Exclusive Walt & Mickey Partners Mini Backpack", "Mini Backpack", "D23", "grail", 250),
        ("Star Wars", "Celebration 2024 Exclusive Vader Chrome Mini Backpack", "Mini Backpack", "Convention", "grail", 230),

        # === ROUND 9 — Disney Parks Exclusives (+10) ===
        ("Disney", "Pirates of the Caribbean Treasure Map AOP Mini Backpack", "Mini Backpack", "Disney Parks", "high", 95),
        ("Disney", "Carousel of Progress Scene Mini Backpack", "Mini Backpack", "Disney Parks", "high", 110),
        ("Disney", "Tower of Terror Bellhop Cosplay Mini Backpack", "Mini Backpack", "Disney Parks", "high", 105),
        ("Disney", "Splash Mountain Zip-a-Dee-Doo-Dah Mini Backpack", "Mini Backpack", "Disney Parks", "grail", 250),
        ("Disney", "Country Bear Jamboree Scene Mini Backpack", "Mini Backpack", "Disney Parks", "high", 100),
        ("Disney", "It's a Small World Boat Ride Scene Mini Backpack", "Mini Backpack", "Disney Parks", "high", 110),
        ("Disney", "Spaceship Earth Epcot Sequin Mini Backpack", "Mini Backpack", "Disney Parks", "high", 115),
        ("Disney", "Animal Kingdom Tree of Life Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 85),
        ("Disney", "Hollywood Studios Twilight Zone Mini Backpack", "Mini Backpack", "Disney Parks", "high", 100),
        ("Disney", "Magic Kingdom Fireworks Glow Mini Backpack", "Mini Backpack", "Disney Parks", "high", 120),

        # === Marvel Mini Backpacks (+10) ===
        ("Marvel", "Iron Man Arc Reactor Glow-In-The-Dark Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Marvel", "Spider-Man 2099 Neon Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Marvel", "Deadpool Chibi AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Marvel", "X-Men '97 Team Lineup AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Marvel", "Wolverine Yellow Suit Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Marvel", "Venom Let There Be Carnage Sequin Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Marvel", "Guardians of the Galaxy Vol 3 Rocket Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Marvel", "She-Hulk Iridescent Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Marvel", "Ms. Marvel Lightning Bolt Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Marvel", "Agatha Harkness Darkhold AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),

        # === Star Wars Bags (+8) ===
        ("Star Wars", "Grogu Snack Time Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Star Wars", "Darth Vader Helmet Sequin Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Star Wars", "Princess Leia Organa Gown Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Star Wars", "Luke Skywalker X-Wing Pilot Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Star Wars", "Chewbacca Fur Texture Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Star Wars", "Yoda Force Ghost Glow Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 62),
        ("Star Wars", "Clone Trooper Phase II Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Star Wars", "Ahsoka Tano White & Blue Fulcrum Mini Backpack", "Mini Backpack", "Standard", "mid", 55),

        # === Sanrio Collabs (+8) ===
        ("Sanrio", "Hello Kitty x Naruto Akatsuki Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "high", 78),
        ("Sanrio", "Hello Kitty x My Hero Academia UA High Mini Backpack", "Mini Backpack", "BoxLunch", "high", 75),
        ("Sanrio", "Cinnamoroll Stargazing Celestial Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 62),
        ("Sanrio", "Kuromi Halloween Witch Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Sanrio", "My Melody x Kuromi Devil & Angel 2-Tone Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Sanrio", "Pompompurin Bee Costume Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Sanrio", "Keroppi Rainforest AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Sanrio", "Badtz-Maru Skater AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 48),

        # === Nickelodeon (+8) ===
        ("Nickelodeon", "Rugrats Reptar Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Nickelodeon", "Rugrats Chuckie Finster Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Nickelodeon", "SpongeBob SquarePants Pineapple House Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Nickelodeon", "SpongeBob Patrick Star Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Nickelodeon", "Danny Phantom Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Nickelodeon", "Invader Zim GIR Doom Song AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Nickelodeon", "Avatar The Last Airbender Appa Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Nickelodeon", "Teenage Mutant Ninja Turtles Pizza AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),

        # === Anime Collabs (+10) ===
        ("Anime", "My Hero Academia Deku Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Anime", "My Hero Academia Bakugo Explosion AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 62),
        ("Anime", "Naruto Shippuden Akatsuki Cloud AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Anime", "Naruto Shippuden Kakashi Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Anime", "Dragon Ball Z Shenron Glow-In-The-Dark Mini Backpack", "Mini Backpack", "BoxLunch", "high", 72),
        ("Anime", "Spy x Family Anya Forger Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Anime", "Chainsaw Man Pochita Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Anime", "Neon Genesis Evangelion Unit-01 AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Anime", "Cowboy Bebop Ein Corgi Cosplay Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Anime", "Fullmetal Alchemist Alphonse Armor Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),

        # === Halloween / Holiday Exclusives (+10) ===
        ("Disney", "Mickey Mouse Vampire Halloween 2024 Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Disney", "Stitch Skeleton Glow-In-The-Dark Halloween Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 68),
        ("Disney", "Nightmare Before Christmas Pumpkin King Halloween LE Mini Backpack", "Mini Backpack", "Hot Topic", "high", 85),
        ("Disney", "Haunted Mansion Hitchhiking Ghosts Glow Halloween Mini Backpack", "Mini Backpack", "Disney Parks", "high", 110),
        ("Disney", "Hocus Pocus Sanderson Sisters Halloween Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 72),
        ("Disney", "Mickey Mouse Christmas Sweater Holiday Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Disney", "Stitch Holiday Gingerbread House Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Sanrio", "Hello Kitty Pumpkin Halloween LE Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 68),
        ("Pokemon", "Gengar Trick or Treat Halloween Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Horror", "Elvira Mistress of the Dark Halloween LE Mini Backpack", "Mini Backpack", "Hot Topic", "high", 90),

        # === Loungefly Wallets & Crossbody Bags (+14) ===
        ("Disney", "Lilo & Stitch Aloha Zip-Around Wallet", "Wallet", "Standard", "standard", 34),
        ("Disney", "Moana Ocean Wave Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Disney", "Encanto Mirabel Door Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Disney", "Wish Star Zip-Around Wallet", "Wallet", "Standard", "standard", 32),
        ("Marvel", "Wolverine Cosplay Zip-Around Wallet", "Wallet", "Hot Topic", "standard", 36),
        ("Marvel", "Spider-Gwen Cosplay Zip-Around Wallet", "Wallet", "Standard", "standard", 34),
        ("Nickelodeon", "SpongeBob Krabby Patty Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),
        ("Nickelodeon", "Rugrats Tommy Pickles Reptar Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 40),
        ("Anime", "Naruto Ichiraku Ramen Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 45),
        ("Anime", "My Hero Academia All Might Crossbody Bag", "Crossbody Bag", "Hot Topic", "standard", 42),
        ("Pixar", "Monsters Inc Boo Door Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),
        ("Pixar", "Finding Nemo Submarine Voyage Crossbody Bag", "Crossbody Bag", "Standard", "standard", 38),
        ("Disney", "Tangled Rapunzel Tower Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),
        ("Disney", "Frozen Elsa Ice Castle Crossbody Bag", "Crossbody Bag", "Standard", "standard", 38),

        # === Pixar Expansion (+10) ===
        ("Pixar", "Cars Lightning McQueen Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Pixar", "Coco Miguel Guitar Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Pixar", "The Incredibles Logo Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Pixar", "Brave Merida Arrow AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Pixar", "Turning Red Mei Panda Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Pixar", "Luca Sea Monster Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Pixar", "Soul 22 & Joe Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),
        ("Pixar", "Onward Barley Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 52),
        ("Pixar", "Elemental Ember & Wade Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Pixar", "Lightyear Sox the Cat Cosplay Crossbody Bag", "Crossbody Bag", "Standard", "standard", 40),
    ]

    # === ROUND 8 — Pokémon, Ghibli, Sanrio, Anime, Parks, Horror, Marvel/DC, Wallets, Seasonal (110 items) ===

    # Pokémon Collection (~15)
    items += [
        ("Pokemon", "Pikachu Lightning Bolt AOP Mini Backpack", "Mini Backpack", "Standard", "mid", 58),
        ("Pokemon", "Gengar Purple Glow-in-the-Dark Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Pokemon", "Squirtle Squad Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Pokemon", "Snorlax Cosplay Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Pokemon", "Charizard Flame AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Pokemon", "Bulbasaur Floral Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Pokemon", "Charmander Embroidered Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Pokemon", "Umbreon & Espeon Duo Glow Mini Backpack", "Mini Backpack", "BoxLunch", "high", 105),
        ("Pokemon", "Pokeball Crossbody Bag", "Crossbody Bag", "Standard", "standard", 42),
        ("Pokemon", "Pikachu 025 Anniversary Mini Backpack", "Mini Backpack", "Pokemon Center", "high", 110),
        ("Pokemon", "Mewtwo Glow-in-the-Dark Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 68),
        ("Pokemon", "Jigglypuff Cosplay Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Pokemon", "Eevee Evolutions AOP Zip-Around Wallet", "Wallet", "BoxLunch", "mid", 52),
        ("Pokemon", "Pikachu Lightning Bolt Crossbody Bag", "Crossbody Bag", "Standard", "standard", 40),
        ("Pokemon", "Gengar Purple Glow Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 45),
    ]

    # Studio Ghibli Collection (~10)
    items += [
        ("Studio Ghibli", "Totoro Grey Fuzzy Mini Backpack", "Mini Backpack", "BoxLunch", "high", 110),
        ("Studio Ghibli", "Kiki's Delivery Service Jiji Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 72),
        ("Studio Ghibli", "Howl's Moving Castle Calcifer Mini Backpack", "Mini Backpack", "BoxLunch", "high", 105),
        ("Studio Ghibli", "Ponyo on the Ocean AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 68),
        ("Studio Ghibli", "Princess Mononoke Forest Spirit Mini Backpack", "Mini Backpack", "BoxLunch", "high", 115),
        ("Studio Ghibli", "Calcifer Flame Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Studio Ghibli", "Catbus Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "high", 100),
        ("Studio Ghibli", "Porco Rosso Airplane Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 62),
        ("Studio Ghibli", "Spirited Away Bathhouse AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 75),
        ("Studio Ghibli", "Totoro Catbus Zip-Around Wallet", "Wallet", "BoxLunch", "mid", 50),
    ]

    # Sanrio Collection (~10)
    items += [
        ("Sanrio", "Hello Kitty 50th Anniversary Mini Backpack", "Mini Backpack", "Standard", "high", 100),
        ("Sanrio", "My Melody Pink Lace Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Sanrio", "Kuromi Purple Checkered Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Sanrio", "Pompompurin Pudding Cosplay Mini Backpack", "Mini Backpack", "Standard", "mid", 52),
        ("Sanrio", "Keroppi Lily Pad AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Sanrio", "Aggretsuko Rage Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Sanrio", "Little Twin Stars Cloud AOP Mini Backpack", "Mini Backpack", "Standard", "mid", 52),
        ("Sanrio", "Badtz-Maru Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Sanrio", "Hello Kitty 50th Anniversary Zip-Around Wallet", "Wallet", "Standard", "mid", 50),
    ]

    # Anime Collection (~10)
    items += [
        ("Anime", "Demon Slayer Tanjiro Checkered AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Anime", "One Piece Luffy Straw Hat Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Anime", "Naruto Akatsuki Cloud AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Anime", "Dragon Ball Z Capsule Corp Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Anime", "Sailor Moon Crystal Transformation Brooch Mini Backpack", "Mini Backpack", "BoxLunch", "high", 105),
        ("Anime", "My Hero Academia UA Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Anime", "Attack on Titan Wings of Freedom Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 62),
        ("Anime", "Jujutsu Kaisen Gojo Blindfold AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Anime", "Cowboy Bebop Spike Spiegel AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 68),
        ("Anime", "Naruto Akatsuki Zip-Around Wallet", "Wallet", "Hot Topic", "standard", 42),
    ]

    # Disney Parks Attractions (~15)
    items += [
        ("Disney", "Walt Disney World 50th Anniversary EARidescent Mini Backpack", "Mini Backpack", "Disney Parks", "high", 120),
        ("Disney", "Enchanted Tiki Room Tropical AOP Mini Backpack", "Mini Backpack", "Disney Parks", "high", 110),
        ("Disney", "Haunted Mansion Hitchhiking Ghosts Glow Mini Backpack", "Mini Backpack", "Disney Parks", "grail", 220),
        ("Disney", "Space Mountain Retro Poster AOP Mini Backpack", "Mini Backpack", "Disney Parks", "high", 100),
        ("Disney", "Jungle Cruise Skipper Cosplay Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 75),
        ("Disney", "Pirates of the Caribbean Skull Glow Mini Backpack", "Mini Backpack", "Disney Parks", "high", 105),
        ("Disney", "It's a Small World Clock Face Mini Backpack", "Mini Backpack", "Disney Parks", "high", 110),
        ("Disney", "Orange Bird Scented Mini Backpack", "Mini Backpack", "Disney Parks", "grail", 240),
        ("Disney", "Figment Imagination AOP Mini Backpack", "Mini Backpack", "Disney Parks", "high", 130),
        ("Disney", "Country Bear Jamboree Cosplay Mini Backpack", "Mini Backpack", "Disney Parks", "high", 95),
        ("Disney", "Carousel of Progress Retro Mini Backpack", "Mini Backpack", "Disney Parks", "high", 100),
        ("Disney", "Monorail Retro Poster AOP Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 80),
        ("Disney", "Retro Attraction Poster Series Mini Backpack (LE)", "Mini Backpack", "Disney Parks LE", "grail", 200),
        ("Disney", "Tomorrowland Astro Orbiter Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 78),
        ("Disney", "Main Street Electrical Parade Glow Mini Backpack", "Mini Backpack", "Disney Parks", "high", 115),
    ]

    # Horror / Movies (~10)
    items += [
        ("Horror", "Beetlejuice Sandworm Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 62),
        ("Horror", "Corpse Bride Emily Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Horror", "Coraline Stars Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "high", 105),
        ("Horror", "Edward Scissorhands Topiary Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 68),
        ("Horror", "Gremlins Gizmo Cosplay Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Horror", "Ghostbusters No Ghost Logo AOP Mini Backpack", "Mini Backpack", "Standard", "mid", 52),
        ("Horror", "IT Pennywise Red Balloon Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Horror", "Scream Ghostface Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Horror", "Stranger Things Hellfire Club Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Horror", "Nightmare Before Christmas Oogie Boogie Glow Mini Backpack", "Mini Backpack", "Disney Parks", "high", 100),
    ]

    # Additional Marvel / DC (~10)
    items += [
        ("Marvel", "Spider-Verse Miles Morales Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Marvel", "Deadpool & Wolverine Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 68),
        ("Marvel", "Loki Alligator Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Marvel", "WandaVision Scarlet Witch Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Marvel", "Moon Knight Glow-in-the-Dark Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("DC", "Poison Ivy Floral Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("DC", "Catwoman Cosplay Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("DC", "Harley Quinn Birds of Prey Sequin Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 62),
        ("Marvel", "She-Hulk Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Marvel", "Ms. Marvel Emblem Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
    ]

    # Matching Wallets & Crossbodies (~15)
    items += [
        ("Disney", "Haunted Mansion Hitchhiking Ghosts Glow Wallet", "Wallet", "Disney Parks", "high", 85),
        ("Disney", "Figment Imagination AOP Wallet", "Wallet", "Disney Parks", "mid", 55),
        ("Disney", "Enchanted Tiki Room Tropical Crossbody", "Crossbody Bag", "Disney Parks", "mid", 60),
        ("Studio Ghibli", "Princess Mononoke Forest Spirit Wallet", "Wallet", "BoxLunch", "mid", 50),
        ("Horror", "Coraline Stars Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 52),
        ("Anime", "Sailor Moon Crystal Wallet", "Wallet", "BoxLunch", "mid", 48),
        ("Sanrio", "Kuromi Purple Checkered Wallet", "Wallet", "Hot Topic", "standard", 38),
        ("Marvel", "Spider-Verse Miles Morales Wallet", "Wallet", "BoxLunch", "standard", 40),
        ("Disney", "Orange Bird Card Holder", "Card Holder", "Disney Parks", "mid", 50),
        ("Pokemon", "Snorlax Cosplay Crossbody Bag", "Crossbody Bag", "Standard", "standard", 42),
        ("Horror", "Beetlejuice Crossbody Bag", "Crossbody Bag", "Hot Topic", "standard", 42),
        ("Anime", "Demon Slayer Tanjiro Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 45),
        ("Disney", "Space Mountain Retro Poster Wallet", "Wallet", "Disney Parks", "mid", 50),
        ("Sanrio", "Cinnamoroll Cloud Card Holder", "Card Holder", "Hot Topic", "standard", 25),
        ("DC", "Poison Ivy Floral Wallet", "Wallet", "Hot Topic", "standard", 38),
    ]

    # Seasonal & Limited Editions (~10)
    items += [
        ("Disney", "Valentine's Day Mickey & Minnie Heart Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Disney", "Halloween Villains Glow-in-the-Dark Mini Backpack", "Mini Backpack", "Disney Parks", "high", 110),
        ("Sanrio", "Hello Kitty Pride Rainbow AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Disney", "Mickey & Minnie Holiday Gingerbread Mini Backpack", "Mini Backpack", "Disney Parks", "high", 100),
        ("Disney", "BoxLunch Earth Day Bambi Recycled Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("Disney", "SDCC Exclusive Sorcerer Mickey Blacklight Mini Backpack", "Mini Backpack", "SDCC Exclusive", "grail", 250),
        ("Disney", "NYCC Exclusive Maleficent Dragon Glow Mini Backpack", "Mini Backpack", "NYCC Exclusive", "grail", 230),
        ("Sanrio", "Valentine's Day Cinnamoroll Heart Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Disney", "Halloween Nightmare Before Christmas Mayor Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 68),
        ("Marvel", "D23 Exclusive Avengers Assemble Mini Backpack", "Mini Backpack", "D23 Exclusive", "grail", 200),
    ]

    # ── Additional Lines — Star Wars, Universal, Collabs, Pixar, Kids ──
    items += [
        # Star Wars — More Characters
        ("Star Wars", "Grogu (The Child) Cradle Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Star Wars", "Ahsoka Tano Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "high", 90),
        ("Star Wars", "Darth Vader Lenticular Mini Backpack", "Mini Backpack", "Vaulted", "grail", 180),
        ("Star Wars", "Boba Fett Jetpack Mini Backpack", "Mini Backpack", "Standard", "mid", 65),
        ("Star Wars", "Princess Leia Bespin Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 70),

        # Universal Monsters
        ("Horror", "Bride of Frankenstein Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Horror", "Creature from the Black Lagoon Mini Backpack", "Mini Backpack", "Hot Topic", "high", 90),
        ("Horror", "Universal Monsters AOP Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Horror", "Frankenstein Lenticular Wallet", "Wallet", "Hot Topic", "mid", 45),

        # Brand Collabs — Coca-Cola & McDonald's
        ("Coca-Cola", "Coca-Cola Logo AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 68),
        ("Coca-Cola", "Coca-Cola Polar Bear Mini Backpack", "Mini Backpack", "Standard", "mid", 62),
        ("Coca-Cola", "Coca-Cola Vintage Logo Wallet", "Wallet", "Standard", "standard", 35),
        ("McDonald's", "McDonald's Happy Meal Gang Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("McDonald's", "McDonald's Grimace Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("McDonald's", "McDonald's Fry Kids AOP Mini Backpack", "Mini Backpack", "Standard", "mid", 65),

        # Pixar — Up, WALL-E, Coco
        ("Pixar", "Up House Balloons Mini Backpack", "Mini Backpack", "BoxLunch", "high", 90),
        ("Pixar", "Up Adventure is Out There Crossbody Bag", "Crossbody Bag", "Standard", "mid", 50),
        ("Pixar", "WALL-E & EVE Plant Boot Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Pixar", "WALL-E Earth Day Recycled Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Pixar", "Coco Miguel Guitar Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 70),
        ("Pixar", "Coco Remember Me Marigold Wallet", "Wallet", "Hot Topic", "standard", 40),

        # Kids — Bluey & Sesame Street
        ("Bluey", "Bluey House AOP Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Bluey", "Bluey & Bingo Dance Mode Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Bluey", "Bluey Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 42),
        ("Sesame Street", "Elmo Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 42),
        ("Sesame Street", "Cookie Monster Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 42),
        ("Sesame Street", "Oscar the Grouch Trash Can Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),

        # ─── Disney Villain Pieces ─────────────────────────────────────────
        ("Disney Villains", "Maleficent Dragon Glow Mini Backpack", "Mini Backpack", "BoxLunch", "high", 95),
        ("Disney Villains", "Ursula Crystal Ball Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Disney Villains", "Cruella De Vil Spots Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 70),
        ("Disney Villains", "Evil Queen Poison Apple Crossbody Bag", "Crossbody Bag", "Hot Topic", "mid", 60),
        ("Disney Villains", "Hades Flames Mini Backpack", "Mini Backpack", "Hot Topic", "high", 80),
        ("Disney Villains", "Jafar Villains Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Disney Villains", "Captain Hook Jolly Roger Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Disney Villains", "Scar Pride Rock Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Disney Villains", "Gaston Tavern Scene Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Disney Villains", "Mother Gothel Tangled Tower Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 70),
        ("Disney Villains", "Queen of Hearts Card AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Disney Villains", "Oogie Boogie Glow Wallet", "Wallet", "BoxLunch", "mid", 40),
        ("Disney Villains", "Dr. Facilier Voodoo Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Disney Villains", "Villain Portraits AOP Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Disney Villains", "Sleeping Beauty Maleficent Castle Mini Backpack", "Mini Backpack", "SDCC Exclusive", "grail", 150),

        # ─── Harry Potter House-Specific ───────────────────────────────────
        ("Harry Potter", "Gryffindor Common Room Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Harry Potter", "Slytherin Crest AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Harry Potter", "Ravenclaw Crest AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Harry Potter", "Hufflepuff Crest AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Harry Potter", "Hogwarts Castle Glow Mini Backpack", "Mini Backpack", "BoxLunch", "high", 90),
        ("Harry Potter", "Diagon Alley Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Harry Potter", "Marauder's Map AOP Wallet", "Wallet", "Standard", "standard", 35),
        ("Harry Potter", "Hedwig Howler Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Harry Potter", "Sorting Hat Figural Mini Backpack", "Mini Backpack", "Hot Topic", "high", 85),
        ("Harry Potter", "Golden Snitch Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 50),
        ("Harry Potter", "Deathly Hallows Glow Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Harry Potter", "Honeydukes Candy AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),

        # ─── Lord of the Rings ─────────────────────────────────────────────
        ("Lord of the Rings", "The One Ring Glow Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Lord of the Rings", "The Shire Map AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Lord of the Rings", "Gandalf vs Balrog Scene Mini Backpack", "Mini Backpack", "Hot Topic", "high", 90),
        ("Lord of the Rings", "Mordor Eye of Sauron Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Lord of the Rings", "Evenstar Glow Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Lord of the Rings", "Minas Tirith Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Lord of the Rings", "Precious Ring AOP Wallet", "Wallet", "Standard", "standard", 38),
        ("Lord of the Rings", "Rivendell Elven Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),

        # ─── Funko x Loungefly Collabs ─────────────────────────────────────
        ("Funko x Loungefly", "Funko Pop! Star Wars Boba Fett Mini Backpack", "Mini Backpack", "Funko Shop", "high", 90),
        ("Funko x Loungefly", "Funko Pop! Disney Stitch Glow Mini Backpack", "Mini Backpack", "Funko Shop", "high", 85),
        ("Funko x Loungefly", "Funko Pop! Marvel Iron Man Mini Backpack", "Mini Backpack", "Funko Shop", "high", 80),
        ("Funko x Loungefly", "Funko Pop! Deadpool & Wolverine Mini Backpack", "Mini Backpack", "Funko Shop", "high", 85),
        ("Funko x Loungefly", "Funko Pop! SpongeBob Pineapple Mini Backpack", "Mini Backpack", "Funko Shop", "mid", 70),
        ("Funko x Loungefly", "Funko Pop! Ghostbusters Stay Puft Mini Backpack", "Mini Backpack", "Funko Shop", "mid", 65),

        # ─── Fanny Packs ──────────────────────────────────────────────────
        ("Disney", "Mickey Ears Rainbow Fanny Pack", "Fanny Pack", "Disney Parks", "mid", 50),
        ("Disney", "Minnie Mouse Polka Dot Fanny Pack", "Fanny Pack", "Standard", "standard", 38),
        ("Star Wars", "Mandalorian Grogu Fanny Pack", "Fanny Pack", "BoxLunch", "mid", 45),
        ("Marvel", "Avengers Logo AOP Fanny Pack", "Fanny Pack", "Standard", "standard", 35),
        ("Sanrio", "Hello Kitty 50th Anniversary Fanny Pack", "Fanny Pack", "Hot Topic", "mid", 48),
        ("Pokemon", "Pikachu Lightning AOP Fanny Pack", "Fanny Pack", "Standard", "standard", 38),
        ("Disney", "Alice in Wonderland Tea Party Fanny Pack", "Fanny Pack", "BoxLunch", "mid", 48),

        # ─── Tote Bags ────────────────────────────────────────────────────
        ("Disney", "Cinderella Castle Tote Bag", "Tote Bag", "Disney Parks", "mid", 55),
        ("Studio Ghibli", "Totoro Forest Scene Tote Bag", "Tote Bag", "BoxLunch", "mid", 50),
        ("Sanrio", "Cinnamoroll Cloud AOP Canvas Tote", "Tote Bag", "Hot Topic", "standard", 40),
        ("Disney", "Haunted Mansion Wallpaper Tote Bag", "Tote Bag", "Disney Parks", "mid", 55),
        ("Pokemon", "Eevee Evolutions AOP Tote Bag", "Tote Bag", "BoxLunch", "mid", 48),
        ("Marvel", "Spider-Verse AOP Canvas Tote", "Tote Bag", "Hot Topic", "standard", 42),
        ("Harry Potter", "Hogwarts Express Canvas Tote", "Tote Bag", "BoxLunch", "standard", 42),

        # ─── Pin Collections ──────────────────────────────────────────────
        ("Disney", "Disney Villains Blind Box Pin Set (8 Pins)", "Pin Set", "BoxLunch", "high", 80),
        ("Disney", "Mickey Through the Years 4-Pin Set", "Pin Set", "Disney Parks", "mid", 55),
        ("Star Wars", "Mandalorian Enamel Pin Set (6 Pins)", "Pin Set", "BoxLunch", "mid", 48),
        ("Sanrio", "Hello Kitty 50th Anniversary Pin Box", "Pin Set", "Hot Topic", "mid", 50),
        ("Pokemon", "Kanto Starters Enamel Pin Set (3 Pins)", "Pin Set", "BoxLunch", "standard", 30),
        ("Disney", "Princess Crown Pin Collection (12 Pins)", "Pin Set", "Disney Parks", "high", 90),
        ("Studio Ghibli", "Spirited Away Characters Pin Set (4 Pins)", "Pin Set", "BoxLunch", "mid", 45),
        ("Marvel", "Avengers Infinity Stones Pin Set (6 Pins)", "Pin Set", "BoxLunch", "mid", 50),

        # ─── Backpack Charms & Keychains ──────────────────────────────────
        ("Disney", "Mickey Mouse Figural Backpack Charm", "Charm", "Standard", "standard", 18),
        ("Sanrio", "Kuromi Plush Backpack Charm", "Charm", "Hot Topic", "standard", 22),
        ("Pokemon", "Pikachu 3D Backpack Charm", "Charm", "Standard", "standard", 18),
        ("Disney", "Stitch Figural Keychain Charm", "Charm", "Standard", "standard", 16),
        ("Studio Ghibli", "No-Face Figural Backpack Charm", "Charm", "BoxLunch", "standard", 22),
        ("Star Wars", "Grogu Figural Backpack Charm", "Charm", "BoxLunch", "standard", 20),
        ("Sanrio", "Pompompurin Plush Keychain Charm", "Charm", "Standard", "standard", 18),
        ("Disney", "Figment Figural Backpack Charm", "Charm", "Disney Parks", "mid", 30),
        ("Disney", "Orange Bird Figural Backpack Charm", "Charm", "Disney Parks", "mid", 28),

        # ─── More Disney Specific ──────────────────────────────────────────
        ("Disney", "Ratatouille Remy Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Disney", "Monsters Inc. Door Vault Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Disney", "Lilo & Stitch Ducklings Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Disney", "Encanto Casita Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Disney", "101 Dalmatians Cruella Spots Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Disney", "Aristocats Marie Floral Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Disney", "Bambi Flower Meadow Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Disney", "Robin Hood Prince John Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Disney", "Fantasia Sorcerer Mickey Glow Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Disney", "Wreck-It Ralph Sugar Rush Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Disney", "Moana Te Fiti Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Disney", "Sleeping Beauty Aurora Castle Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Disney", "Peter Pan Neverland Map Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Disney", "Dumbo Circus Tent Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Disney", "Aladdin Cave of Wonders Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),

        # ─── More Marvel / DC ──────────────────────────────────────────────
        ("Marvel", "Spider-Man Miles Morales Graffiti Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Marvel", "Avengers Endgame Final Battle Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Marvel", "Black Panther Wakanda Forever Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Marvel", "Captain America Shield Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Marvel", "Loki TVA Agent Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Marvel", "WandaVision Scarlet Witch Crown Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Marvel", "Venom Glow Mini Backpack", "Mini Backpack", "Hot Topic", "high", 80),
        ("Marvel", "Iron Man Arc Reactor Glow Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("DC Comics", "Batman 85th Anniversary Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("DC Comics", "Harley Quinn Birds of Prey Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("DC Comics", "Joker Purple Suit Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("DC Comics", "Wonder Woman Golden Eagle Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),

        # ─── More Star Wars ───────────────────────────────────────────────
        ("Star Wars", "Grogu Pram Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Star Wars", "Ahsoka Tano Rebels Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Star Wars", "Darth Vader Helmet Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Star Wars", "R2-D2 Figural Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Star Wars", "Ewok Village Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Star Wars", "Cantina Band AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Star Wars", "Princess Leia Hoth Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),

        # ─── Nintendo / Anime / Studio Ghibli ─────────────────────────────
        ("Nintendo", "Pokemon Eevee Evolutions AOP Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Nintendo", "Pokemon Snorlax Bean Bag Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Nintendo", "Zelda Hyrule Crest Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Nintendo", "Animal Crossing Nook Inc. Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Nintendo", "Kirby Pink Puff Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Studio Ghibli", "Spirited Away No-Face Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Studio Ghibli", "Kiki's Delivery Service Jiji Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Studio Ghibli", "My Neighbor Totoro Bus Stop Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Studio Ghibli", "Howl's Moving Castle Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Studio Ghibli", "Princess Mononoke Forest Spirit Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),

        # ─── More Sanrio Extended ──────────────────────────────────────────
        ("Sanrio", "Cinnamoroll AOP Cloud Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Sanrio", "Kuromi Baku AOP Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Sanrio", "My Melody Strawberry Fields Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Sanrio", "Pompompurin Pudding Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Sanrio", "Hello Kitty 50th Anniversary Gold Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Sanrio", "Keroppi Lily Pad Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
        ("Sanrio", "Badtz-Maru Punk Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Sanrio", "Little Twin Stars Cloud Castle Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),

        # ─── More Horror Franchise ─────────────────────────────────────────
        ("Horror", "Bride of Chucky Tiffany Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Horror", "Ghostface (Scream) Glow Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Horror", "Beetlejuice Sandworm Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Horror", "Gremlins Gizmo Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Horror", "Corpse Bride Emily Cosplay Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Horror", "Elvira Mistress of the Dark Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Horror", "Coraline Button Eyes Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Horror", "Edward Scissorhands Topiary Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),

        # ─── More Pokemon ──────────────────────────────────────────────────
        ("Pokemon", "Pikachu Lightning Bolt Cosplay Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Pokemon", "Gengar Glow Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Pokemon", "Snorlax Sleeping AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Pokemon", "Charizard Fire Scene Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Pokemon", "Eeveelution Circle AOP Wallet", "Wallet", "Standard", "standard", 35),
        ("Pokemon", "Mewtwo Glow Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Pokemon", "Bulbasaur Planter Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),

        # ─── More Wallets & Crossbody ──────────────────────────────────────
        ("Disney", "Mickey & Minnie Date Night Wallet", "Wallet", "Standard", "standard", 35),
        ("Disney", "Cinderella Ball Gown Wallet", "Wallet", "BoxLunch", "standard", 38),
        ("Star Wars", "Darth Vader Helmet Wallet", "Wallet", "Standard", "standard", 32),
        ("Marvel", "Spider-Man Web Wallet", "Wallet", "Standard", "standard", 32),
        ("Sanrio", "Hello Kitty & Friends Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 48),
        ("Disney", "Tangled Lantern Scene Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Disney", "Beauty and the Beast Library Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Harry Potter", "Hogwarts Letter Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 50),
        ("Studio Ghibli", "Totoro Catbus Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),

        # ─── Seasonal & Vaulted Disney ─────────────────────────────────────
        ("Disney", "Halloween 2024 Mickey Pumpkin Mini Backpack", "Mini Backpack", "Disney Parks", "high", 85),
        ("Disney", "Christmas 2024 Holiday Castle Mini Backpack", "Mini Backpack", "Disney Parks", "high", 80),
        ("Disney", "Spring 2024 Flower & Garden Figment Mini Backpack", "Mini Backpack", "Disney Parks", "high", 85),
        ("Disney", "Halloween 2023 Haunted Mansion Glow Mini Backpack (Vaulted)", "Mini Backpack", "Disney Parks", "grail", 130),
        ("Disney", "50th Anniversary Vault Collection Mini Backpack", "Mini Backpack", "Disney Parks", "grail", 150),
        ("Disney", "Food & Wine 2023 Remy Mini Backpack (Vaulted)", "Mini Backpack", "Disney Parks", "high", 100),
        ("Disney", "Stitch Crashes Disney: Lion King Mini Backpack (Vaulted)", "Mini Backpack", "shopDisney", "high", 95),
        ("Disney", "Stitch Crashes Disney: Beauty & Beast Mini Backpack (Vaulted)", "Mini Backpack", "shopDisney", "high", 90),
        ("Disney", "Stitch Crashes Disney: Aladdin Mini Backpack (Vaulted)", "Mini Backpack", "shopDisney", "high", 90),
        ("Disney", "Stitch Crashes Disney: Mulan Mini Backpack (Vaulted)", "Mini Backpack", "shopDisney", "high", 90),
        ("Disney", "Stitch Crashes Disney: Snow White Mini Backpack (Vaulted)", "Mini Backpack", "shopDisney", "high", 95),
        ("Disney", "Stitch Crashes Disney: Pinocchio Mini Backpack (Vaulted)", "Mini Backpack", "shopDisney", "high", 90),
        ("Disney", "Stitch Crashes Disney: Jungle Book Mini Backpack (Vaulted)", "Mini Backpack", "shopDisney", "high", 90),

        # ─── Pre-Funko Era Loungefly (Vintage) ────────────────────────────
        ("Loungefly Vintage", "Skull & Crossbones Leather Mini Backpack (2010)", "Mini Backpack", "Vintage", "high", 100),
        ("Loungefly Vintage", "Hello Kitty Original Collaboration Mini Backpack (2008)", "Mini Backpack", "Vintage", "high", 120),
        ("Loungefly Vintage", "Star Wars Darth Vader Helmet Bag (2012)", "Crossbody Bag", "Vintage", "high", 90),
        ("Loungefly Vintage", "Sugar Skull Dia de los Muertos Wallet (2011)", "Wallet", "Vintage", "mid", 55),
        ("Loungefly Vintage", "Tokidoki x Loungefly Cactus Friends (2009)", "Mini Backpack", "Vintage Collab", "grail", 150),

        # ─── Additional Disney Park Exclusives ─────────────────────────────
        ("Disney", "Figment Epcot Journey Into Imagination Mini Backpack", "Mini Backpack", "Disney Parks", "high", 95),
        ("Disney", "Orange Bird Flower & Garden Mini Backpack", "Mini Backpack", "Disney Parks", "high", 90),
        ("Disney", "Tiana's Palace Mini Backpack", "Mini Backpack", "Disney Parks", "high", 80),
        ("Disney", "Splash Mountain Final Ride Mini Backpack (Vaulted)", "Mini Backpack", "Disney Parks", "grail", 140),
        ("Disney", "Buzz Lightyear Space Ranger Spin Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 60),
        ("Disney", "WDW 50th Anniversary Cinderella Castle Iridescent Mini Backpack", "Mini Backpack", "Disney Parks", "grail", 120),
        ("Disney", "Hocus Pocus Sanderson Sisters Mini Backpack", "Mini Backpack", "Disney Parks", "high", 85),
        ("Disney", "Haunted Mansion Madame Leota Crystal Ball Mini Backpack", "Mini Backpack", "Disney Parks", "high", 90),
    ]

    catalog = []
    for franchise, name, item_type, exclusive, tier, price in items:
        catalog.append({
            "franchise": franchise,
            "name": name,
            "item_type": item_type,
            "exclusive": exclusive,
            "rarity_tier": tier,
            "price_eur": price,
        })
    catalog.extend(_variant_expansion())
    catalog.extend(_expansion_1150_most_searched())
    # Deduplicate by ('franchise', 'name', 'item_type') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["franchise"], item["name"], item["item_type"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def _variant_expansion() -> list[dict]:
    """Exclusive/size/finish variants for existing Loungefly designs. ~60 items."""
    variants = [
        # Mini Backpack → Regular Backpack variants
        ("Disney", "Cinderella Castle Sequin Regular Backpack", "Backpack", "Disney Parks", "high", 110),
        ("Disney", "Mickey Mouse Holographic Regular Backpack", "Backpack", "Disney Parks", "high", 100),
        ("Disney", "Villains Scene AOP Regular Backpack", "Backpack", "Vaulted", "grail", 220),
        ("Sanrio", "Hello Kitty Monster Costumes Regular Backpack", "Backpack", "Hot Topic", "mid", 75),
        ("Pokemon", "Eevee Evolutions Regular Backpack", "Backpack", "BoxLunch", "mid", 85),
        # Mini Backpack → Crossbody Bag variants
        ("Disney", "Cinderella Castle Sequin Crossbody Bag", "Crossbody Bag", "Disney Parks", "mid", 65),
        ("Disney", "Sleeping Beauty Castle Crossbody Bag", "Crossbody Bag", "Disney Parks", "mid", 60),
        ("Disney", "Haunted Mansion Black Widow Bride Crossbody Bag", "Crossbody Bag", "Vaulted", "high", 180),
        ("Studio Ghibli", "Spirited Away No-Face Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 58),
        ("Studio Ghibli", "My Neighbor Totoro Catbus Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 55),
        ("Disney", "Maleficent Dragon Crossbody Bag", "Crossbody Bag", "Hot Topic", "standard", 45),
        # Mini Backpack → Wallet variants
        ("Disney", "Cinderella Castle Sequin Zip-Around Wallet", "Wallet", "Disney Parks", "standard", 40),
        ("Disney", "Villains Scene AOP Zip-Around Wallet", "Wallet", "Vaulted", "high", 100),
        ("Disney", "Haunted Mansion Black Widow Bride Wallet", "Wallet", "Vaulted", "high", 120),
        ("Sanrio", "Hello Kitty Monster Costumes Wallet", "Wallet", "Hot Topic", "standard", 35),
        ("Pokemon", "Eevee Evolutions Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 38),
        ("Disney", "Up Adventure Book Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 38),
        # BoxLunch exclusive → Hot Topic exclusive of same design (renamed to distinguish)
        ("Disney", "Wall-E & Eve Boot Plant Mini Backpack (HT Edition)", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Disney", "Up Adventure Book Mini Backpack (HT Edition)", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Studio Ghibli", "Spirited Away No-Face Mini Backpack (HT Edition)", "Mini Backpack", "Hot Topic", "mid", 68),
        # Disney Parks → BoxLunch exclusive crossovers
        ("Disney", "Sleeping Beauty Castle Mini Backpack (BL Edition)", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Disney", "Orange Bird Mini Backpack (BoxLunch Rerelease)", "Mini Backpack", "BoxLunch Rerelease", "high", 150),
        # Glow-in-the-dark variants
        ("Disney", "Nightmare Before Christmas Blacklight GITD Mini Backpack", "Mini Backpack", "Hot Topic GITD", "high", 95),
        ("Disney", "Haunted Mansion Hitchhiking Ghosts GITD Mini Backpack", "Mini Backpack", "Disney Parks GITD", "high", 130),
        ("Disney", "Villains Scene AOP GITD Mini Backpack", "Mini Backpack", "Vaulted GITD", "grail", 250),
        ("Disney", "Ursula Iridescent GITD Mini Backpack", "Mini Backpack", "Hot Topic GITD", "mid", 75),
        ("Marvel", "Venom Glow-in-the-Dark Mini Backpack", "Mini Backpack", "BoxLunch GITD", "mid", 72),
        ("Star Wars", "Darth Vader Glow-in-the-Dark Mini Backpack", "Mini Backpack", "BoxLunch GITD", "mid", 68),
        # Sequin → Standard variants (same design, different finish)
        ("Disney", "Cinderella Castle Standard Mini Backpack", "Mini Backpack", "Disney Parks", "standard", 48),
        ("Disney", "Fantasia Sorcerer Mickey Standard Mini Backpack", "Mini Backpack", "Standard", "mid", 65),
        ("Disney", "Snow White Evil Queen Standard Mini Backpack", "Mini Backpack", "Standard", "mid", 60),
        # Disney Parks → Disneyland Paris / Tokyo Disney exclusives
        ("Disney", "Cinderella Castle Sequin Mini Backpack (DLP)", "Mini Backpack", "Disneyland Paris", "high", 95),
        ("Disney", "Mickey Mouse Holographic Mini Backpack (TDL)", "Mini Backpack", "Tokyo Disney", "high", 100),
        ("Disney", "Sleeping Beauty Castle Mini Backpack (DLP)", "Mini Backpack", "Disneyland Paris", "high", 90),
        # Funko Shop exclusive variants
        ("Disney", "Maleficent Dragon Mini Backpack (Funko Shop)", "Mini Backpack", "Funko Shop", "high", 95),
        ("Sanrio", "Hello Kitty 50th Anniversary Mini Backpack", "Mini Backpack", "Funko Shop", "mid", 72),
        ("Disney", "Stitch Shoppe Ariel Mini Backpack (Funko Shop)", "Mini Backpack", "Funko Shop", "mid", 68),
        # SDCC / NYCC convention exclusives
        ("Disney", "Haunted Mansion Hitchhiking Ghosts SDCC Mini Backpack", "Mini Backpack", "SDCC Exclusive", "grail", 220),
        ("Marvel", "Spider-Man Across the Spider-Verse SDCC Mini Backpack", "Mini Backpack", "SDCC Exclusive", "high", 120),
        ("Star Wars", "Ahsoka Tano NYCC Mini Backpack", "Mini Backpack", "NYCC Exclusive", "high", 110),
        ("Disney", "Figment SDCC Mini Backpack", "Mini Backpack", "SDCC Exclusive", "high", 140),
        # Holiday / Seasonal variants
        ("Disney", "Mickey & Minnie Holiday 2024 Mini Backpack", "Mini Backpack", "Holiday LE", "mid", 68),
        ("Disney", "Nightmare Before Christmas Holiday Mini Backpack", "Mini Backpack", "Holiday LE", "mid", 72),
        ("Sanrio", "Hello Kitty Valentine's Day Mini Backpack", "Mini Backpack", "Seasonal LE", "mid", 65),
        ("Disney", "Stitch Halloween Cosplay Mini Backpack", "Mini Backpack", "Hot Topic Seasonal", "mid", 60),
        ("Disney", "Mickey Ears Spirit Jersey Mini Backpack (Christmas)", "Mini Backpack", "Disney Parks Seasonal", "mid", 75),
        # Collector Pin sets (bag + pin combos)
        ("Disney", "Orange Bird Mini Backpack + Pin Set", "Mini Backpack Set", "Disney Parks Bundle", "grail", 300),
        ("Disney", "Figment Mini Backpack + Pin Set", "Mini Backpack Set", "EPCOT Bundle", "high", 180),
        ("Disney", "Haunted Mansion Mini Backpack + Pin Set", "Mini Backpack Set", "Disney Parks Bundle", "grail", 280),
        # Additional retailer-exclusive crossbody variants
        ("Marvel", "Spider-Man Across the Spider-Verse Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 52),
        ("Star Wars", "Ahsoka Tano Crossbody Bag", "Crossbody Bag", "BoxLunch", "mid", 50),
        ("Pokemon", "Pikachu Cosplay Crossbody Bag", "Crossbody Bag", "BoxLunch", "standard", 42),
        ("Horror", "Chucky Doll Cosplay Crossbody Bag", "Crossbody Bag", "Hot Topic", "standard", 45),
        ("Sanrio", "Cinnamoroll Cloud Crossbody Bag", "Crossbody Bag", "Hot Topic", "standard", 40),
        # Additional wallet variants
        ("Marvel", "Spider-Man Across the Spider-Verse Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 35),
        ("Star Wars", "Grogu Cosplay Zip-Around Wallet", "Wallet", "BoxLunch", "standard", 36),
        ("Horror", "Ghostface Cosplay Zip-Around Wallet", "Wallet", "Hot Topic", "standard", 34),
        ("Sanrio", "Kuromi Halloween Zip-Around Wallet", "Wallet", "Hot Topic Seasonal", "standard", 38),
        ("Disney", "Encanto Mirabel Zip-Around Wallet", "Wallet", "Standard", "standard", 32),
    ]
    catalog = []
    for franchise, name, item_type, exclusive, tier, price in variants:
        catalog.append({
            "franchise": franchise,
            "name": name,
            "item_type": item_type,
            "exclusive": exclusive,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def _expansion_1150_most_searched() -> list[dict]:
    """~140 most-searched Loungefly items: Disney villains, Pixar, NBC, sequin,
    wallets/crossbody, parks exclusive, Pride, pet collections."""
    items = [
        # ── Disney Villains ─────────────────────────────────────────────────
        ("Disney", "Maleficent Dragon Scene Mini Backpack", "Mini Backpack", "Hot Topic", "grail", 130),
        ("Disney", "Maleficent Flames Glow-in-the-Dark Mini Backpack", "Mini Backpack", "BoxLunch", "high", 95),
        ("Disney", "Evil Queen Poison Apple Sequin Mini Backpack", "Mini Backpack", "Hot Topic", "high", 90),
        ("Disney", "Evil Queen Transformation Scene Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "high", 85),
        ("Disney", "Ursula Tentacles Iridescent Mini Backpack", "Mini Backpack", "Hot Topic", "high", 88),
        ("Disney", "Ursula Poor Unfortunate Souls Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 92),
        ("Disney", "Scar Be Prepared Mini Backpack", "Mini Backpack", "Hot Topic", "high", 85),
        ("Disney", "Scar Green Flames Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Disney", "Cruella De Vil Spots Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 65),
        ("Disney", "Jafar Snake Staff Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Disney", "Hades Ember Glow Mini Backpack", "Mini Backpack", "BoxLunch", "high", 78),
        ("Disney", "Captain Hook Jolly Roger Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 58),
        ("Disney", "Gaston Tavern Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Disney", "Villains Book Crossbody (All Villains Portraits)", "Crossbody", "BoxLunch", "high", 75),
        ("Disney", "Villains Scenes Wallet (All-Over Print)", "Wallet", "Hot Topic", "mid", 45),
        # ── Pixar ───────────────────────────────────────────────────────────
        ("Pixar", "Inside Out 2 Anxiety Mini Backpack", "Mini Backpack", "BoxLunch", "high", 78),
        ("Pixar", "Inside Out 2 All Emotions Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "high", 80),
        ("Pixar", "Inside Out 2 Joy & Sadness Wallet", "Wallet", "Standard", "mid", 38),
        ("Pixar", "Inside Out 2 Ennui Crossbody", "Crossbody", "BoxLunch", "mid", 52),
        ("Pixar", "Ratatouille Remy Cooking Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Pixar", "Ratatouille Anyone Can Cook Crossbody", "Crossbody", "Standard", "mid", 48),
        ("Pixar", "Coco Marigold Bridge Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 82),
        ("Pixar", "Coco Remember Me Guitar Crossbody", "Crossbody", "Loungefly Exclusive", "mid", 55),
        ("Pixar", "Coco Pepita & Dante Mini Backpack", "Mini Backpack", "Hot Topic", "high", 78),
        ("Pixar", "Up Adventure Book Mini Backpack", "Mini Backpack", "BoxLunch", "grail", 110),
        ("Pixar", "Up Carl & Ellie Balloon House Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "high", 90),
        ("Pixar", "Up Grape Soda Pin Wallet", "Wallet", "Standard", "mid", 35),
        ("Pixar", "Turning Red Mei Lee Panda Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Pixar", "Luca Sea Monster Scene Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 58),
        ("Pixar", "Wall-E & Eve Boot Plant Scene Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("Pixar", "Monsters Inc Boo's Door Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "high", 80),
        # ── Nightmare Before Christmas (NBC) ────────────────────────────────
        ("NBC", "Oogie Boogie Burlap Textured Mini Backpack", "Mini Backpack", "Hot Topic", "high", 88),
        ("NBC", "Oogie Boogie Blacklight Mini Backpack", "Mini Backpack", "BoxLunch", "high", 85),
        ("NBC", "Oogie Boogie Casino Scene Crossbody", "Crossbody", "Hot Topic", "mid", 55),
        ("NBC", "Lock Shock & Barrel Bathtub Mini Backpack", "Mini Backpack", "BoxLunch", "high", 82),
        ("NBC", "Lock Shock & Barrel Trick-or-Treat Mini Backpack", "Mini Backpack", "Hot Topic", "high", 78),
        ("NBC", "Lock Shock & Barrel Wallet", "Wallet", "Standard", "mid", 38),
        ("NBC", "Zero Ghost Dog Glow Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("NBC", "Spiral Hill Jack & Sally Scene Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "high", 85),
        ("NBC", "Jack Skellington Pumpkin King Sequin Mini Backpack", "Mini Backpack", "Hot Topic", "high", 90),
        ("NBC", "Sally Patchwork Mini Backpack (Glow Stitches)", "Mini Backpack", "BoxLunch", "high", 82),
        # ── Sequin Editions ─────────────────────────────────────────────────
        ("Disney", "Minnie Mouse Rose Gold Sequin Mini Backpack", "Mini Backpack", "Disney Parks", "high", 85),
        ("Disney", "Minnie Mouse Pastel Rainbow Sequin Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "high", 80),
        ("Disney", "Mickey Mouse Silver Sequin Mini Backpack", "Mini Backpack", "Standard", "mid", 65),
        ("Disney", "Ariel Green/Purple Sequin Flip Mini Backpack", "Mini Backpack", "Hot Topic", "high", 78),
        ("Disney", "Rapunzel Purple/Gold Sequin Mini Backpack", "Mini Backpack", "BoxLunch", "high", 75),
        ("Disney", "Stitch Blue Sequin Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "high", 80),
        ("Disney", "Tinker Bell Green Sequin Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 68),
        ("Disney", "Cinderella Blue Sequin Mini Backpack", "Mini Backpack", "Hot Topic", "high", 75),
        ("Disney", "Belle Gold Sequin Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 70),
        ("Disney", "Elsa Ice Blue Sequin Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 72),
        # ── Wallet / Crossbody for Popular Backpacks ────────────────────────
        ("Disney", "Haunted Mansion Hitchhiking Ghosts Wallet", "Wallet", "BoxLunch", "mid", 42),
        ("Disney", "Haunted Mansion Madame Leota Crossbody", "Crossbody", "Disney Parks", "high", 68),
        ("Disney", "Stitch Pineapple Crossbody", "Crossbody", "BoxLunch", "mid", 50),
        ("Disney", "Stitch Hibiscus Wallet", "Wallet", "Standard", "mid", 35),
        ("Disney", "Alice in Wonderland Cheshire Cat Crossbody", "Crossbody", "Hot Topic", "mid", 55),
        ("Disney", "Alice in Wonderland Tea Party Wallet", "Wallet", "BoxLunch", "mid", 38),
        ("Disney", "Bambi & Thumper Scene Crossbody", "Crossbody", "Loungefly Exclusive", "mid", 52),
        ("Disney", "Dumbo Circus Crossbody", "Crossbody", "BoxLunch", "mid", 48),
        ("Disney", "Lady and the Tramp Spaghetti Scene Crossbody", "Crossbody", "Loungefly Exclusive", "mid", 55),
        ("Disney", "Aristocats Everybody Wants to Be a Cat Wallet", "Wallet", "Standard", "mid", 35),
        ("Disney", "101 Dalmatians Cruella Book Crossbody", "Crossbody", "Hot Topic", "mid", 52),
        ("Disney", "Princess & the Frog Tiana Wallet", "Wallet", "BoxLunch", "mid", 38),
        # ── Disney Parks Exclusive Loungefly ────────────────────────────────
        ("Disney", "Disneyland 70th Anniversary Mini Backpack (Parks Exclusive)", "Mini Backpack", "Disney Parks", "grail", 120),
        ("Disney", "EPCOT Flower & Garden Festival 2025 Mini Backpack", "Mini Backpack", "Disney Parks", "high", 85),
        ("Disney", "Figment Rainbow One Little Spark Mini Backpack (Parks)", "Mini Backpack", "Disney Parks", "high", 90),
        ("Disney", "Orange Bird EPCOT Parks Exclusive Mini Backpack", "Mini Backpack", "Disney Parks", "high", 88),
        ("Disney", "Polynesian Resort Tiki Mini Backpack (Parks)", "Mini Backpack", "Disney Parks", "high", 85),
        ("Disney", "Main Street Confectionery Mini Backpack (Parks)", "Mini Backpack", "Disney Parks", "high", 80),
        ("Disney", "Galaxy's Edge Millennium Falcon Mini Backpack (Parks)", "Mini Backpack", "Disney Parks", "high", 82),
        ("Disney", "Tron Lightcycle Run Light-Up Mini Backpack (Parks)", "Mini Backpack", "Disney Parks", "grail", 110),
        ("Disney", "WDW 50th EARidescent Mini Backpack (Parks Exclusive)", "Mini Backpack", "Disney Parks", "grail", 125),
        ("Disney", "Animal Kingdom Tree of Life Mini Backpack (Parks)", "Mini Backpack", "Disney Parks", "high", 78),
        # ── Pride Collection ────────────────────────────────────────────────
        ("Disney", "Mickey Mouse Pride Rainbow Flag Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 65),
        ("Disney", "Mickey Mouse Pride Rainbow Heart Crossbody", "Crossbody", "BoxLunch", "mid", 48),
        ("Disney", "Mickey Mouse Pride Rainbow Wallet", "Wallet", "Standard", "mid", 35),
        ("Sanrio", "Hello Kitty Pride Rainbow Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 62),
        ("Lisa Frank", "Lisa Frank x Loungefly Pride Rainbow Tiger Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 60),
        ("Care Bears", "Care Bears Pride Rainbow Heart Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),
        ("My Little Pony", "My Little Pony Pride Rainbow Dash Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 55),
        # ── Pet Collections ─────────────────────────────────────────────────
        ("Disney", "Mickey Mouse Pet Harness & Leash Set", "Pet Accessory", "Loungefly Exclusive", "mid", 45),
        ("Disney", "Stitch Pet Harness & Leash Set", "Pet Accessory", "Loungefly Exclusive", "mid", 45),
        ("Disney", "Minnie Mouse Pet Carrier (Mini Backpack Style)", "Pet Accessory", "Loungefly Exclusive", "high", 75),
        ("Disney", "Mickey Mouse Pet Carrier (Mini Backpack Style)", "Pet Accessory", "Loungefly Exclusive", "high", 75),
        ("Star Wars", "Darth Vader Pet Harness & Leash Set", "Pet Accessory", "Loungefly Exclusive", "mid", 48),
        ("Star Wars", "Grogu Pet Carrier (Mini Backpack Style)", "Pet Accessory", "Loungefly Exclusive", "high", 78),
        ("Disney", "Lady and the Tramp Pet Bandana Set", "Pet Accessory", "Loungefly Exclusive", "mid", 28),
        ("Disney", "101 Dalmatians Pet Harness & Leash Set", "Pet Accessory", "Loungefly Exclusive", "mid", 45),
        # ── Additional High-Demand Lines ────────────────────────────────────
        ("Sanrio", "Kuromi & My Melody Contrast Mini Backpack", "Mini Backpack", "Hot Topic", "high", 78),
        ("Sanrio", "Cinnamoroll Cloud Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Sanrio", "Pompompurin Pudding Cup Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "mid", 60),
        ("Sanrio", "Hello Kitty 50th Anniversary Gold Mini Backpack", "Mini Backpack", "Loungefly Exclusive", "high", 85),
        ("Pokemon", "Pikachu Pokeball Mini Backpack", "Mini Backpack", "BoxLunch", "high", 78),
        ("Pokemon", "Eevee Evolutions Mini Backpack", "Mini Backpack", "Hot Topic", "high", 82),
        ("Pokemon", "Gengar Ghost Glow Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Marvel", "Scarlet Witch Crown Mini Backpack", "Mini Backpack", "BoxLunch", "high", 78),
        ("Marvel", "Loki Helmet Sequin Mini Backpack", "Mini Backpack", "Hot Topic", "high", 82),
        ("Harry Potter", "Deathly Hallows Sequin Mini Backpack", "Mini Backpack", "BoxLunch", "high", 80),
        ("Harry Potter", "Hogwarts Book Crossbody (All Houses)", "Crossbody", "Loungefly Exclusive", "mid", 55),
        ("Studio Ghibli", "Totoro Catbus Mini Backpack", "Mini Backpack", "BoxLunch", "grail", 110),
        ("Studio Ghibli", "Spirited Away No-Face Mini Backpack", "Mini Backpack", "BoxLunch", "high", 90),
        ("Studio Ghibli", "Kiki's Delivery Service Jiji Mini Backpack", "Mini Backpack", "Hot Topic", "high", 85),
        ("Pixar", "Toy Story Claw Machine Crossbody", "Crossbody", "BoxLunch", "mid", 55),
        ("Pixar", "Finding Nemo Submarine Voyage Mini Backpack", "Mini Backpack", "Disney Parks", "high", 80),
        ("Disney", "Moana Kakamora Coconut Crossbody", "Crossbody", "Loungefly Exclusive", "mid", 52),
        ("Disney", "Encanto Casita Mirabel Mini Backpack", "Mini Backpack", "BoxLunch", "high", 78),
        ("Disney", "Wish Star Mini Backpack (Glow)", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Disney", "Sleeping Beauty Fairies Mini Backpack (Flora/Fauna/Merryweather)", "Mini Backpack", "Loungefly Exclusive", "high", 80),
        ("Disney", "Pocahontas Meeko Crossbody", "Crossbody", "BoxLunch", "mid", 50),
        ("Disney", "Mulan Mushu Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 65),
        ("Disney", "Lilo & Stitch Scrump Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Disney", "Winnie the Pooh Honey Pot Crossbody", "Crossbody", "Loungefly Exclusive", "mid", 52),
        ("Disney", "Robin Hood Prince John Crown Jewels Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
    ]
    catalog = []
    for franchise, name, item_type, exclusive, tier, price in items:
        catalog.append({
            "franchise": franchise,
            "name": name,
            "item_type": item_type,
            "exclusive": exclusive,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    franchise = item["franchise"]
    name = item["name"]
    item_type = item["item_type"]
    exclusive = item["exclusive"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{franchise}-{name}"),
        title=f"Loungefly {name}",
        set_code=slugify(franchise),
        brand="Loungefly",
        rarity=item["rarity_tier"].title(),
        notes=f"{franchise} | {item_type}" + (f" | {exclusive}" if exclusive else ""),
        attributes_json={
            "franchise": franchise,
            "item_type": item_type,
            "exclusive": exclusive,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    exclusive = item["exclusive"]
    edition_scores = {
        "Vaulted": 0.90,
        "Vaulted Disney Parks": 0.95,
        "Disney Parks": 0.75,
        "BoxLunch": 0.65,
        "Hot Topic": 0.60,
        "Funko Shop": 0.80,
        "Halloween LE": 0.75,
        "Holiday LE": 0.70,
        "Pre-Funko": 0.90,
        "SDCC": 0.95,
        "NYCC": 0.90,
        "D23": 0.95,
        "Valentine LE": 0.65,
        "Easter LE": 0.60,
        "Amazon": 0.55,
        "Loungefly Exclusive": 0.65,
        "Convention": 0.90,
        "Standard": 0.30,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(exclusive, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Loungefly catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Loungefly Import ===")

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

    logger.info(f"\n=== Loungefly Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
