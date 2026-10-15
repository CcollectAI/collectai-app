import { readFileSync } from 'fs';
import { join } from 'path';

/**
 * The item screen's `confidence` param is a PERCENT (2026-10-14).
 *
 * quickscan sent a percent, barcode-scan a fraction; the item screen multiplied
 * by 100 (fraction) while its save divided by 100 (percent). A 0%-identified
 * scan showed "High Confidence". One unit, pinned at every sender and reader.
 */
const read = (p: string) => readFileSync(join(__dirname, '../../', p), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');

describe('item screen confidence param — one unit', () => {
  it('the item screen does not scale it again', () => {
    expect(read('app/item/[id].tsx')).not.toMatch(/parseFloat\(confidence\)\s*\*\s*100/);
  });
  it('quickscan sends a percent', () => {
    expect(read('app/quickscan.tsx')).toMatch(/confidence: String\(Math\.round\(scanResult\.prediction\.confidence \* 100\)\)/);
  });
  it('barcode-scan sends a percent', () => {
    expect(read('app/barcode-scan.tsx')).toMatch(/String\(Math\.round\(lookupResult\.priceBand\.confidence \* 100\)\)/);
  });
  it('the save treats it as a percent', () => {
    expect(read('src/hooks/useItemDetail.ts')).toMatch(/num\(confidence\)! \/ 100/);
  });
});
