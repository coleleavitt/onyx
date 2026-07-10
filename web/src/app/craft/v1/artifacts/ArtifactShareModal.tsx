"use client";

import { useMemo, useState } from "react";
import type { MinimalUserSnapshot } from "@/lib/types";
import useShareableGroups, {
  type MinimalUserGroupSnapshot,
} from "@/hooks/useShareableGroups";
import useShareableUsers from "@/hooks/useShareableUsers";
import { toast } from "@/hooks/useToast";
import Modal from "@/refresh-components/Modal";
import { AddPeoplePicker } from "@/sections/modals/AddPeoplePicker";
import { ShareAccessRow } from "@/sections/modals/ShareAccessRow";
import { Button, Divider, Text } from "@opal/components";
import { SvgShare, SvgUser, SvgUsers, SvgX } from "@opal/icons";
import { updateArtifactLibraryShares } from "@/app/craft/v1/artifacts/api";
import type { ArtifactLibraryItem } from "@/app/craft/v1/artifacts/types";

interface ArtifactShareModalProps {
  item: ArtifactLibraryItem;
  onClose: () => void;
  onSaved: (item: ArtifactLibraryItem) => void;
}

export default function ArtifactShareModal({
  item,
  onClose,
  onSaved,
}: ArtifactShareModalProps) {
  const { data: users = [] } = useShareableUsers({ includeApiKeys: false });
  const { data: groups = [] } = useShareableGroups();
  const [selectedUsers, setSelectedUsers] = useState<MinimalUserSnapshot[]>(
    item.user_shares.map((share) => share.user)
  );
  const [selectedGroups, setSelectedGroups] = useState<
    MinimalUserGroupSnapshot[]
  >(
    item.group_shares.map((share) => ({
      id: share.group_id,
      name: share.group_name,
    }))
  );
  const [stagedUsers, setStagedUsers] = useState<MinimalUserSnapshot[]>([]);
  const [stagedGroups, setStagedGroups] = useState<MinimalUserGroupSnapshot[]>(
    []
  );
  const [saving, setSaving] = useState(false);

  const existingUserIds = useMemo(
    () => new Set([item.owner.id, ...selectedUsers.map((user) => user.id)]),
    [item.owner.id, selectedUsers]
  );
  const existingGroupIds = useMemo(
    () => new Set(selectedGroups.map((group) => group.id)),
    [selectedGroups]
  );

  async function save() {
    setSaving(true);
    try {
      const next = await updateArtifactLibraryShares(
        item.id,
        [...selectedUsers, ...stagedUsers].map((user) => user.id),
        [...selectedGroups, ...stagedGroups].map((group) => group.id)
      );
      toast.success("Artifact sharing updated.");
      onSaved(next);
      onClose();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to update sharing"
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content width="md" height="lg">
        <Modal.Header
          icon={SvgShare}
          title={`Share ${item.name}`}
          description="Give people or groups view access to every version of this artifact."
        />
        <Modal.Body>
          <div className="flex w-full flex-col gap-3">
            <AddPeoplePicker
              existingGroupIds={existingGroupIds}
              existingUserIds={existingUserIds}
              fixedPermissionLabel="Viewer"
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
              onStagedPermissionChange={() => undefined}
              stagedGroups={stagedGroups}
              stagedPermission="VIEWER"
              stagedUsers={stagedUsers}
              users={users}
            />
            <Divider />
            <ShareAccessRow
              avatarInitial={item.owner.email.charAt(0).toUpperCase()}
              icon={SvgUser}
              rightChildren={
                <Text color="text-03" font="secondary-body">
                  Owner
                </Text>
              }
              title={item.owner.email}
            />
            {selectedUsers.map((user) => (
              <ShareAccessRow
                avatarInitial={user.email.charAt(0).toUpperCase()}
                icon={SvgUser}
                key={user.id}
                rightChildren={
                  <div className="flex items-center gap-1">
                    <Text color="text-03" font="secondary-body">
                      Viewer
                    </Text>
                    <Button
                      icon={SvgX}
                      prominence="tertiary"
                      size="2xs"
                      tooltip="Remove access"
                      onClick={() =>
                        setSelectedUsers((current) =>
                          current.filter(
                            (candidate) => candidate.id !== user.id
                          )
                        )
                      }
                    />
                  </div>
                }
                title={user.email}
              />
            ))}
            {selectedGroups.map((group) => (
              <ShareAccessRow
                avatarIcon={SvgUsers}
                icon={SvgUsers}
                key={group.id}
                rightChildren={
                  <div className="flex items-center gap-1">
                    <Text color="text-03" font="secondary-body">
                      Viewer
                    </Text>
                    <Button
                      icon={SvgX}
                      prominence="tertiary"
                      size="2xs"
                      tooltip="Remove access"
                      onClick={() =>
                        setSelectedGroups((current) =>
                          current.filter(
                            (candidate) => candidate.id !== group.id
                          )
                        )
                      }
                    />
                  </div>
                }
                title={group.name}
              />
            ))}
          </div>
        </Modal.Body>
        <Modal.Footer>
          <div className="flex w-full justify-end gap-2">
            <Button prominence="secondary" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={() => void save()} disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </Button>
          </div>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
