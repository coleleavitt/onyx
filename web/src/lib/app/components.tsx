"use client";

import { useSettings } from "@/lib/settings/hooks";
import {
  DEFAULT_LOGO_SIZE_PX,
  NEXT_PUBLIC_DO_NOT_USE_TOGGLE_OFF_DANSWER_POWERED,
} from "@/lib/constants";
import { cn } from "@opal/utils";
import Text from "@/refresh-components/texts/Text";
import Truncated from "@/refresh-components/texts/Truncated";
import { SvgOnyxLogo, SvgOnyxLogoTyped } from "@opal/logos";
import { useTheme } from "next-themes";

export interface LogoProps {
  folded?: boolean;
  size?: number;
  className?: string;
  // Always render the real Onyx logo, ignoring enterprise white-label settings
  // (custom logo / application name). Used by Onyx-branded surfaces like Craft.
  onyxBranded?: boolean;
}

export function Logo({ folded, size, className, onyxBranded }: LogoProps) {
  const resolvedSize = size ?? DEFAULT_LOGO_SIZE_PX;
  const { enterprise, logoUrl, darkLogoUrl, wordmarkUrl, darkWordmarkUrl } =
    useSettings();
  const { resolvedTheme } = useTheme();
  const logoDisplayStyle = enterprise?.logo_display_style;
  const applicationName = enterprise?.application_name;
  const resolvedLogoUrl =
    resolvedTheme === "dark" && darkLogoUrl ? darkLogoUrl : logoUrl;
  const resolvedWordmarkUrl =
    resolvedTheme === "dark" && darkWordmarkUrl ? darkWordmarkUrl : wordmarkUrl;

  if (onyxBranded) {
    return folded ? (
      <SvgOnyxLogo size={resolvedSize} className={cn("shrink-0", className)} />
    ) : (
      <SvgOnyxLogoTyped size={resolvedSize} className={className} />
    );
  }

  const logo = resolvedLogoUrl ? (
    <div
      className={cn(
        "aspect-square relative flex shrink-0 items-center justify-center",
        className
      )}
      style={{ height: resolvedSize }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        alt="Logo"
        src={resolvedLogoUrl}
        className="h-full w-full object-contain object-center"
      />
    </div>
  ) : (
    <SvgOnyxLogo size={resolvedSize} className={cn("shrink-0", className)} />
  );

  const wordmark = resolvedWordmarkUrl ? (
    <div
      className={cn("relative min-w-0 shrink", className)}
      style={{ height: resolvedSize, width: Math.min(resolvedSize * 6, 180) }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        alt={applicationName || "Application logo"}
        src={resolvedWordmarkUrl}
        className="h-full w-full object-contain object-left"
      />
    </div>
  ) : null;

  const renderNameAndPoweredBy = (opts: {
    includeLogo: boolean;
    includeName: boolean;
  }) => {
    return (
      <div className="flex min-w-0 gap-2">
        {opts.includeLogo && logo}
        {!folded && (
          /* H3 text is 4px larger (28px) than the Logo icon (24px), so negative margin hack. */
          <div className="flex flex-1 flex-col -mt-0.5">
            {opts.includeName && (
              <Truncated headingH3>{applicationName}</Truncated>
            )}
            {!NEXT_PUBLIC_DO_NOT_USE_TOGGLE_OFF_DANSWER_POWERED &&
              !enterprise?.hide_onyx_branding && (
                <Text
                  secondaryBody
                  text03
                  className={"line-clamp-1 truncate"}
                  nowrap
                >
                  Powered by Onyx
                </Text>
              )}
          </div>
        )}
      </div>
    );
  };

  // Handle "logo_only" display style
  if (logoDisplayStyle === "logo_only") {
    if (!folded && wordmark) {
      return (
        <div className="flex min-w-0 flex-col gap-1">
          {wordmark}
          {!NEXT_PUBLIC_DO_NOT_USE_TOGGLE_OFF_DANSWER_POWERED &&
            !enterprise?.hide_onyx_branding && (
              <Text secondaryBody text03 className="truncate" nowrap>
                Powered by Onyx
              </Text>
            )}
        </div>
      );
    }
    return renderNameAndPoweredBy({ includeLogo: true, includeName: false });
  }

  // Handle "name_only" display style
  if (logoDisplayStyle === "name_only") {
    return renderNameAndPoweredBy({ includeLogo: false, includeName: true });
  }

  // Handle "logo_and_name" or default behavior
  return applicationName ? (
    renderNameAndPoweredBy({ includeLogo: true, includeName: true })
  ) : folded ? (
    <SvgOnyxLogo size={resolvedSize} className={cn("shrink-0", className)} />
  ) : (
    <SvgOnyxLogoTyped size={resolvedSize} className={className} />
  );
}
