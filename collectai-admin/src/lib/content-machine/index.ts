// ---------------------------------------------------------------------------
// Content Machine — Public API re-exports
// ---------------------------------------------------------------------------

export * from "./types";
export * from "./seed-data";
export { generateIdeas, generateSeries } from "./idea-generator";
export { generateWeeklyCalendar, exportCalendarMarkdown } from "./calendar-generator";
export { generateCaption, generateCaptionPack, generateCaptionPacks, exportCaptionsMarkdown } from "./caption-generator";
export { planBatch, exportBatchMarkdown } from "./batch-planner";
export {
  saveToLocalStorage, loadFromLocalStorage, clearLocalStorage,
  saveBatchChecks, loadBatchChecks,
  saveToSupabase, loadFromSupabase,
  updateIdeaStatus, updateIdeaPriority,
} from "./persistence";
export type { SavedGeneration } from "./persistence";
