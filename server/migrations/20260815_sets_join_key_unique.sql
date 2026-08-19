-- `sets` is joined from /portfolio/items as
--     LEFT JOIN sets s ON s.category_id = i.category
--                     AND lower(s.name) = lower(i.collection_name)
-- and had no constraint making that key unique. Two rows differing only by
-- case ('Base Set' / 'base set') would match the same item twice, and a LEFT
-- JOIN that matches twice DUPLICATES the item row — so `owned` would climb
-- without anybody adding anything, and the completeness percentage with it.
--
-- Enforced on the same expression the join uses, so the guard and the query
-- live in the same type/case space (learning_guard_must_match_constraint_type_space).
CREATE UNIQUE INDEX IF NOT EXISTS sets_category_lower_name_uniq
    ON public.sets (category_id, lower(name));
