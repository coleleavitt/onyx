/**
 * Shared limits for Space (project) metadata. Kept in one place so the create
 * modal, the edit modal, and the inline detail-page editors all validate
 * against the same caps.
 */

/** Maximum length of a Space name/title. */
export const SPACE_NAME_MAX_LENGTH = 255;

/**
 * Maximum length of a Space description. Raised well beyond the old 255 cap to
 * match Perplexity's ~1000-char space descriptions (acceptance criterion 3).
 */
export const SPACE_DESCRIPTION_MAX_LENGTH = 1000;
