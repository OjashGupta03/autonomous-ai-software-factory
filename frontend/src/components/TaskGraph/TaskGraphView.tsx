import { useMemo } from "react";
import { ReactFlow, Background, Controls, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { layoutTaskGraph } from "./layout";
import { TaskGraphNodeCard, type TaskNodeData } from "./TaskNode";
import type { TaskGraphNode } from "@/types/api";

const nodeTypes = { factoryTask: TaskGraphNodeCard };

const EDGE_STATUS_COLOR: Record<string, string> = {
  completed: "#5FBD8A",
  failed: "#E8615F",
};

export function TaskGraphView({
  nodes: graphNodes,
  onSelectTask,
  selectedTaskId,
}: {
  nodes: TaskGraphNode[];
  onSelectTask: (taskId: string) => void;
  selectedTaskId?: string;
}) {
  const { flowNodes, flowEdges } = useMemo(() => {
    const layouted = layoutTaskGraph(graphNodes);
    const byId = new Map(graphNodes.map((n) => [n.id, n]));

    const flowNodes: Node<TaskNodeData>[] = layouted.map((l) => ({
      id: l.id,
      type: "factoryTask",
      position: { x: l.x, y: l.y },
      data: { label: l.node.title, status: l.node.status, taskType: l.node.task_type },
      selected: l.id === selectedTaskId,
    }));

    const flowEdges: Edge[] = graphNodes.flatMap((node) =>
      node.depends_on.map((depId) => {
        const sourceStatus = byId.get(depId)?.status;
        return {
          id: `${depId}->${node.id}`,
          source: depId,
          target: node.id,
          type: "step",
          animated: sourceStatus === "running",
          style: { stroke: EDGE_STATUS_COLOR[sourceStatus ?? ""] ?? "#232937", strokeWidth: 1.5 },
        };
      })
    );

    return { flowNodes, flowEdges };
  }, [graphNodes, selectedTaskId]);

  if (graphNodes.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-text-tertiary text-sm">
        No tasks yet - the Planner hasn't decomposed the requirement.
      </div>
    );
  }

  return (
    <ReactFlow
      nodes={flowNodes}
      edges={flowEdges}
      nodeTypes={nodeTypes}
      onNodeClick={(_, node) => onSelectTask(node.id)}
      fitView
      proOptions={{ hideAttribution: true }}
      colorMode="dark"
    >
      <Background color="#1A1F2B" gap={20} />
      <Controls showInteractive={false} className="!bg-surface !border-border" />
    </ReactFlow>
  );
}
