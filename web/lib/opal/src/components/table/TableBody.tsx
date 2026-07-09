"use client";

import {
  type DragStartEvent,
  type DragEndEvent,
  type CollisionDetection,
  type Modifier,
  type SensorDescriptor,
  type SensorOptions,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import type { WithoutStyles } from "@opal/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DraggableProps {
  dndContextProps: {
    sensors: SensorDescriptor<SensorOptions>[];
    collisionDetection: CollisionDetection;
    modifiers: Modifier[];
    onDragStart: (event: DragStartEvent) => void;
    onDragEnd: (event: DragEndEvent) => void;
    onDragCancel: () => void;
  };
  sortableItems: string[];
  activeId: string | null;
  isEnabled: boolean;
}

interface TableBodyProps extends WithoutStyles<
  React.HTMLAttributes<HTMLTableSectionElement>
> {
  ref?: React.Ref<HTMLTableSectionElement>;
  /** DnD context props from useDraggableRows — enables drag-and-drop reordering */
  dndSortable?: DraggableProps;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function TableBody({ ref, dndSortable, ...props }: TableBodyProps) {
  if (dndSortable?.isEnabled) {
    const { sortableItems } = dndSortable;
    return (
      <SortableContext
        items={sortableItems}
        strategy={verticalListSortingStrategy}
      >
        <tbody ref={ref} {...props} />
      </SortableContext>
    );
  }

  return <tbody ref={ref} {...props} />;
}

export default TableBody;
export type { TableBodyProps, DraggableProps };
