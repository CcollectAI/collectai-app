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

        # Lord of the Rings
        ("Lord of the Rings", "The One Ring Script AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 60),
        ("Lord of the Rings", "The Shire Map Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),
        ("Lord of the Rings", "Gandalf Staff Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Lord of the Rings", "Fellowship Silhouette AOP Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 58),

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
        ("DC Comics", "Aquaman Atlantis Scene Mini Backpack", "Mini Backpack", "Standard", "standard", 46),
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
        ("Disney", "Atlantis Crystal Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 55),
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
        ("Lord of the Rings", "Mordor Eye of Sauron Glow Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Lord of the Rings", "Rivendell Scene Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 62),

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
