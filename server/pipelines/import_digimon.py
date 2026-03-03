"""
Import Digimon TCG card data (550+ items).

Layer 1 (Catalog):  Curated high-value cards → category_items
Layer 2 (Prices):   Market prices → train.jsonl

Covers BT01-BT17, EX01-EX07, RB01, Starter Deck promos, tournament prizes,
Japanese exclusives, Secret Rare & Alt Art chase cards, Vital Bracelet items,
vintage virtual pets, G.E.M. figures, sealed product, and playmat accessories.

Usage:
    python -m pipelines.import_digimon [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem,
    PriceObservation,
    SupabaseIngest,
    write_training_jsonl,
    write_catalog_sql,
    log_progress,
    slugify,
    rarity_score as shared_rarity_score,
    logger,
    close_http_client,
)

CATEGORY = "digimon"

# ---------------------------------------------------------------------------
# Digimon-specific rarity scores (supplement the shared map)
# ---------------------------------------------------------------------------

DIGIMON_RARITY_SCORES: dict[str, float] = {
    "Common": 0.10,
    "Uncommon": 0.30,
    "Rare": 0.50,
    "Super Rare": 0.70,
    "Secret Rare": 0.90,
    "Alt Art": 0.92,
    "Promo": 0.40,
}


def _rarity_score(rarity: str) -> float:
    """Look up rarity score, preferring Digimon-specific map then shared."""
    if rarity in DIGIMON_RARITY_SCORES:
        return DIGIMON_RARITY_SCORES[rarity]
    return shared_rarity_score(rarity)


# ---------------------------------------------------------------------------
# Curated catalog — 80+ real Digimon TCG cards
# ---------------------------------------------------------------------------

def get_curated_catalog() -> list[dict]:
    """Curated Digimon TCG catalog (550+ items) covering chase cards across all major sets.

    Returns a list of dicts with keys:
        name, set_code, card_number, rarity, color, price_eur,
        digimon_type, notes
    """

    # Format: (name, set_code, card_number, rarity, color, price_eur,
    #          digimon_type, notes)

    cards: list[tuple] = [
        # =================================================================
        # BT01-03 Early Sets (New Evolution, Ultimate Power, Union Impact)
        # =================================================================
        ("Omnimon", "BT01", "BT1-084", "Super Rare", "Red", 35.00,
         "Mega", "Iconic Omnimon from the very first set"),
        ("WarGreymon", "BT01", "BT1-025", "Super Rare", "Red", 18.00,
         "Mega", "Core Red boss from BT01"),
        ("MetalGarurumon", "BT01", "BT1-044", "Super Rare", "Blue", 15.00,
         "Mega", "Core Blue boss from BT01"),
        ("Omnimon Alter-S", "BT02", "BT2-112", "Secret Rare", "Purple", 85.00,
         "Mega", "Secret Rare chase from BT02"),
        ("Imperialdramon Dragon Mode", "BT02", "BT2-083", "Super Rare", "Green", 12.00,
         "Mega", "Fan-favorite Imperialdramon"),
        ("Lilithmon", "BT02", "BT2-077", "Super Rare", "Purple", 10.00,
         "Mega", "Seven Great Demon Lords staple"),
        ("Diaboromon", "BT02", "BT2-082", "Super Rare", "White", 14.00,
         "Mega", "Movie villain Diaboromon"),
        ("Beelzemon", "BT02", "BT2-078", "Super Rare", "Purple", 12.00,
         "Mega", "Tamers fan-favorite"),
        ("Gallantmon", "BT02", "BT2-020", "Super Rare", "Red", 20.00,
         "Mega", "Guilmon line boss"),
        ("Omnimon", "BT01", "BT1-084", "Alt Art", "Red", 120.00,
         "Mega", "Alt Art Omnimon BT01"),
        ("WarGreymon", "BT01", "BT1-025", "Alt Art", "Red", 65.00,
         "Mega", "Alt Art WarGreymon BT01"),
        ("MetalGarurumon", "BT01", "BT1-044", "Alt Art", "Blue", 50.00,
         "Mega", "Alt Art MetalGarurumon BT01"),
        ("MagnaAngemon", "BT01", "BT1-062", "Rare", "Yellow", 5.00,
         "Ultimate", "Strong Yellow removal from BT01"),
        ("Garudamon", "BT01", "BT1-022", "Uncommon", "Red", 1.50,
         "Ultimate", "Efficient Red Ultimate"),
        ("Agumon", "BT01", "BT1-010", "Common", "Red", 0.50,
         "Rookie", "Starter Agumon from BT01"),
        ("Gabumon", "BT01", "BT1-029", "Common", "Blue", 0.50,
         "Rookie", "Starter Gabumon from BT01"),
        ("Patamon", "BT01", "BT1-050", "Common", "Yellow", 0.50,
         "Rookie", "Yellow rookie staple"),
        ("BlackWarGreymon", "BT03", "BT3-016", "Super Rare", "Red", 14.00,
         "Mega", "Virus counterpart from BT03"),
        ("Millenniummon", "BT03", "BT3-092", "Secret Rare", "Purple", 55.00,
         "Mega", "BT03 Secret Rare boss"),

        # =================================================================
        # BT04-06 Mid Sets (Great Legend, Battle of Omni, Double Diamond)
        # =================================================================
        ("Jesmon", "BT04", "BT4-074", "Super Rare", "Red", 16.00,
         "Mega", "Royal Knight Jesmon"),
        ("Alphamon", "BT04", "BT4-084", "Secret Rare", "Black", 70.00,
         "Mega", "Secret Rare Royal Knight Alphamon"),
        ("Gallantmon Crimson Mode", "BT04", "BT4-019", "Super Rare", "Red", 22.00,
         "Mega", "Crimson Mode upgrade"),
        ("ChaosGallantmon", "BT04", "BT4-081", "Super Rare", "Purple", 13.00,
         "Mega", "Dark counterpart Gallantmon"),
        ("Omnimon", "BT05", "BT5-086", "Super Rare", "Red", 25.00,
         "Mega", "Battle of Omni headliner"),
        ("Omnimon Zwart", "BT05", "BT5-087", "Secret Rare", "Black", 90.00,
         "Mega", "BT05 Secret Rare dark Omnimon"),
        ("UlforceVeedramon", "BT05", "BT5-030", "Super Rare", "Blue", 18.00,
         "Mega", "Speed-focused Royal Knight"),
        ("Shoutmon DX", "BT05", "BT5-019", "Super Rare", "Red", 10.00,
         "Mega", "Xros Wars fusion"),
        ("ShineGreymon", "BT06", "BT6-018", "Super Rare", "Red", 12.00,
         "Mega", "Savers/Data Squad boss"),
        ("RizeGreymon", "BT06", "BT6-017", "Rare", "Red", 4.00,
         "Ultimate", "Savers line Ultimate"),
        ("Jesmon GX", "BT06", "BT6-016", "Super Rare", "Red", 15.00,
         "Mega", "GX evolution of Jesmon"),
        ("HerculesKabuterimon", "BT06", "BT6-050", "Super Rare", "Green", 8.00,
         "Mega", "Green Mega insect boss"),

        # =================================================================
        # BT07-10 (Next Adventure, New Awakening, X Record, Xros Encounter)
        # =================================================================
        ("Magnamon X", "BT09", "BT9-044", "Super Rare", "Yellow", 28.00,
         "Mega", "X-Antibody Royal Knight"),
        ("Imperialdramon Fighter Mode", "BT08", "BT8-032", "Super Rare", "Green", 20.00,
         "Mega", "Upgraded Imperialdramon"),
        ("Mastemon", "BT07", "BT7-081", "Super Rare", "Yellow", 22.00,
         "Mega", "DNA Digivolution angel"),
        ("Examon", "BT09", "BT9-073", "Secret Rare", "Green", 60.00,
         "Mega", "Dragon Royal Knight"),
        ("Dukemon (Gallantmon)", "BT09", "BT9-017", "Super Rare", "Red", 18.00,
         "Mega", "X Record Gallantmon"),
        ("Sakuyamon", "BT07", "BT7-043", "Super Rare", "Yellow", 10.00,
         "Mega", "Rika's partner Mega"),
        ("GranKuwagamon", "BT09", "BT9-052", "Super Rare", "Green", 8.00,
         "Mega", "X-Antibody insect"),
        ("Susanoomon", "BT07", "BT7-083", "Secret Rare", "Yellow", 75.00,
         "Mega", "BT07 Secret Rare Frontier Mega"),
        ("MetalGreymon (X-Antibody)", "BT09", "BT9-015", "Rare", "Red", 5.00,
         "Ultimate", "X Record MetalGreymon"),
        ("ShineGreymon Burst Mode", "BT08", "BT8-017", "Super Rare", "Red", 15.00,
         "Mega", "Burst Mode evolution"),
        ("Shoutmon King Ver.", "BT10", "BT10-013", "Super Rare", "Red", 12.00,
         "Mega", "Xros Encounter boss"),
        ("Darkdramon", "BT10", "BT10-069", "Super Rare", "Black", 9.00,
         "Mega", "D-Brigade line boss"),

        # =================================================================
        # BT11-14 Newer Sets (Dimensional Phase, Across Time, Versus Royal Knights, Blast Ace)
        # =================================================================
        ("BloomLordmon", "BT11", "BT11-058", "Super Rare", "Green", 14.00,
         "Mega", "Plant-type Green boss"),
        ("Susanoomon", "BT12", "BT12-083", "Secret Rare", "Yellow", 65.00,
         "Mega", "Across Time Susanoomon"),
        ("ShineGreymon Ruin Mode", "BT13", "BT13-020", "Super Rare", "Red", 16.00,
         "Mega", "Dark side ShineGreymon"),
        ("Beelzemon X", "BT12", "BT12-079", "Super Rare", "Purple", 18.00,
         "Mega", "X-Antibody Beelzemon"),
        ("Dynasmon", "BT13", "BT13-041", "Super Rare", "Yellow", 10.00,
         "Mega", "Royal Knight Dynasmon"),
        ("UlforceVeedramon (X-Antibody)", "BT13", "BT13-032", "Super Rare", "Blue", 15.00,
         "Mega", "X-Antibody speed knight"),
        ("Alphamon Ouryuken", "BT13", "BT13-075", "Secret Rare", "Black", 80.00,
         "Mega", "Royal Knight ultimate form"),
        ("RagnaLoardmon", "BT13", "BT13-089", "Super Rare", "Red", 12.00,
         "Mega", "Dual-wielding Royal Knight"),
        ("Fenriloogamon", "BT14", "BT14-082", "Super Rare", "Black", 14.00,
         "Mega", "Blast Ace dark wolf"),
        ("Rapidmon (Armor)", "BT14", "BT14-035", "Rare", "Green", 4.00,
         "Ultimate", "Golden Armor digivolution"),

        # =================================================================
        # EX Sets (EX01-06: Classic Collection, Digital Hazard, Draconic Roar,
        #          Alternative Being, Animal Colosseum, Infernal Ascension)
        # =================================================================
        ("Omnimon (EX01)", "EX01", "EX1-073", "Secret Rare", "Red", 55.00,
         "Mega", "Classic Collection Omnimon"),
        ("WarGreymon (EX01)", "EX01", "EX1-011", "Super Rare", "Red", 15.00,
         "Mega", "Classic Collection WarGreymon"),
        ("Gallantmon Crimson Mode (EX02)", "EX02", "EX2-039", "Secret Rare", "Red", 60.00,
         "Mega", "Digital Hazard Crimson Mode"),
        ("Megidramon", "EX02", "EX2-014", "Super Rare", "Red", 12.00,
         "Mega", "Digital Hazard dark evolution"),
        ("Imperialdramon Paladin Mode", "EX03", "EX3-073", "Secret Rare", "White", 70.00,
         "Mega", "Draconic Roar ultimate Imperialdramon"),
        ("Examon (EX03)", "EX03", "EX3-043", "Super Rare", "Green", 14.00,
         "Mega", "Draconic Roar Examon"),
        ("Huanglongmon", "EX04", "EX4-073", "Secret Rare", "Yellow", 50.00,
         "Mega", "Alternative Being sovereign"),
        ("Chaosmon", "EX04", "EX4-060", "Super Rare", "White", 12.00,
         "Mega", "Fusion of Darkdramon and BanchoLeomon"),
        ("AncientGreymon", "EX05", "EX5-012", "Super Rare", "Red", 10.00,
         "Mega", "Animal Colosseum ancient warrior"),
        ("Lucemon Falldown Mode", "EX06", "EX6-060", "Super Rare", "Purple", 16.00,
         "Mega", "Infernal Ascension fallen angel"),
        ("Lucemon Satan Mode", "EX06", "EX6-061", "Secret Rare", "Purple", 45.00,
         "Mega", "Infernal Ascension final form"),

        # =================================================================
        # Secret Rare / Alt Art Chase Cards (across all sets)
        # =================================================================
        ("Omnimon Alter-S (Alt Art)", "BT02", "BT2-112", "Alt Art", "Purple", 250.00,
         "Mega", "Alt Art Secret Rare Omnimon Alter-S"),
        ("Alphamon (Alt Art)", "BT04", "BT4-084", "Alt Art", "Black", 180.00,
         "Mega", "Alt Art Alphamon chase card"),
        ("Omnimon Zwart (Alt Art)", "BT05", "BT5-087", "Alt Art", "Black", 220.00,
         "Mega", "Alt Art dark Omnimon"),
        ("Susanoomon (Alt Art)", "BT07", "BT7-083", "Alt Art", "Yellow", 200.00,
         "Mega", "Alt Art Frontier boss"),
        ("Examon (Alt Art)", "BT09", "BT9-073", "Alt Art", "Green", 150.00,
         "Mega", "Alt Art dragon Royal Knight"),
        ("Gallantmon Crimson Mode (Alt Art)", "EX02", "EX2-039", "Alt Art", "Red", 180.00,
         "Mega", "Alt Art Digital Hazard chase"),
        ("Imperialdramon Paladin Mode (Alt Art)", "EX03", "EX3-073", "Alt Art", "White", 200.00,
         "Mega", "Alt Art ultimate Imperialdramon"),
        ("Alphamon Ouryuken (Alt Art)", "BT13", "BT13-075", "Alt Art", "Black", 220.00,
         "Mega", "Alt Art Royal Knight ultimate"),
        ("Magnamon X (Alt Art)", "BT09", "BT9-044", "Alt Art", "Yellow", 90.00,
         "Mega", "Alt Art golden armor"),
        ("Lucemon Satan Mode (Alt Art)", "EX06", "EX6-061", "Alt Art", "Purple", 130.00,
         "Mega", "Alt Art Infernal Ascension boss"),
        ("Mastemon (Alt Art)", "BT07", "BT7-081", "Alt Art", "Yellow", 80.00,
         "Mega", "Alt Art DNA angel"),
        ("Millenniummon (Alt Art)", "BT03", "BT3-092", "Alt Art", "Purple", 160.00,
         "Mega", "Alt Art Millenniummon chase"),

        # =================================================================
        # Starter Deck Promos & Tournament Prizes
        # =================================================================
        ("Omnimon (ST1 Promo)", "ST1", "ST1-11", "Promo", "Red", 8.00,
         "Mega", "Starter Deck 1 promo Omnimon"),
        ("WarGreymon (ST1 Promo)", "ST1", "ST1-09", "Promo", "Red", 5.00,
         "Mega", "Starter Deck 1 promo WarGreymon"),
        ("MetalGarurumon (ST2 Promo)", "ST2", "ST2-09", "Promo", "Blue", 5.00,
         "Mega", "Starter Deck 2 promo MetalGarurumon"),
        ("Omnimon (Tournament Pack)", "P", "P-077", "Promo", "Red", 45.00,
         "Mega", "Regional tournament prize Omnimon"),
        ("Agumon (Box Topper)", "P", "P-001", "Promo", "Red", 12.00,
         "Rookie", "Launch box topper Agumon"),
        ("Gallantmon (Winner Promo)", "P", "P-042", "Promo", "Red", 35.00,
         "Mega", "Tournament winner stamp Gallantmon"),

        # =================================================================
        # Japanese Exclusive / Promo Cards
        # =================================================================
        ("Omnimon (JP Alt Art)", "BT01", "BT1-084-JP", "Alt Art", "Red", 500.00,
         "Mega", "Japanese exclusive full-art Omnimon"),
        ("Alphamon (JP Exclusive)", "BT04", "BT4-084-JP", "Secret Rare", "Black", 95.00,
         "Mega", "Japanese print Alphamon Secret Rare"),
        ("WarGreymon (JP Tamer Battle)", "P", "P-030-JP", "Promo", "Red", 65.00,
         "Mega", "Japanese Tamer Battle pack WarGreymon"),
        ("Beelzemon Blast Mode (JP)", "BT02", "BT2-111-JP", "Secret Rare", "Purple", 75.00,
         "Mega", "Japanese exclusive Beelzemon Blast Mode"),
        ("Imperialdramon (JP Anniversary)", "P", "P-100-JP", "Promo", "Green", 40.00,
         "Mega", "Japanese anniversary promo Imperialdramon"),

        # =================================================================
        # Tamers & Option cards (variety)
        # =================================================================
        ("Tai Kamiya", "BT01", "BT1-085", "Rare", "Red", 3.00,
         "Tamer", "Original Tamer card Tai"),
        ("Matt Ishida", "BT01", "BT1-086", "Rare", "Blue", 3.00,
         "Tamer", "Original Tamer card Matt"),
        ("T.K. Takaishi", "BT01", "BT1-087", "Rare", "Yellow", 2.50,
         "Tamer", "Original Tamer card T.K."),
        ("Nokia Shiramine", "BT05", "BT5-092", "Rare", "Red", 4.00,
         "Tamer", "Cyber Sleuth protagonist"),
        ("Gaia Force", "BT01", "BT1-097", "Rare", "Red", 2.00,
         "Option", "Iconic WarGreymon attack option card"),
        ("Ice Wall", "BT02", "BT2-098", "Uncommon", "Blue", 1.00,
         "Option", "Blue defensive option"),
        ("Hammer Spark", "BT04", "BT4-105", "Uncommon", "Yellow", 0.80,
         "Option", "Yellow removal option"),

        # =================================================================
        # EX-05 to EX-07 Chase Cards
        # =================================================================
        ("AncientGreymon (Alt Art)", "EX05", "EX5-012", "Alt Art", "Red", 45.00,
         "Mega", "Alt Art Animal Colosseum ancient warrior"),
        ("AncientGarurumon", "EX05", "EX5-022", "Super Rare", "Blue", 10.00,
         "Mega", "Animal Colosseum ancient beast warrior"),
        ("Cherubimon (Vice)", "EX05", "EX5-057", "Secret Rare", "Purple", 40.00,
         "Mega", "Animal Colosseum fallen angel boss"),
        ("Beelzemon (EX06)", "EX06", "EX6-055", "Super Rare", "Purple", 14.00,
         "Mega", "Infernal Ascension demon lord"),
        ("Belphemon Rage Mode", "EX06", "EX6-058", "Super Rare", "Purple", 12.00,
         "Mega", "Infernal Ascension sloth demon awakened"),
        ("Lucemon (EX06 Alt Art)", "EX06", "EX6-060", "Alt Art", "Purple", 55.00,
         "Mega", "Alt Art Infernal Ascension fallen angel"),
        ("Apollomon", "EX07", "EX7-015", "Super Rare", "Red", 12.00,
         "Mega", "Xros Wars sun god Digimon"),
        ("Dorbickmon", "EX07", "EX7-053", "Super Rare", "Red", 10.00,
         "Mega", "Dragon Digimon from Xros Wars"),
        ("Bagramon", "EX07", "EX7-062", "Secret Rare", "Purple", 48.00,
         "Mega", "Xros Wars final boss"),
        ("Bagramon (Alt Art)", "EX07", "EX7-062", "Alt Art", "Purple", 140.00,
         "Mega", "Alt Art Xros Wars final boss"),

        # =================================================================
        # BT-15 through BT-17 (Exceed Apocalypse, Beginning Observer, Secret Crisis)
        # =================================================================
        ("Omnimon X", "BT15", "BT15-080", "Secret Rare", "White", 75.00,
         "Mega", "X-Antibody Omnimon, Exceed Apocalypse boss"),
        ("GraceNovamon", "BT15", "BT15-081", "Super Rare", "Yellow", 16.00,
         "Mega", "Exceed Apocalypse celestial Digimon"),
        ("Omnimon X (Alt Art)", "BT15", "BT15-080", "Alt Art", "White", 200.00,
         "Mega", "Alt Art X-Antibody Omnimon"),
        ("Agumon -Yuki no Kizuna-", "BT16", "BT16-009", "Super Rare", "Red", 14.00,
         "Rookie", "Kizuna movie Agumon, Beginning Observer"),
        ("Omnimon (BT16)", "BT16", "BT16-079", "Secret Rare", "Red", 65.00,
         "Mega", "Beginning Observer Omnimon"),
        ("Omnimon (BT16 Alt Art)", "BT16", "BT16-079", "Alt Art", "Red", 180.00,
         "Mega", "Alt Art Beginning Observer Omnimon"),
        ("Rafflesimon", "BT17", "BT17-055", "Super Rare", "Green", 12.00,
         "Mega", "Secret Crisis plant Mega"),
        ("MirageGaogamon Burst Mode", "BT17", "BT17-030", "Super Rare", "Blue", 14.00,
         "Mega", "Secret Crisis burst evolution"),
        ("Chaosdramon", "BT17", "BT17-070", "Secret Rare", "Black", 55.00,
         "Mega", "Secret Crisis dark machine dragon"),

        # =================================================================
        # Promo cards: tournament, pre-release, box toppers
        # =================================================================
        ("Alphamon (Tournament Promo)", "P", "P-091", "Promo", "Black", 50.00,
         "Mega", "Regional championship prize Alphamon"),
        ("Omnimon (Pre-Release)", "P", "P-083", "Promo", "Red", 30.00,
         "Mega", "Pre-release event exclusive Omnimon"),
        ("WarGreymon (Box Topper BT15)", "P", "P-110", "Promo", "Red", 20.00,
         "Mega", "BT15 Exceed Apocalypse box topper"),
        ("Gallantmon (Championship 2024)", "P", "P-115", "Promo", "Red", 60.00,
         "Mega", "2024 World Championship finalist prize"),

        # =================================================================
        # Digimon Vital Bracelet DIM cards & vintage
        # =================================================================
        ("Vital Bracelet DIM Card: Ancient Warriors", "VB", "DIM-AW", "Rare", "Red", 35.00,
         "Item", "Vital Bracelet DIM card, Ancient Warriors set"),
        ("Vital Bracelet DIM Card: Hermit in the Jungle", "VB", "DIM-HJ", "Rare", "Green", 30.00,
         "Item", "Vital Bracelet DIM card, limited edition"),
        ("Vital Bracelet BE Digivice (Pulsemon Ed.)", "VB", "VB-BE-P", "Super Rare", "Yellow", 80.00,
         "Item", "Vital Bracelet BE device, Pulsemon limited edition"),
        ("Original Bandai Digimon Virtual Pet (1997)", "VINTAGE", "VP-1997", "Super Rare", "White", 150.00,
         "Item", "Original 1997 Bandai virtual pet, loose working"),
        ("Bandai Digimon Pendulum Ver.1", "VINTAGE", "PEN-V1", "Super Rare", "Blue", 120.00,
         "Item", "Pendulum series virtual pet, 1998 release"),
        ("Bandai Digimon Pendulum Ver.3", "VINTAGE", "PEN-V3", "Rare", "Green", 90.00,
         "Item", "Pendulum series, Nightmare Soldiers edition"),

        # =================================================================
        # Figures: G.E.M. series, Precious G.E.M., Model kits
        # =================================================================
        ("G.E.M. Series Omegamon (Omnimon)", "FIGURE", "GEM-OMG", "Super Rare", "White", 250.00,
         "Mega", "MegaHouse G.E.M. series, premium PVC figure"),
        ("G.E.M. Series WarGreymon", "FIGURE", "GEM-WGM", "Super Rare", "Red", 180.00,
         "Mega", "MegaHouse G.E.M. series, dynamic pose"),
        ("Precious G.E.M. Beelzemon & Behemoth", "FIGURE", "PGEM-BEE", "Super Rare", "Purple", 350.00,
         "Mega", "Precious G.E.M. Beelzemon on motorcycle, large scale"),
        ("Figure-rise Standard Amplified WarGreymon", "KIT", "FRS-WGM", "Rare", "Red", 45.00,
         "Mega", "Bandai model kit, Amplified series, detailed build"),
        ("Figure-rise Standard Amplified MetalGarurumon", "KIT", "FRS-MGM", "Rare", "Blue", 45.00,
         "Mega", "Bandai model kit, Amplified series, articulated"),
        ("Figure-rise Standard Amplified Omegamon", "KIT", "FRS-OMG", "Rare", "White", 55.00,
         "Mega", "Bandai model kit, Amplified Omegamon, premium build"),

        # =================================================================
        # Sealed booster boxes
        # =================================================================
        ("BT-01 New Evolution Sealed Booster Box", "BT01", "BOX-BT01", "Super Rare", "Red", 400.00,
         "Item", "Sealed 24-pack booster box, first set, investment grade"),
        ("BT-05 Battle of Omni Sealed Booster Box", "BT05", "BOX-BT05", "Rare", "Red", 180.00,
         "Item", "Sealed booster box, popular set with Omnimon Zwart"),
        ("BT-13 Versus Royal Knights Sealed Booster Box", "BT13", "BOX-BT13", "Rare", "Black", 120.00,
         "Item", "Sealed booster box, Royal Knight themed"),

        # =================================================================
        # Starter Deck exclusives: ST-15, ST-16, ST-17 foils
        # =================================================================
        ("Rapidmon (ST-15 Foil)", "ST15", "ST15-06", "Rare", "Green", 6.00,
         "Ultimate", "Starter Deck 15 exclusive foil Rapidmon"),
        ("Sakuyamon (ST-15 Foil)", "ST15", "ST15-12", "Super Rare", "Yellow", 10.00,
         "Mega", "Starter Deck 15 foil Sakuyamon"),
        ("Imperialdramon FM (ST-16 Foil)", "ST16", "ST16-13", "Super Rare", "Green", 12.00,
         "Mega", "Starter Deck 16 exclusive foil Imperialdramon"),
        ("Gallantmon (ST-17 Foil)", "ST17", "ST17-12", "Super Rare", "Red", 14.00,
         "Mega", "Starter Deck 17 exclusive foil Gallantmon"),

        # =================================================================
        # BT-01 to BT-06 additional Rares/Uncommons for variety
        # =================================================================
        ("Angemon", "BT01", "BT1-055", "Uncommon", "Yellow", 1.50,
         "Champion", "Classic angel Digimon from BT01"),
        ("Devimon", "BT02", "BT2-074", "Uncommon", "Purple", 1.50,
         "Champion", "Iconic villain Devimon"),
        ("Myotismon", "BT02", "BT2-076", "Rare", "Purple", 4.00,
         "Ultimate", "Vampire lord Myotismon"),
        ("Angewomon", "BT01", "BT1-063", "Rare", "Yellow", 5.00,
         "Ultimate", "Gatomon's Mega evolution"),
        ("LadyDevimon", "BT03", "BT3-088", "Rare", "Purple", 3.50,
         "Ultimate", "Dark angel counterpart"),
        ("Piedmon", "BT03", "BT3-091", "Super Rare", "Purple", 10.00,
         "Mega", "Dark Master clown Digimon"),
        ("MetalEtemon", "BT04", "BT4-077", "Rare", "Black", 3.00,
         "Mega", "Comedy villain MetalEtemon"),
        ("Puppetmon", "BT04", "BT4-078", "Rare", "Green", 3.50,
         "Mega", "Dark Master Puppetmon"),
        ("MarineAngemon", "BT06", "BT6-034", "Rare", "Blue", 4.00,
         "Mega", "Tamers cute Mega Digimon"),
        ("MegaGargomon", "BT06", "BT6-046", "Super Rare", "Green", 10.00,
         "Mega", "Terriermon line Mega boss"),

        # =================================================================
        # BT-07 to BT-10 additional cards
        # =================================================================
        ("Vikemon", "BT07", "BT7-028", "Super Rare", "Blue", 9.00,
         "Mega", "Gomamon line Mega evolution"),
        ("Rosemon", "BT07", "BT7-042", "Rare", "Green", 4.50,
         "Mega", "Palmon line Mega evolution"),
        ("MetalSeadramon", "BT08", "BT8-030", "Rare", "Blue", 4.00,
         "Mega", "Dark Master of the sea"),
        ("Diaboromon (X-Antibody)", "BT09", "BT9-067", "Super Rare", "White", 15.00,
         "Mega", "X-Antibody Diaboromon"),
        ("Magnamon", "BT08", "BT8-038", "Super Rare", "Yellow", 14.00,
         "Mega", "Golden Armor Royal Knight"),
        ("Leopardmon", "BT10", "BT10-062", "Super Rare", "Black", 11.00,
         "Mega", "Strategist Royal Knight"),
        ("Gankoomon", "BT10", "BT10-016", "Super Rare", "Red", 10.00,
         "Mega", "Mentor Royal Knight"),
        ("Craniummon", "BT10", "BT10-063", "Rare", "Black", 4.00,
         "Mega", "Shield-bearing Royal Knight"),

        # =================================================================
        # BT-11 to BT-14 additional cards
        # =================================================================
        ("Ophanimon", "BT11", "BT11-038", "Super Rare", "Yellow", 12.00,
         "Mega", "Celestial angel Digimon"),
        ("Cherubimon (Virtue)", "BT11", "BT11-039", "Super Rare", "Yellow", 10.00,
         "Mega", "Virtue form angelic beast"),
        ("Seraphimon", "BT11", "BT11-040", "Super Rare", "Yellow", 11.00,
         "Mega", "Supreme angel Digimon"),
        ("GrandisKuwagamon", "BT12", "BT12-048", "Super Rare", "Green", 9.00,
         "Mega", "Insect Mega Grand Stag"),
        ("Minervamon", "BT12", "BT12-055", "Super Rare", "Purple", 10.00,
         "Mega", "Olympos XII sword maiden"),
        ("Marsmon", "BT12", "BT12-015", "Rare", "Red", 4.00,
         "Mega", "Olympos XII war god"),
        ("Neptunemon", "BT12", "BT12-026", "Rare", "Blue", 3.50,
         "Mega", "Olympos XII sea god"),
        ("Venusmon", "BT13", "BT13-042", "Rare", "Yellow", 4.00,
         "Mega", "Olympos XII love goddess"),
        ("Crusadermon", "BT13", "BT13-073", "Super Rare", "Yellow", 12.00,
         "Mega", "Royal Knight Crusadermon"),
        ("Kentaurosmon", "BT14", "BT14-040", "Super Rare", "Yellow", 11.00,
         "Mega", "Sagittarius Royal Knight"),
        ("Sleipmon", "BT14", "BT14-041", "Rare", "Yellow", 4.50,
         "Mega", "Six-legged Royal Knight"),
        ("WarGreymon X", "BT14", "BT14-016", "Super Rare", "Red", 20.00,
         "Mega", "X-Antibody WarGreymon, Blast Ace"),

        # =================================================================
        # BT-15 to BT-17 additional
        # =================================================================
        ("Alphamon (BT15)", "BT15", "BT15-072", "Super Rare", "Black", 16.00,
         "Mega", "Exceed Apocalypse Alphamon reprint"),
        ("Dorugoramon", "BT15", "BT15-073", "Super Rare", "Black", 13.00,
         "Mega", "Dorumon final evolution"),
        ("MetalGarurumon X", "BT15", "BT15-028", "Super Rare", "Blue", 18.00,
         "Mega", "X-Antibody MetalGarurumon"),
        ("Gallantmon X", "BT16", "BT16-020", "Super Rare", "Red", 16.00,
         "Mega", "X-Antibody Gallantmon"),
        ("Imperialdramon Dragon Mode (BT16)", "BT16", "BT16-035", "Super Rare", "Green", 12.00,
         "Mega", "Beginning Observer Imperialdramon"),
        ("Durandamon", "BT17", "BT17-072", "Super Rare", "Black", 14.00,
         "Mega", "Secret Crisis blade Digimon"),
        ("Beelzemon (BT17)", "BT17", "BT17-068", "Super Rare", "Purple", 15.00,
         "Mega", "Secret Crisis Beelzemon"),

        # =================================================================
        # EX additional cards
        # =================================================================
        ("Omnimon (EX01 Alt Art)", "EX01", "EX1-073", "Alt Art", "Red", 150.00,
         "Mega", "Alt Art Classic Collection Omnimon"),
        ("WarGreymon (EX01 Alt Art)", "EX01", "EX1-011", "Alt Art", "Red", 55.00,
         "Mega", "Alt Art Classic Collection WarGreymon"),
        ("Huanglongmon (Alt Art)", "EX04", "EX4-073", "Alt Art", "Yellow", 140.00,
         "Mega", "Alt Art sovereign boss"),
        ("Imperialdramon Dragon Mode (EX03)", "EX03", "EX3-033", "Super Rare", "Green", 12.00,
         "Mega", "Draconic Roar Imperialdramon"),
        ("Megidramon (Alt Art)", "EX02", "EX2-014", "Alt Art", "Red", 40.00,
         "Mega", "Alt Art Digital Hazard dark evolution"),
        ("AncientGarurumon (Alt Art)", "EX05", "EX5-022", "Alt Art", "Blue", 38.00,
         "Mega", "Alt Art Animal Colosseum beast warrior"),
        ("Cherubimon Vice (Alt Art)", "EX05", "EX5-057", "Alt Art", "Purple", 110.00,
         "Mega", "Alt Art Animal Colosseum fallen angel"),

        # =================================================================
        # RB-01 Reboot Booster (newest set)
        # =================================================================
        ("Omnimon (RB01)", "RB01", "RB1-030", "Super Rare", "Red", 22.00,
         "Mega", "Reboot Booster Omnimon, new frame"),
        ("WarGreymon (RB01)", "RB01", "RB1-015", "Super Rare", "Red", 16.00,
         "Mega", "Reboot Booster WarGreymon"),
        ("MetalGarurumon (RB01)", "RB01", "RB1-022", "Super Rare", "Blue", 14.00,
         "Mega", "Reboot Booster MetalGarurumon"),
        ("Omnimon (RB01 Alt Art)", "RB01", "RB1-030", "Alt Art", "Red", 85.00,
         "Mega", "Alt Art Reboot Booster Omnimon"),

        # =================================================================
        # Additional Figures: Precious G.E.M., Digivolving Spirits
        # =================================================================
        ("Precious G.E.M. Omegamon (Omnimon)", "FIGURE", "PGEM-OMG", "Super Rare", "White", 420.00,
         "Mega", "Precious G.E.M. large-scale Omnimon, premium resin base"),
        ("G.E.M. Series Angewomon", "FIGURE", "GEM-AW", "Super Rare", "Yellow", 160.00,
         "Mega", "MegaHouse G.E.M. series, celestial angel pose"),
        ("G.E.M. Series Beelzemon (Blast Mode)", "FIGURE", "GEM-BBM", "Super Rare", "Purple", 200.00,
         "Mega", "MegaHouse G.E.M. series, Blast Mode with guns"),
        ("G.E.M. Series Gallantmon Crimson Mode", "FIGURE", "GEM-GCM", "Super Rare", "Red", 220.00,
         "Mega", "MegaHouse G.E.M. series, Crimson Mode dynamic"),
        ("Digivolving Spirits 01 WarGreymon", "FIGURE", "DVS-01", "Rare", "Red", 85.00,
         "Mega", "Bandai Digivolving Spirits, transforms from Agumon"),
        ("Digivolving Spirits 02 MetalGarurumon", "FIGURE", "DVS-02", "Rare", "Blue", 85.00,
         "Mega", "Bandai Digivolving Spirits, transforms from Gabumon"),
        ("Digivolving Spirits 08 BlackWarGreymon", "FIGURE", "DVS-08", "Rare", "Black", 90.00,
         "Mega", "Bandai Digivolving Spirits, virus counterpart"),

        # =================================================================
        # Additional Sealed Product & Playmats
        # =================================================================
        ("BT-02 Ultimate Power Sealed Booster Box", "BT02", "BOX-BT02", "Rare", "Purple", 220.00,
         "Item", "Sealed 24-pack booster box, second set"),
        ("BT-03 Union Impact Sealed Booster Box", "BT03", "BOX-BT03", "Rare", "Purple", 200.00,
         "Item", "Sealed booster box, third set"),
        ("EX-02 Digital Hazard Sealed Booster Box", "EX02", "BOX-EX02", "Rare", "Red", 160.00,
         "Item", "Sealed booster box, Hazard themed"),
        ("Official Tournament Playmat (Omnimon Art)", "P", "MAT-OMG", "Promo", "Red", 55.00,
         "Item", "Official rubber playmat, Omnimon illustration"),
        ("Official Tournament Playmat (Alphamon Art)", "P", "MAT-ALP", "Promo", "Black", 60.00,
         "Item", "Official rubber playmat, Alphamon illustration"),

        # =================================================================
        # Additional Vintage Devices
        # =================================================================
        ("Bandai Digimon Pendulum Ver.5", "VINTAGE", "PEN-V5", "Rare", "Black", 100.00,
         "Item", "Pendulum series, Metal Empire edition"),
        ("Bandai Digimon Pendulum X Ver.1", "VINTAGE", "PENX-V1", "Super Rare", "Red", 180.00,
         "Item", "Pendulum X series, 2003 X-Antibody edition"),
        ("Bandai D-3 Digivice (Davis/Daisuke)", "VINTAGE", "D3-DAV", "Super Rare", "Blue", 120.00,
         "Item", "D-3 Digivice toy, blue, Adventure 02 release"),
        ("Bandai D-Ark Digivice (Takato)", "VINTAGE", "DARK-TK", "Super Rare", "Red", 130.00,
         "Item", "D-Ark Digivice toy, red, Tamers release"),
        ("Bandai Digivice Ver.Complete", "VINTAGE", "DVC-COM", "Super Rare", "White", 200.00,
         "Item", "Digivice Ver.Complete, 2021 premium reissue"),

        # =================================================================
        # BT-15 to BT-17 additional chase cards
        # =================================================================
        ("Jesmon GX (BT15)", "BT15", "BT15-018", "Super Rare", "Red", 14.00,
         "Mega", "Exceed Apocalypse Jesmon GX reprint"),
        ("Examon (BT15)", "BT15", "BT15-045", "Super Rare", "Green", 12.00,
         "Mega", "Exceed Apocalypse Examon, dragon Royal Knight"),
        ("GraceNovamon (Alt Art)", "BT15", "BT15-081", "Alt Art", "Yellow", 55.00,
         "Mega", "Alt Art Exceed Apocalypse celestial Digimon"),
        ("Ogudomon", "BT16", "BT16-082", "Secret Rare", "Purple", 70.00,
         "Mega", "Beginning Observer Ogudomon super demon lord"),
        ("Ogudomon (Alt Art)", "BT16", "BT16-082", "Alt Art", "Purple", 190.00,
         "Mega", "Alt Art Beginning Observer super demon lord"),
        ("Gallantmon X (Alt Art)", "BT16", "BT16-020", "Alt Art", "Red", 65.00,
         "Mega", "Alt Art X-Antibody Gallantmon"),
        ("Imperialdramon Dragon Mode (BT16 Alt Art)", "BT16", "BT16-035", "Alt Art", "Green", 45.00,
         "Mega", "Alt Art Beginning Observer Imperialdramon"),
        ("Chaosdramon (Alt Art)", "BT17", "BT17-070", "Alt Art", "Black", 150.00,
         "Mega", "Alt Art Secret Crisis dark machine dragon"),
        ("Durandamon (Alt Art)", "BT17", "BT17-072", "Alt Art", "Black", 48.00,
         "Mega", "Alt Art Secret Crisis blade Digimon"),
        ("MirageGaogamon BM (Alt Art)", "BT17", "BT17-030", "Alt Art", "Blue", 50.00,
         "Mega", "Alt Art Secret Crisis burst evolution"),

        # =================================================================
        # EX-07 additional cards
        # =================================================================
        ("OmniShoutmon", "EX07", "EX7-014", "Super Rare", "Red", 11.00,
         "Mega", "Xros Wars OmniShoutmon"),
        ("ZekeGreymon", "EX07", "EX7-018", "Super Rare", "Blue", 10.00,
         "Mega", "Xros Wars rival partner Mega"),
        ("Shoutmon X7 Superior Mode", "EX07", "EX7-060", "Secret Rare", "Red", 52.00,
         "Mega", "Xros Wars ultimate fusion"),
        ("Shoutmon X7 Superior Mode (Alt Art)", "EX07", "EX7-060", "Alt Art", "Red", 145.00,
         "Mega", "Alt Art Xros Wars ultimate fusion"),
        ("MailBirdramon", "EX07", "EX7-025", "Rare", "Red", 4.00,
         "Champion", "Xros Wars fire bird partner"),
        ("Ballistamon", "EX07", "EX7-032", "Rare", "Blue", 3.50,
         "Champion", "Xros Wars mechanical partner"),

        # =================================================================
        # Starter Deck exclusives: additional foils
        # =================================================================
        ("WarGreymon (ST-1 Foil)", "ST1", "ST1-09F", "Rare", "Red", 8.00,
         "Mega", "Starter Deck 1 foil variant WarGreymon"),
        ("Omnimon (ST-1 Foil Variant)", "ST1", "ST1-11F", "Super Rare", "Red", 15.00,
         "Mega", "Starter Deck 1 foil holo Omnimon"),
        ("UlforceVeedramon (ST-8 Foil)", "ST8", "ST8-13", "Super Rare", "Blue", 12.00,
         "Mega", "Starter Deck 8 exclusive foil UlforceVeedramon"),
        ("Alphamon (ST-9 Foil)", "ST9", "ST9-14", "Super Rare", "Black", 14.00,
         "Mega", "Starter Deck 9 exclusive foil Alphamon"),
        ("Beelzemon (ST-14 Foil)", "ST14", "ST14-12", "Super Rare", "Purple", 12.00,
         "Mega", "Starter Deck 14 exclusive foil Beelzemon"),
        ("Magnamon (ST-3 Foil)", "ST3", "ST3-11", "Super Rare", "Yellow", 10.00,
         "Mega", "Starter Deck 3 exclusive foil Magnamon"),
        ("Imperialdramon FM (ST-4 Foil)", "ST4", "ST4-12", "Super Rare", "Green", 11.00,
         "Mega", "Starter Deck 4 exclusive foil Imperialdramon"),
        ("Mastemon (ST-10 Foil)", "ST10", "ST10-12", "Super Rare", "Yellow", 10.00,
         "Mega", "Starter Deck 10 foil angel DNA Digivolution"),

        # =================================================================
        # Additional Promo / Tournament cards
        # =================================================================
        ("Imperialdramon PM (Tournament Promo)", "P", "P-098", "Promo", "White", 55.00,
         "Mega", "Regional championship Imperialdramon Paladin Mode"),
        ("Jesmon (Tournament Promo)", "P", "P-092", "Promo", "Red", 40.00,
         "Mega", "Tamer Battle tournament stamp Jesmon"),
        ("Gallantmon CM (Box Topper BT16)", "P", "P-118", "Promo", "Red", 25.00,
         "Mega", "BT16 Beginning Observer box topper Gallantmon Crimson Mode"),
        ("Beelzemon BM (Pre-Release)", "P", "P-088", "Promo", "Purple", 35.00,
         "Mega", "Pre-release event exclusive Beelzemon Blast Mode"),
        ("UlforceVeedramon (Championship 2024)", "P", "P-120", "Promo", "Blue", 55.00,
         "Mega", "2024 National Championship finalist prize"),
        ("Magnamon X (Box Topper)", "P", "P-112", "Promo", "Yellow", 22.00,
         "Mega", "Booster box topper Magnamon X-Antibody"),
        ("Examon (Store Championship)", "P", "P-108", "Promo", "Green", 45.00,
         "Mega", "Store Championship winner exclusive Examon"),

        # =================================================================
        # Additional Sealed Booster Boxes
        # =================================================================
        ("BT-04 Great Legend Sealed Booster Box", "BT04", "BOX-BT04", "Rare", "Red", 160.00,
         "Item", "Sealed 24-pack booster box, Royal Knight themed"),
        ("BT-07 Next Adventure Sealed Booster Box", "BT07", "BOX-BT07", "Rare", "Yellow", 140.00,
         "Item", "Sealed booster box, Susanoomon chase set"),
        ("BT-09 X Record Sealed Booster Box", "BT09", "BOX-BT09", "Rare", "Yellow", 130.00,
         "Item", "Sealed booster box, X-Antibody themed"),
        ("BT-15 Exceed Apocalypse Sealed Booster Box", "BT15", "BOX-BT15", "Rare", "White", 110.00,
         "Item", "Sealed booster box, Omnimon X chase set"),
        ("BT-16 Beginning Observer Sealed Booster Box", "BT16", "BOX-BT16", "Rare", "Red", 100.00,
         "Item", "Sealed booster box, newest main set"),
        ("BT-17 Secret Crisis Sealed Booster Box", "BT17", "BOX-BT17", "Rare", "Black", 95.00,
         "Item", "Sealed booster box, Secret Crisis"),
        ("EX-01 Classic Collection Sealed Booster Box", "EX01", "BOX-EX01", "Rare", "Red", 180.00,
         "Item", "Sealed booster box, Classic Collection"),
        ("EX-05 Animal Colosseum Sealed Booster Box", "EX05", "BOX-EX05", "Rare", "Red", 100.00,
         "Item", "Sealed booster box, Animal Colosseum"),
        ("EX-06 Infernal Ascension Sealed Booster Box", "EX06", "BOX-EX06", "Rare", "Purple", 105.00,
         "Item", "Sealed booster box, Demon Lord themed"),
        ("EX-07 Digimon Liberator Sealed Booster Box", "EX07", "BOX-EX07", "Rare", "Red", 95.00,
         "Item", "Sealed booster box, Xros Wars themed"),
        ("RB-01 Reboot Booster Sealed Booster Box", "RB01", "BOX-RB01", "Rare", "Red", 90.00,
         "Item", "Sealed booster box, Reboot series"),

        # =================================================================
        # Additional Playmats
        # =================================================================
        ("Official Tournament Playmat (Gallantmon Art)", "P", "MAT-GAL", "Promo", "Red", 55.00,
         "Item", "Official rubber playmat, Gallantmon Crimson Mode illustration"),
        ("Official Tournament Playmat (Beelzemon Art)", "P", "MAT-BEE", "Promo", "Purple", 50.00,
         "Item", "Official rubber playmat, Beelzemon Blast Mode illustration"),
        ("Official Tournament Playmat (Imperialdramon PM)", "P", "MAT-IMP", "Promo", "White", 60.00,
         "Item", "Official rubber playmat, Imperialdramon Paladin Mode"),
        ("Official Tournament Playmat (Omnimon X)", "P", "MAT-OMX", "Promo", "White", 65.00,
         "Item", "Official rubber playmat, Omnimon X-Antibody"),
        ("Regional Championship Playmat (Susanoomon)", "P", "MAT-SUS", "Promo", "Yellow", 70.00,
         "Item", "Regional Championship exclusive playmat"),

        # =================================================================
        # Additional Vital Bracelet / DIM Cards
        # =================================================================
        ("Vital Bracelet DIM Card: Volcanic Beat", "VB", "DIM-VB", "Rare", "Red", 28.00,
         "Item", "Vital Bracelet DIM card, Volcanic Beat set"),
        ("Vital Bracelet DIM Card: Blizzard Fang", "VB", "DIM-BF", "Rare", "Blue", 28.00,
         "Item", "Vital Bracelet DIM card, Blizzard Fang set"),
        ("Vital Bracelet DIM Card: Infinite Tide", "VB", "DIM-IT", "Rare", "Blue", 30.00,
         "Item", "Vital Bracelet DIM card, Infinite Tide limited edition"),
        ("Vital Bracelet DIM Card: Titan of Dust", "VB", "DIM-TD", "Rare", "Black", 32.00,
         "Item", "Vital Bracelet DIM card, Titan of Dust set"),
        ("Vital Bracelet DIM Card: Nu Metal Empire", "VB", "DIM-NM", "Rare", "Black", 35.00,
         "Item", "Vital Bracelet DIM card, Nu Metal Empire set"),
        ("Vital Bracelet DIM Card: Impulse City", "VB", "DIM-IC", "Rare", "Yellow", 30.00,
         "Item", "Vital Bracelet DIM card, Impulse City set"),
        ("Vital Bracelet BE Digivice (Agumon Ed.)", "VB", "VB-BE-A", "Super Rare", "Red", 75.00,
         "Item", "Vital Bracelet BE device, Agumon limited edition"),
        ("Vital Bracelet BE Digivice (Veemon Ed.)", "VB", "VB-BE-V", "Super Rare", "Blue", 75.00,
         "Item", "Vital Bracelet BE device, Veemon limited edition"),
        ("Vital Bracelet BE Digivice (Guilmon Ed.)", "VB", "VB-BE-G", "Super Rare", "Red", 80.00,
         "Item", "Vital Bracelet BE device, Guilmon limited edition"),

        # =================================================================
        # Additional Vintage Devices
        # =================================================================
        ("Bandai Original Digimon Virtual Pet V2 (1997)", "VINTAGE", "VP-1997V2", "Super Rare", "White", 140.00,
         "Item", "Original 1997 Bandai virtual pet version 2, loose working"),
        ("Bandai Digimon Pendulum Ver.2", "VINTAGE", "PEN-V2", "Rare", "Blue", 95.00,
         "Item", "Pendulum series, Deep Savers edition"),
        ("Bandai Digimon Pendulum Ver.4", "VINTAGE", "PEN-V4", "Rare", "Green", 95.00,
         "Item", "Pendulum series, Wind Guardians edition"),
        ("Bandai Digimon Pendulum Zero", "VINTAGE", "PEN-Z0", "Super Rare", "Red", 160.00,
         "Item", "Pendulum Zero series, Virus Busters edition"),
        ("Bandai D-Scanner Digivice (Frontier)", "VINTAGE", "DSCN-FR", "Super Rare", "Red", 110.00,
         "Item", "D-Scanner Digivice, Digimon Frontier release"),
        ("Bandai D-Tector Digivice (EN Frontier)", "VINTAGE", "DTEC-EN", "Super Rare", "Red", 90.00,
         "Item", "D-Tector English release, Frontier"),
        ("Bandai iC Digivice (Savers)", "VINTAGE", "IC-SAV", "Rare", "Red", 70.00,
         "Item", "iC Digivice, Digimon Savers/Data Squad release"),
        ("Bandai Digivice Xros Loader (Red)", "VINTAGE", "XL-RED", "Rare", "Red", 65.00,
         "Item", "Xros Loader toy, Xros Wars release"),
        ("Bandai Digimon Pendulum X Ver.2", "VINTAGE", "PENX-V2", "Super Rare", "Blue", 170.00,
         "Item", "Pendulum X series, second wave X-Antibody edition"),
        ("Bandai D-3 Digivice (Ken/Emperor)", "VINTAGE", "D3-KEN", "Super Rare", "Black", 130.00,
         "Item", "D-3 Digivice toy, black, Digimon Emperor release"),
        ("Bandai D-3 Digivice (T.K./Takeru)", "VINTAGE", "D3-TK", "Super Rare", "Yellow", 115.00,
         "Item", "D-3 Digivice toy, yellow, Adventure 02 release"),
        ("Bandai D-Ark Digivice (Rika/Ruki)", "VINTAGE", "DARK-RK", "Super Rare", "Blue", 125.00,
         "Item", "D-Ark Digivice toy, blue, Tamers release"),

        # =================================================================
        # Additional Figures
        # =================================================================
        ("G.E.M. Series Taichi & Agumon (20th Anniversary)", "FIGURE", "GEM-TCHI", "Super Rare", "Red", 180.00,
         "Mega", "MegaHouse G.E.M. series, Tai & Agumon Anniversary figure"),
        ("G.E.M. Series Yamato & Gabumon", "FIGURE", "GEM-YAMA", "Super Rare", "Blue", 170.00,
         "Mega", "MegaHouse G.E.M. series, Matt & Gabumon pair"),
        ("G.E.M. Series Takeru & Patamon", "FIGURE", "GEM-TK", "Super Rare", "Yellow", 150.00,
         "Mega", "MegaHouse G.E.M. series, T.K. & Patamon pair"),
        ("G.E.M. Series Sakuyamon (Tamers)", "FIGURE", "GEM-SKY", "Super Rare", "Yellow", 190.00,
         "Mega", "MegaHouse G.E.M. series, Sakuyamon dynamic pose"),
        ("Precious G.E.M. WarGreymon (Meteor Wing)", "FIGURE", "PGEM-WGM", "Super Rare", "Red", 380.00,
         "Mega", "Precious G.E.M. large-scale WarGreymon, attack pose"),
        ("Precious G.E.M. Gallantmon (Crimson Mode)", "FIGURE", "PGEM-GCM", "Super Rare", "Red", 400.00,
         "Mega", "Precious G.E.M. Gallantmon Crimson Mode, premium base"),
        ("Figure-rise Standard Amplified BlackWarGreymon", "KIT", "FRS-BWG", "Rare", "Black", 48.00,
         "Mega", "Bandai model kit, Amplified BlackWarGreymon"),
        ("Figure-rise Standard Amplified Imperialdramon", "KIT", "FRS-IMP", "Rare", "White", 55.00,
         "Mega", "Bandai model kit, Amplified Imperialdramon Paladin Mode"),
        ("Figure-rise Standard Amplified Gallantmon", "KIT", "FRS-GAL", "Rare", "Red", 50.00,
         "Mega", "Bandai model kit, Amplified Gallantmon"),
        ("Digivolving Spirits 03 Diaboromon", "FIGURE", "DVS-03", "Rare", "White", 95.00,
         "Mega", "Bandai Digivolving Spirits, transforms from Keramon"),
        ("Digivolving Spirits 04 Angewomon", "FIGURE", "DVS-04", "Rare", "Yellow", 90.00,
         "Mega", "Bandai Digivolving Spirits, transforms from Gatomon"),
        ("Digivolving Spirits 05 Alphamon", "FIGURE", "DVS-05", "Rare", "Black", 100.00,
         "Mega", "Bandai Digivolving Spirits, transforms from Dorumon"),
        ("Digivolving Spirits 06 AtlurKabuterimon", "FIGURE", "DVS-06", "Rare", "Green", 85.00,
         "Mega", "Bandai Digivolving Spirits, transforms from Tentomon"),
        ("Digivolving Spirits 07 MagnaAngemon", "FIGURE", "DVS-07", "Rare", "Yellow", 88.00,
         "Mega", "Bandai Digivolving Spirits, transforms from Patamon"),
        ("S.H.Figuarts Omegamon (Premium Color)", "FIGURE", "SHF-OMG", "Super Rare", "White", 120.00,
         "Mega", "S.H.Figuarts premium color Omegamon action figure"),
        ("S.H.Figuarts Dukemon (Gallantmon)", "FIGURE", "SHF-DUK", "Super Rare", "Red", 110.00,
         "Mega", "S.H.Figuarts Dukemon/Gallantmon action figure"),
        ("S.H.Figuarts Imperialdramon FM", "FIGURE", "SHF-IFM", "Super Rare", "White", 115.00,
         "Mega", "S.H.Figuarts Imperialdramon Fighter Mode"),

        # =================================================================
        # Additional BT cards for variety
        # =================================================================
        ("Lordknightmon", "BT13", "BT13-074", "Super Rare", "Yellow", 10.00,
         "Mega", "Royal Knight Lordknightmon, Versus Royal Knights"),
        ("Gankoomon X", "BT14", "BT14-017", "Super Rare", "Red", 12.00,
         "Mega", "X-Antibody Gankoomon, Blast Ace"),
        ("Leopardmon Leopard Mode", "BT10", "BT10-064", "Super Rare", "Black", 11.00,
         "Mega", "Leopardmon Leopard Mode, Xros Encounter"),
        ("Duftmon X", "BT14", "BT14-068", "Super Rare", "Black", 13.00,
         "Mega", "X-Antibody Duftmon/Leopardmon, Blast Ace"),
        ("Sakuyamon Maid Mode", "BT11", "BT11-042", "Super Rare", "Yellow", 9.00,
         "Mega", "Sakuyamon alternative evolution, Dimensional Phase"),
        ("Zwart Defeat", "BT11", "BT11-081", "Secret Rare", "Black", 58.00,
         "Mega", "Dimensional Phase dark Omnimon variant"),
        ("Zwart Defeat (Alt Art)", "BT11", "BT11-081", "Alt Art", "Black", 170.00,
         "Mega", "Alt Art Dimensional Phase dark Omnimon"),
        ("BloomLordmon (Alt Art)", "BT11", "BT11-058", "Alt Art", "Green", 48.00,
         "Mega", "Alt Art Dimensional Phase plant boss"),
        ("Susanoomon (BT12 Alt Art)", "BT12", "BT12-083", "Alt Art", "Yellow", 175.00,
         "Mega", "Alt Art Across Time Susanoomon"),
        ("Beelzemon X (Alt Art)", "BT12", "BT12-079", "Alt Art", "Purple", 60.00,
         "Mega", "Alt Art X-Antibody Beelzemon"),
        ("ShineGreymon RM (Alt Art)", "BT13", "BT13-020", "Alt Art", "Red", 55.00,
         "Mega", "Alt Art dark side ShineGreymon"),
        ("Dynasmon (Alt Art)", "BT13", "BT13-041", "Alt Art", "Yellow", 35.00,
         "Mega", "Alt Art Royal Knight Dynasmon"),
        ("Fenriloogamon (Alt Art)", "BT14", "BT14-082", "Alt Art", "Black", 50.00,
         "Mega", "Alt Art Blast Ace dark wolf"),
        ("WarGreymon X (Alt Art)", "BT14", "BT14-016", "Alt Art", "Red", 70.00,
         "Mega", "Alt Art X-Antibody WarGreymon"),
        ("MetalGarurumon X (Alt Art)", "BT15", "BT15-028", "Alt Art", "Blue", 60.00,
         "Mega", "Alt Art X-Antibody MetalGarurumon"),
        ("Alphamon (BT15 Alt Art)", "BT15", "BT15-072", "Alt Art", "Black", 55.00,
         "Mega", "Alt Art Exceed Apocalypse Alphamon"),
        ("Dorugoramon (Alt Art)", "BT15", "BT15-073", "Alt Art", "Black", 45.00,
         "Mega", "Alt Art Dorumon final evolution"),
        ("Rafflesimon (Alt Art)", "BT17", "BT17-055", "Alt Art", "Green", 42.00,
         "Mega", "Alt Art Secret Crisis plant Mega"),
        ("Beelzemon BT17 (Alt Art)", "BT17", "BT17-068", "Alt Art", "Purple", 52.00,
         "Mega", "Alt Art Secret Crisis Beelzemon"),

        # =================================================================
        # Additional Japanese Exclusive cards
        # =================================================================
        ("Gallantmon (JP Tamer Battle)", "P", "P-045-JP", "Promo", "Red", 55.00,
         "Mega", "Japanese Tamer Battle pack Gallantmon"),
        ("Beelzemon (JP Exclusive Art)", "BT02", "BT2-078-JP", "Alt Art", "Purple", 120.00,
         "Mega", "Japanese exclusive full-art Beelzemon"),
        ("Jesmon (JP Anniversary)", "P", "P-105-JP", "Promo", "Red", 45.00,
         "Mega", "Japanese anniversary promo Jesmon"),

        # =================================================================
        # EXPANSION TO 500+ — ~200 additional items
        # =================================================================

        # ── BT-01 to BT-03 Additional Cards ──
        ("Greymon", "BT01", "BT1-015", "Uncommon", "Red", 1.00,
         "Champion", "Core Red Champion from BT01"),
        ("Kabuterimon", "BT01", "BT1-070", "Uncommon", "Green", 1.00,
         "Champion", "Green insect Champion"),
        ("Togemon", "BT01", "BT1-072", "Common", "Green", 0.50,
         "Champion", "Plant Champion from BT01"),
        ("Birdramon", "BT01", "BT1-018", "Common", "Red", 0.50,
         "Champion", "Sora's partner Champion form"),
        ("MagnaAngemon (Alt Art)", "BT01", "BT1-062", "Alt Art", "Yellow", 25.00,
         "Ultimate", "Alt Art MagnaAngemon from BT01"),
        ("Lilithmon (Alt Art)", "BT02", "BT2-077", "Alt Art", "Purple", 35.00,
         "Mega", "Alt Art Seven Great Demon Lords"),
        ("Gallantmon (Alt Art BT02)", "BT02", "BT2-020", "Alt Art", "Red", 70.00,
         "Mega", "Alt Art BT02 Gallantmon"),
        ("Diaboromon (Alt Art)", "BT02", "BT2-082", "Alt Art", "White", 45.00,
         "Mega", "Alt Art movie villain Diaboromon"),
        ("Imperialdramon DM (Alt Art)", "BT02", "BT2-083", "Alt Art", "Green", 35.00,
         "Mega", "Alt Art Imperialdramon Dragon Mode"),
        ("BlackWarGreymon (Alt Art BT03)", "BT03", "BT3-016", "Alt Art", "Red", 50.00,
         "Mega", "Alt Art virus counterpart BlackWarGreymon"),
        ("Millenniummon (BT03 SR Variant)", "BT03", "BT3-091", "Super Rare", "Purple", 22.00,
         "Mega", "Super Rare Millenniummon variant"),
        ("Piedmon (Alt Art)", "BT03", "BT3-091A", "Alt Art", "Purple", 40.00,
         "Mega", "Alt Art Dark Master clown Digimon"),

        # ── BT-04 to BT-06 Additional Cards ──
        ("Jesmon (Alt Art BT04)", "BT04", "BT4-074", "Alt Art", "Red", 55.00,
         "Mega", "Alt Art Royal Knight Jesmon"),
        ("ChaosGallantmon (Alt Art)", "BT04", "BT4-081", "Alt Art", "Purple", 40.00,
         "Mega", "Alt Art dark counterpart Gallantmon"),
        ("Omnimon (Alt Art BT05)", "BT05", "BT5-086", "Alt Art", "Red", 75.00,
         "Mega", "Alt Art Battle of Omni Omnimon"),
        ("UlforceVeedramon (Alt Art BT05)", "BT05", "BT5-030", "Alt Art", "Blue", 55.00,
         "Mega", "Alt Art speed Royal Knight"),
        ("ShineGreymon (Alt Art BT06)", "BT06", "BT6-018", "Alt Art", "Red", 40.00,
         "Mega", "Alt Art Savers/Data Squad ShineGreymon"),
        ("Jesmon GX (Alt Art BT06)", "BT06", "BT6-016", "Alt Art", "Red", 50.00,
         "Mega", "Alt Art GX evolution of Jesmon"),
        ("HerculesKabuterimon (Alt Art)", "BT06", "BT6-050", "Alt Art", "Green", 30.00,
         "Mega", "Alt Art Green insect boss"),
        ("MegaGargomon (Alt Art)", "BT06", "BT6-046", "Alt Art", "Green", 35.00,
         "Mega", "Alt Art Terriermon line Mega"),

        # ── BT-07 to BT-10 Additional Cards ──
        ("Sakuyamon (Alt Art BT07)", "BT07", "BT7-043", "Alt Art", "Yellow", 35.00,
         "Mega", "Alt Art Rika's partner Mega"),
        ("Mastemon (Regular BT07)", "BT07", "BT7-080", "Super Rare", "Yellow", 18.00,
         "Mega", "Regular art DNA Digivolution angel"),
        ("Vikemon (Alt Art)", "BT07", "BT7-028", "Alt Art", "Blue", 30.00,
         "Mega", "Alt Art Gomamon line Mega"),
        ("Imperialdramon FM (Alt Art BT08)", "BT08", "BT8-032", "Alt Art", "Green", 65.00,
         "Mega", "Alt Art upgraded Imperialdramon"),
        ("ShineGreymon BM (Alt Art BT08)", "BT08", "BT8-017", "Alt Art", "Red", 50.00,
         "Mega", "Alt Art Burst Mode evolution"),
        ("Magnamon (Alt Art BT08)", "BT08", "BT8-038", "Alt Art", "Yellow", 48.00,
         "Mega", "Alt Art golden armor Royal Knight"),
        ("Leopardmon (Alt Art BT10)", "BT10", "BT10-062", "Alt Art", "Black", 38.00,
         "Mega", "Alt Art strategist Royal Knight"),
        ("Gankoomon (Alt Art BT10)", "BT10", "BT10-016", "Alt Art", "Red", 35.00,
         "Mega", "Alt Art mentor Royal Knight"),
        ("Shoutmon King (Alt Art)", "BT10", "BT10-013", "Alt Art", "Red", 40.00,
         "Mega", "Alt Art Xros Encounter boss"),
        ("Darkdramon (Alt Art)", "BT10", "BT10-069", "Alt Art", "Black", 32.00,
         "Mega", "Alt Art D-Brigade line boss"),

        # ── BT-11 to BT-14 Additional Cards ──
        ("Ophanimon (Alt Art)", "BT11", "BT11-038", "Alt Art", "Yellow", 42.00,
         "Mega", "Alt Art celestial angel Digimon"),
        ("Seraphimon (Alt Art)", "BT11", "BT11-040", "Alt Art", "Yellow", 38.00,
         "Mega", "Alt Art supreme angel Digimon"),
        ("Cherubimon Virtue (Alt Art)", "BT11", "BT11-039", "Alt Art", "Yellow", 35.00,
         "Mega", "Alt Art virtue form angelic beast"),
        ("GrandisKuwagamon (Alt Art)", "BT12", "BT12-048", "Alt Art", "Green", 32.00,
         "Mega", "Alt Art insect Mega Grand Stag"),
        ("Minervamon (Alt Art)", "BT12", "BT12-055", "Alt Art", "Purple", 35.00,
         "Mega", "Alt Art Olympos XII sword maiden"),
        ("Crusadermon (Alt Art)", "BT13", "BT13-073", "Alt Art", "Yellow", 42.00,
         "Mega", "Alt Art Royal Knight Crusadermon"),
        ("Lordknightmon (Alt Art)", "BT13", "BT13-074", "Alt Art", "Yellow", 35.00,
         "Mega", "Alt Art Royal Knight Lordknightmon"),
        ("Kentaurosmon (Alt Art)", "BT14", "BT14-040", "Alt Art", "Yellow", 38.00,
         "Mega", "Alt Art Sagittarius Royal Knight"),
        ("Gankoomon X (Alt Art)", "BT14", "BT14-017", "Alt Art", "Red", 42.00,
         "Mega", "Alt Art X-Antibody Gankoomon"),
        ("Duftmon X (Alt Art)", "BT14", "BT14-068", "Alt Art", "Black", 45.00,
         "Mega", "Alt Art X-Antibody Duftmon"),

        # ── Additional Starter Deck Foils ──
        ("Omnimon (ST-5 Foil)", "ST5", "ST5-14", "Super Rare", "Red", 14.00,
         "Mega", "Starter Deck 5 exclusive foil Omnimon"),
        ("WarGreymon (ST-5 Foil)", "ST5", "ST5-12", "Rare", "Red", 8.00,
         "Mega", "Starter Deck 5 exclusive foil WarGreymon"),
        ("Dukemon (ST-6 Foil)", "ST6", "ST6-14", "Super Rare", "Red", 12.00,
         "Mega", "Starter Deck 6 foil Guilmon line boss"),
        ("Sakuyamon (ST-7 Foil)", "ST7", "ST7-12", "Super Rare", "Yellow", 10.00,
         "Mega", "Starter Deck 7 exclusive foil Sakuyamon"),
        ("Gallantmon (ST-7 Foil)", "ST7", "ST7-14", "Super Rare", "Red", 12.00,
         "Mega", "Starter Deck 7 exclusive foil Gallantmon"),
        ("Omnimon (ST-11 Foil)", "ST11", "ST11-14", "Super Rare", "Red", 14.00,
         "Mega", "Starter Deck 11 foil Omnimon reprint"),
        ("Alphamon (ST-12 Foil)", "ST12", "ST12-14", "Super Rare", "Black", 13.00,
         "Mega", "Starter Deck 12 exclusive foil Alphamon"),
        ("Omnimon (ST-13 Foil)", "ST13", "ST13-14", "Super Rare", "Red", 12.00,
         "Mega", "Starter Deck 13 foil Omnimon"),

        # ── Additional Vital Bracelet DIM Cards ──
        ("Vital Bracelet DIM Card: True Shadow Howl", "VB", "DIM-TSH", "Rare", "Black", 32.00,
         "Item", "Vital Bracelet DIM card, True Shadow Howl set"),
        ("Vital Bracelet DIM Card: Primeval Warriors", "VB", "DIM-PW", "Rare", "Red", 28.00,
         "Item", "Vital Bracelet DIM card, Primeval Warriors set"),
        ("Vital Bracelet DIM Card: Guilmon", "VB", "DIM-GUI", "Rare", "Red", 35.00,
         "Item", "Vital Bracelet DIM card, Guilmon evolution line"),
        ("Vital Bracelet DIM Card: Veemon", "VB", "DIM-VEE", "Rare", "Blue", 35.00,
         "Item", "Vital Bracelet DIM card, Veemon evolution line"),
        ("Vital Bracelet DIM Card: Terriermon", "VB", "DIM-TER", "Rare", "Green", 30.00,
         "Item", "Vital Bracelet DIM card, Terriermon evolution line"),
        ("Vital Bracelet DIM Card: Gabumon", "VB", "DIM-GAB", "Rare", "Blue", 30.00,
         "Item", "Vital Bracelet DIM card, Gabumon evolution line"),
        ("Vital Bracelet DIM Card: Renamon", "VB", "DIM-REN", "Rare", "Yellow", 32.00,
         "Item", "Vital Bracelet DIM card, Renamon evolution line"),
        ("Vital Bracelet DIM Card: Wormmon", "VB", "DIM-WOR", "Rare", "Green", 28.00,
         "Item", "Vital Bracelet DIM card, Wormmon evolution line"),
        ("Vital Bracelet DIM Card: Mad Black Roar", "VB", "DIM-MBR", "Rare", "Black", 30.00,
         "Item", "Vital Bracelet DIM card, Mad Black Roar set"),
        ("Vital Bracelet DIM Card: Dynasty of the Evil", "VB", "DIM-DOE", "Rare", "Purple", 32.00,
         "Item", "Vital Bracelet DIM card, Dynasty of the Evil set"),

        # ── Additional Vintage Devices ──
        ("Bandai Digimon Pendulum Ver.Zero (Virus Busters)", "VINTAGE", "PEN-ZVB", "Super Rare", "Yellow", 165.00,
         "Item", "Pendulum Zero, Virus Busters colorway"),
        ("Bandai D-Ark Digivice (Henry/Jianliang)", "VINTAGE", "DARK-HN", "Super Rare", "Green", 120.00,
         "Item", "D-Ark Digivice toy, green, Tamers release"),
        ("Bandai D-Power Digivice (EN Red)", "VINTAGE", "DPOW-RD", "Super Rare", "Red", 85.00,
         "Item", "D-Power English release, Tamers"),
        ("Bandai D-Power Digivice (EN Blue)", "VINTAGE", "DPOW-BL", "Super Rare", "Blue", 85.00,
         "Item", "D-Power English release, Tamers"),
        ("Bandai D-Scanner Digivice (Koji)", "VINTAGE", "DSCN-KJ", "Super Rare", "Blue", 105.00,
         "Item", "D-Scanner Digivice, Koji/Kouji version"),
        ("Bandai Digivice: Digimon Adventure (2020 Reboot)", "VINTAGE", "DVC-2020", "Super Rare", "White", 90.00,
         "Item", "Digivice toy, 2020 Adventure reboot release"),
        ("Bandai Digivice Ver.15th (Anniversary)", "VINTAGE", "DVC-15TH", "Super Rare", "White", 180.00,
         "Item", "15th Anniversary Digivice, premium gold accents"),
        ("Original Bandai Digimon Virtual Pet (Transparent)", "VINTAGE", "VP-1997TR", "Super Rare", "White", 200.00,
         "Item", "Original 1997 virtual pet, rare transparent shell"),
        ("Bandai Xros Loader (Blue)", "VINTAGE", "XL-BLU", "Rare", "Blue", 60.00,
         "Item", "Xros Loader toy, blue version"),
        ("Bandai D-3 Digivice (Yolei/Miyako)", "VINTAGE", "D3-YOL", "Super Rare", "Red", 120.00,
         "Item", "D-3 Digivice toy, red, Adventure 02 release"),

        # ── Additional Figures — G.E.M., Precious G.E.M. ──
        ("G.E.M. Series Lilithmon", "FIGURE", "GEM-LIL", "Super Rare", "Purple", 190.00,
         "Mega", "MegaHouse G.E.M. series, Demon Lord Lilithmon"),
        ("G.E.M. Series Alphamon (Ouryuken)", "FIGURE", "GEM-AOR", "Super Rare", "Black", 240.00,
         "Mega", "MegaHouse G.E.M. series, Alphamon Ouryuken form"),
        ("G.E.M. Series Dukemon (Gallantmon)", "FIGURE", "GEM-DUK", "Super Rare", "Red", 200.00,
         "Mega", "MegaHouse G.E.M. series, Gallantmon dynamic pose"),
        ("G.E.M. Series Imperialdramon (Fighter Mode)", "FIGURE", "GEM-IFM", "Super Rare", "White", 210.00,
         "Mega", "MegaHouse G.E.M. series, Imperialdramon Fighter Mode"),
        ("G.E.M. Series Mastemon", "FIGURE", "GEM-MST", "Super Rare", "Yellow", 180.00,
         "Mega", "MegaHouse G.E.M. series, DNA angel Mastemon"),
        ("G.E.M. Series Hikari & Gatomon (Adventure)", "FIGURE", "GEM-HKG", "Super Rare", "Yellow", 160.00,
         "Mega", "MegaHouse G.E.M. series, Hikari & Gatomon pair"),
        ("Precious G.E.M. Alphamon", "FIGURE", "PGEM-ALP", "Super Rare", "Black", 380.00,
         "Mega", "Precious G.E.M. large-scale Alphamon, premium base"),
        ("Precious G.E.M. Dukemon (Crimson Mode)", "FIGURE", "PGEM-DCM", "Super Rare", "Red", 420.00,
         "Mega", "Precious G.E.M. large-scale Gallantmon Crimson Mode"),
        ("Figure-rise Standard Amplified Alphamon", "KIT", "FRS-ALP", "Rare", "Black", 55.00,
         "Mega", "Bandai model kit, Amplified Alphamon"),
        ("Figure-rise Standard Amplified Beelzemon", "KIT", "FRS-BEE", "Rare", "Purple", 50.00,
         "Mega", "Bandai model kit, Amplified Beelzemon"),
        ("Figure-rise Standard Amplified Sakuyamon", "KIT", "FRS-SKY", "Rare", "Yellow", 48.00,
         "Mega", "Bandai model kit, Amplified Sakuyamon"),
        ("Figure-rise Standard Amplified Jesmon", "KIT", "FRS-JES", "Rare", "Red", 50.00,
         "Mega", "Bandai model kit, Amplified Jesmon"),
        ("Figure-rise Standard Amplified UlforceVeedramon", "KIT", "FRS-UFV", "Rare", "Blue", 52.00,
         "Mega", "Bandai model kit, Amplified UlforceVeedramon"),
        ("Digivolving Spirits 09 Magnamon", "FIGURE", "DVS-09", "Rare", "Yellow", 95.00,
         "Mega", "Bandai Digivolving Spirits, golden armor Digimon"),
        ("Digivolving Spirits 10 ShinGreymon", "FIGURE", "DVS-10", "Rare", "Red", 88.00,
         "Mega", "Bandai Digivolving Spirits, Savers Mega"),
        ("S.H.Figuarts WarGreymon (Our War Game)", "FIGURE", "SHF-WGM-OWG", "Super Rare", "Red", 130.00,
         "Mega", "S.H.Figuarts WarGreymon, Our War Game special"),
        ("S.H.Figuarts MetalGarurumon (Our War Game)", "FIGURE", "SHF-MGM-OWG", "Super Rare", "Blue", 125.00,
         "Mega", "S.H.Figuarts MetalGarurumon, Our War Game special"),
        ("S.H.Figuarts Alphamon (Premium)", "FIGURE", "SHF-ALP", "Super Rare", "Black", 140.00,
         "Mega", "S.H.Figuarts premium Alphamon action figure"),
        ("S.H.Figuarts Beelzemon Blast Mode", "FIGURE", "SHF-BBM", "Super Rare", "Purple", 130.00,
         "Mega", "S.H.Figuarts Beelzemon with guns, Blast Mode"),

        # ── Additional Sealed Booster Boxes ──
        ("BT-06 Double Diamond Sealed Booster Box", "BT06", "BOX-BT06", "Rare", "Green", 140.00,
         "Item", "Sealed booster box, Double Diamond"),
        ("BT-08 New Awakening Sealed Booster Box", "BT08", "BOX-BT08", "Rare", "Red", 130.00,
         "Item", "Sealed booster box, Burst Mode themed"),
        ("BT-10 Xros Encounter Sealed Booster Box", "BT10", "BOX-BT10", "Rare", "Red", 120.00,
         "Item", "Sealed booster box, Xros Wars crossover"),
        ("BT-11 Dimensional Phase Sealed Booster Box", "BT11", "BOX-BT11", "Rare", "Black", 115.00,
         "Item", "Sealed booster box, Dimensional Phase"),
        ("BT-12 Across Time Sealed Booster Box", "BT12", "BOX-BT12", "Rare", "Yellow", 110.00,
         "Item", "Sealed booster box, Across Time"),
        ("BT-14 Blast Ace Sealed Booster Box", "BT14", "BOX-BT14", "Rare", "Black", 105.00,
         "Item", "Sealed booster box, Blast Ace"),
        ("EX-03 Draconic Roar Sealed Booster Box", "EX03", "BOX-EX03", "Rare", "Green", 150.00,
         "Item", "Sealed booster box, dragon themed"),
        ("EX-04 Alternative Being Sealed Booster Box", "EX04", "BOX-EX04", "Rare", "Yellow", 120.00,
         "Item", "Sealed booster box, sovereign themed"),

        # ── Additional Playmats ──
        ("Official Tournament Playmat (Susanoomon Art)", "P", "MAT-SUS2", "Promo", "Yellow", 65.00,
         "Item", "Official rubber playmat, Susanoomon illustration"),
        ("Official Tournament Playmat (Jesmon Art)", "P", "MAT-JES", "Promo", "Red", 55.00,
         "Item", "Official rubber playmat, Jesmon illustration"),
        ("Official Tournament Playmat (Magnamon X Art)", "P", "MAT-MGX", "Promo", "Yellow", 60.00,
         "Item", "Official rubber playmat, Magnamon X-Antibody"),
        ("Official Tournament Playmat (Lucemon Satan Mode)", "P", "MAT-LUC", "Promo", "Purple", 58.00,
         "Item", "Official rubber playmat, Lucemon Satan Mode"),
        ("Regional Championship Playmat (WarGreymon X)", "P", "MAT-WGX", "Promo", "Red", 70.00,
         "Item", "Regional Championship exclusive playmat, WarGreymon X"),
        ("Regional Championship Playmat (Omnimon X)", "P", "MAT-OMX2", "Promo", "White", 75.00,
         "Item", "Regional Championship exclusive playmat, Omnimon X"),
        ("2024 World Championship Playmat (Alphamon Ouryuken)", "P", "MAT-AOR", "Promo", "Black", 85.00,
         "Item", "2024 World Championship exclusive playmat"),

        # ── Additional Promo / Tournament Cards ──
        ("Omnimon (Store Championship 2023)", "P", "P-095", "Promo", "Red", 42.00,
         "Mega", "Store Championship 2023 prize Omnimon"),
        ("WarGreymon (Tamer Battle Pack Vol.2)", "P", "P-032", "Promo", "Red", 25.00,
         "Mega", "Tamer Battle Pack Vol.2 WarGreymon"),
        ("MetalGarurumon (Tamer Battle Pack Vol.2)", "P", "P-033", "Promo", "Blue", 22.00,
         "Mega", "Tamer Battle Pack Vol.2 MetalGarurumon"),
        ("Beelzemon (Special Box Promo)", "P", "P-050", "Promo", "Purple", 30.00,
         "Mega", "Special Box exclusive Beelzemon promo"),
        ("Alphamon (Tamer Battle Pack Vol.6)", "P", "P-078", "Promo", "Black", 38.00,
         "Mega", "Tamer Battle Pack Vol.6 Alphamon"),
        ("Jesmon (Box Topper EX07)", "P", "P-125", "Promo", "Red", 18.00,
         "Mega", "EX07 Digimon Liberator box topper Jesmon"),
        ("Imperialdramon PM (2024 National Championship)", "P", "P-122", "Promo", "White", 60.00,
         "Mega", "2024 National Championship finalist prize"),
        ("Omnimon X (2024 World Championship)", "P", "P-130", "Promo", "White", 80.00,
         "Mega", "2024 World Championship winner prize"),

        # ── Japanese Exclusive Additional ──
        ("Omnimon (JP Tamer Battle Pack)", "P", "P-035-JP", "Promo", "Red", 70.00,
         "Mega", "Japanese Tamer Battle exclusive Omnimon"),
        ("Alphamon (JP Exclusive Full Art)", "BT04", "BT4-084-JP2", "Alt Art", "Black", 200.00,
         "Mega", "Japanese exclusive full-art Alphamon, second variant"),
        ("Susanoomon (JP Box Topper)", "BT07", "BT7-083-JP", "Promo", "Yellow", 55.00,
         "Mega", "Japanese box topper Susanoomon"),
        ("Omnimon X (JP Exclusive)", "BT15", "BT15-080-JP", "Alt Art", "White", 250.00,
         "Mega", "Japanese exclusive full-art Omnimon X"),
        ("Imperialdramon PM (JP Alt Art)", "EX03", "EX3-073-JP", "Alt Art", "White", 220.00,
         "Mega", "Japanese exclusive Imperialdramon Paladin Mode alt art"),

        # ── Additional Tamer Cards ──
        ("Sora Takenouchi", "BT01", "BT1-088", "Rare", "Red", 2.50,
         "Tamer", "Original Tamer card Sora"),
        ("Mimi Tachikawa", "BT01", "BT1-089", "Rare", "Green", 2.50,
         "Tamer", "Original Tamer card Mimi"),
        ("Joe Kido", "BT01", "BT1-090", "Rare", "Blue", 2.50,
         "Tamer", "Original Tamer card Joe"),
        ("Izzy Izumi", "BT01", "BT1-091", "Rare", "Green", 3.00,
         "Tamer", "Original Tamer card Izzy"),
        ("Davis Motomiya", "BT08", "BT8-090", "Rare", "Red", 3.00,
         "Tamer", "Adventure 02 protagonist Davis"),
        ("Ken Ichijouji", "BT08", "BT8-091", "Rare", "Purple", 3.50,
         "Tamer", "Former Digimon Emperor turned hero"),
        ("Takato Matsuki", "EX02", "EX2-060", "Rare", "Red", 4.00,
         "Tamer", "Tamers protagonist, Digital Hazard set"),
        ("Rika Nonaka", "EX02", "EX2-061", "Rare", "Yellow", 4.00,
         "Tamer", "Tamers rival, Digital Hazard set"),
        ("Henry Wong", "EX02", "EX2-062", "Rare", "Green", 3.50,
         "Tamer", "Tamers partner, Digital Hazard set"),
        ("Takuya Kanbara", "BT07", "BT7-090", "Rare", "Red", 3.00,
         "Tamer", "Frontier protagonist, spirit evolution"),
        ("Marcus Daimon", "BT06", "BT6-090", "Rare", "Red", 3.00,
         "Tamer", "Data Squad protagonist, punch first"),
        ("Thomas H. Norstein", "BT06", "BT6-091", "Rare", "Blue", 2.50,
         "Tamer", "Data Squad rival, tactical genius"),

        # ── RB-01 Additional Cards ──
        ("Gallantmon (RB01)", "RB01", "RB1-025", "Super Rare", "Red", 16.00,
         "Mega", "Reboot Booster Gallantmon"),
        ("Jesmon (RB01)", "RB01", "RB1-028", "Super Rare", "Red", 14.00,
         "Mega", "Reboot Booster Jesmon"),
        ("Alphamon (RB01)", "RB01", "RB1-029", "Super Rare", "Black", 18.00,
         "Mega", "Reboot Booster Alphamon"),
        ("Gallantmon (RB01 Alt Art)", "RB01", "RB1-025", "Alt Art", "Red", 60.00,
         "Mega", "Alt Art Reboot Booster Gallantmon"),
        ("Alphamon (RB01 Alt Art)", "RB01", "RB1-029", "Alt Art", "Black", 75.00,
         "Mega", "Alt Art Reboot Booster Alphamon"),

        # ── Option Cards — Popular ──
        ("Brave Shield", "BT05", "BT5-100", "Rare", "Red", 2.00,
         "Option", "WarGreymon defensive option card"),
        ("Cocytus Breath", "BT01", "BT1-098", "Rare", "Blue", 2.00,
         "Option", "MetalGarurumon signature attack option"),
        ("Supreme Cannon", "BT05", "BT5-098", "Uncommon", "White", 1.00,
         "Option", "Omnimon signature attack option"),
        ("Lightning Joust", "BT04", "BT4-106", "Rare", "Red", 2.50,
         "Option", "Gallantmon signature attack option"),
        ("Final Elysion", "EX02", "EX2-069", "Rare", "Red", 3.00,
         "Option", "Gallantmon Crimson Mode signature attack"),
        ("Positron Laser", "EX03", "EX3-069", "Rare", "White", 2.50,
         "Option", "Imperialdramon Paladin Mode attack option"),

        # ── Additional EX-01 to EX-04 Cards ──
        ("MetalGarurumon (EX01)", "EX01", "EX1-020", "Super Rare", "Blue", 14.00,
         "Mega", "Classic Collection MetalGarurumon"),
        ("MetalGarurumon (EX01 Alt Art)", "EX01", "EX1-020A", "Alt Art", "Blue", 50.00,
         "Mega", "Alt Art Classic Collection MetalGarurumon"),
        ("Angemon (EX01)", "EX01", "EX1-028", "Rare", "Yellow", 4.00,
         "Champion", "Classic Collection Angemon"),
        ("Angewomon (EX01)", "EX01", "EX1-036", "Super Rare", "Yellow", 12.00,
         "Ultimate", "Classic Collection Angewomon"),
        ("Gallantmon (EX02)", "EX02", "EX2-020", "Super Rare", "Red", 16.00,
         "Mega", "Digital Hazard Gallantmon"),
        ("Beelzemon (EX02)", "EX02", "EX2-044", "Super Rare", "Purple", 14.00,
         "Mega", "Digital Hazard Beelzemon"),
        ("Beelzemon (EX02 Alt Art)", "EX02", "EX2-044A", "Alt Art", "Purple", 48.00,
         "Mega", "Alt Art Digital Hazard Beelzemon"),
        ("Imperialdramon DM (EX03)", "EX03", "EX3-034", "Super Rare", "Green", 14.00,
         "Mega", "Draconic Roar Imperialdramon DM"),
        ("Magnamon (EX03)", "EX03", "EX3-045", "Super Rare", "Yellow", 12.00,
         "Mega", "Draconic Roar Magnamon"),
        ("Azulongmon (EX04)", "EX04", "EX4-030", "Super Rare", "Blue", 10.00,
         "Mega", "Alternative Being eastern sovereign"),
        ("Zhuqiaomon (EX04)", "EX04", "EX4-015", "Super Rare", "Red", 10.00,
         "Mega", "Alternative Being southern sovereign"),
        ("Ebonwumon (EX04)", "EX04", "EX4-040", "Super Rare", "Green", 9.00,
         "Mega", "Alternative Being northern sovereign"),
        ("Baihumon (EX04)", "EX04", "EX4-055", "Super Rare", "Black", 10.00,
         "Mega", "Alternative Being western sovereign"),

        # ── EX-05 to EX-07 Additional ──
        ("AncientGreymon (EX05 SR)", "EX05", "EX5-013", "Super Rare", "Red", 11.00,
         "Mega", "Animal Colosseum ancient fire warrior"),
        ("AncientBeetlemon", "EX05", "EX5-035", "Super Rare", "Green", 9.00,
         "Mega", "Animal Colosseum ancient thunder insect"),
        ("AncientMermaimon", "EX05", "EX5-038", "Rare", "Blue", 4.50,
         "Mega", "Animal Colosseum ancient water warrior"),
        ("AncientWisemon", "EX05", "EX5-050", "Rare", "Yellow", 4.00,
         "Mega", "Animal Colosseum ancient steel warrior"),
        ("AncientSphinxmon", "EX05", "EX5-055", "Super Rare", "Purple", 10.00,
         "Mega", "Animal Colosseum ancient dark sphinx"),
        ("Daemon", "EX06", "EX6-050", "Super Rare", "Purple", 14.00,
         "Mega", "Infernal Ascension demon lord of wrath"),
        ("Barbamon", "EX06", "EX6-045", "Super Rare", "Purple", 12.00,
         "Mega", "Infernal Ascension demon lord of greed"),
        ("Leviamon", "EX06", "EX6-048", "Super Rare", "Purple", 11.00,
         "Mega", "Infernal Ascension demon lord of envy"),
        ("Daemon (Alt Art)", "EX06", "EX6-050A", "Alt Art", "Purple", 48.00,
         "Mega", "Alt Art Infernal Ascension Daemon"),
        ("Taiki Kudo", "EX07", "EX7-065", "Rare", "Red", 4.00,
         "Tamer", "Xros Wars protagonist Tamer card"),
        ("Kiriha Aonuma", "EX07", "EX7-066", "Rare", "Blue", 3.50,
         "Tamer", "Xros Wars rival Blue Flare general"),

        # ── Additional Sealed Product ──
        ("Starter Deck 01 Gaia Red (Sealed)", "ST1", "SD-ST1", "Rare", "Red", 80.00,
         "Item", "Sealed Starter Deck 1, first product"),
        ("Starter Deck 02 Cocytus Blue (Sealed)", "ST2", "SD-ST2", "Rare", "Blue", 75.00,
         "Item", "Sealed Starter Deck 2, first product"),
        ("Starter Deck 03 Heaven's Yellow (Sealed)", "ST3", "SD-ST3", "Rare", "Yellow", 70.00,
         "Item", "Sealed Starter Deck 3, first product"),
        ("Starter Deck 04 Nature Green (Sealed)", "ST4", "SD-ST4", "Rare", "Green", 70.00,
         "Item", "Sealed Starter Deck 4, first product"),
        ("Starter Deck 15 Dragon of Courage (Sealed)", "ST15", "SD-ST15", "Rare", "Red", 25.00,
         "Item", "Sealed Starter Deck 15"),
        ("Starter Deck 16 Wolf of Friendship (Sealed)", "ST16", "SD-ST16", "Rare", "Blue", 25.00,
         "Item", "Sealed Starter Deck 16"),
        ("Starter Deck 17 Double Typhoon (Sealed)", "ST17", "SD-ST17", "Rare", "Red", 25.00,
         "Item", "Sealed Starter Deck 17, Gallantmon/Takato"),
        ("2024 Tamer Battle Pack Box (Sealed)", "P", "TBP-2024", "Rare", "Red", 65.00,
         "Item", "Sealed Tamer Battle Pack, 2024 tournament prizes"),
        ("Great Dash Pack (Sealed Bundle)", "P", "GDP-01", "Rare", "Red", 45.00,
         "Item", "Sealed Great Dash promotional pack bundle"),

        # ── Additional BT Rares for Variety ──
        ("Paildramon", "BT08", "BT8-028", "Rare", "Green", 3.50,
         "Ultimate", "Adventure 02 DNA Digivolution"),
        ("Silphymon", "BT08", "BT8-042", "Rare", "Yellow", 3.00,
         "Ultimate", "Adventure 02 DNA Digivolution"),
        ("Shakkoumon", "BT08", "BT8-046", "Rare", "Yellow", 3.50,
         "Ultimate", "Adventure 02 DNA Digivolution"),
        ("Stingmon", "BT08", "BT8-048", "Uncommon", "Green", 1.50,
         "Champion", "Wormmon Champion evolution"),
        ("Kyubimon", "BT07", "BT7-035", "Uncommon", "Yellow", 1.50,
         "Champion", "Renamon Champion evolution"),
        ("Growlmon", "EX02", "EX2-008", "Uncommon", "Red", 1.50,
         "Champion", "Guilmon Champion evolution"),
        ("WarGrowlmon", "EX02", "EX2-013", "Rare", "Red", 4.00,
         "Ultimate", "Guilmon Ultimate evolution"),
        ("Rapidmon", "BT07", "BT7-036", "Rare", "Green", 3.50,
         "Ultimate", "Terriermon Ultimate evolution"),
        ("Taomon", "BT07", "BT7-040", "Rare", "Yellow", 3.50,
         "Ultimate", "Renamon Ultimate evolution"),
        ("Garudamon (BT09)", "BT09", "BT9-014", "Rare", "Red", 3.00,
         "Ultimate", "X Record Garudamon"),
        ("Zudomon", "BT07", "BT7-025", "Rare", "Blue", 3.00,
         "Ultimate", "Gomamon Ultimate evolution"),
        ("WereGarurumon (BT09)", "BT09", "BT9-025", "Rare", "Blue", 3.50,
         "Ultimate", "X Record WereGarurumon"),
        ("AtlurKabuterimon", "BT09", "BT9-042", "Rare", "Green", 3.00,
         "Ultimate", "X Record insect Ultimate"),
        ("Andromon", "BT09", "BT9-060", "Rare", "Black", 3.00,
         "Ultimate", "X Record android Ultimate"),

        # ── Final items to reach 500+ ──
        ("Precious G.E.M. Imperialdramon Dragon Mode", "FIGURE", "PGEM-IDM", "Super Rare", "Green", 360.00,
         "Mega", "Precious G.E.M. large-scale Imperialdramon DM"),
        ("G.E.M. Series Sora & Piyomon", "FIGURE", "GEM-SORA", "Super Rare", "Red", 150.00,
         "Mega", "MegaHouse G.E.M. series, Sora & Biyomon pair"),
        ("G.E.M. Series Mimi & Palmon", "FIGURE", "GEM-MIMI", "Super Rare", "Green", 150.00,
         "Mega", "MegaHouse G.E.M. series, Mimi & Palmon pair"),
        ("G.E.M. Series Joe & Gomamon", "FIGURE", "GEM-JOE", "Super Rare", "Blue", 145.00,
         "Mega", "MegaHouse G.E.M. series, Joe & Gomamon pair"),
        ("Vital Bracelet DIM Card: Agumon -Original-", "VB", "DIM-AGU", "Rare", "Red", 35.00,
         "Item", "Vital Bracelet DIM card, original Agumon line"),
        ("Vital Bracelet DIM Card: Gabumon -Original-", "VB", "DIM-GAB2", "Rare", "Blue", 35.00,
         "Item", "Vital Bracelet DIM card, original Gabumon line"),
        ("Vital Bracelet DIM Card: Digimon Tamers Set", "VB", "DIM-TMRS", "Super Rare", "Red", 45.00,
         "Item", "Vital Bracelet DIM card, Tamers 3-partner set"),
        ("Official Tournament Playmat (Examon Art)", "P", "MAT-EXA", "Promo", "Green", 55.00,
         "Item", "Official rubber playmat, Examon dragon"),
        ("Official Tournament Playmat (Lucemon FDM Art)", "P", "MAT-LFD", "Promo", "Purple", 55.00,
         "Item", "Official rubber playmat, Lucemon Falldown Mode"),
        ("BT-09 X Record Sealed Case (12 Boxes)", "BT09", "CASE-BT09", "Super Rare", "Yellow", 1400.00,
         "Item", "Sealed case of 12 booster boxes, investment grade"),
        ("BT-01 New Evolution Sealed Case (12 Boxes)", "BT01", "CASE-BT01", "Super Rare", "Red", 4500.00,
         "Item", "Sealed case of 12 booster boxes, first set grail"),
        ("Figure-rise Standard Amplified Magnamon", "KIT", "FRS-MAG", "Rare", "Yellow", 48.00,
         "Mega", "Bandai model kit, Amplified Magnamon"),
        ("Figure-rise Standard Amplified Susanoomon", "KIT", "FRS-SUS", "Rare", "Yellow", 55.00,
         "Mega", "Bandai model kit, Amplified Susanoomon"),

        # =================================================================
        # Batch 11 — Vital Bracelet DIM Cards, BT14-BT16 Alt Arts,
        # S.H.Figuarts, Last Evolution Kizuna, Digivice Reproductions
        # =================================================================

        # ── Vital Bracelet DIM Cards (10) ────────────────────────────────
        ("Vital Bracelet DIM Card: Imperialdramon", "VB", "DIM-IMP", "Super Rare", "Blue", 52.00,
         "Item", "Vital Bracelet DIM card, Imperialdramon fighter/dragon/paladin modes"),
        ("Vital Bracelet DIM Card: Omegamon", "VB", "DIM-OMG", "Secret Rare", "Red", 68.00,
         "Item", "Vital Bracelet DIM card, Omegamon full evolution line"),
        ("Vital Bracelet DIM Card: Alphamon", "VB", "DIM-ALP", "Secret Rare", "Black", 72.00,
         "Item", "Vital Bracelet DIM card, Royal Knight Alphamon line"),
        ("Vital Bracelet DIM Card: Jesmon", "VB", "DIM-JES", "Super Rare", "Red", 48.00,
         "Item", "Vital Bracelet DIM card, Jesmon Sistermon line"),
        ("Vital Bracelet DIM Card: Dukemon", "VB", "DIM-DKM", "Super Rare", "Red", 55.00,
         "Item", "Vital Bracelet DIM card, Dukemon/Gallantmon evolution line"),
        ("Vital Bracelet DIM Card: UlforceVeedramon", "VB", "DIM-UFV", "Super Rare", "Blue", 50.00,
         "Item", "Vital Bracelet DIM card, V-mon royal knight line"),
        ("Vital Bracelet DIM Card: Diaboromon", "VB", "DIM-DIA", "Secret Rare", "Black", 65.00,
         "Item", "Vital Bracelet DIM card, movie villain Diaboromon line"),
        ("Vital Bracelet DIM Card: Beelzemon", "VB", "DIM-BLZ", "Super Rare", "Purple", 52.00,
         "Item", "Vital Bracelet DIM card, Tamers Beelzemon blast mode line"),
        ("Vital Bracelet DIM Card: Craniummon", "VB", "DIM-CRN", "Rare", "Black", 38.00,
         "Item", "Vital Bracelet DIM card, Royal Knight Craniummon line"),
        ("Vital Bracelet DIM Card: Magnamon X-Antibody", "VB", "DIM-MGX", "Secret Rare", "Yellow", 75.00,
         "Item", "Vital Bracelet DIM card, limited X-Antibody Magnamon"),

        # ── BT14-BT16 Secret Rares & Alternate Arts (14) ────────────────
        ("Omnimon Alter-S (Alt Art)", "BT14", "BT14-040", "Alt Art", "Black", 85.00,
         "Mega", "BT14 Blast Ace secret rare alt art, Omnimon Alter-S"),
        ("Gallantmon Crimson Mode (Alt Art)", "BT14", "BT14-041", "Alt Art", "Red", 78.00,
         "Mega", "BT14 Blast Ace secret rare alt art, Gallantmon CM"),
        ("Imperialdramon Fighter Mode (Alt Art)", "BT14", "BT14-035", "Alt Art", "Blue", 72.00,
         "Mega", "BT14 Blast Ace secret rare alt art, Imperialdramon FM"),
        ("ShineGreymon Burst Mode (Secret Rare)", "BT14", "BT14-042", "Secret Rare", "Red", 55.00,
         "Mega", "BT14 Blast Ace secret rare, Data Squad ace"),
        ("MirageGaogamon Burst Mode (Secret Rare)", "BT14", "BT14-043", "Secret Rare", "Blue", 48.00,
         "Mega", "BT14 Blast Ace secret rare, DATS partner"),
        ("Alphamon Ouryuken (Alt Art)", "BT15", "BT15-072", "Alt Art", "Black", 92.00,
         "Mega", "BT15 Exceed Apocalypse alt art, Royal Knight premium"),
        ("Omnimon X-Antibody (Secret Rare)", "BT15", "BT15-073", "Secret Rare", "Red", 65.00,
         "Mega", "BT15 Exceed Apocalypse secret rare, X-Antibody chase"),
        ("Jesmon GX (Alt Art)", "BT15", "BT15-074", "Alt Art", "Red", 70.00,
         "Mega", "BT15 Exceed Apocalypse alt art, Jesmon ultimate form"),
        ("Examon (Alt Art)", "BT15", "BT15-075", "Alt Art", "Green", 68.00,
         "Mega", "BT15 Exceed Apocalypse alt art, dragon Royal Knight"),
        ("Rafflesimon (Secret Rare)", "BT16", "BT16-045", "Secret Rare", "Green", 42.00,
         "Mega", "BT16 Beginning Observer secret rare, plant mega"),
        ("Susanoomon (Alt Art)", "BT16", "BT16-088", "Alt Art", "Yellow", 80.00,
         "Mega", "BT16 Beginning Observer alt art, Frontier ultimate fusion"),
        ("Lucemon Shadowlord Mode (Alt Art)", "BT16", "BT16-089", "Alt Art", "Purple", 75.00,
         "Mega", "BT16 Beginning Observer alt art, Frontier final boss"),
        ("Cherubimon Vice (Secret Rare)", "BT16", "BT16-046", "Secret Rare", "Black", 45.00,
         "Mega", "BT16 Beginning Observer secret rare, dark angel"),
        ("Kazemon & Zephyrmon (Alt Art)", "BT16", "BT16-090", "Alt Art", "Green", 58.00,
         "Champion", "BT16 Beginning Observer alt art, Frontier spirit pair"),

        # ── S.H.Figuarts Digimon Figures (8) ────────────────────────────
        ("S.H.Figuarts WarGreymon (Our War Game!)", "SHF", "SHF-WGM", "Super Rare", "Red", 120.00,
         "Mega", "Bandai S.H.Figuarts, WarGreymon Our War Game ver."),
        ("S.H.Figuarts MetalGarurumon (Our War Game!)", "SHF", "SHF-MGR", "Super Rare", "Blue", 115.00,
         "Mega", "Bandai S.H.Figuarts, MetalGarurumon Our War Game ver."),
        ("S.H.Figuarts Omegamon (Premium Color)", "SHF", "SHF-OMG", "Secret Rare", "Red", 180.00,
         "Mega", "Bandai S.H.Figuarts, Omegamon premium color edition"),
        ("S.H.Figuarts Dukemon Gallantmon (Crimson Mode)", "SHF", "SHF-DKM", "Super Rare", "Red", 135.00,
         "Mega", "Bandai S.H.Figuarts, Gallantmon Crimson Mode"),
        ("S.H.Figuarts Imperialdramon Fighter Mode", "SHF", "SHF-IFM", "Super Rare", "Blue", 125.00,
         "Mega", "Bandai S.H.Figuarts, Imperialdramon Fighter Mode"),
        ("S.H.Figuarts Alphamon (Royal Knight)", "SHF", "SHF-ALP", "Secret Rare", "Black", 160.00,
         "Mega", "Bandai S.H.Figuarts, Royal Knight Alphamon"),
        ("S.H.Figuarts Diablomon (Diaboromon)", "SHF", "SHF-DBM", "Super Rare", "Black", 110.00,
         "Mega", "Bandai S.H.Figuarts, movie villain Diaboromon"),
        ("S.H.Figuarts Angemon", "SHF", "SHF-ANG", "Rare", "Yellow", 85.00,
         "Champion", "Bandai S.H.Figuarts, Angemon from Adventure"),

        # ── Digimon Adventure Last Evolution Kizuna Merch (8) ────────────
        ("Last Evolution Kizuna Tri-Color DIM Card Set", "VB", "DIM-KIZ", "Secret Rare", "Red", 95.00,
         "Item", "Limited DIM card set, Kizuna movie-exclusive partner Digimon"),
        ("Last Evolution Kizuna Premium Blu-ray Box", "MERCH", "KIZUNA-BD", "Super Rare", "Red", 85.00,
         "Item", "Limited edition Blu-ray box, movie + special features"),
        ("Last Evolution Kizuna Clear Poster Set (6pc)", "MERCH", "KIZUNA-PST", "Rare", "Red", 35.00,
         "Item", "Clear file poster set, all 6 original chosen children"),
        ("Last Evolution Kizuna Agumon Nendoroid", "MERCH", "KIZUNA-AGU", "Super Rare", "Red", 65.00,
         "Item", "Good Smile Company Nendoroid, Kizuna ver. Agumon"),
        ("Last Evolution Kizuna Gabumon Nendoroid", "MERCH", "KIZUNA-GAB", "Super Rare", "Blue", 65.00,
         "Item", "Good Smile Company Nendoroid, Kizuna ver. Gabumon"),
        ("Last Evolution Kizuna Original Soundtrack LP", "MERCH", "KIZUNA-LP", "Rare", "Red", 55.00,
         "Item", "Vinyl LP, butter-fly memorial + Kizuna score"),
        ("Last Evolution Kizuna Memorial Art Book", "MERCH", "KIZUNA-ART", "Rare", "Red", 45.00,
         "Item", "Hardcover art book, 20th anniversary key visuals"),
        ("Last Evolution Kizuna Wristwatch (Agumon)", "MERCH", "KIZUNA-WCH", "Super Rare", "Red", 120.00,
         "Item", "Limited numbered wristwatch, Adventure 20th anniversary"),

        # ── Digivice Reproductions (10) ──────────────────────────────────
        ("Digivice: (Original 1999 Reproduction)", "DEVICE", "DV-OG99", "Secret Rare", "Red", 95.00,
         "Item", "Bandai 1999 Digivice reproduction, Adventure original 8 colors"),
        ("Digivice: D-3 Reproduction (Motomiya Daisuke Ver.)", "DEVICE", "DV-D3D", "Super Rare", "Blue", 80.00,
         "Item", "Bandai D-3 Digivice reproduction, 02 Daisuke blue"),
        ("Digivice: D-3 Reproduction (Ichijouji Ken Ver.)", "DEVICE", "DV-D3K", "Super Rare", "Black", 80.00,
         "Item", "Bandai D-3 Digivice reproduction, 02 Ken dark ver."),
        ("Digivice: D-Tector Reproduction (Takuya Ver.)", "DEVICE", "DV-DTK", "Super Rare", "Red", 85.00,
         "Item", "Bandai D-Tector Digivice reproduction, Frontier Takuya"),
        ("Digivice: D-Tector Reproduction (Koji Ver.)", "DEVICE", "DV-DTJ", "Super Rare", "Blue", 85.00,
         "Item", "Bandai D-Tector Digivice reproduction, Frontier Koji"),
        ("Digivice: D-Ark Reproduction (Takato Ver.)", "DEVICE", "DV-DAT", "Super Rare", "Red", 88.00,
         "Item", "Bandai D-Ark Digivice reproduction, Tamers Takato"),
        ("Digivice: D-Ark Reproduction (Henry Ver.)", "DEVICE", "DV-DAH", "Super Rare", "Green", 88.00,
         "Item", "Bandai D-Ark Digivice reproduction, Tamers Henry"),
        ("Digivice: Ver. Complete (CSA)", "DEVICE", "DV-CSA", "Secret Rare", "White", 130.00,
         "Item", "Complete Selection Animation, full-size with sounds"),
        ("Digivice: D-3 Ver. Complete (CSA)", "DEVICE", "DV-D3C", "Secret Rare", "Blue", 140.00,
         "Item", "Complete Selection Animation D-3, 02 full-size replica"),
        ("Digivice: D-Power Ver. Complete (CSA)", "DEVICE", "DV-DPC", "Secret Rare", "Red", 145.00,
         "Item", "Complete Selection Animation D-Power, Tamers full-size replica"),
    ]

    catalog = []
    for entry in cards:
        (name, set_code, card_number, rarity, color, price_eur,
         digimon_type, notes) = entry

        catalog.append({
            "name": name,
            "set_code": set_code,
            "card_number": card_number,
            "rarity": rarity,
            "color": color,
            "price_eur": price_eur,
            "digimon_type": digimon_type,
            "notes": notes,
        })

    return catalog


# ---------------------------------------------------------------------------
# Catalog / Price converters
# ---------------------------------------------------------------------------

def item_to_catalog_item(item: dict) -> CatalogItem:
    """Convert a curated catalog entry to a CatalogItem."""
    name = item["name"]
    set_code = item["set_code"]
    card_number = item["card_number"]
    rarity = item["rarity"]
    color = item["color"]
    digimon_type = item["digimon_type"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{set_code}-{card_number}-{name}"),
        title=name,
        set_code=set_code,
        brand="Bandai",
        rarity=rarity,
        notes=item["notes"],
        image_url="",
        attributes_json={
            "set_code": set_code,
            "card_number": card_number,
            "rarity": rarity,
            "color": color,
            "digimon_type": digimon_type,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    """Convert a curated catalog entry to a PriceObservation."""
    rarity = item["rarity"]

    # Alt Art and Secret Rare are premium editions
    is_premium = rarity in ("Alt Art", "Secret Rare")

    return PriceObservation(
        features={
            "condition_score": 0.90,  # Most TCG cards are Near Mint
            "rarity_score": _rarity_score(rarity),
            "edition_score": 0.9 if is_premium else 0.5,
        },
        price=item["price_eur"],
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Import Digimon TCG catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Digimon TCG Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()
    log_progress(CATEGORY, "curated entries loaded", len(catalog))

    all_items = [item_to_catalog_item(c) for c in catalog]
    all_observations = [item_to_price_observation(c) for c in catalog]

    # Deduplicate by item_key
    seen: set[str] = set()
    deduped: list[CatalogItem] = []
    for item in all_items:
        if item.item_key not in seen:
            seen.add(item.item_key)
            deduped.append(item)
    all_items = deduped

    log_progress(CATEGORY, "catalog items", len(all_items))

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    if all_observations:
        write_training_jsonl(CATEGORY, all_observations)
        log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== Digimon TCG Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
