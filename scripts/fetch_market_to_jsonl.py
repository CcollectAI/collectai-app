#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone

from app.providers.registry import providers_for_category

# Very simple sampler per category; extend with your own catalog/items
SAMPLES = {
    "mtg": [
        {
            "name": "Atraxa",
            "set": "mom",
            "finish": "foil",
            "rarity": "mythic",
            "condition": "nm",
        }
    ],
    "lorcana": [
        {
            "name": "Mickey",
            "set": "rise",
            "finish": "foil",
            "rarity": "legendary",
            "condition": "nm",
        }
    ],
    "fab": [
        {
            "name": "Arcanite Skullcap",
            "set": "evr",
            "finish": "foil",
            "rarity": "legendary",
            "condition": "nm",
        }
    ],
    "warhammer": [
        {"title": "Space Marines Intercessors", "sealed": True, "status": "oop"}
    ],
    "gunpla": [{"title": "RX-78-2", "grade": "pg", "sealed": True}],
    "designer_toys": [{"title": "BE@RBRICK 400%", "limited": True, "box": True}],
}


def emit_rows(cat: str, hits):
    # Convert market hits into training rows (y_price = observed market price)
    rows = []
    for h in hits:
        if "price" not in h:
            continue
        rows.append(
            {
                "category": cat,
                "y": float(h["price"]),
                "features": h.get("attrs", {}),
                "source": h.get("source"),
            }
        )
    return rows


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "data/training/training.jsonl"
    cats = ["mtg", "lorcana", "fab", "warhammer", "gunpla", "designer_toys"]
    with open(out, "a") as f:
        for cat in cats:
            payloads = SAMPLES.get(cat, [{}])
            for p in payloads:
                hits = []
                for prov in providers_for_category(cat):
                    hits.extend(prov.search(p))
                for row in emit_rows(cat, hits):
                    f.write(json.dumps(row) + "\n")
    print(f"[ok] appended rows into {out} at {datetime.now(timezone.utc).isoformat()}Z")


if __name__ == "__main__":
    main()
