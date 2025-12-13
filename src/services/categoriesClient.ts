import { request } from './collectorsClient';

export interface CategoryMeta {
  slug: string;
  label: string;
  wave: string;
  active: boolean;
  avg_value?: number;
  item_count?: number;
}

export function getCategories(): Promise<CategoryMeta[]> {
  return request<CategoryMeta[]>('/categories');
}
