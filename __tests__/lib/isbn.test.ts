import { checkTypedCode, cleanTypedCode } from '@/lib/isbn';

describe('checkTypedCode', () => {
  it.each([
    ['9781569319000', 'ok'],          // Naruto vol. 1 (ISBN-13)
    ['9780439023481', 'ok'],          // The Hunger Games
    ['1569319006', 'ok'],             // Naruto vol. 1 (ISBN-10)
    ['043942089X', 'ok'],             // ISBN-10 whose check digit is X
    ['673419190626', 'ok'],           // UPC-A (LEGO box)
    ['9780439023482', 'check_digit'], // last digit typo
    ['9780439032481', 'check_digit'], // swapped digits
    ['1569319007', 'check_digit'],
    ['04394208X9', 'length'],         // X only allowed last
    ['97804390234', 'length'],        // 11 digits
    ['12345678', 'length'],
  ])('%s -> %s', (code, expected) => {
    expect(checkTypedCode(cleanTypedCode(code))).toBe(expected);
  });

  it('ignores spaces, hyphens and a lower-case x', () => {
    expect(checkTypedCode(cleanTypedCode('978-1-56931-900-0'))).toBe('ok');
    expect(checkTypedCode(cleanTypedCode('0-439-42089-x'))).toBe('ok');
  });
});
