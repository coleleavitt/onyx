"use client";

import { Formik, Form } from "formik";
import * as Yup from "yup";
import { Button } from "@opal/components";
import { useProjectsContext } from "@/providers/ProjectsContext";
import { useModal } from "@/refresh-components/contexts/ModalContext";
import { SvgAddLines } from "@opal/icons";
import Modal from "@/refresh-components/Modal";
import InputTextAreaField from "@/refresh-components/form/InputTextAreaField";
import CharacterCount from "@/refresh-components/CharacterCount";
import {
  parseSpaceInstructions,
  serializeSpaceInstructions,
} from "@/lib/projects/spaceMetadata";

const MAX_INSTRUCTIONS_LENGTH = 8000;

const validationSchema = Yup.object({
  instructions: Yup.string().max(
    MAX_INSTRUCTIONS_LENGTH,
    `Instructions must be ${MAX_INSTRUCTIONS_LENGTH} characters or fewer`
  ),
});

export default function AddInstructionModal() {
  const modal = useModal();
  const { currentProjectDetails, upsertInstructions } = useProjectsContext();

  // The stored instructions may carry a machine-readable space-metadata block
  // (links/skills). Edit only the human-facing text and preserve the block.
  const rawInstructions = currentProjectDetails?.project?.instructions ?? "";
  const { instructions: humanInstructions, meta } =
    parseSpaceInstructions(rawInstructions);

  return (
    <Modal open={modal.isOpen} onOpenChange={modal.toggle}>
      <Modal.Content width="md">
        <Modal.Header
          icon={SvgAddLines}
          title="Instructions"
          description="Give the agent instructions for how it should work in this space."
          onClose={() => modal.toggle(false)}
        />
        <Formik
          initialValues={{
            instructions: humanInstructions,
          }}
          enableReinitialize
          validationSchema={validationSchema}
          onSubmit={async (values, { setSubmitting }) => {
            try {
              await upsertInstructions(
                serializeSpaceInstructions(values.instructions.trim(), meta)
              );
              modal.toggle(false);
            } catch (e) {
              console.error("Failed to save instructions", e);
            } finally {
              setSubmitting(false);
            }
          }}
        >
          {({ isSubmitting, dirty, isValid, values }) => (
            <Form>
              <Modal.Body>
                <div className="flex flex-col gap-1.5">
                  <InputTextAreaField
                    name="instructions"
                    placeholder="e.g. Summarize all tasks in bullet points, keep responses concise..."
                    rows={6}
                    maxLength={MAX_INSTRUCTIONS_LENGTH}
                    autoFocus
                  />
                  <div className="self-end">
                    <CharacterCount
                      value={values.instructions}
                      limit={MAX_INSTRUCTIONS_LENGTH}
                    />
                  </div>
                </div>
              </Modal.Body>
              <Modal.Footer>
                <Button
                  prominence="secondary"
                  type="button"
                  onClick={() => modal.toggle(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isSubmitting || !dirty || !isValid}
                >
                  Save Instructions
                </Button>
              </Modal.Footer>
            </Form>
          )}
        </Formik>
      </Modal.Content>
    </Modal>
  );
}
