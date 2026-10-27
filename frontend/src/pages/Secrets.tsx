import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/PageHeader";
import { Badge, Button, Card, CardHint, CardTitle, Input } from "@/components/ui";
import { api } from "@/lib/api";

const descriptions: Record<string, string> = {
  LLM_PROVIDER: "openai, deepseek, groq, openrouter, ollama…",
  LLM_MODEL: "model id do provider",
  LLM_API_KEY: "chave do endpoint OpenAI-compatible",
  LLM_BASE_URL: "opcional; sobrescreve o preset do provider",
  ELEVENLABS_API_KEY: "chave da conta ElevenLabs",
  ELEVENLABS_MODEL: "eleven_multilingual_v2, eleven_v3…",
  ELEVENLABS_VOICE_ID_PT: "voice id para português",
  ELEVENLABS_VOICE_ID_EN: "voice id para inglês",
};

export default function Secrets() {
  const queryClient = useQueryClient();
  const secrets = useQuery({ queryKey: ["secrets"], queryFn: api.secrets });
  const [values, setValues] = useState<Record<string, string>>({});

  const save = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) => api.setSecret(key, value),
    onSuccess: (_, variables) => {
      toast.success(`${variables.key} salvo`);
      setValues((current) => ({ ...current, [variables.key]: "" }));
      void queryClient.invalidateQueries({ queryKey: ["secrets"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: (key: string) => api.deleteSecret(key),
    onSuccess: () => {
      toast.message("Chave removida");
      void queryClient.invalidateQueries({ queryKey: ["secrets"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <div>
      <PageHeader
        eyebrow="credentials"
        title="Chaves e segredos"
        description="Gravadas no .env local (chmod 600). O valor completo nunca é devolvido pela API."
      />

      <Card>
        <div className="flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-amber-300" />
          <CardTitle>Variáveis do .env</CardTitle>
        </div>
        <CardHint>
          LLM para tradução via OpenAI-compatible e ElevenLabs para a voz na nuvem.
        </CardHint>

        <div className="mt-5 space-y-4">
          {Object.entries(secrets.data ?? {}).map(([key, state]) => (
            <div key={key} className="rounded-lg border border-white/[0.06] bg-black/20 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-slate-200">{key}</span>
                <Badge tone={state.set ? "emerald" : "zinc"}>
                  {state.set ? state.preview : "não configurado"}
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-auto text-slate-400 hover:text-rose-300"
                  onClick={() => {
                    if (window.confirm(`Remover ${key}?`)) remove.mutate(key);
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" /> remover
                </Button>
              </div>
              <p className="mt-1 text-[11px] text-slate-500">{descriptions[key] ?? ""}</p>

              <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                <Input
                  type="password"
                  autoComplete="off"
                  placeholder={`novo valor para ${key}`}
                  value={values[key] ?? ""}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, [key]: event.target.value }))
                  }
                />
                <Button
                  variant="outline"
                  disabled={!values[key]?.trim() || save.isPending}
                  onClick={() => save.mutate({ key, value: values[key].trim() })}
                >
                  <Save className="h-3.5 w-3.5" /> salvar
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <p className="mt-4 text-[11px] text-slate-500">
        Depois de gravar, rode <code className="text-slate-300">python Scripts/Setup_ElevenLabs.py --ping</code>{" "}
        ou <code className="text-slate-300">--list-voices</code> para validar a chave.
      </p>
    </div>
  );
}
