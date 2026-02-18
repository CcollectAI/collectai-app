/**
 * Taxonomy Mapper Tests
 *
 * Tests edge cases for category/subtype mapping:
 * - Warhammer books vs miniatures (ISBN + keywords)
 * - Taylor Swift items across categories
 * - BTS K-pop photocards vs albums
 */

import { mapToTaxonomy, detectCollections, isLikelyWarhammerBook } from '../map';

describe('Taxonomy Mapper', () => {
  describe('Warhammer disambiguation', () => {
    it('should classify item with ISBN as warhammer_books', () => {
      const result = mapToTaxonomy({
        title: 'Warhammer 40k Space Marine Codex 9th Edition',
        isbn: '9781788269612',
      });

      expect(result.categoryId).toBe('warhammer');
      expect(result.subtypeId).toBe('warhammer_books');
      expect(result.confidence).toBeGreaterThanOrEqual(0.9);
      expect(result.rationale).toContain('ISBN');
    });

    it('should classify codex/rulebook keywords as warhammer_books', () => {
      const result = mapToTaxonomy({
        title: 'Age of Sigmar Core Rulebook 3rd Edition',
      });

      expect(result.categoryId).toBe('warhammer');
      expect(result.subtypeId).toBe('warhammer_books');
      expect(result.rationale).toContain('BOOKS');
    });

    it('should classify Black Library novel as warhammer_books', () => {
      const result = mapToTaxonomy({
        title: 'Black Library Horus Heresy Novel',
      });

      expect(result.categoryId).toBe('warhammer');
      expect(result.subtypeId).toBe('warhammer_books');
    });

    it('should classify sprue/assembled items as warhammer_minis', () => {
      const result = mapToTaxonomy({
        title: 'Warhammer 40k Space Marines Intercessors NOS on sprue',
      });

      expect(result.categoryId).toBe('warhammer');
      expect(result.subtypeId).toBe('warhammer_minis');
      expect(result.rationale).toContain('MINIATURES');
    });

    it('should classify painted miniatures as warhammer_minis', () => {
      const result = mapToTaxonomy({
        title: 'Pro painted Warhammer 40k Ultramarines army lot',
      });

      expect(result.categoryId).toBe('warhammer');
      expect(result.subtypeId).toBe('warhammer_minis');
    });

    it('should classify Citadel products as warhammer_minis', () => {
      const result = mapToTaxonomy({
        title: 'Citadel Combat Patrol Necrons 28mm miniatures',
      });

      expect(result.categoryId).toBe('warhammer');
      expect(result.subtypeId).toBe('warhammer_minis');
    });

    it('should use helper function isLikelyWarhammerBook correctly', () => {
      expect(isLikelyWarhammerBook('Warhammer 40k 10th Edition Rulebook')).toBe(true);
      expect(isLikelyWarhammerBook('Warhammer Space Marines painted army')).toBe(false);
    });
  });

  describe('Taylor Swift items', () => {
    it('should classify Taylor Swift hoodie as taylor_swift tour merch', () => {
      const result = mapToTaxonomy({
        title: 'Taylor Swift Eras Tour Hoodie Size M Black',
      });

      expect(result.categoryId).toBe('taylor_swift');
      expect(result.subtypeId).toBe('taylor_swift_tour');
      expect(result.collections).toContain('taylor_swift');
    });

    it('should classify Taylor Swift signed CD as taylor_swift albums', () => {
      const result = mapToTaxonomy({
        title: 'Taylor Swift 1989 Signed CD Autographed',
      });

      expect(result.categoryId).toBe('taylor_swift');
      expect(result.subtypeId).toBe('taylor_swift_albums');
      expect(result.collections).toContain('taylor_swift');
    });

    it('should classify Taylor Swift vinyl as taylor_swift vinyl', () => {
      const result = mapToTaxonomy({
        title: 'Taylor Swift Folklore Vinyl LP Limited Edition',
      });

      expect(result.categoryId).toBe('taylor_swift');
      expect(result.subtypeId).toBe('taylor_swift_vinyl');
      expect(result.collections).toContain('taylor_swift');
    });

    it('should classify Taylor Swift signed guitar as taylor_swift general', () => {
      const result = mapToTaxonomy({
        title: 'Taylor Swift Signed Acoustic Guitar Autographed',
      });

      expect(result.categoryId).toBe('taylor_swift');
      expect(result.collections).toContain('taylor_swift');
    });
  });

  describe('BTS K-pop items', () => {
    it('should classify BTS photocard as kpop_merch', () => {
      const result = mapToTaxonomy({
        title: 'BTS Jimin Photocard POB Proof Album',
      });

      expect(result.categoryId).toBe('kpop_merch');
      expect(result.subtypeId).toBe('kpop_photocards');
      expect(result.collections).toContain('bts');
    });

    it('should classify BTS album as kpop_merch', () => {
      const result = mapToTaxonomy({
        title: 'BTS Map of the Soul 7 Album CD Version 2',
      });

      expect(result.categoryId).toBe('kpop_merch');
      expect(result.subtypeId).toBe('kpop_albums');
      expect(result.collections).toContain('bts');
    });

    it('should classify BTS lightstick as kpop_lightsticks', () => {
      const result = mapToTaxonomy({
        title: 'BTS Official Army Bomb Ver 4 Lightstick',
      });

      expect(result.categoryId).toBe('kpop_lightsticks');
      expect(result.subtypeId).toBe('kpop_lightsticks_official');
      expect(result.collections).toContain('bts');
    });
  });

  describe('Collection tag detection', () => {
    it('should detect taylor_swift from various forms', () => {
      expect(detectCollections('Taylor Swift concert merch').map(t => t.id)).toContain('taylor_swift');
      expect(detectCollections('Swiftie collection').map(t => t.id)).toContain('taylor_swift');
      expect(detectCollections('Eras Tour poster').map(t => t.id)).toContain('taylor_swift');
    });

    it('should detect bts from various forms', () => {
      expect(detectCollections('BTS photocard').map(t => t.id)).toContain('bts');
      expect(detectCollections('Bangtan Sonyeondan album').map(t => t.id)).toContain('bts');
    });

    it('should detect multiple collection tags', () => {
      const tags = detectCollections('Disney Star Wars Funko Pop');
      expect(tags.map(t => t.id)).toContain('disney');
      expect(tags.map(t => t.id)).toContain('star_wars');
    });

    it('should return empty array for no matches', () => {
      const tags = detectCollections('Generic collectible item');
      expect(tags).toHaveLength(0);
    });
  });

  describe('Standard TCG items', () => {
    it('should classify Pokemon holo card correctly', () => {
      const result = mapToTaxonomy({
        title: 'Pokemon Base Set Charizard Holo 4/102',
      });

      expect(result.categoryId).toBe('pokemon');
      expect(result.subtypeId).toBe('pokemon_cards');
    });

    it('should classify PSA graded Pokemon as pokemon_graded', () => {
      const result = mapToTaxonomy({
        title: 'PSA 10 Pokemon Charizard VMAX Rainbow',
      });

      expect(result.categoryId).toBe('pokemon');
      expect(result.subtypeId).toBe('pokemon_graded');
    });

    it('should classify MTG booster box as mtg_sealed', () => {
      const result = mapToTaxonomy({
        title: 'Magic The Gathering Modern Horizons 3 Draft Booster Box Sealed',
      });

      expect(result.categoryId).toBe('mtg');
      expect(result.subtypeId).toBe('mtg_sealed');
    });
  });

  describe('Category hint override', () => {
    it('should respect category hint when provided', () => {
      const result = mapToTaxonomy({
        title: 'Limited Edition Figure',
        categoryHint: 'funko',
      });

      expect(result.categoryId).toBe('funko');
    });

    it('should warn when category hint not found', () => {
      const result = mapToTaxonomy({
        title: 'Some item',
        categoryHint: 'nonexistent_category',
      });

      expect(result.warnings).toBeDefined();
      expect(result.warnings?.some(w => w.includes('not found'))).toBe(true);
    });
  });

  describe('Confidence and rationale', () => {
    it('should always provide rationale', () => {
      const result = mapToTaxonomy({ title: 'Random item' });
      expect(result.rationale).toBeDefined();
      expect(result.rationale.length).toBeGreaterThan(0);
    });

    it('should provide confidence between 0 and 1', () => {
      const result = mapToTaxonomy({ title: 'Pokemon card' });
      expect(result.confidence).toBeGreaterThanOrEqual(0);
      expect(result.confidence).toBeLessThanOrEqual(1);
    });

    it('should include taxonomy version', () => {
      const result = mapToTaxonomy({ title: 'Any item' });
      expect(result.taxonomyVersion).toBeDefined();
      expect(result.taxonomyVersion).toMatch(/^\d{4}\.\d{2}\.\d{2}$/);
    });
  });

  describe('Unknown/fallback handling', () => {
    it('should return unknown with low confidence for unrecognized items', () => {
      const result = mapToTaxonomy({
        title: 'Abstract concept of nothingness xyz',
      });

      expect(result.categoryId).toBe('unknown');
      expect(result.confidence).toBeLessThan(0.3);
      expect(result.rationale).toContain('Manual');
    });
  });
});
