"use client";

import { Formik } from "formik";
import { Button } from "@opal/components";
import { SvgSimpleLoader } from "@opal/icons";

import SharepointSitePicker from "@/app/admin/connectors/[connector]/pages/ConnectorInput/SharepointSitePicker";
import { Connector, SharepointConfig } from "@/lib/connectors/connectors";
import { Credential } from "@/lib/connectors/credentials";
import { updateConnector } from "@/lib/connector";
import { AccessType } from "@/lib/types";
import Modal from "@/refresh-components/Modal";
import { toast } from "@opal/layouts";

interface EditSharepointSitesModalProps {
  connector: Connector<SharepointConfig>;
  credential: Credential<unknown>;
  accessType: AccessType;
  groups: number[];
  onClose: () => void;
  onSaved: () => void;
}

interface SharepointSitesFormValues {
  sites: string[];
  authority_host: string;
  graph_api_host: string;
  sharepoint_domain_suffix: string;
}

function EditSharepointSitesModal({
  connector,
  credential,
  accessType,
  groups,
  onClose,
  onSaved,
}: EditSharepointSitesModalProps) {
  const config = connector.connector_specific_config;

  return (
    <Formik<SharepointSitesFormValues>
      initialValues={{
        sites: config.sites ?? [],
        authority_host:
          config.authority_host ?? "https://login.microsoftonline.com",
        graph_api_host: config.graph_api_host ?? "https://graph.microsoft.com",
        sharepoint_domain_suffix:
          config.sharepoint_domain_suffix ?? "sharepoint.com",
      }}
      onSubmit={async (values) => {
        try {
          await updateConnector(connector.id, {
            name: connector.name,
            source: connector.source,
            input_type: connector.input_type,
            connector_specific_config: {
              ...config,
              sites: values.sites,
            },
            refresh_freq: connector.refresh_freq,
            prune_freq: connector.prune_freq,
            indexing_start: connector.indexing_start,
            access_type: accessType,
            groups,
          });
          onSaved();
        } catch (error) {
          toast.error(
            error instanceof Error
              ? error.message
              : "Failed to update SharePoint sites"
          );
        }
      }}
    >
      {({ isSubmitting, submitForm }) => (
        <Modal open onOpenChange={(open) => !open && onClose()}>
          <Modal.Content width="lg" height="lg">
            <Modal.Header
              title="SharePoint sites"
              description="Choose the site collections indexed by this connector."
              onClose={onClose}
            />
            <Modal.Body>
              <SharepointSitePicker
                name="sites"
                label="Sites"
                description="Leave empty to index every accessible site."
                currentCredential={credential}
              />
            </Modal.Body>
            <Modal.Footer>
              <Button
                type="button"
                variant="default"
                prominence="tertiary"
                onClick={onClose}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="default"
                prominence="primary"
                icon={isSubmitting ? SvgSimpleLoader : undefined}
                onClick={() => void submitForm()}
                disabled={isSubmitting}
              >
                Save
              </Button>
            </Modal.Footer>
          </Modal.Content>
        </Modal>
      )}
    </Formik>
  );
}

export default EditSharepointSitesModal;
