"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";
import { Button, Switch, Text } from "@opal/components";
import { SvgNetworkGraph } from "@opal/icons";
import Modal from "@/refresh-components/Modal";
import InputTextArea from "@/refresh-components/inputs/InputTextArea";
import {
  getBrainSettings,
  triggerBrainRun,
  updateBrainSettings,
} from "@/lib/memory/api";
import { toast } from "@opal/layouts";

const FOCUS_INSTRUCTIONS_MAX_LENGTH = 2000;

interface BrainSettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export default function BrainSettingsModal({
  open,
  onClose,
}: BrainSettingsModalProps) {
  const { data: settings, mutate } = useSWR(
    open ? "/api/memory/brain/settings" : null,
    getBrainSettings,
    { revalidateOnFocus: false }
  );

  const [brainEnabled, setBrainEnabled] = useState(false);
  const [useConnectors, setUseConnectors] = useState(false);
  const [focusInstructions, setFocusInstructions] = useState("");
  const [saving, setSaving] = useState(false);
  const [refreshQueued, setRefreshQueued] = useState(false);

  useEffect(() => {
    if (!open) return;
    setBrainEnabled(settings?.brain_enabled ?? false);
    setUseConnectors(settings?.brain_use_connectors ?? false);
    setFocusInstructions(settings?.brain_focus_instructions ?? "");
    setRefreshQueued(false);
  }, [open, settings]);

  async function save() {
    setSaving(true);
    try {
      const updated = await updateBrainSettings({
        brain_enabled: brainEnabled,
        brain_use_connectors: useConnectors,
        brain_focus_instructions: focusInstructions.trim() || null,
      });
      await mutate(updated, { revalidate: false });
      toast.success("Brain settings saved.");
      onClose();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Brain settings update failed."
      );
    } finally {
      setSaving(false);
    }
  }

  async function refreshNow() {
    try {
      await triggerBrainRun();
      setRefreshQueued(true);
      toast.success("Brain refresh queued — new pages land in a few minutes.");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Brain refresh request failed."
      );
    }
  }

  return (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <Modal.Content width="md">
        <Modal.Header
          icon={SvgNetworkGraph}
          title="Brain"
          description="Let Onyx continuously learn and organize context on its own."
          onClose={onClose}
        />
        <Modal.Body>
          <div className="flex w-full flex-col gap-3">
            <div className="flex items-center justify-between gap-4 rounded-08 border border-border-01 bg-background-tint-02 p-4">
              <div className="min-w-0">
                <Text font="main-ui-body" color="text-05">
                  Enable Brain
                </Text>
                <Text font="secondary-body" color="text-03">
                  Automatically build and refresh a memory graph from your
                  activity.
                </Text>
              </div>
              <Switch
                checked={brainEnabled}
                disabled={saving}
                onCheckedChange={setBrainEnabled}
              />
            </div>
            <div className="flex items-center justify-between gap-4 rounded-08 border border-border-01 bg-background-tint-02 p-4">
              <div className="min-w-0">
                <Text font="main-ui-body" color="text-05">
                  Use connectors
                </Text>
                <Text font="secondary-body" color="text-03">
                  Include connected sources when Brain refreshes memory.
                </Text>
              </div>
              <Switch
                checked={useConnectors}
                disabled={saving || !brainEnabled}
                onCheckedChange={setUseConnectors}
              />
            </div>
            <label className="flex flex-col gap-1">
              <Text font="main-ui-action" color="text-05">
                Focus instructions
              </Text>
              <InputTextArea
                value={focusInstructions}
                onChange={(event) =>
                  setFocusInstructions(
                    event.target.value.slice(0, FOCUS_INSTRUCTIONS_MAX_LENGTH)
                  )
                }
                placeholder="e.g. Focus on Workstream Alpha. Skip personal-investing pages."
                rows={4}
                maxLength={FOCUS_INSTRUCTIONS_MAX_LENGTH}
                variant={saving ? "disabled" : "primary"}
              />
              <Text font="secondary-body" color="text-02">
                {`${focusInstructions.length}/${FOCUS_INSTRUCTIONS_MAX_LENGTH}`}
              </Text>
            </label>
            <div className="flex items-center justify-between gap-4">
              <Text font="secondary-body" color="text-03">
                {settings?.brain_last_run_at
                  ? `Last refreshed ${formatDistanceToNow(
                      new Date(settings.brain_last_run_at),
                      { addSuffix: true }
                    )}`
                  : "Never refreshed yet."}
              </Text>
              <Button
                prominence="secondary"
                size="sm"
                disabled={!settings?.brain_enabled || refreshQueued || saving}
                tooltip={
                  settings?.brain_enabled
                    ? undefined
                    : "Enable Brain and save first"
                }
                onClick={() => void refreshNow()}
              >
                {refreshQueued ? "Refresh queued" : "Refresh now"}
              </Button>
            </div>
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Button prominence="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={saving} onClick={() => void save()}>
            Save
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
