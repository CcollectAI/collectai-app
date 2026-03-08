import { classifyOnDevice, buildCategoryDistribution } from '../edgeClassifier';

describe('edgeClassifier', () => {
  it('returns user context when dominant category exists', () => {
    const result = classifyOnDevice(null, { pokemon: 30, funko: 5, lego: 3 });
    expect(result.category).toBe('pokemon');
    expect(result.method).toBe('user_context');
    expect(result.confidence).toBeGreaterThan(0.4);
  });

  it('returns aspect ratio hint for portrait images', () => {
    const result = classifyOnDevice({ width: 300, height: 500 }, null);
    expect(result.method).toBe('aspect_ratio');
    expect(result.category).toBe('pokemon');
  });

  it('returns aspect ratio hint for landscape images', () => {
    const result = classifyOnDevice({ width: 800, height: 400 }, null);
    expect(result.method).toBe('aspect_ratio');
    expect(result.category).toBe('lego');
  });

  it('returns default when no signals available', () => {
    const result = classifyOnDevice(null, null);
    expect(result.method).toBe('default');
    expect(result.confidence).toBe(0.1);
  });

  it('buildCategoryDistribution counts correctly', () => {
    const items = [
      { category: 'pokemon' },
      { category: 'pokemon' },
      { category: 'lego' },
    ];
    const dist = buildCategoryDistribution(items);
    expect(dist.pokemon).toBe(2);
    expect(dist.lego).toBe(1);
  });

  it('returns aspect ratio hint for square images', () => {
    const result = classifyOnDevice({ width: 500, height: 500 }, null);
    expect(result.method).toBe('aspect_ratio');
    expect(result.category).toBe('funko');
  });
});
