import type { MinimalUserSnapshot } from "@/lib/types";

export type ArtifactLibraryType =
  | "web_app"
  | "pptx"
  | "docx"
  | "pdf"
  | "image"
  | "markdown"
  | "excel"
  | "csv"
  | "other";

export type ArtifactLibraryScope = "all" | "created" | "shared";

export interface ArtifactLibraryVersion {
  id: string;
  version_number: number;
  name: string;
  path: string;
  mime_type: string | null;
  size_bytes: number | null;
  created_at: string;
}

export interface ArtifactLibraryItem {
  id: string;
  name: string;
  type: ArtifactLibraryType;
  is_pinned: boolean;
  published_at: string | null;
  created_at: string;
  updated_at: string;
  owner: MinimalUserSnapshot;
  is_owner: boolean;
  latest_version: ArtifactLibraryVersion;
  versions: ArtifactLibraryVersion[];
  version_count: number;
  user_shares: Array<{ user: MinimalUserSnapshot }>;
  group_shares: Array<{ group_id: number; group_name: string }>;
}

export interface ArtifactLibraryPage {
  items: ArtifactLibraryItem[];
  next_cursor: string | null;
}

export type ArtifactLibraryBulkAction =
  | "pin"
  | "unpin"
  | "publish"
  | "unpublish"
  | "remove_shared"
  | "delete";
