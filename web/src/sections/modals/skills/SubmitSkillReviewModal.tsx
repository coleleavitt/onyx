"use client";

import { useState } from "react";
import { toast } from "@opal/layouts";
import { submitSkillForReview } from "@/lib/skills/api";
import type { SkillEditableDetail } from "@/lib/skills/types";
import Modal from "@/refresh-components/Modal";
import InputTextArea from "@/refresh-components/inputs/InputTextArea";
import { Button, Text } from "@opal/components";
import { SvgShield } from "@opal/icons";
import { markdown } from "@opal/utils";

interface SubmitSkillReviewModalProps {
  skill: SkillEditableDetail | null;
  open: boolean;
  onClose: () => void;
  onSubmitted: () => Promise<void>;
}

export default function SubmitSkillReviewModal({
  skill,
  open,
  onClose,
  onSubmitted,
}: SubmitSkillReviewModalProps) {
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function close() {
    if (submitting) return;
    setComment("");
    onClose();
  }

  async function submit() {
    if (!skill) return;
    setSubmitting(true);
    try {
      await submitSkillForReview(skill.id, comment.trim() || null);
      await onSubmitted();
      toast.success("Skill submitted for organization review.");
      setComment("");
      onClose();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to submit skill"
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (!skill) return null;

  return (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && close()}>
      <Modal.Content width="sm">
        <Modal.Header
          icon={SvgShield}
          title={markdown(`Submit *${skill.name}*`)}
          description="An administrator will inspect this exact package version before publishing it to the organization."
          onClose={close}
        />
        <Modal.Body>
          <div className="flex w-full flex-col gap-2">
            <Text color="text-04" font="main-ui-action">
              Review notes
            </Text>
            <InputTextArea
              autoResize
              maxRows={8}
              onChange={(event) => setComment(event.target.value)}
              placeholder="Summarize what the skill does and what reviewers should check."
              rows={4}
              value={comment}
            />
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Button disabled={submitting} onClick={close} prominence="secondary">
            Cancel
          </Button>
          <Button
            disabled={submitting}
            icon={SvgShield}
            onClick={() => void submit()}
          >
            {submitting ? "Submitting..." : "Submit for review"}
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
