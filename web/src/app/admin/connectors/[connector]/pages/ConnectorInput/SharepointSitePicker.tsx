"use client";

import { useMemo, useState } from "react";
import { useFormikContext } from "formik";
import useSWR from "swr";
import { Button, Checkbox, Tabs, Text } from "@opal/components";
import { SvgEdit, SvgRefreshCw, SvgSimpleLoader } from "@opal/icons";
import { InputVertical } from "@opal/layouts";
import type { RichStr } from "@opal/types";

import ListInput from "@/app/admin/connectors/[connector]/pages/ConnectorInput/ListInput";
import InputSearch from "@/refresh-components/inputs/InputSearch";
import Truncated from "@/refresh-components/texts/Truncated";
import { Credential } from "@/lib/connectors/credentials";
import { SharepointSite } from "@/lib/connectors/interfaces";
import { errorHandlingFetcher } from "@/lib/fetcher";

const DEFAULT_AUTHORITY_HOST = "https://login.microsoftonline.com";
const DEFAULT_GRAPH_API_HOST = "https://graph.microsoft.com";
const DEFAULT_SHAREPOINT_DOMAIN_SUFFIX = "sharepoint.com";

interface SharepointFormValues {
  sites?: string[];
  authority_host?: string;
  graph_api_host?: string;
  sharepoint_domain_suffix?: string;
}

interface SharepointSitePickerProps {
  name: string;
  label: string | RichStr;
  description?: string | RichStr;
  currentCredential: Credential<unknown> | null;
}

type SiteView = "all" | "selected";

function getStringValue(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function SharepointSitePicker({
  name,
  label,
  description,
  currentCredential,
}: SharepointSitePickerProps) {
  const { values, setFieldValue } = useFormikContext<SharepointFormValues>();
  const [search, setSearch] = useState("");
  const [showManualUrls, setShowManualUrls] = useState(false);
  const selectedUrls = Array.isArray(values.sites) ? values.sites : [];
  const [siteView, setSiteView] = useState<SiteView>(() =>
    selectedUrls.length > 0 ? "selected" : "all"
  );

  const discoveryUrl = useMemo(() => {
    if (!currentCredential) return null;

    const params = new URLSearchParams({
      credential_id: String(currentCredential.id),
      authority_host: getStringValue(
        values.authority_host,
        DEFAULT_AUTHORITY_HOST
      ),
      graph_api_host: getStringValue(
        values.graph_api_host,
        DEFAULT_GRAPH_API_HOST
      ),
      sharepoint_domain_suffix: getStringValue(
        values.sharepoint_domain_suffix,
        DEFAULT_SHAREPOINT_DOMAIN_SUFFIX
      ),
    });
    return `/api/manage/admin/connector/sharepoint/sites?${params.toString()}`;
  }, [
    currentCredential,
    values.authority_host,
    values.graph_api_host,
    values.sharepoint_domain_suffix,
  ]);

  const {
    data: sites,
    error,
    isLoading,
    mutate,
  } = useSWR<SharepointSite[]>(discoveryUrl, errorHandlingFetcher);
  const selectedUrlSet = useMemo(() => new Set(selectedUrls), [selectedUrls]);
  const normalizedSearch = search.trim().toLocaleLowerCase();
  const visibleSites = useMemo(() => {
    const sitesForView =
      siteView === "selected"
        ? (sites ?? []).filter((site) => selectedUrlSet.has(site.web_url))
        : (sites ?? []);
    if (normalizedSearch.length === 0) return sitesForView;
    return sitesForView.filter((site) =>
      `${site.display_name} ${site.web_url} ${site.description ?? ""}`
        .toLocaleLowerCase()
        .includes(normalizedSearch)
    );
  }, [normalizedSearch, selectedUrlSet, siteView, sites]);
  const selectedVisibleCount = visibleSites.reduce(
    (count, site) => count + Number(selectedUrlSet.has(site.web_url)),
    0
  );
  const allVisibleSelected =
    visibleSites.length > 0 && selectedVisibleCount === visibleSites.length;

  function setSiteSelected(siteUrl: string, checked: boolean) {
    const nextSelectedUrls = new Set(selectedUrls);
    if (checked) nextSelectedUrls.add(siteUrl);
    else nextSelectedUrls.delete(siteUrl);
    void setFieldValue(name, Array.from(nextSelectedUrls));
  }

  function setAllVisibleSelected(checked: boolean) {
    const nextSelectedUrls = new Set(selectedUrls);
    for (const site of visibleSites) {
      if (checked) nextSelectedUrls.add(site.web_url);
      else nextSelectedUrls.delete(site.web_url);
    }
    void setFieldValue(name, Array.from(nextSelectedUrls));
  }

  return (
    <InputVertical
      withLabel={name}
      title={label}
      description={description}
      suffix="optional"
    >
      <div className="flex w-full flex-col gap-2">
        <div className="w-full overflow-hidden rounded-md border border-border-02 bg-background-neutral-00">
          <div className="flex min-h-12 items-center gap-2 border-b border-border-02 p-2">
            <div className="min-w-0 flex-1">
              <InputSearch
                aria-label="Search SharePoint sites"
                placeholder="Search sites"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                disabled={!currentCredential || isLoading || Boolean(error)}
              />
            </div>
          </div>

          {!isLoading && !error && currentCredential && (
            <div className="border-b border-border-02 p-2">
              <Tabs
                variant="contained"
                value={siteView}
                onValueChange={(value) => setSiteView(value as SiteView)}
              >
                <Tabs.List aria-label="SharePoint site view">
                  <Tabs.Trigger value="all">
                    {`All (${sites?.length ?? 0})`}
                  </Tabs.Trigger>
                  <Tabs.Trigger value="selected">
                    {`Selected (${selectedUrls.length})`}
                  </Tabs.Trigger>
                </Tabs.List>
              </Tabs>
            </div>
          )}

          {isLoading ? (
            <div className="flex min-h-32 items-center justify-center gap-2 p-4">
              <SvgSimpleLoader />
              <Text font="main-ui-body" color="text-03">
                Loading sites
              </Text>
            </div>
          ) : error ? (
            <div className="flex min-h-32 flex-col items-center justify-center gap-2 p-4">
              <Text font="main-ui-body" color="text-03">
                Sites could not be loaded
              </Text>
              <Button
                type="button"
                variant="default"
                prominence="tertiary"
                size="sm"
                icon={SvgRefreshCw}
                onClick={() => void mutate()}
              >
                Retry
              </Button>
            </div>
          ) : !currentCredential ? (
            <div className="flex min-h-32 items-center justify-center p-4">
              <Text font="main-ui-body" color="text-03">
                Select a credential to load sites
              </Text>
            </div>
          ) : visibleSites.length === 0 ? (
            <div className="flex min-h-32 items-center justify-center p-4">
              <Text font="main-ui-body" color="text-03">
                {siteView === "selected" && normalizedSearch.length === 0
                  ? "No sites selected"
                  : "No matching sites"}
              </Text>
            </div>
          ) : (
            <>
              {siteView === "all" && (
                <div className="flex min-h-11 items-center gap-2 border-b border-border-02 bg-background-neutral-01 p-2">
                  <Checkbox
                    id="sharepoint-select-visible-sites"
                    checked={allVisibleSelected}
                    indeterminate={
                      selectedVisibleCount > 0 && !allVisibleSelected
                    }
                    onCheckedChange={setAllVisibleSelected}
                    aria-label="Select all visible SharePoint sites"
                  />
                  <label
                    htmlFor="sharepoint-select-visible-sites"
                    className="min-w-0 flex-1 cursor-pointer"
                  >
                    <Text font="main-ui-action" color="text-03">
                      Select all visible
                    </Text>
                  </label>
                </div>
              )}
              <div className="max-h-80 overflow-y-auto">
                {visibleSites.map((site) => {
                  const checkboxId = `sharepoint-site-${site.id.replaceAll(",", "-")}`;
                  return (
                    <div
                      key={site.id}
                      className="flex min-h-14 items-center gap-2 border-b border-border-01 p-2 last:border-b-0"
                    >
                      <Checkbox
                        id={checkboxId}
                        checked={selectedUrlSet.has(site.web_url)}
                        onCheckedChange={(checked) =>
                          setSiteSelected(site.web_url, checked)
                        }
                        aria-label={`Select ${site.display_name}`}
                      />
                      <label
                        htmlFor={checkboxId}
                        className="flex min-w-0 flex-1 cursor-pointer flex-col"
                      >
                        <Text font="main-ui-action" color="text-03">
                          {site.display_name}
                        </Text>
                        <Truncated secondaryBody text02 className="w-full">
                          {site.web_url}
                        </Truncated>
                      </label>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

        <div className="flex justify-end">
          <Button
            type="button"
            variant="default"
            prominence="tertiary"
            size="sm"
            icon={SvgEdit}
            onClick={() => setShowManualUrls((isVisible) => !isVisible)}
          >
            Edit URLs
          </Button>
        </div>
        {showManualUrls && (
          <ListInput
            name={name}
            label="Site and folder URLs"
            description="Add full SharePoint site or folder URLs."
          />
        )}
      </div>
    </InputVertical>
  );
}

export default SharepointSitePicker;
