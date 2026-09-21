#!/usr/bin/env bash
# READ-ONLY. Prints ONE line of coverage numbers. Run: bash tier_probe.sh
set -euo pipefail
ssh collectai 'bash -s' <<'REMOTE'
set -euo pipefail
DSN=$(grep -E '^DB_DSN_DIRECT=' /opt/collectors/.env | sed 's/^DB_DSN_DIRECT=//' | tr -d '"'"'"'')
psql "$DSN" -At -v ON_ERROR_STOP=1 <<'SQL'
SELECT 'COVERAGE'
  || ' items=' || count(*)
  || ' resolve_catalogue=' || count(ci.item_key)
  || ' catalogue_rarity=' || count(*) FILTER (WHERE ci.rarity IS NOT NULL)
  || ' own_attrs_signal=' || count(*) FILTER (WHERE i.attrs ?| array['rarity','foil','holo','variant','finish','subtype','type'] OR i.attrs->>'is_foil' = 'true')
  || ' named_set=' || count(*) FILTER (WHERE i.collection_name IS NOT NULL)
  || ' has_canon_key=' || count(i.canonical_key)
FROM items i
LEFT JOIN LATERAL (
  SELECT ci.item_key, ci.rarity FROM category_items ci
  WHERE ci.item_key = i.canonical_key AND ci.category = i.category LIMIT 1
) ci ON TRUE
WHERE NOT i.archived;
SQL
REMOTE
