/**
 * Switching a project's Complete off failed every time (device walk,
 * 2026-09-26): it wrote progress_pct NULL into a NOT NULL column. Reopening
 * now writes the steps' percent.
 */
const mockUpdate = jest.fn();
jest.mock('@/lib/supabase', () => ({
  supabase: {
    from: () => ({
      update: (patch: Record<string, unknown>) => {
        mockUpdate(patch);
        return { eq: async () => ({ error: null }) };
      },
    }),
  },
}));
import { markBuildPaintProjectComplete } from '@/data/providers/buildPaintProvider';

beforeEach(() => mockUpdate.mockClear());

it('reopening writes a number, never NULL (the column is NOT NULL)', async () => {
  await markBuildPaintProjectComplete('p1', false, 25);
  expect(mockUpdate.mock.calls[0][0]).toMatchObject({ status: 'in_progress', progress_pct: 25 });
  await markBuildPaintProjectComplete('p1', false);
  expect(mockUpdate.mock.calls[1][0].progress_pct).toBe(0);
});

it('completing writes 100', async () => {
  await markBuildPaintProjectComplete('p1', true, 25);
  expect(mockUpdate.mock.calls[0][0]).toMatchObject({ status: 'finished', progress_pct: 100 });
});
