import { useState } from "react";
import { AlertTriangle, Check, X, Edit3 } from "lucide-react";
import { useApprovals, useDecideApproval } from "@/api/hooks";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";

export function ApprovalPanel({ projectId }: { projectId: string | undefined }) {
  const { data: approvals } = useApprovals(projectId);
  const decide = useDecideApproval(projectId);
  const [noteDraft, setNoteDraft] = useState<Record<string, string>>({});

  if (!approvals || approvals.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 p-3">
      {approvals.map((approval) => (
        <Card key={approval.id} className="p-3 border-brass/40 bg-brass/5">
          <div className="flex items-start gap-2 mb-2">
            <AlertTriangle size={16} className="text-brass shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-text-primary font-medium">{approval.approval_type.replace(/_/g, " ")}</p>
              <p className="text-xs text-text-secondary mt-0.5">{approval.requested_reason}</p>
            </div>
          </div>
          <textarea
            placeholder="Optional note or modified instruction..."
            value={noteDraft[approval.id] ?? ""}
            onChange={(e) => setNoteDraft((d) => ({ ...d, [approval.id]: e.target.value }))}
            rows={2}
            className="w-full bg-base border border-border rounded px-2 py-1.5 text-xs text-text-primary mb-2 resize-none focus:border-signal outline-none"
          />
          <div className="flex gap-2">
            <Button
              variant="primary"
              className="text-xs px-2 py-1"
              onClick={() => decide.mutate({ approvalId: approval.id, decision: "approved", note: noteDraft[approval.id] })}
              disabled={decide.isPending}
            >
              <Check size={13} /> Approve
            </Button>
            <Button
              variant="secondary"
              className="text-xs px-2 py-1"
              onClick={() => decide.mutate({ approvalId: approval.id, decision: "modified", note: noteDraft[approval.id] })}
              disabled={decide.isPending}
            >
              <Edit3 size={13} /> Modify & retry
            </Button>
            <Button
              variant="danger"
              className="text-xs px-2 py-1"
              onClick={() => decide.mutate({ approvalId: approval.id, decision: "rejected", note: noteDraft[approval.id] })}
              disabled={decide.isPending}
            >
              <X size={13} /> Reject
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}
