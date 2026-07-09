import { IndexAttemptSnapshot } from "@/lib/types";

export type IndexingProgressPhase = "discovering" | "processing";

export interface IndexingProgress {
  phase: IndexingProgressPhase;
  ratio: number | null;
  completed: number;
  total: number | null;
  approximate: boolean;
}

function clampRatio(value: number): number {
  return Math.max(0, Math.min(value, 1));
}

export function getIndexingProgress(
  attempt: IndexAttemptSnapshot | null,
  estimateComparable: boolean = true
): IndexingProgress | null {
  if (
    attempt === null ||
    (attempt.status !== "in_progress" && attempt.status !== "not_started")
  ) {
    return null;
  }

  const totalBatches = attempt.total_batches ?? null;
  const completedBatches = attempt.completed_batches ?? 0;
  const discoveredDocuments = Math.max(
    attempt.source_docs_discovered ?? 0,
    attempt.total_docs_indexed
  );

  if (totalBatches !== null) {
    const ratio =
      totalBatches > 0 ? clampRatio(completedBatches / totalBatches) : 1;
    return {
      phase: "processing",
      ratio,
      completed: completedBatches,
      total: totalBatches,
      approximate: false,
    };
  }

  const estimate = attempt.source_docs_estimated ?? null;
  const estimatedRatio =
    estimateComparable && estimate !== null && estimate > 0
      ? Math.min(clampRatio(discoveredDocuments / estimate), 0.99)
      : null;
  return {
    phase: "discovering",
    ratio: estimatedRatio,
    completed: discoveredDocuments,
    total: estimate,
    approximate: estimatedRatio !== null,
  };
}
