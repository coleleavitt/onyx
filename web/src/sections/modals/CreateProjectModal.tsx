"use client";

import { Formik, Form } from "formik";
import * as Yup from "yup";
import { Button } from "@opal/components";
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
          {({ isSubmitting, isValid }) => (
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
