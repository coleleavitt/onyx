/**
 * Skills API response shapes; mirrors
 * `backend/onyx/server/features/skill/models.py`.
 */

export type SkillSource = "builtin" | "custom";
export type SkillAccessLevel = "OWNER" | "EDITOR" | "VIEWER";
export type SkillSharePermission = "EDITOR" | "VIEWER";
export type SkillReviewStatus =
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "OUTDATED";

export interface SkillUserShare {
  user: {
    id: string;
    email: string;
  };
  permission: SkillSharePermission;
}

export interface SkillGroupShare {
  group_id: number;
  group_name: string;
  permission: SkillSharePermission;
}

export interface Skill {
  source: SkillSource;
  id: string;
  slug: string;
  name: string;
  description: string;

  is_available: boolean | null;
  unavailable_reason: string | null;

  /** True for private personal skills: not public, no direct/group shares. */
  is_personal: boolean;
  enabled: boolean | null;
  author_user_id: string | null;
  author_email: string | null;
  owner: {
    id: string;
    email: string;
  } | null;
  ownership_vacant: boolean;
  created_at: string | null;
  updated_at: string | null;
  user_shares: SkillUserShare[];
  group_shares: SkillGroupShare[];
  public_permission: SkillSharePermission | null;
  user_permission: SkillAccessLevel | null;
  review_status: SkillReviewStatus | null;
  review_submitted_at: string | null;
}

export type BuiltinSkill = Skill & {
  source: "builtin";
  is_available: boolean;
};

export type CustomSkill = Skill & {
  source: "custom";
  enabled: boolean;
};

export interface SkillsList {
  builtins: Skill[];
  customs: Skill[];
}

export interface SkillPreview {
  source: SkillSource;
  id: string;
  name: string;
  description: string;
  author_email: string | null;
  instructions_markdown: string;
}

export type SkillEditableDetail = CustomSkill & {
  instructions_markdown: string;
};

export interface SkillPackageFile {
  path: string;
  size: number;
  sha256: string;
  is_text: boolean;
  content: string | null;
  content_truncated: boolean;
}

export interface SkillPackageFinding {
  code: string;
  severity: "INFO" | "WARNING";
  message: string;
  path: string | null;
}

export interface SkillPackage {
  status: "PASS" | "REVIEW";
  files: SkillPackageFile[];
  findings: SkillPackageFinding[];
  total_uncompressed_bytes: number;
}

export interface SkillPackageFileDiff {
  path: string;
  change_type: "ADDED" | "MODIFIED" | "DELETED";
  diff: string | null;
}

export interface SkillPackageDiff {
  files: SkillPackageFileDiff[];
  candidate: SkillPackage;
}

export interface SkillReviewSubmission {
  id: string;
  skill_id: string;
  skill_name: string;
  skill_slug: string;
  submitted_by: { id: string; email: string };
  reviewed_by: { id: string; email: string } | null;
  bundle_sha256: string;
  current_bundle_sha256: string | null;
  is_current_bundle: boolean;
  status: SkillReviewStatus;
  submission_comment: string | null;
  review_comment: string | null;
  submitted_at: string;
  reviewed_at: string | null;
}
