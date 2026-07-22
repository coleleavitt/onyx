"use client";

import { Form, Formik } from "formik";
import * as Yup from "yup";
import { toast } from "@opal/layouts";
import type { Project } from "@/lib/projects/types";
import Modal from "@/refresh-components/Modal";
import InputTypeInField from "@/refresh-components/form/InputTypeInField";
import InputTextAreaField from "@/refresh-components/form/InputTextAreaField";
import EmojiPickerField from "@/refresh-components/form/EmojiPickerField";
import {
  SPACE_DESCRIPTION_MAX_LENGTH,
  SPACE_NAME_MAX_LENGTH,
} from "@/lib/projects/constants";
import { useProjectsContext } from "@/providers/ProjectsContext";
import { Button } from "@opal/components";
import { InputVertical } from "@opal/layouts";
import { SvgEdit } from "@opal/icons";

interface EditSpaceDetailsModalProps {
  project: Project | null;
  open: boolean;
  onClose: () => void;
}

const validationSchema = Yup.object({
  name: Yup.string()
    .trim()
    .max(
      SPACE_NAME_MAX_LENGTH,
      `Space name must be ${SPACE_NAME_MAX_LENGTH} characters or fewer`,
    )
    .required("Space name is required"),
  description: Yup.string()
    .trim()
    .max(
      SPACE_DESCRIPTION_MAX_LENGTH,
      `Space description must be ${SPACE_DESCRIPTION_MAX_LENGTH} characters or fewer`,
    ),
});

export default function EditSpaceDetailsModal({
  project,
  open,
  onClose,
}: EditSpaceDetailsModalProps) {
  const { updateProjectMetadata } = useProjectsContext();

  if (!project) return null;

  return (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <Modal.Content width="md">
        <Modal.Header
          icon={SvgEdit}
          title="Edit space details"
          description="Update the name and description shown to collaborators."
          onClose={onClose}
        />
        <Formik
          initialValues={{
            name: project.name,
            emoji: project.emoji ?? "",
            description: project.description ?? "",
          }}
          validationSchema={validationSchema}
          enableReinitialize
          validateOnMount
          onSubmit={async (values, { setSubmitting }) => {
            try {
              await updateProjectMetadata(project.id, {
                name: values.name,
                emoji: values.emoji.trim() || null,
                description: values.description,
              });
              toast.success("Space details updated.");
              onClose();
            } catch (error) {
              toast.error(
                error instanceof Error
                  ? error.message
                  : "Failed to update space details.",
              );
            } finally {
              setSubmitting(false);
            }
          }}
        >
          {({ isSubmitting, isValid }) => (
            <Form>
              <Modal.Body alignItems="stretch">
                <div className="flex flex-col gap-4">
                  <div className="flex items-end gap-2">
                    <div className="shrink-0">
                      <InputVertical title="Icon" withLabel="emoji">
                        <EmojiPickerField
                          name="emoji"
                          ariaLabel="Pick an emoji for this space"
                        />
                      </InputVertical>
                    </div>
                    <div className="min-w-0 flex-1">
                      <InputVertical title="Space name" withLabel="name">
                        <InputTypeInField
                          name="name"
                          placeholder="What are you working on?"
                          clearButton
                        />
                      </InputVertical>
                    </div>
                  </div>
                  <InputVertical
                    title="Description"
                    withLabel="description"
                    alignItems="stretch"
                  >
                    <InputTextAreaField
                      name="description"
                      placeholder="What should collaborators know about this space?"
                      autoResize
                      rows={5}
                      maxRows={8}
                      resizable={false}
                    />
                  </InputVertical>
                </div>
              </Modal.Body>
              <Modal.Footer>
                <Button
                  prominence="secondary"
                  type="button"
                  onClick={onClose}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting || !isValid}>
                  Save
                </Button>
              </Modal.Footer>
            </Form>
          )}
        </Formik>
      </Modal.Content>
    </Modal>
  );
}
