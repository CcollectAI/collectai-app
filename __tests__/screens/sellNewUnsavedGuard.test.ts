import { readFileSync } from 'fs';
import { join } from 'path';

/** Back discarded a half-filled listing without asking (walked 2026-10-15).
 *  The guard must exist, and a successful List must bypass it BEFORE leaving,
 *  or the member is asked to "discard" what they just listed. */
describe('sell/new — unsaved changes', () => {
  const src = readFileSync(join(__dirname, '../../app/sell/new.tsx'), 'utf8');
  it('guards Back with useUnsavedChanges', () => {
    expect(src).toMatch(/useUnsavedChanges\(\{ isDirty, bypassRef: leavingAfterSave \}\)/);
  });
  it('sets the bypass before navigating to the new listing', () => {
    const i = src.indexOf('leavingAfterSave.current = true;');
    const j = src.indexOf("router.replace({ pathname: '/listing/[id]'");
    expect(i).toBeGreaterThan(-1);
    expect(i).toBeLessThan(j);
  });
});
