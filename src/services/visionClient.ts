import { API_BASE_URL, API_KEY } from '@/config/api';

export interface VisionPredictRequest {
  image_base64: string;
  category_hint?: string;
  source?: 'portfolio' | 'watchlist' | string;
  [key: string]: unknown;
}

export interface VisionPredictCandidate {
  label: string;
  score: number;
  [key: string]: unknown;
}

export interface VisionPredictOutput {
  category?: string;
  candidates?: VisionPredictCandidate[];
  estimated_value_low?: number;
  estimated_value_mid?: number;
  estimated_value_high?: number;
  details?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface VisionPredictResponse {
  id?: string;
  outputs?: VisionPredictOutput[];
  [key: string]: unknown;
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };

  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let message = `Request failed with status ${res.status}`;
    try {
      const text = await res.text();
      if (text) message = text;
    } catch {
      // ignore
    }
    throw new Error(message);
  }

  return (await res.json()) as T;
}

export function predictVision(
  body: VisionPredictRequest
): Promise<VisionPredictResponse> {
  return request<VisionPredictResponse>('/vision/predict', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

