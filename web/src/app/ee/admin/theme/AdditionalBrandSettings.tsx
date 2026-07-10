"use client";

import { Button, Divider, InputTypeIn, Text } from "@opal/components";
import { cn } from "@opal/utils";
import { useFormikContext } from "formik";
import { useEffect, useMemo } from "react";
import {
  LOGIN_BACKGROUND_CUSTOM,
  LOGIN_BACKGROUND_OPTIONS,
  getLoginBackgroundOptionByUrl,
} from "@/lib/constants/loginBackgrounds";
import { FormField } from "@/refresh-components/form/FormField";
import InputImage from "@/refresh-components/inputs/InputImage";
import type {
  BrandAppearanceSettings,
  BrandAssetKind,
} from "@/lib/settings/types";

interface AdditionalBrandSettingsProps {
  brandId: string | null;
  selectedAssets: Partial<Record<BrandAssetKind, File | null>>;
  onAssetChange: (assetKind: BrandAssetKind, file: File | null) => void;
  assetVersion: number;
}

interface AssetDefinition {
  kind: BrandAssetKind;
  enabledField:
    | "use_custom_dark_logo"
    | "use_custom_favicon"
    | "use_custom_wordmark"
    | "use_custom_dark_wordmark";
  label: string;
  description: string;
  wide?: boolean;
}

const ASSET_DEFINITIONS: AssetDefinition[] = [
  {
    kind: "dark_logo",
    enabledField: "use_custom_dark_logo",
    label: "Dark Mode Logo",
    description: "Optional logo mark for dark mode.",
  },
  {
    kind: "favicon",
    enabledField: "use_custom_favicon",
    label: "Browser Icon",
    description: "Square favicon shown in browser tabs.",
  },
  {
    kind: "wordmark",
    enabledField: "use_custom_wordmark",
    label: "Wordmark",
    description: "Wide logo used by the Logo Only display style.",
    wide: true,
  },
  {
    kind: "dark_wordmark",
    enabledField: "use_custom_dark_wordmark",
    label: "Dark Mode Wordmark",
    description: "Optional wide wordmark for dark mode.",
    wide: true,
  },
];

function buildAssetUrl(
  assetKind: BrandAssetKind,
  brandId: string | null,
  assetVersion: number
): string {
  const params = new URLSearchParams({ v: String(assetVersion) });
  if (brandId) params.set("brand_id", brandId);
  return `/api/admin/enterprise-settings/brand-assets/${assetKind}?${params}`;
}

interface BrandAssetInputProps {
  definition: AssetDefinition;
  brandId: string | null;
  enabled: boolean;
  selectedFile: File | null | undefined;
  assetVersion: number;
  onChange: (file: File | null) => void;
}

function BrandAssetInput({
  definition,
  brandId,
  enabled,
  selectedFile,
  assetVersion,
  onChange,
}: BrandAssetInputProps) {
  const objectUrl = useMemo(
    () => (selectedFile ? URL.createObjectURL(selectedFile) : null),
    [selectedFile]
  );
  useEffect(
    () => () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    },
    [objectUrl]
  );

  const source =
    objectUrl ??
    (enabled
      ? buildAssetUrl(definition.kind, brandId, assetVersion)
      : undefined);

  return (
    <FormField state="idle">
      <FormField.Label>{definition.label}</FormField.Label>
      <FormField.Control>
        <InputImage
          src={source}
          alt={definition.label}
          shape={definition.wide ? "rounded" : "circle"}
          width={definition.wide ? 180 : 96}
          height={96}
          onDrop={onChange}
          onRemove={() => onChange(null)}
        />
      </FormField.Control>
      <FormField.Description>{definition.description}</FormField.Description>
    </FormField>
  );
}

export default function AdditionalBrandSettings({
  brandId,
  selectedAssets,
  onAssetChange,
  assetVersion,
}: AdditionalBrandSettingsProps) {
  const { errors, touched, values, setFieldValue } =
    useFormikContext<BrandAppearanceSettings>();
  const currentBackgroundOption = getLoginBackgroundOptionByUrl(
    values.login_background_url
  );
  const selectedBackgroundId =
    currentBackgroundOption?.id ??
    (values.login_background_url ? LOGIN_BACKGROUND_CUSTOM : "none");
  const accentColorError =
    touched.accent_color && typeof errors.accent_color === "string"
      ? errors.accent_color
      : null;
  const loginBackgroundColorError =
    touched.login_background_color &&
    typeof errors.login_background_color === "string"
      ? errors.login_background_color
      : null;
  const loginBackgroundUrlError =
    touched.login_background_url &&
    typeof errors.login_background_url === "string"
      ? errors.login_background_url
      : null;

  return (
    <div className="flex w-full flex-col gap-4">
      <Divider />
      <div className="flex flex-col gap-1">
        <Text as="h2" font="heading-h3" color="text-05">
          Brand Assets
        </Text>
        <Text as="p" font="main-ui-body" color="text-03">
          Add mode-specific assets while keeping the primary application logo
          above as the fallback.
        </Text>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {ASSET_DEFINITIONS.map((definition) => (
          <BrandAssetInput
            key={definition.kind}
            definition={definition}
            brandId={brandId}
            enabled={values[definition.enabledField]}
            selectedFile={selectedAssets[definition.kind]}
            assetVersion={assetVersion}
            onChange={(file) => {
              onAssetChange(definition.kind, file);
              setFieldValue(definition.enabledField, Boolean(file));
            }}
          />
        ))}
      </div>

      <Divider />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField state={accentColorError ? "error" : "idle"}>
          <FormField.Label>Accent Color</FormField.Label>
          <FormField.Control asChild>
            <InputTypeIn
              clearButton
              variant={accentColorError ? "error" : undefined}
              placeholder="#e3530f"
              value={values.accent_color ?? ""}
              rightChildren={
                values.accent_color ? (
                  <div
                    aria-label={`Accent color ${values.accent_color}`}
                    className="h-5 w-5 rounded-full border border-border-02"
                    style={{ backgroundColor: values.accent_color }}
                  />
                ) : undefined
              }
              onChange={(event) =>
                setFieldValue("accent_color", event.target.value || null)
              }
            />
          </FormField.Control>
          <FormField.Description>
            Applies to primary actions without replacing the Onyx color system.
          </FormField.Description>
          <FormField.Message messages={{ error: accentColorError }} />
        </FormField>

        <FormField state={loginBackgroundColorError ? "error" : "idle"}>
          <FormField.Label>Login Background Color</FormField.Label>
          <FormField.Control asChild>
            <InputTypeIn
              clearButton
              variant={loginBackgroundColorError ? "error" : undefined}
              placeholder="#1a2744"
              value={values.login_background_color ?? ""}
              rightChildren={
                values.login_background_color ? (
                  <div
                    aria-label={`Login background ${values.login_background_color}`}
                    className="h-5 w-5 rounded-full border border-border-02"
                    style={{ backgroundColor: values.login_background_color }}
                  />
                ) : undefined
              }
              onChange={(event) =>
                setFieldValue(
                  "login_background_color",
                  event.target.value || null
                )
              }
            />
          </FormField.Control>
          <FormField.Message messages={{ error: loginBackgroundColorError }} />
        </FormField>
      </div>

      <FormField state="idle">
        <FormField.Label>Login Background</FormField.Label>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {LOGIN_BACKGROUND_OPTIONS.map((option) => {
            const selected = selectedBackgroundId === option.id;
            return (
              <button
                key={option.id}
                type="button"
                aria-pressed={selected}
                className={cn(
                  "group flex h-24 flex-col justify-end overflow-hidden rounded-08 border bg-background-tint-01 p-2 text-left transition-colors",
                  selected
                    ? "border-link bg-link/10"
                    : "border-border-02 hover:border-border-03"
                )}
                style={
                  option.thumbnail
                    ? {
                        backgroundImage: `linear-gradient(to top, rgb(0 0 0 / 0.7), rgb(0 0 0 / 0.05)), url("${option.thumbnail}")`,
                        backgroundPosition: "center",
                        backgroundSize: "cover",
                      }
                    : undefined
                }
                onClick={() =>
                  setFieldValue("login_background_url", option.src || null)
                }
              >
                <span
                  className={cn(
                    "font-main-ui-action",
                    option.thumbnail ? "text-white" : "text-text-04"
                  )}
                >
                  {option.label}
                </span>
              </button>
            );
          })}
        </div>
        <FormField.Description>
          Choose a built-in image, then use custom URL only when the image is
          served elsewhere.
        </FormField.Description>
        {selectedBackgroundId !== LOGIN_BACKGROUND_CUSTOM && (
          <div>
            <Button
              type="button"
              prominence="tertiary"
              onClick={() => setFieldValue("login_background_url", "https://")}
            >
              Use custom URL
            </Button>
          </div>
        )}
      </FormField>

      {selectedBackgroundId === LOGIN_BACKGROUND_CUSTOM && (
        <FormField state={loginBackgroundUrlError ? "error" : "idle"}>
          <FormField.Label>Custom Login Background URL</FormField.Label>
          <FormField.Control asChild>
            <InputTypeIn
              clearButton
              variant={loginBackgroundUrlError ? "error" : undefined}
              placeholder="https://example.com/background.jpg"
              value={values.login_background_url ?? ""}
              onChange={(event) =>
                setFieldValue(
                  "login_background_url",
                  event.target.value || null
                )
              }
            />
          </FormField.Control>
          <FormField.Description>
            Use an HTTPS URL or a root-relative path served by this deployment.
          </FormField.Description>
          <FormField.Message messages={{ error: loginBackgroundUrlError }} />
        </FormField>
      )}

      <FormField state="idle">
        <FormField.Label>Login Subtitle</FormField.Label>
        <FormField.Control asChild>
          <InputTypeIn
            clearButton
            placeholder="Your AI workspace for company knowledge"
            value={values.login_subtitle ?? ""}
            onChange={(event) =>
              setFieldValue("login_subtitle", event.target.value || null)
            }
          />
        </FormField.Control>
        <FormField.Description>
          Short supporting text shown under the application name during sign in.
        </FormField.Description>
      </FormField>
    </div>
  );
}
