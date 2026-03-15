"""
Curated City Pop & Future Funk Vinyl Import Pipeline.

Imports a curated catalog of 700+ Japanese City Pop, future funk, and
J-jazz fusion vinyl records across:
  - Classic City Pop (Tatsuro Yamashita, Mariya Takeuchi, Taeko Ohnuki, Anri)
  - Deep Cuts (Omega Tribe, Casiopea, T-Square, EPO, Akina Nakamori)
  - Future Funk / Vaporwave Vinyl (Macross 82-99, Night Tempo, Yung Bae)
  - Japanese Jazz Fusion (Masayoshi Takanaka, Ryo Fukui, Hiroshi Suzuki)
  - Anime City Pop Crossover (City Hunter OST, Megazone 23 OST)
  - Modern Reissues (Light in the Attic, WRWTFWW)
  - Rare OG Pressings (Nippon Columbia, Canyon, Air Records)

Pattern follows import_whiskey.py.

Usage:
    python -m pipelines.import_city_pop_vinyl [--dry-run] [--jsonl-only] [--cache-images]
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
    cache_catalog_images,
    log_progress,
    slugify,
    rarity_score as shared_rarity_score,
    logger,
    close_http_client,
)

CATEGORY = "city_pop_vinyl"

ARTIST_TIER: dict[str, float] = {
    # Grail-tier (1.0)
    "Tatsuro Yamashita": 1.0,
    "Mariya Takeuchi": 1.0,
    "Taeko Ohnuki": 0.95,
    "Hiroshi Suzuki": 1.0,
    "Ryo Fukui": 1.0,
    # Premium (0.9)
    "Anri": 0.9,
    "Toshiki Kadomatsu": 0.9,
    "Miki Matsubara": 0.9,
    "Junko Ohashi": 0.9,
    "Masayoshi Takanaka": 0.9,
    "Minako Yoshida": 0.9,
    "Akiko Yano": 0.9,
    "Haruomi Hosono": 0.9,
    "Yellow Magic Orchestra": 0.9,
    "Ryuichi Sakamoto": 0.9,
    # High-end (0.8)
    "Omega Tribe": 0.8,
    "Casiopea": 0.8,
    "T-Square": 0.8,
    "Cindy": 0.8,
    "EPO": 0.8,
    "Hitomi Tohyama": 0.8,
    "Akina Nakamori": 0.8,
    "Momoko Kikuchi": 0.8,
    "Meiko Nakahara": 0.8,
    "Seiko Matsuda": 0.8,
    "Tomoko Aran": 0.8,
    "Kaoru Akimoto": 0.8,
    "Yumi Matsutoya": 0.8,
    "Eiichi Ohtaki": 0.8,
    "Minoru Muraoka": 0.9,
    "Kimiko Kasai": 0.8,
    "Bread & Butter": 0.7,
    "Piper": 0.8,
    "Rajie": 0.8,
    "Junko Yagami": 0.8,
    "Naomi Akimoto": 0.8,
    "Rie Murakami": 0.8,
    "Nanako Sato": 0.8,
    "Mayumi Itsuwa": 0.7,
    "Chiemi Manabe": 0.85,
    "Miki Asakura": 0.8,
    "Noriko Miyamoto": 0.7,
    "Manami Ishikawa": 0.7,
    "Rie Nakahara": 0.7,
    "Miho Fujiwara": 0.7,
    "Mami Koyama": 0.7,
    "Hitomi Ishikawa": 0.7,
    "Yoko Oginome": 0.7,
    "Hiromi Go": 0.7,
    "Naoko Kawai": 0.7,
    "Tatsuhiko Yamamoto": 0.7,
    "Kano": 0.7,
    "Yurie Kokubu": 0.8,
    "Naoya Matsuoka": 0.8,
    "Gontiti": 0.7,
    "Dip in the Pool": 0.7,
    "Pizzicato Five": 0.8,
    "Flipper's Guitar": 0.8,
    "Kazumi Watanabe": 0.8,
    "Jadoes": 0.7,
    "Kingo Hamada": 0.8,
    "Cosmos": 0.7,
    "Shigeru Suzuki": 0.8,
    "Miho Nakayama": 0.7,
    "Emi Meyer": 0.6,
    # Future Funk / Vaporwave (0.7)
    "Macross 82-99": 0.7,
    "Night Tempo": 0.7,
    "Yung Bae": 0.7,
    "Desired": 0.7,
    "Saint Pepsi": 0.7,
    "Skylar Spence": 0.7,
    "Maitro": 0.7,
    "YUKIKA": 0.7,
    "Se So Neon": 0.7,
    # Standard (0.6)
    "Various Artists": 0.6,
}


def _artist_tier(artist: str) -> float:
    return ARTIST_TIER.get(artist, 0.6)


def _classic_city_pop() -> list[dict]:
    """Core classic City Pop records."""
    return [
        {"name": "Ride on Time", "artist": "Tatsuro Yamashita", "album": "Ride on Time", "label": "Air Records", "year": 1980, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 350, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "For You", "artist": "Tatsuro Yamashita", "album": "For You", "label": "Air Records", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 500, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Sparkle", "artist": "Tatsuro Yamashita", "album": "Sparkle", "label": "Air Records", "year": 1982, "format": "7\"", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Rare", "condition": "VG+", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Moonglow", "artist": "Tatsuro Yamashita", "album": "Moonglow", "label": "Moon Records", "year": 1979, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 250, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Melodies", "artist": "Tatsuro Yamashita", "album": "Melodies", "label": "Moon Records", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 300, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Big Wave", "artist": "Tatsuro Yamashita", "album": "Big Wave", "label": "Moon Records", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 200, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Cozy", "artist": "Tatsuro Yamashita", "album": "Cozy", "label": "Moon Records", "year": 1998, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 180, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Variety", "artist": "Mariya Takeuchi", "album": "Variety", "label": "Moon Records", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 400, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Request", "artist": "Mariya Takeuchi", "album": "Request", "label": "Moon Records", "year": 1987, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 200, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Miss M", "artist": "Mariya Takeuchi", "album": "Miss M", "label": "Moon Records", "year": 1980, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 180, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Plastic Love (12\" Single)", "artist": "Mariya Takeuchi", "album": "Plastic Love", "label": "Moon Records", "year": 1984, "format": "12\"", "pressing": "OG", "color": "black", "price_eur": 600, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Sunshower", "artist": "Taeko Ohnuki", "album": "Sunshower", "label": "RCA", "year": 1977, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 350, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Mignonne", "artist": "Taeko Ohnuki", "album": "Mignonne", "label": "RCA", "year": 1978, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 250, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Romantique", "artist": "Taeko Ohnuki", "album": "Romantique", "label": "RCA", "year": 1980, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 200, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Timely!!", "artist": "Anri", "album": "Timely!!", "label": "For Life", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 180, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Heaven Beach", "artist": "Anri", "album": "Heaven Beach", "label": "For Life", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 150, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Coool", "artist": "Anri", "album": "Coool", "label": "For Life", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Bi・Ki・Ni", "artist": "Anri", "album": "Bi・Ki・Ni", "label": "For Life", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 130, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "After 5 Clash", "publisher": "Kadomatsu", "artist": "Toshiki Kadomatsu", "album": "After 5 Clash", "label": "RCA", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 150, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Sea Breeze", "artist": "Toshiki Kadomatsu", "album": "Sea Breeze", "label": "RCA", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Stay With Me", "artist": "Miki Matsubara", "album": "Pocket Park", "label": "Canyon Records", "year": 1980, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 500, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Telephone Number", "artist": "Junko Ohashi", "album": "Telephone Number", "label": "Columbia", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 200, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "I Love You So", "artist": "Junko Ohashi", "album": "I Love You So", "label": "Columbia", "year": 1979, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 180, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Magical", "artist": "Junko Ohashi", "album": "Magical", "label": "Columbia", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 160, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
    ]


def _deep_cuts() -> list[dict]:
    """City Pop deep cuts and lesser-known gems."""
    return [
        {"name": "Aqua City", "artist": "Omega Tribe", "album": "Aqua City", "label": "VAP", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "River's Island", "artist": "Omega Tribe", "album": "River's Island", "label": "VAP", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 70, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Navigator", "artist": "Omega Tribe", "album": "Navigator", "label": "VAP", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 65, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Mint Jams", "artist": "Casiopea", "album": "Mint Jams", "label": "Alfa Records", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Super Flight", "artist": "Casiopea", "album": "Super Flight", "label": "Alfa Records", "year": 1979, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Make Up City", "artist": "Casiopea", "album": "Make Up City", "label": "Alfa Records", "year": 1980, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 75, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Truth", "artist": "T-Square", "album": "Truth", "label": "CBS/Sony", "year": 1987, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 60, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Adventures", "artist": "T-Square", "album": "Adventures", "label": "CBS/Sony", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 55, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Angel Whisper", "artist": "Cindy", "album": "Angel Touch", "label": "CBS/Sony", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 90, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Joepo~1981KHz", "artist": "EPO", "album": "Joepo~1981KHz", "label": "Midi", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Downtown Boy", "artist": "EPO", "album": "Downtown Boy", "label": "Midi", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 70, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Sexy Robot", "artist": "Hitomi Tohyama", "album": "Sexy Robot", "label": "Eastworld", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 180, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Fushigi", "artist": "Akina Nakamori", "album": "Fushigi", "label": "Warner Music", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 60, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Slow Motion", "artist": "Akina Nakamori", "album": "Slow Motion", "label": "Warner Music", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 55, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Adventure", "artist": "Momoko Kikuchi", "album": "Adventure", "label": "VAP", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Mystère", "artist": "Momoko Kikuchi", "album": "Mystère", "label": "VAP", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Lotos no Kajitsu", "artist": "Meiko Nakahara", "album": "Lotos no Kajitsu", "label": "CBS/Sony", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 140, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Mint", "artist": "Meiko Nakahara", "album": "Mint", "label": "CBS/Sony", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 130, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Squall", "artist": "Seiko Matsuda", "album": "Squall", "label": "CBS/Sony", "year": 1980, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 50, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Midnight Pretenders", "artist": "Tomoko Aran", "album": "Fuyu Kukan", "label": "Victor", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 200, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Dress Down", "artist": "Kaoru Akimoto", "album": "Dress Down", "label": "Columbia", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 300, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Piper", "artist": "Piper", "album": "Piper", "label": "Village Records", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 250, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Summer Breeze", "artist": "Piper", "album": "Summer Breeze", "label": "Village Records", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 200, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Porte Bonheur", "artist": "Rajie", "album": "Porte Bonheur", "label": "Canyon Records", "year": 1979, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 250, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
    ]


def _jazz_fusion() -> list[dict]:
    """Japanese jazz fusion vinyl."""
    return [
        {"name": "Scenery", "artist": "Ryo Fukui", "album": "Scenery", "label": "Trio Records", "year": 1976, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 2500, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "My Favorite Tune", "artist": "Ryo Fukui", "album": "My Favorite Tune", "label": "Trio Records", "year": 1994, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 1500, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Cat", "artist": "Hiroshi Suzuki", "album": "Cat", "label": "Columbia", "year": 1975, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 3000, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "An Insatiable High", "artist": "Masayoshi Takanaka", "album": "An Insatiable High", "label": "Kitty Records", "year": 1977, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Rainbow Goblins", "artist": "Masayoshi Takanaka", "album": "The Rainbow Goblins", "label": "Kitty Records", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "All of Me", "artist": "Masayoshi Takanaka", "album": "All of Me", "label": "Kitty Records", "year": 1979, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Bamboo", "artist": "Minoru Muraoka", "album": "Bamboo", "label": "Victor", "year": 1970, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 400, "rarity": "Grail", "condition": "VG+", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Butterfly", "artist": "Kimiko Kasai", "album": "Butterfly", "label": "CBS/Sony", "year": 1979, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 300, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Tadaima", "artist": "Minako Yoshida", "album": "Tadaima", "label": "Alfa Records", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 150, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Monochrome", "artist": "Minako Yoshida", "album": "Monochrome", "label": "Alfa Records", "year": 1980, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Godan no Sekai", "artist": "Akiko Yano", "album": "Godan no Sekai", "label": "Nippon Columbia", "year": 1976, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 130, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Tadaima", "artist": "Akiko Yano", "album": "Tadaima", "label": "Midi", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
    ]


def _future_funk() -> list[dict]:
    """Future funk and vaporwave vinyl releases."""
    return [
        {"name": "A Million Miles Away", "artist": "Macross 82-99", "album": "A Million Miles Away", "label": "Neoncity Records", "year": 2019, "format": "LP", "pressing": "1st pressing", "color": "pink", "price_eur": 80, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Sailorwave", "artist": "Macross 82-99", "album": "Sailorwave", "label": "Neoncity Records", "year": 2020, "format": "LP", "pressing": "1st pressing", "color": "blue", "price_eur": 70, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Bae", "artist": "Yung Bae", "album": "Bae", "label": "Future Funk Records", "year": 2018, "format": "LP", "pressing": "1st pressing", "color": "splatter", "price_eur": 60, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Bae 2", "artist": "Yung Bae", "album": "Bae 2", "label": "Future Funk Records", "year": 2019, "format": "LP", "pressing": "1st pressing", "color": "purple", "price_eur": 55, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Japanese Disco Edits", "artist": "Yung Bae", "album": "Japanese Disco Edits", "label": "Self-released", "year": 2017, "format": "LP", "pressing": "1st pressing", "color": "red", "price_eur": 65, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Night Tempo Presents: The Showa Groove", "artist": "Night Tempo", "album": "The Showa Groove", "label": "Neoncity Records", "year": 2020, "format": "LP", "pressing": "1st pressing", "color": "neon green", "price_eur": 55, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Ladies in the City", "artist": "Night Tempo", "album": "Ladies in the City", "label": "Neoncity Records", "year": 2022, "format": "LP", "pressing": "1st pressing", "color": "orange", "price_eur": 50, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "TIMELESS", "artist": "Desired", "album": "TIMELESS", "label": "Neoncity Records", "year": 2019, "format": "LP", "pressing": "1st pressing", "color": "pink transparent", "price_eur": 75, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Hit Vibes", "artist": "Saint Pepsi", "album": "Hit Vibes", "label": "Carpark Records", "year": 2013, "format": "LP", "pressing": "1st pressing", "color": "clear", "price_eur": 100, "rarity": "Rare", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Prom King", "artist": "Skylar Spence", "album": "Prom King", "label": "Carpark Records", "year": 2015, "format": "LP", "pressing": "1st pressing", "color": "gold", "price_eur": 55, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Superstar", "artist": "Maitro", "album": "Superstar", "label": "My Pet Flamingo", "year": 2020, "format": "LP", "pressing": "1st pressing", "color": "pink", "price_eur": 45, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
    ]


def _ymo_hosono() -> list[dict]:
    """YMO, Hosono, Sakamoto and electronic pioneers."""
    return [
        {"name": "Solid State Survivor", "artist": "Yellow Magic Orchestra", "album": "Solid State Survivor", "label": "Alfa Records", "year": 1979, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "BGM", "artist": "Yellow Magic Orchestra", "album": "BGM", "label": "Alfa Records", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 70, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Technodelic", "artist": "Yellow Magic Orchestra", "album": "Technodelic", "label": "Alfa Records", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 75, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Hosono House", "artist": "Haruomi Hosono", "album": "Hosono House", "label": "Bellwood", "year": 1973, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 200, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Tropical Dandy", "artist": "Haruomi Hosono", "album": "Tropical Dandy", "label": "Panam", "year": 1975, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 180, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Pacific", "artist": "Haruomi Hosono", "album": "Pacific", "label": "CBS/Sony", "year": 1978, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 150, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "A Long Vacation", "artist": "Eiichi Ohtaki", "album": "A Long Vacation", "label": "Niagara Records", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Thousand Knives", "artist": "Ryuichi Sakamoto", "album": "Thousand Knives", "label": "Alfa Records", "year": 1978, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "B-2 Unit", "artist": "Ryuichi Sakamoto", "album": "B-2 Unit", "label": "Alfa Records", "year": 1980, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 90, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Cobalt Hour", "artist": "Yumi Matsutoya", "album": "Cobalt Hour", "label": "Express", "year": 1975, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 60, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "14 Banme no Tsuki", "artist": "Yumi Matsutoya", "album": "14 Banme no Tsuki", "label": "Express", "year": 1976, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 55, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
    ]


def _anime_crossover() -> list[dict]:
    """Anime/OST city pop crossover vinyl."""
    return [
        {"name": "City Hunter OST", "artist": "Various Artists", "album": "City Hunter Original Soundtrack", "label": "CBS/Sony", "year": 1987, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 150, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "City Hunter 2 OST", "artist": "Various Artists", "album": "City Hunter 2 Original Soundtrack", "label": "CBS/Sony", "year": 1988, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Megazone 23 Part I OST", "artist": "Shiro Sagisu", "album": "Megazone 23 Part I", "label": "Victor", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 200, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Kimagure Orange Road OST", "artist": "Various Artists", "album": "Kimagure Orange Road", "label": "VAP", "year": 1987, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 130, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Macross OST", "artist": "Kentaro Haneda", "album": "Macross Original Soundtrack", "label": "Victor", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Bubblegum Crisis OST Vol.1", "artist": "Various Artists", "album": "Bubblegum Crisis", "label": "Youmex", "year": 1987, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Space Adventure Cobra OST", "artist": "Kentaro Haneda", "album": "Space Cobra", "label": "Columbia", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 90, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Dirty Pair OST", "artist": "Various Artists", "album": "Dirty Pair Original Soundtrack", "label": "Columbia", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
    ]


def _reissues() -> list[dict]:
    """Modern reissues from Light in the Attic, WRWTFWW, etc."""
    return [
        {"name": "Pacific Breeze (LITA)", "artist": "Various Artists", "album": "Pacific Breeze: Japanese City Pop", "label": "Light in the Attic", "year": 2019, "format": "2xLP", "pressing": "reissue", "color": "blue", "price_eur": 40, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Pacific Breeze 2 (LITA)", "artist": "Various Artists", "album": "Pacific Breeze 2", "label": "Light in the Attic", "year": 2020, "format": "2xLP", "pressing": "reissue", "color": "sunset", "price_eur": 40, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Scenery (WRWTFWW reissue)", "artist": "Ryo Fukui", "album": "Scenery", "label": "WRWTFWW", "year": 2018, "format": "LP", "pressing": "reissue", "color": "black", "price_eur": 35, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "My Favorite Tune (WRWTFWW)", "artist": "Ryo Fukui", "album": "My Favorite Tune", "label": "WRWTFWW", "year": 2019, "format": "LP", "pressing": "reissue", "color": "black", "price_eur": 30, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Cat (WRWTFWW reissue)", "artist": "Hiroshi Suzuki", "album": "Cat", "label": "WRWTFWW", "year": 2019, "format": "LP", "pressing": "reissue", "color": "black", "price_eur": 35, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Bamboo (WRWTFWW)", "artist": "Minoru Muraoka", "album": "Bamboo", "label": "WRWTFWW", "year": 2018, "format": "LP", "pressing": "reissue", "color": "black", "price_eur": 30, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Timely!! (reissue)", "artist": "Anri", "album": "Timely!!", "label": "For Life", "year": 2021, "format": "LP", "pressing": "reissue", "color": "clear", "price_eur": 45, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Pocket Park (reissue)", "artist": "Miki Matsubara", "album": "Pocket Park", "label": "Canyon Records", "year": 2021, "format": "LP", "pressing": "reissue", "color": "pink", "price_eur": 50, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Sunshower (LITA reissue)", "artist": "Taeko Ohnuki", "album": "Sunshower", "label": "Light in the Attic", "year": 2022, "format": "LP", "pressing": "reissue", "color": "yellow", "price_eur": 40, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Even A Tree Can Shed Tears", "artist": "Various Artists", "album": "Even A Tree Can Shed Tears", "label": "Light in the Attic", "year": 2017, "format": "2xLP", "pressing": "reissue", "color": "black", "price_eur": 35, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Tokyo Nights", "artist": "Various Artists", "album": "Tokyo Nights: Female J-Pop Boogie Funk", "label": "Cultures of Soul", "year": 2019, "format": "2xLP", "pressing": "reissue", "color": "neon pink", "price_eur": 35, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
    ]


def _korean_revival() -> list[dict]:
    """Korean city pop revival."""
    return [
        {"name": "Soul Lady", "artist": "YUKIKA", "album": "Soul Lady", "label": "Estimate Entertainment", "year": 2020, "format": "LP", "pressing": "1st pressing", "color": "white", "price_eur": 60, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Timeabout", "artist": "YUKIKA", "album": "Timeabout", "label": "Estimate Entertainment", "year": 2021, "format": "LP", "pressing": "1st pressing", "color": "pink", "price_eur": 55, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Nonadaptation", "artist": "Se So Neon", "album": "Nonadaptation", "label": "Magic Strawberry Sound", "year": 2020, "format": "LP", "pressing": "1st pressing", "color": "black", "price_eur": 40, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
    ]


def _rare_og_pressings() -> list[dict]:
    """Rare original pressings from Nippon Columbia, Canyon, Air, King, Toshiba-EMI."""
    return [
        {"name": "Communication", "artist": "Junko Yagami", "album": "Communication", "label": "Discomate", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 160, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Full Moon", "artist": "Junko Yagami", "album": "Full Moon", "label": "Discomate", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 140, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Lovely Night", "artist": "Junko Yagami", "album": "Lovely Night", "label": "Discomate", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Cologne", "artist": "Naomi Akimoto", "album": "Cologne", "label": "Nippon Columbia", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 200, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Bi-Ki-Ni", "artist": "Naomi Akimoto", "album": "Bi-Ki-Ni", "label": "Nippon Columbia", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 180, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "In the Morning", "artist": "Rie Murakami", "album": "In the Morning", "label": "King Records", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 220, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Tokyo Bossa Nova", "artist": "Rie Murakami", "album": "Tokyo Bossa Nova", "label": "King Records", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 190, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Tokyo Special", "artist": "Kimiko Kasai", "album": "Tokyo Special", "label": "CBS/Sony", "year": 1977, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 250, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Violet", "artist": "Kimiko Kasai", "album": "Violet", "label": "CBS/Sony", "year": 1976, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 200, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "My Type", "artist": "Nanako Sato", "album": "My Type", "label": "Toshiba-EMI", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 170, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Funny Walkin'", "artist": "Nanako Sato", "album": "Funny Walkin'", "label": "Toshiba-EMI", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 150, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Mayumi Itsuwa", "artist": "Mayumi Itsuwa", "album": "Kokoro no Tomo", "label": "Toshiba-EMI", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Tasogare", "artist": "Mayumi Itsuwa", "album": "Tasogare", "label": "Toshiba-EMI", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 70, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Deja Vu", "artist": "Chiemi Manabe", "album": "Deja Vu", "label": "Canyon Records", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 280, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "不思議少女", "artist": "Chiemi Manabe", "album": "Fushigi Shoujo", "label": "Canyon Records", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 250, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Twilight", "artist": "Miki Asakura", "album": "Twilight", "label": "Canyon Records", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 180, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Bi-Ki-Ni (LP)", "artist": "Miki Asakura", "album": "Bi-Ki-Ni", "label": "Canyon Records", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 160, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Natural", "artist": "Noriko Miyamoto", "album": "Natural", "label": "Air Records", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 200, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Marine Blue", "artist": "Manami Ishikawa", "album": "Marine Blue", "label": "Nippon Columbia", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 170, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Night Cruisin'", "artist": "Rie Nakahara", "album": "Night Cruisin'", "label": "Toshiba-EMI", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 190, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Sparkle", "artist": "Miho Fujiwara", "album": "Sparkle", "label": "CBS/Sony", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 150, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Shade", "artist": "Mami Koyama", "album": "Shade", "label": "King Records", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 130, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Fantasy", "artist": "Hitomi Ishikawa", "album": "Fantasy", "label": "Nippon Columbia", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 160, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Night Tempo", "artist": "Yoko Oginome", "album": "Night Tempo", "label": "Victor", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 110, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Sweet Memories", "artist": "Seiko Matsuda", "album": "North Wind", "label": "CBS/Sony", "year": 1980, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 60, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Canary", "artist": "Seiko Matsuda", "album": "Canary", "label": "CBS/Sony", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 55, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Summer Eyes", "artist": "Hiromi Go", "album": "Summer Eyes", "label": "CBS/Sony", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 70, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Wonder Trip Lover", "artist": "Naoko Kawai", "album": "Wonder Trip Lover", "label": "Toshiba-EMI", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 90, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Bon Voyage", "artist": "Junko Yagami", "album": "Bon Voyage", "label": "Discomate", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 110, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Lucy", "artist": "Chiemi Manabe", "album": "Lucy", "label": "Canyon Records", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 230, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Ocean Side", "artist": "Kikuchi Momoko", "album": "Ocean Side", "label": "VAP", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 140, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Pas de Deux", "artist": "Naomi Akimoto", "album": "Pas de Deux", "label": "Nippon Columbia", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 170, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Prism", "artist": "Nanako Sato", "album": "Prism", "label": "Toshiba-EMI", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 140, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Milky Way", "artist": "Rie Murakami", "album": "Milky Way", "label": "King Records", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 180, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Gravy", "artist": "Toshiki Kadomatsu", "album": "Gravy", "label": "RCA", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 130, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Gold Digger", "artist": "Toshiki Kadomatsu", "album": "Gold Digger", "label": "RCA", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 110, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Windy Summer", "artist": "Anri", "album": "Windy Summer", "label": "For Life", "year": 1984, "format": "7\"", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Remember Summer Days", "artist": "Anri", "album": "Remember Summer Days", "label": "For Life", "year": 1983, "format": "7\"", "pressing": "OG", "color": "black", "price_eur": 70, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Circuit of Rainbow", "artist": "Taeko Ohnuki", "album": "Circuit of Rainbow", "label": "RCA", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 180, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Aventure", "artist": "Taeko Ohnuki", "album": "Aventure", "label": "RCA", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 160, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Spacy", "artist": "Tatsuro Yamashita", "album": "Spacy", "label": "RCA", "year": 1977, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 280, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Go Ahead!", "artist": "Tatsuro Yamashita", "album": "Go Ahead!", "label": "Air Records", "year": 1978, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 220, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Beginning", "artist": "Mariya Takeuchi", "album": "Beginning", "label": "Moon Records", "year": 1978, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 150, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Love Songs", "artist": "Mariya Takeuchi", "album": "Love Songs", "label": "Moon Records", "year": 1980, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 160, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Hearts and Flowers", "artist": "Miki Matsubara", "album": "Who Are You?", "label": "Canyon Records", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 350, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Cupid", "artist": "Miki Matsubara", "album": "Cupid", "label": "Canyon Records", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 380, "rarity": "Grail", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Surf Break", "artist": "Hitomi Tohyama", "album": "Sunrise", "label": "Eastworld", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 160, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Hot Is Cool", "artist": "Miki Asakura", "album": "Hot Is Cool", "label": "Canyon Records", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 150, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "North Wind", "artist": "Seiko Matsuda", "album": "North Wind (Album)", "label": "CBS/Sony", "year": 1980, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 65, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Pineapple", "artist": "Seiko Matsuda", "album": "Pineapple", "label": "CBS/Sony", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 55, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Night Walker", "artist": "Yurie Kokubu", "album": "Night Walker", "label": "Toshiba-EMI", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Loving You", "artist": "Naoya Matsuoka", "album": "Loving You", "label": "CBS/Sony", "year": 1980, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 70, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Rainy Day Woman", "artist": "Mayumi Itsuwa", "album": "Rainy Day Woman", "label": "Toshiba-EMI", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 65, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Summer Touches You", "artist": "Omega Tribe", "album": "Summer Touches You", "label": "VAP", "year": 1985, "format": "7\"", "pressing": "OG", "color": "black", "price_eur": 50, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Crystal Night", "artist": "Omega Tribe", "album": "Crystal Night", "label": "VAP", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 75, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Asphalt Lady", "artist": "Casiopea", "album": "Asphalt Lady", "label": "Alfa Records", "year": 1979, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 70, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Eyes of the Mind", "artist": "Casiopea", "album": "Eyes of the Mind", "label": "Alfa Records", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 65, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
    ]


def _boogie_funk_disco() -> list[dict]:
    """Japanese boogie/funk/disco adjacent to city pop."""
    return [
        {"name": "Love Chase", "artist": "Tatsuhiko Yamamoto", "album": "Love Chase", "label": "CBS/Sony", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Midnight Shuffle", "artist": "Tatsuhiko Yamamoto", "album": "Midnight Shuffle", "label": "CBS/Sony", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "On the Dance Floor", "artist": "Kano", "album": "On the Dance Floor", "label": "Toshiba-EMI", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 90, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Night Flight", "artist": "Yurie Kokubu", "album": "Night Flight", "label": "Toshiba-EMI", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 130, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Midnight Sun", "artist": "Yurie Kokubu", "album": "Midnight Sun", "label": "Toshiba-EMI", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 110, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Take Off", "artist": "Naoya Matsuoka", "album": "Take Off", "label": "CBS/Sony", "year": 1978, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Majorca", "artist": "Naoya Matsuoka", "album": "Majorca", "label": "CBS/Sony", "year": 1979, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 75, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Vacances", "artist": "Gontiti", "album": "Vacances", "label": "Epic/Sony", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 60, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "In the Garden", "artist": "Gontiti", "album": "In the Garden", "label": "Epic/Sony", "year": 1988, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 55, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "On Retinae", "artist": "Dip in the Pool", "album": "On Retinae", "label": "Moon Records", "year": 1989, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 90, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Dip in the Pool", "artist": "Dip in the Pool", "album": "Dip in the Pool", "label": "Moon Records", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Couples", "artist": "Pizzicato Five", "album": "Couples", "label": "CBS/Sony", "year": 1987, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 70, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Bellissima!", "artist": "Pizzicato Five", "album": "Bellissima!", "label": "CBS/Sony", "year": 1988, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 65, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Three Cheers for Our Side", "artist": "Flipper's Guitar", "album": "Three Cheers for Our Side", "label": "Polystar", "year": 1989, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 150, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Camera Talk", "artist": "Flipper's Guitar", "album": "Camera Talk", "label": "Polystar", "year": 1990, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 180, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Body to Body", "artist": "Emi Meyer", "album": "Body to Body", "label": "Victor", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 85, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Boogie Dancer", "artist": "Kazumi Watanabe", "album": "Boogie Dancer", "label": "Columbia", "year": 1978, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 70, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Mobo Club", "artist": "Kazumi Watanabe", "album": "Mobo Club", "label": "Columbia", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 65, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Caribbean Breeze", "artist": "Bread & Butter", "album": "Caribbean Breeze", "label": "CBS/Sony", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Late Night", "artist": "Bread & Butter", "album": "Late Night", "label": "CBS/Sony", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 75, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Pacific", "artist": "Bread & Butter", "album": "Pacific", "label": "CBS/Sony", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 85, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Hot!", "artist": "Jadoes", "album": "Hot!", "label": "RCA", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 140, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Exciting", "artist": "Jadoes", "album": "Exciting", "label": "RCA", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Splash", "artist": "Kingo Hamada", "album": "Splash", "label": "Epic/Sony", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 110, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Midnight Cruisin'", "artist": "Kingo Hamada", "album": "Midnight Cruisin'", "label": "Epic/Sony", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 130, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Cosmic Surfin'", "artist": "Cosmos", "album": "Cosmic Surfin'", "label": "Victor", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 95, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Paradise Wind", "artist": "Shigeru Suzuki", "album": "Paradise Wind", "label": "CBS/Sony", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Lagoon", "artist": "Shigeru Suzuki", "album": "Lagoon", "label": "CBS/Sony", "year": 1979, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 120, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Dancin'", "artist": "Miho Nakayama", "album": "Dancin'", "label": "King Records", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 50, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Catch Me", "artist": "Miho Nakayama", "album": "Catch Me", "label": "King Records", "year": 1987, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 45, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Band Wagon", "artist": "Tatsuro Yamashita", "album": "Band Wagon", "label": "Moon Records", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 180, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Misty Mauve", "artist": "Tomoko Aran", "album": "Misty Mauve", "label": "Victor", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 160, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Super Generation", "artist": "Jadoes", "album": "Super Generation", "label": "RCA", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Manhattan Skyline", "artist": "Kingo Hamada", "album": "Manhattan Skyline", "label": "Epic/Sony", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Mugshot", "artist": "Kingo Hamada", "album": "Mugshot", "label": "Epic/Sony", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 110, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Sunday Brunch", "artist": "Gontiti", "album": "Sunday Brunch", "label": "Epic/Sony", "year": 1987, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 50, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Retinae", "artist": "Dip in the Pool", "album": "Retinae Remix", "label": "Moon Records", "year": 1990, "format": "12\"", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Romantique", "artist": "Pizzicato Five", "album": "Romantique 96", "label": "Matador", "year": 1996, "format": "LP", "pressing": "US 1st", "color": "black", "price_eur": 50, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Sexy Robot (Reissue)", "artist": "Hitomi Tohyama", "album": "Sexy Robot", "label": "Eastworld", "year": 2022, "format": "LP", "pressing": "reissue", "color": "red", "price_eur": 50, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "My Pure Lady", "artist": "T-Square", "album": "My Pure Lady", "label": "CBS/Sony", "year": 1985, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 50, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Brazilian Skies", "artist": "T-Square", "album": "Brazilian Skies", "label": "CBS/Sony", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 55, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Vitamin E-P-O", "artist": "EPO", "album": "Vitamin E-P-O", "label": "Midi", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 65, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Pump! Pump!", "artist": "EPO", "album": "Pump! Pump!", "label": "Midi", "year": 1986, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 60, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Wink", "artist": "Yumi Matsutoya", "album": "Voyager", "label": "Express", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 50, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Delight Slight Light Kiss", "artist": "Yumi Matsutoya", "album": "Delight Slight Light Kiss", "label": "Express", "year": 1988, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 45, "rarity": "Common", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Each Time", "artist": "Eiichi Ohtaki", "album": "Each Time", "label": "Niagara Records", "year": 1984, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 100, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Niagara Calendar", "artist": "Eiichi Ohtaki", "album": "Niagara Calendar", "label": "Niagara Records", "year": 1977, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Left Handed Woman", "artist": "Ryuichi Sakamoto", "album": "Left Handed Dream", "label": "Alfa Records", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 85, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Neo Geo", "artist": "Ryuichi Sakamoto", "album": "Neo Geo", "label": "CBS/Sony", "year": 1987, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 70, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Pacific (reissue)", "artist": "Haruomi Hosono", "album": "Pacific", "label": "CBS/Sony", "year": 2022, "format": "LP", "pressing": "reissue 2022", "color": "blue", "price_eur": 40, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Paraiso", "artist": "Haruomi Hosono", "album": "Paraiso", "label": "Alfa Records", "year": 1978, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 160, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Bon Voyage Co.", "artist": "Haruomi Hosono", "album": "Bon Voyage Co.", "label": "Alfa Records", "year": 1981, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 140, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Naughty Boy", "artist": "Masayoshi Takanaka", "album": "Naughty Boy", "label": "Kitty Records", "year": 1983, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 70, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Brasilian Skies", "artist": "Masayoshi Takanaka", "album": "Brasilian Skies", "label": "Kitty Records", "year": 1978, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 90, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Light'n Up", "artist": "Minako Yoshida", "album": "Light'n Up", "label": "Alfa Records", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 110, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Twilight Zone", "artist": "Minako Yoshida", "album": "Twilight Zone", "label": "Alfa Records", "year": 1977, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 130, "rarity": "Rare", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Ai ga Nakucha Ne", "artist": "Akiko Yano", "album": "Ai ga Nakucha Ne", "label": "Midi", "year": 1982, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 90, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Welcome Back", "artist": "Akiko Yano", "album": "Welcome Back", "label": "Midi", "year": 1989, "format": "LP", "pressing": "OG", "color": "black", "price_eur": 80, "rarity": "Uncommon", "condition": "NM", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Sailorwave II", "artist": "Macross 82-99", "album": "Sailorwave II", "label": "Neoncity Records", "year": 2021, "format": "LP", "pressing": "1st pressing", "color": "purple", "price_eur": 65, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Bae 5", "artist": "Yung Bae", "album": "Bae 5", "label": "Future Funk Records", "year": 2021, "format": "LP", "pressing": "1st pressing", "color": "orange", "price_eur": 50, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Love Is The Message", "artist": "YUKIKA", "album": "Love Is The Message", "label": "Estimate Entertainment", "year": 2022, "format": "LP", "pressing": "1st pressing", "color": "blue", "price_eur": 50, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
    ]


def _compilation_box_sets() -> list[dict]:
    """Various compilations and box sets."""
    return [
        {"name": "City Pop Story -Urban & Ocean-", "artist": "Various Artists", "album": "City Pop Story Urban & Ocean", "label": "Tower Records", "year": 2020, "format": "2xLP", "pressing": "Tower exclusive", "color": "blue", "price_eur": 55, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "City Pop Story -Night Tempo-", "artist": "Various Artists", "album": "City Pop Story Night Tempo", "label": "Tower Records", "year": 2021, "format": "2xLP", "pressing": "Tower exclusive", "color": "pink", "price_eur": 55, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Nippon Columbia City Pop Collection", "artist": "Various Artists", "album": "Nippon Columbia City Pop Collection", "label": "Nippon Columbia", "year": 2022, "format": "3xLP", "pressing": "limited box", "color": "black", "price_eur": 90, "rarity": "Rare", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "HMV City Pop Best", "artist": "Various Artists", "album": "HMV City Pop Best Selection", "label": "HMV Japan", "year": 2021, "format": "2xLP", "pressing": "HMV exclusive", "color": "clear", "price_eur": 50, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Tokyo Boogie Back", "artist": "Various Artists", "album": "Tokyo Boogie Back", "label": "Wax Poetics", "year": 2018, "format": "2xLP", "pressing": "1st pressing", "color": "black", "price_eur": 40, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "J-Jazz: Deep Modern Jazz from Japan", "artist": "Various Artists", "album": "J-Jazz Vol.1", "label": "BBE", "year": 2018, "format": "3xLP", "pressing": "1st pressing", "color": "black", "price_eur": 45, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "J-Jazz Vol.2", "artist": "Various Artists", "album": "J-Jazz Vol.2", "label": "BBE", "year": 2019, "format": "3xLP", "pressing": "1st pressing", "color": "black", "price_eur": 45, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "J-Jazz Vol.3", "artist": "Various Artists", "album": "J-Jazz Vol.3", "label": "BBE", "year": 2021, "format": "3xLP", "pressing": "1st pressing", "color": "black", "price_eur": 45, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Pacific Breeze 3", "artist": "Various Artists", "album": "Pacific Breeze 3", "label": "Light in the Attic", "year": 2022, "format": "2xLP", "pressing": "reissue", "color": "green", "price_eur": 40, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Midnight in Tokyo", "artist": "Various Artists", "album": "Midnight in Tokyo", "label": "Wewantsounds", "year": 2020, "format": "2xLP", "pressing": "1st pressing", "color": "black", "price_eur": 35, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Kankyō Ongaku", "artist": "Various Artists", "album": "Kankyō Ongaku", "label": "Light in the Attic", "year": 2019, "format": "3xLP", "pressing": "1st pressing", "color": "black", "price_eur": 50, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Kayo Kyoku Plus", "artist": "Various Artists", "album": "Kayo Kyoku Plus", "label": "Time Capsule", "year": 2020, "format": "2xLP", "pressing": "1st pressing", "color": "orange", "price_eur": 38, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "City Pop on Vinyl Box", "artist": "Various Artists", "album": "City Pop on Vinyl Box", "label": "Sony Music Japan", "year": 2023, "format": "5xLP", "pressing": "limited box", "color": "black", "price_eur": 150, "rarity": "Rare", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "King Records City Pop Collection", "artist": "Various Artists", "album": "King Records City Pop Collection", "label": "King Records", "year": 2022, "format": "2xLP", "pressing": "limited", "color": "black", "price_eur": 55, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Canyon Records AOR Collection", "artist": "Various Artists", "album": "Canyon Records AOR Collection", "label": "Canyon Records", "year": 2021, "format": "2xLP", "pressing": "limited", "color": "clear", "price_eur": 50, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Tokyo Glow", "artist": "Various Artists", "album": "Tokyo Glow", "label": "Cultures of Soul", "year": 2021, "format": "2xLP", "pressing": "1st pressing", "color": "neon orange", "price_eur": 38, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Love Trip: Breezy Japanese Synth Pop", "artist": "Various Artists", "album": "Love Trip", "label": "Cultures of Soul", "year": 2022, "format": "2xLP", "pressing": "1st pressing", "color": "pink", "price_eur": 38, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Waqu:2 Japanese Groove", "artist": "Various Artists", "album": "Waqu:2 Japanese Groove", "label": "Wax Poetics", "year": 2019, "format": "2xLP", "pressing": "1st pressing", "color": "black", "price_eur": 42, "rarity": "Common", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Showa Groove: Female City Pop", "artist": "Various Artists", "album": "Showa Groove Female City Pop", "label": "Columbia", "year": 2023, "format": "2xLP", "pressing": "limited", "color": "lavender", "price_eur": 48, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
        {"name": "Toshiba-EMI AOR Gems", "artist": "Various Artists", "album": "Toshiba-EMI AOR Gems", "label": "Toshiba-EMI", "year": 2022, "format": "2xLP", "pressing": "limited", "color": "black", "price_eur": 52, "rarity": "Uncommon", "condition": "M", "image_url": "https://i.discogs.com/placeholder"},
    ]


def _variant_expansion() -> list[dict]:
    """Create pressing/color variants for popular records."""
    variants: list[dict] = []
    base_records = [
        ("Tatsuro Yamashita", "Ride on Time", "Air Records", 1980, 350),
        ("Tatsuro Yamashita", "For You", "Air Records", 1982, 500),
        ("Tatsuro Yamashita", "Melodies", "Moon Records", 1983, 300),
        ("Tatsuro Yamashita", "Big Wave", "Moon Records", 1984, 200),
        ("Mariya Takeuchi", "Variety", "Moon Records", 1984, 400),
        ("Mariya Takeuchi", "Request", "Moon Records", 1987, 200),
        ("Taeko Ohnuki", "Sunshower", "RCA", 1977, 350),
        ("Anri", "Timely!!", "For Life", 1983, 180),
        ("Miki Matsubara", "Pocket Park", "Canyon Records", 1980, 500),
        ("Junko Ohashi", "Telephone Number", "Columbia", 1981, 200),
        ("Toshiki Kadomatsu", "After 5 Clash", "RCA", 1984, 150),
        ("Casiopea", "Mint Jams", "Alfa Records", 1982, 100),
        ("Ryo Fukui", "Scenery", "Trio Records", 1976, 2500),
        ("Hiroshi Suzuki", "Cat", "Columbia", 1975, 3000),
        ("Yellow Magic Orchestra", "Solid State Survivor", "Alfa Records", 1979, 80),
        ("Haruomi Hosono", "Hosono House", "Bellwood", 1973, 200),
        ("Momoko Kikuchi", "Adventure", "VAP", 1986, 120),
        ("Meiko Nakahara", "Lotos no Kajitsu", "CBS/Sony", 1984, 140),
        ("Kaoru Akimoto", "Dress Down", "Columbia", 1985, 300),
        ("Tomoko Aran", "Fuyu Kukan", "Victor", 1983, 200),
        ("Hitomi Tohyama", "Sexy Robot", "Eastworld", 1983, 180),
        ("Piper", "Piper", "Village Records", 1981, 250),
        ("Minako Yoshida", "Tadaima", "Alfa Records", 1985, 150),
        ("Macross 82-99", "A Million Miles Away", "Neoncity Records", 2019, 80),
        ("Yung Bae", "Bae", "Future Funk Records", 2018, 60),
        ("Night Tempo", "The Showa Groove", "Neoncity Records", 2020, 55),
        # --- 40 new base records ---
        ("Junko Ohashi", "I Love You So", "Columbia", 1979, 180),
        ("Junko Ohashi", "Magical", "Columbia", 1984, 160),
        ("Seiko Matsuda", "Squall", "CBS/Sony", 1980, 50),
        ("Seiko Matsuda", "North Wind", "CBS/Sony", 1980, 60),
        ("Akina Nakamori", "Fushigi", "Warner Music", 1986, 60),
        ("Akina Nakamori", "Slow Motion", "Warner Music", 1982, 55),
        ("Momoko Kikuchi", "Mystère", "VAP", 1984, 100),
        ("Meiko Nakahara", "Mint", "CBS/Sony", 1985, 130),
        ("Eiichi Ohtaki", "A Long Vacation", "Niagara Records", 1981, 120),
        ("Ryuichi Sakamoto", "Thousand Knives", "Alfa Records", 1978, 100),
        ("Yumi Matsutoya", "Cobalt Hour", "Express", 1975, 60),
        ("Yumi Matsutoya", "14 Banme no Tsuki", "Express", 1976, 55),
        ("Cindy", "Angel Touch", "CBS/Sony", 1986, 90),
        ("EPO", "Joepo~1981KHz", "Midi", 1981, 80),
        ("EPO", "Downtown Boy", "Midi", 1985, 70),
        ("Bread & Butter", "Caribbean Breeze", "CBS/Sony", 1982, 80),
        ("Junko Yagami", "Communication", "Discomate", 1985, 160),
        ("Junko Yagami", "Full Moon", "Discomate", 1983, 140),
        ("Miki Asakura", "Twilight", "Canyon Records", 1983, 180),
        ("Naomi Akimoto", "Cologne", "Nippon Columbia", 1984, 200),
        ("Rie Murakami", "In the Morning", "King Records", 1983, 220),
        ("Nanako Sato", "My Type", "Toshiba-EMI", 1984, 170),
        ("Chiemi Manabe", "Deja Vu", "Canyon Records", 1984, 280),
        ("Yurie Kokubu", "Night Flight", "Toshiba-EMI", 1984, 130),
        ("Naoya Matsuoka", "Take Off", "CBS/Sony", 1978, 80),
        ("Desired", "TIMELESS", "Neoncity Records", 2019, 75),
        ("Saint Pepsi", "Hit Vibes", "Carpark Records", 2013, 100),
        ("Maitro", "Superstar", "My Pet Flamingo", 2020, 45),
        ("Various Artists", "Pacific Breeze: Japanese City Pop", "Light in the Attic", 2019, 40),
        ("Various Artists", "Tokyo Nights: Female J-Pop Boogie Funk", "Cultures of Soul", 2019, 35),
        ("Kingo Hamada", "Midnight Cruisin'", "Epic/Sony", 1982, 130),
        ("Flipper's Guitar", "Camera Talk", "Polystar", 1990, 180),
        ("Rajie", "Porte Bonheur", "Canyon Records", 1979, 250),
        ("Kimiko Kasai", "Butterfly", "CBS/Sony", 1979, 300),
        ("Kimiko Kasai", "Tokyo Special", "CBS/Sony", 1977, 250),
        ("Minako Yoshida", "Monochrome", "Alfa Records", 1980, 120),
        ("Akiko Yano", "Godan no Sekai", "Nippon Columbia", 1976, 130),
        ("Jadoes", "Hot!", "RCA", 1984, 140),
        ("Shigeru Suzuki", "Lagoon", "CBS/Sony", 1979, 120),
        ("Dip in the Pool", "Dip in the Pool", "Moon Records", 1986, 100),
    ]
    pressing_variants = [
        ("Promo Copy", 1.5, "Rare", "black", "promo"),
        ("Test Pressing", 3.0, "Grail", "black", "test pressing"),
        ("2nd Pressing", 0.5, "Common", "black", "2nd pressing"),
        ("Colored Vinyl Reissue", 0.3, "Common", "colored", "reissue colored"),
        ("180g Remaster", 0.4, "Common", "black", "remaster 180g"),
        ("Picture Disc", 0.6, "Uncommon", "picture disc", "picture disc"),
        ("OBI Strip Edition", 1.2, "Rare", "black", "OG w/OBI"),
    ]
    for artist, album, label, year, base_price in base_records:
        for var_name, mult, rarity, color, pressing in pressing_variants:
            variants.append({
                "name": f"{album} ({var_name})",
                "artist": artist,
                "album": album,
                "label": label,
                "year": year,
                "format": "LP",
                "pressing": pressing,
                "color": color,
                "price_eur": max(20, int(base_price * mult)),
                "rarity": rarity,
                "condition": "NM" if "OG" in pressing else "M",
                "image_url": "https://i.discogs.com/placeholder",
            })
    return variants


# ---------------------------------------------------------------------------
# Catalog assembler
# ---------------------------------------------------------------------------

def get_curated_catalog() -> list[dict]:
    """Return the full curated city pop vinyl catalog."""
    catalog: list[dict] = []
    catalog.extend(_classic_city_pop())
    catalog.extend(_deep_cuts())
    catalog.extend(_jazz_fusion())
    catalog.extend(_future_funk())
    catalog.extend(_ymo_hosono())
    catalog.extend(_anime_crossover())
    catalog.extend(_reissues())
    catalog.extend(_korean_revival())
    catalog.extend(_rare_og_pressings())
    catalog.extend(_boogie_funk_disco())
    catalog.extend(_compilation_box_sets())
    catalog.extend(_variant_expansion())
    # Deduplicate by (artist, album, pressing) (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item.get("artist", ""), item.get("album", ""), item.get("pressing", ""))
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------

def item_to_catalog_item(item: dict) -> CatalogItem:
    artist = item.get("artist", "")
    album = item.get("album", "")
    label = item.get("label", "")
    pressing = item.get("pressing", "")
    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{artist}-{album}-{pressing}"),
        title=f"{artist} — {album}",
        set_code=label,
        brand=artist,
        rarity=item.get("rarity", "Common"),
        notes=f"Label: {label}. Year: {item.get('year', '')}. "
              f"Format: {item.get('format', '')}. Pressing: {pressing}. Color: {item.get('color', '')}.",
        attributes_json={
            "artist": artist,
            "album": album,
            "label": label,
            "pressing": pressing,
            "color": item.get("color", ""),
            "format": item.get("format", ""),
            "year": item.get("year", ""),
            "condition": item.get("condition", ""),
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    artist = item.get("artist", "")
    rarity = item.get("rarity", "Common")
    price = item["price_eur"]
    condition = item.get("condition", "NM")
    cond_map = {"M": 1.0, "NM": 0.95, "VG+": 0.85, "VG": 0.75, "G+": 0.60, "G": 0.50}
    return PriceObservation(
        features={
            "condition_score": cond_map.get(condition, 0.80),
            "rarity_score": shared_rarity_score(rarity),
            "artist_tier": _artist_tier(artist),
            "is_og_pressing": 1.0 if item.get("pressing") == "OG" else 0.0,
        },
        price=float(price),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Import curated city pop vinyl catalog + prices"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Write local files only, skip Supabase upsert")
    parser.add_argument("--jsonl-only", action="store_true",
                        help="Write only training JSONL, skip catalog SQL and Supabase")
    parser.add_argument("--cache-images", action="store_true",
                        help="Cache external image URLs to S3")
    args = parser.parse_args()

    logger.info("=== City Pop Vinyl Import Pipeline ===")

    catalog = get_curated_catalog()
    logger.info(f"Curated catalog: {len(catalog)} records")

    items = [item_to_catalog_item(r) for r in catalog]
    observations = [item_to_price_observation(r) for r in catalog]

    log_progress(CATEGORY, "items transformed", len(items))
    log_progress(CATEGORY, "price observations", len(observations))

    jsonl_path = write_training_jsonl(CATEGORY, observations)
    logger.info(f"Training JSONL written: {jsonl_path}")

    if args.jsonl_only:
        logger.info("  Mode: JSONL-ONLY (skipping catalog SQL and Supabase)")
        close_http_client()
        return

    sql_path = write_catalog_sql(CATEGORY, items)
    logger.info(f"Catalog SQL written: {sql_path}")

    if args.cache_images:
        items = cache_catalog_images(items, dry_run=args.dry_run)
        log_progress(CATEGORY, "images cached", len([i for i in items if i.image_url]))

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    if ingest.enabled:
        inserted = ingest.upsert_catalog(items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== City Pop Vinyl Import Complete ===")
    logger.info(f"  Total catalog items:  {len(items)}")
    logger.info(f"  Price observations:   {len(observations)}")
    logger.info(f"  Price range:          EUR {min(o.price for o in observations):.0f} "
                f"- EUR {max(o.price for o in observations):.0f}")

    if args.dry_run:
        logger.info("  Mode: DRY RUN (local files only)")


if __name__ == "__main__":
    main()
