/**
 * Centralised brand color constants.
 * Import from here instead of defining TIFFANY / TIFFANY_DARK locally.
 */
export const BRAND_COLORS = {
  tiffany: '#81D8D0',
  tiffanyDark: '#5FBFB6',
} as const;

/** Twitch brand color — fixed external brand, not a theme token. */
export const TWITCH_PURPLE = '#9146FF';

/** Medal/rank colors for leaderboards. */
export const MEDAL_COLORS = {
  gold: '#eab308',
  silver: '#9ca3af',
  bronze: '#b45309',
} as const;

/** Marketplace brand colors for multi-marketplace UI (sell dashboard, etc.). */
export const MARKETPLACE_BRAND_COLORS: Record<string, { label: string; color: string }> = {
  collectai: { label: 'CollectAI P2P', color: '#81D8D0' },
  ebay: { label: 'eBay', color: '#E53238' },
  mercari: { label: 'Mercari', color: '#4DC8F0' },
  cardmarket: { label: 'Cardmarket', color: '#1A3C7D' },
  stockx: { label: 'StockX', color: '#006340' },
  bricklink: { label: 'BrickLink', color: '#D01012' },
  tcgplayer: { label: 'TCGPlayer', color: '#363A5D' },
  discogs: { label: 'Discogs', color: '#333333' },
} as const;
