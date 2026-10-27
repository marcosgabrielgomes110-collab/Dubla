import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, DownloadCloud, AudioLines, XCircle } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/PageHeader";
import { Badge, Button, Card, CardHint, CardTitle, EmptyState, StatusBadge } from "@/components/ui";
import { api, mediaUrl } from "@/lib/api";
import { formatBytes } from "@/lib/utils";

export default function Models() {
  const queryClient = useQueryClient();
  const system = useQuery({ queryKey: ["system"], queryFn: api.system });
  const previews = useQuery({ queryKey: ["previews"], queryFn: api.previews });
  const jobs = useQuery({ queryKey: ["jobs", "models"], queryFn: () => api.jobs(10) });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });

  const language = String(settings.data?.output_language ?? "pt-BR");

  const create = useMutation({
    mutationFn: (payload: {
      name?: string;
      params: Record<string, unknown>;
      type: "script" | "models";
    }) =>
      api.createJob({
        type: payload.type,
        name: payload.name,
        params: payload.params,
      }),
    onSuccess: (job) => {
      toast.success(`Job ${job.id.slice(0, 8)} criado`);
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const modelJobs = jobs.data?.filter((job) => job.type === "models" || job.params?.name) ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="assets"
        title="Vozes & modelos"
        description="Downloads de vozes/modelos e previews de cada motor."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <div className="flex items-center gap-2">
            <DownloadCloud className="h-4 w-4 text-cyan-300" />
            <CardTitle>Downloads</CardTitle>
          </div>
          <CardHint>Cada download roda como job em background.</CardHint>

          <div className="mt-4 grid gap-2">
            <Button
              variant="outline"
              disabled={create.isPending}
              onClick={() =>
                create.mutate({
                  type: "models",
                  params: { engine: "piper", languages: [language] },
                })
              }
            >
              Piper · {language}
            </Button>
            <Button
              variant="outline"
              disabled={create.isPending}
              onClick={() =>
                create.mutate({
                  type: "models",
                  params: { engine: "pocket", languages: [language] },
                })
              }
            >
              Pocket TTS · {language}
            </Button>
            <Button
              variant="outline"
              disabled={create.isPending}
              onClick={() =>
                create.mutate({
                  type: "script",
                  name: "download_models",
                  params: { languages: ["en-US"], engine: "whisper" },
                })
              }
            >
              Whisper · en-US
            </Button>
            <Button
              variant="outline"
              disabled={create.isPending}
              onClick={() =>
                create.mutate({
                  type: "script",
                  name: "download_models",
                  params: { languages: ["en-US"], engine: "vosk" },
                })
              }
            >
              Vosk · en-US
            </Button>
          </div>

          <div className="mt-4 flex flex-wrap gap-1.5">
            {Object.entries(system.data?.packages ?? {}).map(([name, installed]) => (
              <Badge key={name} tone={installed ? "emerald" : "zinc"}>
                {installed ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                {name}
              </Badge>
            ))}
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-2">
            <AudioLines className="h-4 w-4 text-emerald-300" />
            <CardTitle>Previews</CardTitle>
          </div>
          <CardHint>Mesma frase, um arquivo por motor.</CardHint>

          <div className="mt-4 space-y-3">
            {previews.data?.map((preview) => (
              <div key={preview.name}>
                <div className="mb-1 flex items-center justify-between text-[11px] text-slate-400">
                  <span>{preview.name}</span>
                  <span>{formatBytes(preview.size)}</span>
                </div>
                <audio
                  controls
                  preload="none"
                  className="h-8 w-full"
                  src={mediaUrl(`/system/previews/${preview.name}`)}
                />
              </div>
            ))}
            {previews.data?.length === 0 && <EmptyState title="Sem previews" />}
          </div>
        </Card>
      </div>

      <Card className="mt-6">
        <CardTitle>Jobs de download</CardTitle>
        <div className="mt-3 space-y-2">
          {modelJobs.length === 0 && <p className="text-xs text-slate-500">Nenhum download recente.</p>}
          {modelJobs.map((job) => (
            <div
              key={job.id}
              className="flex flex-wrap items-center gap-2 rounded-lg border border-white/[0.06] bg-black/20 px-3 py-2 text-xs"
            >
              <StatusBadge status={job.status} />
              <span className="text-slate-300">{job.type}</span>
              <span className="font-mono text-[10px] text-slate-500">{job.id.slice(0, 10)}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
