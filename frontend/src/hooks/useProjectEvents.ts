import { useEffect, useRef, useState } from "react";
import { getAuthToken } from "@/api/client";
import type { ProjectEventPayload } from "@/types/api";

const MAX_EVENTS_KEPT = 200;

/**
 * Subscribes to the backend's SSE stream (GET /projects/{id}/events) and
 * keeps a rolling buffer of recent events for the live activity feed
 * (spec section 22). Uses a plain EventSource-style fetch+ReadableStream
 * reader rather than the native `EventSource` API because EventSource
 * cannot send an Authorization header - see docs/16-frontend.md.
 */
export function useProjectEvents(projectId: string | undefined) {
  const [events, setEvents] = useState<ProjectEventPayload[]>([]);
  const [connected, setConnected] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!projectId) return;
    setEvents([]);

    const controller = new AbortController();
    abortRef.current = controller;

    async function connect() {
      try {
        const token = getAuthToken();
        const response = await fetch(`/api/v1/projects/${projectId}/events`, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
          signal: controller.signal,
        });
        if (!response.ok || !response.body) {
          setConnected(false);
          return;
        }
        setConnected(true);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";
          for (const part of parts) {
            const line = part.split("\n").find((l) => l.startsWith("data: "));
            if (!line) continue; // heartbeat comment lines have no "data: " prefix
            try {
              const parsed = JSON.parse(line.slice("data: ".length)) as ProjectEventPayload;
              setEvents((prev) => [...prev.slice(-(MAX_EVENTS_KEPT - 1)), parsed]);
            } catch {
              // malformed/partial chunk - skip rather than crash the stream
            }
          }
        }
      } catch {
        // fetch aborted (unmount / project change) or network error
      } finally {
        setConnected(false);
      }
    }

    connect();
    return () => controller.abort();
  }, [projectId]);

  return { events, connected };
}
