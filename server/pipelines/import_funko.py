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

        # ── Harry Potter (60+) ─────────────────────────────────────────
        # Original 11
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
        # Grails & high-value exclusives
        ("Harry Potter", "SE", "Freddy Funko as Dobby (24 pcs)", "SDCC 2017", "grail", 4000),
        ("Harry Potter", "08", "Harry Potter (Quidditch)", "SDCC 2016", "grail", 700),
        ("Harry Potter", "41", "Luna Lovegood (Spectrespecs)", "SDCC 2017", "high", 260),
        ("Harry Potter", "SE", "The Burrow & Molly Weasley Pop Town", "", "high", 280),
        ("Harry Potter", "31", "Harry Potter on Broom", "SDCC", "high", 160),
        ("Harry Potter", "SE", "Cornish Pixie/Mandrake/Grindylow 3-Pack", "Summer Convention", "high", 135),
        ("Harry Potter", "01", "Harry Potter with Hedwig (Original, Retired)", "", "high", 120),
        ("Harry Potter", "61", "Moaning Myrtle", "SDCC 2018", "high", 120),
        ("Harry Potter", "64", "Basilisk (6-Inch)", "SDCC 2020", "high", 180),
        ("Harry Potter", "24", "Hagrid w/ Dragon (6-Inch)", "SDCC 2016", "high", 250),
        ("Harry Potter", "22", "Aragog (6-Inch)", "Fall Convention", "high", 110),
        ("Harry Potter", "21", "Fluffy (6-Inch)", "SDCC 2020", "high", 150),
        # Mid-range collectibles
        ("Harry Potter", "67", "Sirius Black Azkaban (Chase)", "", "mid", 72),
        ("Harry Potter", "SE", "Fred & George Weasley 2-Pack", "BAM", "mid", 70),
        ("Harry Potter", "107", "Nymphadora Tonks", "ECCC", "mid", 55),
        ("Harry Potter", "85", "Glow-in-the-Dark Voldemort", "", "mid", 50),
        ("Harry Potter", "02", "Ron Weasley", "", "mid", 35),
        ("Harry Potter", "07", "Hagrid (6-Inch)", "", "mid", 40),
        ("Harry Potter", "13", "Draco Malfoy", "", "mid", 35),
        ("Harry Potter", "35", "Bellatrix Lestrange", "", "mid", 45),
        ("Harry Potter", "36", "Lucius Malfoy", "", "mid", 40),
        ("Harry Potter", "37", "Professor McGonagall", "", "mid", 35),
        ("Harry Potter", "38", "Mad-Eye Moody", "", "mid", 45),
        ("Harry Potter", "90", "Cedric Diggory (Yule Ball)", "", "mid", 35),
        ("Harry Potter", "62", "Nearly Headless Nick (Glow)", "", "mid", 55),
        ("Harry Potter", "49", "Remus Lupin Werewolf", "", "mid", 45),
        ("Harry Potter", "48", "Peter Pettigrew", "", "mid", 35),
        ("Harry Potter", "104", "Buckbeak", "", "mid", 40),
        ("Harry Potter", "87", "Fawkes", "", "mid", 35),
        ("Harry Potter", "17", "Dobby (Sock)", "", "mid", 45),
        ("Harry Potter", "47", "Luna with Lion Head", "Hot Topic", "mid", 50),
        ("Harry Potter", "17", "Thestral (Rides)", "", "mid", 45),
        ("Harry Potter", "81", "Hungarian Horntail (6-Inch)", "", "mid", 55),
        ("Harry Potter", "52", "Snape as Boggart Neville", "", "mid", 40),
        ("Harry Potter", "112", "Harry w/ Invisibility Cloak", "BoxLunch", "mid", 45),
        ("Harry Potter", "43", "Hermione w/ Time Turner", "", "mid", 30),
        # Standard
        ("Harry Potter", "22", "Neville Longbottom", "", "standard", 20),
        ("Harry Potter", "46", "Ginny Weasley", "", "standard", 18),
        ("Harry Potter", "76", "Hedwig", "", "standard", 25),
        ("Harry Potter", "91", "Harry Potter (Yule Ball)", "", "standard", 18),
        ("Harry Potter", "83", "Hermione (Yule Ball)", "", "standard", 15),
        ("Harry Potter", "96", "Ron (Yule Ball)", "", "standard", 15),
        ("Harry Potter", "115", "Dumbledore (Michael Gambon)", "", "standard", 20),
        ("Harry Potter", "115", "Dumbledore w/ Baby Harry", "", "mid", 35),
        ("Harry Potter", "18", "Dementor", "", "standard", 20),
        # Fantastic Beasts crossover
        ("Fantastic Beasts", "01", "Newt Scamander", "", "standard", 15),
        ("Fantastic Beasts", "08", "Niffler", "", "standard", 15),
        ("Fantastic Beasts", "16", "Grindelwald", "", "standard", 18),
        ("Fantastic Beasts", "11", "Demiguise", "", "mid", 30),
        ("Fantastic Beasts", "04", "Albus Dumbledore", "", "standard", 15),

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

        # ── Lord of the Rings (50) ────────────────────────────────────────
        # Grails & high-value
        ("Lord of the Rings", "SE", "Bilbo Baggins (Spider Webs)", "", "grail", 720),
        ("Lord of the Rings", "448", "Balrog (Glow)", "NYCC 2017", "high", 380),
        ("Lord of the Rings", "SE", "Legolas Greenleaf (Blue Eyes)", "", "high", 330),
        ("Lord of the Rings", "SE", "Aragorn & Arwen 2-Pack", "SDCC 2017 / B&N", "high", 310),
        ("Lord of the Rings", "444", "Frodo Baggins (Chase - Glow Phial)", "", "high", 120),
        ("Lord of the Rings", "124", "Smaug (6-Inch, Gold)", "Hot Topic", "high", 200),
        # Mid-range
        ("Lord of the Rings", "SE", "Invisible Frodo Baggins", "", "mid", 90),
        ("Lord of the Rings", "532", "Gollum", "B&N", "mid", 80),
        ("Lord of the Rings", "449", "Twilight Ringwraith", "Hot Topic", "mid", 70),
        ("Lord of the Rings", "631", "Galadriel (Tempted)", "", "mid", 60),
        ("Lord of the Rings", "632", "Witch King", "", "mid", 50),
        ("Lord of the Rings", "529", "Treebeard (6-Inch)", "", "mid", 50),
        ("Lord of the Rings", "122", "Sauron", "", "mid", 40),
        ("Lord of the Rings", "448", "Balrog", "", "mid", 45),
        ("Lord of the Rings", "SE", "Gollum (Original)", "", "mid", 35),
        ("Lord of the Rings", "534", "King Aragorn", "", "mid", 35),
        ("Lord of the Rings", "63", "Witch-King on Fellbeast (Rides)", "", "mid", 65),
        ("Lord of the Rings", "12", "Bilbo Baggins (Hobbit)", "", "mid", 35),
        ("Lord of the Rings", "13", "Thorin Oakenshield (Hobbit)", "", "mid", 35),
        ("Lord of the Rings", "14", "Azog (Hobbit)", "", "mid", 35),
        ("Lord of the Rings", "15", "Tauriel (Hobbit)", "", "mid", 30),
        ("Lord of the Rings", "46", "Legolas (Hobbit)", "", "mid", 30),
        ("Lord of the Rings", "13", "Gandalf (Hat)", "", "mid", 40),
        ("Lord of the Rings", "SE", "Gimli (Glow Chase)", "", "mid", 55),
        ("Lord of the Rings", "SE", "Mouth of Sauron", "", "mid", 45),
        ("Lord of the Rings", "SE", "Shelob", "", "mid", 35),
        # Standard
        ("Lord of the Rings", "443", "Gandalf", "", "standard", 25),
        ("Lord of the Rings", "444", "Frodo Baggins", "", "standard", 20),
        ("Lord of the Rings", "445", "Samwise Gamgee", "", "standard", 20),
        ("Lord of the Rings", "531", "Aragorn", "", "standard", 22),
        ("Lord of the Rings", "628", "Legolas", "", "standard", 18),
        ("Lord of the Rings", "629", "Gimli", "", "standard", 18),
        ("Lord of the Rings", "447", "Saruman", "", "standard", 20),
        ("Lord of the Rings", "533", "Lurtz", "", "standard", 20),
        ("Lord of the Rings", "446", "Nazgul", "", "standard", 20),
        ("Lord of the Rings", "530", "Pippin Took", "", "standard", 18),
        ("Lord of the Rings", "528", "Merry Brandybuck", "", "standard", 18),
        ("Lord of the Rings", "635", "Arwen", "", "standard", 20),
        ("Lord of the Rings", "636", "Eowyn", "", "standard", 20),
        ("Lord of the Rings", "630", "Boromir", "", "standard", 20),
        ("Lord of the Rings", "845", "Gandalf the White", "", "standard", 22),
        ("Lord of the Rings", "SE", "Gollum (LOTR S2)", "", "standard", 18),
        ("Lord of the Rings", "633", "Dunharrow King", "", "standard", 18),
        ("Lord of the Rings", "SE", "Mordor Orc", "", "standard", 18),
        ("Lord of the Rings", "SE", "Army of the Dead", "", "standard", 20),
        ("Lord of the Rings", "SE", "Smeagol", "", "standard", 18),
        ("Lord of the Rings", "SE", "Grishnakh", "", "standard", 18),
        ("Lord of the Rings", "635", "Elrond", "", "standard", 20),
        ("Lord of the Rings", "SE", "Deagol", "", "standard", 18),
        ("Lord of the Rings", "SE", "Faramir", "", "standard", 22),

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

        # ── Funko Soda Figures (10) ──────────────────────────────────────
        ("Vinyl Soda", "SE", "Batman (Chase Metallic Emerald)", "Common/Chase", "grail", 600),
        ("Vinyl Soda", "SE", "Boba Fett (Chase Flocked)", "Common/Chase", "high", 180),
        ("Vinyl Soda", "SE", "Spider-Man (Chase Glow Green)", "Common/Chase", "high", 200),
        ("Vinyl Soda", "SE", "Freddy Funko as Frankenstein (Chase)", "Funko Shop", "grail", 500),
        ("Vinyl Soda", "SE", "The Joker (Chase Metallic)", "Common/Chase", "high", 250),
        ("Vinyl Soda", "SE", "Darth Vader (Chase)", "Common/Chase", "high", 160),
        ("Vinyl Soda", "SE", "Teenage Mutant Ninja Turtles Shredder (Chase)", "Common/Chase", "high", 140),
        ("Vinyl Soda", "SE", "He-Man (Chase Glow)", "Common/Chase", "high", 175),
        ("Vinyl Soda", "SE", "Skeletor (Chase Metallic)", "Common/Chase", "high", 190),
        ("Vinyl Soda", "SE", "Willy Wonka (Chase)", "Common/Chase", "high", 130),

        # ── Funko Pop! Deluxe / Rides (10) ───────────────────────────────
        ("Pop! Rides", "SE", "Night King on Viserion (Glow)", "HBO Shop", "grail", 800),
        ("Pop! Rides", "18", "Daenerys on Drogon", "Hot Topic", "high", 150),
        ("Pop! Rides", "25", "Batman in Batmobile (1966 Classic)", "Target", "high", 180),
        ("Pop! Rides", "SE", "Ghost Rider on Motorcycle (Glow)", "PX Previews", "high", 250),
        ("Pop! Deluxe", "584", "Iron Man Mark I (Glow)", "PX Previews", "high", 200),
        ("Pop! Deluxe", "727", "Darth Vader on Throne", "GameStop", "mid", 75),
        ("Pop! Deluxe", "SE", "Avengers Assemble: Thor (Amazon Exclusive)", "Amazon", "high", 120),
        ("Pop! Deluxe", "SE", "Avengers Assemble: Hulk (Amazon Exclusive)", "Amazon", "high", 130),
        ("Pop! Rides", "SE", "Hagrid on Motorcycle (6-inch)", "NYCC 2019", "high", 200),
        ("Pop! Deluxe", "SE", "Star-Lord on Benatar Ship", "Amazon", "mid", 85),

        # ── Funko x Loungefly Exclusives (8) ─────────────────────────────
        ("Loungefly Exclusive", "SE", "Funko Pop! & Loungefly Bundle: Maleficent Dragon", "BoxLunch", "high", 250),
        ("Loungefly Exclusive", "SE", "Funko Pop! & Loungefly Bundle: Ursula", "Hot Topic", "high", 200),
        ("Loungefly Exclusive", "SE", "Funko Pop! & Loungefly Bundle: Stitch (Elvis)", "BoxLunch", "high", 180),
        ("Loungefly Exclusive", "SE", "Funko Pop! & Loungefly Bundle: Cruella De Vil", "Hot Topic", "high", 175),
        ("Loungefly Exclusive", "SE", "Funko Pop! & Loungefly Bundle: Ariel", "BoxLunch", "mid", 95),
        ("Loungefly Exclusive", "SE", "Funko Pop! & Loungefly Bundle: Grogu (The Child)", "Target", "high", 120),
        ("Loungefly Exclusive", "SE", "Funko Pop! & Loungefly Bundle: Hades (Glow)", "Hot Topic", "high", 160),
        ("Loungefly Exclusive", "SE", "Funko Pop! & Loungefly Bundle: Rapunzel", "BoxLunch", "mid", 85),

        # ── Convention Exclusives SDCC / NYCC (8) ────────────────────────
        ("Convention Exclusive", "SE", "Headless Ned Stark", "SDCC 2013", "grail", 2500),
        ("Convention Exclusive", "SE", "Skeletor (Metallic)", "SDCC 2013", "grail", 1800),
        ("Convention Exclusive", "SE", "Freddy Funko as The Flash", "SDCC 2016", "grail", 1200),
        ("Convention Exclusive", "SE", "Tony Stark (Holding Helmet)", "SDCC 2017", "high", 350),
        ("Convention Exclusive", "SE", "Conan O'Brien as Superman", "SDCC 2018", "grail", 600),
        ("Convention Exclusive", "SE", "Freddy Funko as Pennywise", "NYCC 2018", "grail", 900),
        ("Convention Exclusive", "SE", "The Mountain (Armored)", "SDCC 2017", "high", 400),
        ("Convention Exclusive", "SE", "Toucan Sam (Glow)", "SDCC 2020", "high", 300),

        # ── Funko Pop! Albums (7) ────────────────────────────────────────
        ("Pop! Albums", "01", "AC/DC: Back in Black", "", "mid", 45),
        ("Pop! Albums", "03", "Metallica: Metallica (Black Album)", "", "mid", 50),
        ("Pop! Albums", "05", "Jimi Hendrix: Are You Experienced", "", "mid", 55),
        ("Pop! Albums", "09", "Ozzy Osbourne: Diary of a Madman", "", "mid", 40),
        ("Pop! Albums", "17", "Tupac: 2Pacalypse Now", "", "mid", 65),
        ("Pop! Albums", "20", "Guns N' Roses: Appetite for Destruction", "", "mid", 55),
        ("Pop! Albums", "24", "Prince: Purple Rain (Metallic)", "FYE", "high", 120),

        # ── Funko Pop! Digital / NFT Redeemables (6) ─────────────────────
        ("Pop! Digital", "SE", "Freddy Funko (Legendary) Wave 1", "NFT Redemption", "grail", 1200),
        ("Pop! Digital", "SE", "Batman (Legendary) Physical", "NFT Redemption", "grail", 800),
        ("Pop! Digital", "SE", "Iron Man (Grail) Physical", "NFT Redemption", "grail", 700),
        ("Pop! Digital", "SE", "Teenage Mutant Ninja Turtles Set (Legendary)", "NFT Redemption", "grail", 950),
        ("Pop! Digital", "SE", "Power Rangers Megazord (Legendary)", "NFT Redemption", "high", 450),
        ("Pop! Digital", "SE", "Scooby-Doo (Legendary) Physical", "NFT Redemption", "high", 380),

        # ── Funko Pop! Trains (6) ────────────────────────────────────────
        ("Pop! Trains", "01", "Mickey Mouse Engine", "Disney Store", "high", 180),
        ("Pop! Trains", "02", "Donald Duck Tender", "Disney Store", "high", 150),
        ("Pop! Trains", "03", "Goofy Flatcar", "Disney Store", "mid", 95),
        ("Pop! Trains", "04", "Pluto Caboose", "Disney Store", "mid", 85),
        ("Pop! Trains", "05", "Minnie Mouse Holiday Engine", "Amazon", "high", 140),
        ("Pop! Trains", "10", "Nightmare Before Christmas: Jack Skellington Train", "Hot Topic", "high", 200),

        # === ROUND 5 — 700+ Expansion: Convention Exclusives, Funko Shop, Grails, Artist Series, Soda, Anime, Gold, Bitty Pops ===

        # ── SDCC 2024 Exclusives ────────────────────────────────────────────
        ("Convention Exclusive", "SE", "Freddy Funko as Darth Vader (SDCC 2024)", "SDCC 2024", "grail", 1500),
        ("Convention Exclusive", "SE", "Goku (Ultra Instinct, Metallic) (SDCC 2024)", "SDCC 2024", "high", 350),
        ("Convention Exclusive", "SE", "Batman (Hush, Glow) (SDCC 2024)", "SDCC 2024", "high", 280),
        ("Convention Exclusive", "SE", "Vegeta (Badman, Flocked) (SDCC 2024)", "SDCC 2024", "high", 250),
        ("Convention Exclusive", "SE", "Naruto (Baryon Mode, Glow) (SDCC 2024)", "SDCC 2024", "high", 320),
        ("Convention Exclusive", "SE", "Wolverine (Weapon X, Bloody) (SDCC 2024)", "SDCC 2024", "high", 200),
        ("Convention Exclusive", "SE", "Mechagodzilla (Metallic) (SDCC 2024)", "SDCC 2024", "high", 220),
        ("Convention Exclusive", "SE", "Freddy Funko as He-Man (SDCC 2024)", "SDCC 2024", "grail", 800),

        # ── NYCC 2024 Exclusives ────────────────────────────────────────────
        ("Convention Exclusive", "SE", "Spider-Man 2099 (Glow) (NYCC 2024)", "NYCC 2024", "high", 250),
        ("Convention Exclusive", "SE", "Vegito (Super Saiyan Blue, Metallic) (NYCC 2024)", "NYCC 2024", "high", 280),
        ("Convention Exclusive", "SE", "Joker (Killing Joke, B&W) (NYCC 2024)", "NYCC 2024", "high", 200),
        ("Convention Exclusive", "SE", "Demon Slayer Muzan (Glow) (NYCC 2024)", "NYCC 2024", "high", 300),
        ("Convention Exclusive", "SE", "Freddy Funko as Pennywise (Bloody) (NYCC 2024)", "NYCC 2024", "grail", 650),
        ("Convention Exclusive", "SE", "All Might (Weakened, Glow) (NYCC 2024)", "NYCC 2024", "high", 180),

        # ── Funko Shop Exclusives ───────────────────────────────────────────
        ("Funko Shop", "SE", "Freddy Funko (Samurai)", "Funko-Shop", "grail", 700),
        ("Funko Shop", "SE", "Freddy Funko (Space Robot, Blue)", "Funko-Shop", "grail", 550),
        ("Funko Shop", "SE", "Freddy Funko (Cuphead)", "Funko-Shop", "high", 400),
        ("Funko Shop", "SE", "Freddy Funko (Tuxedo, Gold)", "Funko-Shop", "high", 350),
        ("Funko Shop", "SE", "Bigfoot (Rainbow, Flocked)", "Funko-Shop", "high", 250),
        ("Funko Shop", "SE", "Zodiac Freddy Funko (Scorpio)", "Funko-Shop", "high", 180),
        ("Funko Shop", "SE", "Fantastik Plastik: Fin Du Chomp", "Funko-Shop", "mid", 95),

        # ── Grails (Holy Grails) ────────────────────────────────────────────
        ("A Clockwork Orange", "SE", "Alex DeLarge", "", "grail", 5500),
        ("Movies", "SE", "Headless Ned Stark (Bloody)", "SDCC 2013", "grail", 3500),
        ("Freddy Funko", "SE", "Freddy Funko as Jaime Lannister (Gold)", "SDCC 2014", "grail", 4000),
        ("Willy Wonka", "SE", "Willy Wonka (Golden Ticket)", "", "grail", 2200),
        ("Cereal Icons", "SE", "Count Chocula (Glow)", "", "grail", 1800),
        ("Cereal Icons", "SE", "Franken Berry (Metallic)", "", "grail", 1500),
        ("Monsters", "SE", "Creature from the Black Lagoon (Metallic)", "Gemini", "grail", 6000),

        # ── Artist Series ───────────────────────────────────────────────────
        ("Artist Series", "SE", "Mickey Mouse (Artist Series, Conductor)", "Amazon", "mid", 45),
        ("Artist Series", "SE", "Stitch (Artist Series, Tropical)", "Amazon", "mid", 48),
        ("Artist Series", "SE", "Jack Skellington (Artist Series, Neon)", "Amazon", "mid", 52),
        ("Artist Series", "SE", "Darth Vader (Artist Series, Bespin)", "Amazon", "mid", 55),
        ("Artist Series", "SE", "Spider-Man (Artist Series, Graffiti)", "Amazon", "mid", 50),
        ("Artist Series", "SE", "Batman (Artist Series, Jim Lee)", "Amazon", "mid", 58),

        # ── Funko Soda Figures ──────────────────────────────────────────────
        ("Vinyl Soda", "SE", "Teenage Mutant Ninja Turtles: Leonardo (Chase)", "Funko-Shop", "high", 120),
        ("Vinyl Soda", "SE", "Batman (Vintage, Chase)", "", "high", 150),
        ("Vinyl Soda", "SE", "Freddy Funko (Surfer, Chase)", "Funko-Shop", "high", 180),
        ("Vinyl Soda", "SE", "Spider-Man (Japanese TV, Chase)", "", "high", 130),
        ("Vinyl Soda", "SE", "Boba Fett (Vintage, Chase)", "", "high", 160),
        ("Vinyl Soda", "SE", "Wolverine (Classic, Chase)", "", "high", 110),
        ("Vinyl Soda", "SE", "Joker (Dark Knight, Chase)", "", "high", 140),
        ("Vinyl Soda", "SE", "Goku (Super Saiyan, Chase)", "", "high", 170),

        # ── Anime License Pops (Chainsaw Man, Jujutsu Kaisen) ───────────────
        ("Animation", "1680", "Denji (Chainsaw Man)", "", "mid", 35),
        ("Animation", "1681", "Power (Chainsaw Man)", "", "mid", 40),
        ("Animation", "1682", "Makima (Chainsaw Man)", "", "mid", 38),
        ("Animation", "1683", "Aki Hayakawa (Chainsaw Man)", "", "mid", 32),
        ("Animation", "1684", "Pochita (Chainsaw Man)", "", "mid", 45),
        ("Animation", "1685", "Pochita (Flocked) (Chainsaw Man)", "Hot Topic", "high", 120),
        ("Animation", "1690", "Yuji Itadori (Jujutsu Kaisen S2)", "", "mid", 35),
        ("Animation", "1691", "Satoru Gojo (Purple Hollow) (Jujutsu Kaisen)", "", "mid", 55),
        ("Animation", "1692", "Ryomen Sukuna (Jujutsu Kaisen)", "", "mid", 42),
        ("Animation", "1693", "Megumi Fushiguro (Jujutsu Kaisen)", "", "mid", 30),
        ("Animation", "1694", "Toji Fushiguro (Jujutsu Kaisen)", "Hot Topic", "mid", 65),
        ("Animation", "1695", "Gojo (Six Eyes, Glow) (Jujutsu Kaisen)", "Entertainment Earth", "high", 140),

        # ── Funko Gold Figures ──────────────────────────────────────────────
        ("Gold", "SE", "LeBron James (12-inch Gold, Chase)", "", "high", 180),
        ("Gold", "SE", "Stephen Curry (12-inch Gold)", "", "mid", 45),
        ("Gold", "SE", "Tom Brady (12-inch Gold, Chase)", "", "high", 150),
        ("Gold", "SE", "Snoop Dogg (12-inch Gold, Chase)", "", "high", 120),
        ("Gold", "SE", "Tupac Shakur (12-inch Gold)", "", "mid", 55),

        # ── Bitty Pops ──────────────────────────────────────────────────────
        ("Bitty Pop!", "SE", "Marvel 4-Pack: Spider-Man, Iron Man, Venom + Mystery", "", "standard", 15),
        ("Bitty Pop!", "SE", "Disney Villains 4-Pack: Maleficent, Ursula, Cruella + Mystery", "", "standard", 15),
        ("Bitty Pop!", "SE", "Star Wars 4-Pack: Darth Vader, Boba Fett, Stormtrooper + Mystery", "", "standard", 15),
        ("Bitty Pop!", "SE", "Harry Potter 4-Pack: Harry, Hermione, Ron + Mystery", "", "standard", 15),
        ("Bitty Pop!", "SE", "The Office 4-Pack: Michael, Dwight, Jim + Mystery", "", "standard", 15),
        ("Bitty Pop!", "SE", "Friends 4-Pack: Rachel, Monica, Phoebe + Mystery", "", "standard", 15),

        # === EXPANSION ROUND 6 — 24 new items to reach 700+ ===

        # ── SDCC 2025 Exclusives (+6) ─────────────────────────────────
        ("Convention Exclusive", "SE", "Freddy Funko as Saitama (SDCC 2025)", "SDCC 2025", "grail", 1200),
        ("Convention Exclusive", "SE", "Gojo Satoru (Infinite Void, Metallic) (SDCC 2025)", "SDCC 2025", "high", 350),
        ("Convention Exclusive", "SE", "Luffy Gear 5 (Glow) (SDCC 2025)", "SDCC 2025", "high", 300),
        ("Convention Exclusive", "SE", "Tanjiro Kamado (Sun Breathing, Metallic) (SDCC 2025)", "SDCC 2025", "high", 280),
        ("Convention Exclusive", "SE", "Freddy Funko as Vegeta (SDCC 2025)", "SDCC 2025", "grail", 900),
        ("Convention Exclusive", "SE", "Spider-Man 2099 (Across the Spider-Verse, Glow) (SDCC 2025)", "SDCC 2025", "high", 250),

        # ── NYCC 2025 Exclusives (+4) ─────────────────────────────────
        ("Convention Exclusive", "SE", "Toji Fushiguro (Bloody, Glow) (NYCC 2025)", "NYCC 2025", "high", 320),
        ("Convention Exclusive", "SE", "Denji (Chainsaw Devil Form, Metallic) (NYCC 2025)", "NYCC 2025", "high", 260),
        ("Convention Exclusive", "SE", "Sukuna (King of Curses, B&W) (NYCC 2025)", "NYCC 2025", "high", 290),
        ("Convention Exclusive", "SE", "Freddy Funko as Eren Yeager Founding Titan (NYCC 2025)", "NYCC 2025", "grail", 750),

        # ── Grails & Vintage (+4) ────────────────────────────────────
        ("Disney", "31", "Dumbo (Clown) (Metallic)", "SDCC 2013", "grail", 2800),
        ("Ad Icons", "SE", "Boo Berry (Metallic, Glow)", "", "grail", 2200),
        ("Movies", "SE", "The Joker (Bank Robber) (Dark Knight)", "", "grail", 1800),
        ("Ad Icons", "SE", "Tony the Tiger (Flocked, Glow)", "Funko Shop", "grail", 1500),

        # ── Anime Pops — New Licenses (+6) ───────────────────────────
        ("Animation", "1700", "Sung Jin-woo (Solo Leveling)", "", "mid", 42),
        ("Animation", "1701", "Igris (Solo Leveling)", "", "mid", 38),
        ("Animation", "1702", "Momo Ayase (Dandadan)", "", "mid", 35),
        ("Animation", "1703", "Okarun (Dandadan)", "", "mid", 40),
        ("Animation", "1704", "Frieren (Frieren: Beyond Journey's End)", "", "mid", 45),
        ("Animation", "1705", "Fern (Frieren: Beyond Journey's End)", "", "mid", 38),

        # ── Funko Soda — New Chases (+4) ─────────────────────────────
        ("Vinyl Soda", "SE", "Gojo (Six Eyes, Chase)", "", "high", 200),
        ("Vinyl Soda", "SE", "Denji (Chainsaw, Chase)", "", "high", 160),
        ("Vinyl Soda", "SE", "Luffy Gear 5 (Chase Glow)", "", "high", 190),
        ("Vinyl Soda", "SE", "Tanjiro (Hinokami Kagura, Chase)", "", "high", 170),
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
    catalog.extend(_batch_character_variants_2026())
    catalog.extend(_batch_expansion_2026_wave2())
    # Deduplicate by ('line', 'number', 'name') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["line"], item["number"], item["name"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)

    # Deduplicate by name (keep first occurrence)
    seen_names: set[str] = set()
    deduped: list[dict] = []
    for item in _deduped:
        key = item.get("name", "")
        if key not in seen_names:
            seen_names.add(key)
            deduped.append(item)

    return deduped


def _batch_character_variants_2026() -> list[dict]:
    """Batch — Character variant types: Chase, Flocked, GITD, Metallic,
    Diamond, Blacklight, Art Series, Die-Cast. ~100 items."""

    pops = [
        # ── Marvel: Iron Man Variants ────────────────────────────────────
        ("Marvel", "SE", "Iron Man (Chase, Helmet Up)", "", "high", 120),
        ("Marvel", "SE", "Iron Man (Flocked, Mark 50)", "BoxLunch", "mid", 55),
        ("Marvel", "SE", "Iron Man (Metallic, Infinity War)", "Funko-Shop", "high", 130),
        ("Marvel", "SE", "Iron Man (Blacklight)", "Target", "mid", 40),
        ("Marvel", "SE", "Iron Man (Die-Cast)", "Funko-Shop", "high", 180),
        ("Marvel", "SE", "Iron Man (Diamond Collection)", "Hot Topic", "mid", 50),

        # ── Marvel: Spider-Man Variants ──────────────────────────────────
        ("Marvel", "SE", "Spider-Man (Chase, Unmasked)", "", "high", 110),
        ("Marvel", "SE", "Spider-Man (Glow-in-Dark, Symbiote)", "Entertainment Earth", "high", 100),
        ("Marvel", "SE", "Spider-Man (Metallic, Classic)", "Funko-Shop", "high", 140),
        ("Marvel", "SE", "Spider-Man (Blacklight, Neon)", "Target", "mid", 45),
        ("Marvel", "SE", "Spider-Man (Diamond Collection)", "Hot Topic", "mid", 45),
        ("Marvel", "SE", "Spider-Man (Die-Cast)", "Funko-Shop", "high", 200),

        # ── Marvel: Deadpool Variants ────────────────────────────────────
        ("Marvel", "SE", "Deadpool (Chase, Unmasked)", "", "high", 100),
        ("Marvel", "SE", "Deadpool (Flocked)", "BoxLunch", "mid", 50),
        ("Marvel", "SE", "Deadpool (Metallic, X-Force)", "Funko-Shop", "high", 120),
        ("Marvel", "SE", "Deadpool (Blacklight)", "Target", "mid", 42),
        ("Marvel", "SE", "Deadpool (Diamond Collection)", "Hot Topic", "mid", 40),

        # ── Star Wars: Darth Vader Variants ──────────────────────────────
        ("Star Wars", "SE", "Darth Vader (Chase, Helmet Removed)", "", "high", 150),
        ("Star Wars", "SE", "Darth Vader (Metallic Chrome)", "Funko-Shop", "high", 200),
        ("Star Wars", "SE", "Darth Vader (Glow-in-Dark, Force Lightning)", "Funko-Shop", "high", 130),
        ("Star Wars", "SE", "Darth Vader (Diamond Collection)", "Hot Topic", "mid", 55),
        ("Star Wars", "SE", "Darth Vader (Die-Cast)", "Funko-Shop", "high", 220),
        ("Star Wars", "SE", "Darth Vader (Blacklight)", "Target", "mid", 60),

        # ── Star Wars: Mandalorian Variants ──────────────────────────────
        ("Star Wars", "SE", "The Mandalorian (Chase, Unmasked)", "", "high", 120),
        ("Star Wars", "SE", "The Mandalorian (Chrome, Beskar)", "Funko-Shop", "high", 140),
        ("Star Wars", "SE", "The Mandalorian (Glow-in-Dark)", "Funko-Shop", "mid", 55),
        ("Star Wars", "SE", "The Mandalorian (Diamond Collection)", "Hot Topic", "mid", 40),

        # ── Star Wars: Grogu Variants ────────────────────────────────────
        ("Star Wars", "SE", "Grogu (Chase, Force Lift)", "", "high", 100),
        ("Star Wars", "SE", "Grogu (Flocked)", "Funko-Shop", "high", 110),
        ("Star Wars", "SE", "Grogu (Diamond Collection)", "Hot Topic", "mid", 38),
        ("Star Wars", "SE", "Grogu (Glow-in-Dark, Using Force)", "Entertainment Earth", "mid", 55),

        # ── Disney: Mickey Mouse Variants ────────────────────────────────
        ("Disney", "SE", "Mickey Mouse (Chase, Conductor)", "", "high", 250),
        ("Disney", "SE", "Mickey Mouse (Glow-in-Dark, Sorcerer)", "BoxLunch", "high", 180),
        ("Disney", "SE", "Mickey Mouse (Diamond Collection)", "Hot Topic", "mid", 55),
        ("Disney", "SE", "Mickey Mouse (Metallic, Rainbow)", "Funko-Shop", "high", 160),
        ("Disney", "SE", "Mickey Mouse (Blacklight)", "Target", "mid", 50),

        # ── Disney: Stitch Variants ──────────────────────────────────────
        ("Disney", "SE", "Stitch (Glow-in-Dark, Alien)", "Funko-Shop", "mid", 65),
        ("Disney", "SE", "Stitch (Diamond Collection)", "Hot Topic", "mid", 50),
        ("Disney", "SE", "Stitch (Blacklight)", "Target", "mid", 55),
        ("Disney", "SE", "Stitch (Metallic, Blue Chrome)", "Funko-Shop", "high", 140),

        # ── Anime: Naruto Variants ───────────────────────────────────────
        ("Naruto", "SE", "Naruto (Chase, Nine-Tails Mode)", "", "high", 150),
        ("Naruto", "SE", "Naruto (Metallic, Sage Mode)", "SDCC 2023", "high", 200),
        ("Naruto", "SE", "Naruto (Glow-in-Dark, Rasengan)", "Entertainment Earth", "mid", 65),
        ("Naruto", "SE", "Naruto (Blacklight)", "Target", "mid", 55),

        # ── Anime: Goku Variants ─────────────────────────────────────────
        ("Dragon Ball Z", "SE", "Goku (Chase, Ultra Instinct Sign)", "", "high", 180),
        ("Dragon Ball Z", "SE", "Goku (Metallic, Super Saiyan Blue)", "SDCC 2022", "high", 250),
        ("Dragon Ball Z", "SE", "Goku (Glow-in-Dark, Kamehameha)", "Entertainment Earth", "mid", 70),
        ("Dragon Ball Z", "SE", "Goku (Diamond Collection)", "Hot Topic", "mid", 45),

        # ── Anime: Luffy Variants ────────────────────────────────────────
        ("One Piece", "SE", "Luffy (Chase, Gear Second)", "", "high", 130),
        ("One Piece", "SE", "Luffy (Metallic, Gear Five)", "Funko-Shop", "high", 180),
        ("One Piece", "SE", "Luffy (Glow-in-Dark, Red Hawk)", "Entertainment Earth", "mid", 60),

        # ── Anime: Deku Variants ─────────────────────────────────────────
        ("My Hero Academia", "SE", "Deku (Chase, Shoot Style)", "", "high", 140),
        ("My Hero Academia", "SE", "Deku (Metallic, Full Cowling)", "Funko-Shop", "high", 160),
        ("My Hero Academia", "SE", "Deku (Glow-in-Dark, One For All 100%)", "Entertainment Earth", "mid", 65),

        # ── DC: Batman Variants ──────────────────────────────────────────
        ("DC Heroes", "SE", "Batman (Chase, Unmasked Bruce Wayne)", "", "high", 180),
        ("DC Heroes", "SE", "Batman (Glow-in-Dark, Hush)", "Target", "mid", 55),
        ("DC Heroes", "SE", "Batman (Diamond Collection)", "Hot Topic", "mid", 45),
        ("DC Heroes", "SE", "Batman (Die-Cast, Black Chrome)", "Funko-Shop", "high", 250),
        ("DC Heroes", "SE", "Batman (Blacklight)", "Target", "mid", 50),
        ("DC Heroes", "SE", "Batman (Art Series, Jim Lee B&W)", "Target", "mid", 55),

        # ── DC: Joker Variants ───────────────────────────────────────────
        ("DC Heroes", "SE", "Joker (Chase, Unmasked Bank Robber)", "", "high", 200),
        ("DC Heroes", "SE", "Joker (Glow-in-Dark, Blacklight)", "Target", "mid", 60),
        ("DC Heroes", "SE", "Joker (Metallic, Classic)", "Funko-Shop", "high", 160),
        ("DC Heroes", "SE", "Joker (Diamond Collection)", "Hot Topic", "mid", 50),

        # ── Horror: Pennywise Variants ───────────────────────────────────
        ("Horror", "SE", "Pennywise (Chase, Sepia Toned)", "", "high", 120),
        ("Horror", "SE", "Pennywise (Glow-in-Dark, Deadlights)", "Funko-Shop", "high", 140),
        ("Horror", "SE", "Pennywise (Metallic, Blue Eyes)", "SDCC 2023", "high", 180),
        ("Horror", "SE", "Pennywise (Diamond Collection)", "Hot Topic", "mid", 50),

        # ── Horror: Michael Myers Variants ───────────────────────────────
        ("Horror", "SE", "Michael Myers (Chase, Unmasked)", "", "high", 250),
        ("Horror", "SE", "Michael Myers (Glow-in-Dark, Blood Splatter)", "Funko-Shop", "high", 200),
        ("Horror", "SE", "Michael Myers (Blacklight)", "Target", "mid", 65),

        # ── Horror: Ghostface Variants ───────────────────────────────────
        ("Horror", "SE", "Ghostface (Chase, Bloody)", "", "high", 120),
        ("Horror", "SE", "Ghostface (Glow-in-Dark)", "Funko-Shop", "mid", 65),
        ("Horror", "SE", "Ghostface (Diamond Collection)", "Hot Topic", "mid", 45),
        ("Horror", "SE", "Ghostface (Blacklight)", "Target", "mid", 55),

        # ── Movies: Marty McFly Variants ─────────────────────────────────
        ("Movies", "SE", "Marty McFly (Chase, Hazmat Suit)", "", "high", 150),
        ("Movies", "SE", "Marty McFly (Metallic, Guitar)", "Funko-Shop", "high", 180),
        ("Movies", "SE", "Marty McFly (Glow-in-Dark, Plutonium)", "Entertainment Earth", "mid", 65),

        # ── Convention Exclusives: SDCC Variants ─────────────────────────
        ("Convention Exclusive", "SE", "Iron Man (Mark 1, Metallic) (SDCC 2023)", "SDCC 2023", "high", 280),
        ("Convention Exclusive", "SE", "Spider-Man (Symbiote, Glow) (SDCC 2023)", "SDCC 2023", "high", 250),
        ("Convention Exclusive", "SE", "Batman (Knightfall, Metallic) (SDCC 2023)", "SDCC 2023", "high", 220),
        ("Convention Exclusive", "SE", "Goku (Kaioken, Glow) (SDCC 2023)", "SDCC 2023", "high", 300),

        # ── Convention Exclusives: NYCC Variants ─────────────────────────
        ("Convention Exclusive", "SE", "Deadpool (Pirate, Metallic) (NYCC 2023)", "NYCC 2023", "high", 180),
        ("Convention Exclusive", "SE", "Stitch (Elvis, Flocked) (NYCC 2023)", "NYCC 2023", "high", 220),
        ("Convention Exclusive", "SE", "Naruto (Baryon Mode, Metallic) (NYCC 2023)", "NYCC 2023", "high", 260),

        # ── Funko Shop Exclusives: Die-Cast ──────────────────────────────
        ("Funko Shop", "SE", "Spider-Man (Die-Cast, Red & Blue)", "Funko-Shop", "high", 190),
        ("Funko Shop", "SE", "Darth Vader (Die-Cast, Chrome)", "Funko-Shop", "high", 210),
        ("Funko Shop", "SE", "Iron Man (Die-Cast, Mark III)", "Funko-Shop", "high", 200),
        ("Funko Shop", "SE", "Batman (Die-Cast, Classic)", "Funko-Shop", "high", 220),
        ("Funko Shop", "SE", "Captain America (Die-Cast, Shield)", "Funko-Shop", "high", 190),

        # ── Blacklight Series ────────────────────────────────────────────
        ("Blacklight", "SE", "Venom (Blacklight)", "Target", "mid", 50),
        ("Blacklight", "SE", "Carnage (Blacklight)", "Target", "mid", 55),
        ("Blacklight", "SE", "Doctor Strange (Blacklight)", "Target", "mid", 48),
        ("Blacklight", "SE", "Captain America (Blacklight)", "Target", "mid", 45),
        ("Blacklight", "SE", "Thor (Blacklight)", "Target", "mid", 45),
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


def _batch_expansion_2026_wave2() -> list[dict]:
    """Wave 2 expansion — ~115 items: more Marvel, Star Wars, Anime, Music,
    TV, Games, Chase variants, and convention exclusives."""

    pops = [
        # ── Marvel: Deadpool Variants & New ─────────────────────────────
        ("Marvel", "546", "Deadpool (Thumbs Up)", "", "standard", 15),
        ("Marvel", "780", "Deadpool (Movie, Swords)", "", "mid", 35),
        ("Marvel", "543", "Deadpool (Rubber Ducky)", "Hot Topic", "mid", 50),
        ("Marvel", "786", "Deadpool 3 (Wolverine Suit)", "", "mid", 45),
        ("Marvel", "SE", "Deadpool (Glow, Headpool)", "Funko-Shop", "high", 160),

        # ── Marvel: Iron Man Expanded ───────────────────────────────────
        ("Marvel", "616", "Iron Man (MK85, Endgame)", "", "mid", 40),
        ("Marvel", "467", "Iron Man (MK39, Gemini)", "Funko-Shop", "high", 180),
        ("Marvel", "338", "Iron Man (MK43, Chrome)", "SDCC 2016", "high", 200),
        ("Marvel", "962", "Iron Man (Model Prime)", "", "mid", 35),

        # ── Marvel: Black Panther Expanded ──────────────────────────────
        ("Marvel", "273", "Black Panther", "", "standard", 15),
        ("Marvel", "274", "Black Panther (Unmasked)", "", "standard", 18),
        ("Marvel", "612", "Black Panther (Wakanda Forever, Glow)", "Target", "high", 100),
        ("Marvel", "1113", "Shuri (Black Panther 2)", "", "standard", 14),
        ("Marvel", "SE", "Black Panther (Purple Glow)", "Entertainment Earth", "high", 130),
        ("Marvel", "SE", "Killmonger (Gold Jaguar)", "Walmart", "mid", 55),

        # ── Star Wars: Mandalorian Expanded ─────────────────────────────
        ("Star Wars", "345", "The Mandalorian (Flying)", "GameStop", "mid", 40),
        ("Star Wars", "584", "Bo-Katan Kryze", "", "standard", 15),
        ("Star Wars", "664", "Paz Vizsla", "", "mid", 35),
        ("Star Wars", "SE", "Din Djarin (Darksaber, Glow)", "Funko-Shop", "high", 120),
        ("Star Wars", "SE", "Moff Gideon (Dark Trooper Suit)", "", "mid", 30),

        # ── Star Wars: Ahsoka Expanded ──────────────────────────────────
        ("Star Wars", "496", "Ahsoka (Rebels)", "", "mid", 45),
        ("Star Wars", "1608", "Ahsoka (Live Action, Dual Sabers)", "", "standard", 18),
        ("Star Wars", "SE", "Ahsoka (Fulcrum, Glow Sabers)", "Funko-Shop", "high", 160),
        ("Star Wars", "SE", "Baylan Skoll (Lightsaber)", "", "mid", 25),
        ("Star Wars", "SE", "Sabine Wren (Ahsoka Series)", "", "standard", 18),

        # ── Anime: Dragon Ball Expanded ─────────────────────────────────
        ("Dragon Ball Z", "1089", "Vegeta (Final Flash)", "", "mid", 35),
        ("Dragon Ball Z", "SE", "Cell (Perfect Form, Metallic)", "Funko-Shop", "high", 140),
        ("Dragon Ball Super", "1292", "Goku Black (Rose, Glow)", "Entertainment Earth", "mid", 55),
        ("Dragon Ball Super", "SE", "Beerus (Metallic)", "SDCC 2016", "high", 250),
        ("Dragon Ball Z", "SE", "Majin Buu (Chocolate)", "Hot Topic", "mid", 65),
        ("Dragon Ball Z", "SE", "Piccolo (Metallic)", "NYCC 2019", "high", 180),

        # ── Anime: Naruto Expanded ──────────────────────────────────────
        ("Naruto", "SE", "Madara Uchiha (Reanimation Glow)", "Funko-Shop", "high", 170),
        ("Naruto", "1500", "Obito Uchiha", "", "mid", 35),
        ("Naruto", "SE", "Gaara (Sand Coffin)", "", "mid", 40),
        ("Naruto", "SE", "Rock Lee (Drunken Fist)", "Hot Topic", "mid", 50),
        ("Naruto", "SE", "Hinata Hyuga (Twin Lion Fists)", "BoxLunch", "mid", 45),

        # ── Anime: Demon Slayer Expanded ────────────────────────────────
        ("Demon Slayer", "SE", "Mitsuri Kanroji (Love Breathing)", "", "mid", 30),
        ("Demon Slayer", "SE", "Shinobu Kocho (Butterfly Dance)", "Hot Topic", "mid", 45),
        ("Demon Slayer", "SE", "Tengen Uzui (Sound Breathing, Glow)", "Funko-Shop", "high", 120),
        ("Demon Slayer", "1534", "Zenitsu (Godspeed)", "", "mid", 35),
        ("Demon Slayer", "SE", "Upper Moon Three Akaza (Battle, Metallic)", "SDCC 2024", "high", 200),
        ("Demon Slayer", "SE", "Kokushibo (Upper Moon One)", "", "mid", 40),

        # ── Music: BTS ──────────────────────────────────────────────────
        ("Rocks", "SE", "BTS - RM", "", "mid", 35),
        ("Rocks", "SE", "BTS - Jin", "", "mid", 35),
        ("Rocks", "SE", "BTS - Suga", "", "mid", 35),
        ("Rocks", "SE", "BTS - J-Hope", "", "mid", 35),
        ("Rocks", "SE", "BTS - Jimin", "", "mid", 40),
        ("Rocks", "SE", "BTS - V", "", "mid", 40),
        ("Rocks", "SE", "BTS - Jung Kook", "", "mid", 45),

        # ── Music: Expanded Legends ─────────────────────────────────────
        ("Rocks", "SE", "Freddie Mercury (Radio Gaga)", "", "mid", 40),
        ("Rocks", "SE", "Tupac (Thug Life, Metallic)", "Funko-Shop", "high", 120),
        ("Rocks", "SE", "Post Malone", "", "standard", 15),
        ("Rocks", "SE", "Billie Eilish (Bad Guy)", "", "standard", 18),
        ("Rocks", "SE", "Dolly Parton (Diamond)", "Hot Topic", "mid", 45),
        ("Rocks", "SE", "Ozzy Osbourne (Diary of a Madman)", "", "mid", 35),

        # ── TV: Stranger Things Expanded ────────────────────────────────
        ("Stranger Things", "SE", "Argyle", "", "standard", 15),
        ("Stranger Things", "SE", "Will Byers (Upside Down)", "Hot Topic", "mid", 55),
        ("Stranger Things", "SE", "Eleven (Season 5, Buzzcut)", "", "mid", 30),
        ("Stranger Things", "SE", "Brenner (Dr. Martin)", "", "standard", 20),

        # ── TV: The Office Expanded ─────────────────────────────────────
        ("The Office", "SE", "Stanley Hudson (Pretzel Day)", "Hot Topic", "mid", 45),
        ("The Office", "SE", "Toby Flenderson", "", "standard", 12),
        ("The Office", "SE", "Ryan Howard (Blonde)", "", "standard", 14),
        ("The Office", "SE", "Kelly Kapoor", "", "standard", 12),

        # ── TV: Friends Expanded ────────────────────────────────────────
        ("Friends", "SE", "Rachel (Fashion, Glow)", "BoxLunch", "mid", 40),
        ("Friends", "SE", "Joey (Porsche)", "Funko-Shop", "mid", 35),
        ("Friends", "SE", "Ross (Pivot, Couch)", "", "mid", 30),
        ("Friends", "SE", "Phoebe (Lobster)", "", "mid", 30),

        # ── Games: Fortnite ─────────────────────────────────────────────
        ("Fortnite", "SE", "Skull Trooper (Purple Glow)", "Walmart", "mid", 50),
        ("Fortnite", "SE", "Peely", "", "standard", 15),
        ("Fortnite", "SE", "Raven (Metallic)", "GameStop", "mid", 40),
        ("Fortnite", "SE", "Midas (Gold, Rex)", "SDCC 2021", "high", 130),
        ("Fortnite", "SE", "Drift", "", "standard", 18),

        # ── Games: Overwatch Expanded ───────────────────────────────────
        ("Overwatch", "SE", "Genji (Carbon Fiber)", "ThinkGeek", "mid", 50),
        ("Overwatch", "SE", "Mercy (Cobalt, Glow)", "Blizzard", "high", 120),
        ("Overwatch", "SE", "Reaper (Hellfire)", "BoxLunch", "mid", 45),
        ("Overwatch", "SE", "Sigma", "", "standard", 15),

        # ── Games: FNAF ─────────────────────────────────────────────────
        ("FNAF", "106", "Foxy the Pirate", "", "mid", 35),
        ("FNAF", "107", "Bonnie", "", "mid", 30),
        ("FNAF", "128", "Springtrap (Flocked)", "GameStop", "mid", 55),
        ("FNAF", "291", "Nightmare Freddy", "", "mid", 30),
        ("FNAF", "SE", "Golden Freddy (Glow)", "SDCC 2016", "high", 200),

        # ── Convention Exclusives: ECCC ─────────────────────────────────
        ("Convention Exclusive", "SE", "Deadpool (Mermaid) (ECCC 2016)", "ECCC 2016", "high", 180),
        ("Convention Exclusive", "SE", "Boba Fett (Vintage, Flocked) (ECCC 2024)", "ECCC 2024", "high", 220),
        ("Convention Exclusive", "SE", "Goku (Spirit Bomb, Glow) (ECCC 2024)", "ECCC 2024", "high", 250),
        ("Convention Exclusive", "SE", "Naruto (Rasengan, Metallic) (ECCC 2025)", "ECCC 2025", "high", 200),
        ("Convention Exclusive", "SE", "Batman (Azrael Suit) (ECCC 2025)", "ECCC 2025", "high", 180),

        # ── Convention Exclusives: SDCC/NYCC Missing ────────────────────
        ("Convention Exclusive", "SE", "Wolverine (Brown Suit, Flocked) (SDCC 2022)", "SDCC 2022", "high", 200),
        ("Convention Exclusive", "SE", "Stitch (Hawaiian, Metallic) (SDCC 2022)", "SDCC 2022", "high", 250),
        ("Convention Exclusive", "SE", "Kakashi (Double Sharingan) (NYCC 2024)", "NYCC 2024", "high", 230),
        ("Convention Exclusive", "SE", "Toga Himiko (Villain, Glow) (NYCC 2024)", "NYCC 2024", "high", 190),

        # ── Chase Variants: TV & Movies ─────────────────────────────────
        ("Stranger Things", "SE", "Vecna (Chase, Glow Vines)", "", "high", 120),
        ("Stranger Things", "SE", "Eddie Munson (Chase, Guitar Solo)", "", "high", 140),
        ("The Office", "SE", "Prison Mike (Chase, Dementor)", "", "high", 180),
        ("Friends", "SE", "Monica (Chase, Turkey Head GITD)", "", "high", 100),

        # ── Chase Variants: Anime ───────────────────────────────────────
        ("Jujutsu Kaisen", "SE", "Sukuna (Chase, Domain Expansion)", "", "high", 180),
        ("Jujutsu Kaisen", "SE", "Megumi (Mahoraga Summon, Glow)", "Hot Topic", "mid", 50),
        ("Jujutsu Kaisen", "SE", "Toji Fushiguro", "", "mid", 35),
        ("One Piece", "SE", "Zoro (Enma Sword, Metallic)", "Funko-Shop", "high", 150),
        ("One Piece", "SE", "Kaido (Dragon Form, 6-Inch)", "", "mid", 55),

        # ── Anime: Spy x Family ─────────────────────────────────────────
        ("Spy x Family", "SE", "Yor Forger (Thorn Princess)", "", "mid", 35),
        ("Spy x Family", "SE", "Anya Forger (School Uniform)", "", "standard", 18),
        ("Spy x Family", "SE", "Loid Forger (Twilight)", "", "standard", 20),

        # ── Jujutsu Kaisen (10) ─────────────────────────────────────────
        ("Jujutsu Kaisen", "1116", "Gojo (Infinite Void)", "Hot Topic", "mid", 55),
        ("Jujutsu Kaisen", "1117", "Sukuna (King of Curses)", "", "mid", 40),
        ("Jujutsu Kaisen", "1118", "Itadori (Black Flash)", "BoxLunch", "mid", 50),
        ("Jujutsu Kaisen", "SE", "Gojo (Hollow Purple, Glow)", "Funko Shop", "high", 180),
        ("Jujutsu Kaisen", "SE", "Sukuna (Domain Expansion)", "SDCC 2024", "high", 250),
        ("Jujutsu Kaisen", "SE", "Megumi Fushiguro (Mahoraga)", "Funko Shop", "high", 120),
        ("Jujutsu Kaisen", "SE", "Nobara Kugisaki", "", "standard", 18),
        ("Jujutsu Kaisen", "SE", "Maki Zenin", "", "standard", 18),
        ("Jujutsu Kaisen", "SE", "Geto (Suguru)", "", "standard", 20),

        # ── Demon Slayer Expansion (8) ───────────────────────────────────
        ("Demon Slayer", "1040", "Rengoku (Ninth Form, Metallic)", "BoxLunch", "high", 120),
        ("Demon Slayer", "SE", "Muzan Kibutsuji", "", "mid", 30),
        ("Demon Slayer", "SE", "Akaza (Upper Moon Three)", "", "mid", 35),
        ("Demon Slayer", "SE", "Tengen Uzui (Sound Breathing)", "Funko Shop", "high", 100),
        ("Demon Slayer", "SE", "Mitsuri Kanroji (Love Breathing)", "Hot Topic", "mid", 55),
        ("Demon Slayer", "SE", "Giyu Tomioka (Water Breathing)", "BoxLunch", "mid", 60),
        ("Demon Slayer", "SE", "Zenitsu (Thunderclap Flash, Glow)", "Special Edition", "high", 150),
        ("Demon Slayer", "SE", "Daki & Gyutaro 2-Pack", "NYCC 2024", "high", 130),

        # ── Solo Leveling / Dandadan / Newer Anime (8) ──────────────────
        ("Solo Leveling", "SE", "Sung Jin-Woo (Arise)", "Funko Shop", "high", 120),
        ("Solo Leveling", "SE", "Shadow Monarch Sung Jin-Woo", "SDCC 2025", "high", 200),
        ("Solo Leveling", "SE", "Igris", "", "mid", 40),
        ("Dandadan", "SE", "Okarun (Turbo Granny Form)", "BoxLunch", "mid", 55),
        ("Dandadan", "SE", "Momo Ayase", "", "standard", 18),
        ("Kaiju No. 8", "SE", "Kafka Hibino (Kaiju Form)", "Hot Topic", "mid", 50),
        ("Kaiju No. 8", "SE", "Mina Ashiro", "", "standard", 18),
        ("Frieren", "SE", "Frieren (Beyond Journey's End)", "", "mid", 30),

        # ── One Piece Expansion (6) ─────────────────────────────────────
        ("One Piece", "SE", "Luffy (Gear 5, Glow)", "Funko Shop", "high", 180),
        ("One Piece", "SE", "Zoro (Enma, Metallic)", "BoxLunch", "high", 110),
        ("One Piece", "SE", "Shanks (Red Hair)", "", "mid", 55),
        ("One Piece", "SE", "Kaido (Dragon Form, 6-Inch)", "Funko Shop", "high", 200),
        ("One Piece", "SE", "Boa Hancock", "", "mid", 35),
        ("One Piece", "SE", "Ace (Fire Fist)", "Hot Topic", "mid", 60),

        # ── Music: BTS Metallic ─────────────────────────────────────────
        ("Rocks", "SE", "BTS - Butter Complete Set (7-Pack, Metallic)", "Funko-Shop", "grail", 400),

        # ── Disney: Villains Expanded ───────────────────────────────────
        ("Disney Villains", "SE", "Hades (Glow, Blue Flame)", "Hot Topic", "mid", 55),
        ("Disney Villains", "SE", "Jafar (Snake Form, Glow)", "BoxLunch", "mid", 45),

        # ── TV: Breaking Bad ────────────────────────────────────────────
        ("Television", "158", "Walter White (Hazmat Suit, Blue Crystal)", "SDCC 2014", "grail", 1000),
        ("Television", "SE", "Jesse Pinkman (Cook Suit)", "", "mid", 55),

        # ── Games: Pokemon Expanded ─────────────────────────────────────
        ("Pokemon", "SE", "Gengar (Glow, Purple)", "Entertainment Earth", "mid", 45),
        ("Pokemon", "SE", "Gyarados (Metallic)", "Funko-Shop", "high", 130),
        ("Pokemon", "SE", "Dragonite (Flocked)", "Hot Topic", "mid", 40),

        # ── Star Trek (25) ───────────────────────────────────────────────
        ("Star Trek", "01", "Captain Kirk", "", "mid", 45),
        ("Star Trek", "02", "Spock", "", "mid", 55),
        ("Star Trek", "03", "Uhura", "", "mid", 35),
        ("Star Trek", "04", "Scotty", "", "standard", 25),
        ("Star Trek", "05", "McCoy", "", "standard", 25),
        ("Star Trek", "06", "Klingon", "", "standard", 20),
        ("Star Trek", "SE", "Captain Kirk (Mirror Mirror)", "GameStop", "high", 120),
        ("Star Trek", "SE", "Spock (Mirror Mirror)", "GameStop", "high", 100),
        ("Star Trek TNG", "188", "Captain Picard", "", "mid", 40),
        ("Star Trek TNG", "189", "Commander Riker", "", "standard", 20),
        ("Star Trek TNG", "190", "Data", "", "mid", 35),
        ("Star Trek TNG", "191", "Worf", "", "mid", 30),
        ("Star Trek TNG", "SE", "Locutus of Borg", "Exclusive", "high", 150),
        ("Star Trek TNG", "SE", "Q", "Exclusive", "mid", 65),
        ("Star Trek TNG", "SE", "Guinan", "", "standard", 18),
        ("Star Trek TNG", "SE", "Geordi La Forge", "", "standard", 18),
        ("Star Trek TNG", "SE", "Deanna Troi", "", "standard", 18),
        ("Star Trek", "SE", "Khan Noonien Singh", "", "mid", 40),
        ("Star Trek", "SE", "Gorn", "Exclusive", "high", 110),
        ("Star Trek DS9", "SE", "Captain Sisko", "", "standard", 22),
        ("Star Trek Voyager", "SE", "Captain Janeway", "", "mid", 35),
        ("Star Trek Voyager", "SE", "Seven of Nine", "", "mid", 40),
        ("Star Trek", "SE", "Spock (Metallic)", "SDCC 2013", "grail", 500),
        ("Star Trek", "SE", "Captain Kirk (Gold)", "Funko Shop", "high", 200),
        ("Star Trek", "SE", "Borg Queen", "", "mid", 45),
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
