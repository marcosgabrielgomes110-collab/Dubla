import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Film, Play, Trash2, X } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/PageHeader";
import { Badge, Button, Card, CardHint, CardTitle, EmptyState } from "@/components/ui";
import { api, mediaUrl } from "@/lib/api";
import { formatBytes, formatDuration, timeAgo } from "@/lib/utils";

export default function Movies() {
  const queryClient = useQueryClient();
  const movies = useQuery({ queryKey: ["movies"], queryFn: api.movies });
  const [selected, setSelected] = useState<string | null>(null);
  const detail = useQuery({
    queryKey: ["movie", selected],
    queryFn: () => api.movie(selected!),
    enabled: Boolean(selected),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteMovie(id),
    onSuccess: () => {
      toast.success("Filme removido");
      setSelected(null);
      void queryClient.invalidateQueries({ queryKey: ["movies"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const current = detail.data as
    | {
        title?: string;
        duration?: number;
        translation?: { engine?: string; model?: string; source?: string; target?: string };
        stt?: { engine?: string; model?: string };
        voice?: { engine?: string; voice?: string };
        movie?: { path?: string; overlaps?: number };
        segments_traduct?: unknown[];
      }
    | undefined;

  return (
    <div>
      <PageHeader
        eyebrow="library"
        title="Filmes publicados"
        description="Vídeos dublados em Data/Movies, com player direto e download."
      />

      {movies.isLoading && <p className="text-sm text-slate-500">carregando…</p>}
      {movies.data?.length === 0 && (
        <EmptyState title="Nenhum filme publicado" hint="Rode o pipeline para gerar o primeiro." />
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {movies.data?.map((movie) => (
          <Card key={movie.id} className="flex flex-col gap-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-100">{movie.title ?? movie.id}</p>
                <p className="mt-0.5 font-mono text-[10px] text-slate-500">{movie.id}</p>
              </div>
              <Badge tone="cyan">{movie.language ?? "—"}</Badge>
            </div>

            <div className="flex flex-wrap gap-1.5 text-[11px] text-slate-400">
              <span>{formatDuration(movie.duration)}</span>
              <span className="text-slate-600">·</span>
              <span>{formatBytes(movie.size)}</span>
              <span className="text-slate-600">·</span>
              <span>{timeAgo(movie.created_at)}</span>
            </div>

            <div className="mt-auto flex items-center gap-2">
              <Button size="sm" onClick={() => setSelected(movie.id)}>
                <Play className="h-3.5 w-3.5" /> Assistir
              </Button>
              <a
                href={mediaUrl(`/movies/${movie.id}/video`)}
                download={movie.video}
                className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/15 bg-white/[0.04] px-3 text-xs text-slate-200 hover:bg-white/[0.08]"
              >
                <Download className="h-3.5 w-3.5" /> Baixar
              </a>
              <button
                type="button"
                onClick={() => {
                  if (window.confirm(`Excluir ${movie.title ?? movie.id}?`)) remove.mutate(movie.id);
                }}
                className="ml-auto rounded-lg p-1.5 text-slate-500 hover:bg-rose-500/10 hover:text-rose-300"
                title="Excluir"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </Card>
        ))}
      </div>

      {selected && (
        <Card className="mt-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>{current?.title ?? "Filme"}</CardTitle>
              <CardHint>
                {current?.stt?.engine}/{current?.stt?.model} ·{" "}
                {current?.translation?.engine}/{current?.translation?.model} ·{" "}
                {current?.voice?.engine} ({current?.voice?.voice})
              </CardHint>
            </div>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="rounded-lg p-1 text-slate-500 hover:bg-white/[0.06] hover:text-slate-200"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-4 overflow-hidden rounded-xl border border-white/10 bg-black">
            <video
              key={selected}
              controls
              autoPlay
              className="aspect-video w-full"
              src={mediaUrl(`/movies/${selected}/video`)}
            />
          </div>

          <div className="mt-3 grid gap-2 text-[11px] text-slate-400 sm:grid-cols-3">
            <p>
              <span className="text-slate-500">origem:</span>{" "}
              {current?.translation?.source ?? "—"} → {current?.translation?.target ?? "—"}
            </p>
            <p>
              <span className="text-slate-500">blocos:</span>{" "}
              {current?.segments_traduct?.length ?? "—"}
            </p>
            <p>
              <span className="text-slate-500">overlaps:</span> {current?.movie?.overlaps ?? "—"}
            </p>
          </div>

          <p className="mt-2 break-all font-mono text-[10px] text-slate-600">
            {current?.movie?.path ?? ""}
          </p>

          <div className="mt-4 flex items-center gap-2">
            <a
              href={mediaUrl(`/movies/${selected}/video`)}
              download
              className="inline-flex h-8 items-center gap-2 rounded-lg border border-white/15 bg-white/[0.04] px-3 text-xs text-slate-200 hover:bg-white/[0.08]"
            >
              <Film className="h-3.5 w-3.5" /> baixar MP4
            </a>
          </div>
        </Card>
      )}
    </div>
  );
}
