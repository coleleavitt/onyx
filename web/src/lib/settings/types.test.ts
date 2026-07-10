import {
  ApplicationStatus,
  QueryHistoryType,
  type AppSettings,
  toSettings,
} from "@/lib/settings/types";

function buildAppSettings(): AppSettings {
  return {
    anonymous_user_enabled: false,
    invite_only_enabled: false,
    notifications: [],
    needs_reindexing: false,
    gpu_enabled: false,
    application_status: ApplicationStatus.ACTIVE,
    auto_scroll: true,
    temperature_override_enabled: true,
    query_history_type: QueryHistoryType.NORMAL,
    enterprise: null,
    appName: "Foundations AI",
    logoUrl: "/api/enterprise-settings/logo",
    darkLogoUrl: null,
    faviconUrl: "/api/enterprise-settings/favicon",
    wordmarkUrl: null,
    darkWordmarkUrl: null,
    vectorDbEnabled: true,
    isLoading: false,
    error: undefined,
  };
}

test("toSettings removes all derived branding fields", () => {
  const settings = toSettings(buildAppSettings());

  expect(settings).not.toHaveProperty("enterprise");
  expect(settings).not.toHaveProperty("appName");
  expect(settings).not.toHaveProperty("logoUrl");
  expect(settings).not.toHaveProperty("darkLogoUrl");
  expect(settings).not.toHaveProperty("faviconUrl");
  expect(settings).not.toHaveProperty("wordmarkUrl");
  expect(settings).not.toHaveProperty("darkWordmarkUrl");
});
