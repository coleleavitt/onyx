"use client";

import { Form, Formik } from "formik";
import * as Yup from "yup";
import { toast } from "@opal/layouts";
import Modal from "@/refresh-components/Modal";
import InputTypeInField from "@/refresh-components/form/InputTypeInField";
import InputTextAreaField from "@/refresh-components/form/InputTextAreaField";
import { useProjectsContext } from "@/providers/ProjectsContext";
import { pasteTextToProject } from "@/lib/projects/svc";
import { Button } from "@opal/components";
import { InputVertical } from "@opal/layouts";
import { SvgEdit } from "@opal/icons";

interface SpacePasteTextModalProps {
  projectId: number;
  open: boolean;
  onClose: () => void;
}

const validationSchema = Yup.object({
  name: Yup.string().trim().max(200, "Name must be 200 characters or fewer"),
  content: Yup.string().trim().required("Paste some text to save"),
});

// Perplexity-parity "Add plaintext": saves pasted/typed text as an indexed file
// in the space via POST /user/projects/file/paste.
export default function SpacePasteTextModal({
  projectId,
  open,
  onClose,
}: SpacePasteTextModalProps) {
  const { fetchProjects, refreshCurrentProjectDetails } = useProjectsContext();

  return (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <Modal.Content width="md">
        <Modal.Header
          icon={SvgEdit}
          title="Add plaintext"
          description="Paste or type text. It is saved as a file this space can reference."
          onClose={onClose}
        />
        <Formik
          initialValues={{ name: "", content: "" }}
          validationSchema={validationSchema}
          validateOnMount
          onSubmit={async (values, { setSubmitting, resetForm }) => {
            try {
              await pasteTextToProject(
                values.name.trim() || "Pasted text",
                values.content,
                projectId
              );
              await fetchProjects();
              await refreshCurrentProjectDetails();
              toast.success("Text saved to this space.");
              resetForm();
              onClose();
            } catch (error) {
              toast.error(
                error instanceof Error ? error.message : "Failed to save text."
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
                  <InputVertical title="Name" withLabel="name">
                    <InputTypeInField
                      name="name"
                      placeholder="e.g. Meeting notes"
                      clearButton
                    />
                  </InputVertical>
                  <InputVertical
                    title="Text"
                    withLabel="content"
                    alignItems="stretch"
                  >
                    <InputTextAreaField
                      name="content"
                      placeholder="Paste or type text here"
                      autoResize
                      rows={8}
                      maxRows={16}
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
