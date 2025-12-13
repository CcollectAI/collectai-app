export type StageStatus = "ok" | "error";
export interface IngestStage { status: StageStatus; error?: string }
export interface OCRStage { status: StageStatus; hints?: Record<string,unknown>; error?: string }
export interface GuideStage {
  status: StageStatus;
  bands?: { p25?: number; p50?: number; p75?: number };
  count?: number;
  error?: string; // "guide-unexpected" | "no-data" | ...
}
export interface PredictStage {
  status: StageStatus;
  q10?: number; q50?: number; q90?: number;
  confidence?: number;
  comps_count?: number;
  model_version?: string;
  source?: "baseline" | "comps";
  training_data_asof?: string;
  error?: string; // "pred-unexpected" | "no-comps" | ...
}
export interface FastPassResponseV1 {
  id: string;
  nk: string;
  ingest: IngestStage;
  ocr: OCRStage;
  guide: GuideStage;
  predict: PredictStage;
  watchlist?: { added?: boolean; id?: string };
}
