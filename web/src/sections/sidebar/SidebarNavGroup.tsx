"use client";

import React, { useCallback, useState } from "react";
import type { Route } from "next";
import { SidebarTab } from "@opal/components";
import { SvgChevronRight } from "@opal/icons";
import { cn } from "@opal/utils";
import type { IconFunctionComponent } from "@opal/types";

const GROUP_EXPANDED_PREFIX = "opal-sidebar-group-expanded-";

function readPersistedExpanded(
  persistKey: string | undefined,
  defaultExpanded: boolean,
): boolean {
  if (!persistKey || typeof window === "undefined") return defaultExpanded;
  const stored = window.localStorage.getItem(
    `${GROUP_EXPANDED_PREFIX}${persistKey}`,
  );
  if (stored === "true") return true;
  if (stored === "false") return false;
  return defaultExpanded;
}

interface SidebarNavGroupProps {
  icon: IconFunctionComponent;
  label: string;
  /** Optional navigation target for the header row (clicking the row). */
  href?: string;
  selected?: boolean;
  folded?: boolean;
  /** localStorage key used to persist expand/collapse across sessions. */
  persistKey?: string;
  defaultExpanded?: boolean;
  /** Whether the group has nested children to reveal. */
  hasChildren?: boolean;
  forceExpanded?: boolean;
  /** Extra hover-revealed action rendered on the right (e.g. "New"). */
  action?: React.ReactNode;
  children?: React.ReactNode;
}

/**
 * A collapsible sidebar nav row. The header navigates via `href`; on hover its
 * left icon morphs into a chevron that toggles the nested `children` (the
 * pattern used by the reference sidebar). Groups are collapsed by default and
 * the expand state persists to `localStorage`.
 */
export default function SidebarNavGroup({
  icon,
  label,
  href,
  selected,
  folded,
  persistKey,
  defaultExpanded = false,
  hasChildren = false,
  forceExpanded = false,
  action,
  children,
}: SidebarNavGroupProps) {
  const [expanded, setExpanded] = useState<boolean>(() =>
    readPersistedExpanded(persistKey, defaultExpanded),
  );

  const toggle = useCallback(
    (event?: React.MouseEvent) => {
      // The chevron sits above the header's navigation link overlay; keep the
      // click from following the row's href.
      event?.preventDefault();
      event?.stopPropagation();
      setExpanded((prev) => {
        const next = !prev;
        if (persistKey && typeof window !== "undefined") {
          window.localStorage.setItem(
            `${GROUP_EXPANDED_PREFIX}${persistKey}`,
            String(next),
          );
        }
        return next;
      });
    },
    [persistKey],
  );

  const canToggle = !folded && hasChildren;
  const isExpanded = forceExpanded || expanded;

  return (
    <div className="flex flex-col">
      <div
        className={cn(
          "relative isolate",
          // On row hover, fade the base icon out so the overlaid chevron reads
          // as the icon morphing into a toggle.
          canToggle &&
            "[&_.opal-content-sm-icon]:transition-opacity [&_.opal-content-sm-icon]:duration-100 [&:hover_.opal-content-sm-icon]:opacity-0 [&:hover_.navgroup-reveal]:opacity-100 [&:hover_.navgroup-reveal]:pointer-events-auto",
        )}
      >
        <SidebarTab
          icon={icon}
          folded={folded}
          href={href as Route | undefined}
          selected={selected}
          onClick={!href && canToggle ? toggle : undefined}
          rightChildren={
            !folded && action ? (
              <div className="navgroup-reveal opacity-0 pointer-events-none transition-opacity duration-100">
                {action}
              </div>
            ) : undefined
          }
        >
          {label}
        </SidebarTab>

        {canToggle && (
          <button
            type="button"
            aria-expanded={isExpanded}
            aria-label={isExpanded ? `Collapse ${label}` : `Expand ${label}`}
            onClick={toggle}
            className="navgroup-reveal absolute left-1 top-0 bottom-0 z-[101] flex w-6 items-center justify-center opacity-0 pointer-events-none transition-opacity duration-100"
          >
            <SvgChevronRight
              aria-hidden
              className={cn(
                "h-4 w-4 stroke-text-03 transition-transform duration-150",
                isExpanded && "rotate-90",
              )}
            />
          </button>
        )}
      </div>

      {canToggle && isExpanded && (
        <div className="flex flex-col pl-2">{children}</div>
      )}
    </div>
  );
}
