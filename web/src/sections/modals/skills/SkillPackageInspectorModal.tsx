"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "@opal/layouts";
import {
  getSkillPackage,
  inspectSkillPackageCandidate,
  updateSkillPackageFile,
} from "@/lib/skills/api";
import type {
  SkillEditableDetail,
  SkillPackage,
  SkillPackageDiff,
} from "@/lib/skills/types";
import Modal from "@/refresh-components/Modal";
import InputTextArea from "@/refresh-components/inputs/InputTextArea";
import { Button, LineItemButton, Tag, Text } from "@opal/components";
import { SvgFileText, SvgShield, SvgUploadCloud } from "@opal/icons";
import { markdown } from "@opal/utils";

interface SkillPackageInspectorModalProps {
  skill: SkillEditableDetail | null;
  candidateFile: File | null;
  open: boolean;
  onClose: () => void;
  onCandidateApproved: (file: File) => Promise<void>;
  onPackageSaved: () => Promise<void>;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function SkillPackageInspectorModal({
  skill,
  candidateFile,
  open,
  onClose,
  onCandidateApproved,
  onPackageSaved,
}: SkillPackageInspectorModalProps) {
  const [pkg, setPackage] = useState<SkillPackage | null>(null);
  const [candidateDiff, setCandidateDiff] = useState<SkillPackageDiff | null>(
    null
  );
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [editedContent, setEditedContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reviewingCandidate = candidateFile !== null;

  useEffect(() => {
    if (!open || !skill) {
      setPackage(null);
      setCandidateDiff(null);
      setSelectedPath(null);
      setError(null);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);
    const request = candidateFile
      ? inspectSkillPackageCandidate(skill.id, candidateFile)
      : getSkillPackage(skill.id);

    void request
      .then((result) => {
        if (!active) return;
        if (candidateFile) {
          const diff = result as SkillPackageDiff;
          setCandidateDiff(diff);
          setPackage(diff.candidate);
          setSelectedPath(diff.files[0]?.path ?? null);
        } else {
          const nextPackage = result as SkillPackage;
          setPackage(nextPackage);
          setSelectedPath(
            nextPackage.files.find((file) => file.path === "SKILL.md")?.path ??
              nextPackage.files[0]?.path ??
              null
          );
        }
      })
      .catch((requestError) => {
        if (!active) return;
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Failed to inspect skill package"
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [candidateFile, open, skill]);

  const selectedFile = useMemo(
    () => pkg?.files.find((file) => file.path === selectedPath) ?? null,
    [pkg?.files, selectedPath]
  );
  const selectedDiff = useMemo(
    () =>
      candidateDiff?.files.find((entry) => entry.path === selectedPath) ?? null,
    [candidateDiff?.files, selectedPath]
  );

  useEffect(() => {
    setEditedContent(selectedFile?.content ?? "");
  }, [selectedFile]);

  const canEditSelected =
    !reviewingCandidate &&
    skill?.user_permission !== "VIEWER" &&
    selectedFile?.is_text === true &&
    !selectedFile.content_truncated;
  const contentChanged =
    canEditSelected && editedContent !== (selectedFile?.content ?? "");
  const fileEntries = reviewingCandidate
    ? (candidateDiff?.files.map((entry) => ({
        path: entry.path,
        description: entry.change_type.toLowerCase(),
      })) ?? [])
    : (pkg?.files.map((file) => ({
        path: file.path,
        description: formatBytes(file.size),
      })) ?? []);

  async function saveFile() {
    if (!skill || !selectedFile || !contentChanged) return;
    setSaving(true);
    try {
      const nextPackage = await updateSkillPackageFile(
        skill.id,
        selectedFile.path,
        editedContent
      );
      setPackage(nextPackage);
      await onPackageSaved();
      toast.success(`Saved ${selectedFile.path}`);
    } catch (saveError) {
      toast.error(
        saveError instanceof Error ? saveError.message : "Failed to save file"
      );
    } finally {
      setSaving(false);
    }
  }

  async function approveCandidate() {
    if (!candidateFile) return;
    setSaving(true);
    try {
      await onCandidateApproved(candidateFile);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  if (!skill) return null;

  return (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <Modal.Content height="lg" width="lg">
        <Modal.Header
          icon={reviewingCandidate ? SvgUploadCloud : SvgShield}
          title={markdown(
            reviewingCandidate
              ? `Review changes to *${skill.name}*`
              : `Inspect *${skill.name}*`
          )}
          description={
            reviewingCandidate
              ? "Review file changes and security findings before replacing the package."
              : "Browse and edit the validated files stored in this skill package."
          }
          onClose={onClose}
        />
        <Modal.Body>
          {loading ? (
            <div className="flex min-h-48 items-center justify-center">
              <Text color="text-03" font="secondary-body">
                Inspecting package...
              </Text>
            </div>
          ) : error ? (
            <Text color="status-error-05" font="secondary-body">
              {error}
            </Text>
          ) : pkg ? (
            <div className="flex min-h-0 w-full flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Tag
                  color={pkg.status === "PASS" ? "green" : "amber"}
                  title={
                    pkg.status === "PASS" ? "Checks passed" : "Review needed"
                  }
                />
                <Text color="text-03" font="secondary-body">
                  {`${pkg.files.length} files, ${formatBytes(pkg.total_uncompressed_bytes)}`}
                </Text>
              </div>

              {pkg.findings.length > 0 && (
                <div className="flex flex-col gap-1 rounded-08 border border-border-01 px-2 py-2">
                  {pkg.findings.map((finding, index) => (
                    <div
                      className="flex items-start justify-between gap-2"
                      key={`${finding.code}-${finding.path ?? "package"}-${index}`}
                    >
                      <div className="min-w-0">
                        <Text color="text-04" font="main-ui-body">
                          {finding.message}
                        </Text>
                        {finding.path && (
                          <Text color="text-03" font="secondary-mono">
                            {finding.path}
                          </Text>
                        )}
                      </div>
                      <Tag
                        color={
                          finding.severity === "WARNING" ? "amber" : "blue"
                        }
                        title={finding.severity.toLowerCase()}
                      />
                    </div>
                  ))}
                </div>
              )}

              <div className="grid min-h-[28rem] grid-cols-1 overflow-hidden rounded-08 border border-border-01 md:grid-cols-[17rem_minmax(0,1fr)]">
                <div className="flex min-h-0 flex-col gap-1 overflow-y-auto border-b border-border-01 bg-background-tint-01 p-1 md:border-b-0 md:border-r">
                  {fileEntries.length === 0 ? (
                    <Text color="text-03" font="secondary-body">
                      No file changes.
                    </Text>
                  ) : (
                    fileEntries.map((entry) => (
                      <LineItemButton
                        description={entry.description}
                        icon={SvgFileText}
                        key={entry.path}
                        onClick={() => setSelectedPath(entry.path)}
                        rounding="md"
                        selectVariant="select-heavy"
                        sizePreset="main-ui"
                        state={
                          entry.path === selectedPath ? "selected" : "empty"
                        }
                        title={entry.path}
                        variant="section"
                        width="full"
                      />
                    ))
                  )}
                </div>

                <div className="min-h-0 overflow-auto bg-background-neutral-00 p-2">
                  {reviewingCandidate ? (
                    selectedDiff ? (
                      <pre className="whitespace-pre-wrap break-words font-mono text-sm text-text-04">
                        {selectedDiff.diff ??
                          `${selectedDiff.change_type.toLowerCase()} binary file`}
                      </pre>
                    ) : (
                      <Text color="text-03" font="secondary-body">
                        Select a changed file.
                      </Text>
                    )
                  ) : selectedFile ? (
                    canEditSelected ? (
                      <InputTextArea
                        autoResize={false}
                        className="min-h-[26rem] border-0 font-mono"
                        onChange={(event) =>
                          setEditedContent(event.target.value)
                        }
                        rows={24}
                        value={editedContent}
                        variant="internal"
                      />
                    ) : selectedFile.content ? (
                      <pre className="whitespace-pre-wrap break-words font-mono text-sm text-text-04">
                        {selectedFile.content}
                      </pre>
                    ) : (
                      <Text color="text-03" font="secondary-body">
                        Binary files can be inspected by hash and size but
                        cannot be edited here.
                      </Text>
                    )
                  ) : (
                    <Text color="text-03" font="secondary-body">
                      Select a file.
                    </Text>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </Modal.Body>
        <Modal.Footer>
          <Button disabled={saving} onClick={onClose} prominence="secondary">
            Cancel
          </Button>
          {reviewingCandidate ? (
            <Button
              disabled={saving || loading || !!error}
              icon={SvgUploadCloud}
              onClick={() => void approveCandidate()}
            >
              {saving ? "Replacing..." : "Replace package"}
            </Button>
          ) : (
            <Button
              disabled={!contentChanged || saving}
              onClick={() => void saveFile()}
            >
              {saving ? "Saving..." : "Save file"}
            </Button>
          )}
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
