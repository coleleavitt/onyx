"use client";

import type { Route } from "next";
import { usePathname, useRouter } from "next/navigation";
import { useSettings } from "@/lib/settings/hooks";
import { Tabs, Text } from "@opal/components";
import InputSelect from "@/refresh-components/inputs/InputSelect";

const CUSTOMIZE_TABS = [
  { label: "Skills", path: "/app/customize/skills" },
  { label: "Workflows", path: "/app/customize/workflows" },
  { label: "Memory", path: "/app/customize/memory" },
] as const;

interface CustomizeLayoutProps {
  children: React.ReactNode;
}

export default function CustomizeLayout({ children }: CustomizeLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const settings = useSettings();
  const tabs =
    settings.onyx_craft_enabled === true
      ? CUSTOMIZE_TABS
      : CUSTOMIZE_TABS.filter((tab) => tab.path !== "/app/customize/workflows");
  const active = tabs.find((tab) => pathname.startsWith(tab.path)) ?? tabs[0];

  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      <nav className="shrink-0 border-b border-border-01 bg-background-neutral-00 px-4 py-2 sm:px-6">
        <div className="flex w-full justify-center">
          <div className="w-full max-w-[80rem]">
            <div className="hidden w-[28rem] max-w-full sm:block">
              <Tabs
                variant="underline"
                value={active.path}
                onValueChange={(value) => router.push(value as Route)}
              >
                <Tabs.List>
                  {tabs.map((tab) => (
                    <Tabs.Trigger key={tab.path} value={tab.path}>
                      {tab.label}
                    </Tabs.Trigger>
                  ))}
                </Tabs.List>
              </Tabs>
            </div>
            <div className="sm:hidden">
              <InputSelect
                value={active.path}
                onValueChange={(value) => router.push(value as Route)}
              >
                <InputSelect.Trigger>
                  <Text font="main-ui-body" color="text-04">
                    {active.label}
                  </Text>
                </InputSelect.Trigger>
                <InputSelect.Content>
                  {tabs.map((tab) => (
                    <InputSelect.Item key={tab.path} value={tab.path}>
                      {tab.label}
                    </InputSelect.Item>
                  ))}
                </InputSelect.Content>
              </InputSelect>
            </div>
          </div>
        </div>
      </nav>
      <div className="flex min-h-0 flex-1 justify-center overflow-hidden">
        <div className="h-full w-full max-w-[80rem]">{children}</div>
      </div>
    </div>
  );
}
