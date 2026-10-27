import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";
import type { JobStatus } from "@/lib/types";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-emerald-400 text-emerald-950 hover:bg-emerald-300",
        outline: "border border-white/15 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]",
        ghost: "text-slate-300 hover:bg-white/[0.06] hover:text-white",
        destructive: "bg-rose-500/90 text-white hover:bg-rose-500",
        subtle: "bg-white/[0.08] text-slate-100 hover:bg-white/[0.14]",
      },
      size: {
        default: "h-9 px-4",
        sm: "h-8 px-3 text-xs",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export function Button({
  className,
  variant,
  size,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("panel p-5", className)}>{children}</div>;
}

export function CardTitle({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={cn("text-sm font-semibold tracking-tight text-slate-100", className)}>{children}</h2>;
}

export function CardHint({ children }: { children: ReactNode }) {
  return <p className="mt-1 text-xs text-slate-400">{children}</p>;
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-9 w-full rounded-lg border border-white/10 bg-[#0b1118] px-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-emerald-400/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/20",
        className,
      )}
      {...props}
    />
  );
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-9 w-full rounded-lg border border-white/10 bg-[#0b1118] px-3 text-sm text-slate-100 focus:border-emerald-400/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/20",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function Label({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <label className={cn("mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-slate-400", className)}>
      {children}
    </label>
  );
}

export function Badge({
  children,
  tone = "zinc",
  className,
}: {
  children: ReactNode;
  tone?: "zinc" | "emerald" | "amber" | "rose" | "cyan" | "violet";
  className?: string;
}) {
  const tones: Record<string, string> = {
    zinc: "border-white/10 bg-white/[0.06] text-slate-300",
    emerald: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    amber: "border-amber-400/30 bg-amber-400/10 text-amber-300",
    rose: "border-rose-400/30 bg-rose-400/10 text-rose-300",
    cyan: "border-cyan-400/30 bg-cyan-400/10 text-cyan-300",
    violet: "border-violet-400/30 bg-violet-400/10 text-violet-300",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const statusTone: Record<JobStatus, "zinc" | "emerald" | "amber" | "rose" | "cyan"> = {
  queued: "amber",
  running: "cyan",
  succeeded: "emerald",
  failed: "rose",
  cancelled: "zinc",
};

export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <Badge tone={statusTone[status]}>
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          status === "running" && "animate-pulse bg-cyan-300",
          status === "succeeded" && "bg-emerald-300",
          status === "failed" && "bg-rose-300",
          status === "queued" && "bg-amber-300",
          status === "cancelled" && "bg-slate-400",
        )}
      />
      {status}
    </Badge>
  );
}

export function Meter({ value, max, tone = "emerald" }: { value: number; max: number; tone?: "emerald" | "cyan" | "amber" }) {
  const percent = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  const bars: Record<string, string> = {
    emerald: "bg-emerald-400",
    cyan: "bg-cyan-400",
    amber: "bg-amber-400",
  };
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
      <div className={cn("h-full rounded-full transition-all", bars[tone])} style={{ width: `${percent}%` }} />
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-white/10 px-6 py-14 text-center">
      <p className="text-sm font-medium text-slate-300">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
