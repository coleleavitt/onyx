"use client";

import { useEffect, useState } from "react";
import { Formik, Form } from "formik";
import * as Yup from "yup";
import { Button, InputSelect, Text } from "@opal/components";
import { useProjectsContext } from "@/providers/ProjectsContext";
import { InputVertical, toast } from "@opal/layouts";
import { useAppRouter } from "@/hooks/appNavigation";
import { useModal } from "@/refresh-components/contexts/ModalContext";
import { SvgFolderPlus } from "@opal/icons";
import Modal from "@/refresh-components/Modal";
import InputTypeInField from "@/refresh-components/form/InputTypeInField";
import InputTextAreaField from "@/refresh-components/form/InputTextAreaField";
import EmojiPickerField from "@/refresh-components/form/EmojiPickerField";
import {
  SPACE_DESCRIPTION_MAX_LENGTH,
  SPACE_NAME_MAX_LENGTH,
} from "@/lib/projects/constants";
import { fetchConnectedKnowledgePresets } from "@/lib/projects/svc";
import type { ConnectedKnowledgePreset } from "@/lib/projects/types";

interface CreateProjectModalProps {
  initialProjectName?: string;
  terminology?: "project" | "space";
}

const NO_PRESET_VALUE = "__none__";

export function presetOptionLabel(preset: ConnectedKnowledgePreset): string {
  return `${preset.emoji ? `${preset.emoji} ` : ""}${preset.name}`;
}

/**
 * Human-readable summary of what a preset attaches, so users see what they
 * are committing a new space to before creating it.
 */
export function presetDetailLine(
  preset: ConnectedKnowledgePreset | undefined,
): string | null {
  if (!preset) return null;
  const nodeCount = preset.connected_knowledge.hierarchy_nodes.length;
  const documentCount = preset.connected_knowledge.documents.length;
  const parts: string[] = [];
  if (preset.description) parts.push(preset.description);
  const sourceTitles = preset.connected_knowledge.hierarchy_nodes
    .slice(0, 3)
    .map((node) => node.title);
  const summaryPieces: string[] = [];
  if (nodeCount > 0) {
    const listed = sourceTitles.join(", ");
    summaryPieces.push(
      nodeCount > sourceTitles.length
        ? `${listed} +${nodeCount - sourceTitles.length} more`
        : listed,
    );
  }
  if (documentCount > 0) {
    summaryPieces.push(
      `${documentCount} document${documentCount === 1 ? "" : "s"}`,
    );
  }
  if (summaryPieces.length > 0) {
    parts.push(`Includes: ${summaryPieces.join(" · ")}`);
  }
  return parts.length > 0 ? parts.join(" — ") : null;
}

export default function CreateProjectModal({
  initialProjectName,
  terminology = "project",
}: CreateProjectModalProps) {
  const { createProject } = useProjectsContext();
  const modal = useModal();
  const route = useAppRouter();
  const label = terminology === "space" ? "Space" : "Project";
  const [presets, setPresets] = useState<ConnectedKnowledgePreset[]>([]);

  useEffect(() => {
    if (!modal.isOpen || terminology !== "space") return;
    fetchConnectedKnowledgePresets()
      .then(setPresets)
      .catch((error) => {
        console.error("Failed to fetch connected knowledge presets", error);
        setPresets([]);
      });
  }, [modal.isOpen, terminology]);
  const validationSchema = Yup.object({
    projectName: Yup.string()
      .trim()
      .max(
        SPACE_NAME_MAX_LENGTH,
        `${label} name must be ${SPACE_NAME_MAX_LENGTH} characters or fewer`
      )
      .required(`${label} name is required`),
    description: Yup.string()
      .trim()
      .max(
        SPACE_DESCRIPTION_MAX_LENGTH,
        `${label} description must be ${SPACE_DESCRIPTION_MAX_LENGTH} characters or fewer`
      ),
  });

  return (
    <Modal open={modal.isOpen} onOpenChange={modal.toggle}>
      <Modal.Content width="sm">
        <Modal.Header
          icon={SvgFolderPlus}
          title={`Create a new ${label}`}
          onClose={() => modal.toggle(false)}
        />
        <Formik
          initialValues={{
            projectName: initialProjectName ?? "",
            emoji: "",
            description: "",
            instructions: "",
            presetId: "",
          }}
          validationSchema={validationSchema}
          validateOnMount
          enableReinitialize
          onSubmit={async (values, { setSubmitting }) => {
            const name = values.projectName.trim();
            try {
              const newProject = await createProject({
                name,
                emoji: values.emoji.trim() || null,
                description: values.description.trim() || null,
                instructions: values.instructions.trim() || null,
                connected_knowledge_preset_id: values.presetId
                  ? Number(values.presetId)
                  : null,
              });
              route({ projectId: newProject.id, projectName: newProject.name });
              modal.toggle(false);
            } catch {
              toast.error(`Failed to create the ${terminology} ${name}`);
            } finally {
              setSubmitting(false);
            }
          }}
        >
          {({ isSubmitting, isValid, values, setFieldValue }) => (
            <Form>
              <Modal.Body>
                <div className="flex items-end gap-2">
                  <div className="shrink-0">
                    <InputVertical title="Icon" withLabel="emoji">
                      <EmojiPickerField
                        name="emoji"
                        ariaLabel={`Pick an emoji for this ${label}`}
                      />
                    </InputVertical>
                  </div>
                  <div className="min-w-0 flex-1">
                    <InputVertical title="Title" withLabel="projectName">
                      <InputTypeInField
                        name="projectName"
                        placeholder={`Name this ${label}`}
                        clearButton
                      />
                    </InputVertical>
                  </div>
                </div>
                <InputVertical
                  title="Description"
                  suffix="optional"
                  withLabel="description"
                >
                  <InputTextAreaField
                    name="description"
                    placeholder={`Describe what this ${label} is for`}
                    autoResize
                  />
                </InputVertical>
                <InputVertical
                  title="Instructions"
                  suffix="optional"
                  withLabel="instructions"
                >
                  <InputTextAreaField
                    name="instructions"
                    placeholder={`Custom instructions for the agent in this ${label}`}
                    autoResize
                  />
                </InputVertical>
                {terminology === "space" && presets.length > 0 && (
                  <InputVertical
                    title="Connected source default"
                    suffix="optional"
                    withLabel="presetId"
                  >
                    <InputSelect
                      value={values.presetId || NO_PRESET_VALUE}
                      onValueChange={(value) =>
                        setFieldValue(
                          "presetId",
                          value === NO_PRESET_VALUE ? "" : value,
                        )
                      }
                    >
                      <InputSelect.Trigger />
                      <InputSelect.Content>
                        <InputSelect.Item value={NO_PRESET_VALUE}>
                          Start without a default source
                        </InputSelect.Item>
                        {presets.map((preset) => (
                          <InputSelect.Item
                            key={preset.id}
                            value={String(preset.id)}
                          >
                            {presetOptionLabel(preset)}
                          </InputSelect.Item>
                        ))}
                      </InputSelect.Content>
                    </InputSelect>
                    {(() => {
                      const detail = presetDetailLine(
                        presets.find(
                          (preset) => String(preset.id) === values.presetId,
                        ),
                      );
                      return detail ? (
                        <Text font="secondary-body" color="text-03">
                          {detail}
                        </Text>
                      ) : null;
                    })()}
                  </InputVertical>
                )}
              </Modal.Body>
              <Modal.Footer>
                <Button
                  prominence="secondary"
                  type="button"
                  onClick={() => modal.toggle(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting || !isValid}>
                  {`Create ${label}`}
                </Button>
              </Modal.Footer>
            </Form>
          )}
        </Formik>
      </Modal.Content>
    </Modal>
  );
}
