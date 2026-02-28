-- =============================================================================
-- Multi-Marketplace Selling System
-- Allows users to list items for sale on multiple external marketplaces
-- (eBay, Mercari, Cardmarket, StockX, BrickLink) from within CollectAI.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Marketplace Accounts — OAuth connections per user per marketplace
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marketplace_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  marketplace_id text NOT NULL, -- 'ebay', 'mercari', 'cardmarket', 'stockx', 'bricklink'
  seller_name text,
  seller_id text, -- external ID on the marketplace
  oauth_token_enc text, -- encrypted OAuth access token
  refresh_token_enc text, -- encrypted OAuth refresh token
  token_expires_at timestamptz,
  scopes text[], -- granted OAuth scopes
  connected_at timestamptz NOT NULL DEFAULT now(),
  last_sync_at timestamptz,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE(user_id, marketplace_id)
);

-- ---------------------------------------------------------------------------
-- 2. Marketplace Listings — items listed on external marketplaces
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marketplace_listings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  item_id uuid NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  account_id uuid REFERENCES marketplace_accounts(id) ON DELETE SET NULL,
  marketplace_id text NOT NULL, -- 'collectai', 'ebay', 'mercari', etc.

  -- External listing data
  external_listing_id text, -- marketplace's internal listing ID
  listing_url text, -- direct URL to the listing
  listing_title text NOT NULL,
  listing_description text,

  -- Pricing
  price numeric NOT NULL CHECK (price > 0),
  currency text NOT NULL DEFAULT 'EUR',
  original_price numeric, -- if price was changed

  -- Listing config
  format text NOT NULL DEFAULT 'fixed_price' CHECK (format IN ('fixed_price', 'auction', 'best_offer')),
  auction_duration_days integer CHECK (auction_duration_days IN (1, 3, 5, 7, 10, 30)),
  auction_start_price numeric,
  buy_it_now_price numeric,
  quantity integer NOT NULL DEFAULT 1 CHECK (quantity >= 0),

  -- Condition
  condition_label text, -- 'New', 'Like New', 'Very Good', 'Good', 'Acceptable'
  condition_notes text,

  -- Shipping
  shipping_method text DEFAULT 'standard', -- 'standard', 'express', 'local_pickup', 'free'
  shipping_cost numeric DEFAULT 0,
  ships_international boolean DEFAULT false,

  -- Returns
  returns_accepted boolean DEFAULT false,
  returns_days integer DEFAULT 14,

  -- Status tracking
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'sold', 'expired', 'delisted', 'error')),
  status_message text, -- error details if status = 'error'

  -- Metrics
  views_count integer NOT NULL DEFAULT 0,
  watchers_count integer NOT NULL DEFAULT 0,
  offers_count integer NOT NULL DEFAULT 0,

  -- Fees
  estimated_fees numeric, -- platform fee estimate
  estimated_net numeric, -- price - fees - shipping
  fee_percentage numeric, -- e.g. 12.9 for eBay

  -- Timestamps
  listed_at timestamptz, -- when published on marketplace
  expires_at timestamptz,
  sold_at timestamptz,
  synced_at timestamptz, -- last sync with marketplace API
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 3. Marketplace Sales — completed sales with financials
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marketplace_sales (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id uuid NOT NULL REFERENCES marketplace_listings(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Buyer info
  buyer_name text,
  buyer_marketplace_id text,
  buyer_rating numeric,

  -- Financials
  sale_price numeric NOT NULL,
  currency text NOT NULL DEFAULT 'EUR',
  shipping_cost_actual numeric DEFAULT 0,
  platform_fee numeric DEFAULT 0,
  payment_processing_fee numeric DEFAULT 0,
  net_proceeds numeric NOT NULL, -- sale_price - all fees

  -- Tracking
  tracking_number text,
  carrier text,
  shipped_at timestamptz,
  delivered_at timestamptz,

  -- Status
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'completed', 'disputed', 'refunded')),

  sold_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 4. Fee Schedules — marketplace fee configuration
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marketplace_fee_schedules (
  marketplace_id text PRIMARY KEY,
  display_name text NOT NULL,
  base_fee_pct numeric NOT NULL DEFAULT 0, -- e.g. 12.9 for eBay
  payment_processing_pct numeric NOT NULL DEFAULT 0, -- e.g. 2.9 for PayPal/Stripe
  fixed_fee numeric NOT NULL DEFAULT 0, -- e.g. 0.30 per transaction
  currency text NOT NULL DEFAULT 'EUR',
  min_fee numeric DEFAULT 0,
  max_fee numeric, -- cap if any
  notes text,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Seed fee schedules
INSERT INTO marketplace_fee_schedules (marketplace_id, display_name, base_fee_pct, payment_processing_pct, fixed_fee, notes) VALUES
  ('collectai', 'CollectAI P2P', 0, 0, 0, 'Free P2P trading within CollectAI'),
  ('ebay', 'eBay', 12.9, 2.9, 0.30, 'Final value fee + payment processing. Varies by category.'),
  ('mercari', 'Mercari', 10.0, 0, 0, 'Flat 10% seller fee. Shipping paid by buyer or seller.'),
  ('cardmarket', 'Cardmarket', 5.0, 0, 0, '5% commission. Lower for Power Sellers.'),
  ('stockx', 'StockX', 9.5, 3.0, 0, 'Transaction fee + payment processing. Varies by seller level.'),
  ('bricklink', 'BrickLink', 3.0, 0, 0, '3% final value fee on orders over $0.50.'),
  ('tcgplayer', 'TCGPlayer', 10.25, 2.5, 0.30, 'Marketplace fee + payment processing.'),
  ('discogs', 'Discogs', 8.0, 0, 0, '8% seller fee on item price.')
ON CONFLICT (marketplace_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 5. Indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_marketplace_accounts_user ON marketplace_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_marketplace_listings_user ON marketplace_listings(user_id);
CREATE INDEX IF NOT EXISTS idx_marketplace_listings_item ON marketplace_listings(item_id);
CREATE INDEX IF NOT EXISTS idx_marketplace_listings_status ON marketplace_listings(status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_marketplace_listings_marketplace ON marketplace_listings(marketplace_id);
CREATE INDEX IF NOT EXISTS idx_marketplace_sales_user ON marketplace_sales(user_id);
CREATE INDEX IF NOT EXISTS idx_marketplace_sales_listing ON marketplace_sales(listing_id);

-- ---------------------------------------------------------------------------
-- 6. RLS Policies
-- ---------------------------------------------------------------------------
ALTER TABLE marketplace_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE marketplace_listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE marketplace_sales ENABLE ROW LEVEL SECURITY;

-- Accounts: users can only see/manage their own
CREATE POLICY marketplace_accounts_select ON marketplace_accounts FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY marketplace_accounts_insert ON marketplace_accounts FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY marketplace_accounts_update ON marketplace_accounts FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY marketplace_accounts_delete ON marketplace_accounts FOR DELETE USING (auth.uid() = user_id);

-- Listings: owners can CRUD, others can view active listings
CREATE POLICY marketplace_listings_select_own ON marketplace_listings FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY marketplace_listings_select_active ON marketplace_listings FOR SELECT USING (status = 'active');
CREATE POLICY marketplace_listings_insert ON marketplace_listings FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY marketplace_listings_update ON marketplace_listings FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY marketplace_listings_delete ON marketplace_listings FOR DELETE USING (auth.uid() = user_id);

-- Sales: users can only see their own
CREATE POLICY marketplace_sales_select ON marketplace_sales FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY marketplace_sales_insert ON marketplace_sales FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY marketplace_sales_update ON marketplace_sales FOR UPDATE USING (auth.uid() = user_id);
