/**
 * Category-specific build step templates.
 * Used for auto-suggesting steps when creating/viewing build & paint projects.
 */

export type BuildStepTemplate = {
  id: string;
  displayName: string;
  steps: { id: string; label: string; order: number }[];
};

/**
 * Category-specific project status pipeline.
 * Each status has an id (stored in DB), label (displayed), order, and color hint.
 * The pipeline represents the real-world workflow for each buildable category.
 */
export type ProjectStatusDef = {
  id: string;
  label: string;
  order: number;
  colorHint: 'muted' | 'info' | 'warning' | 'accent' | 'success';
};

/** Category-specific status pipelines */
export const PROJECT_STATUS_PIPELINES: Record<string, ProjectStatusDef[]> = {
  warhammer: [
    { id: 'wishlist', label: 'Wishlist', order: 0, colorHint: 'muted' },
    { id: 'purchased', label: 'Purchased', order: 1, colorHint: 'info' },
    { id: 'unassembled', label: 'Unassembled', order: 2, colorHint: 'info' },
    { id: 'assembled', label: 'Assembled', order: 3, colorHint: 'warning' },
    { id: 'primed', label: 'Primed', order: 4, colorHint: 'warning' },
    { id: 'battle_ready', label: 'Battle Ready', order: 5, colorHint: 'accent' },
    { id: 'parade_ready', label: 'Parade Ready', order: 6, colorHint: 'accent' },
    { id: 'finished', label: 'Finished', order: 7, colorHint: 'success' },
  ],
  scale_models: [
    { id: 'wishlist', label: 'Wishlist', order: 0, colorHint: 'muted' },
    { id: 'purchased', label: 'Purchased', order: 1, colorHint: 'info' },
    { id: 'unassembled', label: 'Unassembled', order: 2, colorHint: 'info' },
    { id: 'assembled', label: 'Assembled', order: 3, colorHint: 'warning' },
    { id: 'primed', label: 'Primed', order: 4, colorHint: 'warning' },
    { id: 'painted', label: 'Painted', order: 5, colorHint: 'accent' },
    { id: 'weathered', label: 'Weathered', order: 6, colorHint: 'accent' },
    { id: 'decaled', label: 'Decaled', order: 7, colorHint: 'accent' },
    { id: 'finished', label: 'Finished', order: 8, colorHint: 'success' },
  ],
  gunpla: [
    { id: 'wishlist', label: 'Wishlist', order: 0, colorHint: 'muted' },
    { id: 'purchased', label: 'Purchased', order: 1, colorHint: 'info' },
    { id: 'unassembled', label: 'On Sprue', order: 2, colorHint: 'info' },
    { id: 'assembled', label: 'Snap Built', order: 3, colorHint: 'warning' },
    { id: 'primed', label: 'Primed', order: 4, colorHint: 'warning' },
    { id: 'painted', label: 'Painted', order: 5, colorHint: 'accent' },
    { id: 'decaled', label: 'Decaled', order: 6, colorHint: 'accent' },
    { id: 'top_coated', label: 'Top Coated', order: 7, colorHint: 'accent' },
    { id: 'finished', label: 'Finished', order: 8, colorHint: 'success' },
  ],
  lego: [
    { id: 'wishlist', label: 'Wishlist', order: 0, colorHint: 'muted' },
    { id: 'purchased', label: 'Purchased', order: 1, colorHint: 'info' },
    { id: 'sealed', label: 'Sealed (Investment)', order: 2, colorHint: 'info' },
    { id: 'in_progress', label: 'Building', order: 3, colorHint: 'warning' },
    { id: 'built', label: 'Built', order: 4, colorHint: 'accent' },
    { id: 'modified', label: 'Modified / MOC', order: 5, colorHint: 'accent' },
    { id: 'displayed', label: 'Displayed', order: 6, colorHint: 'success' },
  ],
  keycaps: [
    { id: 'wishlist', label: 'Wishlist', order: 0, colorHint: 'muted' },
    { id: 'purchased', label: 'Parts Ordered', order: 1, colorHint: 'info' },
    { id: 'parts_received', label: 'Parts Received', order: 2, colorHint: 'info' },
    { id: 'lubing', label: 'Lubing & Modding', order: 3, colorHint: 'warning' },
    { id: 'assembled', label: 'Assembled', order: 4, colorHint: 'accent' },
    { id: 'tuned', label: 'Tuned & Sound Tested', order: 5, colorHint: 'accent' },
    { id: 'finished', label: 'Finished', order: 6, colorHint: 'success' },
  ],
  designer_toys: [
    { id: 'wishlist', label: 'Wishlist', order: 0, colorHint: 'muted' },
    { id: 'purchased', label: 'Purchased', order: 1, colorHint: 'info' },
    { id: 'unboxed', label: 'Unboxed', order: 2, colorHint: 'info' },
    { id: 'customizing', label: 'Customizing', order: 3, colorHint: 'warning' },
    { id: 'painted', label: 'Painted', order: 4, colorHint: 'accent' },
    { id: 'sealed', label: 'Sealed & Protected', order: 5, colorHint: 'accent' },
    { id: 'displayed', label: 'Displayed', order: 6, colorHint: 'success' },
  ],
  diecast: [
    { id: 'wishlist', label: 'Wishlist', order: 0, colorHint: 'muted' },
    { id: 'purchased', label: 'Purchased', order: 1, colorHint: 'info' },
    { id: 'stock', label: 'Stock / Unmodified', order: 2, colorHint: 'info' },
    { id: 'disassembled', label: 'Disassembled', order: 3, colorHint: 'warning' },
    { id: 'painted', label: 'Repainted', order: 4, colorHint: 'accent' },
    { id: 'detailed', label: 'Detailed & Weathered', order: 5, colorHint: 'accent' },
    { id: 'finished', label: 'Finished', order: 6, colorHint: 'success' },
  ],
  generic: [
    { id: 'wishlist', label: 'Wishlist', order: 0, colorHint: 'muted' },
    { id: 'purchased', label: 'Purchased', order: 1, colorHint: 'info' },
    { id: 'in_progress', label: 'In Progress', order: 2, colorHint: 'warning' },
    { id: 'finished', label: 'Finished', order: 3, colorHint: 'success' },
  ],
};

/** Get the status pipeline for a category, falling back to generic */
export function getStatusPipeline(categoryId: string | null | undefined): ProjectStatusDef[] {
  if (!categoryId) return PROJECT_STATUS_PIPELINES.generic;
  return PROJECT_STATUS_PIPELINES[categoryId] ?? PROJECT_STATUS_PIPELINES.generic;
}

/** Get a status definition by id within a category pipeline */
export function getStatusDef(categoryId: string | null | undefined, statusId: string): ProjectStatusDef | undefined {
  const pipeline = getStatusPipeline(categoryId);
  return pipeline.find((s) => s.id === statusId);
}

/** Check if a status is a terminal/finished state */
export function isFinishedStatus(categoryId: string | null | undefined, statusId: string): boolean {
  const pipeline = getStatusPipeline(categoryId);
  const last = pipeline[pipeline.length - 1];
  return last?.id === statusId;
}

/** Compute percent complete based on status position in pipeline */
export function statusToPercent(categoryId: string | null | undefined, statusId: string): number {
  const pipeline = getStatusPipeline(categoryId);
  const idx = pipeline.findIndex((s) => s.id === statusId);
  if (idx < 0) return 0;
  if (idx === pipeline.length - 1) return 100;
  return Math.round((idx / (pipeline.length - 1)) * 100);
}

/** Categories that support build/paint projects */
export const BUILDABLE_CATEGORIES = [
  'warhammer',
  'gunpla',
  'scale_models',
  'lego',
  'keycaps',
  'designer_toys',
  'diecast',
] as const;

export type BuildableCategoryId = (typeof BUILDABLE_CATEGORIES)[number];

export function isBuildableCategory(categoryId: string | null | undefined): boolean {
  if (!categoryId) return false;
  return (BUILDABLE_CATEGORIES as readonly string[]).includes(categoryId);
}

/** Map from category ID to step template */
export const BUILD_STEP_TEMPLATES: Record<string, BuildStepTemplate> = {
  warhammer: {
    id: 'warhammer',
    displayName: 'Warhammer Miniatures',
    steps: [
      { id: 'wh-1', label: 'Unbox & inspect sprues', order: 1 },
      { id: 'wh-2', label: 'Clean mold lines & flash', order: 2 },
      { id: 'wh-3', label: 'Dry-fit & plan assembly', order: 3 },
      { id: 'wh-4', label: 'Assemble / sub-assemblies', order: 4 },
      { id: 'wh-5', label: 'Prime (zenithal or flat)', order: 5 },
      { id: 'wh-6', label: 'Base colors', order: 6 },
      { id: 'wh-7', label: 'Washes & shading', order: 7 },
      { id: 'wh-8', label: 'Layer highlights', order: 8 },
      { id: 'wh-9', label: 'Details (eyes, gems, metallics)', order: 9 },
      { id: 'wh-10', label: 'Basing', order: 10 },
      { id: 'wh-11', label: 'Varnish & seal', order: 11 },
      { id: 'wh-12', label: 'Photography & display', order: 12 },
    ],
  },
  gunpla: {
    id: 'gunpla',
    displayName: 'Gunpla / Model Kits',
    steps: [
      { id: 'gp-1', label: 'Unbox & organize runners', order: 1 },
      { id: 'gp-2', label: 'Nub removal & cleanup', order: 2 },
      { id: 'gp-3', label: 'Test fit / dry assembly', order: 3 },
      { id: 'gp-4', label: 'Panel line scribing (optional)', order: 4 },
      { id: 'gp-5', label: 'Surface prep & sanding', order: 5 },
      { id: 'gp-6', label: 'Primer coat', order: 6 },
      { id: 'gp-7', label: 'Base paint / color separation', order: 7 },
      { id: 'gp-8', label: 'Detail painting', order: 8 },
      { id: 'gp-9', label: 'Decals / waterslide', order: 9 },
      { id: 'gp-10', label: 'Panel lining', order: 10 },
      { id: 'gp-11', label: 'Top coat / clear coat', order: 11 },
      { id: 'gp-12', label: 'Final assembly & posing', order: 12 },
    ],
  },
  lego: {
    id: 'lego',
    displayName: 'LEGO',
    steps: [
      { id: 'lg-1', label: 'Unbox & verify all numbered bags', order: 1 },
      { id: 'lg-2', label: 'Sort pieces by bag number', order: 2 },
      { id: 'lg-3', label: 'Minifigure assembly', order: 3 },
      { id: 'lg-4', label: 'Build booklet 1 (base structure)', order: 4 },
      { id: 'lg-5', label: 'Build booklet 2 (mid sections)', order: 5 },
      { id: 'lg-6', label: 'Build booklet 3+ (upper / details)', order: 6 },
      { id: 'lg-7', label: 'Sticker / printed tile application', order: 7 },
      { id: 'lg-8', label: 'Technic functions test (if applicable)', order: 8 },
      { id: 'lg-9', label: 'Light kit installation (optional)', order: 9 },
      { id: 'lg-10', label: 'Missing pieces check & order', order: 10 },
      { id: 'lg-11', label: 'Final inspection & tightening', order: 11 },
      { id: 'lg-12', label: 'Display setup & photography', order: 12 },
    ],
  },
  scale_models: {
    id: 'scale_models',
    displayName: 'Scale Models',
    steps: [
      { id: 'sm-1', label: 'Research & reference gathering', order: 1 },
      { id: 'sm-2', label: 'Dry fit & test assembly', order: 2 },
      { id: 'sm-3', label: 'Cockpit / interior detail', order: 3 },
      { id: 'sm-4', label: 'Main assembly', order: 4 },
      { id: 'sm-5', label: 'Filling & sanding seams', order: 5 },
      { id: 'sm-6', label: 'Primer coat', order: 6 },
      { id: 'sm-7', label: 'Pre-shading', order: 7 },
      { id: 'sm-8', label: 'Base camouflage / color', order: 8 },
      { id: 'sm-9', label: 'Decals & markings', order: 9 },
      { id: 'sm-10', label: 'Weathering (washes, chipping, streaking)', order: 10 },
      { id: 'sm-11', label: 'Clear coat', order: 11 },
      { id: 'sm-12', label: 'Final details (antenna, lights, rigging)', order: 12 },
    ],
  },
  keycaps: {
    id: 'keycaps',
    displayName: 'Custom Keyboards / Keycaps',
    steps: [
      { id: 'kc-1', label: 'Layout planning & parts inventory', order: 1 },
      { id: 'kc-2', label: 'PCB & plate assembly', order: 2 },
      { id: 'kc-3', label: 'Stabilizer tuning & lubing', order: 3 },
      { id: 'kc-4', label: 'Switch lubing & filming', order: 4 },
      { id: 'kc-5', label: 'Switch installation', order: 5 },
      { id: 'kc-6', label: 'Foam & dampening installation', order: 6 },
      { id: 'kc-7', label: 'Keycap mounting & alignment', order: 7 },
      { id: 'kc-8', label: 'Sound testing & final tuning', order: 8 },
    ],
  },
  designer_toys: {
    id: 'designer_toys',
    displayName: 'Designer Toys',
    steps: [
      { id: 'dt-1', label: 'Unboxing & inspection', order: 1 },
      { id: 'dt-2', label: 'Surface cleaning & prep', order: 2 },
      { id: 'dt-3', label: 'Custom paint planning & masking', order: 3 },
      { id: 'dt-4', label: 'Base coat application', order: 4 },
      { id: 'dt-5', label: 'Detail painting & accents', order: 5 },
      { id: 'dt-6', label: 'Dry brushing & weathering (optional)', order: 6 },
      { id: 'dt-7', label: 'Sealing & clear coat', order: 7 },
      { id: 'dt-8', label: 'Display setup & photography', order: 8 },
    ],
  },
  diecast: {
    id: 'diecast',
    displayName: 'Diecast Models',
    steps: [
      { id: 'dc-1', label: 'Inspection & reference gathering', order: 1 },
      { id: 'dc-2', label: 'Disassembly (body, chassis, interior)', order: 2 },
      { id: 'dc-3', label: 'Stripping factory paint (if repainting)', order: 3 },
      { id: 'dc-4', label: 'Custom paint & color coats', order: 4 },
      { id: 'dc-5', label: 'Detailing & weathering', order: 5 },
      { id: 'dc-6', label: 'Decal & tampo application', order: 6 },
      { id: 'dc-7', label: 'Reassembly & final fit', order: 7 },
      { id: 'dc-8', label: 'Display case setup & photography', order: 8 },
    ],
  },
  generic: {
    id: 'generic',
    displayName: 'Generic / Other',
    steps: [
      { id: 'gen-1', label: 'Preparation & planning', order: 1 },
      { id: 'gen-2', label: 'Assembly', order: 2 },
      { id: 'gen-3', label: 'Surface prep', order: 3 },
      { id: 'gen-4', label: 'Priming', order: 4 },
      { id: 'gen-5', label: 'Base coating', order: 5 },
      { id: 'gen-6', label: 'Detailing', order: 6 },
      { id: 'gen-7', label: 'Finishing & sealing', order: 7 },
    ],
  },
};

/** Get the step template for a category, falling back to generic */
export function getStepTemplateForCategory(categoryId: string | null | undefined): BuildStepTemplate {
  if (!categoryId) return BUILD_STEP_TEMPLATES.generic;
  return BUILD_STEP_TEMPLATES[categoryId] ?? BUILD_STEP_TEMPLATES.generic;
}
