"use client";

import type { Route } from "next";
import { usePathname, useRouter } from "next/navigation";
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
  const active =
    CUSTOMIZE_TABS.find((tab) => pathname.startsWith(tab.path)) ??
    CUSTOMIZE_TABS[0];

  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      <nav className="shrink-0 border-b border-border-01 bg-background-01 px-4 py-2 sm:px-6">
        <div className="hidden sm:block">
          <Tabs
            value={active.path}
            onValueChange={(value) => router.push(value as Route)}
          >
            <Tabs.List>
              {CUSTOMIZE_TABS.map((tab) => (
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
              {CUSTOMIZE_TABS.map((tab) => (
                <InputSelect.Item key={tab.path} value={tab.path}>
                  {tab.label}
                </InputSelect.Item>
              ))}
            </InputSelect.Content>
          </InputSelect>
        </div>
      </nav>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </div>
  );
}
