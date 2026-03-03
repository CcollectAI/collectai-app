"""
Import Anime Figures catalog.

Layer 1 (Catalog):  Curated anime figure collection → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers 550+ figures across:
- Scale figures: Good Smile Company, Kotobukiya, Alter, Max Factory, FREEing (1/4 to 1/8)
- Nendoroids: chibi-style collectible figures (20+ characters)
- Figma: articulated action figures (10+ characters)
- S.H.Figuarts: Bandai premium articulated figures
- Prize figures: Banpresto (Grandista, DXF, Vibration Stars)
- Garage kits / resin: unpainted GK kits
- Premium resin: Prime 1 Studio, Tsume Art HQS (ultra grails)
- Robot Spirits / Metal Build: Bandai mecha lines (Gundam)
- Pop Up Parade: affordable entry-level figures
- B-style: FREEing 1/4 bunny figures (premium grails)
- Myethos / eStream: premium third-party scale figures
- Series: Demon Slayer, Jujutsu Kaisen, One Piece, Fate, Evangelion,
  Hatsune Miku, Attack on Titan, Chainsaw Man, Spy x Family,
  Dragon Ball Z/Super, Naruto, My Hero Academia, Re:Zero, Bleach, Gundam,
  Berserk, Frieren, Solo Leveling, Oshi no Ko, Blue Lock, Genshin Impact,
  My Dress-Up Darling, DARLING in the FRANXX, Quintessential Quintuplets

Usage:
    python -m pipelines.import_anime_figures [--dry-run]
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

CATEGORY = "anime_figures"


def get_curated_catalog() -> list[dict]:
    """Curated anime figure catalog covering major manufacturers and series (550+ items)."""

    # (manufacturer, figure_type, character, series, scale, rarity_tier, price_eur)
    # rarity_tier: grail (>400), high (200-400), mid (80-200), standard (<80)

    figures = [
        # ── Demon Slayer - Scale Figures ──────────────────────────────
        ("Good Smile Company", "Scale", "Tanjiro Kamado", "Demon Slayer", "1/8", "mid", 160),
        ("Kotobukiya", "Scale", "Nezuko Kamado", "Demon Slayer", "1/8", "mid", 140),
        ("Aniplex", "Scale", "Rengoku Kyojuro", "Demon Slayer", "1/8", "high", 220),
        ("Alter", "Scale", "Shinobu Kocho", "Demon Slayer", "1/7", "high", 250),
        ("Good Smile Company", "Scale", "Muzan Kibutsuji", "Demon Slayer", "1/8", "high", 280),

        # ── Jujutsu Kaisen ────────────────────────────────────────────
        ("Kotobukiya", "Scale", "Gojo Satoru", "Jujutsu Kaisen", "1/7", "high", 230),
        ("Good Smile Company", "Scale", "Itadori Yuji & Sukuna", "Jujutsu Kaisen", "1/7", "high", 260),
        ("MegaHouse", "Scale", "Fushiguro Megumi", "Jujutsu Kaisen", "1/8", "mid", 180),
        ("FREEing", "Scale", "Gojo Satoru Casual Ver.", "Jujutsu Kaisen", "1/4", "grail", 450),

        # ── One Piece ─────────────────────────────────────────────────
        ("MegaHouse", "Portrait of Pirates", "Monkey D. Luffy Gear 5", "One Piece", "1/8", "high", 280),
        ("MegaHouse", "Portrait of Pirates", "Roronoa Zoro", "One Piece", "1/8", "mid", 180),
        ("MegaHouse", "Portrait of Pirates", "Boa Hancock Ver.BB", "One Piece", "1/8", "high", 350),
        ("Banpresto", "DXF", "Shanks Film Red", "One Piece", "Non-scale", "standard", 25),
        ("Banpresto", "King of Artist", "Portgas D. Ace", "One Piece", "Non-scale", "standard", 35),
        ("Tsume Art", "HQS", "Luffy Gear Fourth Snakeman", "One Piece", "1/4", "grail", 750),

        # ── Fate Series ───────────────────────────────────────────────
        ("Good Smile Company", "Scale", "Saber Altria Pendragon", "Fate/Stay Night", "1/7", "high", 220),
        ("Alter", "Scale", "Saber Alter Dress Ver.", "Fate/Stay Night", "1/7", "grail", 400),
        ("Max Factory", "Scale", "Rider Medusa", "Fate/Stay Night", "1/7", "mid", 180),
        ("Aniplex", "Scale", "Jeanne d'Arc", "Fate/Grand Order", "1/7", "high", 260),
        ("Good Smile Company", "Scale", "Mash Kyrielight", "Fate/Grand Order", "1/7", "mid", 190),

        # ── Evangelion ────────────────────────────────────────────────
        ("Kotobukiya", "Scale", "Rei Ayanami Plugsuit Ver.", "Evangelion", "1/6", "high", 200),
        ("Alter", "Scale", "Asuka Langley Test Plugsuit", "Evangelion", "1/7", "high", 280),
        ("Medicom", "RAH", "Shinji Ikari Plugsuit", "Evangelion", "1/6", "high", 350),
        ("Kotobukiya", "Scale", "Eva Unit-01 Awakening", "Evangelion", "Non-scale", "grail", 500),

        # ── Hatsune Miku / Vocaloid ──────────────────────────────────
        ("Good Smile Company", "Scale", "Hatsune Miku V4X", "Vocaloid", "1/8", "mid", 160),
        ("Max Factory", "Scale", "Hatsune Miku Deep Sea Girl", "Vocaloid", "1/8", "high", 320),
        ("FREEing", "Scale", "Hatsune Miku Bunny Ver.", "Vocaloid", "1/4", "grail", 480),
        ("Good Smile Company", "Scale", "Hatsune Miku Memorial Dress", "Vocaloid", "1/7", "high", 200),
        ("Good Smile Company", "Scale", "Kagamine Rin & Len", "Vocaloid", "1/8", "mid", 180),

        # ── Attack on Titan (8) ───────────────────────────────────────
        ("Good Smile Company", "Scale", "Levi Ackerman", "Attack on Titan", "1/7", "high", 240),
        ("Kotobukiya", "Scale", "Levi Fortitude Ver.", "Attack on Titan", "1/8", "mid", 170),
        ("Sentinel", "Scale", "Levi Brave-Act", "Attack on Titan", "1/8", "high", 210),
        ("Good Smile Company", "Scale", "Eren Yeager Attack Titan", "Attack on Titan", "1/7", "high", 260),
        ("Kotobukiya", "Scale", "Mikasa Ackerman", "Attack on Titan", "1/8", "mid", 160),
        ("Good Smile Company", "Scale", "Colossal Titan", "Attack on Titan", "Non-scale", "grail", 420),
        ("Kotobukiya", "Scale", "Erwin Smith", "Attack on Titan", "1/8", "mid", 150),
        ("Sentinel", "Scale", "Hange Zoe", "Attack on Titan", "1/8", "mid", 185),

        # ── Chainsaw Man (6) ──────────────────────────────────────────
        ("Good Smile Company", "Scale", "Denji", "Chainsaw Man", "1/7", "high", 210),
        ("Kotobukiya", "Scale", "Power", "Chainsaw Man", "1/7", "high", 220),
        ("Good Smile Company", "Scale", "Makima", "Chainsaw Man", "1/7", "high", 230),
        ("FREEing", "Scale", "Power Bunny Ver.", "Chainsaw Man", "1/4", "grail", 460),
        ("Kotobukiya", "Scale", "Pochita Oversized", "Chainsaw Man", "Non-scale", "mid", 85),
        ("Good Smile Company", "Scale", "Denji Chainsaw Devil Form", "Chainsaw Man", "1/8", "high", 280),

        # ── Spy x Family (5) ─────────────────────────────────────────
        ("Good Smile Company", "Scale", "Anya Forger", "Spy x Family", "1/7", "mid", 150),
        ("Alter", "Scale", "Yor Forger Thorn Princess", "Spy x Family", "1/7", "high", 260),
        ("Good Smile Company", "Scale", "Loid Forger", "Spy x Family", "1/8", "mid", 140),
        ("Bandai", "S.H.Figuarts", "Yor Forger Action", "Spy x Family", "Non-scale", "mid", 80),
        ("Kotobukiya", "Scale", "Anya & Bond Forger", "Spy x Family", "1/7", "mid", 170),

        # ── Dragon Ball Z / Super (8) ────────────────────────────────
        ("Banpresto", "Grandista", "Son Goku Super Saiyan", "Dragon Ball Z", "Non-scale", "standard", 40),
        ("Bandai", "S.H.Figuarts", "Goku Ultra Instinct", "Dragon Ball Super", "Non-scale", "mid", 95),
        ("MegaHouse", "Dimension of DRAGONBALL", "Vegeta Galick Gun", "Dragon Ball Z", "Non-scale", "mid", 130),
        ("Tsume Art", "HQS", "Broly Legendary Super Saiyan", "Dragon Ball Z", "1/4", "grail", 850),
        ("Bandai", "S.H.Figuarts", "Vegeta SSBE", "Dragon Ball Super", "Non-scale", "mid", 85),
        ("Banpresto", "Grandista", "Frieza Final Form", "Dragon Ball Z", "Non-scale", "standard", 35),
        ("MegaHouse", "Dimension of DRAGONBALL", "Son Gohan SSJ2", "Dragon Ball Z", "Non-scale", "mid", 140),
        ("Bandai", "S.H.Figuarts", "Goku SSJ4", "Dragon Ball GT", "Non-scale", "mid", 90),

        # ── Naruto (6) ───────────────────────────────────────────────
        ("MegaHouse", "GEM", "Naruto Uzumaki Sage Mode", "Naruto Shippuden", "1/8", "mid", 150),
        ("MegaHouse", "GEM", "Sasuke Uchiha Susanoo", "Naruto Shippuden", "1/8", "high", 200),
        ("Good Smile Company", "Scale", "Kakashi Hatake Anbu Ver.", "Naruto Shippuden", "1/8", "high", 230),
        ("MegaHouse", "GEM", "Itachi Uchiha Tsukuyomi", "Naruto Shippuden", "1/8", "high", 240),
        ("Tsume Art", "HQS", "Naruto Six Paths Sage Mode", "Naruto Shippuden", "1/6", "grail", 680),
        ("Kotobukiya", "Scale", "Minato Namikaze", "Naruto Shippuden", "1/8", "mid", 160),

        # ── My Hero Academia (5) ─────────────────────────────────────
        ("Kotobukiya", "Scale", "Izuku Midoriya Shoot Style", "My Hero Academia", "1/8", "mid", 140),
        ("Good Smile Company", "Scale", "All Might Silver Age", "My Hero Academia", "1/8", "high", 220),
        ("Kotobukiya", "Scale", "Katsuki Bakugo", "My Hero Academia", "1/8", "mid", 135),
        ("Kotobukiya", "Scale", "Shoto Todoroki", "My Hero Academia", "1/8", "mid", 130),
        ("Good Smile Company", "Scale", "Deku Full Cowling Ver.", "My Hero Academia", "1/8", "mid", 180),

        # ── Re:Zero (5) ──────────────────────────────────────────────
        ("Good Smile Company", "Scale", "Rem", "Re:Zero", "1/7", "high", 220),
        ("Good Smile Company", "Scale", "Ram", "Re:Zero", "1/7", "mid", 180),
        ("FREEing", "Scale", "Rem Bunny Ver.", "Re:Zero", "1/4", "grail", 520),
        ("Kadokawa", "Scale", "Emilia Crystal Dress", "Re:Zero", "1/7", "high", 250),
        ("FREEing", "Scale", "Ram Bunny Ver.", "Re:Zero", "1/4", "grail", 480),

        # ── Bleach (4) ───────────────────────────────────────────────
        ("MegaHouse", "GEM", "Ichigo Kurosaki Bankai", "Bleach", "1/8", "mid", 170),
        ("MegaHouse", "GEM", "Rukia Kuchiki", "Bleach", "1/8", "mid", 140),
        ("Banpresto", "Grandista", "Grimmjow Jaegerjaquez", "Bleach", "Non-scale", "standard", 38),
        ("MegaHouse", "GEM", "Aizen Sosuke Hogyoku", "Bleach", "1/8", "mid", 185),

        # ── Gundam (4) ───────────────────────────────────────────────
        ("Bandai", "Robot Spirits", "RX-78-2 Gundam ver. A.N.I.M.E.", "Mobile Suit Gundam", "Non-scale", "mid", 80),
        ("Bandai", "Robot Spirits", "Nu Gundam", "Char's Counterattack", "Non-scale", "mid", 95),
        ("Bandai", "Robot Spirits", "Strike Freedom Gundam", "Gundam SEED Destiny", "Non-scale", "mid", 90),
        ("Bandai", "Metal Build", "Wing Gundam Zero EW", "Gundam Wing", "Non-scale", "high", 280),

        # ── Nendoroids (20) ──────────────────────────────────────────
        ("Good Smile Company", "Nendoroid", "Gojo Satoru Nendoroid", "Jujutsu Kaisen", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Tanjiro Kamado Nendoroid", "Demon Slayer", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Hatsune Miku 2.0 Nendoroid", "Vocaloid", "Nendoroid", "standard", 45),
        ("Good Smile Company", "Nendoroid", "Link Breath of the Wild Nendoroid", "Zelda", "Nendoroid", "mid", 80),
        ("Good Smile Company", "Nendoroid", "Levi Ackerman Nendoroid", "Attack on Titan", "Nendoroid", "mid", 90),
        ("Good Smile Company", "Nendoroid", "Naruto Uzumaki Nendoroid", "Naruto", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Rem Nendoroid", "Re:Zero", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Zero Two Nendoroid", "DARLING in the FRANXX", "Nendoroid", "mid", 100),
        ("Good Smile Company", "Nendoroid", "Pochita Nendoroid", "Chainsaw Man", "Nendoroid", "standard", 45),
        ("Good Smile Company", "Nendoroid", "Anya Forger Nendoroid", "Spy x Family", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Denji Nendoroid", "Chainsaw Man", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Makima Nendoroid", "Chainsaw Man", "Nendoroid", "standard", 60),
        ("Good Smile Company", "Nendoroid", "Eren Yeager Nendoroid", "Attack on Titan", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Ichigo Kurosaki Nendoroid", "Bleach", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Deku Nendoroid", "My Hero Academia", "Nendoroid", "standard", 48),
        ("Good Smile Company", "Nendoroid", "All Might Nendoroid", "My Hero Academia", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Goku Nendoroid", "Dragon Ball Z", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Emilia Nendoroid", "Re:Zero", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Bakugo Nendoroid", "My Hero Academia", "Nendoroid", "standard", 48),
        ("Good Smile Company", "Nendoroid", "Sasuke Uchiha Nendoroid", "Naruto", "Nendoroid", "standard", 55),

        # ── Figma (10) ───────────────────────────────────────────────
        ("Max Factory", "Figma", "Saber 2.0 Figma", "Fate/Stay Night", "Figma", "mid", 80),
        ("Max Factory", "Figma", "Guts Berserker Armor Figma", "Berserk", "Figma", "mid", 120),
        ("Max Factory", "Figma", "Link Twilight Princess Figma", "Zelda", "Figma", "mid", 95),
        ("Max Factory", "Figma", "Mikasa Ackerman Figma", "Attack on Titan", "Figma", "standard", 70),
        ("Max Factory", "Figma", "Denji Figma", "Chainsaw Man", "Figma", "standard", 65),
        ("Max Factory", "Figma", "Levi Ackerman Figma", "Attack on Titan", "Figma", "mid", 85),
        ("Max Factory", "Figma", "Eren Yeager Figma", "Attack on Titan", "Figma", "standard", 70),
        ("Max Factory", "Figma", "Kirito Figma", "Sword Art Online", "Figma", "standard", 65),
        ("Max Factory", "Figma", "Power Figma", "Chainsaw Man", "Figma", "standard", 70),
        ("Max Factory", "Figma", "Naruto Uzumaki Figma", "Naruto Shippuden", "Figma", "standard", 75),

        # ── S.H.Figuarts (6) ─────────────────────────────────────────
        ("Bandai", "S.H.Figuarts", "Goku SSJ God", "Dragon Ball Super", "Non-scale", "mid", 85),
        ("Bandai", "S.H.Figuarts", "Naruto Uzumaki Best Selection", "Naruto Shippuden", "Non-scale", "mid", 80),
        ("Bandai", "S.H.Figuarts", "Monkey D. Luffy Gear 5", "One Piece", "Non-scale", "mid", 90),
        ("Bandai", "S.H.Figuarts", "Broly Full Power", "Dragon Ball Super", "Non-scale", "mid", 100),
        ("Bandai", "S.H.Figuarts", "Kakashi Hatake", "Naruto Shippuden", "Non-scale", "mid", 85),
        ("Bandai", "S.H.Figuarts", "Roronoa Zoro", "One Piece", "Non-scale", "mid", 80),

        # ── Prize Figures - Banpresto ─────────────────────────────────
        ("Banpresto", "Grandista", "Son Goku Manga Dimensions", "Dragon Ball Z", "Non-scale", "standard", 35),
        ("Banpresto", "Grandista", "Vegeta Manga Dimensions", "Dragon Ball Z", "Non-scale", "standard", 30),
        ("Banpresto", "Vibration Stars", "Tanjiro Kamado", "Demon Slayer", "Non-scale", "standard", 22),
        ("Banpresto", "Vibration Stars", "Zenitsu Agatsuma", "Demon Slayer", "Non-scale", "standard", 20),
        ("Banpresto", "Chronicle Master Stars", "Luffy Gear 5", "One Piece", "Non-scale", "standard", 38),

        # ── Garage Kits / Resin ───────────────────────────────────────
        ("E2046", "Garage Kit", "Saber Lily Unpainted GK", "Fate/Stay Night", "1/6", "high", 280),
        ("Hobby Japan", "Garage Kit", "Rei Ayanami GK Unpainted", "Evangelion", "1/6", "high", 320),
        ("Private Studio", "Garage Kit", "Gojo Domain Expansion Resin", "Jujutsu Kaisen", "1/6", "grail", 650),
        ("Private Studio", "Garage Kit", "Luffy Gear 5 Resin Statue", "One Piece", "1/6", "grail", 800),
        ("Private Studio", "Garage Kit", "Tanjiro vs Rui Diorama Resin", "Demon Slayer", "1/8", "grail", 550),

        # ── Prime 1 Studio / Tsume Art - Ultra Grails (5) ────────────
        ("Prime 1 Studio", "Premium Masterline", "Eren Attack Titan", "Attack on Titan", "1/4", "grail", 1200),
        ("Prime 1 Studio", "Premium Masterline", "Guts Berserker Armor", "Berserk", "1/4", "grail", 1350),
        ("Tsume Art", "HQS+", "Naruto vs Sasuke Valley of the End", "Naruto Shippuden", "1/6", "grail", 950),
        ("Tsume Art", "HQS", "All Might United States of Smash", "My Hero Academia", "1/4", "grail", 780),
        ("Prime 1 Studio", "Premium Masterline", "Levi vs Beast Titan", "Attack on Titan", "1/4", "grail", 1100),

        # ── Frieren: Beyond Journey's End (3) ──────────────────────────
        ("Good Smile Company", "Scale", "Frieren", "Frieren: Beyond Journey's End", "1/7", "high", 220),
        ("Kotobukiya", "Scale", "Fern", "Frieren: Beyond Journey's End", "1/7", "mid", 170),
        ("Good Smile Company", "Scale", "Himmel the Hero", "Frieren: Beyond Journey's End", "1/8", "mid", 160),

        # ── Oshi no Ko (3) ─────────────────────────────────────────────
        ("Good Smile Company", "Scale", "Ai Hoshino Idol Costume", "Oshi no Ko", "1/7", "high", 240),
        ("Kotobukiya", "Scale", "Ruby Hoshino", "Oshi no Ko", "1/7", "mid", 180),
        ("FREEing", "Scale", "Ai Hoshino Bunny Ver.", "Oshi no Ko", "1/4", "grail", 490),

        # ── Bocchi the Rock! (2) ───────────────────────────────────────
        ("Aniplex", "Scale", "Hitori Gotoh Guitar Ver.", "Bocchi the Rock!", "1/7", "high", 210),
        ("Good Smile Company", "Scale", "Nijika Ijichi", "Bocchi the Rock!", "1/7", "mid", 160),

        # ── JoJo's Bizarre Adventure (2) ──────────────────────────────
        ("Medicos", "Super Action Statue", "Jotaro Kujo", "JoJo's Bizarre Adventure", "Non-scale", "mid", 90),
        ("Medicos", "Super Action Statue", "Dio Brando", "JoJo's Bizarre Adventure", "Non-scale", "mid", 95),

        # ── Solo Leveling (2) ──────────────────────────────────────────
        ("Aniplex", "Scale", "Sung Jinwoo Shadow Monarch", "Solo Leveling", "1/7", "high", 260),
        ("A-Plus", "Scale", "Igris Shadow Soldier", "Solo Leveling", "1/7", "high", 300),

        # ── Sword Art Online (4) ────────────────────────────────────────
        ("Good Smile Company", "Scale", "Kirito Aincrad Ver.", "Sword Art Online", "1/8", "mid", 160),
        ("Kotobukiya", "Scale", "Asuna Undine Ver.", "Sword Art Online", "1/7", "high", 200),
        ("FREEing", "Scale", "Asuna Bunny Ver.", "Sword Art Online", "1/4", "grail", 470),
        ("Good Smile Company", "Scale", "Sinon Phantom Bullet", "Sword Art Online", "1/7", "mid", 170),

        # ── Fullmetal Alchemist (3) ─────────────────────────────────────
        ("Kotobukiya", "Scale", "Edward Elric", "Fullmetal Alchemist", "1/8", "mid", 150),
        ("Good Smile Company", "Scale", "Alphonse Elric", "Fullmetal Alchemist", "1/8", "mid", 175),
        ("Kotobukiya", "Scale", "Roy Mustang Flame Alchemist", "Fullmetal Alchemist", "1/8", "high", 210),

        # ── Tokyo Ghoul (3) ─────────────────────────────────────────────
        ("Kotobukiya", "Scale", "Ken Kaneki Awakened Ver.", "Tokyo Ghoul", "1/8", "high", 230),
        ("Good Smile Company", "Scale", "Touka Kirishima", "Tokyo Ghoul", "1/7", "mid", 165),
        ("Kotobukiya", "Scale", "Ken Kaneki Half-Kakuja", "Tokyo Ghoul", "1/8", "mid", 190),

        # ── Mob Psycho 100 (2) ──────────────────────────────────────────
        ("Good Smile Company", "Scale", "Mob ???% Form", "Mob Psycho 100", "1/8", "high", 210),
        ("Kotobukiya", "Scale", "Reigen Arataka", "Mob Psycho 100", "1/8", "mid", 140),

        # ── Blue Lock (3) ───────────────────────────────────────────────
        ("Good Smile Company", "Scale", "Isagi Yoichi", "Blue Lock", "1/7", "mid", 170),
        ("Kotobukiya", "Scale", "Bachira Meguru", "Blue Lock", "1/7", "mid", 165),
        ("Aniplex", "Scale", "Rin Itoshi", "Blue Lock", "1/7", "high", 200),

        # ── Vinland Saga (2) ───────────────────────────────────────────
        ("Good Smile Company", "Scale", "Thorfinn", "Vinland Saga", "1/7", "high", 220),
        ("Max Factory", "Figma", "Askeladd Figma", "Vinland Saga", "Figma", "mid", 85),

        # ── Mushoku Tensei (3) ──────────────────────────────────────────
        ("Kotobukiya", "Scale", "Roxy Migurdia", "Mushoku Tensei", "1/7", "high", 240),
        ("Good Smile Company", "Scale", "Eris Boreas Greyrat", "Mushoku Tensei", "1/7", "mid", 190),
        ("FREEing", "Scale", "Roxy Migurdia Bunny Ver.", "Mushoku Tensei", "1/4", "grail", 500),

        # ── Dandadan (2) ───────────────────────────────────────────────
        ("Good Smile Company", "Scale", "Momo Ayase", "Dandadan", "1/7", "mid", 180),
        ("Kotobukiya", "Scale", "Okarun Turbo Granny", "Dandadan", "1/8", "mid", 165),

        # ── Cyberpunk: Edgerunners (2) ─────────────────────────────────
        ("Good Smile Company", "Scale", "Lucy", "Cyberpunk: Edgerunners", "1/7", "high", 250),
        ("Kotobukiya", "Scale", "David Martinez", "Cyberpunk: Edgerunners", "1/7", "high", 220),

        # ── Hell's Paradise (2) ────────────────────────────────────────
        ("Aniplex", "Scale", "Gabimaru the Hollow", "Hell's Paradise", "1/7", "high", 210),
        ("Good Smile Company", "Scale", "Sagiri Yamada Asaemon", "Hell's Paradise", "1/7", "mid", 180),

        # ── Lycoris Recoil (2) ─────────────────────────────────────────
        ("Good Smile Company", "Scale", "Chisato Nishikigi", "Lycoris Recoil", "1/7", "mid", 180),
        ("Kotobukiya", "Scale", "Takina Inoue", "Lycoris Recoil", "1/7", "mid", 170),

        # ── Kaiju No. 8 (2) ────────────────────────────────────────────
        ("Good Smile Company", "Scale", "Kafka Hibino Kaiju Form", "Kaiju No. 8", "1/7", "high", 240),
        ("Kotobukiya", "Scale", "Kafka Hibino Human Form", "Kaiju No. 8", "1/8", "mid", 150),

        # ── Additional Nendoroids (10) ──────────────────────────────────
        ("Good Smile Company", "Nendoroid", "Frieren Nendoroid", "Frieren: Beyond Journey's End", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Ai Hoshino Nendoroid", "Oshi no Ko", "Nendoroid", "standard", 60),
        ("Good Smile Company", "Nendoroid", "Sung Jinwoo Nendoroid", "Solo Leveling", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Bocchi Hitori Nendoroid", "Bocchi the Rock!", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Chisato Nishikigi Nendoroid", "Lycoris Recoil", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Power Nendoroid", "Chainsaw Man", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Roxy Migurdia Nendoroid", "Mushoku Tensei", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Jotaro Kujo Nendoroid", "JoJo's Bizarre Adventure", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Kaneki Ken Nendoroid", "Tokyo Ghoul", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Momo Ayase Nendoroid", "Dandadan", "Nendoroid", "standard", 50),

        # ── Additional Figma (5) ───────────────────────────────────────
        ("Max Factory", "Figma", "Gojo Satoru Figma", "Jujutsu Kaisen", "Figma", "mid", 80),
        ("Max Factory", "Figma", "Makima Figma", "Chainsaw Man", "Figma", "mid", 80),
        ("Max Factory", "Figma", "Tanjiro Kamado Figma", "Demon Slayer", "Figma", "standard", 70),
        ("Max Factory", "Figma", "Yor Forger Figma", "Spy x Family", "Figma", "standard", 75),
        ("Max Factory", "Figma", "Sung Jinwoo Figma", "Solo Leveling", "Figma", "mid", 85),

        # ── Additional Prize Figures (5) ───────────────────────────────
        ("Banpresto", "Vibration Stars", "Gojo Satoru Hollow Purple", "Jujutsu Kaisen", "Non-scale", "standard", 25),
        ("Banpresto", "Grandista", "Naruto Uzumaki Baryon Mode", "Naruto Shippuden", "Non-scale", "standard", 35),
        ("Banpresto", "DXF", "Monkey D. Luffy Gear 5 Nika", "One Piece", "Non-scale", "standard", 28),
        ("Banpresto", "Chronicle Master Stars", "Roronoa Zoro Enma", "One Piece", "Non-scale", "standard", 32),
        ("Banpresto", "Vibration Stars", "Denji Rev.", "Chainsaw Man", "Non-scale", "standard", 22),

        # ── Additional Grails (5) ──────────────────────────────────────
        ("Prime 1 Studio", "Premium Masterline", "Gojo Satoru Domain Expansion", "Jujutsu Kaisen", "1/4", "grail", 1400),
        ("Tsume Art", "HQS+", "Luffy Gear 5 Nika", "One Piece", "1/4", "grail", 900),
        ("Prime 1 Studio", "Premium Masterline", "Chainsaw Devil Final Battle", "Chainsaw Man", "1/4", "grail", 1250),
        ("Tsume Art", "HQS", "Ichigo Final Getsuga Tensho", "Bleach", "1/6", "grail", 850),
        ("Prime 1 Studio", "Premium Masterline", "Tanjiro Hinokami Kagura", "Demon Slayer", "1/4", "grail", 1150),

        # ── Misc Series (6) ───────────────────────────────────────────
        ("Good Smile Company", "Scale", "Violet Evergarden", "Violet Evergarden", "1/7", "high", 230),
        ("Good Smile Company", "Scale", "Mai Sakurajima Bunny Ver.", "Rascal Does Not Dream", "1/7", "high", 240),
        ("Alter", "Scale", "Darkness Lalatina", "KonoSuba", "1/7", "mid", 185),
        ("Good Smile Company", "Scale", "Megumin Explosion Ver.", "KonoSuba", "1/7", "high", 210),
        ("Kotobukiya", "Scale", "Rimuru Tempest", "That Time I Got Reincarnated as a Slime", "1/8", "mid", 160),
        ("Alter", "Scale", "Shion", "That Time I Got Reincarnated as a Slime", "1/7", "mid", 175),

        # ── Berserk (5) ──────────────────────────────────────────────────
        ("Good Smile Company", "Scale", "Guts Black Swordsman", "Berserk", "1/6", "grail", 420),
        ("Alter", "Scale", "Griffith Hawk of Light", "Berserk", "1/8", "high", 280),
        ("Art of War", "Scale", "Skull Knight on Horse", "Berserk", "1/6", "grail", 750),
        ("Max Factory", "Figma", "Casca Figma", "Berserk", "Figma", "mid", 110),
        ("Threezero", "Scale", "Guts Berserker Armor Threezero", "Berserk", "1/6", "grail", 550),

        # ── Demon Slayer - Additional ────────────────────────────────────
        ("Aniplex", "Scale", "Tengen Uzui", "Demon Slayer", "1/8", "high", 240),
        ("Alter", "Scale", "Mitsuri Kanroji", "Demon Slayer", "1/7", "high", 260),
        ("Kotobukiya", "Scale", "Giyu Tomioka Water Breathing", "Demon Slayer", "1/8", "high", 210),
        ("Aniplex", "Scale", "Nezuko Kamado Demon Form", "Demon Slayer", "1/8", "high", 270),
        ("Good Smile Company", "Scale", "Zenitsu Agatsuma Thunder Breathing", "Demon Slayer", "1/8", "mid", 180),
        ("Good Smile Company", "Scale", "Inosuke Hashibira", "Demon Slayer", "1/8", "mid", 170),

        # ── Jujutsu Kaisen - Additional ──────────────────────────────────
        ("Kotobukiya", "Scale", "Nobara Kugisaki", "Jujutsu Kaisen", "1/7", "mid", 185),
        ("Aniplex", "Scale", "Toji Fushiguro", "Jujutsu Kaisen", "1/7", "high", 250),
        ("Good Smile Company", "Scale", "Sukuna Heian Era", "Jujutsu Kaisen", "1/7", "high", 290),
        ("Alter", "Scale", "Gojo Satoru Infinite Void", "Jujutsu Kaisen", "1/7", "grail", 400),
        ("MegaHouse", "Scale", "Ryomen Sukuna", "Jujutsu Kaisen", "1/8", "high", 220),
        ("eStream", "Scale", "Gojo Satoru Shibuya Arc", "Jujutsu Kaisen", "1/7", "grail", 480),

        # ── Chainsaw Man - Additional ────────────────────────────────────
        ("Alter", "Scale", "Aki Hayakawa Fox Devil", "Chainsaw Man", "1/7", "high", 240),
        ("Aniplex", "Scale", "Reze Bomb Devil", "Chainsaw Man", "1/7", "high", 260),
        ("eStream", "Scale", "Power Blood Fiend Form", "Chainsaw Man", "1/7", "high", 300),
        ("Myethos", "Scale", "Makima Control Devil", "Chainsaw Man", "1/7", "high", 280),

        # ── Spy x Family - Additional ────────────────────────────────────
        ("FREEing", "Scale", "Yor Forger Bunny Ver.", "Spy x Family", "1/4", "grail", 470),
        ("Alter", "Scale", "Anya Forger Stella Star Ver.", "Spy x Family", "1/7", "mid", 180),
        ("Kotobukiya", "Scale", "Loid Forger Twilight Mission", "Spy x Family", "1/8", "mid", 165),

        # ── Frieren - Additional ─────────────────────────────────────────
        ("Alter", "Scale", "Frieren Magic Casting", "Frieren: Beyond Journey's End", "1/7", "high", 260),
        ("Good Smile Company", "Scale", "Stark", "Frieren: Beyond Journey's End", "1/8", "mid", 160),
        ("FREEing", "Scale", "Fern Bunny Ver.", "Frieren: Beyond Journey's End", "1/4", "grail", 450),

        # ── Solo Leveling - Additional ───────────────────────────────────
        ("Good Smile Company", "Scale", "Beru Shadow Ant King", "Solo Leveling", "1/7", "high", 280),
        ("Kotobukiya", "Scale", "Sung Jinwoo Arise Ver.", "Solo Leveling", "1/8", "high", 230),

        # ── Oshi no Ko - Additional ──────────────────────────────────────
        ("Good Smile Company", "Scale", "Aqua Hoshino", "Oshi no Ko", "1/7", "mid", 180),
        ("Kotobukiya", "Scale", "Kana Arima", "Oshi no Ko", "1/7", "mid", 170),
        ("Aniplex", "Scale", "Mem-Cho", "Oshi no Ko", "1/7", "mid", 165),

        # ── Blue Lock - Additional ───────────────────────────────────────
        ("Kotobukiya", "Scale", "Nagi Seishiro", "Blue Lock", "1/7", "mid", 175),
        ("Good Smile Company", "Scale", "Chigiri Hyoma", "Blue Lock", "1/7", "mid", 170),
        ("FREEing", "Scale", "Isagi Yoichi Jersey Ver.", "Blue Lock", "1/7", "mid", 160),

        # ── One Piece - Additional ───────────────────────────────────────
        ("MegaHouse", "Portrait of Pirates", "Yamato", "One Piece", "1/8", "high", 300),
        ("MegaHouse", "Portrait of Pirates", "Nami Ver.BB", "One Piece", "1/8", "high", 320),
        ("Bandai", "S.H.Figuarts", "Gear 5 Luffy Nika", "One Piece", "Non-scale", "mid", 100),
        ("Tsume Art", "HQS", "Zoro Ashura", "One Piece", "1/4", "grail", 880),
        ("Prime 1 Studio", "Premium Masterline", "Kaido Dragon Form", "One Piece", "1/4", "grail", 1500),

        # ── Fate - Additional ────────────────────────────────────────────
        ("Alter", "Scale", "Saber Excalibur Ver.", "Fate/Stay Night", "1/7", "high", 300),
        ("Good Smile Company", "Scale", "Ishtar", "Fate/Grand Order", "1/7", "high", 240),
        ("FREEing", "Scale", "Saber Bunny Ver.", "Fate/Stay Night", "1/4", "grail", 500),
        ("Alter", "Scale", "Scathach", "Fate/Grand Order", "1/7", "high", 270),
        ("Myethos", "Scale", "Ereshkigal", "Fate/Grand Order", "1/7", "high", 250),

        # ── Evangelion - Additional ──────────────────────────────────────
        ("Alter", "Scale", "Mari Illustrious Makinami Plugsuit", "Evangelion", "1/7", "high", 250),
        ("Kotobukiya", "Scale", "Asuka Langley Shikinami Test Type", "Evangelion", "1/7", "high", 230),
        ("FREEing", "Scale", "Rei Ayanami Bunny Ver.", "Evangelion", "1/4", "grail", 520),

        # ── Dragon Ball - Additional ─────────────────────────────────────
        ("Bandai", "S.H.Figuarts", "Perfect Cell", "Dragon Ball Z", "Non-scale", "mid", 90),
        ("Bandai", "S.H.Figuarts", "Gohan Beast", "Dragon Ball Super: Super Hero", "Non-scale", "mid", 95),
        ("Tsume Art", "HQS", "Majin Vegeta Final Explosion", "Dragon Ball Z", "1/6", "grail", 900),
        ("Prime 1 Studio", "Premium Masterline", "Goku vs Frieza Namek", "Dragon Ball Z", "1/4", "grail", 1300),

        # ── Naruto - Additional ──────────────────────────────────────────
        ("MegaHouse", "GEM", "Gaara Kazekage", "Naruto Shippuden", "1/8", "mid", 170),
        ("Kotobukiya", "Scale", "Hinata Hyuga", "Naruto Shippuden", "1/8", "mid", 160),
        ("Tsume Art", "HQS", "Itachi Uchiha Susanoo", "Naruto Shippuden", "1/6", "grail", 850),
        ("Good Smile Company", "Scale", "Jiraiya Sage Mode", "Naruto Shippuden", "1/8", "high", 210),

        # ── My Hero Academia - Additional ────────────────────────────────
        ("FREEing", "Scale", "Ochaco Uraraka Bunny Ver.", "My Hero Academia", "1/4", "grail", 440),
        ("Aniplex", "Scale", "Dabi Blue Flame", "My Hero Academia", "1/7", "high", 250),
        ("Good Smile Company", "Scale", "Shigaraki Tomura Awakened", "My Hero Academia", "1/7", "high", 240),

        # ── Re:Zero - Additional ─────────────────────────────────────────
        ("Kotobukiya", "Scale", "Beatrice", "Re:Zero", "1/7", "mid", 170),
        ("Kadokawa", "Scale", "Rem Crystal Dress", "Re:Zero", "1/7", "high", 260),
        ("eStream", "Scale", "Rem Oni Ver.", "Re:Zero", "1/7", "grail", 420),

        # ── Bleach - Additional ──────────────────────────────────────────
        ("MegaHouse", "GEM", "Toshiro Hitsugaya Bankai", "Bleach", "1/8", "mid", 175),
        ("Kotobukiya", "Scale", "Ulquiorra Cifer Segunda Etapa", "Bleach", "1/8", "high", 220),
        ("Good Smile Company", "Scale", "Byakuya Kuchiki Senbonzakura", "Bleach", "1/8", "high", 210),
        ("FREEing", "Scale", "Yoruichi Shihoin Bunny Ver.", "Bleach", "1/4", "grail", 460),

        # ── Gundam - Additional ──────────────────────────────────────────
        ("Bandai", "Metal Build", "Gundam Exia", "Gundam 00", "Non-scale", "high", 260),
        ("Bandai", "Metal Build", "Hi-Nu Gundam", "Char's Counterattack", "Non-scale", "high", 320),
        ("Bandai", "Robot Spirits", "Unicorn Gundam Destroy Mode", "Gundam Unicorn", "Non-scale", "mid", 100),
        ("Bandai", "Metal Build", "Freedom Gundam Concept 2", "Gundam SEED", "Non-scale", "high", 350),

        # ── Pop Up Parade (10) ───────────────────────────────────────────
        ("Good Smile Company", "Pop Up Parade", "Gojo Satoru Pop Up Parade", "Jujutsu Kaisen", "Non-scale", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Tanjiro Kamado Pop Up Parade", "Demon Slayer", "Non-scale", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Power Pop Up Parade", "Chainsaw Man", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Anya Forger Pop Up Parade", "Spy x Family", "Non-scale", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Frieren Pop Up Parade", "Frieren: Beyond Journey's End", "Non-scale", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Sung Jinwoo Pop Up Parade", "Solo Leveling", "Non-scale", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Ai Hoshino Pop Up Parade", "Oshi no Ko", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Marin Kitagawa Pop Up Parade", "My Dress-Up Darling", "Non-scale", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Rem Pop Up Parade", "Re:Zero", "Non-scale", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Nezuko Kamado Pop Up Parade", "Demon Slayer", "Non-scale", "standard", 30),

        # ── My Dress-Up Darling (4) ──────────────────────────────────────
        ("Good Smile Company", "Scale", "Marin Kitagawa Shizuku-tan Cosplay", "My Dress-Up Darling", "1/7", "high", 240),
        ("FREEing", "Scale", "Marin Kitagawa Bunny Ver.", "My Dress-Up Darling", "1/4", "grail", 500),
        ("Aniplex", "Scale", "Marin Kitagawa Swimsuit Ver.", "My Dress-Up Darling", "1/7", "high", 250),
        ("Good Smile Company", "Nendoroid", "Marin Kitagawa Nendoroid", "My Dress-Up Darling", "Nendoroid", "standard", 55),

        # ── DARLING in the FRANXX (3) ────────────────────────────────────
        ("Good Smile Company", "Scale", "Zero Two Pilot Suit", "DARLING in the FRANXX", "1/7", "high", 280),
        ("FREEing", "Scale", "Zero Two Bunny Ver.", "DARLING in the FRANXX", "1/4", "grail", 550),
        ("Kotobukiya", "Scale", "Ichigo", "DARLING in the FRANXX", "1/7", "mid", 170),

        # ── Myethos Premium Scales (5) ───────────────────────────────────
        ("Myethos", "Scale", "Hu Tao", "Genshin Impact", "1/7", "high", 260),
        ("Myethos", "Scale", "Ganyu", "Genshin Impact", "1/7", "high", 280),
        ("Myethos", "Scale", "Raiden Shogun", "Genshin Impact", "1/7", "high", 300),
        ("Myethos", "Scale", "Keqing", "Genshin Impact", "1/7", "high", 240),
        ("Myethos", "Scale", "Nahida", "Genshin Impact", "1/7", "high", 250),

        # ── eStream Premium (3) ──────────────────────────────────────────
        ("eStream", "Scale", "Miku Hanazono Concert Ver.", "The Quintessential Quintuplets", "1/7", "high", 280),
        ("eStream", "Scale", "Nino Nakano Shiromuku Ver.", "The Quintessential Quintuplets", "1/7", "high", 300),
        ("eStream", "Scale", "Mai Sakurajima Wedding Ver.", "Rascal Does Not Dream", "1/7", "grail", 400),

        # ── Additional Nendoroids Wave 3 (5) ─────────────────────────────
        ("Good Smile Company", "Nendoroid", "Kafka Hibino Nendoroid", "Kaiju No. 8", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Isagi Yoichi Nendoroid", "Blue Lock", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Yor Forger Nendoroid", "Spy x Family", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Nezuko Kamado Nendoroid", "Demon Slayer", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Violet Evergarden Nendoroid", "Violet Evergarden", "Nendoroid", "standard", 60),

        # ── B-style / FREEing Bunny Grails (5) ──────────────────────────
        ("FREEing", "Scale", "Mai Sakurajima Bunny Ver.", "Rascal Does Not Dream", "1/4", "grail", 550),
        ("FREEing", "Scale", "Megumin Bunny Ver.", "KonoSuba", "1/4", "grail", 480),
        ("FREEing", "Scale", "Emilia Bunny Ver.", "Re:Zero", "1/4", "grail", 500),
        ("FREEing", "Scale", "Nezuko Kamado Bunny Ver.", "Demon Slayer", "1/4", "grail", 510),
        ("FREEing", "Scale", "Shiro Bunny Ver.", "No Game No Life", "1/4", "grail", 530),

        # ── Additional Figma Wave 2 (5) ──────────────────────────────────
        ("Max Factory", "Figma", "Guts Band of the Hawk Figma", "Berserk", "Figma", "mid", 100),
        ("Max Factory", "Figma", "Asuna Figma", "Sword Art Online", "Figma", "standard", 70),
        ("Max Factory", "Figma", "Saber Alter Figma", "Fate/Stay Night", "Figma", "mid", 85),
        ("Max Factory", "Figma", "Hatsune Miku V4 Chinese Figma", "Vocaloid", "Figma", "mid", 90),
        ("Max Factory", "Figma", "Loid Forger Figma", "Spy x Family", "Figma", "standard", 70),

        # ── Additional Prize Figures Wave 2 (5) ─────────────────────────
        ("Banpresto", "Vibration Stars", "Sukuna", "Jujutsu Kaisen", "Non-scale", "standard", 25),
        ("Banpresto", "Grandista", "Ichigo Kurosaki TYBW", "Bleach", "Non-scale", "standard", 35),
        ("Banpresto", "DXF", "Boa Hancock", "One Piece", "Non-scale", "standard", 22),
        ("Banpresto", "Chronicle Master Stars", "Nami Wano", "One Piece", "Non-scale", "standard", 28),
        ("Banpresto", "Vibration Stars", "Nezuko Kamado Blood Demon Art", "Demon Slayer", "Non-scale", "standard", 24),

        # ── Pop Up Parade Wave 2 (15) ──────────────────────────────────
        ("Good Smile Company", "Pop Up Parade", "Denji Pop Up Parade", "Chainsaw Man", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Makima Pop Up Parade", "Chainsaw Man", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Levi Ackerman Pop Up Parade", "Attack on Titan", "Non-scale", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Goku Pop Up Parade", "Dragon Ball Z", "Non-scale", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Naruto Uzumaki Pop Up Parade", "Naruto Shippuden", "Non-scale", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Ichigo Kurosaki Pop Up Parade", "Bleach", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Luffy Pop Up Parade", "One Piece", "Non-scale", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Violet Evergarden Pop Up Parade", "Violet Evergarden", "Non-scale", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Mob Pop Up Parade", "Mob Psycho 100", "Non-scale", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Fern Pop Up Parade", "Frieren: Beyond Journey's End", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Yor Forger Pop Up Parade", "Spy x Family", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Bachira Meguru Pop Up Parade", "Blue Lock", "Non-scale", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Ruby Hoshino Pop Up Parade", "Oshi no Ko", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Gabimaru Pop Up Parade", "Hell's Paradise", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Asuna Pop Up Parade", "Sword Art Online", "Non-scale", "standard", 30),

        # ── Nendoroid Wave 4 — Complete Popular Series (15) ────────────
        ("Good Smile Company", "Nendoroid", "Fern Nendoroid", "Frieren: Beyond Journey's End", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Loid Forger Nendoroid", "Spy x Family", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Goku Ultra Instinct Nendoroid", "Dragon Ball Super", "Nendoroid", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Vegeta Nendoroid", "Dragon Ball Z", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Luffy Gear 5 Nendoroid", "One Piece", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Zoro Nendoroid", "One Piece", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Asuna Nendoroid", "Sword Art Online", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Rimuru Tempest Nendoroid", "That Time I Got Reincarnated as a Slime", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Hinata Shoyo Nendoroid", "Haikyuu!!", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Tobio Kageyama Nendoroid", "Haikyuu!!", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Tanjiro Final Selection Nendoroid", "Demon Slayer", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Itadori Yuji Nendoroid", "Jujutsu Kaisen", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Nobara Kugisaki Nendoroid", "Jujutsu Kaisen", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Sakura Haruno Nendoroid", "Naruto Shippuden", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Edward Elric Nendoroid", "Fullmetal Alchemist", "Nendoroid", "standard", 55),

        # ── Figma Wave 3 — Complete Key Lines (10) ─────────────────────
        ("Max Factory", "Figma", "Itadori Yuji Figma", "Jujutsu Kaisen", "Figma", "standard", 70),
        ("Max Factory", "Figma", "Nobara Kugisaki Figma", "Jujutsu Kaisen", "Figma", "standard", 75),
        ("Max Factory", "Figma", "Rem Figma", "Re:Zero", "Figma", "standard", 70),
        ("Max Factory", "Figma", "Emilia Figma", "Re:Zero", "Figma", "standard", 70),
        ("Max Factory", "Figma", "Ichigo Kurosaki Figma", "Bleach", "Figma", "standard", 75),
        ("Max Factory", "Figma", "Griffith Figma", "Berserk", "Figma", "mid", 90),
        ("Max Factory", "Figma", "Frieren Figma", "Frieren: Beyond Journey's End", "Figma", "standard", 75),
        ("Max Factory", "Figma", "Anya Forger Figma", "Spy x Family", "Figma", "standard", 65),
        ("Max Factory", "Figma", "Guts Black Swordsman Figma", "Berserk", "Figma", "mid", 100),
        ("Max Factory", "Figma", "Luffy Figma", "One Piece", "Figma", "standard", 70),

        # ── B-style FREEing Bunny Grails Wave 2 (10) ──────────────────
        ("FREEing", "Scale", "Yor Forger Bunny Ver. 2nd", "Spy x Family", "1/4", "grail", 480),
        ("FREEing", "Scale", "Chisato Nishikigi Bunny Ver.", "Lycoris Recoil", "1/4", "grail", 460),
        ("FREEing", "Scale", "Takina Inoue Bunny Ver.", "Lycoris Recoil", "1/4", "grail", 450),
        ("FREEing", "Scale", "Lucy Bunny Ver.", "Cyberpunk: Edgerunners", "1/4", "grail", 490),
        ("FREEing", "Scale", "Nobara Kugisaki Bunny Ver.", "Jujutsu Kaisen", "1/4", "grail", 470),
        ("FREEing", "Scale", "Makima Bunny Ver.", "Chainsaw Man", "1/4", "grail", 500),
        ("FREEing", "Scale", "Darkness Bunny Ver.", "KonoSuba", "1/4", "grail", 460),
        ("FREEing", "Scale", "Aqua Bunny Ver.", "KonoSuba", "1/4", "grail", 440),
        ("FREEing", "Scale", "Eris Boreas Bunny Ver.", "Mushoku Tensei", "1/4", "grail", 480),
        ("FREEing", "Scale", "Asuka Langley Bunny Ver.", "Evangelion", "1/4", "grail", 510),

        # ── Prize Figures — SEGA / Furyu / Taito (15) ──────────────────
        ("SEGA", "SPM", "Gojo Satoru SPM", "Jujutsu Kaisen", "Non-scale", "standard", 28),
        ("SEGA", "SPM", "Tanjiro Kamado SPM", "Demon Slayer", "Non-scale", "standard", 25),
        ("SEGA", "SPM", "Nezuko Kamado SPM", "Demon Slayer", "Non-scale", "standard", 25),
        ("SEGA", "SPM", "Power SPM", "Chainsaw Man", "Non-scale", "standard", 28),
        ("SEGA", "SPM", "Makima SPM", "Chainsaw Man", "Non-scale", "standard", 28),
        ("Furyu", "Trio-Try-iT", "Rem Trio-Try-iT", "Re:Zero", "Non-scale", "standard", 22),
        ("Furyu", "Trio-Try-iT", "Ram Trio-Try-iT", "Re:Zero", "Non-scale", "standard", 22),
        ("Furyu", "Trio-Try-iT", "Marin Kitagawa Trio-Try-iT", "My Dress-Up Darling", "Non-scale", "standard", 25),
        ("Taito", "Coreful", "Rem Coreful", "Re:Zero", "Non-scale", "standard", 22),
        ("Taito", "Coreful", "Ram Coreful", "Re:Zero", "Non-scale", "standard", 22),
        ("Taito", "Coreful", "Miku Coreful Cherry Blossom", "Vocaloid", "Non-scale", "standard", 25),
        ("Taito", "Coreful", "Emilia Coreful", "Re:Zero", "Non-scale", "standard", 22),
        ("Furyu", "BiCute Bunnies", "Miku BiCute Bunnies", "Vocaloid", "Non-scale", "standard", 28),
        ("SEGA", "Luminasta", "Frieren Luminasta", "Frieren: Beyond Journey's End", "Non-scale", "standard", 25),
        ("SEGA", "Luminasta", "Fern Luminasta", "Frieren: Beyond Journey's End", "Non-scale", "standard", 25),

        # ── Alter Premium Scales (8) ───────────────────────────────────
        ("Alter", "Scale", "Saber Alter Shinjuku", "Fate/Grand Order", "1/7", "high", 280),
        ("Alter", "Scale", "Jeanne d'Arc Alter", "Fate/Grand Order", "1/7", "high", 290),
        ("Alter", "Scale", "Nia", "Xenoblade Chronicles 2", "1/7", "high", 270),
        ("Alter", "Scale", "Pyra Homura", "Xenoblade Chronicles 2", "1/7", "high", 300),
        ("Alter", "Scale", "Mythra Hikari", "Xenoblade Chronicles 2", "1/7", "high", 300),
        ("Alter", "Scale", "Rem Wedding Ver.", "Re:Zero", "1/7", "high", 260),
        ("Alter", "Scale", "Megumin Winter Ver.", "KonoSuba", "1/7", "high", 240),
        ("Alter", "Scale", "2B YoRHa No.2 Type B", "NieR: Automata", "1/7", "high", 280),

        # ── Kotobukiya Bishoujo & More (8) ─────────────────────────────
        ("Kotobukiya", "Bishoujo", "Jill Valentine Bishoujo", "Resident Evil", "1/7", "mid", 150),
        ("Kotobukiya", "Bishoujo", "Lady Dimitrescu Bishoujo", "Resident Evil Village", "1/7", "mid", 160),
        ("Kotobukiya", "Bishoujo", "Black Widow Bishoujo", "Marvel", "1/7", "mid", 130),
        ("Kotobukiya", "Bishoujo", "Chun-Li Bishoujo", "Street Fighter", "1/7", "mid", 140),
        ("Kotobukiya", "Scale", "Mitsuri Kanroji Love Breathing", "Demon Slayer", "1/8", "high", 220),
        ("Kotobukiya", "Scale", "Obanai Iguro", "Demon Slayer", "1/8", "mid", 190),
        ("Kotobukiya", "Scale", "Muichiro Tokito", "Demon Slayer", "1/8", "mid", 180),
        ("Kotobukiya", "Scale", "Gyomei Himejima", "Demon Slayer", "1/8", "high", 210),

        # ── Bandai Spirits Ichiban Kuji / S.H.Figuarts (10) ───────────
        ("Bandai", "Ichiban Kuji", "Goku Ultra Instinct Ichiban Kuji", "Dragon Ball Super", "Non-scale", "mid", 80),
        ("Bandai", "Ichiban Kuji", "Luffy Gear 5 Nika Ichiban Kuji", "One Piece", "Non-scale", "mid", 90),
        ("Bandai", "Ichiban Kuji", "Gojo Satoru Ichiban Kuji", "Jujutsu Kaisen", "Non-scale", "mid", 85),
        ("Bandai", "S.H.Figuarts", "Tanjiro Kamado Hinokami", "Demon Slayer", "Non-scale", "mid", 85),
        ("Bandai", "S.H.Figuarts", "Rengoku Kyojuro Flame Hashira", "Demon Slayer", "Non-scale", "mid", 90),
        ("Bandai", "S.H.Figuarts", "Itadori Yuji", "Jujutsu Kaisen", "Non-scale", "mid", 80),
        ("Bandai", "S.H.Figuarts", "Vegito SSB", "Dragon Ball Super", "Non-scale", "mid", 95),
        ("Bandai", "S.H.Figuarts", "Gogeta SSB", "Dragon Ball Super: Broly", "Non-scale", "mid", 100),
        ("Bandai", "S.H.Figuarts", "Frieza First Form", "Dragon Ball Z", "Non-scale", "mid", 80),
        ("Bandai", "Metal Build", "Strike Gundam", "Gundam SEED", "Non-scale", "high", 250),

        # ── Myethos Genshin Impact Complete (5) ────────────────────────
        ("Myethos", "Scale", "Zhongli", "Genshin Impact", "1/7", "high", 270),
        ("Myethos", "Scale", "Yae Miko", "Genshin Impact", "1/7", "high", 260),
        ("Myethos", "Scale", "Furina", "Genshin Impact", "1/7", "high", 280),
        ("Myethos", "Scale", "Nilou", "Genshin Impact", "1/7", "high", 260),
        ("Myethos", "Scale", "Wanderer Scaramouche", "Genshin Impact", "1/7", "high", 250),

        # ── Phat! Company Scales (5) ───────────────────────────────────
        ("Phat!", "Scale", "Saber Triumphant Excalibur", "Fate/Stay Night", "1/7", "high", 220),
        ("Phat!", "Scale", "Miku Racing 2019", "Vocaloid", "1/7", "mid", 180),
        ("Phat!", "Scale", "Albedo Overlord", "Overlord", "1/7", "high", 240),
        ("Phat!", "Scale", "Shalltear Bloodfallen", "Overlord", "1/7", "high", 230),
        ("Phat!", "Scale", "Ainz Ooal Gown", "Overlord", "1/7", "high", 250),

        # ── Aquamarine / Flare Scales (5) ──────────────────────────────
        ("Aquamarine", "Scale", "Rem Sleeping Princess", "Re:Zero", "1/7", "mid", 180),
        ("Aquamarine", "Scale", "Megumin School Uniform", "KonoSuba", "1/7", "mid", 170),
        ("Flare", "Scale", "Rimuru Tempest Ultimate Form", "That Time I Got Reincarnated as a Slime", "1/7", "high", 220),
        ("Flare", "Scale", "Milim Nava", "That Time I Got Reincarnated as a Slime", "1/7", "mid", 190),
        ("Aquamarine", "Scale", "Aqua Goddess", "KonoSuba", "1/7", "mid", 160),

        # ── Union Creative / Native (5) ────────────────────────────────
        ("Union Creative", "Scale", "Makima Relax Ver.", "Chainsaw Man", "1/7", "high", 260),
        ("Union Creative", "Scale", "Power Casual Ver.", "Chainsaw Man", "1/7", "high", 240),
        ("Native", "Scale", "Albedo Swimsuit", "Overlord", "1/7", "high", 280),
        ("Native", "Scale", "Rem China Dress", "Re:Zero", "1/7", "high", 290),
        ("Union Creative", "Scale", "Gojo Satoru Standing Pose", "Jujutsu Kaisen", "1/7", "high", 250),

        # ── Orchid Seed / Wing (5) ─────────────────────────────────────
        ("Orchid Seed", "Scale", "Selvaria Bles", "Valkyria Chronicles", "1/7", "high", 280),
        ("Orchid Seed", "Scale", "Cattleya Queen's Blade", "Queen's Blade", "1/7", "mid", 200),
        ("Wing", "Scale", "Lum Urusei Yatsura", "Urusei Yatsura", "1/7", "mid", 190),
        ("Wing", "Scale", "C.C. Code Geass", "Code Geass", "1/7", "mid", 180),
        ("Orchid Seed", "Scale", "Airi Queen's Blade", "Queen's Blade", "1/7", "mid", 190),

        # ── Aniplex+ Premium Scales (5) ────────────────────────────────
        ("Aniplex", "Scale", "Nezuko Kamado BUZZmod.", "Demon Slayer", "1/7", "high", 230),
        ("Aniplex", "Scale", "Shinobu Kocho Insect Breathing", "Demon Slayer", "1/8", "high", 250),
        ("Aniplex", "Scale", "Mash Kyrielight Grand Order", "Fate/Grand Order", "1/7", "high", 240),
        ("Aniplex", "Scale", "Gilgamesh", "Fate/Grand Order", "1/7", "high", 260),
        ("Aniplex", "Scale", "Tamamo no Mae", "Fate/Grand Order", "1/7", "high", 250),

        # ── eStream / Shibuya Scramble (5) ─────────────────────────────
        ("eStream", "Scale", "Rem Neon City Ver.", "Re:Zero", "1/7", "grail", 400),
        ("eStream", "Scale", "Emilia Crystal Dress Ver.", "Re:Zero", "1/7", "grail", 420),
        ("eStream", "Scale", "Miku Hanazono Bride Ver.", "The Quintessential Quintuplets", "1/7", "high", 300),
        ("eStream", "Scale", "Nino Nakano Date Style", "The Quintessential Quintuplets", "1/7", "high", 280),
        ("eStream", "Scale", "Itsuki Nakano Wedding Ver.", "The Quintessential Quintuplets", "1/7", "high", 290),

        # ── Haikyuu!! Series (5) ───────────────────────────────────────
        ("Good Smile Company", "Scale", "Hinata Shoyo", "Haikyuu!!", "1/8", "mid", 170),
        ("Good Smile Company", "Scale", "Tobio Kageyama", "Haikyuu!!", "1/8", "mid", 170),
        ("Good Smile Company", "Scale", "Kei Tsukishima", "Haikyuu!!", "1/8", "mid", 160),
        ("Kotobukiya", "Scale", "Toru Oikawa", "Haikyuu!!", "1/8", "mid", 160),
        ("Kotobukiya", "Scale", "Kotaro Bokuto", "Haikyuu!!", "1/8", "mid", 165),

        # ── NieR Series (5) ────────────────────────────────────────────
        ("Good Smile Company", "Scale", "2B NieR Ver.", "NieR: Automata", "1/7", "high", 250),
        ("Flare", "Scale", "A2 YoRHa Type A No.2", "NieR: Automata", "1/7", "high", 240),
        ("Flare", "Scale", "9S YoRHa No.9 Type S", "NieR: Automata", "1/7", "mid", 190),
        ("Square Enix", "Bring Arts", "Kaine NieR Replicant", "NieR Replicant", "Non-scale", "mid", 120),
        ("Square Enix", "Bring Arts", "Nier Replicant Protagonist", "NieR Replicant", "Non-scale", "mid", 110),

        # ── Overlord Complete (4) ──────────────────────────────────────
        ("Good Smile Company", "Scale", "Ainz Ooal Gown Overlord", "Overlord", "1/7", "high", 280),
        ("FREEing", "Scale", "Albedo Bunny Ver.", "Overlord", "1/4", "grail", 520),
        ("FREEing", "Scale", "Shalltear Bunny Ver.", "Overlord", "1/4", "grail", 500),
        ("Good Smile Company", "Nendoroid", "Ainz Ooal Gown Nendoroid", "Overlord", "Nendoroid", "standard", 55),

        # ── No Game No Life (3) ────────────────────────────────────────
        ("Good Smile Company", "Scale", "Shiro", "No Game No Life", "1/7", "high", 240),
        ("Good Smile Company", "Scale", "Sora", "No Game No Life", "1/8", "mid", 180),
        ("Good Smile Company", "Nendoroid", "Shiro Nendoroid", "No Game No Life", "Nendoroid", "standard", 60),

        # ── Quintessential Quintuplets Complete (5) ────────────────────
        ("Good Smile Company", "Scale", "Yotsuba Nakano", "The Quintessential Quintuplets", "1/7", "mid", 180),
        ("Good Smile Company", "Scale", "Ichika Nakano", "The Quintessential Quintuplets", "1/7", "mid", 175),
        ("Good Smile Company", "Scale", "Itsuki Nakano", "The Quintessential Quintuplets", "1/7", "mid", 175),
        ("Kotobukiya", "Scale", "Miku Nakano", "The Quintessential Quintuplets", "1/7", "mid", 185),
        ("Kotobukiya", "Scale", "Nino Nakano", "The Quintessential Quintuplets", "1/7", "mid", 185),

        # ── Code Geass (3) ─────────────────────────────────────────────
        ("MegaHouse", "GEM", "Lelouch Zero", "Code Geass", "1/8", "mid", 180),
        ("Good Smile Company", "Scale", "C.C. Pilot Suit", "Code Geass", "1/7", "high", 220),
        ("FREEing", "Scale", "C.C. Bunny Ver.", "Code Geass", "1/4", "grail", 500),

        # ── Steins;Gate (3) ────────────────────────────────────────────
        ("Good Smile Company", "Scale", "Kurisu Makise Lab Coat", "Steins;Gate", "1/7", "mid", 180),
        ("Alter", "Scale", "Kurisu Makise Casual", "Steins;Gate", "1/7", "high", 220),
        ("Good Smile Company", "Nendoroid", "Mayuri Shiina Nendoroid", "Steins;Gate", "Nendoroid", "standard", 55),

        # ── Konosuba Complete (4) ──────────────────────────────────────
        ("Kadokawa", "Scale", "Aqua Goddess of Water", "KonoSuba", "1/7", "mid", 170),
        ("Good Smile Company", "Scale", "Wiz Crimson", "KonoSuba", "1/7", "mid", 180),
        ("Good Smile Company", "Scale", "Kazuma Sato", "KonoSuba", "1/8", "mid", 150),
        ("Good Smile Company", "Nendoroid", "Megumin Nendoroid", "KonoSuba", "Nendoroid", "standard", 55),

        # ── Shield Hero / Slime / Isekai (5) ──────────────────────────
        ("Kotobukiya", "Scale", "Raphtalia", "The Rising of the Shield Hero", "1/7", "mid", 180),
        ("Kotobukiya", "Scale", "Naofumi Iwatani", "The Rising of the Shield Hero", "1/7", "mid", 170),
        ("Good Smile Company", "Scale", "Rimuru Tempest Human Form", "That Time I Got Reincarnated as a Slime", "1/7", "mid", 170),
        ("Alter", "Scale", "Milim Nava Demon Lord", "That Time I Got Reincarnated as a Slime", "1/7", "high", 230),
        ("FREEing", "Scale", "Raphtalia Bunny Ver.", "The Rising of the Shield Hero", "1/4", "grail", 460),

        # ── Urusei Yatsura / Classic Anime (3) ─────────────────────────
        ("Good Smile Company", "Scale", "Lum Urusei Yatsura New", "Urusei Yatsura", "1/7", "mid", 180),
        ("Max Factory", "Figma", "Lum Figma", "Urusei Yatsura", "Figma", "standard", 70),
        ("Good Smile Company", "Nendoroid", "Lum Nendoroid", "Urusei Yatsura", "Nendoroid", "standard", 50),

        # ── Banpresto Prize — Demon Slayer Complete Hashira (7) ────────
        ("Banpresto", "Vibration Stars", "Giyu Tomioka", "Demon Slayer", "Non-scale", "standard", 24),
        ("Banpresto", "Vibration Stars", "Rengoku Kyojuro", "Demon Slayer", "Non-scale", "standard", 25),
        ("Banpresto", "Vibration Stars", "Tengen Uzui", "Demon Slayer", "Non-scale", "standard", 24),
        ("Banpresto", "Vibration Stars", "Mitsuri Kanroji", "Demon Slayer", "Non-scale", "standard", 22),
        ("Banpresto", "Vibration Stars", "Muichiro Tokito", "Demon Slayer", "Non-scale", "standard", 22),
        ("Banpresto", "Vibration Stars", "Shinobu Kocho", "Demon Slayer", "Non-scale", "standard", 24),
        ("Banpresto", "Vibration Stars", "Obanai Iguro", "Demon Slayer", "Non-scale", "standard", 22),

        # ── Tsume Art / Prime 1 Studio Additional Grails (5) ──────────
        ("Tsume Art", "HQS", "Gojo Satoru Hollow Purple", "Jujutsu Kaisen", "1/6", "grail", 950),
        ("Prime 1 Studio", "Premium Masterline", "Muzan Kibutsuji", "Demon Slayer", "1/4", "grail", 1300),
        ("Tsume Art", "HQS", "Madara Uchiha", "Naruto Shippuden", "1/6", "grail", 880),
        ("Prime 1 Studio", "Premium Masterline", "Denji vs Katana Man", "Chainsaw Man", "1/4", "grail", 1200),
        ("Tsume Art", "HQS", "Vegeta Final Flash", "Dragon Ball Z", "1/6", "grail", 920),

        # ── Megahouse Portrait of Pirates Complete (5) ─────────────────
        ("MegaHouse", "Portrait of Pirates", "Sanji Whole Cake Island", "One Piece", "1/8", "high", 250),
        ("MegaHouse", "Portrait of Pirates", "Robin Ver.BB", "One Piece", "1/8", "high", 330),
        ("MegaHouse", "Portrait of Pirates", "Trafalgar Law", "One Piece", "1/8", "mid", 200),
        ("MegaHouse", "Portrait of Pirates", "Kaido of the Beasts", "One Piece", "1/8", "high", 350),
        ("MegaHouse", "Portrait of Pirates", "Jinbe", "One Piece", "1/8", "mid", 190),

        # ── Bandai Robot Spirits / Metal Build — Gundam Complete (6) ──
        ("Bandai", "Metal Build", "Destiny Gundam", "Gundam SEED Destiny", "Non-scale", "high", 300),
        ("Bandai", "Metal Build", "00 Raiser", "Gundam 00", "Non-scale", "high", 280),
        ("Bandai", "Metal Build", "Crossbone Gundam X1", "Crossbone Gundam", "Non-scale", "high", 290),
        ("Bandai", "Robot Spirits", "Zaku II ver. A.N.I.M.E.", "Mobile Suit Gundam", "Non-scale", "mid", 75),
        ("Bandai", "Robot Spirits", "Gouf Custom ver. A.N.I.M.E.", "Gundam 08th MS Team", "Non-scale", "mid", 80),
        ("Bandai", "Robot Spirits", "Sazabi ver. A.N.I.M.E.", "Char's Counterattack", "Non-scale", "mid", 100),

        # =================================================================
        # Batch 11 — ALTER, WAVE Dream Tech, Kotobukiya ARTFX J,
        # Myethos, Union Creative, Phat!, eStream
        # =================================================================

        # ── ALTER Figures (8) ───────────────────────────────────────────
        ("Alter", "Scale", "Saber Alter (Shinjuku Ver.)", "Fate/Grand Order", "1/7", "high", 280),
        ("Alter", "Scale", "Mash Kyrielight (Ortinax Ver.)", "Fate/Grand Order", "1/7", "high", 260),
        ("Alter", "Scale", "Jeanne d'Arc (Alter)", "Fate/Grand Order", "1/7", "high", 300),
        ("Alter", "Scale", "Scathach (Assassin Ver.)", "Fate/Grand Order", "1/7", "high", 270),
        ("Alter", "Scale", "Rider/Altria Pendragon (Alter)", "Fate/Grand Order", "1/7", "grail", 420),
        ("Alter", "Scale", "Asuna Yuuki (Aincrad Ver.)", "Sword Art Online", "1/7", "high", 240),
        ("Alter", "Scale", "Shiki Ryougi (Kimono Ver.)", "Kara no Kyoukai", "1/7", "grail", 450),
        ("Alter", "Scale", "Saber Lily (Golden Caliburn)", "Fate/Unlimited Codes", "1/7", "high", 230),

        # ── WAVE Dream Tech Series (6) ─────────────────────────────────
        ("WAVE", "Dream Tech", "Rem (Sleeping Ver.)", "Re:Zero", "1/7", "mid", 130),
        ("WAVE", "Dream Tech", "Ram (Sleeping Ver.)", "Re:Zero", "1/7", "mid", 125),
        ("WAVE", "Dream Tech", "Emilia (Teacher Ver.)", "Re:Zero", "1/7", "mid", 140),
        ("WAVE", "Dream Tech", "Megumin (Swimsuit Ver.)", "KonoSuba", "1/7", "mid", 120),
        ("WAVE", "Dream Tech", "Raphtalia (Childhood Ver.)", "Shield Hero", "1/7", "mid", 135),
        ("WAVE", "Dream Tech", "Shiro (Loungewear Ver.)", "No Game No Life", "1/7", "mid", 125),

        # ── Kotobukiya ARTFX J (8) ─────────────────────────────────────
        ("Kotobukiya", "ARTFX J", "Izuku Midoriya (Smash Ver.)", "My Hero Academia", "1/8", "high", 210),
        ("Kotobukiya", "ARTFX J", "Katsuki Bakugo (Explosion Ver.)", "My Hero Academia", "1/8", "high", 220),
        ("Kotobukiya", "ARTFX J", "Shoto Todoroki (Hero Costume Ver.)", "My Hero Academia", "1/8", "mid", 190),
        ("Kotobukiya", "ARTFX J", "Tanjiro Kamado (Water Breathing)", "Demon Slayer", "1/8", "high", 200),
        ("Kotobukiya", "ARTFX J", "Kyojuro Rengoku (Flame Breathing)", "Demon Slayer", "1/8", "high", 230),
        ("Kotobukiya", "ARTFX J", "Muichiro Tokito (Mist Breathing)", "Demon Slayer", "1/8", "mid", 180),
        ("Kotobukiya", "ARTFX J", "Levi Ackerman (Vertical Maneuvering)", "Attack on Titan", "1/8", "high", 280),
        ("Kotobukiya", "ARTFX J", "Mikasa Ackerman (3DMG Ver.)", "Attack on Titan", "1/8", "high", 250),

        # ── Myethos Figures (7) ────────────────────────────────────────
        ("Myethos", "Fairytale", "Little Mermaid", "FairyTale-Another", "1/8", "high", 240),
        ("Myethos", "Fairytale", "Snow White", "FairyTale-Another", "1/8", "high", 230),
        ("Myethos", "Fairytale", "Alice in Wonderland", "FairyTale-Another", "1/8", "high", 250),
        ("Myethos", "Fairytale", "Sleeping Beauty", "FairyTale-Another", "1/8", "high", 220),
        ("Myethos", "Scale", "Yun Jin (Genshin Impact)", "Honor of Kings", "1/7", "high", 260),
        ("Myethos", "Scale", "Ganyu (Plenilune Gaze)", "Genshin Impact", "1/7", "high", 280),
        ("Myethos", "Scale", "Hu Tao (Fragrance in Thaw)", "Genshin Impact", "1/7", "grail", 420),

        # ── Union Creative Figures (7) ─────────────────────────────────
        ("Union Creative", "Scale", "Joker/Ren Amamiya (Phantom Thief Ver.)", "Persona 5", "1/7", "high", 250),
        ("Union Creative", "Scale", "Makoto Niijima (Queen)", "Persona 5", "1/7", "high", 240),
        ("Union Creative", "Scale", "Ann Takamaki (Panther)", "Persona 5", "1/7", "high", 260),
        ("Union Creative", "Scale", "Momo Belia Deviluke (Darkness Ver.)", "To Love-Ru", "1/6", "high", 300),
        ("Union Creative", "Scale", "Lala Satalin Deviluke (Wedding Ver.)", "To Love-Ru", "1/7", "high", 280),
        ("Union Creative", "Scale", "2B (YoRHa No.2 Type B)", "NieR: Automata", "1/7", "high", 290),
        ("Union Creative", "Scale", "A2 (YoRHa Type A No.2)", "NieR: Automata", "1/7", "high", 270),

        # ── Phat! Company Figures (7) ──────────────────────────────────
        ("Phat! Company", "Scale", "Rem (Crystal Dress Ver.)", "Re:Zero", "1/7", "grail", 480),
        ("Phat! Company", "Scale", "Ram (Crystal Dress Ver.)", "Re:Zero", "1/7", "grail", 460),
        ("Phat! Company", "Scale", "Emilia (Crystal Dress Ver.)", "Re:Zero", "1/7", "grail", 500),
        ("Phat! Company", "Scale", "Aqua (Sneeze Ver.)", "KonoSuba", "1/7", "mid", 160),
        ("Phat! Company", "Scale", "Darkness (Lalatina)", "KonoSuba", "1/7", "mid", 170),
        ("Phat! Company", "Scale", "Megumin (Explosion Ver.)", "KonoSuba", "1/7", "mid", 180),
        ("Phat! Company", "Scale", "Chika Fujiwara (Secretary Ver.)", "Kaguya-sama", "1/7", "mid", 150),

        # ── eStream Crystal Dress & Premium (7) ───────────────────────
        ("eStream", "Crystal Dress", "Rem (Crystal Dress)", "Re:Zero", "1/7", "grail", 520),
        ("eStream", "Crystal Dress", "Emilia (Crystal Dress)", "Re:Zero", "1/7", "grail", 550),
        ("eStream", "Crystal Dress", "Ram (Crystal Dress)", "Re:Zero", "1/7", "grail", 490),
        ("eStream", "Crystal Dress", "Rem (Oni Ver. Crystal Dress)", "Re:Zero", "1/7", "grail", 580),
        ("eStream", "Shibuya Scramble", "Rem (Idol Ver.)", "Re:Zero", "1/7", "high", 350),
        ("eStream", "Shibuya Scramble", "Emilia (Natsuki Subaru's Birthday)", "Re:Zero", "1/7", "high", 380),
        ("eStream", "Shibuya Scramble", "Megumin (Explosion Ver. Deluxe)", "KonoSuba", "1/7", "grail", 420),
    ]

    catalog = []
    for manufacturer, figure_type, character, series, scale, tier, price in figures:
        catalog.append({
            "manufacturer": manufacturer,
            "figure_type": figure_type,
            "character": character,
            "series": series,
            "scale": scale,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    manufacturer = item["manufacturer"]
    character = item["character"]
    series = item["series"]
    figure_type = item["figure_type"]
    scale = item["scale"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{manufacturer}-{character}-{scale}"),
        title=character,
        set_code=slugify(series),
        brand=manufacturer,
        rarity=item["rarity_tier"].title(),
        notes=f"{manufacturer} | {series} | {figure_type} | {scale}",
        attributes_json={
            "manufacturer": manufacturer,
            "figure_type": figure_type,
            "series": series,
            "scale": scale,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    figure_type = item["figure_type"]
    edition_scores = {
        "Scale": 0.7,
        "Portrait of Pirates": 0.8,
        "Nendoroid": 0.4,
        "Figma": 0.5,
        "Grandista": 0.2,
        "Vibration Stars": 0.15,
        "Chronicle Master Stars": 0.25,
        "DXF": 0.15,
        "King of Artist": 0.2,
        "RAH": 0.8,
        "Garage Kit": 0.9,
        "HQS": 0.95,
        "HQS+": 0.97,
        "S.H.Figuarts": 0.6,
        "Robot Spirits": 0.55,
        "Metal Build": 0.75,
        "GEM": 0.7,
        "Dimension of DRAGONBALL": 0.65,
        "Premium Masterline": 0.98,
        "Super Action Statue": 0.6,
        "Pop Up Parade": 0.2,
        "Ichiban Kuji": 0.4,
        "Bishoujo": 0.6,
        "SPM": 0.2,
        "Trio-Try-iT": 0.15,
        "Coreful": 0.15,
        "BiCute Bunnies": 0.2,
        "Luminasta": 0.2,
        "Bring Arts": 0.6,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(figure_type, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Anime Figures catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Anime Figures Import ===")

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

    logger.info(f"\n=== Anime Figures Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
