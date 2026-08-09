/**
 * Referral capture — the front half of the creator funnel.
 *
 * These pin the URL shapes a creator actually posts. The bug this guards
 * against: AuthProvider's link handler used to bail on any URL without a '#',
 * which silently discarded every query-string link ever published.
 */

import { extractReferralCode, normaliseCode } from '@/lib/referral';

describe('normaliseCode', () => {
  it('upper-cases and trims', () => {
    expect(normaliseCode('  luna10 ')).toBe('LUNA10');
  });

  it('rejects empty, junk and over-long input', () => {
    expect(normaliseCode('')).toBeNull();
    expect(normaliseCode('   ')).toBeNull();
    expect(normaliseCode(null)).toBeNull();
    expect(normaliseCode(undefined)).toBeNull();
    expect(normaliseCode('has spaces')).toBeNull();
    expect(normaliseCode('drop;table')).toBeNull();
    expect(normaliseCode('A'.repeat(33))).toBeNull();
  });

  it('allows the character set codes are minted from', () => {
    expect(normaliseCode('luna_10-x')).toBe('LUNA_10-X');
  });
});

describe('extractReferralCode', () => {
  it('reads ?ref= from a universal link', () => {
    expect(extractReferralCode('https://sparrowcollect.com/?ref=luna10')).toBe('LUNA10');
  });

  it('reads the /r/<CODE> path form', () => {
    expect(extractReferralCode('https://sparrowcollect.com/r/luna10')).toBe('LUNA10');
  });

  it('reads /r/<CODE> with trailing query and fragment', () => {
    expect(extractReferralCode('https://sparrowcollect.com/r/LUNA10?utm_source=tiktok#x')).toBe('LUNA10');
  });

  it('reads ?ref= from the custom scheme', () => {
    expect(extractReferralCode('sparrow://?ref=luna10')).toBe('LUNA10');
  });

  it('accepts referral_code and utm_content aliases', () => {
    expect(extractReferralCode('https://sparrowcollect.com/?referral_code=abc1')).toBe('ABC1');
    expect(extractReferralCode('https://sparrowcollect.com/?utm_content=abc2')).toBe('ABC2');
  });

  it('picks ref out of a multi-param query', () => {
    expect(
      extractReferralCode('https://sparrowcollect.com/?utm_source=tiktok&ref=luna10&x=1'),
    ).toBe('LUNA10');
  });

  it('url-decodes the value', () => {
    expect(extractReferralCode('https://sparrowcollect.com/?ref=luna%2D10')).toBe('LUNA-10');
  });

  it('returns null when there is no code', () => {
    expect(extractReferralCode('https://sparrowcollect.com/')).toBeNull();
    expect(extractReferralCode('sparrow://item/123')).toBeNull();
    expect(extractReferralCode(null)).toBeNull();
    expect(extractReferralCode(undefined)).toBeNull();
  });

  it('ignores junk values rather than storing them', () => {
    expect(extractReferralCode('https://sparrowcollect.com/?ref=')).toBeNull();
    expect(extractReferralCode('https://sparrowcollect.com/?ref=a%20b')).toBeNull();
  });

  // The auth deep link carries tokens in the FRAGMENT. Referral parsing must
  // never reach into it, or a stray "ref" in a token could be captured as a code.
  it('does not read the auth fragment', () => {
    const authUrl = 'sparrow://#access_token=eyJref=nope&refresh_token=abc&type=signup';
    expect(extractReferralCode(authUrl)).toBeNull();
  });

  it('still finds ?ref= when an auth fragment follows it', () => {
    expect(
      extractReferralCode('https://sparrowcollect.com/?ref=luna10#access_token=abc'),
    ).toBe('LUNA10');
  });
});
