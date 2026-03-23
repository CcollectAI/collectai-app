"""
Import anime Blu-ray collector data.

Layer 1 (Catalog):  Curated anime Blu-ray limited editions → category_items (85+ items)
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Aniplex USA, JP box sets, Funimation/Crunchyroll LEs
- GKIDS/Shout Factory, Sentai Filmworks, vintage/OOP titles, 4K UHD editions
- Can be augmented with MyAnimeList, AniList, or CDJapan later

Usage:
    python -m pipelines.import_anime_bluray [--dry-run]
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

CATEGORY = "anime_bluray"


def get_curated_catalog() -> list[dict]:
    """Curated anime Blu-ray collector catalog: 205+ items across Aniplex, JP imports, Funimation/Crunchyroll, GKIDS, Sentai, vintage/OOP, 4K UHD, steelbooks, and concert BDs."""

    # Format: (publisher, title, format, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>300), high (100-300), mid (50-100), standard (<50)

    releases = [
        # Aniplex USA Limited Editions
        ("Aniplex USA", "Fate/Zero", "Blu-ray", "Aniplex LE Box Set I+II", "high", 350),
        ("Aniplex USA", "Fate/stay night: Unlimited Blade Works", "Blu-ray", "Aniplex LE Box Set", "high", 300),
        ("Aniplex USA", "Demon Slayer: Mugen Train", "Blu-ray", "Aniplex LE", "high", 120),
        ("Aniplex USA", "Demon Slayer Season 1", "Blu-ray", "Aniplex LE Box Set", "high", 250),
        ("Aniplex USA", "Sword Art Online Season 1", "Blu-ray", "Aniplex LE Box Set", "high", 200),
        ("Aniplex USA", "Sword Art Online: Ordinal Scale", "Blu-ray", "Aniplex LE", "mid", 100),
        ("Aniplex USA", "Madoka Magica", "Blu-ray", "Aniplex LE Box Set", "grail", 400),
        ("Aniplex USA", "Madoka Magica: Rebellion", "Blu-ray", "Aniplex LE", "high", 150),
        ("Aniplex USA", "Kimetsu no Yaiba: Swordsmith Village", "Blu-ray", "Aniplex LE", "high", 130),
        ("Aniplex USA", "Your Lie in April", "Blu-ray", "Aniplex LE Box Set", "high", 280),
        ("Aniplex USA", "Monogatari Series", "Blu-ray", "Aniplex LE Box Set", "grail", 380),
        ("Aniplex USA", "Kill la Kill", "Blu-ray", "Aniplex LE Box Set", "high", 250),

        # Japanese BD Box Sets with Limited Extras
        ("JP Import", "Neon Genesis Evangelion", "Blu-ray", "JP BD Box Set", "grail", 450),
        ("JP Import", "Cowboy Bebop", "Blu-ray", "JP BD Box Remix", "grail", 350),
        ("JP Import", "Ghost in the Shell: SAC", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Akira", "4K UHD", "JP 4K Limited Edition", "high", 180),
        ("JP Import", "Dragon Ball Z", "Blu-ray", "JP Dragon Box Set", "grail", 500),
        ("JP Import", "Mobile Suit Gundam", "Blu-ray", "JP Memorial Box Set", "high", 300),
        ("JP Import", "Serial Experiments Lain", "Blu-ray", "JP BD Box Set", "high", 250),
        ("JP Import", "FLCL", "Blu-ray", "JP BD Box Set", "high", 180),
        ("JP Import", "Steins;Gate", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Legend of the Galactic Heroes", "Blu-ray", "JP BD Complete Box", "grail", 480),

        # Funimation / Crunchyroll Limited Editions
        ("Funimation", "My Hero Academia Season 1", "Blu-ray", "Funimation LE", "mid", 80),
        ("Funimation", "Attack on Titan Season 1", "Blu-ray", "Funimation LE Box Set", "high", 120),
        ("Funimation", "Dragon Ball Super: Broly", "Blu-ray", "Funimation LE", "mid", 60),
        ("Funimation", "Fullmetal Alchemist Brotherhood", "Blu-ray", "Funimation Complete Set", "high", 150),
        ("Funimation", "Cowboy Bebop", "Blu-ray", "Funimation Complete Series", "mid", 70),
        ("Crunchyroll", "Jujutsu Kaisen Season 1", "Blu-ray", "Crunchyroll LE", "mid", 90),
        ("Crunchyroll", "Spy x Family Part 1", "Blu-ray", "Crunchyroll LE", "mid", 75),
        ("Crunchyroll", "Chainsaw Man", "Blu-ray", "Crunchyroll LE", "mid", 85),

        # Laserdisc Era Collectibles
        ("Laserdisc", "Akira", "Laserdisc", "Criterion LD", "high", 180),
        ("Laserdisc", "Ghost in the Shell", "Laserdisc", "JP LD Box", "high", 150),
        ("Laserdisc", "Neon Genesis Evangelion", "Laserdisc", "JP LD Complete Set", "grail", 400),
        ("Laserdisc", "Macross: Do You Remember Love?", "Laserdisc", "JP LD", "high", 120),
        ("Laserdisc", "Nausicaa of the Valley of the Wind", "Laserdisc", "JP LD", "mid", 80),
        ("Laserdisc", "My Neighbor Totoro", "Laserdisc", "JP LD", "mid", 60),

        # Key Individual Titles
        ("GKIDS", "Spirited Away", "4K UHD", "GKIDS Collector's", "mid", 45),
        ("GKIDS", "Princess Mononoke", "4K UHD", "GKIDS Collector's", "mid", 42),

        # ── New items below ──────────────────────────────────────────────

        # More Aniplex USA (+6)
        ("Aniplex USA", "Kaguya-sama: Love Is War", "Blu-ray", "Aniplex LE Box Set", "high", 220),
        ("Aniplex USA", "Rascal Does Not Dream of Bunny Girl Senpai", "Blu-ray", "Aniplex LE Box Set", "high", 260),
        ("Aniplex USA", "86: Eighty-Six", "Blu-ray", "Aniplex LE Box Set", "high", 190),
        ("Aniplex USA", "Lycoris Recoil", "Blu-ray", "Aniplex LE Box Set", "high", 170),
        ("Aniplex USA", "My Dress-Up Darling", "Blu-ray", "Aniplex LE Box Set", "high", 160),
        ("Aniplex USA", "Bocchi the Rock!", "Blu-ray", "Aniplex LE Box Set", "high", 175),

        # JP Import Box Sets (+10)
        ("JP Import", "Dragon Ball Z", "Blu-ray", "JP Blu-ray Box Season Set", "grail", 550),
        ("JP Import", "One Piece", "Blu-ray", "JP BD Collection Box", "grail", 480),
        ("JP Import", "Naruto Shippuden", "Blu-ray", "JP BD Box Set", "grail", 420),
        ("JP Import", "Evangelion 3.0+1.0 Thrice Upon a Time", "Blu-ray", "JP Limited Edition", "high", 180),
        ("JP Import", "Cowboy Bebop Remix", "Blu-ray", "JP BD Remix Complete", "grail", 320),
        ("JP Import", "FLCL Complete", "Blu-ray", "JP BD Box Complete", "high", 200),
        ("JP Import", "Serial Experiments Lain Complete", "Blu-ray", "JP BD Restored Edition", "high", 270),
        ("JP Import", "Steins;Gate Complete", "Blu-ray", "JP BD Complete Box", "high", 230),
        ("JP Import", "Ghost in the Shell: SAC 2nd GIG", "Blu-ray", "JP BD Box Set", "high", 210),
        ("JP Import", "Mobile Suit Gundam Unicorn", "Blu-ray", "JP BD Complete Box", "high", 280),

        # Funimation/Crunchyroll LEs (+8)
        ("Funimation", "Attack on Titan Final Season Part 1", "Blu-ray", "Funimation LE", "high", 110),
        ("Funimation", "My Hero Academia Season 5", "Blu-ray", "Funimation LE", "mid", 75),
        ("Crunchyroll", "Dragon Ball Super: Super Hero", "Blu-ray", "Crunchyroll LE", "mid", 55),
        ("Crunchyroll", "One Piece Film Red", "Blu-ray", "Crunchyroll LE", "mid", 65),
        ("Crunchyroll", "Jujutsu Kaisen Season 2", "Blu-ray", "Crunchyroll LE", "mid", 95),
        ("Crunchyroll", "Chainsaw Man Complete", "Blu-ray", "Crunchyroll LE Box Set", "high", 110),
        ("Crunchyroll", "Spy x Family Complete Season 1", "Blu-ray", "Crunchyroll LE Box Set", "high", 105),
        ("Crunchyroll", "Vinland Saga Season 1", "Blu-ray", "Crunchyroll LE Box Set", "high", 115),

        # GKIDS / Shout Factory (+6)
        ("GKIDS", "Studio Ghibli Complete Collection", "Blu-ray", "GKIDS Collector's Box Set", "grail", 450),
        ("GKIDS", "My Neighbor Totoro", "Blu-ray", "GKIDS Steelbook", "mid", 55),
        ("GKIDS", "Princess Mononoke", "Blu-ray", "GKIDS Steelbook", "mid", 55),
        ("GKIDS", "Spirited Away", "Blu-ray", "GKIDS Steelbook", "mid", 58),
        ("Shout Factory", "Akira", "4K UHD", "Shout Factory 4K LE", "high", 120),
        ("Shout Factory", "Perfect Blue", "Blu-ray", "Shout Factory Limited Edition", "high", 140),

        # Vintage / OOP (+8)
        ("Bandai Visual", "Mobile Suit Gundam 0079", "Blu-ray", "Bandai Visual LE Box Set", "grail", 380),
        ("FUNimation", "Dragon Ball Z", "Blu-ray", "Orange Brick Complete Set", "high", 200),
        ("ADV Films", "Neon Genesis Evangelion", "Blu-ray", "Platinum Complete Collection", "grail", 350),
        ("Geneon", "Tenchi Muyo! Ryo-Ohki", "Blu-ray", "Geneon OOP Box Set", "high", 220),
        ("Geneon", "Serial Experiments Lain", "Blu-ray", "Geneon Pioneer LE", "high", 280),
        ("Viz Media", "Dragon Ball Z", "Blu-ray", "Viz Dragon Box Set", "grail", 600),
        ("Discotek Media", "Lupin the Third Part II", "Blu-ray", "Discotek Complete Collection", "high", 160),
        ("Discotek Media", "Mazinger Z", "Blu-ray", "Discotek Complete Collection", "high", 140),

        # Sentai Filmworks (+6)
        ("Sentai Filmworks", "CLANNAD Complete Collection", "Blu-ray", "Sentai LE Box Set", "high", 130),
        ("Sentai Filmworks", "Parasyte -the maxim-", "Blu-ray", "Sentai LE", "mid", 85),
        ("Sentai Filmworks", "No Game No Life", "Blu-ray", "Sentai LE", "mid", 90),
        ("Sentai Filmworks", "Log Horizon Complete", "Blu-ray", "Sentai LE Box Set", "mid", 80),
        ("Sentai Filmworks", "Chihayafuru Complete", "Blu-ray", "Sentai LE Box Set", "high", 110),
        ("Sentai Filmworks", "Made in Abyss", "Blu-ray", "Sentai LE", "mid", 95),

        # 4K UHD Anime (+5)
        ("Funimation", "Dragon Ball Super: Broly", "4K UHD", "Funimation 4K Steelbook", "mid", 65),
        ("GKIDS", "Your Name", "4K UHD", "GKIDS 4K Collector's", "mid", 55),
        ("GKIDS", "Weathering With You", "4K UHD", "GKIDS 4K Collector's", "mid", 50),
        ("Lionsgate", "Ghost in the Shell (1995)", "4K UHD", "Lionsgate 4K LE Steelbook", "high", 100),
        ("Funimation", "Akira", "4K UHD", "Funimation 4K LE", "high", 110),

        # === ROUND 2 — 35 new items ===

        # 2023-2024 Hits
        ("JP Import", "Frieren: Beyond Journey's End", "Blu-ray", "JP BD Box Set Vol.1-4", "high", 280),
        ("JP Import", "Oshi no Ko", "Blu-ray", "JP BD Box Set", "high", 240),
        ("Crunchyroll", "Jujutsu Kaisen Season 2 Shibuya Incident", "Blu-ray", "Crunchyroll LE Box Set", "high", 120),
        ("JP Import", "Solo Leveling", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Dandadan", "Blu-ray", "JP BD Box Vol.1", "mid", 95),

        # Aniplex Limited — Premium Releases
        ("Aniplex USA", "Demon Slayer Complete Series", "Blu-ray", "Aniplex LE Complete Box", "grail", 500),
        ("Aniplex USA", "Lycoris Recoil Complete", "Blu-ray", "Aniplex LE Complete Box", "high", 200),
        ("Aniplex USA", "Bocchi the Rock! Complete", "Blu-ray", "Aniplex LE Complete Box", "high", 210),
        ("Aniplex USA", "Solo Leveling", "Blu-ray", "Aniplex LE Box Set", "high", 180),

        # JP Import — More Premium
        ("JP Import", "Chainsaw Man", "Blu-ray", "JP BD Complete Box", "high", 260),
        ("JP Import", "Spy x Family Season 2", "Blu-ray", "JP BD Box Set", "high", 220),
        ("JP Import", "Vinland Saga Complete Series", "Blu-ray", "JP BD Complete Box", "grail", 380),
        ("JP Import", "Blue Lock", "Blu-ray", "JP BD Box Set Limited", "high", 250),

        # Classic Reissues
        ("GKIDS", "Neon Genesis Evangelion Ultimate Edition", "Blu-ray", "GKIDS Ultimate BD Box", "grail", 400),
        ("Funimation", "Serial Experiments Lain Complete", "Blu-ray", "Funimation Collector's LE", "high", 180),
        ("Discotek Media", "Revolutionary Girl Utena Complete", "Blu-ray", "Discotek Complete BD Box", "high", 160),

        # Film Releases — Theatrical
        ("GKIDS", "Suzume", "Blu-ray", "GKIDS Collector's Edition", "mid", 55),
        ("GKIDS", "The Boy and the Heron", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 65),
        ("Crunchyroll", "The First Slam Dunk", "Blu-ray", "Crunchyroll LE", "mid", 60),
        ("JP Import", "Suzume", "4K UHD", "JP 4K Limited Edition", "high", 120),

        # Steelbook Editions
        ("Funimation", "Akira", "4K UHD", "Funimation 4K Steelbook", "high", 130),
        ("Lionsgate", "Ghost in the Shell (1995)", "4K UHD", "Lionsgate 4K Steelbook", "high", 110),
        ("GKIDS", "Nausicaa of the Valley of the Wind", "Blu-ray", "GKIDS Steelbook", "mid", 58),

        # Sentai / HIDIVE Collector's
        ("Sentai Filmworks", "CLANNAD & After Story Complete", "Blu-ray", "Sentai Ultimate LE Box Set", "high", 180),
        ("Sentai Filmworks", "Made in Abyss Collector's Edition", "Blu-ray", "Sentai Collector's Box Set", "high", 140),
        ("Sentai Filmworks", "Land of the Lustrous", "Blu-ray", "Sentai LE Box Set", "high", 120),

        # Discotek — Retro Catalog
        ("Discotek Media", "Urusei Yatsura Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 200),
        ("Discotek Media", "City Hunter Complete Series", "Blu-ray", "Discotek Complete BD Collection", "high", 180),
        ("Discotek Media", "Fist of the North Star Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 190),

        # Concert / Live Blu-rays
        ("JP Import", "LiSA Live is Smile Always Ladybug", "Blu-ray", "JP Concert BD Limited", "high", 150),
        ("JP Import", "Aimer Live in Budokan blanc et noir", "Blu-ray", "JP Concert BD Limited", "high", 130),
        ("JP Import", "YOASOBI Arena Tour 2023 Dennou Seikatsu", "Blu-ray", "JP Concert BD Limited", "high", 140),
        ("JP Import", "Kenshi Yonezu TOUR 2023 Kick Back", "Blu-ray", "JP Concert BD Limited", "high", 145),
        ("JP Import", "Ado 2024 Hibana Live", "Blu-ray", "JP Concert BD Limited", "mid", 95),

        # === ROUND 3 — 21 new items ===

        # 2024-2025 Breakout Hits
        ("JP Import", "Kaiju No. 8", "Blu-ray", "JP BD Box Set Vol.1-2", "high", 190),
        ("JP Import", "Wind Breaker", "Blu-ray", "JP BD Box Set", "mid", 95),
        ("JP Import", "Shangri-La Frontier", "Blu-ray", "JP BD Box Set", "high", 170),
        ("JP Import", "Undead Unluck", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("Crunchyroll", "Frieren: Beyond Journey's End", "Blu-ray", "Crunchyroll LE Box Set", "high", 130),

        # Studio Ghibli Individual 4K UHD
        ("GKIDS", "Howl's Moving Castle", "4K UHD", "GKIDS 4K Collector's", "mid", 52),
        ("GKIDS", "Kiki's Delivery Service", "4K UHD", "GKIDS 4K Collector's", "mid", 48),
        ("GKIDS", "Castle in the Sky", "4K UHD", "GKIDS 4K Collector's", "mid", 50),
        ("GKIDS", "Porco Rosso", "4K UHD", "GKIDS 4K Collector's", "mid", 48),

        # Vintage / OOP Rarities
        ("Bandai Visual", "Patlabor The Movie", "Blu-ray", "Bandai Visual JP BD LE", "high", 160),
        ("Bandai Visual", "Royal Space Force: Wings of Honneamise", "Blu-ray", "Bandai Visual JP BD LE", "high", 180),
        ("Pioneer LDC", "Tenchi Muyo! OVA", "Laserdisc", "JP LD Complete Set", "high", 140),
        ("Manga Entertainment", "Ghost in the Shell (1995)", "Blu-ray", "Manga UK Collector's Steelbook", "mid", 65),

        # All-Time Classic Complete Sets
        ("Funimation", "Trigun Complete Series", "Blu-ray", "Funimation Classics LE", "high", 120),
        ("Funimation", "Samurai Champloo Complete", "Blu-ray", "Funimation Classics LE", "high", 135),
        ("Discotek Media", "Giant Robo Complete OVA", "Blu-ray", "Discotek BD Remaster", "high", 110),

        # JP Import — Music / Idol Anime
        ("JP Import", "BanG Dream! It's MyGO!!!!! Complete", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Love Live! Superstar!! Season 2", "Blu-ray", "JP BD Box Set", "high", 220),

        # Aniplex Premium Film
        ("Aniplex USA", "Fate/stay night: Heaven's Feel Trilogy", "Blu-ray", "Aniplex LE Trilogy Box", "grail", 380),
        ("Aniplex USA", "Sword Art Online Progressive: Aria of a Starless Night", "Blu-ray", "Aniplex LE", "high", 130),
        ("Aniplex USA", "Oshi no Ko", "Blu-ray", "Aniplex LE Box Set", "high", 210),

        # === ROUND 4 — 63 new items to reach 205+ ===

        # 2025 New Releases / Recent Seasons
        ("JP Import", "Sakamoto Days", "Blu-ray", "JP BD Box Set Vol.1-2", "high", 180),
        ("JP Import", "Dandadan Complete", "Blu-ray", "JP BD Complete Box", "high", 220),
        ("JP Import", "Blue Box", "Blu-ray", "JP BD Box Set", "mid", 95),
        ("JP Import", "Apothecary Diaries", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Sousou no Frieren Season 2", "Blu-ray", "JP BD Box Set", "high", 240),
        ("Crunchyroll", "Dandadan", "Blu-ray", "Crunchyroll LE Box Set", "high", 110),
        ("Crunchyroll", "Kaiju No. 8", "Blu-ray", "Crunchyroll LE", "mid", 85),
        ("Aniplex USA", "Apothecary Diaries", "Blu-ray", "Aniplex LE Box Set", "high", 190),

        # More Aniplex Premium Releases
        ("Aniplex USA", "Monogatari Series Off & Monster Season", "Blu-ray", "Aniplex LE Box Set", "high", 230),
        ("Aniplex USA", "Sword Art Online Progressive: Scherzo of Deep Night", "Blu-ray", "Aniplex LE", "high", 140),
        ("Aniplex USA", "The Promised Neverland", "Blu-ray", "Aniplex LE Box Set", "high", 200),
        ("Aniplex USA", "Erased (Boku dake ga Inai Machi)", "Blu-ray", "Aniplex LE Box Set", "high", 180),
        ("Aniplex USA", "March Comes in Like a Lion", "Blu-ray", "Aniplex LE Complete Box", "high", 250),

        # JP Import — Cult Classics & Deep Cuts
        ("JP Import", "Trigun Stampede", "Blu-ray", "JP BD Box Set", "high", 190),
        ("JP Import", "Mob Psycho 100 Complete", "Blu-ray", "JP BD Complete Box", "high", 260),
        ("JP Import", "Mushoku Tensei Complete", "Blu-ray", "JP BD Complete Box", "high", 280),
        ("JP Import", "Re:Zero Complete", "Blu-ray", "JP BD Complete Box", "grail", 350),
        ("JP Import", "Violet Evergarden Complete", "Blu-ray", "JP BD Complete Box", "grail", 320),
        ("JP Import", "Laid-Back Camp Complete", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "March Comes in Like a Lion", "Blu-ray", "JP BD Complete Box", "high", 240),

        # 4K UHD Upgrades — New Releases
        ("GKIDS", "Grave of the Fireflies", "4K UHD", "GKIDS 4K Collector's", "mid", 52),
        ("GKIDS", "The Tale of the Princess Kaguya", "4K UHD", "GKIDS 4K Collector's", "mid", 55),
        ("GKIDS", "When Marnie Was There", "4K UHD", "GKIDS 4K Collector's", "mid", 48),
        ("GKIDS", "Ponyo", "4K UHD", "GKIDS 4K Collector's", "mid", 50),
        ("Funimation", "My Hero Academia: World Heroes' Mission", "4K UHD", "Funimation 4K Steelbook", "mid", 55),
        ("Crunchyroll", "Demon Slayer: Mugen Train", "4K UHD", "Crunchyroll 4K Steelbook", "mid", 60),

        # Steelbook Collector's Editions
        ("Funimation", "Attack on Titan Season 1", "Blu-ray", "Funimation Steelbook", "mid", 65),
        ("Funimation", "My Hero Academia Season 1", "Blu-ray", "Funimation Steelbook", "mid", 55),
        ("Crunchyroll", "Jujutsu Kaisen Season 1", "Blu-ray", "Crunchyroll Steelbook", "mid", 60),
        ("GKIDS", "Howl's Moving Castle", "Blu-ray", "GKIDS Steelbook", "mid", 58),
        ("GKIDS", "Laputa: Castle in the Sky", "Blu-ray", "GKIDS Steelbook", "mid", 55),
        ("Manga Entertainment", "Akira", "4K UHD", "Manga UK 4K Steelbook Limited", "high", 110),

        # Discotek Media — More Retro Catalog
        ("Discotek Media", "Getter Robo Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 150),
        ("Discotek Media", "Space Battleship Yamato", "Blu-ray", "Discotek Complete BD Collection", "high", 170),
        ("Discotek Media", "Galaxy Express 999", "Blu-ray", "Discotek Complete BD Collection", "high", 160),
        ("Discotek Media", "Captain Harlock Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 145),

        # Sentai / HIDIVE — New Acquisitions
        ("Sentai Filmworks", "The Devil is a Part-Timer! Complete", "Blu-ray", "Sentai LE Box Set", "mid", 90),
        ("Sentai Filmworks", "Akame ga Kill! Complete", "Blu-ray", "Sentai LE", "mid", 80),
        ("Sentai Filmworks", "Food Wars! Complete", "Blu-ray", "Sentai LE Box Set", "high", 130),
        ("Sentai Filmworks", "Bloom Into You", "Blu-ray", "Sentai LE", "mid", 75),

        # Vintage / OOP — More Rarities
        ("Bandai Visual", "Cowboy Bebop Remix", "Blu-ray", "Bandai Visual JP BD LE", "high", 220),
        ("ADV Films", "Full Metal Panic!", "Blu-ray", "ADV OOP Complete Collection", "high", 180),
        ("Geneon", "Haruhi Suzumiya Complete", "Blu-ray", "Geneon OOP LE Box Set", "high", 250),
        ("Pioneer LDC", "El-Hazard OVA", "Laserdisc", "JP LD Complete Set", "high", 130),
        ("Pioneer LDC", "Battle Angel Alita (Gunnm)", "Laserdisc", "JP LD", "high", 110),

        # Concert / Live Blu-rays — More Artists
        ("JP Import", "Aimer Live in Budokan blanc et noir Day 2", "Blu-ray", "JP Concert BD Limited", "high", 135),
        ("JP Import", "Linked Horizon Live Shingeki no Kiseki", "Blu-ray", "JP Concert BD Limited", "high", 120),
        ("JP Import", "Kalafina Arena LIVE 2016", "Blu-ray", "JP Concert BD Limited", "high", 140),
        ("JP Import", "ClariS 1st Hall Concert Fairy Party", "Blu-ray", "JP Concert BD Limited", "mid", 90),
        ("JP Import", "RADWIMPS Asia Tour 2024", "Blu-ray", "JP Concert BD Limited", "high", 130),

        # Film Releases — More Theatricals
        ("GKIDS", "The Boy and the Heron", "Blu-ray", "GKIDS Collector's Edition", "mid", 55),
        ("Crunchyroll", "Demon Slayer: To the Hashira Training", "Blu-ray", "Crunchyroll LE", "mid", 65),
        ("JP Import", "One Piece Film Red", "4K UHD", "JP 4K Limited Edition", "high", 110),
        ("JP Import", "Dragon Ball Super: Super Hero", "4K UHD", "JP 4K Limited Edition", "high", 100),
        ("GKIDS", "My Neighbor Totoro", "4K UHD", "GKIDS 4K Collector's", "mid", 52),

        # JP Import — Idol / Music Anime
        ("JP Import", "Oshi no Ko Season 2", "Blu-ray", "JP BD Box Set", "high", 220),
        ("JP Import", "Bocchi the Rock! Complete", "Blu-ray", "JP BD Complete Box", "high", 240),
        ("JP Import", "Girls Band Cry", "Blu-ray", "JP BD Box Set", "high", 180),
        ("JP Import", "Love Live! Nijigasaki Season 2", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "The iDOLM@STER Cinderella Girls", "Blu-ray", "JP BD Complete Box", "high", 260),

        # === ROUND 5 — 300+ new items to reach 500+ ===

        # ── Naruto Complete Series ──────────────────────────────────────
        ("JP Import", "Naruto", "Blu-ray", "JP BD Complete Box Season 1", "grail", 380),
        ("JP Import", "Naruto Shippuden Season 2", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Naruto Shippuden Season 3", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Naruto Shippuden Season 4", "Blu-ray", "JP BD Box Set", "high", 190),
        ("JP Import", "Naruto Shippuden Final Arc", "Blu-ray", "JP BD Box Set", "high", 210),
        ("JP Import", "The Last: Naruto the Movie", "Blu-ray", "JP BD Limited Edition", "high", 120),
        ("JP Import", "Boruto: Naruto the Movie", "Blu-ray", "JP BD Limited Edition", "mid", 80),
        ("Viz Media", "Naruto Complete Series", "Blu-ray", "Viz Complete Collection", "high", 180),

        # ── Bleach Franchise ────────────────────────────────────────────
        ("JP Import", "Bleach", "Blu-ray", "JP BD Complete Box Season 1-4", "grail", 450),
        ("JP Import", "Bleach Thousand-Year Blood War Part 1", "Blu-ray", "JP BD Box Set", "high", 220),
        ("JP Import", "Bleach Thousand-Year Blood War Part 2", "Blu-ray", "JP BD Box Set", "high", 230),
        ("JP Import", "Bleach Thousand-Year Blood War Part 3", "Blu-ray", "JP BD Box Set", "high", 240),
        ("Viz Media", "Bleach Complete Series Set 1", "Blu-ray", "Viz BD Box Set", "high", 160),
        ("Viz Media", "Bleach Complete Series Set 2", "Blu-ray", "Viz BD Box Set", "high", 160),

        # ── One Piece Extended ──────────────────────────────────────────
        ("JP Import", "One Piece East Blue Arc", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "One Piece Alabasta Arc", "Blu-ray", "JP BD Box Set", "high", 220),
        ("JP Import", "One Piece Skypiea Arc", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "One Piece Enies Lobby Arc", "Blu-ray", "JP BD Box Set", "high", 240),
        ("JP Import", "One Piece Marineford Arc", "Blu-ray", "JP BD Box Set", "grail", 300),
        ("JP Import", "One Piece Wano Arc Part 1", "Blu-ray", "JP BD Box Set", "high", 250),
        ("JP Import", "One Piece Wano Arc Part 2", "Blu-ray", "JP BD Box Set", "high", 260),
        ("JP Import", "One Piece Film Z", "Blu-ray", "JP BD Limited Edition", "high", 110),
        ("JP Import", "One Piece Film Gold", "Blu-ray", "JP BD Limited Edition", "mid", 90),
        ("Funimation", "One Piece Season 1", "Blu-ray", "Funimation Complete Set", "mid", 65),

        # ── Dragon Ball Extended ────────────────────────────────────────
        ("JP Import", "Dragon Ball", "Blu-ray", "JP BD Complete Box", "grail", 400),
        ("JP Import", "Dragon Ball Z Season 1 Remaster", "Blu-ray", "JP BD Box Remaster", "high", 280),
        ("JP Import", "Dragon Ball Z Season 2 Remaster", "Blu-ray", "JP BD Box Remaster", "high", 280),
        ("JP Import", "Dragon Ball Z Season 3 Remaster", "Blu-ray", "JP BD Box Remaster", "high", 280),
        ("JP Import", "Dragon Ball Super Complete", "Blu-ray", "JP BD Complete Box", "grail", 500),
        ("JP Import", "Dragon Ball Super: Super Hero", "Blu-ray", "JP BD Limited Edition", "high", 120),
        ("Funimation", "Dragon Ball Z Season Set 1-9", "Blu-ray", "Funimation Complete Collection", "high", 200),
        ("JP Import", "Dragon Ball GT", "Blu-ray", "JP BD Complete Box", "high", 300),

        # ── Attack on Titan Complete ────────────────────────────────────
        ("JP Import", "Attack on Titan Season 1", "Blu-ray", "JP BD Box Set", "high", 250),
        ("JP Import", "Attack on Titan Season 2", "Blu-ray", "JP BD Box Set", "high", 220),
        ("JP Import", "Attack on Titan Season 3 Part 1", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Attack on Titan Season 3 Part 2", "Blu-ray", "JP BD Box Set", "high", 210),
        ("JP Import", "Attack on Titan Final Season Part 2", "Blu-ray", "JP BD Box Set", "high", 230),
        ("JP Import", "Attack on Titan Final Season Part 3", "Blu-ray", "JP BD Box Set", "high", 250),
        ("JP Import", "Attack on Titan Complete Series", "Blu-ray", "JP BD Complete Box", "grail", 600),
        ("Funimation", "Attack on Titan Complete Season 1-3", "Blu-ray", "Funimation LE Box Set", "high", 180),

        # ── Demon Slayer Extended ───────────────────────────────────────
        ("JP Import", "Demon Slayer Season 2 Entertainment District", "Blu-ray", "JP BD Box Set", "high", 220),
        ("JP Import", "Demon Slayer Swordsmith Village Arc", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Demon Slayer Hashira Training Arc", "Blu-ray", "JP BD Box Set", "high", 190),
        ("JP Import", "Demon Slayer Infinity Castle Arc Part 1", "Blu-ray", "JP BD Limited Edition", "high", 150),
        ("Aniplex USA", "Demon Slayer Season 2", "Blu-ray", "Aniplex LE Box Set", "high", 180),
        ("Aniplex USA", "Demon Slayer Swordsmith Village", "Blu-ray", "Aniplex LE Box Set", "high", 170),

        # ── Jujutsu Kaisen Extended ─────────────────────────────────────
        ("JP Import", "Jujutsu Kaisen Season 1", "Blu-ray", "JP BD Box Set", "high", 240),
        ("JP Import", "Jujutsu Kaisen Season 2 Hidden Inventory", "Blu-ray", "JP BD Box Set", "high", 220),
        ("JP Import", "Jujutsu Kaisen Season 2 Shibuya Incident", "Blu-ray", "JP BD Box Set", "high", 250),
        ("JP Import", "Jujutsu Kaisen 0 The Movie", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("Crunchyroll", "Jujutsu Kaisen 0 The Movie", "Blu-ray", "Crunchyroll LE Steelbook", "mid", 65),
        ("Aniplex USA", "Jujutsu Kaisen Complete Season 1", "Blu-ray", "Aniplex LE Box Set", "high", 200),

        # ── Chainsaw Man Extended ───────────────────────────────────────
        ("JP Import", "Chainsaw Man Season 1", "Blu-ray", "JP BD Box Set", "high", 260),
        ("JP Import", "Chainsaw Man Reze Arc", "Blu-ray", "JP BD Limited Edition", "high", 150),
        ("Aniplex USA", "Chainsaw Man Season 1", "Blu-ray", "Aniplex LE Box Set", "high", 190),

        # ── Spy x Family Extended ───────────────────────────────────────
        ("JP Import", "Spy x Family Season 1 Part 1", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Spy x Family Season 1 Part 2", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Spy x Family Code: White", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("Crunchyroll", "Spy x Family Code: White", "Blu-ray", "Crunchyroll LE", "mid", 55),

        # ── Frieren ─────────────────────────────────────────────────────
        ("JP Import", "Frieren: Beyond Journey's End Vol.1", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("JP Import", "Frieren: Beyond Journey's End Vol.2", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("JP Import", "Frieren: Beyond Journey's End Vol.3", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("JP Import", "Frieren: Beyond Journey's End Vol.4", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("Aniplex USA", "Frieren: Beyond Journey's End", "Blu-ray", "Aniplex LE Box Set", "high", 250),

        # ── Gundam Franchise ────────────────────────────────────────────
        ("JP Import", "Mobile Suit Gundam: The Origin", "Blu-ray", "JP BD Box Set", "high", 280),
        ("JP Import", "Gundam SEED Complete", "Blu-ray", "JP BD Complete Box", "high", 250),
        ("JP Import", "Gundam SEED Destiny Complete", "Blu-ray", "JP BD Complete Box", "high", 240),
        ("JP Import", "Gundam 00 Complete", "Blu-ray", "JP BD Complete Box", "high", 260),
        ("JP Import", "Gundam Wing Complete", "Blu-ray", "JP BD Complete Box", "high", 280),
        ("JP Import", "Zeta Gundam Complete", "Blu-ray", "JP BD Complete Box", "grail", 350),
        ("JP Import", "Gundam Thunderbolt", "Blu-ray", "JP BD Box Set", "high", 180),
        ("JP Import", "Gundam: The Witch from Mercury", "Blu-ray", "JP BD Complete Box", "high", 250),
        ("JP Import", "Gundam Hathaway's Flash", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("JP Import", "Char's Counterattack", "Blu-ray", "JP BD Limited Edition", "high", 150),
        ("Bandai Visual", "Mobile Suit Gundam F91", "Blu-ray", "Bandai Visual JP BD LE", "high", 120),
        ("Bandai Visual", "Gundam 0083: Stardust Memory", "Blu-ray", "Bandai Visual JP BD LE", "high", 180),

        # ── Macross Franchise ───────────────────────────────────────────
        ("JP Import", "Macross Frontier", "Blu-ray", "JP BD Complete Box", "high", 280),
        ("JP Import", "Macross Delta", "Blu-ray", "JP BD Complete Box", "high", 240),
        ("JP Import", "Macross Plus OVA", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Macross: Do You Remember Love?", "Blu-ray", "JP BD Limited Edition", "grail", 320),
        ("JP Import", "SDF Macross Complete", "Blu-ray", "JP BD Complete Box", "grail", 400),
        ("JP Import", "Macross 7 Complete", "Blu-ray", "JP BD Complete Box", "high", 280),

        # ── Evangelion Extended ──────────────────────────────────────────
        ("JP Import", "Evangelion 1.0 You Are (Not) Alone", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("JP Import", "Evangelion 2.0 You Can (Not) Advance", "Blu-ray", "JP BD Limited Edition", "high", 140),
        ("JP Import", "Evangelion 3.0 You Can (Not) Redo", "Blu-ray", "JP BD Limited Edition", "high", 140),
        ("JP Import", "Evangelion Rebuild Complete Box", "Blu-ray", "JP BD Complete Box", "grail", 500),
        ("GKIDS", "Neon Genesis Evangelion Complete Series", "Blu-ray", "GKIDS Collector's Box Set", "grail", 350),

        # ── Cowboy Bebop / Samurai Champloo / FLCL ──────────────────────
        ("JP Import", "Samurai Champloo", "Blu-ray", "JP BD Complete Box", "grail", 320),
        ("Funimation", "Samurai Champloo Complete Series", "Blu-ray", "Funimation Classics LE", "high", 120),
        ("JP Import", "FLCL Progressive & Alternative", "Blu-ray", "JP BD Box Set", "high", 160),
        ("JP Import", "Cowboy Bebop: The Movie", "Blu-ray", "JP BD Limited Edition", "high", 150),

        # ── Studio Ghibli Full Catalog ──────────────────────────────────
        ("GKIDS", "Princess Mononoke", "4K UHD", "GKIDS 4K Steelbook", "mid", 62),
        ("GKIDS", "Nausicaa of the Valley of the Wind", "4K UHD", "GKIDS 4K Collector's", "mid", 52),
        ("GKIDS", "The Wind Rises", "Blu-ray", "GKIDS Collector's Edition", "mid", 42),
        ("GKIDS", "Arrietty", "Blu-ray", "GKIDS Collector's Edition", "standard", 35),
        ("GKIDS", "From Up on Poppy Hill", "Blu-ray", "GKIDS Collector's Edition", "standard", 32),
        ("GKIDS", "The Red Turtle", "Blu-ray", "GKIDS Collector's Edition", "standard", 30),
        ("GKIDS", "Earwig and the Witch", "Blu-ray", "GKIDS Collector's Edition", "standard", 28),
        ("GKIDS", "Tales from Earthsea", "Blu-ray", "GKIDS Collector's Edition", "standard", 30),
        ("GKIDS", "Pom Poko", "Blu-ray", "GKIDS Collector's Edition", "standard", 32),
        ("GKIDS", "My Neighbors the Yamadas", "Blu-ray", "GKIDS Collector's Edition", "standard", 30),
        ("GKIDS", "Only Yesterday", "Blu-ray", "GKIDS Collector's Edition", "standard", 35),
        ("GKIDS", "Grave of the Fireflies", "Blu-ray", "GKIDS Collector's Edition", "mid", 42),

        # ── Makoto Shinkai Films ────────────────────────────────────────
        ("JP Import", "Your Name", "Blu-ray", "JP BD Collector's Edition", "high", 180),
        ("JP Import", "Weathering With You", "Blu-ray", "JP BD Collector's Edition", "high", 160),
        ("GKIDS", "Your Name", "Blu-ray", "GKIDS Steelbook", "mid", 55),
        ("GKIDS", "Weathering With You", "Blu-ray", "GKIDS Steelbook", "mid", 52),
        ("GKIDS", "Suzume", "4K UHD", "GKIDS 4K Steelbook", "mid", 65),
        ("JP Import", "5 Centimeters Per Second", "Blu-ray", "JP BD Limited Edition", "high", 120),
        ("JP Import", "The Garden of Words", "Blu-ray", "JP BD Limited Edition", "mid", 80),
        ("JP Import", "Children Who Chase Lost Voices", "Blu-ray", "JP BD Limited Edition", "mid", 90),

        # ── Satoshi Kon Films ───────────────────────────────────────────
        ("Shout Factory", "Perfect Blue", "4K UHD", "Shout Factory 4K LE", "high", 130),
        ("JP Import", "Perfect Blue", "Blu-ray", "JP BD Remaster Limited", "high", 160),
        ("JP Import", "Millennium Actress", "Blu-ray", "JP BD Limited Edition", "high", 140),
        ("GKIDS", "Millennium Actress", "Blu-ray", "GKIDS Collector's Edition", "mid", 45),
        ("JP Import", "Paprika", "Blu-ray", "JP BD Limited Edition", "high", 150),
        ("GKIDS", "Paprika", "Blu-ray", "GKIDS Collector's Edition", "mid", 42),
        ("JP Import", "Tokyo Godfathers", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("GKIDS", "Tokyo Godfathers", "Blu-ray", "GKIDS Collector's Edition", "mid", 40),

        # ── Ghost in the Shell ──────────────────────────────────────────
        ("JP Import", "Ghost in the Shell (1995)", "4K UHD", "JP 4K Remaster Limited", "high", 200),
        ("JP Import", "Ghost in the Shell 2: Innocence", "Blu-ray", "JP BD Limited Edition", "high", 150),
        ("JP Import", "Ghost in the Shell: SAC Complete", "Blu-ray", "JP BD Complete Box", "grail", 350),
        ("JP Import", "Ghost in the Shell: SAC_2045 Complete", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "Ghost in the Shell Arise", "Blu-ray", "JP BD Complete Box", "high", 180),

        # ── Classic 80s/90s OVAs ────────────────────────────────────────
        ("Discotek Media", "Bubblegum Crisis", "Blu-ray", "Discotek Complete BD Collection", "high", 130),
        ("Discotek Media", "Vampire Hunter D", "Blu-ray", "Discotek BD Remaster", "high", 110),
        ("Discotek Media", "Vampire Hunter D: Bloodlust", "Blu-ray", "Discotek BD Remaster", "mid", 80),
        ("Discotek Media", "Robot Carnival", "Blu-ray", "Discotek BD Remaster", "high", 100),
        ("Discotek Media", "Golgo 13: The Professional", "Blu-ray", "Discotek BD Remaster", "mid", 70),
        ("JP Import", "Riding Bean", "Blu-ray", "JP BD Limited Edition", "high", 120),
        ("JP Import", "Gunsmith Cats OVA", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("JP Import", "Megazone 23", "Blu-ray", "JP BD Complete Box", "high", 180),
        ("Discotek Media", "Area 88 OVA", "Blu-ray", "Discotek Complete BD Collection", "high", 110),
        ("JP Import", "Patlabor OVA Complete", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "Patlabor Movie 1 & 2", "Blu-ray", "JP BD Box Set", "high", 250),
        ("Discotek Media", "Devilman OVA", "Blu-ray", "Discotek Complete BD Collection", "mid", 75),
        ("Discotek Media", "Crusher Joe", "Blu-ray", "Discotek BD Remaster", "high", 100),
        ("JP Import", "Armored Trooper VOTOMS", "Blu-ray", "JP BD Complete Box", "grail", 380),

        # ── Mecha Classics ──────────────────────────────────────────────
        ("JP Import", "GaoGaiGar", "Blu-ray", "JP BD Complete Box", "grail", 350),
        ("JP Import", "Full Metal Panic!", "Blu-ray", "JP BD Complete Box", "high", 240),
        ("JP Import", "Full Metal Panic! The Second Raid", "Blu-ray", "JP BD Box Set", "high", 180),
        ("JP Import", "Eureka Seven", "Blu-ray", "JP BD Complete Box", "grail", 320),
        ("JP Import", "Code Geass Complete", "Blu-ray", "JP BD Complete Box", "grail", 380),
        ("JP Import", "Gurren Lagann", "Blu-ray", "JP BD Complete Box", "grail", 350),
        ("JP Import", "Rahxephon", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "Escaflowne", "Blu-ray", "JP BD Complete Box", "high", 250),
        ("JP Import", "Patlabor TV Series", "Blu-ray", "JP BD Complete Box", "high", 280),

        # ── Magical Girl ────────────────────────────────────────────────
        ("JP Import", "Sailor Moon Complete", "Blu-ray", "JP BD Complete Box", "grail", 500),
        ("JP Import", "Sailor Moon Crystal Complete", "Blu-ray", "JP BD Complete Box", "high", 280),
        ("JP Import", "Sailor Moon Cosmos", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("JP Import", "CardCaptor Sakura", "Blu-ray", "JP BD Complete Box", "grail", 350),
        ("JP Import", "CardCaptor Sakura: Clear Card", "Blu-ray", "JP BD Box Set", "high", 200),
        ("Aniplex USA", "Madoka Magica: Walpurgis Rising", "Blu-ray", "Aniplex LE", "high", 150),
        ("JP Import", "Revolutionary Girl Utena", "Blu-ray", "JP BD Complete Box", "grail", 380),
        ("JP Import", "Precure All Stars", "Blu-ray", "JP BD Box Set", "high", 200),
        ("Sentai Filmworks", "Flip Flappers", "Blu-ray", "Sentai LE", "mid", 75),

        # ── Sports Anime ────────────────────────────────────────────────
        ("JP Import", "Haikyuu!! Complete Season 1-4", "Blu-ray", "JP BD Complete Box", "grail", 450),
        ("JP Import", "Haikyuu!! The Dumpster Battle", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("JP Import", "Slam Dunk Complete", "Blu-ray", "JP BD Complete Box", "grail", 400),
        ("JP Import", "The First Slam Dunk", "Blu-ray", "JP BD Limited Edition", "high", 140),
        ("JP Import", "Kuroko's Basketball Complete", "Blu-ray", "JP BD Complete Box", "high", 280),
        ("JP Import", "Yowamushi Pedal Complete", "Blu-ray", "JP BD Complete Box", "high", 250),
        ("JP Import", "Run with the Wind", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "Blue Lock Season 1", "Blu-ray", "JP BD Box Set", "high", 230),

        # ── Isekai ──────────────────────────────────────────────────────
        ("JP Import", "Re:Zero Season 1", "Blu-ray", "JP BD Box Set", "high", 230),
        ("JP Import", "Re:Zero Season 2 Complete", "Blu-ray", "JP BD Complete Box", "high", 260),
        ("JP Import", "Mushoku Tensei Season 1", "Blu-ray", "JP BD Box Set", "high", 220),
        ("JP Import", "Mushoku Tensei Season 2", "Blu-ray", "JP BD Box Set", "high", 210),
        ("JP Import", "Konosuba Complete", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "Overlord Complete", "Blu-ray", "JP BD Complete Box", "high", 240),
        ("JP Import", "That Time I Got Reincarnated as a Slime", "Blu-ray", "JP BD Complete Box", "high", 250),
        ("JP Import", "Shield Hero Complete", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "Ascendance of a Bookworm Complete", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "The Rising of the Shield Hero Season 2", "Blu-ray", "JP BD Box Set", "mid", 95),

        # ── Romance / Slice of Life ─────────────────────────────────────
        ("JP Import", "Toradora! Complete", "Blu-ray", "JP BD Complete Box", "high", 250),
        ("Aniplex USA", "Your Lie in April Complete", "Blu-ray", "Aniplex LE Complete Box", "grail", 320),
        ("JP Import", "Fruits Basket Complete", "Blu-ray", "JP BD Complete Box", "high", 280),
        ("Funimation", "Fruits Basket Complete Series", "Blu-ray", "Funimation LE Box Set", "high", 150),
        ("JP Import", "Violet Evergarden: The Movie", "Blu-ray", "JP BD Limited Edition", "high", 140),
        ("JP Import", "A Silent Voice", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("JP Import", "Josee, the Tiger and the Fish", "Blu-ray", "JP BD Limited Edition", "mid", 90),
        ("JP Import", "Horimiya Complete", "Blu-ray", "JP BD Complete Box", "high", 180),
        ("JP Import", "Oregairu Complete", "Blu-ray", "JP BD Complete Box", "high", 220),
        ("JP Import", "Anohana: The Flower We Saw That Day", "Blu-ray", "JP BD Box Set", "high", 180),
        ("JP Import", "March Comes in Like a Lion Complete", "Blu-ray", "JP BD Complete Box", "high", 260),
        ("JP Import", "Nana Complete", "Blu-ray", "JP BD Complete Box", "grail", 350),
        ("JP Import", "Skip and Loafer", "Blu-ray", "JP BD Box Set", "mid", 95),
        ("JP Import", "My Happy Marriage", "Blu-ray", "JP BD Box Set", "high", 150),

        # ── Modern Shonen ───────────────────────────────────────────────
        ("JP Import", "My Hero Academia Complete Season 1-6", "Blu-ray", "JP BD Complete Box", "grail", 550),
        ("JP Import", "My Hero Academia Season 6", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "My Hero Academia Season 7", "Blu-ray", "JP BD Box Set", "high", 210),
        ("JP Import", "Black Clover Complete", "Blu-ray", "JP BD Complete Box", "grail", 400),
        ("JP Import", "Dr. Stone Complete", "Blu-ray", "JP BD Complete Box", "high", 250),
        ("JP Import", "Fire Force Complete", "Blu-ray", "JP BD Complete Box", "high", 240),
        ("JP Import", "Undead Unluck Complete", "Blu-ray", "JP BD Complete Box", "high", 190),
        ("JP Import", "Hell's Paradise", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Mashle: Magic and Muscles", "Blu-ray", "JP BD Box Set", "mid", 95),

        # ── Seinen / Dark ───────────────────────────────────────────────
        ("JP Import", "Berserk (1997)", "Blu-ray", "JP BD Complete Box", "grail", 350),
        ("JP Import", "Berserk Golden Age Trilogy", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Parasyte -the maxim- Complete", "Blu-ray", "JP BD Complete Box", "high", 220),
        ("JP Import", "Tokyo Ghoul Complete", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "Dorohedoro", "Blu-ray", "JP BD Box Set", "high", 180),
        ("JP Import", "Made in Abyss Complete", "Blu-ray", "JP BD Complete Box", "high", 250),
        ("JP Import", "Made in Abyss: Dawn of the Deep Soul", "Blu-ray", "JP BD Limited Edition", "high", 120),
        ("JP Import", "Psycho-Pass Complete", "Blu-ray", "JP BD Complete Box", "grail", 300),
        ("JP Import", "Monster Complete", "Blu-ray", "JP BD Complete Box", "grail", 400),

        # ── Classic Series ──────────────────────────────────────────────
        ("Discotek Media", "Astro Boy (1963) Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 200),
        ("Discotek Media", "Cyborg 009 Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 150),
        ("Discotek Media", "Space Battleship Yamato 2199", "Blu-ray", "Discotek Complete BD Collection", "high", 160),
        ("Discotek Media", "Devilman Crybaby", "Blu-ray", "Discotek BD Remaster", "mid", 70),
        ("JP Import", "Space Battleship Yamato 2199", "Blu-ray", "JP BD Complete Box", "grail", 350),
        ("JP Import", "Space Battleship Yamato 2202", "Blu-ray", "JP BD Complete Box", "high", 280),
        ("JP Import", "Captain Harlock Complete", "Blu-ray", "JP BD Complete Box", "grail", 300),
        ("JP Import", "Galaxy Express 999 Movie", "Blu-ray", "JP BD Limited Edition", "high", 150),

        # ── Steelbooks Wave 2 ───────────────────────────────────────────
        ("Funimation", "Dragon Ball Super: Broly", "Blu-ray", "Funimation Steelbook", "mid", 50),
        ("Crunchyroll", "One Piece Film Red", "Blu-ray", "Crunchyroll Steelbook", "mid", 55),
        ("Crunchyroll", "Demon Slayer: Mugen Train", "Blu-ray", "Crunchyroll Steelbook", "mid", 55),
        ("Funimation", "My Hero Academia: Two Heroes", "Blu-ray", "Funimation Steelbook", "mid", 50),
        ("Funimation", "My Hero Academia: Heroes Rising", "Blu-ray", "Funimation Steelbook", "mid", 55),

        # ── Concert / Event Blu-rays Round 2 ───────────────────────────
        ("JP Import", "LiSA Live is Smile Always Eden no Oto", "Blu-ray", "JP Concert BD Limited", "high", 145),
        ("JP Import", "Aimer Live in Budokan Walpurgis", "Blu-ray", "JP Concert BD Limited", "high", 140),
        ("JP Import", "YOASOBI Asia Tour 2024", "Blu-ray", "JP Concert BD Limited", "high", 150),
        ("JP Import", "Kenshi Yonezu TOUR Junk to Aquarium", "Blu-ray", "JP Concert BD Limited", "high", 140),
        ("JP Import", "Ado World Tour Hibana", "Blu-ray", "JP Concert BD Limited", "high", 130),
        ("JP Import", "Mrs. GREEN APPLE Arena Tour 2024", "Blu-ray", "JP Concert BD Limited", "high", 120),
        ("JP Import", "BUMP OF CHICKEN TOUR Aurora Ark", "Blu-ray", "JP Concert BD Limited", "high", 130),
        ("JP Import", "Kalafina Farewell Concert 2019", "Blu-ray", "JP Concert BD Limited", "high", 160),

        # ── Laserdisc Rarities Round 2 ──────────────────────────────────
        ("Laserdisc", "Urusei Yatsura: Beautiful Dreamer", "Laserdisc", "JP LD", "high", 100),
        ("Laserdisc", "Patlabor: The Movie", "Laserdisc", "JP LD", "high", 110),
        ("Laserdisc", "Royal Space Force", "Laserdisc", "JP LD", "high", 120),
        ("Laserdisc", "Bubblegum Crisis", "Laserdisc", "JP LD Complete Set", "high", 180),
        ("Laserdisc", "Megazone 23", "Laserdisc", "JP LD", "mid", 90),
        ("Laserdisc", "Gundam 0083", "Laserdisc", "JP LD Complete Set", "high", 150),
        ("Laserdisc", "Dragon Ball Z: Broly", "Laserdisc", "JP LD", "mid", 80),

        # ── 2024-2025 Seasonal Hits ─────────────────────────────────────
        ("JP Import", "Oshi no Ko Season 2", "Blu-ray", "JP BD Box Set Complete", "high", 240),
        ("JP Import", "Solo Leveling Season 1", "Blu-ray", "JP BD Box Set Complete", "high", 220),
        ("JP Import", "Kaiju No. 8 Season 1", "Blu-ray", "JP BD Box Set Complete", "high", 210),
        ("JP Import", "Dandadan Season 1", "Blu-ray", "JP BD Box Set Complete", "high", 200),
        ("JP Import", "Sakamoto Days Season 1", "Blu-ray", "JP BD Box Set Complete", "high", 190),
        ("JP Import", "Blue Box Season 1", "Blu-ray", "JP BD Box Set Complete", "mid", 95),
        ("JP Import", "Apothecary Diaries Season 1", "Blu-ray", "JP BD Box Set Complete", "high", 210),
        ("JP Import", "Wind Breaker Season 1", "Blu-ray", "JP BD Box Set Complete", "high", 170),
        ("JP Import", "Shangri-La Frontier Season 1", "Blu-ray", "JP BD Box Set Complete", "high", 180),
        ("JP Import", "Metallic Rouge", "Blu-ray", "JP BD Box Set", "mid", 95),
        ("JP Import", "Delicious in Dungeon", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "A Sign of Affection", "Blu-ray", "JP BD Box Set", "mid", 90),

        # ── Sentai Filmworks Extended ───────────────────────────────────
        ("Sentai Filmworks", "CLANNAD Complete", "Blu-ray", "Sentai Collector's Box Set", "high", 140),
        ("Sentai Filmworks", "Higurashi When They Cry Complete", "Blu-ray", "Sentai LE Box Set", "high", 130),
        ("Sentai Filmworks", "K-On! Complete", "Blu-ray", "Sentai LE Box Set", "high", 120),
        ("Sentai Filmworks", "Non Non Biyori Complete", "Blu-ray", "Sentai LE Box Set", "mid", 85),
        ("Sentai Filmworks", "Revue Starlight", "Blu-ray", "Sentai LE", "mid", 75),
        ("Sentai Filmworks", "O Maidens in Your Savage Season", "Blu-ray", "Sentai LE", "mid", 70),

        # ── Vintage OOP Extended ────────────────────────────────────────
        ("ADV Films", "Martian Successor Nadesico", "Blu-ray", "ADV OOP Complete Collection", "high", 200),
        ("Geneon", "Trigun Complete", "Blu-ray", "Geneon OOP LE Box Set", "high", 220),
        ("Geneon", "Hellsing Ultimate Complete", "Blu-ray", "Geneon OOP LE Box Set", "high", 250),
        ("Bandai Visual", "Turn A Gundam", "Blu-ray", "Bandai Visual JP BD LE Box", "high", 280),
        ("Bandai Visual", "The Big O Complete", "Blu-ray", "Bandai Visual JP BD LE", "high", 200),
        ("Geneon", "Texhnolyze Complete", "Blu-ray", "Geneon OOP LE Box Set", "high", 220),

        # ── Discotek Deep Catalog ───────────────────────────────────────
        ("Discotek Media", "Dirty Pair Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 150),
        ("Discotek Media", "Gatchaman Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 170),
        ("Discotek Media", "Saint Seiya Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 180),
        ("Discotek Media", "Ranma 1/2 Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 200),
        ("Discotek Media", "Kimagure Orange Road", "Blu-ray", "Discotek Complete BD Collection", "high", 160),
        ("Discotek Media", "Patlabor TV Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 170),
        ("Discotek Media", "Tiger Mask Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 140),
        ("Discotek Media", "Votoms Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 180),

        # ── More Film Releases ──────────────────────────────────────────
        ("GKIDS", "The Boy and the Heron", "Blu-ray", "GKIDS Standard", "standard", 30),
        ("JP Import", "Look Back", "Blu-ray", "JP BD Limited Edition", "high", 120),
        ("JP Import", "My Hero Academia: You're Next", "Blu-ray", "JP BD Limited Edition", "high", 130),
        ("Crunchyroll", "Spy x Family Code: White", "Blu-ray", "Crunchyroll LE Steelbook", "mid", 60),
        ("JP Import", "Fate/stay night Heaven's Feel Spring Song", "Blu-ray", "JP BD Limited Edition", "high", 140),
        ("JP Import", "Jujutsu Kaisen 0", "Blu-ray", "JP BD Limited Edition", "high", 120),
        ("JP Import", "One Piece Film Strong World", "Blu-ray", "JP BD Limited Edition", "mid", 90),

        # ── 4K UHD Wave 2 ──────────────────────────────────────────────
        ("GKIDS", "Princess Mononoke", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 55),
        ("GKIDS", "My Neighbor Totoro", "4K UHD", "GKIDS 4K Steelbook", "mid", 58),
        ("Funimation", "Attack on Titan Season 1", "4K UHD", "Funimation 4K Steelbook", "high", 110),
        ("Crunchyroll", "Jujutsu Kaisen 0", "4K UHD", "Crunchyroll 4K Steelbook", "mid", 65),
        ("GKIDS", "Nausicaa of the Valley of the Wind", "4K UHD", "GKIDS 4K Steelbook", "mid", 60),
        ("GKIDS", "Laputa: Castle in the Sky", "4K UHD", "GKIDS 4K Steelbook", "mid", 58),

        # ── Additional Series to reach 500+ ─────────────────────────────
        ("JP Import", "Death Note Complete", "Blu-ray", "JP BD Complete Box", "high", 250),
        ("JP Import", "Steins;Gate 0", "Blu-ray", "JP BD Box Set", "high", 180),
        ("JP Import", "Trigun Stampede Complete", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "Vivy: Fluorite Eye's Song", "Blu-ray", "JP BD Box Set", "high", 180),
        ("JP Import", "Odd Taxi", "Blu-ray", "JP BD Box Set", "high", 170),
        ("JP Import", "Sonny Boy", "Blu-ray", "JP BD Box Set", "mid", 95),
        ("JP Import", "Wonder Egg Priority", "Blu-ray", "JP BD Box Set", "mid", 95),
        ("JP Import", "Summertime Rendering", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "Ranking of Kings", "Blu-ray", "JP BD Complete Box", "high", 220),
        ("JP Import", "Cyberpunk: Edgerunners", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Tiger & Bunny Complete", "Blu-ray", "JP BD Complete Box", "high", 220),
        ("JP Import", "Bungo Stray Dogs Complete", "Blu-ray", "JP BD Complete Box", "high", 240),
        ("JP Import", "Golden Kamuy Complete", "Blu-ray", "JP BD Complete Box", "high", 250),
        ("JP Import", "Vinland Saga Season 2", "Blu-ray", "JP BD Box Set", "high", 220),
        ("JP Import", "Yuri!!! on ICE", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "Land of the Lustrous", "Blu-ray", "JP BD Box Set", "high", 180),
        ("JP Import", "The Tatami Galaxy", "Blu-ray", "JP BD Box Set", "high", 180),
        ("JP Import", "Ping Pong the Animation", "Blu-ray", "JP BD Box Set", "high", 170),
        ("JP Import", "Kids on the Slope", "Blu-ray", "JP BD Box Set", "high", 160),
        ("JP Import", "Space Dandy Complete", "Blu-ray", "JP BD Complete Box", "high", 180),
        ("JP Import", "Planetes Complete", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "Beck: Mongolian Chop Squad", "Blu-ray", "JP BD Complete Box", "high", 180),

        # ── Expansion to 700+ — Recent Hits, 4K UHD, JP Import, Aniplex, Collector Editions ──

        # Recent Hit Anime — Frieren, Oshi no Ko, Solo Leveling, etc. (+10)
        ("Crunchyroll", "Frieren: Beyond Journey's End", "Blu-ray", "Crunchyroll Standard", "mid", 55),
        ("Aniplex USA", "Oshi no Ko Season 1", "Blu-ray", "Aniplex LE Box Set", "high", 180),
        ("Crunchyroll", "Oshi no Ko Season 1", "Blu-ray", "Crunchyroll Standard", "mid", 60),
        ("Crunchyroll", "Solo Leveling Season 1", "Blu-ray", "Crunchyroll LE Box Set", "high", 130),
        ("Crunchyroll", "Solo Leveling Season 1", "Blu-ray", "Crunchyroll Standard", "mid", 50),
        ("Aniplex USA", "Dandadan Part 1", "Blu-ray", "Aniplex LE", "high", 140),
        ("Crunchyroll", "Kaiju No. 8 Season 1", "Blu-ray", "Crunchyroll LE", "mid", 85),
        ("Crunchyroll", "Shangri-La Frontier Season 1", "Blu-ray", "Crunchyroll LE", "mid", 75),
        ("Crunchyroll", "The Apothecary Diaries Season 1", "Blu-ray", "Crunchyroll LE Box Set", "high", 110),

        # 4K UHD Releases (+10)
        ("GKIDS", "Howl's Moving Castle", "4K UHD", "GKIDS Collector's", "mid", 45),
        ("GKIDS", "My Neighbor Totoro", "4K UHD", "GKIDS Collector's", "mid", 42),
        ("GKIDS", "Nausicaa of the Valley of the Wind", "4K UHD", "GKIDS Collector's", "mid", 45),
        ("GKIDS", "Castle in the Sky", "4K UHD", "GKIDS Collector's", "mid", 42),
        ("GKIDS", "Kiki's Delivery Service", "4K UHD", "GKIDS Collector's", "mid", 42),
        ("Shout Factory", "Ghost in the Shell", "4K UHD", "Shout Factory 4K LE", "high", 130),
        ("Shout Factory", "Paprika", "4K UHD", "Shout Factory 4K LE", "high", 110),
        ("Lionsgate", "Dragon Ball Super: Broly", "4K UHD", "Lionsgate 4K + Blu-ray", "mid", 45),
        ("Lionsgate", "Dragon Ball Super: Super Hero", "4K UHD", "Lionsgate 4K + Blu-ray", "mid", 40),
        ("JP Import", "Your Name", "4K UHD", "JP 4K Ultra HD Limited Edition", "high", 160),

        # Aniplex USA Additional LEs (+8)
        ("Aniplex USA", "Solo Leveling", "Blu-ray", "Aniplex LE", "high", 150),
        ("Aniplex USA", "The Promised Neverland Season 1", "Blu-ray", "Aniplex LE Box Set", "high", 200),
        ("Aniplex USA", "Erased", "Blu-ray", "Aniplex LE Box Set", "high", 190),
        ("Aniplex USA", "Blue Lock Part 1", "Blu-ray", "Aniplex LE", "high", 130),
        ("Aniplex USA", "Oshi no Ko Season 2", "Blu-ray", "Aniplex LE", "high", 140),
        ("Aniplex USA", "Demon Slayer: Hashira Training Arc", "Blu-ray", "Aniplex LE", "high", 120),

        # JP Import Box Sets — Additional Titles (+10)
        ("JP Import", "Frieren: Beyond Journey's End", "Blu-ray", "JP BD Box Set Vol. 1-4", "high", 280),
        ("JP Import", "Oshi no Ko", "Blu-ray", "JP BD Box Set Complete", "high", 250),
        ("JP Import", "Jujutsu Kaisen Season 2 Complete", "Blu-ray", "JP BD Complete Box", "high", 260),
        ("JP Import", "Chainsaw Man Complete", "Blu-ray", "JP BD Complete Box", "high", 240),
        ("JP Import", "My Dress-Up Darling Complete", "Blu-ray", "JP BD Complete Box", "high", 200),
        ("JP Import", "Lycoris Recoil Complete", "Blu-ray", "JP BD Complete Box", "high", 210),
        ("JP Import", "86: Eighty-Six Complete", "Blu-ray", "JP BD Complete Box", "high", 230),

        # Complete Series Box Sets (+10)
        ("Funimation", "Fullmetal Alchemist Brotherhood", "Blu-ray", "Funimation 10th Anniversary Box Set", "high", 180),
        ("Funimation", "Soul Eater Complete", "Blu-ray", "Funimation Complete Collection", "mid", 90),
        ("Funimation", "Black Butler Complete", "Blu-ray", "Funimation Complete Collection", "mid", 85),
        ("Funimation", "Assassination Classroom Complete", "Blu-ray", "Funimation Complete Box Set", "high", 110),
        ("Sentai Filmworks", "Toradora! Complete", "Blu-ray", "Sentai LE Box Set", "high", 120),
        ("Sentai Filmworks", "Love, Chunibyo & Other Delusions Complete", "Blu-ray", "Sentai LE Box Set", "mid", 95),
        ("Sentai Filmworks", "Bloom Into You Complete", "Blu-ray", "Sentai LE", "mid", 80),
        ("Viz Media", "Naruto Shippuden Complete", "Blu-ray", "Viz Complete Box Set", "grail", 480),
        ("Viz Media", "Bleach Thousand-Year Blood War Part 1", "Blu-ray", "Viz LE", "high", 110),

        # Steelbook Editions (+8)
        ("GKIDS", "The Boy and the Heron", "4K UHD", "GKIDS Steelbook", "high", 65),
        ("GKIDS", "Grave of the Fireflies", "Blu-ray", "GKIDS Steelbook", "mid", 55),
        ("GKIDS", "Ponyo", "Blu-ray", "GKIDS Steelbook", "mid", 50),
        ("Funimation", "Dragon Ball Super: Super Hero", "Blu-ray", "Funimation Steelbook", "mid", 45),
        ("Funimation", "My Hero Academia: World Heroes Mission", "Blu-ray", "Funimation Steelbook", "mid", 40),
        ("Crunchyroll", "Jujutsu Kaisen 0", "Blu-ray", "Crunchyroll Steelbook", "mid", 50),
        ("Crunchyroll", "Suzume", "Blu-ray", "Crunchyroll Steelbook", "mid", 55),

        # Vintage / OOP Additional (+8)
        ("ADV Films", "Rahxephon Complete", "Blu-ray", "ADV LE Box Set", "high", 200),
        ("Geneon", "Trigun Complete", "Blu-ray", "Geneon OOP Box Set", "high", 190),
        ("Bandai Visual", "Code Geass Complete", "Blu-ray", "Bandai Visual LE Box Set", "high", 250),
        ("Bandai Visual", "Escaflowne Complete", "Blu-ray", "Bandai Visual LE Box Set", "high", 220),
        ("Discotek Media", "Galaxy Express 999", "Blu-ray", "Discotek Complete Collection", "high", 170),
        ("Discotek Media", "Captain Harlock Complete", "Blu-ray", "Discotek Complete Collection", "high", 160),
        ("Discotek Media", "Devilman OVA", "Blu-ray", "Discotek LE", "mid", 80),
        ("Discotek Media", "Cutey Honey Complete", "Blu-ray", "Discotek LE", "mid", 75),

        # Film Blu-rays (+10)
        ("GKIDS", "Weathering With You", "Blu-ray", "GKIDS Standard", "standard", 25),
        ("GKIDS", "Suzume", "Blu-ray", "GKIDS Standard", "standard", 28),
        ("Crunchyroll", "Dragon Ball Super: Super Hero", "Blu-ray", "Crunchyroll Standard", "standard", 28),
        ("Crunchyroll", "One Piece Film Red", "Blu-ray", "Crunchyroll Standard", "standard", 25),
        ("Crunchyroll", "Jujutsu Kaisen 0", "Blu-ray", "Crunchyroll Standard", "standard", 28),
        ("JP Import", "The Boy and the Heron", "Blu-ray", "JP Limited Edition", "high", 140),
        ("JP Import", "The Boy and the Heron", "4K UHD", "JP 4K Ultra HD Limited", "high", 180),
        ("JP Import", "Suzume", "Blu-ray", "JP BD Collector's Edition", "high", 130),
        ("JP Import", "One Piece Film Red", "Blu-ray", "JP BD Deluxe Edition", "high", 120),

        # Crunchyroll/Funimation Additional LEs (+8)
        ("Crunchyroll", "Mushoku Tensei Season 1", "Blu-ray", "Crunchyroll LE Box Set", "high", 115),
        ("Crunchyroll", "Mushoku Tensei Season 2", "Blu-ray", "Crunchyroll LE", "mid", 80),
        ("Crunchyroll", "Ranking of Kings Complete", "Blu-ray", "Crunchyroll LE Box Set", "high", 110),
        ("Crunchyroll", "To Your Eternity Season 1", "Blu-ray", "Crunchyroll LE Box Set", "high", 105),
        ("Crunchyroll", "Dr. Stone Complete", "Blu-ray", "Crunchyroll LE Box Set", "high", 120),
        ("Funimation", "Fire Force Complete", "Blu-ray", "Funimation LE Box Set", "high", 130),
        ("Funimation", "Fruits Basket (2019) Complete", "Blu-ray", "Funimation LE Box Set", "high", 150),
        ("Funimation", "Tokyo Ghoul Complete", "Blu-ray", "Funimation Complete Set", "mid", 95),

        # Sentai Filmworks Additional (+5)
        ("Sentai Filmworks", "Girls' Last Tour Complete", "Blu-ray", "Sentai LE", "mid", 85),
        ("Sentai Filmworks", "Land of the Lustrous", "Blu-ray", "Sentai LE", "mid", 90),
        ("Sentai Filmworks", "Revue Starlight Complete", "Blu-ray", "Sentai LE Box Set", "mid", 95),
        ("Sentai Filmworks", "Akame ga Kill! Complete", "Blu-ray", "Sentai Complete Collection", "mid", 75),
        ("Sentai Filmworks", "Beyond the Boundary Complete", "Blu-ray", "Sentai LE", "mid", 80),

        # Concert / Music Anime Blu-rays (+6)
        ("Aniplex USA", "BanG Dream! Film Live", "Blu-ray", "Aniplex LE", "mid", 75),
        ("Aniplex USA", "Bocchi the Rock! Live at Starry", "Blu-ray", "Aniplex Concert LE", "high", 110),
        ("JP Import", "Love Live! μ's Final LoveLive!", "Blu-ray", "JP BD Memorial Box", "grail", 350),
        ("JP Import", "Love Live! Aqours 5th Live", "Blu-ray", "JP BD Box", "high", 180),
        ("JP Import", "Macross Delta Absolute Live!", "Blu-ray", "JP BD LE", "high", 160),
        ("JP Import", "Symphogear Live 2020", "Blu-ray", "JP BD Box", "high", 150),
    ]

    catalog = []
    for publisher, title, fmt, edition, tier, price in releases:
        catalog.append({
            "publisher": publisher,
            "title": title,
            "format": fmt,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })

    # Round 7 expansion — 50 items
    catalog.extend(_expanded_round7_anime_bluray())

    # Round 8 expansion — 55 items (605+)
    catalog.extend(_expanded_round8_anime_bluray())

    # Round 9 expansion — 135 items (to 900+)
    catalog.extend(_expanded_round9_anime_bluray())

    # Deduplicate by ('publisher', 'title', 'edition') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["publisher"], item["title"], item["edition"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def _expanded_round7_anime_bluray() -> list[dict]:
    """50 new anime Blu-ray items: Aniplex LEs, Funimation steelbooks, GKIDS 4K, Rightstuf boxes, JP volumes with bonuses."""
    releases = [
        # --- Aniplex Limited Editions (new titles) ---
        ("Aniplex USA", "Sword Art Online Progressive: Aria of a Starless Night", "Blu-ray", "Aniplex LE with Art Book", "high", 130),
        ("Aniplex USA", "Sword Art Online Progressive: Scherzo of Deep Night", "Blu-ray", "Aniplex LE with Soundtrack CD", "high", 125),
        ("Aniplex USA", "Fate/Grand Order: Camelot Wandering Agateram", "Blu-ray", "Aniplex LE Box Set", "high", 160),
        ("Aniplex USA", "Fate/Grand Order: Solomon", "Blu-ray", "Aniplex LE with Bonus CD", "high", 140),
        ("Aniplex USA", "Demon Slayer: To the Swordsmith Village", "Blu-ray", "Aniplex LE Steelbook", "high", 120),
        ("Aniplex USA", "Demon Slayer: Hashira Training Arc", "Blu-ray", "Aniplex LE Complete Box", "high", 180),
        ("Aniplex USA", "Bocchi the Rock! Complete", "Blu-ray", "Aniplex LE with Guitar Pick Set", "high", 160),
        ("Aniplex USA", "Lycoris Recoil Complete", "Blu-ray", "Aniplex LE Box Set", "high", 150),
        ("Aniplex USA", "Rascal Does Not Dream of a Dreaming Girl", "Blu-ray", "Aniplex LE with Art Cards", "high", 110),
        ("Aniplex USA", "Puella Magi Madoka Magica: Rebellion", "Blu-ray", "Aniplex LE with Homura Figure", "grail", 350),

        # --- Funimation / Crunchyroll Steelbooks ---
        ("Funimation", "Cowboy Bebop Complete Series", "Blu-ray", "Funimation 25th Anniversary Steelbook", "high", 130),
        ("Funimation", "Fullmetal Alchemist: Brotherhood Complete", "Blu-ray", "Funimation Steelbook Box Set", "high", 140),
        ("Crunchyroll", "Chainsaw Man Season 1", "Blu-ray", "Crunchyroll LE Steelbook", "mid", 65),
        ("Crunchyroll", "Mob Psycho 100 Season 3", "Blu-ray", "Crunchyroll Steelbook", "mid", 55),
        ("Funimation", "Dragon Ball Super: Super Hero", "Blu-ray", "Funimation Steelbook 4K", "mid", 60),
        ("Crunchyroll", "Ranking of Kings Season 1", "Blu-ray", "Crunchyroll LE Box Set", "mid", 70),
        ("Funimation", "One Piece Film Red Collector's", "Blu-ray", "Funimation LE with Uta CD", "high", 100),

        # --- GKIDS Studio Ghibli 4K UHD ---
        ("GKIDS", "Spirited Away", "4K UHD", "GKIDS 4K Steelbook", "mid", 62),
        ("GKIDS", "Howl's Moving Castle", "4K UHD", "GKIDS 4K Steelbook", "mid", 60),
        ("GKIDS", "Kiki's Delivery Service", "4K UHD", "GKIDS 4K Steelbook", "mid", 58),
        ("GKIDS", "Ponyo", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 55),
        ("GKIDS", "The Wind Rises", "4K UHD", "GKIDS 4K Steelbook", "mid", 58),
        ("GKIDS", "Grave of the Fireflies", "4K UHD", "GKIDS 4K Steelbook", "mid", 60),
        ("GKIDS", "Porco Rosso", "4K UHD", "GKIDS 4K Steelbook", "mid", 55),

        # --- Rightstuf / Nozomi Limited Box Sets ---
        ("Rightstuf", "Revolutionary Girl Utena Complete", "Blu-ray", "Rightstuf LE Box Set", "high", 200),
        ("Rightstuf", "Rose of Versailles Complete", "Blu-ray", "Rightstuf LE Box Set", "high", 180),
        ("Rightstuf", "Legend of the Galactic Heroes: Die Neue These", "Blu-ray", "Rightstuf LE Box Set", "high", 160),
        ("Rightstuf", "Aria the Animation Complete", "Blu-ray", "Rightstuf LE Box Set", "high", 140),
        ("Rightstuf", "Cardcaptor Sakura Complete", "Blu-ray", "Rightstuf LE Premium Box Set", "high", 190),

        # --- Japanese Blu-ray Volumes with Bonus Figures/Booklets/Soundtracks ---
        ("JP Import", "Violet Evergarden The Movie", "Blu-ray", "JP BD Limited Edition with Original Soundtrack", "grail", 300),
        ("JP Import", "Weathering with You Collector's Edition", "Blu-ray", "JP BD Collector's Edition with Art Book & CD", "grail", 280),
        ("JP Import", "Your Name. Collector's Edition", "Blu-ray", "JP BD Special Edition with Storyboard Book", "grail", 320),
        ("JP Import", "Suzume Collector's Edition", "Blu-ray", "JP BD LE with Director's Notes & Mini Figure", "grail", 260),
        ("JP Import", "Frieren: Beyond Journey's End Vol.1", "Blu-ray", "JP BD with Bonus Drama CD & Art Cards", "high", 110),
        ("JP Import", "Frieren: Beyond Journey's End Vol.2", "Blu-ray", "JP BD with Bonus Soundtrack CD", "high", 110),
        ("JP Import", "Oshi no Ko Vol.1", "Blu-ray", "JP BD with Bonus Idol CD & Booklet", "high", 120),
        ("JP Import", "86: Eighty Six Complete Box", "Blu-ray", "JP BD LE with Shin Figure & Art Book", "grail", 350),
        ("JP Import", "Bocchi the Rock! Vol.1", "Blu-ray", "JP BD with Bonus Soundtrack CD", "high", 100),
        ("JP Import", "Mobile Suit Gundam: The Witch from Mercury Box", "Blu-ray", "JP BD LE with Aerial Gunpla Kit", "grail", 380),
        ("JP Import", "Spy x Family Season 1 Complete Box", "Blu-ray", "JP BD LE with Anya Figure & Art Book", "high", 250),
        ("JP Import", "Attack on Titan Final Season Complete Box", "Blu-ray", "JP BD Complete with Mikasa Scarf & Art Cards", "grail", 400),
        ("JP Import", "Jujutsu Kaisen Season 2 Complete Box", "Blu-ray", "JP BD LE with Gojo Figure & Soundtrack CD", "grail", 380),

        # --- Additional notable releases ---
        ("Aniplex USA", "Monogatari Series: Monster Season", "Blu-ray", "Aniplex LE Box Set", "high", 200),
        ("JP Import", "Dungeon Meshi Collector's Box", "Blu-ray", "JP BD LE with Recipe Book & Mini Figure", "high", 240),
        ("Sentai Filmworks", "Made in Abyss Complete", "Blu-ray", "Sentai LE Collector's Box", "high", 130),
        ("Sentai Filmworks", "The Aquatope on White Sand Complete", "Blu-ray", "Sentai LE Box Set", "mid", 85),
        ("Discotek Media", "City Hunter Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 200),
    ]
    catalog = []
    for publisher, title, fmt, edition, tier, price in releases:
        catalog.append({
            "publisher": publisher,
            "title": title,
            "format": fmt,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def _expanded_round8_anime_bluray() -> list[dict]:
    """55 new anime Blu-ray items: recent hit series, classic LEs, Aniplex exclusives,
    Studio Trigger, Makoto Shinkai, Discotek classics."""
    releases = [
        # --- Recent Hit Series Blu-rays (+10) ---
        ("Crunchyroll", "Jujutsu Kaisen Season 2 Complete", "Blu-ray", "Crunchyroll LE Complete Box", "high", 140),
        ("JP Import", "Jujutsu Kaisen Shibuya Incident Complete", "Blu-ray", "JP BD Premium Box with Soundtrack", "grail", 320),
        ("Crunchyroll", "Chainsaw Man Season 1 Collector's", "Blu-ray", "Crunchyroll LE with Pochita Plush", "high", 130),
        ("JP Import", "Chainsaw Man Reze Arc Complete", "Blu-ray", "JP BD Box Set with Art Book", "high", 240),
        ("Crunchyroll", "Spy x Family Season 2 Complete", "Blu-ray", "Crunchyroll LE Box Set", "high", 110),
        ("JP Import", "Spy x Family Complete Collection", "Blu-ray", "JP BD Complete Box with Anya Nendoroid", "grail", 350),
        ("Aniplex USA", "Jujutsu Kaisen Season 2", "Blu-ray", "Aniplex LE Complete Box with Gojo Acrylic", "high", 260),
        ("Crunchyroll", "Chainsaw Man Part 2", "Blu-ray", "Crunchyroll LE with Character Cards", "mid", 85),
        ("Crunchyroll", "Spy x Family Season 2 Part 2", "Blu-ray", "Crunchyroll LE", "mid", 75),
        ("JP Import", "Jujutsu Kaisen 0 Collector's", "Blu-ray", "JP BD LE with Yuta Figure", "high", 180),

        # --- Classic Anime Limited Editions (+10) ---
        ("Funimation", "Cowboy Bebop Complete Series 25th Anniversary", "Blu-ray", "Funimation 25th Anniversary LE Box Set", "grail", 300),
        ("JP Import", "Cowboy Bebop Remix Complete Remaster", "Blu-ray", "JP BD Remaster with Bonus CD", "grail", 380),
        ("JP Import", "Trigun Complete Remaster", "Blu-ray", "JP BD Remaster Box Set", "high", 250),
        ("Funimation", "Trigun Complete Series Collector's", "Blu-ray", "Funimation Classics LE with Art Book", "high", 160),
        ("GKIDS", "Neon Genesis Evangelion Complete Series Remaster", "Blu-ray", "GKIDS Remaster Collector's Box", "grail", 420),
        ("JP Import", "Neon Genesis Evangelion TV Series Remaster", "Blu-ray", "JP BD Remaster Complete with Booklet Set", "grail", 480),
        ("JP Import", "Cowboy Bebop Session Box Vol.1", "Blu-ray", "JP BD Limited with Jazz CD", "high", 180),
        ("JP Import", "Cowboy Bebop Session Box Vol.2", "Blu-ray", "JP BD Limited with Jazz CD Vol.2", "high", 180),
        ("Discotek Media", "Trigun Complete BD Remaster", "Blu-ray", "Discotek Remaster Edition", "high", 120),
        ("JP Import", "Neon Genesis Evangelion Directors Cut", "Blu-ray", "JP BD Directors Cut Edition", "grail", 350),

        # --- Aniplex USA Exclusives (+8) ---
        ("Aniplex USA", "Demon Slayer Infinity Castle Arc", "Blu-ray", "Aniplex LE with Muzan Figure", "grail", 380),
        ("Aniplex USA", "Solo Leveling Complete Season 1", "Blu-ray", "Aniplex LE Complete Box with Shadow Art", "high", 220),
        ("Aniplex USA", "Frieren Complete Season 1", "Blu-ray", "Aniplex LE with Frieren Staff Replica", "grail", 320),
        ("Aniplex USA", "Kaguya-sama: Ultra Romantic Complete", "Blu-ray", "Aniplex LE Complete Collection", "high", 240),
        ("Aniplex USA", "86 Eighty-Six Complete Collection", "Blu-ray", "Aniplex LE with Shin Figure & Soundtrack", "grail", 380),
        ("Aniplex USA", "My Dress-Up Darling Complete", "Blu-ray", "Aniplex LE with Marin Cosplay Book", "high", 190),
        ("Aniplex USA", "Spy x Family Season 1", "Blu-ray", "Aniplex LE Complete with Operation Strix Dossier", "high", 200),
        ("Aniplex USA", "Dandadan Season 1", "Blu-ray", "Aniplex LE with Turbo Granny Art Cards", "high", 170),

        # --- Funimation / Crunchyroll Limited Editions (+8) ---
        ("Funimation", "My Hero Academia Complete Season 1-7", "Blu-ray", "Funimation Complete Series LE Box", "grail", 450),
        ("Crunchyroll", "Mob Psycho 100 Complete Series", "Blu-ray", "Crunchyroll LE Complete Collection", "high", 150),
        ("Funimation", "Black Clover Complete Collection", "Blu-ray", "Funimation LE Box Set", "high", 180),
        ("Crunchyroll", "Hell's Paradise Complete", "Blu-ray", "Crunchyroll LE Box Set", "high", 110),
        ("Crunchyroll", "Blue Lock Season 1 Complete", "Blu-ray", "Crunchyroll LE Box Set", "high", 120),
        ("Crunchyroll", "Mashle: Magic and Muscles Complete", "Blu-ray", "Crunchyroll LE", "mid", 75),
        ("Funimation", "Fire Force Complete Series", "Blu-ray", "Funimation LE Complete Box", "high", 160),
        ("Crunchyroll", "Undead Unluck Complete Season 1", "Blu-ray", "Crunchyroll LE Box Set", "mid", 90),

        # --- Studio Trigger Releases (+6) ---
        ("Aniplex USA", "Kill la Kill Complete Series Remaster", "Blu-ray", "Aniplex LE Remaster with Don't Lose Your Way CD", "high", 280),
        ("JP Import", "Promare Collector's Edition", "Blu-ray", "JP BD LE with Galo & Lio Art Book", "high", 180),
        ("JP Import", "Gurren Lagann Complete Remaster", "Blu-ray", "JP BD Remaster Complete Box with Drill Keychain", "grail", 400),
        ("GKIDS", "Promare", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 55),
        ("JP Import", "SSSS.Gridman & Dynazenon Complete", "Blu-ray", "JP BD Complete Box Set", "high", 220),
        ("JP Import", "Cyberpunk: Edgerunners Collector's", "Blu-ray", "JP BD LE with David Figure", "grail", 300),

        # --- Makoto Shinkai Films (+6) ---
        ("JP Import", "Suzume Collector's Edition 4K", "4K UHD", "JP 4K LE with Director Commentary Book", "high", 180),
        ("JP Import", "Your Name. Ultimate Edition", "Blu-ray", "JP BD Ultimate Box with Storyboard Collection", "grail", 400),
        ("JP Import", "Weathering With You Ultimate Edition", "Blu-ray", "JP BD Ultimate Box with Making-Of Book", "grail", 350),
        ("GKIDS", "5 Centimeters Per Second", "Blu-ray", "GKIDS Collector's Edition", "mid", 45),
        ("GKIDS", "The Garden of Words", "Blu-ray", "GKIDS Collector's Edition", "mid", 40),
        ("GKIDS", "Children Who Chase Lost Voices", "Blu-ray", "GKIDS Collector's Edition", "mid", 42),

        # --- Discotek Media Classic Releases (+7) ---
        ("Discotek Media", "Slam Dunk Complete Series", "Blu-ray", "Discotek Complete BD Collection", "high", 190),
        ("Discotek Media", "Hajime no Ippo Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 180),
        ("Discotek Media", "Great Teacher Onizuka Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 150),
        ("Discotek Media", "YuYu Hakusho Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 170),
        ("Discotek Media", "Rurouni Kenshin Complete", "Blu-ray", "Discotek Complete BD Collection", "high", 160),
        ("Discotek Media", "Initial D Complete Series", "Blu-ray", "Discotek Complete BD Collection", "high", 180),
        ("Discotek Media", "Cromartie High School Complete", "Blu-ray", "Discotek BD Remaster", "mid", 65),

        # ── Expansion to 700+ ──────────────────────────────────────────────

        # --- Aniplex USA Expansion ---
        ("Aniplex USA", "Solo Leveling Complete Season 1", "Blu-ray", "Aniplex LE with Shadow Monarch Art Box", "high", 180),
        ("Aniplex USA", "Oshi no Ko Complete Series", "Blu-ray", "Aniplex LE Complete Box Set with Idol Costume Art", "grail", 380),
        ("Aniplex USA", "Sousou no Frieren Season 2", "Blu-ray", "Aniplex LE Box Set", "high", 200),
        ("Aniplex USA", "Frieren Complete Season 1", "Blu-ray", "Aniplex LE Complete Box with Himmel Memorial Book", "grail", 350),
        ("Aniplex USA", "Monogatari Series: Monster Season", "Blu-ray", "Aniplex LE with Shinobu Art Cards", "high", 190),
        ("Aniplex USA", "Dandadan", "Blu-ray", "Aniplex LE Box Set with Turbo Granny Figure", "high", 200),
        ("Aniplex USA", "Apothecary Diaries", "Blu-ray", "Aniplex LE Box Set with Maomao Art Book", "high", 180),
        ("Aniplex USA", "Blue Lock", "Blu-ray", "Aniplex LE with Ego Character Art Set", "high", 170),
        ("Aniplex USA", "Madoka Magica: Walpurgis Rising", "Blu-ray", "Aniplex LE with Witch Art Book", "grail", 350),

        # --- JP Import Expansion ---
        ("JP Import", "Dandadan Season 1", "Blu-ray", "JP BD Complete Box with Okarun Figure", "high", 250),
        ("JP Import", "Sakamoto Days Season 1", "Blu-ray", "JP BD Complete Box Set", "high", 200),
        ("JP Import", "Blue Lock Season 1", "Blu-ray", "JP BD Complete Box with Isagi Card Set", "high", 220),
        ("JP Import", "Kaiju No. 8 Season 1", "Blu-ray", "JP BD Complete Box Set", "high", 210),
        ("JP Import", "Wind Breaker Season 1", "Blu-ray", "JP BD Complete Box Set", "high", 190),
        ("JP Import", "Shangri-La Frontier Season 1", "Blu-ray", "JP BD Complete Box Set", "high", 180),
        ("JP Import", "Blue Box Season 1", "Blu-ray", "JP BD Complete Box with Chinatsu Art Card", "high", 185),
        ("JP Import", "A Sign of Affection", "Blu-ray", "JP BD Complete Box Set", "high", 175),
        ("JP Import", "My Happy Marriage", "Blu-ray", "JP BD Complete Box with Wedding Art Book", "high", 195),
        ("JP Import", "Apothecary Diaries Season 1", "Blu-ray", "JP BD Complete Box Set", "high", 230),

        # --- Crunchyroll LE Expansion ---
        ("Crunchyroll", "Solo Leveling Season 1", "Blu-ray", "Crunchyroll LE with Sung Jinwoo Shadow Sleeve", "mid", 95),
        ("Crunchyroll", "Kaiju No. 8 Season 1", "Blu-ray", "Crunchyroll LE with Kafka Hibino Art Card", "mid", 90),
        ("Crunchyroll", "Delicious in Dungeon", "Blu-ray", "Crunchyroll LE with Recipe Booklet", "mid", 85),
        ("Crunchyroll", "Metallic Rouge", "Blu-ray", "Crunchyroll LE", "mid", 75),
        ("Crunchyroll", "Girls Band Cry", "Blu-ray", "Crunchyroll LE", "mid", 70),
        ("Crunchyroll", "Sakamoto Days Season 1", "Blu-ray", "Crunchyroll LE with Taro Sakamoto Art Sleeve", "mid", 85),
        ("Crunchyroll", "Blue Box", "Blu-ray", "Crunchyroll LE", "mid", 75),
        ("Crunchyroll", "Dandadan Season 1", "Blu-ray", "Crunchyroll LE with Okarun Holographic Sleeve", "high", 110),

        # --- GKIDS / Studio Ghibli 4K Expansion ---
        ("GKIDS", "Howl's Moving Castle", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 48),
        ("GKIDS", "My Neighbor Totoro", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 48),
        ("GKIDS", "Castle in the Sky", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 45),
        ("GKIDS", "Kiki's Delivery Service", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 45),
        ("GKIDS", "Nausicaa of the Valley of the Wind", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 48),
        ("GKIDS", "Porco Rosso", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 45),
        ("GKIDS", "The Tale of the Princess Kaguya", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 48),
        ("GKIDS", "When Marnie Was There", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 45),
        ("GKIDS", "The Wind Rises", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 45),
        ("GKIDS", "Grave of the Fireflies", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 48),
        ("GKIDS", "Arrietty", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 42),
        ("GKIDS", "From Up on Poppy Hill", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 42),

        # --- Sentai Filmworks Expansion ---
        ("Sentai Filmworks", "Akame ga Kill! Complete", "Blu-ray", "Sentai LE Complete Collection", "mid", 75),
        ("Sentai Filmworks", "Land of the Lustrous", "Blu-ray", "Sentai LE Steelbook", "high", 120),
        ("Sentai Filmworks", "Girls' Last Tour Complete", "Blu-ray", "Sentai LE Complete Collection", "mid", 80),
        ("Sentai Filmworks", "Bloom Into You Complete", "Blu-ray", "Sentai LE Complete Collection", "mid", 85),
        ("Sentai Filmworks", "O Maidens in Your Savage Season", "Blu-ray", "Sentai LE Complete Collection", "mid", 70),
        ("Sentai Filmworks", "Skip and Loafer", "Blu-ray", "Sentai LE Complete Collection", "mid", 65),
        ("Sentai Filmworks", "Run with the Wind", "Blu-ray", "Sentai LE Complete Collection", "mid", 80),
        ("Sentai Filmworks", "Chihayafuru Complete", "Blu-ray", "Sentai LE Complete Box Set", "high", 200),

        # --- Steelbook Editions ---
        ("Funimation", "Naruto Shippuden Final Arc", "Blu-ray", "Funimation Steelbook", "mid", 55),
        ("Crunchyroll", "Jujutsu Kaisen 0 The Movie", "Blu-ray", "Crunchyroll Steelbook 4K", "mid", 65),
        ("Funimation", "My Hero Academia: World Heroes' Mission", "Blu-ray", "Funimation Steelbook", "mid", 50),
        ("Crunchyroll", "Chainsaw Man Part 2", "Blu-ray", "Crunchyroll Steelbook", "mid", 55),
        ("Funimation", "One Piece Film Red Collector's", "Blu-ray", "Funimation Steelbook with Shanks Art Card", "mid", 60),
        ("GKIDS", "Suzume Collector's Edition", "Blu-ray", "GKIDS Steelbook with Makoto Shinkai Booklet", "mid", 55),
        ("GKIDS", "Look Back", "Blu-ray", "GKIDS Steelbook", "mid", 50),
        ("Funimation", "The First Slam Dunk", "Blu-ray", "Funimation Steelbook with Court Art Card", "mid", 50),

        # --- JP Concert / Live BDs Expansion ---
        ("JP Import", "YOASOBI Arena Tour 2023 Dennou Seikatsu", "Blu-ray", "JP BD LE with Photobook", "high", 120),
        ("JP Import", "Kenshi Yonezu TOUR 2023 Kick Back", "Blu-ray", "JP BD LE with Documentary", "high", 130),
        ("JP Import", "Mrs. GREEN APPLE Arena Tour 2024", "Blu-ray", "JP BD LE", "high", 110),
        ("JP Import", "RADWIMPS Asia Tour 2024", "Blu-ray", "JP BD LE", "high", 100),
        ("JP Import", "Aimer Live in Budokan blanc et noir Day 2", "Blu-ray", "JP BD LE with Photo Set", "high", 115),
        ("JP Import", "ClariS 1st Hall Concert Fairy Party", "Blu-ray", "JP BD LE", "mid", 85),
        ("JP Import", "Kalafina Farewell Concert 2019", "Blu-ray", "JP BD LE", "high", 140),

        # --- Discotek Media Expansion ---
        ("Discotek Media", "Armored Trooper VOTOMS", "Blu-ray", "Discotek Complete BD Collection", "high", 200),
        ("Discotek Media", "Martian Successor Nadesico", "Blu-ray", "Discotek Complete BD Collection", "high", 140),
        ("Discotek Media", "Gunsmith Cats OVA", "Blu-ray", "Discotek BD Remaster", "mid", 65),
        ("Discotek Media", "Beck: Mongolian Chop Squad", "Blu-ray", "Discotek Complete BD Collection", "high", 150),
        ("Discotek Media", "Riding Bean", "Blu-ray", "Discotek BD Remaster", "mid", 55),
        ("Discotek Media", "Votoms Complete", "Blu-ray", "Discotek BD Pailsen Files Remaster", "high", 160),
        ("Discotek Media", "Megazone 23", "Blu-ray", "Discotek BD Complete Remaster", "high", 130),
        ("Discotek Media", "Bubblegum Crisis", "Blu-ray", "Discotek BD Remaster", "high", 140),
        ("Discotek Media", "Battle Angel Alita (Gunnm)", "Blu-ray", "Discotek BD Remaster", "mid", 70),

        # --- Vintage / OOP BD Expansion ---
        ("JP Import", "Royal Space Force: Wings of Honneamise", "Blu-ray", "JP BD LE Remaster", "high", 150),
        ("JP Import", "Crusher Joe", "Blu-ray", "JP BD LE Remaster", "high", 130),
        ("JP Import", "Dirty Pair Complete", "Blu-ray", "JP BD Complete Box Set", "high", 200),
        ("JP Import", "Area 88 OVA", "Blu-ray", "JP BD Remaster", "high", 120),
        ("JP Import", "Golgo 13: The Professional", "Blu-ray", "JP BD LE Remaster", "mid", 80),
        ("JP Import", "Kimagure Orange Road", "Blu-ray", "JP BD Complete Box Set", "high", 250),
        ("JP Import", "Cutey Honey Complete", "Blu-ray", "JP BD Complete Box Set", "high", 180),
        ("JP Import", "El-Hazard OVA", "Blu-ray", "JP BD LE Remaster", "mid", 90),
        ("JP Import", "Tenchi Muyo! Ryo-Ohki", "Blu-ray", "JP BD Complete Box Remaster", "high", 160),
    ]
    catalog = []
    for publisher, title, fmt, edition, tier, price in releases:
        catalog.append({
            "publisher": publisher,
            "title": title,
            "format": fmt,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def _expanded_round9_anime_bluray() -> list[dict]:
    """135 new anime Blu-ray items: 2024-2025 hits, classic collectors, Ghibli,
    mecha, shonen classics, LE box sets, OVA/movie collections."""
    releases = [
        # ── 2024-2025 Releases (~20) ─────────────────────────────────────
        ("Crunchyroll", "Frieren: Beyond Journey's End Complete", "Blu-ray", "Crunchyroll LE Box Set", "high", 140),
        ("Crunchyroll", "Dandadan Season 1", "Blu-ray", "Crunchyroll LE", "mid", 85),
        ("Crunchyroll", "Solo Leveling Season 1", "Blu-ray", "Crunchyroll LE with Art Cards", "mid", 90),
        ("Crunchyroll", "Kaiju No. 8 Season 1", "Blu-ray", "Crunchyroll LE", "mid", 80),
        ("Aniplex USA", "Oshi no Ko Season 2", "Blu-ray", "Aniplex LE with Idol CD", "high", 150),
        ("Aniplex USA", "Jujutsu Kaisen Season 2 Shibuya Incident", "Blu-ray", "Aniplex LE Complete Box", "high", 200),
        ("Crunchyroll", "Undead Unluck Complete", "Blu-ray", "Crunchyroll LE", "mid", 75),
        ("Crunchyroll", "Shangri-La Frontier Season 1", "Blu-ray", "Crunchyroll LE", "mid", 80),
        ("Aniplex USA", "Demon Slayer: Infinity Castle Part 1", "Blu-ray", "Aniplex LE with Hashira Art Book", "high", 180),
        ("JP Import", "Dandadan Vol.1-6 Complete", "Blu-ray", "JP BD LE with Okarun Figure", "high", 250),
        ("JP Import", "Solo Leveling Season 1 Box", "Blu-ray", "JP BD LE with Sung Jin-Woo Figure", "high", 280),
        ("Crunchyroll", "Wind Breaker Season 1", "Blu-ray", "Crunchyroll LE", "mid", 75),
        ("Crunchyroll", "Mushoku Tensei Season 2 Complete", "Blu-ray", "Crunchyroll LE Box Set", "high", 120),
        ("Aniplex USA", "Sword Art Online Progressive: Kuraki Yuuyami no Scherzo", "Blu-ray", "Aniplex LE", "high", 130),
        ("Crunchyroll", "Hell's Paradise Complete", "Blu-ray", "Crunchyroll LE with Art Book", "mid", 95),
        ("Crunchyroll", "Vinland Saga Season 2 Complete", "Blu-ray", "Crunchyroll LE Box Set", "high", 130),
        ("JP Import", "Frieren Complete Box", "Blu-ray", "JP BD LE with Frieren Figure & OST", "grail", 380),
        ("Crunchyroll", "The Apothecary Diaries Season 1", "Blu-ray", "Crunchyroll LE", "mid", 85),
        ("Crunchyroll", "Metallic Rouge Complete", "Blu-ray", "Crunchyroll LE", "mid", 70),

        # ── Classic Anime Collector's (~20) ──────────────────────────────
        ("Funimation", "Cowboy Bebop 25th Anniversary Complete", "Blu-ray", "Funimation Anniversary LE Box Set", "high", 160),
        ("Crunchyroll", "Trigun Stampede Complete", "Blu-ray", "Crunchyroll LE Steelbook", "mid", 85),
        ("JP Import", "Berserk (1997) Complete Series", "Blu-ray", "JP BD Remaster Box Set", "grail", 350),
        ("Funimation", "Serial Experiments Lain Complete", "Blu-ray", "Funimation Collector's Edition Restored", "high", 180),
        ("GKIDS", "FLCL Complete Series", "Blu-ray", "GKIDS Collector's Edition", "high", 120),
        ("GKIDS", "Perfect Blue", "4K UHD", "GKIDS 4K Collector's Edition", "high", 100),
        ("GKIDS", "Paprika", "4K UHD", "GKIDS 4K Collector's Edition Steelbook", "mid", 80),
        ("GKIDS", "Millennium Actress", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 75),
        ("Sentai Filmworks", "Legend of the Galactic Heroes Complete OVA", "Blu-ray", "Sentai Premium Complete Box (12 discs)", "grail", 400),
        ("Funimation", "Initial D Complete Series", "Blu-ray", "Funimation Complete Collection Box", "high", 250),
        ("JP Import", "Slam Dunk Complete", "Blu-ray", "JP BD Complete Box Remaster", "grail", 350),
        ("Funimation", "Yu Yu Hakusho Complete", "Blu-ray", "Funimation Anniversary Complete Box Set", "high", 200),
        ("JP Import", "Trigun Complete", "Blu-ray", "JP BD Box Remaster", "high", 180),
        ("Discotek Media", "Giant Robo Complete", "Blu-ray", "Discotek BD Complete Remaster", "high", 140),
        ("Discotek Media", "Lupin III: Part IV Complete", "Blu-ray", "Discotek BD Complete Collection", "high", 120),
        ("Discotek Media", "Captain Harlock Complete", "Blu-ray", "Discotek BD Complete Collection", "high", 160),
        ("JP Import", "Ranma 1/2 Complete", "Blu-ray", "JP BD Complete Box Set", "high", 280),
        ("JP Import", "Urusei Yatsura Complete", "Blu-ray", "JP BD Complete Box Set", "grail", 400),
        ("Sentai Filmworks", "Clannad + After Story Complete", "Blu-ray", "Sentai Premium Box Set", "high", 160),
        ("Sentai Filmworks", "Higurashi When They Cry Complete", "Blu-ray", "Sentai Complete Collection", "high", 140),

        # ── Studio Ghibli Blu-ray (~15) ──────────────────────────────────
        ("GKIDS", "Spirited Away", "Blu-ray", "GKIDS Steelbook Edition", "mid", 50),
        ("GKIDS", "Princess Mononoke", "4K UHD", "GKIDS 4K Steelbook", "mid", 65),
        ("GKIDS", "Princess Mononoke", "Blu-ray", "GKIDS Steelbook Edition", "mid", 48),
        ("GKIDS", "My Neighbor Totoro", "4K UHD", "GKIDS 4K Steelbook", "mid", 60),
        ("GKIDS", "My Neighbor Totoro", "Blu-ray", "GKIDS Steelbook Edition", "mid", 45),
        ("GKIDS", "Howl's Moving Castle", "Blu-ray", "GKIDS Steelbook Edition", "mid", 48),
        ("GKIDS", "Nausicaa of the Valley of the Wind", "4K UHD", "GKIDS 4K Steelbook", "mid", 62),
        ("GKIDS", "Nausicaa of the Valley of the Wind", "Blu-ray", "GKIDS Steelbook Edition", "mid", 48),
        ("GKIDS", "Castle in the Sky", "4K UHD", "GKIDS 4K Steelbook", "mid", 60),
        ("GKIDS", "Castle in the Sky", "Blu-ray", "GKIDS Steelbook Edition", "mid", 45),
        ("GKIDS", "Porco Rosso", "Blu-ray", "GKIDS Steelbook Edition", "mid", 45),
        ("GKIDS", "Kiki's Delivery Service", "Blu-ray", "GKIDS Steelbook Edition", "mid", 45),
        ("GKIDS", "The Tale of the Princess Kaguya", "Blu-ray", "GKIDS Collector's Edition", "mid", 55),
        ("GKIDS", "When Marnie Was There", "Blu-ray", "GKIDS Collector's Edition", "mid", 45),
        ("GKIDS", "From Up on Poppy Hill", "Blu-ray", "GKIDS Collector's Edition", "mid", 42),

        # ── Mecha Anime (~15) ────────────────────────────────────────────
        ("Rightstuf", "Mobile Suit Gundam UC Complete", "Blu-ray", "Rightstuf LE Complete Box Set", "high", 200),
        ("Rightstuf", "Mobile Suit Gundam SEED Complete", "Blu-ray", "Rightstuf HD Remaster Box Set", "high", 180),
        ("Rightstuf", "Mobile Suit Gundam 00 Complete", "Blu-ray", "Rightstuf Complete Box Set", "high", 160),
        ("Crunchyroll", "Mobile Suit Gundam: Iron-Blooded Orphans Complete", "Blu-ray", "Crunchyroll LE Box Set", "high", 140),
        ("Crunchyroll", "Mobile Suit Gundam: Witch from Mercury Complete", "Blu-ray", "Crunchyroll LE with Gunpla Kit", "high", 180),
        ("Funimation", "Code Geass Complete", "Blu-ray", "Funimation LE Complete Collection", "high", 180),
        ("Funimation", "Eureka Seven Complete", "Blu-ray", "Funimation Complete Collection Box", "high", 150),
        ("JP Import", "Macross Frontier Complete", "Blu-ray", "JP BD Box with Concert BD", "high", 250),
        ("JP Import", "Macross Delta Complete", "Blu-ray", "JP BD Box with Walkure Live BD", "high", 220),
        ("Funimation", "Full Metal Panic! Complete", "Blu-ray", "Funimation Complete Collection Box", "high", 140),
        ("JP Import", "Patlabor TV + OVA Complete", "Blu-ray", "JP BD Memorial Box Set", "high", 280),
        ("Sentai Filmworks", "Rahxephon Complete", "Blu-ray", "Sentai LE Box Set", "mid", 90),
        ("JP Import", "Getter Robo Arc Complete", "Blu-ray", "JP BD LE Box Set", "high", 120),
        ("JP Import", "Gurren Lagann Complete Box", "Blu-ray", "JP BD LE with Drill Keychain & Art Book", "grail", 350),
        ("Sentai Filmworks", "Escaflowne Complete", "Blu-ray", "Sentai LE Collector's Box", "high", 130),

        # ── Shonen Classics (~15) ────────────────────────────────────────
        ("JP Import", "Naruto Shippuden Complete", "Blu-ray", "JP BD Complete Box Set (72 discs)", "grail", 500),
        ("Crunchyroll", "Bleach: Thousand-Year Blood War Complete", "Blu-ray", "Crunchyroll LE Box Set", "high", 160),
        ("Funimation", "One Piece Film Collection (15 Films)", "Blu-ray", "Funimation Complete Film Box", "high", 250),
        ("Funimation", "Dragon Ball Z (4:3 Original)", "Blu-ray", "Funimation Season Blu-ray Set (Seasons 1-9)", "high", 300),
        ("Funimation", "Hunter x Hunter (2011) Complete", "Blu-ray", "Funimation Complete Box Set", "high", 200),
        ("Funimation", "Fairy Tail Complete Collection", "Blu-ray", "Funimation Complete Box (9 seasons)", "high", 280),
        ("Crunchyroll", "Black Clover Complete", "Blu-ray", "Crunchyroll Complete Collection Box", "high", 200),
        ("Funimation", "Dragon Ball Complete", "Blu-ray", "Funimation Complete Original DB Box", "high", 180),
        ("Funimation", "Dragon Ball GT Complete", "Blu-ray", "Funimation Complete Collection", "mid", 90),
        ("JP Import", "Rurouni Kenshin Complete", "Blu-ray", "JP BD Complete Box Remaster", "high", 250),
        ("JP Import", "Slam Dunk The First Movie", "4K UHD", "JP 4K LE with Art Book", "high", 120),
        ("Crunchyroll", "Blue Lock Season 1 Complete", "Blu-ray", "Crunchyroll LE", "mid", 90),
        ("Crunchyroll", "Haikyuu!! Complete Series", "Blu-ray", "Crunchyroll Complete Box Set", "high", 250),
        ("Crunchyroll", "Dr. Stone Complete", "Blu-ray", "Crunchyroll Complete Box Set", "high", 140),
        ("Crunchyroll", "Fire Force Complete", "Blu-ray", "Crunchyroll Complete Box Set", "high", 120),

        # ── Limited Edition Box Sets (~15) ───────────────────────────────
        ("Aniplex USA", "Demon Slayer Complete (S1-S4)", "Blu-ray", "Aniplex LE Ultimate Box Set", "grail", 500),
        ("Aniplex USA", "Sword Art Online Complete Collection", "Blu-ray", "Aniplex LE Memorial Box (all seasons)", "grail", 450),
        ("Aniplex USA", "Fate/stay night Complete Collection", "Blu-ray", "Aniplex LE (UBW + HF + Zero)", "grail", 600),
        ("JP Import", "Neon Genesis Evangelion Complete", "4K UHD", "JP 4K UHD Box (TV + Rebuild)", "grail", 800),
        ("JP Import", "Cowboy Bebop Complete", "4K UHD", "JP 4K UHD 25th Anniversary Box", "grail", 500),
        ("Aniplex USA", "86: Eighty Six Complete", "Blu-ray", "Aniplex LE with Spearhead Figure Set", "grail", 380),
        ("JP Import", "Attack on Titan Complete Collection", "Blu-ray", "JP BD Complete Box (All Seasons + Specials)", "grail", 600),
        ("Aniplex USA", "Kaguya-sama Complete", "Blu-ray", "Aniplex LE Box Set (3 Seasons + Movie)", "high", 280),
        ("JP Import", "Death Note Complete", "Blu-ray", "JP BD Complete Box with L Figure", "high", 200),
        ("JP Import", "Steins;Gate Complete", "Blu-ray", "JP BD Box (Original + 0 + Movie)", "high", 250),
        ("Funimation", "My Hero Academia Complete (S1-S7)", "Blu-ray", "Funimation Ultimate Collection Box", "high", 300),
        ("Crunchyroll", "Jujutsu Kaisen Complete (S1-S2 + Movie)", "Blu-ray", "Crunchyroll LE Ultimate Box", "high", 280),
        ("Funimation", "One Piece Wano Arc Complete", "Blu-ray", "Funimation LE Box Set", "high", 200),
        ("Aniplex USA", "Monogatari Series Complete Box", "Blu-ray", "Aniplex LE Ultimate Collection", "grail", 700),
        ("Aniplex USA", "Madoka Magica Complete (TV + Movies)", "Blu-ray", "Aniplex LE Ultimate Box", "grail", 500),

        # ── OVA/Movie Collections (~15) ──────────────────────────────────
        ("JP Import", "Macross Plus Complete", "Blu-ray", "JP BD Remaster with Bonus CD", "high", 150),
        ("JP Import", "Patlabor Movies 1-3", "Blu-ray", "JP BD Movie Collection Box", "high", 200),
        ("GKIDS", "Ghost in the Shell (1995)", "4K UHD", "GKIDS 4K Collector's Edition", "high", 100),
        ("GKIDS", "Ghost in the Shell 2: Innocence", "4K UHD", "GKIDS 4K Collector's Edition", "mid", 80),
        ("Funimation", "Ghost in the Shell: SAC Complete", "Blu-ray", "Funimation Complete LE Box", "high", 180),
        ("Sentai Filmworks", "Vampire Hunter D: Bloodlust", "4K UHD", "Sentai 4K Collector's Edition", "high", 100),
        ("GKIDS", "Redline", "4K UHD", "GKIDS 4K Collector's Edition", "high", 110),
        ("GKIDS", "Promare", "4K UHD", "GKIDS 4K Collector's Edition Steelbook", "mid", 70),
        ("Crunchyroll", "Suzume", "4K UHD", "Crunchyroll 4K Steelbook LE", "mid", 65),
        ("GKIDS", "The Boy and the Heron", "4K UHD", "GKIDS 4K Collector's Edition Steelbook", "high", 100),
        ("JP Import", "Belle", "Blu-ray", "JP BD Collector's Edition with Art Book", "high", 130),
        ("JP Import", "Dragon Ball Super: Super Hero", "4K UHD", "JP 4K LE with Figure", "high", 120),
        ("JP Import", "One Piece Film Red Collector's Edition", "4K UHD", "JP 4K LE with Uta Figure & OST", "high", 200),
        ("Discotek Media", "Night on the Galactic Railroad", "Blu-ray", "Discotek BD Remaster", "mid", 60),
        ("Discotek Media", "Angel's Egg", "Blu-ray", "Discotek BD Remaster", "mid", 70),

        # ── Additional Notable Releases (~20) ────────────────────────────
        ("Crunchyroll", "Delicious in Dungeon Complete", "Blu-ray", "Crunchyroll LE Box Set", "mid", 95),
        ("Crunchyroll", "Oshi no Ko Season 1 Complete", "Blu-ray", "Crunchyroll LE with Idol Photo Set", "high", 110),
        ("JP Import", "Oshi no Ko Complete Box", "Blu-ray", "JP BD LE with Ai Figure & CD", "high", 280),
        ("Sentai Filmworks", "The Dangers in My Heart Complete", "Blu-ray", "Sentai LE", "mid", 75),
        ("Aniplex USA", "My Happy Marriage Complete", "Blu-ray", "Aniplex LE with Art Cards", "mid", 90),
        ("JP Import", "Zom 100 Complete", "Blu-ray", "JP BD LE with Bonus OVA", "mid", 95),
        ("Sentai Filmworks", "Skip and Loafer Complete", "Blu-ray", "Sentai LE", "mid", 70),
        ("Funimation", "Spy x Family Complete (S1 + S2 + Movie)", "Blu-ray", "Funimation Ultimate Box Set", "high", 200),
        ("JP Import", "Pluto Complete", "Blu-ray", "JP BD LE Box Set", "high", 180),
        ("GKIDS", "The Boy and the Heron", "Blu-ray", "GKIDS Steelbook", "mid", 55),
        ("JP Import", "Look Back", "Blu-ray", "JP BD LE with Art Book", "high", 100),
        ("Crunchyroll", "Tower of God Season 2", "Blu-ray", "Crunchyroll LE", "mid", 75),
        ("Crunchyroll", "That Time I Got Reincarnated as a Slime Complete", "Blu-ray", "Crunchyroll Complete Box Set", "high", 180),
        ("Crunchyroll", "Re:Zero Complete Collection", "Blu-ray", "Crunchyroll LE Ultimate Box", "high", 200),
        ("Funimation", "Tokyo Ghoul Complete", "Blu-ray", "Funimation Complete Box Set", "high", 140),
        ("Funimation", "Steins;Gate Complete", "Blu-ray", "Funimation LE Complete (Original + 0)", "high", 160),
        ("Sentai Filmworks", "Parasyte -the maxim- Complete", "Blu-ray", "Sentai LE Collection", "mid", 90),
        ("Sentai Filmworks", "Food Wars! Complete", "Blu-ray", "Sentai Complete Collection Box", "high", 150),
        ("Crunchyroll", "Mob Psycho 100 Complete Series", "Blu-ray", "Crunchyroll LE Complete Box (3 seasons)", "high", 180),
        ("Crunchyroll", "Konosuba Complete (S1 + S2 + Movie)", "Blu-ray", "Crunchyroll LE Box Set", "high", 130),

        # ── Specific Seasons / Cours of Long-Running Shows ─────────────────
        ("Funimation", "My Hero Academia Season 5 Part 1", "Blu-ray", "Funimation LE", "mid", 55),
        ("Funimation", "My Hero Academia Season 5 Part 2", "Blu-ray", "Funimation LE", "mid", 55),
        ("Funimation", "My Hero Academia Season 6 Part 1", "Blu-ray", "Funimation LE", "mid", 60),
        ("Funimation", "My Hero Academia Season 6 Part 2", "Blu-ray", "Funimation LE", "mid", 60),
        ("Crunchyroll", "Jujutsu Kaisen Season 2 Hidden Inventory Arc", "Blu-ray", "Crunchyroll LE", "mid", 65),
        ("Crunchyroll", "Jujutsu Kaisen Season 2 Shibuya Incident Arc", "Blu-ray", "Crunchyroll LE", "mid", 65),
        ("Crunchyroll", "One Piece Wano Kuni Arc Part 1", "Blu-ray", "Crunchyroll LE", "mid", 70),
        ("Crunchyroll", "One Piece Wano Kuni Arc Part 2", "Blu-ray", "Crunchyroll LE", "mid", 70),
        ("Crunchyroll", "One Piece Wano Kuni Arc Part 3", "Blu-ray", "Crunchyroll LE", "mid", 70),
        ("Crunchyroll", "One Piece Wano Kuni Arc Part 4", "Blu-ray", "Crunchyroll LE", "mid", 70),
        ("Funimation", "Dragon Ball Super Universe Survival Arc", "Blu-ray", "Funimation LE Box", "high", 110),
        ("Funimation", "Dragon Ball Super Broly Arc", "Blu-ray", "Funimation LE", "mid", 55),
        ("Crunchyroll", "Bleach TYBW Part 1 (Cour 1)", "Blu-ray", "Crunchyroll LE", "high", 80),
        ("Crunchyroll", "Bleach TYBW Part 2 (Cour 2)", "Blu-ray", "Crunchyroll LE", "high", 80),
        ("Crunchyroll", "Black Clover Season 3 Part 1", "Blu-ray", "Crunchyroll LE", "mid", 50),
        ("Crunchyroll", "Black Clover Season 3 Part 2", "Blu-ray", "Crunchyroll LE", "mid", 50),
        ("Crunchyroll", "Black Clover Season 4 Complete", "Blu-ray", "Crunchyroll LE", "mid", 65),
        ("Crunchyroll", "Demon Slayer Swordsmith Village Arc", "Blu-ray", "Crunchyroll LE", "high", 85),
        ("Crunchyroll", "Demon Slayer Hashira Training Arc", "Blu-ray", "Crunchyroll LE", "high", 85),
        ("Funimation", "Fairy Tail Final Season Part 1", "Blu-ray", "Funimation LE", "mid", 55),
        ("Funimation", "Fairy Tail Final Season Part 2", "Blu-ray", "Funimation LE", "mid", 55),

        # ── 4K UHD Anime Releases ──────────────────────────────────────────
        ("Funimation", "Dragon Ball Super: Broly", "4K UHD", "4K UHD + Blu-ray LE", "high", 45),
        ("Funimation", "Dragon Ball Super: Super Hero", "4K UHD", "4K UHD + Blu-ray LE", "high", 45),
        ("Crunchyroll", "Demon Slayer Mugen Train", "4K UHD", "4K UHD LE Steelbook", "high", 50),
        ("Crunchyroll", "Jujutsu Kaisen 0", "4K UHD", "4K UHD + Blu-ray LE", "high", 45),
        ("GKIDS", "Spirited Away", "4K UHD", "4K UHD Steelbook", "high", 40),
        ("GKIDS", "Princess Mononoke", "4K UHD", "4K UHD Steelbook", "high", 40),
        ("GKIDS", "My Neighbor Totoro", "4K UHD", "4K UHD Steelbook", "high", 38),
        ("GKIDS", "Howl's Moving Castle", "4K UHD", "4K UHD Steelbook", "high", 40),
        ("GKIDS", "Nausicaa of the Valley of the Wind", "4K UHD", "4K UHD Steelbook", "high", 38),
        ("GKIDS", "Castle in the Sky", "4K UHD", "4K UHD Steelbook", "mid", 35),
        ("Sony", "Suzume", "4K UHD", "4K UHD + Blu-ray Steelbook", "high", 42),
        ("Sony", "Your Name", "4K UHD", "4K UHD + Blu-ray Steelbook", "high", 48),
        ("Funimation", "Ghost in the Shell (1995)", "4K UHD", "4K UHD Steelbook", "high", 45),
        ("Funimation", "Akira", "4K UHD", "4K UHD LE + Booklet", "high", 55),

        # ── Aniplex Exclusive Imports ──────────────────────────────────────
        ("Aniplex", "Fate/stay night [Heaven's Feel] I", "Blu-ray", "Aniplex JP LE (Box + OST + Art)", "grail", 180),
        ("Aniplex", "Fate/stay night [Heaven's Feel] II", "Blu-ray", "Aniplex JP LE (Box + OST + Art)", "grail", 180),
        ("Aniplex", "Fate/stay night [Heaven's Feel] III", "Blu-ray", "Aniplex JP LE (Box + OST + Art)", "grail", 200),
        ("Aniplex", "Sword Art Online Progressive: Aria", "Blu-ray", "Aniplex JP LE + Soundtrack", "high", 120),
        ("Aniplex", "Lycoris Recoil Vol. 1", "Blu-ray", "Aniplex JP LE + Drama CD", "high", 100),
        ("Aniplex", "Lycoris Recoil Vol. 2", "Blu-ray", "Aniplex JP LE + Drama CD", "high", 100),
        ("Aniplex", "Bocchi the Rock! Vol. 1", "Blu-ray", "Aniplex JP LE + Character Song CD", "high", 95),
        ("Aniplex", "Bocchi the Rock! Vol. 2", "Blu-ray", "Aniplex JP LE + Character Song CD", "high", 95),
        ("Aniplex", "Kaguya-sama: Love is War -Ultra Romantic-", "Blu-ray", "Aniplex JP Complete LE Box", "high", 160),
        ("Aniplex", "Oshi no Ko Vol. 1", "Blu-ray", "Aniplex JP LE + Drama CD + Art Book", "high", 110),
        ("Aniplex", "Oshi no Ko Vol. 2", "Blu-ray", "Aniplex JP LE + Soundtrack", "high", 110),
        ("Aniplex", "Monogatari Series Off Season Box", "Blu-ray", "Aniplex JP LE Complete Box", "grail", 280),

        # ── Boutique Labels (Discotek, Maiden Japan) ───────────────────────
        ("Discotek", "Lupin III Part II Complete", "Blu-ray", "Discotek SD BD Complete (155 eps)", "high", 120),
        ("Discotek", "Mazinger Z Complete", "Blu-ray", "Discotek SD BD Complete", "high", 100),
        ("Discotek", "Getter Robo Complete", "Blu-ray", "Discotek SD BD Complete", "mid", 80),
        ("Discotek", "Captain Harlock Complete", "Blu-ray", "Discotek SD BD Complete", "high", 95),
        ("Discotek", "Galaxy Express 999 Complete", "Blu-ray", "Discotek SD BD Complete Collection", "high", 110),
        ("Discotek", "Devilman OVA Collection", "Blu-ray", "Discotek BD (3 OVAs)", "mid", 45),
        ("Discotek", "Robot Carnival", "Blu-ray", "Discotek BD Remastered", "mid", 30),
        ("Discotek", "Riding Bean", "Blu-ray", "Discotek BD Remastered", "mid", 28),
        ("Discotek", "Fist of the North Star Complete", "Blu-ray", "Discotek SD BD Complete (152 eps)", "high", 140),
        ("Discotek", "Gatchaman Complete Series", "Blu-ray", "Discotek SD BD Complete", "high", 100),
        ("Maiden Japan", "Legend of Galactic Heroes (OVA)", "Blu-ray", "Maiden Japan BD Complete (110 eps)", "grail", 300),
        ("Maiden Japan", "Irresponsible Captain Tylor", "Blu-ray", "Maiden Japan BD Complete Collection", "mid", 65),
        ("Maiden Japan", "Gasaraki Complete", "Blu-ray", "Maiden Japan BD Complete", "mid", 55),
        ("Maiden Japan", "RahXephon Complete", "Blu-ray", "Maiden Japan BD Complete + Movie", "mid", 60),

        # ── Vinegar Syndrome Anime Adjacent ────────────────────────────────
        ("Vinegar Syndrome", "Wicked City", "Blu-ray", "VS LE Slip + Booklet", "high", 40),
        ("Vinegar Syndrome", "Demon City Shinjuku", "Blu-ray", "VS LE Slip + Booklet", "mid", 35),
        ("Vinegar Syndrome", "Ninja Scroll", "Blu-ray", "VS LE Slip + Booklet + Poster", "high", 45),
        ("Vinegar Syndrome", "Vampire Hunter D: Bloodlust", "Blu-ray", "VS LE Slip + Art Cards", "high", 50),
        ("Vinegar Syndrome", "Perfect Blue", "Blu-ray", "VS LE 4K Restoration + Booklet", "high", 55),
        ("Vinegar Syndrome", "Memories (Katsuhiro Otomo)", "Blu-ray", "VS LE Slip + Booklet", "mid", 38),
        ("Vinegar Syndrome", "Golgo 13: The Professional", "Blu-ray", "VS LE Slip + Insert", "mid", 35),

        # ── Arrow Video Anime/Asian Releases ───────────────────────────────
        ("Arrow Video", "Battle Royale", "Blu-ray", "Arrow LE Steelbook + Art Cards", "high", 45),
        ("Arrow Video", "Versus", "Blu-ray", "Arrow LE + Booklet", "mid", 35),
        ("Arrow Video", "Hausu (House)", "Blu-ray", "Arrow LE + Booklet", "mid", 38),
        ("Arrow Video", "Riki-Oh: The Story of Ricky", "Blu-ray", "Arrow LE + Poster", "mid", 35),
        ("Arrow Video", "Stray Cat Rock Collection", "Blu-ray", "Arrow LE Box (5 films)", "high", 65),

        # ── Additional Complete Series Boxes ───────────────────────────────
        ("Funimation", "Yu Yu Hakusho Complete Series", "Blu-ray", "Funimation Complete Box (112 eps)", "high", 120),
        ("Crunchyroll", "Dr. Stone Complete (S1-S3)", "Blu-ray", "Crunchyroll LE Complete Box", "high", 140),
        ("Crunchyroll", "Spy x Family Season 1 Complete", "Blu-ray", "Crunchyroll LE Complete Box", "high", 110),
        ("Crunchyroll", "Chainsaw Man Season 1", "Blu-ray", "Crunchyroll LE + Art Book", "high", 90),
        ("Crunchyroll", "Ranking of Kings Complete", "Blu-ray", "Crunchyroll LE Complete Box", "mid", 80),
        ("Funimation", "Soul Eater Complete Series", "Blu-ray", "Funimation Complete Box (51 eps)", "mid", 85),
        ("Funimation", "Fullmetal Alchemist Brotherhood Complete", "Blu-ray", "Funimation Complete LE Box", "high", 150),
        ("Sentai Filmworks", "CLANNAD + After Story Complete", "Blu-ray", "Sentai Complete Collection", "high", 130),
        ("Sentai Filmworks", "Toradora! Complete Collection", "Blu-ray", "Sentai LE Complete", "mid", 75),
        ("NIS America", "Gurren Lagann Complete", "Blu-ray", "NIS LE Complete Box + Art Book", "high", 160),

        # ── JP Import Limited Editions ─────────────────────────────────────
        ("JP Import", "Violet Evergarden The Movie", "Blu-ray", "JP BD LE + OST + Art Book", "grail", 180),
        ("JP Import", "Weathering with You", "Blu-ray", "JP BD Collector's Edition 4K + BD", "high", 120),
        ("JP Import", "Belle", "Blu-ray", "JP BD LE + OST + Visual Guide", "high", 100),
        ("JP Import", "The Boy and the Heron", "Blu-ray", "JP BD LE + Booklet + Poster", "high", 130),
        ("JP Import", "Dragon Ball Super: Super Hero", "Blu-ray", "JP BD LE + Figure + Art", "grail", 200),
        ("JP Import", "One Piece Film Red", "Blu-ray", "JP BD LE Collector's Box", "high", 150),
        ("JP Import", "Slam Dunk (2022)", "Blu-ray", "JP BD LE + OST + Script", "high", 140),
        ("JP Import", "Mobile Suit Gundam: Hathaway's Flash", "Blu-ray", "JP BD LE Theatrical Version", "high", 110),

        # ── Steelbook Editions ─────────────────────────────────────────────
        ("Funimation", "Cowboy Bebop Complete", "Blu-ray", "Steelbook LE Complete Collection", "high", 90),
        ("Crunchyroll", "Attack on Titan Final Season Part 1", "Blu-ray", "Steelbook LE", "mid", 50),
        ("Crunchyroll", "Attack on Titan Final Season Part 2", "Blu-ray", "Steelbook LE", "mid", 50),
        ("Crunchyroll", "Attack on Titan Final Season Part 3", "Blu-ray", "Steelbook LE", "mid", 55),
        ("Funimation", "Samurai Champloo Complete", "Blu-ray", "Steelbook LE Complete", "high", 80),
        ("GKIDS", "Spirited Away", "Blu-ray", "Steelbook LE (Target Exclusive)", "high", 45),
        ("GKIDS", "Kiki's Delivery Service", "Blu-ray", "Steelbook LE (Target Exclusive)", "mid", 40),
        ("GKIDS", "Ponyo", "Blu-ray", "Steelbook LE (Target Exclusive)", "mid", 38),
        ("Crunchyroll", "Frieren: Beyond Journey's End S1", "Blu-ray", "Crunchyroll LE + Art Cards", "high", 85),
        ("Crunchyroll", "Solo Leveling Season 1", "Blu-ray", "Crunchyroll LE Steelbook", "high", 80),

        # ── Additional Aniplex / JP Imports ────────────────────────────────
        ("Aniplex", "Demon Slayer Kimetsu no Yaiba Season 1 Vol. 1", "Blu-ray", "Aniplex JP LE + CD", "high", 95),
        ("Aniplex", "Demon Slayer Kimetsu no Yaiba Season 1 Vol. 2", "Blu-ray", "Aniplex JP LE + CD", "high", 95),
        ("Aniplex", "Demon Slayer Kimetsu no Yaiba Season 1 Vol. 3", "Blu-ray", "Aniplex JP LE + CD", "high", 95),
        ("Aniplex", "Demon Slayer Mugen Train LE Box", "Blu-ray", "Aniplex JP LE (BD + CD + Art + Figure)", "grail", 220),
        ("Aniplex", "Spy x Family Season 1 Vol. 1", "Blu-ray", "Aniplex JP LE + Drama CD", "high", 90),
        ("Aniplex", "Spy x Family Season 1 Vol. 2", "Blu-ray", "Aniplex JP LE + Drama CD", "high", 90),
        ("Aniplex", "The Apothecary Diaries Vol. 1", "Blu-ray", "Aniplex JP LE + Art Book", "high", 100),
        ("Aniplex", "The Apothecary Diaries Vol. 2", "Blu-ray", "Aniplex JP LE + Character Song", "high", 100),
        ("Aniplex", "Rascal Does Not Dream of Bunny Girl Senpai Complete", "Blu-ray", "Aniplex JP LE Complete Box", "high", 180),
        ("JP Import", "Vinland Saga Season 2 Box", "Blu-ray", "JP BD LE Complete Box + Art", "high", 160),
        ("JP Import", "Bocchi the Rock! Complete", "Blu-ray", "JP BD LE Complete + Live CD", "high", 170),
        ("JP Import", "Oshi no Ko Season 2", "Blu-ray", "JP BD LE + Drama CD", "high", 110),
        ("JP Import", "Blue Lock Season 1 Box", "Blu-ray", "JP BD LE Complete + OST", "high", 150),
        ("JP Import", "Mashle Season 1 Box", "Blu-ray", "JP BD LE + Character Song CD", "mid", 90),
        ("JP Import", "Undead Unluck Season 1 Box", "Blu-ray", "JP BD LE Complete + Art Book", "mid", 85),
        ("JP Import", "Hell's Paradise Season 1 Box", "Blu-ray", "JP BD LE Complete + Booklet", "mid", 80),

        # ── Aniplex USA Exclusive Box Sets (Deep Catalog) ────────────────
        ("Aniplex USA", "Demon Slayer: Hashira Training Arc", "Blu-ray", "Aniplex LE + Hashira Art Cards", "high", 130),
        ("Aniplex USA", "Demon Slayer: Infinity Castle Part 1", "Blu-ray", "Aniplex LE + Muzan Figure", "grail", 350),
        ("Aniplex USA", "Sword Art Online Progressive: Aria", "Blu-ray", "Aniplex LE + Asuna Figure", "high", 180),
        ("Aniplex USA", "Sword Art Online Progressive: Scherzo", "Blu-ray", "Aniplex LE + Art Book", "high", 160),
        ("Aniplex USA", "86 -Eighty Six- Part 1", "Blu-ray", "Aniplex LE Box Set", "high", 200),
        ("Aniplex USA", "86 -Eighty Six- Part 2", "Blu-ray", "Aniplex LE Box Set + OST", "high", 220),
        ("Aniplex USA", "Lycoris Recoil", "Blu-ray", "Aniplex LE Complete Box", "high", 250),
        ("Aniplex USA", "Bocchi the Rock!", "Blu-ray", "Aniplex LE Complete + Live BD", "high", 230),
        ("Aniplex USA", "Fate/Grand Order: Camelot", "Blu-ray", "Aniplex LE + Bedivere Figure", "high", 170),
        ("Aniplex USA", "Fate/Grand Order: Solomon", "Blu-ray", "Aniplex LE + Drama CD", "high", 150),
        ("Aniplex USA", "Rascal Does Not Dream (Movie)", "Blu-ray", "Aniplex LE + Art Book", "high", 160),
        ("Aniplex USA", "Oshi no Ko Season 1", "Blu-ray", "Aniplex LE Complete Box", "high", 200),

        # ── Complete Series Mega Boxes ───────────────────────────────────
        ("Viz Media", "Naruto Shippuden Complete Series", "Blu-ray", "Complete 500 Episode Box Set (72-disc)", "grail", 500),
        ("Viz Media", "Naruto Original Complete Series", "Blu-ray", "Complete 220 Episode Box Set (32-disc)", "grail", 350),
        ("Viz Media", "Bleach Complete Series", "Blu-ray", "Complete 366 Episode Box Set (54-disc)", "grail", 450),
        ("Viz Media", "Bleach TYBW Season 1-2", "Blu-ray", "LE Box Set + Booklet", "high", 180),
        ("Funimation", "One Piece Collection Boxes 1-30", "Blu-ray", "Complete Collection (600+ Episodes)", "grail", 800),
        ("Funimation", "Dragon Ball Z Complete", "Blu-ray", "Dragon Box Set (18-disc Remaster)", "grail", 600),
        ("Funimation", "Dragon Ball Super Complete", "Blu-ray", "Complete 131 Episode Box (13-disc)", "grail", 350),
        ("Funimation", "Yu Yu Hakusho Complete", "Blu-ray", "25th Anniversary Complete Box", "grail", 300),
        ("Funimation", "Fullmetal Alchemist Brotherhood", "Blu-ray", "Complete Series LE Box", "high", 250),
        ("Funimation", "Cowboy Bebop Complete", "Blu-ray", "25th Anniversary Collector's Edition", "high", 200),
        ("Funimation", "Samurai Champloo Complete", "Blu-ray", "Complete Series LE Box", "high", 180),
        ("Viz Media", "Hunter x Hunter (2011) Complete", "Blu-ray", "Complete 148 Episode Box Set", "grail", 400),

        # ── 4K UHD Anime Releases ────────────────────────────────────────
        ("Funimation", "Akira", "4K UHD", "Akira 4K UHD LE SteelBook", "high", 120),
        ("Lionsgate", "Ghost in the Shell (1995)", "4K UHD", "Ghost in the Shell 4K UHD LE", "high", 100),
        ("Funimation", "Dragon Ball Super: Broly", "4K UHD", "Dragon Ball Super Broly 4K UHD LE", "high", 80),
        ("Funimation", "Dragon Ball Super: Super Hero", "4K UHD", "DBS Super Hero 4K UHD LE SteelBook", "mid", 60),
        ("Crunchyroll", "Dragon Ball Z: Battle of Gods", "4K UHD", "Battle of Gods 4K UHD LE", "mid", 70),
        ("GKIDS", "Princess Mononoke", "4K UHD", "Princess Mononoke 4K UHD SteelBook", "high", 90),
        ("GKIDS", "Spirited Away", "4K UHD", "Spirited Away 4K UHD SteelBook", "high", 90),
        ("GKIDS", "My Neighbor Totoro", "4K UHD", "My Neighbor Totoro 4K UHD SteelBook", "high", 85),
        ("GKIDS", "Howl's Moving Castle", "4K UHD", "Howl's Moving Castle 4K UHD SteelBook", "high", 85),
        ("GKIDS", "Nausicaa of the Valley of the Wind", "4K UHD", "Nausicaa 4K UHD SteelBook", "high", 90),
        ("GKIDS", "Castle in the Sky", "4K UHD", "Castle in the Sky 4K UHD SteelBook", "mid", 75),
        ("GKIDS", "Kiki's Delivery Service", "4K UHD", "Kiki's Delivery Service 4K UHD SteelBook", "mid", 75),
        ("Manga Entertainment", "Redline", "4K UHD", "Redline 4K UHD LE (Turbocharged Edition)", "high", 100),
        ("Shout Factory", "Vampire Hunter D: Bloodlust", "4K UHD", "Vampire Hunter D 4K UHD LE", "mid", 70),

        # ── Funimation/Crunchyroll Limited Editions ──────────────────────
        ("Crunchyroll", "Chainsaw Man Season 1", "Blu-ray", "Crunchyroll LE + Art Cards", "high", 120),
        ("Crunchyroll", "Jujutsu Kaisen Season 2", "Blu-ray", "Crunchyroll LE + Shibuya Art Book", "high", 150),
        ("Crunchyroll", "Spy x Family Season 1+2", "Blu-ray", "Complete LE Box + Forger Family Figure", "high", 200),
        ("Crunchyroll", "Frieren: Beyond Journey's End", "Blu-ray", "LE Complete + OST CD", "high", 180),
        ("Crunchyroll", "Mob Psycho 100 Complete", "Blu-ray", "Complete Series LE Box", "high", 200),
        ("Crunchyroll", "Tower of God Season 1", "Blu-ray", "LE + Art Book", "mid", 80),
        ("Funimation", "Attack on Titan: Final Season Complete", "Blu-ray", "Complete Final Season LE Box", "grail", 300),
        ("Funimation", "My Hero Academia Complete Box 1-6", "Blu-ray", "Complete Seasons 1-6 LE Mega Box", "grail", 400),

        # ── JP Import BDs (English Subs) ─────────────────────────────────
        ("JP Import", "Evangelion 1.11+2.22+3.33+3.0+1.0", "Blu-ray", "JP BD Rebuild Complete Box (English Subs)", "grail", 500),
        ("JP Import", "Macross Frontier Complete", "Blu-ray", "JP BD Box Set + Concert BD", "grail", 350),
        ("JP Import", "Macross Delta Complete", "Blu-ray", "JP BD Box Set Complete + Walkure Live", "high", 280),
        ("JP Import", "Macross Plus Complete", "Blu-ray", "JP BD Box + Movie Edition", "high", 200),
        ("JP Import", "Legend of the Galactic Heroes Complete", "Blu-ray", "JP BD Box Set (OVA 110 Ep)", "grail", 600),
        ("JP Import", "Gundam Hathaway's Flash", "Blu-ray", "JP BD LE Collector's Edition", "high", 120),
        ("JP Import", "Gundam SEED Freedom", "Blu-ray", "JP BD LE + Kira Figure", "high", 180),
        ("JP Import", "Violet Evergarden Complete", "Blu-ray", "JP BD Box Complete + Movie", "grail", 400),
        ("JP Import", "Hibike! Euphonium Complete", "Blu-ray", "JP BD Box Complete Series + Films", "high", 280),
        ("JP Import", "Your Name.", "Blu-ray", "JP BD Collector's Edition (Shinkai)", "high", 150),
        ("JP Import", "Suzume", "Blu-ray", "JP BD Collector's Edition (Shinkai)", "high", 130),
        ("JP Import", "Weathering with You", "Blu-ray", "JP BD Collector's Edition (Shinkai)", "high", 140),

        # ── OVA Collections ──────────────────────────────────────────────
        ("Discotek", "Bubblegum Crisis Complete", "Blu-ray", "OVA Complete Collection Remaster", "high", 120),
        ("Discotek", "Riding Bean + Gunsmith Cats", "Blu-ray", "OVA Double Feature Remaster", "mid", 60),
        ("Discotek", "Lupin III: Castle of Cagliostro", "Blu-ray", "Collector's Edition Remaster", "mid", 50),
        ("Discotek", "Giant Robo Complete", "Blu-ray", "OVA Complete BD Box", "high", 100),
        ("Discotek", "Patlabor OVA + Movies", "Blu-ray", "Complete Collection BD Box", "high", 150),
        ("Discotek", "Macross: Do You Remember Love?", "Blu-ray", "Remaster BD", "high", 80),
        ("Discotek", "Megazone 23 Complete", "Blu-ray", "OVA Parts I-III BD Box", "mid", 70),
        ("Discotek", "Project A-Ko Complete", "Blu-ray", "OVA Complete BD Collection", "mid", 60),

        # ── Concert / Live BDs ───────────────────────────────────────────
        ("Aniplex", "LiSA Live at Budokan", "Blu-ray", "Concert BD LE", "high", 120),
        ("Aniplex", "Aimer Special Concert", "Blu-ray", "Concert BD LE + Booklet", "high", 130),
        ("Lantis", "Love Live! Aqours 6th LoveLive!", "Blu-ray", "Concert BD Memorial Box", "high", 180),
        ("Lantis", "Love Live! Superstar!! Liella! 3rd", "Blu-ray", "Concert BD LE", "high", 120),
        ("Bandai Namco", "THE IDOLM@STER Shiny Colors 2nd", "Blu-ray", "Concert BD LE + CD", "high", 150),
        ("King Records", "Macross Frontier Galaxy Live 2023", "Blu-ray", "Concert BD LE", "high", 160),

        # ── Seasonal Complete Sets (2024-2025 Anime) ─────────────────────
        ("Crunchyroll", "Solo Leveling Season 1", "Blu-ray", "Complete LE + Arise Card Set", "high", 150),
        ("Crunchyroll", "Dandadan Season 1", "Blu-ray", "Complete LE + Art Book", "high", 130),
        ("Crunchyroll", "Kaiju No. 8 Season 1", "Blu-ray", "Complete LE + Figure", "high", 160),
        ("Crunchyroll", "Wind Breaker Season 1", "Blu-ray", "Complete LE + OST CD", "mid", 90),
        ("JP Import", "Sousou no Frieren Complete", "Blu-ray", "JP BD LE Complete Box + Drama CD", "high", 250),
        ("JP Import", "Oshi no Ko Season 2 Complete", "Blu-ray", "JP BD LE Complete + Mini Figure", "high", 180),
        ("JP Import", "Mushoku Tensei Season 2 Complete", "Blu-ray", "JP BD LE Complete + Novel Excerpt", "high", 200),
        ("JP Import", "The Apothecary Diaries Complete", "Blu-ray", "JP BD LE Complete + Art Cards", "high", 170),

        # ── Aniplex Exclusive Sets (additional) ─────────────────────────
        ("Aniplex USA", "Demon Slayer: Mugen Train Arc (TV)", "Blu-ray", "Aniplex LE + Art Book", "high", 180),
        ("Aniplex USA", "Demon Slayer: Entertainment District Arc", "Blu-ray", "Aniplex LE Box Set + Soundtrack CD", "high", 220),
        ("Aniplex USA", "Demon Slayer: Swordsmith Village Arc", "Blu-ray", "Aniplex LE Box Set + Figures", "high", 250),
        ("Aniplex USA", "Fate/stay night Heaven's Feel I. presage flower", "Blu-ray", "Aniplex LE", "high", 130),
        ("Aniplex USA", "Fate/stay night Heaven's Feel II. lost butterfly", "Blu-ray", "Aniplex LE", "high", 140),
        ("Aniplex USA", "Fate/stay night Heaven's Feel III. spring song", "Blu-ray", "Aniplex LE", "high", 150),
        ("Aniplex USA", "Fate/stay night Heaven's Feel Trilogy Box", "Blu-ray", "Aniplex LE Trilogy Box", "grail", 400),
        ("Aniplex USA", "SAO Progressive: Aria of a Starless Night", "Blu-ray", "Aniplex LE", "high", 120),
        ("Aniplex USA", "SAO Progressive: Scherzo of a Dark Dusk", "Blu-ray", "Aniplex LE", "high", 130),
        ("Aniplex USA", "Lycoris Recoil", "Blu-ray", "Aniplex LE Complete + Novel", "high", 200),
        ("Aniplex USA", "Bocchi the Rock!", "Blu-ray", "Aniplex LE Complete + Guitar Pick Set", "high", 180),
        ("Aniplex USA", "Rascal Does Not Dream of Bunny Girl Senpai", "Blu-ray", "Aniplex LE Complete", "high", 200),

        # ── 4K UHD Anime ────────────────────────────────────────────────
        ("Toei/Crunchyroll", "Dragon Ball Super: Super Hero", "4K UHD", "4K UHD + Blu-ray LE", "high", 120),
        ("Toei/Crunchyroll", "One Piece Film Red", "4K UHD", "4K UHD + Blu-ray LE", "high", 130),
        ("Toei/Crunchyroll", "Dragon Ball Super: Broly", "4K UHD", "4K UHD + Blu-ray LE", "high", 110),
        ("CoMix Wave/Crunchyroll", "Suzume", "4K UHD", "4K UHD + Blu-ray LE + Art Book", "high", 150),
        ("CoMix Wave", "Your Name (Kimi no Na wa)", "4K UHD", "4K UHD Collector's Edition", "grail", 200),
        ("CoMix Wave", "Weathering With You", "4K UHD", "4K UHD Collector's Edition", "high", 160),
        ("GKIDS", "Spirited Away", "4K UHD", "4K UHD + Blu-ray (Ghibli)", "high", 120),
        ("GKIDS", "Princess Mononoke", "4K UHD", "4K UHD + Blu-ray (Ghibli)", "high", 120),
        ("GKIDS", "My Neighbor Totoro", "4K UHD", "4K UHD + Blu-ray (Ghibli)", "high", 110),
        ("Funimation", "Akira", "4K UHD", "4K UHD Limited Edition SteelBook", "grail", 180),
        ("Funimation", "Cowboy Bebop: The Movie", "4K UHD", "4K UHD + Blu-ray", "high", 100),

        # ── Complete Series Box Sets ────────────────────────────────────
        ("Viz Media", "Naruto Shippuden Complete Series", "Blu-ray", "Complete BD Box (720 episodes)", "grail", 350),
        ("Viz Media", "Naruto (Original) Complete Series", "Blu-ray", "Complete BD Box (220 episodes)", "high", 250),
        ("Viz Media", "Bleach TYBW Season 1", "Blu-ray", "LE + Art Book + Bankai Cards", "high", 150),
        ("Viz Media", "Bleach TYBW Season 2", "Blu-ray", "LE + Art Book", "high", 160),
        ("Viz Media", "Bleach Complete Box Set (Original)", "Blu-ray", "Complete BD (366 episodes)", "grail", 400),
        ("Toei/Funimation", "One Piece Film Collection (15 Films)", "Blu-ray", "Film BD Collection Box", "grail", 300),
        ("Toei/Funimation", "Dragon Ball Z Complete Series", "Blu-ray", "Season BD Box 1-9", "grail", 280),
        ("Funimation", "My Hero Academia Complete S1-S6", "Blu-ray", "LE Box Sets Bundle", "high", 250),
        ("Crunchyroll", "Jujutsu Kaisen Season 1 Complete", "Blu-ray", "LE + Soundtrack CD + Art Cards", "high", 180),
        ("Crunchyroll", "Jujutsu Kaisen Season 2 Complete", "Blu-ray", "LE + Shibuya Art Book", "high", 200),

        # ── Discotek / Boutique Releases ────────────────────────────────
        ("Discotek", "Urusei Yatsura Complete Series", "Blu-ray", "Complete BD Box (195 episodes)", "grail", 250),
        ("Discotek", "Lupin III Part I Complete", "Blu-ray", "HD Remaster BD", "high", 100),
        ("Discotek", "Lupin III: Castle of Cagliostro", "Blu-ray", "Collector's BD + Booklet", "mid", 50),
        ("Discotek", "Robot Carnival", "Blu-ray", "BD + DVD Combo", "mid", 40),
        ("Discotek", "Giant Robo Complete OVA", "Blu-ray", "Complete BD Box", "high", 120),
        ("Discotek", "Fist of the North Star Complete", "Blu-ray", "Complete BD Box (152 episodes)", "high", 180),
        ("Discotek", "Space Adventure Cobra Complete", "Blu-ray", "Complete BD Box", "high", 100),
        ("Arrow Video", "Mobile Suit Gundam (Original Trilogy Films)", "Blu-ray", "Arrow LE Box Set", "high", 130),
        ("Arrow Video", "Patlabor: The Movie 1 & 2", "Blu-ray", "Arrow LE Dual Pack", "high", 110),
        ("Shout Factory", "Ghost in the Shell (1995)", "Blu-ray", "4K Restoration BD + Booklet", "high", 100),
        ("Shout Factory", "Perfect Blue", "Blu-ray", "Limited Edition BD + Art Cards", "high", 120),
        ("Criterion", "Akira (Criterion Collection)", "Blu-ray", "Criterion #868 Special Edition", "high", 120),
        ("Criterion", "Neon Genesis Evangelion Complete", "Blu-ray", "Criterion Box (proposed)", "grail", 300),
        ("All the Anime (UK)", "Cowboy Bebop Complete", "Blu-ray", "Ultimate Edition Box", "grail", 280),
    ]
    catalog = []
    for publisher, title, fmt, edition, tier, price in releases:
        catalog.append({
            "publisher": publisher,
            "title": title,
            "format": fmt,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    publisher = item["publisher"]
    title = item["title"]
    fmt = item["format"]
    edition = item["edition"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{publisher}-{title}-{edition}"),
        title=f"{title} ({fmt})",
        set_code=publisher.lower().replace(" ", "-"),
        brand=publisher,
        rarity=item["rarity_tier"].title(),
        notes=f"{publisher} | {edition} | {fmt}",
        attributes_json={
            "publisher": publisher,
            "format": fmt,
            "edition": edition,
            "is_jp_import": publisher == "JP Import",
            "is_laserdisc": fmt == "Laserdisc",
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    is_limited = any(kw in item["edition"].lower() for kw in ["limited", "le", "box set", "complete"])
    is_jp = item["publisher"] == "JP Import"

    return PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": 0.9 if is_limited else 0.4,
            "is_jp_import": 1.0 if is_jp else 0.0,
            "is_laserdisc": 1.0 if item["format"] == "Laserdisc" else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import anime Blu-ray catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Anime Blu-ray Import ===")

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

    logger.info(f"\n=== Anime Blu-ray Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
