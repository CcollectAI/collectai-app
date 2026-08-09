import Constants from 'expo-constants';
import { logger } from '@/lib/logger';

export type PredictInput = { title:string; category:string; imageUrl?:string|null; purchasePrice?:number|null; };
export type PredictOut = { estimated_value:number; confidence:number; };

export async function predictValue(input: PredictInput): Promise<PredictOut>{
  const extra = Constants.expoConfig?.extra as Record<string, unknown> | undefined;
  const url = extra?.PREDICT_URL as string | undefined;

  // Try external endpoint if provided
  if (url && url.startsWith('http')) {
    try{
      const resp = await fetch(url, { method:'POST', headers:{ 'Content-Type':'application/json' }, body: JSON.stringify(input) });
      if (resp.ok) return await resp.json() as PredictOut;
    } catch (e) {
      // Prediction endpoint unavailable — falls back to the local heuristic below.
      logger.error('[silent-fallback] predict: endpoint unavailable, using heuristic:', e);
    }
  }

  // Local fallback heuristic (stub)
  const base = Number(input.purchasePrice || 50);
  const bump = input.title.toLowerCase().includes('pikachu') ? 1.35 : 1.18;
  const est = Math.round(base * bump * 100) / 100;
  return { estimated_value: est, confidence: 72 };
}
