export type MemoryCategory = "notes" | "concepts" | "entities" | "workstreams";

export interface MemoryItem {
  id: number;
  title: string;
  category: MemoryCategory;
  content: string;
  /** Space scope: set when the memory only applies inside one space. */
  project_id: number | null;
  project_name: string | null;
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
  /** Space scope: set to attach the memory to a single space. */
  project_id?: number | null;
}

export type MemorySourceType =
  | "chat_session"
  | "document"
  | "connector"
  | "file"
  | "manual";

export interface MemorySourceItem {
  id: number;
  source_type: MemorySourceType;
  source_id: string | null;
  label: string;
  url: string | null;
  created_at: string;
}

export interface RelatedMemory {
  id: number;
  title: string;
  category: MemoryCategory;
}

export interface RelatedMemoriesResponse {
  groups: Partial<Record<MemoryCategory, RelatedMemory[]>>;
}

export interface MemoryGraphNode {
  id: number;
  title: string;
  category: MemoryCategory;
  degree: number;
  updated_at: string;
}

export interface MemoryGraphEdge {
  source: number;
  target: number;
}

export interface MemoryGraph {
  nodes: MemoryGraphNode[];
  edges: MemoryGraphEdge[];
}

export interface BrainSettings {
  brain_enabled: boolean;
  brain_use_connectors: boolean;
  brain_focus_instructions: string | null;
  brain_last_run_at: string | null;
}

export interface BrainSettingsUpdate {
  brain_enabled: boolean;
  brain_use_connectors: boolean;
  brain_focus_instructions: string | null;
}

export interface BrainRunTrigger {
  queued: boolean;
  cooldown_seconds: number;
}
