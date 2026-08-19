-- D&D catalogue seed (2026-08-15)
--
-- WHY: `dnd` had a full collecting guide — glossary, holy grail, "where to
-- start" — and ZERO data behind it: 0 category_items, 0 market_hits, 0 user
-- items. The guide walked a beginner to an empty shelf, which is the failure
-- this codebase keeps paying for.
--
-- WHAT IS IN HERE, AND WHY ONLY THIS: books and boxed sets. The guide's own
-- thesis is "there is no product you are required to buy in order to play, so
-- collecting here is about early printings of the rulebooks — the books are the
-- market". Dice and painted miniatures are deliberately excluded: "a polyhedral
-- set" is not a SKU with a stable identity, and a catalogue row nobody can
-- match a listing to is a row that will never carry a price.
--
-- PRICING NEEDS NO NEW ADAPTER. `abebooks` — the obvious fit — has been in
-- DISABLED_ADAPTERS since 2026-05-10 (prices are JS-rendered; Crawl4AI sees 0
-- price tokens). These get priced by the unrestricted trio (ebay + vinted +
-- crawl4ai) that covers every category without a dedicated adapter, which is
-- how `disney` reached 1,292 priced rows out of 1,414 with no adapter of its
-- own. eBay is in any case where the D&D secondary market actually lives.
--
-- item_key is a stable slug; (category, item_key) is UNIQUE, so this is safely
-- re-runnable. source='seed' matches the other 145k curated rows.

INSERT INTO public.category_items
  (category, item_key, title, brand, set_code, source, verified, attributes_json)
VALUES
-- ── Original D&D and the Basic line (TSR) ────────────────────────────────
('dnd','odd-original-collectors-edition-1974','Dungeons & Dragons (Original Collector''s Edition, White Box)','TSR','od&d','seed',false,'{"year":1974,"format":"boxed_set"}'),
('dnd','odd-supplement-i-greyhawk','Supplement I: Greyhawk','TSR','od&d','seed',false,'{"year":1975,"format":"booklet"}'),
('dnd','odd-supplement-ii-blackmoor','Supplement II: Blackmoor','TSR','od&d','seed',false,'{"year":1975,"format":"booklet"}'),
('dnd','odd-supplement-iii-eldritch-wizardry','Supplement III: Eldritch Wizardry','TSR','od&d','seed',false,'{"year":1976,"format":"booklet"}'),
('dnd','odd-supplement-iv-gods-demigods-heroes','Supplement IV: Gods, Demi-Gods & Heroes','TSR','od&d','seed',false,'{"year":1976,"format":"booklet"}'),
('dnd','basic-set-holmes-1977','Dungeons & Dragons Basic Set (Holmes)','TSR','basic','seed',false,'{"year":1977,"format":"boxed_set"}'),
('dnd','basic-set-moldvay-1981','Dungeons & Dragons Basic Set (Moldvay)','TSR','basic','seed',false,'{"year":1981,"format":"boxed_set"}'),
('dnd','expert-set-cook-marsh-1981','Dungeons & Dragons Expert Set (Cook/Marsh)','TSR','basic','seed',false,'{"year":1981,"format":"boxed_set"}'),
('dnd','basic-set-mentzer-1983','Dungeons & Dragons Basic Set (Mentzer, Red Box)','TSR','becmi','seed',false,'{"year":1983,"format":"boxed_set"}'),
('dnd','expert-set-mentzer-1983','Dungeons & Dragons Expert Set (Mentzer)','TSR','becmi','seed',false,'{"year":1983,"format":"boxed_set"}'),
('dnd','companion-set-1984','Dungeons & Dragons Companion Set','TSR','becmi','seed',false,'{"year":1984,"format":"boxed_set"}'),
('dnd','master-set-1985','Dungeons & Dragons Master Set','TSR','becmi','seed',false,'{"year":1985,"format":"boxed_set"}'),
('dnd','immortals-set-1986','Dungeons & Dragons Immortals Set','TSR','becmi','seed',false,'{"year":1986,"format":"boxed_set"}'),
('dnd','rules-cyclopedia-1991','Dungeons & Dragons Rules Cyclopedia','TSR','becmi','seed',false,'{"year":1991,"format":"hardcover"}'),
-- ── AD&D 1st edition core ────────────────────────────────────────────────
('dnd','adnd1e-monster-manual','Monster Manual (AD&D 1e)','TSR','ad&d-1e','seed',false,'{"year":1977,"format":"hardcover"}'),
('dnd','adnd1e-players-handbook','Player''s Handbook (AD&D 1e)','TSR','ad&d-1e','seed',false,'{"year":1978,"format":"hardcover"}'),
('dnd','adnd1e-dungeon-masters-guide','Dungeon Master''s Guide (AD&D 1e)','TSR','ad&d-1e','seed',false,'{"year":1979,"format":"hardcover"}'),
('dnd','adnd1e-deities-and-demigods','Deities & Demigods (AD&D 1e)','TSR','ad&d-1e','seed',false,'{"year":1980,"format":"hardcover","note":"first printings include Cthulhu and Melnibonean mythoi"}'),
('dnd','adnd1e-fiend-folio','Fiend Folio (AD&D 1e)','TSR','ad&d-1e','seed',false,'{"year":1981,"format":"hardcover"}'),
('dnd','adnd1e-monster-manual-ii','Monster Manual II (AD&D 1e)','TSR','ad&d-1e','seed',false,'{"year":1983,"format":"hardcover"}'),
('dnd','adnd1e-unearthed-arcana','Unearthed Arcana (AD&D 1e)','TSR','ad&d-1e','seed',false,'{"year":1985,"format":"hardcover"}'),
('dnd','adnd1e-oriental-adventures','Oriental Adventures (AD&D 1e)','TSR','ad&d-1e','seed',false,'{"year":1985,"format":"hardcover"}'),
('dnd','adnd1e-manual-of-the-planes','Manual of the Planes (AD&D 1e)','TSR','ad&d-1e','seed',false,'{"year":1987,"format":"hardcover"}'),
-- ── Classic TSR modules ──────────────────────────────────────────────────
('dnd','module-b1-in-search-of-the-unknown','B1: In Search of the Unknown','TSR','module','seed',false,'{"year":1979,"format":"module"}'),
('dnd','module-b2-keep-on-the-borderlands','B2: The Keep on the Borderlands','TSR','module','seed',false,'{"year":1979,"format":"module"}'),
('dnd','module-s1-tomb-of-horrors','S1: Tomb of Horrors','TSR','module','seed',false,'{"year":1978,"format":"module"}'),
('dnd','module-s2-white-plume-mountain','S2: White Plume Mountain','TSR','module','seed',false,'{"year":1979,"format":"module"}'),
('dnd','module-s3-expedition-to-the-barrier-peaks','S3: Expedition to the Barrier Peaks','TSR','module','seed',false,'{"year":1980,"format":"module"}'),
('dnd','module-s4-lost-caverns-of-tsojcanth','S4: The Lost Caverns of Tsojcanth','TSR','module','seed',false,'{"year":1982,"format":"module"}'),
('dnd','module-t1-village-of-hommlet','T1: The Village of Hommlet','TSR','module','seed',false,'{"year":1979,"format":"module"}'),
('dnd','module-t1-4-temple-of-elemental-evil','T1-4: The Temple of Elemental Evil','TSR','module','seed',false,'{"year":1985,"format":"module"}'),
('dnd','module-g1-3-against-the-giants','G1-2-3: Against the Giants','TSR','module','seed',false,'{"year":1981,"format":"module"}'),
('dnd','module-d1-2-descent-into-the-depths','D1-2: Descent into the Depths of the Earth','TSR','module','seed',false,'{"year":1981,"format":"module"}'),
('dnd','module-d3-vault-of-the-drow','D3: Vault of the Drow','TSR','module','seed',false,'{"year":1978,"format":"module"}'),
('dnd','module-q1-queen-of-the-demonweb-pits','Q1: Queen of the Demonweb Pits','TSR','module','seed',false,'{"year":1980,"format":"module"}'),
('dnd','module-i6-ravenloft','I6: Ravenloft','TSR','module','seed',false,'{"year":1983,"format":"module"}'),
('dnd','module-x1-isle-of-dread','X1: The Isle of Dread','TSR','module','seed',false,'{"year":1981,"format":"module"}'),
('dnd','module-a1-4-scourge-of-the-slavelords','A1-4: Scourge of the Slave Lords','TSR','module','seed',false,'{"year":1986,"format":"module"}'),
('dnd','module-wg4-forgotten-temple-of-tharizdun','WG4: The Forgotten Temple of Tharizdun','TSR','module','seed',false,'{"year":1982,"format":"module"}'),
('dnd','module-dl1-dragons-of-despair','DL1: Dragons of Despair','TSR','module','seed',false,'{"year":1984,"format":"module"}'),
-- ── AD&D 2nd edition ─────────────────────────────────────────────────────
('dnd','adnd2e-players-handbook','Player''s Handbook (AD&D 2e)','TSR','ad&d-2e','seed',false,'{"year":1989,"format":"hardcover"}'),
('dnd','adnd2e-dungeon-masters-guide','Dungeon Master''s Guide (AD&D 2e)','TSR','ad&d-2e','seed',false,'{"year":1989,"format":"hardcover"}'),
('dnd','adnd2e-monstrous-compendium-volume-one','Monstrous Compendium Volume One','TSR','ad&d-2e','seed',false,'{"year":1989,"format":"binder"}'),
('dnd','adnd2e-monstrous-manual','Monstrous Manual','TSR','ad&d-2e','seed',false,'{"year":1993,"format":"hardcover"}'),
('dnd','adnd2e-planescape-campaign-setting','Planescape Campaign Setting','TSR','ad&d-2e','seed',false,'{"year":1994,"format":"boxed_set"}'),
('dnd','adnd2e-dark-sun-boxed-set','Dark Sun Campaign Setting','TSR','ad&d-2e','seed',false,'{"year":1991,"format":"boxed_set"}'),
('dnd','adnd2e-ravenloft-realm-of-terror','Ravenloft: Realm of Terror','TSR','ad&d-2e','seed',false,'{"year":1990,"format":"boxed_set"}'),
('dnd','adnd2e-forgotten-realms-campaign-setting','Forgotten Realms Campaign Setting (2e)','TSR','ad&d-2e','seed',false,'{"year":1993,"format":"boxed_set"}'),
('dnd','adnd2e-spelljammer-adventures-in-space','Spelljammer: AD&D Adventures in Space','TSR','ad&d-2e','seed',false,'{"year":1989,"format":"boxed_set"}'),
('dnd','adnd2e-birthright-campaign-setting','Birthright Campaign Setting','TSR','ad&d-2e','seed',false,'{"year":1995,"format":"boxed_set"}'),
-- ── Wizards of the Coast: 3.0 / 3.5 / 4e ─────────────────────────────────
('dnd','3e-players-handbook','Player''s Handbook (3rd Edition)','Wizards of the Coast','3e','seed',false,'{"year":2000,"format":"hardcover"}'),
('dnd','3e-dungeon-masters-guide','Dungeon Master''s Guide (3rd Edition)','Wizards of the Coast','3e','seed',false,'{"year":2000,"format":"hardcover"}'),
('dnd','3e-monster-manual','Monster Manual (3rd Edition)','Wizards of the Coast','3e','seed',false,'{"year":2000,"format":"hardcover"}'),
('dnd','35e-players-handbook','Player''s Handbook (v3.5)','Wizards of the Coast','3.5e','seed',false,'{"year":2003,"format":"hardcover"}'),
('dnd','35e-dungeon-masters-guide','Dungeon Master''s Guide (v3.5)','Wizards of the Coast','3.5e','seed',false,'{"year":2003,"format":"hardcover"}'),
('dnd','35e-monster-manual','Monster Manual (v3.5)','Wizards of the Coast','3.5e','seed',false,'{"year":2003,"format":"hardcover"}'),
('dnd','35e-book-of-vile-darkness','Book of Vile Darkness','Wizards of the Coast','3.5e','seed',false,'{"year":2002,"format":"hardcover"}'),
('dnd','35e-tome-of-magic','Tome of Magic','Wizards of the Coast','3.5e','seed',false,'{"year":2006,"format":"hardcover"}'),
('dnd','4e-players-handbook','Player''s Handbook (4th Edition)','Wizards of the Coast','4e','seed',false,'{"year":2008,"format":"hardcover"}'),
('dnd','4e-dungeon-masters-guide','Dungeon Master''s Guide (4th Edition)','Wizards of the Coast','4e','seed',false,'{"year":2008,"format":"hardcover"}'),
('dnd','4e-monster-manual','Monster Manual (4th Edition)','Wizards of the Coast','4e','seed',false,'{"year":2008,"format":"hardcover"}'),
-- ── 5th edition ──────────────────────────────────────────────────────────
('dnd','5e-players-handbook','Player''s Handbook (5th Edition)','Wizards of the Coast','5e','seed',false,'{"year":2014,"format":"hardcover"}'),
('dnd','5e-dungeon-masters-guide','Dungeon Master''s Guide (5th Edition)','Wizards of the Coast','5e','seed',false,'{"year":2014,"format":"hardcover"}'),
('dnd','5e-monster-manual','Monster Manual (5th Edition)','Wizards of the Coast','5e','seed',false,'{"year":2014,"format":"hardcover"}'),
('dnd','5e-curse-of-strahd','Curse of Strahd','Wizards of the Coast','5e','seed',false,'{"year":2016,"format":"hardcover"}'),
('dnd','5e-curse-of-strahd-alt-cover','Curse of Strahd (alternate cover)','Wizards of the Coast','5e','seed',false,'{"year":2016,"format":"hardcover","variant":"alt_cover"}'),
('dnd','5e-tomb-of-annihilation','Tomb of Annihilation','Wizards of the Coast','5e','seed',false,'{"year":2017,"format":"hardcover"}'),
('dnd','5e-waterdeep-dragon-heist','Waterdeep: Dragon Heist','Wizards of the Coast','5e','seed',false,'{"year":2018,"format":"hardcover"}'),
('dnd','5e-descent-into-avernus','Baldur''s Gate: Descent into Avernus','Wizards of the Coast','5e','seed',false,'{"year":2019,"format":"hardcover"}'),
('dnd','5e-tashas-cauldron-of-everything','Tasha''s Cauldron of Everything','Wizards of the Coast','5e','seed',false,'{"year":2020,"format":"hardcover"}'),
('dnd','5e-xanathars-guide-to-everything','Xanathar''s Guide to Everything','Wizards of the Coast','5e','seed',false,'{"year":2017,"format":"hardcover"}'),
('dnd','5e-mordenkainens-tome-of-foes','Mordenkainen''s Tome of Foes','Wizards of the Coast','5e','seed',false,'{"year":2018,"format":"hardcover"}'),
('dnd','5e-van-richtens-guide-to-ravenloft','Van Richten''s Guide to Ravenloft','Wizards of the Coast','5e','seed',false,'{"year":2021,"format":"hardcover"}'),
('dnd','5e-starter-set-lost-mine-of-phandelver','Starter Set: Lost Mine of Phandelver','Wizards of the Coast','5e','seed',false,'{"year":2014,"format":"boxed_set"}')
ON CONFLICT (category, item_key) DO NOTHING;

SELECT set_code, count(*) FROM public.category_items
WHERE category = 'dnd' GROUP BY set_code ORDER BY 2 DESC;
