-- Seed data for category_items taxonomy
-- Includes: Pokemon Base Set holos, MTG Power 9, Funko grails

-- ─────────────────────────────────────────────────────────────────────────────
-- Pokemon Base Set - 16 Holo Rares
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO public.category_items (category, set_code, item_key, title, brand, rarity, notes) VALUES
  ('pokemon', 'base-set', 'alakazam-holo', 'Alakazam (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #1/102'),
  ('pokemon', 'base-set', 'blastoise-holo', 'Blastoise (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #2/102'),
  ('pokemon', 'base-set', 'chansey-holo', 'Chansey (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #3/102'),
  ('pokemon', 'base-set', 'charizard-holo', 'Charizard (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #4/102 - Most sought after'),
  ('pokemon', 'base-set', 'clefairy-holo', 'Clefairy (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #5/102'),
  ('pokemon', 'base-set', 'gyarados-holo', 'Gyarados (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #6/102'),
  ('pokemon', 'base-set', 'hitmonchan-holo', 'Hitmonchan (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #7/102'),
  ('pokemon', 'base-set', 'machamp-holo', 'Machamp (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #8/102 - 1st Ed only in theme deck'),
  ('pokemon', 'base-set', 'magneton-holo', 'Magneton (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #9/102'),
  ('pokemon', 'base-set', 'mewtwo-holo', 'Mewtwo (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #10/102'),
  ('pokemon', 'base-set', 'nidoking-holo', 'Nidoking (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #11/102'),
  ('pokemon', 'base-set', 'ninetales-holo', 'Ninetales (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #12/102'),
  ('pokemon', 'base-set', 'poliwrath-holo', 'Poliwrath (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #13/102'),
  ('pokemon', 'base-set', 'raichu-holo', 'Raichu (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #14/102'),
  ('pokemon', 'base-set', 'venusaur-holo', 'Venusaur (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #15/102'),
  ('pokemon', 'base-set', 'zapdos-holo', 'Zapdos (Holo)', 'Pokemon TCG', 'Holo Rare', 'Base Set #16/102')
ON CONFLICT (category, item_key) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- MTG Alpha/Beta Power 9
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO public.category_items (category, set_code, item_key, title, brand, rarity, notes) VALUES
  ('mtg', 'alpha-beta', 'black-lotus', 'Black Lotus', 'Magic: The Gathering', 'Rare', 'Power 9 - The most valuable MTG card'),
  ('mtg', 'alpha-beta', 'ancestral-recall', 'Ancestral Recall', 'Magic: The Gathering', 'Rare', 'Power 9 - Blue instant'),
  ('mtg', 'alpha-beta', 'time-walk', 'Time Walk', 'Magic: The Gathering', 'Rare', 'Power 9 - Extra turn'),
  ('mtg', 'alpha-beta', 'timetwister', 'Timetwister', 'Magic: The Gathering', 'Rare', 'Power 9 - Wheel effect'),
  ('mtg', 'alpha-beta', 'mox-pearl', 'Mox Pearl', 'Magic: The Gathering', 'Rare', 'Power 9 - White mana'),
  ('mtg', 'alpha-beta', 'mox-sapphire', 'Mox Sapphire', 'Magic: The Gathering', 'Rare', 'Power 9 - Blue mana'),
  ('mtg', 'alpha-beta', 'mox-jet', 'Mox Jet', 'Magic: The Gathering', 'Rare', 'Power 9 - Black mana'),
  ('mtg', 'alpha-beta', 'mox-ruby', 'Mox Ruby', 'Magic: The Gathering', 'Rare', 'Power 9 - Red mana'),
  ('mtg', 'alpha-beta', 'mox-emerald', 'Mox Emerald', 'Magic: The Gathering', 'Rare', 'Power 9 - Green mana')
ON CONFLICT (category, item_key) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- MTG Reserved List Highlights
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO public.category_items (category, set_code, item_key, title, brand, rarity, notes) VALUES
  ('mtg', 'legends', 'tabernacle', 'The Tabernacle at Pendrell Vale', 'Magic: The Gathering', 'Rare', 'Reserved List - Lands matter'),
  ('mtg', 'urza-saga', 'gaeas-cradle', 'Gaea''s Cradle', 'Magic: The Gathering', 'Rare', 'Reserved List - Commander staple'),
  ('mtg', 'stronghold', 'mox-diamond', 'Mox Diamond', 'Magic: The Gathering', 'Rare', 'Reserved List - Fast mana'),
  ('mtg', 'mirage', 'lions-eye-diamond', 'Lion''s Eye Diamond', 'Magic: The Gathering', 'Rare', 'Reserved List - LED combo piece'),
  ('mtg', 'revised', 'underground-sea', 'Underground Sea', 'Magic: The Gathering', 'Rare', 'Dual Land - UB'),
  ('mtg', 'revised', 'volcanic-island', 'Volcanic Island', 'Magic: The Gathering', 'Rare', 'Dual Land - UR'),
  ('mtg', 'revised', 'tropical-island', 'Tropical Island', 'Magic: The Gathering', 'Rare', 'Dual Land - UG'),
  ('mtg', 'revised', 'tundra', 'Tundra', 'Magic: The Gathering', 'Rare', 'Dual Land - WU'),
  ('mtg', 'revised', 'savannah', 'Savannah', 'Magic: The Gathering', 'Rare', 'Dual Land - WG'),
  ('mtg', 'revised', 'scrubland', 'Scrubland', 'Magic: The Gathering', 'Rare', 'Dual Land - WB'),
  ('mtg', 'revised', 'bayou', 'Bayou', 'Magic: The Gathering', 'Rare', 'Dual Land - BG'),
  ('mtg', 'revised', 'badlands', 'Badlands', 'Magic: The Gathering', 'Rare', 'Dual Land - BR'),
  ('mtg', 'revised', 'taiga', 'Taiga', 'Magic: The Gathering', 'Rare', 'Dual Land - RG'),
  ('mtg', 'revised', 'plateau', 'Plateau', 'Magic: The Gathering', 'Rare', 'Dual Land - WR')
ON CONFLICT (category, item_key) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- Funko Pop Grails
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO public.category_items (category, set_code, item_key, title, brand, rarity, notes) VALUES
  ('funko', 'sdcc-2010', 'metallic-blue-batman', 'Metallic Blue Batman #01', 'Funko Pop', 'SDCC Exclusive', 'SDCC 2010 - Only 480 made'),
  ('funko', 'paris-cc', 'holo-darth-maul', 'Holographic Darth Maul', 'Funko Pop', 'Convention Exclusive', 'Paris Comic Con exclusive'),
  ('funko', 'vaulted-2013', 'clockwork-orange-alex', 'Clockwork Orange Alex', 'Funko Pop', 'Vaulted', 'Vaulted in 2013 - Very rare'),
  ('funko', 'sdcc-2013', 'headless-ned-stark-glow', 'Headless Ned Stark (Glow)', 'Funko Pop', 'SDCC Exclusive', 'SDCC 2013 - Game of Thrones'),
  ('funko', 'toy-tokyo', 'planet-arlia-vegeta', 'Planet Arlia Vegeta', 'Funko Pop', 'Toy Tokyo Exclusive', 'Dragon Ball Z - Holy grail'),
  ('funko', 'sdcc-2011', 'red-skull-metallic', 'Red Skull (Metallic)', 'Funko Pop', 'SDCC Exclusive', 'SDCC 2011 - Captain America'),
  ('funko', 'nycc-2012', 'green-lantern-px', 'Green Lantern (Previews)', 'Funko Pop', 'NYCC Exclusive', 'NYCC 2012'),
  ('funko', 'eccc-2017', 'touche-turtle-gold', 'Touche Turtle (Gold)', 'Funko Pop', 'ECCC Exclusive', 'Emerald City Comic Con'),
  ('funko', 'sdcc-2012', 'boo-berry-metallic', 'Boo Berry (Metallic)', 'Funko Pop', 'SDCC Exclusive', 'General Mills cereal monster'),
  ('funko', 'sdcc-2012', 'franken-berry-metallic', 'Franken Berry (Metallic)', 'Funko Pop', 'SDCC Exclusive', 'General Mills cereal monster'),
  ('funko', 'sdcc-2012', 'count-chocula-metallic', 'Count Chocula (Metallic)', 'Funko Pop', 'SDCC Exclusive', 'General Mills cereal monster'),
  ('funko', 'disney-parks', 'haunted-mansion-hatbox', 'Hatbox Ghost', 'Funko Pop', 'Disney Parks Exclusive', 'Haunted Mansion - Very limited')
ON CONFLICT (category, item_key) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- Warhammer Centerpiece Models
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO public.category_items (category, set_code, item_key, title, brand, rarity, notes) VALUES
  ('warhammer', '40k', 'primarch-guilliman', 'Primarch Roboute Guilliman', 'Games Workshop', 'Centerpiece', 'Ultramarines Primarch'),
  ('warhammer', '40k', 'mortarion-daemon', 'Mortarion, Daemon Primarch', 'Games Workshop', 'Centerpiece', 'Death Guard Primarch'),
  ('warhammer', '40k', 'magnus-red', 'Magnus the Red', 'Games Workshop', 'Centerpiece', 'Thousand Sons Primarch'),
  ('warhammer', '40k', 'knight-castellan', 'Knight Castellan', 'Games Workshop', 'Lord of War', 'Imperial Knights'),
  ('warhammer', '40k', 'warlord-titan', 'Warlord Titan', 'Forge World', 'Titan', 'Adeptus Titanicus scale'),
  ('warhammer', '40k', 'blood-angels-sanguinor', 'The Sanguinor', 'Games Workshop', 'HQ', 'Blood Angels chapter hero'),
  ('warhammer', 'aos', 'archaon-everchosen', 'Archaon the Everchosen', 'Games Workshop', 'Centerpiece', 'Slaves to Darkness'),
  ('warhammer', 'aos', 'nagash-supreme', 'Nagash, Supreme Lord of Undead', 'Games Workshop', 'Centerpiece', 'Death Grand Alliance')
ON CONFLICT (category, item_key) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- Designer Toys / Art Toys
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO public.category_items (category, set_code, item_key, title, brand, rarity, notes) VALUES
  ('designer_toys', 'kaws', 'companion-grey', 'KAWS Companion (Grey)', 'KAWS', 'Open Edition', '2016 release'),
  ('designer_toys', 'kaws', 'companion-black', 'KAWS Companion (Black)', 'KAWS', 'Open Edition', 'Classic colorway'),
  ('designer_toys', 'medicom', 'bearbrick-1000-basquiat', 'Bearbrick 1000% Basquiat', 'Medicom', 'Art Collab', 'Jean-Michel Basquiat series'),
  ('designer_toys', 'superplastic', 'janky-artist', 'Superplastic Janky', 'Superplastic', 'Artist Series', 'Various artist collaborations'),
  ('designer_toys', 'coarse', 'noop-cloud', 'Coarse Noop (Cloud)', 'Coarse', 'Limited', 'Cloud colorway exclusive'),
  ('designer_toys', 'good-smile', 'azimuth-james-jean', 'Azimuth by James Jean', 'Good Smile Company', 'First Vinyl', 'James Jean first vinyl figure')
ON CONFLICT (category, item_key) DO NOTHING;
