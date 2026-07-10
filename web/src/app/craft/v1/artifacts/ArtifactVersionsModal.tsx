"use client";

import Modal from "@/refresh-components/Modal";
import { artifactVersionDownloadUrl } from "@/app/craft/v1/artifacts/api";
import type { ArtifactLibraryItem } from "@/app/craft/v1/artifacts/types";
import { Button, Divider, Text } from "@opal/components";
import { SvgDownload, SvgHistory } from "@opal/icons";

interface ArtifactVersionsModalProps {
  item: ArtifactLibraryItem;
  onClose: () => void;
}

function formatBytes(size: number | null): string {
  if (size === null) return "Size unavailable";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ArtifactVersionsModal({
  item,
  onClose,
}: ArtifactVersionsModalProps) {
  return (
    <Modal open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content width="md" height="lg">
        <Modal.Header
          icon={SvgHistory}
          title={item.name}
          description={`${item.version_count} saved ${item.version_count === 1 ? "version" : "versions"}`}
        />
        <Modal.Body>
          <div className="flex w-full flex-col gap-1">
            {item.versions.map((version, index) => (
              <div key={version.id}>
                <div className="flex w-full items-center justify-between gap-3 py-2">
                  <div className="min-w-0">
                    <Text color="text-05" font="main-ui-body">
                      {`Version ${version.version_number}`}
                    </Text>
                    <Text color="text-03" font="secondary-body">
                      {`${new Date(version.created_at).toLocaleString()} · ${formatBytes(version.size_bytes)}`}
                    </Text>
                  </div>
                  <Button
                    href={artifactVersionDownloadUrl(
                      item.id,
                      version.version_number
                    )}
                    icon={SvgDownload}
                    prominence="secondary"
                  >
                    Download
                  </Button>
                </div>
                {index < item.versions.length - 1 ? <Divider /> : null}
              </div>
            ))}
          </div>
        </Modal.Body>
        <Modal.Footer>
          <div className="flex w-full justify-end">
            <Button prominence="secondary" onClick={onClose}>
              Close
            </Button>
          </div>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
