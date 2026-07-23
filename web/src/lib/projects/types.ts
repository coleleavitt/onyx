import { ChatFileType, ChatSession } from "@/app/app/interfaces";
import type { MinimalUserSnapshot, ValidSources } from "@/lib/types";

export type ProjectSharePermission = "EDITOR" | "VIEWER";
export type ProjectAccessLevel = "OWNER" | ProjectSharePermission;
export type ProjectJoinRequestStatus = "PENDING" | "APPROVED" | "DENIED";

export interface Project {
  id: number;
  name: string;
  description: string | null;
  emoji: string | null;
  created_at: string;
  updated_at: string | null;
  user_id: string | null;
  owner: MinimalUserSnapshot | null;
  user_permission: ProjectAccessLevel;
  organization_permission: ProjectSharePermission | null;
  is_personal: boolean;
  is_pinned: boolean;
  instructions: string | null;
  chat_sessions: ChatSession[];
}

export interface ProjectUserShare {
  user: MinimalUserSnapshot;
  permission: ProjectSharePermission;
}

export interface ProjectGroupShare {
  group_id: number;
  group_name: string;
  permission: ProjectSharePermission;
}

export interface ProjectJoinRequest {
  id: number;
  requester: MinimalUserSnapshot;
  requested_permission: ProjectSharePermission;
  status: ProjectJoinRequestStatus;
  resolution_comment: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface ProjectSharing {
  owner: MinimalUserSnapshot | null;
  organization_permission: ProjectSharePermission | null;
  user_shares: ProjectUserShare[];
  group_shares: ProjectGroupShare[];
  join_requests: ProjectJoinRequest[];
}

export interface ProjectShareUpdate {
  organization_permission: ProjectSharePermission | null;
  user_shares: Array<{
    user_id: string;
    permission: ProjectSharePermission;
  }>;
  group_shares: Array<{
    group_id: number;
    permission: ProjectSharePermission;
  }>;
}

export interface CreateProjectInput {
  name: string;
  description?: string | null;
  instructions?: string | null;
  emoji?: string | null;
}

export interface ProjectMetadataUpdate {
  name?: string;
  description?: string | null;
  emoji?: string | null;
}

export interface ProjectAccessRequestState {
  id: number;
  requested_permission: ProjectSharePermission;
  status: ProjectJoinRequestStatus;
  created_at: string;
  resolved_at: string | null;
}

export interface ProjectAccessState {
  has_access: boolean;
  access_request: ProjectAccessRequestState | null;
}

export interface CategorizedFiles {
  user_files: ProjectFile[];
  rejected_files: RejectedFile[];
}

export interface ProjectFile {
  id: string;
  name: string;
  project_id: number | null;
  user_id: string | null;
  file_id: string;
  created_at: string;
  status: UserFileStatus;
  file_type: string;
  last_accessed_at: string;
  chat_file_type: ChatFileType;
  token_count: number | null;
  chunk_count: number | null;
  temp_id?: string | null;
}

export interface RejectedFile {
  file_name: string;
  reason: string;
}

export interface UserFileDeleteResult {
  has_associations: boolean;
  project_names: string[];
  assistant_names: string[];
}

export enum UserFileStatus {
  UPLOADING = "UPLOADING", //UI only
  PROCESSING = "PROCESSING",
  COMPLETED = "COMPLETED",
  SKIPPED = "SKIPPED",
  FAILED = "FAILED",
  CANCELED = "CANCELED",
  DELETING = "DELETING",
}

export interface ProjectConnectedDocument {
  id: string;
  title: string;
  link: string | null;
  source: ValidSources | null;
  parent_hierarchy_node_id: number | null;
  last_modified: string | null;
  last_synced: string | null;
}

export interface ProjectConnectedHierarchyNode {
  id: number;
  title: string;
  link: string | null;
  source: ValidSources;
  parent_id: number | null;
}

export interface ProjectConnectedKnowledge {
  documents: ProjectConnectedDocument[];
  hierarchy_nodes: ProjectConnectedHierarchyNode[];
}

export interface ProjectConnectedKnowledgeUpdate {
  document_ids: string[];
  hierarchy_node_ids: number[];
}

export type ProjectDetails = {
  project: Project;
  files?: ProjectFile[];
  connected_knowledge?: ProjectConnectedKnowledge;
  persona_id_to_is_featured?: Record<number, boolean>;
};
