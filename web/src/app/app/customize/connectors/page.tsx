import { redirect } from "next/navigation";

export default function LegacyCustomizeConnectorsPage() {
  redirect("/admin/add-connector");
}
