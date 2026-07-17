import { unstable_noStore as noStore } from "next/cache";
import { requireOnyxCraftAccessSS } from "@/lib/craft/svcSS";

interface WorkflowsLayoutProps {
  children: React.ReactNode;
}

export default async function WorkflowsLayout({
  children,
}: WorkflowsLayoutProps) {
  noStore();
  await requireOnyxCraftAccessSS();

  return children;
}
