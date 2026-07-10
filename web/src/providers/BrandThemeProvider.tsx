"use client";

import { useEffect } from "react";
import { getBrandAccentVariables } from "@/lib/settings/branding";
import { useSettings } from "@/lib/settings/hooks";

const ACCENT_PROPERTIES = [
  "--theme-primary-04",
  "--theme-primary-05",
  "--theme-primary-06",
] as const;

interface BrandThemeProviderProps {
  children: React.ReactNode;
}

export default function BrandThemeProvider({
  children,
}: BrandThemeProviderProps) {
  const { enterprise, faviconUrl } = useSettings();

  useEffect(() => {
    const root = document.documentElement;
    const variables = getBrandAccentVariables(enterprise?.accent_color);

    for (const property of ACCENT_PROPERTIES) {
      if (variables) {
        root.style.setProperty(property, variables[property]);
      } else {
        root.style.removeProperty(property);
      }
    }

    return () => {
      for (const property of ACCENT_PROPERTIES) {
        root.style.removeProperty(property);
      }
    };
  }, [enterprise?.accent_color]);

  useEffect(() => {
    if (!faviconUrl) return;
    const existing =
      document.querySelector<HTMLLinkElement>("link[rel~='icon']");
    const favicon = existing ?? document.createElement("link");
    favicon.rel = "icon";
    favicon.href = faviconUrl;
    if (!existing) document.head.appendChild(favicon);
  }, [faviconUrl]);

  return children;
}
