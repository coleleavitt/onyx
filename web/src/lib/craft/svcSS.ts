import type { Route } from "next";
import { redirect } from "next/navigation";
import { requireAuth } from "@/lib/auth/svcSS";
import { fetchSettingsSS } from "@/lib/settings/svcSS";

export async function requireOnyxCraftAccessSS(): Promise<void> {
  const [authResult, settings] = await Promise.all([
    requireAuth(),
    fetchSettingsSS(),
  ]);
  if (authResult.redirect) {
    redirect(authResult.redirect as Route);
  }

  if (settings?.settings?.onyx_craft_enabled !== true) {
    redirect("/app" as Route);
  }
}
