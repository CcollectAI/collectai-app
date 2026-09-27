/** A typed, not-yet-added event detail counts (device walk 2026-09-27: Create stayed disabled). */
jest.mock('@/lib/supabase', () => ({ supabase: {} }));
import { joinDescriptionDetail } from '@/hooks/useEventForm';

it('uses the typed detail when nothing was added', () => {
  expect(joinDescriptionDetail('', '  Walk test event ')).toBe('Walk test event');
});
it('appends it to the added details as a new line', () => {
  expect(joinDescriptionDetail('Doors 10:00', 'Bring cards')).toBe('Doors 10:00\nBring cards');
});
it('leaves the description alone when nothing is typed', () => {
  expect(joinDescriptionDetail('Doors 10:00', '   ')).toBe('Doors 10:00');
});
