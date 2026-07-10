import type { OnyxDocument } from "@/lib/search/interfaces";

const ADDITIONAL_SOURCE_SCORE_RATIO = 0.35;
const INITIAL_REVIEWED_SOURCE_LIMIT = 8;

const AUTHORITY_METADATA_KEYS = [
  "source_authority",
  "authority_level",
  "trust_level",
] as const;

const AUTHORITY_REASON_METADATA_KEYS = [
  "source_authority_reason",
  "authority_reason",
  "trust_reason",
] as const;

export const EVIDENCE_METADATA_KEYS = new Set<string>([
  ...AUTHORITY_METADATA_KEYS,
  ...AUTHORITY_REASON_METADATA_KEYS,
  "evidence_status",
]);

export type SourceAuthority = "authoritative" | "trusted" | "credible";

export interface SourceEvidencePartition {
  citedDocuments: OnyxDocument[];
  reviewedDocuments: OnyxDocument[];
  lowerRelevanceDocuments: OnyxDocument[];
}

function normalizedScore(document: OnyxDocument): number {
  return Number.isFinite(document.score) ? document.score : 0;
}

function getFirstMetadataValue(
  document: OnyxDocument,
  keys: readonly string[]
): string | null {
  for (const key of keys) {
    const value = document.metadata[key]?.trim();
    if (value) return value;
  }
  return null;
}

export function getSourceAuthority(
  document: OnyxDocument
): SourceAuthority | null {
  const rawAuthority = getFirstMetadataValue(
    document,
    AUTHORITY_METADATA_KEYS
  )?.toLowerCase();

  switch (rawAuthority) {
    case "3":
    case "authoritative":
      return "authoritative";
    case "2":
    case "trusted":
      return "trusted";
    case "1":
    case "credible":
      return "credible";
    default:
      return null;
  }
}

export function getSourceAuthorityReason(
  document: OnyxDocument
): string | null {
  return getFirstMetadataValue(document, AUTHORITY_REASON_METADATA_KEYS);
}

export function partitionSourceEvidence(
  documents: OnyxDocument[],
  citedDocumentIds: ReadonlySet<string>,
  citationOrder: ReadonlyMap<string, number>
): SourceEvidencePartition {
  const visibleDocuments = documents.filter(
    (document) => !document.hidden && document.score !== null
  );
  const citedDocuments = visibleDocuments
    .filter((document) => citedDocumentIds.has(document.document_id))
    .sort(
      (left, right) =>
        (citationOrder.get(left.document_id) ?? Number.POSITIVE_INFINITY) -
        (citationOrder.get(right.document_id) ?? Number.POSITIVE_INFINITY)
    );
  const uncitedDocuments = visibleDocuments
    .filter((document) => !citedDocumentIds.has(document.document_id))
    .sort((left, right) => normalizedScore(right) - normalizedScore(left));

  if (uncitedDocuments.length === 0) {
    return {
      citedDocuments,
      reviewedDocuments: [],
      lowerRelevanceDocuments: [],
    };
  }

  const topScore = normalizedScore(uncitedDocuments[0]!);
  const relevanceThreshold =
    topScore > 0
      ? topScore * ADDITIONAL_SOURCE_SCORE_RATIO
      : Number.NEGATIVE_INFINITY;
  const relevantDocuments = uncitedDocuments.filter(
    (document) => normalizedScore(document) >= relevanceThreshold
  );
  const reviewedDocuments = relevantDocuments.slice(
    0,
    INITIAL_REVIEWED_SOURCE_LIMIT
  );
  const reviewedIds = new Set(
    reviewedDocuments.map((document) => document.document_id)
  );

  return {
    citedDocuments,
    reviewedDocuments,
    lowerRelevanceDocuments: uncitedDocuments.filter(
      (document) => !reviewedIds.has(document.document_id)
    ),
  };
}
