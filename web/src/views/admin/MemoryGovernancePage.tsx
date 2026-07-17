"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { Button, Card, Divider, Switch, Tag, Text } from "@opal/components";
import {
  SvgCalendar,
  SvgHistory,
  SvgLightbulbSimple,
  SvgRefreshCw,
  SvgTrash,
  SvgUsers,
} from "@opal/icons";
import {
  Content,
  ContentAction,
  InputHorizontal,
  SettingsLayouts,
} from "@opal/layouts";
import InputSelect from "@/refresh-components/inputs/InputSelect";
import ConfirmationModalLayout from "@/refresh-components/layouts/ConfirmationModalLayout";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { errorHandlingFetcher } from "@/lib/fetcher";
import {
  bulkDeleteMemories,
  updateMemoryGovernancePolicy,
  type MemoryGovernanceAuditAction,
  type MemoryGovernanceOverview,
  type MemoryGovernancePolicy,
} from "@/lib/memory-governance";
import { SWR_KEYS } from "@/lib/swr-keys";
import { toast } from "@opal/layouts";

const route = ADMIN_ROUTES.MEMORY_GOVERNANCE;

const RETENTION_OPTIONS = [
  { value: "forever", label: "Keep until deleted" },
  { value: "30", label: "30 days" },
  { value: "90", label: "90 days" },
  { value: "180", label: "180 days" },
  { value: "365", label: "1 year" },
  { value: "730", label: "2 years" },
] as const;

function formatTimestamp(value: string | null): string {
  if (!value) return "Never";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function auditTitle(action: MemoryGovernanceAuditAction): string {
  if (action === "POLICY_UPDATED") return "Policy updated";
  if (action === "RETENTION_CLEANUP") return "Expired memories deleted";
  return "Organization memories deleted";
}

function auditColor(action: MemoryGovernanceAuditAction) {
  if (action === "BULK_DELETE") return "red" as const;
  if (action === "RETENTION_CLEANUP") return "amber" as const;
  return "blue" as const;
}

export default function MemoryGovernancePage() {
  const { data, error, isLoading, mutate } = useSWR<MemoryGovernanceOverview>(
    SWR_KEYS.memoryGovernance,
    errorHandlingFetcher,
    { revalidateOnFocus: false }
  );
  const [draft, setDraft] = useState<MemoryGovernancePolicy | null>(null);
  const [saving, setSaving] = useState(false);
  const [cleanupRunning, setCleanupRunning] = useState(false);
  const [confirmDeleteAll, setConfirmDeleteAll] = useState(false);

  useEffect(() => {
    if (data) setDraft(data.policy);
  }, [data]);

  const changed = useMemo(() => {
    if (!draft || !data) return false;
    return (
      draft.memories_enabled !== data.policy.memories_enabled ||
      draft.memory_creation_enabled !== data.policy.memory_creation_enabled ||
      draft.retention_days !== data.policy.retention_days
    );
  }, [data, draft]);

  async function savePolicy() {
    if (!draft) return;
    setSaving(true);
    try {
      const updated = await updateMemoryGovernancePolicy({
        memories_enabled: draft.memories_enabled,
        memory_creation_enabled:
          draft.memories_enabled && draft.memory_creation_enabled,
        retention_days: draft.retention_days,
      });
      await mutate(updated, false);
      toast.success("Memory policy updated.");
    } catch (saveError) {
      toast.error(
        saveError instanceof Error
          ? saveError.message
          : "Failed to update memory policy"
      );
    } finally {
      setSaving(false);
    }
  }

  async function deleteByScope(scope: "expired" | "all") {
    setCleanupRunning(true);
    try {
      const result = await bulkDeleteMemories(
        scope,
        scope === "all" ? "DELETE ALL MEMORIES" : undefined
      );
      toast.success(
        result.affected_count === 1
          ? "Deleted 1 memory."
          : `Deleted ${result.affected_count} memories.`
      );
      setConfirmDeleteAll(false);
      await mutate();
    } catch (deleteError) {
      toast.error(
        deleteError instanceof Error
          ? deleteError.message
          : "Failed to delete memories"
      );
    } finally {
      setCleanupRunning(false);
    }
  }

  return (
    <SettingsLayouts.Root width="lg">
      <SettingsLayouts.Header
        divider
        icon={route.icon}
        title={route.title}
        description="Control organization-wide personal memory, retention, and administrative deletion."
        rightChildren={
          <Button
            disabled={!changed || saving}
            onClick={() => void savePolicy()}
            prominence="primary"
          >
            {saving ? "Saving..." : "Save policy"}
          </Button>
        }
      />

      <SettingsLayouts.Body>
        {isLoading ? (
          <Text color="text-03" font="secondary-body">
            Loading memory policy...
          </Text>
        ) : error || !data || !draft ? (
          <ContentAction
            description="The organization memory policy could not be loaded."
            icon={SvgRefreshCw}
            rightChildren={
              <Button prominence="secondary" onClick={() => void mutate()}>
                Try again
              </Button>
            }
            sizePreset="main-ui"
            title="Memory governance unavailable"
            variant="section"
          />
        ) : (
          <div className="flex w-full flex-col gap-6">
            <section className="flex w-full flex-col gap-2">
              <Content
                sizePreset="main-content"
                title="Policy"
                variant="section"
                width="full"
              />
              <Card>
                <InputHorizontal
                  description="Allow personal memories to be referenced in chats. Individual users can still opt out."
                  title="Stored Memory"
                  withLabel
                >
                  <Switch
                    checked={draft.memories_enabled}
                    onCheckedChange={(checked) =>
                      setDraft((current) =>
                        current
                          ? {
                              ...current,
                              memories_enabled: checked,
                              memory_creation_enabled: checked
                                ? current.memory_creation_enabled
                                : false,
                            }
                          : current
                      )
                    }
                  />
                </InputHorizontal>
                <InputHorizontal
                  description="Allow assistants and users to add or edit memories. Deletion remains available."
                  disabled={!draft.memories_enabled}
                  title="Memory Updates"
                  withLabel
                >
                  <Switch
                    checked={draft.memory_creation_enabled}
                    disabled={!draft.memories_enabled}
                    onCheckedChange={(checked) =>
                      setDraft((current) =>
                        current
                          ? { ...current, memory_creation_enabled: checked }
                          : current
                      )
                    }
                  />
                </InputHorizontal>
                <InputHorizontal
                  description="A scheduled cleanup removes memories older than this period."
                  title="Retention"
                  withLabel
                >
                  <InputSelect
                    value={String(draft.retention_days ?? "forever")}
                    onValueChange={(value) =>
                      setDraft((current) =>
                        current
                          ? {
                              ...current,
                              retention_days:
                                value === "forever" ? null : Number(value),
                            }
                          : current
                      )
                    }
                  >
                    <InputSelect.Trigger />
                    <InputSelect.Content>
                      {RETENTION_OPTIONS.map((option) => (
                        <InputSelect.Item
                          key={option.value}
                          value={option.value}
                        >
                          {option.label}
                        </InputSelect.Item>
                      ))}
                    </InputSelect.Content>
                  </InputSelect>
                </InputHorizontal>
              </Card>
            </section>

            <section className="flex w-full flex-col gap-2">
              <Content
                sizePreset="main-content"
                title="Stored Data"
                variant="section"
                width="full"
              />
              <Card>
                <ContentAction
                  description={`${data.stats.user_count} users have stored memory`}
                  icon={SvgLightbulbSimple}
                  rightChildren={
                    <Text color="text-05" font="main-ui-body">
                      {data.stats.memory_count.toLocaleString()}
                    </Text>
                  }
                  sizePreset="main-ui"
                  title="Memories"
                  variant="section"
                />
                <Divider paddingParallel="fit" paddingPerpendicular="fit" />
                <ContentAction
                  description="Oldest retained memory"
                  icon={SvgCalendar}
                  rightChildren={
                    <Text color="text-03" font="main-ui-body">
                      {formatTimestamp(data.stats.oldest_memory_at)}
                    </Text>
                  }
                  sizePreset="main-ui"
                  title="Retention Range"
                  variant="section"
                />
                <Divider paddingParallel="fit" paddingPerpendicular="fit" />
                <ContentAction
                  description="Delete records covered by the current retention policy."
                  icon={SvgHistory}
                  rightChildren={
                    <Button
                      disabled={draft.retention_days === null || cleanupRunning}
                      onClick={() => void deleteByScope("expired")}
                      prominence="secondary"
                    >
                      Delete expired
                    </Button>
                  }
                  sizePreset="main-ui"
                  title="Run Cleanup"
                  variant="section"
                />
                <Divider paddingParallel="fit" paddingPerpendicular="fit" />
                <ContentAction
                  description="Permanently remove every user's stored memory."
                  icon={SvgTrash}
                  rightChildren={
                    <Button
                      disabled={cleanupRunning || data.stats.memory_count === 0}
                      onClick={() => setConfirmDeleteAll(true)}
                      prominence="secondary"
                      variant="danger"
                    >
                      Delete all
                    </Button>
                  }
                  sizePreset="main-ui"
                  title="Organization Memory"
                  variant="section"
                />
              </Card>
            </section>

            <section className="flex w-full flex-col gap-2">
              <Content
                sizePreset="main-content"
                title="Audit History"
                variant="section"
                width="full"
              />
              {data.audit_events.length === 0 ? (
                <ContentAction
                  description="Policy changes and administrative deletion will appear here."
                  icon={SvgHistory}
                  sizePreset="main-ui"
                  title="No governance events"
                  variant="section"
                />
              ) : (
                <Card>
                  {data.audit_events.map((event, index) => (
                    <div key={event.id}>
                      <ContentAction
                        description={`${event.actor_email ?? "Scheduled cleanup"} · ${formatTimestamp(event.created_at)}`}
                        icon={
                          event.action === "POLICY_UPDATED"
                            ? SvgUsers
                            : SvgTrash
                        }
                        rightChildren={
                          <div className="flex items-center gap-2">
                            <Tag
                              color={auditColor(event.action)}
                              title={event.action
                                .toLowerCase()
                                .replaceAll("_", " ")}
                            />
                            {event.affected_count > 0 && (
                              <Text color="text-03" font="secondary-body">
                                {`${event.affected_count.toLocaleString()} records`}
                              </Text>
                            )}
                          </div>
                        }
                        sizePreset="main-ui"
                        title={auditTitle(event.action)}
                        variant="section"
                      />
                      {index < data.audit_events.length - 1 && (
                        <Divider
                          paddingParallel="fit"
                          paddingPerpendicular="fit"
                        />
                      )}
                    </div>
                  ))}
                </Card>
              )}
            </section>
          </div>
        )}
      </SettingsLayouts.Body>

      {confirmDeleteAll && (
        <ConfirmationModalLayout
          description="This permanently removes all stored personal memories for every user. Personal profile fields and preferences are not deleted."
          icon={SvgTrash}
          onClose={() => setConfirmDeleteAll(false)}
          submit={
            <Button
              disabled={cleanupRunning}
              onClick={() => void deleteByScope("all")}
              prominence="primary"
              variant="danger"
            >
              {cleanupRunning ? "Deleting..." : "Delete all memories"}
            </Button>
          }
          title="Delete all organization memories?"
        />
      )}
    </SettingsLayouts.Root>
  );
}
