"use client";

import { Button, Text } from "@opal/components";
import Modal from "@/refresh-components/Modal";
import { SvgAddLines } from "@opal/icons";

interface ViewInstructionsModalProps {
  open: boolean;
  instructions: string;
  onClose: () => void;
}

export default function ViewInstructionsModal({
  open,
  instructions,
  onClose,
}: ViewInstructionsModalProps) {
  return (
    <Modal open={open} onOpenChange={(next) => !next && onClose()}>
      <Modal.Content width={instructions.length > 500 ? "md" : "sm"}>
        <Modal.Header
          icon={SvgAddLines}
          title="Instructions"
          onClose={onClose}
        />
        <Modal.Body>
          <div className="whitespace-pre-wrap break-words">
            <Text as="p" font="main-ui-body" color="text-04">
              {instructions}
            </Text>
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Button onClick={onClose}>Done</Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
