/** price_band.sources_disagree reaches the scan card (#12) — a dropped field is class V. */
const mockIntake = jest.fn();
jest.mock('@/lib/supabase', () => ({ supabase: {} }));
jest.mock('@/api/collectorsApi', () => ({ collectorsApi: { intakeImageOnly: (...a: unknown[]) => mockIntake(...a) } }));
import { quickscanSingle } from '@/data/providers/itemsProvider';

const intake = (sources_disagree?: boolean) => ({
  name: 'Charizard', category_id: 'pokemon', attributes: {}, alternatives: [],
  estimated_price: 825.41,
  price_band: { q10: 825.41, q50: 825.41, q90: 1531, confidence: 0.9, currency: 'EUR', ...(sources_disagree === undefined ? {} : { sources_disagree }) },
});

it('carries sources_disagree into the prediction', async () => {
  mockIntake.mockResolvedValue(intake(true));
  const r = await quickscanSingle('file:///x.jpg');
  expect(r.prediction.sourcesDisagree).toBe(true);
  expect([r.prediction.estimatedLow, r.prediction.estimatedHigh]).toEqual([825.41, 1531]);
});

it('absent or false means agreeing sources', async () => {
  mockIntake.mockResolvedValue(intake());
  expect((await quickscanSingle('file:///x.jpg')).prediction.sourcesDisagree).toBe(false);
});
