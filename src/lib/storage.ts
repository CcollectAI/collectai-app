type AsyncStorageLike = { getItem(k:string):Promise<string|null>; setItem(k:string,v:string):Promise<void> };
let AS: AsyncStorageLike | null = null;
try {
  // @ts-ignore
  AS = require('@react-native-async-storage/async-storage').default;
} catch {
  const mem = new Map<string,string>();
  AS = { async getItem(k){ return mem.has(k)? (mem.get(k) as string): null; }, async setItem(k,v){ mem.set(k,v); } };
}
export async function getJSON<T>(key: string, fallback: T): Promise<T> {
  try { const s = await (AS as AsyncStorageLike).getItem(key); return s ? JSON.parse(s) as T : fallback; } catch { return fallback; }
}
export async function setJSON<T>(key: string, value: T): Promise<void> {
  try { await (AS as AsyncStorageLike).setItem(key, JSON.stringify(value)); } catch {}
}
