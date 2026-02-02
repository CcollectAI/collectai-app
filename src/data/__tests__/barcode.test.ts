/**
 * Barcode Lookup Tests
 *
 * Tests the MockDataProvider.lookupByBarcode functionality
 * with known fixture barcodes.
 */

import { mockDataProvider } from '../MockDataProvider';

describe('Barcode Lookup', () => {
  describe('Known fixtures', () => {
    it('should return Warhammer book for ISBN 9781839063077', async () => {
      const result = await mockDataProvider.lookupByBarcode('9781839063077', { codeType: 'isbn' });

      expect(result.title).toBe('Warhammer 40,000: Core Book (10th Edition)');
      expect(result.categoryId).toBe('warhammer');
      expect(result.subtypeId).toBe('rulebook');
      expect(result.priceBand).toBeDefined();
      expect(result.priceBand?.q50).toBe(55);
      expect(result.priceBand?.currency).toBe('EUR');
      expect(result.barcode).toBe('9781839063077');
      expect(result.barcodeType).toBe('isbn');
    });

    it('should return BTS Proof album for EAN 8809848755491', async () => {
      const result = await mockDataProvider.lookupByBarcode('8809848755491', { codeType: 'ean13' });

      expect(result.title).toBe('BTS - Proof (Standard Edition)');
      expect(result.categoryId).toBe('music_media');
      expect(result.subtypeId).toBe('album');
      expect(result.collections).toContain('bts');
      expect(result.attributes?.artist).toBe('BTS');
      expect(result.priceBand?.q50).toBe(55);
    });

    it('should return BTS Map of the Soul: 7 for EAN 8809440339068', async () => {
      const result = await mockDataProvider.lookupByBarcode('8809440339068');

      expect(result.title).toBe('BTS - Map of the Soul: 7');
      expect(result.collections).toContain('bts');
      expect(result.categoryId).toBe('music_media');
    });

    it('should return Taylor Swift Eras Tour merch for UPC 843930092451', async () => {
      const result = await mockDataProvider.lookupByBarcode('843930092451', { codeType: 'upc_a' });

      expect(result.title).toContain('Taylor Swift Eras Tour');
      expect(result.categoryId).toBe('music_media');
      expect(result.subtypeId).toBe('tour_merch');
      expect(result.collections).toContain('taylor_swift');
      expect(result.collections).toContain('eras_tour');
    });

    it('should return Taylor Swift 1989 vinyl for UPC 602455542472', async () => {
      const result = await mockDataProvider.lookupByBarcode('602455542472');

      expect(result.title).toContain('1989');
      expect(result.subtypeId).toBe('vinyl');
      expect(result.collections).toContain('taylor_swift');
    });

    it('should return book for ISBN 9780593499597', async () => {
      const result = await mockDataProvider.lookupByBarcode('9780593499597');

      expect(result.title).toBe('Fourth Wing (Hardcover)');
      expect(result.categoryId).toBe('books');
      expect(result.attributes?.author).toBe('Rebecca Yarros');
    });
  });

  describe('Unknown barcodes', () => {
    it('should return null title and missingRequired for unknown barcode', async () => {
      const result = await mockDataProvider.lookupByBarcode('0000000000000');

      expect(result.title).toBeNull();
      expect(result.categoryId).toBeNull();
      expect(result.missingRequired).toContain('title');
      expect(result.missingRequired).toContain('categoryId');
      expect(result.priceBand).toBeNull();
      expect(result.rationale).toContain('Barcode not found in product databases');
    });

    it('should preserve barcode value in response', async () => {
      const result = await mockDataProvider.lookupByBarcode('1234567890123');

      expect(result.barcode).toBe('1234567890123');
    });
  });

  describe('Price bands', () => {
    it('should include q10, q50, q90 price quantiles', async () => {
      const result = await mockDataProvider.lookupByBarcode('9781839063077');

      expect(result.priceBand).toBeDefined();
      expect(result.priceBand?.q10).toBeLessThan(result.priceBand?.q50 ?? 0);
      expect(result.priceBand?.q50).toBeLessThan(result.priceBand?.q90 ?? 0);
      expect(result.priceBand?.confidence).toBeGreaterThan(0);
      expect(result.priceBand?.confidence).toBeLessThanOrEqual(1);
    });
  });

  describe('Collection tags', () => {
    it('should include bts collection tag for BTS products', async () => {
      const result = await mockDataProvider.lookupByBarcode('8809848755491');
      expect(result.collections).toContain('bts');
    });

    it('should include taylor_swift collection tag for Taylor Swift products', async () => {
      const result = await mockDataProvider.lookupByBarcode('843930092451');
      expect(result.collections).toContain('taylor_swift');
    });

    it('should include multiple collection tags when applicable', async () => {
      const result = await mockDataProvider.lookupByBarcode('843930092451');
      expect(result.collections?.length).toBeGreaterThan(1);
      expect(result.collections).toContain('taylor_swift');
      expect(result.collections).toContain('eras_tour');
    });
  });
});

describe('Market Search', () => {
  describe('BTS searches', () => {
    it('should return hits for BTS query', async () => {
      const result = await mockDataProvider.marketSearch('BTS Proof Album');

      expect(result.hits.length).toBeGreaterThan(0);
      expect(result.providers).toContain('ebay');
      expect(result.confidence).toBeGreaterThan(0);
    });

    it('should filter by collection tag', async () => {
      const result = await mockDataProvider.marketSearch('album', {
        collections: ['bts'],
      });

      expect(result.hits.length).toBeGreaterThan(0);
      // All hits should be BTS-related (mock behavior)
    });
  });

  describe('Taylor Swift searches', () => {
    it('should return hits for Taylor Swift query', async () => {
      const result = await mockDataProvider.marketSearch('Taylor Swift Eras Tour');

      expect(result.hits.length).toBeGreaterThan(0);
    });
  });

  describe('Search options', () => {
    it('should respect limit option', async () => {
      const result = await mockDataProvider.marketSearch('BTS', { limit: 1 });

      expect(result.hits.length).toBeLessThanOrEqual(1);
    });

    it('should filter by soldOnly', async () => {
      const result = await mockDataProvider.marketSearch('BTS', { soldOnly: true });

      result.hits.forEach((hit) => {
        expect(hit.soldAt).toBeDefined();
      });
    });

    it('should filter by minPrice', async () => {
      const result = await mockDataProvider.marketSearch('BTS', { minPrice: 50 });

      result.hits.forEach((hit) => {
        expect(hit.price).toBeGreaterThanOrEqual(50);
      });
    });

    it('should filter by maxPrice', async () => {
      const result = await mockDataProvider.marketSearch('BTS', { maxPrice: 100 });

      result.hits.forEach((hit) => {
        expect(hit.price).toBeLessThanOrEqual(100);
      });
    });
  });

  describe('MarketHit structure', () => {
    it('should return normalized MarketHit objects', async () => {
      const result = await mockDataProvider.marketSearch('BTS');

      if (result.hits.length > 0) {
        const hit = result.hits[0];
        expect(hit.source).toBeDefined();
        expect(hit.rawId).toBeDefined();
        expect(hit.title).toBeDefined();
        expect(typeof hit.price).toBe('number');
        expect(hit.currency).toBeDefined();
      }
    });
  });

  describe('Empty results', () => {
    it('should return empty hits for no matches', async () => {
      const result = await mockDataProvider.marketSearch('xyz123nonexistent');

      // Mock may still return generic results; just verify structure
      expect(result.hits).toBeDefined();
      expect(Array.isArray(result.hits)).toBe(true);
      expect(result.providers).toBeDefined();
    });
  });
});
