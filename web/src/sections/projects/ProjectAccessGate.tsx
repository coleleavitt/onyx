"use client";

import { useState } from "react";
import { toast } from "@/hooks/useToast";
import { useProjectsContext } from "@/providers/ProjectsContext";
import { Button, Text } from "@opal/components";
import { IllustrationContent } from "@opal/layouts";
import { SvgNotFound, SvgNoAccess } from "@opal/illustrations";
import { SvgSimpleLoader } from "@opal/icons";

export default function ProjectAccessGate() {
  const {
    currentProjectId,
    currentProjectState,
    requestProjectAccess,
    cancelProjectAccessRequest,
    refreshCurrentProjectDetails,
  } = useProjectsContext();
  const [busy, setBusy] = useState(false);

  async function requestAccess() {
    if (!currentProjectId) return;
    setBusy(true);
    try {
      await requestProjectAccess(currentProjectId);
      toast.success("Access requested.");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to request access."
      );
    } finally {
      setBusy(false);
    }
  }

  async function cancelRequest() {
    if (!currentProjectId) return;
    setBusy(true);
    try {
      await cancelProjectAccessRequest(currentProjectId);
      toast.success("Access request canceled.");
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to cancel access request."
      );
    } finally {
      setBusy(false);
    }
  }

  if (currentProjectState.status === "idle") return null;

  if (currentProjectState.status === "loading") {
    return (
      <div className="flex h-full w-full items-center justify-center gap-2">
        <SvgSimpleLoader className="h-5 w-5" />
        <Text color="text-03" font="main-ui-body">
          Loading space...
        </Text>
      </div>
    );
  }

  if (currentProjectState.status === "not-found") {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <IllustrationContent
          illustration={SvgNotFound}
          title="Space not found"
          description="This space doesn't exist or has been deleted."
        />
      </div>
    );
  }

  if (currentProjectState.status === "error") {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <IllustrationContent
          illustration={SvgNoAccess}
          title="Space could not be loaded"
          description={currentProjectState.message}
        />
      </div>
    );
  }

  if (currentProjectState.status !== "access-required") return null;

  const accessRequest = currentProjectState.accessState.access_request;
  const pendingRequest =
    accessRequest?.status === "PENDING" ? accessRequest : null;
  const wasDenied = accessRequest?.status === "DENIED";

  return (
    <div className="flex h-full w-full items-center justify-center px-4">
      <div className="flex max-w-md flex-col items-center gap-4 text-center">
        <IllustrationContent
          illustration={SvgNoAccess}
          title={
            pendingRequest
              ? "Access request pending"
              : wasDenied
                ? "Access request denied"
                : "Request space access"
          }
          description={
            pendingRequest
              ? "The owner can approve your request. You can cancel it at any time."
              : wasDenied
                ? "You can request viewer access again. No space details are shown until access is approved."
                : "Ask the owner for viewer access to this private space. No space details are shown until access is approved."
          }
        />
        <div className="flex items-center gap-2">
          {pendingRequest ? (
            <Button
              disabled={busy}
              onClick={() => void cancelRequest()}
              prominence="secondary"
            >
              Cancel request
            </Button>
          ) : (
            <Button disabled={busy} onClick={() => void requestAccess()}>
              {wasDenied ? "Request again" : "Request access"}
            </Button>
          )}
          <Button
            disabled={busy}
            onClick={() => void refreshCurrentProjectDetails()}
            prominence="tertiary"
          >
            Refresh
          </Button>
          <Button href="/app" prominence="tertiary">
            Start a new chat
          </Button>
        </div>
      </div>
    </div>
  );
}
