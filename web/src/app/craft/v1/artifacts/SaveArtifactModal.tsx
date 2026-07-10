"use client";

import { useState } from "react";
import useSWR from "swr";
import { toast } from "@/hooks/useToast";
import { errorHandlingFetcher } from "@/lib/fetcher";
import Modal from "@/refresh-components/Modal";
import InputSelect from "@/refresh-components/inputs/InputSelect";
import {
  saveArtifactToLibrary,
  saveArtifactVersion,
} from "@/app/craft/v1/artifacts/api";
import type { ArtifactLibraryItem } from "@/app/craft/v1/artifacts/types";
import { Button, InputTypeIn, Text } from "@opal/components";
import { SvgFiles } from "@opal/icons";

interface SaveArtifactModalProps {
  sessionId: string;
  path: string;
  suggestedName: string;
  onClose: () => void;
}

export default function SaveArtifactModal({
  sessionId,
  path,
  suggestedName,
  onClose,
}: SaveArtifactModalProps) {
  const [name, setName] = useState(suggestedName);
  const [destination, setDestination] = useState("new");
  const [saving, setSaving] = useState(false);
  const { data: ownedItems = [] } = useSWR<ArtifactLibraryItem[]>(
    "/api/build/artifact-library?scope=created",
    errorHandlingFetcher
  );

  async function save() {
    setSaving(true);
    try {
      if (destination === "new") {
        await saveArtifactToLibrary({ sessionId, path, name });
        toast.success("Artifact saved to your library.");
      } else {
        const item = ownedItems.find(
          (candidate) => candidate.id === destination
        );
        await saveArtifactVersion(destination, { sessionId, path });
        toast.success(
          `Saved a new version of ${item?.name ?? "the artifact"}.`
        );
      }
      onClose();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to save artifact"
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content width="sm">
        <Modal.Header
          icon={SvgFiles}
          title="Save to artifact library"
          description="Keep this output available after the Craft session ends."
        />
        <Modal.Body>
          <div className="flex w-full flex-col gap-4">
            <div className="flex flex-col gap-1">
              <Text color="text-04" font="main-ui-action">
                Destination
              </Text>
              <InputSelect value={destination} onValueChange={setDestination}>
                <InputSelect.Trigger />
                <InputSelect.Content>
                  <InputSelect.Item value="new">New artifact</InputSelect.Item>
                  {ownedItems.map((item) => (
                    <InputSelect.Item key={item.id} value={item.id}>
                      New version of {item.name}
                    </InputSelect.Item>
                  ))}
                </InputSelect.Content>
              </InputSelect>
            </div>
            {destination === "new" ? (
              <div className="flex flex-col gap-1">
                <Text color="text-04" font="main-ui-action">
                  Name
                </Text>
                <InputTypeIn
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Artifact name"
                />
              </div>
            ) : null}
          </div>
        </Modal.Body>
        <Modal.Footer>
          <div className="flex w-full justify-end gap-2">
            <Button prominence="secondary" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button
              onClick={() => void save()}
              disabled={saving || (destination === "new" && !name.trim())}
            >
              {saving ? "Saving..." : "Save"}
            </Button>
          </div>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
