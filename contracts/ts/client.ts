export type FastPassGuide = { status: "ok"|"error"; bands?: {p25?:number;p50?:number;p75?:number}; count?: number; error?: string };
export type FastPassPredict = {
  status: "ok"|"error";
  q10?:number; q50?:number; q90?:number; confidence?:number;
  comps_count?:number; model_version?:string; source?:"baseline"|"comps";
  training_data_asof?:string; error?: string;
};
export type FastPassResponseV1 = {
  id: string; nk: string;
  ingest: {status:"ok"|"error"; error?:string};
  ocr: {status:"ok"|"error"; hints?: Record<string,unknown>; error?:string};
  guide: FastPassGuide;
  predict: FastPassPredict;
  watchlist?: {added?:boolean; id?:string};
};

export type PredictHistoryRow = {
  ts:string; q10?:number; q50?:number; q90?:number;
  confidence?:number; comps_count?:number; model_version?:string; source?:string;
};
export type PredictHistory = { nk: string; rows: PredictHistoryRow[] };

export type ItemRow = { id?:string; nk:string; est_value?: number | null };
export type ItemsResponse = { user_id:string; page:number; page_size:number; total:number; items: ItemRow[]; };
export type ItemsSummary = { user_id:string; count:number; total_value:number; avg_value:number; top: ItemRow[] };
export type MoversRow = { nk:string; latest:number; prev:number; delta:number; pct?:number|null };
export type MoversResponse = { user_id:string; movers: MoversRow[]; mode:"db"|"memory" };

export class CollectorsClient {
  constructor(private base = "http://localhost:8080") {}
  async fastpass(form: FormData): Promise<FastPassResponseV1> {
    const r = await fetch(`${this.base}/ingest/fastpass_v2`, { method:"POST", body: form });
    return r.json();
    }
  async predict(nk: string): Promise<FastPassPredict & {nk:string}> {
    const r = await fetch(`${this.base}/predict/hybrid_safe_v1?nk=${encodeURIComponent(nk)}`);
    const j = await r.json();
    return { status: "ok", nk, ...j };
  }
  async history(nk: string, limit=50): Promise<PredictHistory> {
    const r = await fetch(`${this.base}/predict/history?nk=${encodeURIComponent(nk)}&limit=${limit}`);
    return r.json();
  }
  async items(user_id: string, sort="value_desc", page=1, page_size=20): Promise<ItemsResponse> {
    const r = await fetch(`${this.base}/items?user_id=${encodeURIComponent(user_id)}&sort=${sort}&page=${page}&page_size=${page_size}`);
    return r.json();
  }
  async summary(user_id: string, top_n=0): Promise<ItemsSummary> {
    const r = await fetch(`${this.base}/items/summary?user_id=${encodeURIComponent(user_id)}&top_n=${top_n}`);
    return r.json();
  }
  async movers(user_id: string, limit=10): Promise<MoversResponse> {
    const r = await fetch(`${this.base}/items/movers?user_id=${encodeURIComponent(user_id)}&limit=${limit}`);
    return r.json();
  }
}
