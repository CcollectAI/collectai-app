/**
 * Set / Collection tracking API methods.
 */
import { get, put } from "./httpClient";

export const listSets = (categoryId?: string) =>
  get(`/sets${categoryId ? `?category_id=${encodeURIComponent(categoryId)}` : ""}`);

export const getSetDetail = (setId: string) =>
  get(`/sets/${encodeURIComponent(setId)}`);

export const getSetProgress = (setId: string) =>
  get(`/sets/${encodeURIComponent(setId)}/progress`);

export const updateSetProgress = (setId: string, payload: { item_ids: string[]; action: "add" | "remove" }) =>
  put(`/sets/${encodeURIComponent(setId)}/progress`, payload as Record<string, unknown>);

export const getMySetProgress = () =>
  get("/sets/my-progress");
