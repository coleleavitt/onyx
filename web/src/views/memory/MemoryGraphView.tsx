"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { IllustrationContent } from "@opal/layouts";
import SvgNoResult from "@opal/illustrations/no-result";
import { SvgSimpleLoader } from "@opal/icons";
import { getMemoryGraph } from "@/lib/memory/api";
import type { MemoryGraph, MemoryGraphNode } from "@/lib/memory/types";

const WIDTH = 900;
const HEIGHT = 560;
const ITERATIONS = 150;
const REPULSION = 2600;
const SPRING_LENGTH = 140;
const SPRING_STRENGTH = 0.02;
const CENTERING_STRENGTH = 0.01;
const DAMPING = 0.85;

interface SimNode extends MemoryGraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

function radiusFor(degree: number): number {
  return 6 + 3 * Math.sqrt(Math.max(degree, 0));
}

/**
 * Lightweight, dependency-free force-directed layout: repulsion between all
 * node pairs, spring attraction along edges, and a gentle centering pull.
 * Initial placement on a circle keeps the layout deterministic per data set.
 */
function simulate(graph: MemoryGraph): SimNode[] {
  const centerX = WIDTH / 2;
  const centerY = HEIGHT / 2;
  const layoutRadius = Math.min(WIDTH, HEIGHT) / 2 - 60;
  const nodeCount = Math.max(graph.nodes.length, 1);

  const nodes: SimNode[] = graph.nodes.map((node, index) => {
    const angle = (index / nodeCount) * Math.PI * 2;
    return {
      ...node,
      x: centerX + Math.cos(angle) * layoutRadius,
      y: centerY + Math.sin(angle) * layoutRadius,
      vx: 0,
      vy: 0,
    };
  });

  const byId = new Map(nodes.map((node) => [node.id, node]));
  const edges = graph.edges.filter(
    (edge) => byId.has(edge.source) && byId.has(edge.target)
  );

  for (let iteration = 0; iteration < ITERATIONS; iteration += 1) {
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i]!;
        const b = nodes[j]!;
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        let distSq = dx * dx + dy * dy;
        if (distSq < 0.01) {
          dx = 0.1;
          dy = 0.1;
          distSq = 0.02;
        }
        const dist = Math.sqrt(distSq);
        const force = REPULSION / distSq;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
      }
    }

    for (const edge of edges) {
      const a = byId.get(edge.source);
      const b = byId.get(edge.target);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 0.01);
      const force = (dist - SPRING_LENGTH) * SPRING_STRENGTH;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      a.vx += fx;
      a.vy += fy;
      b.vx -= fx;
      b.vy -= fy;
    }

    for (const node of nodes) {
      node.vx += (centerX - node.x) * CENTERING_STRENGTH;
      node.vy += (centerY - node.y) * CENTERING_STRENGTH;
      node.vx *= DAMPING;
      node.vy *= DAMPING;
      node.x += node.vx;
      node.y += node.vy;

      const margin = radiusFor(node.degree) + 20;
      node.x = Math.min(Math.max(node.x, margin), WIDTH - margin);
      node.y = Math.min(Math.max(node.y, margin), HEIGHT - margin);
    }
  }

  return nodes;
}

interface MemoryGraphViewProps {
  onSelectMemory: (memoryId: number) => void;
}

export default function MemoryGraphView({
  onSelectMemory,
}: MemoryGraphViewProps) {
  const { data: graph, isLoading } = useSWR(
    "/api/memory/graph",
    getMemoryGraph,
    { revalidateOnFocus: false }
  );
  const [nodes, setNodes] = useState<SimNode[] | null>(null);

  useEffect(() => {
    if (!graph) return;
    setNodes(graph.nodes.length > 0 ? simulate(graph) : []);
  }, [graph]);

  const byId = useMemo(
    () => new Map((nodes ?? []).map((node) => [node.id, node])),
    [nodes]
  );
  const edges = useMemo(
    () =>
      (graph?.edges ?? []).filter(
        (edge) => byId.has(edge.source) && byId.has(edge.target)
      ),
    [graph, byId]
  );

  if (isLoading || nodes === null) {
    return (
      <div className="flex justify-center py-16">
        <SvgSimpleLoader className="h-6 w-6" />
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <IllustrationContent
        illustration={SvgNoResult}
        title="No connections yet"
        description="As Onyx links related memories, they'll appear here as a graph."
      />
    );
  }

  return (
    <div className="w-full overflow-hidden rounded-08 border border-border-01 bg-background-tint-02">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-[560px] w-full"
        role="img"
        aria-label="Memory context graph"
      >
        <g>
          {edges.map((edge, index) => {
            const a = byId.get(edge.source);
            const b = byId.get(edge.target);
            if (!a || !b) return null;
            return (
              <line
                key={`${edge.source}-${edge.target}-${index}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="var(--border-02)"
                strokeWidth={1}
              />
            );
          })}
        </g>
        <g>
          {nodes.map((node) => {
            const r = radiusFor(node.degree);
            return (
              <g
                key={node.id}
                className="cursor-pointer"
                onClick={() => onSelectMemory(node.id)}
              >
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={r}
                  fill="var(--action-link-05)"
                  fillOpacity={0.85}
                  stroke="var(--background-neutral-00)"
                  strokeWidth={1.5}
                />
                {r >= 10 ? (
                  <text
                    x={node.x}
                    y={node.y + r + 12}
                    textAnchor="middle"
                    fontSize={11}
                    fill="var(--text-04)"
                  >
                    {node.title.length > 22
                      ? `${node.title.slice(0, 22)}…`
                      : node.title}
                  </text>
                ) : null}
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
