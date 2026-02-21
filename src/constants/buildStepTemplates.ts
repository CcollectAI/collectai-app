/**
 * Category-specific build step templates.
 * Used for auto-suggesting steps when creating/viewing build & paint projects.
 */

export type BuildStepTemplate = {
  id: string;
  displayName: string;
  steps: { id: string; label: string; order: number }[];
};

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
      { id: 'lg-1', label: 'Sort pieces by bag/color', order: 1 },
      { id: 'lg-2', label: 'Build phase 1 (base/frame)', order: 2 },
      { id: 'lg-3', label: 'Build phase 2 (details)', order: 3 },
      { id: 'lg-4', label: 'Build phase 3 (finishing)', order: 4 },
      { id: 'lg-5', label: 'Sticker/decal application', order: 5 },
      { id: 'lg-6', label: 'Minifigure assembly', order: 6 },
      { id: 'lg-7', label: 'Final inspection', order: 7 },
      { id: 'lg-8', label: 'Display setup', order: 8 },
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
