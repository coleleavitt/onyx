"use client";

import { useEffect, useMemo, useState } from "react";
import useShareableGroups, {
  type MinimalUserGroupSnapshot,
} from "@/hooks/useShareableGroups";
import useShareableUsers from "@/hooks/useShareableUsers";
import { toast } from "@/hooks/useToast";
import {
  getProjectSharing,
  resolveProjectAccessRequest,
  updateProjectSharing,
} from "@/lib/projects/svc";
import type {
  Project,
  ProjectSharePermission,
  ProjectSharing,
} from "@/lib/projects/types";
import type { MinimalUserSnapshot } from "@/lib/types";
import Modal from "@/refresh-components/Modal";
import { AddPeoplePicker } from "@/sections/modals/AddPeoplePicker";
import { ShareAccessRow } from "@/sections/modals/ShareAccessRow";
import { SharePermissionMenu } from "@/sections/modals/SharePermissionMenu";
import { StaticPermissionLabel } from "@/sections/modals/ShareModalPermissionControls";
import {
  PERMISSION_OPTIONS,
  SCOPE_OPTIONS,
} from "@/sections/modals/shareAccessConstants";
import {
  applyStagedShares,
  serializeDraftState,
  type ShareDraftState,
} from "@/sections/modals/shareDraftState";
import { Button, Divider, Text } from "@opal/components";
import {
  SvgCheck,
  SvgLock,
  SvgOrganization,
  SvgShare,
  SvgUser,
  SvgUserManage,
  SvgUsers,
  SvgX,
} from "@opal/icons";
import { markdown } from "@opal/utils";

type ProjectShareDraft = ShareDraftState<ProjectSharePermission>;

interface ShareProjectModalProps {
  project: Project | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

function sharingToDraft(sharing: ProjectSharing): ProjectShareDraft {
  return {
    groupShares: sharing.group_shares,
    isPublic: sharing.organization_permission !== null,
    publicPermission: sharing.organization_permission ?? "VIEWER",
    userShares: sharing.user_shares,
  };
}

export default function ShareProjectModal({
  project,
  open,
  onClose,
  onSaved,
}: ShareProjectModalProps) {
  const { data: users = [] } = useShareableUsers({ includeApiKeys: false });
  const { data: groups = [] } = useShareableGroups();
  const [sharing, setSharing] = useState<ProjectSharing | null>(null);
  const [draft, setDraft] = useState<ProjectShareDraft | null>(null);
  const [initialDraft, setInitialDraft] = useState<ProjectShareDraft | null>(
    null
  );
  const [stagedUsers, setStagedUsers] = useState<MinimalUserSnapshot[]>([]);
  const [stagedGroups, setStagedGroups] = useState<MinimalUserGroupSnapshot[]>(
    []
  );
  const [stagedPermission, setStagedPermission] =
    useState<ProjectSharePermission>("VIEWER");
  const [saving, setSaving] = useState(false);
  const [resolvingRequestId, setResolvingRequestId] = useState<number | null>(
    null
  );
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    if (!open || !project) {
      setSharing(null);
      setDraft(null);
      setInitialDraft(null);
      return;
    }

    let active = true;
    setLoadError(false);
    void getProjectSharing(project.id)
      .then((nextSharing) => {
        if (!active) return;
        const nextDraft = sharingToDraft(nextSharing);
        setSharing(nextSharing);
        setDraft(nextDraft);
        setInitialDraft(nextDraft);
        setStagedUsers([]);
        setStagedGroups([]);
        setStagedPermission("VIEWER");
      })
      .catch(() => {
        if (active) setLoadError(true);
      });

    return () => {
      active = false;
    };
  }, [open, project]);

  const effectiveDraft = useMemo(
    () =>
      draft
        ? applyStagedShares(draft, stagedUsers, stagedGroups, stagedPermission)
        : null,
    [draft, stagedGroups, stagedPermission, stagedUsers]
  );
  const isDirty =
    !!effectiveDraft &&
    !!initialDraft &&
    serializeDraftState(effectiveDraft) !== serializeDraftState(initialDraft);
  const existingUserIds = useMemo(() => {
    const ids = new Set(draft?.userShares.map((share) => share.user.id));
    if (sharing?.owner?.id) ids.add(sharing.owner.id);
    return ids;
  }, [draft?.userShares, sharing?.owner?.id]);
  const existingGroupIds = useMemo(
    () => new Set(draft?.groupShares.map((share) => share.group_id)),
    [draft?.groupShares]
  );
  const pendingRequests =
    sharing?.join_requests.filter((request) => request.status === "PENDING") ??
    [];

  function updateUserPermission(
    userId: string,
    permission: ProjectSharePermission
  ) {
    const stagedUser = stagedUsers.find((user) => user.id === userId);
    if (stagedUser) {
      setStagedUsers((current) => current.filter((user) => user.id !== userId));
      setDraft((current) =>
        current
          ? {
              ...current,
              userShares: [
                ...current.userShares.filter(
                  (share) => share.user.id !== userId
                ),
                { user: stagedUser, permission },
              ],
            }
          : current
      );
      return;
    }
    setDraft((current) =>
      current
        ? {
            ...current,
            userShares: current.userShares.map((share) =>
              share.user.id === userId ? { ...share, permission } : share
            ),
          }
        : current
    );
  }

  function updateGroupPermission(
    groupId: number,
    permission: ProjectSharePermission
  ) {
    const stagedGroup = stagedGroups.find((group) => group.id === groupId);
    if (stagedGroup) {
      setStagedGroups((current) =>
        current.filter((group) => group.id !== groupId)
      );
      setDraft((current) =>
        current
          ? {
              ...current,
              groupShares: [
                ...current.groupShares.filter(
                  (share) => share.group_id !== groupId
                ),
                {
                  group_id: stagedGroup.id,
                  group_name: stagedGroup.name,
                  permission,
                },
              ],
            }
          : current
      );
      return;
    }
    setDraft((current) =>
      current
        ? {
            ...current,
            groupShares: current.groupShares.map((share) =>
              share.group_id === groupId ? { ...share, permission } : share
            ),
          }
        : current
    );
  }

  async function save() {
    if (!project || !effectiveDraft) return;
    setSaving(true);
    try {
      const nextSharing = await updateProjectSharing(project.id, {
        organization_permission: effectiveDraft.isPublic
          ? effectiveDraft.publicPermission
          : null,
        user_shares: effectiveDraft.userShares.map((share) => ({
          user_id: share.user.id,
          permission: share.permission,
        })),
        group_shares: effectiveDraft.groupShares.map((share) => ({
          group_id: share.group_id,
          permission: share.permission,
        })),
      });
      const nextDraft = sharingToDraft(nextSharing);
      setSharing(nextSharing);
      setDraft(nextDraft);
      setInitialDraft(nextDraft);
      toast.success("Project sharing updated.");
      onSaved();
      onClose();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to update sharing"
      );
    } finally {
      setSaving(false);
    }
  }

  async function resolveRequest(requestId: number, approve: boolean) {
    if (!project) return;
    setResolvingRequestId(requestId);
    try {
      const nextSharing = await resolveProjectAccessRequest(
        project.id,
        requestId,
        approve
      );
      setSharing(nextSharing);
      const nextDraft = sharingToDraft(nextSharing);
      setDraft(nextDraft);
      setInitialDraft(nextDraft);
      toast.success(approve ? "Access approved." : "Access request denied.");
      onSaved();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to resolve request"
      );
    } finally {
      setResolvingRequestId(null);
    }
  }

  if (!project) return null;

  return (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <Modal.Content height="lg" width="md">
        <Modal.Header
          icon={SvgShare}
          title={markdown(`Share *${project.name}*`)}
          onClose={onClose}
        />
        <Modal.Body>
          {loadError ? (
            <Text color="status-error-05" font="secondary-body">
              Project sharing could not be loaded.
            </Text>
          ) : !sharing || !effectiveDraft ? (
            <div className="flex w-full justify-center py-6">
              <Text color="text-03" font="secondary-body">
                Loading sharing details...
              </Text>
            </div>
          ) : (
            <div className="flex w-full flex-col gap-3">
              <AddPeoplePicker
                existingGroupIds={existingGroupIds}
                existingUserIds={existingUserIds}
                groups={groups}
                onAddGroup={(group) =>
                  setStagedGroups((current) => [...current, group])
                }
                onAddUser={(user) =>
                  setStagedUsers((current) => [...current, user])
                }
                onRemoveGroup={(groupId) =>
                  setStagedGroups((current) =>
                    current.filter((group) => group.id !== groupId)
                  )
                }
                onRemoveUser={(userId) =>
                  setStagedUsers((current) =>
                    current.filter((user) => user.id !== userId)
                  )
                }
                onStagedPermissionChange={setStagedPermission}
                stagedGroups={stagedGroups}
                stagedPermission={stagedPermission}
                stagedUsers={stagedUsers}
                users={users}
              />

              <div className="flex w-full flex-col gap-2 rounded-12 bg-background-tint-00 p-1">
                <ShareAccessRow
                  icon={effectiveDraft.isPublic ? SvgOrganization : SvgLock}
                  titleSlot={
                    <SharePermissionMenu
                      ariaLabel="Change project sharing scope"
                      menuWidth="2xl"
                      onChange={(scope) =>
                        setDraft((current) =>
                          current
                            ? { ...current, isPublic: scope === "PUBLIC" }
                            : current
                        )
                      }
                      options={SCOPE_OPTIONS}
                      showTriggerIcon={false}
                      value={effectiveDraft.isPublic ? "PUBLIC" : "PRIVATE"}
                    />
                  }
                  rightChildren={
                    <SharePermissionMenu
                      ariaLabel="Change organization permission"
                      onChange={(permission) =>
                        setDraft((current) =>
                          current
                            ? { ...current, publicPermission: permission }
                            : current
                        )
                      }
                      options={PERMISSION_OPTIONS}
                      value={effectiveDraft.publicPermission}
                    />
                  }
                />

                <Divider paddingParallel="fit" paddingPerpendicular="fit" />

                {sharing.owner && (
                  <ShareAccessRow
                    avatarInitial={sharing.owner.email.charAt(0).toUpperCase()}
                    icon={SvgUser}
                    rightChildren={
                      <StaticPermissionLabel
                        icon={SvgUserManage}
                        label="Owner"
                      />
                    }
                    title={sharing.owner.email}
                  />
                )}

                {effectiveDraft.userShares.map((share) => (
                  <ShareAccessRow
                    avatarInitial={share.user.email.charAt(0).toUpperCase()}
                    icon={SvgUser}
                    key={share.user.id}
                    rightChildren={
                      <SharePermissionMenu
                        ariaLabel={`Update access for ${share.user.email}`}
                        onChange={(permission) =>
                          updateUserPermission(share.user.id, permission)
                        }
                        onRemove={() =>
                          setDraft((current) =>
                            current
                              ? {
                                  ...current,
                                  userShares: current.userShares.filter(
                                    (candidate) =>
                                      candidate.user.id !== share.user.id
                                  ),
                                }
                              : current
                          )
                        }
                        options={PERMISSION_OPTIONS}
                        value={share.permission}
                      />
                    }
                    title={share.user.email}
                  />
                ))}

                {effectiveDraft.groupShares.map((share) => (
                  <ShareAccessRow
                    avatarIcon={SvgUsers}
                    icon={SvgUsers}
                    key={share.group_id}
                    rightChildren={
                      <SharePermissionMenu
                        ariaLabel={`Update access for ${share.group_name}`}
                        onChange={(permission) =>
                          updateGroupPermission(share.group_id, permission)
                        }
                        onRemove={() =>
                          setDraft((current) =>
                            current
                              ? {
                                  ...current,
                                  groupShares: current.groupShares.filter(
                                    (candidate) =>
                                      candidate.group_id !== share.group_id
                                  ),
                                }
                              : current
                          )
                        }
                        options={PERMISSION_OPTIONS}
                        value={share.permission}
                      />
                    }
                    title={share.group_name}
                  />
                ))}
              </div>

              {pendingRequests.length > 0 && (
                <div className="flex w-full flex-col gap-2">
                  <Text color="text-03" font="secondary-action">
                    Access requests
                  </Text>
                  {pendingRequests.map((request) => (
                    <ShareAccessRow
                      avatarInitial={request.requester.email
                        .charAt(0)
                        .toUpperCase()}
                      icon={SvgUser}
                      key={request.id}
                      rightChildren={
                        <div className="flex items-center gap-1">
                          <Button
                            disabled={resolvingRequestId !== null}
                            icon={SvgX}
                            onClick={() =>
                              void resolveRequest(request.id, false)
                            }
                            prominence="tertiary"
                            size="sm"
                            tooltip="Deny access"
                          />
                          <Button
                            disabled={resolvingRequestId !== null}
                            icon={SvgCheck}
                            onClick={() =>
                              void resolveRequest(request.id, true)
                            }
                            prominence="secondary"
                            size="sm"
                            tooltip="Approve access"
                          />
                        </div>
                      }
                      description={`Requested ${request.requested_permission.toLowerCase()} access`}
                      title={request.requester.email}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button disabled={saving} onClick={onClose} prominence="secondary">
            Cancel
          </Button>
          <Button
            disabled={!isDirty || saving || loadError}
            onClick={() => void save()}
          >
            Save
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
