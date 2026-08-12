-- Jewellery catalogue seed — 2026-08-12 · extends jewellery_seed_2026_08_11.sql
--
-- REVIEW BEFORE RUNNING. Curated from knowledge of each maison's product lines,
-- not from any source. If a line name or material is wrong, no gate can catch
-- it — that check is yours. Same standing rule as the 08-11 batch.
--
-- WHY THIS BATCH. 08-11 seeded 317 rows / 41 maisons, but Tiffany came out at
-- only 54 rows across 13 lines with several of the house's best-known
-- collections absent entirely (Keys, Infinity, 1837, Bird on a Rock, Bean,
-- Open Heart, Diamonds by the Yard). Fourteen maisons sat at 1-2 rows, which is
-- presence without depth: a collector searching "Verdura Maltese Cross" found
-- nothing. This batch deepens Tiffany first, then the signature line of each
-- thin maison.
--
-- CONVENTIONS INHERITED FROM 08-11, DELIBERATELY UNCHANGED:
--   * designer / high-ASP maisons only — no mass-market
--   * fashion houses stay LINE-ANCHORED ("Chanel Coco Crush", never bare
--     "Chanel"), so the classifier cannot pull in bags or watches
--   * NAME-ONLY, no reference numbers — jewellery maisons do not publish
--     equivalents to a watch ref, and inventing them would make these rows look
--     as authoritative as the 1,416 watch rows without being so
--   * source='seed', verified=false, notes = the line
--   * idempotent on (category, item_key)
--
-- THESE ROWS CANNOT BE PRICED. No sold-comp source for jewellery, same as
-- watches — they render "not yet priced". That is a known and accepted
-- consequence of seeding breadth ahead of price coverage, NOT a defect to
-- chase. Note it lowers the priceable-share metric for `jewellery`, so if the
-- watchdog's coverage check is ever extended to this category, seeded rows
-- should be excluded from its denominator rather than the seeding stopped.

BEGIN;

INSERT INTO category_items (category, item_key, title, brand, notes, source, verified, attributes_json)
VALUES
  -- ---------------------------------------------------------------- Tiffany
  -- Tiffany Keys — a flagship line entirely absent from 08-11.
  ('jewellery','tiffany-and-co-tiffany-keys-heart-key-pendant-18k-yellow-gold','Tiffany Keys Heart Key Pendant, 18k Yellow Gold','Tiffany & Co.','Tiffany Keys','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "keys"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-keys-heart-key-pendant-18k-rose-gold','Tiffany Keys Heart Key Pendant, 18k Rose Gold','Tiffany & Co.','Tiffany Keys','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "keys"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-keys-crown-key-pendant-18k-yellow-gold','Tiffany Keys Crown Key Pendant, 18k Yellow Gold','Tiffany & Co.','Tiffany Keys','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "keys"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-keys-daisy-key-pendant-18k-white-gold-with-diamonds','Tiffany Keys Daisy Key Pendant, 18k White Gold with Diamonds','Tiffany & Co.','Tiffany Keys','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "keys"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-keys-oval-key-pendant-platinum-with-diamonds','Tiffany Keys Oval Key Pendant, Platinum with Diamonds','Tiffany & Co.','Tiffany Keys','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "keys"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-keys-modern-keys-round-pendant-18k-rose-gold','Tiffany Keys Modern Keys Round Pendant, 18k Rose Gold','Tiffany & Co.','Tiffany Keys','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "keys"}'::jsonb),
  -- Elsa Peretti — 08-11 carried 7; these are the signature forms.
  ('jewellery','tiffany-and-co-elsa-peretti-open-heart-pendant-18k-yellow-gold','Elsa Peretti Open Heart Pendant, 18k Yellow Gold','Tiffany & Co.','Elsa Peretti','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "elsa_peretti"}'::jsonb),
  ('jewellery','tiffany-and-co-elsa-peretti-bone-cuff-18k-yellow-gold','Elsa Peretti Bone Cuff, 18k Yellow Gold','Tiffany & Co.','Elsa Peretti','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "elsa_peretti"}'::jsonb),
  ('jewellery','tiffany-and-co-elsa-peretti-diamonds-by-the-yard-necklace-18k-yellow-gold','Elsa Peretti Diamonds by the Yard Necklace, 18k Yellow Gold','Tiffany & Co.','Elsa Peretti','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "elsa_peretti"}'::jsonb),
  ('jewellery','tiffany-and-co-elsa-peretti-diamonds-by-the-yard-bracelet-platinum','Elsa Peretti Diamonds by the Yard Bracelet, Platinum','Tiffany & Co.','Elsa Peretti','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "elsa_peretti"}'::jsonb),
  -- Jean Schlumberger — the house's haute joaillerie signature.
  ('jewellery','tiffany-and-co-jean-schlumberger-bird-on-a-rock-brooch-18k-yellow-gold-and-platinum','Jean Schlumberger Bird on a Rock Brooch, 18k Yellow Gold and Platinum','Tiffany & Co.','Jean Schlumberger','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "schlumberger"}'::jsonb),
  ('jewellery','tiffany-and-co-jean-schlumberger-sixteen-stone-ring-18k-yellow-gold-and-platinum','Jean Schlumberger Sixteen Stone Ring, 18k Yellow Gold and Platinum','Tiffany & Co.','Jean Schlumberger','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "schlumberger"}'::jsonb),
  ('jewellery','tiffany-and-co-jean-schlumberger-rope-two-row-ring-18k-yellow-gold','Jean Schlumberger Rope Two-Row Ring, 18k Yellow Gold','Tiffany & Co.','Jean Schlumberger','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "schlumberger"}'::jsonb),
  ('jewellery','tiffany-and-co-jean-schlumberger-lynn-earrings-18k-yellow-gold-and-platinum','Jean Schlumberger Lynn Earrings, 18k Yellow Gold and Platinum','Tiffany & Co.','Jean Schlumberger','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "schlumberger"}'::jsonb),
  ('jewellery','tiffany-and-co-jean-schlumberger-croisillon-bracelet-red-enamel-and-18k-yellow-gold','Jean Schlumberger Croisillon Bracelet, Red Enamel and 18k Yellow Gold','Tiffany & Co.','Jean Schlumberger','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "schlumberger"}'::jsonb),
  -- Paloma Picasso.
  ('jewellery','tiffany-and-co-paloma-picasso-graffiti-love-pendant-18k-yellow-gold','Paloma Picasso Graffiti Love Pendant, 18k Yellow Gold','Tiffany & Co.','Paloma Picasso','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "paloma_picasso"}'::jsonb),
  -- Core house lines absent from 08-11.
  ('jewellery','tiffany-and-co-tiffany-1837-makers-narrow-ring-sterling-silver','Tiffany 1837 Makers Narrow Ring, Sterling Silver','Tiffany & Co.','1837','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "1837"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-1837-makers-id-bracelet-sterling-silver','Tiffany 1837 Makers ID Bracelet, Sterling Silver','Tiffany & Co.','1837','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "1837"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-infinity-pendant-sterling-silver','Tiffany Infinity Pendant, Sterling Silver','Tiffany & Co.','Infinity','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "infinity"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-infinity-bracelet-18k-yellow-gold','Tiffany Infinity Bracelet, 18k Yellow Gold','Tiffany & Co.','Infinity','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "infinity"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-hardwear-graduated-link-necklace-18k-yellow-gold','Tiffany HardWear Graduated Link Necklace, 18k Yellow Gold','Tiffany & Co.','HardWear','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "hardwear"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-lock-bangle-18k-rose-gold-with-diamonds','Tiffany Lock Bangle, 18k Rose Gold with Diamonds','Tiffany & Co.','Lock','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "lock"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-knot-double-row-hinged-bangle-18k-yellow-gold-with-diamonds','Tiffany Knot Double Row Hinged Bangle, 18k Yellow Gold with Diamonds','Tiffany & Co.','Knot','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "knot"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-victoria-cluster-pendant-platinum-with-diamonds','Tiffany Victoria Cluster Pendant, Platinum with Diamonds','Tiffany & Co.','Victoria','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "victoria"}'::jsonb),
  -- Bridal.
  ('jewellery','tiffany-and-co-tiffany-novo-engagement-ring-platinum','Tiffany Novo Engagement Ring, Platinum','Tiffany & Co.','Novo','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "bridal"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-forever-band-ring-platinum-with-diamonds','Tiffany Forever Band Ring, Platinum with Diamonds','Tiffany & Co.','Forever','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "bridal"}'::jsonb),
  ('jewellery','tiffany-and-co-tiffany-soleste-halo-engagement-ring-platinum','Tiffany Soleste Halo Engagement Ring, Platinum','Tiffany & Co.','Soleste','seed',false,'{"seed_batch": "jewellery_2026_08_12", "line": "bridal"}'::jsonb),

  -- --------------------------------------------- Depth for thin maisons (1-2 rows at 08-11)
  ('jewellery','verdura-verdura-maltese-cross-cuff','Verdura Maltese Cross Cuff','Verdura','Maltese Cross','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','verdura-verdura-curb-link-bracelet-18k-yellow-gold','Verdura Curb-Link Bracelet, 18k Yellow Gold','Verdura','Curb-Link','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','seaman-schepps-seaman-schepps-turbo-shell-earrings','Seaman Schepps Turbo Shell Earrings','Seaman Schepps','Turbo Shell','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','seaman-schepps-seaman-schepps-rivoli-ring','Seaman Schepps Rivoli Ring','Seaman Schepps','Rivoli','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','boodles-boodles-raindance-bracelet-18k-white-gold','Boodles Raindance Bracelet, 18k White Gold','Boodles','Raindance','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','garrard-garrard-1735-ring-18k-white-gold','Garrard 1735 Ring, 18k White Gold','Garrard','1735','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','garrard-garrard-wings-classic-pendant-18k-white-gold','Garrard Wings Classic Pendant, 18k White Gold','Garrard','Wings','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','faberge-faberge-egg-pendant-18k-yellow-gold-with-enamel','Fabergé Egg Pendant, 18k Yellow Gold with Enamel','Fabergé','Egg Pendant','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','faberge-faberge-colours-of-love-ring-18k-white-gold','Fabergé Colours of Love Ring, 18k White Gold','Fabergé','Colours of Love','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','asprey-asprey-chaos-ring-18k-yellow-gold','Asprey Chaos Ring, 18k Yellow Gold','Asprey','Chaos','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','asprey-asprey-woodland-pendant-18k-white-gold','Asprey Woodland Pendant, 18k White Gold','Asprey','Woodland','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','damiani-damiani-belle-epoque-ring-18k-white-gold-with-diamonds','Damiani Belle Époque Ring, 18k White Gold with Diamonds','Damiani','Belle Époque','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','damiani-damiani-margherita-ring-18k-rose-gold','Damiani Margherita Ring, 18k Rose Gold','Damiani','Margherita','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','repossi-repossi-berbere-ring-18k-rose-gold','Repossi Berbère Ring, 18k Rose Gold','Repossi','Berbère','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','repossi-repossi-antifer-ring-18k-white-gold','Repossi Antifer Ring, 18k White Gold','Repossi','Antifer','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','vhernier-vhernier-calla-earrings-18k-rose-gold','Vhernier Calla Earrings, 18k Rose Gold','Vhernier','Calla','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','vhernier-vhernier-freccia-ring-titanium','Vhernier Freccia Ring, Titanium','Vhernier','Freccia','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','spinelli-kilcollin-spinelli-kilcollin-raneth-linked-ring-sterling-silver','Spinelli Kilcollin Raneth Linked Ring, Sterling Silver','Spinelli Kilcollin','Raneth','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','foundrae-foundrae-karma-medallion-18k-yellow-gold','Foundrae Karma Medallion, 18k Yellow Gold','Foundrae','Medallion','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','anita-ko-anita-ko-hedges-earrings-18k-yellow-gold','Anita Ko Hedges Earrings, 18k Yellow Gold','Anita Ko','Hedges','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','suzanne-kalan-suzanne-kalan-fireworks-eternity-band-18k-yellow-gold','Suzanne Kalan Fireworks Eternity Band, 18k Yellow Gold','Suzanne Kalan','Fireworks','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','buccellati-buccellati-opera-tulle-ring-18k-yellow-gold','Buccellati Opera Tulle Ring, 18k Yellow Gold','Buccellati','Opera','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','boucheron-boucheron-serpent-boheme-ring-18k-yellow-gold','Boucheron Serpent Bohème Ring, 18k Yellow Gold','Boucheron','Serpent Bohème','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','boucheron-boucheron-quatre-classique-ring-18k-white-gold','Boucheron Quatre Classique Ring, 18k White Gold','Boucheron','Quatre','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','chaumet-chaumet-bee-my-love-ring-18k-rose-gold','Chaumet Bee My Love Ring, 18k Rose Gold','Chaumet','Bee My Love','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','chaumet-chaumet-liens-evidence-bracelet-18k-yellow-gold','Chaumet Liens Évidence Bracelet, 18k Yellow Gold','Chaumet','Liens','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb),
  ('jewellery','chopard-chopard-ice-cube-bracelet-18k-white-gold','Chopard Ice Cube Bracelet, 18k White Gold','Chopard','Ice Cube','seed',false,'{"seed_batch": "jewellery_2026_08_12"}'::jsonb)
ON CONFLICT (category, item_key) DO UPDATE
  SET title = EXCLUDED.title, brand = EXCLUDED.brand, notes = EXCLUDED.notes,
      attributes_json = EXCLUDED.attributes_json, updated_at = now();

SELECT count(*) AS rows_now, count(DISTINCT brand) AS brands,
       count(*) FILTER (WHERE attributes_json->>'seed_batch'='jewellery_2026_08_12') AS this_batch
FROM category_items WHERE category='jewellery';

COMMIT;

-- Reversal: check nothing bound to these keys first —
--   SELECT count(*) FROM items WHERE canonical_key IN (
--     SELECT item_key FROM category_items
--     WHERE attributes_json->>'seed_batch'='jewellery_2026_08_12');
-- then DELETE FROM category_items WHERE category='jewellery'
--   AND attributes_json->>'seed_batch'='jewellery_2026_08_12';
