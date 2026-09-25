/**
 * Set completion reads items.attrs->>'set_name'; the manual-add form saved the
 * category Set field as `set` and dropped "Set / Series" (2026-09-25).
 */
import { setAttrs } from '@/lib/itemSetAttrs';

describe('setAttrs', () => {
  it('the category Set field reaches set_name', () => {
    expect(setAttrs({ set: 'Vivid Voltage' }, '')).toMatchObject({ set_name: 'Vivid Voltage' });
  });
  it('the generic Set / Series field reaches set_name when nothing else did', () => {
    expect(setAttrs({}, ' Scarlet & Violet ')).toEqual({ set_name: 'Scarlet & Violet' });
  });
  it('the category field wins over the generic one', () => {
    expect(setAttrs({ set: 'Base Set' }, 'Other').set_name).toBe('Base Set');
  });
  it('a Series-shaped category keeps its series and gets no invented set_name', () => {
    expect(setAttrs({ series: 'Molly' }, 'Molly')).toEqual({ series: 'Molly' });
  });
  it('nothing typed, nothing written', () => {
    expect(setAttrs({}, '')).toEqual({});
  });
});
