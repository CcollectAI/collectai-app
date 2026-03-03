"""
Import Funko Pop data.

Layer 1 (Catalog):  Curated high-value Funko Pops → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

No official Funko API exists. Data sourced from:
- Curated grail lists (conventions, vaulted, chase variants)
- HobbyDB / Pop Price Guide structure
- Can be augmented with web scraping later

Usage:
    python -m pipelines.import_funko [--dry-run]
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

CATEGORY = "funko"


def get_curated_catalog() -> list[dict]:
    """Curated Funko Pop catalog covering 550+ items across major lines and grails."""

    # Format: (line, number, name, exclusive, rarity_tier, est_price_eur)
    # rarity_tier: grail (>500), high (100-500), mid (30-100), standard (<30)

    pops = [
        # ── DC Comics (6) ─────────────────────────────────────────────
        ("DC Heroes", "01", "Batman (Metallic Blue)", "SDCC 2010", "grail", 12000),
        ("DC Heroes", "01", "Batman", "", "standard", 15),
        ("DC Heroes", "02", "Superman", "", "standard", 12),
        ("DC Heroes", "06", "Green Lantern (Previews)", "NYCC 2012", "grail", 3500),
        ("DC Heroes", "52", "Batgirl", "", "standard", 10),
        ("DC Heroes", "13", "Harley Quinn", "", "mid", 45),

        # ── Marvel (18) ───────────────────────────────────────────────
        ("Marvel", "01", "Spider-Man", "", "mid", 60),
        ("Marvel", "02", "Iron Man", "", "standard", 20),
        ("Marvel", "03", "Hulk", "", "standard", 18),
        ("Marvel", "04", "Thor", "", "mid", 35),
        ("Marvel", "07", "Captain America", "", "mid", 40),
        ("Marvel", "18", "Red Skull (Metallic)", "SDCC 2011", "grail", 2000),
        ("Marvel", "39", "Loki", "", "mid", 50),
        ("Marvel", "65", "Deadpool", "", "standard", 15),
        ("Marvel", "88", "Venom", "", "mid", 45),
        ("Marvel", "18", "Ghost Rider (Metallic)", "SDCC 2013", "grail", 800),
        ("Marvel", "05", "Wolverine", "", "mid", 55),
        ("Marvel", "130", "Black Panther (Glow)", "Target", "high", 120),
        ("Marvel", "169", "Doctor Strange", "", "standard", 18),
        ("Marvel", "308", "Thanos (Metallic)", "Walmart", "high", 110),
        ("Marvel", "402", "Iron Man (Avengers Assemble)", "Amazon", "mid", 65),
        ("Marvel", "499", "Captain America (Glow)", "Entertainment Earth", "high", 140),
        ("Marvel", "580", "Spider-Man (Miles Morales)", "", "standard", 15),
        ("Marvel", "648", "Scarlet Witch (Glow)", "Target", "mid", 75),

        # ── Star Wars (15) ────────────────────────────────────────────
        ("Star Wars", "01", "Darth Vader", "", "mid", 45),
        ("Star Wars", "02", "Yoda", "", "mid", 35),
        ("Star Wars", "03", "Holographic Darth Maul", "Paris Comic Con", "grail", 5000),
        ("Star Wars", "06", "Boba Fett (Droids)", "", "high", 350),
        ("Star Wars", "33", "Boba Fett (Prototype)", "", "high", 300),
        ("Star Wars", "40", "Luke Skywalker (Jedi)", "", "standard", 15),
        ("Star Wars", "130", "Obi-Wan Kenobi", "", "standard", 12),
        ("Star Wars", "326", "The Mandalorian", "", "standard", 18),
        ("Star Wars", "368", "Grogu (The Child)", "", "standard", 14),
        ("Star Wars", "414", "Ahsoka Tano", "", "mid", 40),
        ("Star Wars", "34", "Darth Revan", "GameStop", "high", 250),
        ("Star Wars", "104", "501st Clone Trooper", "GameStop", "high", 180),
        ("Star Wars", "SE", "Shadow Trooper", "Star Wars Celebration", "high", 300),
        ("Star Wars", "13", "C-3PO (Gold Chrome)", "Funko-Shop", "high", 250),
        ("Star Wars", "512", "Grogu (Macy's Parade)", "Amazon", "mid", 55),

        # ── Disney (13) ───────────────────────────────────────────────
        ("Disney", "01", "Mickey Mouse", "", "high", 200),
        ("Disney", "07", "Dumbo (Clown)", "", "high", 400),
        ("Disney", "08", "Cheshire Cat", "", "mid", 80),
        ("Disney", "16", "Lotso (Flocked)", "SDCC 2012", "high", 200),
        ("Haunted Mansion", "12", "Hatbox Ghost", "Disney Parks", "grail", 4000),
        ("Disney Villains", "09", "Maleficent (Flames)", "Hot Topic", "high", 180),
        ("Disney Villains", "231", "Ursula (Diamond)", "Hot Topic", "mid", 55),
        ("Disney Villains", "277", "Cruella de Vil (Glitter)", "", "mid", 40),
        ("Pixar", "02", "Buzz Lightyear (Metallic)", "SDCC 2011", "high", 350),
        ("Pixar", "168", "Woody", "", "standard", 12),
        ("Pixar", "400", "Wall-E (Earth Day)", "BoxLunch", "mid", 65),
        ("Disney", "125", "Stitch (Flocked)", "Hot Topic", "high", 150),
        ("Disney", "352", "Genie (Glow)", "Specialty Series", "mid", 55),

        # ── Anime / DragonBall Z / Expanded Anime (20) ────────────────
        ("Dragon Ball Z", "10", "Planet Arlia Vegeta", "Toy Tokyo", "grail", 8000),
        ("Dragon Ball Z", "14", "Super Saiyan Goku", "", "mid", 40),
        ("Dragon Ball Z", "47", "Goku (Kamehameha)", "", "standard", 15),
        ("Dragon Ball Z", "120", "Vegeta (Galick Gun)", "Chalice", "mid", 60),
        ("Naruto", "71", "Naruto (Six Path)", "Hot Topic", "mid", 65),
        ("Naruto", "73", "Kakashi (Lightning Blade)", "", "mid", 35),
        ("One Piece", "98", "Monkey D. Luffy", "", "mid", 40),
        ("One Piece", "99", "Trafalgar Law", "", "mid", 50),
        ("My Hero Academia", "564", "Deku (Full Cowling)", "Glow", "mid", 70),
        ("My Hero Academia", "248", "All Might (Metallic)", "GameStop", "high", 130),
        ("My Hero Academia", "372", "Todoroki", "", "standard", 18),
        ("Attack on Titan", "239", "Levi Ackerman (Cleaning)", "Hot Topic", "high", 180),
        ("Attack on Titan", "84", "Eren Titan Form", "", "mid", 55),
        ("Demon Slayer", "867", "Tanjiro Kamado", "", "standard", 15),
        ("Demon Slayer", "869", "Nezuko", "", "standard", 18),
        ("Demon Slayer", "1040", "Rengoku (Ninth Form)", "BoxLunch", "mid", 65),
        ("Sailor Moon", "89", "Sailor Moon", "", "mid", 70),
        ("Cowboy Bebop", "145", "Spike Spiegel", "", "high", 150),
        ("Bleach", "59", "Ichigo (Hollow)", "Vaulted", "high", 200),
        ("Jujutsu Kaisen", "1116", "Gojo (Infinite Void)", "Hot Topic", "mid", 45),

        # ── Game of Thrones (7) ───────────────────────────────────────
        ("Game of Thrones", "01", "Ned Stark", "", "mid", 60),
        ("Game of Thrones", "02", "Headless Ned Stark", "SDCC 2013", "grail", 2500),
        ("Game of Thrones", "03", "Daenerys Targaryen", "", "mid", 35),
        ("Game of Thrones", "08", "Khal Drogo", "", "mid", 45),
        ("Game of Thrones", "22", "Night King", "", "standard", 20),
        ("Game of Thrones", "44", "Ramsay Bolton", "", "standard", 25),
        ("Game of Thrones", "61", "Cersei Lannister", "", "standard", 15),

        # ── Horror / Classics (6) ─────────────────────────────────────
        ("Movies", "01", "Clockwork Orange Alex", "Vaulted", "grail", 3000),
        ("Horror", "03", "Michael Myers (Glow)", "Fugitive", "high", 400),
        ("Horror", "19", "Ghostface", "", "mid", 50),
        ("Ad Icons", "02", "Boo Berry (Metallic)", "SDCC 2012", "grail", 1500),
        ("Ad Icons", "01", "Franken Berry (Metallic)", "SDCC 2012", "grail", 1200),
        ("Ad Icons", "03", "Count Chocula (Metallic)", "SDCC 2012", "grail", 1200),

        # ── Pokemon (5) ───────────────────────────────────────────────
        ("Pokemon", "353", "Pikachu", "", "standard", 12),
        ("Pokemon", "843", "Charizard", "", "standard", 15),
        ("Pokemon", "455", "Mewtwo", "", "standard", 15),
        ("Pokemon", "504", "Eevee", "", "standard", 10),
        ("Pokemon", "780", "Bulbasaur (Diamond)", "Hot Topic", "mid", 30),

        # ── Harry Potter (11) ─────────────────────────────────────────
        ("Harry Potter", "01", "Harry Potter", "", "mid", 55),
        ("Harry Potter", "03", "Hermione Granger", "", "mid", 50),
        ("Harry Potter", "04", "Dumbledore (Robes)", "", "mid", 40),
        ("Harry Potter", "06", "Voldemort", "", "mid", 35),
        ("Harry Potter", "71", "Snape (Always - Patronus)", "Hot Topic", "high", 120),
        ("Harry Potter", "76", "Hedwig (Flocked)", "Hot Topic", "high", 110),
        ("Harry Potter", "104", "Harry (Patronus)", "Hot Topic", "mid", 45),
        ("Harry Potter", "127", "Hermione (Patronus)", "", "mid", 35),
        ("Harry Potter", "15", "Sirius Black", "", "mid", 65),
        ("Harry Potter", "09", "Dobby (10-Inch)", "Target", "mid", 45),
        ("Harry Potter", "33", "Dumbledore (Elder Wand)", "NYCC 2017", "high", 200),

        # ── Stranger Things (8) ───────────────────────────────────────
        ("Stranger Things", "421", "Eleven (Underwater)", "Hot Topic", "mid", 35),
        ("Stranger Things", "427", "Eleven (Flocked)", "Benny's Burgers", "high", 180),
        ("Stranger Things", "637", "Eleven (Upside Down)", "ECCC 2017", "high", 250),
        ("Stranger Things", "428", "Demogorgon", "", "mid", 40),
        ("Stranger Things", "1312", "Vecna", "", "standard", 20),
        ("Stranger Things", "475", "Steve Harrington", "", "mid", 60),
        ("Stranger Things", "424", "Dustin Henderson", "", "mid", 35),
        ("Stranger Things", "1250", "Eddie Munson", "Hot Topic", "mid", 55),

        # ── The Office (7) ────────────────────────────────────────────
        ("The Office", "869", "Michael Scott", "", "standard", 12),
        ("The Office", "870", "Dwight Schrute", "", "standard", 12),
        ("The Office", "875", "Prison Mike", "Hot Topic", "high", 140),
        ("The Office", "1060", "Michael Klump", "Target", "mid", 55),
        ("The Office", "938", "Dwight as Recyclops", "SDCC 2020", "high", 200),
        ("The Office", "877", "Andy Bernard (Sumo)", "", "mid", 35),
        ("The Office", "1010", "Date Night Dwight", "Target", "mid", 50),

        # ── Music (8) ─────────────────────────────────────────────────
        ("Rocks", "57", "Metallica - Lars Ulrich", "", "high", 120),
        ("Rocks", "158", "Tupac Shakur (Loyal to the Game)", "", "mid", 55),
        ("Rocks", "87", "Notorious B.I.G. (Crown)", "", "mid", 65),
        ("Rocks", "02", "Elvis Presley (Metallic)", "Hot Topic", "high", 350),
        ("Rocks", "79", "Prince (Purple Rain)", "", "high", 200),
        ("Rocks", "96", "Freddie Mercury (Wembley)", "", "mid", 35),
        ("Rocks", "14", "Jimi Hendrix (Monterey)", "SDCC 2017", "high", 300),
        ("Rocks", "66", "Kurt Cobain (MTV Unplugged)", "", "mid", 80),

        # ── Video Games (8) ───────────────────────────────────────────
        ("Halo", "01", "Master Chief", "", "mid", 80),
        ("Games", "269", "Kratos (Blades of Chaos)", "", "mid", 40),
        ("The Witcher", "151", "Geralt (IGNI)", "GameStop", "mid", 55),
        ("Games", "53", "Vault Boy", "", "standard", 20),
        ("Pokemon", "353", "Pikachu (10-Inch)", "Target", "high", 120),
        ("Games", "103", "Mega Man", "", "mid", 60),
        ("Games", "81", "Pac-Man", "", "mid", 45),
        ("Games", "283", "Sonic the Hedgehog (Gold)", "SDCC 2017", "high", 250),

        # ── Sports (6) ────────────────────────────────────────────────
        ("NBA", "54", "Michael Jordan (Bulls)", "", "mid", 55),
        ("NBA", "11", "Kobe Bryant (Purple Jersey)", "", "high", 400),
        ("NBA", "52", "LeBron James (White Jersey)", "", "mid", 45),
        ("Boxing", "01", "Muhammad Ali", "", "high", 150),
        ("NFL", "137", "Tom Brady (Patriots)", "", "mid", 75),
        ("NBA", "78", "Stephen Curry", "", "standard", 25),

        # ── Soda & Mini Lines (5) ─────────────────────────────────────
        ("Vinyl Soda", "SE", "Batman (Soda Chase)", "Funko-Shop", "high", 110),
        ("Vinyl Soda", "SE", "Spider-Man (Soda)", "", "mid", 35),
        ("Pocket POP Keychain", "SE", "Grogu Keychain", "", "standard", 8),
        ("Bitty Pop", "SE", "Bitty Pop - The Office (4 Pack)", "", "standard", 12),
        ("Bitty Pop", "SE", "Bitty Pop - Harry Potter (4 Pack)", "", "standard", 12),

        # ── Convention Exclusives / Funko Fundays (12) ────────────────
        ("Freddy Funko", "SE", "Freddy Funko (Astronaut)", "Funko HQ", "high", 500),
        ("Freddy Funko", "SE", "Freddy Funko as Pennywise", "Fundays", "grail", 3000),
        ("Freddy Funko", "SE", "Freddy Funko as Skeletor", "Fundays 2016", "grail", 5500),
        ("Freddy Funko", "SE", "Freddy Funko as Boba Fett", "Fundays 2014", "grail", 4000),
        ("Marvel", "SE", "Tony Stark (Metallic)", "SDCC 2013", "grail", 1200),
        ("DC Heroes", "SE", "Batgirl (Metallic Pink)", "SDCC 2012", "grail", 1100),
        ("Disney", "SE", "Winnie the Pooh (Flocked)", "SDCC 2012", "grail", 2200),
        ("Star Wars", "SE", "Holographic Emperor", "SDCC 2012", "grail", 1800),
        ("Animation", "SE", "Glow-in-Dark White Ranger", "SDCC 2013", "grail", 1500),
        ("Games", "SE", "Master Chief (Gold)", "SDCC 2013", "grail", 900),
        ("Freddy Funko", "SE", "Freddy Funko (Neon)", "Fundays 2019", "high", 450),
        ("DC Heroes", "SE", "The Joker (Metallic)", "NYCC 2013", "grail", 1400),

        # ── Television / Other (2) ────────────────────────────────────
        ("Friends", "700", "Monica Geller", "", "standard", 10),
        ("Breaking Bad", "158", "Walter White (Heisenberg)", "", "mid", 60),

        # ── Anime Expansion (8) ─────────────────────────────────────
        ("Dragon Ball Z", "154", "Golden Frieza", "SDCC 2015", "high", 250),
        ("Naruto", "1179", "Minato Namikaze (Glow)", "AAA Anime", "mid", 55),
        ("One Piece", "1269", "Gear Five Luffy", "Funko-Shop", "high", 120),
        ("Hunter x Hunter", "651", "Gon Freecss", "", "mid", 40),
        ("Hunter x Hunter", "652", "Killua Zoldyck", "", "mid", 45),
        ("Chainsaw Man", "1505", "Denji", "", "standard", 18),
        ("Chainsaw Man", "1544", "Power (Glow)", "Hot Topic", "mid", 55),
        ("Spy x Family", "1335", "Anya Forger", "", "standard", 15),

        # ── DC Expansion (6) ────────────────────────────────────────
        ("DC Heroes", "19", "Aquaman", "", "standard", 15),
        ("DC Heroes", "350", "Batman Beyond", "Target", "high", 180),
        ("DC Heroes", "144", "The Flash", "", "standard", 12),
        ("DC Heroes", "65", "Deathstroke", "", "mid", 55),
        ("DC Heroes", "258", "Batman (Merciless)", "Hot Topic", "mid", 70),
        ("DC Heroes", "461", "Superman (Blue Metallic)", "Funko-Shop", "high", 130),

        # ── Marvel Expansion (6) ────────────────────────────────────
        ("Marvel", "529", "Wolverine (Zombie)", "Entertainment Earth", "mid", 50),
        ("Marvel", "938", "Moon Knight", "", "standard", 15),
        ("Marvel", "614", "Taskmaster", "", "standard", 12),
        ("Marvel", "749", "Loki (President)", "Hot Topic", "mid", 45),
        ("Marvel", "1091", "Kang the Conqueror (Glow)", "Target", "mid", 65),
        ("Marvel", "SE", "Venom (Eddie Brock Jumbo)", "Funko-Shop", "high", 200),

        # ── Disney Expansion (5) ────────────────────────────────────
        ("Disney", "990", "Mirabel (Encanto)", "", "standard", 12),
        ("Disney", "1044", "Maui (Glow)", "Funko-Shop", "mid", 65),
        ("Disney", "325", "Raya (Glow)", "BoxLunch", "mid", 50),
        ("Disney", "718", "Elsa (Diamond)", "Hot Topic", "mid", 45),
        ("Disney", "1080", "Simba (Flocked)", "BoxLunch", "mid", 40),

        # ── Star Wars Expansion (5) ─────────────────────────────────
        ("Star Wars", "449", "Darth Vader (Glow)", "GITD", "mid", 50),
        ("Star Wars", "500", "Luke Skywalker (Retro)", "Target", "mid", 40),
        ("Star Wars", "488", "Darth Maul", "", "standard", 20),
        ("Star Wars", "SE", "Stormtrooper (Gold Chrome)", "Galactic Convention", "high", 300),
        ("Star Wars", "345", "R2-D2 (Jabba's Skiff)", "Smuggler's Bounty", "high", 110),

        # ── TV Shows Expansion (7) ──────────────────────────────────
        ("Seinfeld", "1085", "Jerry Seinfeld", "", "standard", 10),
        ("Seinfeld", "1087", "George Costanza", "", "standard", 10),
        ("Ted Lasso", "1351", "Ted Lasso", "", "standard", 14),
        ("Squid Game", "1218", "Player 456", "", "standard", 12),
        ("Yellowstone", "1363", "John Dutton", "", "standard", 10),
        ("House of the Dragon", "03", "Daemon Targaryen", "", "standard", 15),
        ("Wednesday", "1309", "Wednesday Addams", "Hot Topic", "mid", 45),

        # ── Horror Expansion (6) ────────────────────────────────────
        ("Horror", "1225", "Pennywise (Funhouse)", "Hot Topic", "mid", 55),
        ("Horror", "03", "Jason Voorhees (Glow)", "Funko-Shop", "high", 150),
        ("Horror", "56", "Freddy Krueger", "", "mid", 65),
        ("Horror", "848", "Ghostface (Metallic)", "SDCC 2022", "high", 200),
        ("Horror", "1112", "Art the Clown", "", "mid", 40),
        ("Horror", "830", "Chucky (Diamond)", "Hot Topic", "mid", 50),

        # ── Grails / Holy Grails (10) ───────────────────────────────
        ("Freddy Funko", "SE", "Freddy Funko as Darth Maul", "Fundays 2019", "grail", 6000),
        ("Freddy Funko", "SE", "Freddy Funko as Venom", "Fundays 2021", "grail", 3500),
        ("Freddy Funko", "SE", "Freddy Funko as Beetlejuice", "Fundays 2018", "grail", 4500),
        ("Freddy Funko", "SE", "Freddy Funko as the Joker", "Fundays 2017", "grail", 5000),
        ("Willy Wonka", "253", "Willy Wonka (Oompa Loompa)", "Vaulted", "grail", 2000),
        ("Disney", "SE", "Dumbo (Gold Clown)", "SDCC 2013", "grail", 3000),
        ("Freddy Funko", "SE", "Freddy Funko as Deadpool", "Fundays 2015", "grail", 2500),
        ("Star Wars", "SE", "Boba Fett (Prototype Gold)", "SDCC 2013", "grail", 2000),
        ("Freddy Funko", "SE", "Freddy Funko as the Thing", "Fundays 2014", "grail", 3500),
        ("Ad Icons", "04", "Tony the Tiger (Flocked)", "Funko-Shop", "grail", 1800),

        # ── SDCC Exclusives (12) ────────────────────────────────────
        ("Marvel", "SE", "Skrull as Iron Man", "SDCC 2011", "grail", 800),
        ("DC Heroes", "SE", "Bizarro", "SDCC 2012", "grail", 900),
        ("Marvel", "SE", "Metallic Deadpool (Red)", "SDCC 2013", "grail", 700),
        ("Star Wars", "SE", "Holographic Yoda", "SDCC 2013", "high", 400),
        ("Conan", "SE", "Conan O'Brien (Superhero)", "SDCC 2016", "high", 350),
        ("Conan", "SE", "Conan O'Brien as Joker", "SDCC 2017", "high", 400),
        ("Animation", "SE", "Brak (Space Ghost)", "SDCC 2016", "high", 280),
        ("Movies", "SE", "Darren (Seinfeld Wolfpack)", "SDCC 2014", "high", 350),
        ("TV", "SE", "Flocked Snuffleupagus (Sesame St)", "SDCC 2015", "grail", 750),
        ("Marvel", "SE", "Frost Giant Loki", "SDCC 2012", "grail", 600),
        ("DC Heroes", "SE", "Metallic Blue Batman", "SDCC 2010", "grail", 12000),
        ("Movies", "SE", "Headless Hershel (Walking Dead)", "SDCC 2014", "grail", 1500),

        # ── NYCC Exclusives (8) ─────────────────────────────────────
        ("Marvel", "SE", "Agent Venom", "NYCC 2014", "high", 350),
        ("Star Wars", "SE", "Chrome C-3PO", "NYCC 2015", "high", 250),
        ("Animation", "SE", "Metallic Vegeta", "NYCC 2013", "grail", 1200),
        ("DC Heroes", "SE", "White Lantern Flash", "NYCC 2013", "high", 300),
        ("Disney", "SE", "Genie (Metallic)", "NYCC 2013", "high", 450),
        ("TV", "SE", "Heisenberg (Blue Crystal)", "NYCC 2015", "high", 200),
        ("Movies", "SE", "Invisible Bilbo Baggins", "NYCC 2014", "high", 380),
        ("Animation", "SE", "Flocked Beast Man", "NYCC 2013", "high", 280),

        # ── Pop! Rides (6) ──────────────────────────────────────────
        ("Rides", "SE", "Batmobile (1966 TV)", "Hot Topic", "high", 180),
        ("Rides", "SE", "Deadpool Chimichanga Truck", "", "mid", 75),
        ("Rides", "SE", "Ghost Rider with Motorcycle", "PX Previews", "high", 200),
        ("Rides", "SE", "Hagrid Motorbike & Sidecar", "SDCC 2019", "high", 150),
        ("Rides", "SE", "Mandalorian on Blurrg", "", "mid", 55),
        ("Rides", "SE", "Night King on Icy Viserion", "HBO", "high", 120),

        # ── Jumbo / 10-Inch Pops (8) ───────────────────────────────
        ("Marvel", "SE", "Thanos (10-Inch Metallic)", "Target", "high", 150),
        ("Star Wars", "SE", "Grogu (10-Inch)", "Target", "mid", 55),
        ("Disney", "SE", "Stitch (10-Inch Flocked)", "Hot Topic", "high", 200),
        ("DC Heroes", "SE", "Batman (18-Inch)", "Funko-Shop", "high", 180),
        ("Games", "SE", "Master Chief (10-Inch Gold)", "Target", "high", 120),
        ("Animation", "SE", "All Might (10-Inch)", "Walmart", "mid", 70),
        ("Marvel", "SE", "Hulk (10-Inch)", "Target", "mid", 65),
        ("Rocks", "SE", "Notorious B.I.G. (10-Inch)", "Funko-Shop", "mid", 80),

        # ── Funko Soda Chase (8) ────────────────────────────────────
        ("Vinyl Soda", "SE", "Freddy Krueger (Soda Chase)", "Funko-Shop", "high", 130),
        ("Vinyl Soda", "SE", "Ghostface (Soda Chase)", "", "high", 110),
        ("Vinyl Soda", "SE", "Pennywise (Soda Chase)", "Funko-Shop", "high", 120),
        ("Vinyl Soda", "SE", "Maleficent (Soda Chase)", "Funko-Shop", "high", 100),
        ("Vinyl Soda", "SE", "Darth Vader (Soda Chase)", "Funko-Shop", "high", 140),
        ("Vinyl Soda", "SE", "Boba Fett (Soda Chase)", "Funko-Shop", "high", 160),
        ("Vinyl Soda", "SE", "Joker (Soda Chase)", "", "mid", 90),
        ("Vinyl Soda", "SE", "Vegeta (Soda Chase)", "Funko-Shop", "high", 150),

        # ── Bitty Pop (6) ──────────────────────────────────────────
        ("Bitty Pop", "SE", "Bitty Pop - Star Wars (4 Pack)", "", "standard", 12),
        ("Bitty Pop", "SE", "Bitty Pop - Marvel Avengers (4 Pack)", "", "standard", 12),
        ("Bitty Pop", "SE", "Bitty Pop - Disney Villains (4 Pack)", "", "standard", 12),
        ("Bitty Pop", "SE", "Bitty Pop - Stranger Things (4 Pack)", "", "standard", 12),
        ("Bitty Pop", "SE", "Bitty Pop - Demon Slayer (4 Pack)", "", "standard", 14),
        ("Bitty Pop", "SE", "Bitty Pop - Five Nights at Freddy's (4 Pack)", "", "standard", 12),

        # ── Anime Grails / Expansion (12) ──────────────────────────
        ("Dragon Ball Z", "SE", "Super Saiyan Goku (Glow)", "SDCC 2018", "high", 350),
        ("Dragon Ball Z", "623", "Goku (Ultra Instinct Sign)", "Chalice", "mid", 80),
        ("Dragon Ball Super", "827", "Vegeta (Ultra Ego Glow)", "Entertainment Earth", "high", 110),
        ("Naruto", "185", "Naruto (Sage Mode)", "GameStop", "high", 200),
        ("Naruto", "1430", "Itachi Uchiha (Susanoo)", "AAA Anime", "mid", 65),
        ("One Piece", "1276", "Yamato", "", "mid", 35),
        ("Bleach", "1181", "Hollow Ichigo (Glow)", "Hot Topic", "mid", 55),
        ("Tokyo Ghoul", "61", "Ken Kaneki (Glow)", "Funko-Shop", "high", 250),
        ("Death Note", "217", "Ryuk", "", "high", 180),
        ("Death Note", "218", "Light Yagami", "", "high", 120),
        ("Fullmetal Alchemist", "391", "Edward Elric", "", "mid", 75),
        ("Yu-Gi-Oh!", "SE", "Blue-Eyes White Dragon", "Hot Topic", "mid", 55),

        # ── Disney Vaulted / Classic (10) ──────────────────────────
        ("Disney", "SE", "Sorcerer Mickey (Metallic)", "D23 Expo 2013", "grail", 1500),
        ("Disney", "26", "Sulley (Flocked)", "SDCC 2011", "high", 450),
        ("Disney", "11", "Tigger (Flocked)", "SDCC 2012", "high", 350),
        ("Disney", "09", "Peter Pan (Metallic)", "Gemini", "high", 400),
        ("Disney", "32", "Tinker Bell (Diamond)", "Hot Topic", "mid", 50),
        ("Disney", "31", "Goofy", "Vaulted", "high", 250),
        ("Disney", "SE", "Alice (Black & White)", "Hot Topic", "mid", 75),
        ("Disney", "150", "Abu (Flocked)", "BoxLunch", "mid", 40),
        ("Disney", "SE", "Remy (Flocked)", "SDCC 2015", "high", 300),
        ("Disney", "SE", "Ariel (Gold Diamond)", "Hot Topic", "mid", 55),

        # ── 2025-2026 Releases (12) ────────────────────────────────
        ("Marvel", "SE", "Spider-Man 2099 (Glow)", "Target", "mid", 40),
        ("Marvel", "SE", "Iron Man (Holographic)", "Funko-Shop", "mid", 65),
        ("Star Wars", "SE", "Mace Windu (Glow)", "Funko-Shop", "mid", 50),
        ("Animation", "SE", "Tanjiro (Sun Breathing)", "Hot Topic", "mid", 55),
        ("Games", "SE", "Link (Tears of the Kingdom)", "", "standard", 20),
        ("Disney", "SE", "Moana 2 - Moana", "", "standard", 15),
        ("Animation", "SE", "Luffy Gear 5 (Glow Metallic)", "Funko-Shop", "high", 150),
        ("Movies", "SE", "Wicked - Elphaba", "", "standard", 18),
        ("TV", "SE", "Severance - Mark Scout", "", "standard", 15),
        ("Marvel", "SE", "Deadpool & Wolverine (2-Pack)", "Target", "mid", 45),
        ("Animation", "SE", "Gojo (Domain Expansion Glow)", "Funko-Shop", "high", 120),
        ("Disney", "SE", "Lilo & Stitch Alien (Blacklight)", "Funko-Shop", "mid", 75),

        # ── Ad Icons Expansion (8) ─────────────────────────────────
        ("Ad Icons", "85", "Toucan Sam (Flocked)", "Funko-Shop", "high", 200),
        ("Ad Icons", "10", "Trix Rabbit (Flocked)", "Funko-Shop", "high", 250),
        ("Ad Icons", "117", "McDonald's Hamburglar", "", "mid", 35),
        ("Ad Icons", "186", "Pringles Can", "", "mid", 30),
        ("Ad Icons", "131", "Coca-Cola Polar Bear (Diamond)", "Funko-Shop", "mid", 50),
        ("Ad Icons", "25", "Buzz Bee (Honey Nut Cheerios)", "Funko-Shop", "high", 180),
        ("Ad Icons", "40", "Mr. Owl (Tootsie Roll)", "Funko-Shop", "mid", 60),
        ("Ad Icons", "05", "Snap! Crackle! Pop! (3 Pack)", "Funko-Shop", "high", 350),

        # ── Movies Expansion (8) ───────────────────────────────────
        ("Movies", "10", "Tony Montana (Scarface)", "Vaulted", "grail", 600),
        ("Movies", "23", "Hannibal Lecter", "Vaulted", "high", 200),
        ("Movies", "17", "Beetlejuice", "Vaulted", "high", 180),
        ("Movies", "113", "Marty McFly (Hoverboard)", "Funko-Shop", "high", 200),
        ("Movies", "49", "Ferris Bueller", "Vaulted", "high", 150),
        ("Movies", "1075", "Wednesday Addams (w/ Thing)", "Amazon", "mid", 35),
        ("Movies", "SE", "Gandalf (LOTR Balrog Fight)", "SDCC 2019", "high", 250),
        ("Movies", "SE", "E.T. (Glow)", "Target", "mid", 45),

        # ── Music / Rocks Expansion (8) ────────────────────────────
        ("Rocks", "112", "Ozzy Osbourne", "", "mid", 55),
        ("Rocks", "78", "Jerry Garcia (Flocked)", "Hot Topic", "high", 200),
        ("Rocks", "188", "Post Malone", "", "standard", 15),
        ("Rocks", "62", "Biggie (Notorious)", "Metallic", "high", 250),
        ("Rocks", "121", "Selena (Burgundy Dress)", "", "mid", 80),
        ("Rocks", "234", "Bad Bunny", "", "mid", 30),
        ("Rocks", "345", "Taylor Swift (Eras Tour)", "", "mid", 45),
        ("Rocks", "279", "Dolly Parton", "", "standard", 20),

        # ── Sports Expansion (6) ───────────────────────────────────
        ("NBA", "126", "Giannis Antetokounmpo", "", "standard", 18),
        ("NBA", "171", "Luka Doncic", "", "standard", 15),
        ("NBA", "177", "Ja Morant", "", "standard", 15),
        ("Soccer", "SE", "Lionel Messi (PSG)", "", "mid", 40),
        ("Soccer", "SE", "Cristiano Ronaldo (Al-Nassr)", "", "mid", 35),
        ("WWE", "46", "The Rock", "", "mid", 50),

        # ── Television Deep-Cuts (8) ───────────────────────────────
        ("Simpsons", "500", "Homer Simpson", "", "standard", 12),
        ("Simpsons", "502", "Bart Simpson", "", "standard", 12),
        ("Rick and Morty", "112", "Pickle Rick", "", "mid", 30),
        ("Rick and Morty", "417", "Rick with Portal Gun", "Hot Topic", "mid", 50),
        ("Futurama", "29", "Bender (Gold)", "SDCC 2015", "high", 350),
        ("South Park", "01", "Cartman", "", "standard", 15),
        ("Bob's Burgers", "74", "Bob Belcher", "", "standard", 12),
        ("Avatar TLA", "995", "Aang (Avatar State)", "Glow", "high", 130),

        # ── Marvel MCU Expansion (20) ─────────────────────────────────
        ("Marvel", "449", "Iron Man (Mark I)", "", "mid", 40),
        ("Marvel", "580", "Black Widow (Quantum Suit)", "", "standard", 15),
        ("Marvel", "574", "Hulk (Endgame)", "", "standard", 12),
        ("Marvel", "452", "Captain America (Endgame)", "", "standard", 15),
        ("Marvel", "286", "Thor (Ragnarok)", "", "mid", 35),
        ("Marvel", "289", "Hela (Ragnarok)", "", "mid", 45),
        ("Marvel", "427", "Shuri (Black Panther)", "", "standard", 12),
        ("Marvel", "492", "Ant-Man (Endgame)", "", "standard", 10),
        ("Marvel", "301", "Vision", "", "mid", 55),
        ("Marvel", "946", "Namor (Wakanda Forever)", "", "standard", 12),
        ("Marvel", "1117", "Kang (Quantumania)", "", "standard", 15),
        ("Marvel", "462", "Rocket Raccoon (Holiday)", "", "standard", 10),
        ("Marvel", "590", "Hawkeye (Ronin)", "", "standard", 15),
        ("Marvel", "342", "Groot (10-Inch)", "Target", "mid", 45),
        ("Marvel", "SE", "Iron Man (Glow Snap)", "PX Previews", "high", 110),
        ("Marvel", "SE", "Captain America (Sam Wilson)", "Walmart", "mid", 40),
        ("Marvel", "776", "Eternals - Ikaris", "", "standard", 8),
        ("Marvel", "823", "Wanda (Multiverse of Madness)", "", "standard", 12),
        ("Marvel", "SE", "Spider-Man (Japanese TV Series)", "Amazon", "mid", 55),
        ("Marvel", "1103", "She-Hulk (Glow)", "Target", "mid", 35),

        # ── DC Comics Expansion (14) ─────────────────────────────────
        ("DC Heroes", "274", "Batman (Imperial Palace)", "", "standard", 15),
        ("DC Heroes", "289", "Batman (Robert Pattinson)", "", "standard", 12),
        ("DC Heroes", "SE", "Batman (Gold Chrome)", "Funko-Shop", "high", 200),
        ("DC Heroes", "342", "Joker (The Dark Knight)", "", "mid", 55),
        ("DC Heroes", "SE", "Joker (Metallic NYCC 2013)", "NYCC 2013", "grail", 1400),
        ("DC Heroes", "408", "Supergirl", "", "standard", 10),
        ("DC Heroes", "419", "Wonder Woman (Jim Lee)", "GameStop", "mid", 40),
        ("DC Heroes", "462", "Poison Ivy (Diamond)", "Hot Topic", "mid", 35),
        ("DC Heroes", "SE", "Two-Face (Gemini)", "Gemini Collectibles", "high", 200),
        ("DC Heroes", "380", "Zatanna", "", "standard", 12),
        ("DC Heroes", "345", "Robin (Damian Wayne)", "", "standard", 10),
        ("DC Heroes", "SE", "Catwoman (Bronze)", "Entertainment Earth", "mid", 50),
        ("DC Heroes", "286", "The Flash (Flashpoint)", "Hot Topic", "high", 120),
        ("DC Heroes", "SE", "Darkseid (10-Inch)", "Target", "mid", 45),

        # ── Star Wars Deep Expansion (15) ────────────────────────────
        ("Star Wars", "505", "Anakin Skywalker", "", "standard", 12),
        ("Star Wars", "422", "Emperor Palpatine", "", "standard", 10),
        ("Star Wars", "SE", "Vader (Ralph McQuarrie Concept)", "Star Wars Celebration", "high", 350),
        ("Star Wars", "563", "Bo-Katan Kryze", "", "standard", 15),
        ("Star Wars", "449", "General Grievous", "", "mid", 55),
        ("Star Wars", "598", "Cad Bane", "", "standard", 18),
        ("Star Wars", "SE", "Jango Fett (Metallic)", "SDCC 2013", "high", 280),
        ("Star Wars", "SE", "Holographic Luke Skywalker", "SDCC 2022", "high", 200),
        ("Star Wars", "462", "Darth Vader (Bespin)", "", "standard", 15),
        ("Star Wars", "523", "Clone Commander Cody", "", "mid", 40),
        ("Star Wars", "517", "Grand Admiral Thrawn", "Star Wars Celebration", "high", 250),
        ("Star Wars", "SE", "Kit Fisto (Metallic)", "ECCC 2020", "mid", 65),
        ("Star Wars", "476", "Pre Vizsla", "GameStop", "mid", 55),
        ("Star Wars", "SE", "Chewbacca (Flocked)", "Funko-Shop", "high", 130),
        ("Star Wars", "SE", "Padme Amidala (Gold)", "Galactic Convention", "high", 180),

        # ── Disney Parks & Princess & Villain (12) ───────────────────
        ("Disney", "SE", "Mickey Mouse (Splash Mountain)", "Disney Parks", "high", 200),
        ("Disney", "SE", "Orange Bird", "Disney Parks", "high", 180),
        ("Disney", "SE", "Figment (Diamond)", "Disney Parks", "high", 250),
        ("Disney", "SE", "Madame Leota (Glow)", "Disney Parks", "grail", 500),
        ("Disney", "1024", "Rapunzel (Diamond)", "Hot Topic", "mid", 45),
        ("Disney", "1019", "Belle (Diamond)", "Hot Topic", "mid", 40),
        ("Disney", "815", "Snow White (Diamond)", "Hot Topic", "mid", 45),
        ("Disney", "564", "Jasmine (Gold)", "Ultimate Princess", "mid", 35),
        ("Disney", "1082", "Mirabel (Butterfly)", "BoxLunch", "mid", 40),
        ("Disney Villains", "1083", "Jafar (Diamond)", "Hot Topic", "mid", 50),
        ("Disney Villains", "SE", "Evil Queen (Metallic)", "SDCC 2012", "high", 350),
        ("Disney Villains", "SE", "Scar (Flocked)", "Hot Topic", "mid", 55),

        # ── Anime Deep Expansion (20) ────────────────────────────────
        ("Dragon Ball Z", "386", "Vegeta (Over 9000)", "Glow", "mid", 65),
        ("Dragon Ball Z", "948", "Gohan (Beast Mode)", "Entertainment Earth", "mid", 55),
        ("Dragon Ball Z", "SE", "Broly (6-Inch)", "Hot Topic", "high", 110),
        ("Dragon Ball Z", "SE", "Shenron (Gold)", "Hot Topic", "grail", 500),
        ("Naruto", "727", "Sasuke (Rinnegan)", "AAA Anime", "mid", 55),
        ("Naruto", "1179", "Kakashi (Anbu)", "Chalice", "high", 120),
        ("Naruto", "SE", "Pain (Almighty Push Glow)", "GameStop", "mid", 65),
        ("One Piece", "1265", "Zoro (Enma)", "", "standard", 18),
        ("One Piece", "SE", "Kaido (Dragon Form 6-Inch)", "Hot Topic", "high", 130),
        ("One Piece", "1474", "Shanks (Glow)", "Big Apple Collectibles", "mid", 55),
        ("Demon Slayer", "1255", "Muzan Kibutsuji", "", "standard", 15),
        ("Demon Slayer", "SE", "Akaza (Glow)", "Funko-Shop", "mid", 60),
        ("Demon Slayer", "874", "Inosuke Hashibira", "", "standard", 12),
        ("Demon Slayer", "SE", "Gyomei Himejima (Stone Breathing)", "Hot Topic", "mid", 50),
        ("My Hero Academia", "603", "Dabi", "", "mid", 40),
        ("My Hero Academia", "SE", "Shigaraki (Glow)", "Hot Topic", "mid", 55),
        ("Jujutsu Kaisen", "1116", "Gojo (Hollow Purple)", "Funko-Shop", "high", 100),
        ("Jujutsu Kaisen", "1357", "Sukuna", "", "standard", 18),
        ("Bleach", "1180", "Grimmjow", "", "mid", 40),
        ("Bleach", "SE", "Aizen (Muken)", "Hot Topic", "mid", 55),

        # ── Horror All Franchises (12) ───────────────────────────────
        ("Horror", "03", "Michael Myers", "Vaulted", "high", 300),
        ("Horror", "458", "Pennywise (w/ Boat)", "", "mid", 40),
        ("Horror", "992", "Leatherface (Bloody)", "Hot Topic", "mid", 55),
        ("Horror", "360", "Annabelle", "", "mid", 35),
        ("Horror", "798", "Candyman", "", "standard", 20),
        ("Horror", "611", "Pinhead", "", "mid", 65),
        ("Horror", "SE", "Hannibal Lecter (Bloody)", "SDCC 2014", "high", 250),
        ("Horror", "1123", "Tiffany (Bride of Chucky)", "", "mid", 35),
        ("Horror", "SE", "Nosferatu (Glow)", "Funko-Shop", "high", 180),
        ("Horror", "1232", "Sam (Trick 'r Treat)", "", "mid", 45),
        ("Horror", "SE", "Creature from the Black Lagoon (Metallic)", "Gemini", "high", 350),
        ("Horror", "SE", "Dracula (Metallic)", "Funko-Shop", "high", 200),

        # ── Breaking Bad & Game of Thrones (10) ─────────────────────
        ("Breaking Bad", "159", "Jesse Pinkman", "", "mid", 50),
        ("Breaking Bad", "161", "Gus Fring (Dead)", "EE", "high", 180),
        ("Breaking Bad", "162", "Walter White (Hazmat)", "", "mid", 70),
        ("Breaking Bad", "SE", "Heisenberg (Blue Crystal Glow)", "SDCC 2014", "high", 250),
        ("Game of Thrones", "09", "Robb Stark", "", "mid", 80),
        ("Game of Thrones", "50", "Jon Snow (Castle Black)", "", "mid", 40),
        ("Game of Thrones", "38", "Tyrion Lannister (Scar)", "SDCC 2014", "high", 200),
        ("Game of Thrones", "45", "The Mountain (Armoured)", "", "mid", 55),
        ("Game of Thrones", "SE", "Iron Throne", "Hot Topic", "mid", 75),
        ("Game of Thrones", "58", "Brienne of Tarth", "", "mid", 45),

        # ── Stranger Things & The Office Expansion (10) ──────────────
        ("Stranger Things", "1253", "Max Mayfield (Floating)", "Hot Topic", "mid", 45),
        ("Stranger Things", "SE", "Demogorgon (10-Inch)", "Target", "high", 110),
        ("Stranger Things", "523", "Robin Buckley", "", "standard", 15),
        ("Stranger Things", "1241", "Eleven (Battle Damage)", "Walmart", "mid", 40),
        ("Stranger Things", "SE", "Hopper (Bitten)", "Amazon", "mid", 50),
        ("The Office", "906", "Kevin Malone (with Chili)", "Hot Topic", "mid", 55),
        ("The Office", "879", "Angela Martin (with Sprinkles)", "", "standard", 15),
        ("The Office", "1015", "Creed Bratton", "Specialty Series", "high", 120),
        ("The Office", "SE", "Threat Level Midnight (Michael Scarn)", "Target", "mid", 65),
        ("The Office", "SE", "Dwight as Dark Lord", "Hot Topic", "mid", 50),

        # ── Friends & Seinfeld (10) ──────────────────────────────────
        ("Friends", "701", "Rachel Green", "", "standard", 10),
        ("Friends", "702", "Ross Geller", "", "standard", 10),
        ("Friends", "703", "Joey Tribbiani", "", "standard", 10),
        ("Friends", "704", "Phoebe Buffay", "", "standard", 10),
        ("Friends", "705", "Chandler Bing", "", "standard", 10),
        ("Friends", "1278", "Monica (Turkey Head)", "Target", "mid", 50),
        ("Friends", "SE", "Gunther", "Hot Topic", "mid", 35),
        ("Seinfeld", "1089", "Kramer", "", "standard", 12),
        ("Seinfeld", "1095", "Newman", "", "standard", 12),
        ("Seinfeld", "SE", "Jerry (Puffy Shirt)", "Target", "mid", 40),

        # ── Video Games Expansion (15) ───────────────────────────────
        ("Games", "SE", "Link (Ocarina of Time)", "GameStop", "mid", 75),
        ("Games", "423", "Link (Breath of the Wild)", "", "standard", 20),
        ("Games", "SE", "Zelda (Tears of the Kingdom)", "", "standard", 18),
        ("Games", "SE", "Mario (Gold)", "Walmart", "high", 120),
        ("Games", "198", "Mario (Raccoon)", "GameStop", "mid", 40),
        ("Games", "SE", "Luigi (Metallic)", "Target", "mid", 35),
        ("Games", "SE", "Peach (Glow)", "Entertainment Earth", "mid", 45),
        ("Pokemon", "SE", "Pikachu (Flocked)", "Funko-Shop", "mid", 55),
        ("Pokemon", "SE", "Gengar (Metallic)", "ECCC 2022", "high", 110),
        ("Pokemon", "580", "Squirtle", "", "standard", 12),
        ("Halo", "SE", "Master Chief (Active Camo)", "Best Buy", "high", 150),
        ("Halo", "18", "Cortana", "", "mid", 45),
        ("Overwatch", "92", "Tracer", "", "mid", 30),
        ("Overwatch", "493", "D.Va (Diamond)", "Hot Topic", "mid", 55),
        ("Games", "SE", "Pac-Man (Gold)", "Funko-Shop", "high", 130),

        # ── Cereal Mascots / Ad Icons Expansion (10) ─────────────────
        ("Ad Icons", "SE", "Cap'n Crunch", "Funko-Shop", "high", 200),
        ("Ad Icons", "SE", "Lucky Charms Lucky (Glow)", "Funko-Shop", "high", 220),
        ("Ad Icons", "91", "Energizer Bunny (Flocked)", "Funko-Shop", "high", 180),
        ("Ad Icons", "SE", "Hawaiian Punch Punchy", "Funko-Shop", "mid", 65),
        ("Ad Icons", "SE", "Fruit Brute", "Funko-Shop", "high", 350),
        ("Ad Icons", "SE", "Yummy Mummy", "Funko-Shop", "high", 400),
        ("Ad Icons", "12", "Dig Em' Frog", "Funko-Shop", "mid", 70),
        ("Ad Icons", "SE", "Kool-Aid Man (Metallic)", "Funko-Shop", "high", 150),
        ("Ad Icons", "109", "Sprite (Lymon)", "Funko-Shop", "mid", 55),
        ("Ad Icons", "SE", "Green Giant (Metallic)", "Target", "high", 200),

        # ── Freddy Funko Expansion (10) ──────────────────────────────
        ("Freddy Funko", "SE", "Freddy Funko as Iron Man", "Fundays 2014", "grail", 4000),
        ("Freddy Funko", "SE", "Freddy Funko as Batman", "Fundays 2015", "grail", 3000),
        ("Freddy Funko", "SE", "Freddy Funko as Freddy Krueger", "Fundays 2018", "grail", 2500),
        ("Freddy Funko", "SE", "Freddy Funko as Captain America", "Fundays 2019", "grail", 2000),
        ("Freddy Funko", "SE", "Freddy Funko as Spider-Man", "Fundays 2020", "grail", 3500),
        ("Freddy Funko", "SE", "Freddy Funko as Stormtrooper", "Fundays 2016", "grail", 2800),
        ("Freddy Funko", "SE", "Freddy Funko (Letterman Jacket)", "Funko HQ", "high", 400),
        ("Freddy Funko", "SE", "Freddy Funko (Black Tuxedo)", "Fundays 2021", "high", 350),
        ("Freddy Funko", "SE", "Freddy Funko as Wolverine", "Fundays 2022", "grail", 2500),
        ("Freddy Funko", "SE", "Freddy Funko as The Mandalorian", "Fundays 2020", "grail", 3000),

        # ── WWE & Sports Expansion (8) ───────────────────────────────
        ("WWE", "01", "John Cena", "", "mid", 40),
        ("WWE", "77", "Stone Cold Steve Austin", "", "mid", 65),
        ("WWE", "93", "Undertaker (Metallic)", "Walmart", "high", 130),
        ("WWE", "46", "Macho Man Randy Savage (Metallic)", "Target", "high", 110),
        ("NBA", "02", "LeBron James (LA Lakers)", "", "mid", 35),
        ("NBA", "SE", "Michael Jordan (UNC)", "Funko-Shop", "high", 200),
        ("NFL", "SE", "Patrick Mahomes (SB Champion)", "", "mid", 35),
        ("Soccer", "SE", "Lionel Messi (Inter Miami)", "", "mid", 30),

        # ── Animation / Cartoons (10) ────────────────────────────────
        ("Animation", "SE", "Voltron (6-Inch Metallic)", "SDCC 2014", "grail", 700),
        ("Animation", "74", "Ren & Stimpy (2-Pack)", "Vaulted", "high", 200),
        ("Animation", "SE", "Thundercats Lion-O (Flocked)", "SDCC 2014", "high", 350),
        ("Avatar TLA", "541", "Zuko", "", "standard", 15),
        ("Avatar TLA", "996", "Iroh", "", "mid", 35),
        ("Avatar TLA", "SE", "Toph (Metallic)", "ECCC 2021", "mid", 55),
        ("Animation", "252", "He-Man (Metallic)", "Gemini", "high", 250),
        ("Animation", "SE", "Scooby-Doo (Flocked)", "SDCC 2017", "high", 200),
        ("Animation", "SE", "Optimus Prime (Metallic)", "SDCC 2014", "high", 350),
        ("Animation", "SE", "Megazord (6-Inch Metallic)", "SDCC 2017", "high", 250),

        # ── Funko Soda Chase Figures (8) ────────────────────────────────
        ("Vinyl Soda", "SE", "Freddy Funko (Chase)", "Funko-Shop", "grail", 600),
        ("Vinyl Soda", "SE", "Batman (Chase Metallic)", "Funko-Shop", "high", 250),
        ("Vinyl Soda", "SE", "Spider-Man (Chase Glow)", "Funko-Shop", "high", 200),
        ("Vinyl Soda", "SE", "Joker (Chase Dark Knight)", "SDCC 2023", "high", 180),
        ("Vinyl Soda", "SE", "Boba Fett (Chase)", "Funko-Shop", "high", 220),
        ("Vinyl Soda", "SE", "Darth Vader (Chase Glow)", "Funko-Shop", "high", 190),
        ("Vinyl Soda", "SE", "Deadpool (Chase Metallic)", "Funko-Shop", "mid", 90),
        ("Vinyl Soda", "SE", "Teenage Mutant Ninja Turtles Leonardo (Chase)", "Funko-Shop", "mid", 75),

        # ── Funko x Loungefly Crossovers (5) ───────────────────────────
        ("Loungefly x Funko", "SE", "Maleficent Pop! & Mini Backpack Set", "BoxLunch", "high", 120),
        ("Loungefly x Funko", "SE", "Ariel Pop! & Crossbody Set", "BoxLunch", "mid", 95),
        ("Loungefly x Funko", "SE", "Cinderella Castle Pop! & Mini Backpack Set", "Disney Parks", "high", 150),
        ("Loungefly x Funko", "SE", "Star Wars Ahsoka Pop! & Wallet Set", "Hot Topic", "mid", 85),
        ("Loungefly x Funko", "SE", "Mickey Mouse Pop! & Ears Headband Set", "Disney Parks", "mid", 100),

        # ── Pop! Trains (5) ─────────────────────────────────────────────
        ("Pop! Trains", "15", "Hogwarts Express Engine w/ Harry Potter", "Exclusive", "high", 140),
        ("Pop! Trains", "16", "Hogwarts Express Carriage w/ Ron Weasley", "Exclusive", "high", 130),
        ("Pop! Trains", "17", "Hogwarts Express Carriage w/ Hermione", "Exclusive", "high", 130),
        ("Pop! Trains", "20", "Disneyland Railroad w/ Mickey", "Disney Parks", "high", 180),
        ("Pop! Trains", "21", "Nightmare Before Christmas Train w/ Jack", "Hot Topic", "high", 160),

        # ── Pop! Moments (6) ───────────────────────────────────────────
        ("Pop! Moment", "612", "Avengers Assemble: Iron Man (Deluxe)", "Amazon", "high", 120),
        ("Pop! Moment", "620", "Avengers Assemble: Captain America (Deluxe)", "Amazon", "high", 110),
        ("Pop! Moment", "SE", "Harry Potter vs Voldemort", "Exclusive", "high", 140),
        ("Pop! Moment", "SE", "Luke vs Darth Vader (Bespin)", "Movie Moment", "high", 130),
        ("Pop! Moment", "SE", "Batman vs Joker (80th Anniversary)", "GameStop", "mid", 85),
        ("Pop! Moment", "SE", "Carl & Ellie (Up Movie Moment)", "BoxLunch", "high", 160),

        # ── Pop! Albums (7) ────────────────────────────────────────────
        ("Pop! Albums", "01", "AC/DC - Back in Black", "", "mid", 40),
        ("Pop! Albums", "07", "Notorious B.I.G. - Ready to Die", "", "mid", 55),
        ("Pop! Albums", "08", "Tupac - 2Pacalypse Now", "", "mid", 50),
        ("Pop! Albums", "13", "Metallica - Metallica (Black Album)", "", "mid", 60),
        ("Pop! Albums", "18", "Jimi Hendrix - Are You Experienced", "", "mid", 45),
        ("Pop! Albums", "22", "Iron Maiden - The Number of the Beast", "", "mid", 55),
        ("Pop! Albums", "28", "Prince - Purple Rain", "Target", "high", 110),

        # ── Pop! Digital NFT Redemptions (5) ───────────────────────────
        ("Pop! Digital", "SE", "Freddy Funko (Legendary)", "NFT Redemption", "grail", 1500),
        ("Pop! Digital", "SE", "Batman (Grail Series)", "NFT Redemption", "grail", 800),
        ("Pop! Digital", "SE", "Spider-Man (Legendary)", "NFT Redemption", "grail", 900),
        ("Pop! Digital", "SE", "Boba Fett (Legendary)", "NFT Redemption", "high", 400),
        ("Pop! Digital", "SE", "Optimus Prime (Legendary)", "NFT Redemption", "high", 350),

        # ── Funko Hollywood / HQ Exclusives (7) ───────────────────────
        ("Hollywood Exclusive", "SE", "Freddy Funko as Batman (Hollywood)", "Funko Hollywood", "grail", 500),
        ("Hollywood Exclusive", "SE", "Freddy Funko as Ironman (Hollywood)", "Funko Hollywood", "high", 300),
        ("HQ Exclusive", "SE", "Freddy Funko (Funko HQ)", "Funko HQ Everett", "high", 250),
        ("Hollywood Exclusive", "SE", "Toucan Sam (Flocked)", "Funko Hollywood", "high", 200),
        ("Hollywood Exclusive", "SE", "Godzilla (Metallic)", "Funko Hollywood", "high", 180),
        ("HQ Exclusive", "SE", "Bigfoot (Flocked Rainbow)", "Funko HQ Everett", "high", 250),
        ("HQ Exclusive", "SE", "Bigfoot (Snowy)", "Funko HQ Everett", "high", 220),

        # ── Pop! Town (7) ──────────────────────────────────────────────
        ("Pop! Town", "01", "Wayne Manor w/ Batman (Metallic)", "Hot Topic", "high", 150),
        ("Pop! Town", "02", "Avengers Tower w/ Iron Man", "Amazon", "high", 140),
        ("Pop! Town", "10", "Sleeping Beauty Castle w/ Aurora", "Disney Parks", "grail", 500),
        ("Pop! Town", "15", "Hogwarts w/ Dumbledore", "Exclusive", "high", 120),
        ("Pop! Town", "20", "Ghostbusters Firehouse w/ Slimer", "Walmart", "mid", 75),
        ("Pop! Town", "25", "Byers House w/ Demogorgon (Stranger Things)", "Target", "mid", 65),
        ("Pop! Town", "30", "Haunted Mansion w/ Ghost", "Disney Parks", "high", 200),
    ]

    catalog = []
    for line, number, name, exclusive, tier, price in pops:
        catalog.append({
            "line": line,
            "number": number,
            "name": name,
            "exclusive": exclusive,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    line = item["line"]
    number = item["number"]
    name = item["name"]
    exclusive = item["exclusive"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{line}-{number}-{name}"),
        title=f"{name} #{number}",
        set_code=line.lower().replace(" ", "-"),
        brand="Funko Pop",
        rarity=item["rarity_tier"].title(),
        notes=f"{line} #{number}" + (f" | {exclusive}" if exclusive else ""),
        attributes_json={
            "line": line,
            "number": number,
            "exclusive": exclusive,
            "sticker_variant": exclusive if exclusive else "",
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    exclusive_score = 0.9 if item["exclusive"] else 0.3

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": exclusive_score,
            "is_chase": 0.0,
            "is_exclusive": 1.0 if item["exclusive"] else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Funko Pop catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Funko Pop Import ===")

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

    logger.info(f"\n=== Funko Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
