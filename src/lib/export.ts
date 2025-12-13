import { Share } from 'react-native';

function escapeCSV(v: any): string {
  const s = String(v ?? '');
  if (/[",\n\r]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}

/** Share CSV via the native share sheet (no extra deps). Returns the CSV string. */
export async function exportCSV(rows: Record<string, any>[], name = 'items-export'): Promise<string> {
  if (!rows.length) {
    await Share.share({ message: 'No data.' });
    return '';
  }
  const keys = Array.from(new Set(rows.flatMap(r => Object.keys(r))));
  const header = keys.join(',');
  const body = rows.map(r => keys.map(k => escapeCSV(r[k])).join(',')).join('\n');
  const csv = header + '\n' + body;
  await Share.share({ title: name, message: csv });
  return csv;
}
