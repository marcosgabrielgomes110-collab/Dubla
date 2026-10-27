import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Save, Settings2 } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/PageHeader";
import { Button, Card, CardHint, CardTitle, Input, Label, Select } from "@/components/ui";
import { getToken, api, setToken } from "@/lib/api";
import type { SettingRule } from "@/lib/types";

const groups: { title: string; hint: string; keys: string[] }[] = [
  {
    title: "Entrada e saída",
    hint: "Qualidade do download e idiomas do pipeline.",
    keys: ["quality_ytdlp", "input_language", "output_language", "output_path"],
  },
  {
    title: "Transcrição",
    hint: "Motor, modelo e limites dos blocos de fala.",
    keys: [
      "stt_engine",
      "stt_whisper_model",
      "stt_whisper_device",
      "stt_whisper_compute",
      "stt_max_segment",
    ],
  },
  {
    title: "Tradução",
    hint: "Motor, backend e comportamento de falha.",
    keys: [
      "translation_engine",
      "deep_translator_backend",
      "translation_batch_size",
      "translation_retries",
      "translation_cleanup_on_error",
    ],
  },
  {
    title: "Voz",
    hint: "Motor de voz, ajuste ao slot e paralelismo.",
    keys: [
      "voice_engine",
      "voice_fit_speedup_max",
      "voice_sample_rate",
      "voice_parallel",
      "voice_workers",
    ],
  },
  {
    title: "Mux e publicação",
    hint: "Codec do vídeo, overlap e comportamento da pasta final.",
    keys: ["mux_video_codec", "mux_overlap", "mux_loudnorm", "publish_overwrite"],
  },
];

function humanize(key: string) {
  return key.replaceAll("_", " ");
}

function Field({
  name,
  rule,
  value,
  onChange,
}: {
  name: string;
  rule: SettingRule;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  if (rule.type === "object") return null;

  return (
    <div>
      <Label>{humanize(name)}</Label>
      {rule.type === "enum" ? (
        <Select value={String(value ?? "")} onChange={(event) => onChange(event.target.value)}>
          {(rule.options ?? []).map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </Select>
      ) : rule.type === "boolean" ? (
        <label className="flex h-9 items-center gap-2 rounded-lg border border-white/[0.07] bg-black/20 px-3 text-xs text-slate-300">
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(event) => onChange(event.target.checked)}
            className="h-3.5 w-3.5 accent-emerald-400"
          />
          {Boolean(value) ? "ativado" : "desativado"}
        </label>
      ) : rule.type === "integer" || rule.type === "number" ? (
        <Input
          type="number"
          min={rule.min}
          max={rule.max}
          step={rule.type === "integer" ? 1 : 0.05}
          value={String(value ?? 0)}
          onChange={(event) => onChange(Number(event.target.value))}
        />
      ) : (
        <Input value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} />
      )}
    </div>
  );
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const schema = useQuery({ queryKey: ["settings", "schema"], queryFn: api.schema });

  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [token, setTokenDraft] = useState(getToken());

  useEffect(() => {
    if (settings.data) setDraft({ ...settings.data });
  }, [settings.data]);

  const changes = useMemo(() => {
    if (!settings.data) return {};
    const diff: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(draft)) {
      if (JSON.stringify(value) !== JSON.stringify(settings.data[key])) diff[key] = value;
    }
    return diff;
  }, [draft, settings.data]);

  const save = useMutation({
    mutationFn: () => api.patchSettings(changes),
    onSuccess: () => {
      toast.success("Configurações salvas");
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <div>
      <PageHeader
        eyebrow="configuration"
        title="Configurações"
        description="Ajustes aplicados ao próximo job. Os valores atuais vêm do configs.json."
        actions={
          <Button onClick={() => save.mutate()} disabled={!Object.keys(changes).length || save.isPending}>
            <Save className="h-4 w-4" />
            Salvar alterações
          </Button>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        {groups.map((group) => (
          <Card key={group.title}>
            <div className="flex items-center gap-2">
              <Settings2 className="h-4 w-4 text-slate-400" />
              <CardTitle>{group.title}</CardTitle>
            </div>
            <CardHint>{group.hint}</CardHint>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {group.keys.map((key) => {
                const rule = schema.data?.settings?.[key];
                if (!rule) return null;
                return (
                  <Field
                    key={key}
                    name={key}
                    rule={rule}
                    value={draft[key]}
                    onChange={(value) => setDraft((current) => ({ ...current, [key]: value }))}
                  />
                );
              })}
            </div>
          </Card>
        ))}
      </div>

      <Card>
        <div className="flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-amber-300" />
          <CardTitle>Token da API</CardTitle>
        </div>
        <CardHint>
          Necessário apenas se o servidor estiver com <code className="text-slate-300">DUBLA_API_TOKEN</code>.
          Fica salvo só neste navegador (localStorage).
        </CardHint>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <Input
            type="password"
            value={token}
            onChange={(event) => setTokenDraft(event.target.value)}
            placeholder="X-API-Token"
            autoComplete="off"
          />
          <Button
            variant="outline"
            onClick={() => {
              setToken(token.trim());
              toast.success(token.trim() ? "Token salvo" : "Token removido");
            }}
          >
            Salvar token
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              setToken("");
              setTokenDraft("");
              toast.message("Token removido");
            }}
          >
            Limpar
          </Button>
        </div>
      </Card>

      {Object.keys(changes).length > 0 && (
        <p className="mt-4 text-xs text-amber-300/80">
          {Object.keys(changes).length} alteração(ões) pendente(s) — clique em “Salvar alterações”.
        </p>
      )}
    </div>
  );
}
