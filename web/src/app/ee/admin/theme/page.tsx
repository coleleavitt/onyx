"use client";

import { Button } from "@opal/components";
import { SettingsLayouts } from "@opal/layouts";
import { Form, Formik } from "formik";
import { useEffect, useMemo, useRef, useState } from "react";
import useSWR, { mutate } from "swr";
import * as Yup from "yup";
import AdditionalBrandSettings from "@/app/ee/admin/theme/AdditionalBrandSettings";
import {
  AppearanceThemeSettings,
  type AppearanceThemeSettingsRef,
} from "@/app/ee/admin/theme/AppearanceThemeSettings";
import BrandProfileSettings, {
  DEFAULT_BRAND_SELECTION,
} from "@/app/ee/admin/theme/BrandProfileSettings";
import { toast } from "@/hooks/useToast";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { errorHandlingFetcher } from "@/lib/fetcher";
import type {
  BrandAppearanceSettings,
  BrandAssetKind,
  BrandProfile,
  EnterpriseSettings,
} from "@/lib/settings/types";
import { SWR_KEYS } from "@/lib/swr-keys";

const route = ADMIN_ROUTES.THEME;
const DEFAULT_ASSET_KEY = "__default__";

const CHAR_LIMITS = {
  application_name: 50,
  custom_greeting_message: 50,
  custom_header_content: 100,
  custom_lower_disclaimer_content: 200,
  custom_popup_header: 100,
  custom_popup_content: 500,
  consent_screen_prompt: 200,
  login_subtitle: 100,
};

const ASSET_FLAG_BY_KIND: Record<
  BrandAssetKind,
  keyof BrandAppearanceSettings
> = {
  logo: "use_custom_logo",
  dark_logo: "use_custom_dark_logo",
  favicon: "use_custom_favicon",
  wordmark: "use_custom_wordmark",
  dark_wordmark: "use_custom_dark_wordmark",
};

type AssetDrafts = Record<string, Partial<Record<BrandAssetKind, File | null>>>;

function toAppearanceSettings(
  source: BrandAppearanceSettings
): BrandAppearanceSettings {
  return {
    application_name: source.application_name || null,
    use_custom_logo: source.use_custom_logo,
    use_custom_dark_logo: source.use_custom_dark_logo,
    use_custom_favicon: source.use_custom_favicon,
    use_custom_wordmark: source.use_custom_wordmark,
    use_custom_dark_wordmark: source.use_custom_dark_wordmark,
    use_custom_logotype: source.use_custom_logotype,
    logo_display_style: source.logo_display_style,
    accent_color: source.accent_color || null,
    login_background_color: source.login_background_color || null,
    login_background_url: source.login_background_url || null,
    login_subtitle: source.login_subtitle || null,
    custom_nav_items: source.custom_nav_items,
    two_lines_for_chat_header: source.two_lines_for_chat_header,
    custom_lower_disclaimer_content:
      source.custom_lower_disclaimer_content || null,
    custom_header_content: source.custom_header_content || null,
    custom_popup_header: source.custom_popup_header || null,
    custom_popup_content: source.custom_popup_content || null,
    enable_consent_screen: source.enable_consent_screen,
    consent_screen_prompt: source.consent_screen_prompt || null,
    show_first_visit_notice: source.show_first_visit_notice,
    custom_greeting_message: source.custom_greeting_message || null,
    custom_help_link_url: source.custom_help_link_url || null,
    custom_help_link_label: source.custom_help_link_label || null,
    hide_onyx_branding: source.hide_onyx_branding,
  };
}

function getSelectedAppearance(
  settings: EnterpriseSettings,
  selectedBrandId: string
): BrandAppearanceSettings {
  if (selectedBrandId === DEFAULT_BRAND_SELECTION) {
    return toAppearanceSettings(settings);
  }
  const profile = settings.brand_profiles.find(
    (candidate) => candidate.id === selectedBrandId
  );
  return toAppearanceSettings(profile ?? settings);
}

function replaceSelectedAppearance(
  settings: EnterpriseSettings,
  selectedBrandId: string,
  appearance: BrandAppearanceSettings
): EnterpriseSettings {
  if (selectedBrandId === DEFAULT_BRAND_SELECTION) {
    return { ...settings, ...appearance };
  }
  return {
    ...settings,
    brand_profiles: settings.brand_profiles.map((profile) =>
      profile.id === selectedBrandId ? { ...profile, ...appearance } : profile
    ),
  };
}

function getInitialValues(appearance: BrandAppearanceSettings) {
  return {
    ...appearance,
    application_name: appearance.application_name ?? "",
    logo_display_style: appearance.logo_display_style ?? "logo_and_name",
    custom_greeting_message: appearance.custom_greeting_message ?? "",
    custom_header_content: appearance.custom_header_content ?? "",
    custom_lower_disclaimer_content:
      appearance.custom_lower_disclaimer_content ?? "",
    custom_popup_header: appearance.custom_popup_header ?? "",
    custom_popup_content: appearance.custom_popup_content ?? "",
    consent_screen_prompt: appearance.consent_screen_prompt ?? "",
    custom_help_link_url: appearance.custom_help_link_url ?? "",
    custom_help_link_label: appearance.custom_help_link_label ?? "",
    accent_color: appearance.accent_color ?? "",
    login_background_color: appearance.login_background_color ?? "",
    login_background_url: appearance.login_background_url ?? "",
    login_subtitle: appearance.login_subtitle ?? "",
  };
}

function disablePendingAssetFlags(
  settings: EnterpriseSettings,
  assetDrafts: AssetDrafts
): EnterpriseSettings {
  let safeSettings = settings;
  for (const [assetKey, assets] of Object.entries(assetDrafts)) {
    const brandId =
      assetKey === DEFAULT_ASSET_KEY ? DEFAULT_BRAND_SELECTION : assetKey;
    let appearance = getSelectedAppearance(safeSettings, brandId);
    for (const [assetKind, file] of Object.entries(assets) as [
      BrandAssetKind,
      File | null,
    ][]) {
      if (file instanceof File) {
        appearance = {
          ...appearance,
          [ASSET_FLAG_BY_KIND[assetKind]]: false,
        };
      }
    }
    safeSettings = replaceSelectedAppearance(safeSettings, brandId, appearance);
  }
  return safeSettings;
}

async function putEnterpriseSettings(
  settings: EnterpriseSettings
): Promise<void> {
  const response = await fetch("/api/admin/enterprise-settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Failed to update appearance settings.");
  }
}

async function uploadPendingAssets(assetDrafts: AssetDrafts): Promise<void> {
  for (const [assetKey, assets] of Object.entries(assetDrafts)) {
    for (const [assetKind, file] of Object.entries(assets) as [
      BrandAssetKind,
      File | null,
    ][]) {
      if (!(file instanceof File)) continue;

      const params = new URLSearchParams();
      if (assetKey !== DEFAULT_ASSET_KEY) params.set("brand_id", assetKey);
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(
        `/api/admin/enterprise-settings/brand-assets/${assetKind}?${params}`,
        { method: "PUT", body: formData }
      );
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? `Failed to upload ${assetKind}.`);
      }
    }
  }
}

const validationSchema = Yup.object().shape({
  application_name: Yup.string()
    .trim()
    .max(
      CHAR_LIMITS.application_name,
      `Maximum ${CHAR_LIMITS.application_name} characters`
    )
    .nullable(),
  logo_display_style: Yup.string()
    .oneOf(["logo_and_name", "logo_only", "name_only"])
    .required(),
  use_custom_logo: Yup.boolean().required(),
  use_custom_dark_logo: Yup.boolean().required(),
  use_custom_favicon: Yup.boolean().required(),
  use_custom_wordmark: Yup.boolean().required(),
  use_custom_dark_wordmark: Yup.boolean().required(),
  accent_color: Yup.string()
    .matches(/^(|#[0-9a-fA-F]{6})$/, "Use the #RRGGBB format")
    .nullable(),
  login_background_color: Yup.string()
    .matches(/^(|#[0-9a-fA-F]{6})$/, "Use the #RRGGBB format")
    .nullable(),
  login_background_url: Yup.string()
    .nullable()
    .test(
      "background-url",
      "Use an HTTPS URL or root-relative path",
      (value) =>
        !value ||
        (value.startsWith("/") && !value.startsWith("//")) ||
        Yup.string().url().isValidSync(value)
    ),
  login_subtitle: Yup.string()
    .max(
      CHAR_LIMITS.login_subtitle,
      `Maximum ${CHAR_LIMITS.login_subtitle} characters`
    )
    .nullable(),
  custom_greeting_message: Yup.string()
    .max(
      CHAR_LIMITS.custom_greeting_message,
      `Maximum ${CHAR_LIMITS.custom_greeting_message} characters`
    )
    .nullable(),
  custom_header_content: Yup.string()
    .max(
      CHAR_LIMITS.custom_header_content,
      `Maximum ${CHAR_LIMITS.custom_header_content} characters`
    )
    .nullable(),
  custom_lower_disclaimer_content: Yup.string()
    .max(
      CHAR_LIMITS.custom_lower_disclaimer_content,
      `Maximum ${CHAR_LIMITS.custom_lower_disclaimer_content} characters`
    )
    .nullable(),
  show_first_visit_notice: Yup.boolean().nullable(),
  custom_popup_header: Yup.string()
    .max(
      CHAR_LIMITS.custom_popup_header,
      `Maximum ${CHAR_LIMITS.custom_popup_header} characters`
    )
    .when("show_first_visit_notice", {
      is: true,
      then: (schema) => schema.required("Notice Header is required"),
      otherwise: (schema) => schema.nullable(),
    }),
  custom_popup_content: Yup.string()
    .max(
      CHAR_LIMITS.custom_popup_content,
      `Maximum ${CHAR_LIMITS.custom_popup_content} characters`
    )
    .when("show_first_visit_notice", {
      is: true,
      then: (schema) => schema.required("Notice Content is required"),
      otherwise: (schema) => schema.nullable(),
    }),
  enable_consent_screen: Yup.boolean().nullable(),
  consent_screen_prompt: Yup.string()
    .max(
      CHAR_LIMITS.consent_screen_prompt,
      `Maximum ${CHAR_LIMITS.consent_screen_prompt} characters`
    )
    .when("enable_consent_screen", {
      is: true,
      then: (schema) => schema.required("Notice Consent Prompt is required"),
      otherwise: (schema) => schema.nullable(),
    }),
  custom_help_link_label: Yup.string().nullable(),
  custom_help_link_url: Yup.string()
    .nullable()
    .when("custom_help_link_label", {
      is: (label: string | null | undefined) => Boolean(label?.trim()),
      then: (schema) =>
        schema
          .required("URL is required when a label is set")
          .url("Must be a valid URL"),
      otherwise: (schema) =>
        schema.test(
          "optional-url",
          "Must be a valid URL",
          (value) => !value || Yup.string().url().isValidSync(value)
        ),
    }),
  hide_onyx_branding: Yup.boolean().nullable(),
});

export default function ThemePage() {
  const { data: storedSettings, mutate: mutateAdminSettings } =
    useSWR<EnterpriseSettings>(
      SWR_KEYS.adminEnterpriseSettings,
      errorHandlingFetcher,
      { revalidateOnFocus: false }
    );
  const [draftSettings, setDraftSettings] = useState<EnterpriseSettings | null>(
    null
  );
  const [selectedBrandId, setSelectedBrandId] = useState(
    DEFAULT_BRAND_SELECTION
  );
  const [assetDrafts, setAssetDrafts] = useState<AssetDrafts>({});
  const [assetVersion, setAssetVersion] = useState(0);
  const [configurationDirty, setConfigurationDirty] = useState(false);
  const appearanceSettingsRef = useRef<AppearanceThemeSettingsRef>(null);

  useEffect(() => {
    if (storedSettings && !draftSettings) setDraftSettings(storedSettings);
  }, [draftSettings, storedSettings]);

  const selectedAssetKey =
    selectedBrandId === DEFAULT_BRAND_SELECTION
      ? DEFAULT_ASSET_KEY
      : selectedBrandId;
  const selectedAssets = assetDrafts[selectedAssetKey] ?? {};
  const hasAssetUploads = useMemo(
    () =>
      Object.values(assetDrafts).some((assets) =>
        Object.values(assets).some((file) => file instanceof File)
      ),
    [assetDrafts]
  );

  if (!draftSettings) return null;
  const activeDraftSettings = draftSettings;

  const activeAppearance = getSelectedAppearance(
    activeDraftSettings,
    selectedBrandId
  );

  return (
    <Formik
      enableReinitialize
      initialValues={getInitialValues(activeAppearance)}
      validationSchema={validationSchema}
      validateOnChange={false}
      onSubmit={async (values, formikHelpers) => {
        const finalSettings = replaceSelectedAppearance(
          draftSettings,
          selectedBrandId,
          toAppearanceSettings(values)
        );
        const provisionalSettings = disablePendingAssetFlags(
          finalSettings,
          assetDrafts
        );

        try {
          if (hasAssetUploads) {
            await putEnterpriseSettings(provisionalSettings);
            await uploadPendingAssets(assetDrafts);
          }
          await putEnterpriseSettings(finalSettings);
          setDraftSettings(finalSettings);
          setAssetDrafts({});
          setAssetVersion((version) => version + 1);
          setConfigurationDirty(false);
          formikHelpers.resetForm({ values });
          await Promise.all([
            mutateAdminSettings(),
            mutate(SWR_KEYS.enterpriseSettings),
          ]);
          toast.success("Appearance settings saved successfully!");
        } catch (error) {
          toast.error(
            error instanceof Error
              ? error.message
              : "Failed to save appearance settings."
          );
        } finally {
          formikHelpers.setSubmitting(false);
        }
      }}
    >
      {({
        isSubmitting,
        dirty,
        values,
        validateForm,
        setErrors,
        submitForm,
      }) => {
        function saveCurrentDraft(): EnterpriseSettings {
          const updatedSettings = replaceSelectedAppearance(
            activeDraftSettings,
            selectedBrandId,
            toAppearanceSettings(values)
          );
          setDraftSettings(updatedSettings);
          if (dirty) setConfigurationDirty(true);
          return updatedSettings;
        }

        function updateProfile(updatedProfile: BrandProfile) {
          setDraftSettings((current) =>
            current
              ? {
                  ...current,
                  brand_profiles: current.brand_profiles.map((profile) =>
                    profile.id === updatedProfile.id ? updatedProfile : profile
                  ),
                }
              : current
          );
          setConfigurationDirty(true);
        }

        return (
          <Form className="w-full h-full">
            <SettingsLayouts.Root>
              <SettingsLayouts.Header
                title={route.title}
                description="Customize how the application appears for each public hostname."
                icon={route.icon}
                rightChildren={
                  <Button
                    disabled={
                      isSubmitting ||
                      (!dirty && !configurationDirty && !hasAssetUploads)
                    }
                    type="button"
                    onClick={async () => {
                      const errors = await validateForm();
                      if (Object.keys(errors).length > 0) {
                        setErrors(errors);
                        appearanceSettingsRef.current?.focusFirstError(errors);
                        return;
                      }
                      await submitForm();
                    }}
                  >
                    {isSubmitting ? "Applying..." : "Apply Changes"}
                  </Button>
                }
              />
              <SettingsLayouts.Body>
                <BrandProfileSettings
                  profiles={draftSettings.brand_profiles}
                  selectedBrandId={selectedBrandId}
                  defaultBrandId={draftSettings.default_brand_id}
                  onSelectBrand={(brandId) => {
                    saveCurrentDraft();
                    setSelectedBrandId(brandId);
                  }}
                  onAddBrand={() => {
                    const settingsWithCurrentDraft = saveCurrentDraft();
                    const brandId = `brand-${crypto.randomUUID().slice(0, 8)}`;
                    const newProfile: BrandProfile = {
                      ...toAppearanceSettings(settingsWithCurrentDraft),
                      use_custom_logo: false,
                      use_custom_dark_logo: false,
                      use_custom_favicon: false,
                      use_custom_wordmark: false,
                      use_custom_dark_wordmark: false,
                      use_custom_logotype: false,
                      id: brandId,
                      name: "New brand",
                      hostnames: [],
                    };
                    setDraftSettings({
                      ...settingsWithCurrentDraft,
                      brand_profiles: [
                        ...settingsWithCurrentDraft.brand_profiles,
                        newProfile,
                      ],
                    });
                    setConfigurationDirty(true);
                    setSelectedBrandId(brandId);
                  }}
                  onRemoveBrand={(brandId) => {
                    if (!window.confirm("Delete this brand profile?")) return;
                    setDraftSettings((current) =>
                      current
                        ? {
                            ...current,
                            brand_profiles: current.brand_profiles.filter(
                              (profile) => profile.id !== brandId
                            ),
                            default_brand_id:
                              current.default_brand_id === brandId
                                ? null
                                : current.default_brand_id,
                          }
                        : current
                    );
                    setAssetDrafts((current) => {
                      const next = { ...current };
                      delete next[brandId];
                      return next;
                    });
                    setConfigurationDirty(true);
                    setSelectedBrandId(DEFAULT_BRAND_SELECTION);
                  }}
                  onUpdateBrand={updateProfile}
                  onDefaultBrandChange={(brandId) => {
                    saveCurrentDraft();
                    setDraftSettings((current) =>
                      current
                        ? { ...current, default_brand_id: brandId }
                        : current
                    );
                    setConfigurationDirty(true);
                  }}
                />

                <AppearanceThemeSettings
                  ref={appearanceSettingsRef}
                  brandId={
                    selectedBrandId === DEFAULT_BRAND_SELECTION
                      ? null
                      : selectedBrandId
                  }
                  selectedLogo={selectedAssets.logo ?? null}
                  setSelectedLogo={(file) =>
                    setAssetDrafts((current) => ({
                      ...current,
                      [selectedAssetKey]: {
                        ...current[selectedAssetKey],
                        logo: file,
                      },
                    }))
                  }
                  logoVersion={assetVersion}
                  charLimits={CHAR_LIMITS}
                />

                <AdditionalBrandSettings
                  brandId={
                    selectedBrandId === DEFAULT_BRAND_SELECTION
                      ? null
                      : selectedBrandId
                  }
                  selectedAssets={selectedAssets}
                  onAssetChange={(assetKind, file) =>
                    setAssetDrafts((current) => ({
                      ...current,
                      [selectedAssetKey]: {
                        ...current[selectedAssetKey],
                        [assetKind]: file,
                      },
                    }))
                  }
                  assetVersion={assetVersion}
                />
              </SettingsLayouts.Body>
            </SettingsLayouts.Root>
          </Form>
        );
      }}
    </Formik>
  );
}
