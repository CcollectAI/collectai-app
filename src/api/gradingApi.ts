/**
 * Grading service integration API methods.
 */
import { get } from "./httpClient";

export const gradingLookup = (certNumber: string, service: 'psa' | 'cgc' | 'bgs' | 'beckett') =>
  get<{
    cert_number: string;
    service: string;
    service_name: string;
    item_name: string | null;
    grade: string | null;
    grade_numeric: number | null;
    sub_grades: Record<string, number> | null;
    population_at_grade: number | null;
    population_higher: number | null;
    cert_verified: boolean;
    cert_url: string | null;
    label_type: string | null;
    year: string | null;
    error: string | null;
  }>(`/grading/lookup?cert_number=${encodeURIComponent(certNumber)}&service=${encodeURIComponent(service)}`);

export const gradingPopulation = (itemName: string, category: string, service?: string) =>
  get<{
    item_name: string;
    category: string;
    service: string;
    total_graded: number;
    population: {
      grade: string;
      count: number;
      pct_of_total: number | null;
    }[];
    avg_grade: number | null;
    highest_grade: string | null;
    last_updated: string | null;
  }>(`/grading/population?item_name=${encodeURIComponent(itemName)}&category=${encodeURIComponent(category)}${service ? `&service=${encodeURIComponent(service)}` : ''}`);

export const gradingServices = (category?: string) =>
  get<{
    services: {
      id: string;
      name: string;
      short_name: string;
      website: string;
      submission_url: string;
      grade_scale: string;
      categories: string[];
      turnaround: string;
      price_range: string;
    }[];
    eligible_categories: string[];
  }>(`/grading/services${category ? `?category=${encodeURIComponent(category)}` : ''}`);
