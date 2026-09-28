/**
 * openAffiliateUrl is the one place a shop tap is recorded (demand_signals,
 * affiliate_click). A link wrapped by an affiliate network names the network's
 * host, so the caller's `source` must win over the hostname.
 */
jest.mock('react-native', () => ({ Linking: { openURL: jest.fn().mockResolvedValue(undefined) } }));
jest.mock('@/analytics/track', () => ({ track: jest.fn() }));
jest.mock('@/api/intelligenceApi', () => ({ recordAffiliateClick: jest.fn() }));
jest.mock('@/lib/logger', () => ({ logger: { error: jest.fn() } }));

import { Linking } from 'react-native';
import { recordAffiliateClick } from '@/api/intelligenceApi';
import { openAffiliateUrl } from '@/utils/affiliateHelpers';

describe('openAffiliateUrl', () => {
  beforeEach(() => jest.clearAllMocks());

  it('records the caller-named marketplace for a network-wrapped link', () => {
    const url = 'https://tcgplayer.pxf.io/c/1/2/3?u=https%3A%2F%2Fwww.tcgplayer.com%2Fproduct%2F1&subId1=sparrow';
    openAffiliateUrl(url, { source: 'tcgplayer' });
    expect(recordAffiliateClick).toHaveBeenCalledWith(expect.objectContaining({ source: 'tcgplayer' }));
    expect(Linking.openURL).toHaveBeenCalledWith(url);
  });

  it('falls back to the hostname when the caller names no marketplace', () => {
    openAffiliateUrl('https://www.ebay.com/itm/1');
    expect(recordAffiliateClick).toHaveBeenCalledWith(expect.objectContaining({ source: 'ebay' }));
  });

  it('neither records nor opens a non-http url', () => {
    openAffiliateUrl('javascript:alert(1)', { source: 'ebay' });
    expect(recordAffiliateClick).not.toHaveBeenCalled();
    expect(Linking.openURL).not.toHaveBeenCalled();
  });
});
