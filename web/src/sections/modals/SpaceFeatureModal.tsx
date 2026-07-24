"use client";

import { useState } from "react";
import { toast } from "@opal/layouts";
import Modal from "@/refresh-components/Modal";
import { Button } from "@opal/components";
import { SvgGlobe } from "@opal/icons";
import { useProjectsContext } from "@/providers/ProjectsContext";
import { useUserGroups } from "@/lib/hooks";
import { setProjectFeaturing } from "@/lib/projects/svc";

interface SpaceFeatureModalProps {
  projectId: number;
  open: boolean;
  onClose: () => void;
}

// F2: admin control to feature a space to the whole org and/or a department
// group. Featuring auto-surfaces the space in entitled members' sidebars but
// grants no access on its own (PUT /user/projects/{id}/featuring).
export default function SpaceFeatureModal({
  projectId,
  open,
  onClose,
}: SpaceFeatureModalProps) {
  const { fetchProjects } = useProjectsContext();
  const { data: groups } = useUserGroups();
  const [isOrgFeatured, setIsOrgFeatured] = useState(false);
  const [groupId, setGroupId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await setProjectFeaturing(projectId, isOrgFeatured, groupId);
      await fetchProjects();
      toast.success("Featuring updated.");
      onClose();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to update featuring.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onOpenChange={(next) => !next && onClose()}>
      <Modal.Content width="md">
        <Modal.Header
          icon={SvgGlobe}
          title="Feature this space"
          description="Featured spaces auto-appear in entitled members' sidebars. Featuring grants no access on its own."
          onClose={onClose}
        />
        <Modal.Body alignItems="stretch">
          <div className="flex flex-col gap-4 p-1">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={isOrgFeatured}
                onChange={(event) => setIsOrgFeatured(event.target.checked)}
              />
              <span>Feature for everyone in the organization</span>
            </label>
            <label className="flex flex-col gap-1">
              <span>Feature for a department group</span>
              <select
                className="rounded-08 border border-border bg-background px-2 py-1"
                value={groupId ?? ""}
                onChange={(event) =>
                  setGroupId(
                    event.target.value ? Number(event.target.value) : null,
                  )
                }
              >
                <option value="">None</option>
                {(groups ?? []).map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Button
            prominence="secondary"
            type="button"
            onClick={onClose}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button type="button" onClick={handleSave} disabled={saving}>
            Save
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
