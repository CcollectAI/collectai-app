"""
Import Designer Toys / Art Toys catalog (500+ items).

Layer 1 (Catalog):  Curated designer toy figures → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- KAWS full catalog (Companion, Flayed, BFF, Together, Gone, Clean Slate, Share, Separated,
  Accomplice, Bendy, Passing Through, Take, Along the Way, Holiday series, Chum, FAMILY)
- Bearbrick 100%+400% sets (BAPE, Stussy, Neighborhood, Atmos, Nike SB, Cleverin, Kith,
  Supreme, Dior, Chrome Hearts, Kanye, Mastermind, CLOT, Karimoku), 1000% (40+ grails),
  Bearbrick Series blind boxes
- Pop Mart (Molly, Dimoo, PUCKY, LABUBU, Hirono, Zsiga, Skullpanda, CRYBABY, Sweet Bean,
  The Monsters, Space Molly 400%/1000% Mega Collection)
- Superplastic (Janky series 1-5, Guggimon, Kranky, Dayzee, Superdoodle, J Balvin collab)
- Coarse figures (Omen, Noop, Pain, Top, False Friends)
- Ron English (MC Supersized, Popaganda, Temper Tot, FAT Tony, Astronaut Grin)
- Takashi Murakami (ComplexCon, Kaikai Kiki, Mr. DOB, Doraemon, Flower, OVO)
- Kidrobot full Dunny archive (20+ Dunnys), Labbit, Munny, South Park, Simpsons, TMNT
- BAIT exclusives (Astro Boy, Street Fighter, Ultraman)
- Mighty Jaxx XXRay (Batman, Elmo, Spongebob, Mickey, Deadpool), Kandy, Mightyverse
- Unruly Industries (Spider-Gwen, Batman, Joker, Wolverine, Venom, Miles Morales, Harley)
- Secret Base (Skull Bee, Honey Bear, Ghost Bear)
- Hot Toys Cosbaby (Marvel, Star Wars, DC, Disney)
- Fools Paradise (Astro Boy, Pinocchio, Mad Dog, Joker, Rocky, Narcos, Django)
- Vinyl Collectibles Dolls / VCD by Medicom (Snoopy, Mickey, Ultraman, Godzilla, Astro Boy)
- Daniel Arsham (Eroded Pikachu, Future Relic, Crystal Relic, Rubik's Cube, Gameboy, Porsche)
- A Bathing Ape / BAPE figures (Baby Milo, Star Wars, Dragon Ball)
- FigureComplex / Revoltech Amazing Yamaguchi (Batman, Spider-Man, Deadpool, Wolverine)
- ComplexCon Exclusives, J Balvin, How2Work, T9G, INSTINCTOY, Sticky Monster Lab
- Clutter Gallery Exclusives, Devil Toys / Quiccs TEQ63, Luke Chueh, Hebru Brantley
- James Jean, Futura Laboratories, CPFM, Futura

Usage:
    python -m pipelines.import_designer_toys [--dry-run]
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

CATEGORY = "designer_toys"


def get_curated_catalog() -> list[dict]:
    """Curated designer toy catalog covering major artists and brands (500+ items)."""

    # (brand, line, name, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>1500), high (500-1500), mid (100-500), standard (<100)

    toys = [
        # ── KAWS Companions ──────────────────────────────────────────────
        ("KAWS", "Companion", "Companion Open Edition Grey", "Open Edition", "mid", 280),
        ("KAWS", "Companion", "Companion Open Edition Black", "Open Edition", "mid", 300),
        ("KAWS", "Companion", "Companion Open Edition Brown", "Open Edition", "mid", 320),
        ("KAWS", "Companion", "Companion Open Edition Pink", "Open Edition", "mid", 350),
        ("KAWS", "Companion", "Companion Flayed Grey", "Open Edition", "mid", 300),
        ("KAWS", "Companion", "Companion Flayed Black", "Open Edition", "mid", 320),
        ("KAWS", "Companion", "Companion Flayed Brown", "Open Edition", "mid", 340),
        ("KAWS", "Companion", "Dissected Companion Grey 2006", "Limited", "grail", 2800),
        ("KAWS", "Companion", "Dissected Companion Brown 2006", "Limited", "grail", 2600),
        ("KAWS", "Companion", "Resting Place Companion", "Limited", "high", 1200),
        ("KAWS", "Small Lie", "Small Lie Grey", "Open Edition", "mid", 250),
        ("KAWS", "Small Lie", "Small Lie Black", "Open Edition", "mid", 270),
        ("KAWS", "BFF", "BFF Pink", "Open Edition", "mid", 350),
        ("KAWS", "BFF", "BFF Blue", "Open Edition", "mid", 380),
        ("KAWS", "Together", "Together Grey", "Open Edition", "mid", 450),
        ("KAWS", "Holiday", "Holiday Japan (Mount Fuji)", "Limited", "high", 900),
        ("KAWS", "Holiday", "Holiday Singapore", "Limited", "high", 800),
        ("KAWS", "What Party", "What Party White", "Open Edition", "mid", 150),
        # KAWS expanded
        ("KAWS", "Gone", "Gone Companion Grey", "Open Edition", "mid", 400),
        ("KAWS", "Gone", "Gone Companion Black", "Open Edition", "mid", 420),
        ("KAWS", "Clean Slate", "Clean Slate Grey", "Open Edition", "mid", 380),
        ("KAWS", "Clean Slate", "Clean Slate Brown", "Open Edition", "mid", 400),
        ("KAWS", "Share", "Share Companion Grey", "Open Edition", "mid", 420),
        ("KAWS", "Share", "Share Companion Black", "Open Edition", "mid", 440),
        ("KAWS", "Seeing/Watching", "Seeing/Watching Grey", "Limited", "high", 850),
        ("KAWS", "Astro Boy", "KAWS Astro Boy Companion", "Collab", "grail", 2200),
        ("KAWS", "Sesame Street", "KAWS x Sesame Street Ernie", "Collab", "mid", 350),
        ("KAWS", "Sesame Street", "KAWS x Sesame Street BFF Elmo", "Collab", "mid", 380),
        ("KAWS", "Pinocchio", "KAWS Pinocchio & Jiminy Cricket", "Limited", "high", 1100),
        ("KAWS", "Chum", "Chum White", "Limited", "high", 950),

        # ── Bearbrick 1000% ──────────────────────────────────────────────
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Basquiat V1", "Collab", "high", 1400),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Basquiat V2", "Collab", "high", 1200),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Banksy Flower Bomber", "Collab", "grail", 3500),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% fragment design", "Collab", "grail", 4200),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Keith Haring V1", "Collab", "high", 1100),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% BAPE Camo Green", "Collab", "grail", 3800),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Hajime Sorayama Sexy Robot", "Collab", "grail", 4800),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Karimoku Carved Wood", "Collab", "grail", 5000),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Basquiat V1", "Collab", "mid", 350),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Banksy Flower Bomber", "Collab", "high", 500),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% fragment design", "Collab", "high", 550),
        # Bearbrick expanded — 100%+400% sets
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% BAPE Camo Green", "Collab", "high", 600),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Stussy Black", "Collab", "high", 520),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Neighborhood Black", "Collab", "high", 500),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Atmos Elephant", "Collab", "mid", 450),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Nike SB Dunk", "Collab", "high", 580),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Cleverin Blue", "Collab", "mid", 200),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Kith Treats", "Collab", "mid", 420),
        # Bearbrick expanded — 1000%
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Andy Warhol Flowers", "Collab", "grail", 3200),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Jackson Pollock Studio", "Collab", "grail", 2800),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Stussy 30th Anniversary", "Collab", "grail", 3500),
        # Bearbrick Series blind boxes
        ("Medicom", "Bearbrick Series", "Bearbrick Series 44 Sealed Case", "Blind Box Set", "standard", 95),
        ("Medicom", "Bearbrick Series", "Bearbrick Series 43 Sealed Case", "Blind Box Set", "standard", 90),

        # ── Pop Mart ─────────────────────────────────────────────────────
        ("Pop Mart", "Molly", "Molly Anniversary Statues Series", "Blind Box Set", "standard", 75),
        ("Pop Mart", "Molly", "Molly x Instinctoy Erosion", "Collab", "mid", 180),
        ("Pop Mart", "Dimoo", "Dimoo World Heritage Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "Dimoo", "Dimoo Fairy Tale Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "Skullpanda", "Skullpanda Night City Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "The Monsters", "The Monsters Circus Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "Mega Collection", "Mega Collection 1000% Space Molly Jasmine", "Mega", "high", 900),
        ("Pop Mart", "Mega Collection", "Mega Collection 1000% Space Molly Christmas", "Mega", "high", 1100),
        # Pop Mart expanded
        ("Pop Mart", "PUCKY", "PUCKY Sleeping Forest Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "PUCKY", "PUCKY Pool Babies Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "LABUBU", "LABUBU The Monsters Tasty Life Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "LABUBU", "LABUBU Have a Seat Series", "Blind Box Set", "standard", 70),
        ("Pop Mart", "Hirono", "Hirono The Other One Series", "Blind Box Set", "standard", 75),
        ("Pop Mart", "Zsiga", "Zsiga Walking Into the Forest Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "The Monsters", "The Monsters Toys Series Full Case", "Blind Box Set", "standard", 80),
        ("Pop Mart", "Space Molly", "Space Molly 400% Pinkerton", "Limited", "high", 650),

        # ── Superplastic ─────────────────────────────────────────────────
        ("Superplastic", "Janky", "Janky Series 1 Full Case", "Blind Box Set", "standard", 90),
        ("Superplastic", "Janky", "Janky x Guggimon OG", "Standard", "standard", 25),
        ("Superplastic", "Guggimon", "Guggimon Supervillain 8-inch", "Standard", "mid", 120),
        ("Superplastic", "Guggimon", "Guggimon x Fortnite Edition", "Collab", "mid", 200),
        ("Superplastic", "Kranky", "Kranky Superplastic 8-inch Glow", "Limited", "mid", 180),
        ("Superplastic", "Janky", "Janky x BAIT Edition", "Collab", "mid", 350),

        # ── Coarse ───────────────────────────────────────────────────────
        ("Coarse", "Omen", "Omen Fade 10-inch", "Limited", "mid", 350),
        ("Coarse", "Omen", "Omen Rise 10-inch", "Limited", "mid", 380),
        ("Coarse", "Noop", "Noop Blackout Edition", "Limited", "high", 600),
        ("Coarse", "Pain", "Pain Ignite 14-inch", "Limited", "high", 750),

        # ── Ron English ──────────────────────────────────────────────────
        ("Ron English", "MC Supersized", "MC Supersized Original Colorway", "Limited", "mid", 400),
        ("Ron English", "MC Supersized", "MC Supersized Glow-in-Dark", "Limited", "high", 600),
        ("Ron English", "Temper Tot", "Temper Tot OG Red", "Limited", "mid", 250),
        ("Ron English", "Telegrinnies", "Telegrinnies Full Set", "Limited", "mid", 350),

        # ── Takashi Murakami ─────────────────────────────────────────────
        ("Takashi Murakami", "ComplexCon", "Flower Parent and Child (Blue/White)", "ComplexCon Exclusive", "grail", 1800),
        ("Takashi Murakami", "ComplexCon", "Murakami x KAWS Flower", "ComplexCon Exclusive", "grail", 2200),
        ("Takashi Murakami", "Kaikai Kiki", "Mr. DOB Figure Gold", "Limited", "high", 900),
        ("Takashi Murakami", "Kaikai Kiki", "Flower Ball 3D Magnet Set", "Standard", "mid", 200),

        # ── Kidrobot ─────────────────────────────────────────────────────
        ("Kidrobot", "Dunny", "Dunny 8-inch Huck Gee Gold Life", "Limited", "high", 550),
        ("Kidrobot", "Dunny", "Dunny 8-inch Kronk Wild Ones", "Limited", "mid", 300),
        ("Kidrobot", "Dunny", "Dunny 8-inch Jon-Paul Kaiser Noir", "Limited", "mid", 350),
        ("Kidrobot", "Dunny", "Dunny 3-inch Series 2012 Full Case", "Blind Box Set", "standard", 85),
        ("Kidrobot", "Dunny", "Dunny 3-inch Azteca II Full Case", "Blind Box Set", "standard", 90),
        ("Kidrobot", "Munny", "Munny DIY 7-inch Blank White", "Standard", "standard", 30),
        ("Kidrobot", "Dunny", "Mega Man 8-inch Dunny Blue", "Collab", "mid", 250),
        ("Kidrobot", "South Park", "South Park Cartman 6-inch Vinyl", "Collab", "mid", 120),
        ("Kidrobot", "South Park", "South Park Kenny 6-inch Vinyl", "Collab", "mid", 110),
        ("Kidrobot", "Simpsons", "Simpsons Homer Buddha 7-inch", "Collab", "mid", 180),

        # ── BAIT Exclusives ──────────────────────────────────────────────
        ("BAIT", "Astro Boy", "BAIT x Astro Boy Mechanics 10-inch", "Collab", "high", 500),
        ("BAIT", "Astro Boy", "BAIT x Astro Boy Atom Glow-in-Dark", "Collab", "high", 550),
        ("BAIT", "Street Fighter", "BAIT x Street Fighter Ryu 10-inch", "Collab", "mid", 350),
        ("BAIT", "Street Fighter", "BAIT x Street Fighter Akuma 10-inch", "Collab", "mid", 380),
        ("BAIT", "Ultraman", "BAIT x Ultraman Diecast 8-inch", "Collab", "high", 600),

        # ── Mighty Jaxx ──────────────────────────────────────────────────
        ("Mighty Jaxx", "XXRay", "XXRay Batman 10-inch by Jason Freeny", "Collab", "mid", 250),
        ("Mighty Jaxx", "XXRay", "XXRay Elmo 10-inch by Jason Freeny", "Collab", "mid", 200),
        ("Mighty Jaxx", "XXRay", "XXRay Spongebob 10-inch by Jason Freeny", "Collab", "mid", 220),
        ("Mighty Jaxx", "XXRay", "XXRay Pikachu 4-inch by Jason Freeny", "Collab", "mid", 180),
        ("Mighty Jaxx", "XXRay Plus", "XXRay Plus Dissected Kaws Companion", "Collab", "mid", 280),
        ("Mighty Jaxx", "Mightyverse", "Mightyverse COTE Blind Box Set", "Blind Box Set", "standard", 55),
        ("Mighty Jaxx", "Mightyverse", "Mightyverse Freeny Hidden Dissectibles One Piece", "Blind Box Set", "standard", 65),
        ("Mighty Jaxx", "Jason Freeny", "Balloon Dog Anatomy Red by Jason Freeny", "Limited", "mid", 320),

        # ── Unruly Industries ────────────────────────────────────────────
        ("Unruly Industries", "Marvel", "Spider-Gwen Designer Statue", "Limited", "high", 550),
        ("Unruly Industries", "DC", "Batman Designer Statue by Joe DellaGatta", "Limited", "high", 600),
        ("Unruly Industries", "DC", "Joker Designer Statue", "Limited", "high", 580),
        ("Unruly Industries", "Marvel", "Wolverine Designer Statue", "Limited", "high", 520),
        ("Unruly Industries", "Marvel", "Venom Designer Statue", "Limited", "high", 650),

        # ── Secret Base ──────────────────────────────────────────────────
        ("Secret Base", "Skull Bee", "Skull Bee OG Black Edition", "Limited", "high", 700),
        ("Secret Base", "Skull Bee", "Skull Bee Gold Chrome Edition", "Limited", "grail", 1600),
        ("Secret Base", "Honey Bear", "Honey Bear Clear Blue Edition", "Limited", "high", 550),
        ("Secret Base", "Ghost Bear", "Ghost Bear Collab x BAIT", "Collab", "high", 800),
        ("Secret Base", "Ghost Bear", "Ghost Bear OG Glow-in-Dark", "Limited", "high", 650),

        # ── Hot Toys Cosbaby ─────────────────────────────────────────────
        ("Hot Toys", "Cosbaby Marvel", "Cosbaby Iron Man Mark L", "Standard", "standard", 45),
        ("Hot Toys", "Cosbaby Marvel", "Cosbaby Spider-Man Integrated Suit", "Standard", "standard", 40),
        ("Hot Toys", "Cosbaby Star Wars", "Cosbaby The Mandalorian & Grogu", "Standard", "standard", 50),
        ("Hot Toys", "Cosbaby Star Wars", "Cosbaby Darth Vader Lightsaber", "Standard", "standard", 40),
        ("Hot Toys", "Cosbaby DC", "Cosbaby Batman The Dark Knight", "Standard", "standard", 45),
        ("Hot Toys", "Cosbaby DC", "Cosbaby Joker The Dark Knight", "Standard", "standard", 45),

        # ── Fools Paradise ───────────────────────────────────────────────
        ("Fools Paradise", "Astro Boy", "Astro Boy Homage OG Edition", "Limited", "high", 750),
        ("Fools Paradise", "Astro Boy", "Astro Boy Homage Stealth Black", "Limited", "high", 800),
        ("Fools Paradise", "Pinocchio", "Pinocchio Cool Kid Edition", "Limited", "high", 700),
        ("Fools Paradise", "Mad Dog", "Michael Mad Dog Scarface Edition", "Limited", "high", 650),
        ("Fools Paradise", "Mad Dog", "Michael Mad Dog OG White Suit", "Limited", "high", 680),

        # ── Vinyl Collectibles Dolls (VCD) by Medicom ────────────────────
        ("Medicom", "VCD", "VCD Snoopy & Woodstock 1997", "Limited", "high", 800),
        ("Medicom", "VCD", "VCD Snoopy Joe Cool", "Standard", "mid", 250),
        ("Medicom", "VCD", "VCD Mickey Mouse Standard", "Standard", "mid", 200),
        ("Medicom", "VCD", "VCD Mickey Mouse Vintage B&W", "Limited", "mid", 350),
        ("Medicom", "VCD", "VCD Ultraman Type A", "Limited", "high", 600),

        # ── Daniel Arsham ────────────────────────────────────────────────
        ("Daniel Arsham", "Eroded", "Eroded Pikachu 2020 (Blue)", "Limited", "grail", 2500),
        ("Daniel Arsham", "Eroded", "Eroded Pikachu 2020 (Pink)", "Limited", "grail", 2800),
        ("Daniel Arsham", "Future Relic", "Future Relic 09 Eroded Turntable", "Limited", "grail", 3500),
        ("Daniel Arsham", "Future Relic", "Future Relic 06 Eroded Camera", "Limited", "grail", 2000),
        ("Daniel Arsham", "Crystal Relic", "Crystal Relic 002 Porsche 911", "Limited", "grail", 4500),

        # ── A Bathing Ape / BAPE Figures ─────────────────────────────────
        ("BAPE", "Baby Milo", "Baby Milo 10-inch Vinyl OG Green", "Standard", "mid", 180),
        ("BAPE", "Baby Milo", "Baby Milo 10-inch Vinyl Camo", "Limited", "mid", 350),
        ("BAPE", "Star Wars", "BAPE x Star Wars Stormtrooper 12-inch", "Collab", "high", 700),
        ("BAPE", "Star Wars", "BAPE x Star Wars Darth Vader 12-inch", "Collab", "high", 750),
        ("BAPE", "Dragon Ball", "BAPE x Dragon Ball Z Son Goku Figure", "Collab", "high", 500),

        # ── FigureComplex / Revoltech Amazing Yamaguchi ──────────────────
        ("Kaiyodo", "Amazing Yamaguchi", "Amazing Yamaguchi Batman No.009", "Standard", "mid", 120),
        ("Kaiyodo", "Amazing Yamaguchi", "Amazing Yamaguchi Spider-Man No.002", "Standard", "mid", 130),
        ("Kaiyodo", "Amazing Yamaguchi", "Amazing Yamaguchi Deadpool No.001", "Standard", "mid", 110),
        ("Kaiyodo", "Amazing Yamaguchi", "Amazing Yamaguchi Wolverine No.005", "Standard", "mid", 140),
        ("Kaiyodo", "Amazing Yamaguchi", "Amazing Yamaguchi Iron Man Bleeding Edge", "Standard", "mid", 150),

        # ── KAWS Additional ─────────────────────────────────────────────────
        ("KAWS", "Companion", "Companion Passing Through Grey", "Open Edition", "mid", 380),
        ("KAWS", "Companion", "Companion Passing Through Black", "Open Edition", "mid", 400),
        ("KAWS", "Companion", "Take Companion Grey", "Open Edition", "mid", 320),
        ("KAWS", "Companion", "Take Companion Black", "Open Edition", "mid", 340),
        ("KAWS", "Separated", "Separated Companion Brown", "Open Edition", "mid", 350),
        ("KAWS", "Separated", "Separated Companion Black", "Open Edition", "mid", 370),
        ("KAWS", "Accomplice", "Accomplice Pink Rabbit", "Limited", "high", 1400),
        ("KAWS", "Bendy", "Bendy Companion Black", "Limited", "high", 900),

        # ── Bearbrick 100%+400% Additional ──────────────────────────────────
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Kanye West Graduation", "Collab", "high", 700),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Grateful Dead Dancing Bear Green", "Collab", "mid", 380),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Clot Silk", "Collab", "high", 650),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Mastermind Japan Black Chrome", "Collab", "high", 800),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Coca-Cola Red", "Collab", "mid", 300),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Chrome Hearts", "Collab", "grail", 2200),

        # ── Bearbrick 1000% Additional ─────────────────────────────────────
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Kith x Coca-Cola", "Collab", "grail", 3000),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Van Gogh Self Portrait", "Collab", "high", 1300),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Peanuts Snoopy", "Collab", "high", 1100),

        # ── Pop Mart Additional ─────────────────────────────────────────────
        ("Pop Mart", "LABUBU", "LABUBU Macaron Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "Molly", "Molly Bugs Series", "Blind Box Set", "standard", 70),
        ("Pop Mart", "Dimoo", "Dimoo Dating Day Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "Skullpanda", "Skullpanda Tell Me What You Want Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "Mega Collection", "Mega Collection 1000% Space Molly Doraemon", "Mega", "high", 1200),
        ("Pop Mart", "Hirono", "Hirono Little Mischief Series", "Blind Box Set", "standard", 70),
        ("Pop Mart", "Crybaby", "Crybaby Crying Parade Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "LABUBU", "LABUBU Time to Chill Vinyl 10-inch", "Limited", "mid", 180),

        # ── Superplastic Additional ─────────────────────────────────────────
        ("Superplastic", "Janky", "Janky Series 3 Full Case", "Blind Box Set", "standard", 95),
        ("Superplastic", "Guggimon", "Guggimon Halloween Edition 8-inch", "Limited", "mid", 250),
        ("Superplastic", "Dayzee", "Dayzee OG 8-inch", "Standard", "mid", 120),

        # ── Coarse Additional ───────────────────────────────────────────────
        ("Coarse", "Noop Noop", "Noop Noop Midnight Pair", "Limited", "high", 500),
        ("Coarse", "False Friends", "False Friends (Ignite & Fade Pair)", "Limited", "high", 700),

        # ── T9G / Rangeas / Other JP Artists ────────────────────────────────
        ("T9G", "Rangeas", "Rangeas OG Pink Edition", "Limited", "mid", 350),
        ("T9G", "Rangeas", "Rangeas Glow-in-Dark Black", "Limited", "high", 500),
        ("Instinctoy", "Erosion", "Erosion Molly x Instinctoy Pink BG", "Collab", "mid", 220),
        ("Instinctoy", "Liquid", "Liquid Spongebob by Instinctoy", "Collab", "mid", 280),

        # ── Futura Laboratories ────────────────────────────────────────────
        ("Futura Laboratories", "FL Pointman", "Pointman 12-inch OG Blue", "Limited", "high", 800),
        ("Futura Laboratories", "FL Pointman", "Pointman 6-inch UNKLE", "Collab", "high", 600),

        # ── Hebru Brantley ─────────────────────────────────────────────────
        ("Hebru Brantley", "Flyboy", "Flyboy 18-inch OG", "Limited", "high", 900),
        ("Hebru Brantley", "Lil Mama", "Lil Mama 12-inch Edition", "Limited", "high", 700),

        # ── James Jean ─────────────────────────────────────────────────────
        ("James Jean", "Descendant", "Descendant Blue Vinyl 10-inch", "Limited", "high", 650),

        # ── Clutter Magazine Exclusives ────────────────────────────────────
        ("Clutter", "Dunny", "Clutter x Dunny Custom Series Sealed Set", "Limited", "mid", 200),

        # ── JBalvin x KAWS ─────────────────────────────────────────────────
        ("KAWS", "FAMILY", "FAMILY Figure Set (Brown)", "Limited", "high", 1300),

        # ── Sticky Monster Lab ─────────────────────────────────────────────
        ("Sticky Monster Lab", "Kibon", "Kibon OG Edition 6-inch", "Limited", "mid", 180),
        ("Sticky Monster Lab", "Kibon", "Kibon Glow-in-Dark Edition", "Limited", "mid", 250),
        ("Sticky Monster Lab", "Bo", "Bo Sitting 4-inch", "Standard", "standard", 55),

        # ── Luke Chueh ─────────────────────────────────────────────────────
        ("Luke Chueh", "Possessed", "Possessed Bear OG White", "Limited", "mid", 350),
        ("Luke Chueh", "Possessed", "Possessed Bear Blood Red", "Limited", "high", 500),

        # ── Doraemon x Takashi Murakami ────────────────────────────────────
        ("Takashi Murakami", "Doraemon", "Doraemon Flower Ball 12-inch", "Collab", "high", 1400),
        ("Takashi Murakami", "Doraemon", "Doraemon Superflat Mini Figure Set", "Collab", "mid", 250),

        # ── Cactus Plant Flea Market x Nike (Art Figure) ───────────────────
        ("CPFM", "Flea Market Smiley", "Smiley Face 12-inch Glow", "Collab", "high", 800),

        # ── Quiccs by Devil Toys ───────────────────────────────────────────
        ("Devil Toys", "TEQ63", "TEQ63 OG Grey 6-inch by Quiccs", "Standard", "mid", 120),
        ("Devil Toys", "TEQ63", "TEQ63 Stealth Black 6-inch by Quiccs", "Limited", "mid", 250),

        # ── KAWS Grails & Rare Variants ────────────────────────────────────
        ("KAWS", "Companion", "Companion 4-Foot Grey 2007", "Limited", "grail", 15000),
        ("KAWS", "Companion", "Companion Flayed 4-Foot 2009", "Limited", "grail", 18000),
        ("KAWS", "Companion", "Five Years Later Companion Grey", "Limited", "grail", 3500),
        ("KAWS", "Companion", "Resting Place Black 2013", "Limited", "high", 1400),
        ("KAWS", "Companion", "Companion Originalfake Grey 2006", "Limited", "grail", 3000),
        ("KAWS", "Holiday", "Holiday Hong Kong 2019", "Limited", "high", 750),
        ("KAWS", "Holiday", "Holiday United Kingdom 2021", "Limited", "high", 650),
        ("KAWS", "Holiday", "Holiday Changbai Mountain 2020", "Limited", "high", 800),
        ("KAWS", "WHAT PARTY", "What Party Yellow", "Open Edition", "mid", 160),
        ("KAWS", "WHAT PARTY", "What Party Orange", "Open Edition", "mid", 160),
        ("KAWS", "Companion", "Companion Blush Pink 2016", "Open Edition", "mid", 380),
        ("KAWS", "Chum", "Chum Black 2002", "Limited", "grail", 2200),
        ("KAWS", "Along the Way", "Along the Way Brown", "Open Edition", "mid", 450),
        ("KAWS", "Along the Way", "Along the Way Black", "Open Edition", "mid", 470),
        ("KAWS", "FAMILY", "FAMILY Figure Set (Grey)", "Limited", "high", 1200),

        # ── Bearbrick 1000% Grails ─────────────────────────────────────────
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Chanel (Karl Lagerfeld)", "Collab", "grail", 12000),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Pushead V5 Silver", "Collab", "grail", 5500),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Daft Punk (Silver Chrome)", "Collab", "grail", 8000),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% KITH 10th Anniversary", "Collab", "grail", 4000),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% BAPE ABC Camo Pink", "Collab", "grail", 4500),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Emotionally Unavailable Black Heart", "Collab", "grail", 3500),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Atmos Elephant", "Collab", "grail", 3000),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Mastermind Japan Gold Stripe", "Collab", "grail", 5000),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% My First Be@rbrick B@by", "Standard", "high", 1400),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Space Invaders", "Collab", "high", 1200),

        # ── Bearbrick 400% & 100%+400% Additional ─────────────────────────
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% CLOT Silk Royale", "Collab", "high", 700),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% BAPE 28th Anniversary", "Collab", "high", 600),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Supreme Red Box Logo", "Collab", "high", 900),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Dior Homme", "Collab", "grail", 2500),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Jean-Michel Basquiat V4", "Collab", "high", 500),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Sex Pistols", "Collab", "mid", 400),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% My First Be@rbrick B@by Pearl", "Standard", "high", 550),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Oasis", "Collab", "mid", 350),

        # ── Pop Mart LABUBU Expanded ───────────────────────────────────────
        ("Pop Mart", "LABUBU", "LABUBU Exciting Macaron Series", "Blind Box Set", "standard", 70),
        ("Pop Mart", "LABUBU", "LABUBU The Monsters Candy World", "Blind Box Set", "standard", 65),
        ("Pop Mart", "LABUBU", "LABUBU x Lisa Vinyl Plush 30cm", "Collab", "high", 500),
        ("Pop Mart", "LABUBU", "LABUBU Woodland Elves Series", "Blind Box Set", "standard", 75),
        ("Pop Mart", "LABUBU", "LABUBU The Monsters Let's Camping", "Blind Box Set", "standard", 60),
        ("Pop Mart", "LABUBU", "LABUBU Spooky Night Glow-in-Dark", "Limited", "mid", 200),

        # ── Pop Mart Space Molly & Mega ────────────────────────────────────
        ("Pop Mart", "Space Molly", "Space Molly 400% Mika", "Limited", "high", 700),
        ("Pop Mart", "Space Molly", "Space Molly 400% Back to the Future", "Collab", "high", 800),
        ("Pop Mart", "Mega Collection", "Mega Collection 1000% Space Molly Barbie", "Mega", "grail", 1800),
        ("Pop Mart", "Mega Collection", "Mega Collection 1000% Space Molly SpongeBob", "Mega", "high", 1400),
        ("Pop Mart", "Mega Collection", "Mega Collection 400% Space Molly Coca-Cola", "Mega", "high", 600),
        ("Pop Mart", "Space Molly", "Space Molly 400% The Powerpuff Girls", "Collab", "high", 550),

        # ── Pop Mart Skullpanda & Hirono Expanded ──────────────────────────
        ("Pop Mart", "Skullpanda", "Skullpanda The Sound Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "Skullpanda", "Skullpanda Hype Panda Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "Hirono", "Hirono Mime Series", "Blind Box Set", "standard", 75),
        ("Pop Mart", "Hirono", "Hirono The Other One Witch Series", "Blind Box Set", "standard", 80),
        ("Pop Mart", "Crybaby", "Crybaby Monster Tears Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "Dimoo", "Dimoo No Borders Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "Dimoo", "Dimoo Letters from Snowman", "Blind Box Set", "standard", 60),

        # ── Takashi Murakami Expanded ──────────────────────────────────────
        ("Takashi Murakami", "ComplexCon", "Flower Parent and Child (Red/Blue)", "ComplexCon Exclusive", "grail", 2000),
        ("Takashi Murakami", "Kaikai Kiki", "Mr. DOB Figure Red/Blue", "Limited", "high", 850),
        ("Takashi Murakami", "Kaikai Kiki", "Flower Cushion Rainbow 60cm", "Standard", "mid", 350),
        ("Takashi Murakami", "ComplexCon", "Murakami x Billie Eilish Figure", "ComplexCon Exclusive", "grail", 1600),
        ("Takashi Murakami", "Kaikai Kiki", "Panda Figure Sleeping 12-inch", "Limited", "high", 700),

        # ── Daniel Arsham Expanded ─────────────────────────────────────────
        ("Daniel Arsham", "Eroded", "Eroded Porsche 911 Turbo", "Limited", "grail", 5000),
        ("Daniel Arsham", "Eroded", "Eroded Basketball (Blue)", "Limited", "high", 800),
        ("Daniel Arsham", "Future Relic", "Future Relic 01 Eroded VHS Tape", "Limited", "high", 1200),
        ("Daniel Arsham", "Crystal Relic", "Crystal Relic 001 Air Jordan 4", "Limited", "grail", 3000),
        ("Daniel Arsham", "Eroded", "Eroded Bronze Teddy Bear", "Limited", "grail", 2500),
        ("Daniel Arsham", "Snarkitecture", "Snarkitecture x Arsham Figure Set", "Limited", "high", 900),

        # ── James Jean Expanded ────────────────────────────────────────────
        ("James Jean", "Descendant", "Descendant Horse Rider 12-inch", "Limited", "grail", 1800),
        ("James Jean", "Descendant", "Descendant Pink/Gold 10-inch", "Limited", "high", 750),
        ("James Jean", "Azimuth", "Azimuth Figure 10-inch", "Limited", "high", 600),

        # ── Superplastic Expanded ──────────────────────────────────────────
        ("Superplastic", "Janky", "Janky Series 4 Full Case", "Blind Box Set", "standard", 95),
        ("Superplastic", "Guggimon", "Guggimon x Pete Davidson Edition", "Collab", "mid", 300),
        ("Superplastic", "Janky", "Janky x Gorillaz Edition", "Collab", "mid", 280),
        ("Superplastic", "Guggimon", "Guggimon Nightmare Edition 12-inch", "Limited", "high", 500),
        ("Superplastic", "Superdoodle", "Superdoodle Frenzy 8-inch", "Limited", "mid", 180),

        # ── Kidrobot Expanded ──────────────────────────────────────────────
        ("Kidrobot", "Dunny", "Dunny 20-inch Huck Gee Post-Apocalypse", "Limited", "grail", 1800),
        ("Kidrobot", "Dunny", "Dunny 8-inch Andy Warhol Campbell's Soup", "Collab", "mid", 350),
        ("Kidrobot", "Dunny", "Dunny 3-inch The Wild Ones Full Case", "Blind Box Set", "standard", 85),
        ("Kidrobot", "Dunny", "Dunny 8-inch Arcane Divination Frank Kozik", "Limited", "mid", 400),
        ("Kidrobot", "Art Giant", "Basquiat Dunny 20-inch", "Collab", "high", 800),
        ("Kidrobot", "Simpsons", "Simpsons Treehouse of Horror Full Case", "Collab", "mid", 200),

        # ── Mighty Jaxx Expanded ───────────────────────────────────────────
        ("Mighty Jaxx", "XXRay", "XXRay Plus Sesame Street Big Bird", "Collab", "mid", 200),
        ("Mighty Jaxx", "Kandy", "Kandy x Transformers Optimus Prime 10-inch", "Collab", "mid", 300),
        ("Mighty Jaxx", "Kandy", "Kandy x Looney Tunes Bugs Bunny 10-inch", "Collab", "mid", 250),
        ("Mighty Jaxx", "XXRAY", "XXRAY GI Joe Snake Eyes 4-inch", "Collab", "mid", 160),

        # ── Ron English Expanded ───────────────────────────────────────────
        ("Ron English", "Made in China", "Made in China Grin 12-inch Red", "Limited", "high", 700),
        ("Ron English", "MC Supersized", "MC Supersized Gold Chrome", "Limited", "grail", 1500),
        ("Ron English", "Popaganda", "Popaganda Cereal Killer 8-inch Set", "Limited", "mid", 400),

        # ── Coarse Expanded ────────────────────────────────────────────────
        ("Coarse", "Omen", "Omen Bloom 10-inch", "Limited", "mid", 400),
        ("Coarse", "Noop Noop", "Noop Noop Glacier Pair", "Limited", "high", 550),
        ("Coarse", "Top", "Top Void Edition 14-inch", "Limited", "high", 800),

        # ── Futura Laboratories Expanded ──────────────────────────────────
        ("Futura Laboratories", "FL Pointman", "Pointman 20-inch OG Chrome", "Limited", "grail", 2000),
        ("Futura Laboratories", "FL Pointman", "Pointman 6-inch Silver Anniversary", "Limited", "high", 700),

        # ── Hebru Brantley Expanded ───────────────────────────────────────
        ("Hebru Brantley", "Flyboy", "Flyboy 6-inch OG Color", "Standard", "mid", 300),
        ("Hebru Brantley", "Lil Mama", "Lil Mama 6-inch OG Color", "Standard", "mid", 280),

        # ── Luke Chueh Expanded ───────────────────────────────────────────
        ("Luke Chueh", "Possessed", "Possessed Bear Glow-in-Dark", "Limited", "high", 600),
        ("Luke Chueh", "Brick Bear", "Brick Bear 8-inch Red", "Limited", "mid", 280),

        # ── BAPE Figures Expanded ─────────────────────────────────────────
        ("BAPE", "Baby Milo", "Baby Milo 10-inch Vinyl Gold Chrome", "Limited", "high", 500),
        ("BAPE", "Dragon Ball", "BAPE x Dragon Ball Z Vegeta Figure", "Collab", "high", 550),

        # ── Hot Toys Cosbaby Expanded ─────────────────────────────────────
        ("Hot Toys", "Cosbaby Marvel", "Cosbaby Deadpool Swords", "Standard", "standard", 40),
        ("Hot Toys", "Cosbaby Marvel", "Cosbaby Thanos Infinity Gauntlet", "Standard", "standard", 50),
        ("Hot Toys", "Cosbaby Star Wars", "Cosbaby Boba Fett", "Standard", "standard", 45),

        # ── Fools Paradise Expanded ───────────────────────────────────────
        ("Fools Paradise", "Wait and See", "Wait and See OG Edition", "Limited", "high", 650),
        ("Fools Paradise", "Django", "Django Unchained Homage", "Limited", "high", 700),

        # ── KAWS Full Catalog Expansion ──────────────────────────────────────
        ("KAWS", "Companion", "Companion Resting Place Brown 2013", "Limited", "high", 1300),
        ("KAWS", "Companion", "Companion Sitting Grey 2018", "Open Edition", "mid", 360),
        ("KAWS", "Companion", "Companion Sitting Black 2018", "Open Edition", "mid", 380),
        ("KAWS", "Companion", "Companion Flayed Open Edition Blush", "Open Edition", "mid", 350),
        ("KAWS", "Holiday", "Holiday Thailand (Khao Lak)", "Limited", "high", 850),
        ("KAWS", "Holiday", "Holiday Indonesia", "Limited", "high", 700),
        ("KAWS", "Holiday", "Holiday Korea", "Limited", "high", 750),
        ("KAWS", "Holiday", "Holiday Melbourne", "Limited", "high", 650),
        ("KAWS", "Companion", "Dissected Companion (Small) Grey", "Limited", "mid", 450),
        ("KAWS", "Chum", "Chum Pink 2003", "Limited", "grail", 1800),
        ("KAWS", "Companion", "Companion Originalfake Black 2006", "Limited", "grail", 2800),
        ("KAWS", "BFF", "BFF Open Edition Black", "Open Edition", "mid", 400),
        ("KAWS", "BFF", "BFF Plush Blue (36-inch)", "Limited", "high", 900),
        ("KAWS", "Together", "Together Brown 2018", "Open Edition", "mid", 460),
        ("KAWS", "Together", "Together Black 2018", "Open Edition", "mid", 480),
        ("KAWS", "Separated", "Separated Companion Grey", "Open Edition", "mid", 360),
        ("KAWS", "Small Lie", "Small Lie Brown", "Open Edition", "mid", 260),

        # ── Bearbrick 1000% Grails Additional ────────────────────────────────
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Supreme Red", "Collab", "grail", 6000),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Pepsi (Ice Blue)", "Collab", "grail", 3500),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Nike SB Dunk Low", "Collab", "grail", 4000),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Chrome Ironman", "Collab", "grail", 3200),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Marvel Spider-Man", "Collab", "high", 1400),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Star Wars Darth Vader Chrome", "Collab", "grail", 3000),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Chiaki Inaba (White)", "Collab", "high", 1300),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Katsushika Hokusai Wave", "Collab", "grail", 4500),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Jean-Michel Basquiat V5", "Collab", "high", 1500),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Keith Haring V5", "Collab", "high", 1100),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% CLOT x Herschel Silk Camo", "Collab", "grail", 3500),

        # ── Bearbrick 100%+400% Additional ──────────────────────────────────
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Anti Social Social Club", "Collab", "mid", 450),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Ape Shall Never Kill Ape", "Collab", "high", 650),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% BE@RBRICK ANNA SUI Black", "Collab", "mid", 400),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Readymade x Mickey Mouse", "Collab", "high", 600),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% UNDERCOVER x GILAPPLE", "Collab", "high", 700),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% NEIGHBORHOOD SKULL", "Collab", "high", 550),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Eric Haze Blk", "Collab", "mid", 380),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% BAIT x Transformers Nemesis Prime", "Collab", "high", 500),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Piet Mondrian", "Collab", "mid", 400),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% KARIMOKU Hermes", "Collab", "grail", 3000),

        # ── Pop Mart LABUBU Full Expansion ───────────────────────────────────
        ("Pop Mart", "LABUBU", "LABUBU The Monsters City of Wishes", "Blind Box Set", "standard", 70),
        ("Pop Mart", "LABUBU", "LABUBU The Monsters Winter Sports", "Blind Box Set", "standard", 65),
        ("Pop Mart", "LABUBU", "LABUBU The Monsters Summer Breeze", "Blind Box Set", "standard", 60),
        ("Pop Mart", "LABUBU", "LABUBU Treasure Island Series", "Blind Box Set", "standard", 75),
        ("Pop Mart", "LABUBU", "LABUBU x Lisa Bangkok Exclusive", "Collab", "high", 650),
        ("Pop Mart", "LABUBU", "LABUBU Sitting 1000% Figure", "Mega", "grail", 1800),

        # ── Pop Mart Molly Full Expansion ────────────────────────────────────
        ("Pop Mart", "Molly", "Molly x Warner Bros 100th Anniversary", "Collab", "mid", 120),
        ("Pop Mart", "Molly", "Molly Wedding Flower Girl", "Blind Box Set", "standard", 65),
        ("Pop Mart", "Molly", "Molly My Childhood Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "Molly", "Molly Steampunk Series", "Blind Box Set", "standard", 70),
        ("Pop Mart", "Molly", "Molly x Haikyuu Collab Series", "Collab", "mid", 150),

        # ── Pop Mart Dimoo Full Expansion ────────────────────────────────────
        ("Pop Mart", "Dimoo", "Dimoo Aquarium Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "Dimoo", "Dimoo Animal Kingdom Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "Dimoo", "Dimoo Midnight Circus Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "Dimoo", "Dimoo Forest Night Series", "Blind Box Set", "standard", 55),

        # ── Pop Mart Skullpanda Full Expansion ───────────────────────────────
        ("Pop Mart", "Skullpanda", "Skullpanda Everyday Wonderland Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "Skullpanda", "Skullpanda Ancient Castle Series", "Blind Box Set", "standard", 70),
        ("Pop Mart", "Skullpanda", "Skullpanda Warmth Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "Skullpanda", "Skullpanda Ink Language Series", "Blind Box Set", "standard", 65),

        # ── Pop Mart Hirono Full Expansion ───────────────────────────────────
        ("Pop Mart", "Hirono", "Hirono Reshape Series", "Blind Box Set", "standard", 80),
        ("Pop Mart", "Hirono", "Hirono Little Troublemaker Series", "Blind Box Set", "standard", 75),
        ("Pop Mart", "Hirono", "Hirono x Sanrio Hello Kitty Series", "Collab", "mid", 120),

        # ── Pop Mart PUCKY Full Expansion ────────────────────────────────────
        ("Pop Mart", "PUCKY", "PUCKY Space Babies Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "PUCKY", "PUCKY Milk Babies Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "PUCKY", "PUCKY What Are the Fairies Doing Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "PUCKY", "PUCKY Elf Planet Series", "Blind Box Set", "standard", 65),

        # ── Pop Mart CRYBABY Full Expansion ──────────────────────────────────
        ("Pop Mart", "Crybaby", "Crybaby x Powerpuff Girls Series", "Collab", "mid", 100),
        ("Pop Mart", "Crybaby", "Crybaby Sad Club Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "Crybaby", "Crybaby Cheer Up Baby Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "Crybaby", "Crybaby My Melody Baby Series", "Collab", "mid", 110),

        # ── Pop Mart Sweet Bean Full Line ────────────────────────────────────
        ("Pop Mart", "Sweet Bean", "Sweet Bean Supermarket Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "Sweet Bean", "Sweet Bean Frozen Time Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "Sweet Bean", "Sweet Bean Akihabara Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "Sweet Bean", "Sweet Bean x Harry Potter Series", "Collab", "mid", 100),

        # ── Pop Mart Zsiga Full Line ─────────────────────────────────────────
        ("Pop Mart", "Zsiga", "Zsiga I'm Not Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "Zsiga", "Zsiga We Are So Cute Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "Zsiga", "Zsiga Taxi Series", "Blind Box Set", "standard", 70),

        # ── Pop Mart Mega Collection Full Expansion ──────────────────────────
        ("Pop Mart", "Mega Collection", "Mega Collection 1000% Space Molly Mickey Mouse", "Mega", "grail", 2000),
        ("Pop Mart", "Mega Collection", "Mega Collection 1000% Space Molly Stitch", "Mega", "high", 1400),
        ("Pop Mart", "Mega Collection", "Mega Collection 1000% Space Molly Buzz Lightyear", "Mega", "high", 1200),
        ("Pop Mart", "Mega Collection", "Mega Collection 400% Space Molly Pikachu", "Mega", "high", 800),
        ("Pop Mart", "Mega Collection", "Mega Collection 400% Space Molly Woody", "Mega", "high", 600),

        # ── Superplastic Full Expansion ──────────────────────────────────────
        ("Superplastic", "Janky", "Janky Series 2 Full Case", "Blind Box Set", "standard", 90),
        ("Superplastic", "Janky", "Janky Series 5 Full Case", "Blind Box Set", "standard", 100),
        ("Superplastic", "Janky", "Janky x J Balvin OG 8-inch", "Collab", "high", 500),
        ("Superplastic", "Janky", "Janky x ComplexCon Exclusive 2022", "Collab", "mid", 350),
        ("Superplastic", "Guggimon", "Guggimon Superjanky 8-inch Red Chrome", "Limited", "mid", 300),
        ("Superplastic", "Guggimon", "Guggimon Superjanky 8-inch Galaxy", "Limited", "mid", 280),
        ("Superplastic", "Kranky", "Kranky OG Superjanky 8-inch", "Limited", "mid", 200),
        ("Superplastic", "Superdoodle", "Superdoodle Holiday 8-inch", "Limited", "mid", 160),
        ("Superplastic", "Superplastic", "Janky x Cardi B Edition 8-inch", "Collab", "high", 450),

        # ── Coarse Full Expansion ────────────────────────────────────────────
        ("Coarse", "Omen", "Omen Glow 10-inch", "Limited", "mid", 420),
        ("Coarse", "Omen", "Omen Vivid 10-inch", "Limited", "mid", 380),
        ("Coarse", "Pain", "Pain Serenity 14-inch", "Limited", "high", 700),
        ("Coarse", "Top", "Top Ascend 14-inch", "Limited", "high", 750),
        ("Coarse", "Noop Noop", "Noop Noop Dawn Pair", "Limited", "high", 550),
        ("Coarse", "Omen", "Omen Original (Kickstarter Edition)", "Limited", "high", 800),

        # ── Fools Paradise Full Expansion ────────────────────────────────────
        ("Fools Paradise", "Astro Boy", "Astro Boy Homage Glow-in-Dark", "Limited", "grail", 1500),
        ("Fools Paradise", "Pinocchio", "Pinocchio Street Kid Stealth", "Limited", "high", 750),
        ("Fools Paradise", "Joker", "Joker Homage OG Purple", "Limited", "high", 800),
        ("Fools Paradise", "Rocky", "Rocky Balboa Homage", "Limited", "high", 700),
        ("Fools Paradise", "Narcos", "Narcos Pablo Homage OG", "Limited", "high", 680),
        ("Fools Paradise", "Mad Dog", "Michael Mad Dog Gold Chrome", "Limited", "grail", 1600),

        # ── ComplexCon Exclusives ────────────────────────────────────────────
        ("ComplexCon", "Exclusive", "ComplexCon x KAWS Chum (2019 Exclusive)", "Collab", "grail", 2500),
        ("ComplexCon", "Exclusive", "ComplexCon x Verdy Girls Dont Cry Figure", "Collab", "high", 800),
        ("ComplexCon", "Exclusive", "ComplexCon x Bearbrick 100%+400% Set", "Collab", "high", 600),
        ("ComplexCon", "Exclusive", "ComplexCon x Takashi Murakami Flower Plush 60cm", "Collab", "high", 900),

        # ── Kidrobot Dunny Archive ───────────────────────────────────────────
        ("Kidrobot", "Dunny", "Dunny 3-inch Series 2009 Full Case", "Blind Box Set", "standard", 85),
        ("Kidrobot", "Dunny", "Dunny 3-inch Series 2010 Full Case", "Blind Box Set", "standard", 90),
        ("Kidrobot", "Dunny", "Dunny 3-inch Series 2013 Full Case", "Blind Box Set", "standard", 80),
        ("Kidrobot", "Dunny", "Dunny 8-inch Gary Baseman Night Riders", "Limited", "mid", 350),
        ("Kidrobot", "Dunny", "Dunny 8-inch Andrew Bell O-No Sushi", "Limited", "mid", 300),
        ("Kidrobot", "Dunny", "Dunny 8-inch Mishka Keep Watch", "Collab", "mid", 400),
        ("Kidrobot", "Dunny", "Dunny 8-inch Kozik Smorkin Labbit", "Limited", "mid", 280),
        ("Kidrobot", "Dunny", "Dunny 20-inch MC Supersized by Ron English", "Collab", "high", 1200),
        ("Kidrobot", "Dunny", "Dunny 3-inch Jean-Michel Basquiat Set", "Collab", "mid", 120),
        ("Kidrobot", "Dunny", "Dunny 8-inch Cognition Enhancer", "Limited", "mid", 350),

        # ── Kidrobot Other Lines ─────────────────────────────────────────────
        ("Kidrobot", "Labbit", "Happy Labbit 7-inch Smoke Free", "Standard", "standard", 35),
        ("Kidrobot", "Labbit", "Labbit x Kozik 10-inch Pink", "Limited", "mid", 200),
        ("Kidrobot", "Munny", "Munny World 4-inch DIY 4-Pack", "Standard", "standard", 40),
        ("Kidrobot", "South Park", "South Park Fractured But Whole 3-inch Series", "Collab", "standard", 70),
        ("Kidrobot", "Bob's Burgers", "Bob's Burgers Blind Box Full Case", "Collab", "standard", 65),
        ("Kidrobot", "Simpsons", "Simpsons Kidrobot x Futurama Full Case", "Collab", "mid", 150),
        ("Kidrobot", "TMNT", "TMNT Ooze Action Glow Set", "Collab", "mid", 180),

        # ── How2Work ─────────────────────────────────────────────────────────
        ("How2Work", "Snoopy", "Snoopy Astronaut (Large)", "Limited", "high", 900),
        ("How2Work", "Snoopy", "Snoopy Astronaut (Small)", "Limited", "mid", 350),
        ("How2Work", "Labubu", "How2Work x Kasing Lung Cloud Prototype", "Collab", "high", 1200),
        ("How2Work", "Zimomo", "Zimomo OG Edition 6-inch", "Limited", "mid", 250),

        # ── T9G / INSTINCTOY / Japanese Artists ──────────────────────────────
        ("T9G", "Rangeas", "Rangeas Milky Way Edition", "Limited", "high", 600),
        ("T9G", "Rangeas", "Rangeas Blood Red Edition", "Limited", "high", 550),
        ("T9G", "Rangeas", "Rangeas Clear Rainbow Edition", "Limited", "high", 700),
        ("Instinctoy", "Mini Erosion", "Mini Erosion Stitch Collab", "Collab", "mid", 180),
        ("Instinctoy", "Liquid", "Liquid Bear by Instinctoy Clear", "Limited", "mid", 250),
        ("Instinctoy", "Vincent", "Vincent by Instinctoy OG Green", "Limited", "mid", 200),

        # ── Sticky Monster Lab Full Expansion ────────────────────────────────
        ("Sticky Monster Lab", "Kibon", "Kibon Christmas Edition", "Limited", "mid", 200),
        ("Sticky Monster Lab", "Kibon", "Kibon Surf Edition", "Limited", "mid", 180),
        ("Sticky Monster Lab", "Bo", "Bo Sleeping 4-inch", "Standard", "standard", 55),
        ("Sticky Monster Lab", "Bo", "Bo Christmas 4-inch", "Limited", "standard", 80),
        ("Sticky Monster Lab", "SML", "SML Monster Family Set (5 pcs)", "Limited", "mid", 300),
        ("Sticky Monster Lab", "SML", "SML Rice Bowl 8-inch", "Limited", "mid", 220),

        # ── Clutter Gallery Exclusives ───────────────────────────────────────
        ("Clutter", "Gallery", "Clutter Gallery x Quiccs TEQ63 1-off Custom", "Limited", "grail", 2000),
        ("Clutter", "Gallery", "Clutter Gallery x MAD Bent World Dunny", "Limited", "high", 600),
        ("Clutter", "Gallery", "Clutter Gallery x JPK Custom Android 8-inch", "Limited", "high", 800),
        ("Clutter", "Magazine", "Clutter Magazine x DCON Exclusive Dunny Set", "Limited", "mid", 250),

        # ── Devil Toys / Quiccs ──────────────────────────────────────────────
        ("Devil Toys", "TEQ63", "TEQ63 Chrome Silver 6-inch by Quiccs", "Limited", "mid", 300),
        ("Devil Toys", "TEQ63", "TEQ63 Gold 6-inch by Quiccs", "Limited", "high", 500),
        ("Devil Toys", "TEQ63", "TEQ63 Fortress Black 10-inch by Quiccs", "Limited", "high", 700),
        ("Devil Toys", "TEQ63", "TEQ63 x BAIT Edition 6-inch", "Collab", "mid", 350),
        ("Devil Toys", "TEQ63", "TEQ63 Red 6-inch by Quiccs", "Limited", "mid", 200),

        # ── J Balvin Collaborations ──────────────────────────────────────────
        ("J Balvin", "Superplastic", "J Balvin Janky OG Multicolor", "Collab", "high", 500),
        ("J Balvin", "Collab", "J Balvin x McDonald's Figure Set", "Collab", "mid", 180),
        ("J Balvin", "Collab", "J Balvin x Takashi Murakami Print Figure", "Collab", "high", 800),

        # ── Mighty Jaxx Full Expansion ───────────────────────────────────────
        ("Mighty Jaxx", "XXRay", "XXRay Plus Rainbow Dissected Bear", "Limited", "mid", 250),
        ("Mighty Jaxx", "XXRay", "XXRay Plus Mickey Mouse 10-inch", "Collab", "mid", 300),
        ("Mighty Jaxx", "XXRay", "XXRay Deadpool 10-inch", "Collab", "mid", 250),
        ("Mighty Jaxx", "Kandy", "Kandy x Spongebob Squarepants 10-inch", "Collab", "mid", 220),
        ("Mighty Jaxx", "Kandy", "Kandy x DC Justice League Set", "Collab", "mid", 350),
        ("Mighty Jaxx", "Mightyverse", "Mightyverse One Piece Luffy Hidden Dissectible", "Collab", "standard", 70),

        # ── Ron English Full Expansion ───────────────────────────────────────
        ("Ron English", "MC Supersized", "MC Supersized Blue Camo", "Limited", "mid", 450),
        ("Ron English", "Popaganda", "Popaganda Grin 12-inch Neon Green", "Limited", "high", 650),
        ("Ron English", "Temper Tot", "Temper Tot Glow-in-Dark Green", "Limited", "mid", 300),
        ("Ron English", "FAT Tony", "FAT Tony Original 12-inch", "Limited", "mid", 400),
        ("Ron English", "Astronaut", "Astronaut Grin OG White", "Limited", "mid", 350),

        # ── Unruly Industries Full Expansion ─────────────────────────────────
        ("Unruly Industries", "Marvel", "Miles Morales Spider-Man Designer Statue", "Limited", "high", 580),
        ("Unruly Industries", "Marvel", "Deadpool Designer Statue", "Limited", "high", 550),
        ("Unruly Industries", "DC", "Harley Quinn Designer Statue", "Limited", "high", 560),
        ("Unruly Industries", "DC", "Superman Designer Statue", "Limited", "high", 540),

        # ── BAPE Figures Full Expansion ──────────────────────────────────────
        ("BAPE", "Baby Milo", "Baby Milo 10-inch Vinyl Blue", "Standard", "mid", 200),
        ("BAPE", "Baby Milo", "Baby Milo 10-inch Vinyl Pink Camo", "Limited", "mid", 380),
        ("BAPE", "Dragon Ball", "BAPE x Dragon Ball Z Frieza Figure", "Collab", "high", 520),
        ("BAPE", "Star Wars", "BAPE x Star Wars Boba Fett 12-inch", "Collab", "high", 680),

        # ── Luke Chueh Full Expansion ────────────────────────────────────────
        ("Luke Chueh", "Bear In Mind", "Bear In Mind Dissected 8-inch", "Limited", "high", 550),
        ("Luke Chueh", "Possessed", "Possessed Bear Pink Fade", "Limited", "mid", 380),
        ("Luke Chueh", "Headspace", "Headspace Bear OG 10-inch", "Limited", "high", 600),

        # ── Hebru Brantley Full Expansion ────────────────────────────────────
        ("Hebru Brantley", "Flyboy", "Flyboy 6-inch Chrome", "Limited", "high", 500),
        ("Hebru Brantley", "Rocket", "Rocket 12-inch OG Edition", "Limited", "high", 800),
        ("Hebru Brantley", "Lil Mama", "Lil Mama 18-inch OG Edition", "Limited", "grail", 1500),

        # ── Secret Base Full Expansion ───────────────────────────────────────
        ("Secret Base", "Skull Bee", "Skull Bee Clear Neon Edition", "Limited", "high", 750),
        ("Secret Base", "Skull Bee", "Skull Bee Purple Metallic", "Limited", "high", 800),
        ("Secret Base", "Honey Bear", "Honey Bear OG Amber Edition", "Limited", "high", 600),
        ("Secret Base", "Ghost Bear", "Ghost Bear Pink Translucent", "Limited", "high", 550),

        # ── Hot Toys Cosbaby Full Expansion ──────────────────────────────────
        ("Hot Toys", "Cosbaby Marvel", "Cosbaby Doctor Strange Multiverse", "Standard", "standard", 45),
        ("Hot Toys", "Cosbaby Marvel", "Cosbaby Black Panther", "Standard", "standard", 42),
        ("Hot Toys", "Cosbaby Star Wars", "Cosbaby Luke Skywalker", "Standard", "standard", 38),
        ("Hot Toys", "Cosbaby DC", "Cosbaby Wonder Woman", "Standard", "standard", 42),
        ("Hot Toys", "Cosbaby DC", "Cosbaby Aquaman", "Standard", "standard", 40),
        ("Hot Toys", "Cosbaby Disney", "Cosbaby Stitch Ohana", "Standard", "standard", 35),
        ("Hot Toys", "Cosbaby Disney", "Cosbaby Buzz Lightyear", "Standard", "standard", 35),

        # ── VCD by Medicom Full Expansion ────────────────────────────────────
        ("Medicom", "VCD", "VCD Peanuts Lucy", "Standard", "mid", 200),
        ("Medicom", "VCD", "VCD Peanuts Charlie Brown", "Standard", "mid", 220),
        ("Medicom", "VCD", "VCD Astro Boy Vintage", "Limited", "high", 700),
        ("Medicom", "VCD", "VCD Godzilla 1954", "Limited", "high", 800),
        ("Medicom", "VCD", "VCD Mickey Mouse Runaway Brain", "Limited", "mid", 400),

        # ── Daniel Arsham Full Expansion ─────────────────────────────────────
        ("Daniel Arsham", "Eroded", "Eroded Rubik's Cube (Pink)", "Limited", "high", 900),
        ("Daniel Arsham", "Eroded", "Eroded Gameboy (Blue)", "Limited", "high", 1000),
        ("Daniel Arsham", "Crystal Relic", "Crystal Relic 003 Cassette Tape", "Limited", "high", 1200),
        ("Daniel Arsham", "Snarkitecture", "Snarkitecture Broken Mirror Figure", "Limited", "high", 800),

        # ── James Jean Full Expansion ────────────────────────────────────────
        ("James Jean", "Laputa", "Laputa Blue/Purple 12-inch", "Limited", "grail", 1600),
        ("James Jean", "Iri", "Iri Figure 10-inch", "Limited", "high", 700),
        ("James Jean", "Descendant", "Descendant Storm Rider Bronze", "Limited", "grail", 2000),

        # ── Futura Laboratories Full Expansion ───────────────────────────────
        ("Futura Laboratories", "FL Pointman", "Pointman 12-inch Neon Green", "Limited", "high", 850),
        ("Futura Laboratories", "FL Pointman", "Pointman 6-inch ComplexCon Edition", "Collab", "high", 700),
        ("Futura Laboratories", "FL", "Futura x Medicom Bearbrick 100%+400%", "Collab", "high", 800),

        # ── CPFM / Cactus Plant Flea Market ─────────────────────────────────
        ("CPFM", "Flea Market Smiley", "Smiley Face 12-inch OG Yellow", "Collab", "high", 700),
        ("CPFM", "Flea Market Smiley", "Smiley Face 6-inch Set (3-pack)", "Collab", "mid", 350),

        # ── Takashi Murakami Full Expansion ──────────────────────────────────
        ("Takashi Murakami", "Kaikai Kiki", "Kaikai Kiki Set (2 pcs)", "Limited", "high", 600),
        ("Takashi Murakami", "ComplexCon", "Murakami x OVO Flower (Drake Collab)", "ComplexCon Exclusive", "grail", 2500),
        ("Takashi Murakami", "Flower", "Flower Plush Cushion Rainbow 30cm", "Standard", "standard", 95),
        ("Takashi Murakami", "Flower", "Flower Plush Cushion Black 60cm", "Standard", "mid", 200),
        ("Takashi Murakami", "Mr. DOB", "Mr. DOB Figure Pink/Blue 25cm", "Limited", "high", 950),
    ]

    catalog = []
    for brand, line, name, edition, tier, price in toys:
        catalog.append({
            "brand": brand,
            "line": line,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })

    catalog.extend(_batch_art_toys_2025())
    return catalog


def _batch_art_toys_2025() -> list[dict]:
    """Batch 8 — Superplastic expanded, Coarse Toys, ThreeA/3A Ashley Wood,
    Mighty Jaxx XXRAY, James Jean, Futura, Ron English, Clutter exclusives. ~50 items."""

    items = [
        # Superplastic — Janky extended
        ("Superplastic", "Janky", "Janky Series 3 Full Case (12 Blind Boxes)", "Blind Box Set", "standard", 95),
        ("Superplastic", "Janky", "Janky Series 4 Full Case (12 Blind Boxes)", "Blind Box Set", "standard", 95),
        ("Superplastic", "Janky", "Janky x Gorillaz 2D Superjanky 8-inch", "Collab", "high", 450),
        ("Superplastic", "Janky", "Janky x Post Malone Posty Superjanky", "Collab", "high", 500),

        # Superplastic — Guggimon & Dayzee
        ("Superplastic", "Guggimon", "Guggimon Blood Superjanky 8-inch", "Limited", "mid", 280),
        ("Superplastic", "Guggimon", "Guggimon Poison 8-inch (ComplexCon 2023)", "Collab", "high", 400),
        ("Superplastic", "Dayzee", "Dayzee OG 8-inch Vinyl", "Limited", "mid", 220),
        ("Superplastic", "Dayzee", "Dayzee Valentine Pink 8-inch", "Limited", "mid", 250),
        ("Superplastic", "Dayzee", "Dayzee Midnight Black 8-inch", "Limited", "mid", 240),

        # Coarse Toys — Omen extended
        ("Coarse", "Omen", "Omen Fade to Black 10-inch", "Limited", "high", 500),
        ("Coarse", "Omen", "Omen Eclipse 10-inch (Gallery Edition)", "Limited", "grail", 900),

        # Coarse Toys — False Friends
        ("Coarse", "False Friends", "False Friends Dusk & Dawn Pair", "Limited", "high", 650),
        ("Coarse", "False Friends", "False Friends Blood & Ivory Pair", "Limited", "high", 700),

        # Coarse Toys — Noop extended
        ("Coarse", "Noop Noop", "Noop Noop Ember Pair", "Limited", "high", 580),
        ("Coarse", "Noop Noop", "Noop Noop Glacier Pair (Art Basel Edition)", "Limited", "grail", 850),

        # ThreeA / 3A — Ashley Wood Originals
        ("ThreeA", "Ashley Wood", "WWR Bertie Mk 3 Jungle Grunt 1/6", "Limited", "high", 600),
        ("ThreeA", "Ashley Wood", "WWR Square Mk 2 Desert Assault 1/6", "Limited", "high", 550),
        ("ThreeA", "Ashley Wood", "Adventure Kartel Tommy Mission 1/6", "Limited", "high", 700),
        ("ThreeA", "Ashley Wood", "Popbot TK Slicer 1/6", "Limited", "grail", 900),
        ("ThreeA", "Ashley Wood", "WWR Large Martin Rothchild 12-inch", "Limited", "high", 800),

        # Mighty Jaxx — XXRAY Series
        ("Mighty Jaxx", "XXRAY", "XXRAY Plus Batman (DC) 10-inch", "Limited", "mid", 200),
        ("Mighty Jaxx", "XXRAY", "XXRAY Elmo (Sesame Street) 4-inch", "Standard", "standard", 55),
        ("Mighty Jaxx", "XXRAY", "XXRAY SpongeBob SquarePants 4-inch", "Standard", "standard", 55),
        ("Mighty Jaxx", "XXRAY", "XXRAY Mickey Mouse (Disney) 4-inch", "Standard", "standard", 60),
        ("Mighty Jaxx", "XXRAY", "XXRAY Deadpool (Marvel) 4-inch", "Standard", "standard", 55),

        # Mighty Jaxx — Dissected & Kandy
        ("Mighty Jaxx", "Dissected", "Dissected Astro Boy BAIT Exclusive", "Collab", "high", 450),
        ("Mighty Jaxx", "Dissected", "Dissected Care Bear 8-inch", "Limited", "mid", 180),
        ("Mighty Jaxx", "Kandy", "Kandy x Spongebob Full Case (12 Blind Boxes)", "Blind Box Set", "standard", 85),
        ("Mighty Jaxx", "Mightyverse", "Mightyverse Freeny's Hidden Dissectibles Dragon Ball Z Case", "Blind Box Set", "standard", 70),

        # James Jean — Art Figures
        ("James Jean", "Dogwood", "Dogwood OG Edition 14-inch", "Limited", "grail", 1800),
        ("James Jean", "Dogwood", "Dogwood Night Bloom Edition 14-inch", "Limited", "grail", 2200),
        ("James Jean", "Descendant", "Descendant Fire Walker Bronze", "Limited", "grail", 2400),
        ("James Jean", "Descendant", "Descendant Cloud Wanderer 12-inch", "Limited", "grail", 1900),

        # Futura Laboratories — FL-001 & Pointman extended
        ("Futura Laboratories", "FL-001", "FL-001 All Over Print Figure 12-inch", "Limited", "high", 750),
        ("Futura Laboratories", "FL-001", "FL-001 Infrared Edition 6-inch", "Limited", "mid", 400),
        ("Futura Laboratories", "FL Pointman", "Pointman Chrome Edition 12-inch", "Limited", "grail", 1200),

        # Ron English — MC Supersized & Grin
        ("Ron English", "MC Supersized", "MC Supersized OG Red 10-inch", "Limited", "high", 600),
        ("Ron English", "MC Supersized", "MC Supersized Army Green 10-inch", "Limited", "high", 550),
        ("Ron English", "MC Supersized", "MC Supersized Rainbow 10-inch (ComplexCon)", "Collab", "grail", 1000),
        ("Ron English", "Grin", "Grin OG White 8-inch", "Limited", "mid", 350),
        ("Ron English", "Grin", "Grin Gold Chrome 8-inch", "Limited", "high", 500),
        ("Ron English", "Temper Tot", "Temper Tot Red Star 8-inch", "Limited", "mid", 300),
        ("Ron English", "Popaganda", "Popaganda Cereal Killers Full Set (6 pcs)", "Limited", "high", 800),

        # Clutter Magazine / Gallery Exclusives
        ("Clutter", "Gallery", "Clutter Gallery x Czee13 Custom Canbot 8-inch", "Limited", "high", 500),
        ("Clutter", "Gallery", "Clutter Gallery x OG Slick LA Hands 12-inch", "Limited", "high", 700),
        ("Clutter", "Magazine", "Clutter Magazine x DesignerCon Exclusive Dunny 3-pack", "Limited", "mid", 180),
        ("Clutter", "Gallery", "Clutter Gallery x RunDMB Custom Munny 8-inch", "Limited", "high", 600),
        ("Clutter", "Magazine", "Clutter Magazine x DCON Exclusive Canbot Set (4 pcs)", "Limited", "mid", 250),

        # ── KAWS - Additional Editions ─────────────────────────────────────
        ("KAWS", "Companion", "Companion Resting Place Brown 2013", "Limited", "grail", 3200),
        ("KAWS", "Companion", "Companion Five Years Later Black", "Limited", "grail", 2400),
        ("KAWS", "Together", "Together Grey Open Edition 2018", "Open Edition", "mid", 280),
        ("KAWS", "Together", "Together Brown Open Edition 2018", "Open Edition", "mid", 300),
        ("KAWS", "Share", "Share Black Open Edition 2020", "Open Edition", "mid", 350),
        ("KAWS", "Share", "Share Brown Open Edition 2020", "Open Edition", "mid", 370),
        ("KAWS", "Separated", "Separated Grey Open Edition 2021", "Open Edition", "mid", 300),
        ("KAWS", "Separated", "Separated Brown Open Edition 2021", "Open Edition", "mid", 320),
        ("KAWS", "Holiday", "KAWS Holiday Japan Mt. Fuji (Brown)", "Limited", "high", 900),
        ("KAWS", "Holiday", "KAWS Holiday Singapore (Grey)", "Limited", "high", 850),

        # ── Ron English - Expansion ────────────────────────────────────────
        ("Ron English", "MC Supersized", "MC Supersized Glow-in-the-Dark 10-inch", "Limited", "high", 650),
        ("Ron English", "MC Supersized", "MC Supersized Pink Camo 10-inch", "Limited", "high", 580),
        ("Ron English", "Astronaut Grin", "Astronaut Grin White 12-inch", "Limited", "high", 700),
        ("Ron English", "Astronaut Grin", "Astronaut Grin Black 12-inch", "Limited", "high", 720),
        ("Ron English", "FAT Tony", "FAT Tony OG Flesh 8-inch", "Limited", "mid", 400),
        ("Ron English", "FAT Tony", "FAT Tony Bronze 8-inch", "Limited", "high", 550),
        ("Ron English", "Temper Tot", "Temper Tot Blue Star 8-inch", "Limited", "mid", 320),
        ("Ron English", "Grin", "Grin Infrared 8-inch (ComplexCon)", "Collab", "high", 600),

        # ── Coarse Toys - Expansion ────────────────────────────────────────
        ("Coarse", "Noop", "Noop Ivory 5-inch", "Limited", "mid", 280),
        ("Coarse", "Noop", "Noop Midnight 5-inch", "Limited", "mid", 300),
        ("Coarse", "Noop", "Noop Dust 5-inch (DCON Exclusive)", "Collab", "high", 450),
        ("Coarse", "Pain", "Pain Daily OG Red 10-inch", "Limited", "high", 600),
        ("Coarse", "Pain", "Pain Daily Grey 10-inch", "Limited", "high", 580),
        ("Coarse", "Top", "Top Ivory Edition 6-inch", "Limited", "mid", 350),
        ("Coarse", "False Friends", "False Friends Set (2 pcs) OG", "Limited", "high", 800),

        # ── Superplastic / Janky - Expansion ──────────────────────────────
        ("Superplastic", "Janky", "Janky Series 5 Full Case (12 Blind Boxes)", "Blind Box Set", "standard", 95),
        ("Superplastic", "Janky", "Janky x Tyler The Creator Superjanky", "Collab", "high", 550),
        ("Superplastic", "Guggimon", "Guggimon Neon Green 8-inch (Art Basel)", "Collab", "high", 480),
        ("Superplastic", "Kranky", "Kranky OG Blue 8-inch", "Limited", "mid", 250),
        ("Superplastic", "Kranky", "Kranky Lava 8-inch", "Limited", "mid", 280),
        ("Superplastic", "Superdoodle", "Superdoodle OG White 6-inch", "Limited", "mid", 200),
        ("Superplastic", "Dayzee", "Dayzee Gold Chrome 8-inch (DCON)", "Collab", "high", 500),

        # ── Mighty Jaxx - Expansion ────────────────────────────────────────
        ("Mighty Jaxx", "XXRAY", "XXRAY Plus Batman GID 10-inch", "Limited", "high", 550),
        ("Mighty Jaxx", "XXRAY", "XXRAY Plus SpongeBob Rainbow 4-inch", "Limited", "mid", 200),
        ("Mighty Jaxx", "Kandy", "Kandy x Spongebob Freeny's Hidden Dissectibles Series 2 (Set)", "Limited", "mid", 180),
        ("Mighty Jaxx", "Mightyverse", "Mightyverse All Gone Set (4 pcs)", "Limited", "mid", 250),
        ("Mighty Jaxx", "XXRAY", "XXRAY Wonder Woman 4-inch", "Limited", "mid", 160),
        ("Mighty Jaxx", "XXRAY", "XXRAY Pikachu 4-inch", "Collab", "high", 500),

        # ── Toyqube - Expansion ────────────────────────────────────────────
        ("Toyqube", "Astroboy", "Astroboy Greeting OG 10-inch", "Limited", "high", 600),
        ("Toyqube", "Astroboy", "Astroboy Greeting Chrome Silver 10-inch", "Limited", "high", 750),
        ("Toyqube", "Astroboy", "Astroboy Greeting Matte Black 10-inch", "Limited", "high", 650),
        ("Toyqube", "Pinocchio", "Pinocchio Wooden Style 10-inch", "Limited", "mid", 400),
        ("Toyqube", "Pinocchio", "Pinocchio Chrome Gold 10-inch", "Limited", "high", 700),
        ("Toyqube", "Astroboy", "Astroboy Greeting GID 6-inch", "Limited", "mid", 350),

        # ── A Bathing Ape / BAPE Figures - Expansion ──────────────────────
        ("BAPE", "Baby Milo", "Baby Milo OG Brown 8-inch Vinyl", "Limited", "mid", 350),
        ("BAPE", "Baby Milo", "Baby Milo Camo Green 8-inch Vinyl", "Limited", "mid", 380),
        ("BAPE", "Baby Milo", "Baby Milo x Star Wars Stormtrooper 6-inch", "Collab", "high", 600),
        ("BAPE", "Baby Milo", "Baby Milo x Dragon Ball Z Goku 6-inch", "Collab", "high", 650),
        ("BAPE", "ABC Camo", "BAPE x Bearbrick 100%+400% ABC Camo Green", "Collab", "high", 900),
        ("BAPE", "ABC Camo", "BAPE x Bearbrick 100%+400% ABC Camo Pink", "Collab", "high", 950),

        # ── KAWS — Holiday & Additional (Round 5) ─────────────────────────
        ("KAWS", "Holiday", "Holiday UK (Countryside)", "Limited", "high", 850),
        ("KAWS", "Holiday", "Holiday Hong Kong Float", "Limited", "high", 750),
        ("KAWS", "Holiday", "Holiday Taipei Seated", "Limited", "high", 700),
        ("KAWS", "Holiday", "Holiday Space Chrome Silver", "Limited", "grail", 1800),
        ("KAWS", "Holiday", "Holiday Space Glow in the Dark", "Limited", "grail", 2000),
        ("KAWS", "Small Lie", "Small Lie Brown", "Open Edition", "mid", 260),
        ("KAWS", "Gone", "Gone Companion Brown", "Open Edition", "mid", 430),
        ("KAWS", "FAMILY", "Family Brown", "Open Edition", "mid", 480),
        ("KAWS", "FAMILY", "Family Black", "Open Edition", "mid", 500),
        ("KAWS", "Separated", "Separated Companion Black", "Open Edition", "mid", 380),
        ("KAWS", "Along the Way", "Along the Way Grey", "Open Edition", "mid", 450),
        ("KAWS", "Along the Way", "Along the Way Black", "Open Edition", "mid", 470),
        ("KAWS", "Take", "Take Companion Grey", "Open Edition", "mid", 400),
        ("KAWS", "Passing Through", "Passing Through Black", "Open Edition", "mid", 420),

        # ── BE@RBRICK 400% Collaborations (Round 5) ───────────────────────
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Keith Haring V6", "Collab", "mid", 380),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Andy Warhol Brillo Box", "Collab", "mid", 400),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% KITH 10th Anniversary", "Collab", "high", 600),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Dior Oblique", "Collab", "grail", 1800),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Chrome Hearts Silver Cross", "Collab", "grail", 2200),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Kanye West Graduation Bear", "Collab", "high", 800),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Supreme Box Logo Red", "Collab", "high", 700),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Mastermind Japan Black", "Collab", "high", 650),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% CLOT x Nike Royale", "Collab", "high", 550),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Hajime Sorayama Space Girl", "Collab", "high", 750),

        # ── BE@RBRICK 1000% Grails (Round 5) ──────────────────────────────
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Supreme Red Box Logo", "Collab", "grail", 4500),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Daft Punk RAM Chrome", "Collab", "grail", 5500),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Pushead Metallic", "Collab", "grail", 3800),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Kaws Dissected Brown", "Collab", "grail", 6500),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Atmos Elephant Print", "Collab", "grail", 3200),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% BAIT Iron Man", "Collab", "grail", 3500),

        # ── Superplastic — Janky & Guggimon (Round 5) ─────────────────────
        ("Superplastic", "Janky", "Janky x JBalvin Neon Orange 8-inch", "Collab", "high", 550),
        ("Superplastic", "Janky", "Janky Series 5 Sealed Case (24pc)", "Blind Box Set", "standard", 95),
        ("Superplastic", "Guggimon", "Guggimon Jaws 8-inch (SDCC Exclusive)", "Collab", "high", 600),
        ("Superplastic", "Guggimon", "Guggimon Chrome Silver 12-inch", "Limited", "high", 800),
        ("Superplastic", "Kranky", "Kranky Holiday Sweater 8-inch", "Limited", "mid", 320),
        ("Superplastic", "Janky", "Janky x Pete Davidson 8-inch", "Collab", "mid", 280),

        # ── Coarse Figures (Round 5) ──────────────────────────────────────
        ("Coarse", "Omen", "Omen Void Black 8-inch", "Limited", "high", 650),
        ("Coarse", "Omen", "Omen Fade Shadow 8-inch", "Limited", "high", 700),
        ("Coarse", "Noop", "Noop Noop Bear Moss Green", "Limited", "mid", 350),
        ("Coarse", "Pain", "Pain Cry Ivory 12-inch", "Limited", "high", 900),
        ("Coarse", "False Friends", "False Friends Bunny & Wolf Set", "Limited", "high", 1200),
        ("Coarse", "Top", "Top Reach Glacier Blue 8-inch", "Limited", "high", 550),

        # ── Ron English Figures (Round 5) ─────────────────────────────────
        ("Ron English", "MC Supersized", "MC Supersized Gold Chrome 12-inch", "Limited", "high", 800),
        ("Ron English", "MC Supersized", "MC Supersized Glow 8-inch", "Limited", "mid", 350),
        ("Ron English", "Popaganda", "Temper Tot Blue 6-inch", "Limited", "mid", 250),
        ("Ron English", "Popaganda", "FAT Tony Neon Green 8-inch", "Limited", "mid", 300),
        ("Ron English", "Astronaut Grin", "Astronaut Grin OG White 12-inch", "Limited", "high", 500),

        # ── Takashi Murakami (Round 5) ────────────────────────────────────
        ("Takashi Murakami", "Flower", "Flower Plush Cushion Rainbow 60cm", "Open Edition", "mid", 200),
        ("Takashi Murakami", "Flower", "Flower Plush Cushion Blue Pink 30cm", "Open Edition", "standard", 80),
        ("Takashi Murakami", "Flower", "Flower Plush Cushion Black White 60cm", "Open Edition", "mid", 220),
        ("Takashi Murakami", "Mr. DOB", "Mr. DOB Figure Gold Chrome 10-inch", "Limited", "high", 1200),
        ("Takashi Murakami", "ComplexCon", "Murakami x ComplexCon Flower Pillow Signed", "ComplexCon Exclusive", "grail", 2500),
        ("Takashi Murakami", "Kaikai Kiki", "Kaikai & Kiki Blue Eyes Figure Set", "Limited", "high", 900),

        # ── Daniel Arsham Eroded Figures (Round 5) ────────────────────────
        ("Daniel Arsham", "Eroded", "Eroded Pikachu Resin Figure", "Limited", "grail", 4500),
        ("Daniel Arsham", "Eroded", "Eroded Porsche 911 Turbo Crystal", "Limited", "grail", 6000),
        ("Daniel Arsham", "Eroded", "Eroded Gameboy Crystal Relic", "Limited", "grail", 3200),
        ("Daniel Arsham", "Crystal Relic", "Crystal Relic Camera 002", "Limited", "grail", 3800),
        ("Daniel Arsham", "Future Relic", "Future Relic 09 Eroded Turntable", "Limited", "grail", 4200),
        ("Daniel Arsham", "Eroded", "Eroded Mickey Mouse Figure", "Limited", "grail", 5500),

        # ── James Jean x AllRightsReserved (Round 5) ──────────────────────
        ("James Jean", "Descendant", "Descendant Dragon Sculpture Frost Edition", "Limited", "high", 1200),
        ("James Jean", "Descendant", "Descendant Dragon Sculpture Fire Edition", "Limited", "high", 1400),
        ("James Jean", "AllRightsReserved", "Rider Sculpture Bronze Patina", "Limited", "grail", 2800),
        ("James Jean", "AllRightsReserved", "Lotus Sculpture Pink Resin", "Limited", "high", 800),

        # === EXPANSION ROUND 6 — 29 new items to reach 700+ ===

        # ── KAWS — 2025/2026 Releases (+6) ──────────────────────────────
        ("KAWS", "Companion", "Companion 2025 Open Edition (Grey)", "Open Edition", "mid", 300),
        ("KAWS", "Companion", "Companion 2025 Open Edition (Black)", "Open Edition", "mid", 310),
        ("KAWS", "Clean Slate", "Clean Slate Brown Open Edition 2023", "Open Edition", "mid", 380),
        ("KAWS", "Clean Slate", "Clean Slate Grey Open Edition 2023", "Open Edition", "mid", 370),
        ("KAWS", "Holiday", "KAWS Holiday Korea (Seoul Tower)", "Limited", "high", 920),
        ("KAWS", "Holiday", "KAWS Holiday Indonesia (Bali)", "Limited", "high", 880),

        # ── BE@RBRICK 100%+400% New Collabs (+6) ────────────────────────
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Jean-Michel Basquiat V8", "Collab", "mid", 350),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Banksy Flower Bomber", "Collab", "high", 700),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Nike SB Dunk Low Chicago", "Collab", "high", 650),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Travis Scott Cactus Jack", "Collab", "high", 850),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Stussy 40th Anniversary", "Collab", "mid", 480),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Karimoku Layered Wood 2024", "Collab", "grail", 4800),

        # ── Superplastic — 2025 Releases (+4) ───────────────────────────
        ("Superplastic", "Janky", "Janky x MrBeast 8-inch Superjanky", "Collab", "high", 480),
        ("Superplastic", "Guggimon", "Guggimon Tokyo Exclusive 8-inch", "Limited", "high", 550),
        ("Superplastic", "Dayzee", "Dayzee OG Pink 12-inch (1st Edition)", "Limited", "high", 600),
        ("Superplastic", "Superdoodle", "Superdoodle Rainbow Drip 8-inch", "Limited", "mid", 300),

        # ── Daniel Arsham — New Eroded (+4) ──────────────────────────────
        ("Daniel Arsham", "Eroded", "Eroded Darth Vader Helmet Crystal", "Limited", "grail", 5000),
        ("Daniel Arsham", "Eroded", "Eroded Basketball (Blue Calcite)", "Limited", "high", 1400),
        ("Daniel Arsham", "Future Relic", "Future Relic 10 Eroded Camera (White)", "Limited", "grail", 3500),
        ("Daniel Arsham", "Crystal Relic", "Crystal Relic 005 Cassette Player", "Limited", "high", 1300),

        # ── Pop Mart — Space Molly & New Lines (+5) ─────────────────────
        ("Pop Mart", "Space Molly", "Space Molly 400% Spongebob Collab", "Collab", "high", 450),
        ("Pop Mart", "Space Molly", "Space Molly 1000% Chrome Silver", "Collab", "grail", 2000),
        ("Pop Mart", "LABUBU", "LABUBU The Monsters Christmas 400%", "Limited", "high", 350),
        ("Pop Mart", "LABUBU", "LABUBU Have a Seat Series Sealed Case (12pc)", "Blind Box Set", "standard", 85),
        ("Pop Mart", "Hirono", "Hirono The Other One Series Sealed Case (12pc)", "Blind Box Set", "standard", 95),

        # ── Hebru Brantley & Luke Chueh (+4) ────────────────────────────
        ("Hebru Brantley", "Flyboy", "Flyboy OG Black 12-inch", "Limited", "high", 800),
        ("Hebru Brantley", "Flyboy", "Flyboy Chrome Gold 12-inch (ComplexCon)", "Collab", "grail", 1500),
        ("Luke Chueh", "Possessed", "Possessed Bear OG Pink 8-inch", "Limited", "mid", 350),
        ("Luke Chueh", "Possessed", "Possessed Bear Black & White 8-inch", "Limited", "mid", 380),
    ]

    catalog = []
    for brand, line, name, edition, tier, price in items:
        catalog.append({
            "brand": brand,
            "line": line,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    line = item["line"]
    name = item["name"]
    edition = item["edition"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{name}"),
        title=name,
        set_code=slugify(line),
        brand=brand,
        rarity=item["rarity_tier"].title(),
        notes=f"{brand} | {line}" + (f" | {edition}" if edition else ""),
        attributes_json={
            "brand": brand,
            "line": line,
            "edition": edition,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    edition = item["edition"]
    edition_scores = {
        "Limited": 0.85,
        "Collab": 0.75,
        "ComplexCon Exclusive": 0.95,
        "Mega": 0.80,
        "Open Edition": 0.3,
        "Standard": 0.2,
        "Blind Box Set": 0.2,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(edition, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Designer Toys catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Designer Toys Import ===")

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

    logger.info(f"\n=== Designer Toys Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
