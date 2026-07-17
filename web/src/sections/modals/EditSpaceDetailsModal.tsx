"use client";

import { Form, Formik } from "formik";
import * as Yup from "yup";
import { toast } from "@/hooks/useToast";
import type { Project } from "@/lib/projects/types";
import Modal from "@/refresh-components/Modal";
import InputTypeInField from "@/refresh-components/form/InputTypeInField";
import InputTextAreaField from "@/refresh-components/form/InputTextAreaField";
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
    .max(255, "Space name must be 255 characters or fewer")
    .required("Space name is required"),
  description: Yup.string()
    .trim()
    .max(255, "Space description must be 255 characters or fewer"),
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
      <Modal.Content width="sm">
        <Modal.Header
          icon={SvgEdit}
          title="Edit Space Details"
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
                  : "Failed to update space details."
              );
            } finally {
              setSubmitting(false);
            }
          }}
        >
          {({ isSubmitting, isValid }) => (
            <Form>
              <Modal.Body>
                <div className="flex flex-col gap-4">
                  <div className="flex items-end gap-2">
                    <div className="w-16 shrink-0">
                      <InputVertical title="Icon" withLabel="emoji">
                        <InputTypeInField
                          name="emoji"
                          placeholder="🙂"
                          maxLength={8}
                        />
                      </InputVertical>
                    </div>
                    <div className="min-w-0 flex-1">
                      <InputVertical title="Space Name" withLabel="name">
                        <InputTypeInField
                          name="name"
                          placeholder="What are you working on?"
                          clearButton
                        />
                      </InputVertical>
                    </div>
                  </div>
                  <InputVertical title="Description" withLabel="description">
                    <InputTextAreaField
                      name="description"
                      placeholder="What should collaborators know about this space?"
                      autoResize
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
