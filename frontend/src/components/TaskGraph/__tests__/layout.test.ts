import { describe, expect, it } from "vitest";
import { layoutTaskGraph } from "../layout";
import type { TaskGraphNode } from "@/types/api";

function node(id: string, dependsOn: string[] = []): TaskGraphNode {
  return { id, title: id, status: "pending", task_type: "backend_implementation", depends_on: dependsOn };
}

describe("layoutTaskGraph", () => {
  it("places a root node before its dependent along the x axis", () => {
    const layouted = layoutTaskGraph([node("A"), node("B", ["A"])]);
    const a = layouted.find((n) => n.id === "A")!;
    const b = layouted.find((n) => n.id === "B")!;
    expect(a.x).toBeLessThan(b.x);
  });

  it("places independent nodes at the same depth in the same column", () => {
    const layouted = layoutTaskGraph([node("A"), node("B"), node("C", ["A", "B"])]);
    const a = layouted.find((n) => n.id === "A")!;
    const b = layouted.find((n) => n.id === "B")!;
    const c = layouted.find((n) => n.id === "C")!;
    expect(a.x).toBe(b.x);
    expect(c.x).toBeGreaterThan(a.x);
  });

  it("handles an empty graph without throwing", () => {
    expect(layoutTaskGraph([])).toEqual([]);
  });

  it("does not infinite-loop on a malformed cyclic graph", () => {
    const layouted = layoutTaskGraph([node("A", ["B"]), node("B", ["A"])]);
    expect(layouted.length).toBe(2);
  });
});
