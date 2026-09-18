import { partialCount } from '../../src/lib/partialCount';

describe('partialCount', () => {
  it('marks a count that has more pages behind it', () => {
    expect(partialCount(24, true)).toBe('24+');
  });

  it('leaves a complete count alone', () => {
    expect(partialCount(24, false)).toBe('24');
  });

  it('marks zero too — "0+" is honest when nothing on THIS page matched', () => {
    // A filter that matched nothing in the loaded pages is not proof the
    // result set is empty.
    expect(partialCount(0, true)).toBe('0+');
  });
});
