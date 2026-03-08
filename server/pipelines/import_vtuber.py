"""
Import VTuber merchandise catalog.

Layer 1 (Catalog):  Curated VTuber merch → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Hololive: acrylic stands, tapestries, badges per talent
- Hololive anniversary/birthday sets
- Nijisanji: merch drops
- Hololive x Lawson collabs
- Concert/event limited goods
- Key talents: Gawr Gura, Pekora, Marine, Subaru, Mori Calliope, Suisei

Usage:
    python -m pipelines.import_vtuber [--dry-run]
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

CATEGORY = "vtuber"


def _additional_nijisanji_en() -> list[tuple]:
    """NIJISANJI EN talent merch — Selen, Pomu, Elira, Vox, Mysta."""
    return [
        ("Nijisanji", "Selen Tatsuki", "Tapestry", "Selen Tatsuki Graduation Memorial B2 Tapestry", "Anniversary", "high", 95),
        ("Nijisanji", "Selen Tatsuki", "Acrylic Stand", "Selen Tatsuki Birthday 2023 Acrylic Stand", "Birthday", "mid", 30),
        ("Nijisanji", "Selen Tatsuki", "Badge Set", "Selen Tatsuki Graduation Memorial Badge Set (5pc)", "Anniversary", "mid", 40),
        ("Nijisanji", "Pomu Rainpuff", "Birthday Set", "Pomu Rainpuff Birthday 2023 Complete Merch Set", "Birthday", "high", 75),
        ("Nijisanji", "Pomu Rainpuff", "Tapestry", "Pomu Rainpuff Graduation Memorial B2 Tapestry", "Anniversary", "high", 90),
        ("Nijisanji", "Mysta Rias", "Acrylic Stand", "Mysta Rias Birthday 2023 Acrylic Stand", "Birthday", "mid", 28),
        ("Nijisanji", "Mysta Rias", "Birthday Set", "Mysta Rias Farewell Memorial Goods Set", "Anniversary", "high", 80),
    ]


def _additional_nijisanji_jp() -> list[tuple]:
    """NIJISANJI JP — Kuzuha, Kanae, Mito, Lize birthday/anniversary merch."""
    return [
        ("Nijisanji", "Kuzuha", "Tapestry", "Kuzuha 5th Anniversary B2 Tapestry", "Anniversary", "high", 65),
        ("Nijisanji", "Kuzuha", "Acrylic Stand", "Kuzuha x Kanae ChroNoiR 5th Anniv. Acrylic Stand Set", "Anniversary", "high", 55),
        ("Nijisanji", "Kanae", "Birthday Set", "Kanae Birthday 2024 Premium Merch Set", "Birthday", "high", 85),
        ("Nijisanji", "Tsukino Mito", "Birthday Set", "Tsukino Mito Birthday 2024 Complete Set", "Birthday", "high", 70),
        ("Nijisanji", "Tsukino Mito", "Acrylic Stand", "Tsukino Mito 6th Anniversary Acrylic Stand", "Anniversary", "mid", 32),
        ("Nijisanji", "Lize Helesta", "Birthday Set", "Lize Helesta Birthday 2024 Complete Merch Set", "Birthday", "high", 68),
    ]


def _additional_hololive_5th_gen() -> list[tuple]:
    """Hololive 5th Gen — Lamy, Nene, Botan, Polka merch."""
    return [
        ("Hololive", "Yukihana Lamy", "Birthday Set", "Yukihana Lamy Birthday 2024 Complete Merch Set", "Birthday", "high", 72),
        ("Hololive", "Yukihana Lamy", "Acrylic Stand", "Yukihana Lamy 3D Anniversary Acrylic Stand", "Anniversary", "mid", 28),
        ("Hololive", "Momosuzu Nene", "Birthday Set", "Momosuzu Nene Birthday 2024 Full Set", "Birthday", "high", 65),
        ("Hololive", "Momosuzu Nene", "Tapestry", "Momosuzu Nene New Outfit B2 Tapestry", "Outfit Reveal", "mid", 30),
        ("Hololive", "Shishiro Botan", "Birthday Set", "Shishiro Botan Birthday 2024 Complete Set", "Birthday", "high", 70),
        ("Hololive", "Shishiro Botan", "Acrylic Stand", "Shishiro Botan SSRB Acrylic Stand", "Standard", "mid", 22),
        ("Hololive", "Omaru Polka", "Birthday Set", "Omaru Polka Birthday 2024 Full Merch Set", "Birthday", "high", 68),
        ("Hololive", "Omaru Polka", "Tapestry", "Omaru Polka 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 32),
    ]


def _additional_hololive_dev_is() -> list[tuple]:
    """Hololive ReGLOSS/DEV_IS — Hajime Kanade, Otonose Kanade merch."""
    return [
        ("Hololive", "Hiodoshi Ao", "Acrylic Stand", "Hiodoshi Ao 1st Anniversary Acrylic Stand", "Anniversary", "mid", 26),
        ("Hololive", "Otonose Kanade", "Birthday Set", "Otonose Kanade Birthday 2024 Merch Set", "Birthday", "high", 60),
        ("Hololive", "Otonose Kanade", "Tapestry", "Otonose Kanade 1st Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("Hololive", "Todoroki Hajime", "Acrylic Stand", "Todoroki Hajime 1st Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("Hololive", "Todoroki Hajime", "Birthday Set", "Todoroki Hajime Birthday 2024 Merch Set", "Birthday", "high", 58),
    ]


def _additional_vspo_phase_vshojo() -> list[tuple]:
    """VSPO!, Phase Connect, VShojo merch."""
    return [
        ("VSPO!", "Ichinose Uruha", "Acrylic Stand", "Ichinose Uruha Birthday 2024 Acrylic Stand", "Birthday", "mid", 25),
        ("VSPO!", "Tosaki Beni", "Birthday Set", "Tosaki Beni Birthday 2024 Complete Set", "Birthday", "mid", 48),
        ("VSPO!", "Yakumo Beni", "Tapestry", "Yakumo Beni 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 22),
        ("VSPO!", "Shinomiya Noah", "Birthday Set", "Shinomiya Noah Birthday 2024 Full Merch Set", "Birthday", "high", 55),
        ("Phase Connect", "Pipkin Pippa", "Acrylic Stand", "Pipkin Pippa 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Phase Connect", "Tenma Maemi", "Birthday Set", "Tenma Maemi Birthday 2024 Merch Set", "Birthday", "mid", 40),
        ("VShojo", "Ironmouse", "Birthday Set", "Ironmouse Birthday 2024 Complete Merch Set", "Birthday", "high", 65),
        ("VShojo", "Zentreya", "Acrylic Stand", "Zentreya 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 20),
    ]


def _additional_concert_blurays() -> list[tuple]:
    """Concert exclusive Blu-rays — HoloFes, Nijifes."""
    return [
        ("Hololive", "Various", "Concert Blu-ray", "Hololive 5th Fes. Capture the Moment Blu-ray", "Concert", "high", 85),
        ("Hololive", "Various", "Concert Blu-ray", "Hololive 4th Fes. Our Bright Parade Blu-ray Box", "Concert", "high", 90),
        ("Hololive", "Various", "Concert Blu-ray", "Hololive 3rd Fes. Link Your Wish Blu-ray", "Concert", "high", 75),
        ("Nijisanji", "Various", "Concert Blu-ray", "Nijisanji Koshien 2023 Blu-ray", "Concert", "high", 65),
        ("Nijisanji", "Various", "Concert Blu-ray", "NijiFes 2023 Blu-ray Box", "Concert", "high", 80),
        ("Hololive", "Hoshimachi Suisei", "Concert Blu-ray", "Suisei Stellar into the Galaxy Solo Live Blu-ray", "Solo Concert", "grail", 110),
    ]


def _additional_vtuber_items() -> list[tuple]:
    """Additional VTuber merch — EN Myth anniversary, concerts, collabs, indie agencies."""
    return [
        # Hololive 5th Gen — birthday/anniversary extras
        ("Hololive", "Yukihana Lamy", "Tapestry", "Yukihana Lamy 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 32),
        ("Hololive", "Shishiro Botan", "Acrylic Stand", "Shishiro Botan 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 26),
        ("Hololive", "Momosuzu Nene", "Birthday Set", "Momosuzu Nene Birthday 2023 Complete Set", "Birthday", "high", 68),
        ("Hololive", "Omaru Polka", "Acrylic Stand", "Omaru Polka Birthday 2024 Acrylic Stand", "Birthday", "mid", 24),

        # Hololive DEV_IS/ReGLOSS debut goods
        ("Hololive", "Otonose Kanade", "Acrylic Stand", "Otonose Kanade Debut Celebration Acrylic Stand", "Debut", "mid", 26),
        ("Hololive", "Todoroki Hajime", "Tapestry", "Todoroki Hajime Debut Celebration B2 Tapestry", "Debut", "mid", 28),
        ("Hololive", "Ichijou Ririka", "Acrylic Stand", "Ichijou Ririka 1st Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("Hololive", "Juufuutei Raden", "Birthday Set", "Juufuutei Raden Birthday 2024 Merch Set", "Birthday", "high", 58),

        # VSPO! — Noah, Beni
        ("VSPO!", "Shinomiya Noah", "Tapestry", "Shinomiya Noah 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("VSPO!", "Tosaki Beni", "Acrylic Stand", "Tosaki Beni 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 22),

        # Phase Connect — Sakana, Pippa
        ("Phase Connect", "Pipkin Pippa", "Birthday Set", "Pipkin Pippa Birthday 2024 Complete Set", "Birthday", "high", 55),
        ("Phase Connect", "Sakana", "Acrylic Stand", "Sakana (CEO) Phase Connect Anniversary Acrylic Stand", "Anniversary", "mid", 20),
        ("Phase Connect", "Jelly Hoshiumi", "Birthday Set", "Jelly Hoshiumi Birthday 2024 Merch Set", "Birthday", "mid", 42),

        # VShojo — Ironmouse, Zentreya
        ("VShojo", "Ironmouse", "Tapestry", "Ironmouse 5th Anniversary B2 Tapestry", "Anniversary", "mid", 35),
        ("VShojo", "Zentreya", "Birthday Set", "Zentreya Birthday 2024 Complete Merch Set", "Birthday", "high", 55),
        ("VShojo", "Kson", "Acrylic Stand", "Kson 1st VShojo Anniversary Acrylic Stand", "Anniversary", "mid", 22),

        # Concert Blu-rays — HoloFes, NijiFes, SUPER EXPO
        ("Hololive", "Various", "Concert Blu-ray", "Hololive SUPER EXPO 2024 Blu-ray Box", "Concert", "high", 95),
        ("Nijisanji", "Various", "Concert Blu-ray", "NijiFes 2024 Blu-ray Box", "Concert", "high", 85),
        ("Hololive", "Various", "Concert Blu-ray", "Hololive 5th Fes. Day 1 & Day 2 Blu-ray Set", "Concert", "grail", 120),

        # Hololive EN Myth 3rd Anniversary
        ("Hololive", "Gawr Gura", "Anniversary Set", "Gawr Gura 3rd Anniversary Premium Set", "Anniversary", "grail", 130),
        ("Hololive", "Mori Calliope", "Anniversary Set", "Mori Calliope 3rd Anniversary Premium Set", "Anniversary", "high", 95),
        ("Hololive", "Ninomae Ina'nis", "Anniversary Set", "Ninomae Ina'nis 3rd Anniversary Premium Set", "Anniversary", "high", 90),
        ("Hololive", "Takanashi Kiara", "Anniversary Set", "Takanashi Kiara 3rd Anniversary Premium Set", "Anniversary", "high", 88),
        ("Hololive", "Watson Amelia", "Anniversary Set", "Watson Amelia 3rd Anniversary Premium Set", "Anniversary", "high", 92),

        # More Nijisanji JP — Kuzuha, Kanae, Mito birthday
        ("Nijisanji", "Kuzuha", "Signed Shikishi", "Kuzuha Hand-Signed Birthday Shikishi Board", "Birthday", "grail", 200),
        ("Nijisanji", "Kanae", "Tapestry", "Kanae 5th Anniversary B2 Tapestry", "Anniversary", "high", 55),
        ("Nijisanji", "Tsukino Mito", "Tapestry", "Tsukino Mito 6th Anniversary B2 Tapestry", "Anniversary", "mid", 45),

        # Collaboration cafe goods
        ("Hololive", "Various", "Collab Goods", "Hololive x Animate Cafe Acrylic Coaster Set (10pc)", "Animate Collab", "mid", 48),
        ("Hololive", "Various", "Collab Goods", "Hololive x Animate Cafe Random Can Badge (Full Set)", "Animate Collab", "mid", 38),
        ("Nijisanji", "Various", "Collab Goods", "Nijisanji x Tower Records Cafe Acrylic Stand Set", "Tower Records Collab", "mid", 42),
        ("Nijisanji", "Various", "Collab Goods", "Nijisanji x Tower Records Clear File Collection", "Tower Records Collab", "mid", 30),
        ("Hololive", "Various", "Collab Goods", "Hololive x Sweets Paradise Cafe Menu Acrylic Set", "Collab Cafe", "mid", 35),

        # High-value signed/limited items
        ("Hololive", "Tokoyami Towa", "Signed Shikishi", "Tokoyami Towa Hand-Signed Shikishi Board", "Birthday", "grail", 180),
        ("Hololive", "Houshou Marine", "Signed Shikishi", "Houshou Marine Hand-Signed Shikishi Board", "Birthday", "grail", 250),
        ("Hololive", "Various", "Concert Goods", "Hololive SUPER EXPO 2024 Venue-Limited Pin Set", "Concert", "mid", 42),
    ]


def get_curated_catalog() -> list[dict]:
    """Curated VTuber merchandise catalog — 500+ items across Hololive, Nijisanji, VSPO, Phase Connect, VShojo, collabs, concerts & high-value goods."""

    # (agency, talent, item_type, name, exclusive_type, rarity_tier, price_eur)
    # rarity_tier: grail (>100), high (50-100), mid (20-50), standard (<20)

    items = [
        # Hololive – Acrylic stands
        ("Hololive", "Gawr Gura", "Acrylic Stand", "Gawr Gura Birthday 2022 Acrylic Stand", "Birthday", "mid", 28),
        ("Hololive", "Usada Pekora", "Acrylic Stand", "Usada Pekora 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 30),
        ("Hololive", "Houshou Marine", "Acrylic Stand", "Houshou Marine Birthday 2023 Acrylic Stand", "Birthday", "mid", 25),
        ("Hololive", "Oozora Subaru", "Acrylic Stand", "Oozora Subaru New Outfit Acrylic Stand", "Outfit Reveal", "mid", 22),
        ("Hololive", "Mori Calliope", "Acrylic Stand", "Mori Calliope UnAlive Acrylic Stand", "Album Release", "mid", 25),
        ("Hololive", "Hoshimachi Suisei", "Acrylic Stand", "Hoshimachi Suisei Stellar into the Galaxy Stand", "Concert", "mid", 30),

        # Hololive – Tapestries
        ("Hololive", "Gawr Gura", "Tapestry", "Gawr Gura 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 40),
        ("Hololive", "Houshou Marine", "Tapestry", "Houshou Marine Shion Summer B2 Tapestry", "Seasonal", "mid", 38),
        ("Hololive", "Shiranui Flare", "Tapestry", "Shiranui Flare Birthday B2 Tapestry", "Birthday", "standard", 18),

        # Hololive – Anniversary/Birthday sets
        ("Hololive", "Gawr Gura", "Birthday Set", "Gawr Gura Birthday 2023 Full Merch Set", "Birthday", "high", 90),
        ("Hololive", "Usada Pekora", "Birthday Set", "Usada Pekora Birthday 2023 Complete Set", "Birthday", "high", 85),
        ("Hololive", "Hoshimachi Suisei", "Birthday Set", "Suisei Birthday 2023 Merch Set", "Birthday", "high", 80),
        ("Hololive", "Mori Calliope", "Anniversary Set", "Mori Calliope 3rd Anniversary Box", "Anniversary", "high", 95),

        # Hololive – Badges & small goods
        ("Hololive", "Various", "Badge Set", "Hololive Gen 3 Random Badge Collection", "Standard", "standard", 12),
        ("Hololive", "Various", "Badge Set", "Hololive EN Myth Badge Set Complete", "Generation", "mid", 35),

        # Nijisanji merch drops
        ("Nijisanji", "Vox Akuma", "Acrylic Stand", "Vox Akuma Birthday 2023 Acrylic Stand", "Birthday", "mid", 25),
        ("Nijisanji", "Luca Kaneshiro", "Acrylic Stand", "Luca Kaneshiro Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Nijisanji", "Elira Pendora", "Tapestry", "Elira Pendora Debut Anniversary Tapestry", "Anniversary", "mid", 30),
        ("Nijisanji", "Selen Tatsuki", "Badge Set", "Selen Tatsuki Random Badge Collection", "Standard", "standard", 10),
        ("Nijisanji", "Various", "Merch Box", "Nijisanji EN Luxiem Voice Pack + Goods Set", "Group", "high", 65),

        # Hololive x Lawson collabs
        ("Hololive", "Various", "Collab Clear File", "Hololive x Lawson Summer Clear File Set", "Lawson Collab", "mid", 25),
        ("Hololive", "Gawr Gura", "Collab Acrylic", "Gura x Lawson Limited Acrylic Stand", "Lawson Collab", "mid", 35),
        ("Hololive", "Usada Pekora", "Collab Snack", "Pekora x Lawson Collab Chips + Card", "Lawson Collab", "standard", 15),
        ("Hololive", "Various", "Collab Tapestry", "Hololive x Lawson Valentine Tapestry Set", "Lawson Collab", "high", 55),

        # Concert/event limited goods
        ("Hololive", "Various", "Concert Goods", "Hololive 4th Fes. Our Bright Parade Penlight", "Concert", "mid", 40),
        ("Hololive", "Various", "Concert Goods", "Hololive 4th Fes. T-Shirt", "Concert", "mid", 45),
        ("Hololive", "Hoshimachi Suisei", "Concert Goods", "Suisei Stellar into the Galaxy Penlight", "Solo Concert", "high", 55),
        ("Hololive", "Various", "Concert Goods", "Hololive 3rd Fes. Link Your Wish Full Merch Set", "Concert", "grail", 140),
        ("Hololive", "Mori Calliope", "Concert Goods", "Mori Calliope New Underworld Order Tour Hoodie", "Solo Concert", "high", 70),
        ("Hololive", "Various", "Concert Goods", "HoloEN Connect the World Stage Acrylic Set", "Concert", "high", 60),

        # ──────────────────────────────────────────────────────────────
        # NEW ITEMS (36 additions below)
        # ──────────────────────────────────────────────────────────────

        # Hololive EN – IRyS, Fauna, Kronii, Mumei, Baelz, Nerissa (+6)
        ("Hololive", "IRyS", "Birthday Set", "IRyS Birthday 2024 Merch Set", "Birthday", "high", 75),
        ("Hololive", "Ceres Fauna", "Acrylic Stand", "Ceres Fauna 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 26),
        ("Hololive", "Ouro Kronii", "Tapestry", "Ouro Kronii Birthday 2024 B2 Tapestry", "Birthday", "mid", 32),
        ("Hololive", "Nanashi Mumei", "Birthday Set", "Nanashi Mumei Birthday 2024 Complete Set", "Birthday", "high", 70),
        ("Hololive", "Hakos Baelz", "Acrylic Stand", "Hakos Baelz 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("Hololive", "Nerissa Ravencroft", "Anniversary Set", "Nerissa Ravencroft 1st Anniversary Box", "Anniversary", "high", 65),

        # Hololive JP – Towa, Fubuki, Flare, Aki, Subaru, Matsuri (+6)
        ("Hololive", "Tokoyami Towa", "Acrylic Stand", "Tokoyami Towa Birthday 2024 Acrylic Stand", "Birthday", "mid", 28),
        ("Hololive", "Shirakami Fubuki", "Birthday Set", "Shirakami Fubuki Birthday 2024 Full Set", "Birthday", "high", 72),
        ("Hololive", "Shiranui Flare", "Anniversary Set", "Shiranui Flare 4th Anniversary Merch Box", "Anniversary", "high", 60),
        ("Hololive", "Aki Rosenthal", "Tapestry", "Aki Rosenthal Birthday 2024 B2 Tapestry", "Birthday", "mid", 22),
        ("Hololive", "Oozora Subaru", "Birthday Set", "Oozora Subaru Birthday 2024 Complete Set", "Birthday", "high", 78),
        ("Hololive", "Natsuiro Matsuri", "Acrylic Stand", "Natsuiro Matsuri Summer Festival Acrylic Stand", "Seasonal", "mid", 20),

        # Hololive ID – Moona, Kobo, Reine (+3)
        ("Hololive", "Moona Hoshinova", "Birthday Set", "Moona Hoshinova Birthday 2024 Merch Set", "Birthday", "mid", 45),
        ("Hololive", "Kobo Kanaeru", "Acrylic Stand", "Kobo Kanaeru 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 28),
        ("Hololive", "Pavolia Reine", "Tapestry", "Pavolia Reine Birthday 2024 B2 Tapestry", "Birthday", "mid", 24),

        # Nijisanji EN – Vox, Ike, Shu, Elira, Pomu (+5)
        ("Nijisanji", "Vox Akuma", "Birthday Set", "Vox Akuma Birthday 2024 Complete Set", "Birthday", "high", 80),
        ("Nijisanji", "Ike Eveland", "Acrylic Stand", "Ike Eveland Birthday 2024 Acrylic Stand", "Birthday", "mid", 24),
        ("Nijisanji", "Shu Yamino", "Tapestry", "Shu Yamino Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("Nijisanji", "Elira Pendora", "Birthday Set", "Elira Pendora Birthday 2024 Complete Set", "Birthday", "high", 68),
        ("Nijisanji", "Pomu Rainpuff", "Acrylic Stand", "Pomu Rainpuff Farewell Memorial Acrylic Stand", "Anniversary", "high", 85),

        # Nijisanji JP – Kuzuha, Kanae, Lize, Ange (+4)
        ("Nijisanji", "Kuzuha", "Birthday Set", "Kuzuha Birthday 2024 Premium Merch Set", "Birthday", "high", 95),
        ("Nijisanji", "Kanae", "Acrylic Stand", "Kanae Birthday 2024 Acrylic Stand", "Birthday", "mid", 30),
        ("Nijisanji", "Lize Helesta", "Tapestry", "Lize Helesta Anniversary B2 Tapestry", "Anniversary", "mid", 26),
        ("Nijisanji", "Ange Katrina", "Birthday Set", "Ange Katrina Birthday 2024 Complete Set", "Birthday", "high", 62),

        # Concert/Event Goods (+5)
        ("Hololive", "Various", "Concert Goods", "Hololive 5th Fes. Capture the Moment Penlight", "Concert", "mid", 45),
        ("Hololive", "Various", "Concert Goods", "Holofes 5th Exclusive Acrylic Stand Set (12pc)", "Concert", "grail", 180),
        ("Nijisanji", "Various", "Concert Goods", "Nijisanji JP AR LIVE Concert Tapestry", "Concert", "high", 55),
        ("Hololive", "Various", "Concert Goods", "Hololive EXPO 2024 Venue-Limited Goods Set", "Concert", "grail", 120),
        ("Hololive", "Various", "Concert Goods", "VTuber Fes Japan 2024 Exclusive Badge Collection", "Concert", "mid", 38),

        # Collab Goods (+4)
        ("Hololive", "Various", "Collab Clear File", "Hololive x Lawson Christmas Clear File Set", "Lawson Collab", "mid", 28),
        ("Hololive", "Various", "Collab Acrylic", "Hololive x Don Quijote Limited Acrylic Stand Set", "Lawson Collab", "high", 52),
        ("Nijisanji", "Various", "Collab Clear File", "Nijisanji x Animate Fair Clear File Collection", "Standard", "mid", 22),
        ("VShojo", "Various", "Merch Box", "VShojo Spring 2024 Merch Drop Bundle", "Group", "mid", 42),

        # High-Value Items (+3)
        ("Hololive", "Gawr Gura", "Signed Shikishi", "Gawr Gura Hand-Signed Shikishi Board", "Birthday", "grail", 220),
        ("Hololive", "Hoshimachi Suisei", "Art Print", "Hoshimachi Suisei Original Art Print (Numbered)", "Solo Concert", "grail", 160),
        ("Hololive", "Usada Pekora", "Anniversary Set", "Usada Pekora 1st Anniversary Milestone Goods Set", "Anniversary", "grail", 135),

        # ── ROUND 4 — 65 new items to reach 200+ ──────────────────────────

        # Hololive EN Advent — Shiori, Bijou, Nerissa, FUWAMOCO (+8)
        ("Hololive", "Shiori Novella", "Birthday Set", "Shiori Novella 1st Anniversary Merch Set", "Anniversary", "high", 60),
        ("Hololive", "Shiori Novella", "Acrylic Stand", "Shiori Novella Debut Celebration Acrylic Stand", "Debut", "mid", 24),
        ("Hololive", "Koseki Bijou", "Birthday Set", "Koseki Bijou 1st Anniversary Full Set", "Anniversary", "high", 62),
        ("Hololive", "Koseki Bijou", "Tapestry", "Koseki Bijou New Year 2025 B2 Tapestry", "Seasonal", "mid", 28),
        ("Hololive", "FUWAMOCO", "Birthday Set", "FUWAMOCO 1st Anniversary Twin Merch Set", "Anniversary", "high", 78),
        ("Hololive", "FUWAMOCO", "Acrylic Stand", "FUWAMOCO Debut Celebration Paired Acrylic Stand", "Debut", "mid", 32),
        ("Hololive", "Nerissa Ravencroft", "Tapestry", "Nerissa Ravencroft 1st Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Hololive", "Nerissa Ravencroft", "Acrylic Stand", "Nerissa Ravencroft Debut Celebration Acrylic Stand", "Debut", "mid", 24),

        # Hololive JP Gen 0 — Sora, Roboco, AZKi, Suisei extras (+6)
        ("Hololive", "Tokino Sora", "Anniversary Set", "Tokino Sora 7th Anniversary Premium Box", "Anniversary", "grail", 140),
        ("Hololive", "Tokino Sora", "Tapestry", "Tokino Sora 7th Anniversary B2 Tapestry", "Anniversary", "mid", 35),
        ("Hololive", "Roboco-san", "Birthday Set", "Roboco-san Birthday 2024 Merch Set", "Birthday", "high", 55),
        ("Hololive", "AZKi", "Concert Goods", "AZKi 6th Anniversary Live Penlight", "Solo Concert", "mid", 38),
        ("Hololive", "AZKi", "Anniversary Set", "AZKi 6th Anniversary Full Merch Set", "Anniversary", "high", 70),
        ("Hololive", "Hoshimachi Suisei", "Concert Goods", "Suisei Shout in Crisis Solo Live Hoodie", "Solo Concert", "high", 65),

        # Hololive JP Gen 1 — Fubuki, Matsuri, Haato, Mel (+5)
        ("Hololive", "Shirakami Fubuki", "Tapestry", "Shirakami Fubuki 6th Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Hololive", "Akai Haato", "Birthday Set", "Akai Haato Birthday 2024 Complete Set", "Birthday", "high", 58),
        ("Hololive", "Akai Haato", "Acrylic Stand", "Haachama Cooking Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Hololive", "Natsuiro Matsuri", "Birthday Set", "Natsuiro Matsuri Birthday 2024 Full Set", "Birthday", "high", 62),
        ("Hololive", "Yozora Mel", "Tapestry", "Yozora Mel Graduation Memorial B2 Tapestry", "Anniversary", "high", 50),

        # Hololive JP Gen 2 — Aqua, Shion, Choco, Ayame, Subaru extras (+5)
        ("Hololive", "Minato Aqua", "Signed Shikishi", "Minato Aqua Graduation Memorial Hand-Signed Shikishi", "Anniversary", "grail", 280),
        ("Hololive", "Minato Aqua", "Anniversary Set", "Minato Aqua Graduation Premium Box", "Anniversary", "grail", 150),
        ("Hololive", "Murasaki Shion", "Birthday Set", "Murasaki Shion Birthday 2024 Full Set", "Birthday", "high", 65),
        ("Hololive", "Yuzuki Choco", "Tapestry", "Yuzuki Choco Birthday 2024 B2 Tapestry", "Birthday", "mid", 26),
        ("Hololive", "Nakiri Ayame", "Birthday Set", "Nakiri Ayame Birthday 2024 Complete Set", "Birthday", "high", 80),

        # Hololive JP Gen 3 — Noel, Flare, Rushia memorial (+4)
        ("Hololive", "Shirogane Noel", "Birthday Set", "Shirogane Noel Birthday 2024 Complete Set", "Birthday", "high", 72),
        ("Hololive", "Shirogane Noel", "Concert Goods", "Shirogane Noel Solo Live 2024 Penlight", "Solo Concert", "mid", 40),
        ("Hololive", "Shiranui Flare", "Tapestry", "Shiranui Flare 5th Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("Hololive", "Houshou Marine", "Concert Goods", "Houshou Marine Major Debut Penlight + Towel Set", "Solo Concert", "high", 55),

        # Hololive JP Gen 4 — Kanata, Watame, Luna, Towa extras (+5)
        ("Hololive", "Amane Kanata", "Birthday Set", "Amane Kanata Birthday 2024 Complete Set", "Birthday", "high", 68),
        ("Hololive", "Amane Kanata", "Signed Shikishi", "Amane Kanata Hand-Signed Birthday Shikishi", "Birthday", "grail", 190),
        ("Hololive", "Tsunomaki Watame", "Birthday Set", "Tsunomaki Watame Birthday 2024 Full Set", "Birthday", "high", 65),
        ("Hololive", "Tsunomaki Watame", "Concert Goods", "Watame Night Fever!! Solo Live Penlight", "Solo Concert", "mid", 38),
        ("Hololive", "Himemori Luna", "Birthday Set", "Himemori Luna Birthday 2024 Complete Set", "Birthday", "high", 60),

        # Nijisanji EN — Rosemi, Shu, Aia, Scarle, Doppio (+5)
        ("Nijisanji", "Rosemi Lovelock", "Birthday Set", "Rosemi Lovelock Birthday 2024 Complete Set", "Birthday", "high", 58),
        ("Nijisanji", "Rosemi Lovelock", "Acrylic Stand", "Rosemi Lovelock 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("Nijisanji", "Scarle Yonaguni", "Birthday Set", "Scarle Yonaguni Birthday 2024 Merch Set", "Birthday", "mid", 45),
        ("Nijisanji", "Doppio Dropscythe", "Acrylic Stand", "Doppio Dropscythe Birthday 2024 Acrylic Stand", "Birthday", "mid", 22),
        ("Nijisanji", "Aia Amare", "Tapestry", "Aia Amare Graduation Memorial B2 Tapestry", "Anniversary", "high", 55),

        # Nijisanji JP — Shiina, Sasaki, Honma, Mayuyu (+5)
        ("Nijisanji", "Shiina Yuika", "Birthday Set", "Shiina Yuika Birthday 2024 Complete Set", "Birthday", "high", 65),
        ("Nijisanji", "Sasaki Saku", "Birthday Set", "Sasaki Saku Birthday 2024 Merch Set", "Birthday", "high", 60),
        ("Nijisanji", "Honma Himawari", "Tapestry", "Honma Himawari 5th Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("Nijisanji", "Mayuzumi Kai", "Tapestry", "Mayuzumi Kai Graduation Memorial B2 Tapestry", "Anniversary", "high", 75),
        ("Nijisanji", "Fuwa Minato", "Birthday Set", "Fuwa Minato Birthday 2024 Full Merch Set", "Birthday", "high", 58),

        # VSPO! — Hinano, Nazuna, Mimi (+4)
        ("VSPO!", "Kaga Nazuna", "Birthday Set", "Kaga Nazuna Birthday 2024 Full Merch Set", "Birthday", "mid", 48),
        ("VSPO!", "Kaga Nazuna", "Acrylic Stand", "Kaga Nazuna 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("VSPO!", "Aizawa Ema", "Birthday Set", "Aizawa Ema Birthday 2024 Complete Set", "Birthday", "mid", 45),
        ("VSPO!", "Hinano Tachibana", "Tapestry", "Hinano Tachibana 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 24),

        # Phase Connect — Lia, Muyu, Runie (+3)
        ("Phase Connect", "Rinkou Ashelia", "Birthday Set", "Rinkou Ashelia Birthday 2024 Merch Set", "Birthday", "mid", 38),
        ("Phase Connect", "Muyu", "Acrylic Stand", "Muyu 1st Anniversary Acrylic Stand", "Anniversary", "mid", 20),
        ("Phase Connect", "Runie Ruse", "Birthday Set", "Runie Ruse Birthday 2024 Complete Set", "Birthday", "mid", 42),

        # VShojo — Henya, Mata, Geega (+4)
        ("VShojo", "Henya the Genius", "Birthday Set", "Henya the Genius Birthday 2024 Complete Set", "Birthday", "high", 55),
        ("VShojo", "Henya the Genius", "Acrylic Stand", "Henya 1st VShojo Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("VShojo", "Matara Kan", "Birthday Set", "Matara Kan Birthday 2024 Full Merch Set", "Birthday", "high", 60),
        ("VShojo", "Geega", "Acrylic Stand", "Geega 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 20),

        # Indie VTubers (+3)
        ("Indie", "Shylily", "Birthday Set", "Shylily Birthday 2024 Merch Box", "Birthday", "mid", 48),
        ("Indie", "Nyanners", "Anniversary Set", "Nyanners 10th Anniversary Commemorative Set", "Anniversary", "high", 65),
        ("Indie", "Vedal987", "Acrylic Stand", "Vedal987 x Neuro-sama Duo Acrylic Stand", "Standard", "mid", 25),

        # More Concert/Live Goods (+5)
        ("Hololive", "Various", "Concert Goods", "Hololive SUPER EXPO 2025 Venue-Limited T-Shirt", "Concert", "mid", 45),
        ("Hololive", "Various", "Concert Goods", "Hololive 6th Fes. Day 1 Venue-Limited Acrylic Stand Set", "Concert", "high", 80),
        ("Nijisanji", "Various", "Concert Goods", "Nijisanji AR LIVE 2024 Penlight Set", "Concert", "mid", 42),
        ("Hololive", "Mori Calliope", "Concert Goods", "Mori Calliope Sinderella Solo Live 2024 Hoodie", "Solo Concert", "high", 70),
        ("Hololive", "Tokoyami Towa", "Concert Goods", "Tokoyami Towa 1st Solo Live T-Shirt", "Solo Concert", "mid", 40),

        # More Collab Goods (+3)
        ("Hololive", "Various", "Collab Goods", "Hololive x Sanrio Characters Acrylic Stand Set (6pc)", "Collab Cafe", "mid", 42),
        ("Nijisanji", "Various", "Collab Goods", "Nijisanji x FamilyMart Clear File Collection Set", "Standard", "mid", 22),
        ("Hololive", "Various", "Collab Goods", "Hololive x Pizza Hut Collab Clear File Set (JP Only)", "Collab Cafe", "mid", 28),

        # ── Hololive JP Gen 3 — Marine, Noel, Pekora, Flare, Rushia memorial (+6) ──
        ("Hololive", "Houshou Marine", "Birthday Set", "Houshou Marine Birthday 2024 Complete Set", "Birthday", "high", 85),
        ("Hololive", "Houshou Marine", "Tapestry", "Houshou Marine Ahoy!! 2024 B2 Tapestry", "Seasonal", "mid", 35),
        ("Hololive", "Usada Pekora", "Tapestry", "Usada Pekora 5th Anniversary B2 Tapestry", "Anniversary", "mid", 38),
        ("Hololive", "Usada Pekora", "Concert Goods", "Usada Pekora 1st Solo Live Penlight", "Solo Concert", "mid", 42),
        ("Hololive", "Shirogane Noel", "Tapestry", "Shirogane Noel Birthday 2024 B2 Tapestry", "Birthday", "mid", 30),
        ("Hololive", "Uruha Rushia", "Tapestry", "Uruha Rushia Farewell Memorial B2 Tapestry", "Anniversary", "grail", 150),

        # ── Hololive EN Council/Promise — Kronii, Fauna, Mumei, Baelz (+6) ──
        ("Hololive", "Ouro Kronii", "Birthday Set", "Ouro Kronii Birthday 2024 Complete Set", "Birthday", "high", 72),
        ("Hololive", "Ouro Kronii", "Acrylic Stand", "Ouro Kronii 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 26),
        ("Hololive", "Ceres Fauna", "Birthday Set", "Ceres Fauna Birthday 2024 Full Set", "Birthday", "high", 68),
        ("Hololive", "Ceres Fauna", "Tapestry", "Ceres Fauna 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("Hololive", "Nanashi Mumei", "Acrylic Stand", "Nanashi Mumei 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 26),
        ("Hololive", "Hakos Baelz", "Birthday Set", "Hakos Baelz Birthday 2024 Complete Set", "Birthday", "high", 65),

        # ── Hololive Nendoroids & Figma (+10) ──────────────────────────
        ("Hololive", "Gawr Gura", "Nendoroid", "Nendoroid Gawr Gura #1688", "Standard", "high", 55),
        ("Hololive", "Mori Calliope", "Nendoroid", "Nendoroid Mori Calliope #1769", "Standard", "high", 52),
        ("Hololive", "Hoshimachi Suisei", "Nendoroid", "Nendoroid Hoshimachi Suisei #1707", "Standard", "high", 58),
        ("Hololive", "Usada Pekora", "Nendoroid", "Nendoroid Usada Pekora #1656", "Standard", "high", 55),
        ("Hololive", "Tokino Sora", "Nendoroid", "Nendoroid Tokino Sora #1243", "Standard", "high", 65),
        ("Hololive", "Houshou Marine", "Nendoroid", "Nendoroid Houshou Marine #1687", "Standard", "high", 58),
        ("Hololive", "Shirakami Fubuki", "Nendoroid", "Nendoroid Shirakami Fubuki #1255", "Standard", "high", 60),
        ("Hololive", "Gawr Gura", "Figma", "Figma Gawr Gura #601", "Standard", "high", 75),
        ("Hololive", "Mori Calliope", "Figma", "Figma Mori Calliope #610", "Standard", "high", 72),
        ("Hololive", "Hoshimachi Suisei", "Figma", "Figma Hoshimachi Suisei #612", "Standard", "high", 78),

        # ── Hololive Voice Packs (+6) ──────────────────────────────────
        ("Hololive", "Gawr Gura", "Voice Pack", "Gawr Gura ASMR Voice Pack (2024 Limited)", "Birthday", "mid", 35),
        ("Hololive", "Mori Calliope", "Voice Pack", "Mori Calliope Rap Lesson Voice Pack", "Birthday", "mid", 32),
        ("Hololive", "Hoshimachi Suisei", "Voice Pack", "Suisei Tetris Voice Navigation Pack", "Birthday", "mid", 30),
        ("Hololive", "Usada Pekora", "Voice Pack", "Usada Pekora War Criminal Voice Situation Pack", "Birthday", "mid", 35),
        ("Hololive", "Houshou Marine", "Voice Pack", "Houshou Marine Alarm Voice Pack (2024 Birthday)", "Birthday", "mid", 33),
        ("Hololive", "Tokoyami Towa", "Voice Pack", "Tokoyami Towa Bibi & Towa Wake-Up Voice Pack", "Birthday", "mid", 28),

        # ── Hololive EN Myth — Watson Amelia, Kiara, Ina extras (+5) ──
        ("Hololive", "Watson Amelia", "Tapestry", "Watson Amelia 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 35),
        ("Hololive", "Watson Amelia", "Acrylic Stand", "Watson Amelia Graduation Memorial Acrylic Stand", "Anniversary", "high", 85),
        ("Hololive", "Takanashi Kiara", "Birthday Set", "Takanashi Kiara Birthday 2024 Full Set", "Birthday", "high", 70),
        ("Hololive", "Takanashi Kiara", "Tapestry", "Takanashi Kiara KFP Employee B2 Tapestry", "Seasonal", "mid", 28),
        ("Hololive", "Ninomae Ina'nis", "Birthday Set", "Ninomae Ina'nis Birthday 2024 Complete Set", "Birthday", "high", 72),

        # ── Nijisanji EN — Claude, Sonny, Alban, Ren, Maria (+8) ──────
        ("Nijisanji", "Claude Clawmark", "Acrylic Stand", "Claude Clawmark Debut Acrylic Stand", "Debut", "mid", 22),
        ("Nijisanji", "Sonny Brisko", "Birthday Set", "Sonny Brisko Birthday 2024 Complete Set", "Birthday", "high", 55),
        ("Nijisanji", "Sonny Brisko", "Tapestry", "Sonny Brisko 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 26),
        ("Nijisanji", "Alban Knox", "Birthday Set", "Alban Knox Birthday 2024 Full Merch Set", "Birthday", "high", 52),
        ("Nijisanji", "Ren Zotto", "Acrylic Stand", "Ren Zotto Birthday 2024 Acrylic Stand", "Birthday", "mid", 24),
        ("Nijisanji", "Maria Marionette", "Birthday Set", "Maria Marionette Birthday 2024 Complete Set", "Birthday", "high", 58),
        ("Nijisanji", "Maria Marionette", "Tapestry", "Maria Marionette 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("Nijisanji", "Millie Parfait", "Birthday Set", "Millie Parfait Birthday 2024 Merch Set", "Birthday", "high", 55),

        # ── Nijisanji JP — Ibrahim, Leos, Oliver, Furen (+6) ──────────
        ("Nijisanji", "Ibrahim", "Birthday Set", "Ibrahim Birthday 2024 Complete Merch Set", "Birthday", "high", 60),
        ("Nijisanji", "Leos Vincent", "Acrylic Stand", "Leos Vincent Birthday 2024 Acrylic Stand", "Birthday", "mid", 26),
        ("Nijisanji", "Oliver Evans", "Birthday Set", "Oliver Evans Birthday 2024 Full Set", "Birthday", "high", 55),
        ("Nijisanji", "Furen E Lustario", "Tapestry", "Furen E Lustario 4th Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Nijisanji", "Hayama Marin", "Birthday Set", "Hayama Marin Birthday 2024 Merch Set", "Birthday", "mid", 48),
        ("Nijisanji", "Inui Toko", "Birthday Set", "Inui Toko Birthday 2024 Complete Set", "Birthday", "high", 62),

        # ── Nijisanji Nendoroids (+4) ─────────────────────────────────
        ("Nijisanji", "Kuzuha", "Nendoroid", "Nendoroid Kuzuha #1631", "Standard", "high", 55),
        ("Nijisanji", "Kanae", "Nendoroid", "Nendoroid Kanae #1632", "Standard", "high", 52),
        ("Nijisanji", "Tsukino Mito", "Nendoroid", "Nendoroid Tsukino Mito #1440", "Standard", "high", 60),
        ("Nijisanji", "Vox Akuma", "Nendoroid", "Nendoroid Vox Akuma #2068", "Standard", "high", 52),

        # ── VSPO! — Additional members (+6) ───────────────────────────
        ("VSPO!", "Nekota Tsuna", "Birthday Set", "Nekota Tsuna Birthday 2024 Complete Set", "Birthday", "mid", 45),
        ("VSPO!", "Nekota Tsuna", "Acrylic Stand", "Nekota Tsuna 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("VSPO!", "Komori Met", "Birthday Set", "Komori Met Birthday 2024 Merch Set", "Birthday", "mid", 42),
        ("VSPO!", "Kaminari Qpi", "Tapestry", "Kaminari Qpi 1st Anniversary B2 Tapestry", "Anniversary", "mid", 24),
        ("VSPO!", "Kisaragi Ren", "Acrylic Stand", "Kisaragi Ren Birthday 2024 Acrylic Stand", "Birthday", "mid", 22),
        ("VSPO!", "Yumeno Akari", "Birthday Set", "Yumeno Akari Birthday 2024 Full Merch Set", "Birthday", "mid", 48),

        # ── VShojo Additional (+5) ────────────────────────────────────
        ("VShojo", "Kson", "Birthday Set", "Kson Birthday 2024 Complete Merch Set", "Birthday", "high", 58),
        ("VShojo", "Ironmouse", "Nendoroid", "Nendoroid Ironmouse #2150", "Standard", "high", 55),
        ("VShojo", "Ironmouse", "Concert Goods", "Ironmouse Subathon 2024 Commemorative Set", "Concert", "grail", 120),
        ("VShojo", "Froot", "Birthday Set", "Apricot (Froot) Birthday 2024 Merch Set", "Birthday", "mid", 45),
        ("VShojo", "Haruka Karibu", "Acrylic Stand", "Haruka Karibu 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 20),

        # ── Phase Connect Additional (+5) ─────────────────────────────
        ("Phase Connect", "Panko", "Birthday Set", "Panko Birthday 2024 Complete Set", "Birthday", "mid", 38),
        ("Phase Connect", "Ember Amane", "Acrylic Stand", "Ember Amane 1st Anniversary Acrylic Stand", "Anniversary", "mid", 20),
        ("Phase Connect", "Airi Chisaka", "Birthday Set", "Airi Chisaka Birthday 2024 Merch Set", "Birthday", "mid", 42),
        ("Phase Connect", "Idia Yumemi", "Tapestry", "Idia Yumemi Debut Celebration B2 Tapestry", "Debut", "mid", 24),
        ("Phase Connect", "Various", "Merch Box", "Phase Connect Gen 2 Anniversary Complete Box", "Generation", "high", 65),

        # ── Indie VTubers Additional (+8) ─────────────────────────────
        ("Indie", "Neuro-sama", "Acrylic Stand", "Neuro-sama x Evil Neuro Duo Acrylic Stand Set", "Standard", "mid", 28),
        ("Indie", "Neuro-sama", "Birthday Set", "Neuro-sama 2nd Anniversary Merch Set", "Anniversary", "high", 55),
        ("Indie", "Shylily", "Tapestry", "Shylily 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Indie", "Bao The Whale", "Birthday Set", "Bao The Whale Birthday 2024 Complete Set", "Birthday", "mid", 42),
        ("Indie", "Projekt Melody", "Anniversary Set", "Projekt Melody 5th Anniversary Box", "Anniversary", "high", 65),
        ("Indie", "Snuffy", "Acrylic Stand", "Snuffy 2024 Debut Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Indie", "CottontailVA", "Tapestry", "CottontailVA Birthday 2024 B2 Tapestry", "Birthday", "mid", 22),
        ("Indie", "Filian", "Birthday Set", "Filian Birthday 2024 Complete Merch Set", "Birthday", "mid", 45),

        # ── Collaboration Cafe Goods (additional) ─────────────────────
        ("Hololive", "Various", "Collab Goods", "Hololive x Curry Meshi Collaboration Merch Set", "Collab Cafe", "mid", 32),
        ("Hololive", "Various", "Collab Goods", "Hololive x Village Vanguard Exclusive Acrylic Set", "Collab Cafe", "mid", 38),
        ("Hololive", "Various", "Collab Goods", "Hololive x Joypolis Venue Exclusive Badge Set", "Collab Cafe", "mid", 35),
        ("Nijisanji", "Various", "Collab Goods", "Nijisanji x Animate Girls Festival Tapestry Set", "Animate Collab", "mid", 42),
        ("Nijisanji", "Various", "Collab Goods", "Nijisanji x Sweets Paradise Cafe Exclusive Coasters (Full Set)", "Collab Cafe", "mid", 35),

        # ── More Concert & Live Goods (+6) ───────────────────────────
        ("Hololive", "Various", "Concert Goods", "Hololive SUPER EXPO 2025 Full Venue Set", "Concert", "grail", 200),
        ("Hololive", "Hoshimachi Suisei", "Concert Goods", "Suisei Stellar Stellar MV Acrylic Diorama", "Solo Concert", "high", 55),
        ("Hololive", "Various", "Concert Goods", "HoloEN Connect the World 2024 Penlight", "Concert", "mid", 42),
        ("Nijisanji", "Various", "Concert Goods", "Nijisanji Koshien 2024 Full Team Badge Set", "Concert", "mid", 48),
        ("Nijisanji", "Various", "Concert Goods", "NijiFes 2024 Venue-Limited Penlight", "Concert", "mid", 40),
        ("Hololive", "Sakura Miko", "Concert Goods", "Sakura Miko Solo Live 2024 Penlight + Towel", "Solo Concert", "high", 55),

        # ── Hololive JP GAMERS — Okayu, Korone, Mio, Fubuki (+5) ────
        ("Hololive", "Nekomata Okayu", "Birthday Set", "Nekomata Okayu Birthday 2024 Complete Set", "Birthday", "high", 68),
        ("Hololive", "Inugami Korone", "Birthday Set", "Inugami Korone Birthday 2024 Full Set", "Birthday", "high", 72),
        ("Hololive", "Inugami Korone", "Nendoroid", "Nendoroid Inugami Korone #1660", "Standard", "high", 55),
        ("Hololive", "Ookami Mio", "Birthday Set", "Ookami Mio Birthday 2024 Merch Set", "Birthday", "high", 60),
        ("Hololive", "Ookami Mio", "Tapestry", "Ookami Mio Tarot Fortune B2 Tapestry", "Seasonal", "mid", 26),

        # ── Hololive JP 4th Gen extras (+4) ──────────────────────────
        ("Hololive", "Tokoyami Towa", "Birthday Set", "Tokoyami Towa Birthday 2024 Complete Set", "Birthday", "high", 68),
        ("Hololive", "Himemori Luna", "Tapestry", "Himemori Luna Birthday 2024 B2 Tapestry", "Birthday", "mid", 26),
        ("Hololive", "Tsunomaki Watame", "Tapestry", "Tsunomaki Watame 4th Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Hololive", "Amane Kanata", "Tapestry", "Amane Kanata 4th Anniversary B2 Tapestry", "Anniversary", "mid", 28),

        # ── Hololive Sakura Miko & others (+4) ──────────────────────
        ("Hololive", "Sakura Miko", "Birthday Set", "Sakura Miko Birthday 2024 Complete Set", "Birthday", "high", 80),
        ("Hololive", "Sakura Miko", "Signed Shikishi", "Sakura Miko Hand-Signed Birthday Shikishi", "Birthday", "grail", 200),
        ("Hololive", "Sakura Miko", "Nendoroid", "Nendoroid Sakura Miko #1535", "Standard", "high", 62),
        ("Hololive", "Sakura Miko", "Tapestry", "Sakura Miko Elite B2 Tapestry (2024)", "Seasonal", "mid", 30),

        # ══════════════════════════════════════════════════════════════
        # EXPANSION TO 500+ — ~200 additional items
        # ══════════════════════════════════════════════════════════════

        # ── Hololive JP Gen 6 (holoX) — Laplus, Lui, Koyori, Chloe, Iroha ──
        ("Hololive", "Laplus Darkness", "Birthday Set", "Laplus Darkness Birthday 2024 Complete Set", "Birthday", "high", 65),
        ("Hololive", "Laplus Darkness", "Acrylic Stand", "Laplus Darkness 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 26),
        ("Hololive", "Laplus Darkness", "Tapestry", "Laplus Darkness New Outfit B2 Tapestry", "Outfit Reveal", "mid", 28),
        ("Hololive", "Takane Lui", "Birthday Set", "Takane Lui Birthday 2024 Complete Set", "Birthday", "high", 62),
        ("Hololive", "Takane Lui", "Acrylic Stand", "Takane Lui 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("Hololive", "Hakui Koyori", "Birthday Set", "Hakui Koyori Birthday 2024 Full Merch Set", "Birthday", "high", 68),
        ("Hololive", "Hakui Koyori", "Tapestry", "Hakui Koyori Lab Coat B2 Tapestry", "Seasonal", "mid", 28),
        ("Hololive", "Hakui Koyori", "Voice Pack", "Hakui Koyori Science Experiment Voice Pack", "Birthday", "mid", 30),
        ("Hololive", "Sakamata Chloe", "Birthday Set", "Sakamata Chloe Birthday 2024 Complete Set", "Birthday", "high", 72),
        ("Hololive", "Sakamata Chloe", "Acrylic Stand", "Sakamata Chloe 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 26),
        ("Hololive", "Sakamata Chloe", "Tapestry", "Sakamata Chloe New Year 2025 B2 Tapestry", "Seasonal", "mid", 30),
        ("Hololive", "Kazama Iroha", "Birthday Set", "Kazama Iroha Birthday 2024 Complete Set", "Birthday", "high", 65),
        ("Hololive", "Kazama Iroha", "Tapestry", "Kazama Iroha Samurai B2 Tapestry", "Seasonal", "mid", 26),

        # ── Hololive DEV_IS — FLOW GLOW (+6) ──
        ("Hololive", "Isaki Riona", "Acrylic Stand", "Isaki Riona Debut Celebration Acrylic Stand", "Debut", "mid", 24),
        ("Hololive", "Koganei Niko", "Acrylic Stand", "Koganei Niko Debut Celebration Acrylic Stand", "Debut", "mid", 24),
        ("Hololive", "Mizumiya Su", "Acrylic Stand", "Mizumiya Su Debut Celebration Acrylic Stand", "Debut", "mid", 24),
        ("Hololive", "Rindo Chihaya", "Acrylic Stand", "Rindo Chihaya Debut Celebration Acrylic Stand", "Debut", "mid", 24),
        ("Hololive", "Kikirara Vivi", "Acrylic Stand", "Kikirara Vivi Debut Celebration Acrylic Stand", "Debut", "mid", 24),
        ("Hololive", "Juufuutei Raden", "Tapestry", "Juufuutei Raden Art-Style B2 Tapestry", "Seasonal", "mid", 28),

        # ── Hololive ID Gen 1 — Risu, Moona, Iofi (+5) ──
        ("Hololive", "Ayunda Risu", "Birthday Set", "Ayunda Risu Birthday 2024 Complete Set", "Birthday", "high", 48),
        ("Hololive", "Ayunda Risu", "Acrylic Stand", "Ayunda Risu 4th Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Hololive", "Airani Iofifteen", "Birthday Set", "Airani Iofifteen Birthday 2024 Merch Set", "Birthday", "mid", 45),
        ("Hololive", "Moona Hoshinova", "Tapestry", "Moona Hoshinova 4th Anniversary B2 Tapestry", "Anniversary", "mid", 26),
        ("Hololive", "Moona Hoshinova", "Acrylic Stand", "Moona Hoshinova New Year 2025 Acrylic Stand", "Seasonal", "mid", 22),

        # ── Hololive ID Gen 2 — Ollie, Anya, Reine (+5) ──
        ("Hololive", "Kureiji Ollie", "Birthday Set", "Kureiji Ollie Birthday 2024 Complete Set", "Birthday", "high", 52),
        ("Hololive", "Kureiji Ollie", "Acrylic Stand", "Kureiji Ollie 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("Hololive", "Anya Melfissa", "Birthday Set", "Anya Melfissa Birthday 2024 Merch Set", "Birthday", "mid", 48),
        ("Hololive", "Pavolia Reine", "Birthday Set", "Pavolia Reine Birthday 2024 Complete Set", "Birthday", "high", 55),
        ("Hololive", "Pavolia Reine", "Acrylic Stand", "Pavolia Reine 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 24),

        # ── Hololive ID Gen 3 — Zeta, Kaela, Kobo (+5) ──
        ("Hololive", "Vestia Zeta", "Birthday Set", "Vestia Zeta Birthday 2024 Complete Set", "Birthday", "high", 50),
        ("Hololive", "Vestia Zeta", "Acrylic Stand", "Vestia Zeta 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Hololive", "Kaela Kovalskia", "Birthday Set", "Kaela Kovalskia Birthday 2024 Merch Set", "Birthday", "high", 52),
        ("Hololive", "Kaela Kovalskia", "Tapestry", "Kaela Kovalskia Blacksmith B2 Tapestry", "Seasonal", "mid", 24),
        ("Hololive", "Kobo Kanaeru", "Birthday Set", "Kobo Kanaeru Birthday 2024 Complete Set", "Birthday", "high", 58),

        # ── Nijisanji JP — Mayuzumi, Fuwa, Hayama, Ange, Lize, Inui, Shiina, Sasaki additional ──
        ("Nijisanji", "Kenmochi Touya", "Birthday Set", "Kenmochi Touya Birthday 2024 Complete Set", "Birthday", "high", 65),
        ("Nijisanji", "Kenmochi Touya", "Acrylic Stand", "Kenmochi Touya 6th Anniversary Acrylic Stand", "Anniversary", "mid", 28),
        ("Nijisanji", "Ange Katrina", "Tapestry", "Ange Katrina 5th Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Nijisanji", "Yashiro Kizuku", "Birthday Set", "Yashiro Kizuku Birthday 2024 Complete Set", "Birthday", "high", 58),
        ("Nijisanji", "Hoshikawa Sara", "Birthday Set", "Hoshikawa Sara Birthday 2024 Full Merch Set", "Birthday", "high", 68),
        ("Nijisanji", "Hoshikawa Sara", "Tapestry", "Hoshikawa Sara Summer B2 Tapestry", "Seasonal", "mid", 32),
        ("Nijisanji", "Suo Sango", "Birthday Set", "Suo Sango Birthday 2024 Complete Set", "Birthday", "mid", 48),
        ("Nijisanji", "Kaida Haru", "Acrylic Stand", "Kaida Haru Birthday 2024 Acrylic Stand", "Birthday", "mid", 24),
        ("Nijisanji", "Nagao Kei", "Birthday Set", "Nagao Kei Birthday 2024 Merch Set", "Birthday", "mid", 45),
        ("Nijisanji", "Akira Ray", "Acrylic Stand", "Akira Ray 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 22),

        # ── Nijisanji EN — Ethyria, Noctyx, XSOLEIL, TTT, Denauth (+12) ──
        ("Nijisanji", "Enna Alouette", "Birthday Set", "Enna Alouette Birthday 2024 Complete Set", "Birthday", "high", 55),
        ("Nijisanji", "Enna Alouette", "Tapestry", "Enna Alouette 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 26),
        ("Nijisanji", "Reimu Endou", "Birthday Set", "Reimu Endou Birthday 2024 Merch Set", "Birthday", "mid", 48),
        ("Nijisanji", "Fulgur Ovid", "Birthday Set", "Fulgur Ovid Birthday 2024 Complete Set", "Birthday", "high", 52),
        ("Nijisanji", "Uki Violeta", "Acrylic Stand", "Uki Violeta Birthday 2024 Acrylic Stand", "Birthday", "mid", 24),
        ("Nijisanji", "Hex Haywire", "Birthday Set", "Hex Haywire Birthday 2024 Merch Set", "Birthday", "mid", 42),
        ("Nijisanji", "Kyo Kaneko", "Acrylic Stand", "Kyo Kaneko 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Nijisanji", "Aster Arcadia", "Birthday Set", "Aster Arcadia Birthday 2024 Complete Set", "Birthday", "mid", 45),
        ("Nijisanji", "Kotoka Torahime", "Tapestry", "Kotoka Torahime 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 26),
        ("Nijisanji", "Ver Vermillion", "Birthday Set", "Ver Vermillion Birthday 2024 Merch Set", "Birthday", "mid", 42),
        ("Nijisanji", "Meloco Kyoran", "Acrylic Stand", "Meloco Kyoran Birthday 2024 Acrylic Stand", "Birthday", "mid", 24),
        ("Nijisanji", "Victoria Brightshield", "Acrylic Stand", "Victoria Brightshield Debut Acrylic Stand", "Debut", "mid", 22),

        # ── Nijisanji KR Merged (+4) ──
        ("Nijisanji", "Ban Hada", "Birthday Set", "Ban Hada Birthday 2024 Complete Set", "Birthday", "mid", 45),
        ("Nijisanji", "Nari Yang", "Acrylic Stand", "Nari Yang 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Nijisanji", "So Nagi", "Birthday Set", "So Nagi Birthday 2024 Merch Set", "Birthday", "mid", 42),
        ("Nijisanji", "Ha Yun", "Tapestry", "Ha Yun Graduation Memorial B2 Tapestry", "Anniversary", "high", 60),

        # ── VSPO! — Complete Roster (+10) ──
        ("VSPO!", "Ichinose Uruha", "Birthday Set", "Ichinose Uruha Birthday 2024 Complete Set", "Birthday", "high", 58),
        ("VSPO!", "Kurumi Noah", "Birthday Set", "Kurumi Noah Birthday 2024 Full Merch Set", "Birthday", "mid", 48),
        ("VSPO!", "Kurumi Noah", "Acrylic Stand", "Kurumi Noah 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("VSPO!", "Yakumo Beni", "Birthday Set", "Yakumo Beni Birthday 2024 Complete Set", "Birthday", "mid", 45),
        ("VSPO!", "Togashi Ema", "Acrylic Stand", "Togashi Ema Birthday 2024 Acrylic Stand", "Birthday", "mid", 22),
        ("VSPO!", "Hanabusa Lisa", "Birthday Set", "Hanabusa Lisa Birthday 2024 Merch Set", "Birthday", "mid", 42),
        ("VSPO!", "Sendo Mia", "Acrylic Stand", "Sendo Mia 1st Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("VSPO!", "Various", "Concert Goods", "VSPO! 3rd Anniversary Live Penlight Set", "Concert", "mid", 38),
        ("VSPO!", "Various", "Concert Goods", "VSPO! vs Hololive Collab Stream Merch Set", "Concert", "mid", 42),
        ("VSPO!", "Various", "Merch Box", "VSPO! 2024 Anniversary Complete Box", "Generation", "high", 75),

        # ── VShojo — Complete Roster (+8) ──
        ("VShojo", "Froot", "Tapestry", "Apricot (Froot) 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("VShojo", "Silvervale", "Birthday Set", "Silvervale Birthday 2024 Complete Set", "Birthday", "mid", 42),
        ("VShojo", "Hime Hajime", "Acrylic Stand", "Hime Hajime Birthday 2024 Acrylic Stand", "Birthday", "mid", 22),
        ("VShojo", "Geega", "Birthday Set", "Geega Birthday 2024 Complete Merch Set", "Birthday", "mid", 45),
        ("VShojo", "Matara Kan", "Tapestry", "Matara Kan 1st VShojo Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("VShojo", "Various", "Concert Goods", "VShojo New Year Concert 2025 Penlight", "Concert", "mid", 35),
        ("VShojo", "Various", "Merch Box", "VShojo 4th Anniversary Complete Box Set", "Generation", "high", 80),
        ("VShojo", "Ironmouse", "Signed Shikishi", "Ironmouse Hand-Signed Birthday Shikishi 2024", "Birthday", "grail", 180),

        # ── Hololive Nendoroids — Additional ──
        ("Hololive", "Ouro Kronii", "Nendoroid", "Nendoroid Ouro Kronii #2089", "Standard", "high", 55),
        ("Hololive", "Ceres Fauna", "Nendoroid", "Nendoroid Ceres Fauna #2090", "Standard", "high", 52),
        ("Hololive", "Nanashi Mumei", "Nendoroid", "Nendoroid Nanashi Mumei #2091", "Standard", "high", 55),
        ("Hololive", "IRyS", "Nendoroid", "Nendoroid IRyS #1981", "Standard", "high", 58),
        ("Hololive", "Shiori Novella", "Nendoroid", "Nendoroid Shiori Novella #2200", "Standard", "high", 52),
        ("Hololive", "FUWAMOCO", "Nendoroid", "Nendoroid FUWAMOCO Twin Set #2201", "Standard", "grail", 110),
        ("Hololive", "Tokoyami Towa", "Nendoroid", "Nendoroid Tokoyami Towa #1900", "Standard", "high", 55),
        ("Hololive", "Tsunomaki Watame", "Nendoroid", "Nendoroid Tsunomaki Watame #1810", "Standard", "high", 52),
        ("Hololive", "Amane Kanata", "Nendoroid", "Nendoroid Amane Kanata #1820", "Standard", "high", 55),
        ("Hololive", "Nekomata Okayu", "Nendoroid", "Nendoroid Nekomata Okayu #1660", "Standard", "high", 58),

        # ── Hololive Figma — Additional ──
        ("Hololive", "Usada Pekora", "Figma", "Figma Usada Pekora #620", "Standard", "high", 72),
        ("Hololive", "Houshou Marine", "Figma", "Figma Houshou Marine #625", "Standard", "high", 75),
        ("Hololive", "Shirakami Fubuki", "Figma", "Figma Shirakami Fubuki #590", "Standard", "high", 70),
        ("Hololive", "Tokino Sora", "Figma", "Figma Tokino Sora #580", "Standard", "high", 78),

        # ── Hololive Voice Packs — Additional ──
        ("Hololive", "Sakamata Chloe", "Voice Pack", "Sakamata Chloe ASMR Voice Pack (2024)", "Birthday", "mid", 30),
        ("Hololive", "Laplus Darkness", "Voice Pack", "Laplus Darkness Secret Society Voice Pack", "Birthday", "mid", 28),
        ("Hololive", "Shiranui Flare", "Voice Pack", "Shiranui Flare Elf Bedtime Story Voice Pack", "Birthday", "mid", 28),
        ("Hololive", "Oozora Subaru", "Voice Pack", "Oozora Subaru Sports Commentary Voice Pack", "Birthday", "mid", 30),
        ("Hololive", "Shirakami Fubuki", "Voice Pack", "Shirakami Fubuki Alarm & Navigation Voice Pack", "Birthday", "mid", 32),
        ("Hololive", "Nakiri Ayame", "Voice Pack", "Nakiri Ayame Giggle Alarm Voice Pack", "Birthday", "mid", 35),

        # ── Hololive Signed Goods — Additional ──
        ("Hololive", "Usada Pekora", "Signed Shikishi", "Usada Pekora Hand-Signed Birthday Shikishi 2024", "Birthday", "grail", 220),
        ("Hololive", "Hoshimachi Suisei", "Signed Shikishi", "Hoshimachi Suisei Hand-Signed Birthday Shikishi 2024", "Birthday", "grail", 240),
        ("Hololive", "Shirakami Fubuki", "Signed Shikishi", "Shirakami Fubuki Hand-Signed 6th Anniversary Shikishi", "Anniversary", "grail", 180),
        ("Hololive", "Nakiri Ayame", "Signed Shikishi", "Nakiri Ayame Hand-Signed Birthday Shikishi", "Birthday", "grail", 200),

        # ── Hololive Collaboration Cafe Items ──
        ("Hololive", "Various", "Collab Goods", "Hololive x Animate Cafe 2024 Random Acrylic Charm (Full Set)", "Animate Collab", "mid", 55),
        ("Hololive", "Various", "Collab Goods", "Hololive x Capcom Cafe Monster Hunter Collab Set", "Collab Cafe", "mid", 42),
        ("Hololive", "Various", "Collab Goods", "Hololive x Bandai Namco Amusement Prize Plush Set", "Standard", "mid", 48),
        ("Hololive", "Various", "Collab Goods", "Hololive x Family Mart Clear File Collection 2024", "Standard", "mid", 25),
        ("Hololive", "Various", "Collab Goods", "Hololive x SEGA Arcade Prize Figure Set (4pc)", "Standard", "high", 65),
        ("Nijisanji", "Various", "Collab Goods", "Nijisanji x Lawson 2024 Clear File Complete Set", "Standard", "mid", 28),
        ("Nijisanji", "Various", "Collab Goods", "Nijisanji x Sanrio Characters Collab Goods Set", "Collab Cafe", "mid", 45),

        # ── Concert & Live Goods — Additional ──
        ("Hololive", "Various", "Concert Goods", "Hololive 6th Fes. Day 2 Venue-Limited Pin Set", "Concert", "mid", 38),
        ("Hololive", "Various", "Concert Goods", "HoloEN 3rd Anniversary Live Penlight", "Concert", "mid", 42),
        ("Hololive", "Various", "Concert Goods", "HoloID 4th Anniversary Concert Exclusive Towel Set", "Concert", "mid", 32),
        ("Hololive", "Various", "Concert Blu-ray", "Hololive 6th Fes. Blu-ray Box (Pre-Order)", "Concert", "high", 95),
        ("Nijisanji", "Various", "Concert Goods", "Nijisanji Wrestle 2024 Event Goods Set", "Concert", "mid", 45),
        ("Nijisanji", "Various", "Concert Goods", "Nijisanji Koshien 2024 Full Team Towel Set", "Concert", "mid", 38),
        ("Nijisanji", "Various", "Concert Blu-ray", "Nijisanji Koshien 2024 Blu-ray", "Concert", "high", 70),

        # ── Indie VTubers — Additional (+10) ──
        ("Indie", "Shylily", "Acrylic Stand", "Shylily 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("Indie", "Bao The Whale", "Tapestry", "Bao The Whale 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 26),
        ("Indie", "Nyanners", "Signed Shikishi", "Nyanners 10th Anniversary Signed Board", "Anniversary", "grail", 150),
        ("Indie", "Filian", "Acrylic Stand", "Filian VR Concert Acrylic Stand", "Concert", "mid", 24),
        ("Indie", "Projekt Melody", "Tapestry", "Projekt Melody 5th Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Indie", "Saruei", "Birthday Set", "Saruei Birthday 2024 Complete Merch Set", "Birthday", "mid", 42),
        ("Indie", "Saruei", "Acrylic Stand", "Saruei Art Exhibition Acrylic Stand", "Anniversary", "mid", 22),
        ("Indie", "Dokibird", "Birthday Set", "Dokibird Rise Again Complete Merch Set", "Anniversary", "high", 85),
        ("Indie", "Dokibird", "Tapestry", "Dokibird 1st Anniversary B2 Tapestry", "Anniversary", "mid", 35),
        ("Indie", "Neuro-sama", "Voice Pack", "Neuro-sama AI Voice Pack (Limited Edition)", "Anniversary", "high", 55),

        # ── Additional Nijisanji Nendoroids & Figma ──
        ("Nijisanji", "Lize Helesta", "Nendoroid", "Nendoroid Lize Helesta #1650", "Standard", "high", 55),
        ("Nijisanji", "Ange Katrina", "Nendoroid", "Nendoroid Ange Katrina #1651", "Standard", "high", 52),
        ("Nijisanji", "Hoshikawa Sara", "Nendoroid", "Nendoroid Hoshikawa Sara #1800", "Standard", "high", 58),
        ("Nijisanji", "Elira Pendora", "Nendoroid", "Nendoroid Elira Pendora #2100", "Standard", "high", 52),

        # ── Phase Connect — Complete Roster ──
        ("Phase Connect", "Lia Lovelock", "Birthday Set", "Lia Lovelock Birthday 2024 Complete Set", "Birthday", "mid", 42),
        ("Phase Connect", "Lia Lovelock", "Acrylic Stand", "Lia Lovelock 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Phase Connect", "Shiina Amanogawa", "Birthday Set", "Shiina Amanogawa Birthday 2024 Merch Set", "Birthday", "mid", 40),
        ("Phase Connect", "Nasa", "Acrylic Stand", "Nasa 1st Anniversary Acrylic Stand", "Anniversary", "mid", 20),
        ("Phase Connect", "Chisaka Airi", "Tapestry", "Chisaka Airi Birthday B2 Tapestry", "Birthday", "mid", 24),
        ("Phase Connect", "Erina Makina", "Birthday Set", "Erina Makina Birthday 2024 Merch Set", "Birthday", "mid", 38),
        ("Phase Connect", "Clara Pamu", "Acrylic Stand", "Clara Pamu Debut Celebration Acrylic Stand", "Debut", "mid", 20),
        ("Phase Connect", "Various", "Concert Goods", "Phase Connect 3rd Anniversary Live Penlight", "Concert", "mid", 35),
        ("Phase Connect", "Various", "Merch Box", "Phase Connect Gen 3 Debut Complete Box", "Generation", "high", 58),
        ("Phase Connect", "Tenma Maemi", "Tapestry", "Tenma Maemi 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 26),

        # ── Nijisanji JP — Additional Members ──
        ("Nijisanji", "Ex Albio", "Birthday Set", "Ex Albio Birthday 2024 Complete Set", "Birthday", "high", 55),
        ("Nijisanji", "Ex Albio", "Acrylic Stand", "Ex Albio 4th Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("Nijisanji", "Gundou Mirei", "Tapestry", "Gundou Mirei Graduation Memorial B2 Tapestry", "Anniversary", "high", 70),
        ("Nijisanji", "Ars Almal", "Birthday Set", "Ars Almal Birthday 2024 Complete Set", "Birthday", "high", 60),
        ("Nijisanji", "Ars Almal", "Acrylic Stand", "Ars Almal 5th Anniversary Acrylic Stand", "Anniversary", "mid", 26),
        ("Nijisanji", "Maimoto Keisuke", "Birthday Set", "Maimoto Keisuke Birthday 2024 Full Merch Set", "Birthday", "high", 55),
        ("Nijisanji", "Machita Chima", "Birthday Set", "Machita Chima Birthday 2024 Complete Set", "Birthday", "high", 62),
        ("Nijisanji", "Machita Chima", "Tapestry", "Machita Chima Graduation Memorial B2 Tapestry", "Anniversary", "high", 80),
        ("Nijisanji", "Fushimi Gaku", "Acrylic Stand", "Fushimi Gaku Birthday 2024 Acrylic Stand", "Birthday", "mid", 22),
        ("Nijisanji", "Debidebi Debiru", "Birthday Set", "Debidebi Debiru Birthday 2024 Merch Set", "Birthday", "mid", 48),
        ("Nijisanji", "Shellin Burgundy", "Birthday Set", "Shellin Burgundy Birthday 2024 Complete Set", "Birthday", "mid", 45),
        ("Nijisanji", "Lauren Iroas", "Acrylic Stand", "Lauren Iroas Birthday 2024 Acrylic Stand", "Birthday", "mid", 26),
        ("Nijisanji", "Axia Krone", "Tapestry", "Axia Krone Graduation Memorial B2 Tapestry", "Anniversary", "high", 65),

        # ── Hololive — Additional Birthday/Anniversary Sets ──
        ("Hololive", "Aki Rosenthal", "Birthday Set", "Aki Rosenthal Birthday 2024 Complete Set", "Birthday", "high", 55),
        ("Hololive", "Yozora Mel", "Birthday Set", "Yozora Mel Birthday 2024 Farewell Set", "Birthday", "high", 58),
        ("Hololive", "Murasaki Shion", "Tapestry", "Murasaki Shion Birthday 2024 B2 Tapestry", "Birthday", "mid", 28),
        ("Hololive", "Murasaki Shion", "Signed Shikishi", "Murasaki Shion Hand-Signed Birthday Shikishi", "Birthday", "grail", 190),
        ("Hololive", "Yuzuki Choco", "Birthday Set", "Yuzuki Choco Birthday 2024 Complete Set", "Birthday", "high", 58),
        ("Hololive", "Yuzuki Choco", "Voice Pack", "Yuzuki Choco ASMR Medical Exam Voice Pack", "Birthday", "mid", 32),
        ("Hololive", "IRyS", "Tapestry", "IRyS Birthday 2024 B2 Tapestry", "Birthday", "mid", 30),
        ("Hololive", "IRyS", "Acrylic Stand", "IRyS 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 26),
        ("Hololive", "IRyS", "Voice Pack", "IRyS Hope Voice Pack (2024 Birthday)", "Birthday", "mid", 30),
        ("Hololive", "Koseki Bijou", "Acrylic Stand", "Koseki Bijou 1st Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("Hololive", "Shiori Novella", "Tapestry", "Shiori Novella Birthday B2 Tapestry", "Birthday", "mid", 26),
        ("Hololive", "FUWAMOCO", "Tapestry", "FUWAMOCO 1st Anniversary Twin B2 Tapestry", "Anniversary", "mid", 35),
        ("Hololive", "FUWAMOCO", "Voice Pack", "FUWAMOCO Morning Alarm Voice Pack (Twin Set)", "Birthday", "mid", 38),

        # ── Additional Concert Blu-rays ──
        ("Hololive", "Houshou Marine", "Concert Blu-ray", "Houshou Marine Major Debut Concert Blu-ray", "Solo Concert", "high", 85),
        ("Hololive", "Usada Pekora", "Concert Blu-ray", "Usada Pekora 1st Solo Live Blu-ray", "Solo Concert", "high", 80),
        ("Hololive", "Sakura Miko", "Concert Blu-ray", "Sakura Miko Solo Live 2024 Blu-ray", "Solo Concert", "high", 78),
        ("Hololive", "Mori Calliope", "Concert Blu-ray", "Mori Calliope Sinderella Live Blu-ray", "Solo Concert", "high", 82),
        ("Hololive", "Tokoyami Towa", "Concert Blu-ray", "Tokoyami Towa 1st Solo Live Blu-ray", "Solo Concert", "high", 72),
        ("Hololive", "Tsunomaki Watame", "Concert Blu-ray", "Watame Night Fever!! Solo Live Blu-ray", "Solo Concert", "high", 70),

        # ── Additional Autograph Boards ──
        ("Hololive", "Mori Calliope", "Signed Shikishi", "Mori Calliope Hand-Signed Sinderella Live Shikishi", "Solo Concert", "grail", 220),
        ("Hololive", "Gawr Gura", "Signed Shikishi", "Gawr Gura Hand-Signed Farewell Shikishi Board", "Anniversary", "grail", 350),
        ("Hololive", "Tokino Sora", "Signed Shikishi", "Tokino Sora Hand-Signed 7th Anniversary Shikishi", "Anniversary", "grail", 200),
        ("Nijisanji", "Tsukino Mito", "Signed Shikishi", "Tsukino Mito Hand-Signed 6th Anniversary Shikishi", "Anniversary", "grail", 180),

        # ── Nijisanji EN — Remaining Members ──
        ("Nijisanji", "Petra Gurin", "Birthday Set", "Petra Gurin Birthday 2024 Complete Set", "Birthday", "high", 52),
        ("Nijisanji", "Petra Gurin", "Acrylic Stand", "Petra Gurin 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("Nijisanji", "Finana Ryugu", "Birthday Set", "Finana Ryugu Birthday 2024 Merch Set", "Birthday", "mid", 48),
        ("Nijisanji", "Luca Kaneshiro", "Birthday Set", "Luca Kaneshiro Birthday 2024 Complete Set", "Birthday", "high", 68),
        ("Nijisanji", "Luca Kaneshiro", "Tapestry", "Luca Kaneshiro 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Nijisanji", "Shu Yamino", "Birthday Set", "Shu Yamino Birthday 2024 Complete Merch Set", "Birthday", "high", 55),
        ("Nijisanji", "Ike Eveland", "Birthday Set", "Ike Eveland Birthday 2024 Complete Set", "Birthday", "high", 52),
        ("Nijisanji", "Nina Kosaka", "Tapestry", "Nina Kosaka Graduation Memorial B2 Tapestry", "Anniversary", "high", 70),

        # ── Final Expansion Items ──
        ("Hololive", "Ouro Kronii", "Voice Pack", "Ouro Kronii Time Warp Voice Pack (2024)", "Birthday", "mid", 30),
        ("Hololive", "Ceres Fauna", "Voice Pack", "Ceres Fauna Nature ASMR Voice Pack (2024)", "Birthday", "mid", 30),
        ("Hololive", "Hakos Baelz", "Voice Pack", "Hakos Baelz Chaos Voice Situation Pack", "Birthday", "mid", 28),
        ("Hololive", "Nerissa Ravencroft", "Voice Pack", "Nerissa Ravencroft Singing Lesson Voice Pack", "Birthday", "mid", 28),
        ("Hololive", "Koseki Bijou", "Voice Pack", "Koseki Bijou Gaming Voice Pack (2024)", "Birthday", "mid", 28),
        ("Hololive", "Shiori Novella", "Voice Pack", "Shiori Novella Horror Story Voice Pack", "Birthday", "mid", 28),
        ("Hololive", "Laplus Darkness", "Nendoroid", "Nendoroid Laplus Darkness #2180", "Standard", "high", 52),
        ("Hololive", "Sakamata Chloe", "Nendoroid", "Nendoroid Sakamata Chloe #2190", "Standard", "high", 55),
        ("Hololive", "Hakui Koyori", "Nendoroid", "Nendoroid Hakui Koyori #2185", "Standard", "high", 52),
        ("Hololive", "Various", "Collab Goods", "Hololive x Taito Arcade Prize Keychain Set (12pc)", "Standard", "mid", 35),
        ("Nijisanji", "Various", "Collab Goods", "Nijisanji x Sega Arcade Prize Plush Set (8pc)", "Standard", "mid", 42),
        ("Indie", "Vedal987", "Birthday Set", "Vedal987 x Neuro-sama Anniversary Complete Set", "Anniversary", "high", 65),
        ("Indie", "CottontailVA", "Birthday Set", "CottontailVA Birthday 2024 Full Merch Set", "Birthday", "mid", 38),

        # ══════════════════════════════════════════════════════════════
        # EXPANSION TO 605+ — ~55 additional under-represented items
        # ══════════════════════════════════════════════════════════════

        # ── Hololive EN Gen 3 (Advent) — Shiori, Bijou, Nerissa, FUWAMOCO (+8) ──
        ("Hololive", "Shiori Novella", "Voice Pack", "Shiori Novella Forbidden Library ASMR Voice Pack", "Birthday", "mid", 30),
        ("Hololive", "Shiori Novella", "Signed Shikishi", "Shiori Novella Hand-Signed 1st Anniversary Shikishi", "Anniversary", "grail", 160),
        ("Hololive", "Koseki Bijou", "Birthday Set", "Koseki Bijou Birthday 2025 Complete Merch Set", "Birthday", "high", 72),
        ("Hololive", "Koseki Bijou", "Voice Pack", "Koseki Bijou Gem Hunter Voice Pack", "Birthday", "mid", 28),
        ("Hololive", "FUWAMOCO", "Concert Goods", "FUWAMOCO Bau Bau Live 2025 Penlight Set", "Concert", "mid", 42),
        ("Hololive", "FUWAMOCO", "Signed Shikishi", "FUWAMOCO Hand-Signed Twin Shikishi Board Set", "Anniversary", "grail", 280),
        ("Hololive", "Nerissa Ravencroft", "Birthday Set", "Nerissa Ravencroft Birthday 2025 Complete Set", "Birthday", "high", 68),
        ("Hololive", "Nerissa Ravencroft", "Concert Goods", "Nerissa Ravencroft Karaoke Live Towel + Penlight", "Solo Concert", "mid", 40),

        # ── Hololive ID — Risu, Moona, Iofi, Ollie, Anya, Zeta, Kaela (+7) ──
        ("Hololive", "Ayunda Risu", "Tapestry", "Ayunda Risu 5th Anniversary B2 Tapestry", "Anniversary", "mid", 26),
        ("Hololive", "Ayunda Risu", "Voice Pack", "Ayunda Risu Squirrel ASMR Voice Pack", "Birthday", "mid", 28),
        ("Hololive", "Airani Iofifteen", "Tapestry", "Airani Iofifteen 5th Anniversary Art B2 Tapestry", "Anniversary", "mid", 24),
        ("Hololive", "Kureiji Ollie", "Voice Pack", "Kureiji Ollie Zombie Wake-Up Voice Pack", "Birthday", "mid", 28),
        ("Hololive", "Anya Melfissa", "Acrylic Stand", "Anya Melfissa 4th Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Hololive", "Vestia Zeta", "Voice Pack", "Vestia Zeta Secret Agent Voice Pack", "Birthday", "mid", 28),
        ("Hololive", "Kaela Kovalskia", "Acrylic Stand", "Kaela Kovalskia 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 24),

        # ── Nijisanji EN — Luxiem/Noctyx (+8) ──
        ("Nijisanji", "Vox Akuma", "Tapestry", "Vox Akuma 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 32),
        ("Nijisanji", "Vox Akuma", "Voice Pack", "Vox Akuma Demon Lord ASMR Voice Pack", "Birthday", "mid", 35),
        ("Nijisanji", "Luca Kaneshiro", "Signed Shikishi", "Luca Kaneshiro Hand-Signed Farewell Shikishi Board", "Anniversary", "grail", 180),
        ("Nijisanji", "Ike Eveland", "Tapestry", "Ike Eveland Birthday 2024 B2 Tapestry", "Birthday", "mid", 26),
        ("Nijisanji", "Shu Yamino", "Acrylic Stand", "Shu Yamino 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("Nijisanji", "Fulgur Ovid", "Tapestry", "Fulgur Ovid 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("Nijisanji", "Alban Knox", "Tapestry", "Alban Knox Birthday 2024 B2 Tapestry", "Birthday", "mid", 26),
        ("Nijisanji", "Yugo Asuma", "Tapestry", "Yugo Asuma Graduation Memorial B2 Tapestry", "Anniversary", "high", 65),

        # ── VShojo — Ironmouse, Kson, Henya, Froot, Geega, Mata, Hime (+7) ──
        ("VShojo", "Ironmouse", "Voice Pack", "Ironmouse Birthday 2025 Demon Queen Voice Pack", "Birthday", "mid", 35),
        ("VShojo", "Kson", "Tapestry", "Kson 2nd VShojo Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("VShojo", "Henya the Genius", "Tapestry", "Henya the Genius Birthday 2025 B2 Tapestry", "Birthday", "mid", 26),
        ("VShojo", "Froot", "Acrylic Stand", "Apricot (Froot) New Outfit Acrylic Stand", "Outfit Reveal", "mid", 22),
        ("VShojo", "Geega", "Tapestry", "Geega 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 24),
        ("VShojo", "Matara Kan", "Acrylic Stand", "Matara Kan 2nd VShojo Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("VShojo", "Hime Hajime", "Birthday Set", "Hime Hajime Birthday 2025 Complete Merch Set", "Birthday", "mid", 42),

        # ── Hololive JP Recent Gens — ReGLOSS/DEV_IS & FLOW GLOW (+8) ──
        ("Hololive", "Otonose Kanade", "Voice Pack", "Otonose Kanade Piano ASMR Voice Pack", "Birthday", "mid", 30),
        ("Hololive", "Todoroki Hajime", "Birthday Set", "Todoroki Hajime Birthday 2025 Complete Set", "Birthday", "high", 62),
        ("Hololive", "Ichijou Ririka", "Birthday Set", "Ichijou Ririka Birthday 2025 Merch Set", "Birthday", "high", 58),
        ("Hololive", "Juufuutei Raden", "Signed Shikishi", "Juufuutei Raden Hand-Signed Art Shikishi Board", "Birthday", "grail", 175),
        ("Hololive", "Hiodoshi Ao", "Birthday Set", "Hiodoshi Ao Birthday 2025 Complete Set", "Birthday", "high", 55),
        ("Hololive", "Isaki Riona", "Birthday Set", "Isaki Riona 1st Anniversary Merch Set", "Anniversary", "high", 52),
        ("Hololive", "Koganei Niko", "Birthday Set", "Koganei Niko 1st Anniversary Merch Set", "Anniversary", "high", 50),
        ("Hololive", "Mizumiya Su", "Birthday Set", "Mizumiya Su 1st Anniversary Merch Set", "Anniversary", "high", 50),

        # ── Holostars / STAR — Aruran, Rikka, Miyabi, Astel, Izuru, Roberu, Temma (+7) ──
        ("Holostars", "Arurandeisu", "Birthday Set", "Arurandeisu Birthday 2024 Complete Merch Set", "Birthday", "mid", 42),
        ("Holostars", "Rikka", "Concert Goods", "Rikka Solo Live 2024 Penlight + Towel Set", "Solo Concert", "mid", 38),
        ("Holostars", "Kishido Temma", "Acrylic Stand", "Kishido Temma 4th Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Holostars", "Yukoku Roberu", "Birthday Set", "Yukoku Roberu Birthday 2024 Full Merch Set", "Birthday", "mid", 45),
        ("Holostars", "Astel Leda", "Tapestry", "Astel Leda 4th Anniversary B2 Tapestry", "Anniversary", "mid", 24),
        ("Holostars", "Kageyama Shien", "Birthday Set", "Kageyama Shien Birthday 2024 Complete Set", "Birthday", "mid", 48),
        ("Holostars", "Various", "Concert Goods", "Holostars 5th Anniversary Live Penlight Set", "Concert", "mid", 35),

        # ── Phase Connect — Pippa, Tenma, Lia, Lumi, Ember (+5) ──
        ("Phase Connect", "Pipkin Pippa", "Voice Pack", "Pipkin Pippa Rabbit Hole Voice Pack", "Birthday", "mid", 28),
        ("Phase Connect", "Tenma Maemi", "Acrylic Stand", "Tenma Maemi 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Phase Connect", "Lumi Celestia", "Birthday Set", "Lumi Celestia Birthday 2025 Complete Merch Set", "Birthday", "mid", 42),
        ("Phase Connect", "Lumi Celestia", "Acrylic Stand", "Lumi Celestia 1st Anniversary Acrylic Stand", "Anniversary", "mid", 20),
        ("Phase Connect", "Ember Amane", "Birthday Set", "Ember Amane Birthday 2025 Merch Set", "Birthday", "mid", 38),

        # ── Independent VTuber Collabs (+5) ──
        ("Indie", "Dokibird", "Concert Goods", "Dokibird Freedom Live 2025 Penlight + Wristband", "Concert", "mid", 38),
        ("Indie", "Neuro-sama", "Nendoroid", "Nendoroid Neuro-sama x Evil Neuro Twin Set #2350", "Standard", "grail", 110),
        ("Indie", "Shylily", "Voice Pack", "Shylily Orca ASMR Voice Pack (Limited)", "Birthday", "mid", 30),
        ("Indie", "Filian", "Tapestry", "Filian x Shylily Collab B2 Tapestry", "Standard", "mid", 28),
        ("Indie", "Bao The Whale", "Acrylic Stand", "Bao x Shylily Summer Duo Acrylic Stand Set", "Standard", "mid", 26),

        # ── Expansion to 700+ — Hololive 3rd/4th/5th Fes, Nijisanji EN, VShojo, Indie, Gamers/Stars ──

        # Hololive 3rd Fes Goods (+5)
        ("Hololive", "Various", "Concert Goods", "Hololive 3rd Fes. Link Your Wish Venue Penlight", "Concert", "mid", 38),
        ("Hololive", "Various", "Concert Goods", "Hololive 3rd Fes. Link Your Wish Tapestry Set (6pc)", "Concert", "high", 75),
        ("Hololive", "Various", "Concert Goods", "Hololive 3rd Fes. Link Your Wish T-Shirt (Staff Ver.)", "Concert", "mid", 42),
        ("Hololive", "Various", "Concert Goods", "Hololive 3rd Fes. Link Your Wish Rubber Strap Set", "Concert", "mid", 30),
        ("Hololive", "Various", "Concert Goods", "Hololive 3rd Fes. Link Your Wish Clear File Set (10pc)", "Concert", "mid", 25),

        # Hololive 4th Fes Goods (+5)
        ("Hololive", "Various", "Concert Goods", "Hololive 4th Fes. Our Bright Parade Venue Penlight", "Concert", "mid", 40),
        ("Hololive", "Various", "Concert Goods", "Hololive 4th Fes. Our Bright Parade Acrylic Diorama Set", "Concert", "high", 65),
        ("Hololive", "Various", "Concert Goods", "Hololive 4th Fes. Our Bright Parade Blanket", "Concert", "mid", 48),
        ("Hololive", "Various", "Concert Goods", "Hololive 4th Fes. Our Bright Parade Trading Badge Set (20pc)", "Concert", "mid", 35),
        ("Hololive", "Various", "Concert Goods", "Hololive 4th Fes. Our Bright Parade Photo Card Set", "Concert", "mid", 28),

        # Hololive 5th Fes Goods (+5)
        ("Hololive", "Various", "Concert Goods", "Hololive 5th Fes. Capture the Moment Venue Penlight", "Concert", "mid", 42),
        ("Hololive", "Various", "Concert Goods", "Hololive 5th Fes. Capture the Moment Fan Towel", "Concert", "mid", 25),
        ("Hololive", "Various", "Concert Goods", "Hololive 5th Fes. Capture the Moment Poster Set (A2 x6)", "Concert", "high", 55),
        ("Hololive", "Various", "Concert Goods", "Hololive 5th Fes. Capture the Moment Wristband Set (5pc)", "Concert", "standard", 18),
        ("Hololive", "Various", "Concert Goods", "Hololive 5th Fes. Capture the Moment Clear Folder Set (12pc)", "Concert", "mid", 28),

        # Nijisanji EN — Ethyria, Iluna, XSOLEIL birthday/grad merch (+10)
        ("Nijisanji", "Enna Alouette", "Birthday Set", "Enna Alouette Birthday 2025 Complete Merch Set", "Birthday", "high", 65),
        ("Nijisanji", "Enna Alouette", "Tapestry", "Enna Alouette 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Nijisanji", "Millie Parfait", "Birthday Set", "Millie Parfait Birthday 2025 Complete Set", "Birthday", "high", 62),
        ("Nijisanji", "Millie Parfait", "Acrylic Stand", "Millie Parfait 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 25),
        ("Nijisanji", "Reimu Endou", "Birthday Set", "Reimu Endou Birthday 2025 Merch Set", "Birthday", "high", 58),
        ("Nijisanji", "Nina Kosaka", "Tapestry", "Nina Kosaka Graduation Memorial B2 Tapestry", "Anniversary", "high", 88),
        ("Nijisanji", "Kyo Kaneko", "Birthday Set", "Kyo Kaneko Birthday 2025 Complete Set", "Birthday", "mid", 48),
        ("Nijisanji", "Aia Amare", "Birthday Set", "Aia Amare Birthday 2025 Merch Set", "Birthday", "mid", 45),
        ("Nijisanji", "Scarle Yonaguni", "Tapestry", "Scarle Yonaguni Birthday B2 Tapestry", "Birthday", "mid", 32),
        ("Nijisanji", "Maria Marionette", "Birthday Set", "Maria Marionette Birthday 2025 Complete Set", "Birthday", "high", 60),

        # VShojo expanded merch (+8)
        ("VShojo", "Ironmouse", "Concert Goods", "Ironmouse VShojo Fest 2025 Venue Penlight", "Concert", "high", 55),
        ("VShojo", "Ironmouse", "Nendoroid", "Nendoroid Ironmouse Demon Queen Ver. #2450", "Standard", "high", 65),
        ("VShojo", "Zentreya", "Tapestry", "Zentreya 4th Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("VShojo", "Henya the Genius", "Voice Pack", "Henya the Genius Birthday Voice Pack Physical Edition", "Birthday", "mid", 32),
        ("VShojo", "Matara Kan", "Birthday Set", "Matara Kan Birthday 2025 Complete Merch Set", "Birthday", "high", 55),
        ("VShojo", "Geega", "Acrylic Stand", "Geega Birthday 2025 Acrylic Stand", "Birthday", "mid", 22),
        ("VShojo", "Haruka Karibu", "Tapestry", "Haruka Karibu Graduation Memorial B2 Tapestry", "Anniversary", "high", 85),
        ("VShojo", "Kson", "Concert Goods", "Kson Solo Live 2025 Venue-Limited Towel + Badge Set", "Concert", "mid", 38),

        # Hololive Gamers merch (+6)
        ("Hololive", "Shirakami Fubuki", "Birthday Set", "Shirakami Fubuki Birthday 2025 Premium Set", "Birthday", "high", 80),
        ("Hololive", "Shirakami Fubuki", "Signed Tapestry", "Shirakami Fubuki Hand-Signed Birthday B2 Tapestry", "Birthday", "grail", 260),
        ("Hololive", "Ookami Mio", "Birthday Set", "Ookami Mio Birthday 2025 Complete Set", "Birthday", "high", 68),
        ("Hololive", "Ookami Mio", "Tapestry", "Ookami Mio 6th Anniversary B2 Tapestry", "Anniversary", "mid", 32),
        ("Hololive", "Nekomata Okayu", "Birthday Set", "Nekomata Okayu Birthday 2025 Premium Set", "Birthday", "high", 75),
        ("Hololive", "Inugami Korone", "Birthday Set", "Inugami Korone Birthday 2025 Complete Set", "Birthday", "high", 78),

        # Holostars EN — TEMPUS merch (+5)
        ("Holostars", "Regis Altare", "Birthday Set", "Regis Altare Birthday 2025 Complete Merch Set", "Birthday", "mid", 45),
        ("Holostars", "Axel Syrios", "Birthday Set", "Axel Syrios Birthday 2025 Merch Set", "Birthday", "mid", 42),
        ("Holostars", "Noir Vesper", "Tapestry", "Noir Vesper Graduation Memorial B2 Tapestry", "Anniversary", "high", 75),
        ("Holostars", "Magni Dezmond", "Tapestry", "Magni Dezmond Graduation Memorial B2 Tapestry", "Anniversary", "high", 72),
        ("Holostars", "Various", "Concert Goods", "Holostars EN 2nd Anniversary Live Goods Set", "Concert", "mid", 38),

        # Hololive EN — Advent & Justice birthday merch (+8)
        ("Hololive", "Shiori Novella", "Birthday Set", "Shiori Novella Birthday 2025 Complete Merch Set", "Birthday", "high", 65),
        ("Hololive", "Shiori Novella", "Acrylic Stand", "Shiori Novella 1st Anniversary Acrylic Stand", "Anniversary", "mid", 26),
        ("Hololive", "Koseki Bijou", "Birthday Set", "Koseki Bijou Birthday 2025 Premium Set", "Birthday", "high", 70),
        ("Hololive", "Nerissa Ravencroft", "Birthday Set", "Nerissa Ravencroft Birthday 2025 Set", "Birthday", "high", 62),
        ("Hololive", "FUWAMOCO", "Birthday Set", "FUWAMOCO Shared Birthday 2025 Premium Duo Set", "Birthday", "grail", 110),
        ("Hololive", "Elizabeth Rose Bloodflame", "Debut Set", "Elizabeth Rose Bloodflame Debut Celebration Set", "Debut", "mid", 42),
        ("Hololive", "Gigi Murin", "Debut Set", "Gigi Murin Debut Celebration Merch Set", "Debut", "mid", 40),
        ("Hololive", "Cecilia Immergreen", "Debut Set", "Cecilia Immergreen Debut Celebration Merch Set", "Debut", "mid", 40),

        # Indie VTuber Collabs & Anniversary (+8)
        ("Indie", "Dokibird", "Birthday Set", "Dokibird Birthday 2025 Premium Merch Set", "Birthday", "high", 70),
        ("Indie", "Dokibird", "Signed Shikishi", "Dokibird Hand-Signed Birthday Shikishi Board", "Birthday", "grail", 150),
        ("Indie", "Neuro-sama", "Acrylic Stand", "Neuro-sama 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 28),
        ("Indie", "Shylily", "Birthday Set", "Shylily Birthday 2025 Complete Merch Set", "Birthday", "high", 60),
        ("Indie", "Filian", "Birthday Set", "Filian Birthday 2025 Merch Set", "Birthday", "mid", 48),
        ("Indie", "Bao The Whale", "Birthday Set", "Bao Birthday 2025 Premium Merch Set", "Birthday", "mid", 45),
        ("Indie", "Saruei", "Tapestry", "Saruei 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Indie", "Vedal987", "Acrylic Stand", "Vedal987 x Neuro-sama Duo Acrylic Stand Set", "Standard", "mid", 25),

        # Concert Blu-rays — additional solo/unit concerts (+6)
        ("Hololive", "Tokoyami Towa", "Concert Blu-ray", "Tokoyami Towa 1st Solo Live Before Dawn Blu-ray", "Solo Concert", "high", 85),
        ("Hololive", "Houshou Marine", "Concert Blu-ray", "Houshou Marine 1st Solo Live Ahoy!! Blu-ray", "Solo Concert", "grail", 110),
        ("Hololive", "Mori Calliope", "Concert Blu-ray", "Mori Calliope New Underworld Order Tour Blu-ray", "Solo Concert", "high", 90),
        ("Hololive", "Usada Pekora", "Concert Blu-ray", "Usada Pekora Birthday Party 2024 Blu-ray", "Birthday", "high", 75),
        ("Nijisanji", "Kuzuha", "Concert Blu-ray", "Kuzuha Solo Concert Virtual Strike Blu-ray", "Solo Concert", "high", 80),
        ("Nijisanji", "Kanae", "Concert Blu-ray", "Kanae Birthday Concert 2024 Blu-ray", "Birthday", "high", 70),

        # Voice Pack Physical Editions (+5)
        ("Hololive", "Gawr Gura", "Voice Pack", "Gawr Gura Birthday Voice Pack Physical CD Edition", "Birthday", "mid", 35),
        ("Hololive", "Hoshimachi Suisei", "Voice Pack", "Hoshimachi Suisei Birthday Voice Pack Physical Edition", "Birthday", "mid", 38),
        ("Hololive", "Mori Calliope", "Voice Pack", "Mori Calliope Anniversary Voice Pack Physical CD", "Anniversary", "mid", 32),
        ("Nijisanji", "Vox Akuma", "Voice Pack", "Vox Akuma Birthday Voice Pack Physical CD Edition", "Birthday", "mid", 35),
        ("Nijisanji", "Ike Eveland", "Voice Pack", "Ike Eveland Birthday Voice Pack Physical CD Edition", "Birthday", "mid", 30),

        # Hololive x Lawson/FamilyMart collab goods (+5)
        ("Hololive", "Various", "Collab Goods", "Hololive x Lawson 2025 Campaign Acrylic Stand Set (10pc)", "Lawson Collab", "mid", 48),
        ("Hololive", "Various", "Collab Goods", "Hololive x Lawson 2025 Clear File Set (12pc)", "Lawson Collab", "mid", 30),
        ("Hololive", "Various", "Collab Goods", "Hololive x FamilyMart 2025 Campaign Can Badge Set", "Collab Cafe", "mid", 25),
        ("Hololive", "Various", "Collab Goods", "Hololive x Sanrio Characters Acrylic Stand Full Set", "Collab Cafe", "high", 65),
        ("Hololive", "Various", "Collab Goods", "Hololive x Don Quijote Chibi Plush Set (10pc)", "Collab Cafe", "high", 58),

        # Nijisanji Festival/Concert merch (+6)
        ("Nijisanji", "Various", "Concert Goods", "Nijisanji Koshien 2024 Venue Penlight + Towel Set", "Concert", "mid", 40),
        ("Nijisanji", "Various", "Concert Goods", "NijiFes 2025 Acrylic Diorama Full Set", "Concert", "high", 72),
        ("Nijisanji", "Various", "Concert Goods", "NijiFes 2025 Venue-Limited Poster Set (A2 x8)", "Concert", "high", 55),
        ("Nijisanji", "Various", "Concert Goods", "Nijisanji AR Live 2025 Venue Badge Collection (15pc)", "Concert", "mid", 35),
        ("Nijisanji", "Various", "Concert Goods", "NijiFes 2025 Clear File Set (20pc)", "Concert", "mid", 30),
        ("Nijisanji", "Various", "Concert Blu-ray", "Nijisanji Koshien 2024 Blu-ray Box", "Concert", "high", 70),

        # Hololive Stars JP — Uproar!! merch (+5)
        ("Holostars", "Yatogami Fuma", "Birthday Set", "Yatogami Fuma Birthday 2025 Complete Set", "Birthday", "mid", 45),
        ("Holostars", "Utsugi Uyu", "Birthday Set", "Utsugi Uyu Birthday 2025 Merch Set", "Birthday", "mid", 42),
        ("Holostars", "Hizaki Gamma", "Acrylic Stand", "Hizaki Gamma 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Holostars", "Minase Rio", "Birthday Set", "Minase Rio Birthday 2025 Complete Set", "Birthday", "mid", 48),
        ("Holostars", "Various", "Concert Goods", "Holostars Karaoke Live 2025 Venue Goods Set", "Concert", "mid", 35),

        # High-value signed/limited (+8)
        ("Hololive", "Gawr Gura", "Signed Shikishi", "Gawr Gura Hand-Signed Farewell Shikishi Board", "Anniversary", "grail", 400),
        ("Hololive", "Mori Calliope", "Signed Tapestry", "Mori Calliope Hand-Signed 4th Anniversary B2 Tapestry", "Anniversary", "grail", 240),
        ("Hololive", "Nekomata Okayu", "Signed Tapestry", "Nekomata Okayu Hand-Signed Birthday B2 Tapestry", "Birthday", "grail", 200),
        ("Hololive", "Inugami Korone", "Signed Tapestry", "Inugami Korone Hand-Signed Birthday B2 Tapestry", "Birthday", "grail", 210),
        ("Nijisanji", "Enna Alouette", "Signed Shikishi", "Enna Alouette Hand-Signed Birthday Shikishi Board", "Birthday", "grail", 160),
        ("VShojo", "Ironmouse", "Signed Shikishi", "Ironmouse Hand-Signed Birthday Shikishi Board", "Birthday", "grail", 180),
        ("Indie", "Shylily", "Signed Tapestry", "Shylily Hand-Signed Birthday B2 Tapestry", "Birthday", "grail", 140),
        ("Indie", "Filian", "Signed Shikishi", "Filian Hand-Signed Anniversary Shikishi Board", "Anniversary", "grail", 120),
    ]

    # Merge helper functions
    items += _additional_nijisanji_en()
    items += _additional_nijisanji_jp()
    items += _additional_hololive_5th_gen()
    items += _additional_hololive_dev_is()
    items += _additional_vspo_phase_vshojo()
    items += _additional_concert_blurays()
    items += _additional_vtuber_items()
    # Expansion Batch 2 — Hololive 6th gen, Nijisanji EN, VShojo, EXPO, signed tapestries
    items += _expanded_batch_2()

    catalog = []
    for agency, talent, item_type, name, exclusive_type, tier, price in items:
        catalog.append({
            "agency": agency,
            "talent": talent,
            "item_type": item_type,
            "name": name,
            "exclusive_type": exclusive_type,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def _expanded_batch_2() -> list[tuple]:
    """50 additional VTuber merch — Hololive 6th gen, Nijisanji EN waves, VShojo, EXPO 2024, signed tapestries."""
    return [
        # ── Hololive 6th Gen (holoX) — Lui, Chloe, Iroha, Koyori, Laplus ──
        ("Hololive", "Takane Lui", "Birthday Set", "Takane Lui Birthday 2024 Premium Merch Set", "Birthday", "high", 72),
        ("Hololive", "Takane Lui", "Tapestry", "Takane Lui 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Hololive", "Takane Lui", "Acrylic Stand", "Takane Lui New Outfit Celebration Acrylic Stand", "Outfit Reveal", "mid", 26),
        ("Hololive", "Sakamata Chloe", "Birthday Set", "Sakamata Chloe Birthday 2024 Complete Merch Set", "Birthday", "high", 75),
        ("Hololive", "Sakamata Chloe", "Tapestry", "Sakamata Chloe 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 32),
        ("Hololive", "Sakamata Chloe", "Signed Tapestry", "Sakamata Chloe Hand-Signed Birthday B2 Tapestry", "Birthday", "grail", 180),
        ("Hololive", "Kazama Iroha", "Birthday Set", "Kazama Iroha Birthday 2024 Premium Set", "Birthday", "high", 70),
        ("Hololive", "Kazama Iroha", "Acrylic Stand", "Kazama Iroha Samurai Outfit Acrylic Stand", "Outfit Reveal", "mid", 25),
        ("Hololive", "Kazama Iroha", "Tapestry", "Kazama Iroha 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("Hololive", "Hakui Koyori", "Birthday Set", "Hakui Koyori Birthday 2024 Complete Set", "Birthday", "high", 68),
        ("Hololive", "Hakui Koyori", "Tapestry", "Hakui Koyori 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 28),
        ("Hololive", "Hakui Koyori", "Signed Tapestry", "Hakui Koyori Hand-Signed Birthday B2 Tapestry", "Birthday", "grail", 170),
        ("Hololive", "Laplus Darkness", "Birthday Set", "Laplus Darkness Birthday 2024 Premium Set", "Birthday", "high", 75),
        ("Hololive", "Laplus Darkness", "Tapestry", "Laplus Darkness 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Hololive", "Laplus Darkness", "Signed Tapestry", "Laplus Darkness Hand-Signed Birthday B2 Tapestry", "Birthday", "grail", 195),

        # ── Nijisanji EN Wave Merch — Luxiem, Noctyx, XSOLEIL, TTT ──
        ("Nijisanji", "Vox Akuma", "Birthday Set", "Vox Akuma Birthday 2024 Premium Complete Set", "Birthday", "high", 85),
        ("Nijisanji", "Vox Akuma", "Signed Shikishi", "Vox Akuma Hand-Signed Birthday Shikishi Board", "Birthday", "grail", 200),
        ("Nijisanji", "Ike Eveland", "Tapestry", "Ike Eveland 2nd Anniversary B2 Tapestry", "Anniversary", "mid", 30),
        ("Nijisanji", "Fulgur Ovid", "Birthday Set", "Fulgur Ovid Birthday 2024 Merch Set", "Birthday", "high", 55),
        ("Nijisanji", "Sonny Brisko", "Birthday Set", "Sonny Brisko Birthday 2024 Complete Set", "Birthday", "high", 60),
        ("Nijisanji", "Kotoka Torahime", "Birthday Set", "Kotoka Torahime Birthday 2024 Set", "Birthday", "mid", 48),
        ("Nijisanji", "Ver Vermillion", "Acrylic Stand", "Ver Vermillion 2nd Anniversary Acrylic Stand", "Anniversary", "mid", 24),
        ("Nijisanji", "Hex Haywire", "Birthday Set", "Hex Haywire Birthday 2024 Merch Set", "Birthday", "mid", 45),
        ("Nijisanji", "Victoria Brightshield", "Debut Set", "Victoria Brightshield Debut Celebration Merch Set", "Debut", "mid", 38),
        ("Nijisanji", "Claude Clawmark", "Debut Set", "Claude Clawmark Debut Celebration Merch Set", "Debut", "mid", 38),

        # ── VShojo Official Merch — Ironmouse, Silvervale, Kson, Henya ──
        ("VShojo", "Ironmouse", "Anniversary Set", "Ironmouse 5th Anniversary Premium Complete Set", "Anniversary", "high", 90),
        ("VShojo", "Ironmouse", "Signed Tapestry", "Ironmouse Hand-Signed B2 Tapestry (100 pcs)", "Anniversary", "grail", 220),
        ("VShojo", "Ironmouse", "Nendoroid", "Nendoroid Ironmouse #2300", "Standard", "high", 55),
        ("VShojo", "Silvervale", "Birthday Set", "Silvervale Birthday 2024 Complete Merch Set", "Birthday", "high", 65),
        ("VShojo", "Silvervale", "Acrylic Stand", "Silvervale New Outfit Acrylic Stand", "Outfit Reveal", "mid", 22),
        ("VShojo", "Henya the Genius", "Birthday Set", "Henya the Genius Birthday 2024 Set", "Birthday", "mid", 48),
        ("VShojo", "Henya the Genius", "Acrylic Stand", "Henya the Genius 1st VShojo Anniversary Stand", "Anniversary", "mid", 22),
        ("VShojo", "Kson", "Birthday Set", "Kson Birthday 2024 Premium Merch Set", "Birthday", "high", 60),
        ("VShojo", "Matara Kan", "Debut Set", "Matara Kan VShojo Debut Celebration Set", "Debut", "mid", 42),

        # ── Hololive EXPO 2024 Goods ──
        ("Hololive", "Various", "EXPO Goods", "Hololive EXPO 2024 Venue-Limited Acrylic Keychain Set (20pc)", "Concert", "high", 75),
        ("Hololive", "Various", "EXPO Goods", "Hololive EXPO 2024 Stage Photo Collection (Full Set)", "Concert", "mid", 45),
        ("Hololive", "Various", "EXPO Goods", "Hololive EXPO 2024 Venue-Limited T-Shirt (Staff Ver.)", "Concert", "mid", 40),
        ("Hololive", "Various", "EXPO Goods", "Hololive EXPO 2024 Premium Ticket Holder + Lanyard", "Concert", "mid", 35),
        ("Hololive", "Various", "EXPO Goods", "Hololive EXPO 2024 Rubber Stamp Collection Full Set", "Concert", "mid", 30),

        # ── Birthday/Anniversary Limited Signed Tapestries ──
        ("Hololive", "Gawr Gura", "Signed Tapestry", "Gawr Gura Hand-Signed 3rd Anniversary B2 Tapestry", "Anniversary", "grail", 350),
        ("Hololive", "Hoshimachi Suisei", "Signed Tapestry", "Hoshimachi Suisei Hand-Signed Birthday B2 Tapestry", "Birthday", "grail", 280),
        ("Hololive", "Usada Pekora", "Signed Tapestry", "Usada Pekora Hand-Signed Birthday B2 Tapestry", "Birthday", "grail", 300),
        ("Hololive", "Houshou Marine", "Signed Tapestry", "Houshou Marine Hand-Signed 4th Anniversary B2 Tapestry", "Anniversary", "grail", 320),
        ("Nijisanji", "Kanae", "Signed Tapestry", "Kanae Hand-Signed 5th Anniversary B2 Tapestry", "Anniversary", "grail", 250),
        ("Nijisanji", "Kuzuha", "Signed Tapestry", "Kuzuha Hand-Signed Birthday B2 Tapestry", "Birthday", "grail", 270),

        # ── Hololive EXPO 2024 — Additional venue goods ──
        ("Hololive", "Various", "EXPO Goods", "Hololive EXPO 2024 Venue-Limited Poster Set (A2 x5)", "Concert", "high", 60),
        ("Hololive", "Various", "EXPO Goods", "Hololive EXPO 2024 Clear File Complete Set (20pc)", "Concert", "mid", 38),
        ("Hololive", "Various", "EXPO Goods", "Hololive EXPO 2024 Trading Card Booster Box", "Concert", "mid", 42),
        ("Nijisanji", "Various", "EXPO Goods", "Nijisanji EXPO 2024 Venue-Limited Acrylic Diorama Set", "Concert", "high", 68),
    ]


def item_to_catalog_item(item: dict) -> CatalogItem:
    agency = item["agency"]
    talent = item["talent"]
    name = item["name"]
    item_type = item["item_type"]
    exclusive_type = item["exclusive_type"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{agency}-{name}"),
        title=name,
        set_code=slugify(f"{agency}-{talent}"),
        brand=agency,
        rarity=item["rarity_tier"].title(),
        notes=f"{agency} | {talent} | {item_type}" + (f" | {exclusive_type}" if exclusive_type else ""),
        attributes_json={
            "agency": agency,
            "talent": talent,
            "item_type": item_type,
            "exclusive_type": exclusive_type,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    exclusive_type = item["exclusive_type"]
    edition_scores = {
        "Birthday": 0.70,
        "Anniversary": 0.75,
        "Concert": 0.80,
        "Solo Concert": 0.85,
        "Lawson Collab": 0.75,
        "Outfit Reveal": 0.65,
        "Album Release": 0.60,
        "Seasonal": 0.50,
        "Generation": 0.55,
        "Group": 0.60,
        "Debut": 0.70,
        "Animate Collab": 0.70,
        "Tower Records Collab": 0.70,
        "Collab Cafe": 0.65,
        "Standard": 0.30,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(exclusive_type, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import VTuber merch catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== VTuber Merch Import ===")

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

    logger.info(f"\n=== VTuber Merch Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
