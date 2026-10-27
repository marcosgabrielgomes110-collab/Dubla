import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  CheckCircle2,
  Cpu,
  Disc3,
  Film,
  HardDrive,
  Mic2,
  Radio,
  ServerCog,
  XCircle,
} from "lucide-react";

import { PageHeader } from "@/components/PageHeader";
import { Badge, Card, CardHint, CardTitle, EmptyState, Meter, StatusBadge } from "@/components/ui";
import { api, mediaUrl } from "@/lib/api";
import { formatBytes, formatDuration, timeAgo } from "@/lib/utils";

function Stat({
  icon: Icon,
  label,
  value,
  hint,
  tone = "emerald",
}: {
  icon: typeof Film;
  label: string;
  value: string;
  hint: string;
  tone?: "emerald" | "cyan" | "amber";
}) {
  const colors = {
    emerald: "text-emerald-300 bg-emerald-400/10 border-emerald-400/20",
    cyan: "text-cyan-300 bg-cyan-400/10 border-cyan-400/20",
    amber: "text-amber-300 bg-amber-400/10 border-amber-400/20",
  } as const;
  return (
    <Card className="flex items-start gap-4">
      <div className={`rounded-lg border p-2.5 ${colors[tone]}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
        <p className="mt-0.5 truncate text-xl font-semibold text-white">{value}</p>
        <p className="mt-0.5 text-xs text-slate-500">{hint}</p>
      </div>
    </Card>
  );
}

export default function Dashboard() {
  const system = useQuery({ queryKey: ["system"], queryFn: api.system, refetchInterval: 15000 });
  const jobs = useQuery({ queryKey: ["jobs", "recent"], queryFn: () => api.jobs(8) });
  const movies = useQuery({ queryKey: ["movies"], queryFn: api.movies });
  const previews = useQuery({ queryKey: ["previews"], queryFn: api.previews });

  const info = system.data;
  const running = jobs.data?.filter((job) => job.status === "running").length ?? 0;
  const installed = info ? Object.entries(info.packages).filter(([, value]) => value) : [];

  return (
    <div>
      <PageHeader
        eyebrow="studio overview"
        title="Visão geral"
        description="Estado do pipeline, fila de jobs, disco e vozes disponíveis."
        actions={
          <Link
            to="/pipeline"
            className="inline-flex h-9 items-center gap-2 rounded-lg bg-emerald-400 px-4 text-sm font-medium text-emerald-950 transition-colors hover:bg-emerald-300"
          >
            <Radio className="h-4 w-4" /> Novo pipeline
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          icon={Film}
          label="Filmes publicados"
          value={String(movies.data?.length ?? 0)}
          hint="em Data/Movies"
        />
        <Stat
          icon={Radio}
          label="Jobs ativos"
          value={String(running)}
          hint={running ? "processando agora" : "fila livre"}
          tone="cyan"
        />
        <Stat
          icon={HardDrive}
          label="Disco livre"
          value={info ? formatBytes(info.disk.free) : "—"}
          hint={info ? `${formatBytes(info.disk.used)} usados` : "carregando"}
          tone="amber"
        />
        <Stat
          icon={Cpu}
          label="RAM disponível"
          value={info ? formatBytes(info.memory.available) : "—"}
          hint={info ? `de ${formatBytes(info.memory.total)}` : "carregando"}
        />
      </div>

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1.35fr_1fr]">
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Jobs recentes</CardTitle>
              <CardHint>Execuções criadas pela API ou pelo CLI.</CardHint>
            </div>
            <ServerCog className="h-4 w-4 text-slate-500" />
          </div>

          <div className="mt-4 space-y-2">
            {jobs.isLoading && <p className="text-xs text-slate-500">carregando…</p>}
            {jobs.data?.length === 0 && <EmptyState title="Nenhum job ainda" hint="Rode o primeiro pipeline." />}
            {jobs.data?.map((job) => (
              <div
                key={job.id}
                className="flex flex-wrap items-center gap-3 rounded-lg border border-white/[0.06] bg-black/20 px-3 py-2.5"
              >
                <StatusBadge status={job.status} />
                <span className="text-xs font-medium text-slate-200">{job.type}</span>
                <span className="truncate font-mono text-[11px] text-slate-500">{job.id.slice(0, 10)}</span>
                <span className="ml-auto text-[11px] text-slate-500">{timeAgo(job.created_at)}</span>
                {job.status === "succeeded" && job.result && (
                  <Link to="/movies" className="text-emerald-300 hover:text-emerald-200">
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </Link>
                )}
              </div>
            ))}
          </div>
        </Card>

        <div className="space-y-6">
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Ambiente</CardTitle>
                <CardHint>{info ? `${info.hostname} · Python ${info.python}` : "carregando…"}</CardHint>
              </div>
              <Disc3 className="h-4 w-4 text-slate-500" />
            </div>

            {info && (
              <>
                <div className="mt-4 space-y-3">
                  <div>
                    <div className="mb-1 flex justify-between text-[11px] text-slate-500">
                      <span>Disco</span>
                      <span>{Math.round((info.disk.used / info.disk.total) * 100)}%</span>
                    </div>
                    <Meter value={info.disk.used} max={info.disk.total} />
                  </div>
                  <div>
                    <div className="mb-1 flex justify-between text-[11px] text-slate-500">
                      <span>RAM</span>
                      <span>{Math.round((1 - info.memory.available / info.memory.total) * 100)}%</span>
                    </div>
                    <Meter value={info.memory.total - info.memory.available} max={info.memory.total} tone="cyan" />
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-1.5">
                  {Object.entries(info.binaries).map(([name, path]) => (
                    <Badge key={name} tone={path ? "emerald" : "zinc"}>
                      {path ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                      {name}
                    </Badge>
                  ))}
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {installed.map(([name]) => (
                    <Badge key={name} tone="violet">
                      {name}
                    </Badge>
                  ))}
                </div>
              </>
            )}
          </Card>

          <Card>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Previews de voz</CardTitle>
                <CardHint>Mesma frase em cada motor.</CardHint>
              </div>
              <Mic2 className="h-4 w-4 text-slate-500" />
            </div>
            <div className="mt-4 space-y-2">
              {previews.data?.map((preview) => (
                <div key={preview.name} className="flex items-center gap-3">
                  <span className="w-24 shrink-0 text-xs text-slate-300">
                    {preview.name.replace(".wav", "")}
                  </span>
                  <audio
                    controls
                    preload="none"
                    src={mediaUrl(`/system/previews/${preview.name}`)}
                    className="h-8 w-full"
                  />
                </div>
              ))}
              {previews.data?.length === 0 && (
                <p className="text-xs text-slate-500">Gere as previews com o script de vozes.</p>
              )}
            </div>
          </Card>
        </div>
      </div>

      {movies.data && movies.data.length > 0 && (
        <Card className="mt-6">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Últimos filmes</CardTitle>
              <CardHint>Publicados em Data/Movies.</CardHint>
            </div>
            <Link to="/movies" className="text-xs text-emerald-300 hover:text-emerald-200">
              ver todos
            </Link>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {movies.data.slice(0, 3).map((movie) => (
              <Link
                key={movie.id}
                to="/movies"
                className="rounded-lg border border-white/[0.06] bg-black/20 px-3 py-3 transition-colors hover:border-emerald-400/30"
              >
                <p className="truncate text-sm font-medium text-slate-200">{movie.title ?? movie.id}</p>
                <p className="mt-1 text-[11px] text-slate-500">
                  {movie.language ?? "—"} · {formatDuration(movie.duration)} · {formatBytes(movie.size)}
                </p>
              </Link>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
