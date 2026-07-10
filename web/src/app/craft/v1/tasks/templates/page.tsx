"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Button,
  Divider,
  InputTypeIn,
  Tabs,
  Tag,
  Text,
} from "@opal/components";
import {
  SvgCalendar,
  SvgClock,
  SvgFileBroadcast,
  SvgFileChartPie,
  SvgShield,
  SvgSparkle,
} from "@opal/icons";
import {
  ContentAction,
  IllustrationContent,
  SettingsLayouts,
} from "@opal/layouts";
import SvgNoResult from "@opal/illustrations/no-result";
import {
  TASKS_PATH,
  newTaskFromTemplatePath,
} from "@/app/craft/v1/tasks/constants";
import {
  compileLocalPayloadToUtcCron,
  humanReadableScheduleFromCron,
} from "@/app/craft/v1/tasks/schedule";
import {
  SCHEDULED_TASK_TEMPLATES,
  type ScheduledTaskTemplate,
  type ScheduledTaskTemplateCategory,
} from "@/app/craft/v1/tasks/task-starters";

type TemplateFilter = "All" | ScheduledTaskTemplateCategory;

const FILTERS: readonly TemplateFilter[] = [
  "All",
  "Briefings",
  "Knowledge",
  "Operations",
  "Risk",
];

function templateIcon(category: ScheduledTaskTemplateCategory) {
  if (category === "Briefings") return SvgCalendar;
  if (category === "Knowledge") return SvgFileBroadcast;
  if (category === "Risk") return SvgShield;
  return SvgFileChartPie;
}

function templateSchedule(template: ScheduledTaskTemplate): string {
  const compiled = compileLocalPayloadToUtcCron(
    template.mode,
    template.payload
  );
  if (!compiled.ok) return "Review schedule";
  return humanReadableScheduleFromCron(template.mode, compiled.cron);
}

export default function ScheduledTaskTemplatesPage() {
  const router = useRouter();
  const [filter, setFilter] = useState<TemplateFilter>("All");
  const [searchQuery, setSearchQuery] = useState("");
  const visibleTemplates = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return SCHEDULED_TASK_TEMPLATES.filter((template) => {
      const matchesFilter = filter === "All" || template.category === filter;
      const matchesSearch =
        query.length === 0 ||
        template.name.toLowerCase().includes(query) ||
        template.description.toLowerCase().includes(query) ||
        template.prompt.toLowerCase().includes(query);
      return matchesFilter && matchesSearch;
    });
  }, [filter, searchQuery]);

  return (
    <SettingsLayouts.Root width="lg">
      <SettingsLayouts.Header
        backButton={() => router.push(TASKS_PATH)}
        divider
        icon={SvgSparkle}
        title="Automation Templates"
        description="Start with a recurring workflow, then review its prompt, schedule, and app approvals before saving."
      >
        <div className="flex flex-col gap-2">
          <InputTypeIn
            placeholder="Search templates..."
            searchIcon
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
          />
          <Tabs
            value={filter}
            onValueChange={(value) => setFilter(value as TemplateFilter)}
          >
            <Tabs.List>
              {FILTERS.map((value) => (
                <Tabs.Trigger key={value} value={value}>
                  {value}
                </Tabs.Trigger>
              ))}
            </Tabs.List>
          </Tabs>
        </div>
      </SettingsLayouts.Header>

      <SettingsLayouts.Body>
        {visibleTemplates.length === 0 ? (
          <IllustrationContent
            illustration={SvgNoResult}
            title="No matching templates"
            description="Try another search or workflow category."
          />
        ) : (
          <div className="flex w-full flex-col gap-1">
            {visibleTemplates.map((template, index) => (
              <div key={template.id}>
                <ContentAction
                  description={template.description}
                  icon={templateIcon(template.category)}
                  rightChildren={
                    <div className="flex shrink-0 items-center gap-2">
                      <div className="hidden items-end gap-1 sm:flex sm:flex-col">
                        <Tag color="gray" title={template.category} />
                        <div className="flex items-center gap-1">
                          <SvgClock className="h-3.5 w-3.5 text-text-03" />
                          <Text color="text-03" font="secondary-body">
                            {templateSchedule(template)}
                          </Text>
                        </div>
                      </div>
                      <Button
                        href={newTaskFromTemplatePath(template.id)}
                        prominence="secondary"
                      >
                        Use template
                      </Button>
                    </div>
                  }
                  sizePreset="main-ui"
                  title={template.name}
                  variant="section"
                />
                {index < visibleTemplates.length - 1 && (
                  <Divider paddingParallel="fit" paddingPerpendicular="fit" />
                )}
              </div>
            ))}
          </div>
        )}
      </SettingsLayouts.Body>
    </SettingsLayouts.Root>
  );
}
