// ═══════════════════════════════════════════════════════════════════════════
// CollectAI Video Image Library — catalog image overlays per niche
// Images sourced from catalog_items table via S3 or CDN.
//
// Used by: PullReveal, WhatsItWorth, HiddenGem templates
// Falls back to emoji placeholder if no image available.
// ═══════════════════════════════════════════════════════════════════════════

export interface CatalogImage {
  id: string;
  nicheId: string;
  itemName: string;
  imageUrl: string;           // S3/CDN URL
  thumbnailUrl: string;
  estimatedValue: number;
  tags: string[];             // e.g. ["rare", "graded", "sealed"]
}

// ─── Demo images (replace with API fetch from catalog_items) ─────────────

export const DEMO_IMAGES: CatalogImage[] = [
  // Pokemon
  { id: "img-pkmn-01", nicheId: "pokemon", itemName: "Illustrator Pikachu", imageUrl: "", thumbnailUrl: "", estimatedValue: 5275000, tags: ["rare", "graded"] },
  { id: "img-pkmn-02", nicheId: "pokemon", itemName: "Base Set Charizard PSA 10", imageUrl: "", thumbnailUrl: "", estimatedValue: 420000, tags: ["graded", "iconic"] },
  { id: "img-pkmn-03", nicheId: "pokemon", itemName: "Gold Star Rayquaza", imageUrl: "", thumbnailUrl: "", estimatedValue: 45000, tags: ["rare"] },

  // MTG
  { id: "img-mtg-01", nicheId: "mtg", itemName: "Alpha Black Lotus BGS 9.5", imageUrl: "", thumbnailUrl: "", estimatedValue: 540000, tags: ["rare", "graded", "iconic"] },
  { id: "img-mtg-02", nicheId: "mtg", itemName: "Alpha Mox Sapphire", imageUrl: "", thumbnailUrl: "", estimatedValue: 80000, tags: ["rare"] },

  // Funko
  { id: "img-funko-01", nicheId: "funko", itemName: "Alex DeLarge (Glow)", imageUrl: "", thumbnailUrl: "", estimatedValue: 13300, tags: ["rare", "vaulted"] },
  { id: "img-funko-02", nicheId: "funko", itemName: "Holographic Darth Maul", imageUrl: "", thumbnailUrl: "", estimatedValue: 8500, tags: ["rare", "iconic"] },

  // LEGO
  { id: "img-lego-01", nicheId: "lego", itemName: "Cafe Corner 10182 (sealed)", imageUrl: "", thumbnailUrl: "", estimatedValue: 6000, tags: ["sealed", "retired"] },
  { id: "img-lego-02", nicheId: "lego", itemName: "Mr. Gold Minifigure", imageUrl: "", thumbnailUrl: "", estimatedValue: 5000, tags: ["rare"] },

  // Watches
  { id: "img-watch-01", nicheId: "watches", itemName: "Rolex Daytona 116500LN", imageUrl: "", thumbnailUrl: "", estimatedValue: 45000, tags: ["luxury"] },
  { id: "img-watch-02", nicheId: "watches", itemName: "Patek Philippe Nautilus 5711/1A", imageUrl: "", thumbnailUrl: "", estimatedValue: 180000, tags: ["luxury", "rare"] },

  // Sneakers
  { id: "img-snkr-01", nicheId: "sneakers", itemName: "Jordan 1 Chicago (DS)", imageUrl: "", thumbnailUrl: "", estimatedValue: 4500, tags: ["deadstock", "iconic"] },
  { id: "img-snkr-02", nicheId: "sneakers", itemName: "Nike MAG (Back to the Future)", imageUrl: "", thumbnailUrl: "", estimatedValue: 55000, tags: ["rare", "iconic"] },

  // Vinyl
  { id: "img-vinyl-01", nicheId: "vinyl", itemName: "Beatles Butcher Cover (sealed)", imageUrl: "", thumbnailUrl: "", estimatedValue: 125000, tags: ["sealed", "iconic"] },
  { id: "img-vinyl-02", nicheId: "vinyl", itemName: "Mariya Takeuchi 'Variety' OG", imageUrl: "", thumbnailUrl: "", estimatedValue: 800, tags: ["city-pop"] },

  // Yu-Gi-Oh
  { id: "img-ygo-01", nicheId: "yugioh", itemName: "Tournament Black Luster Soldier", imageUrl: "", thumbnailUrl: "", estimatedValue: 2000000, tags: ["rare", "iconic"] },
  { id: "img-ygo-02", nicheId: "yugioh", itemName: "Ghost Rare 1st Ed Stardust Dragon", imageUrl: "", thumbnailUrl: "", estimatedValue: 3000, tags: ["rare", "graded"] },
];

// ─── Selection ───────────────────────────────────────────────────────────

/**
 * Get images for a specific niche, optionally filtered by tags.
 */
export function getImagesForNiche(nicheId: string, tags?: string[]): CatalogImage[] {
  let images = DEMO_IMAGES.filter((img) => img.nicheId === nicheId);
  if (tags && tags.length > 0) {
    images = images.filter((img) => tags.some((t) => img.tags.includes(t)));
  }
  return images;
}

/**
 * Get a random image for a niche.
 */
export function getRandomImage(nicheId: string): CatalogImage | undefined {
  const images = getImagesForNiche(nicheId);
  return images.length > 0 ? images[Math.floor(Math.random() * images.length)] : undefined;
}

/**
 * Build the full image URL from catalog_items table.
 * This would be wired to the backend API in production.
 */
export function getCatalogImageUrl(itemId: string): string {
  const bucket = process.env.REMOTION_S3_BUCKET ?? "collectai-video-assets";
  return `https://${bucket}.s3.eu-central-1.amazonaws.com/catalog/${itemId}.webp`;
}
