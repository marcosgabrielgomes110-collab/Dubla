import { useEffect, useRef } from "react";

import type { LogEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

const levelColor: Record<string, string> = {
  info: "text-slate-300",
  ok: "text-emerald-300",
  warning: "text-amber-300",
  error: "text-rose-300",
  progress: "text-slate-400",
};

export function JobLog({ logs, empty = "Os logs aparecem aqui quando o job começa." }: { logs: LogEvent[]; empty?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = ref.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [logs.length]);

  return (
    <div
      ref={ref}
      className="h-[360px] overflow-y-auto rounded-lg border border-white/[0.06] bg-black/40 p-3 font-mono text-[11px] leading-relaxed"
    >
      {logs.length === 0 && <p className="text-slate-500">{empty}</p>}
      {logs.map((log, index) => (
        <div key={`${log.ts}-${index}`} className="flex gap-2">
          <span className="shrink-0 text-slate-600">{log.ts?.slice(11, 19) ?? "--:--:--"}</span>
          <span className={cn("shrink-0 uppercase", levelColor[log.level] ?? "text-slate-300")}>
            {log.level.slice(0, 5)}
          </span>
          <span className="whitespace-pre-wrap break-words text-slate-300">{log.message}</span>
        </div>
      ))}
    </div>
  );
}
