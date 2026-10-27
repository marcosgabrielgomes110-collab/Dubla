export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface Job {
  id: string;
  type: "pipeline" | "script" | "models";
  params: Record<string, unknown>;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  return_code: number | null;
  result: string | null;
  error: string | null;
  log_lines: number;
}

export interface LogEvent {
  ts: string;
  level: string;
  source: string;
  message: string;
}

export interface SettingRule {
  type: "string" | "enum" | "boolean" | "integer" | "number" | "object";
  options?: string[];
  min?: number;
  max?: number;
  description?: string;
}

export interface SystemInfo {
  python: string;
  hostname: string;
  root: string;
  binaries: Record<string, string | null>;
  packages: Record<string, boolean>;
  disk: { total: number; used: number; free: number };
  memory: { total: number; available: number };
}

export interface Movie {
  id: string;
  title: string | null;
  language: string | null;
  duration: number | null;
  size: number;
  video: string;
  created_at: string | null;
}

export interface Preview {
  name: string;
  size: number;
}

export interface SecretState {
  [key: string]: { set: boolean; preview: string };
}

export type Settings = Record<string, unknown>;
