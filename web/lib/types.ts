// Mirrors the Pydantic models in backend/src/aislescout/models.py.

export type UnitBasis = "lb" | "fl oz" | "each";

export interface Store {
  source: string;
  store_id: string;
  chain: string;
  name: string;
  address: string;
  city: string;
  state: string;
  zip_code: string;
  latitude: number | null;
  longitude: number | null;
}

export interface Deal {
  source: string;
  store_id: string;
  product_id: string;
  name: string;
  brand: string;
  size_text: string;
  sold_by: "unit" | "weight";
  regular_price: number | null;
  sale_price: number | null;
  price: number;
  min_quantity: number;
  member_only: boolean;
  unit_price: number | null;
  unit_basis: UnitBasis | null;
  valid_from: string | null; // YYYY-MM-DD
  valid_to: string | null;
  image_url: string | null;
  product_url: string | null;
  product_rating: number | null;
  review_count: number | null;
  on_sale: boolean;
  savings_pct: number | null;
}

export interface SearchResult {
  deal: Deal;
  store: Store;
}

export interface SourceStatus {
  source: string;
  status: "ok" | "skipped" | "error";
  message: string;
  result_count: number;
}

export interface SearchResponse {
  query: string;
  zip_code: string;
  sale_only: boolean;
  demo: boolean;
  results: SearchResult[];
  sources: SourceStatus[];
}
