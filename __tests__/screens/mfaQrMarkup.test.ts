/**
 * The 2FA QR is SVG, and React Native's <Image> cannot draw SVG — on Android
 * the QR box was empty (2026-09-24). mfa-setup renders it with SvgXml, which
 * needs the raw markup out of the data URI auth-js builds.
 */
import { qrSvgMarkup } from '../../app/mfa-setup';

describe('qrSvgMarkup', () => {
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 29 29"><path d="M0,0h7v7h-7z"/></svg>';

  it('takes the markup out of auth-js\'s `data:image/svg+xml;utf-8,` URI', () => {
    // The exact prefix auth-js GoTrueClient adds in mfa.enroll().
    expect(qrSvgMarkup(`data:image/svg+xml;utf-8,${svg}`)).toBe(svg);
  });

  it('keeps commas inside the markup (only the first comma ends the prefix)', () => {
    expect(qrSvgMarkup(`data:image/svg+xml;utf-8,${svg}`)).toContain('M0,0h7');
  });

  it('passes bare markup through', () => {
    expect(qrSvgMarkup(svg)).toBe(svg);
  });
});
