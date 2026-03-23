"""
Import Action Figures catalog.

Layer 1 (Catalog):  Curated modern action figure lines → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Hasbro GI Joe Classified Series (6-inch, 2020–present)
- Hasbro Power Rangers Lightning Collection (6-inch)
- Hasbro Star Wars Black Series (6-inch)
- Hasbro Star Wars Vintage Collection (3.75-inch)
- NECA 7-inch figures (Predator, Aliens, TMNT, horror, gaming)
- McFarlane DC Multiverse (7-inch)
- McFarlane Spawn (7-inch)
- Super7 Ultimates! (TMNT, Thundercats, Masters of the Universe)
- Mattel Masters of the Universe Origins (5.5-inch)
- Jazwares Fortnite / AEW (6-inch)
- Bandai / Tamashii Nations S.H.Figuarts (Star Wars, Marvel, Dragon Ball)
- Mezco ONE:12 Collective
- Diamond Select Marvel Select
- Jada Toys (Street Fighter, Universal Monsters)
- Mattel WWE Elite
- Boss Fight Studio (Vitruvian H.A.C.K.S., Bucky O'Hare)
- 1000Toys (TOA Heavy Industries, GANTZ:O, Hellboy)
- 610+ items across all lines

Usage:
    python -m pipelines.import_action_figures [--dry-run]
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

CATEGORY = "action_figures"


def _variant_expansion() -> list[dict]:
    """~100 variant items: retailer/convention exclusives, repaints, scale variants,
    deluxe editions, battle-damaged versions, 2-packs, cel-shaded vs movie-accurate."""

    # (brand, line, name, scale, franchise, packaging, exclusive, price_eur)
    variants = [
        # ─── Retailer Exclusives ────────────────────────────────────────
        ("Hasbro", "Black Series", "Boba Fett (Carbonized, Target Exclusive)", '6"', "Star Wars", "Standard", "Target", 38),
        ("Hasbro", "Black Series", "Clone Trooper (212th Battalion, Walmart Exclusive)", '6"', "Star Wars", "Standard", "Walmart", 35),
        ("Hasbro", "Black Series", "Mandalorian Super Commando (Walmart Exclusive)", '6"', "Star Wars", "Standard", "Walmart", 35),
        ("Hasbro", "Black Series", "Heavy Infantry Mandalorian (Amazon Exclusive)", '6"', "Star Wars", "Deluxe", "Amazon", 45),
        ("Hasbro", "Black Series", "Darth Maul (Mandalore, Amazon Exclusive)", '6"', "Star Wars", "Standard", "Amazon", 38),
        ("Hasbro", "Black Series", "Stormtrooper (Carbonized, Target Exclusive)", '6"', "Star Wars", "Standard", "Target", 35),
        ("Hasbro", "Black Series", "General Grievous (Amazon Exclusive)", '6"', "Star Wars", "Deluxe", "Amazon", 48),
        ("Hasbro", "Black Series", "Darth Vader (Carbonized, Walmart Exclusive)", '6"', "Star Wars", "Standard", "Walmart", 38),
        ("Hasbro", "GI Joe Classified", "Crimson Guard (Target Exclusive)", '6"', "GI Joe", "Standard", "Target", 35),
        ("Hasbro", "GI Joe Classified", "Cobra B.A.T. (Amazon Exclusive, 2-Pack)", '6"', "GI Joe", "Deluxe", "Amazon", 55),
        ("McFarlane", "DC Multiverse", "Batman (Gold Label, Amazon Exclusive)", '7"', "DC Comics", "Standard", "Amazon", 32),
        ("McFarlane", "DC Multiverse", "Superman (Gold Label, Target Exclusive)", '7"', "DC Comics", "Standard", "Target", 32),
        ("McFarlane", "DC Multiverse", "The Flash (Gold Label, Walmart Exclusive)", '7"', "DC Comics", "Standard", "Walmart", 30),
        ("NECA", "Ultimate", "Predator (100th Figure, BBTS Exclusive)", '7"', "Predator", "Window Box", "BBTS", 45),
        ("NECA", "Ultimate", "Jason Voorhees (BBTS Exclusive Blood Splatter)", '7"', "Horror", "Window Box", "BBTS", 42),
        ("Super7", "Ultimates!", "TMNT Raphael (Entertainment Earth Exclusive)", '7"', "TMNT", "Standard", "Entertainment Earth", 58),
        ("Super7", "Ultimates!", "MOTU Skeletor (Entertainment Earth Exclusive)", '7"', "MOTU", "Standard", "Entertainment Earth", 55),

        # ─── Convention Exclusives ──────────────────────────────────────
        ("Hasbro", "Black Series", "Clone Trooper (Phase I, SDCC 2023)", '6"', "Star Wars", "Standard", "SDCC", 55),
        ("Hasbro", "Black Series", "Boba Fett (Prototype Armor, SDCC)", '6"', "Star Wars", "Standard", "SDCC", 60),
        ("Hasbro", "Black Series", "Luke Skywalker (X-Wing Pilot, SDCC)", '6"', "Star Wars", "Standard", "SDCC", 52),
        ("Hasbro", "Black Series", "Stormtrooper (Jedha Patrol, NYCC)", '6"', "Star Wars", "Standard", "NYCC", 48),
        ("Hasbro", "Black Series", "Captain Rex (SDCC 2024)", '6"', "Star Wars", "Standard", "SDCC", 65),
        ("Hasbro", "GI Joe Classified", "Snake Eyes (SDCC 2022 Translucent)", '6"', "GI Joe", "Standard", "SDCC", 60),
        ("Hasbro", "GI Joe Classified", "Cobra Commander (NYCC 2023 Chrome)", '6"', "GI Joe", "Standard", "NYCC", 55),
        ("Hasbro", "GI Joe Classified", "Storm Shadow (Pulse Con 2023)", '6"', "GI Joe", "Standard", "Pulse Con", 50),
        ("McFarlane", "DC Multiverse", "Batman (SDCC Gold Edition)", '7"', "DC Comics", "Standard", "SDCC", 45),
        ("McFarlane", "DC Multiverse", "Joker (NYCC Purple Reign)", '7"', "DC Comics", "Standard", "NYCC", 42),
        ("NECA", "Ultimate", "Teenage Mutant Ninja Turtles 4-Pack (SDCC Exclusive)", '7"', "TMNT", "Deluxe", "SDCC", 120),
        ("Super7", "Ultimates!", "MOTU He-Man (Filmation, SDCC Glow)", '7"', "MOTU", "Standard", "SDCC", 65),
        ("Mezco", "ONE:12 Collective", "Gomez (SDCC Midnight Agent)", '6"', "Original", "Deluxe", "SDCC", 110),
        ("Mezco", "ONE:12 Collective", "Batman (NYCC Dark Detective)", '6"', "DC Comics", "Deluxe", "NYCC", 125),

        # ─── Battle-Damaged / Weathered / Clean Versions ────────────────
        ("Hasbro", "Black Series", "Boba Fett (Battle-Damaged)", '6"', "Star Wars", "Standard", "", 35),
        ("Hasbro", "Black Series", "The Mandalorian (Weathered Beskar)", '6"', "Star Wars", "Standard", "", 32),
        ("Hasbro", "Black Series", "Darth Vader (Battle-Damaged, ROTJ)", '6"', "Star Wars", "Standard", "", 35),
        ("Hasbro", "Black Series", "Stormtrooper (Battle-Damaged Remnant)", '6"', "Star Wars", "Standard", "", 30),
        ("Hasbro", "Black Series", "Clone Trooper (Phase II Weathered)", '6"', "Star Wars", "Standard", "", 32),
        ("McFarlane", "DC Multiverse", "Batman (Battle-Damaged, Dark Knight)", '7"', "DC Comics", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Superman (Battle-Damaged, Doomsday)", '7"', "DC Comics", "Standard", "", 25),
        ("McFarlane", "Spawn", "Spawn (Burned, Battle-Damaged)", '7"', "Spawn", "Standard", "", 28),
        ("NECA", "Ultimate", "Predator (Battle-Damaged, Jungle Hunter)", '7"', "Predator", "Window Box", "", 38),
        ("NECA", "Ultimate", "Alien Warrior (Battle-Damaged)", '7"', "Aliens", "Window Box", "", 38),
        ("Hasbro", "GI Joe Classified", "Snake Eyes (Weathered, Arashikage)", '6"', "GI Joe", "Standard", "", 35),
        ("McFarlane", "DC Multiverse", "Joker (Arkham Asylum, Weathered)", '7"', "DC Comics", "Standard", "", 25),

        # ─── Different Scales (Same Character) ─────────────────────────
        ("Hasbro", "Black Series", "The Mandalorian (12-inch, Beskar)", '12"', "Star Wars", "Deluxe", "", 55),
        ("Hasbro", "Black Series", "Darth Vader (12-inch)", '12"', "Star Wars", "Deluxe", "", 55),
        ("Hasbro", "Black Series", "Boba Fett (12-inch)", '12"', "Star Wars", "Deluxe", "", 55),
        ("Hasbro", "Black Series", "Stormtrooper (12-inch)", '12"', "Star Wars", "Deluxe", "", 48),
        ("Hasbro", "Vintage Collection", "Darth Vader (3.75-inch, Kenner Retro)", '3.75"', "Star Wars", "Standard", "", 18),
        ("McFarlane", "DC Multiverse", "Batman (12-inch Mega, Rebirth)", '12"', "DC Comics", "Deluxe", "", 48),
        ("McFarlane", "DC Multiverse", "Superman (12-inch Mega, Action Comics)", '12"', "DC Comics", "Deluxe", "", 48),
        ("McFarlane", "DC Multiverse", "Joker (12-inch Mega, Death of the Family)", '12"', "DC Comics", "Deluxe", "", 48),
        ("NECA", "Quarter Scale", "Predator (Jungle Hunter, 18-inch)", '18"', "Predator", "Deluxe", "", 120),
        ("NECA", "Quarter Scale", "Alien Big Chap (18-inch)", '18"', "Alien", "Deluxe", "", 125),

        # ─── Repaint / Redeco Variants ──────────────────────────────────
        ("Hasbro", "Black Series", "Clone Trooper (Coruscant Guard, Red)", '6"', "Star Wars", "Standard", "", 32),
        ("Hasbro", "Black Series", "Clone Trooper (Shock Trooper, Red)", '6"', "Star Wars", "Standard", "", 35),
        ("Hasbro", "Black Series", "Clone Trooper (442nd Siege Battalion)", '6"', "Star Wars", "Standard", "", 32),
        ("Hasbro", "Black Series", "Scout Trooper (Gaming Greats, Green Camo)", '6"', "Star Wars", "Standard", "", 30),
        ("Hasbro", "GI Joe Classified", "Cobra Viper (Python Patrol Repaint)", '6"', "GI Joe", "Standard", "", 32),
        ("Hasbro", "GI Joe Classified", "Crimson Guard (Ivory Repaint)", '6"', "GI Joe", "Standard", "", 35),
        ("McFarlane", "DC Multiverse", "Batman (Earth-2 Blue & Grey)", '7"', "DC Comics", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Batman (Rebirth, Black & Grey Repaint)", '7"', "DC Comics", "Standard", "", 22),
        ("McFarlane", "Spawn", "Spawn (Blue Variant Repaint)", '7"', "Spawn", "Standard", "", 28),
        ("McFarlane", "Spawn", "Spawn (Crimson Repaint)", '7"', "Spawn", "Standard", "", 28),
        ("Super7", "Ultimates!", "TMNT Leonardo (Toon, Metallic Repaint)", '7"', "TMNT", "Standard", "", 55),
        ("Super7", "Ultimates!", "MOTU He-Man (Gold Repaint, Filmation)", '7"', "MOTU", "Standard", "", 58),

        # ─── 2-Pack vs Single Figure Versions ──────────────────────────
        ("Hasbro", "Black Series", "Darth Vader & Obi-Wan Kenobi 2-Pack", '6"', "Star Wars", "Deluxe", "", 55),
        ("Hasbro", "Black Series", "Luke Skywalker & Yoda (Dagobah) 2-Pack", '6"', "Star Wars", "Deluxe", "", 50),
        ("Hasbro", "Black Series", "Han Solo & Chewbacca 2-Pack", '6"', "Star Wars", "Deluxe", "", 52),
        ("Hasbro", "Black Series", "Ahsoka & Captain Rex 2-Pack", '6"', "Star Wars", "Deluxe", "Hasbro Pulse", 60),
        ("Hasbro", "GI Joe Classified", "Snake Eyes & Storm Shadow 2-Pack", '6"', "GI Joe", "Deluxe", "", 52),
        ("Hasbro", "GI Joe Classified", "Flint & Lady Jaye 2-Pack", '6"', "GI Joe", "Deluxe", "Target", 55),
        ("McFarlane", "DC Multiverse", "Batman & Superman 2-Pack (Dark Knight Returns)", '7"', "DC Comics", "Deluxe", "", 42),
        ("McFarlane", "DC Multiverse", "Batman & Joker 2-Pack (Arkham Asylum)", '7"', "DC Comics", "Deluxe", "", 42),
        ("NECA", "Ultimate", "Dutch & Predator 2-Pack (Predator)", '7"', "Predator", "Deluxe", "", 65),
        ("NECA", "Ultimate", "Ripley & Alien Queen 2-Pack", '7"', "Aliens", "Deluxe", "", 70),

        # ─── Cel-Shaded / Cartoon-Accurate vs Movie-Accurate ───────────
        ("McFarlane", "DC Multiverse", "Batman (Animated Series, Cel-Shaded)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Joker (Animated Series, Cel-Shaded)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Harley Quinn (Animated Series, Cel-Shaded)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Superman (Animated Series, Cel-Shaded)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Robin (Animated Series, Cel-Shaded)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Mr. Freeze (Animated Series, Cel-Shaded)", '7"', "DC Comics", "Standard", "", 28),
        ("Hasbro", "Black Series", "Clone Trooper (Clone Wars, Cartoon-Accurate)", '6"', "Star Wars", "Standard", "", 30),
        ("Hasbro", "Black Series", "Anakin Skywalker (Clone Wars, Cartoon-Accurate)", '6"', "Star Wars", "Standard", "", 32),
        ("Hasbro", "Black Series", "Obi-Wan Kenobi (Clone Wars, Cartoon-Accurate)", '6"', "Star Wars", "Standard", "", 32),

        # ─── Deluxe Editions (More Accessories) ─────────────────────────
        ("Hasbro", "Black Series", "Luke Skywalker (Jedi Knight, Deluxe with Throne)", '6"', "Star Wars", "Deluxe", "", 42),
        ("Hasbro", "Black Series", "Obi-Wan Kenobi (Padawan, Deluxe)", '6"', "Star Wars", "Deluxe", "", 40),
        ("Hasbro", "Black Series", "Darth Maul (Deluxe, Sith Speeder)", '6"', "Star Wars", "Deluxe", "", 48),
        ("Hasbro", "Black Series", "Captain Rex (Deluxe, with Jetpack)", '6"', "Star Wars", "Deluxe", "", 45),
        ("Hasbro", "GI Joe Classified", "Duke (Deluxe, Tiger Force)", '6"', "GI Joe", "Deluxe", "", 42),
        ("Hasbro", "GI Joe Classified", "Roadblock (Deluxe, Heavy Weapons)", '6"', "GI Joe", "Deluxe", "", 42),
        ("McFarlane", "DC Multiverse", "Batman (Deluxe, with Bat-Signal Base)", '7"', "DC Comics", "Deluxe", "", 38),
        ("McFarlane", "DC Multiverse", "Aquaman (Deluxe, with Trident & Base)", '7"', "DC Comics", "Deluxe", "", 35),
        ("NECA", "Ultimate", "Freddy Krueger (Deluxe, Dream Sequence)", '7"', "Horror", "Deluxe", "", 42),
        ("NECA", "Ultimate", "Michael Myers (Deluxe, Halloween 2018)", '7"', "Horror", "Deluxe", "", 42),

        # ─── Additional Scale & Exclusive Variants ──────────────────────
        ("Bandai", "S.H.Figuarts", "Goku (Ultra Instinct, Event Exclusive Silver)", '6"', "Dragon Ball", "Standard", "SDCC", 85),
        ("Bandai", "S.H.Figuarts", "Vegeta (Super Saiyan Blue, Repaint)", '6"', "Dragon Ball", "Standard", "", 60),
        ("Medicom", "MAFEX", "Spider-Man (Cel-Shaded, Comic Ver.)", '6"', "Marvel", "Standard", "", 85),
        ("Medicom", "MAFEX", "Batman (Animated Series, Cel-Shaded)", '6"', "DC Comics", "Standard", "", 88),
        ("Good Smile", "Figma", "Link (Twilight Princess, Deluxe with Epona)", '6"', "Zelda", "Deluxe", "", 110),
        ("Good Smile", "Figma", "Guts (Berserk: Berserker Armor, Repaint)", '6"', "Berserk", "Standard", "", 90),
    ]

    result = []
    for brand, line, name, scale, franchise, packaging, exclusive, price in variants:
        result.append({
            "brand": brand,
            "line": line,
            "name": name,
            "scale": scale,
            "franchise": franchise,
            "packaging_type": packaging,
            "retailer_exclusive": exclusive,
            "price_eur": price,
        })
    return result


def get_curated_catalog() -> list[dict]:
    """Curated 610+ modern action figures catalog: GI Joe Classified, Power Rangers
    Lightning, Star Wars Black Series, NECA, McFarlane, Super7, MOTU Origins, WWE Elite,
    Boss Fight Studio, 1000Toys, etc."""

    # (brand, line, name, scale, franchise, packaging, exclusive, price_eur)
    # scale: 3.75", 6", 7", 12"
    # packaging: Standard, Window Box, Archive, Deluxe, HasLab

    items = [
        # ─── Hasbro Star Wars Black Series (6") ──────────────────────
        ("Hasbro", "Black Series", "The Mandalorian (Beskar)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "The Mandalorian & Grogu", '6"', "Star Wars", "Deluxe", "", 38),
        ("Hasbro", "Black Series", "Din Djarin (Morak)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Darth Vader (ESB)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Darth Vader (ROTJ)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Darth Vader (Obi-Wan Kenobi)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Darth Vader (Duel's End)", '6"', "Star Wars", "Standard", "Hasbro Pulse", 35),
        ("Hasbro", "Black Series", "Boba Fett (ESB)", '6"', "Star Wars", "Standard", "", 30),
        ("Hasbro", "Black Series", "Boba Fett (ROTJ)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Boba Fett (Throne Room)", '6"', "Star Wars", "Deluxe", "", 38),
        ("Hasbro", "Black Series", "Luke Skywalker (Jedi Knight ROTJ)", '6"', "Star Wars", "Standard", "", 30),
        ("Hasbro", "Black Series", "Luke Skywalker (Endor)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Luke Skywalker (Yavin Ceremony)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Luke Skywalker (Dagobah)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Luke Skywalker (Snowspeeder Pilot)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Han Solo (ANH)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Han Solo (Bespin)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Han Solo (Endor)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Princess Leia (ANH)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Princess Leia (Boushh)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Princess Leia (Endor)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Chewbacca", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Obi-Wan Kenobi (Wandering Jedi)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Obi-Wan Kenobi (ROTS)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Anakin Skywalker (ROTS)", '6"', "Star Wars", "Standard", "", 30),
        ("Hasbro", "Black Series", "Clone Trooper (Phase II)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Clone Trooper (501st)", '6"', "Star Wars", "Standard", "", 35),
        ("Hasbro", "Black Series", "Clone Trooper (332nd Ahsoka)", '6"', "Star Wars", "Standard", "", 30),
        ("Hasbro", "Black Series", "Clone Commander Cody", '6"', "Star Wars", "Standard", "", 32),
        ("Hasbro", "Black Series", "Captain Rex", '6"', "Star Wars", "Standard", "", 38),
        ("Hasbro", "Black Series", "Ahsoka Tano (Clone Wars)", '6"', "Star Wars", "Standard", "", 35),
        ("Hasbro", "Black Series", "Ahsoka Tano (Rebels)", '6"', "Star Wars", "Standard", "", 32),
        ("Hasbro", "Black Series", "Ahsoka Tano (Ahsoka Series)", '6"', "Star Wars", "Standard", "", 30),
        ("Hasbro", "Black Series", "Grand Admiral Thrawn", '6"', "Star Wars", "Standard", "", 38),
        ("Hasbro", "Black Series", "Emperor Palpatine (Throne Room)", '6"', "Star Wars", "Deluxe", "", 42),
        ("Hasbro", "Black Series", "Stormtrooper", '6"', "Star Wars", "Standard", "", 25),
        ("Hasbro", "Black Series", "Scout Trooper", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Death Trooper", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Shoretrooper", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Range Trooper", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Incinerator Trooper", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Purge Trooper", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Dark Trooper", '6"', "Star Wars", "Standard", "", 32),
        ("Hasbro", "Black Series", "Cad Bane (Book of Boba Fett)", '6"', "Star Wars", "Standard", "", 32),
        ("Hasbro", "Black Series", "Bo-Katan Kryze", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Moff Gideon", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Fennec Shand", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Cobb Vanth", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Darth Maul", '6"', "Star Wars", "Standard", "", 35),
        ("Hasbro", "Black Series", "General Grievous", '6"', "Star Wars", "Deluxe", "", 42),
        ("Hasbro", "Black Series", "Count Dooku", '6"', "Star Wars", "Standard", "", 30),
        ("Hasbro", "Black Series", "Jango Fett", '6"', "Star Wars", "Standard", "", 30),
        ("Hasbro", "Black Series", "Padme Amidala", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Qui-Gon Jinn", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Mace Windu", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Kit Fisto", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Plo Koon", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Reva (Third Sister)", '6"', "Star Wars", "Standard", "", 25),
        ("Hasbro", "Black Series", "Grand Inquisitor", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Fifth Brother", '6"', "Star Wars", "Standard", "", 25),
        ("Hasbro", "Black Series", "Sabine Wren (Ahsoka)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Hera Syndulla (Ahsoka)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Ezra Bridger (Ahsoka)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Baylan Skoll", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Shin Hati", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Huyang", '6"', "Star Wars", "Standard", "", 28),

        # ─── Hasbro Star Wars Vintage Collection (3.75") ─────────────
        ("Hasbro", "Vintage Collection", "The Mandalorian (VC166)", '3.75"', "Star Wars", "Standard", "", 18),
        ("Hasbro", "Vintage Collection", "Grogu (VC191)", '3.75"', "Star Wars", "Standard", "", 15),
        ("Hasbro", "Vintage Collection", "Boba Fett (VC186)", '3.75"', "Star Wars", "Standard", "", 18),
        ("Hasbro", "Vintage Collection", "Luke Skywalker (Jedi Knight, VC175)", '3.75"', "Star Wars", "Standard", "", 18),
        ("Hasbro", "Vintage Collection", "Darth Vader (VC178)", '3.75"', "Star Wars", "Standard", "", 18),
        ("Hasbro", "Vintage Collection", "Han Solo (VC50 reissue)", '3.75"', "Star Wars", "Standard", "", 18),
        ("Hasbro", "Vintage Collection", "Princess Leia (VC111 reissue)", '3.75"', "Star Wars", "Standard", "", 18),
        ("Hasbro", "Vintage Collection", "Stormtrooper (VC140 reissue)", '3.75"', "Star Wars", "Standard", "", 15),
        ("Hasbro", "Vintage Collection", "Clone Commander Wolffe (VC168)", '3.75"', "Star Wars", "Standard", "", 22),
        ("Hasbro", "Vintage Collection", "Clone Trooper (VC15 reissue)", '3.75"', "Star Wars", "Standard", "", 18),
        ("Hasbro", "Vintage Collection", "Ahsoka Tano (Clone Wars VC102 reissue)", '3.75"', "Star Wars", "Standard", "", 22),
        ("Hasbro", "Vintage Collection", "Captain Rex (VC182)", '3.75"', "Star Wars", "Standard", "", 22),
        ("Hasbro", "Vintage Collection", "Razor Crest Vehicle", '3.75"', "Star Wars", "Deluxe", "", 85),
        ("Hasbro", "Vintage Collection", "Imperial Troop Transport", '3.75"', "Star Wars", "Deluxe", "", 55),
        ("Hasbro", "Vintage Collection", "Nevarro Cantina Playset", '3.75"', "Star Wars", "Deluxe", "", 65),

        # ─── Hasbro GI Joe Classified Series (6") ────────────────────
        ("Hasbro", "GI Joe Classified", "Snake Eyes (#02)", '6"', "GI Joe", "Standard", "", 32),
        ("Hasbro", "GI Joe Classified", "Snake Eyes & Timber (#52)", '6"', "GI Joe", "Deluxe", "", 48),
        ("Hasbro", "GI Joe Classified", "Storm Shadow (#05)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Cobra Commander (#06)", '6"', "GI Joe", "Standard", "", 30),
        ("Hasbro", "GI Joe Classified", "Cobra Commander (Regal Variant)", '6"', "GI Joe", "Standard", "Target", 42),
        ("Hasbro", "GI Joe Classified", "Duke (#04)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Scarlett (#01)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Roadblock (#01)", '6"', "GI Joe", "Standard", "", 25),
        ("Hasbro", "GI Joe Classified", "Destro (#03)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Baroness (#19)", '6"', "GI Joe", "Standard", "", 32),
        ("Hasbro", "GI Joe Classified", "Baroness with COIL Cycle", '6"', "GI Joe", "Deluxe", "Target", 55),
        ("Hasbro", "GI Joe Classified", "Firefly (#21)", '6"', "GI Joe", "Standard", "", 30),
        ("Hasbro", "GI Joe Classified", "Zartan (#23)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Flint (#26)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Lady Jaye (#25)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Major Bludd (#27)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Crimson Guard (#08)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Cobra B.A.T. (#33)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Cobra Officer (#37)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Tomax & Xamot 2-Pack", '6"', "GI Joe", "Deluxe", "Amazon", 58),
        ("Hasbro", "GI Joe Classified", "Serpentor & Air Chariot", '6"', "GI Joe", "Deluxe", "", 52),
        ("Hasbro", "GI Joe Classified", "Croc Master & Fiona", '6"', "GI Joe", "Deluxe", "", 45),
        ("Hasbro", "GI Joe Classified", "Dreadnok Buzzer", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Dreadnok Ripper", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Dreadnok Torch", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Stalker (#34)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Spirit Iron-Knife (#36)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Dr. Mindbender", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Cobra Viper", '6"', "GI Joe", "Standard", "", 30),

        # ─── Hasbro Power Rangers Lightning Collection (6") ──────────
        ("Hasbro", "PR Lightning", "Mighty Morphin Red Ranger", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "PR Lightning", "Mighty Morphin Green Ranger", '6"', "Power Rangers", "Standard", "", 35),
        ("Hasbro", "PR Lightning", "Mighty Morphin White Ranger", '6"', "Power Rangers", "Standard", "", 32),
        ("Hasbro", "PR Lightning", "Mighty Morphin Blue Ranger", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "PR Lightning", "Mighty Morphin Pink Ranger", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "PR Lightning", "Mighty Morphin Black Ranger", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "PR Lightning", "Mighty Morphin Yellow Ranger", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "PR Lightning", "Lord Zedd", '6"', "Power Rangers", "Standard", "", 30),
        ("Hasbro", "PR Lightning", "Rita Repulsa", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "PR Lightning", "Goldar", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "PR Lightning", "Dino Charge Red Ranger", '6"', "Power Rangers", "Standard", "", 25),
        ("Hasbro", "PR Lightning", "SPD Shadow Ranger", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "PR Lightning", "Zeo Gold Ranger", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "PR Lightning", "In Space Red Ranger", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "PR Lightning", "Time Force Red Ranger", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "PR Lightning", "Drakkon (Shattered Grid)", '6"', "Power Rangers", "Standard", "Hasbro Pulse", 38),
        ("Hasbro", "PR Lightning", "Psycho Rangers 5-Pack", '6"', "Power Rangers", "Deluxe", "Amazon", 110),

        # ─── NECA 7" Figures ──────────────────────────────────────────
        ("NECA", "Ultimate", "Predator (Jungle Hunter, Ultimate)", '7"', "Predator", "Window Box", "", 35),
        ("NECA", "Ultimate", "Predator (City Hunter, Ultimate)", '7"', "Predator", "Window Box", "", 35),
        ("NECA", "Ultimate", "Predator (Elder, Ultimate)", '7"', "Predator", "Window Box", "", 35),
        ("NECA", "Ultimate", "Predator (Fugitive, Ultimate)", '7"', "Predator", "Window Box", "", 35),
        ("NECA", "Ultimate", "Alien Warrior (Ultimate)", '7"', "Aliens", "Window Box", "", 35),
        ("NECA", "Ultimate", "Alien Queen (Deluxe)", '7"', "Aliens", "Deluxe", "", 85),
        ("NECA", "Ultimate", "Ripley (Aliens Ultimate)", '7"', "Aliens", "Window Box", "", 35),
        ("NECA", "Ultimate", "Newt (Aliens Ultimate)", '7"', "Aliens", "Window Box", "", 32),
        ("NECA", "Cartoon", "TMNT Leonardo (Toon)", '7"', "TMNT", "Window Box", "", 38),
        ("NECA", "Cartoon", "TMNT Donatello (Toon)", '7"', "TMNT", "Window Box", "", 38),
        ("NECA", "Cartoon", "TMNT Raphael (Toon)", '7"', "TMNT", "Window Box", "", 38),
        ("NECA", "Cartoon", "TMNT Michelangelo (Toon)", '7"', "TMNT", "Window Box", "", 38),
        ("NECA", "Cartoon", "TMNT Shredder (Toon)", '7"', "TMNT", "Window Box", "", 35),
        ("NECA", "Cartoon", "TMNT Krang (Toon)", '7"', "TMNT", "Window Box", "", 35),
        ("NECA", "Cartoon", "TMNT Bebop & Rocksteady 2-Pack", '7"', "TMNT", "Deluxe", "", 65),
        ("NECA", "1990 Movie", "TMNT Leonardo (1990 Movie)", '7"', "TMNT", "Window Box", "", 35),
        ("NECA", "1990 Movie", "TMNT Shredder (1990 Movie)", '7"', "TMNT", "Window Box", "", 35),
        ("NECA", "1990 Movie", "TMNT Foot Soldier (1990 Movie)", '7"', "TMNT", "Window Box", "", 30),
        ("NECA", "Ultimate", "Jason Voorhees (Friday 13th Part 3)", '7"', "Horror", "Window Box", "", 35),
        ("NECA", "Ultimate", "Jason Voorhees (Friday 13th Part 4)", '7"', "Horror", "Window Box", "", 35),
        ("NECA", "Ultimate", "Freddy Krueger (Dream Warriors)", '7"', "Horror", "Window Box", "", 35),
        ("NECA", "Ultimate", "Michael Myers (Halloween 2018)", '7"', "Horror", "Window Box", "", 35),
        ("NECA", "Ultimate", "Chucky (Childs Play)", '7"', "Horror", "Window Box", "", 32),
        ("NECA", "Ultimate", "Pennywise (IT 2017)", '7"', "Horror", "Window Box", "", 35),
        ("NECA", "Ultimate", "Leatherface (Texas Chainsaw)", '7"', "Horror", "Window Box", "", 35),
        ("NECA", "Gargoyles", "Goliath", '7"', "Gargoyles", "Window Box", "", 35),
        ("NECA", "Gargoyles", "Demona", '7"', "Gargoyles", "Window Box", "", 35),
        ("NECA", "Gargoyles", "Thailog", '7"', "Gargoyles", "Window Box", "", 35),
        ("NECA", "Toony Terrors", "Elvira", '7"', "Horror", "Standard", "", 22),
        ("NECA", "Toony Terrors", "Beetlejuice", '7"', "Horror", "Standard", "", 22),

        # ─── McFarlane DC Multiverse (7") ─────────────────────────────
        ("McFarlane", "DC Multiverse", "Batman (Hush)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Batman (Dark Knight Returns)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Batman (The Batman 2022)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Batman (Arkham Knight)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Batman (DC Rebirth)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Superman (Action Comics #1000)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Superman (Unchained)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Wonder Woman (Todd Edition)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Flash (Rebirth)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Aquaman (Endless Winter)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Green Lantern (John Stewart)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Joker (DC Rebirth)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Joker (The Batman Who Laughs)", '7"', "DC", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Harley Quinn (Rebirth)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Deathstroke", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Red Hood", '7"', "DC", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Nightwing", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Robin (Tim Drake)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Batgirl (Rebirth)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Darkseid (Mega Fig)", '7"', "DC", "Deluxe", "", 48),
        ("McFarlane", "DC Multiverse", "Gorilla Grodd (Mega Fig)", '7"', "DC", "Deluxe", "", 45),
        ("McFarlane", "DC Multiverse", "Bane (Mega Fig)", '7"', "DC", "Deluxe", "", 45),
        ("McFarlane", "DC Multiverse", "Clayface (Mega Fig)", '7"', "DC", "Deluxe", "", 45),
        ("McFarlane", "DC Multiverse", "Superman vs Doomsday 2-Pack", '7"', "DC", "Deluxe", "", 55),

        # ─── McFarlane Spawn (7") ─────────────────────────────────────
        ("McFarlane", "Spawn", "Spawn (Mortal Kombat 11)", '7"', "Spawn", "Standard", "", 22),
        ("McFarlane", "Spawn", "Spawn (Classic)", '7"', "Spawn", "Standard", "", 25),
        ("McFarlane", "Spawn", "Spawn (Gunslinger)", '7"', "Spawn", "Standard", "", 25),
        ("McFarlane", "Spawn", "Violator (Mega Fig)", '7"', "Spawn", "Deluxe", "", 42),
        ("McFarlane", "Spawn", "She-Spawn", '7"', "Spawn", "Standard", "", 22),
        ("McFarlane", "Spawn", "Mandarin Spawn", '7"', "Spawn", "Standard", "", 22),
        ("McFarlane", "Spawn", "Reaper", '7"', "Spawn", "Standard", "", 22),
        ("McFarlane", "Spawn", "Medieval Spawn", '7"', "Spawn", "Standard", "", 25),

        # ─── Super7 Ultimates! ────────────────────────────────────────
        ("Super7", "Ultimates!", "TMNT Leonardo (Ultimates)", '7"', "TMNT", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "TMNT Donatello (Ultimates)", '7"', "TMNT", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "TMNT Raphael (Ultimates)", '7"', "TMNT", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "TMNT Michelangelo (Ultimates)", '7"', "TMNT", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "TMNT Shredder (Ultimates)", '7"', "TMNT", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "TMNT Baxter Stockman (Ultimates)", '7"', "TMNT", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Thundercats Lion-O (Ultimates)", '7"', "Thundercats", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Thundercats Mumm-Ra (Ultimates)", '7"', "Thundercats", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Thundercats Panthro (Ultimates)", '7"', "Thundercats", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Thundercats Cheetara (Ultimates)", '7"', "Thundercats", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "MOTU He-Man (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "MOTU Skeletor (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "MOTU Trap Jaw (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "MOTU Mer-Man (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "MOTU Teela (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "MOTU She-Ra (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Silverhawks Quicksilver (Ultimates)", '7"', "Silverhawks", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Conan the Barbarian (Ultimates)", '7"', "Conan", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "G.I. Joe Snake Eyes (Ultimates)", '7"', "GI Joe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "G.I. Joe Cobra Commander (Ultimates)", '7"', "GI Joe", "Deluxe", "", 55),

        # ─── Mattel MOTU Origins (5.5") ───────────────────────────────
        ("Mattel", "MOTU Origins", "He-Man (Origins)", '5.5"', "Masters of the Universe", "Standard", "", 18),
        ("Mattel", "MOTU Origins", "Skeletor (Origins)", '5.5"', "Masters of the Universe", "Standard", "", 18),
        ("Mattel", "MOTU Origins", "Battle Cat (Origins)", '5.5"', "Masters of the Universe", "Deluxe", "", 28),
        ("Mattel", "MOTU Origins", "Man-At-Arms (Origins)", '5.5"', "Masters of the Universe", "Standard", "", 18),
        ("Mattel", "MOTU Origins", "Teela (Origins)", '5.5"', "Masters of the Universe", "Standard", "", 18),
        ("Mattel", "MOTU Origins", "Beast Man (Origins)", '5.5"', "Masters of the Universe", "Standard", "", 18),
        ("Mattel", "MOTU Origins", "Evil-Lyn (Origins)", '5.5"', "Masters of the Universe", "Standard", "", 18),
        ("Mattel", "MOTU Origins", "Trap Jaw (Origins)", '5.5"', "Masters of the Universe", "Standard", "", 18),
        ("Mattel", "MOTU Origins", "Hordak (Origins)", '5.5"', "Masters of the Universe", "Standard", "", 18),
        ("Mattel", "MOTU Origins", "Faker (Origins)", '5.5"', "Masters of the Universe", "Standard", "Target", 22),
        ("Mattel", "MOTU Origins", "Castle Grayskull (Origins)", '5.5"', "Masters of the Universe", "Deluxe", "", 75),
        ("Mattel", "MOTU Origins", "Snake Mountain (Origins)", '5.5"', "Masters of the Universe", "Deluxe", "", 120),

        # ─── Mezco ONE:12 Collective ──────────────────────────────────
        ("Mezco", "ONE:12", "Spider-Man (ONE:12)", '6"', "Marvel", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Wolverine (ONE:12)", '6"', "Marvel", "Deluxe", "", 80),
        ("Mezco", "ONE:12", "Punisher (ONE:12)", '6"', "Marvel", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Batman (Sovereign Knight, ONE:12)", '6"', "DC", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Batman (Supreme Knight, ONE:12)", '6"', "DC", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Joker (ONE:12)", '6"', "DC", "Deluxe", "", 80),
        ("Mezco", "ONE:12", "Doctor Strange (ONE:12)", '6"', "Marvel", "Deluxe", "", 80),
        ("Mezco", "ONE:12", "Deadpool (ONE:12)", '6"', "Marvel", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Captain America (ONE:12)", '6"', "Marvel", "Deluxe", "", 80),
        ("Mezco", "ONE:12", "Flash (ONE:12)", '6"', "DC", "Deluxe", "", 80),
        ("Mezco", "ONE:12", "Popeye (ONE:12)", '6"', "Classic", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Conan (ONE:12)", '6"', "Conan", "Deluxe", "", 85),

        # ─── S.H.Figuarts (Bandai/Tamashii Nations) ──────────────────
        ("Bandai", "S.H.Figuarts", "The Mandalorian (SHF)", '6"', "Star Wars", "Deluxe", "", 65),
        ("Bandai", "S.H.Figuarts", "Darth Vader (SHF, ROTJ)", '6"', "Star Wars", "Deluxe", "", 70),
        ("Bandai", "S.H.Figuarts", "Boba Fett (SHF, Book of Boba Fett)", '6"', "Star Wars", "Deluxe", "", 65),
        ("Bandai", "S.H.Figuarts", "Clone Trooper Phase II (SHF)", '6"', "Star Wars", "Deluxe", "", 65),
        ("Bandai", "S.H.Figuarts", "Stormtrooper (SHF, ANH)", '6"', "Star Wars", "Deluxe", "", 60),
        ("Bandai", "S.H.Figuarts", "Iron Man Mk 50 (SHF)", '6"', "Marvel", "Deluxe", "", 70),
        ("Bandai", "S.H.Figuarts", "Spider-Man (NWH Integrated, SHF)", '6"', "Marvel", "Deluxe", "", 65),
        ("Bandai", "S.H.Figuarts", "Captain America (Endgame, SHF)", '6"', "Marvel", "Deluxe", "", 70),
        ("Bandai", "S.H.Figuarts", "Thor (Endgame, SHF)", '6"', "Marvel", "Deluxe", "", 65),
        ("Bandai", "S.H.Figuarts", "Thanos (Endgame, SHF)", '6"', "Marvel", "Deluxe", "", 80),

        # ─── Diamond Select (Marvel Select, 7") ──────────────────────
        ("Diamond Select", "Marvel Select", "Spider-Man (Marvel Select)", '7"', "Marvel", "Standard", "", 30),
        ("Diamond Select", "Marvel Select", "Venom (Marvel Select)", '7"', "Marvel", "Standard", "", 32),
        ("Diamond Select", "Marvel Select", "Thanos (Marvel Select)", '7"', "Marvel", "Standard", "", 35),
        ("Diamond Select", "Marvel Select", "Hulk (Marvel Select)", '7"', "Marvel", "Standard", "", 32),
        ("Diamond Select", "Marvel Select", "Wolverine (Marvel Select)", '7"', "Marvel", "Standard", "", 30),
        ("Diamond Select", "Marvel Select", "Carnage (Marvel Select)", '7"', "Marvel", "Standard", "", 35),
        ("Diamond Select", "Marvel Select", "Iron Man (Marvel Select)", '7"', "Marvel", "Standard", "", 30),
        ("Diamond Select", "Marvel Select", "Captain America (Marvel Select)", '7"', "Marvel", "Standard", "", 30),
        ("Diamond Select", "Marvel Select", "Doctor Strange (Marvel Select)", '7"', "Marvel", "Standard", "", 30),
        ("Diamond Select", "Marvel Select", "Deadpool (Marvel Select)", '7"', "Marvel", "Standard", "", 30),

        # ─── Jada Toys ────────────────────────────────────────────────
        ("Jada Toys", "Street Fighter", "Ryu (Street Fighter)", '6"', "Street Fighter", "Standard", "", 22),
        ("Jada Toys", "Street Fighter", "Chun-Li (Street Fighter)", '6"', "Street Fighter", "Standard", "", 22),
        ("Jada Toys", "Street Fighter", "M. Bison (Street Fighter)", '6"', "Street Fighter", "Standard", "", 22),
        ("Jada Toys", "Street Fighter", "Ken (Street Fighter)", '6"', "Street Fighter", "Standard", "", 22),
        ("Jada Toys", "Universal Monsters", "Frankenstein (Universal Monsters)", '6"', "Horror", "Standard", "", 22),
        ("Jada Toys", "Universal Monsters", "Dracula (Universal Monsters)", '6"', "Horror", "Standard", "", 22),
        ("Jada Toys", "Universal Monsters", "Wolfman (Universal Monsters)", '6"', "Horror", "Standard", "", 22),
        ("Jada Toys", "Universal Monsters", "Creature from Black Lagoon", '6"', "Horror", "Standard", "", 22),

        # ─── Jazwares / AEW ───────────────────────────────────────────
        ("Jazwares", "AEW Unrivaled", "Kenny Omega", '6"', "AEW", "Standard", "", 22),
        ("Jazwares", "AEW Unrivaled", "Jon Moxley", '6"', "AEW", "Standard", "", 22),
        ("Jazwares", "AEW Unrivaled", "MJF", '6"', "AEW", "Standard", "", 22),
        ("Jazwares", "AEW Unrivaled", "Chris Jericho", '6"', "AEW", "Standard", "", 22),
        ("Jazwares", "AEW Unrivaled", "Cody Rhodes", '6"', "AEW", "Standard", "", 25),
        ("Jazwares", "AEW Unrivaled", "Sting", '6"', "AEW", "Standard", "", 28),
        ("Jazwares", "Fortnite", "Skull Trooper", '6"', "Fortnite", "Standard", "", 18),
        ("Jazwares", "Fortnite", "Peely", '6"', "Fortnite", "Standard", "", 18),
        ("Jazwares", "Fortnite", "Meowscles", '6"', "Fortnite", "Standard", "", 18),

        # ─── Boss Fight Studio ────────────────────────────────────────
        ("Boss Fight Studio", "Vitruvian H.A.C.K.S.", "Spartan Warrior", '3.75"', "Historical", "Standard", "", 22),
        ("Boss Fight Studio", "Vitruvian H.A.C.K.S.", "Medusa", '3.75"', "Mythology", "Standard", "", 22),
        ("Boss Fight Studio", "Vitruvian H.A.C.K.S.", "Skeleton Knight", '3.75"', "Fantasy", "Standard", "", 22),
        ("Boss Fight Studio", "Hero H.A.C.K.S.", "Flash Gordon", '3.75"', "Flash Gordon", "Standard", "", 22),
        ("Boss Fight Studio", "Hero H.A.C.K.S.", "Ming the Merciless", '3.75"', "Flash Gordon", "Standard", "", 22),

        # ─── Additional Star Wars Action Figures ──────────────────────
        ("Hasbro", "Black Series", "Darth Revan", '6"', "Star Wars", "Standard", "GameStop", 45),
        ("Hasbro", "Black Series", "Darth Nihilus", '6"', "Star Wars", "Standard", "GameStop", 42),
        ("Hasbro", "Black Series", "Jaina Solo (Legends)", '6"', "Star Wars", "Standard", "", 40),
        ("Hasbro", "Black Series", "Bastila Shan", '6"', "Star Wars", "Standard", "GameStop", 38),
        ("Hasbro", "Black Series", "HK-47", '6"', "Star Wars", "Standard", "GameStop", 38),
        ("Hasbro", "Black Series", "Clone Trooper (Kamino)", '6"', "Star Wars", "Standard", "Walgreens", 35),
        ("Hasbro", "Black Series", "Shadow Trooper", '6"', "Star Wars", "Standard", "GameStop", 32),
        ("Hasbro", "Black Series", "Purge Trooper (Electrostaff)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Tech (Bad Batch)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Hunter (Bad Batch)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Wrecker (Bad Batch)", '6"', "Star Wars", "Deluxe", "", 38),
        ("Hasbro", "Black Series", "Crosshair (Bad Batch)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Echo (Bad Batch)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Omega (Bad Batch)", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Asajj Ventress", '6"', "Star Wars", "Standard", "", 30),
        ("Hasbro", "Black Series", "Savage Opress", '6"', "Star Wars", "Standard", "", 30),
        ("Hasbro", "Black Series", "Pre Vizsla", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Gar Saxon", '6"', "Star Wars", "Standard", "", 28),
        ("Hasbro", "Black Series", "Mandalorian Super Commando", '6"', "Star Wars", "Standard", "", 28),

        # ─── Hasbro Indiana Jones Adventure Series (6") ──────────────
        ("Hasbro", "Indiana Jones Adventure Series", "Indiana Jones (Raiders)", '6"', "Indiana Jones", "Standard", "", 28),
        ("Hasbro", "Indiana Jones Adventure Series", "Indiana Jones (Dial of Destiny)", '6"', "Indiana Jones", "Standard", "", 28),
        ("Hasbro", "Indiana Jones Adventure Series", "Marion Ravenwood", '6"', "Indiana Jones", "Standard", "", 28),
        ("Hasbro", "Indiana Jones Adventure Series", "Short Round", '6"', "Indiana Jones", "Standard", "", 28),
        ("Hasbro", "Indiana Jones Adventure Series", "Sallah", '6"', "Indiana Jones", "Standard", "", 28),
        ("Hasbro", "Indiana Jones Adventure Series", "Dr. Henry Jones Sr.", '6"', "Indiana Jones", "Standard", "", 28),
        ("Hasbro", "Indiana Jones Adventure Series", "Helena Shaw", '6"', "Indiana Jones", "Standard", "", 28),

        # ─── NECA Predator & Alien (Additional) ──────────────────────
        ("NECA", "Ultimate", "City Hunter Predator", '7"', "Predator", "Window Box", "", 38),
        ("NECA", "Ultimate", "Jungle Hunter Predator", '7"', "Predator", "Window Box", "", 38),
        ("NECA", "Ultimate", "Elder Predator", '7"', "Predator", "Window Box", "", 38),
        ("NECA", "Ultimate", "Fugitive Predator", '7"', "Predator", "Window Box", "", 38),
        ("NECA", "Ultimate", "Warrior Alien (Brown)", '7"', "Aliens", "Window Box", "", 35),
        ("NECA", "Ultimate", "Alien Queen", '7"', "Aliens", "Deluxe", "", 85),
        ("NECA", "Ultimate", "Newborn Alien", '7"', "Aliens", "Window Box", "", 35),
        ("NECA", "Ultimate", "Dog Alien (Alien 3)", '7"', "Aliens", "Window Box", "", 35),

        # ─── NECA Horror (Additional) ────────────────────────────────
        ("NECA", "Ultimate", "Chucky (Child's Play)", '7"', "Child's Play", "Window Box", "", 38),
        ("NECA", "Ultimate", "Pennywise (IT 1990)", '7"', "IT", "Window Box", "", 35),
        ("NECA", "Ultimate", "Ghostface (Scream)", '7"', "Scream", "Window Box", "", 35),
        ("NECA", "Ultimate", "Pinhead (Hellraiser)", '7"', "Hellraiser", "Window Box", "", 40),
        ("NECA", "Ultimate", "Ash Williams (Evil Dead 2)", '7"', "Evil Dead", "Window Box", "", 38),

        # ─── McFarlane DC Multiverse (Additional) ────────────────────
        ("McFarlane", "DC Multiverse", "Batman Beyond", '7"', "DC Comics", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Batgirl (Cassandra Cain)", '7"', "DC Comics", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Green Arrow (Oliver Queen)", '7"', "DC Comics", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Black Adam", '7"', "DC Comics", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Shazam (New 52)", '7"', "DC Comics", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Darkseid (Armored)", '7"', "DC Comics", "Deluxe", "", 45),
        ("McFarlane", "DC Multiverse", "Doomsday", '7"', "DC Comics", "Deluxe", "", 45),
        ("McFarlane", "DC Multiverse", "Killer Croc", '7"', "DC Comics", "Deluxe", "", 45),
        ("McFarlane", "DC Multiverse", "Swamp Thing", '7"', "DC Comics", "Deluxe", "", 48),
        ("McFarlane", "DC Multiverse", "Gorilla Grodd", '7"', "DC Comics", "Deluxe", "", 48),

        # ─── Hasbro Marvel Legends (Modern Action Figures) ────────────
        ("Hasbro", "Marvel Legends", "Spider-Man 2099", '6"', "Marvel", "Standard", "", 25),
        ("Hasbro", "Marvel Legends", "Deadpool (Classic)", '6"', "Marvel", "Standard", "", 25),
        ("Hasbro", "Marvel Legends", "Wolverine (Brown Costume)", '6"', "Marvel", "Standard", "", 25),
        ("Hasbro", "Marvel Legends", "Captain America (Sam Wilson)", '6"', "Marvel", "Standard", "", 25),
        ("Hasbro", "Marvel Legends", "Iron Spider", '6"', "Marvel", "Standard", "", 25),
        ("Hasbro", "Marvel Legends", "Moon Knight", '6"', "Marvel", "Standard", "", 28),
        ("Hasbro", "Marvel Legends", "Ms. Marvel (Kamala Khan)", '6"', "Marvel", "Standard", "", 25),
        ("Hasbro", "Marvel Legends", "Scarlet Witch (WandaVision)", '6"', "Marvel", "Standard", "", 28),
        ("Hasbro", "Marvel Legends", "Loki (Disney+)", '6"', "Marvel", "Standard", "", 28),
        ("Hasbro", "Marvel Legends", "Kang the Conqueror", '6"', "Marvel", "Standard", "", 25),
        ("Hasbro", "Marvel Legends", "Namor (Wakanda Forever)", '6"', "Marvel", "Standard", "", 25),
        ("Hasbro", "Marvel Legends", "She-Hulk", '6"', "Marvel", "Standard", "", 25),

        # ─── Spin Master DC (4" & 12") ───────────────────────────────
        ("Spin Master", "DC 4-inch", "Batman (Rebirth)", '4"', "DC Comics", "Standard", "", 12),
        ("Spin Master", "DC 4-inch", "Superman (Rebirth)", '4"', "DC Comics", "Standard", "", 12),
        ("Spin Master", "DC 4-inch", "The Flash (Rebirth)", '4"', "DC Comics", "Standard", "", 12),
        ("Spin Master", "DC 12-inch", "Batman (Armored)", '12"', "DC Comics", "Standard", "", 25),
        ("Spin Master", "DC 12-inch", "Superman (Man of Steel)", '12"', "DC Comics", "Standard", "", 25),

        # ─── Hiya Toys Exquisite Mini / Super (3.75") ─────────────────
        ("Hiya Toys", "Exquisite Mini", "Alien Warrior", '3.75"', "Aliens", "Standard", "", 22),
        ("Hiya Toys", "Exquisite Mini", "Predator (Jungle)", '3.75"', "Predator", "Standard", "", 22),
        ("Hiya Toys", "Exquisite Mini", "RoboCop", '3.75"', "RoboCop", "Standard", "", 22),
        ("Hiya Toys", "Exquisite Mini", "Judge Dredd", '3.75"', "Judge Dredd", "Standard", "", 22),
        ("Hiya Toys", "Exquisite Super", "Godzilla (2019)", '7"', "Godzilla", "Standard", "", 55),
        ("Hiya Toys", "Exquisite Super", "Kong (GvK)", '7"', "Godzilla", "Standard", "", 55),
        ("Hiya Toys", "Exquisite Mini", "Colonial Marine (Aliens)", '3.75"', "Aliens", "Standard", "", 22),
        ("Hiya Toys", "Exquisite Mini", "T-800 (Terminator 2)", '3.75"', "Terminator", "Standard", "", 22),
        ("Hiya Toys", "Exquisite Super", "Mechagodzilla (2021)", '7"', "Godzilla", "Standard", "", 55),

        # ─── NECA (Additional) ──────────────────────────────────────
        ("NECA", "Ultimate", "Predator (Stalker)", '7"', "Predator", "Window Box", "", 35),
        ("NECA", "Ultimate", "Predator (Guardian)", '7"', "Predator", "Window Box", "", 38),
        ("NECA", "Ultimate", "Predator (Lost Tribe Warrior)", '7"', "Predator", "Window Box", "", 35),
        ("NECA", "Ultimate", "Predator (Alpha)", '7"', "Predator", "Window Box", "", 42),
        ("NECA", "Ultimate", "Predator (Lasershot)", '7"', "Predator", "Window Box", "", 35),
        ("NECA", "Ultimate", "Alien Big Chap (1979)", '7"', "Aliens", "Window Box", "", 38),
        ("NECA", "Ultimate", "Alien (Resurrection Warrior)", '7"', "Aliens", "Window Box", "", 35),
        ("NECA", "Ultimate", "Bishop (Aliens)", '7"', "Aliens", "Window Box", "", 35),
        ("NECA", "Ultimate", "Hicks (Aliens)", '7"', "Aliens", "Window Box", "", 35),
        ("NECA", "Ultimate", "Hudson (Aliens)", '7"', "Aliens", "Window Box", "", 35),
        ("NECA", "1990 Movie", "TMNT Raphael (1990 Movie)", '7"', "TMNT", "Window Box", "", 35),
        ("NECA", "1990 Movie", "TMNT Donatello (1990 Movie)", '7"', "TMNT", "Window Box", "", 35),
        ("NECA", "1990 Movie", "TMNT Michelangelo (1990 Movie)", '7"', "TMNT", "Window Box", "", 35),
        ("NECA", "1990 Movie", "TMNT Casey Jones (1990 Movie)", '7"', "TMNT", "Window Box", "", 38),
        ("NECA", "1990 Movie", "TMNT Splinter (1990 Movie)", '7"', "TMNT", "Window Box", "", 38),
        ("NECA", "1990 Movie", "TMNT Tokka & Rahzar 2-Pack", '7"', "TMNT", "Deluxe", "", 65),
        ("NECA", "Ultimate", "Kratos (God of War 2018)", '7"', "God of War", "Window Box", "", 38),
        ("NECA", "Ultimate", "Kratos & Atreus 2-Pack", '7"', "God of War", "Deluxe", "", 65),
        ("NECA", "Ultimate", "Pennywise (IT Chapter Two)", '7"', "IT", "Window Box", "", 35),
        ("NECA", "Ultimate", "Pennywise (Dancing Clown)", '7"', "IT", "Window Box", "", 35),
        ("NECA", "Ultimate", "Michael Myers (Halloween Kills)", '7"', "Horror", "Window Box", "", 35),
        ("NECA", "Ultimate", "Jason Voorhees (Part 6)", '7"', "Horror", "Window Box", "", 35),
        ("NECA", "Ultimate", "Freddy Krueger (New Nightmare)", '7"', "Horror", "Window Box", "", 35),
        ("NECA", "Ultimate", "Godzilla (1954)", '7"', "Godzilla", "Window Box", "", 38),
        ("NECA", "Ultimate", "Godzilla (1989)", '7"', "Godzilla", "Window Box", "", 38),
        ("NECA", "Ultimate", "Godzilla vs Kong (2021)", '7"', "Godzilla", "Window Box", "", 35),
        ("NECA", "Ultimate", "King Kong (Skull Island)", '7"', "King Kong", "Window Box", "", 38),
        ("NECA", "Ultimate", "Gremlin (Ultimate)", '7"', "Gremlins", "Window Box", "", 32),
        ("NECA", "Ultimate", "Stripe (Gremlins)", '7"', "Gremlins", "Window Box", "", 32),
        ("NECA", "Ultimate", "E.T. (Ultimate)", '7"', "E.T.", "Window Box", "", 35),
        ("NECA", "Gargoyles", "Brooklyn", '7"', "Gargoyles", "Window Box", "", 35),
        ("NECA", "Gargoyles", "Lexington", '7"', "Gargoyles", "Window Box", "", 35),
        ("NECA", "Gargoyles", "Broadway", '7"', "Gargoyles", "Window Box", "", 35),
        ("NECA", "Gargoyles", "Hudson", '7"', "Gargoyles", "Window Box", "", 35),
        ("NECA", "Gargoyles", "Xanatos (Steel Clan)", '7"', "Gargoyles", "Window Box", "", 38),
        ("NECA", "Ultimate", "RoboCop (Ultimate)", '7"', "RoboCop", "Window Box", "", 38),
        ("NECA", "Ultimate", "ED-209 (RoboCop)", '7"', "RoboCop", "Deluxe", "", 65),
        ("NECA", "Ultimate", "Chucky (Bride of Chucky)", '7"', "Child's Play", "Window Box", "", 35),
        ("NECA", "Ultimate", "Tiffany (Bride of Chucky)", '7"', "Child's Play", "Window Box", "", 35),
        ("NECA", "Ultimate", "Ahab Predator", '7"', "Predator", "Window Box", "", 42),

        # ─── McFarlane DC Multiverse (Additional) ──────────────────
        ("McFarlane", "DC Multiverse", "Batman (Zero Year)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Batman (Three Jokers)", '7"', "DC", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Batman (Flashpoint Thomas Wayne)", '7"', "DC", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Batman (Knightfall)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Batman (Last Knight on Earth)", '7"', "DC", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Batman (White Knight)", '7"', "DC", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Superman (Injustice 2)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Superman (Red Son)", '7"', "DC", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Superman (Kingdom Come)", '7"', "DC", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Flash (Injustice 2)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Flash (Flashpoint)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Reverse Flash", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Aquaman (JL Endless Winter)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Aquaman (Flashpoint)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Green Lantern (Hal Jordan Rebirth)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Sinestro", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Joker (Three Jokers Criminal)", '7"', "DC", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Joker (Three Jokers Comedian)", '7"', "DC", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Joker (Clown Prince, Rebirth)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Catwoman (Rebirth)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Batwoman", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Supergirl", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Robin (Damian Wayne)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Blue Beetle (Jaime Reyes)", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Booster Gold", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Lex Luthor (Power Suit, Mega Fig)", '7"', "DC", "Deluxe", "", 48),
        ("McFarlane", "DC Multiverse", "Solomon Grundy (Mega Fig)", '7"', "DC", "Deluxe", "", 48),
        ("McFarlane", "DC Multiverse", "Brainiac", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Mr. Freeze", '7"', "DC", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Poison Ivy", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Scarecrow", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Ra's al Ghul", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Black Manta", '7"', "DC", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Deathstroke (Arkham Origins)", '7"', "DC", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Constantine", '7"', "DC", "Standard", "", 22),

        # ─── Mezco ONE:12 (Additional) ─────────────────────────────
        ("Mezco", "ONE:12", "Batman (Ascending Knight, ONE:12)", '6"', "DC", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Batman (Gotham by Gaslight, ONE:12)", '6"', "DC", "Deluxe", "", 90),
        ("Mezco", "ONE:12", "Judge Dredd (ONE:12)", '6"', "Judge Dredd", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Doc Nocturnal (ONE:12)", '6"', "Mezco Original", "Deluxe", "", 90),
        ("Mezco", "ONE:12", "Gomez (Agent, ONE:12)", '6"', "Mezco Original", "Deluxe", "", 95),
        ("Mezco", "ONE:12", "Rumble Society Baron Bends (ONE:12)", '6"', "Mezco Original", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Moon Knight (ONE:12)", '6"', "Marvel", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Green Goblin (ONE:12)", '6"', "Marvel", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Iron Man (ONE:12)", '6"', "Marvel", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Magneto (ONE:12)", '6"', "Marvel", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Cable (ONE:12)", '6"', "Marvel", "Deluxe", "", 80),
        ("Mezco", "ONE:12", "Blade (ONE:12)", '6"', "Marvel", "Deluxe", "", 80),
        ("Mezco", "ONE:12", "Harley Quinn (ONE:12)", '6"', "DC", "Deluxe", "", 80),
        ("Mezco", "ONE:12", "Catwoman (ONE:12)", '6"', "DC", "Deluxe", "", 80),
        ("Mezco", "ONE:12", "Two-Face (ONE:12)", '6"', "DC", "Deluxe", "", 80),
        ("Mezco", "ONE:12", "John Wick (ONE:12)", '6"', "John Wick", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Frankenstein (ONE:12)", '6"', "Horror", "Deluxe", "", 80),
        ("Mezco", "ONE:12", "Universal Monsters Nosferatu (ONE:12)", '6"', "Horror", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Ghostbusters Set (ONE:12)", '6"', "Ghostbusters", "Deluxe", "", 320),
        ("Mezco", "ONE:12", "Rorschach (ONE:12)", '6"', "DC", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Aquaman (ONE:12)", '6"', "DC", "Deluxe", "", 80),
        ("Mezco", "ONE:12", "Superman (ONE:12)", '6"', "DC", "Deluxe", "", 85),
        ("Mezco", "ONE:12", "Darkseid (ONE:12)", '6"', "DC", "Deluxe", "", 95),
        ("Mezco", "ONE:12", "Thanos (ONE:12)", '6"', "Marvel", "Deluxe", "", 90),
        ("Mezco", "ONE:12", "King Kong (Mezco ONE:12)", '6"', "King Kong", "Deluxe", "", 85),

        # ─── Super7 Ultimates! (Additional) ────────────────────────
        ("Super7", "Ultimates!", "TMNT Foot Soldier (Ultimates)", '7"', "TMNT", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "TMNT Krang (Ultimates)", '7"', "TMNT", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "TMNT Splinter (Ultimates)", '7"', "TMNT", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "TMNT Bebop (Ultimates)", '7"', "TMNT", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "TMNT Rocksteady (Ultimates)", '7"', "TMNT", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "TMNT Metalhead (Ultimates)", '7"', "TMNT", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Thundercats Tygra (Ultimates)", '7"', "Thundercats", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Thundercats Slithe (Ultimates)", '7"', "Thundercats", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Thundercats WilyKit & WilyKat (Ultimates)", '7"', "Thundercats", "Deluxe", "", 65),
        ("Super7", "Ultimates!", "Silverhawks Steelwill (Ultimates)", '7"', "Silverhawks", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Silverhawks Steelheart (Ultimates)", '7"', "Silverhawks", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Silverhawks Bluegrass (Ultimates)", '7"', "Silverhawks", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Silverhawks Mon*Star (Ultimates)", '7"', "Silverhawks", "Deluxe", "", 60),
        ("Super7", "Ultimates!", "Conan War Paint (Ultimates)", '7"', "Conan", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "Thulsa Doom (Ultimates)", '7"', "Conan", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "G.I. Joe Storm Shadow (Ultimates)", '7"', "GI Joe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "G.I. Joe Destro (Ultimates)", '7"', "GI Joe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "G.I. Joe Baroness (Ultimates)", '7"', "GI Joe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "MOTU Buzz-Off (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "MOTU Man-At-Arms (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "MOTU Hordak (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "MOTU Evil-Lyn (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "MOTU Beast Man (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 55),
        ("Super7", "Ultimates!", "MOTU Ram Man (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 58),
        ("Super7", "Ultimates!", "MOTU Faker (Ultimates)", '7"', "Masters of the Universe", "Deluxe", "", 55),

        # ─── Bandai / Tamashii Nations S.H.Figuarts (Additional) ───
        ("Bandai", "S.H.Figuarts", "Goku Super Saiyan (SHF)", '6"', "Dragon Ball", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Goku Ultra Instinct (SHF)", '6"', "Dragon Ball", "Deluxe", "", 60),
        ("Bandai", "S.H.Figuarts", "Vegeta Super Saiyan (SHF)", '6"', "Dragon Ball", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Vegeta SSGSS (SHF)", '6"', "Dragon Ball", "Deluxe", "", 60),
        ("Bandai", "S.H.Figuarts", "Frieza Final Form (SHF)", '6"', "Dragon Ball", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Cell Perfect Form (SHF)", '6"', "Dragon Ball", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Broly (SHF, DBS)", '6"', "Dragon Ball", "Deluxe", "", 65),
        ("Bandai", "S.H.Figuarts", "Piccolo (SHF)", '6"', "Dragon Ball", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Gohan Beast (SHF)", '6"', "Dragon Ball", "Deluxe", "", 58),
        ("Bandai", "S.H.Figuarts", "Trunks Super Saiyan (SHF)", '6"', "Dragon Ball", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Naruto Uzumaki (SHF)", '6"', "Naruto", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Sasuke Uchiha (SHF)", '6"', "Naruto", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Kakashi Hatake (SHF)", '6"', "Naruto", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Itachi Uchiha (SHF)", '6"', "Naruto", "Deluxe", "", 60),
        ("Bandai", "S.H.Figuarts", "Naruto Sage Mode (SHF)", '6"', "Naruto", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Luffy Gear 5 (SHF)", '6"', "One Piece", "Deluxe", "", 60),
        ("Bandai", "S.H.Figuarts", "Zoro (SHF)", '6"', "One Piece", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Sanji (SHF)", '6"', "One Piece", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Kamen Rider Zero-One (SHF)", '6"', "Kamen Rider", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Kamen Rider Build (SHF)", '6"', "Kamen Rider", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Kamen Rider Revice (SHF)", '6"', "Kamen Rider", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Kamen Rider Geats (SHF)", '6"', "Kamen Rider", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Kamen Rider Den-O (SHF)", '6"', "Kamen Rider", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Kamen Rider Kuuga (SHF)", '6"', "Kamen Rider", "Deluxe", "", 60),
        ("Bandai", "S.H.Figuarts", "Kamen Rider W (SHF)", '6"', "Kamen Rider", "Deluxe", "", 58),
        ("Bandai", "S.H.Figuarts", "Kamen Rider OOO (SHF)", '6"', "Kamen Rider", "Deluxe", "", 55),
        ("Bandai", "S.H.Figuarts", "Hulk (Endgame, SHF)", '6"', "Marvel", "Deluxe", "", 70),
        ("Bandai", "S.H.Figuarts", "Doctor Strange (NWH, SHF)", '6"', "Marvel", "Deluxe", "", 65),
        ("Bandai", "S.H.Figuarts", "Obi-Wan Kenobi (SHF, ROTS)", '6"', "Star Wars", "Deluxe", "", 65),
        ("Bandai", "S.H.Figuarts", "Anakin Skywalker (SHF, ROTS)", '6"', "Star Wars", "Deluxe", "", 65),

        # ─── Figma / Good Smile ────────────────────────────────────
        ("Good Smile", "Figma", "Link (Figma, Tears of the Kingdom)", '6"', "Zelda", "Deluxe", "", 65),
        ("Good Smile", "Figma", "Link (Figma, Twilight Princess)", '6"', "Zelda", "Deluxe", "", 70),
        ("Good Smile", "Figma", "Zelda (Figma, TotK)", '6"', "Zelda", "Deluxe", "", 65),
        ("Good Smile", "Figma", "Guts (Figma, Berserker Armor)", '6"', "Berserk", "Deluxe", "", 80),
        ("Good Smile", "Figma", "Guts (Figma, Black Swordsman)", '6"', "Berserk", "Deluxe", "", 75),
        ("Good Smile", "Figma", "Griffith (Figma, Berserk)", '6"', "Berserk", "Deluxe", "", 70),
        ("Good Smile", "Figma", "Tanjiro Kamado (Figma)", '6"', "Demon Slayer", "Deluxe", "", 60),
        ("Good Smile", "Figma", "Nezuko Kamado (Figma)", '6"', "Demon Slayer", "Deluxe", "", 60),
        ("Good Smile", "Figma", "Zenitsu Agatsuma (Figma)", '6"', "Demon Slayer", "Deluxe", "", 58),
        ("Good Smile", "Figma", "Rengoku (Figma, Demon Slayer)", '6"', "Demon Slayer", "Deluxe", "", 60),
        ("Good Smile", "Figma", "Eren Yeager (Figma)", '6"', "Attack on Titan", "Deluxe", "", 65),
        ("Good Smile", "Figma", "Levi Ackerman (Figma)", '6"', "Attack on Titan", "Deluxe", "", 70),
        ("Good Smile", "Figma", "Mikasa Ackerman (Figma)", '6"', "Attack on Titan", "Deluxe", "", 60),
        ("Good Smile", "Figma", "Samus Aran (Figma, Dread)", '6"', "Metroid", "Deluxe", "", 65),
        ("Good Smile", "Figma", "Solid Snake (Figma, MGS2)", '6"', "Metal Gear", "Deluxe", "", 70),
        ("Good Smile", "Figma", "2B (Figma, NieR Automata)", '6"', "NieR", "Deluxe", "", 75),
        ("Good Smile", "Figma", "Saber Altria (Figma, Fate)", '6"', "Fate", "Deluxe", "", 65),
        ("Good Smile", "Figma", "Astro Boy (Figma)", '6"', "Astro Boy", "Deluxe", "", 55),
        ("Good Smile", "Figma", "Denji (Figma, Chainsaw Man)", '6"', "Chainsaw Man", "Deluxe", "", 60),
        ("Good Smile", "Figma", "Power (Figma, Chainsaw Man)", '6"', "Chainsaw Man", "Deluxe", "", 60),

        # ─── Jazwares / Jakks (Additional) ─────────────────────────
        ("Jazwares", "Fortnite", "Drift", '6"', "Fortnite", "Standard", "", 18),
        ("Jazwares", "Fortnite", "Raven", '6"', "Fortnite", "Standard", "", 18),
        ("Jazwares", "Fortnite", "Ragnarok", '6"', "Fortnite", "Standard", "", 18),
        ("Jazwares", "Fortnite", "Black Knight", '6"', "Fortnite", "Standard", "", 20),
        ("Jazwares", "Fortnite", "Midas", '6"', "Fortnite", "Standard", "", 18),
        ("Jazwares", "Fortnite", "Jonesy", '6"', "Fortnite", "Standard", "", 15),
        ("Jazwares", "AEW Unrivaled", "Hangman Adam Page", '6"', "AEW", "Standard", "", 22),
        ("Jazwares", "AEW Unrivaled", "Orange Cassidy", '6"', "AEW", "Standard", "", 22),
        ("Jazwares", "AEW Unrivaled", "Jade Cargill", '6"', "AEW", "Standard", "", 22),
        ("Jazwares", "AEW Unrivaled", "Wardlow", '6"', "AEW", "Standard", "", 22),
        ("Jazwares", "Halo", "Master Chief (Halo Infinite)", '6"', "Halo", "Standard", "", 22),
        ("Jazwares", "Halo", "Spartan MK VII", '6"', "Halo", "Standard", "", 20),
        ("Jazwares", "Halo", "The Arbiter", '6"', "Halo", "Standard", "", 22),
        ("Jakks Pacific", "Halo", "Master Chief (12-inch)", '12"', "Halo", "Standard", "", 25),
        ("Jakks Pacific", "Sonic", "Sonic the Hedgehog (4-inch)", '4"', "Sonic", "Standard", "", 12),

        # ─── Diamond Select (Additional) ───────────────────────────
        ("Diamond Select", "Marvel Select", "Colossus (Marvel Select)", '7"', "Marvel", "Standard", "", 32),
        ("Diamond Select", "Marvel Select", "Magneto (Marvel Select)", '7"', "Marvel", "Standard", "", 32),
        ("Diamond Select", "Marvel Select", "Silver Surfer (Marvel Select)", '7"', "Marvel", "Standard", "", 32),
        ("Diamond Select", "Marvel Select", "Doctor Doom (Marvel Select)", '7"', "Marvel", "Standard", "", 32),
        ("Diamond Select", "Marvel Select", "Abomination (Marvel Select)", '7"', "Marvel", "Standard", "", 35),
        ("Diamond Select", "Marvel Select", "Juggernaut (Marvel Select)", '7"', "Marvel", "Standard", "", 35),
        ("Diamond Select", "Marvel Select", "Green Goblin (Marvel Select)", '7"', "Marvel", "Standard", "", 32),
        ("Diamond Select", "DC Gallery", "Batman (DC Gallery PVC)", '7"', "DC", "Standard", "", 45),
        ("Diamond Select", "DC Gallery", "Joker (DC Gallery PVC)", '7"', "DC", "Standard", "", 42),
        ("Diamond Select", "DC Gallery", "Harley Quinn (DC Gallery PVC)", '7"', "DC", "Standard", "", 42),
        ("Diamond Select", "Star Trek Select", "Kirk (Star Trek Select)", '7"', "Star Trek", "Standard", "", 28),
        ("Diamond Select", "Star Trek Select", "Spock (Star Trek Select)", '7"', "Star Trek", "Standard", "", 28),
        ("Diamond Select", "Star Trek Select", "Picard (Star Trek Select)", '7"', "Star Trek", "Standard", "", 28),
        ("Diamond Select", "John Wick Gallery", "John Wick (Gallery PVC)", '7"', "John Wick", "Standard", "", 45),
        ("Diamond Select", "John Wick Gallery", "John Wick Chapter 2 (Gallery)", '7"', "John Wick", "Standard", "", 45),

        # ─── Hasbro GI Joe Classified (Additional) ───────────────────
        ("Hasbro", "GI Joe Classified", "Gung-Ho (#07)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Beachhead (#10)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Lady Jaye (Retro Card)", '6"', "GI Joe", "Standard", "Walmart", 35),
        ("Hasbro", "GI Joe Classified", "Quick Kick (#44)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Cover Girl (#59)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Shipwreck (#70)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Snow Job (#14)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Wild Bill (#41)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Python Patrol Cobra Officer", '6"', "GI Joe", "Standard", "Amazon", 35),
        ("Hasbro", "GI Joe Classified", "Nemesis Enforcer", '6"', "GI Joe", "Standard", "", 30),
        ("Hasbro", "GI Joe Classified", "Cobra Eel (#58)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Recondo (#62)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Mutt & Junkyard", '6"', "GI Joe", "Deluxe", "", 42),
        ("Hasbro", "GI Joe Classified", "Bazooka (#68)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Night Force Tunnel Rat", '6"', "GI Joe", "Standard", "Target", 35),

        # ─── Spin Master DC (Additional) ─────────────────────────────
        ("Spin Master", "DC 4-inch", "Robin (Tim Drake)", '4"', "DC Comics", "Standard", "", 12),
        ("Spin Master", "DC 4-inch", "Joker (Classic)", '4"', "DC Comics", "Standard", "", 12),
        ("Spin Master", "DC 4-inch", "Harley Quinn", '4"', "DC Comics", "Standard", "", 12),
        ("Spin Master", "DC 4-inch", "Nightwing", '4"', "DC Comics", "Standard", "", 12),
        ("Spin Master", "DC 4-inch", "Batgirl", '4"', "DC Comics", "Standard", "", 12),
        ("Spin Master", "DC 4-inch", "Catwoman", '4"', "DC Comics", "Standard", "", 12),
        ("Spin Master", "DC 4-inch", "Riddler", '4"', "DC Comics", "Standard", "", 12),
        ("Spin Master", "DC 12-inch", "Penguin", '12"', "DC Comics", "Standard", "", 25),
        ("Spin Master", "DC 12-inch", "Bane", '12"', "DC Comics", "Standard", "", 28),
        ("Spin Master", "DC 12-inch", "Aquaman", '12"', "DC Comics", "Standard", "", 25),

        # ─── Mattel WWE Elite ────────────────────────────────────────
        ("Mattel", "WWE Elite", "Stone Cold Steve Austin (Elite)", '6"', "WWE", "Standard", "", 28),
        ("Mattel", "WWE Elite", "The Rock (Elite)", '6"', "WWE", "Standard", "", 30),
        ("Mattel", "WWE Elite", "John Cena (Elite)", '6"', "WWE", "Standard", "", 28),
        ("Mattel", "WWE Elite", "Undertaker (Elite)", '6"', "WWE", "Deluxe", "", 35),
        ("Mattel", "WWE Elite", "Mankind (Elite)", '6"', "WWE", "Standard", "", 30),
        ("Mattel", "WWE Elite", "Triple H (Elite)", '6"', "WWE", "Standard", "", 28),
        ("Mattel", "WWE Elite", "Shawn Michaels (Elite)", '6"', "WWE", "Standard", "", 30),
        ("Mattel", "WWE Elite", "Randy Savage (Elite)", '6"', "WWE", "Standard", "", 35),
        ("Mattel", "WWE Elite", "Hulk Hogan (Elite)", '6"', "WWE", "Standard", "", 32),
        ("Mattel", "WWE Elite", "Andre the Giant (Elite)", '6"', "WWE", "Deluxe", "", 40),

        # ─── Boss Fight Studio (Additional) ──────────────────────────
        ("Boss Fight Studio", "Vitruvian H.A.C.K.S.", "Gladiator", '3.75"', "Historical", "Standard", "", 22),
        ("Boss Fight Studio", "Vitruvian H.A.C.K.S.", "Amazon Warrior", '3.75"', "Mythology", "Standard", "", 22),
        ("Boss Fight Studio", "Vitruvian H.A.C.K.S.", "Minotaur", '3.75"', "Mythology", "Standard", "", 24),
        ("Boss Fight Studio", "Bucky O'Hare", "Captain Bucky O'Hare", '4"', "Bucky O'Hare", "Standard", "", 35),
        ("Boss Fight Studio", "Bucky O'Hare", "First Mate Jenny", '4"', "Bucky O'Hare", "Standard", "", 35),
        ("Boss Fight Studio", "Bucky O'Hare", "Willy DuWitt", '4"', "Bucky O'Hare", "Standard", "", 32),
        ("Boss Fight Studio", "Bucky O'Hare", "Deadeye Duck", '4"', "Bucky O'Hare", "Standard", "", 35),
        ("Boss Fight Studio", "Bucky O'Hare", "Blinky", '4"', "Bucky O'Hare", "Standard", "", 32),
        ("Boss Fight Studio", "Bucky O'Hare", "Commander Dogstar", '4"', "Bucky O'Hare", "Standard", "", 35),
        ("Boss Fight Studio", "Bucky O'Hare", "Toadborg", '4"', "Bucky O'Hare", "Deluxe", "", 40),

        # ─── 1000Toys ────────────────────────────────────────────────
        ("1000Toys", "TOA Heavy Industries", "Synthetic Human (1/12)", '6"', "Original", "Deluxe", "", 75),
        ("1000Toys", "TOA Heavy Industries", "Synthetic Human (Black Ver.)", '6"', "Original", "Deluxe", "", 80),
        ("1000Toys", "TOA Heavy Industries", "ROBOX BASIC", '6"', "Original", "Deluxe", "", 65),
        ("1000Toys", "TOA Heavy Industries", "ROBOX mk02", '6"', "Original", "Deluxe", "", 70),
        ("1000Toys", "1000Toys", "Hellboy (Standard)", '6"', "Hellboy", "Standard", "", 60),
        ("1000Toys", "1000Toys", "Hellboy (BPRD Shirt)", '6"', "Hellboy", "Standard", "", 65),
        ("1000Toys", "GANTZ:O", "Gantz Suit (Hard Suit, 1/12)", '6"', "GANTZ", "Deluxe", "", 85),
        ("1000Toys", "GANTZ:O", "Gantz Suit (Soft Suit)", '6"', "GANTZ", "Deluxe", "", 80),
        ("1000Toys", "TOA Heavy Industries", "Synthetic Human (Female, 1/12)", '6"', "Original", "Deluxe", "", 78),
        ("1000Toys", "TOA Heavy Industries", "Synthetic Human (1/6 Scale)", '12"', "Original", "Deluxe", "", 180),

        # === ROUND 5 — 700+ Expansion: NECA, McFarlane, Super7, Mezco, Hasbro Pulse, SH Figuarts, Figma, Mafex ===

        # ─── NECA Predator / Alien (New Waves) ─────────────────────────
        ("NECA", "Ultimate Predator", "Ultimate Jungle Hunter Predator (V2)", '7"', "Predator", "Window Box", "", 40),
        ("NECA", "Ultimate Predator", "Ultimate City Hunter Predator (V2)", '7"', "Predator", "Window Box", "", 42),
        ("NECA", "Ultimate Predator", "Ultimate Fugitive Predator (2018)", '7"', "Predator", "Window Box", "", 38),
        ("NECA", "Ultimate Predator", "Ultimate Emissary Predator #2", '7"', "Predator", "Window Box", "", 40),
        ("NECA", "Ultimate Predator", "Ultimate Alpha Predator (Prey)", '7"', "Predator", "Window Box", "", 42),
        ("NECA", "Ultimate Predator", "Ultimate Feral Predator (Prey)", '7"', "Predator", "Window Box", "", 45),
        ("NECA", "Ultimate Predator", "Ultimate Lasershot Predator", '7"', "Predator", "Window Box", "", 38),
        ("NECA", "Ultimate Predator", "Ultimate Scout Predator", '7"', "Predator", "Window Box", "", 38),
        ("NECA", "Ultimate Alien", "Ultimate Xenomorph Warrior (Blue)", '7"', "Aliens", "Window Box", "", 38),
        ("NECA", "Ultimate Alien", "Ultimate Big Chap Alien (40th Anniversary)", '7"', "Alien", "Window Box", "", 42),
        ("NECA", "Ultimate Alien", "Ultimate Alien Queen", '7"', "Aliens", "Deluxe", "", 85),
        ("NECA", "Ultimate Alien", "Ultimate Newborn Alien (Alien Resurrection)", '7"', "Aliens", "Window Box", "", 40),
        ("NECA", "Ultimate Alien", "Ultimate Dog Alien (Alien 3)", '7"', "Aliens", "Window Box", "", 38),

        # ─── McFarlane Spawn Mega Figures ───────────────────────────────
        ("McFarlane", "Spawn", "Spawn (Mortal Kombat 11 Mega)", '12"', "Spawn", "Deluxe", "", 55),
        ("McFarlane", "Spawn", "Violator (Mega Figure)", '12"', "Spawn", "Deluxe", "", 60),
        ("McFarlane", "Spawn", "Mandarin Spawn (Mega Figure)", '12"', "Spawn", "Deluxe", "", 55),
        ("McFarlane", "Spawn", "Ninja Spawn (Mega Figure)", '12"', "Spawn", "Deluxe", "", 52),
        ("McFarlane", "Spawn", "Gunslinger Spawn (Mega Figure)", '12"', "Spawn", "Deluxe", "", 55),
        ("McFarlane", "Spawn", "Spawn (Issue 1 Cover Art Posed)", '7"', "Spawn", "Standard", "", 28),
        ("McFarlane", "Spawn", "Medieval Spawn (Remastered)", '7"', "Spawn", "Standard", "", 30),
        ("McFarlane", "Spawn", "Clown / Violator (Bloody)", '7"', "Spawn", "Standard", "", 28),
        ("McFarlane", "Spawn", "She-Spawn (Deluxe)", '7"', "Spawn", "Deluxe", "", 38),
        ("McFarlane", "Spawn", "Soul Crusher (Spawn Universe)", '7"', "Spawn", "Standard", "", 28),

        # ─── Super7 Ultimates Wave 10+ ──────────────────────────────────
        ("Super7", "Ultimates!", "Thundercats Mumm-Ra (Ever-Living)", '7"', "Thundercats", "Standard", "", 55),
        ("Super7", "Ultimates!", "Thundercats Tygra (Wave 8)", '7"', "Thundercats", "Standard", "", 48),
        ("Super7", "Ultimates!", "Thundercats Cheetara (Wave 9)", '7"', "Thundercats", "Standard", "", 52),
        ("Super7", "Ultimates!", "TMNT Leatherhead (Wave 10)", '7"', "TMNT", "Standard", "", 55),
        ("Super7", "Ultimates!", "TMNT Ace Duck (Wave 10)", '7"', "TMNT", "Standard", "", 50),
        ("Super7", "Ultimates!", "TMNT Mondo Gecko (Wave 11)", '7"', "TMNT", "Standard", "", 52),
        ("Super7", "Ultimates!", "TMNT Ray Fillet (Wave 11)", '7"', "TMNT", "Standard", "", 50),
        ("Super7", "Ultimates!", "MOTU Mantenna (Wave 10)", '7"', "MOTU", "Standard", "", 55),
        ("Super7", "Ultimates!", "MOTU Modulok (Wave 10 Deluxe)", '7"', "MOTU", "Deluxe", "", 75),
        ("Super7", "Ultimates!", "MOTU Dragstor (Wave 11)", '7"', "MOTU", "Standard", "", 52),
        ("Super7", "Ultimates!", "SilverHawks Quicksilver (Wave 2)", '7"', "SilverHawks", "Standard", "", 55),
        ("Super7", "Ultimates!", "SilverHawks Mon*Star (Armored)", '7"', "SilverHawks", "Deluxe", "", 70),

        # ─── Mezco ONE:12 Collective (Recent) ──────────────────────────
        ("Mezco", "ONE:12 Collective", "Batman (Supreme Knight)", '6"', "DC Comics", "Deluxe", "Mezco Exclusive", 120),
        ("Mezco", "ONE:12 Collective", "Spider-Man (Miles Morales)", '6"', "Marvel", "Standard", "", 95),
        ("Mezco", "ONE:12 Collective", "Wolverine (Tiger Stripe)", '6"', "Marvel", "Standard", "", 100),
        ("Mezco", "ONE:12 Collective", "Punisher (War Machine Armor)", '6"', "Marvel", "Deluxe", "Mezco Exclusive", 130),
        ("Mezco", "ONE:12 Collective", "The Joker (Clown Prince of Crime)", '6"', "DC Comics", "Deluxe", "", 110),
        ("Mezco", "ONE:12 Collective", "Darkseid", '6"', "DC Comics", "Deluxe", "", 125),
        ("Mezco", "ONE:12 Collective", "Doc Nocturnal", '6"', "Original", "Standard", "Mezco Exclusive", 90),
        ("Mezco", "ONE:12 Collective", "Gomez (The Rumble Society)", '6"', "Original", "Standard", "Mezco Exclusive", 85),

        # ─── Hasbro Pulse Exclusives ────────────────────────────────────
        ("Hasbro", "Black Series", "Darth Revan (Hasbro Pulse Exclusive)", '6"', "Star Wars", "Standard", "Hasbro Pulse", 45),
        ("Hasbro", "Black Series", "Clone Trooper (Phase I, Hasbro Pulse)", '6"', "Star Wars", "Standard", "Hasbro Pulse", 38),
        ("Hasbro", "Black Series", "Starkiller (Galen Marek)", '6"', "Star Wars", "Standard", "Hasbro Pulse", 42),
        ("Hasbro", "Lightning Collection", "Lord Drakkon (Pulse Exclusive)", '6"', "Power Rangers", "Standard", "Hasbro Pulse", 40),
        ("Hasbro", "Lightning Collection", "Psycho Green Ranger", '6"', "Power Rangers", "Standard", "Hasbro Pulse", 38),
        ("Hasbro", "GI Joe Classified", "Serpentor & Air Chariot (Pulse Exclusive)", '6"', "GI Joe", "Deluxe", "Hasbro Pulse", 55),
        ("Hasbro", "GI Joe Classified", "Python Patrol Officer (Pulse Exclusive)", '6"', "GI Joe", "Standard", "Hasbro Pulse", 35),
        ("Hasbro", "HasLab", "Galactus (HasLab, 32-inch)", '32"', "Marvel", "HasLab", "Hasbro Pulse", 480),
        ("Hasbro", "HasLab", "Unicron (HasLab, Transformers)", '27"', "Transformers", "HasLab", "Hasbro Pulse", 650),

        # ─── SH Figuarts Dragon Ball Super Hero ────────────────────────
        ("Bandai", "S.H.Figuarts", "Son Gohan (Beast Form)", '6"', "Dragon Ball", "Standard", "", 65),
        ("Bandai", "S.H.Figuarts", "Piccolo (Orange Piccolo)", '6"', "Dragon Ball", "Standard", "", 60),
        ("Bandai", "S.H.Figuarts", "Cell Max", '7"', "Dragon Ball", "Deluxe", "", 85),
        ("Bandai", "S.H.Figuarts", "Gamma 1", '6"', "Dragon Ball", "Standard", "", 55),
        ("Bandai", "S.H.Figuarts", "Gamma 2", '6"', "Dragon Ball", "Standard", "", 55),
        ("Bandai", "S.H.Figuarts", "Vegeta (Ultra Ego)", '6"', "Dragon Ball", "Standard", "", 68),
        ("Bandai", "S.H.Figuarts", "Goku (Ultra Instinct -Sign-)", '6"', "Dragon Ball", "Standard", "", 62),
        ("Bandai", "S.H.Figuarts", "Broly (Full Power, DBS)", '7"', "Dragon Ball", "Deluxe", "", 90),

        # ─── Figma New Releases ─────────────────────────────────────────
        ("Good Smile", "Figma", "Link (Tears of the Kingdom)", '6"', "Zelda", "Standard", "", 75),
        ("Good Smile", "Figma", "Samus Aran (Metroid Dread)", '6"', "Metroid", "Standard", "", 80),
        ("Good Smile", "Figma", "Cloud Strife (FF7 Remake)", '6"', "Final Fantasy", "Standard", "", 82),
        ("Good Smile", "Figma", "Solid Snake (Metal Gear Solid)", '6"', "Metal Gear", "Standard", "", 78),
        ("Good Smile", "Figma", "Guts (Berserk: Black Swordsman)", '6"', "Berserk", "Standard", "", 85),
        ("Good Smile", "Figma", "Chainsaw Man (Denji)", '6"', "Chainsaw Man", "Standard", "", 72),
        ("Good Smile", "Figma", "Power (Chainsaw Man)", '6"', "Chainsaw Man", "Standard", "", 70),
        ("Good Smile", "Figma", "Makima (Chainsaw Man)", '6"', "Chainsaw Man", "Standard", "", 72),

        # ─── Mafex Batman / Spider-Man ──────────────────────────────────
        ("Medicom", "MAFEX", "Batman (Hush)", '6"', "DC Comics", "Standard", "", 85),
        ("Medicom", "MAFEX", "Batman (The Dark Knight Returns)", '6"', "DC Comics", "Standard", "", 90),
        ("Medicom", "MAFEX", "Batman (Batman Begins)", '6"', "DC Comics", "Standard", "", 88),
        ("Medicom", "MAFEX", "Spider-Man (Ben Reilly)", '6"', "Marvel", "Standard", "", 82),
        ("Medicom", "MAFEX", "Spider-Man (Miles Morales, ITSV)", '6"', "Marvel", "Standard", "", 85),
        ("Medicom", "MAFEX", "Spider-Man (Comic Paint Ver.)", '6"', "Marvel", "Standard", "", 80),
        ("Medicom", "MAFEX", "Venom (Comic Ver.)", '6"', "Marvel", "Standard", "", 88),
        ("Medicom", "MAFEX", "Superman (Hush)", '6"', "DC Comics", "Standard", "", 82),
        ("Medicom", "MAFEX", "Catwoman (Hush)", '6"', "DC Comics", "Standard", "", 78),

        # ─── Additional Action Figures (+12) ───────────────────────────────
        ("Hasbro", "Classified", "Cobra Commander (v2)", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "Classified", "Snake Eyes (Retro Card)", '6"', "GI Joe", "Retro Card", "", 32),
        ("McFarlane", "DC Multiverse", "Swamp Thing Mega Figure", '7"', "DC Comics", "Deluxe", "", 45),
        ("NECA", "Ultimate", "Predator (Jungle Hunter)", '7"', "Predator", "Ultimate Box", "", 38),
        ("NECA", "Ultimate", "Alien Warrior (Blue)", '7"', "Aliens", "Ultimate Box", "", 35),
        ("Super7", "Ultimates", "Thundercats Mumm-Ra (Ever Living)", '7"', "Thundercats", "Deluxe", "", 55),
        ("Mezco", "One:12 Collective", "Wolverine (Tiger Stripe)", '6"', "Marvel", "Standard", "", 90),
        ("Mezco", "One:12 Collective", "Punisher (War Machine Armor)", '6"', "Marvel", "Deluxe", "PX Exclusive", 110),

        # ─── Round 35: NECA (~15) ────────────────────────────────────────
        ("NECA", "Ultimate", "Predator (City Hunter)", '7"', "Predator", "Ultimate Box", "", 42),
        ("NECA", "Ultimate", "Predator (Fugitive)", '7"', "Predator", "Ultimate Box", "", 40),
        ("NECA", "Ultimate", "Predator (Elder)", '7"', "Predator", "Ultimate Box", "", 45),
        ("NECA", "Ultimate", "Alien Big Chap (1979)", '7"', "Aliens", "Ultimate Box", "", 45),
        ("NECA", "Ultimate", "Alien Queen Deluxe", '7"', "Aliens", "Deluxe", "", 95),
        ("NECA", "Movie", "TMNT Raphael (1990 Movie)", '7"', "TMNT", "Window Box", "", 38),
        ("NECA", "Movie", "TMNT Leonardo (1990 Movie)", '7"', "TMNT", "Window Box", "", 38),
        ("NECA", "Movie", "TMNT Donatello (1990 Movie)", '7"', "TMNT", "Window Box", "", 38),
        ("NECA", "Movie", "TMNT Michelangelo (1990 Movie)", '7"', "TMNT", "Window Box", "", 38),
        ("NECA", "Ultimate", "Jason Voorhees (Part 4 Final Chapter)", '7"', "Horror", "Ultimate Box", "", 38),
        ("NECA", "Ultimate", "Jason Voorhees (Part 7 New Blood)", '7"', "Horror", "Ultimate Box", "", 40),
        ("NECA", "Ultimate", "T-800 Terminator (Tech Noir)", '7"', "Terminator", "Ultimate Box", "", 38),
        ("NECA", "Ultimate", "Gremlins Stripe", '7"', "Gremlins", "Ultimate Box", "", 35),
        ("NECA", "Ultimate", "Ash Williams (Evil Dead 2)", '7"', "Horror", "Ultimate Box", "", 38),
        ("NECA", "Ultimate", "Kratos (God of War 2018)", '7"', "Gaming", "Ultimate Box", "", 42),

        # ─── Round 35: McFarlane DC Multiverse (~15) ─────────────────────
        ("McFarlane", "DC Multiverse", "Batman (Hush)", '7"', "DC Comics", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Batman (Rebirth)", '7"', "DC Comics", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Batman (Arkham Knight)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Batman (Arkham City)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Batman (Dark Nights: Metal)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Batman (Flashpoint)", '7"', "DC Comics", "Standard", "", 30),
        ("McFarlane", "DC Multiverse", "Superman (Action Comics #1000)", '7"', "DC Comics", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Superman (Unchained Armor)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "The Flash (Wally West)", '7"', "DC Comics", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "The Flash (Injustice 2)", '7"', "DC Comics", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Darkseid (Armored, Mega Figure)", '7"', "DC Comics", "Deluxe", "", 55),
        ("McFarlane", "DC Multiverse", "Nightwing (Better Than Batman)", '7"', "DC Comics", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Green Lantern (John Stewart)", '7"', "DC Comics", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Aquaman (JL Movie)", '7"', "DC Comics", "Standard", "", 22),
        ("McFarlane", "DC Multiverse", "Deathstroke (Arkham Origins)", '7"', "DC Comics", "Standard", "", 28),

        # ─── Round 35: Marvel Legends (~10) ──────────────────────────────
        ("Hasbro", "Marvel Legends", "Haslab Sentinel", '26"', "Marvel", "HasLab", "Hasbro Pulse", 450),
        ("Hasbro", "Marvel Legends", "Haslab Galactus", '32"', "Marvel", "HasLab", "Hasbro Pulse", 500),
        ("Hasbro", "Marvel Legends", "Green Goblin (Retro Wave)", '6"', "Marvel", "Retro Card", "", 32),
        ("Hasbro", "Marvel Legends", "Symbiote Spider-Man (Retro Wave)", '6"', "Marvel", "Retro Card", "", 30),
        ("Hasbro", "Marvel Legends", "Venom (Monster Venom BAF)", '6"', "Marvel", "Standard", "", 35),
        ("Hasbro", "Marvel Legends", "Wolverine (X-Men '97)", '6"', "Marvel", "Standard", "", 28),
        ("Hasbro", "Marvel Legends", "Magneto (X-Men '97)", '6"', "Marvel", "Standard", "", 28),
        ("Hasbro", "Marvel Legends", "Doc Ock (Spider-Man Animated)", '6"', "Marvel", "Retro Card", "", 30),
        ("Hasbro", "Marvel Legends", "Kingpin (Retro Wave)", '6"', "Marvel", "Retro Card", "", 35),
        ("Hasbro", "Marvel Legends", "Iron Man (Modular Armor)", '6"', "Marvel", "Standard", "", 28),

        # ─── Round 35: Super7 Ultimates (~10) ────────────────────────────
        ("Super7", "Ultimates!", "TMNT Leonardo (Wave 1)", '7"', "TMNT", "Standard", "", 55),
        ("Super7", "Ultimates!", "TMNT Donatello (Wave 1)", '7"', "TMNT", "Standard", "", 55),
        ("Super7", "Ultimates!", "TMNT Michelangelo (Wave 1)", '7"', "TMNT", "Standard", "", 55),
        ("Super7", "Ultimates!", "TMNT Bebop", '7"', "TMNT", "Standard", "", 55),
        ("Super7", "Ultimates!", "TMNT Rocksteady", '7"', "TMNT", "Standard", "", 55),
        ("Super7", "Ultimates!", "Thundercats Lion-O (Wave 1)", '7"', "Thundercats", "Standard", "", 55),
        ("Super7", "Ultimates!", "Thundercats Panthro", '7"', "Thundercats", "Standard", "", 55),
        ("Super7", "Ultimates!", "MOTU He-Man (Filmation)", '7"', "MOTU", "Standard", "", 55),
        ("Super7", "Ultimates!", "Silverhawks Quicksilver", '7"', "Silverhawks", "Standard", "", 55),
        ("Super7", "Ultimates!", "GI Joe Cobra Commander", '7"', "GI Joe", "Standard", "", 55),

        # ─── Round 35: Mezco One:12 (~10) ────────────────────────────────
        ("Mezco", "One:12 Collective", "Batman (Supreme Knight)", '6"', "DC Comics", "Deluxe", "", 120),
        ("Mezco", "One:12 Collective", "Batman (Ascending Knight)", '6"', "DC Comics", "Standard", "", 95),
        ("Mezco", "One:12 Collective", "Spider-Man (Classic)", '6"', "Marvel", "Standard", "", 90),
        ("Mezco", "One:12 Collective", "Wolverine (Classic)", '6"', "Marvel", "Standard", "", 95),
        ("Mezco", "One:12 Collective", "The Joker (Deluxe Edition)", '6"', "DC Comics", "Deluxe", "", 110),
        ("Mezco", "One:12 Collective", "Blade", '6"', "Marvel", "Standard", "", 90),
        ("Mezco", "One:12 Collective", "Doctor Strange", '6"', "Marvel", "Standard", "", 90),
        ("Mezco", "One:12 Collective", "Punisher (Classic)", '6"', "Marvel", "Standard", "", 85),
        ("Mezco", "One:12 Collective", "Deathstroke", '6"', "DC Comics", "Standard", "", 90),
        ("Mezco", "One:12 Collective", "Captain America", '6"', "Marvel", "Standard", "", 90),

        # ─── Hasbro G.I. Joe Classified Series (6") ────────────────────
        ("Hasbro", "G.I. Joe Classified", "Snake Eyes", '6"', "G.I. Joe", "Standard", "", 28),
        ("Hasbro", "G.I. Joe Classified", "Storm Shadow", '6"', "G.I. Joe", "Standard", "", 28),
        ("Hasbro", "G.I. Joe Classified", "Cobra Commander", '6"', "G.I. Joe", "Standard", "", 30),
        ("Hasbro", "G.I. Joe Classified", "Baroness", '6"', "G.I. Joe", "Standard", "", 28),
        ("Hasbro", "G.I. Joe Classified", "Destro", '6"', "G.I. Joe", "Standard", "", 28),
        ("Hasbro", "G.I. Joe Classified", "Firefly", '6"', "G.I. Joe", "Standard", "", 30),
        ("Hasbro", "G.I. Joe Classified", "Zartan", '6"', "G.I. Joe", "Standard", "", 30),
        ("Hasbro", "G.I. Joe Classified", "Major Bludd", '6"', "G.I. Joe", "Standard", "", 28),
        ("Hasbro", "G.I. Joe Classified", "Crimson Guard", '6"', "G.I. Joe", "Standard", "", 28),
        ("Hasbro", "G.I. Joe Classified", "Tomax & Xamot 2-Pack", '6"', "G.I. Joe", "Deluxe", "", 55),
        ("Hasbro", "G.I. Joe Classified", "Serpentor & Air Chariot", '6"', "G.I. Joe", "Deluxe", "Hasbro Pulse", 55),
        ("Hasbro", "G.I. Joe Classified", "B.A.T. (Battle Android Trooper)", '6"', "G.I. Joe", "Standard", "", 28),
        ("Hasbro", "G.I. Joe Classified", "Croc Master & Fiona", '6"', "G.I. Joe", "Deluxe", "", 38),
        ("Hasbro", "G.I. Joe Classified", "Spirit Iron-Knife", '6"', "G.I. Joe", "Standard", "", 28),
        ("Hasbro", "G.I. Joe Classified", "Cover Girl", '6"', "G.I. Joe", "Standard", "", 28),

        # ─── Bandai S.H.Figuarts — Dragon Ball ─────────────────────────
        ("Bandai", "S.H.Figuarts", "Son Goku SSJ (Legendary Super Saiyan)", '6"', "Dragon Ball", "Standard", "", 65),
        ("Bandai", "S.H.Figuarts", "Son Goku SSJ3", '6"', "Dragon Ball", "Standard", "", 70),
        ("Bandai", "S.H.Figuarts", "Son Goku Ultra Instinct", '6"', "Dragon Ball", "Standard", "", 75),
        ("Bandai", "S.H.Figuarts", "Vegeta SSJ Blue (SSGSS)", '6"', "Dragon Ball", "Standard", "", 65),
        ("Bandai", "S.H.Figuarts", "Piccolo (Proud Namekian)", '6"', "Dragon Ball", "Standard", "", 60),
        ("Bandai", "S.H.Figuarts", "Frieza (Final Form)", '6"', "Dragon Ball", "Standard", "", 60),
        ("Bandai", "S.H.Figuarts", "Perfect Cell", '6"', "Dragon Ball", "Standard", "", 65),
        ("Bandai", "S.H.Figuarts", "Majin Buu (Zen Ver.)", '6"', "Dragon Ball", "Standard", "", 65),
        # ─── Bandai S.H.Figuarts — Naruto / One Piece ──────────────────
        ("Bandai", "S.H.Figuarts", "Naruto Uzumaki (Sage Mode)", '6"', "Naruto", "Standard", "", 60),
        ("Bandai", "S.H.Figuarts", "Sasuke Uchiha (Itachi Battle)", '6"', "Naruto", "Standard", "", 62),
        ("Bandai", "S.H.Figuarts", "Itachi Uchiha (NarutoP99 Edition)", '6"', "Naruto", "Standard", "", 65),
        ("Bandai", "S.H.Figuarts", "Kakashi Hatake (Anbu)", '6"', "Naruto", "Standard", "", 62),
        ("Bandai", "S.H.Figuarts", "Monkey D. Luffy (Gear 5)", '6"', "One Piece", "Standard", "", 80),
        ("Bandai", "S.H.Figuarts", "Roronoa Zoro (Wano Kuni)", '6"', "One Piece", "Standard", "", 68),
        ("Bandai", "S.H.Figuarts", "Trafalgar Law (Wano Kuni)", '6"', "One Piece", "Standard", "", 65),

        # ─── Four Horsemen Mythic Legions ───────────────────────────────
        ("Four Horsemen", "Mythic Legions", "Sir Gideon Heavensbrand (Knight)", '6"', "Mythic Legions", "Standard", "", 55),
        ("Four Horsemen", "Mythic Legions", "Gorgo Aetherblade (Orc Warrior)", '6"', "Mythic Legions", "Standard", "", 55),
        ("Four Horsemen", "Mythic Legions", "Bothar Shadowhorn (Dwarf)", '6"', "Mythic Legions", "Standard", "", 55),
        ("Four Horsemen", "Mythic Legions", "Skeleton Soldier (Army Builder)", '6"', "Mythic Legions", "Standard", "", 45),
        ("Four Horsemen", "Mythic Legions", "Malynna (Dark Elf Ranger)", '6"', "Mythic Legions", "Standard", "", 55),
        ("Four Horsemen", "Mythic Legions", "Baron Volligar (Undead Knight)", '6"', "Mythic Legions", "Standard", "", 60),
        ("Four Horsemen", "Mythic Legions", "Ilgarr (Frost Giant)", '7"', "Mythic Legions", "Deluxe", "", 75),
        ("Four Horsemen", "Mythic Legions", "Arethyr (Demon Lord)", '6"', "Mythic Legions", "Standard", "", 65),
        ("Four Horsemen", "Mythic Legions", "Templar Knight Legion Builder", '6"', "Mythic Legions", "Standard", "", 45),
        ("Four Horsemen", "Mythic Legions", "Goblin Army Builder", '6"', "Mythic Legions", "Standard", "", 42),

        # ─── Storm Collectibles — Fighting Games ────────────────────────
        ("Storm Collectibles", "Mortal Kombat", "Scorpion", '7"', "Mortal Kombat", "Standard", "", 70),
        ("Storm Collectibles", "Mortal Kombat", "Sub-Zero", '7"', "Mortal Kombat", "Standard", "", 70),
        ("Storm Collectibles", "Mortal Kombat", "Raiden", '7"', "Mortal Kombat", "Standard", "", 72),
        ("Storm Collectibles", "Street Fighter", "Ryu", '7"', "Street Fighter", "Standard", "", 70),
        ("Storm Collectibles", "Street Fighter", "Ken Masters", '7"', "Street Fighter", "Standard", "", 70),
        ("Storm Collectibles", "Street Fighter", "Akuma", '7"', "Street Fighter", "Standard", "", 75),
        ("Storm Collectibles", "Street Fighter", "Chun-Li", '7"', "Street Fighter", "Standard", "", 72),
        ("Storm Collectibles", "Tekken", "Jin Kazama", '7"', "Tekken", "Standard", "", 70),
        ("Storm Collectibles", "Tekken", "Kazuya Mishima", '7"', "Tekken", "Standard", "", 70),
        ("Storm Collectibles", "Mortal Kombat", "Shao Kahn", '7"', "Mortal Kombat", "Deluxe", "", 90),

        # ─── Jada Toys Ultra Street Fighter II ──────────────────────────
        ("Jada Toys", "Ultra Street Fighter II", "Ryu", '6"', "Street Fighter", "Standard", "", 25),
        ("Jada Toys", "Ultra Street Fighter II", "Ken", '6"', "Street Fighter", "Standard", "", 25),
        ("Jada Toys", "Ultra Street Fighter II", "Chun-Li", '6"', "Street Fighter", "Standard", "", 25),
        ("Jada Toys", "Ultra Street Fighter II", "Vega", '6"', "Street Fighter", "Standard", "", 25),
        ("Jada Toys", "Ultra Street Fighter II", "M. Bison", '6"', "Street Fighter", "Standard", "", 25),

        # ─── Hasbro Power Rangers Lightning Collection ─────────────────────
        ("Hasbro", "Power Rangers Lightning", "Mighty Morphin Red Ranger (Jason)", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "Power Rangers Lightning", "Mighty Morphin Green Ranger (Tommy)", '6"', "Power Rangers", "Standard", "", 35),
        ("Hasbro", "Power Rangers Lightning", "Mighty Morphin White Ranger (Tommy)", '6"', "Power Rangers", "Standard", "", 32),
        ("Hasbro", "Power Rangers Lightning", "Mighty Morphin Pink Ranger (Kimberly)", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "Power Rangers Lightning", "Lord Drakkon", '6"', "Power Rangers", "Standard", "", 38),
        ("Hasbro", "Power Rangers Lightning", "Dino Thunder White Ranger", '6"', "Power Rangers", "Standard", "", 30),
        ("Hasbro", "Power Rangers Lightning", "In Space Red Ranger", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "Power Rangers Lightning", "SPD Shadow Ranger", '6"', "Power Rangers", "Standard", "", 30),
        ("Hasbro", "Power Rangers Lightning", "Zeo Gold Ranger", '6"', "Power Rangers", "Standard", "", 32),
        ("Hasbro", "Power Rangers Lightning", "Psycho Green Ranger", '6"', "Power Rangers", "Standard", "", 35),
        ("Hasbro", "Power Rangers Lightning", "Mighty Morphin Blue Ranger (Billy)", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "Power Rangers Lightning", "Dino Charge Red Ranger", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "Power Rangers Lightning", "Turbo Red Ranger", '6"', "Power Rangers", "Standard", "", 28),
        ("Hasbro", "Power Rangers Lightning", "Time Force Red Ranger", '6"', "Power Rangers", "Standard", "", 30),
        ("Hasbro", "Power Rangers Lightning", "Lord Zedd", '6"', "Power Rangers", "Deluxe", "", 38),
        ("Hasbro", "Power Rangers Lightning", "Mighty Morphin Megazord (Zord Ascension)", '12"', "Power Rangers", "HasLab", "", 250),

        # ─── Diamond Select — Marvel, DC, Ghostbusters ─────────────────────
        ("Diamond Select", "Marvel Select", "Spider-Man (Spectacular)", '7"', "Marvel", "Standard", "", 30),
        ("Diamond Select", "Marvel Select", "Venom", '7"', "Marvel", "Standard", "", 32),
        ("Diamond Select", "Marvel Select", "Carnage", '7"', "Marvel", "Standard", "", 32),
        ("Diamond Select", "Marvel Select", "Thanos (Infinity War)", '7"', "Marvel", "Standard", "", 35),
        ("Diamond Select", "Marvel Select", "Hulk (Immortal)", '7"', "Marvel", "Standard", "", 30),
        ("Diamond Select", "Marvel Select", "Wolverine (Brown Costume)", '7"', "Marvel", "Standard", "", 28),
        ("Diamond Select", "Marvel Select", "Iron Man (Bleeding Edge)", '7"', "Marvel", "Standard", "", 30),
        ("Diamond Select", "Marvel Select", "Captain America (Classic)", '7"', "Marvel", "Standard", "", 28),
        ("Diamond Select", "DC Gallery", "Batman (Hush)", '7"', "DC Comics", "Standard", "", 30),
        ("Diamond Select", "DC Gallery", "Joker (Killing Joke)", '7"', "DC Comics", "Standard", "", 30),
        ("Diamond Select", "Ghostbusters Select", "Peter Venkman (Series 1)", '7"', "Ghostbusters", "Standard", "", 28),
        ("Diamond Select", "Ghostbusters Select", "Egon Spengler (Series 1)", '7"', "Ghostbusters", "Standard", "", 28),
        ("Diamond Select", "Ghostbusters Select", "Ray Stantz (Series 1)", '7"', "Ghostbusters", "Standard", "", 28),
        ("Diamond Select", "Ghostbusters Select", "Winston Zeddemore (Series 1)", '7"', "Ghostbusters", "Standard", "", 28),
        ("Diamond Select", "Ghostbusters Select", "Gozer the Gozerian", '7"', "Ghostbusters", "Standard", "", 30),

        # ─── Boss Fight Studio — Vitruvian HACKS, Bucky O'Hare ────────────
        ("Boss Fight Studio", "Vitruvian H.A.C.K.S.", "Spartan Warrior (Leonidas)", '4"', "Mythology", "Standard", "", 28),
        ("Boss Fight Studio", "Vitruvian H.A.C.K.S.", "Gorgon Medusa", '4"', "Mythology", "Standard", "", 30),
        ("Boss Fight Studio", "Vitruvian H.A.C.K.S.", "Spartan Queen", '4"', "Mythology", "Standard", "", 28),
        ("Boss Fight Studio", "Vitruvian H.A.C.K.S.", "Minotaur", '4"', "Mythology", "Standard", "", 32),
        ("Boss Fight Studio", "Vitruvian H.A.C.K.S.", "Skeleton Warrior", '4"', "Mythology", "Standard", "", 25),
        ("Boss Fight Studio", "Vitruvian H.A.C.K.S.", "Athenian Warrior", '4"', "Mythology", "Standard", "", 28),
        ("Boss Fight Studio", "Bucky O'Hare", "Bucky O'Hare (Wave 1)", '4"', "Bucky O'Hare", "Standard", "", 28),
        ("Boss Fight Studio", "Bucky O'Hare", "Deadeye Duck (Wave 1)", '4"', "Bucky O'Hare", "Standard", "", 28),
        ("Boss Fight Studio", "Bucky O'Hare", "Jenny (Wave 1)", '4"', "Bucky O'Hare", "Standard", "", 28),
        ("Boss Fight Studio", "Bucky O'Hare", "Blinky (Wave 1)", '4"', "Bucky O'Hare", "Standard", "", 28),
        ("Boss Fight Studio", "Bucky O'Hare", "Storm Toad Trooper", '4"', "Bucky O'Hare", "Standard", "", 25),
        ("Boss Fight Studio", "Bucky O'Hare", "Toadborg", '4"', "Bucky O'Hare", "Standard", "", 30),

        # ─── 1000Toys — Hellboy, Synthetic Human ──────────────────────────
        ("1000Toys", "1000Toys", "Hellboy Standard Edition", '6"', "Hellboy", "Standard", "", 80),
        ("1000Toys", "1000Toys", "Hellboy Exclusive (BPRD Shirt)", '6"', "Hellboy", "Deluxe", "1000Toys Exclusive", 100),
        ("1000Toys", "1000Toys", "Synthetic Human Test Body (1/6 Scale)", '12"', "Original", "Standard", "", 120),
        ("1000Toys", "1000Toys", "Synthetic Human Female Test Body (1/12)", '6"', "Original", "Standard", "", 55),
        ("1000Toys", "1000Toys", "TOA Heavy Industries Synthetic Human (1/12)", '6"', "Original", "Standard", "", 60),
        ("1000Toys", "1000Toys", "GANTZ:O Reika (1/12)", '6"', "GANTZ", "Standard", "", 75),
        ("1000Toys", "1000Toys", "GANTZ:O Kato (1/12)", '6"', "GANTZ", "Standard", "", 72),
        ("1000Toys", "1000Toys", "Robo-Dou Getter 1", '6"', "Getter Robo", "Standard", "", 85),

        # ─── Mafex — Batman, Spider-Man, Wolverine ────────────────────────
        ("Mafex", "Mafex", "Batman (Hush)", '6"', "DC Comics", "Standard", "", 85),
        ("Mafex", "Mafex", "Batman (The Dark Knight Returns)", '6"', "DC Comics", "Standard", "", 90),
        ("Mafex", "Mafex", "Joker (The Dark Knight)", '6"', "DC Comics", "Standard", "", 80),
        ("Mafex", "Mafex", "Catwoman (Hush)", '6"', "DC Comics", "Standard", "", 80),
        ("Mafex", "Mafex", "Spider-Man (Comic Paint)", '6"', "Marvel", "Standard", "", 85),
        ("Mafex", "Mafex", "Spider-Man (Miles Morales, Into the Spider-Verse)", '6"', "Marvel", "Standard", "", 80),
        ("Mafex", "Mafex", "Wolverine (Comic Ver.)", '6"', "Marvel", "Standard", "", 85),
        ("Mafex", "Mafex", "Wolverine (Brown Costume)", '6"', "Marvel", "Standard", "", 88),
        ("Mafex", "Mafex", "Cyclops (Comic Ver.)", '6"', "Marvel", "Standard", "", 80),
        ("Mafex", "Mafex", "Venom (Comic Ver.)", '6"', "Marvel", "Standard", "", 90),
        ("Mafex", "Mafex", "Robocop", '6"', "Robocop", "Standard", "", 75),
        ("Mafex", "Mafex", "John Wick (Chapter 2)", '6"', "John Wick", "Standard", "", 78),

        # ─── Additional Lines ──────────────────────────────────────────────
        ("Hasbro", "GI Joe Classified", "Snake Eyes (Deluxe)", '6"', "GI Joe", "Deluxe", "", 38),
        ("Hasbro", "GI Joe Classified", "Storm Shadow", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Cobra Commander", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Baroness", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Destro", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Firefly", '6"', "GI Joe", "Standard", "", 28),
        ("Hasbro", "GI Joe Classified", "Zartan", '6"', "GI Joe", "Standard", "", 32),
        ("Hasbro", "GI Joe Classified", "Serpentor & Air Chariot", '6"', "GI Joe", "Deluxe", "", 55),
        ("Mattel", "WWE Elite", "The Undertaker (WrestleMania 40)", '6"', "WWE", "Standard", "", 30),
        ("Mattel", "WWE Elite", "CM Punk (Return)", '6"', "WWE", "Standard", "", 32),
        ("Mattel", "WWE Elite", "Roman Reigns (Bloodline)", '6"', "WWE", "Standard", "", 28),
        ("Mattel", "WWE Elite", "Cody Rhodes (WrestleMania 40)", '6"', "WWE", "Standard", "", 28),

        # ─── More McFarlane DC Multiverse ──────────────────────────────────
        ("McFarlane", "DC Multiverse", "Red Hood (Gotham Knights)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Nightwing (Gotham Knights)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Green Arrow (Injustice 2)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Black Adam (Movie)", '7"', "DC Comics", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Aquaman (Lost Kingdom)", '7"', "DC Comics", "Standard", "", 25),
        ("McFarlane", "DC Multiverse", "Supergirl (DC Rebirth)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Batgirl (Gotham Knights)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Darkseid (Zack Snyder JL)", '7"', "DC Comics", "Deluxe", "", 45),
        ("McFarlane", "DC Multiverse", "Bane (DC Rebirth)", '7"', "DC Comics", "Deluxe", "", 42),
        ("McFarlane", "DC Multiverse", "Constantine (DC Rebirth)", '7"', "DC Comics", "Standard", "", 28),
        ("McFarlane", "DC Multiverse", "Swamp Thing (DC Rebirth)", '7"', "DC Comics", "Deluxe", "", 40),

        # ─── More NECA Figures ─────────────────────────────────────────────
        ("NECA", "Ultimate", "Godzilla (2019 King of the Monsters)", '7"', "Godzilla", "Window Box", "", 42),
        ("NECA", "Ultimate", "Godzilla (Heisei Era)", '7"', "Godzilla", "Window Box", "", 40),
        ("NECA", "Ultimate", "King Kong (Skull Island)", '7"', "King Kong", "Window Box", "", 42),
        ("NECA", "Ultimate", "Alien (40th Anniversary Big Chap)", '7"', "Alien", "Window Box", "", 38),
        ("NECA", "Ultimate", "Alien Xenomorph Warrior (Blue)", '7"', "Alien", "Window Box", "", 35),
        ("NECA", "Ultimate", "Predator (Jungle Hunter)", '7"', "Predator", "Window Box", "", 38),
        ("NECA", "Ultimate", "TMNT (Cartoon) Leonardo", '7"', "TMNT", "Window Box", "", 42),
        ("NECA", "Ultimate", "TMNT (Cartoon) Donatello", '7"', "TMNT", "Window Box", "", 42),
        ("NECA", "Ultimate", "TMNT (Cartoon) Raphael", '7"', "TMNT", "Window Box", "", 42),
        ("NECA", "Ultimate", "TMNT (Cartoon) Michelangelo", '7"', "TMNT", "Window Box", "", 42),
        ("NECA", "Ultimate", "TMNT (Cartoon) Shredder", '7"', "TMNT", "Window Box", "", 42),
        ("NECA", "Ultimate", "TMNT (Cartoon) Krang's Android Body", '7"', "TMNT", "Deluxe", "", 55),

        # ─── More Super7 Ultimates! ───────────────────────────────────────
        ("Super7", "Ultimates!", "Thundercats Lion-O", '7"', "Thundercats", "Standard", "", 55),
        ("Super7", "Ultimates!", "Thundercats Mumm-Ra", '7"', "Thundercats", "Standard", "", 55),
        ("Super7", "Ultimates!", "MOTU He-Man", '7"', "MOTU", "Standard", "", 50),
        ("Super7", "Ultimates!", "MOTU Skeletor", '7"', "MOTU", "Standard", "", 50),
        ("Super7", "Ultimates!", "Transformers Banzai-Tron", '7"', "Transformers", "Standard", "", 55),
        ("Super7", "Ultimates!", "SilverHawks Quicksilver", '7"', "SilverHawks", "Standard", "", 55),

        # ─── More Lines to Reach 1020+ ─────────────────────────────────────
        ("Mezco", "ONE:12 Collective", "Mezco Batman (Supreme Knight)", '6"', "DC Comics", "Standard", "", 85),
        ("Mezco", "ONE:12 Collective", "Mezco Joker (Clown Prince of Crime)", '6"', "DC Comics", "Standard", "", 80),
        ("Mezco", "ONE:12 Collective", "Mezco Punisher (Netflix)", '6"', "Marvel", "Standard", "", 80),
        ("Mezco", "ONE:12 Collective", "Mezco Wolverine (Tiger Stripe)", '6"', "Marvel", "Standard", "", 85),
        ("Mezco", "ONE:12 Collective", "Mezco Spider-Man (Homecoming)", '6"', "Marvel", "Standard", "", 85),
        ("Mezco", "ONE:12 Collective", "Mezco Doc Ock (Classic)", '6"', "Marvel", "Standard", "", 80),
        ("Bandai", "S.H.Figuarts", "S.H.Figuarts Goku Ultra Instinct", '6"', "Dragon Ball", "Standard", "", 65),
        ("Bandai", "S.H.Figuarts", "S.H.Figuarts Vegeta Super Saiyan Blue", '6"', "Dragon Ball", "Standard", "", 60),
        ("Bandai", "S.H.Figuarts", "S.H.Figuarts Broly (Full Power)", '6"', "Dragon Ball", "Standard", "", 70),
        ("Bandai", "S.H.Figuarts", "S.H.Figuarts Frieza (Final Form)", '6"', "Dragon Ball", "Standard", "", 55),
        ("Bandai", "S.H.Figuarts", "S.H.Figuarts The Mandalorian (Beskar)", '6"', "Star Wars", "Standard", "", 65),
        ("Bandai", "S.H.Figuarts", "S.H.Figuarts Darth Vader (ROTJ)", '6"', "Star Wars", "Standard", "", 65),
        ("Mattel", "MOTU Origins", "He-Man", '5.5"', "MOTU", "Standard", "", 18),
        ("Mattel", "MOTU Origins", "Skeletor", '5.5"', "MOTU", "Standard", "", 18),
        ("Mattel", "MOTU Origins", "Battle Cat", '5.5"', "MOTU", "Deluxe", "", 30),
        ("Mattel", "MOTU Origins", "Panthor", '5.5"', "MOTU", "Deluxe", "", 30),

        # ── Star Trek Action Figures (15) ────────────────────────────────────
        ("McFarlane", "Star Trek", "Captain Kirk (TOS)", '7"', "Star Trek", "Standard", "", 25),
        ("McFarlane", "Star Trek", "Captain Picard (TNG)", '7"', "Star Trek", "Standard", "", 25),
        ("McFarlane", "Star Trek", "Spock (TOS)", '7"', "Star Trek", "Standard", "", 25),
        ("Playmates", "Star Trek Discovery", "Captain Burnham", '5"', "Star Trek", "Standard", "", 18),
        ("Playmates", "Star Trek SNW", "Captain Pike", '5"', "Star Trek", "Standard", "", 20),
        ("Playmates", "Star Trek SNW", "Spock (Strange New Worlds)", '5"', "Star Trek", "Standard", "", 20),
        ("Playmates", "Star Trek Lower Decks", "Ensign Mariner", '5"', "Star Trek", "Standard", "", 18),
        ("NECA", "Star Trek", "Wrath of Khan Kirk & Spock 2-Pack", '7"', "Star Trek", "Window Box", "", 55),
        ("NECA", "Star Trek", "Khan Noonien Singh (Wrath of Khan)", '7"', "Star Trek", "Window Box", "", 35),
        ("Diamond Select", "Star Trek Select", "Captain Kirk (TOS)", '7"', "Star Trek", "Standard", "", 30),
        ("Diamond Select", "Star Trek Select", "Mr. Spock (TOS)", '7"', "Star Trek", "Standard", "", 30),
        ("Diamond Select", "Star Trek Select", "Captain Picard (TNG)", '7"', "Star Trek", "Standard", "", 30),
        ("Diamond Select", "Star Trek Select", "Borg Drone", '7"', "Star Trek", "Standard", "", 28),
        ("Mezco", "ONE:12 Collective", "Captain Kirk (TOS)", '6"', "Star Trek", "Deluxe", "", 90),
        ("Mezco", "ONE:12 Collective", "Mr. Spock (TOS)", '6"', "Star Trek", "Deluxe", "", 90),
    ]

    catalog = []
    for brand, line, name, scale, franchise, packaging, exclusive, price in items:
        catalog.append({
            "brand": brand,
            "line": line,
            "name": name,
            "scale": scale,
            "franchise": franchise,
            "packaging_type": packaging,
            "retailer_exclusive": exclusive,
            "price_eur": price,
        })

    # Add variant items (exclusives, repaints, scale variants, 2-packs, etc.)
    variants = _variant_expansion()
    # Dedup by (brand, line, name) to avoid collisions with existing items
    existing_keys = {(d["brand"], d["line"], d["name"]) for d in catalog}
    for v in variants:
        key = (v["brand"], v["line"], v["name"])
        if key not in existing_keys:
            catalog.append(v)
            existing_keys.add(key)

    # Deduplicate by ('brand', 'line', 'name') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["brand"], item["line"], item["name"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def item_to_catalog_item(item: dict) -> CatalogItem:
    name = item["name"]
    brand = item["brand"]
    line = item["line"]
    franchise = item["franchise"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{line}-{name}"),
        title=name,
        set_code=slugify(line),
        brand=brand,
        rarity="High" if item["retailer_exclusive"] else "Standard",
        notes=f"{brand} | {line} | {franchise} | {item['scale']}",
        attributes_json={
            "brand": brand,
            "line": line,
            "scale": item["scale"],
            "franchise": franchise,
            "packaging_type": item["packaging_type"],
            "retailer_exclusive": item["retailer_exclusive"],
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    exclusive_bonus = 0.1 if item["retailer_exclusive"] else 0.0

    scale_scores = {
        '3.75"': 0.3,
        '4"': 0.35,
        '5.5"': 0.35,
        '6"': 0.5,
        '7"': 0.5,
        '12"': 0.7,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": scale_scores.get(item["scale"], 0.5) + exclusive_bonus,
            "edition_score": 0.5,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Action Figures catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Action Figures Import ===")

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

    logger.info(f"\n=== Action Figures Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
