import { useEffect, useRef } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";

import { getToken } from "@/lib/api";
import type { LogEvent, JobStatus } from "@/lib/types";

interface Handlers {
  onLog: (event: LogEvent) => void;
  onStatus: (status: JobStatus) => void;
  onError?: (error: unknown) => void;
}

const TERMINAL: JobStatus[] = ["succeeded", "failed", "cancelled"];

export function useJobStream(jobId: string | null, handlers: Handlers) {
  const ref = useRef(handlers);
  ref.current = handlers;

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();

    const connect = async () => {
      try {
        await fetchEventSource(`/api/v1/jobs/${jobId}/events`, {
          headers: getToken() ? { "X-API-Token": getToken() } : {},
          signal: controller.signal,
          openWhenHidden: true,
          async onmessage(message) {
            if (message.event === "status") {
              const status = JSON.parse(message.data).status as JobStatus;
              ref.current.onStatus(status);
              if (TERMINAL.includes(status)) controller.abort();
              return;
            }
            if (!message.data) return;
            try {
              ref.current.onLog(JSON.parse(message.data) as LogEvent);
            } catch {
              /* ignore malformed line */
            }
          },
          onerror(error) {
            ref.current.onError?.(error);
            throw error;
          },
        });
      } catch {
        /* aborted or finished */
      }
    };

    void connect();
    return () => controller.abort();
  }, [jobId]);
}
