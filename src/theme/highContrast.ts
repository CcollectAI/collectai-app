/**
 * High Contrast Theme
 * WCAG 2.1 AA compliant colors for improved accessibility.
 * Contrast ratios: text on background >= 4.5:1, large text >= 3:1
 *
 * NOTE: These are standalone color palettes intended for future high-contrast
 * mode. They mirror the shape of LIGHT_COLORS / DARK_COLORS in useAppTheme.ts
 * but with boosted contrast ratios.
 */

/**
 * High contrast light palette
 * Dark navy text on off-white backgrounds
 */
export const highContrastLight = {
  background: '#FAFAFA',
  card: '#FFFFFF',
  border: '#1A1A1A',
  text: '#0D0D0D',
  muted: '#404040',
  mutedText: '#404040',
  accent: '#0052CC',
  accentText: '#FFFFFF',
  brand: {
    base: '#0052CC',
    dark: '#003D99',
    darker: '#002966',
    light: '#4DA6FF',
    lighter: '#E6F0FF',
  },
  tileScale: ['#E6F0FF', '#4DA6FF', '#0052CC', '#003D99'],
  quickscanBackdrop: '#F0F0F0',
  success: '#006600',
  warning: '#CC6600',
  danger: '#CC0000',
  error: '#CC0000',
  info: '#0052CC',
  skeleton: '#D0D0D0',
  skeletonCard: '#FFFFFF',
  overlay: 'rgba(0,0,0,0.7)',
  offlineBanner: '#CC6600',
  offlineBannerText: '#FFFFFF',
  chartLine: '#0052CC',
  chartFill: '#E6F0FF',
  chartDot: '#003D99',
  toastSuccess: '#003300',
  toastError: '#660000',
  toastWarning: '#663300',
  toastInfo: '#002266',
  successBg: '#CCFFCC',
  warningBg: '#FFF0CC',
  dangerBg: '#FFCCCC',
  infoBg: '#CCE0FF',
  tier: {
    bronze: '#8B5E3C',
    silver: '#808080',
    gold: '#CC9900',
    platinum: '#A0A0A0',
  },
  primary: '#0052CC',
  inputBackground: '#FFFFFF',
  inputBorder: '#1A1A1A',
} as const;

/**
 * High contrast dark palette
 * Light text on deep black backgrounds
 */
export const highContrastDark = {
  background: '#000000',
  card: '#0D0D0D',
  border: '#FFFFFF',
  text: '#FFFFFF',
  muted: '#E0E0E0',
  mutedText: '#E0E0E0',
  accent: '#4DA6FF',
  accentText: '#000000',
  brand: {
    base: '#4DA6FF',
    dark: '#80BFFF',
    darker: '#FFFFFF',
    light: '#003D99',
    lighter: '#001A40',
  },
  tileScale: ['#001A40', '#003D99', '#4DA6FF', '#80BFFF'],
  quickscanBackdrop: '#0D0D0D',
  success: '#00CC00',
  warning: '#FFCC00',
  danger: '#FF4444',
  error: '#FF4444',
  info: '#4DA6FF',
  skeleton: '#333333',
  skeletonCard: '#0D0D0D',
  overlay: 'rgba(0,0,0,0.85)',
  offlineBanner: '#CC6600',
  offlineBannerText: '#FFFFFF',
  chartLine: '#4DA6FF',
  chartFill: '#001A40',
  chartDot: '#80BFFF',
  toastSuccess: '#003300',
  toastError: '#660000',
  toastWarning: '#663300',
  toastInfo: '#002266',
  successBg: '#003300',
  warningBg: '#332200',
  dangerBg: '#330000',
  infoBg: '#001A40',
  tier: {
    bronze: '#CD7F32',
    silver: '#C0C0C0',
    gold: '#FFD700',
    platinum: '#E5E4E2',
  },
  primary: '#4DA6FF',
  inputBackground: '#0D0D0D',
  inputBorder: '#FFFFFF',
} as const;
