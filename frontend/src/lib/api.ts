import type {
  Job,
  LogEvent,
  Movie,
  Preview,
  SecretState,
  SettingRule,
  Settings,
  SystemInfo,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api/v1";
const TOKEN_KEY = "dubla.apiToken";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setToken(token: string): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event("dubla:token"));
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { "X-API-Token": token } : {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  for (const [key, value] of Object.entries(authHeaders())) headers.set(key, value);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = typeof data?.detail === "string" ? data.detail : JSON.stringify(data?.detail ?? data);
    } catch {
      /* keep status text */
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function mediaUrl(path: string): string {
  const token = getToken();
  const separator = path.includes("?") ? "&" : "?";
  return `${API_BASE}${path}${token ? `${separator}token=${encodeURIComponent(token)}` : ""}`;
}

export const api = {
  system: () => request<SystemInfo>("/system/info"),
  logs: (date?: string, tail = 200) =>
    request<{ file?: string; lines?: string[]; files?: string[] }>(
      `/system/logs?${date ? `date=${date}&` : ""}tail=${tail}`,
    ),
  previews: () => request<Preview[]>("/system/previews"),

  settings: () => request<Settings>("/settings"),
  schema: () => request<{ settings: Record<string, SettingRule> }>("/settings/schema"),
  patchSettings: (values: Settings) =>
    request<Settings>("/settings", { method: "PATCH", body: JSON.stringify({ values }) }),

  secrets: () => request<SecretState>("/secrets"),
  setSecret: (key: string, value: string) =>
    request<{ key: string; set: boolean }>(`/secrets/${key}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),
  deleteSecret: (key: string) =>
    request<{ key: string; deleted: boolean }>(`/secrets/${key}`, { method: "DELETE" }),

  jobs: (limit = 30, status?: string) =>
    request<Job[]>(`/jobs?limit=${limit}${status ? `&status=${status}` : ""}`),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  jobLogs: (id: string, tail = 500) =>
    request<{ id: string; status: string; logs: LogEvent[] }>(`/jobs/${id}/logs?tail=${tail}`),
  createJob: (payload: {
    type: "pipeline" | "script" | "models";
    url?: string;
    name?: string;
    params?: Record<string, unknown>;
  }) => request<Job>("/jobs", { method: "POST", body: JSON.stringify(payload) }),
  cancelJob: (id: string) => request<Job>(`/jobs/${id}/cancel`, { method: "POST" }),

  movies: () => request<Movie[]>("/movies"),
  movie: (id: string) => request<Record<string, unknown>>(`/movies/${id}`),
  deleteMovie: (id: string) =>
    request<{ deleted: string }>(`/movies/${id}`, { method: "DELETE" }),
};
