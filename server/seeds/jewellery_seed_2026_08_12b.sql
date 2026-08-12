-- Jewellery catalogue seed — 2026-08-12 batch B · third jewellery batch
--
-- REVIEW BEFORE RUNNING. Curated from knowledge of each maison's product lines,
-- not from any source. If a line name or material is wrong, no gate can catch
-- it — that check is yours. Standing rule since the 08-11 batch.
--
-- WHY THIS BATCH. After 08-11 (317) and 08-12a (48), the catalogue sat at 365
-- rows / 41 maisons with Tiffany at 78 and a long middle tier stuck at 5-9:
-- Graff 7, Harry Winston 7, Mikimoto 7, Louis Vuitton 7, Dior 7, Chopard 7,
-- Piaget 6, Pomellato 6, Gucci 5. Each had two or three lines represented and
-- the rest of the house missing. This batch adds NEW LINES for those houses,
-- then opens maisons that were absent entirely.
--
-- DUPLICATE DISCIPLINE — the lesson from batch A. That batch checked only for
-- exact `item_key` collisions, passed, and still shipped six duplicates:
-- "Verdura Maltese Cross Cuff" landed beside the existing "Verdura Maltese
-- Cross Cuff, 18k Yellow Gold with Enamel". Same product, different key, no
-- gate saw it. So every row below was written against the full existing title
-- list for its house, and both checks — exact key AND same-product title — are
-- run before this file is applied. A material variant of an existing piece is
-- legitimate (08-11 itself lists one ring in three golds); a bare restatement
-- of one is not.
--
-- CONVENTIONS INHERITED, DELIBERATELY UNCHANGED:
--   * designer / high-ASP maisons only — no mass-market
--   * fashion houses stay LINE-ANCHORED ("Gucci Horsebit", never bare "Gucci"),
--     so the classifier cannot pull in handbags, belts or watches
--   * NAME-ONLY, no invented reference numbers
--   * source='seed', verified=false, notes = the line
--   * idempotent on (category, item_key)
--
-- THESE ROWS CANNOT BE PRICED — no sold-comp source for jewellery. They render
-- "not yet priced". Accepted cost of breadth ahead of price coverage.

BEGIN;

INSERT INTO category_items (category, item_key, title, brand, notes, source, verified, attributes_json)
VALUES
  -- ------------------------------------------------------- Graff (new lines)
  ('jewellery','graff-graff-threads-ring-18k-white-gold','Graff Threads Ring, 18k White Gold','Graff','Threads','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','graff-graff-threads-bracelet-18k-rose-gold','Graff Threads Bracelet, 18k Rose Gold','Graff','Threads','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','graff-graff-tildas-bow-pendant-18k-white-gold','Graff Tilda''s Bow Pendant, 18k White Gold','Graff','Tilda''s Bow','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','graff-graff-tildas-bow-earrings-18k-white-gold','Graff Tilda''s Bow Earrings, 18k White Gold','Graff','Tilda''s Bow','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','graff-graff-laurence-graff-signature-ring-platinum','Graff Laurence Graff Signature Ring, Platinum','Graff','Laurence Graff Signature','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  -- ----------------------------------------------- Harry Winston (new lines)
  ('jewellery','harry-winston-harry-winston-forget-me-not-ring-platinum','Harry Winston Forget-Me-Not Ring, Platinum','Harry Winston','Forget-Me-Not','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','harry-winston-harry-winston-forget-me-not-earrings-18k-rose-gold','Harry Winston Forget-Me-Not Earrings, 18k Rose Gold','Harry Winston','Forget-Me-Not','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','harry-winston-harry-winston-loop-pendant-18k-yellow-gold','Harry Winston Loop Pendant, 18k Yellow Gold','Harry Winston','Loop','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','harry-winston-harry-winston-water-earrings-platinum','Harry Winston Water Earrings, Platinum','Harry Winston','Water','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','harry-winston-harry-winston-secret-cluster-ring-platinum','Harry Winston Secret Cluster Ring, Platinum','Harry Winston','Secret Cluster','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  -- ---------------------------------------------------- Mikimoto (new lines)
  ('jewellery','mikimoto-mikimoto-morning-dew-pendant-18k-white-gold','Mikimoto Morning Dew Pendant, 18k White Gold','Mikimoto','Morning Dew','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','mikimoto-mikimoto-cherry-blossom-brooch-18k-white-gold','Mikimoto Cherry Blossom Brooch, 18k White Gold','Mikimoto','Cherry Blossom','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','mikimoto-mikimoto-les-petales-ring-18k-rose-gold','Mikimoto Les Pétales Ring, 18k Rose Gold','Mikimoto','Les Pétales','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','mikimoto-mikimoto-m-collection-station-necklace-18k-yellow-gold','Mikimoto M Collection Station Necklace, 18k Yellow Gold','Mikimoto','M Collection','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  -- ----------------------------------------------- Louis Vuitton (new lines)
  ('jewellery','louis-vuitton-louis-vuitton-b-blossom-ring-18k-yellow-gold','Louis Vuitton B Blossom Ring, 18k Yellow Gold','Louis Vuitton','B Blossom','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','louis-vuitton-louis-vuitton-b-blossom-pendant-18k-white-gold','Louis Vuitton B Blossom Pendant, 18k White Gold','Louis Vuitton','B Blossom','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','louis-vuitton-louis-vuitton-star-blossom-earrings-18k-rose-gold','Louis Vuitton Star Blossom Earrings, 18k Rose Gold','Louis Vuitton','Star Blossom','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','louis-vuitton-louis-vuitton-lv-diamonds-solitaire-ring-platinum','Louis Vuitton LV Diamonds Solitaire Ring, Platinum','Louis Vuitton','LV Diamonds','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  -- ------------------------------------------------------- Dior (new lines)
  ('jewellery','dior-dior-mimirose-ring-18k-white-gold','Dior Mimirose Ring, 18k White Gold','Dior','Mimirose','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','dior-dior-mimirose-earrings-18k-yellow-gold','Dior Mimirose Earrings, 18k Yellow Gold','Dior','Mimirose','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','dior-dior-rose-dior-pre-catelan-ring-18k-rose-gold','Dior Rose Dior Pré Catelan Ring, 18k Rose Gold','Dior','Rose Dior Pré Catelan','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','dior-dior-archi-dior-bar-en-corolle-bracelet-18k-yellow-gold','Dior Archi Dior Bar en Corolle Bracelet, 18k Yellow Gold','Dior','Archi Dior','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  -- ------------------------------------------------------ Gucci (new lines)
  ('jewellery','gucci-gucci-horsebit-ring-18k-yellow-gold','Gucci Horsebit Ring, 18k Yellow Gold','Gucci','Horsebit','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','gucci-gucci-horsebit-bracelet-18k-yellow-gold','Gucci Horsebit Bracelet, 18k Yellow Gold','Gucci','Horsebit','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','gucci-gucci-interlocking-g-pendant-sterling-silver','Gucci Interlocking G Pendant, Sterling Silver','Gucci','Interlocking G','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','gucci-gucci-le-marche-des-merveilles-ring-18k-yellow-gold','Gucci Le Marché des Merveilles Ring, 18k Yellow Gold','Gucci','Le Marché des Merveilles','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  -- ----------------------------------------------------- Chanel (new lines)
  ('jewellery','chanel-chanel-plume-de-chanel-ring-18k-white-gold','Chanel Plume de Chanel Ring, 18k White Gold','Chanel','Plume de Chanel','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','chanel-chanel-plume-de-chanel-pendant-18k-white-gold','Chanel Plume de Chanel Pendant, 18k White Gold','Chanel','Plume de Chanel','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','chanel-chanel-bouton-de-camelia-ring-18k-white-gold','Chanel Bouton de Camélia Ring, 18k White Gold','Chanel','Bouton de Camélia','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','chanel-chanel-baroque-earrings-18k-yellow-gold','Chanel Baroque Earrings, 18k Yellow Gold','Chanel','Baroque','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  -- ----------------------------------------------------- Hermès (new lines)
  ('jewellery','hermes-hermes-galop-dhermes-pendant-18k-rose-gold','Hermès Galop d''Hermès Pendant, 18k Rose Gold','Hermès','Galop','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','hermes-hermes-galop-dhermes-ring-18k-rose-gold','Hermès Galop d''Hermès Ring, 18k Rose Gold','Hermès','Galop','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','hermes-hermes-farandole-necklace-sterling-silver','Hermès Farandole Necklace, Sterling Silver','Hermès','Farandole','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','hermes-hermes-ever-chaine-dancre-ring-18k-rose-gold','Hermès Ever Chaîne d''Ancre Ring, 18k Rose Gold','Hermès','Chaîne d''Ancre','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  -- ---------------------------------------------------- Pomellato (new lines)
  ('jewellery','pomellato-pomellato-tabou-bracelet-18k-rose-gold','Pomellato Tabou Bracelet, 18k Rose Gold','Pomellato','Tabou','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','pomellato-pomellato-catene-necklace-18k-rose-gold','Pomellato Catene Necklace, 18k Rose Gold','Pomellato','Catene','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','pomellato-pomellato-mama-non-mama-ring-18k-rose-gold','Pomellato M''ama non M''ama Ring, 18k Rose Gold','Pomellato','M''ama non M''ama','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','pomellato-pomellato-ritratto-ring-18k-rose-gold','Pomellato Ritratto Ring, 18k Rose Gold','Pomellato','Ritratto','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  -- ----------------------------------------------------- Piaget (new lines)
  ('jewellery','piaget-piaget-sunlight-pendant-18k-rose-gold','Piaget Sunlight Pendant, 18k Rose Gold','Piaget','Sunlight','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','piaget-piaget-sunlight-earrings-18k-yellow-gold','Piaget Sunlight Earrings, 18k Yellow Gold','Piaget','Sunlight','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','piaget-piaget-extremely-piaget-cuff-18k-white-gold','Piaget Extremely Piaget Cuff, 18k White Gold','Piaget','Extremely Piaget','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  -- -------------------------------------------------- Bulgari / Cartier / VCA
  ('jewellery','bulgari-bulgari-fiorever-ring-18k-rose-gold','Bulgari Fiorever Ring, 18k Rose Gold','Bulgari','Fiorever','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','van-cleef-and-arpels-van-cleef-and-arpels-perlee-couleurs-bracelet-18k-rose-gold','Perlée Couleurs Bracelet, 18k Rose Gold','Van Cleef & Arpels','Perlée','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','van-cleef-and-arpels-van-cleef-and-arpels-lucky-animals-clip-18k-yellow-gold','Lucky Animals Clip, 18k Yellow Gold','Van Cleef & Arpels','Lucky Animals','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),

  -- ============================ maisons absent from the catalogue entirely ===
  ('jewellery','david-webb-david-webb-zebra-bracelet-18k-yellow-gold-with-enamel','David Webb Zebra Bracelet, 18k Yellow Gold with Enamel','David Webb','Kingdom','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','david-webb-david-webb-nail-cuff-18k-yellow-gold','David Webb Nail Cuff, 18k Yellow Gold','David Webb','Motif','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','solange-azagury-partridge-solange-azagury-partridge-hotlips-ring-18k-yellow-gold','Solange Azagury-Partridge Hotlips Ring, 18k Yellow Gold','Solange Azagury-Partridge','Hotlips','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','stephen-webster-stephen-webster-thorn-bangle-18k-yellow-gold','Stephen Webster Thorn Bangle, 18k Yellow Gold','Stephen Webster','Thorn','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','stephen-webster-stephen-webster-crystal-haze-ring-18k-rose-gold','Stephen Webster Crystal Haze Ring, 18k Rose Gold','Stephen Webster','Crystal Haze','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','shaun-leane-shaun-leane-serpents-trace-bracelet-sterling-silver','Shaun Leane Serpent''s Trace Bracelet, Sterling Silver','Shaun Leane','Serpent''s Trace','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','shaun-leane-shaun-leane-talon-ring-18k-yellow-gold','Shaun Leane Talon Ring, 18k Yellow Gold','Shaun Leane','Talon','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','theo-fennell-theo-fennell-art-ring-18k-yellow-gold','Theo Fennell Art Ring, 18k Yellow Gold','Theo Fennell','Art','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','jessica-mccormack-jessica-mccormack-gypset-hoop-earrings-18k-yellow-gold','Jessica McCormack Gypset Hoop Earrings, 18k Yellow Gold','Jessica McCormack','Gypset','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','jessica-mccormack-jessica-mccormack-party-hat-solitaire-ring-18k-yellow-gold','Jessica McCormack Party Hat Solitaire Ring, 18k Yellow Gold','Jessica McCormack','Party Hat','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','nikos-koulis-nikos-koulis-oui-ring-18k-white-gold','Nikos Koulis Oui Ring, 18k White Gold','Nikos Koulis','Oui','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','ara-vartanian-ara-vartanian-inverted-diamond-ring-18k-black-gold','Ara Vartanian Inverted Diamond Ring, 18k Black Gold','Ara Vartanian','Inverted','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','sabbadini-sabbadini-bow-brooch-18k-yellow-gold','Sabbadini Bow Brooch, 18k Yellow Gold','Sabbadini','Bow','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','picchiotti-picchiotti-xpandable-bracelet-18k-white-gold','Picchiotti Xpandable Bracelet, 18k White Gold','Picchiotti','Xpandable','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','bea-bongiasca-bea-bongiasca-vine-ring-9k-yellow-gold-with-enamel','Bea Bongiasca Vine Ring, 9k Yellow Gold with Enamel','Bea Bongiasca','Vine','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','yvonne-leon-yvonne-leon-pearl-drop-earrings-18k-yellow-gold','Yvonne Léon Pearl Drop Earrings, 18k Yellow Gold','Yvonne Léon','Pearl Drop','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','retrouvai-retrouvai-lollipop-ring-14k-yellow-gold','Retrouvaí Lollipop Ring, 14k Yellow Gold','Retrouvaí','Lollipop','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','melissa-kaye-melissa-kaye-lola-needle-earrings-18k-rose-gold','Melissa Kaye Lola Needle Earrings, 18k Rose Gold','Melissa Kaye','Lola','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','silvia-furmanovich-silvia-furmanovich-marquetry-earrings-18k-yellow-gold','Silvia Furmanovich Marquetry Earrings, 18k Yellow Gold','Silvia Furmanovich','Marquetry','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','viltier-viltier-magnetic-ring-18k-rose-gold','Viltier Magnetic Ring, 18k Rose Gold','Viltier','Magnetic','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','elie-top-elie-top-mecanismes-celestes-pendant-sterling-silver-and-18k-gold','Elie Top Mécanismes Célestes Pendant, Sterling Silver and 18k Gold','Elie Top','Mécanismes Célestes','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','delfina-delettrez-delfina-delettrez-two-in-one-pearl-earring-18k-yellow-gold','Delfina Delettrez Two in One Pearl Earring, 18k Yellow Gold','Delfina Delettrez','Two in One','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','cindy-chao-cindy-chao-black-label-butterfly-brooch-titanium','Cindy Chao Black Label Butterfly Brooch, Titanium','Cindy Chao','Black Label','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','wallace-chan-wallace-chan-titanium-butterfly-brooch','Wallace Chan Titanium Butterfly Brooch','Wallace Chan','Butterfly','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','sylva-and-cie-sylva-and-cie-vintage-cushion-ring-18k-yellow-gold','Sylva & Cie Vintage Cushion Ring, 18k Yellow Gold','Sylva & Cie','Vintage Cushion','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb),
  ('jewellery','briony-raymond-briony-raymond-cascade-earrings-18k-yellow-gold','Briony Raymond Cascade Earrings, 18k Yellow Gold','Briony Raymond','Cascade','seed',false,'{"seed_batch": "jewellery_2026_08_12b"}'::jsonb)
ON CONFLICT (category, item_key) DO NOTHING;

SELECT count(*) AS rows_now, count(DISTINCT brand) AS brands,
       count(*) FILTER (WHERE attributes_json->>'seed_batch'='jewellery_2026_08_12b') AS this_batch
FROM category_items WHERE category='jewellery';

COMMIT;

-- Reversal: check nothing bound to these keys first —
--   SELECT count(*) FROM items WHERE canonical_key IN (
--     SELECT item_key FROM category_items
--     WHERE attributes_json->>'seed_batch'='jewellery_2026_08_12b');
-- then DELETE FROM category_items WHERE category='jewellery'
--   AND attributes_json->>'seed_batch'='jewellery_2026_08_12b';
