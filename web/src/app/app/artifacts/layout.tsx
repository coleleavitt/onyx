import { unstable_noStore as noStore } from "next/cache";
import { requireOnyxCraftAccessSS } from "@/lib/craft/svcSS";

interface ArtifactLibraryLayoutProps {
  children: React.ReactNode;
}

export default async function ArtifactLibraryLayout({
  children,
}: ArtifactLibraryLayoutProps) {
  noStore();
  await requireOnyxCraftAccessSS();

  return children;
}
