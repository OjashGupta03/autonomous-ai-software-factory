import { useState } from "react";
import { File, FileCode } from "lucide-react";
import { useFileContent, useFiles } from "@/api/hooks";
import { cn } from "@/lib/utils";

export function FileViewer({ projectId }: { projectId: string | undefined }) {
  const { data: files } = useFiles(projectId);
  const [selectedPath, setSelectedPath] = useState<string | undefined>();
  const { data: fileContent } = useFileContent(projectId, selectedPath);

  return (
    <div className="flex h-full">
      <div className="w-56 border-r border-border-subtle overflow-y-auto scrollbar-factory shrink-0">
        {files?.length === 0 && <p className="text-text-tertiary text-xs p-3">No files generated yet.</p>}
        {files?.map((file) => (
          <button
            key={file.id}
            onClick={() => setSelectedPath(file.path)}
            className={cn(
              "flex items-center gap-1.5 w-full text-left px-3 py-1.5 text-xs font-mono truncate transition-colors",
              selectedPath === file.path
                ? "bg-surface-hover text-text-primary"
                : "text-text-secondary hover:text-text-primary hover:bg-surface-hover/50"
            )}
            title={file.path}
          >
            <FileCode size={12} className="shrink-0 text-text-tertiary" />
            {file.path}
            <span className="ml-auto text-text-tertiary">v{file.version}</span>
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-auto scrollbar-factory">
        {!selectedPath && (
          <div className="h-full flex items-center justify-center text-text-tertiary text-sm gap-2">
            <File size={16} />
            Select a file to view its contents
          </div>
        )}
        {fileContent && (
          <pre className="text-xs font-mono text-text-primary p-4 leading-relaxed whitespace-pre-wrap">
            <code>{fileContent.content}</code>
          </pre>
        )}
      </div>
    </div>
  );
}
