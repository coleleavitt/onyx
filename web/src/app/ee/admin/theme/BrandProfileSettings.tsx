"use client";

import { Button, Divider, InputTypeIn, Switch, Text } from "@opal/components";
import { SvgPlus, SvgTrash } from "@opal/icons";
import { FormField } from "@/refresh-components/form/FormField";
import InputChipField from "@/refresh-components/inputs/InputChipField";
import InputSelect from "@/refresh-components/inputs/InputSelect";
import type { BrandProfile } from "@/lib/settings/types";
import { useMemo, useState } from "react";

export const DEFAULT_BRAND_SELECTION = "__default__";

interface BrandProfileSettingsProps {
  profiles: BrandProfile[];
  selectedBrandId: string;
  defaultBrandId: string | null;
  onSelectBrand: (brandId: string) => void;
  onAddBrand: () => void;
  onRemoveBrand: (brandId: string) => void;
  onUpdateBrand: (profile: BrandProfile) => void;
  onDefaultBrandChange: (brandId: string | null) => void;
}

export default function BrandProfileSettings({
  profiles,
  selectedBrandId,
  defaultBrandId,
  onSelectBrand,
  onAddBrand,
  onRemoveBrand,
  onUpdateBrand,
  onDefaultBrandChange,
}: BrandProfileSettingsProps) {
  const [hostnameInput, setHostnameInput] = useState("");
  const selectedProfile = profiles.find(
    (profile) => profile.id === selectedBrandId
  );
  const duplicateHostnames = useMemo(() => {
    const owners = new Map<string, number>();
    for (const profile of profiles) {
      for (const hostname of profile.hostnames) {
        const normalized = hostname.trim().toLowerCase();
        owners.set(normalized, (owners.get(normalized) ?? 0) + 1);
      }
    }
    return new Set(
      Array.from(owners.entries())
        .filter(([, ownerCount]) => ownerCount > 1)
        .map(([hostname]) => hostname)
    );
  }, [profiles]);

  return (
    <div className="flex w-full flex-col gap-4 rounded-08 bg-background-tint-00 p-4">
      <div className="flex flex-col items-stretch gap-2 md:flex-row md:items-end">
        <FormField state="idle" className="flex-1">
          <FormField.Label>Brand Profile</FormField.Label>
          <FormField.Control>
            <InputSelect value={selectedBrandId} onValueChange={onSelectBrand}>
              <InputSelect.Trigger
                placeholder={selectedProfile?.name ?? "Default appearance"}
              />
              <InputSelect.Content>
                <InputSelect.Item value={DEFAULT_BRAND_SELECTION}>
                  Default appearance
                </InputSelect.Item>
                {profiles.map((profile) => (
                  <InputSelect.Item key={profile.id} value={profile.id}>
                    {profile.name}
                  </InputSelect.Item>
                ))}
              </InputSelect.Content>
            </InputSelect>
          </FormField.Control>
          <FormField.Description>
            The default appearance is used when no hostname matches.
          </FormField.Description>
        </FormField>
        <Button
          type="button"
          prominence="secondary"
          icon={SvgPlus}
          onClick={onAddBrand}
        >
          Add Brand
        </Button>
        {selectedProfile && (
          <Button
            type="button"
            variant="danger"
            prominence="tertiary"
            icon={SvgTrash}
            tooltip="Delete brand profile"
            aria-label="Delete brand profile"
            onClick={() => onRemoveBrand(selectedProfile.id)}
          />
        )}
      </div>

      {selectedProfile ? (
        <>
          <Divider />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField state="idle">
              <FormField.Label>Profile Name</FormField.Label>
              <FormField.Control asChild>
                <InputTypeIn
                  value={selectedProfile.name}
                  onChange={(event) =>
                    onUpdateBrand({
                      ...selectedProfile,
                      name: event.target.value,
                    })
                  }
                />
              </FormField.Control>
              <FormField.Description>
                Used only to identify this profile in administration.
              </FormField.Description>
            </FormField>

            <FormField state="idle" className="gap-0">
              <div className="flex h-10 items-center justify-between">
                <FormField.Label>Default for Unmatched Hosts</FormField.Label>
                <FormField.Control>
                  <Switch
                    aria-label="Default for unmatched hosts"
                    checked={defaultBrandId === selectedProfile.id}
                    onCheckedChange={(checked) =>
                      onDefaultBrandChange(checked ? selectedProfile.id : null)
                    }
                  />
                </FormField.Control>
              </div>
              <FormField.Description>
                Otherwise, unmatched hosts use the default appearance above.
              </FormField.Description>
            </FormField>
          </div>

          <FormField state={duplicateHostnames.size > 0 ? "error" : "idle"}>
            <FormField.Label>Hostnames</FormField.Label>
            <FormField.Control>
              <InputChipField
                chips={selectedProfile.hostnames.map((hostname) => ({
                  id: hostname,
                  label: hostname,
                  error: duplicateHostnames.has(hostname.toLowerCase()),
                }))}
                value={hostnameInput}
                onChange={setHostnameInput}
                placeholder="chat.example.com"
                onAdd={(hostname) => {
                  const normalized = hostname.trim().toLowerCase();
                  if (
                    normalized &&
                    !selectedProfile.hostnames.includes(normalized)
                  ) {
                    onUpdateBrand({
                      ...selectedProfile,
                      hostnames: [...selectedProfile.hostnames, normalized],
                    });
                  }
                  setHostnameInput("");
                }}
                onRemoveChip={(hostname) =>
                  onUpdateBrand({
                    ...selectedProfile,
                    hostnames: selectedProfile.hostnames.filter(
                      (existingHostname) => existingHostname !== hostname
                    ),
                  })
                }
              />
            </FormField.Control>
            <FormField.Description>
              Enter exact public hostnames without a scheme, path, or port.
            </FormField.Description>
            {duplicateHostnames.size > 0 && (
              <Text font="secondary-body" color="status-error-05">
                A hostname can only belong to one brand profile.
              </Text>
            )}
          </FormField>
        </>
      ) : (
        <Text font="main-ui-body" color="text-03">
          Edit the existing default appearance below, or add a hostname-specific
          profile.
        </Text>
      )}
    </div>
  );
}
