/**
 * Taxonomy Mapper
 *
 * Deterministic mapper that outputs category_id/subtype_id + confidence + rationale.
 * Never silently ambiguous — always provides reasoning.
 *
 * Rules:
 * - ISBN present → likely books subtype
 * - Keywords drive subtype selection
 * - Collection tags are orthogonal and detected separately
 */

import {
  ALL_CATEGORIES,
  COLLECTION_TAGS,
  TAXONOMY_VERSION,
  type CategoryDefinition,
  type CollectionTag,
  type SubtypeDefinition,
} from './registry';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type MappingResult = {
  categoryId: string;
  subtypeId: string;
  confidence: number;  // 0.0 - 1.0
  rationale: string;
  taxonomyVersion: string;
  collections: string[];  // Detected collection tags
  warnings?: string[];
};

export type MappingInput = {
  title: string;
  description?: string;
  isbn?: string;
  keywords?: string[];
  categoryHint?: string;  // User-provided hint
  attributes?: Record<string, unknown>;
};

// ─────────────────────────────────────────────────────────────────────────────
// Keyword Patterns
// ─────────────────────────────────────────────────────────────────────────────

const ISBN_PATTERN = /^(?:97[89])?\d{9}[\dXx]$/;

const WARHAMMER_BOOK_KEYWORDS = [
  'codex', 'rulebook', 'battletome', 'black library', 'isbn', 'novel',
  'lore', 'campaign', 'supplement', 'core rules', 'index',
];

const WARHAMMER_MINI_KEYWORDS = [
  'sprue', 'citadel', 'mini', 'miniature', '28mm', 'resin', 'assembled',
  'painted', 'primed', 'nos', 'nib', 'finecast', 'forge world', 'army',
  'kill team', 'combat patrol', 'start collecting',
];

// ─────────────────────────────────────────────────────────────────────────────
// Core Mapping Logic
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Map input to taxonomy with confidence and rationale.
 */
export function mapToTaxonomy(input: MappingInput): MappingResult {
  const text = normalizeText(input.title + ' ' + (input.description ?? ''));
  const warnings: string[] = [];

  // Step 1: Detect collection tags
  const collections = detectCollectionTags(text);

  // Step 2: Try ISBN-based mapping first (high confidence)
  if (input.isbn && isValidIsbn(input.isbn)) {
    const isbnResult = mapByIsbn(input.isbn, text, input.categoryHint);
    if (isbnResult) {
      return { ...isbnResult, collections, taxonomyVersion: TAXONOMY_VERSION };
    }
  }

  // Step 3: Try category hint if provided
  if (input.categoryHint) {
    const hintResult = mapByCategoryHint(input.categoryHint, text);
    if (hintResult) {
      return { ...hintResult, collections, taxonomyVersion: TAXONOMY_VERSION };
    }
    warnings.push(`Category hint '${input.categoryHint}' not found in registry`);
  }

  // Step 4: Special handling for artist collections (before generic keywords)
  // Artist collection tags should take precedence over generic categories like vinyl_records
  if (collections.length > 0) {
    const collectionResult = mapByCollectionTags(collections, text);
    if (collectionResult) {
      return { ...collectionResult, collections, warnings, taxonomyVersion: TAXONOMY_VERSION };
    }
  }

  // Step 5: Keyword-based mapping
  const keywordResult = mapByKeywords(text, input.keywords ?? []);
  if (keywordResult) {
    return { ...keywordResult, collections, warnings, taxonomyVersion: TAXONOMY_VERSION };
  }

  // Step 6: Fallback - unknown
  return {
    categoryId: 'unknown',
    subtypeId: 'unknown',
    confidence: 0.1,
    rationale: 'No matching category found. Manual classification recommended.',
    taxonomyVersion: TAXONOMY_VERSION,
    collections,
    warnings: [...warnings, 'Could not determine category from available information'],
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Mapping Strategies
// ─────────────────────────────────────────────────────────────────────────────

function mapByIsbn(isbn: string, text: string, categoryHint?: string): Omit<MappingResult, 'collections' | 'taxonomyVersion'> | null {
  // ISBN present strongly suggests books
  // Check for Warhammer books specifically
  if (hasAnyKeyword(text, ['warhammer', '40k', '40,000', 'age of sigmar', 'aos', 'games workshop'])) {
    return {
      categoryId: 'warhammer',
      subtypeId: 'warhammer_books',
      confidence: 0.95,
      rationale: `ISBN detected (${isbn}) combined with Warhammer keywords → warhammer_books with high confidence`,
    };
  }

  // Generic book - could be many categories
  // Lower confidence since we don't know the specific category
  return {
    categoryId: 'unknown',
    subtypeId: 'unknown',
    confidence: 0.3,
    rationale: `ISBN detected (${isbn}) but category unclear. Could be rulebook, novel, or guide. Needs manual classification.`,
    warnings: ['ISBN present but category undetermined'],
  };
}

function mapByCategoryHint(hint: string, text: string): Omit<MappingResult, 'collections' | 'taxonomyVersion'> | null {
  const normalizedHint = hint.toLowerCase().trim();

  // Find matching category
  const category = ALL_CATEGORIES.find(
    (c) => c.id === normalizedHint || c.name.toLowerCase() === normalizedHint
  );

  if (!category) return null;

  // Find best matching subtype within category
  const subtypeMatch = findBestSubtype(category, text);

  return {
    categoryId: category.id,
    subtypeId: subtypeMatch.subtype.id,
    confidence: Math.min(0.85, subtypeMatch.score + 0.3), // Hint adds confidence
    rationale: `User hint '${hint}' matched category. Subtype determined by keywords: ${subtypeMatch.matchedKeywords.join(', ') || 'default'}.`,
  };
}

function mapByKeywords(text: string, additionalKeywords: string[]): Omit<MappingResult, 'collections' | 'taxonomyVersion'> | null {
  const searchText = text + ' ' + additionalKeywords.join(' ');

  // Special case: Warhammer disambiguation (books vs minis)
  if (hasAnyKeyword(searchText, ['warhammer', '40k', '40,000', 'age of sigmar', 'aos', 'games workshop'])) {
    return mapWarhammerItem(searchText);
  }

  // First, try to match category-level keywords (high priority)
  const categoryMatches: { category: CategoryDefinition; matchCount: number }[] = [];
  for (const category of ALL_CATEGORIES) {
    if (category.keywords && category.keywords.length > 0) {
      const matchCount = countKeywordMatches(searchText, category.keywords);
      if (matchCount > 0) {
        categoryMatches.push({ category, matchCount });
      }
    }
  }

  // Sort by match count descending
  categoryMatches.sort((a, b) => b.matchCount - a.matchCount);

  // If we have a strong category match, prioritize it
  if (categoryMatches.length > 0) {
    const topCategory = categoryMatches[0].category;
    const subtypeMatch = findBestSubtype(topCategory, searchText);
    const categoryKeywordsMatched = getMatchedKeywords(searchText, topCategory.keywords || []);

    return {
      categoryId: topCategory.id,
      subtypeId: subtypeMatch.subtype.id,
      confidence: Math.min(0.85, 0.5 + categoryMatches[0].matchCount * 0.15 + subtypeMatch.score * 0.2),
      rationale: `Category match: ${categoryKeywordsMatched.join(', ')} → ${topCategory.name}. Subtype: ${subtypeMatch.matchedKeywords.join(', ') || 'default'}`,
    };
  }

  // Fallback: Score all categories by subtype keywords only
  let bestMatch: {
    category: CategoryDefinition;
    subtype: SubtypeDefinition;
    score: number;
    matchedKeywords: string[];
  } | null = null;

  for (const category of ALL_CATEGORIES) {
    const subtypeMatch = findBestSubtype(category, searchText);
    if (subtypeMatch.score > (bestMatch?.score ?? 0)) {
      bestMatch = {
        category,
        subtype: subtypeMatch.subtype,
        score: subtypeMatch.score,
        matchedKeywords: subtypeMatch.matchedKeywords,
      };
    }
  }

  if (bestMatch && bestMatch.score > 0.2) {
    return {
      categoryId: bestMatch.category.id,
      subtypeId: bestMatch.subtype.id,
      confidence: Math.min(0.9, bestMatch.score),
      rationale: `Keyword match: ${bestMatch.matchedKeywords.slice(0, 5).join(', ')} → ${bestMatch.category.name} / ${bestMatch.subtype.name}`,
    };
  }

  return null;
}

function mapWarhammerItem(text: string): Omit<MappingResult, 'collections' | 'taxonomyVersion'> {
  const bookScore = countKeywordMatches(text, WARHAMMER_BOOK_KEYWORDS);
  const miniScore = countKeywordMatches(text, WARHAMMER_MINI_KEYWORDS);

  if (bookScore > miniScore && bookScore > 0) {
    return {
      categoryId: 'warhammer',
      subtypeId: 'warhammer_books',
      confidence: Math.min(0.9, 0.5 + bookScore * 0.1),
      rationale: `Warhammer item classified as BOOKS based on keywords: ${getMatchedKeywords(text, WARHAMMER_BOOK_KEYWORDS).join(', ')}`,
    };
  }

  if (miniScore > 0) {
    return {
      categoryId: 'warhammer',
      subtypeId: 'warhammer_minis',
      confidence: Math.min(0.9, 0.5 + miniScore * 0.1),
      rationale: `Warhammer item classified as MINIATURES based on keywords: ${getMatchedKeywords(text, WARHAMMER_MINI_KEYWORDS).join(', ')}`,
    };
  }

  // Default to minis if no clear signal
  return {
    categoryId: 'warhammer',
    subtypeId: 'warhammer_minis',
    confidence: 0.5,
    rationale: 'Warhammer detected but no clear book/mini keywords. Defaulting to miniatures. Manual review recommended.',
    warnings: ['Ambiguous Warhammer classification'],
  };
}

function mapByCollectionTags(collections: string[], text: string): Omit<MappingResult, 'collections' | 'taxonomyVersion'> | null {
  // K-pop collections -> music_memorabilia by default
  const kpopTags = ['bts', 'blackpink', 'stray_kids', 'seventeen'];
  if (collections.some((c) => kpopTags.includes(c))) {
    // Try to determine subtype
    if (hasAnyKeyword(text, ['photocard', 'pc', 'photo card'])) {
      return {
        categoryId: 'music_memorabilia',
        subtypeId: 'music_photocards',
        confidence: 0.8,
        rationale: `K-pop collection detected with photocard keywords → music_photocards`,
      };
    }
    if (hasAnyKeyword(text, ['album', 'cd', 'vinyl'])) {
      return {
        categoryId: 'music_memorabilia',
        subtypeId: 'music_albums',
        confidence: 0.8,
        rationale: `K-pop collection detected with album keywords → music_albums`,
      };
    }
    if (hasAnyKeyword(text, ['lightstick', 'light stick', 'army bomb'])) {
      return {
        categoryId: 'music_memorabilia',
        subtypeId: 'music_lightsticks',
        confidence: 0.85,
        rationale: `K-pop collection detected with lightstick keywords → music_lightsticks`,
      };
    }
    return {
      categoryId: 'music_memorabilia',
      subtypeId: 'music_merch',
      confidence: 0.6,
      rationale: `K-pop collection detected, defaulting to general merchandise`,
    };
  }

  // Taylor Swift special handling - crosses categories
  if (collections.includes('taylor_swift')) {
    if (hasAnyKeyword(text, ['hoodie', 'shirt', 'tee', 'sweater', 'jacket'])) {
      return {
        categoryId: 'apparel',
        subtypeId: 'apparel_tops',
        confidence: 0.8,
        rationale: `Taylor Swift collection with apparel keywords → apparel_tops`,
      };
    }
    if (hasAnyKeyword(text, ['guitar', 'signed guitar'])) {
      return {
        categoryId: 'instruments',
        subtypeId: hasAnyKeyword(text, ['signed', 'autograph']) ? 'instruments_signed' : 'instruments_guitars',
        confidence: 0.85,
        rationale: `Taylor Swift collection with guitar keywords → instruments`,
      };
    }
    if (hasAnyKeyword(text, ['cd', 'vinyl', 'album', 'record'])) {
      return {
        categoryId: 'music_memorabilia',
        subtypeId: 'music_albums',
        confidence: 0.85,
        rationale: `Taylor Swift collection with album keywords → music_albums`,
      };
    }
    return {
      categoryId: 'music_memorabilia',
      subtypeId: 'music_merch',
      confidence: 0.6,
      rationale: `Taylor Swift collection detected, defaulting to music merchandise`,
    };
  }

  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

function normalizeText(text: string): string {
  return text.toLowerCase().replace(/[^\w\s]/g, ' ').replace(/\s+/g, ' ').trim();
}

function isValidIsbn(isbn: string): boolean {
  const cleaned = isbn.replace(/[-\s]/g, '');
  return ISBN_PATTERN.test(cleaned);
}

function hasAnyKeyword(text: string, keywords: string[]): boolean {
  const normalized = normalizeText(text);
  return keywords.some((kw) => normalized.includes(kw.toLowerCase()));
}

function countKeywordMatches(text: string, keywords: string[]): number {
  const normalized = normalizeText(text);
  return keywords.filter((kw) => normalized.includes(kw.toLowerCase())).length;
}

function getMatchedKeywords(text: string, keywords: string[]): string[] {
  const normalized = normalizeText(text);
  return keywords.filter((kw) => normalized.includes(kw.toLowerCase()));
}

function findBestSubtype(
  category: CategoryDefinition,
  text: string
): { subtype: SubtypeDefinition; score: number; matchedKeywords: string[] } {
  let bestSubtype = category.subtypes[0];
  let bestScore = 0;
  let bestKeywords: string[] = [];

  for (const subtype of category.subtypes) {
    const matched = getMatchedKeywords(text, subtype.keywords);
    const score = matched.length / Math.max(subtype.keywords.length, 1);
    if (score > bestScore) {
      bestScore = score;
      bestSubtype = subtype;
      bestKeywords = matched;
    }
  }

  return { subtype: bestSubtype, score: bestScore, matchedKeywords: bestKeywords };
}

function detectCollectionTags(text: string): string[] {
  const detected: string[] = [];
  const normalized = normalizeText(text);

  for (const tag of COLLECTION_TAGS) {
    const allTerms = [tag.id, tag.name.toLowerCase(), ...tag.aliases.map((a) => a.toLowerCase())];
    if (allTerms.some((term) => normalized.includes(term))) {
      detected.push(tag.id);
    }
  }

  return detected;
}

// ─────────────────────────────────────────────────────────────────────────────
// Convenience Exports
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Quick check if text likely refers to Warhammer books vs minis.
 */
export function isLikelyWarhammerBook(text: string): boolean {
  const result = mapToTaxonomy({ title: text });
  return result.subtypeId === 'warhammer_books';
}

/**
 * Detect all collection tags in text.
 */
export function detectCollections(text: string): CollectionTag[] {
  const ids = detectCollectionTags(normalizeText(text));
  return ids.map((id) => COLLECTION_TAGS.find((t) => t.id === id)!).filter(Boolean);
}
