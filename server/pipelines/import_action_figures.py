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
- 550+ items across all lines

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


def get_curated_catalog() -> list[dict]:
    """Curated 550+ modern action figures catalog: GI Joe Classified, Power Rangers
    Lightning, Star Wars Black Series, NECA, McFarlane, Super7, MOTU Origins, etc."""

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
        ("NECA", "Ultimate", "Leatherface (Texas Chainsaw)", '7"', "Texas Chainsaw", "Window Box", "", 38),
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
    return catalog


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
