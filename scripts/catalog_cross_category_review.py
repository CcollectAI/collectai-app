#!/usr/bin/env python3
"""Surface suspicious cross-category catalog placements."""
import importlib
import logging
import os
import re
import sys
from collections import defaultdict

# Silence pipeline import logs
logging.getLogger().setLevel(logging.ERROR)
for name in ('collectai.pipeline', 'collectai', 'root'):
    logging.getLogger(name).setLevel(logging.ERROR)

sys.path.insert(0, 'server')


def normalize(t: str) -> str:
    if not t:
        return ''
    s = re.sub(r'[^\w\s]', ' ', t.lower())
    return re.sub(r'\s+', ' ', s).strip()


# Categories that legitimately share titles — same character/franchise across formats.
# Wider than strictly necessary so we catch the obvious legit overlaps and only
# surface things that actually need a human eyeball.
LEGITIMATE_CLUSTERS = [
    # Collectible figures — same character can exist as Funko, Hot Toys, LEGO minifig,
    # vintage Kenner, Marvel Legends, Bandai S.H.Figuarts, etc. All real distinct SKUs.
    {'hot_toys', 'funko', 'lego', 'vintage_toys', 'action_figures', 'marvel_legends',
     'bandai_premium', 'anime_figures', 'gunpla', 'designer_toys', 'plush_collectibles',
     'nintendo_merch', 'pop_fandom', 'theme_park', 'disney', 'ghibli', 'loungefly',
     'one_piece', 'one_piece_tcg', 'blind_box', 'vtuber', 'retro_pokemon'},
    # Music — same album exists as standard vinyl, city-pop vinyl, anime OST vinyl,
    # Taylor Swift edition, K-pop lightstick bundle, etc.
    {'vinyl', 'city_pop_vinyl', 'anime_ost_vinyl', 'anime_vinyl_expanded',
     'taylor_swift', 'kpop_lightsticks', 'kpop', 'anime_soundtrack', 'pop_fandom',
     'jp_event'},
    # Film — Blu-ray + steelbook + anime Blu-ray + 4K all overlap
    {'bluray', 'anime_bluray', 'bluray_steelbook'},
    # Print — manga / comic_books / jp_magazine all overlap on character titles
    {'manga', 'comic_books', 'jp_magazine', 'one_piece'},
    # TCG — same character exists as Pokemon card AND One Piece card etc
    {'sportscards', 'pokemon', 'mtg', 'yugioh', 'lorcana', 'one_piece', 'one_piece_tcg'},
    # Gaming hardware/merch — Nintendo merch + retro games overlap
    {'retro_games', 'retro_handhelds', 'retro_pokemon', 'nintendo_merch', 'pop_fandom'},
    # Vehicles — same supercar exists as LEGO Technic, diecast, scale model
    {'scale_models', 'diecast', 'lego'},
    # Idol / event / fashion
    {'sneakers', 'streetwear', 'loungefly'},
    {'watches', 'jewelry', 'fragrances', 'whiskey'},  # luxury cluster
    {'keycaps', 'vintage_cameras'},
]


def cluster_for(cats: set) -> bool:
    """True if every category in `cats` fits inside one legitimate cluster."""
    for cluster in LEGITIMATE_CLUSTERS:
        if cats <= cluster:
            return True
    return False


def main():
    title_to_cats = defaultdict(set)
    title_to_examples = {}

    for f in sorted(os.listdir('server/pipelines')):
        if not f.startswith('import_') or not f.endswith('.py'):
            continue
        if f in ('import_common.py', 'import_all.py', 'import_books_isbn.py'):
            continue
        cat = f.removeprefix('import_').removesuffix('.py')
        try:
            m = importlib.import_module(f'pipelines.{f[:-3]}')
            fn = getattr(m, 'get_curated_catalog', None)
            if not fn:
                continue
            for item in fn():
                if isinstance(item, dict):
                    t = item.get('title') or item.get('name') or ''
                else:
                    t = getattr(item, 'title', '') or getattr(item, 'name', '')
                if not t:
                    continue
                n = normalize(t)
                title_to_cats[n].add(cat)
                title_to_examples[n] = t
        except Exception as e:
            print(f'  ! pipeline {cat} import failed: {e}', file=sys.stderr)
            continue

    overlaps = [(n, cats) for n, cats in title_to_cats.items() if len(cats) >= 2]
    legit = [(n, c) for n, c in overlaps if cluster_for(c)]
    suspicious = [(n, c) for n, c in overlaps if not cluster_for(c)]

    print(f'Total cross-pipeline overlaps: {len(overlaps)}')
    print(f'  Legitimate (cluster match):  {len(legit)}')
    print(f'  Suspicious (review needed):  {len(suspicious)}')
    print()

    if not suspicious:
        print('No suspicious cross-category placements found. ✅')
        return

    # Group suspicious by category-pair signature
    by_pair = defaultdict(list)
    for n, cats in suspicious:
        sig = ' + '.join(sorted(cats))
        by_pair[sig].append(title_to_examples[n])

    print('Suspicious placements grouped by category combo:')
    print('=' * 78)
    for sig in sorted(by_pair.keys(), key=lambda s: (-len(by_pair[s]), s)):
        titles = by_pair[sig]
        print()
        print(f'━━ {sig}  ({len(titles)} items)')
        for t in titles[:20]:
            print(f'    • {t}')
        if len(titles) > 20:
            print(f'    ... +{len(titles) - 20} more')


if __name__ == '__main__':
    main()
