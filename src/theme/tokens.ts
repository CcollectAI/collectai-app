export const colors = {
  bg: '#FFFFFF',
  surface: '#FFFFFF',
  text: '#0F172A',
  subtext: '#475569',
  border: '#E2E8F0',
  accent: '#81E6D9',       // Tiffany-ish light
  accentStrong: '#14B8A6', // teal-500
  muted: '#F8FAFC',
  positive: '#16A34A',
  negative: '#DC2626',
  warning: '#F59E0B',
  shadow: '#000000',
};

export const radius = { sm:10, md:14, lg:20, xl:28 };
export const spacing = (n:number)=> n*8;
export const shadow = {
  card: { shadowColor: colors.shadow as any, shadowOpacity: 0.08, shadowRadius: 10, elevation: 5 },
};
export const fonts = {
  title: { fontSize: 20, fontWeight: '700', color: colors.text },
  h1: { fontSize: 28, fontWeight: '800', color: colors.text },
  h2: { fontSize: 22, fontWeight: '700', color: colors.text },
  body: { fontSize: 16, color: colors.text },
  small: { fontSize: 13, color: colors.subtext },
};
