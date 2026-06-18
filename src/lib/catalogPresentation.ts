/**
 * catalogPresentation — render-time cleanup of raw catalog fields.
 *
 * category_items rows are scraped, so titles carry collector jargon ("CIB"),
 * redundant platform suffixes ("(PS2)"), and the platform often gets stuffed
 * into BOTH `brand` and `set_code` — surfacing as duplicate "ps2 / PS2" tags
 * and a wrong "Brand: PS2". This module cleans the PRESENTATION only; the
 * stored data is never mutated. Used by the museum detail screen + catalog
 * cards/carousels.
 *
 * Design rule: be conservative. Only strip tokens that are unambiguous
 * collector jargon (CIB/NIB/Sealed/Loose…) — NEVER common words like "New"
 * or "Mint" that appear in real titles ("New Super Mario Bros"). Anything not
 * provably redundant is left untouched. Behaviour is locked by unit tests.
 */

// Known game platforms → display label, keyed by a normalized form.
const PLATFORMS: Record<string, string> = {
  PS1: 'PS1', PSX: 'PS1', PSONE: 'PS1',
  PS2: 'PS2', PS3: 'PS3', PS4: 'PS4', PS5: 'PS5',
  PSP: 'PSP', PSVITA: 'PS Vita', VITA: 'PS Vita',
  NES: 'NES', SNES: 'SNES', SUPERNINTENDO: 'SNES', N64: 'N64',
  GAMECUBE: 'GameCube', GC: 'GameCube', NGC: 'GameCube',
  WII: 'Wii', WIIU: 'Wii U', SWITCH: 'Switch', NINTENDOSWITCH: 'Switch',
  GB: 'Game Boy', GAMEBOY: 'Game Boy', GBC: 'Game Boy Color',
  GBA: 'Game Boy Advance', NDS: 'Nintendo DS', DS: 'Nintendo DS', '3DS': 'Nintendo 3DS',
  XBOX: 'Xbox', X360: 'Xbox 360', XBOX360: 'Xbox 360',
  XBONE: 'Xbox One', XBOXONE: 'Xbox One', XSX: 'Xbox Series X',
  GENESIS: 'Genesis', MEGADRIVE: 'Mega Drive', DREAMCAST: 'Dreamcast',
  SEGASATURN: 'Saturn', SATURN: 'Saturn', GAMEGEAR: 'Game Gear',
  ATARI2600: 'Atari 2600', '2600': 'Atari 2600',
};

// Unambiguous completeness/condition jargon → human label. Intentionally tight:
// excludes ambiguous words (New, Mint, Used) that occur in real game titles.
const CONDITIONS: Record<string, string> = {
  CIB: 'Complete in Box', NIB: 'New in Box', BNIB: 'New in Box',
  SEALED: 'Sealed', LOOSE: 'Loose', BOXED: 'Boxed',
};

// Always-noise values (any category) — pure filler, never information.
const NOISE = new Set(['UNKNOWN', 'N/A', 'NA', 'NONE', 'DEFAULT', 'MISC', 'OTHER', '-']);
// "Common" is a REAL rarity tier for TCG (Pokémon/MTG) but meaningless filler
// for video games, so it's only dropped when the item resolves to a platform.
const GAME_NOISE_RARITY = new Set(['COMMON']);

const norm = (s: string): string => s.toUpperCase().replace(/[\s._/-]/g, '');

function platformLabel(raw?: string | null): string | null {
  if (!raw) return null;
  return PLATFORMS[norm(raw)] ?? null;
}

function conditionLabel(raw?: string | null): string | null {
  if (!raw) return null;
  return CONDITIONS[norm(raw)] ?? null;
}

function isNoise(raw?: string | null): boolean {
  return !raw || NOISE.has(raw.trim().toUpperCase());
}

function dedupe(arr: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const x of arr) {
    const k = x.toUpperCase();
    if (!seen.has(k)) { seen.add(k); out.push(x); }
  }
  return out;
}

function cleanTitle(
  rawTitle: string,
  fields: { brand?: string | null; setCode?: string | null },
): { title: string; condition: string | null } {
  let t = (rawTitle || '').trim();
  let condition: string | null = null;

  // 1. Strip redundant trailing (parenthetical) / [bracket] suffixes — but only
  //    when the contents are a known platform, a condition token, or literally
  //    the item's brand/set_code (i.e. provably redundant with a shown field).
  const trailing = /\s*[([]([^()[\]]+)[)\]]\s*$/;
  let m: RegExpMatchArray | null;
  while ((m = t.match(trailing)) && m.index !== undefined) {
    const inner = m[1].trim();
    const cl = conditionLabel(inner);
    const redundant =
      platformLabel(inner) != null ||
      (fields.brand && norm(inner) === norm(fields.brand)) ||
      (fields.setCode && norm(inner) === norm(fields.setCode));
    if (cl) {
      condition = condition ?? cl;
      t = t.slice(0, m.index).trim();
    } else if (redundant) {
      t = t.slice(0, m.index).trim();
    } else {
      break;
    }
  }

  // 2. Strip standalone condition tokens anywhere in the remaining title.
  for (const tok of Object.keys(CONDITIONS)) {
    const re = new RegExp(`\\b${tok}\\b`, 'i');
    if (re.test(t)) {
      condition = condition ?? CONDITIONS[tok];
      t = t.replace(new RegExp(`\\s*\\b${tok}\\b\\s*`, 'ig'), ' ');
    }
  }

  // 3. Tidy: collapse whitespace and trim dangling separators.
  t = t.replace(/\s{2,}/g, ' ').replace(/^[\s\-–:,]+|[\s\-–:,]+$/g, '').trim();
  return { title: t || (rawTitle || '').trim(), condition };
}

export type CleanCatalog = {
  /** Cleaned headline (jargon + redundant platform suffix removed). */
  title: string;
  /** Ordered, deduped chips for the badge row. */
  tags: string[];
  /** Resolved console label when the brand/set is actually a platform. */
  platform: string | null;
  /** Human condition label lifted out of the title, if any. */
  condition: string | null;
  /** Rarity, or null when low-signal ("Common"). */
  rarity: string | null;
  /** Set code, or null when it's actually the platform / low-signal. */
  setCode: string | null;
  /** Brand, or null when it's actually a platform (shown as Platform instead). */
  brand: string | null;
};

export function cleanCatalogItem(input: {
  title?: string | null;
  brand?: string | null;
  rarity?: string | null;
  setCode?: string | null;
}): CleanCatalog {
  const brandRaw = input.brand?.trim() || null;
  const setRaw = input.setCode?.trim() || null;
  const rarityRaw = input.rarity?.trim() || null;

  const platform = platformLabel(brandRaw) ?? platformLabel(setRaw);
  const brand = platformLabel(brandRaw) ? null : brandRaw;
  const setCode = platformLabel(setRaw) || isNoise(setRaw) ? null : setRaw;
  // Drop pure noise everywhere; drop "Common" only for video games (it's a real
  // TCG rarity), so Pokémon/MTG commons keep their tier.
  const rarityUp = rarityRaw?.toUpperCase();
  const rarity =
    isNoise(rarityRaw) || (platform != null && !!rarityUp && GAME_NOISE_RARITY.has(rarityUp))
      ? null
      : rarityRaw;

  const { title, condition } = cleanTitle(input.title ?? '', { brand: brandRaw, setCode: setRaw });

  const tags = dedupe(
    [platform, condition, rarity, setCode, brand].filter(Boolean) as string[],
  );

  return { title, tags, platform, condition, rarity, setCode, brand };
}

/** Title-only convenience for cards/carousels. */
export function cleanCatalogTitle(
  title?: string | null,
  opts?: { brand?: string | null; setCode?: string | null },
): string {
  return cleanCatalogItem({ title, brand: opts?.brand, setCode: opts?.setCode }).title;
}
