#!/usr/bin/env python3
"""Generate the per-collectible landing pages web/value/<slug>.html.

One page per search intent ("pokemon card value", "lego set value", ...).
Everything on a page must be TRUE for the shipped app:

- The FAQ answers are copied verbatim from the FAQPage JSON-LD in
  web/guides.html (vetted in 4e3ae099). They are referenced by question text,
  so a rewritten guide question fails this script instead of silently dropping.
- The "where the prices come from" line is a MEASUREMENT, not a claim:
  market_hits rows per category/provider over the 30 days to 2026-10-12.
  Re-measure before changing it:
    SELECT category, provider, is_listing, count(*) FROM market_hits
    WHERE seen_at > now() - interval '30 days' GROUP BY 1,2,3;
  eBay rows are LISTINGS (asking prices) — never call them sold prices.

Run:  python3 scripts/build_value_pages.py   (rewrites web/value/*.html and
the <url> block for /value/ pages in web/sitemap.xml and the
'## Price guides' list in web/llms.txt)
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
OUT = WEB / "value"
SITE = "https://sparrowcollect.com"
APP_STORE = "https://apps.apple.com/app/id6767359453"
MEASURED = "the 30 days to 12 October 2026"

PAGES = [
    {
        "slug": "pokemon-cards",
        "name": "Pokémon cards",
        "title": "Pokémon Card Value Scanner & Price Guide | Sparrow Collect",
        "h1": "What are my Pokémon cards worth?",
        "desc": "Scan a Pokémon card with your phone to identify the card, set and variant and see a value built from TCGplayer and Cardmarket prices plus eBay listings.",
        "intro": "Point your camera at a Pokémon card and Sparrow Collect identifies the card, set and variant, then shows a low, mid and high value with the prices it rests on. Vintage holos, full arts, Japanese and English cards all live in one collection.",
        "sources": "TCGplayer and Cardmarket card prices, plus eBay listings",
        "faq": [
            "What are my Pokemon cards worth?",
            "What is the best Pokemon card scanner app?",
            "Should I get my Pokemon cards graded?",
            "Japanese vs. English Pokemon cards — which are worth more?",
            "When is the best time to sell Pokemon cards?",
            "How do I tell if a Pokemon card is fake?",
            "How do I start collecting Pokemon cards?",
        ],
    },
    {
        "slug": "magic-the-gathering-cards",
        "name": "Magic: The Gathering cards",
        "title": "MTG Card Value Scanner & Price Guide | Sparrow Collect",
        "h1": "How much are my Magic: The Gathering cards worth?",
        "desc": "Scan Magic: The Gathering cards to identify the card, set and edition and see a value built from Scryfall card prices and eBay listings.",
        "intro": "Scan a Magic card and Sparrow Collect identifies the exact card, set and edition, then values it from card-market prices with the working shown. Standard, Modern, Legacy and Vintage cards sit in one portfolio next to the rest of your collection.",
        "sources": "Scryfall card prices, plus eBay listings",
        "faq": [
            "How much are my Magic: The Gathering cards worth?",
            "How do I tell if a sealed booster box has been resealed?",
            "PSA 9 vs. PSA 10 — how much does one grade matter?",
            "How do I know if a grading slab is authentic?",
        ],
    },
    {
        "slug": "yugioh-cards",
        "name": "Yu-Gi-Oh! cards",
        "title": "Yu-Gi-Oh! Card Value Scanner & Price Guide | Sparrow Collect",
        "h1": "What are my Yu-Gi-Oh! cards worth?",
        "desc": "Scan Yu-Gi-Oh! cards to identify the set and rarity and see a value built from Cardmarket and TCGplayer prices. Ghost Rares, Starlights and 1st Editions.",
        "intro": "Scan a Yu-Gi-Oh! card and Sparrow Collect identifies the card, set and rarity, then shows a value range built from card-market prices. Ghost Rares, Starlight Rares and 1st Edition cards are tracked alongside sealed product.",
        "sources": "Cardmarket and TCGplayer card prices",
        "faq": [
            "What are my Yu-Gi-Oh! cards worth?",
            "Should I grade my Yu-Gi-Oh! cards?",
            "How do I tell if a sealed booster box has been resealed?",
        ],
    },
    {
        "slug": "sports-cards",
        "name": "sports cards",
        "title": "Sports Card Value Scanner & Price Guide | Sparrow Collect",
        "h1": "What is my sports card collection worth?",
        "desc": "Scan baseball, basketball, football and hockey cards to identify them and see a value built from eBay listings. Rookies and autographs in one app.",
        "intro": "Scan a baseball, basketball, football or hockey card and Sparrow Collect identifies it and values it from marketplace listings, with the working shown. Rookies, autographs and numbered parallels all fit in one collection.",
        "sources": "eBay listings",
        "faq": [
            "What is the value of my sports card collection?",
            "Should I grade my sports cards?",
            "PSA vs. BGS vs. CGC — which grading service should I use?",
            "Hobby box vs. retail box — which is better for value?",
            "How do I know if my card will get a PSA 10?",
        ],
    },
    {
        "slug": "funko-pop",
        "name": "Funko Pops",
        "title": "Funko Pop Value Scanner & Price Guide | Sparrow Collect",
        "h1": "How much is my Funko Pop worth?",
        "desc": "Scan a Funko Pop to identify the figure, variant and exclusive edition and see a value built from eBay listings. Commons, chases, vaulted and convention grails.",
        "intro": "Scan a Funko Pop box and Sparrow Collect identifies the figure, variant and exclusive edition, then shows a value range built from marketplace listings. Commons, chases, vaulted figures and convention exclusives all go in one collection.",
        "sources": "eBay listings",
        "faq": [
            "How much is my Funko Pop worth?",
            "What is the best app for Funko Pop collectors?",
            "When should I sell my Funko Pops?",
            "How do I spot a fake Funko Pop?",
            "How do I start a Funko Pop collection?",
        ],
    },
    {
        "slug": "lego-sets",
        "name": "LEGO sets",
        "title": "LEGO Set Value Checker & Price Guide | Sparrow Collect",
        "h1": "How do I check the value of my LEGO sets?",
        "desc": "Scan a LEGO set (barcode works for sealed boxes) and see a value built from eBay listings, sealed or opened. Track retired sets across your whole collection.",
        "intro": "Scan a LEGO set (barcode scanning works for sealed boxes) and Sparrow Collect identifies it, then values it as sealed or opened from marketplace listings. Retired Star Wars, Modular Buildings and Technic sets are tracked next to everything else you collect.",
        "sources": "eBay listings",
        "faq": [
            "How do I check the value of my LEGO sets?",
            "Sealed vs. opened LEGO — which is worth more?",
            "Should I sell or hold my LEGO sets?",
            "What should I know before collecting LEGO?",
        ],
    },
    {
        "slug": "vinyl-records",
        "name": "vinyl records",
        "title": "Vinyl Record Value Scanner & Price Guide | Sparrow Collect",
        "h1": "What is my vinyl record collection worth?",
        "desc": "Scan a record to identify the release and see a value built from Discogs and eBay listings, graded on the Goldmine scale.",
        "intro": "Scan a record and Sparrow Collect identifies the release, then values it from Discogs and eBay listings with Goldmine condition grading. First pressings, coloured variants and Japanese City Pop all sit in one collection.",
        "sources": "Discogs listings and eBay listings",
        "faq": [
            "What is my vinyl record collection worth?",
            "What is the best app for tracking vinyl record values?",
            "What does condition mean for vinyl record value?",
            "First pressing vs. reissue vinyl — how much does it matter?",
            "Should I sell my vinyl records or keep them?",
            "How do I start collecting vinyl records?",
        ],
    },
    {
        "slug": "retro-video-games",
        "name": "retro video games",
        "title": "Retro Video Game Value Scanner | Sparrow Collect",
        "h1": "How much are my retro video games worth?",
        "desc": "Scan NES, SNES, N64, PlayStation and Sega games to identify them and see a value built from eBay listings. Track every game in one app.",
        "intro": "Scan a cartridge, disc or box and Sparrow Collect identifies the game, then values it from marketplace listings. NES, SNES, N64, PlayStation, Sega and handheld games all go in one collection.",
        "sources": "eBay listings",
        "faq": [
            "How much are retro video games worth?",
            "What should I look for when buying vintage toys?",
            "How should I store my collectibles to preserve value?",
        ],
    },
    {
        "slug": "anime-figures",
        "name": "anime figures",
        "title": "Anime Figure Value Scanner & Price Guide | Sparrow Collect",
        "h1": "How do I find the value of anime figures?",
        "desc": "Scan anime figures from Good Smile, Kotobukiya, Alter and Bandai to identify them and see a value built from eBay listings. Scale figures, Nendoroids, prizes.",
        "intro": "Scan a figure or its box and Sparrow Collect identifies the figure, variant and edition, then shows a value range from marketplace listings. Scale figures, prize figures, Gunpla and Bandai Premium exclusives each have their own category.",
        "sources": "eBay listings",
        "faq": [
            "How do I find the value of anime figures?",
            "How do I spot a fake anime figure or bootleg?",
            "Does Sparrow Collect work for Japanese collectibles?",
            "How do I start collecting anime figures?",
        ],
    },
    {
        "slug": "watches",
        "name": "watches",
        "title": "Watch Collection Value Tracker | Sparrow Collect",
        "h1": "How do I value my watch collection?",
        "desc": "Photograph a watch to identify it and see a value built from eBay listings. Rolex, Omega, Seiko, vintage and modern, in one app.",
        "intro": "Photograph a watch and Sparrow Collect identifies it, then values it from marketplace listings. Seiko, Omega, Rolex and the rest of your collection sit in one portfolio.",
        "sources": "eBay listings",
        "faq": [
            "How do I value my watch collection?",
            "How do I verify a vintage watch is genuine?",
            "How do I start collecting watches?",
        ],
    },
    # --- added 2026-10-13; sources re-measured that day (30 days to 2026-10-13):
    # lorcana = lorcast 70,460 + ebay 1,904; hot_toys ebay 3,796; warhammer ebay
    # 5,930; gunpla ebay 4,762; diecast ebay 8,171.
    {
        "slug": "lorcana-cards",
        "name": "Disney Lorcana cards",
        "title": "Disney Lorcana Card Value Scanner | Sparrow Collect",
        "h1": "What are my Disney Lorcana cards worth?",
        "desc": "Scan Disney Lorcana cards to identify the card and set and see a value built from Lorcast card prices and eBay listings. All sets and promos.",
        "intro": "Scan a Lorcana card and Sparrow Collect identifies the exact card, set and variant, then shows a low, mid and high value with the prices it rests on. Every set and promo sits in one collection next to your other games.",
        "sources": "Lorcast card prices, plus eBay listings",
        "faq": [
            "How do I find out what my collectibles are worth?",
            "How do I tell if a sealed booster box has been resealed?",
            "How should I store my collectibles to preserve value?",
        ],
    },
    {
        "slug": "hot-toys",
        "name": "Hot Toys figures",
        "title": "Hot Toys Figure Value Scanner | Sparrow Collect",
        "h1": "What are my Hot Toys figures worth?",
        "desc": "Scan Hot Toys 1/6 scale figures from Star Wars, Marvel and DC to identify them and see a value built from eBay listings. Track every figure in one app.",
        "intro": "Scan a Hot Toys figure or its box and Sparrow Collect identifies the figure, variant and exclusive edition, then shows a value range from marketplace listings. Star Wars, Marvel and DC 1/6 scale figures sit in one collection.",
        "sources": "eBay listings",
        "faq": [
            "What are my Hot Toys figures worth?",
            "How should I store my collectibles to preserve value?",
            "Is there one app for all my collectibles?",
        ],
    },
    {
        "slug": "warhammer",
        "name": "Warhammer miniatures",
        "title": "Warhammer Collection Value Tracker | Sparrow Collect",
        "h1": "How much is my Warhammer collection worth?",
        "desc": "Track the value of Warhammer 40K and Age of Sigmar miniatures, sealed or painted, with values built from eBay listings. Your whole army in one app.",
        "intro": "Add your Warhammer 40K and Age of Sigmar boxes and armies, sealed or painted, and Sparrow Collect values them from marketplace listings with the working shown. Your miniatures sit next to everything else you collect.",
        "sources": "eBay listings",
        "faq": [
            "How much is my Warhammer collection worth?",
            "How do I find out what my collectibles are worth?",
            "How should I store my collectibles to preserve value?",
        ],
    },
    {
        "slug": "gunpla",
        "name": "Gunpla model kits",
        "title": "Gunpla Model Kit Value Scanner | Sparrow Collect",
        "h1": "What are my Gunpla model kits worth?",
        "desc": "Scan Gunpla kits (HG, MG, PG, RG) to identify them and see a value built from eBay listings. Track built and sealed kits in one app.",
        "intro": "Scan a Gunpla box and Sparrow Collect identifies the kit, then values it from marketplace listings with the prices behind every value. HG, MG, PG and RG kits sit in one collection next to your figures and Bandai Premium exclusives.",
        "sources": "eBay listings",
        "faq": [
            "How do I spot a fake anime figure or bootleg?",
            "Does Sparrow Collect work for Japanese collectibles?",
            "How should I store my collectibles to preserve value?",
        ],
    },
    {
        "slug": "diecast-hot-wheels",
        "name": "diecast cars",
        "title": "Hot Wheels & Diecast Value Scanner | Sparrow Collect",
        "h1": "How much are my Hot Wheels and diecast cars worth?",
        "desc": "Scan Hot Wheels, Tomica and 1:18 scale diecast cars to identify them and see a value built from eBay listings. Track every car in one app.",
        "intro": "Scan a car or its card and Sparrow Collect identifies it, then values it from marketplace listings with the working shown. Hot Wheels, Tomica and 1:18 scale models sit in one collection.",
        "sources": "eBay listings",
        "faq": [
            "What should I look for when buying vintage toys?",
            "How do I find out what my collectibles are worth?",
            "How should I store my collectibles to preserve value?",
        ],
    },
    {
        "slug": "sneakers",
        "name": "sneakers",
        "title": "Sneaker Value Scanner & Resale Price Guide | Sparrow Collect",
        "h1": "How much are my sneakers worth?",
        "desc": "Scan a pair of sneakers to identify them and see a value built from eBay listings. Nike, Adidas, Jordan and collabs. Track every pair in one app.",
        "intro": "Scan a pair and Sparrow Collect identifies it, then values it from marketplace listings. Every pair sits in the same collection as your cards, figures and records.",
        "sources": "eBay listings",
        "faq": [
            "How much are my sneakers worth?",
            "How can I authenticate sneakers before buying?",
            "What should I know before collecting sneakers?",
        ],
    },
]


def load_guide_faq() -> dict[str, str]:
    s = (WEB / "guides.html").read_text()
    faq: dict[str, str] = {}
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
        j = json.loads(m.group(1))
        if j.get("@type") == "FAQPage":
            for q in j["mainEntity"]:
                faq[q["name"]] = q["acceptedAnswer"]["text"]
    return faq


def head_and_style() -> str:
    """Reuse the vetted <style> block of categories.html so the pages match."""
    s = (WEB / "categories.html").read_text()
    m = re.search(r"<style>.*?</style>", s, re.S)
    if not m:
        sys.exit("categories.html has no <style> block")
    extra = """
        .content { max-width: 760px; margin: 0 auto; padding: 8px 32px 40px; }
        .content h2 { font-size: 24px; font-weight: 800; margin: 32px 0 12px; }
        .content p, .content li { font-size: 16px; color: #475569; line-height: 1.7; }
        .content ol { padding-left: 22px; }
        .content li { margin-bottom: 6px; }
        .qa { border-bottom: 1px solid #e2e8f0; padding: 18px 0; }
        .qa h3 { font-size: 17px; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
        .related { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
        .related a { padding: 8px 14px; border: 1px solid rgba(129,216,208,0.4); border-radius: 999px; font-size: 14px; color: #334155; }
        .related a:hover { border-color: #81D8D0; }
        @media (max-width: 768px) { .content { padding: 8px 20px 32px; } }
    </style>"""
    return m.group(0).replace("</style>", extra)


def esc(t: str) -> str:
    return html.escape(t, quote=True)


def page(p: dict, faq: dict[str, str], style: str) -> str:
    url = f"{SITE}/value/{p['slug']}"
    qas = []
    for q in p["faq"]:
        if q not in faq:
            sys.exit(f"{p['slug']}: guide question not found in guides.html: {q!r}")
        qas.append((q, faq[q]))
    for field, limit in (("title", 63), ("desc", 160)):
        if len(p[field]) > limit:
            sys.exit(f"{p['slug']}: {field} is {len(p[field])} chars (> {limit})")

    breadcrumb = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Sparrow Collect", "item": SITE},
            {"@type": "ListItem", "position": 2, "name": "Categories", "item": f"{SITE}/categories"},
            {"@type": "ListItem", "position": 3, "name": p["h1"], "item": url},
        ],
    }
    faq_ld = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in qas
        ],
    }
    related = "\n".join(
        f'            <a href="/value/{o["slug"]}">{esc(o["name"][0].upper() + o["name"][1:])}</a>'
        for o in PAGES if o["slug"] != p["slug"]
    )
    qa_html = "\n".join(
        f'        <div class="qa">\n            <h3>{esc(q)}</h3>\n            <p>{esc(a)}</p>\n        </div>'
        for q, a in qas
    )
    t, d = esc(p["title"]), esc(p["desc"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{t}</title>
    <meta name="description" content="{d}">
    <link rel="canonical" href="{url}">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Sparrow Collect">
    <meta property="og:url" content="{url}">
    <meta property="og:title" content="{t}">
    <meta property="og:description" content="{d}">
    <meta property="og:image" content="{SITE}/og-card.jpg">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="Sparrow Collect app showing a collection with values">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{t}">
    <meta name="twitter:description" content="{d}">
    <meta name="twitter:image" content="{SITE}/og-card.jpg">
    <meta name="theme-color" content="#81D8D0">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
    <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&display=swap" rel="stylesheet">
    <script type="application/ld+json">
{json.dumps(breadcrumb, ensure_ascii=False, indent=2)}
    </script>
    <script type="application/ld+json">
{json.dumps(faq_ld, ensure_ascii=False, indent=2)}
    </script>
    {style}
</head>
<body>

    <nav class="nav">
        <a href="/" class="nav-left">
            <img src="/icon.png" alt="Sparrow Collect app icon" class="nav-icon" width="36" height="36">
            <div class="nav-brand">Sparrow<span>&nbsp;Collect</span></div>
        </a>
        <div class="nav-links">
            <a href="/#features" class="nav-link">Features</a>
            <a href="/categories" class="nav-link">Categories</a>
            <a href="/guides" class="nav-link">Guides</a>
            <a href="/#faq" class="nav-link">FAQ</a>
            <a href="/#download" class="nav-cta">Download</a>
        </div>
    </nav>

    <div class="breadcrumb">
        <a href="/">Sparrow Collect</a> &rsaquo; <a href="/categories">Categories</a> &rsaquo; {esc(p["name"][0].upper() + p["name"][1:])}
    </div>

    <div class="page-header">
        <h1>{esc(p["h1"])}</h1>
        <p>{esc(p["intro"])}</p>
    </div>

    <main class="content">
        <h2>How to value {esc(p["name"])} with your phone</h2>
        <ol>
            <li>Open Sparrow Collect and point your camera at the item.</li>
            <li>The app identifies it and asks for the condition options that fit {esc(p["name"])}.</li>
            <li>You get a low, mid and high value, with how many prices it rests on and which sources they came from.</li>
        </ol>

        <h2>Where the prices come from</h2>
        <p>Values for {esc(p["name"])} are built from {esc(p["sources"])} (the sources that delivered prices in {MEASURED}). Each value in the app shows the prices behind it, so you can see what it is based on instead of trusting a single number.</p>

        <h2>Questions collectors ask</h2>
{qa_html}

        <h2>More price guides</h2>
        <div class="related">
{related}
            <a href="/categories">All 56 categories</a>
            <a href="/guides">Collector guides</a>
        </div>
    </main>

    <section class="cta-banner">
        <h2>Scan your {esc(p["name"])}.</h2>
        <p>Free to download on iPhone. Android coming soon.</p>
        <a href="{APP_STORE}" class="cta-btn">Get Sparrow Collect on the App Store</a>
    </section>

    <footer class="footer">
        <div>&copy; 2026 Sparrow Collect. All rights reserved.</div>
        <div class="footer-links">
            <a href="/privacy">Privacy Policy</a>
            <a href="/terms">Terms of Service</a>
            <a href="/user-policy">Acceptable Use</a>
            <a href="mailto:support@sparrowcollect.com">Contact</a>
        </div>
    </footer>
    <script src="/referral.js" defer></script>
</body>
</html>
"""


def update_sitemap() -> None:
    sm = WEB / "sitemap.xml"
    s = sm.read_text()
    s = re.sub(r"\s*<url><loc>https://sparrowcollect\.com/value/[^<]*</loc>.*?</url>", "", s)
    today = date.today().isoformat()
    block = "".join(
        f"\n  <url><loc>{SITE}/value/{p['slug']}</loc><lastmod>{today}</lastmod></url>" for p in PAGES
    )
    s = s.replace("\n</urlset>", block + "\n</urlset>")
    sm.write_text(s)


def update_llms() -> None:
    """Rewrite the '## Price guides' list in web/llms.txt (read by AI crawlers)."""
    f = WEB / "llms.txt"
    s = f.read_text()
    if "## Price guides" not in s:
        sys.exit("llms.txt has no '## Price guides' section")
    items = "".join(f"- [{p['h1']}]({SITE}/value/{p['slug']}): {p['desc']}\n" for p in PAGES)
    s = re.sub(r"## Price guides\n.*?(?=\n## )", "## Price guides\n\n" + items, s, flags=re.S)
    f.write_text(s)


def main() -> None:
    faq = load_guide_faq()
    style = head_and_style()
    OUT.mkdir(exist_ok=True)
    for p in PAGES:
        (OUT / f"{p['slug']}.html").write_text(page(p, faq, style))
    update_sitemap()
    update_llms()
    print(f"wrote {len(PAGES)} pages to {OUT.relative_to(ROOT)} and updated sitemap.xml")


if __name__ == "__main__":
    main()
