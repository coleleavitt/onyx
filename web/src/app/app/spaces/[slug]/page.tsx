import AppPage from "@/views/AppPage";

// Canonical Space-detail route: /app/spaces/{name-slug}-{id}. The project id is
// resolved from the pathname by ProjectsContext/useAppFocus; this page renders
// the same app surface as /app so the Space detail shows inside the app shell.
export default function Page() {
  return <AppPage />;
}
