import { FetchError } from "@/lib/fetcher";
import type {
  Project,
  CategorizedFiles,
  ProjectFile,
  RejectedFile,
  UserFileDeleteResult,
  UserFileStatus,
  ProjectDetails,
  ProjectSharing,
  ProjectShareUpdate,
  CreateProjectInput,
  ProjectMetadataUpdate,
  ProjectAccessState,
  ConnectedKnowledgePreset,
  ConnectedSourceScope,
  ProjectConnectedKnowledge,
  ProjectConnectedKnowledgeUpdate,
  ProjectJoinRequest,
} from "@/lib/projects/types";

const handleRequestError = async (
  action: string,
  response: Response
): Promise<never> => {
  let info: unknown = null;
  try {
    info = await response.json();
  } catch {
    info = null;
  }
  const detail =
    info && typeof info === "object" && "detail" in info
      ? String((info as { detail?: unknown }).detail)
      : `${action} failed (Status: ${response.status})`;
  throw new FetchError(detail, response.status, info);
};

export async function fetchProjects(): Promise<Project[]> {
  const response = await fetch("/api/user/projects");
  if (!response.ok) {
    await handleRequestError("Fetch projects", response);
  }
  return response.json();
}

export async function createProject(
  input: string | CreateProjectInput
): Promise<Project> {
  const createInput =
    typeof input === "string" ? { name: input, description: null } : input;
  const params = new URLSearchParams({ name: createInput.name });
  if (
    createInput.description !== undefined &&
    createInput.description !== null
  ) {
    params.set("description", createInput.description);
  }
  if (
    createInput.instructions !== undefined &&
    createInput.instructions !== null &&
    createInput.instructions !== ""
  ) {
    params.set("instructions", createInput.instructions);
  }
  if (
    createInput.emoji !== undefined &&
    createInput.emoji !== null &&
    createInput.emoji !== ""
  ) {
    params.set("emoji", createInput.emoji);
  }
  if (createInput.connected_knowledge_preset_id != null) {
    params.set(
      "connected_knowledge_preset_id",
      String(createInput.connected_knowledge_preset_id)
    );
  }
  const response = await fetch(
    `/api/user/projects/create?${params.toString()}`,
    {
      method: "POST",
    }
  );
  if (!response.ok) {
    await handleRequestError("Create project", response);
  }
  return response.json();
}

export async function fetchConnectedKnowledgePresets(): Promise<
  ConnectedKnowledgePreset[]
> {
  const response = await fetch("/api/user/projects/connected-knowledge-presets");
  if (!response.ok) {
    await handleRequestError("Fetch connected knowledge presets", response);
  }
  return response.json();
}

export interface CreateConnectedKnowledgePresetRequest {
  name: string;
  description?: string | null;
  emoji?: string | null;
  instructions?: string | null;
  document_ids: string[];
  hierarchy_node_ids: number[];
}

export async function createConnectedKnowledgePreset(
  request: CreateConnectedKnowledgePresetRequest
): Promise<ConnectedKnowledgePreset> {
  const response = await fetch(
    "/api/user/projects/connected-knowledge-presets",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }
  );
  if (!response.ok) {
    await handleRequestError("Create connected knowledge preset", response);
  }
  return response.json();
}

export async function fetchConnectedSourceScopes(): Promise<
  ConnectedSourceScope[]
> {
  const response = await fetch("/api/user/projects/connected-source-scopes");
  if (!response.ok) {
    await handleRequestError("Fetch connected source scopes", response);
  }
  return response.json();
}

export async function updateConnectedSourceScope(
  scope: ConnectedSourceScope
): Promise<ConnectedSourceScope> {
  const response = await fetch(
    `/api/user/projects/connected-source-scopes/${scope.hierarchy_node_id}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        access_type: scope.access_type,
        curation_status: scope.curation_status,
        display_label: scope.display_label,
        tenant_label: scope.tenant_label,
        department_label: scope.department_label,
        sort_order: scope.sort_order,
        size_bytes: scope.size_bytes,
        document_count_estimate: scope.document_count_estimate,
        warning: scope.warning,
        group_ids: scope.group_ids,
        excluded_hierarchy_node_ids: scope.excluded_hierarchy_node_ids,
      }),
    }
  );
  if (!response.ok) {
    await handleRequestError("Update connected source scope", response);
  }
  return response.json();
}

export async function uploadFiles(
  files: File[],
  projectId?: number | null,
  tempIdMap?: Map<string, string>
): Promise<CategorizedFiles> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  if (projectId !== undefined && projectId !== null) {
    formData.append("project_id", String(projectId));
  }
  if (tempIdMap !== undefined && tempIdMap !== null) {
    formData.append(
      "temp_id_map",
      JSON.stringify(Object.fromEntries(tempIdMap))
    );
  }

  const response = await fetch("/api/user/projects/file/upload", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    await handleRequestError("Upload files", response);
  }

  return response.json();
}

export async function getRecentFiles(): Promise<ProjectFile[]> {
  const response = await fetch(`/api/user/files/recent`);
  if (!response.ok) {
    await handleRequestError("Fetch recent files", response);
  }
  return response.json();
}

export async function getFilesInProject(
  projectId: number
): Promise<ProjectFile[]> {
  const response = await fetch(`/api/user/projects/files/${projectId}`);
  if (!response.ok) {
    await handleRequestError("Fetch project files", response);
  }
  return response.json();
}

export async function getProject(projectId: number): Promise<Project> {
  const response = await fetch(`/api/user/projects/${projectId}`);
  if (!response.ok) {
    await handleRequestError("Fetch project", response);
  }
  return response.json();
}

export async function getProjectSharing(
  projectId: number
): Promise<ProjectSharing> {
  const response = await fetch(`/api/user/projects/${projectId}/sharing`);
  if (!response.ok) {
    await handleRequestError("Fetch project sharing", response);
  }
  return response.json();
}

export async function updateProjectSharing(
  projectId: number,
  sharing: ProjectShareUpdate
): Promise<ProjectSharing> {
  const response = await fetch(`/api/user/projects/${projectId}/sharing`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(sharing),
  });
  if (!response.ok) {
    await handleRequestError("Update project sharing", response);
  }
  return response.json();
}

export async function resolveProjectAccessRequest(
  projectId: number,
  requestId: number,
  approve: boolean
): Promise<ProjectSharing> {
  const response = await fetch(
    `/api/user/projects/${projectId}/join-requests/${requestId}/resolve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approve }),
    }
  );
  if (!response.ok) {
    await handleRequestError("Resolve project access request", response);
  }
  return response.json();
}

export async function updateProjectMetadata(
  projectId: number,
  metadata: ProjectMetadataUpdate
): Promise<Project> {
  const response = await fetch(`/api/user/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(metadata),
  });
  if (!response.ok) {
    await handleRequestError("Update project", response);
  }
  return response.json();
}

export async function renameProject(
  projectId: number,
  name: string
): Promise<Project> {
  return updateProjectMetadata(projectId, { name });
}

export async function fetchProjectAccessState(
  projectId: number
): Promise<ProjectAccessState> {
  const response = await fetch(`/api/user/projects/${projectId}/access-state`);
  if (!response.ok) {
    await handleRequestError("Fetch project access state", response);
  }
  return response.json();
}

export async function requestProjectAccess(
  projectId: number
): Promise<ProjectJoinRequest> {
  const response = await fetch(
    `/api/user/projects/${projectId}/request-access`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ requested_permission: "VIEWER" }),
    }
  );
  if (!response.ok) {
    await handleRequestError("Request project access", response);
  }
  return response.json();
}

export async function cancelProjectAccessRequest(
  projectId: number
): Promise<void> {
  const response = await fetch(
    `/api/user/projects/${projectId}/request-access`,
    {
      method: "DELETE",
    }
  );
  if (!response.ok) {
    await handleRequestError("Cancel project access request", response);
  }
}

export async function setProjectPinned(
  projectId: number,
  pinned: boolean
): Promise<Project> {
  const response = await fetch(`/api/user/projects/${projectId}/pin`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pinned }),
  });
  if (!response.ok) {
    await handleRequestError("Update space pin", response);
  }
  return response.json();
}

export async function deleteProject(projectId: number): Promise<void> {
  const response = await fetch(`/api/user/projects/${projectId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    await handleRequestError("Delete project", response);
  }
}

export async function getProjectInstructions(
  projectId: number
): Promise<string | null> {
  const response = await fetch(`/api/user/projects/${projectId}/instructions`);
  if (!response.ok) {
    await handleRequestError("Fetch project instructions", response);
  }
  const data = (await response.json()) as { instructions: string | null };
  return data.instructions ?? null;
}

export async function upsertProjectInstructions(
  projectId: number,
  instructions: string
): Promise<string | null> {
  const response = await fetch(`/api/user/projects/${projectId}/instructions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instructions }),
  });
  if (!response.ok) {
    await handleRequestError("Update project instructions", response);
  }
  const data = (await response.json()) as { instructions: string | null };
  return data.instructions ?? null;
}

export async function getProjectDetails(
  projectId: number
): Promise<ProjectDetails> {
  const response = await fetch(`/api/user/projects/${projectId}/details`);
  if (!response.ok) {
    await handleRequestError("Fetch project details", response);
  }
  return response.json();
}

export async function getProjectConnectedKnowledge(
  projectId: number
): Promise<ProjectConnectedKnowledge> {
  const response = await fetch(
    `/api/user/projects/${encodeURIComponent(projectId)}/connected-knowledge`
  );
  if (!response.ok) {
    await handleRequestError("Fetch project connected knowledge", response);
  }
  return response.json();
}

export async function updateProjectConnectedKnowledge(
  projectId: number,
  knowledge: ProjectConnectedKnowledgeUpdate
): Promise<ProjectConnectedKnowledge> {
  const response = await fetch(
    `/api/user/projects/${encodeURIComponent(projectId)}/connected-knowledge`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(knowledge),
    }
  );
  if (!response.ok) {
    await handleRequestError("Update project connected knowledge", response);
  }
  return response.json();
}

export async function unlinkFileFromProject(
  projectId: number,
  fileId: string
): Promise<Response> {
  const response = await fetch(
    `/api/user/projects/${encodeURIComponent(
      projectId
    )}/files/${encodeURIComponent(fileId)}`,
    { method: "DELETE" }
  );
  if (!response.ok) {
    await handleRequestError("Unlink file from project", response);
  }
  return response;
}

export async function linkFileToProject(
  projectId: number,
  fileId: string
): Promise<Response> {
  const response = await fetch(
    `/api/user/projects/${encodeURIComponent(
      projectId
    )}/files/${encodeURIComponent(fileId)}`,
    { method: "POST" }
  );
  if (!response.ok) {
    await handleRequestError("Link file to project", response);
  }
  return response;
}

export async function deleteUserFile(
  fileId: string
): Promise<UserFileDeleteResult> {
  const response = await fetch(
    `/api/user/projects/file/${encodeURIComponent(fileId)}`,
    {
      method: "DELETE",
    }
  );
  if (!response.ok) {
    await handleRequestError("Delete file", response);
  }
  return (await response.json()) as UserFileDeleteResult;
}

export async function getUserFileStatuses(
  fileIds: string[]
): Promise<ProjectFile[]> {
  const response = await fetch(`/api/user/projects/file/statuses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_ids: fileIds }),
  });
  if (!response.ok) {
    await handleRequestError("Fetch file statuses", response);
  }
  return response.json();
}

export async function getSessionProjectTokenCount(
  chatSessionId: string
): Promise<number> {
  const response = await fetch(
    `/api/user/projects/session/${encodeURIComponent(
      chatSessionId
    )}/token-count`
  );
  if (!response.ok) {
    return 0;
  }
  const data = (await response.json()) as { total_tokens: number };
  return data.total_tokens ?? 0;
}

export async function getProjectFilesForSession(
  chatSessionId: string
): Promise<ProjectFile[]> {
  const response = await fetch(
    `/api/user/projects/session/${encodeURIComponent(chatSessionId)}/files`
  );
  if (!response.ok) {
    return [];
  }
  return response.json();
}

export async function getProjectTokenCount(projectId: number): Promise<number> {
  const response = await fetch(
    `/api/user/projects/${encodeURIComponent(projectId)}/token-count`
  );
  if (!response.ok) {
    return 0;
  }
  const data = (await response.json()) as { total_tokens: number };
  return data.total_tokens ?? 0;
}

export async function getMaxSelectedDocumentTokens(
  personaId: number
): Promise<number | null> {
  const response = await fetch(
    `/api/chat/max-selected-document-tokens?persona_id=${personaId}`
  );
  if (!response.ok) {
    return null;
  }
  const json = await response.json();
  return (json?.max_tokens as number) ?? null;
}

export async function moveChatSession(
  projectId: number,
  chatSessionId: string
): Promise<boolean> {
  const response = await fetch(
    `/api/user/projects/${projectId}/move_chat_session`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_session_id: chatSessionId }),
    }
  );
  if (!response.ok) {
    await handleRequestError("Move chat session", response);
  }
  return response.ok;
}

export async function removeChatSessionFromProject(
  chatSessionId: string
): Promise<boolean> {
  const response = await fetch(`/api/user/projects/remove_chat_session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_session_id: chatSessionId }),
  });
  if (!response.ok) {
    await handleRequestError("Remove chat session from project", response);
  }
  return response.ok;
}
