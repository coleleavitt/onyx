export type MemoryCategory = "notes" | "concepts" | "entities" | "workstreams";

export interface MemoryItem {
  id: number;
  title: string;
  category: MemoryCategory;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface MemoryListResponse {
  items: MemoryItem[];
  total: number;
  category_counts: Record<MemoryCategory, number>;
}

export interface MemoryRevision {
  id: string;
  memory_id: number;
  title: string;
  category: MemoryCategory;
  content: string;
  source: string;
  created_at: string;
}

export interface MemoryInput {
  title?: string | null;
  category: MemoryCategory;
  content: string;
}
