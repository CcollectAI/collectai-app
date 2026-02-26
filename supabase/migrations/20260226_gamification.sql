-- =============================================================================
-- Gamification system: achievements, XP, streaks, challenges
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Achievement definitions (globally readable catalog)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.achievements (
    id TEXT PRIMARY KEY,                -- e.g., 'first_scan', 'collector_10'
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    icon TEXT NOT NULL,                  -- Ionicons icon name
    category TEXT NOT NULL CHECK (category IN (
        'scanning', 'collection', 'trading', 'social', 'building', 'streaks', 'milestones'
    )),
    xp_reward INT NOT NULL DEFAULT 10,
    tier TEXT NOT NULL DEFAULT 'bronze' CHECK (tier IN (
        'bronze', 'silver', 'gold', 'platinum', 'diamond'
    )),
    threshold INT,                      -- e.g., 10 for "Own 10 items"
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 2. User achievements (unlocked records)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_achievements (
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    achievement_id TEXT NOT NULL REFERENCES public.achievements(id) ON DELETE CASCADE,
    unlocked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    progress INT NOT NULL DEFAULT 0,    -- current progress toward threshold
    PRIMARY KEY (user_id, achievement_id)
);

-- ---------------------------------------------------------------------------
-- 3. User XP / level / streak tracking (one row per user)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_gamification (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    total_xp INT NOT NULL DEFAULT 0,
    level INT NOT NULL DEFAULT 1,
    current_streak INT NOT NULL DEFAULT 0,
    longest_streak INT NOT NULL DEFAULT 0,
    last_activity_date DATE,
    weekly_xp INT NOT NULL DEFAULT 0,
    monthly_xp INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 4. Challenges (weekly / monthly / special)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    challenge_type TEXT NOT NULL CHECK (challenge_type IN ('weekly', 'monthly', 'special')),
    category TEXT,                       -- optional category filter
    target_count INT NOT NULL DEFAULT 1,
    xp_reward INT NOT NULL DEFAULT 50,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 5. User challenge progress
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_challenge_progress (
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    challenge_id UUID NOT NULL REFERENCES public.challenges(id) ON DELETE CASCADE,
    current_count INT NOT NULL DEFAULT 0,
    completed BOOLEAN NOT NULL DEFAULT false,
    completed_at TIMESTAMPTZ,
    PRIMARY KEY (user_id, challenge_id)
);

-- ===========================================================================
-- Indexes
-- ===========================================================================
CREATE INDEX IF NOT EXISTS idx_achievements_category ON public.achievements(category);
CREATE INDEX IF NOT EXISTS idx_achievements_tier ON public.achievements(tier);
CREATE INDEX IF NOT EXISTS idx_achievements_sort ON public.achievements(sort_order);

CREATE INDEX IF NOT EXISTS idx_user_achievements_user ON public.user_achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_user_achievements_unlocked ON public.user_achievements(user_id, unlocked_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_gamification_xp ON public.user_gamification(total_xp DESC);
CREATE INDEX IF NOT EXISTS idx_user_gamification_weekly ON public.user_gamification(weekly_xp DESC);
CREATE INDEX IF NOT EXISTS idx_user_gamification_monthly ON public.user_gamification(monthly_xp DESC);
CREATE INDEX IF NOT EXISTS idx_user_gamification_level ON public.user_gamification(level DESC);
CREATE INDEX IF NOT EXISTS idx_user_gamification_streak ON public.user_gamification(current_streak DESC);

CREATE INDEX IF NOT EXISTS idx_challenges_active ON public.challenges(active, start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_challenges_type ON public.challenges(challenge_type);

CREATE INDEX IF NOT EXISTS idx_user_challenge_progress_user ON public.user_challenge_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_user_challenge_progress_challenge ON public.user_challenge_progress(challenge_id);

-- ===========================================================================
-- Row Level Security
-- ===========================================================================

-- achievements: publicly readable catalog
ALTER TABLE public.achievements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Achievements are publicly readable"
    ON public.achievements FOR SELECT
    USING (true);

-- user_achievements: users read/write only their own
ALTER TABLE public.user_achievements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own achievements"
    ON public.user_achievements FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own achievements"
    ON public.user_achievements FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own achievements"
    ON public.user_achievements FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- user_gamification: users read their own; leaderboard via service role
ALTER TABLE public.user_gamification ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own gamification"
    ON public.user_gamification FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own gamification"
    ON public.user_gamification FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own gamification"
    ON public.user_gamification FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Leaderboard: allow all authenticated users to read (for rankings)
CREATE POLICY "Authenticated users can read leaderboard"
    ON public.user_gamification FOR SELECT
    USING (auth.role() = 'authenticated');

-- challenges: publicly readable
ALTER TABLE public.challenges ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Challenges are publicly readable"
    ON public.challenges FOR SELECT
    USING (true);

-- user_challenge_progress: users read/write only their own
ALTER TABLE public.user_challenge_progress ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own challenge progress"
    ON public.user_challenge_progress FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own challenge progress"
    ON public.user_challenge_progress FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own challenge progress"
    ON public.user_challenge_progress FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ===========================================================================
-- Seed achievements (~30 across 7 categories)
-- ===========================================================================
INSERT INTO public.achievements (id, title, description, icon, category, xp_reward, tier, threshold, sort_order) VALUES
-- Scanning
('first_scan',        'First Scan',           'Scan your first item with the camera',                'scan-outline',          'scanning',    10,  'bronze',   1,   100),
('scan_10',           'Scanner Pro',          'Scan 10 items',                                        'scan-outline',          'scanning',    25,  'silver',   10,  101),
('scan_50',           'Eagle Eye',            'Scan 50 items',                                        'eye-outline',           'scanning',    75,  'gold',     50,  102),
('scan_100',          'Master Scanner',       'Scan 100 items — you can identify anything!',          'hardware-chip-outline', 'scanning',    150, 'platinum', 100, 103),
('barcode_first',     'Barcode Hunter',       'Use the barcode scanner for the first time',           'barcode-outline',       'scanning',    10,  'bronze',   1,   104),

-- Collection
('first_item',        'Getting Started',      'Add your first item to your collection',               'add-circle-outline',    'collection',  10,  'bronze',   1,   200),
('collector_10',      'Budding Collector',    'Own 10 items in your collection',                      'albums-outline',        'collection',  25,  'silver',   10,  201),
('collector_50',      'Serious Collector',    'Own 50 items in your collection',                      'library-outline',       'collection',  75,  'gold',     50,  202),
('collector_100',     'Centurion',            'Own 100 items — now that is a collection!',            'trophy-outline',        'collection',  150, 'platinum', 100, 203),
('collector_500',     'Hoarder',              'Own 500 items — your shelves are overflowing!',        'diamond-outline',       'collection',  500, 'diamond',  500, 204),
('multi_category',    'Renaissance Collector','Add items in 5 different categories',                  'grid-outline',          'collection',  50,  'gold',     5,   205),

-- Trading
('first_sale',        'First Sale',           'Complete your first sale',                             'cash-outline',          'trading',     25,  'bronze',   1,   300),
('trader_10',         'Market Regular',       'Complete 10 trades',                                   'swap-horizontal-outline','trading',    75,  'gold',     10,  301),
('first_purchase',    'First Buy',            'Make your first purchase through the app',             'cart-outline',          'trading',     15,  'bronze',   1,   302),
('big_spender',       'Big Spender',          'Spend over $500 in total purchases',                   'wallet-outline',        'trading',     100, 'gold',     500, 303),

-- Social
('first_connection',  'Hello World',          'Make your first connection',                           'people-outline',        'social',      10,  'bronze',   1,   400),
('social_butterfly_10','Social Butterfly',    'Connect with 10 collectors',                           'people-circle-outline', 'social',      50,  'silver',   10,  401),
('first_message',     'Conversation Starter', 'Send your first direct message',                      'chatbubble-outline',    'social',      10,  'bronze',   1,   402),
('event_attendee',    'Event Goer',           'RSVP to your first event',                            'calendar-outline',      'social',      15,  'bronze',   1,   403),
('event_host',        'Event Host',           'Create and host your first event',                    'megaphone-outline',     'social',      50,  'gold',     1,   404),

-- Building
('first_project',     'First Build',          'Start your first build & paint project',              'construct-outline',     'building',    15,  'bronze',   1,   500),
('master_builder_5',  'Master Builder',       'Complete 5 build & paint projects',                   'hammer-outline',        'building',    100, 'gold',     5,   501),
('project_complete',  'Project Done',         'Complete your first build & paint project',           'checkmark-done-outline','building',    25,  'silver',   1,   502),
('paint_perfectionist','Paint Perfectionist', 'Complete 3 projects with all paint steps done',       'color-palette-outline', 'building',    75,  'gold',     3,   503),

-- Streaks
('streak_3',          'Getting Warmed Up',    'Maintain a 3-day activity streak',                    'flame-outline',         'streaks',     15,  'bronze',   3,   600),
('streak_7',          'On Fire',              'Maintain a 7-day activity streak',                    'flame-outline',         'streaks',     50,  'silver',   7,   601),
('streak_14',         'Unstoppable',          'Maintain a 14-day activity streak',                   'flame-outline',         'streaks',     100, 'gold',     14,  602),
('streak_30',         'Legendary Dedication', 'Maintain a 30-day activity streak',                   'flame-outline',         'streaks',     250, 'platinum', 30,  603),

-- Milestones (portfolio value in base currency)
('portfolio_100',     'Triple Digits',        'Portfolio value reaches $100',                         'trending-up-outline',   'milestones',  25,  'bronze',   100,    700),
('portfolio_1000',    'Four Figures',          'Portfolio value reaches $1,000',                       'stats-chart-outline',   'milestones',  75,  'silver',   1000,   701),
('portfolio_10000',   'Five Figures',          'Portfolio value reaches $10,000',                      'rocket-outline',        'milestones',  200, 'gold',     10000,  702),
('portfolio_100000',  'Six Figures',           'Portfolio value reaches $100,000',                     'star-outline',          'milestones',  500, 'platinum', 100000, 703)
ON CONFLICT (id) DO NOTHING;

-- ===========================================================================
-- Seed initial challenges
-- ===========================================================================
INSERT INTO public.challenges (title, description, challenge_type, category, target_count, xp_reward, start_date, end_date) VALUES
('Scan-a-thon',      'Scan 5 items this week',                    'weekly',  NULL,        5,  75,  '2026-02-23', '2026-03-01'),
('Social Week',      'Make 3 new connections this week',          'weekly',  NULL,        3,  50,  '2026-02-23', '2026-03-01'),
('Builder''s Sprint','Complete 2 build steps this week',          'weekly',  'building',  2,  50,  '2026-02-23', '2026-03-01'),
('Monthly Hoarder',  'Add 20 items to your collection this month','monthly', NULL,       20, 200,  '2026-02-01', '2026-02-28'),
('Value Hunter',     'Find 3 deals via the deal hub this month',  'monthly', NULL,        3, 150,  '2026-02-01', '2026-02-28'),
('Category Explorer','Add items in 3 different categories',       'monthly', NULL,        3, 100,  '2026-02-01', '2026-02-28')
ON CONFLICT DO NOTHING;
