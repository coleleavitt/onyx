import AgentEditorPage from "@/views/AgentEditorPage";

// Route components may only receive Next.js PageProps; wrap instead of
// re-exporting so AgentEditorPage's own props stay off the route signature.
export default function CreateAgentPage() {
  return <AgentEditorPage />;
}
