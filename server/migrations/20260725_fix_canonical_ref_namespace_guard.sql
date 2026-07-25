-- Fix: canonical_ref lost its category prefix for every colon-bearing item_key.
--
-- The guard tested `strpos(canonical_key, ':') > 0` -- "contains a colon" --
-- as a proxy for "already namespaced". tcgcsv-derived keys are NATIVELY
-- colon-bearing (`tcgplayer:593032:cold_foil`), so 80,607 of 221,278 catalog
-- rows (all of yugioh 58,565, digimon 9,045, one_piece_tcg 6,841 and lorcana
-- 6,156) were treated as pre-namespaced and never got their prefix.
--
-- canonical_ref came out as `tcgplayer:593032:cold_foil` while
-- price_predictions holds `lorcana:tcgplayer:593032:cold_foil`, so the join
-- matched nothing and the item was silently unpriceable -- in exactly the
-- categories CLAUDE.md calls "100% priceable by construction". The
-- construction was right; this guard discarded it.
--
-- Correct test: is the prefix THIS ITEM'S CATEGORY. Found by an authenticated
-- end-to-end POST /items, which is the only check that exercised the whole
-- chain; 10 green audits missed it because each asked a structural question.
--
-- Verified before: canonical_ref=tcgplayer:593032:cold_foil, priced=False
--          after : canonical_ref=lorcana:tcgplayer:593032:cold_foil, priced=True
CREATE OR REPLACE FUNCTION public.items_resolve_canonical_ref() RETURNS trigger AS $fn$
    DECLARE direct text; mapped text;
    BEGIN
        IF NEW.canonical_key IS NULL THEN
            NEW.canonical_ref := NULL; RETURN NEW;
        END IF;
        -- Already namespaced WITH THIS ITEM'S CATEGORY -> never double-prefix.
        IF split_part(NEW.canonical_key, ':', 1) = NEW.category THEN
            NEW.canonical_ref := NEW.canonical_key; RETURN NEW;
        END IF;
        IF NEW.category IS NULL THEN
            NEW.canonical_ref := NULL; RETURN NEW;
        END IF;
        direct := NEW.category || ':' || NEW.canonical_key;
        SELECT x.price_ref INTO mapped FROM public.catalog_price_refs x
         WHERE x.category = NEW.category AND x.item_key = NEW.canonical_key;
        IF EXISTS (SELECT 1 FROM public.price_predictions p
                   WHERE p.item_ref = direct
                     AND p.generated_at >= now() - interval '30 days') THEN
            NEW.canonical_ref := direct;
        ELSE
            NEW.canonical_ref := COALESCE(mapped, direct);
        END IF;
        RETURN NEW;
    END
$fn$ LANGUAGE plpgsql;
