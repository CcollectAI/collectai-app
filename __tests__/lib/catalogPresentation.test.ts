import { cleanCatalogItem, cleanCatalogTitle } from '@/lib/catalogPresentation';

describe('cleanCatalogItem', () => {
  it('cleans the .hack PS2 example (the reported card)', () => {
    const r = cleanCatalogItem({
      title: '.hack//G.U. Vol 3 Redemption CIB (PS2)',
      brand: 'PS2',
      setCode: 'ps2',
      rarity: 'Common',
    });
    expect(r.title).toBe('.hack//G.U. Vol 3 Redemption');
    expect(r.tags).toEqual(['PS2', 'Complete in Box']);
    expect(r.platform).toBe('PS2');
    expect(r.brand).toBeNull();   // platform, not a brand
    expect(r.setCode).toBeNull(); // duplicate platform
    expect(r.rarity).toBeNull();  // "Common" is low-signal
  });

  it('NEVER strips real-title words that look like conditions', () => {
    const r = cleanCatalogItem({ title: 'New Super Mario Bros (DS)', brand: 'DS' });
    expect(r.title).toBe('New Super Mario Bros'); // "New" preserved
    expect(r.platform).toBe('Nintendo DS');
    expect(r.tags).toEqual(['Nintendo DS']);
  });

  it('leaves TCG cards untouched (brand is a real brand, rarity meaningful)', () => {
    const r = cleanCatalogItem({
      title: 'Charizard',
      brand: 'Pokemon',
      setCode: 'Base Set',
      rarity: 'Rare Holo',
    });
    expect(r.title).toBe('Charizard');
    expect(r.platform).toBeNull();
    expect(r.brand).toBe('Pokemon');
    expect(r.setCode).toBe('Base Set');
    expect(r.rarity).toBe('Rare Holo');
    expect(r.tags).toEqual(['Rare Holo', 'Base Set', 'Pokemon']);
  });

  it('keeps "Common" for TCG (real rarity) but drops it for video games', () => {
    // TCG: no platform → Common is a legitimate rarity tier, kept.
    const card = cleanCatalogItem({ title: 'Pidgey', brand: 'Pokemon', setCode: 'Base Set', rarity: 'Common' });
    expect(card.rarity).toBe('Common');
    expect(card.tags).toContain('Common');
    // Video game: platform resolved → Common is filler, dropped.
    const game = cleanCatalogItem({ title: 'Some Game', brand: 'PS2', rarity: 'Common' });
    expect(game.rarity).toBeNull();
    expect(game.tags).toEqual(['PS2']);
  });

  it('dedupes platform tags across case (ps2 + PS2 -> one PS2)', () => {
    const r = cleanCatalogItem({ title: 'Gran Turismo 4', brand: 'PS2', setCode: 'ps2' });
    expect(r.tags).toEqual(['PS2']);
  });

  it('strips a redundant trailing platform even without brand/set fields', () => {
    expect(cleanCatalogTitle('Final Fantasy VII (PS1)')).toBe('Final Fantasy VII');
  });

  it('leaves a clean title and non-platform parenthetical alone', () => {
    expect(cleanCatalogTitle('Sonic the Hedgehog (Not for Resale)')).toBe(
      'Sonic the Hedgehog (Not for Resale)',
    );
    expect(cleanCatalogTitle('Metroid Prime')).toBe('Metroid Prime');
  });
});
