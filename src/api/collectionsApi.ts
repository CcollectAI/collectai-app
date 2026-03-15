/**
 * Collections API methods.
 */
import { get } from "./httpClient";

export const listCollections = (category?: string) =>
  get(`/collections${category ? `?category=${encodeURIComponent(category)}` : ""}`);

export const getCollectionDetail = (collectionId: string) =>
  get(`/collections/${encodeURIComponent(collectionId)}`);

export const getCollectionProgress = (collectionId: string) =>
  get(`/collections/${encodeURIComponent(collectionId)}/progress`);

export const getUserCollectionProgress = (category?: string) =>
  get(`/collections/user/progress${category ? `?category=${encodeURIComponent(category)}` : ""}`);
