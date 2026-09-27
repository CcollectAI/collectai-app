/**
 * An item saved from QuickScan keeps its photo (device walk 2026-09-27:
 * persistQuickscanDraft accepted photoUri and never used it).
 */
const mockUpload = jest.fn();
const mockPost = jest.fn();
jest.mock('@/lib/supabase', () => ({ supabase: {} }));
jest.mock('@/api/collectorsApi', () => ({
  collectorsApi: {
    uploadPhoto: (...a: unknown[]) => mockUpload(...a),
    post: (...a: unknown[]) => mockPost(...a),
    patch: jest.fn(async () => ({})),
  },
}));
import { persistQuickscanDraft } from '@/data/providers/itemsProvider';

beforeEach(() => {
  mockUpload.mockReset();
  mockPost.mockReset();
  mockPost.mockResolvedValue({ id: 'i1', title: 'Charizard', category: 'pokemon', image_url: 'https://cdn/x.jpg' });
});

it('uploads the scan photo and creates the item with its URL', async () => {
  mockUpload.mockResolvedValue({ cdn_url: 'https://cdn/x.jpg' });
  const r = await persistQuickscanDraft({ photoUri: 'file:///tmp/card.png', categoryId: 'pokemon', title: 'Charizard' } as never);
  expect(mockUpload).toHaveBeenCalledWith('quickscan-draft', 'file:///tmp/card.png', 'image/png');
  expect(mockPost.mock.calls[0][1]).toMatchObject({ image_url: 'https://cdn/x.jpg' });
  expect(r.imageUrl).toBe('https://cdn/x.jpg');
  expect(r.photoSaved).toBe(true);
});

it('a failed upload still saves the item, and says the photo was lost', async () => {
  mockUpload.mockRejectedValue(new Error('offline'));
  mockPost.mockResolvedValue({ id: 'i1', title: 'Charizard', category: 'pokemon', image_url: null });
  const r = await persistQuickscanDraft({ photoUri: 'file:///tmp/card.jpg', categoryId: 'pokemon', title: 'Charizard' } as never);
  expect(mockPost).toHaveBeenCalled();
  expect(mockPost.mock.calls[0][1].image_url).toBeUndefined();
  expect(r.photoSaved).toBe(false);
});
