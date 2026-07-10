import { parseErrorDetail } from "@/lib/fetcher";
import type {
  ArtifactLibraryBulkAction,
  ArtifactLibraryItem,
} from "@/app/craft/v1/artifacts/types";

const BASE_URL = "/api/build/artifact-library";
export const PINNED_ARTIFACTS_URL = `${BASE_URL}?scope=all&pinned=true&limit=5`;

async function checkedJson<T>(
  response: Response,
  fallback: string
): Promise<T> {
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response, fallback));
  }
  return response.json() as Promise<T>;
}

export async function saveArtifactToLibrary(input: {
  sessionId: string;
  path: string;
  name?: string;
}): Promise<ArtifactLibraryItem> {
  return checkedJson<ArtifactLibraryItem>(
    await fetch(BASE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: input.sessionId,
        path: input.path,
        name: input.name,
      }),
    }),
    "Failed to save artifact"
  );
}

export async function saveArtifactVersion(
  itemId: string,
  input: { sessionId: string; path: string }
): Promise<ArtifactLibraryItem> {
  return checkedJson<ArtifactLibraryItem>(
    await fetch(`${BASE_URL}/${itemId}/versions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: input.sessionId,
        path: input.path,
      }),
    }),
    "Failed to save artifact version"
  );
}

export async function updateArtifactLibraryItem(
  itemId: string,
  update: { name?: string; published?: boolean }
): Promise<ArtifactLibraryItem> {
  return checkedJson<ArtifactLibraryItem>(
    await fetch(`${BASE_URL}/${itemId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    }),
    "Failed to update artifact"
  );
}

export async function setArtifactLibraryPin(
  itemId: string,
  pinned: boolean
): Promise<ArtifactLibraryItem> {
  return checkedJson<ArtifactLibraryItem>(
    await fetch(`${BASE_URL}/${itemId}/pin`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pinned }),
    }),
    "Failed to update artifact pin"
  );
}

export async function removeSharedArtifact(itemId: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/${itemId}/shared`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, "Failed to remove shared artifact")
    );
  }
}

export async function updateArtifactLibraryShares(
  itemId: string,
  userIds: string[],
  groupIds: number[]
): Promise<ArtifactLibraryItem> {
  return checkedJson<ArtifactLibraryItem>(
    await fetch(`${BASE_URL}/${itemId}/shares`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_ids: userIds, group_ids: groupIds }),
    }),
    "Failed to update artifact sharing"
  );
}

export async function bulkUpdateArtifactLibrary(
  itemIds: string[],
  action: ArtifactLibraryBulkAction
): Promise<void> {
  const response = await fetch(`${BASE_URL}/bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_ids: itemIds, action }),
  });
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, "Failed to update artifacts")
    );
  }
}

export function artifactVersionDownloadUrl(
  itemId: string,
  versionNumber: number
): string {
  return `${BASE_URL}/${itemId}/versions/${versionNumber}/download`;
}
