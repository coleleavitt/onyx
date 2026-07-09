import { SERVER_SIDE_ONLY__PAID_ENTERPRISE_FEATURES_ENABLED } from "@/lib/constants";
import { fetchStandardSettingsSS } from "@/lib/settings/svcSS";
import EEFeatureRedirect from "@/app/ee/EEFeatureRedirect";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // First check build-time constant (fast path)
  if (!SERVER_SIDE_ONLY__PAID_ENTERPRISE_FEATURES_ENABLED) {
    return <EEFeatureRedirect />;
  }

  // Runtime settings are the client/server source of truth for stripped builds.
  try {
    const settings = await fetchStandardSettingsSS();
    if (settings?.ee_features_enabled === false) {
      return <EEFeatureRedirect />;
    }
  } catch (error) {
    // If settings fetch fails, allow access (fail open for better UX)
    console.error("Failed to fetch settings for EE check:", error);
  }

  return children;
}
