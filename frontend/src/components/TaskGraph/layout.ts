import type { TaskGraphNode } from "@/types/api";

export interface LayoutedNode {
  id: string;
  x: number;
  y: number;
  node: TaskGraphNode;
}

const COLUMN_WIDTH = 260;
const ROW_HEIGHT = 96;

/**
 * A small dependency-depth layout: each node's column is the length of
 * the longest dependency chain leading to it (so an edge never points
 * right-to-left), and within a column, nodes stack top to bottom in a
 * stable order. This avoids pulling in a full graph-layout dependency
 * (e.g. dagre) for what is, for this project's task counts, a fairly
 * small DAG - see docs/16-frontend.md.
 */
export function layoutTaskGraph(nodes: TaskGraphNode[]): LayoutedNode[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const depthCache = new Map<string, number>();

  function depthOf(id: string, guard: Set<string> = new Set()): number {
    if (depthCache.has(id)) return depthCache.get(id)!;
    if (guard.has(id)) return 0; // defensive: a cycle should never reach the UI, but never hang if it does
    const node = byId.get(id);
    if (!node || node.depends_on.length === 0) {
      depthCache.set(id, 0);
      return 0;
    }
    guard.add(id);
    const depth = 1 + Math.max(...node.depends_on.map((dep) => depthOf(dep, guard)));
    guard.delete(id);
    depthCache.set(id, depth);
    return depth;
  }

  const columns = new Map<number, TaskGraphNode[]>();
  for (const node of nodes) {
    const depth = depthOf(node.id);
    const bucket = columns.get(depth) ?? [];
    bucket.push(node);
    columns.set(depth, bucket);
  }

  const layouted: LayoutedNode[] = [];
  for (const [depth, bucket] of [...columns.entries()].sort((a, b) => a[0] - b[0])) {
    bucket.forEach((node, row) => {
      layouted.push({ id: node.id, x: depth * COLUMN_WIDTH, y: row * ROW_HEIGHT, node });
    });
  }
  return layouted;
}
