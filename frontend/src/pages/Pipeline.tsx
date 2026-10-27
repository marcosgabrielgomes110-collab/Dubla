import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Ban, Loader2, Play, Radio, TerminalSquare } from "lucide-react";
import { toast } from "sonner";

import { JobLog } from "@/components/JobLog";
import { PageHeader } from "@/components/PageHeader";
import { Badge, Button, Card, CardHint, CardTitle, Input, Label, Select, StatusBadge } from "@/components/ui";
import { useJobStream } from "@/hooks/useJobStream";
import { api } from "@/lib/api";
import type { JobStatus, LogEvent } from "@/lib/types";

interface FormState {
  stt_engine: string;
  stt_whisper_model: string;
  stt_vosk_model: string;
  translation_engine: string;
  deep_translator_backend: string;
  voice_engine: string;
  output_language: string;
  voice_parallel: boolean;
  voice_workers: number;
}

const defaults: FormState = {
  stt_engine: "whisper",
  stt_whisper_model: "base",
  stt_vosk_model: "auto",
  translation_engine: "argos",
  deep_translator_backend: "mymemory",
  voice_engine: "piper",
  output_language: "pt-BR",
  voice_parallel: false,
  voice_workers: 4,
};

export default function Pipeline() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const schema = useQuery({ queryKey: ["settings", "schema"], queryFn: api.schema });

  const [url, setUrl] = useState("");
  const [force, setForce] = useState(false);
  const [form, setForm] = useState<FormState>(defaults);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [logs, setLogs] = useState<LogEvent[]>([]);

  useEffect(() => {
    if (!settings.data) return;
    setForm((current) => ({
      ...current,
      stt_engine: String(settings.data.stt_engine ?? current.stt_engine),
      stt_whisper_model: String(settings.data.stt_whisper_model ?? current.stt_whisper_model),
      stt_vosk_model: String(settings.data.stt_vosk_model ?? current.stt_vosk_model),
      translation_engine: String(settings.data.translation_engine ?? current.translation_engine),
      deep_translator_backend: String(
        settings.data.deep_translator_backend ?? current.deep_translator_backend,
      ),
      voice_engine: String(settings.data.voice_engine ?? current.voice_engine),
      output_language: String(settings.data.output_language ?? current.output_language),
      voice_parallel: Boolean(settings.data.voice_parallel ?? current.voice_parallel),
      voice_workers: Number(settings.data.voice_workers ?? current.voice_workers),
    }));
  }, [settings.data]);

  useJobStream(jobId, {
    onLog: (event) => setLogs((current) => [...current, event]),
    onStatus: (next) => {
      setStatus(next);
      if (["succeeded", "failed", "cancelled"].includes(next)) {
        void queryClient.invalidateQueries({ queryKey: ["jobs"] });
        if (next === "succeeded") void queryClient.invalidateQueries({ queryKey: ["movies"] });
      }
    },
    onError: () => toast.error("Conexão de logs interrompida"),
  });

  const run = useMutation({
    mutationFn: async () => {
      await api.patchSettings({ ...form });
      return api.createJob({ type: "pipeline", url: url.trim(), params: { force } });
    },
    onSuccess: (job) => {
      setJobId(job.id);
      setStatus(job.status);
      setLogs([]);
      toast.success("Pipeline iniciado");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const cancel = useMutation({
    mutationFn: () => api.cancelJob(jobId!),
    onSuccess: () => toast.message("Cancelamento solicitado"),
    onError: (error: Error) => toast.error(error.message),
  });

  const enumOptions = (key: string, fallback: string[]) =>
    schema.data?.settings?.[key]?.options ?? fallback;

  const running = status === "running" || status === "queued";
  const canRun = url.trim().length > 8 && !run.isPending && !running;

  const languageOptions = useMemo(
    () => ["pt-BR", "pt-PT", "en-US", "es-ES", "fr-FR", "de-DE", "it-IT", "ja-JP", "zh-CN"],
    [],
  );

  return (
    <div>
      <PageHeader
        eyebrow="run"
        title="Pipeline"
        description="Baixa, transcreve, traduz, gera a voz, monta o áudio e publica o filme dublado."
      />

      <div className="grid gap-6 lg:grid-cols-[1.05fr_1fr]">
        <Card>
          <div className="flex items-center gap-2">
            <Radio className="h-4 w-4 text-emerald-300" />
            <CardTitle>Nova execução</CardTitle>
          </div>
          <CardHint>Os motores escolhidos são salvos no configs.json antes de iniciar o job.</CardHint>

          <div className="mt-5 space-y-4">
            <div>
              <Label>URL do vídeo</Label>
              <Input
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                spellCheck={false}
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label>STT</Label>
                <Select
                  value={form.stt_engine}
                  onChange={(event) => setForm({ ...form, stt_engine: event.target.value })}
                >
                  {enumOptions("stt_engine", ["whisper", "vosk", "auto"]).map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Modelo STT</Label>
                <Select
                  value={form.stt_whisper_model}
                  onChange={(event) => setForm({ ...form, stt_whisper_model: event.target.value })}
                >
                  {enumOptions("stt_whisper_model", ["tiny", "base", "small", "medium", "large-v3"]).map(
                    (option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ),
                  )}
                </Select>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label>Tradução</Label>
                <Select
                  value={form.translation_engine}
                  onChange={(event) =>
                    setForm({ ...form, translation_engine: event.target.value })
                  }
                >
                  {enumOptions("translation_engine", ["argos", "llm", "deep-translator"]).map(
                    (option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ),
                  )}
                </Select>
              </div>
              <div>
                <Label>Backend deep-translator</Label>
                <Select
                  value={form.deep_translator_backend}
                  onChange={(event) =>
                    setForm({ ...form, deep_translator_backend: event.target.value })
                  }
                >
                  {enumOptions("deep_translator_backend", ["mymemory", "google", "auto"]).map(
                    (option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ),
                  )}
                </Select>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label>Voz</Label>
                <Select
                  value={form.voice_engine}
                  onChange={(event) => setForm({ ...form, voice_engine: event.target.value })}
                >
                  {enumOptions("voice_engine", ["piper", "pocket", "elevenlabs", "espeak", "qwen"]).map(
                    (option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ),
                  )}
                </Select>
              </div>
              <div>
                <Label>Idioma de saída</Label>
                <Select
                  value={form.output_language}
                  onChange={(event) => setForm({ ...form, output_language: event.target.value })}
                >
                  {languageOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex items-center gap-2 rounded-lg border border-white/[0.07] bg-black/20 px-3 py-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={form.voice_parallel}
                  onChange={(event) => setForm({ ...form, voice_parallel: event.target.checked })}
                  className="h-3.5 w-3.5 accent-emerald-400"
                />
                Voz em paralelo
              </label>
              <div>
                <Label>Workers</Label>
                <Input
                  type="number"
                  min={1}
                  max={16}
                  value={form.voice_workers}
                  onChange={(event) =>
                    setForm({ ...form, voice_workers: Number(event.target.value) || 1 })
                  }
                />
              </div>
            </div>

            <label className="flex items-center gap-2 text-xs text-slate-300">
              <input
                type="checkbox"
                checked={force}
                onChange={(event) => setForce(event.target.checked)}
                className="h-3.5 w-3.5 accent-emerald-400"
              />
              Forçar reprocessamento e sobrescrever a publicação
            </label>

            <div className="flex items-center gap-2 pt-1">
              <Button onClick={() => run.mutate()} disabled={!canRun}>
                {run.isPending || running ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                {running ? "Executando" : "Iniciar pipeline"}
              </Button>
              {jobId && (
                <Button
                  variant="outline"
                  onClick={() => cancel.mutate()}
                  disabled={!running || cancel.isPending}
                >
                  <Ban className="h-4 w-4" /> Cancelar
                </Button>
              )}
              <Link to="/movies" className="ml-auto text-xs text-slate-400 hover:text-slate-200">
                ver filmes
              </Link>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <TerminalSquare className="h-4 w-4 text-slate-400" />
                <CardTitle>Job</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {status && <StatusBadge status={status} />}
                {jobId && <Badge tone="zinc">{jobId.slice(0, 10)}</Badge>}
              </div>
            </div>
            <CardHint>
              Logs em tempo real via SSE. O processo roda isolado do servidor da API.
            </CardHint>
            {jobId && (
              <p className="mt-2 break-all font-mono text-[10px] text-slate-500">
                {status === "succeeded" ? "concluído" : status === "failed" ? "falhou" : "em execução"}
              </p>
            )}
          </Card>

          <JobLog logs={logs} />
        </div>
      </div>
    </div>
  );
}
