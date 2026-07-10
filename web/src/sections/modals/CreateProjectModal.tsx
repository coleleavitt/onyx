"use client";

import { Formik, Form } from "formik";
import * as Yup from "yup";
import { Button } from "@opal/components";
import { useProjectsContext } from "@/providers/ProjectsContext";
import { InputVertical } from "@opal/layouts";
import { useAppRouter } from "@/hooks/appNavigation";
import { useModal } from "@/refresh-components/contexts/ModalContext";
import { SvgFolderPlus } from "@opal/icons";
import Modal from "@/refresh-components/Modal";
import InputTypeInField from "@/refresh-components/form/InputTypeInField";
import { toast } from "@/hooks/useToast";

interface CreateProjectModalProps {
  initialProjectName?: string;
  terminology?: "project" | "space";
}

export default function CreateProjectModal({
  initialProjectName,
  terminology = "project",
}: CreateProjectModalProps) {
  const { createProject } = useProjectsContext();
  const modal = useModal();
  const route = useAppRouter();
  const label = terminology === "space" ? "Space" : "Project";
  const validationSchema = Yup.object({
    projectName: Yup.string().trim().required(`${label} name is required`),
  });

  return (
    <Modal open={modal.isOpen} onOpenChange={modal.toggle}>
      <Modal.Content width="sm">
        <Modal.Header
          icon={SvgFolderPlus}
          title={`Create New ${label}`}
          description={`${label}s keep related files, chats, collaborators, and instructions together.`}
          onClose={() => modal.toggle(false)}
        />
        <Formik
          initialValues={{ projectName: initialProjectName ?? "" }}
          validationSchema={validationSchema}
          validateOnMount
          enableReinitialize
          onSubmit={async (values, { setSubmitting }) => {
            const name = values.projectName.trim();
            try {
              const newProject = await createProject(name);
              route({ projectId: newProject.id });
              modal.toggle(false);
            } catch {
              toast.error(`Failed to create the ${terminology} ${name}`);
            } finally {
              setSubmitting(false);
            }
          }}
        >
          {({ isSubmitting, isValid }) => (
            <Form>
              <Modal.Body>
                <InputVertical title={`${label} Name`} withLabel="projectName">
                  <InputTypeInField
                    name="projectName"
                    placeholder="What are you working on?"
                    clearButton
                  />
                </InputVertical>
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
