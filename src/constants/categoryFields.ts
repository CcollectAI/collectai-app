/**
 * Per-category form field definitions.
 * Maps each category slug to the specific attribute fields shown
 * when adding/editing items of that category.
 *
 * Keys match AttrSchemas in types/category.ts.
 */

import type { Category } from '../../types/category';

export type FieldType = 'text' | 'boolean' | 'select';

export type CategoryField = {
  key: string;
  label: string;
  placeholder?: string;
  type: FieldType;
  icon?: string; // Ionicons name
  options?: string[]; // for 'select' type
};

// ---------------------------------------------------------------------------
// TCGs
// ---------------------------------------------------------------------------

const POKEMON_FIELDS: CategoryField[] = [
  { key: 'set', label: 'Set', placeholder: 'e.g. Base Set, Scarlet & Violet', type: 'text', icon: 'albums-outline' },
  { key: 'number', label: 'Card Number', placeholder: 'e.g. 4/102', type: 'text', icon: 'barcode-outline' },
  { key: 'rarity', label: 'Rarity', placeholder: 'e.g. Holo Rare, Ultra Rare', type: 'text', icon: 'star-outline' },
  { key: 'language', label: 'Language', type: 'select', icon: 'language-outline', options: ['English', 'Japanese', 'Korean', 'Chinese', 'French', 'German', 'Italian', 'Spanish', 'Portuguese'] },
  { key: 'printing', label: 'Printing', type: 'select', icon: 'layers-outline', options: ['1st Edition', 'Shadowless', 'Unlimited', 'Reverse Holo'] },
  { key: 'grade', label: 'Grade', placeholder: 'e.g. PSA 10, CGC 9.5, Raw', type: 'text', icon: 'shield-checkmark-outline' },
];

const MTG_FIELDS: CategoryField[] = [
  { key: 'set', label: 'Set', placeholder: 'e.g. Alpha, Modern Horizons 3', type: 'text', icon: 'albums-outline' },
  { key: 'collector_no', label: 'Collector Number', placeholder: 'e.g. 232/303', type: 'text', icon: 'barcode-outline' },
  { key: 'edition', label: 'Edition', type: 'select', icon: 'layers-outline', options: ['Alpha', 'Beta', 'Unlimited', 'Revised', 'Other'] },
  { key: 'foil', label: 'Foil', type: 'boolean', icon: 'sparkles-outline' },
  { key: 'language', label: 'Language', type: 'select', icon: 'language-outline', options: ['English', 'Japanese', 'German', 'French', 'Italian', 'Spanish', 'Portuguese', 'Russian', 'Korean', 'Chinese'] },
  { key: 'grade', label: 'Grade', placeholder: 'e.g. PSA 10, BGS 9.5, Raw', type: 'text', icon: 'shield-checkmark-outline' },
];

const YUGIOH_FIELDS: CategoryField[] = [
  { key: 'set', label: 'Set', placeholder: 'e.g. LOB, PHHY', type: 'text', icon: 'albums-outline' },
  { key: 'number', label: 'Card Number', placeholder: 'e.g. LOB-001', type: 'text', icon: 'barcode-outline' },
  { key: 'rarity', label: 'Rarity', placeholder: 'e.g. Secret Rare, Ultra Rare', type: 'text', icon: 'star-outline' },
  { key: 'edition', label: 'Edition', type: 'select', icon: 'layers-outline', options: ['1st Edition', 'Unlimited', 'Limited Edition'] },
  { key: 'language', label: 'Language', type: 'select', icon: 'language-outline', options: ['English', 'Japanese', 'Korean', 'French', 'German', 'Italian', 'Spanish', 'Portuguese'] },
  { key: 'grade', label: 'Grade', placeholder: 'e.g. PSA 10, CGC 9.5', type: 'text', icon: 'shield-checkmark-outline' },
];

const LORCANA_FIELDS: CategoryField[] = [
  { key: 'set', label: 'Set', placeholder: 'e.g. The First Chapter', type: 'text', icon: 'albums-outline' },
  { key: 'number', label: 'Card Number', placeholder: 'e.g. 1/204', type: 'text', icon: 'barcode-outline' },
  { key: 'color', label: 'Color', type: 'select', icon: 'color-palette-outline', options: ['Amber', 'Amethyst', 'Emerald', 'Ruby', 'Sapphire', 'Steel'] },
  { key: 'rarity', label: 'Rarity', type: 'select', icon: 'star-outline', options: ['Common', 'Uncommon', 'Rare', 'Super Rare', 'Legendary'] },
  { key: 'variant', label: 'Variant', type: 'select', icon: 'sparkles-outline', options: ['Standard', 'Foil', 'Enchanted'] },
  { key: 'language', label: 'Language', type: 'select', icon: 'language-outline', options: ['English', 'French', 'German', 'Italian'] },
];

// ---------------------------------------------------------------------------
// Toys / Figures
// ---------------------------------------------------------------------------

const FUNKO_FIELDS: CategoryField[] = [
  { key: 'line', label: 'Line', type: 'select', icon: 'cube-outline', options: ['Pop!', 'Pop! Vinyl Soda', 'Pop! Rides', 'Pop! Deluxe', 'Pop! Moment', 'Pop! Albums', 'Bitty Pop!'] },
  { key: 'number', label: 'Number', placeholder: 'e.g. #1234', type: 'text', icon: 'barcode-outline' },
  { key: 'exclusive', label: 'Exclusive', placeholder: 'e.g. Hot Topic, SDCC', type: 'text', icon: 'lock-closed-outline' },
  { key: 'sticker_variant', label: 'Sticker Variant', placeholder: 'e.g. GITD, Flocked, Chase', type: 'text', icon: 'pricetag-outline' },
  { key: 'box_condition', label: 'Box Condition', type: 'select', icon: 'cube-outline', options: ['Mint', 'Near Mint', 'Good', 'Fair', 'Damaged', 'Out of Box'] },
  { key: 'vaulted', label: 'Vaulted', type: 'boolean', icon: 'lock-closed-outline' },
];

const DESIGNER_TOYS_FIELDS: CategoryField[] = [
  { key: 'brand', label: 'Brand', placeholder: 'e.g. KAWS, Bearbrick, Pop Mart', type: 'text', icon: 'briefcase-outline' },
  { key: 'series', label: 'Series', placeholder: 'e.g. Companion, Series 47', type: 'text', icon: 'albums-outline' },
  { key: 'figure_name', label: 'Figure Name', placeholder: 'e.g. Dissected Companion', type: 'text', icon: 'person-outline' },
  { key: 'size', label: 'Size', type: 'select', icon: 'resize-outline', options: ['100%', '400%', '1000%', 'Other'] },
  { key: 'edition', label: 'Edition', type: 'select', icon: 'layers-outline', options: ['Retail', 'Collab', 'Limited', 'Chase'] },
  { key: 'release_year', label: 'Release Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
];

const ANIME_FIGURES_FIELDS: CategoryField[] = [
  { key: 'manufacturer', label: 'Manufacturer', placeholder: 'e.g. Good Smile, Alter', type: 'text', icon: 'business-outline' },
  { key: 'series', label: 'Series / Franchise', placeholder: 'e.g. Demon Slayer, Fate', type: 'text', icon: 'film-outline' },
  { key: 'character', label: 'Character', placeholder: 'e.g. Nezuko Kamado', type: 'text', icon: 'person-outline' },
  { key: 'scale', label: 'Scale', type: 'select', icon: 'resize-outline', options: ['1/4', '1/6', '1/7', '1/8', 'Non-scale'] },
  { key: 'type', label: 'Type', type: 'select', icon: 'shapes-outline', options: ['Scale Figure', 'Nendoroid', 'Figma', 'Prize Figure', 'Garage Kit'] },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['New Sealed', 'Opened', 'Displayed', 'Damaged Box'] },
  { key: 'release_year', label: 'Release Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
];

const HOT_TOYS_FIELDS: CategoryField[] = [
  { key: 'franchise', label: 'Franchise', placeholder: 'e.g. Marvel, Star Wars', type: 'text', icon: 'film-outline' },
  { key: 'character', label: 'Character', placeholder: 'e.g. Iron Man Mark L', type: 'text', icon: 'person-outline' },
  { key: 'scale', label: 'Scale', type: 'select', icon: 'resize-outline', options: ['1/6', '1/4', 'Life-size'] },
  { key: 'edition', label: 'Edition', type: 'select', icon: 'layers-outline', options: ['Standard', 'Deluxe', 'Special', 'Exclusive'] },
  { key: 'mms_number', label: 'MMS Number', placeholder: 'e.g. MMS473', type: 'text', icon: 'barcode-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['New Sealed', 'Opened', 'Displayed'] },
  { key: 'release_year', label: 'Release Year', placeholder: 'e.g. 2023', type: 'text', icon: 'calendar-outline' },
];

const ACTION_FIGURES_FIELDS: CategoryField[] = [
  { key: 'line', label: 'Line', placeholder: 'e.g. Black Series, Lightning Collection', type: 'text', icon: 'albums-outline' },
  { key: 'scale', label: 'Scale', type: 'select', icon: 'resize-outline', options: ['3.75"', '6"', '12"'] },
  { key: 'wave', label: 'Wave', placeholder: 'e.g. Wave 3', type: 'text', icon: 'layers-outline' },
  { key: 'packaging_type', label: 'Packaging', type: 'select', icon: 'cube-outline', options: ['Box Art', 'Standard', 'Window Box', 'Archive'] },
  { key: 'retailer_exclusive', label: 'Retailer Exclusive', placeholder: 'e.g. Target, Walmart', type: 'text', icon: 'lock-closed-outline' },
  { key: 'sealed', label: 'Sealed', type: 'boolean', icon: 'lock-closed-outline' },
];

const VINTAGE_TOYS_FIELDS: CategoryField[] = [
  { key: 'era', label: 'Era', placeholder: 'e.g. 1980s', type: 'text', icon: 'time-outline' },
  { key: 'manufacturer', label: 'Manufacturer', placeholder: 'e.g. Kenner, Hasbro', type: 'text', icon: 'business-outline' },
  { key: 'item_type', label: 'Item Type', type: 'select', icon: 'shapes-outline', options: ['Figure', 'Vehicle', 'Playset', 'Empty Box', 'Proof Card', 'Accessory'] },
  { key: 'completeness', label: 'Completeness', type: 'select', icon: 'checkmark-done-outline', options: ['CIB', 'Loose Complete', 'Loose Incomplete', 'Box Only'] },
  { key: 'origin_country', label: 'Origin Country', placeholder: 'e.g. USA, Japan', type: 'text', icon: 'globe-outline' },
  { key: 'afa_grade', label: 'AFA Grade', placeholder: 'e.g. AFA 85', type: 'text', icon: 'shield-checkmark-outline' },
];

const MARVEL_LEGENDS_FIELDS: CategoryField[] = [
  { key: 'wave', label: 'Wave', placeholder: 'e.g. Bro Thor Wave', type: 'text', icon: 'layers-outline' },
  { key: 'baf_figure', label: 'BAF Figure', placeholder: 'e.g. Mr. Hyde', type: 'text', icon: 'body-outline' },
  { key: 'series', label: 'Series', type: 'select', icon: 'albums-outline', options: ['Standard', 'Retro', '20th Anniversary', 'Haslab', 'Deluxe', 'Fan Channel'] },
  { key: 'packaging_type', label: 'Packaging', type: 'select', icon: 'cube-outline', options: ['Standard', 'Window Box', 'Retro Card'] },
  { key: 'retailer_exclusive', label: 'Retailer Exclusive', placeholder: 'e.g. Target, Walmart', type: 'text', icon: 'lock-closed-outline' },
  { key: 'sealed', label: 'Sealed', type: 'boolean', icon: 'lock-closed-outline' },
];

// ---------------------------------------------------------------------------
// Building / Models
// ---------------------------------------------------------------------------

const LEGO_FIELDS: CategoryField[] = [
  { key: 'set_number', label: 'Set Number', placeholder: 'e.g. 75192', type: 'text', icon: 'barcode-outline' },
  { key: 'theme', label: 'Theme', placeholder: 'e.g. Star Wars, Technic, City', type: 'text', icon: 'grid-outline' },
  { key: 'piece_count', label: 'Piece Count', placeholder: 'e.g. 7541', type: 'text', icon: 'apps-outline' },
  { key: 'year', label: 'Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
  { key: 'retirement_date', label: 'Retirement Date', placeholder: 'e.g. 2025-12', type: 'text', icon: 'time-outline' },
  { key: 'sealed', label: 'Sealed / New in Box', type: 'boolean', icon: 'lock-closed-outline' },
];

const GUNPLA_FIELDS: CategoryField[] = [
  { key: 'grade', label: 'Grade', type: 'select', icon: 'trophy-outline', options: ['HG', 'RG', 'MG', 'PG', 'SD', 'RE/100', 'FM'] },
  { key: 'series', label: 'Gundam Series', placeholder: 'e.g. UC, Wing, SEED, IBO', type: 'text', icon: 'film-outline' },
  { key: 'mobile_suit', label: 'Mobile Suit', placeholder: 'e.g. RX-78-2', type: 'text', icon: 'rocket-outline' },
  { key: 'scale', label: 'Scale', type: 'select', icon: 'resize-outline', options: ['1/144', '1/100', '1/60'] },
  { key: 'version', label: 'Version', placeholder: 'e.g. Ver.Ka, P-Bandai', type: 'text', icon: 'layers-outline' },
  { key: 'built', label: 'Built', type: 'boolean', icon: 'construct-outline' },
];

const SCALE_MODELS_FIELDS: CategoryField[] = [
  { key: 'brand', label: 'Brand', placeholder: 'e.g. Tamiya, Hasegawa, Revell', type: 'text', icon: 'briefcase-outline' },
  { key: 'subject', label: 'Subject', type: 'select', icon: 'airplane-outline', options: ['Aircraft', 'Tank', 'Ship', 'Car', 'Motorcycle', 'Sci-fi', 'Other'] },
  { key: 'scale', label: 'Scale', type: 'select', icon: 'resize-outline', options: ['1/72', '1/48', '1/35', '1/350', '1/700', '1/24', 'Other'] },
  { key: 'era', label: 'Era', type: 'select', icon: 'time-outline', options: ['WWI', 'WWII', 'Cold War', 'Modern', 'Sci-fi'] },
  { key: 'built', label: 'Built', type: 'boolean', icon: 'construct-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['New Sealed', 'Open Box', 'Built Unpainted', 'Built Painted'] },
];

const WARHAMMER_FIELDS: CategoryField[] = [
  { key: 'item_category', label: 'Item Category', type: 'select', icon: 'list-outline', options: ['Miniature', 'Book / Novel', 'Codex / Battletome', 'Rulebook', 'Art Book', 'Limited Edition Book'] },
  { key: 'game_system', label: 'Game System', type: 'select', icon: 'game-controller-outline', options: ['Warhammer 40K', 'Age of Sigmar', 'Horus Heresy', 'Kill Team', 'Warcry', 'Necromunda'] },
  { key: 'faction', label: 'Faction', placeholder: 'e.g. Space Marines, Orks', type: 'text', icon: 'flag-outline' },
  { key: 'kit_name', label: 'Kit / Title', placeholder: 'e.g. Leviathan Box Set or Horus Rising', type: 'text', icon: 'cube-outline' },
  { key: 'kit_type', label: 'Kit Type', type: 'select', icon: 'shapes-outline', options: ['HQ', 'Troops', 'Elite', 'Vehicle', 'Centerpiece', 'Titan', 'Start Collecting'] },
  { key: 'isbn', label: 'ISBN', placeholder: 'e.g. 978-1849707435', type: 'text', icon: 'barcode-outline' },
  { key: 'author', label: 'Author', placeholder: 'e.g. Dan Abnett', type: 'text', icon: 'person-outline' },
  { key: 'publisher', label: 'Publisher', type: 'select', icon: 'business-outline', options: ['Black Library', 'Games Workshop', 'Forge World'] },
  { key: 'book_type', label: 'Book Type', type: 'select', icon: 'book-outline', options: ['Novel', 'Omnibus', 'Codex', 'Battletome', 'Rulebook', 'Campaign Book', 'Art Book', 'Imperial Armour'] },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['New Sealed', 'New on Sprue', 'Like New', 'Good', 'Built', 'Primed', 'Painted', 'Pro Painted'] },
  { key: 'edition', label: 'Edition', type: 'select', icon: 'layers-outline', options: ['Standard', 'Limited', 'Special', 'Collector', 'Numbered', 'OOP'] },
  { key: 'points', label: 'Points', placeholder: 'e.g. 250', type: 'text', icon: 'analytics-outline' },
];

// ---------------------------------------------------------------------------
// Gaming
// ---------------------------------------------------------------------------

const RETRO_GAMES_FIELDS: CategoryField[] = [
  { key: 'platform', label: 'Platform', type: 'select', icon: 'game-controller-outline', options: ['NES', 'SNES', 'N64', 'GameCube', 'Wii', 'Game Boy', 'GBA', 'DS', 'Genesis', 'Saturn', 'Dreamcast', 'PS1', 'PS2', 'PSP', 'Xbox', 'PC', 'Atari', 'Other'] },
  { key: 'title', label: 'Game Title', placeholder: 'e.g. Super Mario World', type: 'text', icon: 'text-outline' },
  { key: 'region', label: 'Region', type: 'select', icon: 'globe-outline', options: ['NTSC (US)', 'PAL (EU)', 'NTSC-J (JP)'] },
  { key: 'completeness', label: 'Completeness', type: 'select', icon: 'checkbox-outline', options: ['Loose (Cart only)', 'CIB (Complete in Box)', 'Sealed', 'Graded'] },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['Mint', 'Near Mint', 'Good', 'Fair', 'Poor'] },
  { key: 'year', label: 'Release Year', placeholder: 'e.g. 1992', type: 'text', icon: 'calendar-outline' },
];

// ---------------------------------------------------------------------------
// Media
// ---------------------------------------------------------------------------

const MANGA_FIELDS: CategoryField[] = [
  { key: 'title', label: 'Series Title', placeholder: 'e.g. One Piece, Berserk', type: 'text', icon: 'book-outline' },
  { key: 'publisher', label: 'Publisher', type: 'select', icon: 'business-outline', options: ['VIZ Media', 'Kodansha', 'Dark Horse', 'Tokyopop', 'Yen Press', 'Seven Seas', 'Square Enix', 'Shogakukan', 'Other'] },
  { key: 'volume', label: 'Volume', placeholder: 'e.g. Vol. 1, Complete Set', type: 'text', icon: 'layers-outline' },
  { key: 'total_volumes', label: 'Total Volumes in Series', placeholder: 'e.g. 37', type: 'text', icon: 'stats-chart-outline' },
  { key: 'language', label: 'Language', type: 'select', icon: 'language-outline', options: ['English', 'Japanese', 'French', 'German', 'Spanish'] },
  { key: 'printing', label: 'Printing', type: 'select', icon: 'print-outline', options: ['1st Printing', 'Later Printing', 'OOP (Out of Print)'] },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['Mint', 'Like New', 'Good', 'Acceptable', 'Ex-Library'] },
];

const BLURAY_STEELBOOK_FIELDS: CategoryField[] = [
  { key: 'title', label: 'Title', placeholder: 'e.g. Blade Runner 2049', type: 'text', icon: 'film-outline' },
  { key: 'studio', label: 'Studio / Label', placeholder: 'e.g. Criterion, Arrow', type: 'text', icon: 'business-outline' },
  { key: 'format', label: 'Format', type: 'select', icon: 'disc-outline', options: ['4K UHD', 'Blu-ray', 'DVD', '4K + Blu-ray'] },
  { key: 'edition', label: 'Edition', type: 'select', icon: 'layers-outline', options: ['Steelbook', 'Slipcover', 'Mediabook', 'Limited Edition', 'Standard'] },
  { key: 'region', label: 'Region', type: 'select', icon: 'globe-outline', options: ['Region A', 'Region B', 'Region C', 'Region Free'] },
  { key: 'sealed', label: 'Sealed', type: 'boolean', icon: 'lock-closed-outline' },
];

const ANIME_BLURAY_FIELDS: CategoryField[] = [
  { key: 'title', label: 'Anime Title', placeholder: 'e.g. Cowboy Bebop', type: 'text', icon: 'film-outline' },
  { key: 'studio', label: 'Studio / Label', placeholder: 'e.g. Aniplex, Funimation', type: 'text', icon: 'business-outline' },
  { key: 'format', label: 'Format', type: 'select', icon: 'disc-outline', options: ['BD Box Set', 'BD Single', 'BD + DVD', 'Laserdisc'] },
  { key: 'region', label: 'Region', type: 'select', icon: 'globe-outline', options: ['Region A', 'Region B', 'Region C', 'Region Free'] },
  { key: 'limited', label: 'Limited / Numbered Run', type: 'boolean', icon: 'star-outline' },
  { key: 'extras', label: 'Extras', placeholder: 'e.g. Art booklet, OST CD', type: 'text', icon: 'gift-outline' },
  { key: 'sealed', label: 'Sealed', type: 'boolean', icon: 'lock-closed-outline' },
];

const ANIME_SOUNDTRACK_FIELDS: CategoryField[] = [
  { key: 'title', label: 'Album Title', placeholder: 'e.g. Spirited Away OST', type: 'text', icon: 'musical-notes-outline' },
  { key: 'anime', label: 'Anime / Game', placeholder: 'e.g. Spirited Away', type: 'text', icon: 'film-outline' },
  { key: 'format', label: 'Format', type: 'select', icon: 'disc-outline', options: ['CD', 'Vinyl', 'Cassette', 'Digital'] },
  { key: 'label', label: 'Label', placeholder: 'e.g. King Records', type: 'text', icon: 'business-outline' },
  { key: 'catalog_no', label: 'Catalog Number', placeholder: 'e.g. KICA-1234', type: 'text', icon: 'barcode-outline' },
  { key: 'edition', label: 'Edition', type: 'select', icon: 'layers-outline', options: ['Standard', 'Limited', 'Event Exclusive', 'Preorder Bonus'] },
  { key: 'sealed', label: 'Sealed', type: 'boolean', icon: 'lock-closed-outline' },
];

const ANIME_OST_VINYL_FIELDS: CategoryField[] = [
  { key: 'title', label: 'Title', placeholder: 'e.g. Akira OST', type: 'text', icon: 'musical-notes-outline' },
  { key: 'anime', label: 'Anime', placeholder: 'e.g. Akira', type: 'text', icon: 'film-outline' },
  { key: 'label', label: 'Label', placeholder: 'e.g. Tiger Lab, Milan', type: 'text', icon: 'business-outline' },
  { key: 'color', label: 'Vinyl Color', placeholder: 'e.g. Clear Red, Splatter', type: 'text', icon: 'color-palette-outline' },
  { key: 'pressing', label: 'Pressing', type: 'select', icon: 'layers-outline', options: ['1st Pressing', 'Repress', '2nd Pressing'] },
  { key: 'rpm', label: 'RPM', type: 'select', icon: 'speedometer-outline', options: ['33', '45'] },
  { key: 'sealed', label: 'Sealed', type: 'boolean', icon: 'lock-closed-outline' },
];

// ---------------------------------------------------------------------------
// Music / Fandom
// ---------------------------------------------------------------------------

const KPOP_MERCH_FIELDS: CategoryField[] = [
  { key: 'artist', label: 'Artist / Group', placeholder: 'e.g. BTS, Blackpink, Stray Kids', type: 'text', icon: 'people-outline' },
  { key: 'item_type', label: 'Item Type', type: 'select', icon: 'shapes-outline', options: ['Photocard', 'Album', 'Lightstick', 'Poster', 'Fansign', 'Merchandise', 'Other'] },
  { key: 'album', label: 'Album', placeholder: 'e.g. Map of the Soul: 7', type: 'text', icon: 'disc-outline' },
  { key: 'version', label: 'Version', placeholder: 'e.g. Version 1, Weverse Exclusive', type: 'text', icon: 'layers-outline' },
  { key: 'member', label: 'Member', placeholder: 'e.g. Jungkook, Lisa', type: 'text', icon: 'person-outline' },
  { key: 'official', label: 'Official Merchandise', type: 'boolean', icon: 'checkmark-circle-outline' },
];

const TAYLOR_SWIFT_FIELDS: CategoryField[] = [
  { key: 'item_type', label: 'Item Type', type: 'select', icon: 'shapes-outline', options: ['Vinyl', 'CD', 'Merch', 'Ticket', 'Signed Item', 'Tour Exclusive'] },
  { key: 'album', label: 'Album / Era', placeholder: "e.g. 1989 (Taylor's Version)", type: 'text', icon: 'disc-outline' },
  { key: 'variant', label: 'Variant', placeholder: 'e.g. Lavender Vinyl, Target Exclusive', type: 'text', icon: 'color-palette-outline' },
  { key: 'era', label: 'Tour Era', placeholder: 'e.g. Eras Tour, 1989', type: 'text', icon: 'musical-note-outline' },
  { key: 'signed', label: 'Signed', type: 'boolean', icon: 'create-outline' },
  { key: 'sealed', label: 'Sealed', type: 'boolean', icon: 'lock-closed-outline' },
];

const POP_FANDOM_FIELDS: CategoryField[] = [
  { key: 'artist', label: 'Artist', placeholder: 'e.g. Ariana Grande, Olivia Rodrigo', type: 'text', icon: 'people-outline' },
  { key: 'item_type', label: 'Item Type', type: 'select', icon: 'shapes-outline', options: ['Vinyl', 'Merch', 'Poster', 'Tour Item', 'Signed Item'] },
  { key: 'variant', label: 'Variant', placeholder: 'e.g. Color variant, exclusive', type: 'text', icon: 'color-palette-outline' },
  { key: 'tour', label: 'Tour', placeholder: 'e.g. Sweetener Tour', type: 'text', icon: 'musical-note-outline' },
  { key: 'signed', label: 'Signed', type: 'boolean', icon: 'create-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['Mint', 'Near Mint', 'Good', 'Fair'] },
];

const KPOP_LIGHTSTICKS_FIELDS: CategoryField[] = [
  { key: 'artist', label: 'Artist / Group', placeholder: 'e.g. BTS, TWICE', type: 'text', icon: 'people-outline' },
  { key: 'version', label: 'Version', placeholder: 'e.g. Ver.3, Special Edition', type: 'text', icon: 'layers-outline' },
  { key: 'tour_exclusive', label: 'Tour Exclusive', type: 'boolean', icon: 'star-outline' },
  { key: 'bluetooth', label: 'Bluetooth Enabled', type: 'boolean', icon: 'bluetooth-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['New Sealed', 'Opened', 'Used'] },
  { key: 'year', label: 'Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
];

// ---------------------------------------------------------------------------
// Disney / Theme Parks
// ---------------------------------------------------------------------------

const DISNEY_FIELDS: CategoryField[] = [
  { key: 'item_type', label: 'Item Type', type: 'select', icon: 'shapes-outline', options: ['Pin', 'Figure', 'Plush', 'Art', 'Ears', 'Ornament', 'Other'] },
  { key: 'franchise', label: 'Franchise', type: 'select', icon: 'film-outline', options: ['Classic Disney', 'Pixar', 'Marvel', 'Star Wars', 'Other'] },
  { key: 'collection', label: 'Collection', placeholder: 'e.g. Disney 100, Fantasia', type: 'text', icon: 'albums-outline' },
  { key: 'park_exclusive', label: 'Park Exclusive', type: 'boolean', icon: 'location-outline' },
  { key: 'limited_edition', label: 'Limited Edition', type: 'boolean', icon: 'star-outline' },
  { key: 'year', label: 'Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
];

const THEME_PARK_FIELDS: CategoryField[] = [
  { key: 'park', label: 'Park', placeholder: 'e.g. Disneyland, USJ, WDW', type: 'text', icon: 'location-outline' },
  { key: 'item_type', label: 'Item Type', type: 'select', icon: 'shapes-outline', options: ['Pin', 'Popcorn Bucket', 'Figure', 'Apparel', 'Prop Replica', 'Other'] },
  { key: 'event', label: 'Event', placeholder: 'e.g. 50th Anniversary, Halloween', type: 'text', icon: 'calendar-outline' },
  { key: 'year', label: 'Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
  { key: 'region', label: 'Region', type: 'select', icon: 'globe-outline', options: ['US', 'JP', 'EU', 'HK', 'Shanghai'] },
  { key: 'limited_edition', label: 'Limited Edition', type: 'boolean', icon: 'star-outline' },
];

const GHIBLI_FIELDS: CategoryField[] = [
  { key: 'film', label: 'Film', placeholder: 'e.g. Spirited Away, Totoro', type: 'text', icon: 'film-outline' },
  { key: 'item_type', label: 'Item Type', type: 'select', icon: 'shapes-outline', options: ['Figure', 'Plush', 'Art Print', 'Animation Cel', 'Music Box', 'Other'] },
  { key: 'manufacturer', label: 'Manufacturer', placeholder: 'e.g. Donguri Sora, Benelic', type: 'text', icon: 'business-outline' },
  { key: 'jp_exclusive', label: 'Japan Exclusive', type: 'boolean', icon: 'flag-outline' },
  { key: 'vintage', label: 'Vintage (Pre-2000)', type: 'boolean', icon: 'time-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['Mint', 'Near Mint', 'Good', 'Fair'] },
];

// ---------------------------------------------------------------------------
// Japan Exclusives
// ---------------------------------------------------------------------------

const BANDAI_PREMIUM_FIELDS: CategoryField[] = [
  { key: 'line', label: 'Line', placeholder: 'e.g. S.H.Figuarts, Robot Spirits', type: 'text', icon: 'cube-outline' },
  { key: 'franchise', label: 'Franchise', placeholder: 'e.g. Gundam, Dragon Ball', type: 'text', icon: 'film-outline' },
  { key: 'item_name', label: 'Item Name', placeholder: 'e.g. Strike Freedom Ver.', type: 'text', icon: 'text-outline' },
  { key: 'p_bandai', label: 'P-Bandai Web Exclusive', type: 'boolean', icon: 'lock-closed-outline' },
  { key: 'tamashii_exclusive', label: 'Tamashii Nations Exclusive', type: 'boolean', icon: 'star-outline' },
  { key: 'release_year', label: 'Release Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
];

const JP_MAGAZINE_FIELDS: CategoryField[] = [
  { key: 'magazine', label: 'Magazine', placeholder: 'e.g. Dengeki, Newtype, Famitsu', type: 'text', icon: 'newspaper-outline' },
  { key: 'issue', label: 'Issue', placeholder: 'e.g. March 2024', type: 'text', icon: 'calendar-outline' },
  { key: 'insert_type', label: 'Insert Type', type: 'select', icon: 'gift-outline', options: ['Poster', 'Figure', 'Code', 'Artbook', 'Clear File', 'None'] },
  { key: 'franchise', label: 'Franchise', placeholder: 'e.g. Fate, Hololive', type: 'text', icon: 'film-outline' },
  { key: 'year', label: 'Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['New Sealed', 'Opened (Insert Present)', 'Opened (Insert Missing)'] },
];

const JP_EVENT_FIELDS: CategoryField[] = [
  { key: 'event', label: 'Event', placeholder: 'e.g. Comiket, Wonder Festival', type: 'text', icon: 'calendar-outline' },
  { key: 'season', label: 'Season', placeholder: 'e.g. Summer 2024', type: 'text', icon: 'sunny-outline' },
  { key: 'item_type', label: 'Item Type', type: 'select', icon: 'shapes-outline', options: ['Figure', 'Doujin', 'Tapestry', 'Acrylic Stand', 'Badge', 'Other'] },
  { key: 'circle', label: 'Circle / Manufacturer', placeholder: 'e.g. T2 Art Works', type: 'text', icon: 'people-outline' },
  { key: 'franchise', label: 'Franchise', placeholder: 'e.g. Touhou, Vocaloid', type: 'text', icon: 'film-outline' },
  { key: 'limited_quantity', label: 'Limited Quantity', type: 'boolean', icon: 'alert-circle-outline' },
];

// ---------------------------------------------------------------------------
// Nintendo / Pokemon Merch
// ---------------------------------------------------------------------------

const NINTENDO_MERCH_FIELDS: CategoryField[] = [
  { key: 'franchise', label: 'Franchise', type: 'select', icon: 'game-controller-outline', options: ['Pokemon', 'Mario', 'Zelda', 'Kirby', 'Splatoon', 'Animal Crossing', 'Other'] },
  { key: 'item_type', label: 'Item Type', type: 'select', icon: 'shapes-outline', options: ['Plush', 'Figure', 'Amiibo', 'Apparel', 'Art / Print', 'Other'] },
  { key: 'store_exclusive', label: 'Store Exclusive', placeholder: 'e.g. Pokemon Center, Nintendo Store', type: 'text', icon: 'storefront-outline' },
  { key: 'region', label: 'Region', type: 'select', icon: 'globe-outline', options: ['JP', 'US', 'EU'] },
  { key: 'year', label: 'Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
  { key: 'sealed', label: 'Sealed / New with Tag', type: 'boolean', icon: 'lock-closed-outline' },
];

const RETRO_POKEMON_FIELDS: CategoryField[] = [
  { key: 'item_type', label: 'Item Type', placeholder: 'e.g. Pokedex toy, GB accessory', type: 'text', icon: 'shapes-outline' },
  { key: 'generation', label: 'Generation', type: 'select', icon: 'layers-outline', options: ['Gen 1 (Red/Blue)', 'Gen 2 (Gold/Silver)', 'Gen 3 (Ruby/Sapphire)', 'Gen 4 (Diamond/Pearl)', 'Gen 5+'] },
  { key: 'brand', label: 'Brand', placeholder: 'e.g. TOMY, Hasbro, Tiger', type: 'text', icon: 'briefcase-outline' },
  { key: 'year', label: 'Year', placeholder: 'e.g. 1999', type: 'text', icon: 'calendar-outline' },
  { key: 'working', label: 'Working', type: 'boolean', icon: 'checkmark-circle-outline' },
  { key: 'boxed', label: 'Boxed', type: 'boolean', icon: 'cube-outline' },
];

// ---------------------------------------------------------------------------
// IP-Specific
// ---------------------------------------------------------------------------

const ONE_PIECE_FIELDS: CategoryField[] = [
  { key: 'item_type', label: 'Item Type', type: 'select', icon: 'shapes-outline', options: ['Figure', 'Card', 'Plush', 'Art', 'Ichiban Kuji', 'Other'] },
  { key: 'character', label: 'Character', placeholder: 'e.g. Luffy, Zoro', type: 'text', icon: 'person-outline' },
  { key: 'manufacturer', label: 'Manufacturer', type: 'select', icon: 'business-outline', options: ['Megahouse', 'Bandai', 'Banpresto', 'Tamashii Nations', 'Other'] },
  { key: 'line', label: 'Line', placeholder: 'e.g. Portrait of Pirates, Figuarts ZERO', type: 'text', icon: 'albums-outline' },
  { key: 'scale', label: 'Scale', placeholder: 'e.g. 1/8', type: 'text', icon: 'resize-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['New Sealed', 'Opened', 'Displayed'] },
];

const VTUBER_FIELDS: CategoryField[] = [
  { key: 'vtuber', label: 'Agency', type: 'select', icon: 'people-outline', options: ['Hololive', 'Nijisanji', 'VShojo', 'Indie', 'Other'] },
  { key: 'character', label: 'Character', placeholder: 'e.g. Gawr Gura, Ironmouse', type: 'text', icon: 'person-outline' },
  { key: 'item_type', label: 'Item Type', type: 'select', icon: 'shapes-outline', options: ['Acrylic Stand', 'Tapestry', 'Badge', 'Voice Pack', 'Figure', 'Other'] },
  { key: 'event', label: 'Event', placeholder: 'e.g. Birthday 2024, Concert', type: 'text', icon: 'calendar-outline' },
  { key: 'official', label: 'Official Merchandise', type: 'boolean', icon: 'checkmark-circle-outline' },
  { key: 'year', label: 'Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
];

// ---------------------------------------------------------------------------
// Niche
// ---------------------------------------------------------------------------

const KEYCAPS_FIELDS: CategoryField[] = [
  { key: 'maker', label: 'Maker', placeholder: 'e.g. Jelly Key, Dwarf Factory', type: 'text', icon: 'person-outline' },
  { key: 'sculpt', label: 'Sculpt', placeholder: 'e.g. Zen Pond, Bongo Cat', type: 'text', icon: 'shapes-outline' },
  { key: 'colorway', label: 'Colorway', placeholder: 'e.g. Coral Reef, Galaxy', type: 'text', icon: 'color-palette-outline' },
  { key: 'profile', label: 'Profile', type: 'select', icon: 'keypad-outline', options: ['Cherry', 'SA', 'DSA', 'KAT', 'OEM', 'Other'] },
  { key: 'material', label: 'Material', type: 'select', icon: 'diamond-outline', options: ['Resin', 'Metal', 'Wood', 'Ceramic'] },
  { key: 'run_size', label: 'Run Size', placeholder: 'e.g. 1 of 50', type: 'text', icon: 'analytics-outline' },
  { key: 'drop_date', label: 'Drop Date', placeholder: 'e.g. 2024-03', type: 'text', icon: 'calendar-outline' },
];

const LOUNGEFLY_FIELDS: CategoryField[] = [
  { key: 'license', label: 'License', placeholder: 'e.g. Disney, Marvel, Sanrio', type: 'text', icon: 'film-outline' },
  { key: 'collection', label: 'Collection', placeholder: 'e.g. Villains, Princess', type: 'text', icon: 'albums-outline' },
  { key: 'retailer', label: 'Retailer Exclusive', placeholder: 'e.g. BoxLunch, Hot Topic', type: 'text', icon: 'storefront-outline' },
  { key: 'era', label: 'Era', type: 'select', icon: 'time-outline', options: ['Pre-Funko', 'Funko Era'] },
  { key: 'drop_date', label: 'Drop Date', placeholder: 'e.g. 2024-06', type: 'text', icon: 'calendar-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['New with Tags', 'New without Tags', 'Used - Like New', 'Used'] },
];

// ---------------------------------------------------------------------------
// Collectibles
// ---------------------------------------------------------------------------

const BLIND_BOX_FIELDS: CategoryField[] = [
  { key: 'brand', label: 'Brand', placeholder: 'e.g. Pop Mart, Sonny Angel', type: 'text', icon: 'business-outline' },
  { key: 'series', label: 'Series', placeholder: 'e.g. Molly, Dimoo', type: 'text', icon: 'albums-outline' },
  { key: 'figure_name', label: 'Figure Name', placeholder: 'e.g. Space Molly 400%', type: 'text', icon: 'person-outline' },
  { key: 'variant', label: 'Variant', type: 'select', icon: 'sparkles-outline', options: ['Regular', 'Chase', 'Secret', 'Special'] },
  { key: 'sealed', label: 'Sealed', type: 'boolean', icon: 'lock-closed-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['Mint', 'Near Mint', 'Good', 'No Card'] },
];

// ---------------------------------------------------------------------------
// Spirits & Luxury
// ---------------------------------------------------------------------------

const WHISKEY_FIELDS: CategoryField[] = [
  { key: 'distillery', label: 'Distillery', placeholder: 'e.g. Macallan, Yamazaki', type: 'text', icon: 'business-outline' },
  { key: 'expression', label: 'Expression', placeholder: 'e.g. 18 Year Sherry Oak', type: 'text', icon: 'flask-outline' },
  { key: 'age_statement', label: 'Age Statement', placeholder: 'e.g. 12, 18, NAS', type: 'text', icon: 'time-outline' },
  { key: 'spirit_type', label: 'Type', type: 'select', icon: 'wine-outline', options: ['Scotch', 'Bourbon', 'Japanese', 'Irish', 'Rye', 'Other'] },
  { key: 'cask_type', label: 'Cask Type', placeholder: 'e.g. Sherry, Bourbon, Mizunara', type: 'text', icon: 'cube-outline' },
  { key: 'abv', label: 'ABV', placeholder: 'e.g. 43%, Cask Strength', type: 'text', icon: 'analytics-outline' },
  { key: 'sealed', label: 'Sealed', type: 'boolean', icon: 'lock-closed-outline' },
];

const VINTAGE_CAMERAS_FIELDS: CategoryField[] = [
  { key: 'brand', label: 'Brand', placeholder: 'e.g. Leica, Nikon, Canon', type: 'text', icon: 'business-outline' },
  { key: 'model', label: 'Model', placeholder: 'e.g. M3, F3, AE-1', type: 'text', icon: 'camera-outline' },
  { key: 'camera_type', label: 'Camera Type', type: 'select', icon: 'aperture-outline', options: ['SLR', 'Rangefinder', 'TLR', 'Point & Shoot', 'Medium Format', 'Large Format'] },
  { key: 'film_format', label: 'Film Format', type: 'select', icon: 'film-outline', options: ['35mm', '120 (Medium Format)', '4x5', '8x10', '110', 'Instant'] },
  { key: 'year', label: 'Year', placeholder: 'e.g. 1972', type: 'text', icon: 'calendar-outline' },
  { key: 'working', label: 'Working', type: 'boolean', icon: 'checkmark-circle-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['Mint', 'Excellent', 'Good', 'Fair', 'For Parts'] },
];

const PENS_FIELDS: CategoryField[] = [
  { key: 'brand', label: 'Brand', placeholder: 'e.g. Montblanc, Pelikan, Sailor', type: 'text', icon: 'business-outline' },
  { key: 'model', label: 'Model', placeholder: 'e.g. 149, M800, Pro Gear', type: 'text', icon: 'create-outline' },
  { key: 'nib_size', label: 'Nib Size', type: 'select', icon: 'create-outline', options: ['EF', 'F', 'M', 'B', 'BB', 'Stub', 'Italic', 'Flex'] },
  { key: 'nib_material', label: 'Nib Material', type: 'select', icon: 'diamond-outline', options: ['Steel', '14K Gold', '18K Gold', '21K Gold', 'Palladium'] },
  { key: 'filling_system', label: 'Filling System', type: 'select', icon: 'water-outline', options: ['Piston', 'Converter', 'Cartridge', 'Vacuum', 'Eyedropper', 'Lever'] },
  { key: 'limited_edition', label: 'Limited Edition', type: 'boolean', icon: 'star-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['New in Box', 'Like New', 'User Grade', 'Vintage - Restored', 'Vintage - Unrestored'] },
];

// ---------------------------------------------------------------------------
// Additional TCGs
// ---------------------------------------------------------------------------

const DIGIMON_FIELDS: CategoryField[] = [
  { key: 'set', label: 'Set', placeholder: 'e.g. BT-01, EX-04', type: 'text', icon: 'albums-outline' },
  { key: 'number', label: 'Card Number', placeholder: 'e.g. BT1-025', type: 'text', icon: 'barcode-outline' },
  { key: 'rarity', label: 'Rarity', type: 'select', icon: 'star-outline', options: ['Common', 'Uncommon', 'Rare', 'Super Rare', 'Secret Rare', 'Alt Art'] },
  { key: 'language', label: 'Language', type: 'select', icon: 'language-outline', options: ['English', 'Japanese'] },
  { key: 'variant', label: 'Variant', type: 'select', icon: 'sparkles-outline', options: ['Standard', 'Alt Art', 'Box Topper', 'Promo'] },
  { key: 'grade', label: 'Grade', placeholder: 'e.g. PSA 10, CGC 9.5', type: 'text', icon: 'shield-checkmark-outline' },
];

const ONE_PIECE_TCG_FIELDS: CategoryField[] = [
  { key: 'set', label: 'Set', placeholder: 'e.g. OP-01, OP-05', type: 'text', icon: 'albums-outline' },
  { key: 'number', label: 'Card Number', placeholder: 'e.g. OP01-001', type: 'text', icon: 'barcode-outline' },
  { key: 'rarity', label: 'Rarity', type: 'select', icon: 'star-outline', options: ['Common', 'Uncommon', 'Rare', 'Super Rare', 'Secret Rare', 'Leader', 'Alt Art', 'Manga Art'] },
  { key: 'language', label: 'Language', type: 'select', icon: 'language-outline', options: ['English', 'Japanese'] },
  { key: 'variant', label: 'Variant', type: 'select', icon: 'sparkles-outline', options: ['Standard', 'Alt Art', 'Manga Art', 'Promo', 'Tournament'] },
  { key: 'grade', label: 'Grade', placeholder: 'e.g. PSA 10, CGC 9.5', type: 'text', icon: 'shield-checkmark-outline' },
];

// ---------------------------------------------------------------------------
// Media — Comic Books & Vinyl Records
// ---------------------------------------------------------------------------

const COMIC_BOOKS_FIELDS: CategoryField[] = [
  { key: 'publisher', label: 'Publisher', type: 'select', icon: 'business-outline', options: ['Marvel', 'DC', 'Image', 'Dark Horse', 'IDW', 'Boom! Studios', 'Indie', 'Other'] },
  { key: 'series', label: 'Series', placeholder: 'e.g. Amazing Spider-Man, Batman', type: 'text', icon: 'book-outline' },
  { key: 'issue', label: 'Issue Number', placeholder: 'e.g. #300, #1', type: 'text', icon: 'barcode-outline' },
  { key: 'year', label: 'Year', placeholder: 'e.g. 1988', type: 'text', icon: 'calendar-outline' },
  { key: 'variant', label: 'Variant', placeholder: 'e.g. Cover A, 1:25 Ratio', type: 'text', icon: 'layers-outline' },
  { key: 'grade', label: 'Grade', placeholder: 'e.g. CGC 9.8, Raw NM', type: 'text', icon: 'shield-checkmark-outline' },
  { key: 'key_issue', label: 'Key Issue', type: 'boolean', icon: 'star-outline' },
  { key: 'signed', label: 'Signed', type: 'boolean', icon: 'create-outline' },
];

const VINYL_RECORDS_FIELDS: CategoryField[] = [
  { key: 'artist', label: 'Artist', placeholder: 'e.g. Pink Floyd, Kendrick Lamar', type: 'text', icon: 'person-outline' },
  { key: 'album', label: 'Album', placeholder: 'e.g. Dark Side of the Moon', type: 'text', icon: 'disc-outline' },
  { key: 'label', label: 'Label', placeholder: 'e.g. Columbia, Def Jam', type: 'text', icon: 'business-outline' },
  { key: 'pressing', label: 'Pressing', type: 'select', icon: 'layers-outline', options: ['1st Pressing', '2nd Pressing', 'Repress', 'Reissue', 'Remaster'] },
  { key: 'color', label: 'Vinyl Color', placeholder: 'e.g. Black, Clear, Splatter', type: 'text', icon: 'color-palette-outline' },
  { key: 'rpm', label: 'RPM', type: 'select', icon: 'speedometer-outline', options: ['33', '45', '78'] },
  { key: 'color_vinyl', label: 'Color Vinyl', type: 'boolean', icon: 'color-palette-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['Mint', 'Near Mint', 'Very Good+', 'Very Good', 'Good', 'Fair'] },
];

// ---------------------------------------------------------------------------
// Lifestyle — Sneakers & Watches
// ---------------------------------------------------------------------------

const SNEAKERS_FIELDS: CategoryField[] = [
  { key: 'brand', label: 'Brand', type: 'select', icon: 'business-outline', options: ['Nike', 'Jordan', 'Adidas', 'New Balance', 'Asics', 'Puma', 'Reebok', 'Converse', 'Vans', 'Other'] },
  { key: 'model', label: 'Model', placeholder: 'e.g. Air Jordan 1, Dunk Low', type: 'text', icon: 'footsteps-outline' },
  { key: 'colorway', label: 'Colorway', placeholder: 'e.g. Chicago, Panda, Bred', type: 'text', icon: 'color-palette-outline' },
  { key: 'size', label: 'Size', placeholder: 'e.g. 10, 10.5', type: 'text', icon: 'resize-outline' },
  { key: 'size_system', label: 'Size System', type: 'select', icon: 'globe-outline', options: ['US', 'EU', 'UK'] },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['DS (Deadstock)', 'VNDS', 'Used - Excellent', 'Used - Good', 'Used - Fair', 'Beaters'] },
  { key: 'collaboration', label: 'Collaboration', placeholder: 'e.g. Travis Scott, Off-White', type: 'text', icon: 'people-outline' },
  { key: 'sku', label: 'SKU / Style Code', placeholder: 'e.g. DQ8583-100', type: 'text', icon: 'barcode-outline' },
  { key: 'year', label: 'Release Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
  { key: 'retail_price', label: 'Retail Price', placeholder: 'e.g. 170', type: 'text', icon: 'cash-outline' },
];

const WATCHES_FIELDS: CategoryField[] = [
  { key: 'brand', label: 'Brand', type: 'select', icon: 'business-outline', options: ['Rolex', 'Omega', 'Seiko', 'Tudor', 'Casio', 'G-Shock', 'Grand Seiko', 'TAG Heuer', 'Cartier', 'Patek Philippe', 'Audemars Piguet', 'Other'] },
  { key: 'model', label: 'Model', placeholder: 'e.g. Submariner, Speedmaster', type: 'text', icon: 'watch-outline' },
  { key: 'reference', label: 'Reference Number', placeholder: 'e.g. 126610LN', type: 'text', icon: 'barcode-outline' },
  { key: 'case_size', label: 'Case Diameter', type: 'select', icon: 'resize-outline', options: ['34mm', '36mm', '38mm', '39mm', '40mm', '41mm', '42mm', '43mm', '44mm', '45mm', '46mm'] },
  { key: 'movement', label: 'Movement', type: 'select', icon: 'cog-outline', options: ['Automatic', 'Manual', 'Quartz', 'Solar', 'Spring Drive', 'Eco-Drive'] },
  { key: 'material', label: 'Case Material', type: 'select', icon: 'diamond-outline', options: ['Stainless Steel', 'Gold', 'Rose Gold', 'Titanium', 'Ceramic', 'Carbon', 'Platinum', 'Two-Tone'] },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['BNIB', 'Excellent', 'Good', 'Fair', 'Serviced', 'Needs Service'] },
  { key: 'box_papers', label: 'Box & Papers', type: 'boolean', icon: 'documents-outline' },
  { key: 'year', label: 'Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
];

// ---------------------------------------------------------------------------
// Legacy
// ---------------------------------------------------------------------------

const DIECAST_FIELDS: CategoryField[] = [
  { key: 'brand', label: 'Brand', type: 'select', icon: 'car-outline', options: ['Hot Wheels', 'Matchbox', 'Johnny Lightning', 'Greenlight', 'Auto World', 'Other'] },
  { key: 'series', label: 'Series', placeholder: 'e.g. Treasure Hunt, Premium', type: 'text', icon: 'albums-outline' },
  { key: 'scale', label: 'Scale', type: 'select', icon: 'resize-outline', options: ['1:64', '1:43', '1:24', '1:18', 'Other'] },
  { key: 'year', label: 'Year', placeholder: 'e.g. 2024', type: 'text', icon: 'calendar-outline' },
  { key: 'card_condition', label: 'Card Condition', type: 'select', icon: 'shield-outline', options: ['Mint on Card', 'Near Mint', 'Good', 'Loose'] },
  { key: 'chase', label: 'Chase / TH / STH', type: 'boolean', icon: 'star-outline' },
];

const SPORTSCARDS_FIELDS: CategoryField[] = [
  { key: 'player', label: 'Player', placeholder: 'e.g. LeBron James', type: 'text', icon: 'person-outline' },
  { key: 'set', label: 'Set', placeholder: 'e.g. Topps Chrome, Panini Prizm', type: 'text', icon: 'albums-outline' },
  { key: 'year', label: 'Year', placeholder: 'e.g. 2023', type: 'text', icon: 'calendar-outline' },
  { key: 'grade', label: 'Grade', placeholder: 'e.g. PSA 10, BGS 9.5', type: 'text', icon: 'shield-checkmark-outline' },
  { key: 'variant', label: 'Variant', placeholder: 'e.g. Refractor, Numbered /25, Auto', type: 'text', icon: 'sparkles-outline' },
];

const RETRO_HANDHELDS_FIELDS: CategoryField[] = [
  { key: 'console_type', label: 'Console Type', type: 'select', icon: 'game-controller-outline', options: ['Game Boy', 'Game Boy Color', 'GBA', 'GBA SP', 'DS', 'DS Lite', 'PSP', 'PS Vita', 'Tamagotchi', 'Game & Watch', 'Other'] },
  { key: 'model', label: 'Model', placeholder: 'e.g. DMG-01, PSP-3000', type: 'text', icon: 'barcode-outline' },
  { key: 'colorway', label: 'Colorway', placeholder: 'e.g. Atomic Purple, Ice Blue', type: 'text', icon: 'color-palette-outline' },
  { key: 'year', label: 'Year', placeholder: 'e.g. 1998', type: 'text', icon: 'calendar-outline' },
  { key: 'boxed', label: 'Boxed / CIB', type: 'boolean', icon: 'cube-outline' },
  { key: 'working_condition', label: 'Working Condition', type: 'select', icon: 'checkmark-circle-outline', options: ['Fully Working', 'Partially Working', 'For Parts'] },
];

const PLUSH_COLLECTIBLES_FIELDS: CategoryField[] = [
  { key: 'brand', label: 'Brand', type: 'select', icon: 'heart-circle-outline', options: ['Squishmallow', 'Jellycat', 'Build-A-Bear', 'Sanrio', 'Pokemon Center', 'Other'] },
  { key: 'character', label: 'Character', placeholder: 'e.g. Ronnie the Cow', type: 'text', icon: 'person-outline' },
  { key: 'size', label: 'Size', type: 'select', icon: 'resize-outline', options: ['5"', '8"', '12"', '16"', '20"', '24"'] },
  { key: 'collection', label: 'Collection', placeholder: 'e.g. Halloween, Valentine\'s', type: 'text', icon: 'albums-outline' },
  { key: 'exclusive_retailer', label: 'Exclusive Retailer', placeholder: 'e.g. Target, Costco', type: 'text', icon: 'lock-closed-outline' },
  { key: 'has_tags', label: 'Has Tags', type: 'boolean', icon: 'pricetag-outline' },
];

// ---------------------------------------------------------------------------
// Board Games
// ---------------------------------------------------------------------------

const OOP_BOARD_GAMES_FIELDS: CategoryField[] = [
  { key: 'publisher', label: 'Publisher', placeholder: 'e.g. Fantasy Flight, CMON', type: 'text', icon: 'business-outline' },
  { key: 'designer', label: 'Designer', placeholder: 'e.g. Uwe Rosenberg', type: 'text', icon: 'person-outline' },
  { key: 'player_count', label: 'Player Count', placeholder: 'e.g. 2-4', type: 'text', icon: 'people-outline' },
  { key: 'play_time', label: 'Play Time', placeholder: 'e.g. 120min', type: 'text', icon: 'time-outline' },
  { key: 'edition', label: 'Edition', placeholder: 'e.g. Kickstarter, Retail, Deluxe', type: 'text', icon: 'layers-outline' },
  { key: 'bgg_rating', label: 'BGG Rating', placeholder: 'e.g. 8.2', type: 'text', icon: 'star-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['Sealed', 'Complete', 'Incomplete', 'Good', 'Fair'] },
  { key: 'year', label: 'Year', placeholder: 'e.g. 2019', type: 'text', icon: 'calendar-outline' },
];

// ---------------------------------------------------------------------------
// City Pop Vinyl
// ---------------------------------------------------------------------------

const CITY_POP_VINYL_FIELDS: CategoryField[] = [
  { key: 'artist', label: 'Artist', placeholder: 'e.g. Tatsuro Yamashita, Mariya Takeuchi', type: 'text', icon: 'person-outline' },
  { key: 'album', label: 'Album', placeholder: 'e.g. For You, Variety', type: 'text', icon: 'disc-outline' },
  { key: 'label', label: 'Label', placeholder: 'e.g. Air Records, Moon Records', type: 'text', icon: 'business-outline' },
  { key: 'pressing', label: 'Pressing', type: 'select', icon: 'layers-outline', options: ['OG', 'Reissue', 'Promo', 'Test Pressing', 'Remaster 180g', 'Picture Disc'] },
  { key: 'color', label: 'Vinyl Color', placeholder: 'e.g. Black, Clear, Red', type: 'text', icon: 'color-palette-outline' },
  { key: 'format', label: 'Format', type: 'select', icon: 'disc-outline', options: ['LP', '2xLP', '7"', '12"', 'CD'] },
  { key: 'year', label: 'Year', placeholder: 'e.g. 1982', type: 'text', icon: 'calendar-outline' },
  { key: 'condition', label: 'Condition', type: 'select', icon: 'shield-outline', options: ['M', 'NM', 'VG+', 'VG', 'G+', 'G'] },
  { key: 'obi', label: 'Has OBI Strip?', type: 'boolean', icon: 'bookmark-outline' },
];

// ---------------------------------------------------------------------------
// Niche Perfumery
// ---------------------------------------------------------------------------

const NICHE_PERFUMERY_FIELDS: CategoryField[] = [
  { key: 'house', label: 'House', placeholder: 'e.g. Creed, Tom Ford, Xerjoff', type: 'text', icon: 'business-outline' },
  { key: 'fragrance_name', label: 'Fragrance Name', placeholder: 'e.g. Aventus, Tobacco Vanille', type: 'text', icon: 'flask-outline' },
  { key: 'concentration', label: 'Concentration', type: 'select', icon: 'water-outline', options: ['EDT', 'EDP', 'Extrait', 'Parfum'] },
  { key: 'size_ml', label: 'Size (ml)', placeholder: 'e.g. 50, 100', type: 'text', icon: 'resize-outline' },
  { key: 'gender', label: 'Gender', type: 'select', icon: 'person-outline', options: ['Masculine', 'Feminine', 'Unisex'] },
  { key: 'fragrance_family', label: 'Fragrance Family', placeholder: 'e.g. Woody, Oriental, Fresh', type: 'text', icon: 'leaf-outline' },
  { key: 'fill_level', label: 'Fill Level', type: 'select', icon: 'battery-half-outline', options: ['Full', '90%', '75%', '50%', '25%', 'Empty'] },
  { key: 'batch_code', label: 'Batch Code', placeholder: 'e.g. A52B01', type: 'text', icon: 'barcode-outline' },
  { key: 'year', label: 'Year', placeholder: 'e.g. 2023', type: 'text', icon: 'calendar-outline' },
];

// ---------------------------------------------------------------------------
// Master lookup
// ---------------------------------------------------------------------------

export const CATEGORY_FIELDS: Partial<Record<Category, CategoryField[]>> = {
  // TCGs
  pokemon: POKEMON_FIELDS,
  mtg: MTG_FIELDS,
  yugioh: YUGIOH_FIELDS,
  lorcana: LORCANA_FIELDS,

  // Toys / Figures
  funko: FUNKO_FIELDS,
  designer_toys: DESIGNER_TOYS_FIELDS,
  anime_figures: ANIME_FIGURES_FIELDS,
  hot_toys: HOT_TOYS_FIELDS,
  action_figures: ACTION_FIGURES_FIELDS,
  vintage_toys: VINTAGE_TOYS_FIELDS,
  marvel_legends: MARVEL_LEGENDS_FIELDS,

  // Building / Models
  lego: LEGO_FIELDS,
  gunpla: GUNPLA_FIELDS,
  scale_models: SCALE_MODELS_FIELDS,
  warhammer: WARHAMMER_FIELDS,

  // Gaming
  retro_games: RETRO_GAMES_FIELDS,

  // Media
  manga: MANGA_FIELDS,
  bluray_steelbook: BLURAY_STEELBOOK_FIELDS,
  anime_bluray: ANIME_BLURAY_FIELDS,
  anime_soundtrack: ANIME_SOUNDTRACK_FIELDS,
  anime_ost_vinyl: ANIME_OST_VINYL_FIELDS,

  // Music / Fandom
  kpop_merch: KPOP_MERCH_FIELDS,
  taylor_swift: TAYLOR_SWIFT_FIELDS,
  pop_fandom: POP_FANDOM_FIELDS,
  kpop_lightsticks: KPOP_LIGHTSTICKS_FIELDS,

  // Disney / Theme Parks
  disney: DISNEY_FIELDS,
  theme_park: THEME_PARK_FIELDS,
  ghibli: GHIBLI_FIELDS,

  // Japan Exclusives
  bandai_premium: BANDAI_PREMIUM_FIELDS,
  jp_magazine: JP_MAGAZINE_FIELDS,
  jp_event: JP_EVENT_FIELDS,

  // Nintendo / Pokemon Merch
  nintendo_merch: NINTENDO_MERCH_FIELDS,
  retro_pokemon: RETRO_POKEMON_FIELDS,

  // IP-Specific
  one_piece: ONE_PIECE_FIELDS,
  vtuber: VTUBER_FIELDS,

  // Niche
  keycaps: KEYCAPS_FIELDS,
  loungefly: LOUNGEFLY_FIELDS,

  // Lifestyle
  sneakers: SNEAKERS_FIELDS,
  watches: WATCHES_FIELDS,

  // Legacy
  diecast: DIECAST_FIELDS,
  sportscards: SPORTSCARDS_FIELDS,
  retro_handhelds: RETRO_HANDHELDS_FIELDS,

  // Collectibles
  blind_box: BLIND_BOX_FIELDS,
  plush_collectibles: PLUSH_COLLECTIBLES_FIELDS,

  // Spirits & Luxury
  whiskey: WHISKEY_FIELDS,
  vintage_cameras: VINTAGE_CAMERAS_FIELDS,
  pens: PENS_FIELDS,

  // Additional TCGs
  digimon: DIGIMON_FIELDS,
  one_piece_tcg: ONE_PIECE_TCG_FIELDS,

  // Media — Expansion
  comic_books: COMIC_BOOKS_FIELDS,
  vinyl_records: VINYL_RECORDS_FIELDS,

  // New Categories
  oop_board_games: OOP_BOARD_GAMES_FIELDS,
  city_pop_vinyl: CITY_POP_VINYL_FIELDS,
  niche_perfumery: NICHE_PERFUMERY_FIELDS,
};

/**
 * Get form fields for a specific category.
 * Returns empty array for unknown categories.
 */
export function getCategoryFields(categorySlug: string): CategoryField[] {
  return CATEGORY_FIELDS[categorySlug as Category] ?? [];
}
