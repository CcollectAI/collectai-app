-- canonical_ref only for a key the catalogue knows (OPEN_DECISIONS #17, 2026-09-28).
--
-- The function passed ANY key through as `category:key`. A key that is not a
-- catalogue item (`charizard`, written by a seed script; any direct Supabase
-- write or API call can do the same) still got a ref, and that ref matched the
-- title-filed predictions of whatever free-text scrape shared the slug. The
-- test account's "Charizard (Base Set 004)" showed "Our comps say €10": a
-- 2026-09-06 prediction over 8 eBay rows under `pokemon:charizard` — plushies
-- and a 25th-anniversary box — while the card itself holds EUR 812-1,531 sales.
--
-- A wrong ref is worse than none (items_router._resolve_canonical_key): no ref
-- means the item shows the member's own value, not a confident wrong one.
--
-- Unchanged: NULL key -> NULL; the category-prefix guard of 20260725; the
-- crosswalk (catalog_price_refs) and the direct-vs-mapped choice.
CREATE OR REPLACE FUNCTION public.items_resolve_canonical_ref() RETURNS trigger AS $fn$
    DECLARE direct text; mapped text; bare text;
    BEGIN
        IF NEW.canonical_key IS NULL OR NEW.category IS NULL THEN
            NEW.canonical_ref := NULL; RETURN NEW;
        END IF;
        -- Already namespaced WITH THIS ITEM'S CATEGORY -> never double-prefix
        -- (tcgcsv keys are natively colon-bearing; see 20260725).
        IF split_part(NEW.canonical_key, ':', 1) = NEW.category THEN
            bare := substr(NEW.canonical_key, length(NEW.category) + 2);
            direct := NEW.canonical_key;
        ELSE
            bare := NEW.canonical_key;
            direct := NEW.category || ':' || NEW.canonical_key;
        END IF;
        SELECT x.price_ref INTO mapped FROM public.catalog_price_refs x
         WHERE x.category = NEW.category AND x.item_key = bare;
        IF mapped IS NULL AND NOT EXISTS (
            SELECT 1 FROM public.category_items ci
             WHERE ci.category = NEW.category
               AND ci.item_key IN (bare, NEW.canonical_key)
        ) THEN
            NEW.canonical_ref := NULL; RETURN NEW;
        END IF;
        IF bare <> NEW.canonical_key THEN
            -- Namespaced key: pass through as before, now that it is known.
            NEW.canonical_ref := direct; RETURN NEW;
        END IF;
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
