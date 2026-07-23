import { ValidSources } from "@/lib/types";

// Sort options for document pagination
export type DocumentSortField = "name" | "last_updated";
export type DocumentSortDirection = "asc" | "desc";
export type FolderPosition = "on_top" | "mixed";

export type ConnectedSourceCurationStatus =
  | "DEFAULT_SAFE"
  | "STANDARD"
  | "ARCHIVE"
  | "HIDDEN"
  | "DIAGNOSTIC";

export interface HierarchyNodeGovernance {
  curation_status: ConnectedSourceCurationStatus | null;
  is_default: boolean;
  is_archived: boolean;
  is_hidden: boolean;
  is_diagnostic: boolean;
  is_selectable: boolean;
  denial_reason: string | null;
  display_label: string | null;
  tenant_label: string | null;
  department_label: string | null;
  sort_order: number;
  size_bytes: number | null;
  document_count_estimate: number | null;
  indexed_document_count: number;
  indexed_chunk_count: number;
  indexing_status: string | null;
  last_synced_at: string | null;
  warning: string | null;
  allowed_group_ids: number[];
  excluded_hierarchy_node_ids: number[];
}

// Hierarchy Node types matching backend models
export interface HierarchyNodeSummary {
  id: number;
  title: string;
  link: string | null;
  parent_id: number | null;
  governance: HierarchyNodeGovernance | null;
}

export interface HierarchyNodesRequest {
  source: ValidSources;
}

export interface HierarchyNodesResponse {
  nodes: HierarchyNodeSummary[];
}

// Document types for hierarchy
export interface DocumentPageCursor {
  // Fields for last_updated sorting
  last_modified?: string | null;
  last_synced?: string | null;
  // Field for name sorting
  name?: string | null;
  // Document ID for tie-breaking (always required)
  document_id: string;
}

export interface HierarchyNodeDocumentsRequest {
  parent_hierarchy_node_id: number;
  cursor?: DocumentPageCursor | null;
  sort_field?: DocumentSortField;
  sort_direction?: DocumentSortDirection;
  folder_position?: FolderPosition;
}

export interface DocumentSummary {
  id: string;
  title: string;
  link: string | null;
  parent_id: number | null;
  last_modified: string | null;
  last_synced: string | null;
}

export interface HierarchyNodeDocumentsResponse {
  documents: DocumentSummary[];
  next_cursor: DocumentPageCursor | null;
  page_size: number;
  sort_field: DocumentSortField;
  sort_direction: DocumentSortDirection;
  folder_position: FolderPosition;
}

// Connected source type for display
export interface ConnectedSource {
  source: ValidSources;
  connectorCount: number;
}

// Union type for folders and documents in hierarchy tables
export type HierarchyItem =
  | { type: "folder"; data: HierarchyNodeSummary }
  | { type: "document"; data: DocumentSummary };

// Props for hierarchy breadcrumb navigation
export interface HierarchyBreadcrumbProps {
  source: ValidSources;
  path: HierarchyNodeSummary[];
  onNavigateToRoot: () => void;
  onNavigateToNode: (node: HierarchyNodeSummary, index: number) => void;
}

// Search result type — includes source for icon display
export interface HierarchyNodeSearchSummary {
  id: number;
  title: string;
  link: string | null;
  parent_id: number | null;
  source: ValidSources;
}

export interface HierarchyNodeSearchResponse {
  nodes: HierarchyNodeSearchSummary[];
}
