import { Alert } from 'react-native';
import { logger } from '@/lib/logger';
type Row = { category: string; name: string; priceEUR: number; pct?: number };
const fmt = (v: unknown) => { if (v==null) return ''; const s=String(v); return /[,"\n]/.test(s) ? `"${s.replace(/"/g,'""')}"` : s; };
export function rowsToCSV(rows: Row[]): string {
  const head = ['Category','Name','Price (EUR)','Change %']; const lines = [head.join(',')];
  for (const r of rows) lines.push([fmt(r.category),fmt(r.name),fmt(r.priceEUR),fmt(typeof r.pct==='number'? r.pct.toFixed(2):'')].join(','));
  return lines.join('\n');
}
export async function saveCSVAndShare(filename: string, csv: string): Promise<string> {
  try {
    const FS = await import('expo-file-system');
    const cacheDir = FS.Paths.cache.uri;
    const path = cacheDir + '/' + filename;
    await FS.writeAsStringAsync(path, csv, { encoding: 'utf8' });
    try {
      const SH = await import('expo-sharing');
      if (await SH.isAvailableAsync()) await SH.shareAsync(path, { mimeType:'text/csv', dialogTitle: filename });
      else Alert.alert('Saved', `CSV: ${path}`);
    }
    catch (e) {
      logger.error('[silent-catch] csv.ts:20:', e); Alert.alert('Saved (no sharing module)', `CSV: ${path}`); }
    return path;
  } catch (e) {
    logger.error('[silent-catch] csv.ts:22:', e); Alert.alert('Export unavailable', 'FileSystem/Sharing not installed yet.'); return 'unavailable'; }
}
