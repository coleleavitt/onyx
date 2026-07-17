"use client";

import { useEffect, useRef, useState } from "react";
import MinimalMarkdown from "@/components/chat/MinimalMarkdown";
import Modal from "@/refresh-components/Modal";
import { artifactVersionDownloadUrl } from "@/app/craft/v1/artifacts/api";
import type { ArtifactLibraryItem } from "@/app/craft/v1/artifacts/types";
import { Button, Text } from "@opal/components";
import {
  SvgDocFile,
  SvgDownload,
  SvgFile,
  SvgEdit,
  SvgHistory,
  SvgImage,
  SvgPin,
  SvgPinned,
  SvgShare,
  SvgSimpleLoader,
} from "@opal/icons";

interface ArtifactPreviewModalProps {
  item: ArtifactLibraryItem;
  onClose: () => void;
  onHistory: () => void;
  onShare: () => void;
  onRename?: () => void;
  onPin?: () => void;
}

interface PreviewPayload {
  objectUrl: string | null;
  text: string | null;
  buffer: ArrayBuffer | null;
}

const EMPTY_PAYLOAD: PreviewPayload = {
  objectUrl: null,
  text: null,
  buffer: null,
};

function isTextPreview(item: ArtifactLibraryItem): boolean {
  const mimeType = item.latest_version.mime_type ?? "";
  return (
    item.type === "markdown" ||
    item.type === "csv" ||
    mimeType.startsWith("text/") ||
    mimeType.includes("json")
  );
}

function PreviewFallback({ item }: { item: ArtifactLibraryItem }) {
  return (
    <div className="flex h-full min-h-80 w-full flex-col items-center justify-center gap-3 px-6 text-center">
      <SvgFile size={48} className="stroke-text-02" />
      <div className="flex max-w-md flex-col gap-1">
        <Text font="heading-h3" color="text-05">
          Preview unavailable
        </Text>
        <Text font="secondary-body" color="text-03">
          {`${item.name} can be downloaded and opened in its native application.`}
        </Text>
      </div>
      <Button
        href={artifactVersionDownloadUrl(
          item.id,
          item.latest_version.version_number
        )}
        icon={SvgDownload}
        prominence="secondary"
      >
        Download
      </Button>
    </div>
  );
}

export default function ArtifactPreviewModal({
  item,
  onClose,
  onHistory,
  onShare,
  onRename,
  onPin,
}: ArtifactPreviewModalProps) {
  const [payload, setPayload] = useState<PreviewPayload>(EMPTY_PAYLOAD);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const docxContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | null = null;
    setPayload(EMPTY_PAYLOAD);
    setLoading(true);
    setError(null);

    void fetch(
      artifactVersionDownloadUrl(item.id, item.latest_version.version_number),
      { signal: controller.signal }
    )
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Preview request failed (${response.status})`);
        }
        const blob = await response.blob();
        if (item.type === "docx") {
          return { ...EMPTY_PAYLOAD, buffer: await blob.arrayBuffer() };
        }
        if (isTextPreview(item)) {
          return { ...EMPTY_PAYLOAD, text: await blob.text() };
        }
        objectUrl = URL.createObjectURL(blob);
        return { ...EMPTY_PAYLOAD, objectUrl };
      })
      .then((nextPayload) => {
        setPayload(nextPayload);
        setLoading(false);
      })
      .catch((previewError: unknown) => {
        if (
          previewError instanceof DOMException &&
          previewError.name === "AbortError"
        ) {
          return;
        }
        setError(
          previewError instanceof Error
            ? previewError.message
            : "The artifact could not be loaded."
        );
        setLoading(false);
      });

    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [item]);

  useEffect(() => {
    const container = docxContainerRef.current;
    if (item.type !== "docx" || !payload.buffer || !container) return;
    container.replaceChildren();
    let active = true;
    void import("docx-preview")
      .then(({ renderAsync }) =>
        renderAsync(payload.buffer as ArrayBuffer, container, undefined, {
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
        })
      )
      .catch((previewError: unknown) => {
        if (!active) return;
        setError(
          previewError instanceof Error
            ? previewError.message
            : "The document could not be rendered."
        );
      });
    return () => {
      active = false;
      container.replaceChildren();
    };
  }, [item.type, payload.buffer]);

  const preview = (() => {
    if (loading) {
      return (
        <div className="flex h-full min-h-80 w-full items-center justify-center gap-2">
          <SvgSimpleLoader className="h-5 w-5" />
          <Text font="main-ui-body" color="text-03">
            Loading preview...
          </Text>
        </div>
      );
    }
    if (error) {
      return (
        <div className="flex h-full min-h-80 w-full flex-col items-center justify-center gap-2 px-6 text-center">
          <SvgFile size={48} className="stroke-text-02" />
          <Text font="heading-h3" color="text-05">
            Cannot preview artifact
          </Text>
          <Text font="secondary-body" color="text-03">
            {error}
          </Text>
        </div>
      );
    }
    if (item.type === "pdf" && payload.objectUrl) {
      return (
        <iframe
          className="h-full min-h-96 w-full border-0"
          src={payload.objectUrl}
          title={`Preview of ${item.name}`}
        />
      );
    }
    if (item.type === "image" && payload.objectUrl) {
      return (
        <div className="flex h-full min-h-80 w-full items-center justify-center p-4">
          <img
            alt={`Preview of ${item.name}`}
            className="max-h-full max-w-full object-contain"
            src={payload.objectUrl}
          />
        </div>
      );
    }
    if (item.type === "docx" && payload.buffer) {
      return (
        <div className="h-full w-full overflow-auto bg-background-tint-01 p-4 sm:p-8">
          <div
            ref={docxContainerRef}
            className="mx-auto min-h-full max-w-4xl overflow-hidden"
          />
        </div>
      );
    }
    if (payload.text !== null) {
      return item.type === "markdown" ? (
        <div className="h-full w-full overflow-auto p-5 sm:p-8">
          <MinimalMarkdown
            content={payload.text}
            className="mx-auto max-w-3xl"
          />
        </div>
      ) : (
        <pre className="h-full w-full overflow-auto whitespace-pre-wrap p-5 font-mono text-sm text-text-04 sm:p-8">
          {payload.text}
        </pre>
      );
    }
    return <PreviewFallback item={item} />;
  })();

  const HeaderIcon =
    item.type === "image"
      ? SvgImage
      : item.type === "docx"
        ? SvgDocFile
        : SvgFile;

  return (
    <Modal open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content width="full" height="full" preventAccidentalClose={false}>
        <Modal.Header
          icon={HeaderIcon}
          title={item.name}
          description={`Version ${item.latest_version.version_number} · ${item.is_owner ? "Created by you" : `Shared by ${item.owner.email}`}`}
          onClose={onClose}
        />
        <Modal.Body twoTone={false} padding={0}>
          <div className="h-full min-h-0 w-full">{preview}</div>
        </Modal.Body>
        <Modal.Footer justifyContent="between">
          <Button icon={SvgHistory} prominence="tertiary" onClick={onHistory}>
            Versions
          </Button>
          <div className="flex items-center gap-2">
            {onPin ? (
              <Button
                icon={item.is_pinned ? SvgPinned : SvgPin}
                prominence="tertiary"
                onClick={onPin}
              >
                {item.is_pinned ? "Unpin" : "Pin"}
              </Button>
            ) : null}
            {item.is_owner && onRename ? (
              <Button icon={SvgEdit} prominence="tertiary" onClick={onRename}>
                Rename
              </Button>
            ) : null}
            {item.is_owner ? (
              <Button icon={SvgShare} prominence="secondary" onClick={onShare}>
                Share
              </Button>
            ) : null}
            <Button
              href={artifactVersionDownloadUrl(
                item.id,
                item.latest_version.version_number
              )}
              icon={SvgDownload}
            >
              Download
            </Button>
          </div>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
