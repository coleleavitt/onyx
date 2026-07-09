"use client";

import { Text } from "@opal/components";
import { SvgSimpleLoader } from "@opal/icons";
import { timeAgo } from "@opal/time";

import { getIndexingProgress } from "@/lib/indexingProgress";
import { IndexAttemptSnapshot } from "@/lib/types";

interface IndexingProgressPanelProps {
  attempt: IndexAttemptSnapshot | null;
  estimateComparable: boolean;
}

export default function IndexingProgressPanel({
  attempt,
  estimateComparable,
}: IndexingProgressPanelProps) {
  const progress = getIndexingProgress(attempt, estimateComparable);
  if (progress === null || attempt === null) return null;

  const discoveredDocuments = Math.max(
    attempt.source_docs_discovered ?? 0,
    attempt.total_docs_indexed
  );
  const percentage =
    progress.ratio === null ? null : Math.round(progress.ratio * 100);
  const progressText =
    progress.phase === "processing" && progress.total !== null
      ? `${progress.completed.toLocaleString()} of ${progress.total.toLocaleString()} batches`
      : percentage !== null
        ? `~${percentage}%`
        : "In progress";
  const phaseLabel =
    progress.phase === "discovering"
      ? "Discovering source documents"
      : "Processing discovered documents";

  return (
    <div className="mt-6 border-t border-border-01 pt-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <Text font="main-ui-body" color="text-04">
            {phaseLabel}
          </Text>
          {attempt.source_progress_label && (
            <div className="mt-0.5 min-w-0">
              <Text font="secondary-body" color="text-02" maxLines={1}>
                {`Scanning ${attempt.source_progress_label}`}
              </Text>
            </div>
          )}
        </div>
        <Text font="main-ui-body" color="text-03" nowrap>
          {progressText}
        </Text>
      </div>

      {percentage === null ? (
        <div className="mt-3 flex h-2 items-center" aria-busy="true">
          <SvgSimpleLoader className="h-4 w-4" />
        </div>
      ) : (
        <div
          className="mt-3 h-2 w-full overflow-hidden rounded-sm bg-background-tint-02"
          role="progressbar"
          aria-label={phaseLabel}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percentage}
          aria-valuetext={
            progress.approximate
              ? `Approximately ${percentage}% discovered`
              : `${progressText} completed`
          }
        >
          <div
            className="h-full bg-action-link-05 transition-[width] duration-300"
            style={{ width: `${percentage}%` }}
          />
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1">
        <Text font="secondary-body" color="text-03">
          {`${discoveredDocuments.toLocaleString()} discovered`}
        </Text>
        <Text font="secondary-body" color="text-03">
          {`${attempt.total_docs_indexed.toLocaleString()} indexed this run`}
        </Text>
        {attempt.source_docs_estimated != null && (
          <Text font="secondary-body" color="text-02">
            {`~${attempt.source_docs_estimated.toLocaleString()} searchable files`}
          </Text>
        )}
        {attempt.last_heartbeat_time && (
          <Text font="secondary-body" color="text-02">
            {`Worker active ${timeAgo(attempt.last_heartbeat_time)}`}
          </Text>
        )}
      </div>
    </div>
  );
}
