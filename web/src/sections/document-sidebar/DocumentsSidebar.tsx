"use client";

import { MinimalOnyxDocument, OnyxDocument } from "@/lib/search/interfaces";
import ChatDocumentDisplay from "@/sections/document-sidebar/ChatDocumentDisplay";
import { removeDuplicateDocs } from "@/lib/documentUtils";
import { Dispatch, SetStateAction, useMemo, memo, useState } from "react";
import { getCitations } from "@/app/app/services/packetUtils";
import {
  useCurrentMessageTree,
  useSelectedNodeForDocDisplay,
} from "@/app/app/stores/useChatSessionStore";
import { Button, Divider, Text } from "@opal/components";
import {
  SvgCheckCircle,
  SvgChevronDown,
  SvgChevronRight,
  SvgFile,
  SvgSearchMenu,
  SvgX,
} from "@opal/icons";
import { partitionSourceEvidence } from "@/sections/document-sidebar/sourceEvidence";

// Build an OnyxDocument from basic file info
const buildOnyxDocumentFromFile = (
  id: string,
  name?: string | null,
  appendProjectPrefix?: boolean
): OnyxDocument => {
  const document_id = appendProjectPrefix ? `project_file__${id}` : id;
  return {
    document_id,
    semantic_identifier: name || id,
    link: "",
    source_type: "file" as any,
    blurb: "",
    boost: 0,
    hidden: false,
    score: 1,
    chunk_ind: 0,
    match_highlights: [],
    metadata: {},
    updated_at: null,
    is_internet: false,
  } as any;
};

interface HeaderProps {
  children: string;
  onClose: () => void;
}

function Header({ children, onClose }: HeaderProps) {
  return (
    <div className="sticky top-0 z-sticky bg-background-tint-01">
      <div className="flex flex-row w-full items-center justify-between gap-2 py-3">
        <div className="flex items-center gap-2 w-full px-3">
          <SvgSearchMenu className="w-[1.3rem] h-[1.3rem] stroke-text-03" />
          <Text as="h2" font="heading-h3" color="text-03">
            {children}
          </Text>
        </div>
        <Button
          icon={SvgX}
          prominence="tertiary"
          onClick={onClose}
          tooltip="Close Sidebar"
        />
      </div>
      <Divider paddingParallel="fit" paddingPerpendicular="fit" />
    </div>
  );
}

interface EvidenceSectionHeaderProps {
  count: number;
  icon: typeof SvgCheckCircle;
  title: string;
}

function EvidenceSectionHeader({
  count,
  icon: Icon,
  title,
}: EvidenceSectionHeaderProps) {
  return (
    <div className="flex items-center justify-between gap-2 py-2">
      <div className="flex items-center gap-2">
        <Icon size={16} className="stroke-text-03" />
        <Text font="main-ui-action" color="text-04">
          {title}
        </Text>
      </div>
      <Text font="secondary-body" color="text-02">
        {String(count)}
      </Text>
    </div>
  );
}

interface ChatDocumentDisplayWrapperProps {
  children?: React.ReactNode;
}

function ChatDocumentDisplayWrapper({
  children,
}: ChatDocumentDisplayWrapperProps) {
  return (
    <div className="flex flex-col gap-1 items-center justify-center">
      {children}
    </div>
  );
}

interface DocumentsSidebarProps {
  closeSidebar: () => void;
  selectedDocuments: OnyxDocument[] | null;
  modal: boolean;
  setPresentingDocument: Dispatch<SetStateAction<MinimalOnyxDocument | null>>;
}

const DocumentsSidebar = memo(
  ({
    closeSidebar,
    modal,
    selectedDocuments,
    setPresentingDocument,
  }: DocumentsSidebarProps) => {
    const [showReviewedSources, setShowReviewedSources] = useState(false);
    const [showLowerRelevanceSources, setShowLowerRelevanceSources] =
      useState(false);
    const idOfMessageToDisplay = useSelectedNodeForDocDisplay();
    const currentMessageTree = useCurrentMessageTree();

    const selectedMessage = idOfMessageToDisplay
      ? currentMessageTree?.get(idOfMessageToDisplay)
      : null;

    // Get citations in order and build a set of cited document IDs
    const { citedDocumentIds, citationOrder } = useMemo(() => {
      if (!selectedMessage) {
        return {
          citedDocumentIds: new Set<string>(),
          citationOrder: new Map<string, number>(),
        };
      }

      const citedDocumentIds = new Set<string>();
      const citationOrder = new Map<string, number>();
      const citations = getCitations(selectedMessage.packets);
      citations.forEach((citation, index) => {
        citedDocumentIds.add(citation.document_id);
        // Only set the order for the first occurrence
        if (!citationOrder.has(citation.document_id)) {
          citationOrder.set(citation.document_id, index);
        }
      });
      return { citedDocumentIds, citationOrder };
    }, [idOfMessageToDisplay, selectedMessage?.packets.length]);

    // if these are missing for some reason, then nothing we can do. Just
    // don't render.
    // TODO: improve this display
    if (!selectedMessage || !currentMessageTree) return null;

    const humanMessage = selectedMessage.parentNodeId
      ? currentMessageTree.get(selectedMessage.parentNodeId)
      : null;
    const humanFileDescriptors = humanMessage?.files.filter(
      (file) => file.user_file_id !== null
    );
    const selectedDocumentIds =
      selectedDocuments?.map((document) => document.document_id) || [];
    const currentDocuments = selectedMessage.documents || null;
    const dedupedDocuments = removeDuplicateDocs(currentDocuments || []);
    const { citedDocuments, reviewedDocuments, lowerRelevanceDocuments } =
      partitionSourceEvidence(
        dedupedDocuments,
        citedDocumentIds,
        citationOrder
      );
    const hasCited = citedDocuments.length > 0;
    const hasReviewed = reviewedDocuments.length > 0;
    const hasLowerRelevance = lowerRelevanceDocuments.length > 0;

    return (
      <div
        id="onyx-chat-sidebar"
        className="bg-background-tint-01 overflow-y-scroll h-full w-full border-l"
      >
        <Header onClose={closeSidebar}>Sources</Header>
        <div className="flex flex-col px-3 pb-6 gap-4">
          {hasCited && (
            <section>
              <EvidenceSectionHeader
                count={citedDocuments.length}
                icon={SvgCheckCircle}
                title="Sourced"
              />
              <ChatDocumentDisplayWrapper>
                {citedDocuments.map((document) => (
                  <ChatDocumentDisplay
                    key={document.document_id}
                    setPresentingDocument={setPresentingDocument}
                    modal={modal}
                    document={document}
                    isSelected={selectedDocumentIds.includes(
                      document.document_id
                    )}
                  />
                ))}
              </ChatDocumentDisplayWrapper>
            </section>
          )}

          {hasReviewed && (
            <section>
              <Button
                prominence="tertiary"
                icon={showReviewedSources ? SvgChevronDown : SvgChevronRight}
                onClick={() => setShowReviewedSources((visible) => !visible)}
              >
                {showReviewedSources
                  ? "Hide reviewed sources"
                  : `Show ${reviewedDocuments.length} reviewed ${
                      reviewedDocuments.length === 1 ? "source" : "sources"
                    }`}
              </Button>
              {showReviewedSources && (
                <>
                  <EvidenceSectionHeader
                    count={reviewedDocuments.length}
                    icon={SvgSearchMenu}
                    title="Reviewed"
                  />
                  <ChatDocumentDisplayWrapper>
                    {reviewedDocuments.map((document) => (
                      <ChatDocumentDisplay
                        key={document.document_id}
                        setPresentingDocument={setPresentingDocument}
                        modal={modal}
                        document={document}
                        isSelected={selectedDocumentIds.includes(
                          document.document_id
                        )}
                      />
                    ))}
                  </ChatDocumentDisplayWrapper>
                </>
              )}
            </section>
          )}

          {showReviewedSources && hasLowerRelevance && (
            <section>
              <Button
                prominence="tertiary"
                icon={
                  showLowerRelevanceSources ? SvgChevronDown : SvgChevronRight
                }
                onClick={() =>
                  setShowLowerRelevanceSources((visible) => !visible)
                }
              >
                {showLowerRelevanceSources
                  ? "Hide lower-relevance results"
                  : `Show ${lowerRelevanceDocuments.length} lower-relevance ${
                      lowerRelevanceDocuments.length === 1
                        ? "result"
                        : "results"
                    }`}
              </Button>
              {showLowerRelevanceSources && (
                <ChatDocumentDisplayWrapper>
                  {lowerRelevanceDocuments.map((document) => (
                    <ChatDocumentDisplay
                      key={document.document_id}
                      setPresentingDocument={setPresentingDocument}
                      modal={modal}
                      document={document}
                      isSelected={selectedDocumentIds.includes(
                        document.document_id
                      )}
                    />
                  ))}
                </ChatDocumentDisplayWrapper>
              )}
            </section>
          )}

          {humanFileDescriptors && humanFileDescriptors.length > 0 && (
            <section>
              <EvidenceSectionHeader
                count={humanFileDescriptors.length}
                icon={SvgFile}
                title="Attached"
              />
              <ChatDocumentDisplayWrapper>
                {humanFileDescriptors.map((file) => (
                  <ChatDocumentDisplay
                    key={file.id}
                    setPresentingDocument={setPresentingDocument}
                    modal={modal}
                    document={buildOnyxDocumentFromFile(
                      file.id,
                      file.name,
                      false
                    )}
                    isSelected={false}
                  />
                ))}
              </ChatDocumentDisplayWrapper>
            </section>
          )}
        </div>
      </div>
    );
  }
);
DocumentsSidebar.displayName = "DocumentsSidebar";

export default DocumentsSidebar;
