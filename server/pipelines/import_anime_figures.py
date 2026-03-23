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


def _variant_expansion(catalog: list[dict]) -> list[dict]:
    """Generate scale, manufacturer, and limited edition variants for anime figures.

    Adds 1/4 vs 1/7 vs 1/8 scale variants, different manufacturer versions
    of the same character, and limited painted/exclusive editions.
    """
    expanded: list[dict] = list(catalog)

    variant_figures = [
        # ─── Scale variants (same character, different scales) ─────────────
        ("Good Smile Company", "Scale", "Tanjiro Kamado 1/7 Ver.", "Demon Slayer", "1/7", "high", 220),
        ("FREEing", "B-style", "Nezuko Kamado Bunny Ver.", "Demon Slayer", "1/4", "grail", 420),
        ("Kotobukiya", "Scale", "Gojo Satoru 1/8 Ver.", "Jujutsu Kaisen", "1/8", "mid", 170),
        ("Alter", "Scale", "Rem 1/7 Ver.", "Re:Zero", "1/7", "high", 260),
        ("FREEing", "B-style", "Rem Bunny Ver. 2nd", "Re:Zero", "1/4", "grail", 500),
        # ─── Manufacturer variants (different makers, same character) ──────
        ("Alter", "Scale", "Gojo Satoru Alter Ver.", "Jujutsu Kaisen", "1/7", "grail", 400),
        ("Kotobukiya", "Scale", "Zero Two Kotobukiya Ver.", "DARLING in the FRANXX", "1/7", "high", 240),
        ("Max Factory", "Scale", "Miku Max Factory Racing Ver.", "Vocaloid", "1/7", "high", 280),
        ("eStream", "Scale", "Rem eStream Crystal Dress", "Re:Zero", "1/7", "grail", 550),
        ("Myethos", "Scale", "Miku Myethos Shaohua Ver.", "Vocaloid", "1/7", "grail", 480),
        # ─── Limited/painted editions ──────────────────────────────────────
        ("Good Smile Company", "Scale", "Miku 15th Anniversary Ltd.", "Vocaloid", "1/8", "grail", 600),
        ("Prime 1 Studio", "Premium", "Guts Berserker Armor Bloody", "Berserk", "1/4", "grail", 1200),
        ("Aniplex", "Scale", "Shinobu Kocho Limited Color", "Demon Slayer", "1/8", "grail", 380),
    ]

    for manufacturer, figure_type, character, series, scale, tier, price in variant_figures:
        expanded.append({
            "manufacturer": manufacturer,
            "figure_type": figure_type,
            "character": character,
            "series": series,
            "scale": scale,
            "rarity_tier": tier,
            "price_eur": price,
        })

    return expanded


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

        # ── Chainsaw Man - Expansion ─────────────────────────────────────
        ("Good Smile Company", "Scale", "Yoshida Hirofumi", "Chainsaw Man", "1/7", "mid", 180),
        ("Kotobukiya", "Scale", "Kobeni Higashiyama", "Chainsaw Man", "1/7", "mid", 170),
        ("Alter", "Scale", "Himeno Cigarette Ver.", "Chainsaw Man", "1/7", "high", 240),
        ("Aniplex", "Scale", "Darkness Devil", "Chainsaw Man", "1/7", "grail", 420),
        ("Good Smile Company", "Scale", "Angel Devil", "Chainsaw Man", "1/7", "mid", 190),
        ("MegaHouse", "Scale", "Katana Man Unmasked", "Chainsaw Man", "1/8", "mid", 175),
        ("eStream", "Scale", "Makima Office Suit Ver.", "Chainsaw Man", "1/7", "high", 320),
        ("Myethos", "Scale", "Reze Casual Ver.", "Chainsaw Man", "1/7", "high", 250),
        ("FREEing", "Scale", "Kobeni Bunny Ver.", "Chainsaw Man", "1/4", "grail", 470),
        ("Banpresto", "Vibration Stars", "Aki Hayakawa Rev.", "Chainsaw Man", "Non-scale", "standard", 24),

        # ── Spy x Family - Expansion ─────────────────────────────────────
        ("Alter", "Scale", "Yor Forger Casual Dress Ver.", "Spy x Family", "1/7", "high", 250),
        ("Kotobukiya", "Scale", "Anya Forger Winter Uniform", "Spy x Family", "1/7", "mid", 160),
        ("Good Smile Company", "Scale", "Bond Forger Oversized", "Spy x Family", "Non-scale", "mid", 100),
        ("MegaHouse", "Scale", "Yor Forger Thorn Princess Battle", "Spy x Family", "1/8", "high", 230),
        ("FREEing", "Scale", "Anya Forger Bunny Ver.", "Spy x Family", "1/4", "grail", 420),
        ("Aniplex", "Scale", "Loid & Anya Forger Family Portrait", "Spy x Family", "1/7", "high", 300),
        ("Banpresto", "Vibration Stars", "Yor Forger Action Ver.", "Spy x Family", "Non-scale", "standard", 28),
        ("SEGA", "Luminasta", "Anya Forger Penguin Costume", "Spy x Family", "Non-scale", "standard", 25),

        # ── Jujutsu Kaisen - Expansion ───────────────────────────────────
        ("Alter", "Scale", "Ryomen Sukuna True Form", "Jujutsu Kaisen", "1/7", "grail", 450),
        ("Good Smile Company", "Scale", "Toji Fushiguro", "Jujutsu Kaisen", "1/7", "high", 250),
        ("Aniplex", "Scale", "Nobara Kugisaki", "Jujutsu Kaisen", "1/7", "mid", 190),
        ("Kotobukiya", "Scale", "Maki Zenin", "Jujutsu Kaisen", "1/7", "mid", 180),
        ("MegaHouse", "Scale", "Choso", "Jujutsu Kaisen", "1/8", "mid", 175),
        ("eStream", "Scale", "Gojo Satoru Domain Expansion", "Jujutsu Kaisen", "1/7", "grail", 520),
        ("Banpresto", "King of Artist", "Toji Fushiguro KoA", "Jujutsu Kaisen", "Non-scale", "standard", 35),

        # ── My Hero Academia - Expansion ─────────────────────────────────
        ("Alter", "Scale", "Endeavor Hellflame", "My Hero Academia", "1/7", "high", 280),
        ("Good Smile Company", "Scale", "Hawks Wing Spread", "My Hero Academia", "1/7", "high", 260),
        ("Aniplex", "Scale", "Toga Himiko Unmasked", "My Hero Academia", "1/7", "high", 230),
        ("Kotobukiya", "ARTFX J", "Eraserhead (Aizawa Shota)", "My Hero Academia", "1/8", "high", 210),
        ("FREEing", "Scale", "Momo Yaoyorozu Bunny Ver.", "My Hero Academia", "1/4", "grail", 450),
        ("MegaHouse", "Scale", "Mirko Rumi Usagiyama", "My Hero Academia", "1/8", "high", 240),
        ("Banpresto", "Grandista", "All Might Grandista", "My Hero Academia", "Non-scale", "standard", 40),

        # ── Bocchi the Rock! - Expansion ─────────────────────────────────
        ("Good Smile Company", "Scale", "Kita Ikuyo Singing Ver.", "Bocchi the Rock!", "1/7", "mid", 175),
        ("Kotobukiya", "Scale", "Ryo Yamada Bass Ver.", "Bocchi the Rock!", "1/7", "mid", 170),
        ("Alter", "Scale", "Bocchi Hitori Stage Fright Ver.", "Bocchi the Rock!", "1/7", "high", 220),
        ("Good Smile Company", "Pop Up Parade", "Kita Ikuyo Pop Up Parade", "Bocchi the Rock!", "Non-scale", "standard", 32),
        ("Good Smile Company", "Nendoroid", "Ryo Yamada Nendoroid", "Bocchi the Rock!", "Nendoroid", "standard", 50),

        # ── Frieren - Expansion ──────────────────────────────────────────
        ("Alter", "Scale", "Frieren Seated Magic Ver.", "Frieren: Beyond Journey's End", "1/7", "high", 270),
        ("Kotobukiya", "Scale", "Stark Battle Ready", "Frieren: Beyond Journey's End", "1/8", "mid", 175),
        ("Good Smile Company", "Scale", "Sein the Priest", "Frieren: Beyond Journey's End", "1/8", "mid", 160),
        ("MegaHouse", "Scale", "Himmel the Hero Sword Draw", "Frieren: Beyond Journey's End", "1/8", "mid", 170),
        ("Good Smile Company", "Nendoroid", "Stark Nendoroid", "Frieren: Beyond Journey's End", "Nendoroid", "standard", 50),

        # ── Oshi no Ko - Expansion ───────────────────────────────────────
        ("Good Smile Company", "Scale", "Ai Hoshino Star Costume", "Oshi no Ko", "1/7", "high", 260),
        ("Alter", "Scale", "Akane Kurokawa Stage Ver.", "Oshi no Ko", "1/7", "mid", 190),
        ("Kotobukiya", "Scale", "Ruby Hoshino Idol Costume", "Oshi no Ko", "1/7", "mid", 185),
        ("FREEing", "Scale", "Ruby Hoshino Bunny Ver.", "Oshi no Ko", "1/4", "grail", 470),
        ("Good Smile Company", "Nendoroid", "Aqua Hoshino Nendoroid", "Oshi no Ko", "Nendoroid", "standard", 55),
        ("MegaHouse", "Scale", "MEM-cho Swimsuit Ver.", "Oshi no Ko", "1/7", "mid", 175),
        ("Good Smile Company", "Pop Up Parade", "Kana Arima Pop Up Parade", "Oshi no Ko", "Non-scale", "standard", 32),

        # ── Frieren - Additional Figures (Round 5) ─────────────────────
        ("Good Smile Company", "Scale", "Frieren Casting Zoltraak", "Frieren: Beyond Journey's End", "1/7", "high", 260),
        ("Alter", "Scale", "Fern Staff Combat Ver.", "Frieren: Beyond Journey's End", "1/7", "high", 240),
        ("Kotobukiya", "ARTFX", "Himmel Legendary Hero Pose", "Frieren: Beyond Journey's End", "1/8", "mid", 180),
        ("FREEing", "Scale", "Frieren Bunny Ver.", "Frieren: Beyond Journey's End", "1/4", "grail", 490),
        ("Bandai", "S.H.Figuarts", "Frieren Action Figure", "Frieren: Beyond Journey's End", "Non-scale", "mid", 90),
        ("Banpresto", "Grandista", "Stark Grandista Figure", "Frieren: Beyond Journey's End", "Non-scale", "standard", 38),

        # ── Chainsaw Man - Additional Figures (Round 5) ────────────────
        ("Alter", "Scale", "Makima Control Devil Form", "Chainsaw Man", "1/7", "high", 290),
        ("MegaHouse", "GEM", "Reze Bomb Devil", "Chainsaw Man", "1/8", "high", 220),
        ("Good Smile Company", "Scale", "Aki Hayakawa Fox Devil", "Chainsaw Man", "1/7", "high", 240),
        ("Kotobukiya", "ARTFX", "Pochita Nendoroid Giant", "Chainsaw Man", "Non-scale", "mid", 95),
        ("eStream", "Scale", "Power Blood Fiend Transformation", "Chainsaw Man", "1/7", "grail", 500),
        ("Banpresto", "Vibration Stars", "Denji Vibration Stars", "Chainsaw Man", "Non-scale", "standard", 28),
        ("Good Smile Company", "Scale", "War Devil Yoru", "Chainsaw Man", "1/7", "high", 250),

        # ── Blue Lock - Figures (Round 5) ──────────────────────────────
        ("Good Smile Company", "Scale", "Isagi Yoichi Shooting Ver.", "Blue Lock", "1/7", "high", 220),
        ("Kotobukiya", "Scale", "Bachira Meguru Dribble Ver.", "Blue Lock", "1/8", "mid", 180),
        ("Alter", "Scale", "Rin Itoshi Goal Celebration", "Blue Lock", "1/7", "high", 250),
        ("MegaHouse", "Scale", "Nagi Seishiro Trap Ver.", "Blue Lock", "1/8", "mid", 190),
        ("Good Smile Company", "Scale", "Kaiser Michael Ego Ver.", "Blue Lock", "1/7", "high", 260),
        ("Banpresto", "DXF", "Isagi Yoichi DXF Figure", "Blue Lock", "Non-scale", "standard", 30),
        ("Good Smile Company", "Nendoroid", "Bachira Meguru Nendoroid", "Blue Lock", "Nendoroid", "standard", 52),
        ("Good Smile Company", "Pop Up Parade", "Chigiri Hyoma Pop Up Parade", "Blue Lock", "Non-scale", "standard", 35),
        ("FREEing", "Scale", "Rin Itoshi Bunny Ver.", "Blue Lock", "1/4", "grail", 460),
        ("Kotobukiya", "ARTFX", "Nagi & Reo Dual Set", "Blue Lock", "1/8", "high", 320),

        # ── Bocchi the Rock! - Additional Figures (Round 5) ────────────
        ("Alter", "Scale", "Nijika Ijichi Drumming Ver.", "Bocchi the Rock!", "1/7", "high", 230),
        ("FREEing", "Scale", "Kita Ikuyo Bunny Ver.", "Bocchi the Rock!", "1/4", "grail", 450),
        ("MegaHouse", "Scale", "Bocchi Hitori Guitar Solo", "Bocchi the Rock!", "1/8", "mid", 170),
        ("Good Smile Company", "Nendoroid", "Nijika Ijichi Nendoroid", "Bocchi the Rock!", "Nendoroid", "standard", 50),
        ("Kotobukiya", "Scale", "PA-san (Seika Ijichi)", "Bocchi the Rock!", "1/7", "mid", 165),

        # ── Oshi no Ko - Additional Figures (Round 5) ──────────────────
        ("Alter", "Scale", "Ai Hoshino Dome Tour Finale", "Oshi no Ko", "1/7", "grail", 420),
        ("Kotobukiya", "ARTFX", "Aqua Hoshino Dark Star Ver.", "Oshi no Ko", "1/8", "high", 200),
        ("Good Smile Company", "Scale", "Akane Kurokawa 'Ai' Cosplay", "Oshi no Ko", "1/7", "high", 230),
        ("eStream", "Scale", "Ruby Hoshino Stage Performance", "Oshi no Ko", "1/7", "high", 280),

        # ── Alter Premium Scales (Round 5) ─────────────────────────────
        ("Alter", "Scale", "Tohka Yatogami Astral Dress", "Date A Live", "1/7", "high", 280),
        ("Alter", "Scale", "Megumin Explosion Magic", "KonoSuba", "1/7", "high", 290),
        ("Alter", "Scale", "Rimuru Tempest Ultimate Form", "That Time I Got Reincarnated as a Slime", "1/7", "high", 270),
        ("Alter", "Scale", "Violet Evergarden Auto Memory Doll", "Violet Evergarden", "1/7", "high", 310),
        ("Alter", "Scale", "Saber Artoria Avalon Ver.", "Fate/Grand Order", "1/7", "grail", 450),

        # ── Good Smile Company 1/7 Scales (Round 5) ───────────────────
        ("Good Smile Company", "Scale", "Shoko Ieiri White Coat", "Jujutsu Kaisen", "1/7", "mid", 195),
        ("Good Smile Company", "Scale", "Marin Kitagawa Cosplay Ver. 2", "My Dress-Up Darling", "1/7", "high", 250),
        ("Good Smile Company", "Scale", "Power Chainsaw Man (Alternate)", "Chainsaw Man", "1/7", "high", 235),
        ("Good Smile Company", "Scale", "Raphtalia Light Novel Ver.", "The Rising of the Shield Hero", "1/7", "mid", 190),
        ("Good Smile Company", "Scale", "Emilia Crystal Dress Ver.", "Re:Zero", "1/7", "high", 280),

        # ── Kotobukiya ARTFX (Round 5) ─────────────────────────────────
        ("Kotobukiya", "ARTFX", "Tanjiro Kamado Water Breathing", "Demon Slayer", "1/8", "high", 200),
        ("Kotobukiya", "ARTFX", "Zenitsu Agatsuma Thunder Breathing", "Demon Slayer", "1/8", "mid", 180),
        ("Kotobukiya", "ARTFX", "Inosuke Hashibira Beast Breathing", "Demon Slayer", "1/8", "mid", 175),
        ("Kotobukiya", "ARTFX", "Muichiro Tokito Mist Breathing", "Demon Slayer", "1/8", "mid", 185),
        ("Kotobukiya", "ARTFX", "Giyu Tomioka Water Breathing", "Demon Slayer", "1/8", "high", 210),

        # ── Bandai Tamashii Nations (Round 5) ──────────────────────────
        ("Bandai", "S.H.Figuarts", "Goku Ultra Instinct Sign", "Dragon Ball Super", "Non-scale", "mid", 100),
        ("Bandai", "S.H.Figuarts", "Luffy Gear 5 Nika", "One Piece", "Non-scale", "high", 130),
        ("Bandai", "Metal Build", "Gundam Aerial Full Armor", "Gundam: Witch from Mercury", "Non-scale", "high", 350),
        ("Bandai", "Robot Spirits", "Eva Unit-02 Production Model", "Evangelion", "Non-scale", "mid", 110),
        ("Bandai", "S.H.Figuarts", "Naruto Uzumaki Baryon Mode", "Naruto Shippuden", "Non-scale", "mid", 95),

        # ── MegaHouse G.E.M. Series (Round 5) ─────────────────────────
        ("MegaHouse", "GEM", "Ichigo Kurosaki Final Getsuga", "Bleach", "1/8", "high", 280),
        ("MegaHouse", "GEM", "Trunks Super Saiyan Sword", "Dragon Ball Z", "1/8", "mid", 180),
        ("MegaHouse", "GEM", "Kakashi Hatake Anbu Ver.", "Naruto Shippuden", "1/8", "high", 240),
        ("MegaHouse", "GEM", "Levi Ackerman Cleaning Ver.", "Attack on Titan", "1/8", "mid", 200),
        ("MegaHouse", "Portrait of Pirates", "Nico Robin Wano Ver.", "One Piece", "1/8", "high", 300),
        ("MegaHouse", "GEM", "Gojo Satoru Hollow Purple", "Jujutsu Kaisen", "1/8", "high", 320),

        # === EXPANSION ROUND 6 — 31 new items to reach 700+ ===

        # ── Alter — Premium 2025/2026 Releases (+6) ─────────────────────
        ("Alter", "Scale", "Makima Barefoot Ver.", "Chainsaw Man", "1/7", "high", 310),
        ("Alter", "Scale", "Yor Forger Thorn Princess Night Mission", "Spy x Family", "1/7", "high", 290),
        ("Alter", "Scale", "Frieren Flower Field Ver.", "Frieren: Beyond Journey's End", "1/7", "high", 280),
        ("Alter", "Scale", "Ai Hoshino Final Stage Performance", "Oshi no Ko", "1/7", "grail", 400),
        ("Alter", "Scale", "Power Blood Chainsaw Form", "Chainsaw Man", "1/7", "grail", 380),
        ("Alter", "Scale", "Nobara Kugisaki Black Flash", "Jujutsu Kaisen", "1/7", "high", 270),

        # ── Good Smile Company — Recent Series (+6) ─────────────────────
        ("Good Smile Company", "Scale", "Anya Forger School Uniform Ver.", "Spy x Family", "1/7", "mid", 165),
        ("Good Smile Company", "Scale", "Sung Jin-woo Shadow Monarch", "Solo Leveling", "1/7", "high", 280),
        ("Good Smile Company", "Scale", "Momo Ayase School Uniform", "Dandadan", "1/7", "mid", 180),
        ("Good Smile Company", "Scale", "Okarun Turbo Granny Possessed", "Dandadan", "1/7", "mid", 190),
        ("Good Smile Company", "Nendoroid", "Sung Jin-woo Nendoroid", "Solo Leveling", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Pop Up Parade", "Hime Gotou Pop Up Parade", "Oshi no Ko", "Non-scale", "standard", 30),

        # ── Kotobukiya — ARTFX J Recent (+5) ────────────────────────────
        ("Kotobukiya", "ARTFX J", "Yuji Itadori Black Flash", "Jujutsu Kaisen", "1/8", "high", 230),
        ("Kotobukiya", "ARTFX J", "Denji Chainsaw Devil Transformation", "Chainsaw Man", "1/8", "high", 220),
        ("Kotobukiya", "ARTFX J", "Yor Forger Assassin Pose", "Spy x Family", "1/8", "high", 210),
        ("Kotobukiya", "ARTFX J", "Sung Jin-woo Dagger Stance", "Solo Leveling", "1/8", "high", 240),
        ("Kotobukiya", "ARTFX J", "Frieren Magic Circle Casting", "Frieren: Beyond Journey's End", "1/8", "mid", 195),

        # ── FREEing B-Style Bunny Figures (+5) ──────────────────────────
        ("FREEing", "Scale", "Momo Ayase Bunny Ver.", "Dandadan", "1/4", "grail", 470),

        # ── Prime 1 Studio & Tsume Art Grails (+5) ──────────────────────
        ("Prime 1 Studio", "Premium Masterline", "Luffy Gear 5 Nika", "One Piece", "1/4", "grail", 1500),
        ("Tsume Art", "HQS", "Zoro Enma Three Sword Style", "One Piece", "1/6", "grail", 900),
        ("Prime 1 Studio", "Premium Masterline", "Gojo Satoru Unlimited Void", "Jujutsu Kaisen", "1/4", "grail", 1400),
        ("Tsume Art", "HQS", "Sung Jin-woo Arise", "Solo Leveling", "1/6", "grail", 850),
        ("Prime 1 Studio", "Premium Masterline", "Pochita & Denji Hug", "Chainsaw Man", "1/4", "grail", 1100),

        # ── Banpresto Prize — Recent Series (+4) ────────────────────────
        ("Banpresto", "Grandista", "Sung Jin-woo Grandista", "Solo Leveling", "Non-scale", "standard", 38),
        ("Banpresto", "DXF", "Momo Ayase DXF Figure", "Dandadan", "Non-scale", "standard", 28),
        ("Banpresto", "Vibration Stars", "Frieren Vibration Stars", "Frieren: Beyond Journey's End", "Non-scale", "standard", 26),
        ("Banpresto", "DXF", "Fern DXF Figure", "Frieren: Beyond Journey's End", "Non-scale", "standard", 26),

        # ── Nendoroid Numbered Series ──────────────────────────────────────
        ("Good Smile Company", "Nendoroid", "Nendoroid #2171 Gojo Satoru (Season 2)", "Jujutsu Kaisen", "Non-scale", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Nendoroid #2197 Itadori Yuji (Sukuna)", "Jujutsu Kaisen", "Non-scale", "mid", 60),
        ("Good Smile Company", "Nendoroid", "Nendoroid #1902 Tanjiro Kamado (Final Selection)", "Demon Slayer", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid #2062 Makima", "Chainsaw Man", "Non-scale", "mid", 70),
        ("Good Smile Company", "Nendoroid", "Nendoroid #2070 Power", "Chainsaw Man", "Non-scale", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Nendoroid #2058 Denji (Chainsaw Form)", "Chainsaw Man", "Non-scale", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Nendoroid #2147 Frieren", "Frieren: Beyond Journey's End", "Non-scale", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Nendoroid #2148 Fern", "Frieren: Beyond Journey's End", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid #2210 Sung Jin-woo", "Solo Leveling", "Non-scale", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Nendoroid #1305 Levi (Cleaning Ver.)", "Attack on Titan", "Non-scale", "high", 120),
        ("Good Smile Company", "Nendoroid", "Nendoroid #1520 Hatsune Miku (16th Anniversary)", "Vocaloid", "Non-scale", "mid", 70),
        ("Good Smile Company", "Nendoroid", "Nendoroid #631 Rem", "Re:Zero", "Non-scale", "mid", 80),
        ("Good Smile Company", "Nendoroid", "Nendoroid #632 Ram", "Re:Zero", "Non-scale", "mid", 75),
        ("Good Smile Company", "Nendoroid", "Nendoroid #1920 Anya Forger", "Spy x Family", "Non-scale", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Nendoroid #2110 Ai Hoshino", "Oshi no Ko", "Non-scale", "mid", 70),
        ("Good Smile Company", "Nendoroid", "Nendoroid #1902 Yor Forger (Thorn Princess)", "Spy x Family", "Non-scale", "mid", 80),
        ("Good Smile Company", "Nendoroid", "Nendoroid #1811 Shinji Ikari (Plugsuit)", "Evangelion", "Non-scale", "mid", 60),
        ("Good Smile Company", "Nendoroid", "Nendoroid #1476 Naruto (Sage Mode)", "Naruto Shippuden", "Non-scale", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Nendoroid #2230 Isagi Yoichi", "Blue Lock", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid #2016 Marin Kitagawa (Cosplay)", "My Dress-Up Darling", "Non-scale", "mid", 80),

        # ── Pop Up Parade Expanded ─────────────────────────────────────────
        ("Good Smile Company", "Pop Up Parade", "Gojo Satoru (PUP)", "Jujutsu Kaisen", "Non-scale", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Tanjiro Kamado (PUP)", "Demon Slayer", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Nezuko Kamado (PUP)", "Demon Slayer", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Anya Forger (PUP)", "Spy x Family", "Non-scale", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Loid Forger (PUP)", "Spy x Family", "Non-scale", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Yor Forger (PUP)", "Spy x Family", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Luffy Gear 5 (PUP)", "One Piece", "Non-scale", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Denji (PUP)", "Chainsaw Man", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Power (PUP)", "Chainsaw Man", "Non-scale", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Marin Kitagawa (PUP)", "My Dress-Up Darling", "Non-scale", "standard", 38),
        ("Good Smile Company", "Pop Up Parade", "Frieren (PUP)", "Frieren: Beyond Journey's End", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Himmel (PUP)", "Frieren: Beyond Journey's End", "Non-scale", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Sung Jin-woo (PUP)", "Solo Leveling", "Non-scale", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Zero Two (PUP)", "DARLING in the FRANXX", "Non-scale", "standard", 38),
        ("Good Smile Company", "Pop Up Parade", "Ai Hoshino (PUP)", "Oshi no Ko", "Non-scale", "standard", 35),

        # ── Figma Specific Characters ──────────────────────────────────────
        ("Max Factory", "Figma", "Figma #555 Guts (Berserker Armor)", "Berserk", "Non-scale", "high", 120),
        ("Max Factory", "Figma", "Figma #601 Gojo Satoru", "Jujutsu Kaisen", "Non-scale", "mid", 80),
        ("Max Factory", "Figma", "Figma #520 Levi Ackerman (Final Season)", "Attack on Titan", "Non-scale", "mid", 85),
        ("Max Factory", "Figma", "Figma #580 Denji", "Chainsaw Man", "Non-scale", "mid", 75),
        ("Max Factory", "Figma", "Figma #350 Link (Tears of the Kingdom)", "Zelda: TotK", "Non-scale", "mid", 80),
        ("Max Factory", "Figma", "Figma #490 Saber Altria 2.0", "Fate/Stay Night", "Non-scale", "mid", 90),
        ("Max Factory", "Figma", "Figma #595 Sung Jin-woo", "Solo Leveling", "Non-scale", "mid", 75),
        ("Max Factory", "Figma", "Figma #411 Astolfo", "Fate/Apocrypha", "Non-scale", "mid", 100),
        ("Max Factory", "Figma", "Figma #500 Hatsune Miku (NT)", "Vocaloid", "Non-scale", "mid", 75),
        ("Max Factory", "Figma", "Figma #445 Tanjiro Kamado", "Demon Slayer", "Non-scale", "mid", 70),

        # ── Prize Figures (Banpresto, Taito, SEGA) ─────────────────────────
        ("Banpresto", "Grandista", "Goku Ultra Instinct Grandista", "Dragon Ball Super", "Non-scale", "standard", 40),
        ("Banpresto", "Grandista", "Vegeta SSBE Grandista", "Dragon Ball Super", "Non-scale", "standard", 38),
        ("Banpresto", "Grandista", "Luffy Gear 5 Grandista Manga Dimensions", "One Piece", "Non-scale", "mid", 50),
        ("Banpresto", "King of Artist", "Roronoa Zoro King of Artist (Wano)", "One Piece", "Non-scale", "standard", 38),
        ("Banpresto", "Vibration Stars", "Gojo Satoru Vibration Stars", "Jujutsu Kaisen", "Non-scale", "standard", 30),
        ("Banpresto", "Vibration Stars", "Yuji Itadori Vibration Stars II", "Jujutsu Kaisen", "Non-scale", "standard", 28),
        ("Taito", "Coreful", "Rem (Coreful Wedding Ver.)", "Re:Zero", "Non-scale", "standard", 28),
        ("Taito", "Coreful", "Ram (Coreful Chinese Dress)", "Re:Zero", "Non-scale", "standard", 28),
        ("Taito", "Coreful", "Marin Kitagawa (Coreful Swimsuit)", "My Dress-Up Darling", "Non-scale", "standard", 35),
        ("SEGA", "Luminasta", "Yor Forger Luminasta (Thorn Princess)", "Spy x Family", "Non-scale", "standard", 30),
        ("SEGA", "Luminasta", "Frieren Luminasta", "Frieren: Beyond Journey's End", "Non-scale", "standard", 28),
        ("SEGA", "SPM", "Tanjiro Kamado SPM (Hinokami Kagura)", "Demon Slayer", "Non-scale", "standard", 28),
        ("Banpresto", "World Collectable Figure", "WCF One Piece Wano Set (6 Figures)", "One Piece", "Non-scale", "standard", 45),
        ("Banpresto", "DXF", "Anya Forger DXF (Starlight Princess)", "Spy x Family", "Non-scale", "standard", 25),
        ("Taito", "AMP", "Ai Hoshino AMP Figure (Idol Costume)", "Oshi no Ko", "Non-scale", "standard", 30),
        ("Banpresto", "DXF", "Momo Ayase DXF (Turbo Granny)", "Dandadan", "Non-scale", "standard", 30),
        ("SEGA", "SPM", "Isagi Yoichi SPM", "Blue Lock", "Non-scale", "standard", 26),
        ("Banpresto", "Grandista", "Naruto Baryon Mode Grandista", "Naruto Shippuden", "Non-scale", "standard", 40),

        # ── Garage Kits & Wonder Festival Exclusives ───────────────────────
        ("WF Exclusive", "Garage Kit", "Saber Lily (GK, 1/6 Unpainted)", "Fate/Stay Night", "1/6", "grail", 500),
        ("WF Exclusive", "Garage Kit", "Rem (GK, 1/7 Resin, Painted)", "Re:Zero", "1/7", "grail", 600),
        ("WF Exclusive", "Garage Kit", "Asuka Plugsuit (GK, 1/6 Unpainted)", "Evangelion", "1/6", "grail", 450),
        ("WF Exclusive", "Garage Kit", "Hatsune Miku Racing (GK, 1/7 Painted)", "Vocaloid", "1/7", "grail", 550),
        ("WF Exclusive", "Garage Kit", "Rei Ayanami (GK, 1/6 Resin Painted)", "Evangelion", "1/6", "grail", 500),
        ("WF Exclusive", "Garage Kit", "Guts Berserker (GK, 1/6 Resin Painted)", "Berserk", "1/6", "grail", 700),
        ("WF Exclusive", "Garage Kit", "Makima (GK, 1/7 Painted Resin)", "Chainsaw Man", "1/7", "grail", 550),
        ("WF Exclusive", "Garage Kit", "Power (GK, 1/7 Painted Resin)", "Chainsaw Man", "1/7", "grail", 500),
        ("WF Exclusive", "Garage Kit", "Yor Forger (GK, 1/6 Painted Resin)", "Spy x Family", "1/6", "grail", 480),
        ("WF Exclusive", "Garage Kit", "Zero Two (GK, 1/7 Painted Resin)", "DARLING in the FRANXX", "1/7", "grail", 520),

        # ── More Scale Figures — Recent Series ─────────────────────────────
        ("Kotobukiya", "Scale", "Makima (Business Suit Ver.)", "Chainsaw Man", "1/7", "high", 220),
        ("Alter", "Scale", "Frieren (Sitting on a Rock)", "Frieren: Beyond Journey's End", "1/7", "high", 250),
        ("Good Smile Company", "Scale", "Ai Hoshino (Idol Costume)", "Oshi no Ko", "1/7", "high", 220),
        ("MegaHouse", "Scale", "Yor Forger (Elegant Dress)", "Spy x Family", "1/7", "high", 240),
        ("Kotobukiya", "Scale", "Marin Kitagawa (Shizuku-tan Cosplay)", "My Dress-Up Darling", "1/7", "high", 230),
        ("FREEing", "Scale", "Power Bunny Ver.", "Chainsaw Man", "1/4", "grail", 480),
        ("Good Smile Company", "Scale", "Isagi Yoichi (Flow State)", "Blue Lock", "1/7", "mid", 180),
        ("Aniplex", "Scale", "Sung Jin-woo (Arise)", "Solo Leveling", "1/7", "high", 280),
        ("Myethos", "Scale", "Frieren (Fairytale Ver.)", "Frieren: Beyond Journey's End", "1/7", "high", 260),
        ("eStream", "Scale", "Rem (Crystal Dress Ver.)", "Re:Zero", "1/7", "grail", 450),

        # ── Genshin Impact Figures ─────────────────────────────────────────
        ("miHoYo", "Scale", "Raiden Shogun", "Genshin Impact", "1/7", "high", 280),
        ("miHoYo", "Scale", "Hu Tao", "Genshin Impact", "1/7", "high", 250),
        ("miHoYo", "Scale", "Ganyu", "Genshin Impact", "1/7", "high", 260),
        ("Good Smile Company", "Nendoroid", "Nendoroid Aether", "Genshin Impact", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid Lumine", "Genshin Impact", "Non-scale", "mid", 55),
        ("Phat! Company", "Scale", "Keqing (Piercing Thunderbolt)", "Genshin Impact", "1/7", "high", 240),

        # ── Dragon Ball Additional ─────────────────────────────────────────
        ("Banpresto", "Grandista", "Vegito Grandista", "Dragon Ball Super", "Non-scale", "standard", 42),
        ("Banpresto", "Grandista", "Cell (Perfect Form) Grandista", "Dragon Ball Z", "Non-scale", "standard", 38),
        ("Banpresto", "DXF", "Gohan Beast DXF", "Dragon Ball Super: Super Hero", "Non-scale", "standard", 30),
        ("MegaHouse", "Dragon Ball Capsule", "Shenron Dragon Ball Capsule (Complete)", "Dragon Ball Z", "Non-scale", "mid", 80),

        # ── More Nendoroid Recent ──────────────────────────────────────────
        ("Good Smile Company", "Nendoroid", "Nendoroid Zenitsu Agatsuma (Thunder Breathing)", "Demon Slayer", "Non-scale", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Nendoroid Nezuko Kamado (Demon Form)", "Demon Slayer", "Non-scale", "mid", 70),
        ("Good Smile Company", "Nendoroid", "Nendoroid Rengoku Kyojuro", "Demon Slayer", "Non-scale", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Nendoroid Monkey D. Luffy (Gear 5)", "One Piece", "Non-scale", "mid", 60),
        ("Good Smile Company", "Nendoroid", "Nendoroid Roronoa Zoro (Wano)", "One Piece", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid Griffith (Hawk of Light)", "Berserk", "Non-scale", "mid", 70),
        ("Good Smile Company", "Nendoroid", "Nendoroid Guts (Band of the Hawk)", "Berserk", "Non-scale", "mid", 70),
        ("Good Smile Company", "Nendoroid", "Nendoroid Pochita", "Chainsaw Man", "Non-scale", "mid", 50),
        ("Good Smile Company", "Nendoroid", "Nendoroid Ruby Hoshino", "Oshi no Ko", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid Momo Ayase", "Dandadan", "Non-scale", "mid", 55),

        # ── More Scale Figures — Naruto / Bleach / My Hero ─────────────────
        ("MegaHouse", "G.E.M.", "Naruto Uzumaki (Six Paths Sage)", "Naruto Shippuden", "1/8", "high", 250),
        ("MegaHouse", "G.E.M.", "Sasuke Uchiha (Susano'o)", "Naruto Shippuden", "1/8", "high", 280),
        ("Tsume Art", "HQS", "Minato Namikaze", "Naruto Shippuden", "1/6", "grail", 850),
        ("Kotobukiya", "Scale", "Ichigo Kurosaki (Bankai)", "Bleach TYBW", "1/8", "high", 220),
        ("Aniplex", "Scale", "Ichigo Kurosaki (Final Getsuga Tenshou)", "Bleach TYBW", "1/7", "high", 280),
        ("Kotobukiya", "Scale", "Izuku Midoriya (Shoot Style)", "My Hero Academia", "1/8", "mid", 180),
        ("Kotobukiya", "Scale", "All Might (United States of Smash)", "My Hero Academia", "1/8", "high", 250),
        ("Banpresto", "DXF", "Bakugo Katsuki DXF", "My Hero Academia", "Non-scale", "standard", 28),

        # ── More Pop Up Parade / Prize Extended ────────────────────────────
        ("Good Smile Company", "Pop Up Parade", "Rem (PUP Ice Season Ver.)", "Re:Zero", "Non-scale", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Ram (PUP Ice Season Ver.)", "Re:Zero", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "Guts (PUP Band of the Hawk)", "Berserk", "Non-scale", "standard", 38),
        ("Good Smile Company", "Pop Up Parade", "Ichigo Kurosaki (PUP)", "Bleach TYBW", "Non-scale", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Naruto Uzumaki (PUP Sage)", "Naruto Shippuden", "Non-scale", "standard", 32),
        ("Good Smile Company", "Pop Up Parade", "All Might (PUP)", "My Hero Academia", "Non-scale", "standard", 38),
        ("Banpresto", "Maximatic", "Goku SSJ Maximatic", "Dragon Ball Z", "Non-scale", "standard", 35),
        ("Banpresto", "Maximatic", "Vegeta Maximatic II", "Dragon Ball Z", "Non-scale", "standard", 32),
        ("Taito", "Coreful", "Frieren (Coreful Magic Ver.)", "Frieren: Beyond Journey's End", "Non-scale", "standard", 30),
        ("SEGA", "Luminasta", "Makima Luminasta", "Chainsaw Man", "Non-scale", "standard", 32),
        ("SEGA", "SPM", "Denji (SPM Chainsaw Form)", "Chainsaw Man", "Non-scale", "standard", 30),
        ("Banpresto", "Grandista", "Frieza Final Form Grandista", "Dragon Ball Z", "Non-scale", "standard", 35),

        # ── More Scale Figures — Evangelion / Re:Zero / Fate Extended ──────
        ("Good Smile Company", "Scale", "Asuka Langley (Jersey Ver.)", "Evangelion", "1/7", "high", 220),
        ("Kotobukiya", "Scale", "Rei Ayanami (Casual Dress)", "Evangelion", "1/7", "mid", 180),
        ("Prime 1 Studio", "Premium Masterline", "Eva Unit-01 (Awakening)", "Evangelion", "1/4", "grail", 1200),
        ("Kadokawa", "Scale", "Rem (Wedding Dress Ver.)", "Re:Zero", "1/7", "high", 220),
        ("Kadokawa", "Scale", "Ram (China Dress Ver.)", "Re:Zero", "1/7", "mid", 180),
        ("Good Smile Company", "Scale", "Emilia (Crystal Dress Ver.)", "Re:Zero", "1/7", "high", 250),
        ("Alter", "Scale", "Saber (Excalibur Ver.)", "Fate/Stay Night", "1/7", "high", 280),
        ("Good Smile Company", "Scale", "Gilgamesh (Fate/Grand Order)", "Fate/Grand Order", "1/8", "high", 240),
        ("Max Factory", "Scale", "Rider (Fate/Stay Night HF)", "Fate/Stay Night", "1/7", "high", 260),
        ("FREEing", "Scale", "Saber Alter Bunny Ver.", "Fate/Stay Night", "1/4", "grail", 500),
        ("FREEing", "Scale", "Rem Bunny Ver. 2nd", "Re:Zero", "1/4", "grail", 480),
        ("FREEing", "Scale", "Emilia Bunny Ver.", "Re:Zero", "1/4", "grail", 460),

        # ── More Figma / Nendoroid Extended ────────────────────────────────
        ("Max Factory", "Figma", "Figma #352 Rem", "Re:Zero", "Non-scale", "mid", 90),
        ("Max Factory", "Figma", "Figma #353 Ram", "Re:Zero", "Non-scale", "mid", 85),
        ("Max Factory", "Figma", "Figma #227 Saber 2.0", "Fate/Stay Night", "Non-scale", "mid", 100),
        ("Max Factory", "Figma", "Figma #457 Nero Claudius", "Fate/Extra Last Encore", "Non-scale", "mid", 80),
        ("Max Factory", "Figma", "Figma #382 Goblin Slayer", "Goblin Slayer", "Non-scale", "mid", 80),
        ("Good Smile Company", "Nendoroid", "Nendoroid #1379 Echidna", "Re:Zero", "Non-scale", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Nendoroid #1251 Kaguya Shinomiya", "Kaguya-sama", "Non-scale", "mid", 60),
        ("Good Smile Company", "Nendoroid", "Nendoroid #1252 Miyuki Shirogane", "Kaguya-sama", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid #1736 Megumin (Explosion)", "KonoSuba", "Non-scale", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Nendoroid #1737 Aqua (Goddess)", "KonoSuba", "Non-scale", "mid", 55),

        # ── More Banpresto / Prize Extended ────────────────────────────────
        ("Banpresto", "Q Posket", "Q Posket Yor Forger", "Spy x Family", "Non-scale", "standard", 22),
        ("Banpresto", "Q Posket", "Q Posket Anya Forger", "Spy x Family", "Non-scale", "standard", 20),
        ("Banpresto", "Q Posket", "Q Posket Nezuko Kamado", "Demon Slayer", "Non-scale", "standard", 22),
        ("Banpresto", "Q Posket", "Q Posket Rem", "Re:Zero", "Non-scale", "standard", 20),
        ("Banpresto", "Q Posket", "Q Posket Ram", "Re:Zero", "Non-scale", "standard", 20),
        ("Taito", "Desktop Army", "Desktop Army Frieren", "Frieren: Beyond Journey's End", "Non-scale", "standard", 25),
        ("Taito", "Coreful", "Hatsune Miku (Coreful Sakura)", "Vocaloid", "Non-scale", "standard", 28),
        ("SEGA", "Luminasta", "Zero Two Luminasta", "DARLING in the FRANXX", "Non-scale", "standard", 32),
        ("SEGA", "SPM", "Gojo Satoru SPM (Hollow Purple)", "Jujutsu Kaisen", "Non-scale", "standard", 30),
        ("Banpresto", "Vibration Stars", "Tanjiro Vibration Stars (Hinokami)", "Demon Slayer", "Non-scale", "standard", 28),
        ("Taito", "Coreful", "Ai Hoshino (Coreful Stage Ver.)", "Oshi no Ko", "Non-scale", "standard", 30),
        ("Banpresto", "DXF", "Luffy DXF Grandline Men (Wano)", "One Piece", "Non-scale", "standard", 25),

        # ── More Prime 1 / Premium Resin ───────────────────────────────────
        ("Prime 1 Studio", "Premium Masterline", "Griffith (Hawk of Light)", "Berserk", "1/4", "grail", 1500),
        ("Prime 1 Studio", "Premium Masterline", "Tanjiro Kamado (Water Breathing)", "Demon Slayer", "1/4", "grail", 1200),
        ("Tsume Art", "HQS", "Gojo Satoru (Infinite Void)", "Jujutsu Kaisen", "1/6", "grail", 900),
        ("Tsume Art", "HQS", "All Might (United States of Smash)", "My Hero Academia", "1/6", "grail", 850),
        ("Prime 1 Studio", "Premium Masterline", "Eren Yeager (Attack Titan)", "Attack on Titan", "1/4", "grail", 1300),
        ("F4F (First 4 Figures)", "Scale", "Guts (Berserker Armor, Light-Up)", "Berserk", "1/4", "grail", 1000),

        # ── Additional Scale Figures ───────────────────────────────────────
        ("Kotobukiya", "Scale", "Quintessential Quintuplets Miku Nakano", "Quintessential Quintuplets", "1/7", "mid", 180),
        ("Kotobukiya", "Scale", "Quintessential Quintuplets Nino Nakano (Wedding)", "Quintessential Quintuplets", "1/7", "mid", 190),
        ("Good Smile Company", "Scale", "Zero Two (Wedding Dress)", "DARLING in the FRANXX", "1/7", "high", 280),
        ("Myethos", "Scale", "Miku Hatsune (Shaohua Ver.)", "Vocaloid", "1/7", "high", 250),
        ("eStream", "Scale", "Ram (Crystal Dress Ver.)", "Re:Zero", "1/7", "grail", 430),
        ("Good Smile Company", "Scale", "Momo Ayase (School Uniform)", "Dandadan", "1/7", "mid", 190),
        ("Aniplex", "Scale", "Isagi Yoichi (Goal Ver.)", "Blue Lock", "1/7", "mid", 200),
        ("Kotobukiya", "ARTFX J", "Yoh Asakura", "Shaman King", "1/8", "mid", 180),
        ("MegaHouse", "G.E.M.", "Levi Ackerman (Cleaning Ver.)", "Attack on Titan", "1/8", "high", 280),
        ("Alter", "Scale", "Megumin (Explosion Magic Ver.)", "KonoSuba", "1/7", "high", 260),
        ("Good Smile Company", "Scale", "Aqua (Winter Outfit)", "KonoSuba", "1/7", "mid", 190),

        # ── Nendoroids — Most Searched (~25) ──────────────────────────────
        ("Good Smile Company", "Nendoroid", "Gojo Satoru (#1600)", "Jujutsu Kaisen", "N/A", "mid", 80),
        ("Good Smile Company", "Nendoroid", "Gojo Satoru (Casual Ver. #1601)", "Jujutsu Kaisen", "N/A", "mid", 75),
        ("Good Smile Company", "Nendoroid", "Tanjiro Kamado (#1193)", "Demon Slayer", "N/A", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Nezuko Kamado (#1194)", "Demon Slayer", "N/A", "mid", 70),
        ("Good Smile Company", "Nendoroid", "Hatsune Miku (#2000, 15th Anniv.)", "Vocaloid", "N/A", "high", 120),
        ("Good Smile Company", "Nendoroid", "Hatsune Miku (#2075, Racing 2025)", "Vocaloid", "N/A", "mid", 90),
        ("Good Smile Company", "Nendoroid", "Hatsune Miku (#33, Original Re-Release)", "Vocaloid", "N/A", "mid", 60),
        ("Good Smile Company", "Nendoroid", "Link (Tears of the Kingdom #2188)", "Zelda", "N/A", "mid", 70),
        ("Good Smile Company", "Nendoroid", "Link (Breath of the Wild #733 DX)", "Zelda", "N/A", "mid", 80),
        ("Good Smile Company", "Nendoroid", "Zero Two (#952)", "DARLING in the FRANXX", "N/A", "high", 130),
        ("Good Smile Company", "Nendoroid", "Rem (#663)", "Re:Zero", "N/A", "high", 100),
        ("Good Smile Company", "Nendoroid", "Ram (#732)", "Re:Zero", "N/A", "mid", 85),
        ("Good Smile Company", "Nendoroid", "Denji (#1560)", "Chainsaw Man", "N/A", "mid", 60),
        ("Good Smile Company", "Nendoroid", "Power (#1580)", "Chainsaw Man", "N/A", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Makima (#1610)", "Chainsaw Man", "N/A", "mid", 70),
        ("Good Smile Company", "Nendoroid", "Yor Forger (#1902)", "Spy x Family", "N/A", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Anya Forger (#1903)", "Spy x Family", "N/A", "mid", 50),
        ("Good Smile Company", "Nendoroid", "Loid Forger (#1901)", "Spy x Family", "N/A", "mid", 50),
        ("Good Smile Company", "Nendoroid", "Guts (Berserker Armor #1080)", "Berserk", "N/A", "high", 110),
        ("Good Smile Company", "Nendoroid", "Frieren (#2305)", "Frieren", "N/A", "mid", 65),
        ("Good Smile Company", "Nendoroid", "Fern (#2310)", "Frieren", "N/A", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Sung Jin-woo (#2350)", "Solo Leveling", "N/A", "mid", 70),
        ("Good Smile Company", "Nendoroid", "Itadori Yuji (#1825)", "Jujutsu Kaisen", "N/A", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Sukuna (#1830)", "Jujutsu Kaisen", "N/A", "mid", 75),
        ("Good Smile Company", "Nendoroid", "Satoru Gojo (Season 2 #2100)", "Jujutsu Kaisen", "N/A", "mid", 85),

        # ── Pop Up Parade — Most Searched (~25) ──────────────────────────
        ("Good Smile Company", "Pop Up Parade", "Denji", "Chainsaw Man", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Power", "Chainsaw Man", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Makima", "Chainsaw Man", "1/7", "standard", 38),
        ("Good Smile Company", "Pop Up Parade", "Aki Hayakawa", "Chainsaw Man", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Gojo Satoru", "Jujutsu Kaisen", "1/7", "standard", 40),
        ("Good Smile Company", "Pop Up Parade", "Itadori Yuji", "Jujutsu Kaisen", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Megumi Fushiguro", "Jujutsu Kaisen", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Toji Fushiguro", "Jujutsu Kaisen", "1/7", "standard", 40),
        ("Good Smile Company", "Pop Up Parade", "Sukuna (King of Curses)", "Jujutsu Kaisen", "1/7", "standard", 38),
        ("Good Smile Company", "Pop Up Parade", "Tanjiro Kamado", "Demon Slayer", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Nezuko Kamado", "Demon Slayer", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Rengoku Kyojuro", "Demon Slayer", "1/7", "standard", 38),
        ("Good Smile Company", "Pop Up Parade", "Tengen Uzui", "Demon Slayer", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Yor Forger", "Spy x Family", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Anya Forger", "Spy x Family", "1/7", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Frieren", "Frieren", "1/7", "standard", 38),
        ("Good Smile Company", "Pop Up Parade", "Himmel", "Frieren", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Sung Jin-woo", "Solo Leveling", "1/7", "standard", 40),
        ("Good Smile Company", "Pop Up Parade", "Igris", "Solo Leveling", "1/7", "standard", 38),
        ("Good Smile Company", "Pop Up Parade", "Kirito (Alicization)", "Sword Art Online", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Asuna (Goddess of Creation)", "Sword Art Online", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Hatsune Miku (Racing 2024)", "Vocaloid", "1/7", "standard", 38),
        ("Good Smile Company", "Pop Up Parade", "Emilia (Ice Season)", "Re:Zero", "1/7", "standard", 35),
        ("Good Smile Company", "Pop Up Parade", "Rem (Oiran Ver.)", "Re:Zero", "1/7", "standard", 38),
        ("Good Smile Company", "Pop Up Parade", "Marin Kitagawa (Cosplay)", "My Dress-Up Darling", "1/7", "standard", 38),

        # ── Prize Figures — Banpresto Most Searched (~25) ────────────────
        ("Banpresto", "Vibration Stars", "Tanjiro Kamado (Water Breathing)", "Demon Slayer", "1/8", "standard", 30),
        ("Banpresto", "Vibration Stars", "Nezuko Kamado (Blood Demon Art)", "Demon Slayer", "1/8", "standard", 32),
        ("Banpresto", "Vibration Stars", "Rengoku (Flame Breathing)", "Demon Slayer", "1/8", "standard", 35),
        ("Banpresto", "Vibration Stars", "Muzan Kibutsuji", "Demon Slayer", "1/8", "standard", 30),
        ("Banpresto", "Vibration Stars", "Akaza", "Demon Slayer", "1/8", "standard", 32),
        ("Banpresto", "Vibration Stars", "Gyomei Himejima", "Demon Slayer", "1/8", "standard", 30),
        ("Banpresto", "DXF", "Goku (Super Saiyan Blue)", "Dragon Ball Super", "1/8", "standard", 28),
        ("Banpresto", "DXF", "Vegeta (Ultra Ego)", "Dragon Ball Super", "1/8", "standard", 30),
        ("Banpresto", "DXF", "Broly (Full Power)", "Dragon Ball Super", "1/8", "standard", 32),
        ("Banpresto", "DXF", "Frieza (Final Form)", "Dragon Ball Z", "1/8", "standard", 25),
        ("Banpresto", "DXF", "Cell (Perfect Form)", "Dragon Ball Z", "1/8", "standard", 25),
        ("Banpresto", "Grandista", "Luffy (Gear 5, Manga Dimensions)", "One Piece", "1/7", "mid", 55),
        ("Banpresto", "Grandista", "Zoro (Enma, Manga Dimensions)", "One Piece", "1/7", "mid", 50),
        ("Banpresto", "Grandista", "Naruto (Baryon Mode)", "Naruto", "1/7", "mid", 55),
        ("Banpresto", "Grandista", "Sasuke (Susanoo)", "Naruto", "1/7", "mid", 48),
        ("Banpresto", "King of Artist", "Luffy (Snakeman)", "One Piece", "1/8", "mid", 45),
        ("Banpresto", "King of Artist", "Zoro (King of Hell)", "One Piece", "1/8", "mid", 42),
        ("Banpresto", "King of Artist", "Ace (Fire Fist)", "One Piece", "1/8", "mid", 40),
        ("Banpresto", "SPM", "Gojo Satoru (Domain Expansion)", "Jujutsu Kaisen", "1/8", "standard", 30),
        ("Banpresto", "SPM", "Itadori Yuji (Black Flash)", "Jujutsu Kaisen", "1/8", "standard", 28),
        ("Banpresto", "SPM", "Megumi Fushiguro (Mahoraga)", "Jujutsu Kaisen", "1/8", "standard", 28),
        ("Banpresto", "SPM", "Toji Fushiguro (Inverted Spear)", "Jujutsu Kaisen", "1/8", "standard", 32),
        ("Banpresto", "SPM", "Sukuna (Malevolent Shrine)", "Jujutsu Kaisen", "1/8", "standard", 30),
        ("Banpresto", "SPM", "Momo Ayase", "Dandadan", "1/8", "standard", 28),
        ("Banpresto", "SPM", "Okarun (Turbo Granny)", "Dandadan", "1/8", "standard", 30),

        # ── Figma — Most Searched (~15) ──────────────────────────────────
        ("Max Factory", "Figma", "Link (Tears of the Kingdom #626)", "Zelda", "N/A", "mid", 90),
        ("Max Factory", "Figma", "Link (Breath of the Wild #320 DX)", "Zelda", "N/A", "high", 120),
        ("Max Factory", "Figma", "Guts (Berserker Armor #410)", "Berserk", "N/A", "high", 150),
        ("Max Factory", "Figma", "Guts (Black Swordsman #359)", "Berserk", "N/A", "high", 130),
        ("Max Factory", "Figma", "Samus Aran (Prime 4 #615)", "Metroid", "N/A", "mid", 80),
        ("Max Factory", "Figma", "Samus Aran (Dread #601)", "Metroid", "N/A", "mid", 75),
        ("Max Factory", "Figma", "Kirito (Alicization #435)", "Sword Art Online", "N/A", "mid", 70),
        ("Max Factory", "Figma", "Solid Snake (Metal Gear Solid 2 #243)", "Metal Gear", "N/A", "high", 150),
        ("Max Factory", "Figma", "Griffith (Hawk of Light #138)", "Berserk", "N/A", "grail", 300),
        ("Max Factory", "Figma", "Hatsune Miku (V4 Chinese #450)", "Vocaloid", "N/A", "mid", 70),
        ("Max Factory", "Figma", "Gojo Satoru (#595)", "Jujutsu Kaisen", "N/A", "mid", 80),
        ("Max Factory", "Figma", "Levi Ackerman (#213)", "Attack on Titan", "N/A", "high", 120),
        ("Max Factory", "Figma", "Eren Yeager (Attack Titan #446)", "Attack on Titan", "N/A", "mid", 90),
        ("Max Factory", "Figma", "Cloud Strife (FF7R #587)", "Final Fantasy", "N/A", "mid", 85),
        ("Max Factory", "Figma", "Tifa Lockhart (FF7R #588)", "Final Fantasy", "N/A", "mid", 90),

        # ── Resin Statues & Garage Kits (~15) ────────────────────────────
        ("Tsume Art", "HQS+", "Luffy vs Kaido (Wano) HQS+ 1/4", "One Piece", "1/4", "grail", 2500),
        ("Tsume Art", "HQS", "Gojo (Hollow Purple) HQS 1/6", "Jujutsu Kaisen", "1/6", "grail", 1200),
        ("Tsume Art", "HQS", "Tanjiro (Hinokami Kagura) HQS 1/6", "Demon Slayer", "1/6", "grail", 1100),
        ("Tsume Art", "Ikigai", "Chainsaw Man (Denji) 1/6", "Chainsaw Man", "1/6", "grail", 800),
        ("Prime 1 Studio", "Premium Masterline", "Goku Ultra Instinct 1/4", "Dragon Ball Super", "1/4", "grail", 1500),
        ("Prime 1 Studio", "Premium Masterline", "Naruto Baryon Mode 1/4", "Naruto", "1/4", "grail", 1400),
        ("Prime 1 Studio", "Premium Masterline", "Tanjiro (Water & Fire) 1/4", "Demon Slayer", "1/4", "grail", 1300),
        ("F4F (First 4 Figures)", "Scale", "Link on Epona (BOTW) 1/4", "Zelda", "1/4", "grail", 900),
        ("F4F (First 4 Figures)", "Scale", "Meta Knight 1/4", "Kirby", "1/4", "grail", 700),
        ("F4F (First 4 Figures)", "Scale", "Guts (Black Swordsman) 1/4", "Berserk", "1/4", "grail", 1100),
        ("Garage Kit", "Resin", "Gojo (Domain Expansion, GK 1/6 Unpainted)", "Jujutsu Kaisen", "1/6", "high", 250),
        ("Garage Kit", "Resin", "Rem (Crystal Dress, GK 1/6 Unpainted)", "Re:Zero", "1/6", "high", 200),
        ("Garage Kit", "Resin", "Miku (Racing 2024, GK 1/7 Unpainted)", "Vocaloid", "1/7", "high", 180),
        ("Garage Kit", "Resin", "Zero Two (Wedding, GK 1/7 Painted)", "DARLING in the FRANXX", "1/7", "grail", 400),
        ("Garage Kit", "Resin", "Guts (Berserker, GK 1/6 Painted)", "Berserk", "1/6", "grail", 500),

        # ── B-style / FREEing — Additional Bunnies (~15) ────────────────
        ("FREEing", "B-style", "Zero Two Bunny Ver.", "DARLING in the FRANXX", "1/4", "grail", 450),
        ("FREEing", "B-style", "Miku Bunny Ver. (Art by SanMuYYB)", "Vocaloid", "1/4", "grail", 500),
        ("FREEing", "B-style", "Marin Kitagawa Bunny Ver.", "My Dress-Up Darling", "1/4", "grail", 480),
        ("FREEing", "B-style", "Emilia Bunny Ver.", "Re:Zero", "1/4", "grail", 400),
        ("FREEing", "B-style", "Ram Bunny Ver. 2nd", "Re:Zero", "1/4", "grail", 450),
        ("FREEing", "B-style", "Raphtalia Bunny Ver.", "Shield Hero", "1/4", "grail", 380),
        ("FREEing", "B-style", "Yor Forger Bunny Ver.", "Spy x Family", "1/4", "grail", 500),
        ("FREEing", "B-style", "Megumin Bunny Ver.", "KonoSuba", "1/4", "grail", 420),
        ("FREEing", "B-style", "Asuna Bunny Ver.", "Sword Art Online", "1/4", "grail", 380),
        ("FREEing", "B-style", "C.C. Bunny Ver.", "Code Geass", "1/4", "grail", 400),
        ("FREEing", "B-style", "Mai Sakurajima Bunny Ver.", "Bunny Girl Senpai", "1/4", "grail", 550),
        ("FREEing", "B-style", "Mikasa Ackerman Bunny Ver.", "Attack on Titan", "1/4", "grail", 420),
        ("FREEing", "B-style", "Nico Robin Bunny Ver.", "One Piece", "1/4", "grail", 480),
        ("FREEing", "B-style", "Android 18 Bunny Ver.", "Dragon Ball", "1/4", "grail", 450),
        ("FREEing", "B-style", "Aqua Bunny Ver.", "KonoSuba", "1/4", "grail", 380),

        # ── Additional Hot Scale Figures (~10) ───────────────────────────
        ("Myethos", "Scale", "Frieren (Casting Spell)", "Frieren", "1/7", "high", 220),
        ("Myethos", "Scale", "Yor Forger (Thorn Princess)", "Spy x Family", "1/7", "high", 250),
        ("Kotobukiya", "ARTFX J", "Gojo Satoru (Hollow Purple)", "Jujutsu Kaisen", "1/8", "high", 200),
        ("Kotobukiya", "ARTFX J", "Tanjiro Kamado (Hinokami Kagura)", "Demon Slayer", "1/8", "high", 190),
        ("Alter", "Scale", "Rem (Oni Ver.)", "Re:Zero", "1/7", "high", 280),
        ("Alter", "Scale", "Emilia (Frozen Bond)", "Re:Zero", "1/7", "high", 260),
        ("eStream", "Scale", "Emilia (Crystal Dress Ver.)", "Re:Zero", "1/7", "grail", 520),
        ("Aniplex", "Scale", "Marin Kitagawa (Shizuku-tan)", "My Dress-Up Darling", "1/7", "high", 250),
        ("Good Smile Company", "Scale", "Miku (Symphony 2025)", "Vocaloid", "1/7", "high", 220),
        ("Kotobukiya", "Scale", "Power (Chainsaw Man)", "Chainsaw Man", "1/7", "mid", 170),
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

    # Expand with scale/manufacturer/limited variants before dedup
    catalog = _variant_expansion(catalog)

    # Add wave 2 expansion items
    catalog.extend(_wave2_anime_expansion())

    # Deduplicate by ('manufacturer', 'character', 'scale', 'figure_type') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["manufacturer"], item["character"], item["scale"], item["figure_type"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def _wave2_anime_expansion() -> list[dict]:
    """Wave 2 — ~155 items: Demon Slayer, Jujutsu Kaisen, Spy x Family,
    Chainsaw Man, Frieren, One Piece, Evangelion, Fate, Nendoroid & figma
    expansions, and Prize figures (Banpresto)."""

    figures = [
        # ── Demon Slayer — Scale Figures ───────────────────────────────
        ("Aniplex", "Scale", "Rengoku Kyojuro Flame Hashira Ver.", "Demon Slayer", "1/8", "high", 280),
        ("Alter", "Scale", "Mitsuri Kanroji Love Breathing", "Demon Slayer", "1/7", "high", 260),
        ("Kotobukiya", "Scale", "Muichiro Tokito Mist Hashira", "Demon Slayer", "1/8", "mid", 180),
        ("Good Smile Company", "Scale", "Shinobu Kocho Insect Hashira", "Demon Slayer", "1/7", "high", 240),
        ("Alter", "Scale", "Tengen Uzui Sound Hashira Ver.", "Demon Slayer", "1/7", "high", 280),
        ("FREEing", "B-style", "Mitsuri Kanroji Bunny Ver.", "Demon Slayer", "1/4", "grail", 450),
        ("Good Smile Company", "Scale", "Akaza Upper Moon Three", "Demon Slayer", "1/7", "high", 300),
        ("Aniplex", "Scale", "Zenitsu Agatsuma Thunderclap", "Demon Slayer", "1/8", "high", 220),

        # ── Jujutsu Kaisen — Scale Figures ─────────────────────────────
        ("Alter", "Scale", "Satoru Gojo Hollow Purple Ver.", "Jujutsu Kaisen", "1/7", "grail", 420),
        ("FREEing", "B-style", "Nobara Kugisaki Bunny Ver.", "Jujutsu Kaisen", "1/4", "grail", 400),
        ("Kotobukiya", "Scale", "Yuji Itadori Black Flash", "Jujutsu Kaisen", "1/7", "high", 200),
        ("Good Smile Company", "Scale", "Megumi Fushiguro Chimera Shadow", "Jujutsu Kaisen", "1/7", "high", 240),
        ("Aniplex", "Scale", "Sukuna Domain Expansion Ver.", "Jujutsu Kaisen", "1/7", "grail", 380),
        ("Kotobukiya", "Scale", "Toji Fushiguro Sorcerer Killer", "Jujutsu Kaisen", "1/7", "high", 260),
        ("Alter", "Scale", "Maki Zenin Playful Mind", "Jujutsu Kaisen", "1/7", "high", 220),

        # ── Spy x Family ───────────────────────────────────────────────
        ("Good Smile Company", "Scale", "Yor Forger Thorn Princess Ver.", "Spy x Family", "1/7", "high", 280),
        ("Alter", "Scale", "Yor Forger Elegant Dress Ver.", "Spy x Family", "1/7", "grail", 350),
        ("FREEing", "B-style", "Yor Forger Bunny Ver.", "Spy x Family", "1/4", "grail", 480),
        ("Kotobukiya", "Scale", "Loid Forger Twilight Ver.", "Spy x Family", "1/7", "high", 200),
        ("Good Smile Company", "Scale", "Anya Forger Mission Start Ver.", "Spy x Family", "1/7", "mid", 180),
        ("Bandai", "S.H.Figuarts", "Loid Forger S.H.Figuarts", "Spy x Family", "Non-scale", "mid", 70),

        # ── Chainsaw Man ───────────────────────────────────────────────
        ("Good Smile Company", "Scale", "Denji Chainsaw Devil Form", "Chainsaw Man", "1/7", "high", 280),
        ("Kotobukiya", "Scale", "Makima Control Devil Ver.", "Chainsaw Man", "1/7", "high", 260),
        ("FREEing", "B-style", "Makima Bunny Ver.", "Chainsaw Man", "1/4", "grail", 500),
        ("Alter", "Scale", "Power Blood Fiend Ver.", "Chainsaw Man", "1/7", "high", 300),
        ("Good Smile Company", "Scale", "Pochita Plush Scale Figure", "Chainsaw Man", "1/1", "mid", 120),
        ("Kotobukiya", "Scale", "Reze Bomb Girl Ver.", "Chainsaw Man", "1/7", "high", 240),
        ("eStream", "Scale", "Makima eStream Ver.", "Chainsaw Man", "1/7", "grail", 520),

        # ── Frieren: Beyond Journey's End ──────────────────────────────
        ("Good Smile Company", "Scale", "Frieren Sousou no Frieren Scale", "Frieren: Beyond Journey's End", "1/7", "high", 260),
        ("Alter", "Scale", "Fern Battle Magic Ver.", "Frieren: Beyond Journey's End", "1/7", "high", 220),
        ("Kotobukiya", "Scale", "Frieren Staff Raised Ver.", "Frieren: Beyond Journey's End", "1/7", "high", 240),
        ("Good Smile Company", "Scale", "Himmel Hero Party Ver.", "Frieren: Beyond Journey's End", "1/7", "mid", 180),
        ("Max Factory", "Scale", "Ubel Killing Magic Ver.", "Frieren: Beyond Journey's End", "1/7", "high", 250),

        # ── One Piece — Portrait of Pirates ────────────────────────────
        ("MegaHouse", "Portrait of Pirates", "Monkey D. Luffy Gear 5 PoP", "One Piece", "1/8", "grail", 400),
        ("MegaHouse", "Portrait of Pirates", "Roronoa Zoro King of Hell PoP", "One Piece", "1/8", "high", 300),
        ("MegaHouse", "Portrait of Pirates", "Nico Robin Flower Flower PoP", "One Piece", "1/8", "high", 280),
        ("MegaHouse", "Portrait of Pirates", "Nami Zeus PoP", "One Piece", "1/8", "high", 260),
        ("MegaHouse", "Portrait of Pirates", "Trafalgar Law Room PoP", "One Piece", "1/8", "high", 250),
        ("MegaHouse", "Portrait of Pirates", "Yamato Thunder PoP", "One Piece", "1/8", "high", 300),
        ("MegaHouse", "Portrait of Pirates", "Boa Hancock Love PoP", "One Piece", "1/8", "high", 350),
        ("MegaHouse", "Portrait of Pirates", "Shanks Haki PoP", "One Piece", "1/8", "grail", 400),
        ("Tsume Art", "HQS", "Kaido Dragon Form HQS", "One Piece", "1/7", "grail", 800),
        ("Bandai", "Ichiban Kuji", "Luffy Gear 5 Ichiban Kuji Last One", "One Piece", "Non-scale", "mid", 80),

        # ── Evangelion ─────────────────────────────────────────────────
        ("Kotobukiya", "Scale", "Rei Ayanami Plugsuit 3.0+1.0", "Evangelion", "1/7", "high", 200),
        ("Alter", "Scale", "Asuka Langley Plugsuit 3.0+1.0", "Evangelion", "1/7", "high", 260),
        ("Good Smile Company", "Scale", "Mari Makinami Plugsuit Ver.", "Evangelion", "1/7", "high", 220),
        ("Kotobukiya", "Scale", "Kaworu Nagisa & Shinji Ikari Pair", "Evangelion", "1/7", "high", 280),
        ("FREEing", "B-style", "Rei Ayanami Bunny 3.0+1.0 Ver.", "Evangelion", "1/4", "grail", 450),
        ("Bandai", "Metal Build", "EVA Unit-01 Metal Build", "Evangelion", "Non-scale", "grail", 350),

        # ── Fate/Stay Night & Fate/Grand Order ─────────────────────────
        ("Alter", "Scale", "Saber Alter Shinjuku Ver.", "Fate/Grand Order", "1/7", "grail", 400),
        ("Good Smile Company", "Scale", "Jeanne d'Arc Ruler Ver.", "Fate/Grand Order", "1/7", "high", 280),
        ("Max Factory", "Scale", "Scathach Lancer Ver.", "Fate/Grand Order", "1/7", "high", 300),
        ("Alter", "Scale", "Artoria Pendragon Saber 15th Anniversary", "Fate/Stay Night", "1/7", "grail", 450),
        ("Kotobukiya", "Scale", "Mash Kyrielight Shielder Ver.", "Fate/Grand Order", "1/7", "high", 220),
        ("FREEing", "B-style", "Ereshkigal Bunny Ver.", "Fate/Grand Order", "1/4", "grail", 500),
        ("Aniplex", "Scale", "Ishtar Archer Ver.", "Fate/Grand Order", "1/7", "high", 280),

        # ── Nendoroid Expansions ───────────────────────────────────────
        ("Good Smile Company", "Nendoroid", "Nendoroid Yor Forger Thorn Princess", "Spy x Family", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid Denji", "Chainsaw Man", "Non-scale", "mid", 50),
        ("Good Smile Company", "Nendoroid", "Nendoroid Makima", "Chainsaw Man", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid Frieren", "Frieren: Beyond Journey's End", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid Fern", "Frieren: Beyond Journey's End", "Non-scale", "mid", 50),
        ("Good Smile Company", "Nendoroid", "Nendoroid Gojo Satoru", "Jujutsu Kaisen", "Non-scale", "mid", 60),
        ("Good Smile Company", "Nendoroid", "Nendoroid Sukuna", "Jujutsu Kaisen", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid Luffy Gear 5", "One Piece", "Non-scale", "mid", 60),
        ("Good Smile Company", "Nendoroid", "Nendoroid Rengoku", "Demon Slayer", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid Power", "Chainsaw Man", "Non-scale", "mid", 50),
        ("Good Smile Company", "Nendoroid", "Nendoroid Anya Forger", "Spy x Family", "Non-scale", "mid", 45),
        ("Good Smile Company", "Nendoroid", "Nendoroid Sung Jin-woo", "Solo Leveling", "Non-scale", "mid", 55),

        # ── figma Expansions ───────────────────────────────────────────
        ("Max Factory", "Figma", "figma Guts Berserker Armor Ver.", "Berserk", "Non-scale", "high", 120),
        ("Max Factory", "Figma", "figma Denji Chainsaw Man", "Chainsaw Man", "Non-scale", "mid", 70),
        ("Max Factory", "Figma", "figma Gojo Satoru", "Jujutsu Kaisen", "Non-scale", "mid", 75),
        ("Max Factory", "Figma", "figma Eren Yeager Attack Titan", "Attack on Titan", "Non-scale", "high", 90),
        ("Max Factory", "Figma", "figma Yor Forger Thorn Princess", "Spy x Family", "Non-scale", "mid", 70),
        ("Max Factory", "Figma", "figma Tanjiro Kamado Hinokami", "Demon Slayer", "Non-scale", "mid", 70),
        ("Max Factory", "Figma", "figma Sung Jin-woo Solo Leveling", "Solo Leveling", "Non-scale", "mid", 75),
        ("Max Factory", "Figma", "figma Frieren", "Frieren: Beyond Journey's End", "Non-scale", "mid", 70),

        # ── Prize Figures — Banpresto ──────────────────────────────────
        ("Banpresto", "Grandista", "Vegeta Grandista Manga Dimensions", "Dragon Ball Z", "Non-scale", "mid", 55),
        ("Banpresto", "DXF", "Yor Forger DXF Figure", "Spy x Family", "Non-scale", "standard", 25),
        ("Banpresto", "Grandista", "Zoro Grandista Manga Dimensions", "One Piece", "Non-scale", "mid", 50),
        ("Banpresto", "DXF", "Makima DXF Figure", "Chainsaw Man", "Non-scale", "standard", 30),
        ("Banpresto", "Grandista", "Tanjiro Kamado Grandista", "Demon Slayer", "Non-scale", "standard", 35),
        ("Banpresto", "Vibration Stars", "Yuji Itadori Vibration Stars", "Jujutsu Kaisen", "Non-scale", "standard", 28),
        ("Banpresto", "DXF", "Anya Forger DXF The Movie", "Spy x Family", "Non-scale", "standard", 25),
        ("Banpresto", "Grandista", "Goku Super Saiyan Blue Grandista", "Dragon Ball Super", "Non-scale", "mid", 50),
        ("Banpresto", "Vibration Stars", "Luffy Gear 5 Vibration Stars", "One Piece", "Non-scale", "standard", 35),

        # ── Pop Up Parade Expansions ───────────────────────────────────
        ("Good Smile Company", "Pop Up Parade", "Pop Up Parade Gojo Satoru", "Jujutsu Kaisen", "Non-scale", "standard", 28),
        ("Good Smile Company", "Pop Up Parade", "Pop Up Parade Yor Forger", "Spy x Family", "Non-scale", "standard", 28),
        ("Good Smile Company", "Pop Up Parade", "Pop Up Parade Makima", "Chainsaw Man", "Non-scale", "standard", 28),
        ("Good Smile Company", "Pop Up Parade", "Pop Up Parade Power", "Chainsaw Man", "Non-scale", "standard", 25),
        ("Good Smile Company", "Pop Up Parade", "Pop Up Parade Frieren", "Frieren: Beyond Journey's End", "Non-scale", "standard", 28),
        ("Good Smile Company", "Pop Up Parade", "Pop Up Parade Fern", "Frieren: Beyond Journey's End", "Non-scale", "standard", 25),
        ("Good Smile Company", "Pop Up Parade", "Pop Up Parade Luffy Gear 5", "One Piece", "Non-scale", "standard", 30),
        ("Good Smile Company", "Pop Up Parade", "Pop Up Parade Tanjiro Water Breathing", "Demon Slayer", "Non-scale", "standard", 28),

        # ── Premium Resin — Prime 1 / Tsume ────────────────────────────
        ("Prime 1 Studio", "Premium Masterline", "Luffy Gear 5 Premium Masterline", "One Piece", "1/4", "grail", 1500),
        ("Tsume Art", "HQS+", "Gojo Satoru HQS+ Domain Expansion", "Jujutsu Kaisen", "1/6", "grail", 900),
        ("Prime 1 Studio", "Premium Masterline", "Naruto Baryon Mode Premium Masterline", "Naruto", "1/4", "grail", 1200),
        ("Tsume Art", "HQS", "Tanjiro Hinokami Kagura HQS", "Demon Slayer", "1/6", "grail", 700),
        ("Prime 1 Studio", "Premium Masterline", "Eren Founding Titan Premium Masterline", "Attack on Titan", "1/4", "grail", 1800),

        # ── Misc Popular Series ────────────────────────────────────────
        ("Myethos", "Scale", "Hu Tao Myethos Ver.", "Genshin Impact", "1/7", "high", 300),
        ("Kotobukiya", "Bishoujo", "Marin Kitagawa Bishoujo Ver.", "My Dress-Up Darling", "1/7", "high", 240),
        ("Good Smile Company", "Scale", "Zero Two Idol Ver.", "DARLING in the FRANXX", "1/7", "high", 280),
        ("Alter", "Scale", "Ai Hoshino Idol Costume", "Oshi no Ko", "1/7", "high", 260),
        ("Kotobukiya", "Scale", "Isagi Yoichi Blue Lock Ver.", "Blue Lock", "1/7", "mid", 180),
        ("Bandai", "Ichiban Kuji", "Sung Jin-woo Ichiban Kuji Last One", "Solo Leveling", "Non-scale", "mid", 90),

        # ── More Alter Figures ─────────────────────────────────────────
        ("Alter", "Scale", "Shinobu Oshino Kiss-Shot Ver.", "Monogatari", "1/7", "grail", 400),
        ("Alter", "Scale", "Senjougahara Hitagi Haregi Ver.", "Monogatari", "1/7", "high", 300),
        ("Alter", "Scale", "Takina Inoue Café Ver.", "Lycoris Recoil", "1/7", "high", 240),
        ("Alter", "Scale", "Chisato Nishikigi Lycoris Ver.", "Lycoris Recoil", "1/7", "high", 260),

        # ── Good Smile Company Additional ──────────────────────────────
        ("Good Smile Company", "Scale", "Bocchi Hitori Guitar Ver.", "Bocchi the Rock!", "1/7", "high", 220),
        ("Good Smile Company", "Scale", "Kita Ikuyo Bass Ver.", "Bocchi the Rock!", "1/7", "mid", 180),
        ("Good Smile Company", "Scale", "Oshi no Ko Ruby Idol Stage", "Oshi no Ko", "1/7", "high", 240),
        ("Good Smile Company", "Scale", "Aqua Hoshino Dark Side Ver.", "Oshi no Ko", "1/7", "mid", 180),

        # ── Kotobukiya Additional ──────────────────────────────────────
        ("Kotobukiya", "Bishoujo", "Asuna Yuuki ALO Ver.", "Sword Art Online", "1/7", "high", 200),
        ("Kotobukiya", "Bishoujo", "Sinon GGO Ver.", "Sword Art Online", "1/7", "mid", 160),
        ("Kotobukiya", "Scale", "Nezuko Kamado Blood Demon Art", "Demon Slayer", "1/8", "high", 220),
        ("Kotobukiya", "Scale", "Tanjiro Kamado Water Breathing", "Demon Slayer", "1/8", "high", 200),

        # ── Max Factory Additional ─────────────────────────────────────
        ("Max Factory", "Scale", "Rem Morning Star Ver.", "Re:Zero", "1/7", "high", 260),
        ("Max Factory", "Scale", "Ram Oni Ver.", "Re:Zero", "1/7", "high", 240),
        ("Max Factory", "Scale", "Emilia Crystal Dress Ver.", "Re:Zero", "1/7", "grail", 380),

        # ── FREEing B-style Additional ─────────────────────────────────
        ("FREEing", "B-style", "Zero Two Bunny Ver. 2nd", "DARLING in the FRANXX", "1/4", "grail", 500),
        ("FREEing", "B-style", "Makima Bunny Ver. 2nd", "Chainsaw Man", "1/4", "grail", 520),
        ("FREEing", "B-style", "Frieren Bunny Ver.", "Frieren: Beyond Journey's End", "1/4", "grail", 450),

        # ── Nendoroid Additional ───────────────────────────────────────
        ("Good Smile Company", "Nendoroid", "Nendoroid Bocchi Hitori", "Bocchi the Rock!", "Non-scale", "mid", 50),
        ("Good Smile Company", "Nendoroid", "Nendoroid Chisato Nishikigi", "Lycoris Recoil", "Non-scale", "mid", 50),
        ("Good Smile Company", "Nendoroid", "Nendoroid Takina Inoue", "Lycoris Recoil", "Non-scale", "mid", 45),
        ("Good Smile Company", "Nendoroid", "Nendoroid Ai Hoshino", "Oshi no Ko", "Non-scale", "mid", 55),
        ("Good Smile Company", "Nendoroid", "Nendoroid Ruby Hoshino", "Oshi no Ko", "Non-scale", "mid", 50),
        ("Good Smile Company", "Nendoroid", "Nendoroid Ubel", "Frieren: Beyond Journey's End", "Non-scale", "mid", 50),
        ("Good Smile Company", "Nendoroid", "Nendoroid Stark", "Frieren: Beyond Journey's End", "Non-scale", "mid", 45),
        ("Good Smile Company", "Nendoroid", "Nendoroid Toji Fushiguro", "Jujutsu Kaisen", "Non-scale", "mid", 55),

        # ── figma Additional ───────────────────────────────────────────
        ("Max Factory", "Figma", "figma Makima", "Chainsaw Man", "Non-scale", "mid", 70),
        ("Max Factory", "Figma", "figma Sukuna", "Jujutsu Kaisen", "Non-scale", "mid", 75),
        ("Max Factory", "Figma", "figma Link Tears of the Kingdom", "Zelda", "Non-scale", "mid", 65),
        ("Max Factory", "Figma", "figma Saber Artoria", "Fate/Stay Night", "Non-scale", "mid", 80),

        # ── Robot Spirits / Metal Build ────────────────────────────────
        ("Bandai", "Metal Build", "Strike Freedom Gundam Metal Build", "Gundam SEED", "Non-scale", "grail", 400),
        ("Bandai", "Metal Build", "Wing Gundam Zero EW Metal Build", "Gundam Wing", "Non-scale", "grail", 350),
        ("Bandai", "Robot Spirits", "RX-78-2 Gundam ver. A.N.I.M.E.", "Gundam", "Non-scale", "high", 80),
        ("Bandai", "Robot Spirits", "Zaku II ver. A.N.I.M.E.", "Gundam", "Non-scale", "mid", 60),
        ("Bandai", "Robot Spirits", "Nu Gundam ver. A.N.I.M.E.", "Gundam", "Non-scale", "high", 90),

        # ── S.H.Figuarts Expanded ──────────────────────────────────────
        ("Bandai", "S.H.Figuarts", "Goku Ultra Instinct S.H.Figuarts", "Dragon Ball Super", "Non-scale", "high", 120),
        ("Bandai", "S.H.Figuarts", "Vegeta SSBE S.H.Figuarts", "Dragon Ball Super", "Non-scale", "high", 100),
        ("Bandai", "S.H.Figuarts", "Naruto Sage Mode S.H.Figuarts", "Naruto", "Non-scale", "mid", 70),
        ("Bandai", "S.H.Figuarts", "Tanjiro Kamado S.H.Figuarts", "Demon Slayer", "Non-scale", "mid", 65),
        ("Bandai", "S.H.Figuarts", "Luffy Gear 5 S.H.Figuarts", "One Piece", "Non-scale", "high", 90),

        # ── Myethos / eStream Additional ───────────────────────────────
        ("Myethos", "Scale", "Fischl Myethos Prinzessin Ver.", "Genshin Impact", "1/7", "high", 280),
        ("Myethos", "Scale", "Ganyu Myethos Qilin Ver.", "Genshin Impact", "1/7", "high", 300),
        ("eStream", "Scale", "Emilia eStream Crystal Dress", "Re:Zero", "1/7", "grail", 500),
        ("eStream", "Scale", "Ram eStream Neon City", "Re:Zero", "1/7", "grail", 480),

        # ── Bring Arts / Play Arts Kai ─────────────────────────────────
        ("Square Enix", "Bring Arts", "2B NieR Automata Bring Arts", "NieR Automata", "Non-scale", "high", 120),
        ("Square Enix", "Bring Arts", "Cloud Strife FF7 Remake Bring Arts", "Final Fantasy VII", "Non-scale", "high", 100),
        ("Square Enix", "Play Arts Kai", "Sephiroth FF7 Remake Play Arts Kai", "Final Fantasy VII", "Non-scale", "high", 180),
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
