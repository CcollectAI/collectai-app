"""
Import anime OST vinyl records catalog.

Layer 1 (Catalog):  Curated anime vinyl releases → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers 600+ items across 30+ label groups:
- Tiger Lab Vinyl releases (Cowboy Bebop, Samurai Champloo, FLCL, Akira, Ghost in the Shell)
- Milan Records anime vinyl (Studio Ghibli: Spirited Away, Mononoke, Totoro, etc.)
- Data Discs (game/anime crossover: Jet Set Radio, Shenmue, Streets of Rage, etc.)
- Mondo anime releases (Akira, GiTS, Dragon Ball Z, Attack on Titan, Demon Slayer, etc.)
- Aniplex / Sony Music Japan (Demon Slayer, SAO, Fate, Madoka Magica, etc.)
- King Records / Japanese labels (classic anime: Dragon Ball, Sailor Moon, Yu Yu Hakusho)
- Crunchyroll / new labels (Jujutsu Kaisen, Chainsaw Man, Spy x Family, etc.)
- Classic/vintage anime OST (Lupin III, Yamato, Gundam, Bubblegum Crisis, etc.)
- Japanese pressings: King Records, Flying Dog, Tokuma, Nippon Columbia
- Event-exclusive color variants (anime expos, RSD, numbered pressings)
- City pop / anime crossover vinyl
- Wayo Records (Persona 5, NieR: Gestalt)
- Ship to Shore PhonoCo (Mega Man, Castlevania)
- iam8bit releases (Undertale, Celeste, Hollow Knight)
- Vinyl Me Please anime editions
- Studio Ghibli Joe Hisaishi deluxe/color pressings
- Recent seasonal hits: Chainsaw Man, Spy x Family, Jujutsu Kaisen color variants
- Glow-in-dark, splatter, clear, and other limited color pressings
- Lantis / Pony Canyon anime pressings
- Square Enix / Atlus game soundtrack releases
- Numbered / limited color variants (RSD, convention exclusives)
- Modern shonen & isekai anime releases
- Tokusatsu / super robot anime vinyl
- Score / orchestral anime recordings

Usage:
    python -m pipelines.import_anime_ost_vinyl [--dry-run]
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

CATEGORY = "anime_ost_vinyl"


def get_curated_catalog() -> list[dict]:
    """Curated anime OST vinyl records catalog — 600+ items across 30+ label groups."""

    # (label, title, franchise, pressing, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>100), high (50-100), mid (25-50), standard (<25)

    items = [
        # ── Tiger Lab Vinyl ──────────────────────────────────────────────
        ("Tiger Lab Vinyl", "Cowboy Bebop OST 1 (Seatbelts)", "Cowboy Bebop", "US Pressing", "Black", "mid", 40),
        ("Tiger Lab Vinyl", "Cowboy Bebop OST 1 (Seatbelts)", "Cowboy Bebop", "US Pressing", "Red Translucent", "high", 70),
        ("Tiger Lab Vinyl", "Cowboy Bebop Vitaminless", "Cowboy Bebop", "US Pressing", "Black", "mid", 38),
        ("Tiger Lab Vinyl", "Cowboy Bebop Blue", "Cowboy Bebop", "US Pressing", "Blue Translucent", "high", 65),
        ("Tiger Lab Vinyl", "Samurai Champloo: The Way of the Samurai", "Samurai Champloo", "US Pressing", "Black", "mid", 35),
        ("Tiger Lab Vinyl", "Samurai Champloo: The Way of the Samurai", "Samurai Champloo", "US Pressing", "Red/White Splatter", "high", 80),
        ("Tiger Lab Vinyl", "Samurai Champloo: Departure", "Samurai Champloo", "US Pressing", "Black", "mid", 38),
        ("Tiger Lab Vinyl", "Samurai Champloo: Impression", "Samurai Champloo", "US Pressing", "Black", "mid", 38),

        # ── Milan Records – Studio Ghibli ────────────────────────────────
        ("Milan Records", "Spirited Away Soundtrack (Joe Hisaishi)", "Spirited Away", "EU/US Pressing", "Black", "mid", 35),
        ("Milan Records", "Princess Mononoke Soundtrack", "Princess Mononoke", "EU/US Pressing", "Black", "mid", 32),
        ("Milan Records", "My Neighbor Totoro Image Album", "My Neighbor Totoro", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "Howl's Moving Castle Soundtrack", "Howl's Moving Castle", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "Nausicaa Soundtrack", "Nausicaa", "EU/US Pressing", "Black", "mid", 35),
        ("Milan Records", "Castle in the Sky Soundtrack", "Castle in the Sky", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "Kiki's Delivery Service Soundtrack", "Kiki's Delivery Service", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "Laputa: Castle in the Sky Image Album", "Castle in the Sky", "EU/US Pressing", "Black", "mid", 32),
        ("Milan Records", "Ponyo on the Cliff Soundtrack", "Ponyo", "EU/US Pressing", "Black", "mid", 28),
        ("Milan Records", "The Wind Rises Soundtrack", "The Wind Rises", "EU/US Pressing", "Black", "mid", 30),

        # ── Japanese pressings – King Records, Flying Dog, Tokuma ────────
        ("King Records", "Macross Frontier Vocal Collection (2LP)", "Macross Frontier", "Japanese Pressing", "Black", "high", 75),
        ("Flying Dog", "Cowboy Bebop OST (Original Japanese)", "Cowboy Bebop", "Japanese Pressing", "Black", "grail", 130),
        ("King Records", "Evangelion Original Soundtrack (2LP)", "Evangelion", "Japanese Pressing", "Black", "high", 85),
        ("Tokuma Japan", "Nausicaa OST (Original 1984 Pressing)", "Nausicaa", "Japanese OG Pressing", "Black", "grail", 150),
        ("King Records", "Ghost in the Shell OST (Kenji Kawai)", "Ghost in the Shell", "Japanese Pressing", "Black", "high", 95),
        ("Flying Dog", "Macross Plus OST (Yoko Kanno)", "Macross Plus", "Japanese Pressing", "Black", "high", 80),

        # ── King Records / Japanese Labels (additional) ──────────────────
        ("King Records", "Dragon Ball Z: Cha-La Head-Cha-La (7\" Single)", "Dragon Ball Z", "Japanese OG Pressing", "Black", "high", 55),
        ("Columbia Japan", "Sailor Moon Original Soundtrack (2LP)", "Sailor Moon", "Japanese OG Pressing", "Black", "high", 75),
        ("Victor", "Yu Yu Hakusho Original Soundtrack", "Yu Yu Hakusho", "Japanese OG Pressing", "Black", "high", 65),
        ("Aniplex", "Rurouni Kenshin Original Soundtrack", "Rurouni Kenshin", "Japanese Pressing", "Black", "high", 60),
        ("Sunrise Music", "Inuyasha Original Soundtrack", "Inuyasha", "Japanese Pressing", "Black", "high", 55),
        ("Kitty Records", "Ranma 1/2 Original Soundtrack", "Ranma 1/2", "Japanese OG Pressing", "Black", "high", 50),

        # ── Event-exclusive color variants (original) ────────────────────
        ("Mondo", "Akira Symphonic Suite (2LP)", "Akira", "Event Exclusive", "Tetsuo Splatter", "grail", 140),
        ("Tiger Lab Vinyl", "Cowboy Bebop OST 1 (Record Store Day)", "Cowboy Bebop", "RSD Exclusive", "Gold", "grail", 110),
        ("Milan Records", "Spirited Away (Anime Expo Exclusive)", "Spirited Away", "Event Exclusive", "Clear Blue", "grail", 120),
        ("Mondo", "Ghost in the Shell OST (Deluxe)", "Ghost in the Shell", "Event Exclusive", "Cyber Green Marble", "grail", 150),

        # ── Event Exclusive / Limited Color Variants (expanded) ──────────
        ("Tiger Lab Vinyl", "Samurai Champloo: The Way of the Samurai (RSD)", "Samurai Champloo", "RSD Exclusive", "Cherry Blossom Pink", "grail", 115),
        ("Milan Records", "Princess Mononoke (Anime NYC Exclusive)", "Princess Mononoke", "Event Exclusive", "Forest Green Marble", "grail", 125),
        ("Mondo", "Akira OST (Numbered /500)", "Akira", "Event Exclusive", "Picture Disc", "grail", 160),
        ("Tiger Lab Vinyl", "FLCL OST (Anime Expo Exclusive)", "FLCL", "Event Exclusive", "Orange Splatter", "grail", 105),
        ("Data Discs", "Jet Set Radio OST (Crunchyroll Expo Exclusive)", "Jet Set Radio", "Event Exclusive", "Clear Yellow", "grail", 110),
        ("Mondo", "Dragon Ball Z: Fusion Reborn (RSD)", "Dragon Ball Z", "RSD Exclusive", "Fusion Splatter", "grail", 130),
        ("Aniplex", "Demon Slayer OST (AnimeJapan Exclusive)", "Demon Slayer", "Event Exclusive", "Flame Red/Orange Splatter", "grail", 140),
        ("Crunchyroll Records", "Jujutsu Kaisen OST (Numbered /1000)", "Jujutsu Kaisen", "Event Exclusive", "Cursed Purple Marble", "grail", 120),

        # ── City pop / anime crossover vinyl ─────────────────────────────
        ("Nippon Columbia", "Kimagure Orange Road: Singing Heart", "Kimagure Orange Road", "Japanese OG Pressing", "Black", "high", 65),
        ("Canyon Records", "Dirty Pair Original Soundtrack", "Dirty Pair", "Japanese OG Pressing", "Black", "high", 55),
        ("Victor", "Urusei Yatsura: Music Capsule", "Urusei Yatsura", "Japanese OG Pressing", "Black", "high", 60),
        ("King Records", "Megazone 23 Soundtrack", "Megazone 23", "Japanese OG Pressing", "Black", "high", 70),
        ("Canyon Records", "City Hunter OST (Get Wild)", "City Hunter", "Japanese OG Pressing", "Black", "high", 55),

        # ── Key titles – modern pressings ────────────────────────────────
        ("Mondo", "Akira OST (Geinoh Yamashirogumi)", "Akira", "Reissue", "Black", "mid", 45),
        ("Milan Records", "Your Name OST (RADWIMPS)", "Your Name", "EU Pressing", "Black", "mid", 35),
        ("Tiger Lab Vinyl", "FLCL OST (The Pillows)", "FLCL", "US Pressing", "Black", "mid", 40),

        # ── Data Discs (game/anime crossover) ────────────────────────────
        ("Data Discs", "Streets of Rage 2 OST (Yuzo Koshiro)", "Streets of Rage", "EU Pressing", "Red Translucent", "high", 55),
        ("Data Discs", "Shenmue OST (2LP)", "Shenmue", "EU Pressing", "Blue Translucent", "high", 60),
        ("Data Discs", "Sonic the Hedgehog 1&2 OST", "Sonic the Hedgehog", "EU Pressing", "Blue", "mid", 45),
        ("Data Discs", "Panzer Dragoon OST", "Panzer Dragoon", "EU Pressing", "Clear", "high", 55),
        ("Data Discs", "Jet Set Radio OST (2LP)", "Jet Set Radio", "EU Pressing", "Green Translucent", "high", 65),
        ("Data Discs", "Streets of Rage 2 OST (Yuzo Koshiro)", "Streets of Rage", "EU Pressing", "Black", "mid", 40),
        ("Data Discs", "Shenmue OST (2LP)", "Shenmue", "EU Pressing", "Black", "mid", 42),
        ("Data Discs", "Sonic the Hedgehog 1&2 OST", "Sonic the Hedgehog", "EU Pressing", "Classic Gold", "high", 60),
        ("Square Enix Music", "NieR: Automata Vinyl Box Set (4LP)", "NieR: Automata", "Japanese Pressing", "Black", "grail", 180),
        ("Square Enix Music", "NieR: Automata OST (Weight of the World)", "NieR: Automata", "EU Pressing", "White", "high", 65),

        # ── Mondo (expanded beyond Akira/GiTS) ──────────────────────────
        ("Mondo", "Dragon Ball Z: Fusion Reborn OST", "Dragon Ball Z", "US Pressing", "Black", "mid", 38),
        ("Mondo", "My Hero Academia OST (Yuki Hayashi)", "My Hero Academia", "US Pressing", "Red/White/Blue Tricolor", "high", 55),
        ("Mondo", "Spirited Away Soundtrack (Alternate Art)", "Spirited Away", "US Pressing", "Clear Blue", "high", 60),
        ("Mondo", "Attack on Titan Season 1 OST (Hiroyuki Sawano)", "Attack on Titan", "US Pressing", "Crimson Red", "high", 65),
        ("Mondo", "Demon Slayer: Mugen Train OST", "Demon Slayer", "US Pressing", "Flame Orange", "high", 55),
        ("Mondo", "One Punch Man OST (Makoto Miyazaki)", "One Punch Man", "US Pressing", "Yellow", "mid", 42),

        # ── Aniplex / Sony Music Japan ───────────────────────────────────
        ("Aniplex", "Demon Slayer OST (Yuki Kajiura / Go Shiina)", "Demon Slayer", "Japanese Pressing", "Black", "high", 70),
        ("Aniplex", "Sword Art Online OST (Yuki Kajiura)", "Sword Art Online", "Japanese Pressing", "Black", "high", 60),
        ("Aniplex", "Fate/Stay Night: Unlimited Blade Works OST", "Fate/Stay Night", "Japanese Pressing", "Black", "high", 65),
        ("Aniplex", "Madoka Magica OST (Yuki Kajiura)", "Madoka Magica", "Japanese Pressing", "Black", "high", 75),
        ("Aniplex", "Monogatari Series OST (Satoru Kosaki)", "Monogatari", "Japanese Pressing", "Black", "high", 70),
        ("Aniplex", "Your Lie in April OST (Masaru Yokoyama)", "Your Lie in April", "Japanese Pressing", "Black", "high", 55),
        ("Aniplex", "Fullmetal Alchemist: Brotherhood OST (Akira Senju)", "Fullmetal Alchemist", "Japanese Pressing", "Black", "high", 80),
        ("Sony Music Japan", "Demon Slayer OST (2LP Deluxe)", "Demon Slayer", "Japanese Pressing", "Red/Black Split", "grail", 110),

        # ── Crunchyroll / New Labels ─────────────────────────────────────
        ("Crunchyroll Records", "Jujutsu Kaisen OST (Hiroaki Tsutsumi)", "Jujutsu Kaisen", "US Pressing", "Black", "mid", 35),
        ("Crunchyroll Records", "Chainsaw Man OST (Kensuke Ushio)", "Chainsaw Man", "US Pressing", "Blood Red", "mid", 38),
        ("Crunchyroll Records", "Spy x Family OST (K)NoW_NAME", "Spy x Family", "US Pressing", "Pink", "standard", 24),
        ("Crunchyroll Records", "Bocchi the Rock! OST", "Bocchi the Rock!", "US Pressing", "Pink Splatter", "mid", 32),
        ("Crunchyroll Records", "Vinland Saga OST (Yutaka Yamada)", "Vinland Saga", "US Pressing", "Black", "mid", 30),

        # ── Classic / Vintage Anime OST ──────────────────────────────────
        ("Nippon Columbia", "Lupin III '77 Original Soundtrack (Yuji Ohno)", "Lupin III", "Japanese OG Pressing", "Black", "grail", 120),
        ("Nippon Columbia", "Space Battleship Yamato OST (1974)", "Space Battleship Yamato", "Japanese OG Pressing", "Black", "grail", 140),
        ("King Records", "Mobile Suit Gundam OST (Takeo Watanabe)", "Mobile Suit Gundam", "Japanese OG Pressing", "Black", "grail", 130),
        ("Invitation", "Akira OST (Geinoh Yamashirogumi) Original Japan", "Akira", "Japanese OG Pressing", "Black", "grail", 200),
        ("Youmex", "Bubblegum Crisis OST", "Bubblegum Crisis", "Japanese OG Pressing", "Black", "high", 85),
        ("Avex Trax", "Initial D: Super Eurobeat Selection", "Initial D", "Japanese OG Pressing", "Black", "high", 75),
        ("Columbia Japan", "Dragon Ball OST (Shunsuke Kikuchi)", "Dragon Ball", "Japanese OG Pressing", "Black", "grail", 110),
        ("Columbia Japan", "Saint Seiya Original Soundtrack", "Saint Seiya", "Japanese OG Pressing", "Black", "high", 90),

        # ── Studio Ghibli – Joe Hisaishi deluxe/color pressings ────────
        ("Milan Records", "Spirited Away Soundtrack (2LP Deluxe)", "Spirited Away", "EU/US Pressing", "Clear Ocean Blue", "high", 58),
        ("Milan Records", "My Neighbor Totoro Image Album (Color)", "My Neighbor Totoro", "EU/US Pressing", "Leaf Green", "high", 52),
        ("Milan Records", "Princess Mononoke Soundtrack (2LP)", "Princess Mononoke", "EU/US Pressing", "Forest Green Marble", "high", 55),
        ("Milan Records", "Howl's Moving Castle Soundtrack (Color)", "Howl's Moving Castle", "EU/US Pressing", "Sky Blue Translucent", "high", 54),
        ("Milan Records", "Castle in the Sky Image Album (Color)", "Castle in the Sky", "EU/US Pressing", "Crystal Clear", "high", 50),
        ("Milan Records", "Porco Rosso Soundtrack (Joe Hisaishi)", "Porco Rosso", "EU/US Pressing", "Black", "mid", 35),
        ("Milan Records", "The Tale of Princess Kaguya Soundtrack", "Princess Kaguya", "EU/US Pressing", "Black", "mid", 38),

        # ── Tiger Lab Vinyl – additional represses ─────────────────────
        ("Tiger Lab Vinyl", "Akira Symphonic Suite (Repress)", "Akira", "US Pressing", "Black", "mid", 42),
        ("Tiger Lab Vinyl", "Akira Symphonic Suite (Repress)", "Akira", "US Pressing", "Tetsuo Red Splatter", "high", 75),
        ("Tiger Lab Vinyl", "Ghost in the Shell OST (Repress)", "Ghost in the Shell", "US Pressing", "Black", "mid", 40),
        ("Tiger Lab Vinyl", "Ghost in the Shell OST (Repress)", "Ghost in the Shell", "US Pressing", "Cyber Green", "high", 72),
        ("Tiger Lab Vinyl", "Cowboy Bebop Vitaminless", "Cowboy Bebop", "US Pressing", "Orange Translucent", "high", 68),

        # ── Data Discs – game/anime crossover expansion ────────────────
        ("Data Discs", "Streets of Rage OST (Yuzo Koshiro)", "Streets of Rage", "EU Pressing", "Clear Purple", "high", 58),
        ("Data Discs", "Streets of Rage 3 OST", "Streets of Rage", "EU Pressing", "Neon Green", "high", 55),
        ("Data Discs", "Shenmue II OST (2LP)", "Shenmue", "EU Pressing", "Clear", "high", 58),
        ("Data Discs", "Golden Axe OST", "Golden Axe", "EU Pressing", "Gold", "mid", 42),

        # ── Mondo – anime expansion ────────────────────────────────────
        ("Mondo", "Paprika OST (Susumu Hirasawa)", "Paprika", "US Pressing", "Dream Red Splatter", "high", 65),
        ("Mondo", "Perfect Blue OST", "Perfect Blue", "US Pressing", "Midnight Blue", "high", 68),
        ("Mondo", "Cowboy Bebop OST (2LP Deluxe)", "Cowboy Bebop", "US Pressing", "Smoke Clear", "high", 70),
        ("Mondo", "Evangelion 3.0+1.0 OST", "Evangelion", "US Pressing", "Eva Purple/Green Split", "high", 62),

        # ── Wayo Records ───────────────────────────────────────────────
        ("Wayo Records", "Persona 5 Original Soundtrack (4LP Box)", "Persona 5", "EU Pressing", "Phantom Red", "grail", 140),
        ("Wayo Records", "NieR: Gestalt & Replicant OST (2LP)", "NieR", "EU Pressing", "White", "high", 68),
        ("Wayo Records", "NieR: Automata Piano Collections", "NieR: Automata", "EU Pressing", "Clear", "high", 55),

        # ── Ship to Shore PhonoCo ──────────────────────────────────────
        ("Ship to Shore PhonoCo", "Mega Man 2 OST (Takashi Tateishi)", "Mega Man 2", "US Pressing", "Blue", "mid", 45),
        ("Ship to Shore PhonoCo", "Castlevania: Symphony of the Night OST (Michiru Yamane)", "Castlevania: SotN", "US Pressing", "Blood Red", "high", 65),
        ("Ship to Shore PhonoCo", "Castlevania III: Dracula's Curse OST", "Castlevania III", "US Pressing", "Glow-in-Dark", "high", 70),

        # ── iam8bit releases ───────────────────────────────────────────
        ("iam8bit", "Undertale Vinyl Soundtrack (Toby Fox) 2LP", "Undertale", "US Pressing", "Blue", "high", 55),
        ("iam8bit", "Celeste OST (Lena Raine) 2LP", "Celeste", "US Pressing", "Mountain Blue", "high", 52),
        ("iam8bit", "Hollow Knight OST (Christopher Larkin) 2LP", "Hollow Knight", "US Pressing", "Void Black", "high", 55),
        ("iam8bit", "Ori and the Blind Forest OST (Gareth Coker)", "Ori and the Blind Forest", "US Pressing", "Glow Blue", "high", 58),

        # ── Vinyl Me Please anime editions ─────────────────────────────
        ("Vinyl Me Please", "Cowboy Bebop OST (VMP Exclusive)", "Cowboy Bebop", "US Pressing", "Whiskey Gold Splatter", "grail", 115),
        ("Vinyl Me Please", "Akira OST (VMP Exclusive)", "Akira", "US Pressing", "Neo-Tokyo Neon Splatter", "grail", 125),

        # ── Recent hits – color variants & limited pressings ───────────
        ("Crunchyroll Records", "Chainsaw Man OST (Kensuke Ushio)", "Chainsaw Man", "US Pressing", "Chainsaw Splatter Clear", "high", 55),
        ("Crunchyroll Records", "Spy x Family OST (K)NoW_NAME", "Spy x Family", "US Pressing", "Anya Pink Marble", "mid", 35),
        ("Crunchyroll Records", "Jujutsu Kaisen S2 OST", "Jujutsu Kaisen", "US Pressing", "Sukuna Red/Gold Splatter", "high", 52),
        ("Crunchyroll Records", "Chainsaw Man OST (Glow-in-Dark)", "Chainsaw Man", "Event Exclusive", "Glow-in-Dark Green", "grail", 105),

        # ── Lantis / Pony Canyon Anime Pressings ──────────────────────────
        ("Lantis", "Gurren Lagann OST (Taku Iwasaki)", "Gurren Lagann", "Japanese Pressing", "Drill Orange", "high", 65),
        ("Lantis", "Kill la Kill OST (Hiroyuki Sawano)", "Kill la Kill", "Japanese Pressing", "Red/Black Split", "high", 62),
        ("Lantis", "Love Live! School Idol Project OST", "Love Live!", "Japanese Pressing", "Pink", "mid", 45),
        ("Pony Canyon", "Vinland Saga OST (Yutaka Yamada) 2LP", "Vinland Saga", "Japanese Pressing", "Viking Brown", "high", 58),
        ("Pony Canyon", "Golden Kamuy OST (Kenichiro Suehiro)", "Golden Kamuy", "Japanese Pressing", "Gold", "mid", 48),
        ("Pony Canyon", "Odd Taxi OST (PUNPEE/VaVa/OMSB)", "Odd Taxi", "Japanese Pressing", "Taxi Yellow", "high", 62),
        ("Lantis", "BanG Dream! OST (Elements Garden)", "BanG Dream!", "Japanese Pressing", "Star Pink", "mid", 38),

        # ── Square Enix / Atlus VGM Expansion ─────────────────────────────
        ("Square Enix Music", "Final Fantasy X OST (Nobuo Uematsu) 4LP", "Final Fantasy X", "Japanese Pressing", "Zanarkand Blue", "grail", 150),
        ("Square Enix Music", "Final Fantasy XIV: Endwalker OST (Masayoshi Soken) 4LP", "Final Fantasy XIV", "Japanese Pressing", "Black", "grail", 130),
        ("Atlus Music", "Persona 3 OST (Shoji Meguro) 3LP", "Persona 3", "Japanese Pressing", "Velvet Blue", "grail", 125),
        ("Atlus Music", "Shin Megami Tensei V OST 2LP", "SMT V", "Japanese Pressing", "Nahobino Silver", "high", 70),
        ("Square Enix Music", "Chrono Cross OST (Yasunori Mitsuda) Reissue", "Chrono Cross", "Reissue", "Sea Blue", "high", 65),
        ("Square Enix Music", "Kingdom Hearts III OST (Yoko Shimomura) 3LP", "Kingdom Hearts III", "Japanese Pressing", "Keyblade Silver", "grail", 120),

        # ── Numbered / Limited Color Variants (expanded) ─────────────────
        ("Milan Records", "Spirited Away (Numbered /2000 Gold Foil)", "Spirited Away", "Numbered Limited", "Gold Swirl", "grail", 150),
        ("Mondo", "Akira OST (RSD 2025 Pink/Blue Split)", "Akira", "RSD Exclusive", "Pink/Blue Split", "grail", 135),
        ("Tiger Lab Vinyl", "FLCL OST (Numbered /1500 Clear)", "FLCL", "Numbered Limited", "Crystal Clear", "grail", 120),
        ("Mondo", "Ghost in the Shell OST (Numbered /1000)", "Ghost in the Shell", "Numbered Limited", "Matrix Green Swirl", "grail", 145),
        ("Aniplex", "Fate/Zero OST (Yuki Kajiura) (AnimeJapan /500)", "Fate/Zero", "Event Exclusive", "Gold/Black Marble", "grail", 160),
        ("Crunchyroll Records", "Attack on Titan S4 OST (RSD)", "Attack on Titan S4", "RSD Exclusive", "Rumbling Red Splatter", "grail", 115),

        # ── Modern Shonen & Isekai Anime Releases ────────────────────────
        ("Aniplex", "Demon Slayer: Hashira Training OST", "Demon Slayer S4", "Japanese Pressing", "Black", "high", 55),
        ("Aniplex", "Sword Art Online Alicization OST (Yuki Kajiura) 2LP", "SAO Alicization", "Japanese Pressing", "Black", "high", 68),
        ("Kadokawa", "Re:Zero OST (Kenichiro Suehiro) 2LP", "Re:Zero", "Japanese Pressing", "Black", "high", 58),
        ("Kadokawa", "Overlord IV OST (Shuji Katayama)", "Overlord IV", "Japanese Pressing", "Black", "mid", 45),
        ("Kadokawa", "Mushoku Tensei OST (Yoshiaki Fujisawa) 2LP", "Mushoku Tensei", "Japanese Pressing", "Isekai Green", "high", 60),
        ("Lantis", "That Time I Got Reincarnated as a Slime OST", "TenSura", "Japanese Pressing", "Slime Blue", "mid", 42),
        ("Aniplex", "Kaguya-sama: Love is War OST (Kei Haneoka)", "Kaguya-sama", "Japanese Pressing", "Heart Pink", "mid", 48),
        ("Aniplex", "Undead Unluck OST (Taku Iwasaki)", "Undead Unluck", "Japanese Pressing", "Black", "mid", 38),
        ("Aniplex", "Solo Leveling OST (Hiroyuki Sawano) (Color)", "Solo Leveling", "Japanese Pressing", "Shadow Purple", "high", 62),
        ("Kadokawa", "Shield Hero OST (Kevin Penkin) 2LP", "Shield Hero", "Japanese Pressing", "Black", "mid", 48),
        ("Pony Canyon", "Blue Lock OST (Yutaka Yamada)", "Blue Lock", "Japanese Pressing", "Black", "mid", 42),

        # ── Tokusatsu / Super Robot Anime Vinyl ──────────────────────────
        ("Columbia Japan", "Mazinger Z OST (Michiaki Watanabe) Reissue", "Mazinger Z", "Reissue", "Black", "mid", 38),
        ("Columbia Japan", "Great Mazinger OST", "Great Mazinger", "Japanese OG Pressing", "Black", "grail", 160),
        ("King Records", "Getter Robo OST (Shunsuke Kikuchi)", "Getter Robo", "Japanese OG Pressing", "Black", "grail", 150),
        ("Columbia Japan", "UFO Robot Grendizer OST", "Grendizer", "Japanese OG Pressing", "Black", "grail", 140),
        ("King Records", "Combattler V OST", "Combattler V", "Japanese OG Pressing", "Black", "high", 95),
        ("Nippon Columbia", "Daitarn 3 OST", "Daitarn 3", "Japanese OG Pressing", "Black", "high", 85),
        ("King Records", "GaoGaiGar OST (Kohei Tanaka) 2LP", "GaoGaiGar", "Japanese Pressing", "Brave Gold", "high", 75),

        # ── Score / Orchestral Anime Recordings ──────────────────────────
        ("Aniplex", "Demon Slayer Orchestral Concert Album 2LP", "Demon Slayer", "Japanese Pressing", "Concert Black", "high", 72),
        ("Sony Music Japan", "Joe Hisaishi Symphonic Suite: Studio Ghibli 3LP", "Studio Ghibli", "Japanese Pressing", "Clear", "grail", 110),
        ("Flying Dog", "Macross Frontier Galaxy Concert 2LP", "Macross Frontier", "Japanese Pressing", "Star Dust Clear", "high", 80),
        ("King Records", "Evangelion Symphonic Works (2LP)", "Evangelion", "Japanese Pressing", "Eva Purple", "high", 85),
        ("Aniplex", "Attack on Titan Final Season Concert 2LP", "Attack on Titan", "Japanese Pressing", "Black", "high", 68),
        ("Lantis", "Gundam Unicorn RE:MIX 0096 Vinyl", "Gundam Unicorn", "Japanese Pressing", "Unicorn White", "high", 72),

        # ── Additional Modern Pressings ──────────────────────────────────
        ("Tiger Lab Vinyl", "Ghost in the Shell: Arise OST", "Ghost in the Shell: Arise", "US Pressing", "Neon Blue", "mid", 42),
        ("Tiger Lab Vinyl", "Lupin III Part 6 OST (Yuji Ohno)", "Lupin III Part 6", "US Pressing", "Black", "mid", 38),
        ("Mondo", "Promare OST (Hiroyuki Sawano)", "Promare", "US Pressing", "Flame Blue/Red Split", "high", 55),
        ("Mondo", "Belle OST (Ludvig Forssell/Millennium Parade)", "Belle", "US Pressing", "Rose Pink", "high", 52),
        ("Mondo", "Suzume OST (RADWIMPS/Kazuma Jinnouchi)", "Suzume", "US Pressing", "Clear Blue", "high", 58),
        ("Milan Records", "Weathering with You OST (RADWIMPS)", "Weathering with You", "EU Pressing", "Rain Blue", "mid", 38),
        ("Milan Records", "The Boy and the Heron OST (Joe Hisaishi) 2LP", "The Boy and the Heron", "EU/US Pressing", "Clear", "high", 55),
        ("Crunchyroll Records", "Frieren OST (Evan Call)", "Frieren", "US Pressing", "Frost White", "mid", 35),
        ("Crunchyroll Records", "Dandadan OST", "Dandadan", "US Pressing", "Okarun Yellow", "mid", 32),
        ("Crunchyroll Records", "Ranking of Kings OST (MAYUKO)", "Ranking of Kings", "US Pressing", "Crown Gold", "mid", 35),

        # ── Aniplex / Kadokawa — Additional Modern Anime ──────────────────
        ("Aniplex", "March Comes in Like a Lion OST (Yukari Hashimoto)", "March Comes in Like a Lion", "Japanese Pressing", "Black", "high", 58),
        ("Aniplex", "Puella Magi Madoka Magica: Rebellion OST (Yuki Kajiura)", "Madoka Magica: Rebellion", "Japanese Pressing", "Black", "high", 72),
        ("Kadokawa", "Ascendance of a Bookworm OST", "Ascendance of a Bookworm", "Japanese Pressing", "Black", "mid", 38),
        ("Aniplex", "Lycoris Recoil OST", "Lycoris Recoil", "Japanese Pressing", "Red/Blue Split", "mid", 48),
        ("Kadokawa", "The Apothecary Diaries OST (Kevin Penkin/Satoru Kosaki)", "Apothecary Diaries", "Japanese Pressing", "Black", "mid", 45),
        ("Aniplex", "Erased OST (Yuki Kajiura)", "Erased", "Japanese Pressing", "Blue Translucent", "high", 55),
        ("Pony Canyon", "Laid-Back Camp OST", "Laid-Back Camp", "Japanese Pressing", "Camping Green", "mid", 42),
        ("Aniplex", "A Place Further Than the Universe OST (Yoshiaki Fujisawa)", "A Place Further", "Japanese Pressing", "Antarctic Blue", "high", 60),

        # ── Classic / Vintage JP Vinyl (rare) ─────────────────────────────
        ("Nippon Columbia", "Fist of the North Star OST (Katsuhisa Hattori)", "Fist of the North Star", "Japanese OG Pressing", "Black", "grail", 170),
        ("King Records", "Touch OST (Yoshiyuki Nishi) 1985", "Touch", "Japanese OG Pressing", "Black", "grail", 110),
        ("Victor", "Urusei Yatsura: Only You OST (Fumitaka Anzai) 1983", "Urusei Yatsura", "Japanese OG Pressing", "Black", "grail", 130),
        ("Nippon Columbia", "Galaxy Express 999 OST (Nozomi Aoki) 1979", "Galaxy Express 999", "Japanese OG Pressing", "Black", "grail", 180),
        ("King Records", "Nadesico OST (Takayuki Hattori)", "Nadesico", "Japanese OG Pressing", "Black", "high", 75),
        ("Victor", "Outlaw Star OST", "Outlaw Star", "Japanese OG Pressing", "Black", "high", 70),
        ("Sunrise Music", "Gundam 08th MS Team OST", "Gundam 08th MS Team", "Japanese OG Pressing", "Black", "high", 80),
        ("Nippon Columbia", "Getter Robo OST (Shunsuke Kikuchi)", "Getter Robo", "Japanese OG Pressing", "Black", "grail", 155),

        # ── iam8bit / Boutique Expansion ──────────────────────────────────
        ("iam8bit", "Death Stranding OST (Ludvig Forssell) 3LP", "Death Stranding", "US Pressing", "BB Amber", "high", 65),
        ("iam8bit", "The Last Guardian OST (Takeshi Furukawa)", "The Last Guardian", "US Pressing", "Trico Feather Grey", "high", 55),
        ("iam8bit", "Sayonara Wild Hearts OST (Daniel Olsén)", "Sayonara Wild Hearts", "US Pressing", "Neon Pink", "mid", 45),
        ("iam8bit", "Journey OST (Austin Wintory) 10th Anniversary", "Journey", "US Pressing", "Gold Foil", "high", 68),
        ("iam8bit", "Katamari Damacy OST (Yuu Miyake) 2LP", "Katamari Damacy", "US Pressing", "Rainbow Splatter", "high", 60),
        ("iam8bit", "Monument Valley OST (Stafford Bawler)", "Monument Valley", "US Pressing", "Geometric Clear", "mid", 42),

        # ── Wayo Records Expansion ────────────────────────────────────────
        ("Wayo Records", "Castlevania: Dawn of Sorrow OST (Michiru Yamane)", "Castlevania: DoS", "EU Pressing", "Sunrise Orange", "high", 62),
        ("Wayo Records", "Okami OST (Masami Ueda) 4LP Box", "Okami", "EU Pressing", "Celestial White", "grail", 120),

        # ── Studio Ghibli – Complete Soundtracks (remaining titles) ──────
        ("Milan Records", "Arrietty Soundtrack (Cecile Corbel)", "Arrietty", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "Arrietty Soundtrack (Cecile Corbel)", "Arrietty", "EU/US Pressing", "Leaf Green", "high", 52),
        ("Milan Records", "When Marnie Was There Soundtrack (Takatsugu Muramatsu)", "When Marnie Was There", "EU/US Pressing", "Black", "mid", 32),
        ("Milan Records", "From Up on Poppy Hill Soundtrack (Satoshi Takebe)", "From Up on Poppy Hill", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "From Up on Poppy Hill Soundtrack (Satoshi Takebe)", "From Up on Poppy Hill", "EU/US Pressing", "Ocean Blue", "high", 50),
        ("Milan Records", "My Neighbors the Yamadas Soundtrack (Akiko Yano)", "My Neighbors the Yamadas", "EU/US Pressing", "Black", "mid", 35),
        ("Tokuma Japan", "Spirited Away OST (Original 2001 Pressing)", "Spirited Away", "Japanese OG Pressing", "Black", "grail", 190),
        ("Tokuma Japan", "Princess Mononoke OST (Original 1997 Pressing)", "Princess Mononoke", "Japanese OG Pressing", "Black", "grail", 200),
        ("Tokuma Japan", "Howl's Moving Castle OST (Original 2004 Pressing)", "Howl's Moving Castle", "Japanese OG Pressing", "Black", "grail", 175),
        ("Tokuma Japan", "Castle in the Sky OST (Original 1986 Pressing)", "Castle in the Sky", "Japanese OG Pressing", "Black", "grail", 210),
        ("Studio Ghibli Records", "Joe Hisaishi Meets Studio Ghibli (3LP Box)", "Studio Ghibli", "Japanese Pressing", "Black", "grail", 140),
        ("Studio Ghibli Records", "Earwig and the Witch Soundtrack (Satoshi Takebe)", "Earwig and the Witch", "Japanese Pressing", "Black", "mid", 35),
        ("Milan Records", "The Boy and the Heron Soundtrack (Joe Hisaishi) 2LP", "The Boy and the Heron", "EU/US Pressing", "Heron Grey Marble", "high", 60),
        ("Milan Records", "Porco Rosso Soundtrack (Joe Hisaishi)", "Porco Rosso", "EU/US Pressing", "Adriatic Blue", "high", 52),
        ("Milan Records", "Ponyo on the Cliff Soundtrack", "Ponyo", "EU/US Pressing", "Jellyfish Pink", "high", 50),
        ("Milan Records", "Nausicaa Image Album (Joe Hisaishi)", "Nausicaa", "EU/US Pressing", "Forest Green", "high", 55),

        # ── Dragon Ball – Complete Vinyl Discography ─────────────────────
        ("Columbia Japan", "Dragon Ball OST Vol.2 (Shunsuke Kikuchi)", "Dragon Ball", "Japanese OG Pressing", "Black", "grail", 105),
        ("Columbia Japan", "Dragon Ball Z Hit Song Collection Vol.1 (7\")", "Dragon Ball Z", "Japanese OG Pressing", "Black", "high", 60),
        ("Columbia Japan", "Dragon Ball Z Hit Song Collection Vol.2 (7\")", "Dragon Ball Z", "Japanese OG Pressing", "Black", "high", 58),
        ("Mondo", "Dragon Ball Z: History of Trunks OST", "Dragon Ball Z", "US Pressing", "Trunks Purple", "high", 52),
        ("Mondo", "Dragon Ball Z: Broly OST", "Dragon Ball Z", "US Pressing", "Legendary Green", "high", 55),
        ("Mondo", "Dragon Ball Super OST (Norihito Sumitomo) 2LP", "Dragon Ball Super", "US Pressing", "Ultra Instinct Silver", "high", 60),
        ("Columbia Japan", "Dragon Ball GT OST (Kazuhiko Toyama)", "Dragon Ball GT", "Japanese OG Pressing", "Black", "high", 65),

        # ── Naruto / Bleach / One Piece ──────────────────────────────────
        ("Aniplex", "Naruto Original Soundtrack (Toshio Masuda) 2LP", "Naruto", "Japanese Pressing", "Orange", "high", 70),
        ("Aniplex", "Naruto Shippuden OST (Yasuharu Takanashi) 2LP", "Naruto Shippuden", "Japanese Pressing", "Black", "high", 65),
        ("Aniplex", "Naruto Shippuden OST 2 (Yasuharu Takanashi)", "Naruto Shippuden", "Japanese Pressing", "Sage Green", "high", 62),
        ("Aniplex", "Naruto Shippuden OST 3 (Yasuharu Takanashi)", "Naruto Shippuden", "Japanese Pressing", "Kyuubi Red", "high", 65),
        ("Sony Music Japan", "Bleach Original Soundtrack (Shiro Sagisu) 2LP", "Bleach", "Japanese Pressing", "Black", "high", 72),
        ("Sony Music Japan", "Bleach Original Soundtrack 2 (Shiro Sagisu)", "Bleach", "Japanese Pressing", "Hollow White", "high", 68),
        ("Sony Music Japan", "Bleach Original Soundtrack 3 (Shiro Sagisu)", "Bleach", "Japanese Pressing", "Bankai Blue", "high", 70),
        ("Sony Music Japan", "Bleach: Thousand-Year Blood War OST (Shiro Sagisu) 2LP", "Bleach TYBW", "Japanese Pressing", "Quincy White", "high", 75),
        ("Toei Animation", "One Piece Original Soundtrack (Kohei Tanaka) 2LP", "One Piece", "Japanese Pressing", "Black", "high", 72),
        ("Toei Animation", "One Piece OST: New World (Kohei Tanaka/Shiro Hamaguchi)", "One Piece", "Japanese Pressing", "Grand Line Blue", "high", 68),
        ("Toei Animation", "One Piece Film: Red OST (Ado/Vaundy) 2LP", "One Piece Film: Red", "Japanese Pressing", "Shanks Red", "high", 80),

        # ── Attack on Titan – Complete ───────────────────────────────────
        ("Pony Canyon", "Attack on Titan OST (Hiroyuki Sawano) 2LP", "Attack on Titan", "Japanese Pressing", "Black", "high", 70),
        ("Pony Canyon", "Attack on Titan S2 OST (Hiroyuki Sawano)", "Attack on Titan S2", "Japanese Pressing", "Beast Titan Brown", "high", 65),
        ("Pony Canyon", "Attack on Titan S3 OST (Hiroyuki Sawano/Kohta Yamamoto)", "Attack on Titan S3", "Japanese Pressing", "Black", "high", 68),
        ("Mondo", "Attack on Titan Season 2 OST", "Attack on Titan", "US Pressing", "Colossal Titan Red", "high", 58),
        ("Mondo", "Attack on Titan Season 3 OST", "Attack on Titan", "US Pressing", "Survey Corps Green", "high", 55),
        ("Mondo", "Attack on Titan Final Season OST", "Attack on Titan", "US Pressing", "Rumbling Black/Red Split", "high", 62),

        # ── Demon Slayer – Complete ──────────────────────────────────────
        ("Aniplex", "Demon Slayer: Entertainment District OST (Yuki Kajiura/Go Shiina)", "Demon Slayer S2", "Japanese Pressing", "Tengen Flashy", "high", 65),
        ("Aniplex", "Demon Slayer: Swordsmith Village OST", "Demon Slayer S3", "Japanese Pressing", "Mist White", "high", 60),
        ("Aniplex", "Demon Slayer OST (Yuki Kajiura) Color Variant", "Demon Slayer", "Japanese Pressing", "Water Blue Splatter", "grail", 110),
        ("Mondo", "Demon Slayer: Entertainment District OST", "Demon Slayer S2", "US Pressing", "Uzui Gold", "high", 58),

        # ── Jujutsu Kaisen – Complete ────────────────────────────────────
        ("Crunchyroll Records", "Jujutsu Kaisen OST (Hiroaki Tsutsumi) Color", "Jujutsu Kaisen", "US Pressing", "Domain Purple", "high", 55),
        ("Aniplex", "Jujutsu Kaisen 0 Film OST (Hiroaki Tsutsumi/Arisa Okehazama)", "Jujutsu Kaisen 0", "Japanese Pressing", "Rika Purple", "high", 65),
        ("Aniplex", "Jujutsu Kaisen S2 Hidden Inventory OST", "Jujutsu Kaisen S2", "Japanese Pressing", "Gojo Blue/Purple Split", "high", 68),

        # ── Evangelion – Complete Vinyl ───────────────────────────────────
        ("King Records", "Evangelion: Death & Rebirth OST", "Evangelion", "Japanese Pressing", "Black", "high", 80),
        ("King Records", "End of Evangelion OST (Shiro Sagisu)", "Evangelion", "Japanese Pressing", "Black", "high", 85),
        ("King Records", "Evangelion 1.0 You Are (Not) Alone OST", "Evangelion Rebuild", "Japanese Pressing", "Black", "high", 70),
        ("King Records", "Evangelion 2.0 You Can (Not) Advance OST", "Evangelion Rebuild", "Japanese Pressing", "Black", "high", 72),
        ("King Records", "Evangelion 3.0 You Can (Not) Redo OST", "Evangelion Rebuild", "Japanese Pressing", "Red", "high", 75),
        ("King Records", "Evangelion 3.0+1.0 OST (Shiro Sagisu)", "Evangelion Rebuild", "Japanese Pressing", "Black", "high", 78),
        ("King Records", "Evangelion Original Soundtrack (2LP Reissue)", "Evangelion", "Reissue", "Eva Unit 01 Purple", "high", 55),

        # ── Cowboy Bebop – Remaining Albums ──────────────────────────────
        ("Tiger Lab Vinyl", "Cowboy Bebop No Disc (Seatbelts)", "Cowboy Bebop", "US Pressing", "Black", "mid", 40),
        ("Tiger Lab Vinyl", "Cowboy Bebop No Disc (Seatbelts)", "Cowboy Bebop", "US Pressing", "Purple Translucent", "high", 68),
        ("Tiger Lab Vinyl", "Cowboy Bebop Ask DNA (Seatbelts)", "Cowboy Bebop", "US Pressing", "Black", "mid", 38),
        ("Tiger Lab Vinyl", "Cowboy Bebop Ask DNA (Seatbelts)", "Cowboy Bebop", "US Pressing", "Green Translucent", "high", 65),
        ("Tiger Lab Vinyl", "Cowboy Bebop Cowgirl Ed (Seatbelts)", "Cowboy Bebop", "US Pressing", "Black", "mid", 38),
        ("Tiger Lab Vinyl", "Cowboy Bebop Cowgirl Ed (Seatbelts)", "Cowboy Bebop", "US Pressing", "Ed Orange", "high", 62),
        ("Flying Dog", "Cowboy Bebop Tank! CSS (7\" Single)", "Cowboy Bebop", "Japanese Pressing", "Black", "high", 85),
        ("Flying Dog", "Cowboy Bebop Vinyl Box Set (8LP)", "Cowboy Bebop", "Japanese Pressing", "Black", "grail", 350),

        # ── FLCL – Complete ──────────────────────────────────────────────
        ("Tiger Lab Vinyl", "FLCL OST 2 (The Pillows)", "FLCL", "US Pressing", "Black", "mid", 40),
        ("Tiger Lab Vinyl", "FLCL OST 2 (The Pillows)", "FLCL", "US Pressing", "Yellow Translucent", "high", 65),
        ("Tiger Lab Vinyl", "FLCL OST 3 (The Pillows)", "FLCL", "US Pressing", "Black", "mid", 40),
        ("Tiger Lab Vinyl", "FLCL OST 3 (The Pillows)", "FLCL", "US Pressing", "Pink Translucent", "high", 65),
        ("Tiger Lab Vinyl", "FLCL Progressive/Alternative OST", "FLCL Progressive", "US Pressing", "Black", "mid", 35),

        # ── Samurai Champloo – Remaining ─────────────────────────────────
        ("Tiger Lab Vinyl", "Samurai Champloo: Force of Nature", "Samurai Champloo", "US Pressing", "Black", "mid", 38),
        ("Tiger Lab Vinyl", "Samurai Champloo: Force of Nature", "Samurai Champloo", "US Pressing", "Forest Green", "high", 72),
        ("Tiger Lab Vinyl", "Samurai Champloo: Playlist", "Samurai Champloo", "US Pressing", "Black", "mid", 38),
        ("Tiger Lab Vinyl", "Samurai Champloo: Playlist", "Samurai Champloo", "US Pressing", "Blue Splatter", "high", 70),
        ("Tiger Lab Vinyl", "Samurai Champloo Music Record: Departure (Color)", "Samurai Champloo", "US Pressing", "Sunset Orange", "high", 72),
        ("Tiger Lab Vinyl", "Samurai Champloo Music Record: Impression (Color)", "Samurai Champloo", "US Pressing", "Mugen Red", "high", 72),

        # ── Final Fantasy – Complete Vinyl ───────────────────────────────
        ("Square Enix Music", "Final Fantasy VII Remake OST (Nobuo Uematsu/Masashi Hamauzu) 7LP", "FF VII Remake", "Japanese Pressing", "Black", "grail", 200),
        ("Square Enix Music", "Final Fantasy VIII OST (Nobuo Uematsu) 4LP", "Final Fantasy VIII", "Japanese Pressing", "Black", "grail", 150),
        ("Square Enix Music", "Final Fantasy IX OST (Nobuo Uematsu) 4LP", "Final Fantasy IX", "Japanese Pressing", "Black", "grail", 150),
        ("Square Enix Music", "Final Fantasy VI OST (Nobuo Uematsu) 3LP", "Final Fantasy VI", "Japanese Pressing", "Black", "grail", 140),
        ("Square Enix Music", "Final Fantasy IV OST (Nobuo Uematsu) 2LP", "Final Fantasy IV", "Japanese Pressing", "Black", "grail", 120),
        ("Square Enix Music", "Final Fantasy XV OST (Yoko Shimomura) 4LP", "Final Fantasy XV", "Japanese Pressing", "Black", "grail", 130),
        ("Square Enix Music", "Final Fantasy XVI OST (Masayoshi Soken) 4LP Box", "Final Fantasy XVI", "Japanese Pressing", "Clive Black", "grail", 140),
        ("Square Enix Music", "Final Fantasy VII Piano Collections (LP)", "Final Fantasy VII", "Japanese Pressing", "Black", "high", 65),

        # ── Zelda – Complete Vinyl ───────────────────────────────────────
        ("iam8bit", "Legend of Zelda: Ocarina of Time OST (Koji Kondo) 2LP", "Zelda: OoT", "US Pressing", "Gold Triforce", "grail", 120),
        ("iam8bit", "Legend of Zelda: Majora's Mask OST (2LP)", "Zelda: MM", "US Pressing", "Mask Purple", "grail", 110),
        ("iam8bit", "Legend of Zelda: Wind Waker OST (Kenta Nagata) 2LP", "Zelda: WW", "US Pressing", "Great Sea Blue", "grail", 105),
        ("iam8bit", "Legend of Zelda: Breath of the Wild OST (2LP)", "Zelda: BotW", "US Pressing", "Champion Blue", "grail", 110),
        ("iam8bit", "Legend of Zelda: Tears of the Kingdom OST (2LP)", "Zelda: TotK", "US Pressing", "Zonai Green", "grail", 115),
        ("iam8bit", "Legend of Zelda: A Link to the Past OST (Koji Kondo)", "Zelda: ALttP", "US Pressing", "Hyrule Gold", "high", 85),
        ("iam8bit", "Legend of Zelda: Link's Awakening OST", "Zelda: LA", "US Pressing", "Dreamer Blue", "high", 75),

        # ── Persona – Complete Vinyl ─────────────────────────────────────
        ("Atlus Music", "Persona 4 OST (Shoji Meguro) 3LP", "Persona 4", "Japanese Pressing", "TV Yellow", "grail", 130),
        ("Atlus Music", "Persona 3 Reload OST (Atsushi Kitajoh) 3LP", "Persona 3 Reload", "Japanese Pressing", "Reload Blue", "grail", 125),
        ("iam8bit", "Persona 5 Royal OST (Shoji Meguro) 3LP", "Persona 5 Royal", "US Pressing", "Royal Gold", "grail", 135),
        ("Wayo Records", "Persona 4 Golden OST (Shoji Meguro) 2LP", "Persona 4 Golden", "EU Pressing", "Golden Yellow", "high", 75),
        ("iam8bit", "Persona 5 Strikers OST (Atsushi Kitajoh) 2LP", "Persona 5 Strikers", "US Pressing", "Strikers Red", "high", 65),

        # ── NieR – Complete Vinyl ────────────────────────────────────────
        ("Square Enix Music", "NieR Replicant ver.1.22 OST (Keiichi Okabe) 4LP Box", "NieR Replicant", "Japanese Pressing", "White", "grail", 160),
        ("Wayo Records", "NieR: Automata Arranged & Unreleased 2LP", "NieR: Automata", "EU Pressing", "2B White/9S Black Split", "high", 72),
        ("Square Enix Music", "NieR: Automata Ver1.1a Anime OST", "NieR: Automata", "Japanese Pressing", "Black", "high", 65),
        ("Wayo Records", "NieR Orchestral Arrangement Album 2LP", "NieR", "EU Pressing", "Concert Clear", "high", 68),

        # ── Dark Souls / FromSoftware ────────────────────────────────────
        ("Laced Records", "Dark Souls Original Soundtrack (Motoi Sakuraba) 2LP", "Dark Souls", "EU Pressing", "Ember Orange", "high", 65),
        ("Laced Records", "Dark Souls II OST (Motoi Sakuraba) 2LP", "Dark Souls II", "EU Pressing", "Bonfire Amber", "high", 58),
        ("Laced Records", "Dark Souls III OST (Yuka Kitamura) 2LP", "Dark Souls III", "EU Pressing", "Ashen Grey", "high", 60),
        ("Laced Records", "Bloodborne OST (2LP)", "Bloodborne", "EU Pressing", "Hunter Red", "high", 68),
        ("Laced Records", "Elden Ring OST (Tsukasa Saitoh) 4LP Box", "Elden Ring", "EU Pressing", "Erdtree Gold", "grail", 115),
        ("Laced Records", "Sekiro: Shadows Die Twice OST (2LP)", "Sekiro", "EU Pressing", "Prosthetic Silver", "high", 58),
        ("Laced Records", "Demon's Souls OST (2LP)", "Demon's Souls", "EU Pressing", "Fog White", "high", 55),
        ("Laced Records", "Armored Core VI OST (2LP)", "Armored Core VI", "EU Pressing", "Mech Grey", "high", 60),

        # ── Hollow Knight / Undertale / Celeste / Indie ──────────────────
        ("iam8bit", "Hollow Knight OST (Christopher Larkin) 2LP", "Hollow Knight", "US Pressing", "Greenpath Green", "high", 58),
        ("iam8bit", "Hollow Knight: Gods & Nightmares OST", "Hollow Knight", "US Pressing", "Grimm Red", "high", 52),
        ("Fangamer", "Hollow Knight: Silksong OST (Christopher Larkin)", "Hollow Knight: Silksong", "Boutique Pressing", "Silk White", "high", 55),
        ("iam8bit", "Undertale Vinyl Soundtrack (Toby Fox) 2LP", "Undertale", "US Pressing", "Determination Red", "high", 58),
        ("Fangamer", "Deltarune OST (Toby Fox) 2LP", "Deltarune", "Boutique Pressing", "Dark World Purple", "high", 55),
        ("iam8bit", "Celeste OST (Lena Raine) 2LP", "Celeste", "US Pressing", "Summit White", "high", 55),
        ("Fangamer", "Celeste: Farewell OST (Lena Raine)", "Celeste", "Boutique Pressing", "Farewell Blue", "high", 50),
        ("Ship to Shore PhonoCo", "Shovel Knight OST (Jake Kaufman) 2LP", "Shovel Knight", "US Pressing", "Blue/Gold Splatter", "mid", 45),
        ("Supergiant Games", "Hades OST (Darren Korb) 4LP", "Hades", "Boutique Pressing", "Blood Red/Black Split", "high", 65),
        ("Supergiant Games", "Hades II OST (Darren Korb) 2LP", "Hades II", "Boutique Pressing", "Melinoe Purple", "high", 60),
        ("iam8bit", "Cuphead OST (Kristofer Maddigan) 4LP", "Cuphead", "US Pressing", "Inkwell Black", "high", 70),
        ("iam8bit", "Cuphead: Delicious Last Course OST (2LP)", "Cuphead DLC", "US Pressing", "Chef Gold", "high", 55),

        # ── Major Labels – Mondo Expansion ───────────────────────────────
        ("Mondo", "Ninja Scroll OST", "Ninja Scroll", "US Pressing", "Crimson Red", "high", 55),
        ("Mondo", "Vampire Hunter D: Bloodlust OST", "Vampire Hunter D", "US Pressing", "Gothic Purple", "high", 58),
        ("Mondo", "Redline OST (James Shimoji)", "Redline", "US Pressing", "Nitro Orange", "high", 60),
        ("Mondo", "Tekkonkinkreet OST (Plaid)", "Tekkonkinkreet", "US Pressing", "Black/White Split", "high", 55),
        ("Mondo", "Weathering with You OST (RADWIMPS)", "Weathering with You", "US Pressing", "Rain Blue Splatter", "high", 58),
        ("Mondo", "Princess Mononoke OST (Joe Hisaishi)", "Princess Mononoke", "US Pressing", "Forest Green", "high", 58),
        ("Mondo", "Totoro OST (Joe Hisaishi)", "My Neighbor Totoro", "US Pressing", "Totoro Grey", "high", 55),
        ("Mondo", "Howl's Moving Castle OST (Joe Hisaishi)", "Howl's Moving Castle", "US Pressing", "Sky Blue", "high", 55),
        ("Mondo", "Silent Hill 2 OST (Akira Yamaoka)", "Silent Hill 2", "US Pressing", "Fog White", "high", 65),
        ("Mondo", "Silent Hill OST (Akira Yamaoka)", "Silent Hill", "US Pressing", "Rust Red", "high", 60),
        ("Mondo", "Metal Gear Solid OST (Kazuki Muraoka/TAPPY)", "Metal Gear Solid", "US Pressing", "Tactical Grey", "high", 60),
        ("Mondo", "Castlevania: Symphony of the Night OST", "Castlevania: SotN", "US Pressing", "Alucard Silver", "high", 65),

        # ── Ship to Shore PhonoCo Expansion ──────────────────────────────
        ("Ship to Shore PhonoCo", "Mega Man 3 OST", "Mega Man 3", "US Pressing", "Red", "mid", 42),
        ("Ship to Shore PhonoCo", "Mega Man X OST", "Mega Man X", "US Pressing", "X-Hunter Blue", "high", 50),
        ("Ship to Shore PhonoCo", "Castlevania: Bloodlines OST", "Castlevania: Bloodlines", "US Pressing", "Blood Red", "high", 55),
        ("Ship to Shore PhonoCo", "Star Fox OST (Hajime Hirasawa)", "Star Fox", "US Pressing", "Arwing Silver", "high", 52),
        ("Ship to Shore PhonoCo", "Ninja Gaiden OST (Keiji Yamagishi)", "Ninja Gaiden", "US Pressing", "Ninja Black", "mid", 42),
        ("Ship to Shore PhonoCo", "F-Zero OST (Yumiko Kanki/Naoto Ishida)", "F-Zero", "US Pressing", "Blue Falcon Blue", "mid", 45),

        # ── Brave Wave ───────────────────────────────────────────────────
        ("Brave Wave", "Street Fighter II OST (Yoko Shimomura) 2LP", "Street Fighter II", "Boutique Pressing", "Hadouken Blue", "high", 55),
        ("Brave Wave", "Mega Man X2 OST", "Mega Man X2", "Boutique Pressing", "Flame Red", "mid", 48),
        ("Brave Wave", "Mega Man X3 OST", "Mega Man X3", "Boutique Pressing", "Zero Blonde", "mid", 48),
        ("Brave Wave", "Shovel Knight: Plague of Shadows OST", "Shovel Knight", "Boutique Pressing", "Plague Green", "mid", 38),

        # ── Light in the Attic Records ───────────────────────────────────
        ("Light in the Attic", "Kiki's Delivery Service OST (Joe Hisaishi) Reissue", "Kiki's Delivery Service", "US Pressing", "Black", "mid", 35),
        ("Light in the Attic", "City Pop on Vinyl: Anime Themes Compilation", "Various Anime", "US Pressing", "Neon Pink", "mid", 40),
        ("Light in the Attic", "Pacific Breeze Vol.1 (Anime-adjacent JP)", "Japanese Pop", "US Pressing", "Clear Blue", "mid", 42),
        ("Light in the Attic", "Pacific Breeze Vol.2", "Japanese Pop", "US Pressing", "Sunset Orange", "mid", 42),

        # ── Data Discs – Complete Game Catalog ───────────────────────────
        ("Data Discs", "Outrun OST (Hiroshi Kawaguchi)", "OutRun", "EU Pressing", "Ferrari Red", "high", 55),
        ("Data Discs", "Outrun OST (Hiroshi Kawaguchi)", "OutRun", "EU Pressing", "Black", "mid", 40),
        ("Data Discs", "After Burner II OST", "After Burner II", "EU Pressing", "Jet Blue", "mid", 42),
        ("Data Discs", "Super Hang-On OST", "Super Hang-On", "EU Pressing", "Racing Red", "mid", 40),
        ("Data Discs", "Space Harrier OST", "Space Harrier", "EU Pressing", "Fantasy Blue", "mid", 42),
        ("Data Discs", "Virtua Fighter OST", "Virtua Fighter", "EU Pressing", "Clear Blue", "mid", 40),
        ("Data Discs", "Thunder Force IV OST", "Thunder Force IV", "EU Pressing", "Lightning Yellow", "mid", 38),
        ("Data Discs", "Revenge of Shinobi OST (Yuzo Koshiro)", "Revenge of Shinobi", "EU Pressing", "Ninja Black", "high", 50),
        ("Data Discs", "Streets of Rage 4 OST (Olivier Deriviere) 2LP", "Streets of Rage 4", "EU Pressing", "Neon Green", "mid", 42),
        ("Data Discs", "Comix Zone OST", "Comix Zone", "EU Pressing", "Comic Yellow", "mid", 40),

        # ── Magical Girl Anime ───────────────────────────────────────────
        ("Columbia Japan", "Sailor Moon R Movie OST", "Sailor Moon", "Japanese OG Pressing", "Black", "high", 70),
        ("Columbia Japan", "Sailor Moon S OST (Takanori Arisawa)", "Sailor Moon", "Japanese OG Pressing", "Black", "high", 72),
        ("Columbia Japan", "Sailor Moon SuperS OST", "Sailor Moon", "Japanese OG Pressing", "Black", "high", 68),
        ("Columbia Japan", "Sailor Moon Stars OST", "Sailor Moon", "Japanese OG Pressing", "Black", "high", 70),
        ("King Records", "Cardcaptor Sakura OST (Takayuki Negishi)", "Cardcaptor Sakura", "Japanese OG Pressing", "Black", "high", 80),
        ("Lantis", "Puella Magi Madoka Magica OST (Yuki Kajiura) Reissue 2LP", "Madoka Magica", "Reissue", "Soul Gem Pink", "high", 55),
        ("Aniplex", "Madoka Magica: Rebellion OST (Yuki Kajiura)", "Madoka Magica: Rebellion", "Japanese Pressing", "Black", "high", 75),
        ("King Records", "Creamy Mami OST (Koji Makaino)", "Creamy Mami", "Japanese OG Pressing", "Black", "high", 85),
        ("King Records", "Minky Momo OST", "Minky Momo", "Japanese OG Pressing", "Black", "high", 80),
        ("King Records", "Ojamajo Doremi OST", "Ojamajo Doremi", "Japanese OG Pressing", "Black", "high", 65),

        # ── 80s/90s OVA Soundtracks ──────────────────────────────────────
        ("Victor", "Gunbuster OST (Kohei Tanaka)", "Gunbuster", "Japanese OG Pressing", "Black", "grail", 120),
        ("King Records", "Dangaioh OST", "Dangaioh", "Japanese OG Pressing", "Black", "high", 90),
        ("Youmex", "Bubblegum Crisis: Hurricane Live! 2032-2033", "Bubblegum Crisis", "Japanese OG Pressing", "Black", "high", 88),
        ("Youmex", "AD Police OST", "AD Police", "Japanese OG Pressing", "Black", "high", 80),
        ("Victor", "Riding Bean OST", "Riding Bean", "Japanese OG Pressing", "Black", "high", 85),
        ("Victor", "Iria: Zeiram OST", "Iria: Zeiram", "Japanese OG Pressing", "Black", "high", 75),
        ("Victor", "Birdy the Mighty OST", "Birdy the Mighty", "Japanese OG Pressing", "Black", "high", 70),
        ("King Records", "Appleseed OVA OST (1988)", "Appleseed", "Japanese OG Pressing", "Black", "high", 90),
        ("Kitty Records", "Armitage III OST", "Armitage III", "Japanese OG Pressing", "Black", "high", 80),
        ("Victor", "Angel Cop OST", "Angel Cop", "Japanese OG Pressing", "Black", "high", 85),
        ("Victor", "Cyber City Oedo 808 OST", "Cyber City Oedo 808", "Japanese OG Pressing", "Black", "high", 90),
        ("Victor", "Gall Force OST", "Gall Force", "Japanese OG Pressing", "Black", "high", 75),

        # ── Mecha Anime – Gundam & More ──────────────────────────────────
        ("King Records", "Gundam 0083: Stardust Memory OST", "Gundam 0083", "Japanese OG Pressing", "Black", "high", 85),
        ("King Records", "Victory Gundam OST (Chihiro Nobata)", "Victory Gundam", "Japanese OG Pressing", "Black", "high", 75),
        ("Sunrise Music", "G Gundam OST (Kohei Tanaka)", "G Gundam", "Japanese OG Pressing", "Black", "high", 70),
        ("Sunrise Music", "Gundam SEED OST (Toshihiko Sahashi)", "Gundam SEED", "Japanese Pressing", "Black", "high", 65),
        ("Bandai Namco Music", "Gundam Thunderbolt OST (Naruyoshi Kikuchi)", "Gundam Thunderbolt", "Japanese Pressing", "Jazz Black", "high", 70),
        ("Sunrise Music", "Gundam: Iron-Blooded Orphans OST (Masaru Yokoyama)", "Gundam IBO", "Japanese Pressing", "Barbatos Red", "high", 62),
        ("King Records", "Patlabor TV OST (Kenji Kawai)", "Patlabor", "Japanese OG Pressing", "Black", "high", 90),
        ("King Records", "Patlabor Movie OST (Kenji Kawai)", "Patlabor Movie", "Japanese OG Pressing", "Black", "grail", 120),
        ("Nippon Columbia", "Votoms OST (Hiroki Inui)", "Armored Trooper Votoms", "Japanese OG Pressing", "Black", "grail", 155),
        ("King Records", "Rahxephon OST (Ichiko Hashimoto)", "RahXephon", "Japanese Pressing", "Black", "high", 65),

        # ── Sports Anime ─────────────────────────────────────────────────
        ("Lantis", "Haikyuu!! OST (Yuki Hayashi) 2LP", "Haikyuu!!", "Japanese Pressing", "Karasuno Orange", "high", 58),
        ("Lantis", "Haikyuu!! S2 OST (Yuki Hayashi)", "Haikyuu!! S2", "Japanese Pressing", "Black", "high", 55),
        ("King Records", "Slam Dunk OST (Takanobu Masuda) Reissue", "Slam Dunk", "Reissue", "Black", "mid", 42),
        ("Aniplex", "Kuroko's Basketball OST (Yoshihiro Ike)", "Kuroko's Basketball", "Japanese Pressing", "Black", "mid", 40),
        ("Pony Canyon", "Blue Lock OST (Yutaka Yamada) 2LP", "Blue Lock", "Japanese Pressing", "Football Blue", "mid", 45),
        ("Avex Trax", "Initial D: Second Stage Eurobeat Selection", "Initial D", "Japanese OG Pressing", "Black", "high", 72),
        ("Avex Trax", "Initial D: Third Stage OST", "Initial D", "Japanese OG Pressing", "Black", "high", 68),

        # ── Additional iam8bit ───────────────────────────────────────────
        ("iam8bit", "Gris OST (Berlinist) LP", "Gris", "US Pressing", "Watercolor Splatter", "mid", 45),
        ("iam8bit", "Transistor OST (Darren Korb) 2LP", "Transistor", "US Pressing", "Red/Gold Split", "high", 55),
        ("iam8bit", "Bastion OST (Darren Korb) 2LP", "Bastion", "US Pressing", "Caelondia Brown", "high", 52),
        ("iam8bit", "What Remains of Edith Finch OST (Jeff Russo)", "Edith Finch", "US Pressing", "Twilight Purple", "mid", 40),
        ("iam8bit", "Hyper Light Drifter OST (Disasterpeace) 2LP", "Hyper Light Drifter", "US Pressing", "Neon Pink", "high", 55),
        ("iam8bit", "Fez OST (Disasterpeace) 2LP", "Fez", "US Pressing", "Cube Gold", "mid", 48),

        # ── Wayo Records Expansion ───────────────────────────────────────
        ("Wayo Records", "Dragon Quest III OST (Koichi Sugiyama) 2LP", "Dragon Quest III", "EU Pressing", "Hero Green", "high", 75),
        ("Wayo Records", "Dragon Quest V OST (Koichi Sugiyama) 2LP", "Dragon Quest V", "EU Pressing", "Black", "high", 70),
        ("Wayo Records", "Dragon Quest XI OST (Koichi Sugiyama) 3LP", "Dragon Quest XI", "EU Pressing", "Luminary Blue", "high", 80),
        ("Wayo Records", "Ace Attorney OST (Masakazu Sugimori) 2LP", "Ace Attorney", "EU Pressing", "Objection Red", "high", 62),
        ("Wayo Records", "Castlevania: Aria of Sorrow OST (Michiru Yamane)", "Castlevania: AoS", "EU Pressing", "Soul Silver", "high", 58),

        # ── Aniplex – Modern Anime Expansion ─────────────────────────────
        ("Aniplex", "Dororo OST (Yoshihiro Ike)", "Dororo", "Japanese Pressing", "Black", "mid", 48),
        ("Aniplex", "Promised Neverland OST (Takahiro Obata)", "Promised Neverland", "Japanese Pressing", "Black", "mid", 45),
        ("Aniplex", "Fire Force OST (Kenichiro Suehiro)", "Fire Force", "Japanese Pressing", "Infernal Red", "mid", 42),
        ("Aniplex", "Rascal Does Not Dream OST (fox capture plan)", "Bunny Girl Senpai", "Japanese Pressing", "Black", "mid", 48),
        ("Aniplex", "Toilet-Bound Hanako-kun OST", "Hanako-kun", "Japanese Pressing", "Ghost Teal", "mid", 38),
        ("Aniplex", "The Apothecary Diaries OST (Kevin Penkin/Satoru Kosaki)", "Apothecary Diaries", "Japanese Pressing", "Maomao Green", "high", 55),
        ("Aniplex", "Shangri-La Frontier OST", "Shangri-La Frontier", "Japanese Pressing", "Black", "mid", 38),
        ("Aniplex", "Wind Breaker OST", "Wind Breaker", "Japanese Pressing", "Black", "mid", 35),

        # ── Laced Records – Complete Game Catalog ────────────────────────
        ("Laced Records", "God of War (2018) OST (Bear McCreary) 2LP", "God of War", "EU Pressing", "Leviathan Blue", "high", 60),
        ("Laced Records", "God of War: Ragnarok OST (Bear McCreary) 3LP", "God of War: Ragnarok", "EU Pressing", "Fimbulwinter White", "high", 68),
        ("Laced Records", "Horizon Zero Dawn OST (Joris de Man) 4LP Box", "Horizon Zero Dawn", "EU Pressing", "Machine Blue", "grail", 100),
        ("Laced Records", "Horizon Forbidden West OST (Joris de Man) 3LP", "Horizon Forbidden West", "EU Pressing", "Forbidden Red", "high", 75),
        ("Laced Records", "Returnal OST (Bobby Krlic) 2LP", "Returnal", "EU Pressing", "Atropos Grey", "high", 55),
        ("Laced Records", "Uncharted: Legacy of Thieves OST (Henry Jackman) 2LP", "Uncharted", "EU Pressing", "Black", "high", 55),

        # ── Materia Collective ───────────────────────────────────────────
        ("Materia Collective", "Undertale Piano Collections (LP)", "Undertale", "Boutique Pressing", "Black", "mid", 38),
        ("Materia Collective", "Stardew Valley Piano Collections", "Stardew Valley", "Boutique Pressing", "Spring Green", "mid", 35),
        ("Materia Collective", "Chrono Trigger Tribute Album (2LP)", "Chrono Trigger", "Boutique Pressing", "Time Purple", "mid", 48),
        ("Materia Collective", "Earthbound Tribute Album (2LP)", "Earthbound", "Boutique Pressing", "Saturn Purple", "mid", 48),

        # ── Fangamer Expansion ───────────────────────────────────────────
        ("Fangamer", "Outer Wilds OST (Andrew Prahlow) 2LP", "Outer Wilds", "Boutique Pressing", "Supernova Orange", "high", 58),
        ("Fangamer", "Tunic OST (Lifeformed) LP", "Tunic", "Boutique Pressing", "Fox Orange", "mid", 38),
        ("Fangamer", "Stardew Valley OST (ConcernedApe) 2LP", "Stardew Valley", "Boutique Pressing", "Farm Green", "mid", 45),
        ("Fangamer", "Chicory: A Colorful Tale OST (Lena Raine)", "Chicory", "Boutique Pressing", "Rainbow Splatter", "mid", 42),
        ("Fangamer", "Ori and the Will of the Wisps OST (Gareth Coker) 2LP", "Ori WotW", "Boutique Pressing", "Wisps Blue", "high", 58),

        # ── Picture Discs & Glow-in-Dark Specials ────────────────────────
        ("Mondo", "Spirited Away (Picture Disc)", "Spirited Away", "Event Exclusive", "Picture Disc", "grail", 140),
        ("Mondo", "Totoro OST (Picture Disc)", "My Neighbor Totoro", "Event Exclusive", "Picture Disc", "grail", 130),
        ("Tiger Lab Vinyl", "Cowboy Bebop OST 1 (Glow-in-Dark)", "Cowboy Bebop", "Event Exclusive", "Glow-in-Dark Green", "grail", 120),
        ("Milan Records", "Nausicaa Soundtrack (Picture Disc)", "Nausicaa", "Event Exclusive", "Picture Disc", "grail", 135),
        ("iam8bit", "Zelda: Ocarina of Time (Glow-in-Dark 2LP)", "Zelda: OoT", "Event Exclusive", "Glow-in-Dark Green", "grail", 145),
        ("iam8bit", "Undertale (Glow-in-Dark)", "Undertale", "Event Exclusive", "Glow-in-Dark Blue", "grail", 110),
        ("Data Discs", "Streets of Rage 2 (Picture Disc)", "Streets of Rage", "Event Exclusive", "Picture Disc", "grail", 105),
        ("Data Discs", "Jet Set Radio (Glow-in-Dark Splatter)", "Jet Set Radio", "Event Exclusive", "Glow-in-Dark Yellow", "grail", 120),

        # ── Milan Records – Anime Film Expansion ─────────────────────────
        ("Milan Records", "Suzume OST (RADWIMPS/Kazuma Jinnouchi) 2LP", "Suzume", "EU/US Pressing", "Door Blue", "high", 55),
        ("Milan Records", "Your Name OST (RADWIMPS) Color", "Your Name", "EU/US Pressing", "Comet Red/Blue Split", "high", 58),
        ("Milan Records", "Belle OST (Millennium Parade)", "Belle", "EU Pressing", "Rose Pink", "mid", 38),
        ("Milan Records", "Ghost in the Shell 2: Innocence OST (Kenji Kawai)", "GiTS 2: Innocence", "EU Pressing", "Black", "mid", 42),
        ("Milan Records", "Akira Kaneda Bike Red Variant", "Akira", "EU Pressing", "Kaneda Red", "high", 65),

        # ── Crunchyroll Records Expansion ────────────────────────────────
        ("Crunchyroll Records", "Hell's Paradise OST", "Hell's Paradise", "US Pressing", "Tao Green", "mid", 32),
        ("Crunchyroll Records", "Mashle OST", "Mashle", "US Pressing", "Cream Puff Tan", "standard", 24),
        ("Crunchyroll Records", "Zom 100 OST", "Zom 100", "US Pressing", "Zombie Green", "standard", 22),
        ("Crunchyroll Records", "Heavenly Delusion OST", "Heavenly Delusion", "US Pressing", "Black", "mid", 28),
        ("Crunchyroll Records", "Kaiju No. 8 OST", "Kaiju No. 8", "US Pressing", "Monster Blue", "mid", 32),
        ("Crunchyroll Records", "Tower of God OST", "Tower of God", "US Pressing", "Black", "mid", 28),
        ("Crunchyroll Records", "The Eminence in Shadow OST", "Eminence in Shadow", "US Pressing", "Shadow Purple", "mid", 30),

        # ── Square Enix – Remaining VGM ──────────────────────────────────
        ("Square Enix Music", "Chrono Trigger OST (Yasunori Mitsuda) 3LP", "Chrono Trigger", "Japanese Pressing", "Black", "grail", 160),
        ("Square Enix Music", "Secret of Mana OST (Hiroki Kikuta) 2LP", "Secret of Mana", "Japanese Pressing", "Mana Tree Green", "grail", 110),
        ("Square Enix Music", "Xenogears OST (Yasunori Mitsuda) 3LP", "Xenogears", "Japanese Pressing", "Gear Gold", "grail", 140),
        ("Square Enix Music", "Front Mission OST (Yoko Shimomura)", "Front Mission", "Japanese Pressing", "Black", "high", 70),
        ("Square Enix Music", "Valkyrie Profile OST (Motoi Sakuraba) 2LP", "Valkyrie Profile", "Japanese Pressing", "Black", "high", 75),
        ("Square Enix Music", "Dragon Quest VIII OST (Koichi Sugiyama) 3LP", "Dragon Quest VIII", "Japanese Pressing", "Black", "grail", 120),
        ("Square Enix Music", "Trials of Mana Remake OST 2LP", "Trials of Mana", "Japanese Pressing", "Black", "high", 65),

        # ── Additional Japanese Label Releases ───────────────────────────
        ("Kadokawa", "The Melancholy of Haruhi Suzumiya OST", "Haruhi Suzumiya", "Japanese OG Pressing", "Black", "high", 80),
        ("Kadokawa", "Lucky Star OST (Satoru Kosaki)", "Lucky Star", "Japanese OG Pressing", "Black", "high", 65),
        ("Lantis", "K-ON! OST (Hajime Hyakkoku)", "K-ON!", "Japanese Pressing", "Tea Time Brown", "high", 70),
        ("Pony Canyon", "Toradora! OST", "Toradora!", "Japanese OG Pressing", "Black", "high", 65),
        ("Pony Canyon", "Steins;Gate OST (Takeshi Abo)", "Steins;Gate", "Japanese Pressing", "Lab Coat White", "high", 75),
        ("Pony Canyon", "Clannad OST (Jun Maeda/Magome Togoshi)", "Clannad", "Japanese Pressing", "Black", "high", 68),
        ("Aniplex", "Angel Beats! OST (Jun Maeda/ANANT-GARDE EYES)", "Angel Beats!", "Japanese Pressing", "Black", "high", 62),
        ("Aniplex", "Anohana OST (REMEDIOS)", "Anohana", "Japanese Pressing", "Clear", "high", 58),
        ("Aniplex", "Your Lie in April OST (Masaru Yokoyama) Color", "Your Lie in April", "Japanese Pressing", "Piano White", "high", 62),
        ("Kadokawa", "No Game No Life OST (Yoshino Nanjo/SUZUKI Konomi)", "No Game No Life", "Japanese Pressing", "Game Board Multi", "high", 60),

        # ── Classic Shonen Jump – Remaining ──────────────────────────────
        ("Columbia Japan", "Saint Seiya: Soldiers' Dream (7\" Single)", "Saint Seiya", "Japanese OG Pressing", "Black", "high", 55),
        ("Sunrise Music", "Inuyasha: The Final Act OST", "Inuyasha", "Japanese Pressing", "Black", "high", 58),
        ("Victor", "Hunter x Hunter (1999) OST", "Hunter x Hunter", "Japanese OG Pressing", "Black", "high", 75),
        ("VAP", "Hunter x Hunter (2011) OST (Yoshihisa Hirano)", "Hunter x Hunter (2011)", "Japanese Pressing", "Black", "high", 65),
        ("Aniplex", "Black Clover OST (Minako Seki)", "Black Clover", "Japanese Pressing", "Grimoire Black", "mid", 42),
        ("Aniplex", "Mob Psycho 100 II OST (Kenji Kawai)", "Mob Psycho 100 II", "Japanese Pressing", "Psycho Blue", "high", 60),
        ("Aniplex", "Mob Psycho 100 III OST (Kenji Kawai)", "Mob Psycho 100 III", "Japanese Pressing", "Dimple Green", "high", 55),
        ("Aniplex", "Assassination Classroom OST (Naoki Sato)", "Assassination Classroom", "Japanese Pressing", "Black", "mid", 42),

        # ── Vinyl Me Please – Additional Anime ──────────────────────────
        ("Vinyl Me Please", "Spirited Away OST (VMP Exclusive)", "Spirited Away", "US Pressing", "Bathhouse Steam Clear", "grail", 130),
        ("Vinyl Me Please", "Ghost in the Shell OST (VMP Exclusive)", "Ghost in the Shell", "US Pressing", "Cyber Teal", "grail", 120),
        ("Vinyl Me Please", "Your Name OST (VMP Exclusive)", "Your Name", "US Pressing", "Taki & Mitsuha Split", "grail", 115),

        # ── Box Sets & Deluxe Editions ───────────────────────────────────
        ("Tiger Lab Vinyl", "Samurai Champloo Complete Box Set (6LP)", "Samurai Champloo", "US Pressing", "Black", "grail", 200),
        ("Mondo", "Akira Deluxe Box Set (3LP)", "Akira", "US Pressing", "Neo-Tokyo Splatter", "grail", 180),
        ("Mondo", "Attack on Titan Complete Box Set (6LP)", "Attack on Titan", "US Pressing", "Black", "grail", 200),
        ("Milan Records", "Studio Ghibli Complete Piano Collection (4LP Box)", "Studio Ghibli", "EU/US Pressing", "Black", "grail", 140),
        ("King Records", "Evangelion Complete Box Set (8LP)", "Evangelion", "Japanese Pressing", "NERV Black", "grail", 250),
        ("Square Enix Music", "Final Fantasy VII Remake & Rebirth OST Box (10LP)", "FF VII Remake", "Japanese Pressing", "Mako Green", "grail", 280),
        ("Aniplex", "Demon Slayer Complete Series OST Box Set (6LP)", "Demon Slayer", "Japanese Pressing", "Flame Red/Water Blue", "grail", 220),
        ("Wayo Records", "Persona 5/Royal/Strikers Complete Box (8LP)", "Persona 5", "EU Pressing", "Joker Red", "grail", 250),

        # ── Kadokawa / Pony Canyon Modern ────────────────────────────────
        ("Kadokawa", "That Time I Got Reincarnated as a Slime S2 OST", "TenSura S2", "Japanese Pressing", "Black", "mid", 40),
        ("Kadokawa", "Cautious Hero OST", "Cautious Hero", "Japanese Pressing", "Black", "standard", 22),
        ("Kadokawa", "Combatants Will Be Dispatched! OST", "Combatants", "Japanese Pressing", "Black", "standard", 20),
        ("Pony Canyon", "Ousama Ranking S2 OST (MAYUKO)", "Ranking of Kings S2", "Japanese Pressing", "Black", "mid", 35),
        ("Pony Canyon", "Skip and Loafer OST", "Skip and Loafer", "Japanese Pressing", "Black", "mid", 30),
        ("Pony Canyon", "A Sign of Affection OST", "A Sign of Affection", "Japanese Pressing", "Clear Pink", "mid", 32),

        # ── Additional Retro Anime ───────────────────────────────────────
        ("King Records", "Legend of the Galactic Heroes OST (Mitsuo Hagita)", "LotGH", "Japanese OG Pressing", "Black", "grail", 180),
        ("Nippon Columbia", "Future Boy Conan OST", "Future Boy Conan", "Japanese OG Pressing", "Black", "grail", 160),
        ("Victor", "Giant Robo OST (Toshiyuki Watanabe)", "Giant Robo", "Japanese OG Pressing", "Black", "grail", 130),
        ("King Records", "Banner of the Stars OST", "Banner of the Stars", "Japanese OG Pressing", "Black", "high", 75),
        ("King Records", "Blue Seed OST", "Blue Seed", "Japanese OG Pressing", "Black", "high", 65),
        ("King Records", "Sorcerer Hunters OST", "Sorcerer Hunters", "Japanese OG Pressing", "Black", "high", 60),

        # ── Additional Classics & Missing Titles ─────────────────────────
        ("Nippon Columbia", "Captain Harlock OST (Seiji Yokoyama) 1978", "Captain Harlock", "Japanese OG Pressing", "Black", "grail", 210),
        ("King Records", "Orguss OST (1983)", "Orguss", "Japanese OG Pressing", "Black", "grail", 130),
        ("Victor", "Macross: Do You Remember Love? OST (1984)", "Macross DYRL", "Japanese OG Pressing", "Black", "grail", 200),
        ("Geneon", "Serial Experiments Lain OST (Reichi Nakaido)", "Serial Experiments Lain", "Japanese OG Pressing", "Black", "grail", 250),
        ("VAP", "Berserk Original Soundtrack (Susumu Hirasawa)", "Berserk", "Japanese OG Pressing", "Black", "grail", 175),
        ("Mondo", "Berserk: Golden Age OST", "Berserk", "US Pressing", "Crimson Red", "high", 58),
        ("Mondo", "Trigun Stampede OST", "Trigun Stampede", "US Pressing", "Desert Tan", "mid", 42),
        ("Aniplex", "Spy x Family S2 OST ((K)NoW_NAME)", "Spy x Family S2", "Japanese Pressing", "Black", "mid", 40),
        ("Aniplex", "Frieren: Beyond Journey's End OST (Evan Call) 2LP", "Frieren", "Japanese Pressing", "Elven Silver", "high", 65),
        ("Mondo", "Pluto OST (Yugo Kanno)", "Pluto", "US Pressing", "Black", "mid", 38),

        # --- Round 7 additions (60 items) ---

        # ── Studio Ghibli — Remaining Joe Hisaishi Titles ──────────────────
        ("Milan Records", "Grave of the Fireflies Soundtrack (Michio Mamiya)", "Grave of the Fireflies", "EU/US Pressing", "Black", "mid", 38),
        ("Milan Records", "Grave of the Fireflies Soundtrack (Michio Mamiya)", "Grave of the Fireflies", "EU/US Pressing", "Firefly Amber", "high", 58),
        ("Milan Records", "Ocean Waves Soundtrack (Shigeru Nagata)", "Ocean Waves", "EU/US Pressing", "Black", "mid", 32),
        ("Milan Records", "Only Yesterday Soundtrack (Katz Hoshi)", "Only Yesterday", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "Whisper of the Heart Soundtrack (Yuji Nomi)", "Whisper of the Heart", "EU/US Pressing", "Black", "mid", 32),
        ("Milan Records", "Whisper of the Heart Soundtrack (Yuji Nomi)", "Whisper of the Heart", "EU/US Pressing", "Antique Amber", "high", 52),
        ("Milan Records", "Pom Poko Soundtrack (Shang Shang Typhoon)", "Pom Poko", "EU/US Pressing", "Black", "mid", 30),

        # ── Sailor Moon — Complete Vinyl ────────────────────────────────────
        ("Columbia Japan", "Sailor Moon S Movie: Hearts in Ice OST", "Sailor Moon", "Japanese OG Pressing", "Black", "high", 68),
        ("Columbia Japan", "Sailor Moon Sailor Stars Song Collection", "Sailor Moon", "Japanese OG Pressing", "Black", "high", 72),
        ("Columbia Japan", "Sailor Moon Crystal OST (Yasuharu Takanashi)", "Sailor Moon Crystal", "Japanese Pressing", "Crystal Clear", "high", 60),

        # ── Macross — Complete Vinyl ────────────────────────────────────────
        ("Victor", "Macross Original Soundtrack (1982)", "Macross", "Japanese OG Pressing", "Black", "grail", 170),
        ("King Records", "Macross 7 OST (Fire Bomber)", "Macross 7", "Japanese OG Pressing", "Black", "high", 85),
        ("Flying Dog", "Macross Delta OST (JUNNA/Walkure)", "Macross Delta", "Japanese Pressing", "Walkure Pink", "high", 62),
        ("Flying Dog", "Macross Plus Movie Edition OST (Yoko Kanno)", "Macross Plus", "Japanese Pressing", "Sharon Apple Silver", "high", 78),

        # ── Dragon Ball — Additional Releases ──────────────────────────────
        ("Columbia Japan", "Dragon Ball Z BGM Collection (Shunsuke Kikuchi)", "Dragon Ball Z", "Japanese OG Pressing", "Black", "high", 65),
        ("Columbia Japan", "Dragon Ball Kai OST (Kenji Yamamoto)", "Dragon Ball Kai", "Japanese Pressing", "Black", "high", 55),
        ("Mondo", "Dragon Ball Z: Cooler's Revenge OST", "Dragon Ball Z", "US Pressing", "Cooler Purple", "high", 50),

        # ── Trigun / Berserk / 90s Classics ────────────────────────────────
        ("Victor", "Trigun OST (Tsuneo Imahori)", "Trigun", "Japanese OG Pressing", "Black", "grail", 120),
        ("Geneon", "Trigun OST 2: The Second Donut Happy Pack", "Trigun", "Japanese OG Pressing", "Black", "high", 85),
        ("VAP", "Berserk: Forces OST (Susumu Hirasawa)", "Berserk", "Japanese OG Pressing", "Black", "grail", 160),
        ("Aniplex", "Berserk Memorial Edition OST 2LP", "Berserk", "Japanese Pressing", "Eclipse Red", "high", 68),

        # ── Additional Modern Anime — 2023-2025 Releases ──────────────────
        ("Aniplex", "Oshi no Ko OST (Akari Daimon) 2LP", "Oshi no Ko", "Japanese Pressing", "Star White/Purple Split", "high", 62),
        ("Crunchyroll Records", "Solo Leveling OST (Hiroyuki Sawano)", "Solo Leveling", "US Pressing", "Shadow Black/Purple", "high", 55),
        ("Aniplex", "Demon Slayer: Infinity Castle OST (Yuki Kajiura) 2LP", "Demon Slayer", "Japanese Pressing", "Infinity Purple", "high", 68),
        ("Crunchyroll Records", "Sakamoto Days OST", "Sakamoto Days", "US Pressing", "Hitman Grey", "mid", 32),
        ("Pony Canyon", "Delicious in Dungeon OST (Yasunori Mitsuda)", "Delicious in Dungeon", "Japanese Pressing", "Dungeon Gold", "high", 58),
        ("Aniplex", "The Elusive Samurai OST", "Elusive Samurai", "Japanese Pressing", "Black", "mid", 38),

        # ── Yu Yu Hakusho / Classic Jump Anime ─────────────────────────────
        ("Victor", "Yu Yu Hakusho OST Vol.2 (Yusuke Honma)", "Yu Yu Hakusho", "Japanese OG Pressing", "Black", "high", 62),
        ("Victor", "Yu Yu Hakusho Song Collection (7\" Single)", "Yu Yu Hakusho", "Japanese OG Pressing", "Black", "high", 55),
        ("Aniplex", "Rurouni Kenshin: Meiji Swordsman OST (Noriyuki Asakura)", "Rurouni Kenshin", "Japanese OG Pressing", "Black", "high", 65),

        # ── Gundam — Additional Releases ───────────────────────────────────
        ("Sunrise Music", "Mobile Suit Zeta Gundam OST (Shigeaki Saegusa)", "Zeta Gundam", "Japanese OG Pressing", "Black", "grail", 130),
        ("King Records", "Gundam ZZ OST (Shigeaki Saegusa)", "Gundam ZZ", "Japanese OG Pressing", "Black", "high", 90),
        ("Bandai Namco Music", "Gundam: Witch from Mercury OST (Takashi Ohmama)", "Gundam WfM", "Japanese Pressing", "Aerial White", "high", 58),
        ("Sunrise Music", "Gundam Wing OST (Kow Otani)", "Gundam Wing", "Japanese OG Pressing", "Black", "high", 75),
        ("Sunrise Music", "Turn A Gundam OST (Yoko Kanno)", "Turn A Gundam", "Japanese OG Pressing", "Black", "grail", 110),

        # ── Sports / Slice-of-Life Anime ───────────────────────────────────
        ("Pony Canyon", "Yuri!!! on Ice OST (Taro Umebayashi/Taku Matsushiba)", "Yuri!!! on Ice", "Japanese Pressing", "Ice Blue", "high", 65),
        ("Lantis", "Free! OST (Tatsuya Kato)", "Free!", "Japanese Pressing", "Pool Blue", "mid", 45),
        ("Aniplex", "Violet Evergarden OST (Evan Call) 2LP", "Violet Evergarden", "Japanese Pressing", "Violet Purple", "high", 68),

        # ── Additional Laced Records ───────────────────────────────────────
        ("Laced Records", "Ghost of Tsushima OST (Ilan Eshkeri/Shigeru Umebayashi) 3LP", "Ghost of Tsushima", "EU Pressing", "Samurai Red", "high", 75),
        ("Laced Records", "Final Fantasy VII Rebirth OST (Masayoshi Soken) 4LP Box", "FF VII Rebirth", "EU Pressing", "Reunion Blue", "grail", 130),
        ("Laced Records", "Shadow of the Colossus OST (Kow Otani) 2LP", "Shadow of the Colossus", "EU Pressing", "Colossal Grey", "high", 62),
        ("Laced Records", "The Last of Us Part I OST (Gustavo Santaolalla) 2LP", "The Last of Us", "EU Pressing", "Spore Green", "high", 60),

        # ── Additional Fangamer / Boutique ─────────────────────────────────
        ("Fangamer", "Shovel Knight: Specter of Torment OST (Jake Kaufman)", "Shovel Knight", "Boutique Pressing", "Specter Blue", "mid", 40),
        ("Fangamer", "Sea of Stars OST (Yasunori Mitsuda) 2LP", "Sea of Stars", "Boutique Pressing", "Eclipse Purple", "high", 55),
        ("Fangamer", "Eastward OST (Joel Corelitz)", "Eastward", "Boutique Pressing", "Pixel Green", "mid", 38),

        # ── Additional Event Exclusives ────────────────────────────────────
        ("Mondo", "Cowboy Bebop OST (SDCC Exclusive)", "Cowboy Bebop", "Event Exclusive", "Jet Black/White Split", "grail", 135),
        ("Tiger Lab Vinyl", "Samurai Champloo (Anime Expo 2024)", "Samurai Champloo", "Event Exclusive", "Mugen Blue/Jin Silver", "grail", 130),
        ("Milan Records", "Totoro OST (RSD 2025)", "My Neighbor Totoro", "RSD Exclusive", "Camphor Tree Green", "grail", 115),
        ("Aniplex", "Madoka Magica OST (MadoFes Exclusive)", "Madoka Magica", "Event Exclusive", "Soul Gem Rainbow Splatter", "grail", 145),

        # ── Classic OVA / 80s-90s Rarities ─────────────────────────────────
        ("Victor", "Megazone 23 OST (Shiro Sagisu)", "Megazone 23", "Japanese OG Pressing", "Black", "grail", 140),
        ("King Records", "Dirty Pair: Project Eden OST (Epo)", "Dirty Pair", "Japanese OG Pressing", "Black", "high", 80),
        ("King Records", "Vampire Hunter D OST (Noriyoshi Matsuura) 1985", "Vampire Hunter D", "Japanese OG Pressing", "Black", "grail", 150),
        ("Youmex", "Gall Force: Eternal Story OST", "Gall Force", "Japanese OG Pressing", "Black", "high", 78),
        ("King Records", "Record of Lodoss War OST (Hitoshi Sakimoto)", "Record of Lodoss War", "Japanese OG Pressing", "Black", "grail", 130),

        # ── Tiger Lab Vinyl — 2024-2025 New Releases ────────────────────
        ("Tiger Lab Vinyl", "Serial Experiments Lain OST (Remastered)", "Serial Experiments Lain", "US Pressing", "Clear Purple", "high", 75),
        ("Tiger Lab Vinyl", "Paprika OST (Susumu Hirasawa)", "Paprika", "US Pressing", "Red Swirl", "high", 80),
        ("Tiger Lab Vinyl", "Wolf's Rain OST (Yoko Kanno)", "Wolf's Rain", "US Pressing", "Black", "mid", 42),
        ("Tiger Lab Vinyl", "Ergo Proxy OST", "Ergo Proxy", "US Pressing", "Smoke Grey", "mid", 45),
        ("Tiger Lab Vinyl", "Texhnolyze OST (Hajime Mizoguchi)", "Texhnolyze", "US Pressing", "Black", "mid", 40),
        ("Tiger Lab Vinyl", "Paranoia Agent OST (Susumu Hirasawa)", "Paranoia Agent", "US Pressing", "Orange Marble", "high", 72),
        ("Tiger Lab Vinyl", "Darker Than Black OST", "Darker Than Black", "US Pressing", "Black", "mid", 38),
        ("Tiger Lab Vinyl", "Michiko & Hatchin OST (Kassin)", "Michiko & Hatchin", "US Pressing", "Gold Translucent", "high", 65),

        # ── Mondo — Anime Pressings ─────────────────────────────────────
        ("Mondo", "Akira Symphonic Suite (Geinoh Yamashirogumi) Deluxe 2xLP", "Akira", "US Pressing", "Neon Blue/Pink Splatter", "grail", 180),
        ("Mondo", "Perfect Blue OST (Masahiro Ikumi)", "Perfect Blue", "US Pressing", "Clear w/ Red Splatter", "grail", 200),
        ("Mondo", "Vampire Hunter D: Bloodlust OST", "Vampire Hunter D", "US Pressing", "Blood Red", "high", 90),
        ("Mondo", "Belladonna of Sadness OST (Masahiko Satoh)", "Belladonna of Sadness", "US Pressing", "Pink Marble", "high", 85),
        ("Mondo", "Dragon Ball Z – Bruce Faulconer Score Vol. 1", "Dragon Ball Z", "US Pressing", "Orange/Blue Split", "high", 70),
        ("Mondo", "Demon Slayer: Kimetsu no Yaiba S1 OST", "Demon Slayer", "US Pressing", "Water Breathing Blue", "high", 75),
        ("Mondo", "Attack on Titan Season 4 OST (Kohta Yamamoto)", "Attack on Titan", "US Pressing", "Crimson Red", "high", 80),
        ("Mondo", "Neon Genesis Evangelion OST (Shiro Sagisu) 2xLP", "Evangelion", "US Pressing", "Lilith Purple Splatter", "grail", 160),

        # ── Light in the Attic — City Pop Reissues ──────────────────────
        ("Light in the Attic", "Tatsuro Yamashita — FOR YOU (Reissue)", "City Pop", "US Pressing", "Black", "high", 55),
        ("Light in the Attic", "Tatsuro Yamashita — RIDE ON TIME (Reissue)", "City Pop", "US Pressing", "Black", "high", 58),
        ("Light in the Attic", "Mariya Takeuchi — Variety (Reissue)", "City Pop", "US Pressing", "Pink Vinyl", "high", 65),
        ("Light in the Attic", "Taeko Ohnuki — Sunshower (Reissue)", "City Pop", "US Pressing", "Black", "mid", 48),
        ("Light in the Attic", "Haruomi Hosono — Hosono House (Reissue)", "City Pop", "US Pressing", "Black", "mid", 42),
        ("Light in the Attic", "Minako Yoshida — Light'n Up (Reissue)", "City Pop", "US Pressing", "Clear", "mid", 45),
        ("Light in the Attic", "Akiko Yano — Tadaima (Reissue)", "City Pop", "US Pressing", "Black", "mid", 40),
        ("Light in the Attic", "Toshiki Kadomatsu — Sea Breeze (Reissue)", "City Pop", "US Pressing", "Blue Translucent", "high", 60),

        # ── Data Discs — Game/Anime Crossover ───────────────────────────
        ("Data Discs", "Sonic the Hedgehog OST (Masato Nakamura)", "Sonic", "EU Pressing", "Classic Blue", "high", 55),
        ("Data Discs", "Sonic the Hedgehog 2 OST", "Sonic", "EU Pressing", "Gold Translucent", "high", 60),
        ("Data Discs", "Streets of Rage 2 OST (Yuzo Koshiro)", "Streets of Rage", "EU Pressing", "Red Translucent", "high", 65),
        ("Data Discs", "Streets of Rage 3 OST", "Streets of Rage", "EU Pressing", "Green/Purple Splatter", "high", 58),
        ("Data Discs", "Shenmue OST (Takenobu Mitsuyoshi)", "Shenmue", "EU Pressing", "Cherry Blossom Pink", "high", 70),
        ("Data Discs", "Shenmue II OST", "Shenmue", "EU Pressing", "Orange Translucent", "high", 65),
        ("Data Discs", "OutRun OST (Hiroshi Kawaguchi)", "OutRun", "EU Pressing", "Sunset Orange/Pink", "high", 55),
        ("Data Discs", "Panzer Dragoon OST", "Panzer Dragoon", "EU Pressing", "Dragon Green", "high", 60),

        # ── Wayô Records — Game/Anime Piano & Orchestral ────────────────
        ("Wayô Records", "NieR: Automata Piano Collections", "NieR", "EU Pressing", "Black", "high", 55),
        ("Wayô Records", "NieR Gestalt & Replicant OST 2xLP", "NieR", "EU Pressing", "White", "high", 70),
        ("Wayô Records", "Final Fantasy VII Piano Collections", "Final Fantasy", "EU Pressing", "Black", "high", 60),
        ("Wayô Records", "Final Fantasy X Piano Collections", "Final Fantasy", "EU Pressing", "Black", "mid", 48),
        ("Wayô Records", "Chrono Cross OST (Yasunori Mitsuda) 2xLP", "Chrono Cross", "EU Pressing", "Sea Blue", "high", 75),
        ("Wayô Records", "Xenoblade Chronicles OST (Yoko Shimomura)", "Xenoblade", "EU Pressing", "Green Translucent", "high", 65),
        ("Wayô Records", "Kingdom Hearts Piano Collections", "Kingdom Hearts", "EU Pressing", "Black", "mid", 50),
        ("Wayô Records", "Dragon Quest XI Symphonic Suite", "Dragon Quest", "EU Pressing", "Black", "high", 55),

        # ── Ship to Shore PhonoCo ────────────────────────────────────────
        ("Ship to Shore", "Castlevania: Symphony of the Night OST 2xLP", "Castlevania", "US Pressing", "Bat Wing Purple", "grail", 130),
        ("Ship to Shore", "Castlevania III: Dracula's Curse OST", "Castlevania", "US Pressing", "Blood Red", "high", 65),
        ("Ship to Shore", "Silent Hill OST (Akira Yamaoka)", "Silent Hill", "US Pressing", "Fog Grey", "grail", 140),
        ("Ship to Shore", "Silent Hill 2 OST (Akira Yamaoka) 2xLP", "Silent Hill", "US Pressing", "Clear w/ Red Splatter", "grail", 160),
        ("Ship to Shore", "Contra III: The Alien Wars OST", "Contra", "US Pressing", "Military Green", "high", 55),
        ("Ship to Shore", "Super Castlevania IV OST", "Castlevania", "US Pressing", "Orange Marble", "high", 60),
    ]

    catalog = []
    for label, title, franchise, pressing, variant, tier, price in items:
        catalog.append({
            "label": label,
            "title": title,
            "franchise": franchise,
            "pressing": pressing,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    label = item["label"]
    title = item["title"]
    franchise = item["franchise"]
    pressing = item["pressing"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{label}-{title}-{variant}"),
        title=f"{title} ({variant})",
        set_code=slugify(label),
        brand=label,
        rarity=item["rarity_tier"].title(),
        notes=f"{label} | {franchise} | {pressing} | {variant}",
        attributes_json={
            "label": label,
            "franchise": franchise,
            "pressing": pressing,
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    pressing = item["pressing"]
    edition_scores = {
        "Japanese OG Pressing": 0.95,
        "Japanese Pressing": 0.80,
        "Event Exclusive": 0.90,
        "RSD Exclusive": 0.85,
        "Numbered Limited": 0.88,
        "Boutique Pressing": 0.75,
        "US Pressing": 0.50,
        "EU/US Pressing": 0.45,
        "EU Pressing": 0.45,
        "Reissue": 0.35,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(pressing, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import anime OST vinyl catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Anime OST Vinyl Import ===")

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

    logger.info(f"\n=== Anime OST Vinyl Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
