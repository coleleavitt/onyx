import { unstable_noStore as noStore } from "next/cache";
import { requireOnyxCraftAccessSS } from "@/lib/craft/svcSS";

export interface LayoutProps {
  children: React.ReactNode;
}

/**
 * Build Layout - Guards Craft routes before their client components mount.
 */
export default async function Layout({ children }: LayoutProps) {
  noStore();

  await requireOnyxCraftAccessSS();

  return <>{children}</>;
}
