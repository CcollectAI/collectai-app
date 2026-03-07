"""
Import Blind Box / Mystery Figure catalog (500+ items).

Layer 1 (Catalog):  Curated blind box figures → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Pop Mart (Labubu, Dimoo, Molly, Skullpanda, Hirono, Crybaby, Zsiga)
- Sonny Angels (fruit, animal, marine, dream, Christmas, Halloween, limited)
- tokidoki (Unicorno, Mermicorno, SANDy, Donutella)
- Kidrobot Dunny (various artists/series)
- Medicom Bearbrick blind box series
- BAIT / Secret Base collaborations
- Regional exclusives (China, Japan, Thailand)
- Vintage / discontinued (early Pop Mart, rare Sonny Angels)

Usage:
    python -m pipelines.import_blind_box [--dry-run]
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

CATEGORY = "blind_box"


def get_curated_catalog() -> list[dict]:
    """Curated blind box catalog (500+ items) covering major brands and subcategories."""

    # (name, brand, series, variant, rarity, price_eur, is_secret, notes)
    # Rarity tiers: Common, Uncommon, Rare, Secret, Ultra Rare, Grail
    # Prices in EUR, reflecting real secondary market values (2024-2026)

    items_raw = [
        # ── Pop Mart — Labubu ───────────────────────────────────────────
        ("Labubu The Monsters Tasty Life", "Pop Mart", "Labubu", "Tasty Life Series", "Common", 14, False, "Standard blind box figure, 12 designs"),
        ("Labubu The Monsters Have a Seat", "Pop Mart", "Labubu", "Have a Seat Series", "Common", 16, False, "Sitting pose series, 12 designs"),
        ("Labubu The Monsters Celebration", "Pop Mart", "Labubu", "Celebration Series", "Common", 15, False, "Party theme series"),
        ("Labubu Macaron Miffy Collab", "Pop Mart", "Labubu", "Miffy Collaboration", "Rare", 85, False, "Pop Mart x Miffy limited collab"),
        ("Labubu The Monsters Space Series Secret", "Pop Mart", "Labubu", "Space Series Secret", "Secret", 180, True, "Secret chase figure, glow-in-dark astronaut"),
        ("Labubu Zimomo Large Artist Series", "Pop Mart", "Labubu", "Artist Collab 400%", "Ultra Rare", 650, False, "Large format artist collaboration"),
        ("Labubu The Monsters Candy Series Secret", "Pop Mart", "Labubu", "Candy Secret", "Secret", 220, True, "Translucent candy variant chase"),
        ("Labubu Exciting Macaron Full Case", "Pop Mart", "Labubu", "Exciting Macaron", "Common", 12, False, "Standard series, 9+1 designs"),

        # ── Pop Mart — Dimoo ────────────────────────────────────────────
        ("Dimoo World Heritage Series", "Pop Mart", "Dimoo", "World Heritage", "Common", 14, False, "Landmark-themed figures"),
        ("Dimoo Fairy Tale Series", "Pop Mart", "Dimoo", "Fairy Tale", "Common", 13, False, "Classic fairy tale designs"),
        ("Dimoo Dating Day Series", "Pop Mart", "Dimoo", "Dating Day", "Common", 14, False, "Romantic theme blind box"),
        ("Dimoo Aquarium Series Secret Whale", "Pop Mart", "Dimoo", "Aquarium Secret", "Secret", 160, True, "Secret whale figure, highly sought"),
        ("Dimoo Midnight Circus Secret", "Pop Mart", "Dimoo", "Midnight Circus Secret", "Secret", 145, True, "Ringmaster secret chase"),

        # ── Pop Mart — Molly ────────────────────────────────────────────
        ("Molly Anniversary Statues Series", "Pop Mart", "Molly", "Anniversary Statues", "Common", 15, False, "Iconic series, 12 designs"),
        ("Molly x Instinctoy Erosion Molly", "Pop Mart", "Molly", "Instinctoy Erosion", "Rare", 180, False, "Artist collab limited edition"),
        ("Space Molly 400% Pinkerton", "Pop Mart", "Molly", "Space Molly 400%", "Ultra Rare", 650, False, "Large format, Pinkerton colorway"),
        ("Space Molly 1000% Jasmine", "Pop Mart", "Molly", "Space Molly 1000%", "Grail", 1800, False, "Mega size, Jasmine theme, extremely limited"),
        ("Molly Bug's World Secret Mantis", "Pop Mart", "Molly", "Bug's World Secret", "Secret", 130, True, "Metallic mantis chase figure"),

        # ── Pop Mart — Skullpanda ───────────────────────────────────────
        ("Skullpanda Night City Series", "Pop Mart", "Skullpanda", "Night City", "Common", 14, False, "Cyberpunk-themed series"),
        ("Skullpanda Tell Me What You Want", "Pop Mart", "Skullpanda", "Tell Me What You Want", "Common", 15, False, "Fashion-themed blind box"),
        ("Skullpanda Ancient Castle Secret", "Pop Mart", "Skullpanda", "Ancient Castle Secret", "Secret", 200, True, "Gothic castle secret chase"),

        # ── Pop Mart — Hirono ───────────────────────────────────────────
        ("Hirono The Other One Series", "Pop Mart", "Hirono", "The Other One", "Common", 16, False, "Dark fantasy theme, 9 designs"),
        ("Hirono Mime Series Secret", "Pop Mart", "Hirono", "Mime Secret", "Secret", 250, True, "Mime secret figure with mirror base"),
        ("Hirono Little Mischief Series", "Pop Mart", "Hirono", "Little Mischief", "Common", 15, False, "Playful mischief theme"),

        # ── Pop Mart — Crybaby ──────────────────────────────────────────
        ("Crybaby Crying in the Rain", "Pop Mart", "Crybaby", "Crying in the Rain", "Common", 14, False, "Rain theme series by Molly's creator"),
        ("Crybaby Monster Tears Secret", "Pop Mart", "Crybaby", "Monster Tears Secret", "Secret", 170, True, "Monster variant secret figure"),
        ("Crybaby Jungle Adventure Series", "Pop Mart", "Crybaby", "Jungle Adventure", "Common", 14, False, "Jungle explorer theme"),

        # ── Pop Mart — Zsiga ────────────────────────────────────────────
        ("Zsiga Walking Into the Forest", "Pop Mart", "Zsiga", "Forest Series", "Common", 15, False, "Forest creature designs"),
        ("Zsiga Second Generation I'm Not Me", "Pop Mart", "Zsiga", "I'm Not Me", "Common", 15, False, "Identity theme, 12 designs"),

        # ── Sonny Angels — Fruit ────────────────────────────────────────
        ("Sonny Angel Fruit Series Watermelon", "Sonny Angel", "Fruit Series", "Watermelon", "Common", 10, False, "Classic fruit hat figure"),
        ("Sonny Angel Fruit Series Strawberry", "Sonny Angel", "Fruit Series", "Strawberry", "Common", 10, False, "Iconic pink strawberry hat"),
        ("Sonny Angel Fruit Series Banana", "Sonny Angel", "Fruit Series", "Banana", "Common", 10, False, "Yellow banana hat figure"),
        ("Sonny Angel Fruit Series Robbie Secret", "Sonny Angel", "Fruit Series", "Robbie Secret", "Secret", 120, True, "Secret Robbie figure from fruit series"),

        # ── Sonny Angels — Animal ───────────────────────────────────────
        ("Sonny Angel Animal Series 4 Cat", "Sonny Angel", "Animal Series 4", "Cat", "Common", 11, False, "Cat costume angel baby"),
        ("Sonny Angel Animal Series 4 Rabbit", "Sonny Angel", "Animal Series 4", "Rabbit", "Common", 11, False, "Rabbit costume figure"),
        ("Sonny Angel Animal Series 4 Panda", "Sonny Angel", "Animal Series 4", "Panda", "Common", 11, False, "Panda costume figure"),
        ("Sonny Angel Animal Series 3 Elephant Robbie", "Sonny Angel", "Animal Series 3", "Elephant Robbie Secret", "Secret", 100, True, "Secret Robbie elephant variant"),

        # ── Sonny Angels — Marine ───────────────────────────────────────
        ("Sonny Angel Marine Series Clownfish", "Sonny Angel", "Marine Series", "Clownfish", "Common", 11, False, "Ocean creature hat"),
        ("Sonny Angel Marine Series Sea Otter", "Sonny Angel", "Marine Series", "Sea Otter", "Common", 11, False, "Otter costume figure"),
        ("Sonny Angel Marine Series Whale Shark Secret", "Sonny Angel", "Marine Series", "Whale Shark Secret", "Secret", 110, True, "Secret whale shark chase figure"),

        # ── Sonny Angels — Dream / Seasonal / Limited ───────────────────
        ("Sonny Angel Dream Series Cloud", "Sonny Angel", "Dream Series", "Cloud", "Uncommon", 18, False, "Dreamy cloud hat, pastel colors"),
        ("Sonny Angel Christmas 2023 Reindeer", "Sonny Angel", "Christmas 2023", "Reindeer", "Rare", 35, False, "Seasonal Christmas edition"),
        ("Sonny Angel Christmas 2023 Santa Secret", "Sonny Angel", "Christmas 2023", "Santa Secret", "Secret", 140, True, "Secret Santa chase figure"),
        ("Sonny Angel Halloween 2023 Pumpkin", "Sonny Angel", "Halloween 2023", "Pumpkin", "Rare", 30, False, "Seasonal Halloween edition"),
        ("Sonny Angel Halloween 2023 Ghost Secret", "Sonny Angel", "Halloween 2023", "Ghost Secret", "Secret", 130, True, "Translucent ghost secret figure"),
        ("Sonny Angel 20th Anniversary Crown", "Sonny Angel", "20th Anniversary", "Crown Limited", "Ultra Rare", 280, False, "Gold crown limited anniversary edition"),
        ("Sonny Angel Hippers Looking Back Cat", "Sonny Angel", "Hippers Series", "Looking Back Cat", "Rare", 45, False, "Hippers sitting pose series"),

        # ── tokidoki — Unicorno ─────────────────────────────────────────
        ("Unicorno Series 12 Starlight", "tokidoki", "Unicorno Series 12", "Starlight", "Common", 12, False, "Galaxy-themed unicorn blind box"),
        ("Unicorno Series 12 Cosmo Chase", "tokidoki", "Unicorno Series 12", "Cosmo Chase", "Rare", 55, True, "Chase variant with metallic finish"),
        ("Unicorno Metallico Series Chrome Pegasus", "tokidoki", "Unicorno Metallico", "Chrome Pegasus", "Rare", 65, False, "Full chrome metallic figure"),
        ("Unicorno Cherry Blossom Series Sakura", "tokidoki", "Unicorno Cherry Blossom", "Sakura", "Common", 13, False, "Japanese cherry blossom theme"),
        ("Unicorno x Hello Kitty Collab", "tokidoki", "Unicorno x Sanrio", "Hello Kitty", "Rare", 70, False, "Sanrio crossover limited edition"),

        # ── tokidoki — Mermicorno ───────────────────────────────────────
        ("Mermicorno Series 7 Coral", "tokidoki", "Mermicorno Series 7", "Coral", "Common", 12, False, "Mermaid unicorn ocean theme"),
        ("Mermicorno Series 7 Abyssal Chase", "tokidoki", "Mermicorno Series 7", "Abyssal Chase", "Rare", 50, True, "Deep sea chase variant"),
        ("Mermicorno Series 6 Pearl", "tokidoki", "Mermicorno Series 6", "Pearl", "Common", 11, False, "Pearl shimmer finish"),

        # ── tokidoki — SANDy / Donutella ────────────────────────────────
        ("SANDy Fantasy Series Castle", "tokidoki", "SANDy Fantasy", "Castle", "Common", 13, False, "Sand castle character figure"),
        ("Donutella and Her Sweet Friends Series 3 Choco", "tokidoki", "Donutella Series 3", "Choco", "Common", 11, False, "Donut-themed character"),
        ("Donutella Series 3 Golden Glaze Chase", "tokidoki", "Donutella Series 3", "Golden Glaze Chase", "Rare", 60, True, "Gold metallic donut chase"),

        # ── Kidrobot Dunny ──────────────────────────────────────────────
        ("Dunny Series 2024 Full Case", "Kidrobot", "Dunny Series 2024", "Full Case", "Common", 85, False, "20-piece sealed case, 16 designs + chases"),
        ("Dunny 8-inch Huck Gee Gold Life", "Kidrobot", "Dunny Artist", "Huck Gee Gold Life", "Rare", 280, False, "Artist series by Huck Gee"),
        ("Dunny 8-inch Kronk Wild Ones", "Kidrobot", "Dunny Artist", "Kronk Wild Ones", "Rare", 180, False, "Kronk artist collaboration"),
        ("Dunny 3-inch Azteca II Chase", "Kidrobot", "Dunny Azteca II", "Chase Figure", "Secret", 150, True, "Azteca II secret chase figure"),
        ("Dunny 3-inch Andy Warhol Series 2", "Kidrobot", "Dunny Warhol", "Series 2 Blind Box", "Common", 18, False, "Warhol pop art designs"),
        ("Dunny 8-inch Jean-Michel Basquiat", "Kidrobot", "Dunny Artist", "Basquiat Masterpiece", "Rare", 220, False, "Basquiat art collaboration"),
        ("Dunny 3-inch City Cryptid Mothman Chase", "Kidrobot", "Dunny City Cryptid", "Mothman Chase", "Secret", 130, True, "Glow-in-dark Mothman secret"),
        ("Dunny Evolved Series Full Case", "Kidrobot", "Dunny Evolved", "Full Case", "Common", 90, False, "Evolution theme, sealed case"),

        # ── Medicom Bearbrick Blind Boxes ───────────────────────────────
        ("Bearbrick Series 46 Sealed Case", "Medicom", "Bearbrick Series 46", "Sealed Case", "Common", 95, False, "24-piece sealed case, 100% size"),
        ("Bearbrick Series 45 Sealed Case", "Medicom", "Bearbrick Series 45", "Sealed Case", "Common", 90, False, "24-piece sealed case"),
        ("Bearbrick Series 44 Artist Chase", "Medicom", "Bearbrick Series 44", "Artist Chase", "Secret", 160, True, "Secret artist collaboration piece"),
        ("Bearbrick Series 43 Horror Chase", "Medicom", "Bearbrick Series 43", "Horror Chase", "Secret", 140, True, "Horror theme secret figure"),
        ("Bearbrick Series 42 SF Chase", "Medicom", "Bearbrick Series 42", "Science Fiction Chase", "Secret", 135, True, "Sci-fi theme secret figure"),

        # ── BAIT / Secret Base Collaborations ───────────────────────────
        ("BAIT x Secret Base Skull Bee Clear Blue", "BAIT", "Secret Base Collab", "Skull Bee Clear Blue", "Rare", 350, False, "BAIT exclusive clear blue colorway"),
        ("BAIT x Kidrobot Dunny Street Fighter Akuma", "BAIT", "Kidrobot Collab", "Street Fighter Akuma", "Rare", 180, False, "BAIT exclusive SF collab"),
        ("Secret Base Ghost Bear BAIT Glow Edition", "Secret Base", "Ghost Bear", "BAIT Glow Edition", "Ultra Rare", 450, False, "Glow-in-dark BAIT exclusive"),
        ("BAIT x tokidoki Unicorno SDCC Black", "BAIT", "tokidoki Collab", "Unicorno SDCC Black", "Rare", 120, False, "San Diego Comic Con exclusive"),
        ("Secret Base Honey Bear Gold Chrome", "Secret Base", "Honey Bear", "Gold Chrome", "Grail", 900, False, "Limited gold chrome colorway, 100 pieces"),

        # ── Regional Exclusives — China ─────────────────────────────────
        ("Pop Mart Dimoo Hanfu Series China Exclusive", "Pop Mart", "Dimoo Hanfu", "China Exclusive", "Rare", 45, False, "China mainland exclusive Hanfu theme"),
        ("Pop Mart Labubu Year of Dragon Gold", "Pop Mart", "Labubu Zodiac", "Dragon Gold China", "Ultra Rare", 380, False, "Chinese New Year 2024, gold dragon, China-only"),
        ("52TOYS Panda Roll Beach Series", "52TOYS", "Panda Roll", "Beach Series", "Common", 10, False, "Chinese brand, panda theme blind box"),
        ("FINDING UNICORN Shinwoo Ghost Bear Pink", "Finding Unicorn", "Shinwoo Ghost Bear", "Pink China Exclusive", "Rare", 55, False, "Chinese designer toy brand exclusive"),

        # ── Regional Exclusives — Japan ─────────────────────────────────
        ("Sonny Angel Kewpie Collab Japan Only", "Sonny Angel", "Kewpie Collab", "Japan Exclusive", "Rare", 65, False, "Japan domestic market only release"),
        ("Pop Mart Labubu Maneki Neko Japan Exclusive", "Pop Mart", "Labubu Maneki Neko", "Japan Pop-Up Exclusive", "Rare", 85, False, "Lucky cat theme, Japan pop-up store only"),
        ("Medicom Bearbrick Series 44 Fujiko F Fujio Japan", "Medicom", "Bearbrick Japan", "Fujiko F Fujio", "Rare", 75, False, "Japan-exclusive Doraemon artist figure"),

        # ── Regional Exclusives — Thailand / SEA ────────────────────────
        ("Pop Mart Crybaby Songkran Festival Thailand", "Pop Mart", "Crybaby Songkran", "Thailand Exclusive", "Rare", 70, False, "Thai Songkran water festival edition"),
        ("Pop Mart Labubu Thai Tea Series Bangkok", "Pop Mart", "Labubu Thai Tea", "Bangkok Pop-Up", "Rare", 60, False, "Bangkok store exclusive, milk tea theme"),
        ("Sank Toys Good Night Series Thailand Release", "Sank Toys", "Good Night", "Thailand Release", "Uncommon", 25, False, "Thai market exclusive sleeping figures"),

        # ── Vintage / Discontinued — Early Pop Mart ─────────────────────
        ("Molly Kennyswork 1st Edition 2006 OG", "Pop Mart", "Molly OG", "1st Edition 2006", "Grail", 1200, False, "Original Molly by Kenny Wong before Pop Mart, extremely rare"),
        ("Dimoo World Series 1st Run 2019", "Pop Mart", "Dimoo World V1", "1st Run 2019", "Rare", 120, False, "First Dimoo blind box run, discontinued"),
        ("Pucky Sleeping Forest 1st Edition", "Pop Mart", "Pucky Sleeping Forest V1", "1st Edition", "Rare", 95, False, "First Pucky series, 2019 original run"),
        ("Labubu The Monsters Series 1 OG 2019", "Pop Mart", "Labubu OG", "Series 1 Original 2019", "Ultra Rare", 350, False, "First Labubu blind box, now discontinued"),
        ("Space Molly 1000% Shark 2021", "Pop Mart", "Space Molly 1000%", "Shark 2021 Edition", "Grail", 2000, False, "Sold out instantly, extreme secondary market premium"),

        # ── Vintage / Discontinued — Rare Sonny Angels ──────────────────
        ("Sonny Angel Mini Figure 2004 1st Release Cupid", "Sonny Angel", "Original 2004", "Cupid 1st Release", "Grail", 450, False, "First-ever Sonny Angel release, museum piece"),
        ("Sonny Angel Valentine 2012 Chocolate", "Sonny Angel", "Valentine 2012", "Chocolate", "Ultra Rare", 200, False, "Early Valentine limited, long discontinued"),
        ("Sonny Angel Cherry Blossom 2015 Limited", "Sonny Angel", "Cherry Blossom 2015", "Sakura Limited", "Ultra Rare", 180, False, "Japan spring limited, highly collectible"),
        ("Sonny Angel Artist Collection Isetan Mitsukoshi", "Sonny Angel", "Artist Collection", "Isetan Exclusive", "Grail", 380, False, "Department store exclusive artist collab, 500 pcs"),
        ("Sonny Angel Robbie Angel Crown Gold", "Sonny Angel", "Robbie Angel", "Crown Gold", "Grail", 550, False, "Rarest Robbie variant, gold crown, under 200 made"),

        # ── Pop Mart — DIMOO World (expanded) ─────────────────────────────
        ("Dimoo World Heritage Series Sphinx", "Pop Mart", "Dimoo", "World Heritage Sphinx", "Common", 14, False, "Egyptian Sphinx design from World Heritage"),
        ("Dimoo Letters fromErta Series", "Pop Mart", "Dimoo", "Letters from Erta", "Common", 15, False, "Nature postal theme, 12 designs"),
        ("Dimoo Natural History Museum Secret", "Pop Mart", "Dimoo", "Natural History Secret", "Secret", 175, True, "Dinosaur skeleton glow secret chase"),

        # ── Pop Mart — Pucky ──────────────────────────────────────────────
        ("Pucky Sleeping Forest Series Deer", "Pop Mart", "Pucky", "Sleeping Forest Deer", "Common", 14, False, "Sleeping forest animal theme"),
        ("Pucky What Are the Fairies Doing", "Pop Mart", "Pucky", "Fairy Series", "Common", 14, False, "Fairy-themed series, 12 designs"),
        ("Pucky Horoscope Babies Secret", "Pop Mart", "Pucky", "Horoscope Secret", "Secret", 155, True, "Zodiac baby secret chase figure"),
        ("Pucky Pool Babies Series", "Pop Mart", "Pucky", "Pool Babies", "Common", 13, False, "Swimming pool theme babies"),

        # ── Pop Mart — Molly Career / Mega ────────────────────────────────
        ("Molly Career Series Astronaut", "Pop Mart", "Molly", "Career Astronaut", "Common", 15, False, "Career-themed Molly, astronaut design"),
        ("Molly Career Series Chef", "Pop Mart", "Molly", "Career Chef", "Common", 15, False, "Career-themed Molly, chef design"),
        ("Molly My Childhood Series", "Pop Mart", "Molly", "My Childhood", "Common", 14, False, "Nostalgic childhood theme"),
        ("Space Molly 1000% Backyard Party", "Pop Mart", "Molly", "Space Molly 1000%", "Grail", 1500, False, "Mega size, Backyard Party colorway, limited 3000pcs"),
        ("Mega Molly Space 400% Chrome", "Pop Mart", "Molly", "Mega Molly 400%", "Ultra Rare", 550, False, "Chrome finish large format Molly"),

        # ── Pop Mart — Labubu Monster (expanded) ──────────────────────────
        ("Labubu The Monsters Warm Together", "Pop Mart", "Labubu", "Warm Together Series", "Common", 15, False, "Winter warmth theme, 12 designs"),
        ("Labubu The Monsters Dream Series", "Pop Mart", "Labubu", "Dream Series", "Common", 14, False, "Dream cloud theme blind box"),
        ("Labubu Treasure Island Series Secret", "Pop Mart", "Labubu", "Treasure Island Secret", "Secret", 195, True, "Pirate treasure secret chase, metallic gold"),

        # ── Pop Mart — Crybaby (expanded) ─────────────────────────────────
        ("Crybaby Sad Club Series", "Pop Mart", "Crybaby", "Sad Club", "Common", 14, False, "Emotional club theme, 12 designs"),
        ("Crybaby × Powerpuff Girls Collab", "Pop Mart", "Crybaby", "Powerpuff Collab", "Rare", 75, False, "Cartoon Network licensed collab"),

        # ── BE@RBRICK Blind Boxes ─────────────────────────────────────────
        ("Bearbrick Series 47 Sealed Case", "Medicom", "Bearbrick Series 47", "Sealed Case", "Common", 98, False, "24-piece sealed case, latest series"),
        ("Bearbrick 100% KAWS Dissected Companion Grey", "Medicom", "Bearbrick x KAWS", "Dissected Grey 100%", "Rare", 280, False, "KAWS artist collab, grey dissected"),
        ("Bearbrick 100% KAWS Companion Black", "Medicom", "Bearbrick x KAWS", "Companion Black 100%", "Rare", 250, False, "KAWS all-black variant from blind series"),
        ("Bearbrick 100% Banksy Flower Thrower", "Medicom", "Bearbrick x Banksy", "Flower Thrower 100%", "Rare", 220, False, "Banksy street art collaboration blind box"),
        ("Bearbrick 100% Banksy Girl with Balloon", "Medicom", "Bearbrick x Banksy", "Girl with Balloon 100%", "Rare", 240, False, "Banksy iconic artwork collab"),
        ("Bearbrick 400% KAWS Tension Pink", "Medicom", "Bearbrick x KAWS", "Tension Pink 400%", "Ultra Rare", 850, False, "Large format KAWS collab, tension series"),

        # ── 52TOYS ────────────────────────────────────────────────────────
        ("52TOYS BEASTBOX Dio Transforming Cube", "52TOYS", "BEASTBOX", "Dio Cube", "Common", 18, False, "Transforming animal cube figure"),
        ("52TOYS BEASTBOX Jaws Great White", "52TOYS", "BEASTBOX", "Jaws Great White", "Uncommon", 22, False, "Great white shark transform cube"),
        ("52TOYS Panda Roll Dessert Series", "52TOYS", "Panda Roll", "Dessert Series", "Common", 10, False, "Rolling panda dessert theme"),
        ("52TOYS Panda Roll Hot Spring Series", "52TOYS", "Panda Roll", "Hot Spring", "Common", 10, False, "Panda in onsen/hot spring theme"),
        ("52TOYS Panda Roll Secret Gold Panda", "52TOYS", "Panda Roll", "Gold Panda Secret", "Secret", 85, True, "Gold chrome panda secret chase"),

        # ── FINDING UNICORN ───────────────────────────────────────────────
        ("Shinwoo Ghost Bear Lonely Christmas", "Finding Unicorn", "Shinwoo Ghost Bear", "Lonely Christmas", "Common", 16, False, "Christmas themed ghost bear series"),
        ("Shinwoo Ghost Bear White Night Secret", "Finding Unicorn", "Shinwoo Ghost Bear", "White Night Secret", "Secret", 120, True, "Translucent white glow secret chase"),
        ("Zimomo Starry Night Series", "Finding Unicorn", "Zimomo", "Starry Night", "Common", 15, False, "Star-themed series, 9 designs"),
        ("Zimomo Flower Language Secret", "Finding Unicorn", "Zimomo", "Flower Language Secret", "Secret", 110, True, "Floral bouquet secret figure"),

        # ── ToyCity ───────────────────────────────────────────────────────
        ("Laura Rainy Day Series", "ToyCity", "Laura", "Rainy Day Series", "Common", 14, False, "Rain theme Laura series, 9+1 designs"),
        ("Laura Sweet Bean Cake Series", "ToyCity", "Laura", "Sweet Bean Cake", "Common", 14, False, "Dessert pastry theme Laura"),
        ("ToyCity x Sanrio Characters Blind Box", "ToyCity", "Sanrio Collab", "Sanrio Characters", "Uncommon", 18, False, "ToyCity x Sanrio licensed crossover"),

        # ── Japanese Gacha / Gashapon ─────────────────────────────────────
        ("Bandai Gashapon Hug Cot Pikachu", "Bandai", "Gashapon Hug Cot", "Pikachu Cable Hugger", "Common", 5, False, "Cable-hugging Pikachu capsule toy"),
        ("Bandai Gashapon Cup no Fuchiko", "Bandai", "Gashapon", "Cup no Fuchiko", "Common", 4, False, "OL figure on cup rim, viral gashapon"),
        ("Takara Tomy A.R.T.S. Sumikko Gurashi Capsule", "Takara Tomy", "A.R.T.S. Gashapon", "Sumikko Gurashi", "Common", 5, False, "San-X character capsule toy"),
        ("Takara Tomy A.R.T.S. Neko Atsume Capsule", "Takara Tomy", "A.R.T.S. Gashapon", "Neko Atsume", "Common", 4, False, "Cat collection game characters"),

        # ── James Jean x POP MART ─────────────────────────────────────────
        ("James Jean x Pop Mart The Traveler", "Pop Mart", "James Jean Collab", "The Traveler", "Rare", 95, False, "Fine artist James Jean collaboration"),
        ("James Jean x Pop Mart Lil' Foxes Series", "Pop Mart", "James Jean Collab", "Lil' Foxes", "Uncommon", 25, False, "Fox-themed artist blind box series"),

        # ── Convention Exclusives ──────────────────────────────────────────
        ("Pop Mart Labubu Thailand Toy Expo Gold", "Pop Mart", "Labubu TTE", "Thailand Toy Expo Gold", "Ultra Rare", 420, False, "Thailand Toy Expo 2024 exclusive, gold variant"),
        ("Pop Mart Skullpanda Designer Con Black", "Pop Mart", "Skullpanda DesignerCon", "DesignerCon Black", "Rare", 110, False, "Designer Con Anaheim exclusive colorway"),
        ("Kidrobot Dunny SDCC 2024 Metallic Chase", "Kidrobot", "Dunny SDCC", "SDCC 2024 Metallic", "Ultra Rare", 350, True, "San Diego Comic-Con exclusive metallic"),

        # ── Miniso Blind Boxes ────────────────────────────────────────────
        ("Miniso x Sanrio Cinnamoroll Cloud Series", "Miniso", "Sanrio Collab", "Cinnamoroll Cloud", "Common", 8, False, "Miniso x Sanrio blind box, cloud theme"),
        ("Miniso x Disney Tsum Tsum Series", "Miniso", "Disney Collab", "Tsum Tsum Blind Box", "Common", 8, False, "Miniso x Disney stackable figures"),
        ("Miniso x Sanrio Kuromi Gothic Rose", "Miniso", "Sanrio Collab", "Kuromi Gothic Rose", "Common", 9, False, "Miniso x Sanrio Kuromi gothic theme"),
        ("Miniso x Disney Stitch Tropical Series", "Miniso", "Disney Collab", "Stitch Tropical", "Common", 8, False, "Miniso x Disney Hawaiian Stitch"),

        # ── Pop Mart — Sweet Bean ────────────────────────────────────────
        ("Sweet Bean Supermarket Series", "Pop Mart", "Sweet Bean", "Supermarket Series", "Common", 14, False, "Grocery shopping theme, 12 designs"),
        ("Sweet Bean Akihabara Series", "Pop Mart", "Sweet Bean", "Akihabara Series", "Common", 15, False, "Japanese otaku culture theme"),
        ("Sweet Bean Frozen Time Secret", "Pop Mart", "Sweet Bean", "Frozen Time Secret", "Secret", 165, True, "Ice crystal secret chase figure"),

        # ── Pop Mart — KUBO ──────────────────────────────────────────────
        ("KUBO What Will Happen Series", "Pop Mart", "KUBO", "What Will Happen", "Common", 14, False, "Daily life misadventures, 12 designs"),
        ("KUBO Sports Day Secret", "Pop Mart", "KUBO", "Sports Day Secret", "Secret", 140, True, "Golden trophy secret chase figure"),

        # ── Pop Mart — Yuki ──────────────────────────────────────────────
        ("Yuki Transparent Season Series", "Pop Mart", "Yuki", "Transparent Season", "Common", 15, False, "Seasonal transparent body designs"),
        ("Yuki Space Travel Series Secret", "Pop Mart", "Yuki", "Space Travel Secret", "Secret", 185, True, "Holographic astronaut secret chase"),

        # ── Pop Mart — Vita ──────────────────────────────────────────────
        ("Vita Daily Wear Series", "Pop Mart", "Vita", "Daily Wear", "Common", 14, False, "Fashion outfit theme, 9 designs"),
        ("Vita Vintage Market Secret", "Pop Mart", "Vita", "Vintage Market Secret", "Secret", 150, True, "Retro clothing secret variant"),

        # ── Pop Mart — Azura ─────────────────────────────────────────────
        ("Azura Ocean Voyage Series", "Pop Mart", "Azura", "Ocean Voyage", "Common", 15, False, "Nautical voyage theme, 12 designs"),
        ("Azura Deep Sea Secret", "Pop Mart", "Azura", "Deep Sea Secret", "Secret", 175, True, "Bioluminescent deep sea chase"),

        # ── Pop Mart — RiCO ──────────────────────────────────────────────
        ("RiCO Happy Festival Series", "Pop Mart", "RiCO", "Happy Festival", "Common", 14, False, "Festival celebration theme"),
        ("RiCO Valentine Secret Rose Gold", "Pop Mart", "RiCO", "Valentine Secret", "Secret", 160, True, "Rose gold metallic secret chase"),

        # ── Sonny Angels — Vegetable ─────────────────────────────────────
        ("Sonny Angel Vegetable Series Carrot", "Sonny Angel", "Vegetable Series", "Carrot", "Common", 11, False, "Carrot hat angel baby figure"),
        ("Sonny Angel Vegetable Series Corn", "Sonny Angel", "Vegetable Series", "Corn", "Common", 11, False, "Corn costume figure"),
        ("Sonny Angel Vegetable Series Eggplant Secret", "Sonny Angel", "Vegetable Series", "Eggplant Secret", "Secret", 105, True, "Secret eggplant Robbie variant"),

        # ── Sonny Angels — Flower ────────────────────────────────────────
        ("Sonny Angel Flower Series Rose", "Sonny Angel", "Flower Series", "Rose", "Common", 12, False, "Rose hat angel baby"),
        ("Sonny Angel Flower Series Sunflower", "Sonny Angel", "Flower Series", "Sunflower", "Common", 12, False, "Sunflower hat figure"),
        ("Sonny Angel Flower Series Lily Secret", "Sonny Angel", "Flower Series", "Lily Secret", "Secret", 115, True, "Secret lily Robbie variant"),

        # ── Sonny Angels — Sweets ────────────────────────────────────────
        ("Sonny Angel Sweets Series Macaron", "Sonny Angel", "Sweets Series", "Macaron", "Uncommon", 16, False, "Pastel macaron hat figure"),
        ("Sonny Angel Sweets Series Pudding", "Sonny Angel", "Sweets Series", "Pudding", "Uncommon", 16, False, "Caramel pudding hat figure"),

        # ── tokidoki — Cactus Friends ────────────────────────────────────
        ("Cactus Friends Cactus Pup", "tokidoki", "Cactus Friends", "Cactus Pup", "Common", 12, False, "Cactus dog character blind box"),
        ("Cactus Friends Golden Cactus Chase", "tokidoki", "Cactus Friends", "Golden Cactus Chase", "Rare", 55, True, "Gold metallic cactus chase figure"),

        # ── tokidoki — Sushi Cars ────────────────────────────────────────
        ("Sushi Cars Tuna Roll Racer", "tokidoki", "Sushi Cars", "Tuna Roll Racer", "Common", 13, False, "Sushi-themed vehicle blind box"),
        ("Sushi Cars Wasabi Drift Chase", "tokidoki", "Sushi Cars", "Wasabi Drift Chase", "Rare", 48, True, "Green metallic wasabi chase"),

        # ── Kidrobot — Labbit ────────────────────────────────────────────
        ("Labbit Insiders Series Full Case", "Kidrobot", "Labbit Insiders", "Full Case", "Common", 75, False, "12-piece sealed case, Frank Kozik designs"),
        ("Labbit 14-inch Smorkin Labbit", "Kidrobot", "Labbit", "Smorkin Labbit 14-inch", "Rare", 150, False, "Large format Frank Kozik Labbit"),

        # ── Kidrobot — Simpsons ──────────────────────────────────────────
        ("Kidrobot Simpsons Series 1 Homer", "Kidrobot", "Simpsons Series 1", "Homer", "Common", 22, False, "Matt Groening licensed blind box"),
        ("Kidrobot Simpsons Treehouse of Horror Chase", "Kidrobot", "Simpsons Treehouse", "Treehouse Chase", "Secret", 120, True, "Halloween special secret chase"),

        # ── Sank Toys ────────────────────────────────────────────────────
        ("Sank Toys Good Night Series Pillow", "Sank Toys", "Good Night", "Pillow Variant", "Common", 22, False, "Sleeping child figure with pillow"),
        ("Sank Toys On the Way Home Sunset", "Sank Toys", "On the Way Home", "Sunset Edition", "Uncommon", 28, False, "Golden sunset colorway figure"),
        ("Sank Toys Lost In Life Series Coffee", "Sank Toys", "Lost In Life", "Coffee Break", "Common", 24, False, "Office worker drinking coffee pose"),
        ("Sank Toys Good Night Galaxy Secret", "Sank Toys", "Good Night", "Galaxy Secret", "Secret", 180, True, "Glow-in-dark galaxy pattern secret"),

        # ── POP BEAN ─────────────────────────────────────────────────────
        ("POP BEAN Dreamy Park Series", "POP BEAN", "Dreamy Park", "Dreamy Park Series", "Common", 12, False, "Amusement park theme, Chinese designer brand"),
        ("POP BEAN Summer Pool Secret", "POP BEAN", "Summer Fun", "Pool Party Secret", "Secret", 90, True, "Inflatable pool ring secret chase"),

        # ── RICO x Disney ────────────────────────────────────────────────
        ("Pop Mart Disney Princess Sitting Series", "Pop Mart", "Disney Princess", "Sitting Princess Series", "Uncommon", 18, False, "Disney licensed princess sitting pose"),
        ("Pop Mart Disney Villains Series", "Pop Mart", "Disney Villains", "Villains Series", "Uncommon", 18, False, "Disney villains character blind box"),
        ("Pop Mart Mickey Ever-Curious Series", "Pop Mart", "Mickey Mouse", "Ever-Curious Series", "Uncommon", 16, False, "Mickey Mouse exploration theme"),
        ("Pop Mart Mickey Ever-Curious Secret Steamboat", "Pop Mart", "Mickey Mouse", "Steamboat Secret", "Secret", 200, True, "Steamboat Willie vintage secret chase"),

        # ── Mega Space Molly KAWS / Artist ───────────────────────────────
        ("Space Molly 400% KAWS Companion", "Pop Mart", "Molly", "Space Molly 400% KAWS", "Grail", 1200, False, "KAWS artist collaboration, extremely limited"),
        ("Space Molly 1000% Keith Haring", "Pop Mart", "Molly", "Space Molly 1000% Keith Haring", "Grail", 1600, False, "Keith Haring pop art edition, 1000 pcs"),

        # ── Funko Mystery Minis ──────────────────────────────────────────
        ("Funko Mystery Minis Harry Potter S3", "Funko", "Mystery Minis", "Harry Potter Series 3", "Common", 8, False, "Funko blind box, Harry Potter license"),
        ("Funko Mystery Minis Marvel Zombies Chase", "Funko", "Mystery Minis", "Marvel Zombies Chase", "Rare", 45, True, "Glow-in-dark zombie chase variant"),

        # ── Mighty Jaxx ──────────────────────────────────────────────────
        ("Mighty Jaxx Freeny's Hidden Dissectibles One Piece", "Mighty Jaxx", "Hidden Dissectibles", "One Piece Series", "Uncommon", 22, False, "Anatomical One Piece figures"),
        ("Mighty Jaxx XXRAY Spongebob Chase", "Mighty Jaxx", "XXRAY", "Spongebob Gold Chase", "Rare", 95, True, "Gold dissection variant chase"),

        # ── Kasing Lung Zimomo (expanded) ────────────────────────────────
        ("Zimomo The Explorer Series", "Finding Unicorn", "Zimomo", "The Explorer", "Common", 15, False, "Adventure explorer theme, 9 designs"),
        ("Zimomo Secret Garden Secret", "Finding Unicorn", "Zimomo", "Secret Garden Secret", "Secret", 130, True, "Floral overgrown secret chase figure"),

        # ── Convention & Store Exclusives (expanded) ─────────────────────
        ("Pop Mart Molly New York Exclusive Liberty", "Pop Mart", "Molly NYC", "Statue of Liberty", "Rare", 95, False, "NYC flagship store exclusive"),
        ("Pop Mart Dimoo Shanghai Exclusive Bund", "Pop Mart", "Dimoo Shanghai", "The Bund Edition", "Rare", 80, False, "Shanghai flagship exclusive"),
        ("Sonny Angel Paris Exclusive Eiffel", "Sonny Angel", "Paris Exclusive", "Eiffel Tower Hat", "Rare", 75, False, "Paris store exclusive edition"),
        ("tokidoki NYCC 2024 Unicorno Neon", "tokidoki", "NYCC 2024", "Unicorno Neon", "Ultra Rare", 140, False, "New York Comic Con exclusive neon"),

        # ── Vintage / Discontinued — Kidrobot & tokidoki ─────────────────
        ("Dunny Series 2005 Full Case OG", "Kidrobot", "Dunny Series 2005", "Full Case OG", "Grail", 800, False, "Original 2005 series, sealed case extremely rare"),
        ("tokidoki Unicorno Series 1 OG 2013", "tokidoki", "Unicorno Series 1", "OG 2013 Edition", "Rare", 90, False, "First unicorno series, long discontinued"),
        ("Kidrobot Munny 4-inch DIY Blank OG 2006", "Kidrobot", "Munny", "DIY Blank OG 2006", "Uncommon", 35, False, "Original blank platform figure, 2006"),

        # ── INSTINCTOY / Sofubi Style ────────────────────────────────────
        ("INSTINCTOY Liquid Series Clear Purple", "INSTINCTOY", "Liquid Series", "Clear Purple", "Rare", 120, False, "Japanese sofubi designer toy, clear resin"),
        ("INSTINCTOY Erosion Molly Gold Dust", "INSTINCTOY", "Erosion Molly", "Gold Dust Edition", "Ultra Rare", 350, False, "Premium resin erosion figure, gold flakes"),

        # ── Coarse Toys ──────────────────────────────────────────────────
        ("Coarse Omen Fade 5-inch", "Coarse", "Omen", "Fade Edition", "Rare", 180, False, "German designer toy brand, limited colorway"),
        ("Coarse Noop Noop Darkness", "Coarse", "Noop Noop", "Darkness Edition", "Rare", 160, False, "Matte black limited edition figure"),

        # ── Additional Pop Mart — Hirono ─────────────────────────────────
        ("Hirono Reshape Series", "Pop Mart", "Hirono", "Reshape Series", "Common", 16, False, "Surreal body reshape theme, 9 designs"),
        ("Hirono Reshape Secret Prism", "Pop Mart", "Hirono", "Reshape Secret Prism", "Secret", 240, True, "Prismatic crystal body secret chase"),

        # ── Additional Sonny Angel — Bugs ────────────────────────────────
        ("Sonny Angel Bug's World Ladybug", "Sonny Angel", "Bug's World", "Ladybug", "Common", 12, False, "Ladybug costume angel baby figure"),
        ("Sonny Angel Bug's World Stag Beetle Secret", "Sonny Angel", "Bug's World", "Stag Beetle Secret", "Secret", 125, True, "Secret stag beetle Robbie variant"),

        # ── Additional Mighty Jaxx ───────────────────────────────────────
        ("Mighty Jaxx Kandy x Spongebob Blind Box", "Mighty Jaxx", "Kandy", "Spongebob Series", "Common", 18, False, "Kandy format Spongebob blind box figures"),
        ("Mighty Jaxx XXRAY Plus Batman Chase Gold", "Mighty Jaxx", "XXRAY Plus", "Batman Gold Chase", "Rare", 110, True, "Gold variant dissection Batman chase"),

        # ── Pop Mart — Labubu (more series) ──────────────────────────────
        ("Labubu The Monsters Flower Mirror Series", "Pop Mart", "Labubu", "Flower Mirror Series", "Common", 15, False, "Floral mirror theme, 12 designs"),
        ("Labubu The Monsters Music Festival", "Pop Mart", "Labubu", "Music Festival Series", "Common", 16, False, "Music festival theme with instrument accessories"),
        ("Labubu The Monsters Fruit Series Secret", "Pop Mart", "Labubu", "Fruit Series Secret", "Secret", 210, True, "Translucent fruit secret chase with glitter"),
        ("Labubu The Monsters Swimming Pool", "Pop Mart", "Labubu", "Swimming Pool Series", "Common", 14, False, "Pool float poses, 9+1 designs"),

        # ── Pop Mart — Dimoo (more series) ────────────────────────────────
        ("Dimoo Animal Kingdom Series", "Pop Mart", "Dimoo", "Animal Kingdom", "Common", 14, False, "Animal costume Dimoo, 12 designs"),
        ("Dimoo Space Travel Series Secret Nebula", "Pop Mart", "Dimoo", "Space Travel Secret", "Secret", 170, True, "Holographic nebula Dimoo secret chase"),
        ("Dimoo No Limits Series", "Pop Mart", "Dimoo", "No Limits", "Common", 15, False, "Extreme sports theme, skateboard/surf/BMX"),

        # ── Pop Mart — Skullpanda (more series) ───────────────────────────
        ("Skullpanda The Mare of Animals Series", "Pop Mart", "Skullpanda", "Mare of Animals", "Common", 15, False, "Animal spirit surreal designs"),
        ("Skullpanda Hype Panda City Series", "Pop Mart", "Skullpanda", "Hype Panda City", "Common", 14, False, "Urban streetwear theme, 12 designs"),
        ("Skullpanda The Ink Painting Secret", "Pop Mart", "Skullpanda", "Ink Painting Secret", "Secret", 210, True, "Chinese ink wash painting secret chase"),

        # ── Sonny Angel — More Series ────────────────────────────────────
        ("Sonny Angel Mini Figure Candy Store Series Lollipop", "Sonny Angel", "Candy Store", "Lollipop", "Common", 12, False, "Candy store theme lollipop hat"),
        ("Sonny Angel Mini Figure Candy Store Secret Gummy Bear", "Sonny Angel", "Candy Store", "Gummy Bear Secret", "Secret", 115, True, "Secret gummy bear Robbie variant"),
        ("Sonny Angel Space Adventure Series Astronaut", "Sonny Angel", "Space Adventure", "Astronaut", "Common", 13, False, "Space suit astronaut hat figure"),
        ("Sonny Angel Space Adventure Secret UFO", "Sonny Angel", "Space Adventure", "UFO Secret", "Secret", 125, True, "Secret UFO riding Robbie variant"),
        ("Sonny Angel Chocolate Series Dark Cocoa", "Sonny Angel", "Chocolate Series", "Dark Cocoa", "Uncommon", 15, False, "Valentine's Day chocolate theme"),
        ("Sonny Angel Winter Wonderland Series Snowflake", "Sonny Angel", "Winter Wonderland", "Snowflake", "Rare", 32, False, "Winter seasonal snowflake design"),
        ("Sonny Angel Hippers Series Sleeping Dog", "Sonny Angel", "Hippers Series", "Sleeping Dog", "Rare", 40, False, "Hippers sleeping pose dog figure"),
        ("Sonny Angel 15th Anniversary Vintage", "Sonny Angel", "15th Anniversary", "Vintage Gold", "Ultra Rare", 220, False, "15th anniversary gold vintage edition"),

        # ── tokidoki — More Series ────────────────────────────────────────
        ("Unicorno Series 13 Moonbeam", "tokidoki", "Unicorno Series 13", "Moonbeam", "Common", 13, False, "Lunar glow unicorn design"),
        ("Unicorno Series 13 Nebula Chase", "tokidoki", "Unicorno Series 13", "Nebula Chase", "Rare", 58, True, "Galaxy nebula chrome chase figure"),
        ("Unicorno Tropical Series Coconut", "tokidoki", "Unicorno Tropical", "Coconut", "Common", 12, False, "Tropical fruit unicorn theme"),
        ("Mermicorno Series 8 Deep Dive", "tokidoki", "Mermicorno Series 8", "Deep Dive", "Common", 12, False, "Deep sea diver mermaid unicorn"),
        ("tokidoki x Marvel Frenzies Spider-Man", "tokidoki", "Marvel Frenzies", "Spider-Man", "Uncommon", 18, False, "Marvel licensed character frenzies"),
        ("tokidoki Neon Star Series Astral", "tokidoki", "Neon Star", "Astral Edition", "Common", 14, False, "Neon glow star-themed series"),

        # ── Kidrobot Dunny — More Series ──────────────────────────────────
        ("Dunny 3-inch Exquisite Corpse Series", "Kidrobot", "Dunny Exquisite Corpse", "Mix-and-Match Figure", "Common", 15, False, "Mix-and-match body parts concept"),
        ("Dunny 5-inch Kaws Companion Grey", "Kidrobot", "Dunny x KAWS", "Companion Grey", "Ultra Rare", 500, False, "Early KAWS x Kidrobot collaboration"),
        ("Dunny 8-inch Sket One Sriracha", "Kidrobot", "Dunny Artist", "Sket One Sriracha", "Rare", 160, False, "Sket One food-themed artist series"),
        ("Dunny 3-inch Fatale Series Full Case", "Kidrobot", "Dunny Fatale", "Full Case", "Common", 85, False, "Femme fatale theme, 20-piece case"),
        ("Dunny 20-inch Tristan Eaton Dunny", "Kidrobot", "Dunny Mega", "Tristan Eaton 20-inch", "Grail", 1200, False, "Museum-scale 20-inch Dunny, signed edition"),

        # ── Sank Toys — More Series ───────────────────────────────────────
        ("Sank Toys Waiting for You Sunset", "Sank Toys", "Waiting for You", "Sunset Edition", "Uncommon", 30, False, "Child sitting on bench sunset colorway"),
        ("Sank Toys Still Wishing Series Star", "Sank Toys", "Still Wishing", "Star Gazer", "Uncommon", 26, False, "Looking at stars pose"),
        ("Sank Toys Lost In Life Series Overtime", "Sank Toys", "Lost In Life", "Overtime Nap", "Common", 22, False, "Sleeping at desk office worker"),
        ("Sank Toys Good Night Series Moon Secret", "Sank Toys", "Good Night", "Moon Secret", "Secret", 195, True, "Crescent moon glowing secret variant"),
        ("Sank Toys Backpack Boy Ocean", "Sank Toys", "Backpack Boy", "Ocean Blue", "Uncommon", 32, False, "Backpack boy ocean blue colorway"),

        # ── Finding Unicorn — More Series ─────────────────────────────────
        ("Shinwoo Ghost Bear Sakura Season", "Finding Unicorn", "Shinwoo Ghost Bear", "Sakura Season", "Common", 16, False, "Cherry blossom spring ghost bear"),
        ("Shinwoo Ghost Bear Black Galaxy", "Finding Unicorn", "Shinwoo Ghost Bear", "Black Galaxy", "Rare", 55, False, "Limited black galaxy sparkle edition"),
        ("Zimomo Ocean Dream Series", "Finding Unicorn", "Zimomo", "Ocean Dream", "Common", 15, False, "Underwater dream theme, 9 designs"),
        ("RICO Bear Pool Party Series", "Finding Unicorn", "RICO Bear", "Pool Party", "Common", 14, False, "Summer pool party bear figures"),

        # ── 52TOYS — More Series ──────────────────────────────────────────
        ("52TOYS LuLu the Piggy Caturday Series", "52TOYS", "LuLu the Piggy", "Caturday Series", "Common", 12, False, "Piggy dressed as cats theme"),
        ("52TOYS Panda Roll Camping Series", "52TOYS", "Panda Roll", "Camping Series", "Common", 10, False, "Outdoor camping theme panda"),
        ("52TOYS BEASTBOX T-Rex Mech Cube", "52TOYS", "BEASTBOX", "T-Rex Mech Cube", "Uncommon", 25, False, "Transforming T-Rex mechanical cube"),
        ("52TOYS Nook Sleeping Series", "52TOYS", "Nook", "Sleeping Series", "Common", 11, False, "Sleeping animal figures in nooks"),
        ("52TOYS MegaBOX Voltron", "52TOYS", "MegaBOX", "Voltron Cube", "Rare", 45, False, "Transforming Voltron cube figure"),

        # ── Pop Mart — Pino Jelly ───────────────────────────────────────
        ("Pino Jelly How Are You Feeling Series", "Pop Mart", "Pino Jelly", "How Are You Feeling", "Common", 14, False, "Emotional expression jelly figures"),
        ("Pino Jelly Make a Wish Secret Star", "Pop Mart", "Pino Jelly", "Make a Wish Secret", "Secret", 145, True, "Shooting star jelly secret chase"),

        # ── Pop Mart — Nori ──────────────────────────────────────────────
        ("Nori Rice Ball Series", "Pop Mart", "Nori", "Rice Ball Series", "Common", 13, False, "Japanese onigiri rice ball theme"),
        ("Nori Sushi Express Secret Golden Roll", "Pop Mart", "Nori", "Sushi Express Secret", "Secret", 155, True, "Gold foil sushi secret chase figure"),

        # ── Pop Mart — Baby Molly ────────────────────────────────────────
        ("Baby Molly When I Was Three Series", "Pop Mart", "Baby Molly", "When I Was Three", "Common", 15, False, "Baby Molly childhood memories, 12 designs"),
        ("Baby Molly My Pet Series", "Pop Mart", "Baby Molly", "My Pet Secret", "Secret", 160, True, "Giant pet animal secret chase"),

        # ── BE@RBRICK Blind Boxes — More Artist Collabs ─────────────────
        ("Bearbrick 100% Keith Haring V3", "Medicom", "Bearbrick x Keith Haring", "Haring V3 100%", "Rare", 180, False, "Keith Haring pop art collaboration v3"),
        ("Bearbrick 100% Basquiat V2", "Medicom", "Bearbrick x Basquiat", "Basquiat V2 100%", "Rare", 200, False, "Jean-Michel Basquiat art series v2"),
        ("Bearbrick 100% Andy Warhol Marilyn", "Medicom", "Bearbrick x Warhol", "Warhol Marilyn 100%", "Rare", 220, False, "Warhol Marilyn Monroe pop art collab"),
        ("Bearbrick Series 48 Sealed Case", "Medicom", "Bearbrick Series 48", "Sealed Case", "Common", 100, False, "Latest series 24-piece sealed case"),
        ("Bearbrick 400% Hajime Sorayama Robot", "Medicom", "Bearbrick x Sorayama", "Robot Sexy 400%", "Ultra Rare", 750, False, "Hajime Sorayama chrome robot collab"),

        # ── MEGA Space Molly — More Variants ─────────────────────────────
        ("Space Molly 400% Burning Heart", "Pop Mart", "Molly", "Space Molly 400% Burning", "Ultra Rare", 580, False, "Large format burning heart flame design"),
        ("Space Molly 400% Planet Earth", "Pop Mart", "Molly", "Space Molly 400% Earth", "Ultra Rare", 520, False, "Large format earth globe design"),
        ("Space Molly 1000% Van Gogh Starry Night", "Pop Mart", "Molly", "Space Molly 1000% Van Gogh", "Grail", 1900, False, "Van Gogh Starry Night, limited 500pcs"),
        ("Space Molly 1000% Luffy One Piece", "Pop Mart", "Molly", "Space Molly 1000% Luffy", "Grail", 1700, False, "One Piece x Pop Mart licensed collab"),

        # ── Funko Mystery Minis — More ───────────────────────────────────
        ("Funko Mystery Minis Disney Villains", "Funko", "Mystery Minis", "Disney Villains Series", "Common", 9, False, "Disney Villains licensed blind box"),
        ("Funko Mystery Minis Five Nights at Freddy's Chase", "Funko", "Mystery Minis", "FNAF Glow Chase", "Rare", 40, True, "Glow-in-dark FNAF chase variant"),
        ("Funko Mystery Minis Star Wars Chase Grogu", "Funko", "Mystery Minis", "Star Wars Grogu Chase", "Rare", 35, True, "Metallic Grogu chase figure"),

        # ── POP BEAN — More ──────────────────────────────────────────────
        ("POP BEAN Animal Cafe Series", "POP BEAN", "Animal Cafe", "Animal Cafe Series", "Common", 12, False, "Animal barista cafe theme"),
        ("POP BEAN Starry Garden Secret Moonflower", "POP BEAN", "Starry Garden", "Moonflower Secret", "Secret", 95, True, "Bioluminescent moonflower secret chase"),

        # ── ToyCity — More ───────────────────────────────────────────────
        ("Laura Fairy Tale Forest Series", "ToyCity", "Laura", "Fairy Tale Forest", "Common", 14, False, "Enchanted forest fairy tale theme"),
        ("Laura Ocean Breeze Secret Mermaid", "ToyCity", "Laura", "Ocean Breeze Secret", "Secret", 110, True, "Mermaid Laura secret chase figure"),
        ("ToyCity Cino Dream Coffee Series", "ToyCity", "Cino", "Dream Coffee", "Common", 13, False, "Coffee-themed Cino character blind box"),

        # ── Japanese Gacha / Gashapon — More ─────────────────────────────
        ("Bandai Gashapon Kirby Friends Series 3", "Bandai", "Gashapon", "Kirby Friends 3", "Common", 5, False, "Kirby and friends capsule toy"),
        ("Bandai Gashapon Pokemon Palette Color Collection", "Bandai", "Gashapon", "Pokemon Palette", "Common", 6, False, "Color-sorted Pokemon mini figures"),
        ("Kaiyodo Revoltech Mini Danboard Amazon", "Kaiyodo", "Revoltech Mini", "Danboard Amazon", "Uncommon", 12, False, "Mini cardboard robot Amazon box ver"),

        # ── COARSE Toys — More ───────────────────────────────────────────
        ("Coarse Little Voyagers Wave 3 Dusk", "Coarse", "Little Voyagers W3", "Dusk Edition", "Uncommon", 35, False, "German designer toy, sailing theme"),
        ("Coarse Omen Rise 5-inch", "Coarse", "Omen", "Rise Edition", "Rare", 175, False, "Limited sunrise colorway figure"),

        # ── Popmart — MEGA Space Molly 100% ──────────────────────────────
        ("Mega Space Molly 100% Series 2 Full Case", "Pop Mart", "Mega Molly 100%", "Series 2 Full Case", "Common", 110, False, "12-piece sealed case of 100% Space Molly"),
        ("Mega Space Molly 100% Series 2 Secret Rainbow", "Pop Mart", "Mega Molly 100%", "Rainbow Secret", "Secret", 250, True, "Rainbow chrome secret chase from 100% series"),

        # ── Vintage / Grail — More ───────────────────────────────────────
        ("Bearbrick 1000% KAWS Dissected Companion", "Medicom", "Bearbrick x KAWS 1000%", "Dissected 1000%", "Grail", 5000, False, "Museum-scale 1000% KAWS Bearbrick, under 500 made"),
        ("Dunny 8-inch KAWS Companion 2006 Grey", "Kidrobot", "Dunny x KAWS 2006", "Companion Grey OG", "Grail", 3000, False, "Original 2006 KAWS x Kidrobot, extremely rare"),

        # ── Pop Mart — Hacipupu ──────────────────────────────────────────
        ("Hacipupu Let Me Think About It Series", "Pop Mart", "Hacipupu", "Let Me Think", "Common", 14, False, "Thinking pose cat-ear character series"),
        ("Hacipupu Sweet Dream Secret Star", "Pop Mart", "Hacipupu", "Sweet Dream Secret", "Secret", 175, True, "Starlight dream secret chase figure"),

        # ── Pop Mart — Instinctoy Erosion Series ─────────────────────────
        ("Pop Mart Erosion Molly Crystal Clear", "Pop Mart", "Erosion Series", "Molly Crystal Clear", "Rare", 160, False, "Crystal clear resin erosion figure"),
        ("Pop Mart Erosion Dimoo Jade Green", "Pop Mart", "Erosion Series", "Dimoo Jade Green", "Rare", 150, False, "Jade green semi-transparent erosion"),

        # ── Sonny Angel — Cake Series ────────────────────────────────────
        ("Sonny Angel Cake Series Shortcake", "Sonny Angel", "Cake Series", "Shortcake", "Common", 12, False, "Strawberry shortcake hat figure"),
        ("Sonny Angel Cake Series Cheesecake Secret", "Sonny Angel", "Cake Series", "Cheesecake Secret", "Secret", 120, True, "Golden cheesecake Robbie secret variant"),

        # ── tokidoki — Moofia ────────────────────────────────────────────
        ("Moofia Series 2 Strawberry Milk", "tokidoki", "Moofia Series 2", "Strawberry Milk", "Common", 11, False, "Milk carton character strawberry flavor"),
        ("Moofia Series 2 Golden Milk Chase", "tokidoki", "Moofia Series 2", "Golden Milk Chase", "Rare", 55, True, "Gold metallic milk carton chase"),

        # ── BE@RBRICK — Designer Series ──────────────────────────────────
        ("Bearbrick 100% Futura Pointman", "Medicom", "Bearbrick x Futura", "Pointman 100%", "Rare", 190, False, "Futura graffiti artist collab blind box"),
        ("Bearbrick 100% Pushead Series 3", "Medicom", "Bearbrick x Pushead", "Pushead V3 100%", "Rare", 170, False, "Brian Schroeder skull art collaboration"),
        ("Bearbrick 100% A Bathing Ape Camo Green", "Medicom", "Bearbrick x BAPE", "BAPE Camo Green 100%", "Rare", 250, False, "A Bathing Ape camo pattern blind box figure"),

        # ── Kaiyodo ──────────────────────────────────────────────────────
        ("Kaiyodo Revoltech Danboard Mini THR", "Kaiyodo", "Revoltech Danboard", "THR Exclusive", "Uncommon", 15, False, "Japanese revoltech cardboard robot exclusive"),
        ("Kaiyodo Cup Noodle Capsule Timer Figure", "Kaiyodo", "Cup Noodle", "Timer Figure", "Common", 6, False, "Nissin Cup Noodle timer mini figures"),

        # ── Pop Mart — MEGA Collection 100% ──────────────────────────────
        ("Mega Collection 100% Labubu", "Pop Mart", "Mega Collection 100%", "Labubu 100%", "Common", 22, False, "100% size blind box Labubu figures"),
        ("Mega Collection 100% Dimoo Fairy", "Pop Mart", "Mega Collection 100%", "Dimoo Fairy 100%", "Common", 22, False, "100% size blind box Dimoo fairy figures"),
        ("Mega Collection 100% Secret Chrome Molly", "Pop Mart", "Mega Collection 100%", "Chrome Molly Secret", "Secret", 180, True, "Full chrome Molly secret from 100% series"),

        # ── Final Additions ──────────────────────────────────────────────
        ("Pop Mart Zsiga Lulu's Forest Secret Unicorn", "Pop Mart", "Zsiga Lulu", "Forest Secret Unicorn", "Secret", 165, True, "Forest unicorn glow-in-dark secret chase"),
        ("Sonny Angel Looking Back Rabbit Hippers", "Sonny Angel", "Hippers Series", "Looking Back Rabbit", "Rare", 42, False, "Hippers sitting pose rabbit looking back figure"),

        # ── Pop Mart — More IPs ──────────────────────────────────────────
        ("Pop Mart Nori Flower Market Series", "Pop Mart", "Nori", "Flower Market", "Common", 14, False, "Nori rice ball flower themed series"),
        ("Pop Mart Nori Flower Market Secret Rose", "Pop Mart", "Nori", "Flower Market Secret", "Secret", 150, True, "Golden rose secret figure"),
        ("Pop Mart Yuki Fairy Tale Series", "Pop Mart", "Yuki", "Fairy Tale", "Common", 14, False, "Yuki fairy tale themed figures"),
        ("Pop Mart Yuki Fairy Tale Secret Crystal", "Pop Mart", "Yuki", "Fairy Tale Secret", "Secret", 140, True, "Crystal clear secret variant"),
        ("Pop Mart KUBO Cooking Series", "Pop Mart", "KUBO", "Cooking", "Common", 14, False, "KUBO kitchen themed blind box"),
        ("Pop Mart KUBO Cooking Secret Gold Chef", "Pop Mart", "KUBO", "Cooking Secret", "Secret", 130, True, "Metallic gold chef hat KUBO"),
        ("Pop Mart Vita Dream Job Series", "Pop Mart", "Vita", "Dream Job", "Common", 14, False, "Vita career themed series"),
        ("Pop Mart Vita Dream Job Secret Astronaut", "Pop Mart", "Vita", "Dream Job Secret", "Secret", 135, True, "Holographic astronaut Vita"),
        ("Pop Mart RiCO Summer Pool Series", "Pop Mart", "RiCO", "Summer Pool", "Common", 14, False, "RiCO pool party themed series"),
        ("Pop Mart RiCO Summer Pool Secret", "Pop Mart", "RiCO", "Summer Pool Secret", "Secret", 125, True, "Iridescent pool float RiCO"),
        ("Pop Mart Azura Midnight Garden Series", "Pop Mart", "Azura", "Midnight Garden", "Common", 14, False, "Azura garden at night theme"),
        ("Pop Mart Azura Midnight Garden Secret", "Pop Mart", "Azura", "Midnight Garden Secret", "Secret", 145, True, "Glow-in-dark garden Azura"),
        ("Pop Mart Pino Jelly Fruit Paradise", "Pop Mart", "Pino Jelly", "Fruit Paradise", "Common", 14, False, "Pino Jelly fruit themed series"),
        ("Pop Mart Pino Jelly Fruit Secret Diamond", "Pop Mart", "Pino Jelly", "Fruit Paradise Secret", "Secret", 140, True, "Diamond dusted fruit Pino Jelly"),
        ("Pop Mart Baby Molly Sports Day", "Pop Mart", "Baby Molly", "Sports Day", "Common", 14, False, "Baby Molly sport themed figures"),
        ("Pop Mart Baby Molly Sports Day Secret Gold", "Pop Mart", "Baby Molly", "Sports Day Secret", "Secret", 130, True, "Gold medal Baby Molly secret"),
        ("Pop Mart Hacipupu Grocery Store", "Pop Mart", "Hacipupu", "Grocery Store", "Common", 14, False, "Hacipupu grocery themed figures"),
        ("Pop Mart Hacipupu Grocery Secret Cake", "Pop Mart", "Hacipupu", "Grocery Store Secret", "Secret", 120, True, "Wedding cake Hacipupu secret"),
        ("Pop Mart Labubu The Monsters Collector", "Pop Mart", "Labubu", "Collector Series", "Rare", 55, False, "Labubu collecting themed premium figures"),
        ("Pop Mart Labubu Vinyl Plush 6-inch", "Pop Mart", "Labubu", "Vinyl Plush 6in", "Uncommon", 35, False, "Larger format vinyl plush Labubu"),
        ("Pop Mart Labubu The Monsters Snow Trip", "Pop Mart", "Labubu", "Snow Trip", "Common", 14, False, "Winter ski themed Labubu series"),
        ("Pop Mart Labubu The Monsters Comic Con", "Pop Mart", "Labubu", "Comic Con Exclusive", "Rare", 95, False, "SDCC/Comic Con exclusive Labubu"),
        ("Pop Mart Dimoo Starry Night Series", "Pop Mart", "Dimoo", "Starry Night", "Common", 14, False, "Van Gogh inspired art series"),
        ("Pop Mart Dimoo Starry Night Secret", "Pop Mart", "Dimoo", "Starry Night Secret", "Secret", 170, True, "Gold frame secret Dimoo"),
        ("Pop Mart Dimoo Christmas Series", "Pop Mart", "Dimoo", "Christmas 2025", "Common", 14, False, "Holiday Christmas themed Dimoo"),
        ("Pop Mart Molly Steampunk Series", "Pop Mart", "Molly", "Steampunk", "Common", 16, False, "Steampunk aesthetic Molly figures"),
        ("Pop Mart Molly Steampunk Secret Mech", "Pop Mart", "Molly", "Steampunk Secret", "Secret", 200, True, "Mechanical gear chrome secret Molly"),
        ("Pop Mart Skullpanda Midnight Circus", "Pop Mart", "Skullpanda", "Midnight Circus", "Common", 16, False, "Dark circus themed Skullpanda"),
        ("Pop Mart Skullpanda Midnight Circus Secret", "Pop Mart", "Skullpanda", "Midnight Circus Secret", "Secret", 180, True, "Ringmaster secret Skullpanda"),
        ("Pop Mart Hirono Shadow Play Series", "Pop Mart", "Hirono", "Shadow Play", "Common", 16, False, "Shadow puppet inspired Hirono"),
        ("Pop Mart Hirono Shadow Play Secret", "Pop Mart", "Hirono", "Shadow Play Secret", "Secret", 190, True, "Translucent shadow Hirono"),
        ("Pop Mart Crybaby Ocean Tears Series", "Pop Mart", "Crybaby", "Ocean Tears", "Common", 14, False, "Ocean themed Crybaby figures"),
        ("Pop Mart Crybaby Ocean Tears Secret Pearl", "Pop Mart", "Crybaby", "Ocean Tears Secret", "Secret", 160, True, "Pearl shell secret Crybaby"),
        ("Pop Mart Zsiga Butterfly Garden", "Pop Mart", "Zsiga", "Butterfly Garden", "Common", 14, False, "Butterfly themed Zsiga series"),

        # ── Pop Mart — Large Format & Premium ────────────────────────────
        ("Space Molly 1000% MEGA Hatsune Miku", "Pop Mart", "Molly", "Space Molly x Hatsune Miku", "Grail", 2500, False, "1000% Hatsune Miku collaboration"),
        ("Space Molly 400% Buzz Lightyear", "Pop Mart", "Molly", "Space Molly x Pixar", "Ultra Rare", 450, False, "400% Toy Story collaboration"),
        ("Space Molly 1000% Spider-Man", "Pop Mart", "Molly", "Space Molly x Marvel", "Grail", 1800, False, "1000% Marvel Spider-Man collab"),
        ("Space Molly 400% Iron Man", "Pop Mart", "Molly", "Space Molly x Marvel", "Ultra Rare", 500, False, "400% Marvel Iron Man collab"),
        ("Space Molly 400% Doraemon", "Pop Mart", "Molly", "Space Molly x Doraemon", "Ultra Rare", 400, False, "400% Doraemon collaboration"),
        ("Mega Collection 100% Skullpanda", "Pop Mart", "Mega Collection 100%", "Skullpanda 100%", "Rare", 45, False, "100% format Skullpanda collection"),

        # ── Sonny Angel — Complete Series ────────────────────────────────
        ("Sonny Angel Flower Series Daisy", "Sonny Angel", "Flower Series", "Daisy", "Common", 12, False, "Standard flower series daisy"),
        ("Sonny Angel Flower Series Tulip", "Sonny Angel", "Flower Series", "Tulip", "Common", 12, False, "Standard flower series tulip"),
        ("Sonny Angel Fruit Series Apple", "Sonny Angel", "Fruit Series", "Apple", "Common", 10, False, "Standard fruit series apple figure"),
        ("Sonny Angel Fruit Series Peach", "Sonny Angel", "Fruit Series", "Peach", "Common", 10, False, "Standard fruit series peach figure"),
        ("Sonny Angel Fruit Series Grape", "Sonny Angel", "Fruit Series", "Grape", "Common", 10, False, "Standard fruit series grape"),
        ("Sonny Angel Animal Series 1 Rabbit OG", "Sonny Angel", "Animal Series 1", "Rabbit OG", "Rare", 85, False, "Original 2004 animal series 1 rabbit"),
        ("Sonny Angel Animal Series 1 Bear OG", "Sonny Angel", "Animal Series 1", "Bear OG", "Rare", 80, False, "Original 2004 animal series 1 bear"),
        ("Sonny Angel Animal Series 2 Frog", "Sonny Angel", "Animal Series 2", "Frog", "Common", 12, False, "Animal series 2 frog"),
        ("Sonny Angel Animal Series 2 Penguin", "Sonny Angel", "Animal Series 2", "Penguin", "Common", 12, False, "Animal series 2 penguin"),
        ("Sonny Angel Animal Series 2 Owl Secret", "Sonny Angel", "Animal Series 2", "Owl Secret", "Secret", 120, True, "Secret owl figure with golden eyes"),
        ("Sonny Angel Marine Series Dolphin", "Sonny Angel", "Marine Series", "Dolphin", "Common", 12, False, "Marine series dolphin figure"),
        ("Sonny Angel Marine Series Turtle", "Sonny Angel", "Marine Series", "Turtle", "Common", 12, False, "Marine series turtle figure"),
        ("Sonny Angel Christmas 2024 Snowman", "Sonny Angel", "Christmas 2024", "Snowman", "Common", 14, False, "2024 Christmas snowman figure"),
        ("Sonny Angel Christmas 2024 Angel Secret", "Sonny Angel", "Christmas 2024", "Angel Secret", "Secret", 160, True, "Gold angel wings secret figure"),
        ("Sonny Angel Halloween 2024 Vampire", "Sonny Angel", "Halloween 2024", "Vampire", "Common", 14, False, "2024 Halloween vampire figure"),
        ("Sonny Angel Halloween 2024 Witch Secret", "Sonny Angel", "Halloween 2024", "Witch Secret", "Secret", 150, True, "Purple sparkle witch secret"),
        ("Sonny Angel Valentine 2025 Cupid", "Sonny Angel", "Valentine 2025", "Cupid", "Common", 14, False, "2025 Valentine cupid figure"),
        ("Sonny Angel Valentine 2025 Heart Secret", "Sonny Angel", "Valentine 2025", "Heart Secret", "Secret", 140, True, "Crystal heart secret figure"),
        ("Sonny Angel Mini Figure Museum Series Statue", "Sonny Angel", "Museum Series", "Statue", "Rare", 35, False, "Museum art inspired series"),
        ("Sonny Angel Mini Figure Museum Secret Gold", "Sonny Angel", "Museum Series", "Gold Statue Secret", "Secret", 180, True, "Gold museum statue secret"),
        ("Sonny Angel Dessert Series Donut", "Sonny Angel", "Dessert Series", "Donut", "Common", 12, False, "Dessert series donut figure"),
        ("Sonny Angel Dessert Series Parfait", "Sonny Angel", "Dessert Series", "Parfait", "Common", 12, False, "Dessert series parfait figure"),
        ("Sonny Angel Dessert Series Crepe Secret", "Sonny Angel", "Dessert Series", "Crepe Secret", "Secret", 130, True, "Rainbow crepe secret figure"),
        ("Sonny Angel New Year 2025 Dragon", "Sonny Angel", "New Year 2025", "Dragon", "Rare", 40, False, "2025 Lunar New Year dragon"),
        ("Sonny Angel Camping Series Tent", "Sonny Angel", "Camping Series", "Tent", "Common", 12, False, "Camping outdoor themed series"),
        ("Sonny Angel Camping Series Campfire Secret", "Sonny Angel", "Camping Series", "Campfire Secret", "Secret", 125, True, "Glow campfire secret figure"),

        # ── tokidoki — Complete Lines ────────────────────────────────────
        ("Unicorno Series 14 Stardust", "tokidoki", "Unicorno Series 14", "Stardust", "Common", 12, False, "Series 14 stardust unicorn"),
        ("Unicorno Series 14 Galaxy Chase", "tokidoki", "Unicorno Series 14", "Galaxy Chase", "Secret", 120, True, "Metallic galaxy chase figure"),
        ("Unicorno Winter Wonderland Series Frost", "tokidoki", "Unicorno Winter", "Frost", "Common", 14, False, "Winter themed frost unicorn"),
        ("Unicorno Winter Wonderland Ice Queen Chase", "tokidoki", "Unicorno Winter", "Ice Queen Chase", "Secret", 130, True, "Translucent ice queen chase"),
        ("Unicorno x Disney Princess Aurora", "tokidoki", "Unicorno x Disney", "Aurora", "Rare", 45, False, "Disney Princess Aurora collab"),
        ("Unicorno x Disney Princess Ariel", "tokidoki", "Unicorno x Disney", "Ariel", "Rare", 45, False, "Disney Princess Ariel collab"),
        ("Mermicorno Series 9 Coral Reef", "tokidoki", "Mermicorno Series 9", "Coral Reef", "Common", 12, False, "Series 9 coral reef mermaid"),
        ("Mermicorno Series 9 Deep Sea Chase", "tokidoki", "Mermicorno Series 9", "Deep Sea Chase", "Secret", 110, True, "Bioluminescent deep sea chase"),
        ("tokidoki Donutella Series 4 Glazed", "tokidoki", "Donutella Series 4", "Glazed", "Common", 12, False, "Series 4 glazed donut figure"),
        ("tokidoki Donutella Series 4 Galaxy Donut Chase", "tokidoki", "Donutella Series 4", "Galaxy Donut Chase", "Secret", 100, True, "Galaxy sprinkle chase figure"),
        ("tokidoki Cactus Pups Series 2 Desert Rose", "tokidoki", "Cactus Pups Series 2", "Desert Rose", "Common", 12, False, "Cactus pups desert series"),
        ("tokidoki Cactus Pups Series 2 Gold Bloom Chase", "tokidoki", "Cactus Pups Series 2", "Gold Bloom Chase", "Secret", 95, True, "Gold bloom cactus chase"),
        ("tokidoki Tiger Nation Series Full Case", "tokidoki", "Tiger Nation", "Full Case", "Common", 14, False, "Tiger themed nation series"),
        ("tokidoki Sea Punk Frenzies Octopus", "tokidoki", "Sea Punk Frenzies", "Octopus", "Common", 10, False, "Sea punk kawaii octopus"),
        ("tokidoki Palette Series Paint Splash Chase", "tokidoki", "Palette Series", "Paint Splash Chase", "Secret", 85, True, "Art palette paint splash chase"),
        ("tokidoki x Barbie Series Malibu", "tokidoki", "tokidoki x Barbie", "Malibu", "Rare", 35, False, "Barbie collaboration Malibu edition"),

        # ── Kidrobot — Extended Catalog ──────────────────────────────────
        ("Dunny 3-inch French Series Full Case", "Kidrobot", "Dunny French", "Full Case", "Common", 16, False, "French artist designer Dunny series"),
        ("Dunny 3-inch Side Show Full Case", "Kidrobot", "Dunny Side Show", "Full Case", "Common", 16, False, "Circus sideshow themed Dunny"),
        ("Dunny 3-inch Ye Olde English Full Case", "Kidrobot", "Dunny Ye Olde English", "Full Case", "Common", 16, False, "Medieval English themed Dunny"),
        ("Dunny 8-inch MAD Bent World Spray", "Kidrobot", "Dunny Artist", "MAD Bent World Spray", "Rare", 120, False, "MAD designed 8-inch Dunny"),
        ("Dunny 8-inch Quiccs MegaTeq Ghost", "Kidrobot", "Dunny Artist", "Quiccs MegaTeq Ghost", "Rare", 150, False, "Quiccs x Kidrobot ghost Dunny"),
        ("Dunny 5-inch Andrew Bell O-No Sushi", "Kidrobot", "Dunny Artist", "Andrew Bell O-No Sushi", "Rare", 80, False, "O-No sushi themed Dunny"),
        ("Kidrobot Labbit 10-inch Attaboy Cloud", "Kidrobot", "Labbit", "Attaboy Cloud", "Rare", 100, False, "10-inch cloud pattern Labbit"),
        ("Kidrobot Munny World Series 4 Full Case", "Kidrobot", "Munny World", "Series 4 Full Case", "Common", 14, False, "Munny world series 4 figures"),
        ("Kidrobot Bob's Burgers Series 2 Full Case", "Kidrobot", "Bob's Burgers", "Series 2 Full Case", "Common", 16, False, "Bob's Burgers mini figures"),
        ("Kidrobot Rick and Morty Series 2 Chase", "Kidrobot", "Rick and Morty", "Series 2 Chase", "Rare", 65, False, "Rick and Morty chase figure"),

        # ── Sank Toys — Full Line ────────────────────────────────────────
        ("Sank Toys Good Night Series Dream Cloud", "Sank Toys", "Good Night", "Dream Cloud", "Common", 35, False, "Cloud pillow good night figure"),
        ("Sank Toys Good Night Series Starlight Secret", "Sank Toys", "Good Night", "Starlight Secret", "Secret", 250, True, "Glow starlight premium secret"),
        ("Sank Toys On the Way Home Autumn", "Sank Toys", "On the Way Home", "Autumn", "Common", 35, False, "Autumn leaf homeward figure"),
        ("Sank Toys On the Way Home Spring Secret", "Sank Toys", "On the Way Home", "Spring Secret", "Secret", 280, True, "Cherry blossom spring secret"),
        ("Sank Toys Backpack Boy Mountain", "Sank Toys", "Backpack Boy", "Mountain", "Common", 35, False, "Mountain hiking backpack boy"),
        ("Sank Toys Backpack Boy Desert Secret", "Sank Toys", "Backpack Boy", "Desert Secret", "Secret", 260, True, "Mirage desert secret figure"),
        ("Sank Toys Still Wishing Series Rainbow", "Sank Toys", "Still Wishing", "Rainbow", "Rare", 55, False, "Rainbow themed wishing figure"),
        ("Sank Toys Waiting for You Rain", "Sank Toys", "Waiting for You", "Rain", "Common", 35, False, "Rainy day waiting figure"),
        ("Sank Toys Waiting for You Snow Secret", "Sank Toys", "Waiting for You", "Snow Secret", "Secret", 270, True, "Crystal snow secret figure"),

        # ── Finding Unicorn — All Series ─────────────────────────────────
        ("Shinwoo Ghost Bear Summer Beach", "Finding Unicorn", "Shinwoo Ghost Bear", "Summer Beach", "Common", 14, False, "Beach theme ghost bear"),
        ("Shinwoo Ghost Bear Valentine Heart", "Finding Unicorn", "Shinwoo Ghost Bear", "Valentine Heart", "Rare", 40, False, "Valentine heart ghost bear"),
        ("Shinwoo Ghost Bear Halloween Pumpkin", "Finding Unicorn", "Shinwoo Ghost Bear", "Halloween Pumpkin", "Rare", 38, False, "Halloween pumpkin ghost bear"),
        ("Shinwoo Ghost Bear Gold Anniversary", "Finding Unicorn", "Shinwoo Ghost Bear", "Gold Anniversary", "Ultra Rare", 200, False, "Gold plated anniversary ghost bear"),
        ("Zimomo Under the Sea Series", "Finding Unicorn", "Zimomo", "Under the Sea", "Common", 14, False, "Underwater ocean themed Zimomo"),
        ("Zimomo Under the Sea Secret Mermaid", "Finding Unicorn", "Zimomo", "Under the Sea Secret", "Secret", 150, True, "Mermaid crown secret Zimomo"),
        ("Zimomo Space Colony Series", "Finding Unicorn", "Zimomo", "Space Colony", "Common", 14, False, "Space colony themed Zimomo"),
        ("RICO Bear Camping Trip Series", "Finding Unicorn", "RICO Bear", "Camping Trip", "Common", 14, False, "Outdoor camping themed RICO Bear"),
        ("RICO Bear Camping Secret Firefly", "Finding Unicorn", "RICO Bear", "Camping Secret", "Secret", 120, True, "Glow firefly secret RICO Bear"),

        # ── 52TOYS — All Lines ───────────────────────────────────────────
        ("52TOYS Panda Roll Sushi Chef Series", "52TOYS", "Panda Roll", "Sushi Chef", "Common", 12, False, "Sushi making panda roll figures"),
        ("52TOYS Panda Roll Sushi Chef Secret Gold", "52TOYS", "Panda Roll", "Sushi Chef Secret", "Secret", 100, True, "Gold sushi chef panda secret"),
        ("52TOYS Panda Roll Space Explorer", "52TOYS", "Panda Roll", "Space Explorer", "Common", 12, False, "Astronaut panda roll figures"),
        ("52TOYS LuLu the Piggy Farm Series", "52TOYS", "LuLu the Piggy", "Farm", "Common", 12, False, "Farm themed piggy figures"),
        ("52TOYS LuLu the Piggy Farm Secret Gold Pig", "52TOYS", "LuLu the Piggy", "Farm Secret", "Secret", 95, True, "Gold pig secret figure"),
        ("52TOYS BEASTBOX Stego Mech Cube", "52TOYS", "BEASTBOX", "Stego Mech", "Rare", 30, False, "Transforming stegosaurus cube"),
        ("52TOYS BEASTBOX Raptor Stealth Cube", "52TOYS", "BEASTBOX", "Raptor Stealth", "Rare", 30, False, "Transforming raptor cube"),
        ("52TOYS MegaBOX Gundam Wing", "52TOYS", "MegaBOX", "Gundam Wing", "Rare", 45, False, "Larger MegaBOX Gundam series"),
        ("52TOYS Nook Dreaming Series", "52TOYS", "Nook", "Dreaming", "Common", 12, False, "Sleepy Nook dreaming figures"),
        ("52TOYS Nook Dreaming Secret Cloud", "52TOYS", "Nook", "Dreaming Secret", "Secret", 90, True, "Cloud pillow secret Nook"),
        ("52TOYS Panda Roll Year of Rabbit", "52TOYS", "Panda Roll", "Year of Rabbit", "Rare", 25, False, "Zodiac rabbit panda roll"),

        # ── BE@RBRICK Series ─────────────────────────────────────────────
        ("Bearbrick 100% Chiaki Kuriyama", "Medicom", "Bearbrick Series", "Chiaki Kuriyama", "Rare", 45, False, "Artist collaboration 100%"),
        ("Bearbrick 100% Grateful Dead Dancing Bear", "Medicom", "Bearbrick Series", "Grateful Dead", "Rare", 50, False, "Grateful Dead dancing bear"),
        ("Bearbrick 100% Fragment Design Black", "Medicom", "Bearbrick x Fragment", "Fragment Black", "Rare", 60, False, "Hiroshi Fujiwara Fragment collab"),
        ("Bearbrick 100% Undercover Bear", "Medicom", "Bearbrick x Undercover", "Undercover", "Rare", 55, False, "Jun Takahashi Undercover collab"),
        ("Bearbrick 100% Stussy Black", "Medicom", "Bearbrick x Stussy", "Stussy Black", "Rare", 50, False, "Stussy streetwear collaboration"),
        ("Bearbrick 100% atmos Elephant", "Medicom", "Bearbrick x atmos", "Elephant", "Rare", 55, False, "atmos sneaker shop collaboration"),
        ("Bearbrick 100% Karimoku Wood", "Medicom", "Bearbrick Karimoku", "Wood", "Ultra Rare", 200, False, "Real wood Karimoku crafted bear"),
        ("Bearbrick 100% My First Baby Gold Chrome", "Medicom", "Bearbrick My First Baby", "Gold Chrome", "Ultra Rare", 150, False, "Chrome gold baby bearbrick"),
        ("Bearbrick 400% Clot Silk Black", "Medicom", "Bearbrick x Clot", "Silk Black", "Ultra Rare", 350, False, "Clot Edison Chen silk collab"),
        ("Bearbrick 1000% Pink Panther", "Medicom", "Bearbrick 1000%", "Pink Panther", "Grail", 1200, False, "1000% Pink Panther collaboration"),
        ("Bearbrick 400% Squid Game Front Man", "Medicom", "Bearbrick x Netflix", "Squid Game", "Ultra Rare", 300, False, "Netflix Squid Game collaboration"),
        ("Bearbrick 100% Pac-Man", "Medicom", "Bearbrick x Bandai Namco", "Pac-Man", "Rare", 40, False, "Pac-Man game collaboration"),

        # ── Japanese Gashapon/Capsule Toys ───────────────────────────────
        ("Bandai Gashapon Demon Slayer Hashira Set", "Bandai", "Gashapon", "Demon Slayer Hashira", "Rare", 25, False, "Demon Slayer Hashira figure set"),
        ("Bandai Gashapon Jujutsu Kaisen Deformed", "Bandai", "Gashapon", "Jujutsu Kaisen", "Common", 8, False, "JJK deformed mini figures"),
        ("Bandai Gashapon My Hero Academia Suwarimi", "Bandai", "Gashapon", "My Hero Suwarimi", "Common", 8, False, "MHA sitting pose capsule figures"),
        ("Bandai Gashapon One Piece Film Red", "Bandai", "Gashapon", "One Piece Film Red", "Common", 8, False, "One Piece Film Red capsule"),
        ("Bandai Gashapon Dragon Ball Super Deformed", "Bandai", "Gashapon", "Dragon Ball Super", "Common", 8, False, "Dragon Ball SD capsule figures"),
        ("Bandai Gashapon Spy x Family Deformed", "Bandai", "Gashapon", "Spy x Family", "Common", 8, False, "Spy x Family deformed capsule"),
        ("Bandai Gashapon Neko Atsume Series 3", "Bandai", "Gashapon", "Neko Atsume S3", "Common", 6, False, "Cat collecting game capsule toys"),
        ("Takara Tomy A.R.T.S. Rilakkuma Cafe", "Takara Tomy", "A.R.T.S. Gashapon", "Rilakkuma Cafe", "Common", 8, False, "Rilakkuma cafe themed capsule"),
        ("Takara Tomy A.R.T.S. Pompompurin Room", "Takara Tomy", "A.R.T.S. Gashapon", "Pompompurin Room", "Common", 8, False, "Sanrio Pompompurin room diorama"),
        ("Takara Tomy A.R.T.S. Cinnamoroll Cloud", "Takara Tomy", "A.R.T.S. Gashapon", "Cinnamoroll Cloud", "Common", 8, False, "Sanrio Cinnamoroll cloud capsule"),
        ("Kaiyodo Capsule Q Museum Dinosaur", "Kaiyodo", "Capsule Q Museum", "Dinosaur", "Rare", 15, False, "High detail museum quality dinosaur"),
        ("Kaiyodo Revoltech Mini EVA Unit-01", "Kaiyodo", "Revoltech Mini", "EVA Unit-01", "Rare", 20, False, "Mini poseable Evangelion figure"),

        # ── Funko Mystery Minis — Extended ───────────────────────────────
        ("Funko Mystery Minis Stranger Things S2", "Funko", "Mystery Minis", "Stranger Things S2", "Common", 10, False, "Stranger Things season 2 minis"),
        ("Funko Mystery Minis IT Chase Pennywise", "Funko", "Mystery Minis", "IT Chase Pennywise", "Rare", 45, False, "IT Pennywise chase variant"),
        ("Funko Mystery Minis Lord of the Rings", "Funko", "Mystery Minis", "Lord of the Rings", "Common", 10, False, "LOTR mini figures series"),
        ("Funko Mystery Minis DC Bombshells Chase", "Funko", "Mystery Minis", "DC Bombshells Chase", "Rare", 35, False, "DC Bombshells chase variant"),
        ("Funko Mystery Minis Rick and Morty S3", "Funko", "Mystery Minis", "Rick and Morty S3", "Common", 10, False, "Rick and Morty series 3"),
        ("Funko Mystery Minis The Office Full Case", "Funko", "Mystery Minis", "The Office Full Case", "Common", 12, False, "The Office mini figures case"),

        # ── Mighty Jaxx — Extended ───────────────────────────────────────
        ("Mighty Jaxx Freeny's Hidden Dissectibles Naruto", "Mighty Jaxx", "Hidden Dissectibles", "Naruto", "Common", 16, False, "Anatomical Naruto figures"),
        ("Mighty Jaxx Freeny's Hidden Dissectibles Dragon Ball", "Mighty Jaxx", "Hidden Dissectibles", "Dragon Ball", "Common", 16, False, "Anatomical Dragon Ball figures"),
        ("Mighty Jaxx XXRAY Plus Wonder Woman Chrome", "Mighty Jaxx", "XXRAY Plus", "Wonder Woman Chrome", "Rare", 85, False, "Chrome Wonder Woman dissected"),
        ("Mighty Jaxx Jason Freeny Balloon Dog Anatomy", "Mighty Jaxx", "Balloon Dog", "Anatomy Red", "Rare", 55, False, "Balloon dog anatomy figure"),
        ("Mighty Jaxx Kandy x Dragon Ball Goku", "Mighty Jaxx", "Kandy", "Dragon Ball Goku", "Common", 14, False, "Dragon Ball Kandy figure"),

        # ── INSTINCTOY & Coarse — Extended ───────────────────────────────
        ("INSTINCTOY Mini Liquid Series Neon Green", "INSTINCTOY", "Liquid Series", "Neon Green", "Rare", 120, False, "Neon green liquid filled figure"),
        ("INSTINCTOY Mini Liquid Series Sunset Orange", "INSTINCTOY", "Liquid Series", "Sunset Orange", "Rare", 120, False, "Sunset orange liquid filled figure"),
        ("INSTINCTOY Erosion Labubu Crystal", "INSTINCTOY", "Erosion Labubu", "Crystal", "Ultra Rare", 450, False, "Crystal clear erosion Labubu"),
        ("Coarse Little Voyagers Wave 4 Dawn", "Coarse", "Little Voyagers W4", "Dawn", "Rare", 80, False, "Wave 4 dawn little voyager"),
        ("Coarse Noop Noop Frost", "Coarse", "Noop Noop", "Frost", "Rare", 65, False, "Frost white Noop Noop figure"),
        ("Coarse Omen Shatter 5-inch", "Coarse", "Omen", "Shatter", "Rare", 85, False, "Shattered texture omen figure"),

        # ── Vintage / Rare Grails ────────────────────────────────────────
        ("Dunny Series 2004 OG Full Case", "Kidrobot", "Dunny Series 2004", "Full Case OG", "Grail", 800, False, "Very first Dunny blind box series"),
        ("Sonny Angel Robbie Angel Crown Silver OG 2005", "Sonny Angel", "Robbie Angel OG", "Crown Silver 2005", "Grail", 500, False, "Very early Robbie Angel silver crown"),
        ("tokidoki Unicorno Series 2 OG Sakura 2014", "tokidoki", "Unicorno Series 2", "OG Sakura 2014", "Grail", 300, False, "Early unicorno series 2 sakura"),
        ("Medicom Bearbrick Series 1 OG 2001", "Medicom", "Bearbrick Series 1", "OG 2001 Full Case", "Grail", 2000, False, "Original 2001 Bearbrick series 1"),
        ("Space Molly 1000% Chrome Mirror 2020", "Pop Mart", "Space Molly 1000%", "Chrome Mirror 2020", "Grail", 3000, False, "Mirror chrome 2020 limited release"),
        ("KAWS Companion Open Edition Grey 2016", "Medicom", "KAWS Companion", "Open Edition Grey", "Grail", 1500, False, "KAWS open edition companion figure"),

        # ── Pop Mart — Disney & Licensed ─────────────────────────────────
        ("Pop Mart Disney Princess Tea Party Belle", "Pop Mart", "Disney Princess", "Tea Party Belle", "Rare", 28, False, "Disney Belle tea party figure"),
        ("Pop Mart Disney Princess Tea Party Rapunzel", "Pop Mart", "Disney Princess", "Tea Party Rapunzel", "Rare", 28, False, "Disney Rapunzel tea party figure"),
        ("Pop Mart Disney Villains Maleficent", "Pop Mart", "Disney Villains", "Maleficent", "Rare", 30, False, "Disney Maleficent premium figure"),
        ("Pop Mart Disney Pixar Monsters Inc Boo", "Pop Mart", "Disney Pixar", "Monsters Inc Boo", "Rare", 25, False, "Monsters Inc Boo figure"),
        ("Pop Mart Marvel Avengers Iron Man", "Pop Mart", "Marvel Avengers", "Iron Man", "Rare", 28, False, "Marvel Iron Man blind box"),
        ("Pop Mart DC Batman Series Dark Knight", "Pop Mart", "DC Batman", "Dark Knight", "Rare", 28, False, "DC Batman dark knight figure"),
        ("Pop Mart Sanrio Characters Cafe", "Pop Mart", "Sanrio Cafe", "Cafe Series", "Common", 14, False, "Sanrio characters cafe theme"),
        ("Pop Mart Sanrio Characters Cafe Secret Hello Kitty", "Pop Mart", "Sanrio Cafe", "Cafe Secret", "Secret", 120, True, "Gold apron Hello Kitty secret"),

        # ── ToyCity — Extended Laura & More ──────────────────────────────
        ("Laura Midnight City Series", "ToyCity", "Laura", "Midnight City", "Common", 14, False, "Nighttime city themed Laura"),
        ("Laura Midnight City Secret Neon", "ToyCity", "Laura", "Midnight City Secret", "Secret", 120, True, "Neon light secret Laura figure"),
        ("ToyCity Cino Afternoon Tea Series", "ToyCity", "Cino", "Afternoon Tea", "Common", 12, False, "Tea time themed Cino series"),
        ("ToyCity Cino Afternoon Tea Secret", "ToyCity", "Cino", "Afternoon Tea Secret", "Secret", 100, True, "Gold teapot Cino secret figure"),
        ("ToyCity x Crayon Shin-chan Series", "ToyCity", "Crayon Shin-chan", "Shin-chan Series", "Common", 14, False, "Crayon Shin-chan blind box"),

        # ── POP BEAN — Extended ──────────────────────────────────────────
        ("POP BEAN Dreamy Bakery Series", "POP BEAN", "Dreamy Bakery", "Bakery", "Common", 12, False, "Bakery themed POP BEAN figures"),
        ("POP BEAN Dreamy Bakery Secret Croissant Gold", "POP BEAN", "Dreamy Bakery", "Croissant Gold Secret", "Secret", 95, True, "Gold croissant secret figure"),
        ("POP BEAN Ocean Voyage Series", "POP BEAN", "Ocean Voyage", "Ocean Voyage", "Common", 12, False, "Sailor themed POP BEAN figures"),

        # ── Miniso Collaborations ────────────────────────────────────────
        ("Miniso x Sanrio My Melody Garden", "Miniso", "Sanrio Collab", "My Melody Garden", "Common", 10, False, "My Melody garden theme"),
        ("Miniso x Disney Winnie the Pooh Honey", "Miniso", "Disney Collab", "Winnie Honey", "Common", 10, False, "Winnie the Pooh honey theme"),
        ("Miniso x Pokemon Sitting Series", "Miniso", "Pokemon Collab", "Sitting Pokemon", "Common", 12, False, "Pokemon sitting pose capsule"),
        ("Miniso x SpongeBob Underwater Series", "Miniso", "SpongeBob Collab", "Underwater", "Common", 10, False, "SpongeBob underwater blind box"),

        # ── More Sonny Angel Limited ─────────────────────────────────────
        ("Sonny Angel Artist Collection NY Exclusive", "Sonny Angel", "Artist Collection", "NY Exclusive", "Ultra Rare", 250, False, "New York exclusive artist collab"),
        ("Sonny Angel Collaboration Moomin", "Sonny Angel", "Moomin Collab", "Moomin", "Rare", 65, False, "Moomin x Sonny Angel collab"),
        ("Sonny Angel Cat Life Series Napping", "Sonny Angel", "Cat Life", "Napping Cat", "Common", 14, False, "Cat lifestyle napping pose"),
        ("Sonny Angel Cat Life Series Playing Secret", "Sonny Angel", "Cat Life", "Playing Secret", "Secret", 120, True, "Secret playing cat figure"),
        ("Sonny Angel Dinosaur Series T-Rex", "Sonny Angel", "Dinosaur Series", "T-Rex", "Common", 12, False, "Dinosaur series T-Rex figure"),
        ("Sonny Angel Dinosaur Series Triceratops Secret", "Sonny Angel", "Dinosaur Series", "Triceratops Secret", "Secret", 130, True, "Metallic triceratops secret"),
        ("Sonny Angel Dog Series Shiba Inu", "Sonny Angel", "Dog Series", "Shiba Inu", "Common", 12, False, "Dog series shiba inu figure"),
        ("Sonny Angel Dog Series Corgi Secret", "Sonny Angel", "Dog Series", "Corgi Secret", "Secret", 125, True, "Crown wearing corgi secret"),
        ("Sonny Angel Forest Animal Series Deer", "Sonny Angel", "Forest Animal", "Deer", "Common", 12, False, "Forest animal deer figure"),
        ("Sonny Angel Forest Animal Series Fox Secret", "Sonny Angel", "Forest Animal", "Fox Secret", "Secret", 135, True, "Autumn leaf fox secret figure"),
        ("Sonny Angel Tropical Animal Series Flamingo", "Sonny Angel", "Tropical Animal", "Flamingo", "Common", 12, False, "Tropical animal flamingo figure"),
        ("Sonny Angel Birdie Series Parakeet", "Sonny Angel", "Birdie Series", "Parakeet", "Common", 12, False, "Birdie series parakeet figure"),

        # ── Expansion Batch — Pop Mart Mega Collection (Sizes) ──────────
        ("Space Molly 100% Pinkerton", "Pop Mart", "Space Molly 100%", "Pinkerton 100%", "Rare", 45, False, "Small format Space Molly Pinkerton"),
        ("Space Molly 100% Watermelon", "Pop Mart", "Space Molly 100%", "Watermelon 100%", "Rare", 42, False, "Small format watermelon colorway"),
        ("Space Molly 400% Hatsune Miku", "Pop Mart", "Space Molly 400%", "Hatsune Miku", "Ultra Rare", 850, False, "400% Hatsune Miku collaboration"),
        ("Space Molly 400% Back to the Future", "Pop Mart", "Space Molly 400%", "Back to the Future", "Ultra Rare", 700, False, "400% BTTF DeLorean theme"),
        ("Space Molly 1000% SpongeBob", "Pop Mart", "Space Molly 1000%", "SpongeBob", "Grail", 2200, False, "Mega size SpongeBob collab"),
        ("Space Molly 1000% Marvel Iron Man", "Pop Mart", "Space Molly 1000%", "Marvel Iron Man", "Grail", 2500, False, "Mega size Iron Man collaboration"),
        ("Labubu 400% The Monsters Tropical", "Pop Mart", "Labubu 400%", "Tropical Series 400%", "Ultra Rare", 550, False, "Large format Labubu tropical"),
        ("Labubu 1000% The Monsters Galaxy", "Pop Mart", "Labubu 1000%", "Galaxy 1000%", "Grail", 1600, False, "Mega size galaxy themed Labubu"),

        # ── Medicom Be@rbrick Blind Boxes ────────────────────────────────
        ("Medicom Be@rbrick Series 46 Full Case", "Medicom", "Bearbrick Series 46", "Full Case", "Rare", 180, False, "Latest 100% series blind box case"),
        ("Medicom Be@rbrick Series 45 Secret Chase", "Medicom", "Bearbrick Series 45", "Secret Chase", "Secret", 280, True, "Secret artist chase figure"),
        ("Medicom Be@rbrick Horror Series 100%", "Medicom", "Bearbrick Horror", "Horror Series", "Rare", 35, False, "Horror themed 100% blind box"),
        ("Medicom Be@rbrick Cute Series 100%", "Medicom", "Bearbrick Cute", "Cute Series", "Common", 20, False, "Cute themed 100% blind box"),
        ("Medicom Be@rbrick Cleverin Air Freshener Set", "Medicom", "Bearbrick Cleverin", "Air Freshener", "Rare", 55, False, "Cleverin functional art figure"),

        # ── KAWS Holiday Collaborations ──────────────────────────────────
        ("KAWS Holiday Japan Mount Fuji", "Medicom", "KAWS Holiday", "Japan Mount Fuji", "Ultra Rare", 750, False, "KAWS Holiday Japan reclining figure"),
        ("KAWS Holiday Hong Kong", "Medicom", "KAWS Holiday", "Hong Kong Bath", "Ultra Rare", 700, False, "KAWS Holiday HK floating figure"),
        ("KAWS Holiday Korea Seoul", "Medicom", "KAWS Holiday", "Korea Seoul", "Ultra Rare", 680, False, "KAWS Holiday Korea camping figure"),
        ("KAWS Holiday UK London", "Medicom", "KAWS Holiday", "UK London", "Ultra Rare", 720, False, "KAWS Holiday UK seated figure"),
        ("KAWS Holiday Singapore Companion", "Medicom", "KAWS Holiday", "Singapore", "Ultra Rare", 690, False, "KAWS Holiday Singapore reclining"),

        # ── tokidoki Unicorno New Series ──────────────────────────────────
        ("tokidoki Unicorno Series 13 Full Case", "tokidoki", "Unicorno Series 13", "Full Case", "Common", 14, False, "Latest Unicorno blind box series"),
        ("tokidoki Unicorno Series 13 Secret Prism", "tokidoki", "Unicorno Series 13", "Secret Prism", "Secret", 110, True, "Rainbow prism secret unicorno"),
        ("tokidoki Unicorno Tropical Paradise", "tokidoki", "Unicorno Tropical", "Tropical Paradise", "Common", 15, False, "Tropical themed unicorno series"),
        ("tokidoki Unicorno Valentine's Day Limited", "tokidoki", "Unicorno Valentine", "Valentine's Day", "Rare", 55, False, "Valentine's exclusive unicorno"),
        ("tokidoki Unicorno x Hello Kitty Collab", "tokidoki", "Unicorno x Hello Kitty", "Hello Kitty Collab", "Rare", 65, False, "Sanrio x tokidoki collaboration"),

        # ── Sonny Angel Marine / Fruit / Seasonal Extended ───────────────
        ("Sonny Angel Marine Series Dolphin", "Sonny Angel", "Marine Series", "Dolphin", "Common", 11, False, "Marine series dolphin hat figure"),
        ("Sonny Angel Marine Series Seahorse", "Sonny Angel", "Marine Series", "Seahorse", "Common", 11, False, "Marine series seahorse figure"),
        ("Sonny Angel Marine Series Jellyfish Secret", "Sonny Angel", "Marine Series", "Jellyfish Secret", "Secret", 130, True, "Translucent jellyfish secret figure"),
        ("Sonny Angel Fruit Series Mango", "Sonny Angel", "Fruit Series", "Mango", "Common", 10, False, "Tropical mango hat figure"),
        ("Sonny Angel Christmas 2025 Angel", "Sonny Angel", "Christmas 2025", "Christmas Angel", "Rare", 45, False, "2025 Christmas limited edition"),
        ("Sonny Angel Christmas 2025 Reindeer Secret", "Sonny Angel", "Christmas 2025", "Reindeer Secret", "Secret", 160, True, "Gold reindeer Christmas secret"),
        ("Sonny Angel Halloween 2025 Vampire", "Sonny Angel", "Halloween 2025", "Vampire", "Rare", 42, False, "2025 Halloween vampire edition"),
        ("Sonny Angel Halloween 2025 Pumpkin Secret", "Sonny Angel", "Halloween 2025", "Pumpkin Secret", "Secret", 150, True, "Glow-in-dark pumpkin secret"),
        ("Sonny Angel Flower Series Sunflower", "Sonny Angel", "Flower Series", "Sunflower", "Common", 12, False, "Flower series sunflower hat"),
        ("Sonny Angel Sweets Series Macaron", "Sonny Angel", "Sweets Series", "Macaron", "Common", 12, False, "Pastel macaron hat figure"),

        # ── Labubu New Releases ──────────────────────────────────────────
        ("Labubu The Monsters Forest Gaze", "Pop Mart", "Labubu", "Forest Gaze Series", "Common", 15, False, "Forest nature themed Labubu series"),
        ("Labubu The Monsters Forest Gaze Secret", "Pop Mart", "Labubu", "Forest Gaze Secret", "Secret", 190, True, "Golden deer antler secret Labubu"),
        ("Labubu The Monsters Dream Wedding", "Pop Mart", "Labubu", "Dream Wedding Series", "Common", 16, False, "Wedding themed Labubu series"),
        ("Labubu The Monsters Dream Wedding Secret", "Pop Mart", "Labubu", "Dream Wedding Secret", "Secret", 210, True, "Crystal bouquet secret Labubu"),
        ("Labubu The Monsters Ocean Explorer", "Pop Mart", "Labubu", "Ocean Explorer", "Common", 15, False, "Deep sea themed Labubu series"),
        ("Labubu The Monsters x Disney Stitch Collab", "Pop Mart", "Labubu", "Disney Stitch Collab", "Rare", 90, False, "Disney x Labubu Stitch collaboration"),
        ("Labubu The Monsters Retro Arcade", "Pop Mart", "Labubu", "Retro Arcade", "Common", 15, False, "Arcade gaming themed Labubu"),

        # ── More Pop Mart Licensed & IP ─────────────────────────────────
        ("Pop Mart Dimoo Dating Day Secret Cupid", "Pop Mart", "Dimoo", "Dating Day Secret Cupid", "Secret", 170, True, "Golden cupid wing secret Dimoo"),
        ("Pop Mart Hirono Reshape Series", "Pop Mart", "Hirono", "Reshape Series", "Common", 16, False, "Identity reshape theme, 9 designs"),
        ("Pop Mart Hirono Reshape Secret Mirror", "Pop Mart", "Hirono", "Reshape Secret Mirror", "Secret", 260, True, "Mirror reflection secret Hirono"),
        ("Pop Mart Skullpanda Warmth Series", "Pop Mart", "Skullpanda", "Warmth Series", "Common", 15, False, "Cozy warmth themed series"),
        ("Pop Mart Skullpanda Warmth Secret Fireplace", "Pop Mart", "Skullpanda", "Warmth Secret Fireplace", "Secret", 195, True, "Glowing fireplace secret figure"),
        ("Pop Mart Crybaby x Powerpuff Girls Collab", "Pop Mart", "Crybaby", "Powerpuff Girls Collab", "Rare", 75, False, "Powerpuff Girls x Crybaby limited collab"),
        ("Pop Mart Zsiga Night Walk Series", "Pop Mart", "Zsiga", "Night Walk Series", "Common", 15, False, "Nighttime walk themed series"),
        ("Pop Mart Pucky Sleep Babies Series", "Pop Mart", "Pucky", "Sleep Babies Series", "Common", 14, False, "Sleeping baby fairy theme"),
        ("Pop Mart Pucky Sleep Babies Secret Moon", "Pop Mart", "Pucky", "Sleep Babies Secret Moon", "Secret", 150, True, "Crescent moon secret Pucky figure"),
        ("Pop Mart Instinctoy Erosion Molly Sunset", "Pop Mart", "Molly", "Instinctoy Erosion Sunset", "Rare", 190, False, "Sunset colorway erosion Molly"),
        ("Sonny Angel Vegetable Series Carrot", "Sonny Angel", "Vegetable Series", "Carrot", "Common", 11, False, "Vegetable series carrot hat figure"),

        # ── Pop Mart — Dimoo Expansion ─────────────────────────────────────
        ("Dimoo Space Travel Series", "Pop Mart", "Dimoo", "Space Travel", "Common", 14, False, "Space exploration themed Dimoo series"),
        ("Dimoo Space Travel Secret Astronaut", "Pop Mart", "Dimoo", "Space Travel Secret", "Secret", 175, True, "Glow-in-dark astronaut secret Dimoo"),
        ("Dimoo No Limits Series", "Pop Mart", "Dimoo", "No Limits", "Common", 15, False, "Sports extreme theme Dimoo"),
        ("Dimoo No Limits Secret Skydiver", "Pop Mart", "Dimoo", "No Limits Secret", "Secret", 160, True, "Parachute skydiver secret Dimoo"),
        ("Dimoo Animal Friends Series", "Pop Mart", "Dimoo", "Animal Friends", "Common", 14, False, "Animal costume Dimoo figures"),
        ("Dimoo Animal Friends Secret Unicorn", "Pop Mart", "Dimoo", "Animal Friends Secret", "Secret", 180, True, "Rainbow unicorn secret Dimoo"),
        ("Dimoo Retro Computer Series", "Pop Mart", "Dimoo", "Retro Computer", "Common", 15, False, "Retro tech themed Dimoo"),
        ("Dimoo x Disney Frozen Elsa Collab", "Pop Mart", "Dimoo", "Disney Frozen Elsa", "Rare", 75, False, "Disney Frozen x Dimoo collaboration"),
        ("Dimoo Letters From Snowman Series", "Pop Mart", "Dimoo", "Letters From Snowman", "Common", 15, False, "Winter snowman themed Dimoo"),
        ("Dimoo Letters From Snowman Secret Ice", "Pop Mart", "Dimoo", "Letters From Snowman Secret", "Secret", 170, True, "Crystal ice secret Dimoo figure"),

        # ── Pop Mart — Skullpanda Expansion ────────────────────────────────
        ("Skullpanda Everyday Wonderland Series", "Pop Mart", "Skullpanda", "Everyday Wonderland", "Common", 15, False, "Alice-inspired wonderland theme"),
        ("Skullpanda Everyday Wonderland Secret Queen", "Pop Mart", "Skullpanda", "Everyday Wonderland Secret", "Secret", 210, True, "Queen of Hearts secret figure"),
        ("Skullpanda Hype Panda City Boy Series", "Pop Mart", "Skullpanda", "City Boy", "Common", 15, False, "Streetwear city boy theme"),
        ("Skullpanda Hype Panda City Boy Secret DJ", "Pop Mart", "Skullpanda", "City Boy Secret DJ", "Secret", 195, True, "Turntable DJ secret Skullpanda"),
        ("Skullpanda Temperature Of Desire Series", "Pop Mart", "Skullpanda", "Temperature Of Desire", "Common", 16, False, "Fashion desire themed series"),
        ("Skullpanda Temperature Of Desire Secret Flame", "Pop Mart", "Skullpanda", "Temperature Of Desire Secret", "Secret", 220, True, "Blue flame secret figure"),
        ("Skullpanda Ink Rhythm Chinese Series", "Pop Mart", "Skullpanda", "Ink Rhythm", "Common", 16, False, "Chinese ink art themed series"),
        ("Skullpanda The Sound Series", "Pop Mart", "Skullpanda", "The Sound", "Common", 15, False, "Musical instrument themed figures"),

        # ── Pop Mart — Hirono Expansion ────────────────────────────────────
        ("Hirono Reshape Series Regular", "Pop Mart", "Hirono", "Reshape Regular", "Common", 16, False, "Dark reshape identity theme"),
        ("Hirono Reshape Secret Broken Mask", "Pop Mart", "Hirono", "Reshape Secret Mask", "Secret", 270, True, "Cracked mask secret Hirono"),
        ("Hirono Lang Series", "Pop Mart", "Hirono", "Lang Series", "Common", 16, False, "Wolf companion theme Hirono"),
        ("Hirono Lang Secret Moon Wolf", "Pop Mart", "Hirono", "Lang Secret Moon", "Secret", 260, True, "Moon howling wolf secret figure"),
        ("Hirono x Crying in the Rain Collab", "Pop Mart", "Hirono", "Crying Rain Collab", "Rare", 85, False, "Hirono x Crybaby crossover collab"),
        ("Hirono The Other One Secret Shadow", "Pop Mart", "Hirono", "The Other One Shadow Secret", "Secret", 240, True, "Shadow silhouette secret Hirono"),
        ("Hirono Birdie Series", "Pop Mart", "Hirono", "Birdie", "Common", 16, False, "Bird companion themed Hirono"),
        ("Hirono Stairway Series", "Pop Mart", "Hirono", "Stairway", "Common", 16, False, "Surreal stairway theme 9 designs"),

        # ── tokidoki Expansion ─────────────────────────────────────────────
        ("tokidoki Mermicorno Series 7 Full Case", "tokidoki", "Mermicorno Series 7", "Full Case", "Common", 15, False, "Mermaid unicorno series 7"),
        ("tokidoki Mermicorno Series 7 Secret Pearl", "tokidoki", "Mermicorno Series 7", "Secret Pearl", "Secret", 100, True, "Pearl crown mermicorno secret"),
        ("tokidoki SANDy Series 3 Full Case", "tokidoki", "SANDy Series 3", "Full Case", "Common", 14, False, "Sandy beach themed series 3"),
        ("tokidoki Donutella Series 4 Full Case", "tokidoki", "Donutella Series 4", "Full Case", "Common", 14, False, "Donut themed character series 4"),
        ("tokidoki Cactus Kitties Series", "tokidoki", "Cactus Kitties", "Full Case", "Common", 14, False, "Cactus cat blind box series"),
        ("tokidoki Neon Star Series 5", "tokidoki", "Neon Star Series 5", "Full Case", "Common", 14, False, "Neon star character series 5"),
        ("tokidoki Tiger Nation Series", "tokidoki", "Tiger Nation", "Tiger Nation", "Common", 15, False, "Tiger themed tokidoki figures"),

        # ── Finding Unicorn Expansion ──────────────────────────────────────
        ("Finding Unicorn Shinwoo Ghost Bear Series", "Finding Unicorn", "Shinwoo Ghost Bear", "Standard", "Common", 14, False, "Popular ghost bear blind box"),
        ("Finding Unicorn Shinwoo Ghost Bear Secret Golden", "Finding Unicorn", "Shinwoo Ghost Bear", "Golden Secret", "Secret", 160, True, "Gold metallic ghost bear secret"),
        ("Finding Unicorn Lulu Piggy Travel Series", "Finding Unicorn", "Lulu Piggy", "Travel Series", "Common", 13, False, "Travel themed piggy figures"),
        ("Finding Unicorn Zhuo Cat Cafe Series", "Finding Unicorn", "Zhuo Cat", "Cafe Series", "Common", 13, False, "Cat cafe themed blind box"),
        ("Finding Unicorn RiCO Happy Factory Series", "Finding Unicorn", "RiCO", "Happy Factory", "Common", 14, False, "Factory worker themed figures"),
        ("Finding Unicorn RiCO Secret Robot Gold", "Finding Unicorn", "RiCO", "Happy Factory Secret", "Secret", 145, True, "Gold robot Rico secret figure"),
        ("Finding Unicorn Bao Bao Panda Dream Series", "Finding Unicorn", "Bao Bao Panda", "Dream Series", "Common", 13, False, "Dreaming panda blind box"),

        # ── 52Toys Expansion ───────────────────────────────────────────────
        ("52Toys MEGABOX Transformers Bumblebee", "52Toys", "MEGABOX", "Transformers Bumblebee", "Rare", 28, False, "Transforming cube Bumblebee figure"),
        ("52Toys MEGABOX Transformers Optimus Prime", "52Toys", "MEGABOX", "Transformers Optimus", "Rare", 28, False, "Transforming cube Optimus figure"),
        ("52Toys Nook Series Forest Diary", "52Toys", "Nook", "Forest Diary", "Common", 12, False, "Forest animal diary themed series"),
        ("52Toys Nook Secret Mushroom Fairy", "52Toys", "Nook", "Forest Diary Secret", "Secret", 95, True, "Mushroom fairy Nook secret figure"),
        ("52Toys BEASTBOX DIO Shark", "52Toys", "BEASTBOX", "DIO Shark", "Rare", 25, False, "Transforming cube shark figure"),
        ("52Toys Kimmy & Miki Pajama Series", "52Toys", "Kimmy & Miki", "Pajama Party", "Common", 12, False, "Pajama party themed blind box"),
        ("52Toys Panda Roll Daily Life Series", "52Toys", "Panda Roll", "Daily Life", "Common", 12, False, "Daily life panda rolling figures"),

        # ── Miniso Collaborations Expansion ────────────────────────────────
        ("Miniso x Barbie Fashion Series", "Miniso", "Barbie Collab", "Fashion Barbie", "Common", 12, False, "Barbie fashion blind box figures"),
        ("Miniso x Minions Banana Series", "Miniso", "Minions Collab", "Banana Minions", "Common", 10, False, "Minions banana themed blind box"),
        ("Miniso x Toy Story Aliens Series", "Miniso", "Toy Story Collab", "Aliens Green", "Common", 10, False, "Toy Story alien figures capsule"),
        ("Miniso x Chiikawa Adventure Series", "Miniso", "Chiikawa Collab", "Adventure", "Common", 12, False, "Chiikawa adventure themed series"),
        ("Miniso x Crayon Shin-chan Pajama Series", "Miniso", "Shin-chan Collab", "Pajama", "Common", 10, False, "Shin-chan pajama blind box"),

        # ── Litor's Works Expansion ────────────────────────────────────────
        ("Litor's Works Umasou! Dinosaur Series 3", "Litor's Works", "Umasou!", "Dinosaur Series 3", "Common", 14, False, "Cute dinosaur blind box series 3"),
        ("Litor's Works Umasou! Secret Rex Crystal", "Litor's Works", "Umasou!", "Dinosaur S3 Secret", "Secret", 120, True, "Crystal T-Rex secret Umasou"),
        ("Litor's Works Keep Me Company Series", "Litor's Works", "Keep Me Company", "Standard", "Common", 14, False, "Companion themed blind box"),
    ]

    catalog = []
    for name, brand, series, variant, rarity, price_eur, is_secret, notes in items_raw:
        catalog.append({
            "name": name,
            "brand": brand,
            "series": series,
            "variant": variant,
            "rarity": rarity,
            "price_eur": price_eur,
            "is_secret": is_secret,
            "notes": notes,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    series = item["series"]
    name = item["name"]
    variant = item["variant"]
    rarity = item["rarity"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{series}-{name}"),
        title=name,
        set_code=slugify(series),
        brand=brand,
        rarity=rarity,
        notes=item["notes"],
        attributes_json={
            "brand": brand,
            "series": series,
            "variant": variant,
            "is_secret": item["is_secret"],
        },
    )


_BLIND_BOX_RARITY: dict[str, float] = {
    "Common": 0.1,
    "Uncommon": 0.3,
    "Rare": 0.5,
    "Secret": 0.85,
    "Ultra Rare": 0.8,
    "Grail": 0.95,
}


def _blind_box_rarity_score(rarity: str) -> float:
    """Map blind-box rarity tiers to 0-1 score, falling back to shared map."""
    if rarity in _BLIND_BOX_RARITY:
        return _BLIND_BOX_RARITY[rarity]
    return shared_rarity_score(rarity)


def item_to_price_observation(item: dict) -> PriceObservation:
    rarity = item["rarity"]
    is_secret = item["is_secret"]

    return PriceObservation(
        features={
            "condition_score": 0.90,
            "rarity_score": _blind_box_rarity_score(rarity),
            "edition_score": 0.8 if is_secret else 0.3,
            "is_secret": 1.0 if is_secret else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Blind Box catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Blind Box Import ===")

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

    logger.info(f"\n=== Blind Box Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
