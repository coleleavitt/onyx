"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { toast } from "@opal/layouts";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { listSkillReviews, resolveSkillReview } from "@/lib/skills/api";
import type { SkillReviewSubmission } from "@/lib/skills/types";
import Modal from "@/refresh-components/Modal";
import InputTextArea from "@/refresh-components/inputs/InputTextArea";
import { Button, Divider, Tabs, Tag, Text } from "@opal/components";
import { SvgBlocks, SvgCheck, SvgShield, SvgX } from "@opal/icons";
import { ContentAction, SettingsLayouts } from "@opal/layouts";

type ReviewFilter = "PENDING" | "ALL";

const route = ADMIN_ROUTES.SKILL_REVIEWS;

function statusColor(status: SkillReviewSubmission["status"]) {
  if (status === "APPROVED") return "green" as const;
  if (status === "PENDING") return "blue" as const;
  if (status === "REJECTED") return "red" as const;
  return "amber" as const;
}

export default function SkillReviewsPage() {
  const [filter, setFilter] = useState<ReviewFilter>("PENDING");
  const [selected, setSelected] = useState<SkillReviewSubmission | null>(null);
  const [reviewComment, setReviewComment] = useState("");
  const [resolving, setResolving] = useState(false);
  const { data, error, isLoading, mutate } = useSWR("/api/skills/reviews", () =>
    listSkillReviews()
  );
  const reviews = useMemo(
    () =>
      (data ?? []).filter(
        (review) => filter === "ALL" || review.status === "PENDING"
      ),
    [data, filter]
  );

  function closeReview() {
    if (resolving) return;
    setSelected(null);
    setReviewComment("");
  }

  async function resolve(approve: boolean) {
    if (!selected) return;
    setResolving(true);
    try {
      const result = await resolveSkillReview(
        selected.id,
        approve,
        reviewComment.trim() || null
      );
      toast.success(
        result.status === "OUTDATED"
          ? "Submission marked outdated."
          : approve
            ? "Skill approved and published."
            : "Skill submission rejected."
      );
      await mutate();
      setSelected(null);
      setReviewComment("");
    } catch (resolveError) {
      toast.error(
        resolveError instanceof Error
          ? resolveError.message
          : "Failed to resolve review"
      );
    } finally {
      setResolving(false);
    }
  }

  return (
    <SettingsLayouts.Root>
      <SettingsLayouts.Header
        divider
        icon={route.icon}
        title={route.title}
        description="Inspect submitted skill packages before publishing them to the organization."
        rightChildren={
          <Tabs
            value={filter}
            onValueChange={(value) => setFilter(value as ReviewFilter)}
          >
            <Tabs.List>
              <Tabs.Trigger value="PENDING">Pending</Tabs.Trigger>
              <Tabs.Trigger value="ALL">All</Tabs.Trigger>
            </Tabs.List>
          </Tabs>
        }
      />
      <SettingsLayouts.Body>
        {isLoading ? (
          <Text color="text-03" font="secondary-body">
            Loading skill reviews...
          </Text>
        ) : error ? (
          <Text color="status-error-05" font="secondary-body">
            Skill reviews could not be loaded.
          </Text>
        ) : reviews.length === 0 ? (
          <ContentAction
            description="New organization submissions will appear here."
            icon={SvgShield}
            sizePreset="main-ui"
            title={filter === "PENDING" ? "No pending reviews" : "No reviews"}
            variant="section"
          />
        ) : (
          <div className="flex w-full flex-col gap-1">
            {reviews.map((review, index) => (
              <div key={review.id}>
                <ContentAction
                  description={`Submitted by ${review.submitted_by.email}`}
                  icon={SvgBlocks}
                  rightChildren={
                    <div className="flex items-center gap-2">
                      <Tag
                        color={statusColor(review.status)}
                        title={review.status.toLowerCase()}
                      />
                      <Button
                        onClick={() => {
                          setSelected(review);
                          setReviewComment(review.review_comment ?? "");
                        }}
                        prominence="secondary"
                      >
                        Review
                      </Button>
                    </div>
                  }
                  sizePreset="main-ui"
                  title={review.skill_name}
                  variant="section"
                />
                {index < reviews.length - 1 && (
                  <Divider paddingParallel="fit" paddingPerpendicular="fit" />
                )}
              </div>
            ))}
          </div>
        )}
      </SettingsLayouts.Body>

      <Modal
        open={selected !== null}
        onOpenChange={(open) => !open && closeReview()}
      >
        <Modal.Content width="md">
          <Modal.Header
            icon={SvgShield}
            title={selected?.skill_name ?? "Skill review"}
            description={selected?.skill_slug}
            onClose={closeReview}
          />
          <Modal.Body>
            {selected && (
              <div className="flex w-full flex-col gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Tag
                    color={statusColor(selected.status)}
                    title={selected.status.toLowerCase()}
                  />
                  {!selected.is_current_bundle && (
                    <Tag color="amber" title="package changed" />
                  )}
                  <Text color="text-03" font="secondary-mono">
                    {selected.bundle_sha256.slice(0, 12)}
                  </Text>
                </div>
                {selected.submission_comment && (
                  <div className="rounded-08 border border-border-01 px-2 py-2">
                    <Text color="text-04" font="main-ui-body">
                      {selected.submission_comment}
                    </Text>
                  </div>
                )}
                <Button
                  href={`/craft/v1/skills/edit/${selected.skill_id}`}
                  icon={SvgBlocks}
                  prominence="secondary"
                >
                  Inspect package
                </Button>
                <div className="flex flex-col gap-1">
                  <Text color="text-04" font="main-ui-action">
                    Review comment
                  </Text>
                  <InputTextArea
                    autoResize
                    maxRows={8}
                    onChange={(event) => setReviewComment(event.target.value)}
                    placeholder="Record why this submission was approved or rejected."
                    rows={4}
                    value={reviewComment}
                  />
                </div>
              </div>
            )}
          </Modal.Body>
          <Modal.Footer justifyContent="between">
            <Button
              disabled={resolving}
              onClick={closeReview}
              prominence="secondary"
            >
              Cancel
            </Button>
            {selected?.status === "PENDING" && (
              <div className="flex items-center gap-2">
                <Button
                  disabled={resolving || !reviewComment.trim()}
                  icon={SvgX}
                  onClick={() => void resolve(false)}
                  variant="danger"
                >
                  Reject
                </Button>
                <Button
                  disabled={resolving || !selected.is_current_bundle}
                  icon={SvgCheck}
                  onClick={() => void resolve(true)}
                >
                  Approve
                </Button>
              </div>
            )}
          </Modal.Footer>
        </Modal.Content>
      </Modal>
    </SettingsLayouts.Root>
  );
}
