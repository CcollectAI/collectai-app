-- ═══════════════════════════════════════════════════════════════════════════
-- 007_content_machine_seeds.sql — Seed data for CollectAI Content Machine
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── Accounts ────────────────────────────────────────────────────────────

INSERT INTO content_accounts (handle, display_name, purpose, platform, content_focus) VALUES
  ('@collectai.app', 'CollectAI', 'Main brand — app features, market alerts, deals, conversion', 'tiktok',
   ARRAY['market-alert', 'deal-hunting', 'price-prediction', 'app-feature']),
  ('@collectai.finds', 'CollectAI Finds', 'Thrift finds, hidden gems, deal hunting, unboxing, process', 'tiktok',
   ARRAY['deal-hunting', 'unboxing-reveal', 'grading-guide', 'beginner-guide']),
  ('@collectai.grail', 'CollectAI Grails', 'Grail pieces, collection showcases, portfolio flex, rare items, lifestyle', 'tiktok',
   ARRAY['collection-showcase', 'lifestyle-collector', 'unboxing-reveal', 'price-prediction'])
ON CONFLICT (handle) DO NOTHING;

-- ─── Pillars ─────────────────────────────────────────────────────────────

INSERT INTO content_pillars (slug, name, description, target_mix_pct, default_cta, emoji, best_formats, best_presence) VALUES
  ('market-alert', 'Market Alert', 'Price movements, vaulted items, trending collectibles', 20,
   'Download CollectAI to track prices', '🚨',
   ARRAY['reveal', 'comparison', 'POV'], ARRAY['voiceover', 'text_only']),
  ('deal-hunting', 'Deal Hunting', 'Hidden gems, thrift finds, garage sale scores', 15,
   'Scan any collectible with CollectAI', '💎',
   ARRAY['reveal', 'unboxing', 'POV'], ARRAY['face', 'voiceover', 'hands_only']),
  ('collection-showcase', 'Collection Showcase', 'Portfolio flex, shelf tours, collection milestones', 15,
   'Track your collection in CollectAI', '👑',
   ARRAY['lifestyle', 'reveal', 'timelapse'], ARRAY['face', 'voiceover']),
  ('grading-guide', 'Grading Guide', 'Condition assessment, authentication, grading tips', 10,
   'Get AI condition grades with CollectAI', '🔍',
   ARRAY['tutorial', 'comparison', 'POV'], ARRAY['hands_only', 'voiceover']),
  ('unboxing-reveal', 'Unboxing & Reveal', 'New pickups, mail day, pack openings', 10,
   'See what it''s worth — scan with CollectAI', '📦',
   ARRAY['unboxing', 'reveal', 'ASMR'], ARRAY['hands_only', 'face']),
  ('price-prediction', 'Price Prediction', 'What''s going up, what''s crashing, investment tips', 10,
   'CollectAI predicts prices with ML', '📈',
   ARRAY['comparison', 'reveal', 'tutorial'], ARRAY['voiceover', 'text_only']),
  ('beginner-guide', 'Beginner Guide', 'How to start collecting, avoid fakes, first buys', 10,
   'Start your collection with CollectAI', '🎓',
   ARRAY['tutorial', 'comparison', 'fix-it'], ARRAY['face', 'voiceover']),
  ('lifestyle-collector', 'Collector Lifestyle', 'Desk setup, display shelves, collector routines', 5,
   'Organize your collection in CollectAI', '🏠',
   ARRAY['lifestyle', 'timelapse', 'routine'], ARRAY['face', 'hands_only']),
  ('app-feature', 'App Feature', 'CollectAI demos, QuickScan, portfolio analytics, new features', 5,
   'Download CollectAI — link in bio', '📱',
   ARRAY['tutorial', 'reveal', 'transformation'], ARRAY['voiceover', 'hands_only'])
ON CONFLICT (slug) DO NOTHING;

-- ─── Niches ──────────────────────────────────────────────────────────────

INSERT INTO content_niches (slug, name, category_slug, emoji, price_range, audience_tags, trending_topics, short_description, personality_tags) VALUES
  ('pokemon-tcg', 'Pokemon TCG', 'pokemon_tcg', '💠', '$1 - $500K', ARRAY['gen-z', 'nostalgia', 'investors'], ARRAY['Prismatic Evolutions', 'PSA 10 chase', 'alt art'], 'The biggest TCG market — nostalgia meets investment', ARRAY['competitive', 'nostalgic', 'hype']),
  ('mtg', 'Magic: The Gathering', 'mtg', '🪄', '$1 - $100K', ARRAY['millennials', 'competitive', 'collectors'], ARRAY['Reserved List', 'Modern staples', 'foil chase'], 'The OG TCG with deep collector value', ARRAY['strategic', 'patient', 'knowledgeable']),
  ('funko-pop', 'Funko Pop', 'funko', '👾', '$5 - $15K', ARRAY['gen-z', 'pop-culture', 'casual'], ARRAY['vaulted Pops', 'SDCC exclusives', 'grail hunt'], 'Pop culture collectibles with huge community', ARRAY['fun', 'hunting', 'completionist']),
  ('lego', 'LEGO', 'lego', '🧱', '$10 - $10K', ARRAY['all-ages', 'families', 'investors'], ARRAY['retiring sets', 'GWP chase', 'modular buildings'], 'Sets that appreciate faster than stocks', ARRAY['patient', 'detail-oriented', 'builder']),
  ('sneakers', 'Sneakers', 'sneakers', '👟', '$50 - $50K', ARRAY['gen-z', 'streetwear', 'investors'], ARRAY['Nike SB dunks', 'Jordan retros', 'Travis Scott'], 'Hype-driven market with rapid price swings', ARRAY['trendy', 'fast-paced', 'knowledgeable']),
  ('watches', 'Watches', 'watches', '⌚', '$100 - $500K', ARRAY['millennials', 'luxury', 'investors'], ARRAY['Rolex waitlists', 'Omega Swatch', 'micro-brands'], 'Horological treasures and investment pieces', ARRAY['patient', 'refined', 'knowledgeable']),
  ('vinyl', 'Vinyl Records', 'vinyl', '🎵', '$5 - $25K', ARRAY['millennials', 'music-lovers', 'crate-diggers'], ARRAY['first pressings', 'colored vinyl', 'RSD drops'], 'Analog warmth meets collector passion', ARRAY['passionate', 'knowledgeable', 'patient']),
  ('warhammer', 'Warhammer 40K', 'warhammer', '⚔️', '$10 - $5K', ARRAY['millennials', 'hobbyists', 'painters'], ARRAY['OOP models', 'Forge World', 'pro-painted'], 'Tabletop gaming meets fine art', ARRAY['creative', 'patient', 'detail-oriented']),
  ('yugioh', 'Yu-Gi-Oh!', 'yugioh', '🃏', '$1 - $100K', ARRAY['gen-z', 'nostalgia', 'competitive'], ARRAY['Ghost Rares', 'Starlight Rares', 'QCSR'], 'Ghost Rares and Starlight Rares driving massive value', ARRAY['competitive', 'nostalgic', 'sharp']),
  ('kpop', 'K-pop Merch', 'kpop', '🎤', '$5 - $5K', ARRAY['gen-z', 'global', 'completionist'], ARRAY['photocards', 'fansign exclusives', 'season greetings'], 'Photocard culture with intense trading community', ARRAY['passionate', 'social', 'completionist']),
  ('hot-toys', 'Hot Toys', 'hot_toys', '🧸', '$200 - $10K', ARRAY['millennials', 'movie-fans', 'display'], ARRAY['Marvel exclusives', 'Star Wars', 'sold-out figures'], 'Museum-quality sixth-scale figures', ARRAY['patient', 'display-focused', 'premium']),
  ('manga', 'Manga', 'manga', '📚', '$5 - $5K', ARRAY['gen-z', 'anime-fans', 'readers'], ARRAY['OOP volumes', 'box sets', 'first editions'], 'Out-of-print volumes driving collector demand', ARRAY['patient', 'knowledgeable', 'passionate'])
ON CONFLICT (slug) DO NOTHING;

-- ─── Products (App Features) ─────────────────────────────────────────────

INSERT INTO content_products (slug, name, category, description, tier, best_content_angles) VALUES
  ('collectai-free', 'CollectAI Free', 'app', 'Free tier — collection tracking, basic scanning', 'free',
   ARRAY['demo', 'beginner', 'comparison']),
  ('collectai-pro', 'CollectAI Pro', 'subscription', 'Pro tier — portfolio analytics, condition grading, set completion', 'pro',
   ARRAY['feature-demo', 'before-after', 'conversion']),
  ('quickscan', 'QuickScan', 'feature', 'AI-powered instant item identification and valuation', 'free',
   ARRAY['reveal', 'magic-moment', 'demo']),
  ('portfolio-analytics', 'Portfolio Analytics', 'feature', 'Track portfolio value, ROI, condition distribution', 'pro',
   ARRAY['showcase', 'data-reveal', 'flex']),
  ('deal-desk', 'Deal Desk', 'feature', 'P2P marketplace with AI risk assessment', 'pro',
   ARRAY['deal-hunting', 'trust', 'demo']),
  ('price-alerts', 'Price Alerts', 'feature', 'Real-time notifications on price movements', 'free',
   ARRAY['urgency', 'FOMO', 'demo']),
  ('condition-grading', 'AI Condition Grading', 'feature', 'AI-powered condition assessment with confidence scores', 'pro',
   ARRAY['grading', 'education', 'comparison'])
ON CONFLICT (slug) DO NOTHING;
