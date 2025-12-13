export type CSVRow = {
  title: string;
  category: string;
  priceEUR: number;
  changePct?: number;
  notes?: string;
  imageUri?: string;
  year?: string;
};

const HEADER_ALIASES: Record<string, keyof CSVRow> = {
  title: 'title',
  name: 'title',
  item: 'title',

  category: 'category',
  cat: 'category',

  price: 'priceEUR',
  priceeur: 'priceEUR',
  value: 'priceEUR',
  amount: 'priceEUR',

  changepct: 'changePct',
  '%': 'changePct',
  change: 'changePct',

  notes: 'notes',
  note: 'notes',
  comment: 'notes',

  image: 'imageUri',
  imageurl: 'imageUri',
  imageuri: 'imageUri',
  photo: 'imageUri',

  year: 'year',
};

function normalizeHeader(h: string): keyof CSVRow | null {
  const k = h.trim().toLowerCase();
  return HEADER_ALIASES[k] ?? (HEADER_ALIASES[k.replace(/\s+/g,'')] ?? null);
}

function toNumber(n: string | undefined): number | undefined {
  if (!n) return undefined;
  const cleaned = n.replace(/[,\s€$]/g, '');
  const val = Number(cleaned);
  return Number.isFinite(val) ? val : undefined;
}

export function parseCSV(text: string): {
  rows: CSVRow[];
  errors: string[];
  headerMap: Record<number, keyof CSVRow>;
} {
  const lines = text
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .split('\n')
    .filter(l => l.trim().length > 0);

  const errors: string[] = [];
  if (lines.length === 0) return { rows: [], errors: ['Empty CSV'], headerMap: {} };

  // naive CSV split (supports quoted commas)
  const splitLine = (line: string): string[] => {
    const out: string[] = [];
    let cur = '';
    let q = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        // toggle quote or escape
        if (q && line[i+1] === '"') { cur += '"'; i++; }
        else q = !q;
      } else if (ch === ',' && !q) {
        out.push(cur);
        cur = '';
      } else {
        cur += ch;
      }
    }
    out.push(cur);
    return out;
  };

  const headerCells = splitLine(lines[0]);
  const headerMap: Record<number, keyof CSVRow> = {};
  headerCells.forEach((h, i) => {
    const norm = normalizeHeader(h);
    if (norm) headerMap[i] = norm;
  });

  if (!Object.values(headerMap).includes('title')) errors.push('Missing "title" column');
  if (!Object.values(headerMap).includes('category')) errors.push('Missing "category" column');
  if (!Object.values(headerMap).includes('priceEUR')) errors.push('Missing "price" column');

  const rows: CSVRow[] = [];
  for (let li = 1; li < lines.length; li++) {
    const cols = splitLine(lines[li]);
    const obj: any = {};
    Object.entries(headerMap).forEach(([idxStr, key]) => {
      const idx = Number(idxStr);
      const raw = (cols[idx] ?? '').trim();
      if (key === 'priceEUR' || key === 'changePct') {
        const num = toNumber(raw);
        if (num !== undefined) obj[key] = num;
      } else {
        obj[key] = raw;
      }
    });

    // Validate required
    const missing: string[] = [];
    if (!obj.title) missing.push('title');
    if (!obj.category) missing.push('category');
    if (typeof obj.priceEUR !== 'number') missing.push('price');
    if (missing.length) {
      errors.push(`Row ${li}: missing ${missing.join(', ')}`);
      continue;
    }
    rows.push({
      title: obj.title,
      category: obj.category,
      priceEUR: obj.priceEUR,
      changePct: typeof obj.changePct === 'number' ? obj.changePct : undefined,
      notes: obj.notes || undefined,
      imageUri: obj.imageUri || undefined,
      year: obj.year || undefined,
    });
  }

  return { rows, errors, headerMap };
}
