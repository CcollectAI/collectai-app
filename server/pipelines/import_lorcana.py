"""
Import Disney Lorcana card data.

Layer 1 (Catalog):  All cards → category_items
Layer 2 (Prices):   Market prices → train.jsonl + market_hits

API: Uses lorcanajson.org (community JSON database)
Fallback: Manual curated data for initial sets

Usage:
    python -m pipelines.import_lorcana [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem, PriceObservation, MarketHit, SupabaseIngest,
    write_training_jsonl, write_catalog_sql, fetch_json,
    log_progress, slugify, to_eur,
    rarity_score as shared_rarity_score,
    RARITY_SCORE_MAP,
    logger,
    close_http_client,
)

CATEGORY = "lorcana"
# Community API for Lorcana card data
API_BASE = "https://api.lorcanajson.org"


def fetch_all_cards() -> list[dict]:
    """Fetch all Lorcana cards from the community API."""
    try:
        data = fetch_json(f"{API_BASE}/cards")
        if isinstance(data, list):
            cards = data
        elif isinstance(data, dict):
            cards = data.get("data", data.get("cards", []))
        else:
            cards = []
        log_progress(CATEGORY, "cards fetched", len(cards))
        return cards
    except Exception as e:
        logger.info(f"API fetch failed ({e}), using curated seed data...")
        return _curated_seed_cards()


def _curated_seed_cards() -> list[dict]:
    """Curated high-value Lorcana cards when API is unavailable."""
    sets = [
        ("TFC", "The First Chapter"),
        ("ROF", "Rise of the Floodborn"),
        ("ITI", "Into the Inklands"),
        ("URR", "Ursula's Return"),
        ("SSK", "Shimmering Skies"),
        ("AZU", "Azurite Sea"),
        ("PROMO", "Promotional Cards"),
    ]

    cards = []
    # High-value cards per set (enchanted/legendary)
    notable_cards = [
        ("TFC", "Elsa - Spirit of Winter", "Legendary", "enchanted", 180.0),
        ("TFC", "Mickey Mouse - True Friend", "Legendary", "enchanted", 120.0),
        ("TFC", "Stitch - Rock Star", "Super Rare", "standard", 15.0),
        ("TFC", "Maleficent - Monstrous Dragon", "Super Rare", "standard", 12.0),
        ("TFC", "Robin Hood - Unrivaled Archer", "Legendary", "enchanted", 200.0),
        ("ROF", "Belle - Strange but Special", "Legendary", "enchanted", 150.0),
        ("ROF", "Hades - King of Olympus", "Super Rare", "standard", 18.0),
        ("ROF", "Beast - Hardheaded", "Legendary", "enchanted", 100.0),
        ("ITI", "Rapunzel - Sunshine", "Legendary", "enchanted", 90.0),
        ("ITI", "Tinker Bell - Giant Fairy", "Super Rare", "standard", 20.0),
        ("URR", "Ursula - Sea Witch Queen", "Legendary", "enchanted", 85.0),
        ("URR", "Simba - Returned King", "Super Rare", "standard", 14.0),
        ("SSK", "Moana - Born Leader", "Legendary", "enchanted", 60.0),
        ("SSK", "Jafar - Striking Illusionist", "Super Rare", "standard", 16.0),
        ("AZU", "Ariel - Determined Collector", "Legendary", "enchanted", 50.0),
        ("AZU", "Captain Hook - Ruthless Pirate", "Super Rare", "standard", 12.0),

        # ── The First Chapter — additional ─────────────────────────────────
        ("TFC", "Aurora - Dreaming Guardian", "Legendary", "enchanted", 95.0),
        ("TFC", "Cruella De Vil - Miserable as Usual", "Super Rare", "standard", 10.0),
        ("TFC", "Simba - Future King", "Legendary", "standard", 25.0),
        ("TFC", "Maui - Demigod", "Super Rare", "standard", 14.0),
        ("TFC", "Aladdin - Prince Ali", "Super Rare", "standard", 8.0),
        ("TFC", "Hades - Infernal Schemer", "Super Rare", "standard", 9.0),
        ("TFC", "Rapunzel - Gifted with Healing", "Legendary", "enchanted", 160.0),
        ("TFC", "Tinker Bell - Peter Pan's Ally", "Super Rare", "standard", 11.0),
        ("TFC", "Moana - Of Motunui", "Legendary", "standard", 28.0),

        # ── Rise of the Floodborn — additional ─────────────────────────────
        ("ROF", "Mulan - Imperial Soldier", "Legendary", "enchanted", 130.0),
        ("ROF", "Gaston - Baritone Bully", "Super Rare", "standard", 12.0),
        ("ROF", "Cinderella - Ballroom Sensation", "Legendary", "enchanted", 110.0),
        ("ROF", "Maui - Half-Shark", "Super Rare", "standard", 15.0),
        ("ROF", "Lilo - Making a Wish", "Legendary", "enchanted", 140.0),
        ("ROF", "Lady Tremaine - Overbearing Matriarch", "Super Rare", "standard", 10.0),
        ("ROF", "Scar - Shameless Firebug", "Legendary", "standard", 22.0),
        ("ROF", "Cogsworth - Grandfather Clock", "Super Rare", "standard", 8.0),

        # ── Into the Inklands — additional ─────────────────────────────────
        ("ITI", "Maui - Hero to All", "Legendary", "enchanted", 100.0),
        ("ITI", "Peter Pan - Lost Boy Leader", "Super Rare", "standard", 16.0),
        ("ITI", "Robin Hood - Champion of Sherwood", "Legendary", "enchanted", 85.0),
        ("ITI", "Hades - Lord of the Underworld", "Legendary", "standard", 30.0),
        ("ITI", "Minnie Mouse - Wide-Eyed Diver", "Legendary", "enchanted", 75.0),
        ("ITI", "Goofy - Knight for a Day", "Super Rare", "standard", 12.0),
        ("ITI", "Piglet - Very Small Animal", "Super Rare", "standard", 10.0),

        # ── Ursula's Return — additional ───────────────────────────────────
        ("URR", "Mickey Mouse - Musketeer", "Legendary", "enchanted", 95.0),
        ("URR", "Elsa - Ice Surfer", "Legendary", "enchanted", 80.0),
        ("URR", "Hercules - True Hero", "Super Rare", "standard", 18.0),
        ("URR", "Cruella De Vil - Perfectly Wretched", "Legendary", "standard", 26.0),
        ("URR", "Diablo - Devoted Herald", "Super Rare", "standard", 12.0),
        ("URR", "Aurora - Briar Rose", "Legendary", "enchanted", 70.0),
        ("URR", "Maleficent - Sinister Visitor", "Super Rare", "standard", 15.0),

        # ── Shimmering Skies — additional ──────────────────────────────────
        ("SSK", "Stitch - Carefree Surfer", "Legendary", "enchanted", 75.0),
        ("SSK", "Tinker Bell - Generous Fairy", "Super Rare", "standard", 14.0),
        ("SSK", "Gaston - Intellectual Powerhouse", "Legendary", "standard", 20.0),
        ("SSK", "Pocahontas - Windborne", "Legendary", "enchanted", 65.0),
        ("SSK", "Merlin - Rabbit", "Super Rare", "standard", 10.0),
        ("SSK", "Scar - Fiery Usurper", "Legendary", "standard", 22.0),
        ("SSK", "Jasmine - Desert Moon", "Super Rare", "standard", 13.0),

        # ── Azurite Sea — additional ───────────────────────────────────────
        ("AZU", "Moana - Wayfinder", "Legendary", "enchanted", 55.0),
        ("AZU", "Sebastian - Court Composer", "Super Rare", "standard", 10.0),
        ("AZU", "Ursula - Deceiver", "Legendary", "enchanted", 50.0),
        ("AZU", "Triton - The Sea King", "Legendary", "standard", 28.0),
        ("AZU", "Flounder - Loyal Friend", "Super Rare", "standard", 8.0),
        ("AZU", "Scuttle - Expert on Humans", "Super Rare", "standard", 7.0),
        ("AZU", "Jafar - Royal Vizier", "Legendary", "standard", 24.0),

        # ── The First Chapter — Enchanted Rares (complete) ────────────────
        ("TFC", "Maleficent - Monstrous Dragon", "Legendary", "enchanted", 170.0),
        ("TFC", "Stitch - Rock Star", "Super Rare", "enchanted", 140.0),
        ("TFC", "Cruella De Vil - Miserable as Usual", "Super Rare", "enchanted", 80.0),
        ("TFC", "Hades - Infernal Schemer", "Super Rare", "enchanted", 90.0),
        ("TFC", "Captain Hook - Captain of the Jolly Roger", "Legendary", "enchanted", 150.0),
        ("TFC", "Maui - Demigod", "Super Rare", "enchanted", 75.0),
        ("TFC", "Simba - Future King", "Legendary", "enchanted", 130.0),

        # ── Rise of the Floodborn — Enchanted Rares (complete) ────────────
        ("ROF", "Gaston - Baritone Bully", "Super Rare", "enchanted", 85.0),
        ("ROF", "Maui - Half-Shark", "Super Rare", "enchanted", 90.0),
        ("ROF", "Scar - Shameless Firebug", "Legendary", "enchanted", 120.0),
        ("ROF", "Lady Tremaine - Overbearing Matriarch", "Super Rare", "enchanted", 70.0),
        ("ROF", "Cogsworth - Grandfather Clock", "Super Rare", "enchanted", 65.0),
        ("ROF", "Hercules - Divine Hero", "Legendary", "enchanted", 125.0),
        ("ROF", "Diablo - Devoted Herald", "Super Rare", "enchanted", 75.0),

        # ── Into the Inklands — Enchanted Rares (complete) ────────────────
        ("ITI", "Peter Pan - Lost Boy Leader", "Super Rare", "enchanted", 95.0),
        ("ITI", "Hades - Lord of the Underworld", "Legendary", "enchanted", 110.0),
        ("ITI", "Goofy - Knight for a Day", "Super Rare", "enchanted", 80.0),
        ("ITI", "Piglet - Very Small Animal", "Super Rare", "enchanted", 70.0),
        ("ITI", "Milo Thatch - Scholar", "Legendary", "enchanted", 85.0),
        ("ITI", "Kida - Protector of Atlantis", "Legendary", "enchanted", 100.0),
        ("ITI", "Pacha - Village Leader", "Super Rare", "enchanted", 65.0),

        # ── Ursula's Return — Enchanted Rares (complete) ──────────────────
        ("URR", "Hercules - True Hero", "Super Rare", "enchanted", 85.0),
        ("URR", "Diablo - Devoted Herald", "Super Rare", "enchanted", 70.0),
        ("URR", "Maleficent - Sinister Visitor", "Super Rare", "enchanted", 80.0),
        ("URR", "Cruella De Vil - Perfectly Wretched", "Legendary", "enchanted", 100.0),
        ("URR", "Gaston - Scheming Suitor", "Legendary", "enchanted", 90.0),
        ("URR", "Cogsworth - Reliable Timepiece", "Super Rare", "enchanted", 60.0),
        ("URR", "Tinker Bell - Tiny Tactician", "Legendary", "enchanted", 110.0),

        # ── Shimmering Skies — Enchanted Rares (complete) ─────────────────
        ("SSK", "Tinker Bell - Generous Fairy", "Super Rare", "enchanted", 80.0),
        ("SSK", "Merlin - Rabbit", "Super Rare", "enchanted", 65.0),
        ("SSK", "Gaston - Intellectual Powerhouse", "Legendary", "enchanted", 95.0),
        ("SSK", "Scar - Fiery Usurper", "Legendary", "enchanted", 90.0),
        ("SSK", "Jasmine - Desert Moon", "Super Rare", "enchanted", 70.0),
        ("SSK", "Robin Hood - Daydreamer", "Legendary", "enchanted", 85.0),
        ("SSK", "Rapunzel - Letting Down Her Hair", "Legendary", "enchanted", 100.0),

        # ── Azurite Sea — Enchanted Rares (complete) ──────────────────────
        ("AZU", "Sebastian - Court Composer", "Super Rare", "enchanted", 55.0),
        ("AZU", "Flounder - Loyal Friend", "Super Rare", "enchanted", 50.0),
        ("AZU", "Scuttle - Expert on Humans", "Super Rare", "enchanted", 45.0),
        ("AZU", "Triton - The Sea King", "Legendary", "enchanted", 90.0),
        ("AZU", "Prince Eric - Determined Sailor", "Legendary", "enchanted", 60.0),
        ("AZU", "Hades - Underworld Ruler", "Legendary", "enchanted", 75.0),

        # ── Sealed Product — Booster Boxes ────────────────────────────────
        ("TFC", "The First Chapter Booster Box", "Sealed Product", "sealed", 350.0),
        ("ROF", "Rise of the Floodborn Booster Box", "Sealed Product", "sealed", 160.0),
        ("ITI", "Into the Inklands Booster Box", "Sealed Product", "sealed", 130.0),
        ("URR", "Ursula's Return Booster Box", "Sealed Product", "sealed", 110.0),
        ("SSK", "Shimmering Skies Booster Box", "Sealed Product", "sealed", 100.0),
        ("AZU", "Azurite Sea Booster Box", "Sealed Product", "sealed", 100.0),

        # ── Sealed Product — Illumineer's Trove ──────────────────────────
        ("TFC", "The First Chapter Illumineer's Trove", "Sealed Product", "sealed", 200.0),
        ("ROF", "Rise of the Floodborn Illumineer's Trove", "Sealed Product", "sealed", 90.0),
        ("ITI", "Into the Inklands Illumineer's Trove", "Sealed Product", "sealed", 70.0),
        ("URR", "Ursula's Return Illumineer's Trove", "Sealed Product", "sealed", 60.0),
        ("SSK", "Shimmering Skies Illumineer's Trove", "Sealed Product", "sealed", 55.0),
        ("AZU", "Azurite Sea Illumineer's Trove", "Sealed Product", "sealed", 55.0),

        # ── Sealed Product — Starter Decks ────────────────────────────────
        ("TFC", "The First Chapter Starter Deck Amber/Amethyst", "Sealed Product", "sealed", 45.0),
        ("TFC", "The First Chapter Starter Deck Emerald/Ruby", "Sealed Product", "sealed", 50.0),
        ("TFC", "The First Chapter Starter Deck Sapphire/Steel", "Sealed Product", "sealed", 40.0),
        ("ROF", "Rise of the Floodborn Starter Deck Amber/Sapphire", "Sealed Product", "sealed", 25.0),
        ("ROF", "Rise of the Floodborn Starter Deck Ruby/Amethyst", "Sealed Product", "sealed", 22.0),

        # ── Promotional Cards ─────────────────────────────────────────────
        ("PROMO", "Mickey Mouse - Brave Little Tailor (D23 Expo)", "Legendary", "promo", 500.0),
        ("PROMO", "Stitch - Carefree Surfer (Store Championship)", "Super Rare", "promo", 80.0),
        ("PROMO", "Elsa - Spirit of Winter (Gen Con Promo)", "Legendary", "promo", 250.0),
        ("PROMO", "Robin Hood - Unrivaled Archer (Launch Party)", "Legendary", "promo", 120.0),
        ("PROMO", "Belle - Strange but Special (Championship Promo)", "Legendary", "promo", 150.0),
        ("PROMO", "Maleficent - Monstrous Dragon (Organized Play)", "Super Rare", "promo", 100.0),
        ("PROMO", "Mickey Mouse - True Friend (Challenge Promo)", "Legendary", "promo", 200.0),
        ("PROMO", "Rapunzel - Sunshine (GameStop Promo)", "Legendary", "promo", 60.0),
        ("PROMO", "Tinker Bell - Giant Fairy (League Promo)", "Super Rare", "promo", 45.0),
        ("PROMO", "Hades - King of Olympus (Regional Promo)", "Super Rare", "promo", 70.0),

        # ── The First Chapter — Additional Legendary & Super Rare ─────────
        ("TFC", "Beast - Relentless", "Legendary", "standard", 22.0),
        ("TFC", "Elsa - Snow Queen", "Legendary", "standard", 30.0),
        ("TFC", "Cinderella - Gentle and Kind", "Super Rare", "standard", 8.0),
        ("TFC", "Scar - Betrayer", "Legendary", "standard", 20.0),

        # ── Rise of the Floodborn — Additional ────────────────────────────
        ("ROF", "Rapunzel - Gifted Artist", "Legendary", "standard", 24.0),
        ("ROF", "Aladdin - Street Rat", "Super Rare", "standard", 10.0),
        ("ROF", "Jasmine - Queen of Agrabah", "Legendary", "standard", 22.0),
        ("ROF", "Simba - Rightful King", "Legendary", "standard", 20.0),

        # ── Into the Inklands — Additional ────────────────────────────────
        ("ITI", "Stitch - Abomination", "Legendary", "standard", 28.0),
        ("ITI", "Cinderella - Stouthearted", "Legendary", "standard", 18.0),
        ("ITI", "Mulan - Soldier in Training", "Super Rare", "standard", 12.0),
        ("ITI", "Belle - Bookworm", "Legendary", "standard", 20.0),

        # ── Ursula's Return — Additional ──────────────────────────────────
        ("URR", "Rapunzel - Sunshine", "Legendary", "standard", 22.0),
        ("URR", "Moana - Chosen by the Ocean", "Legendary", "standard", 26.0),
        ("URR", "Genie - On the Job", "Super Rare", "standard", 14.0),
        ("URR", "Aladdin - Prince Ali", "Super Rare", "standard", 10.0),

        # ── Shimmering Skies — Additional ─────────────────────────────────
        ("SSK", "Elsa - Ice Queen", "Legendary", "standard", 24.0),
        ("SSK", "Belle - Hidden Depths", "Legendary", "standard", 18.0),
        ("SSK", "Simba - Fierce Fighter", "Super Rare", "standard", 12.0),
        ("SSK", "Mulan - Imperial Guardian", "Legendary", "standard", 20.0),

        # ── Azurite Sea — Additional ──────────────────────────────────────
        ("AZU", "Rapunzel - Dream Chaser", "Legendary", "standard", 22.0),
        ("AZU", "Stitch - New Dog", "Legendary", "standard", 28.0),
        ("AZU", "Maui - Hero of Men and Women", "Super Rare", "standard", 14.0),
        ("AZU", "Elsa - Glacial Guardian", "Legendary", "standard", 20.0),

        # ── Tournament Prize Cards ────────────────────────────────────────
        ("PROMO", "Mickey Mouse - Brave Little Tailor (Set Championship 2024)", "Legendary", "promo", 400.0),
        ("PROMO", "Stitch - Abomination (Regional Winner)", "Legendary", "promo", 180.0),
        ("PROMO", "Elsa - Spirit of Winter (Worlds 2024)", "Legendary", "promo", 600.0),

        # ── Gift Set / Special Product Exclusives ─────────────────────────
        ("TFC", "The First Chapter Gift Set Exclusive Art Mickey", "Legendary", "standard", 35.0),
        ("ROF", "Rise of the Floodborn Gift Set Exclusive Art Beast", "Legendary", "standard", 25.0),
        ("ITI", "Into the Inklands Gift Set Exclusive Art Rapunzel", "Legendary", "standard", 20.0),

        # ── Ursula's Return — Gift Set & Starter Decks ──────────────────────
        ("URR", "Ursula's Return Gift Set Exclusive Art Ursula", "Legendary", "standard", 22.0),
        ("URR", "Ursula's Return Starter Deck Amber/Amethyst", "Sealed Product", "sealed", 18.0),
        ("URR", "Ursula's Return Starter Deck Ruby/Sapphire", "Sealed Product", "sealed", 18.0),

        # ── Shimmering Skies — Gift Set & Starter Decks ─────────────────────
        ("SSK", "Shimmering Skies Gift Set Exclusive Art Moana", "Legendary", "standard", 18.0),
        ("SSK", "Shimmering Skies Starter Deck Emerald/Steel", "Sealed Product", "sealed", 16.0),
        ("SSK", "Shimmering Skies Starter Deck Amber/Ruby", "Sealed Product", "sealed", 16.0),

        # ── Azurite Sea — Gift Set & Starter Decks ──────────────────────────
        ("AZU", "Azurite Sea Gift Set Exclusive Art Ariel", "Legendary", "standard", 16.0),
        ("AZU", "Azurite Sea Starter Deck Amethyst/Emerald", "Sealed Product", "sealed", 15.0),
        ("AZU", "Azurite Sea Starter Deck Steel/Sapphire", "Sealed Product", "sealed", 15.0),

        # ── Into the Inklands — Starter Decks ───────────────────────────────
        ("ITI", "Into the Inklands Starter Deck Ruby/Sapphire", "Sealed Product", "sealed", 20.0),
        ("ITI", "Into the Inklands Starter Deck Amber/Emerald", "Sealed Product", "sealed", 20.0),

        # ── The First Chapter — Additional Legendary, SR, Rare ──────────────
        ("TFC", "Mufasa - Betrayed Leader", "Legendary", "standard", 18.0),
        ("TFC", "Jafar - Royal Vizier", "Super Rare", "standard", 7.0),
        ("TFC", "Captain Hook - Captain of the Jolly Roger", "Legendary", "standard", 22.0),
        ("TFC", "Gaston - Arrogant Hunter", "Super Rare", "standard", 6.0),
        ("TFC", "Te Ka - Heartless", "Super Rare", "standard", 8.0),
        ("TFC", "Magic Broom - Bucket Brigade", "Super Rare", "standard", 6.0),
        ("TFC", "Flounder - Voice of Reason", "Super Rare", "standard", 5.0),
        ("TFC", "Olaf - Friendly Snowman", "Super Rare", "standard", 7.0),
        ("TFC", "Prince Eric - Dashing and Brave", "Rare", "standard", 3.0),
        ("TFC", "Sebastian - Court Composer", "Rare", "standard", 2.0),
        ("TFC", "Cogsworth - Grandfatherly", "Rare", "standard", 2.0),
        ("TFC", "Lumiere - Fiery Host", "Rare", "standard", 2.5),

        # ── Rise of the Floodborn — Additional Legendary, SR, Rare ──────────
        ("ROF", "Jafar - Lamp Thief", "Legendary", "standard", 20.0),
        ("ROF", "Ursula - Power Hungry", "Legendary", "standard", 22.0),
        ("ROF", "Stitch - Carefree Surfer", "Super Rare", "standard", 12.0),
        ("ROF", "Mickey Mouse - Artful Rogue", "Super Rare", "standard", 10.0),
        ("ROF", "Genie - Wish Granter", "Super Rare", "standard", 9.0),
        ("ROF", "Maleficent - Sorceress", "Super Rare", "standard", 11.0),
        ("ROF", "Captain Hook - Thinking a Happy Thought", "Legendary", "standard", 18.0),
        ("ROF", "Beast - Wolfsbane", "Rare", "standard", 3.0),
        ("ROF", "Lumiere - Illuminary Musketeer", "Rare", "standard", 2.5),
        ("ROF", "Mrs. Potts - Enchanted Teapot", "Rare", "standard", 2.0),
        ("ROF", "Chip - Enchanted Teacup", "Rare", "standard", 2.0),

        # ── Into the Inklands — Additional Legendary, SR, Rare ──────────────
        ("ITI", "Simba - Protective Cub", "Legendary", "standard", 22.0),
        ("ITI", "Elsa - Gloves Off", "Legendary", "standard", 24.0),
        ("ITI", "Anna - Heir to Arendelle", "Super Rare", "standard", 10.0),
        ("ITI", "Sven - Loyal Reindeer", "Super Rare", "standard", 8.0),
        ("ITI", "Donald Duck - Musketeer", "Super Rare", "standard", 9.0),
        ("ITI", "Jasmine - Disguised", "Legendary", "standard", 18.0),
        ("ITI", "Aladdin - Street Rat", "Rare", "standard", 3.0),
        ("ITI", "Abu - Clever Monkey", "Rare", "standard", 2.0),
        ("ITI", "Magic Carpet - Woven Vehicle", "Rare", "standard", 2.5),

        # ── Ursula's Return — Additional Legendary, SR, Rare ────────────────
        ("URR", "Flotsam and Jetsam - Slippery Eels", "Super Rare", "standard", 8.0),
        ("URR", "Ariel - Singing Mermaid", "Legendary", "standard", 22.0),
        ("URR", "Sebastian - Crab Conductor", "Super Rare", "standard", 10.0),
        ("URR", "Scuttle - Resourceful Seagull", "Super Rare", "standard", 7.0),
        ("URR", "Maui - Demigod of the Wind and Sea", "Legendary", "standard", 20.0),
        ("URR", "Stitch - Experiment 626", "Super Rare", "standard", 12.0),
        ("URR", "Nana - Darling Family Dog", "Rare", "standard", 2.0),
        ("URR", "Pongo - Protective Father", "Rare", "standard", 2.5),
        ("URR", "Perdita - Doting Mother", "Rare", "standard", 2.5),

        # ── Shimmering Skies — Additional Legendary, SR, Rare ───────────────
        ("SSK", "Cinderella - Dreamer", "Legendary", "standard", 18.0),
        ("SSK", "Mulan - Armored Warrior", "Legendary", "standard", 20.0),
        ("SSK", "Li Shang - Imperial Captain", "Super Rare", "standard", 10.0),
        ("SSK", "Mushu - Tiny Guardian", "Super Rare", "standard", 8.0),
        ("SSK", "Snow White - Fairest of All", "Legendary", "standard", 22.0),
        ("SSK", "Rapunzel - Sun Drop", "Super Rare", "standard", 12.0),
        ("SSK", "Flynn Rider - Charming Rogue", "Super Rare", "standard", 9.0),
        ("SSK", "Pascal - Loyal Chameleon", "Rare", "standard", 2.0),
        ("SSK", "Maximus - Palace Horse", "Rare", "standard", 2.5),

        # ── Azurite Sea — Additional Legendary, SR, Rare ────────────────────
        ("AZU", "Belle - Inventive Engineer", "Legendary", "standard", 20.0),
        ("AZU", "Cogsworth - Talking Clock", "Super Rare", "standard", 8.0),
        ("AZU", "Lumiere - Dashing Candelabra", "Super Rare", "standard", 9.0),
        ("AZU", "Gaston - Determined Hunter", "Legendary", "standard", 22.0),
        ("AZU", "LeFou - Bumbling Sidekick", "Super Rare", "standard", 6.0),
        ("AZU", "Beast - Enchanted Prince", "Legendary", "standard", 24.0),
        ("AZU", "Mrs. Potts - Warm Hearted", "Rare", "standard", 2.0),
        ("AZU", "Chip - Eager Teacup", "Rare", "standard", 2.0),
        ("AZU", "Wardrobe - Protective Furniture", "Rare", "standard", 2.5),

        # ── Promotional Cards — additional ──────────────────────────────────
        ("PROMO", "Hades - King of Olympus (Set Championship Alt Art)", "Super Rare", "promo", 90.0),
        ("PROMO", "Moana - Of Motunui (Launch Event)", "Legendary", "promo", 80.0),
        ("PROMO", "Cinderella - Gentle and Kind (League Promo)", "Super Rare", "promo", 40.0),
        ("PROMO", "Beast - Relentless (Regional Promo)", "Legendary", "promo", 100.0),
        ("PROMO", "Gaston - Baritone Bully (Store Championship)", "Super Rare", "promo", 60.0),
        ("PROMO", "Simba - Future King (Organized Play)", "Legendary", "promo", 120.0),
        ("PROMO", "Aurora - Briar Rose (League Promo)", "Legendary", "promo", 55.0),
        ("PROMO", "Scar - Betrayer (Challenge Promo)", "Legendary", "promo", 130.0),
        ("PROMO", "Ursula - Sea Witch Queen (Worlds 2025)", "Legendary", "promo", 500.0),
        ("PROMO", "Ariel - Determined Collector (Gen Con 2024)", "Legendary", "promo", 200.0),
        ("PROMO", "Captain Hook - Captain of the Jolly Roger (Prerelease)", "Legendary", "promo", 90.0),
        ("PROMO", "Maui - Demigod (Prerelease)", "Super Rare", "promo", 50.0),
        ("PROMO", "Genie - On the Job (FLGS Exclusive)", "Super Rare", "promo", 35.0),
        ("PROMO", "Jasmine - Queen of Agrabah (Tournament Kit)", "Legendary", "promo", 75.0),
        ("PROMO", "Simba - Returned King (Winner Promo)", "Super Rare", "promo", 85.0),
        ("PROMO", "Stitch - Rock Star (Nationals 2024)", "Super Rare", "promo", 150.0),

        # ── Organized Play Prize Cards ──────────────────────────────────────
        ("PROMO", "Elsa - Spirit of Winter (2024 World Championship)", "Legendary", "promo", 800.0),
        ("PROMO", "Mickey Mouse - True Friend (Lorcana Invitational 2024)", "Legendary", "promo", 350.0),
        ("PROMO", "Robin Hood - Unrivaled Archer (National Winner)", "Legendary", "promo", 280.0),
        ("PROMO", "Belle - Strange but Special (Regionals Top 8)", "Legendary", "promo", 180.0),

        # ── Disney100 Crossover Promos ──────────────────────────────────────
        ("PROMO", "Mickey Mouse - Disney100 Celebration", "Legendary", "promo", 300.0),
        ("PROMO", "Minnie Mouse - Disney100 Celebration", "Legendary", "promo", 250.0),
        ("PROMO", "Goofy - Disney100 Celebration", "Super Rare", "promo", 120.0),
        ("PROMO", "Donald Duck - Disney100 Celebration", "Super Rare", "promo", 130.0),
        ("PROMO", "Cinderella - Disney100 Celebration", "Legendary", "promo", 200.0),

        # ── Accessories — Playmats ──────────────────────────────────────────
        ("PROMO", "Official Playmat - Elsa Spirit of Winter", "Accessory", "accessory", 45.0),
        ("PROMO", "Official Playmat - Mickey Mouse True Friend", "Accessory", "accessory", 40.0),
        ("PROMO", "Official Playmat - Maleficent Dragon", "Accessory", "accessory", 40.0),
        ("PROMO", "Official Playmat - Robin Hood Alt Art", "Accessory", "accessory", 50.0),
        ("PROMO", "Official Playmat - Belle Floodborn Alt Art", "Accessory", "accessory", 45.0),
        ("PROMO", "Official Playmat - Stitch Rock Star", "Accessory", "accessory", 35.0),
        ("PROMO", "Official Playmat - Ursula Sea Witch Queen", "Accessory", "accessory", 40.0),
        ("PROMO", "Official Playmat - Moana Wayfinder", "Accessory", "accessory", 35.0),
        ("PROMO", "Official Playmat - Rapunzel Sunshine", "Accessory", "accessory", 35.0),
        ("PROMO", "Tournament Playmat - Set Championship 2024", "Accessory", "accessory", 80.0),
        ("PROMO", "Tournament Playmat - Regionals 2024", "Accessory", "accessory", 60.0),
        ("PROMO", "Tournament Playmat - Worlds 2024", "Accessory", "accessory", 150.0),

        # ── Accessories — Deck Boxes ────────────────────────────────────────
        ("PROMO", "Official Deck Box - Elsa Spirit of Winter", "Accessory", "accessory", 18.0),
        ("PROMO", "Official Deck Box - Mickey Mouse True Friend", "Accessory", "accessory", 16.0),
        ("PROMO", "Official Deck Box - Stitch Rock Star", "Accessory", "accessory", 15.0),
        ("PROMO", "Official Deck Box - Maleficent Dragon", "Accessory", "accessory", 16.0),
        ("PROMO", "Official Deck Box - Rapunzel Sunshine", "Accessory", "accessory", 15.0),
        ("PROMO", "Official Deck Box - Captain Hook", "Accessory", "accessory", 15.0),

        # ── Accessories — Card Sleeves ──────────────────────────────────────
        ("PROMO", "Official Card Sleeves - Elsa (65 count)", "Accessory", "accessory", 12.0),
        ("PROMO", "Official Card Sleeves - Mickey (65 count)", "Accessory", "accessory", 11.0),
        ("PROMO", "Official Card Sleeves - Stitch (65 count)", "Accessory", "accessory", 11.0),
        ("PROMO", "Official Card Sleeves - Maleficent (65 count)", "Accessory", "accessory", 12.0),
        ("PROMO", "Official Card Sleeves - Robin Hood (65 count)", "Accessory", "accessory", 11.0),
        ("PROMO", "Official Card Sleeves - Ursula (65 count)", "Accessory", "accessory", 12.0),

        # ── Sealed Product — Booster Packs (singles) ────────────────────────
        ("TFC", "The First Chapter Single Booster Pack", "Sealed Product", "sealed", 25.0),
        ("ROF", "Rise of the Floodborn Single Booster Pack", "Sealed Product", "sealed", 8.0),
        ("ITI", "Into the Inklands Single Booster Pack", "Sealed Product", "sealed", 6.0),
        ("URR", "Ursula's Return Single Booster Pack", "Sealed Product", "sealed", 5.0),
        ("SSK", "Shimmering Skies Single Booster Pack", "Sealed Product", "sealed", 5.0),
        ("AZU", "Azurite Sea Single Booster Pack", "Sealed Product", "sealed", 5.0),

        # ── Sealed Product — Gift Sets per set ──────────────────────────────
        ("TFC", "The First Chapter Gift Set", "Sealed Product", "sealed", 60.0),
        ("ROF", "Rise of the Floodborn Gift Set", "Sealed Product", "sealed", 40.0),
        ("ITI", "Into the Inklands Gift Set", "Sealed Product", "sealed", 35.0),
        ("URR", "Ursula's Return Gift Set", "Sealed Product", "sealed", 30.0),
        ("SSK", "Shimmering Skies Gift Set", "Sealed Product", "sealed", 28.0),
        ("AZU", "Azurite Sea Gift Set", "Sealed Product", "sealed", 28.0),

        # ── The First Chapter — Deep Cuts (Rare / Uncommon chase) ───────────
        ("TFC", "Tinker Bell - Tiny Tactician", "Legendary", "standard", 24.0),
        ("TFC", "Coconut Basket", "Rare", "standard", 5.0),
        ("TFC", "Firebird Suit", "Rare", "standard", 3.0),
        ("TFC", "Hans - Scheming Prince", "Rare", "standard", 4.0),
        ("TFC", "Sven - Official Ice Deliverer", "Rare", "standard", 3.0),
        ("TFC", "Dr. Facilier - Agent Provocateur", "Super Rare", "standard", 9.0),
        ("TFC", "Tiana - Celebrating Princess", "Super Rare", "standard", 8.0),

        # ── Rise of the Floodborn — Deep Cuts ──────────────────────────────
        ("ROF", "Captain Hook - Ruthless Pirate", "Legendary", "standard", 20.0),
        ("ROF", "Yzma - Scary Beyond Reason", "Super Rare", "standard", 10.0),
        ("ROF", "Kronk - Right Hand Man", "Super Rare", "standard", 8.0),
        ("ROF", "Kuzco - Wanted Llama", "Rare", "standard", 3.5),
        ("ROF", "Meg - Pulling the Strings", "Super Rare", "standard", 9.0),
        ("ROF", "Hades - Hot-Headed Deity", "Legendary", "standard", 18.0),

        # ── Into the Inklands — Deep Cuts ───────────────────────────────────
        ("ITI", "Gaston - Ambitious Hunter", "Super Rare", "standard", 10.0),
        ("ITI", "Captain Hook - Forceful Duelist", "Legendary", "standard", 20.0),
        ("ITI", "Merlin - Self-Appointed Mentor", "Super Rare", "standard", 9.0),
        ("ITI", "Arthur - Trained Swordsman", "Rare", "standard", 3.0),
        ("ITI", "Madame Mim - Fox", "Super Rare", "standard", 8.0),

        # ── Ursula's Return — Deep Cuts ─────────────────────────────────────
        ("URR", "Jafar - Puppet Master", "Legendary", "standard", 24.0),
        ("URR", "Scar - Vicious Cheater", "Legendary", "standard", 22.0),
        ("URR", "Rapunzel - Resourceful Rebel", "Super Rare", "standard", 10.0),
        ("URR", "Pascal - Supportive Friend", "Rare", "standard", 3.0),
        ("URR", "Mother Gothel - Selfish Manipulator", "Super Rare", "standard", 9.0),

        # ── Shimmering Skies — Deep Cuts ────────────────────────────────────
        ("SSK", "Ariel - Curious Collector", "Legendary", "standard", 22.0),
        ("SSK", "Prince Eric - Seafaring Prince", "Super Rare", "standard", 10.0),
        ("SSK", "Sebastian - Under the Sea", "Super Rare", "standard", 8.0),
        ("SSK", "King Triton - Ruler of the Seas", "Legendary", "standard", 20.0),
        ("SSK", "Flounder - Guppy", "Rare", "standard", 3.0),

        # ── Azurite Sea — Deep Cuts ─────────────────────────────────────────
        ("AZU", "Simba - Brave Lion", "Legendary", "standard", 22.0),
        ("AZU", "Nala - Fierce Lioness", "Super Rare", "standard", 10.0),
        ("AZU", "Timon - Jungle Guide", "Super Rare", "standard", 7.0),
        ("AZU", "Pumbaa - Flatulent Friend", "Super Rare", "standard", 7.0),
        ("AZU", "Rafiki - Mystic Sage", "Legendary", "standard", 18.0),
        ("AZU", "Scar - Dark Schemer", "Legendary", "standard", 24.0),
        ("AZU", "Zazu - Majordomo", "Rare", "standard", 2.5),
        ("AZU", "Mufasa - Great King", "Legendary", "standard", 28.0),

        # ── Enchanted Rares — TFC additional variants ───────────────────────
        ("TFC", "Tinker Bell - Peter Pan's Ally", "Legendary", "enchanted", 100.0),
        ("TFC", "Moana - Of Motunui", "Legendary", "enchanted", 140.0),
        ("TFC", "Beast - Relentless", "Legendary", "enchanted", 120.0),
        ("TFC", "Aladdin - Prince Ali", "Super Rare", "enchanted", 85.0),
        ("TFC", "Elsa - Snow Queen", "Legendary", "enchanted", 150.0),

        # ── Enchanted Rares — ROF additional variants ───────────────────────
        ("ROF", "Rapunzel - Gifted Artist", "Legendary", "enchanted", 115.0),
        ("ROF", "Jasmine - Queen of Agrabah", "Legendary", "enchanted", 105.0),
        ("ROF", "Simba - Rightful King", "Legendary", "enchanted", 110.0),
        ("ROF", "Stitch - Carefree Surfer", "Super Rare", "enchanted", 90.0),
        ("ROF", "Aladdin - Street Rat", "Super Rare", "enchanted", 75.0),

        # ── Enchanted Rares — ITI additional variants ───────────────────────
        ("ITI", "Stitch - Abomination", "Legendary", "enchanted", 120.0),
        ("ITI", "Cinderella - Stouthearted", "Legendary", "enchanted", 90.0),
        ("ITI", "Belle - Bookworm", "Legendary", "enchanted", 100.0),
        ("ITI", "Mulan - Soldier in Training", "Super Rare", "enchanted", 80.0),

        # ── Enchanted Rares — URR additional variants ───────────────────────
        ("URR", "Moana - Chosen by the Ocean", "Legendary", "enchanted", 105.0),
        ("URR", "Rapunzel - Sunshine", "Legendary", "enchanted", 95.0),
        ("URR", "Ariel - Singing Mermaid", "Legendary", "enchanted", 100.0),
        ("URR", "Genie - On the Job", "Super Rare", "enchanted", 75.0),

        # ── Enchanted Rares — SSK additional variants ───────────────────────
        ("SSK", "Elsa - Ice Queen", "Legendary", "enchanted", 100.0),
        ("SSK", "Belle - Hidden Depths", "Legendary", "enchanted", 85.0),
        ("SSK", "Mulan - Imperial Guardian", "Legendary", "enchanted", 95.0),
        ("SSK", "Simba - Fierce Fighter", "Super Rare", "enchanted", 70.0),

        # ── Enchanted Rares — AZU additional variants ───────────────────────
        ("AZU", "Rapunzel - Dream Chaser", "Legendary", "enchanted", 85.0),
        ("AZU", "Stitch - New Dog", "Legendary", "enchanted", 95.0),
        ("AZU", "Elsa - Glacial Guardian", "Legendary", "enchanted", 90.0),
        ("AZU", "Belle - Inventive Engineer", "Legendary", "enchanted", 80.0),
        ("AZU", "Gaston - Determined Hunter", "Legendary", "enchanted", 75.0),

        # ── Sealed Product — Booster Display Cases (inner carton) ───────────
        ("TFC", "The First Chapter Booster Display Case (4 boxes)", "Sealed Product", "sealed", 1400.0),
        ("ROF", "Rise of the Floodborn Booster Display Case (4 boxes)", "Sealed Product", "sealed", 640.0),
        ("ITI", "Into the Inklands Booster Display Case (4 boxes)", "Sealed Product", "sealed", 520.0),
        ("URR", "Ursula's Return Booster Display Case (4 boxes)", "Sealed Product", "sealed", 440.0),

        # ── Additional Tournament Prize Cards ───────────────────────────────
        ("PROMO", "Mulan - Soldier in Training (Regional Winner)", "Legendary", "promo", 200.0),
        ("PROMO", "Maui - Hero to All (Set Championship)", "Legendary", "promo", 150.0),
        ("PROMO", "Hercules - True Hero (League Promo)", "Super Rare", "promo", 65.0),
        ("PROMO", "Rapunzel - Gifted Artist (League Promo)", "Legendary", "promo", 80.0),
        ("PROMO", "Tinker Bell - Giant Fairy (Store Championship)", "Super Rare", "promo", 70.0),
        ("PROMO", "Cogsworth - Grandfather Clock (FLGS Promo)", "Super Rare", "promo", 30.0),
        ("PROMO", "Lilo - Making a Wish (Winner Promo)", "Legendary", "promo", 160.0),

        # ── Additional Accessories — Playmats (tournament specific) ─────────
        ("PROMO", "Tournament Playmat - Nationals 2024", "Accessory", "accessory", 100.0),
        ("PROMO", "Official Playmat - Ariel Azurite Sea", "Accessory", "accessory", 35.0),
        ("PROMO", "Official Playmat - Simba Returned King", "Accessory", "accessory", 35.0),
        ("PROMO", "Official Playmat - Hades Infernal", "Accessory", "accessory", 40.0),
        ("PROMO", "Official Playmat - Cinderella Ballroom", "Accessory", "accessory", 35.0),

        # ── Additional Accessories — Card Sleeves ───────────────────────────
        ("PROMO", "Official Card Sleeves - Hades (65 count)", "Accessory", "accessory", 11.0),
        ("PROMO", "Official Card Sleeves - Belle (65 count)", "Accessory", "accessory", 11.0),
        ("PROMO", "Official Card Sleeves - Ariel (65 count)", "Accessory", "accessory", 12.0),
        ("PROMO", "Official Card Sleeves - Moana (65 count)", "Accessory", "accessory", 11.0),
        ("PROMO", "Official Card Sleeves - Rapunzel (65 count)", "Accessory", "accessory", 11.0),
        ("PROMO", "Official Card Sleeves - Gaston (65 count)", "Accessory", "accessory", 11.0),

        # ── Additional Accessories — Deck Boxes ─────────────────────────────
        ("PROMO", "Official Deck Box - Ursula Sea Witch", "Accessory", "accessory", 16.0),
        ("PROMO", "Official Deck Box - Moana Wayfinder", "Accessory", "accessory", 15.0),
        ("PROMO", "Official Deck Box - Hades King", "Accessory", "accessory", 16.0),
        ("PROMO", "Official Deck Box - Ariel Collector", "Accessory", "accessory", 15.0),
        ("PROMO", "Official Deck Box - Belle Bookworm", "Accessory", "accessory", 15.0),

        # ── Deep Cuts — TFC additional uncommon/rare ────────────────────────
        ("TFC", "Anna - Heir to Arendelle", "Rare", "standard", 3.0),
        ("TFC", "Kristoff - Official Ice Master", "Rare", "standard", 2.5),
        ("TFC", "Pongo - Dalmatian Dad", "Rare", "standard", 2.0),
        ("TFC", "Perdita - Dalmatian Mom", "Rare", "standard", 2.0),
        ("TFC", "Maximus - Relentless Pursuer", "Rare", "standard", 2.5),
        ("TFC", "Mother Gothel - Selfish Manipulator", "Super Rare", "standard", 7.0),
        ("TFC", "Ariel - Spectacular Singer", "Super Rare", "standard", 9.0),

        # ── Deep Cuts — ROF additional uncommon/rare ────────────────────────
        ("ROF", "Flounder - Voice of Reason", "Rare", "standard", 2.0),
        ("ROF", "Sebastian - Crab Advisor", "Rare", "standard", 2.0),
        ("ROF", "Olaf - Warm Hugger", "Rare", "standard", 2.5),
        ("ROF", "Elsa - Storm Chaser", "Super Rare", "standard", 10.0),
        ("ROF", "Moana - Chosen One", "Super Rare", "standard", 9.0),
        ("ROF", "Anna - True Hearted", "Rare", "standard", 3.0),

        # ── Deep Cuts — ITI additional uncommon/rare ────────────────────────
        ("ITI", "Flynn Rider - Charming Rogue", "Rare", "standard", 3.0),
        ("ITI", "Pascal - Loyal Chameleon", "Rare", "standard", 2.0),
        ("ITI", "Maximus - Palace Horse", "Rare", "standard", 2.5),
        ("ITI", "Tiana - Hardworking Waitress", "Super Rare", "standard", 9.0),
        ("ITI", "Dr. Facilier - Shadow Man", "Super Rare", "standard", 10.0),
        ("ITI", "Yzma - Alchemist", "Rare", "standard", 3.5),
        ("ITI", "Kronk - Shoulder Angel Listener", "Rare", "standard", 2.5),

        # ── Deep Cuts — URR additional uncommon/rare ────────────────────────
        ("URR", "Flynn Rider - Wanted Thief", "Rare", "standard", 2.5),
        ("URR", "Mushu - Tiny Guardian", "Rare", "standard", 2.5),
        ("URR", "Mulan - Determined Fighter", "Super Rare", "standard", 10.0),
        ("URR", "Li Shang - Commanding Leader", "Rare", "standard", 3.0),
        ("URR", "Cinderella - Hard Worker", "Super Rare", "standard", 8.0),
        ("URR", "Fairy Godmother - Magical Helper", "Super Rare", "standard", 7.0),

        # ── Deep Cuts — SSK additional uncommon/rare ────────────────────────
        ("SSK", "Maleficent - Dark Fae", "Legendary", "standard", 22.0),
        ("SSK", "Aurora - Awakened Princess", "Super Rare", "standard", 10.0),
        ("SSK", "Phillip - Brave Prince", "Rare", "standard", 3.0),
        ("SSK", "Flora - Doting Fairy", "Rare", "standard", 2.0),
        ("SSK", "Fauna - Nurturing Fairy", "Rare", "standard", 2.0),
        ("SSK", "Merryweather - Spirited Fairy", "Rare", "standard", 2.0),
        ("SSK", "Hades - Quick Tempered", "Super Rare", "standard", 9.0),

        # ── Deep Cuts — AZU additional uncommon/rare ────────────────────────
        ("AZU", "Aladdin - Diamond in the Rough", "Super Rare", "standard", 10.0),
        ("AZU", "Jasmine - Free Spirit", "Legendary", "standard", 20.0),
        ("AZU", "Genie - Phenomenal Cosmic Power", "Legendary", "standard", 22.0),
        ("AZU", "Iago - Loud Parrot", "Rare", "standard", 2.0),
        ("AZU", "Abu - Tricky Monkey", "Rare", "standard", 2.0),
        ("AZU", "Magic Carpet - Enchanted Transport", "Rare", "standard", 2.5),
        ("AZU", "Maleficent - Uninvited Guest", "Legendary", "standard", 22.0),
    ]

    for set_code, name, rarity, variant, price_eur in notable_cards:
        set_name = next(s[1] for s in sets if s[0] == set_code)
        cards.append({
            "name": name,
            "set_code": set_code,
            "set_name": set_name,
            "rarity": rarity,
            "variant": variant,
            "price_eur": price_eur,
        })

    # Generate common/uncommon/rare fillers per set
    rarities = [
        ("Common", 60, 0.10),
        ("Uncommon", 30, 0.30),
        ("Rare", 20, 1.50),
        ("Super Rare", 8, 8.00),
        ("Legendary", 4, 25.00),
    ]

    for set_code, set_name in sets:
        if set_code == "PROMO":
            continue  # promos don't have common/uncommon fillers
        for rarity, count, avg_price in rarities:
            for n in range(1, min(count + 1, 6)):  # seed 5 per rarity per set
                cards.append({
                    "name": f"{set_name} {rarity} #{n}",
                    "set_code": set_code,
                    "set_name": set_name,
                    "rarity": rarity,
                    "variant": "standard",
                    "price_eur": avg_price,
                })

    return cards


def card_to_catalog_item(card: dict) -> CatalogItem:
    name = card.get("name", card.get("Name", ""))
    set_code = card.get("set_code", card.get("Set_ID", ""))
    set_name = card.get("set_name", card.get("Set_Name", ""))
    rarity = card.get("rarity", card.get("Rarity", ""))
    number = card.get("number", card.get("Card_Num", ""))
    color = card.get("color", card.get("Color", ""))
    image = card.get("image", card.get("Image", ""))

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{set_code}-{number or name}"),
        title=name,
        set_code=set_code,
        brand="Disney Lorcana",
        rarity=rarity,
        notes=f"{set_name}" + (f" #{number}" if number else ""),
        image_url=image if isinstance(image, str) else "",
        attributes_json={
            "set": set_name,
            "number": str(number),
            "rarity": rarity,
            "color": color,
        },
    )


def card_to_price_observation(card: dict) -> PriceObservation | None:
    price = card.get("price_eur") or card.get("price")
    if not price:
        return None
    try:
        price_float = float(price)
    except (ValueError, TypeError):
        return None
    if price_float <= 0:
        return None

    rarity = card.get("rarity", card.get("Rarity", ""))
    variant = card.get("variant", "standard")

    return PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": shared_rarity_score(rarity),
            "edition_score": 0.9 if variant == "enchanted" else 0.5,
            "is_foil": 1.0 if variant in ("enchanted", "foil") else 0.0,
        },
        price=price_float,
    )


def main():
    parser = argparse.ArgumentParser(description="Import Lorcana catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Disney Lorcana Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    cards = fetch_all_cards()

    all_items = [card_to_catalog_item(c) for c in cards]
    all_observations = [obs for c in cards if (obs := card_to_price_observation(c))]

    # Deduplicate
    seen = set()
    deduped = []
    for item in all_items:
        if item.item_key not in seen:
            seen.add(item.item_key)
            deduped.append(item)
    all_items = deduped

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    if all_observations:
        write_training_jsonl(CATEGORY, all_observations)
        log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()

    logger.info(f"\n=== Lorcana Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
