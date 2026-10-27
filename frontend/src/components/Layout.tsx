import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  AudioLines,
  CircleDot,
  Film,
  KeyRound,
  LayoutDashboard,
  Radio,
  Settings2,
  Sparkles,
} from "lucide-react";

import { getToken } from "@/lib/api";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Visão geral", icon: LayoutDashboard, end: true },
  { to: "/pipeline", label: "Pipeline", icon: Radio },
  { to: "/movies", label: "Filmes", icon: Film },
  { to: "/models", label: "Vozes & modelos", icon: AudioLines },
  { to: "/settings", label: "Configurações", icon: Settings2 },
  { to: "/secrets", label: "Chaves", icon: KeyRound },
];

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <img src="/logo.svg" alt="Dubla" className="h-10 w-10 rounded-xl" />
      <div>
        <p className="text-sm font-semibold tracking-[0.22em] text-white">DUBLA</p>
        <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">dubbing studio</p>
      </div>
    </div>
  );
}

function TokenState() {
  const [token, setTokenState] = useState(getToken());
  useEffect(() => {
    const update = () => setTokenState(getToken());
    window.addEventListener("dubla:token", update);
    window.addEventListener("storage", update);
    return () => {
      window.removeEventListener("dubla:token", update);
      window.removeEventListener("storage", update);
    };
  }, []);

  return (
    <div className="flex items-center gap-2 rounded-lg border border-white/[0.07] bg-black/20 px-3 py-2">
      <CircleDot className={cn("h-3.5 w-3.5", token ? "text-emerald-400" : "text-slate-500")} />
      <div className="leading-tight">
        <p className="text-[11px] font-medium text-slate-300">{token ? "token ativo" : "sem token"}</p>
        <p className="text-[10px] text-slate-500">API local</p>
      </div>
    </div>
  );
}

export function Layout() {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      <aside className="hidden border-r border-white/[0.07] bg-black/25 px-4 py-6 lg:flex lg:flex-col">
        <Brand />
        <nav className="mt-8 space-y-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-emerald-400/10 text-emerald-200"
                    : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-100",
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto space-y-3">
          <TokenState />
          <a
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-slate-500 transition-colors hover:bg-white/[0.04] hover:text-slate-300"
          >
            <Sparkles className="h-3.5 w-3.5" />
            OpenAPI /docs
          </a>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-20 border-b border-white/[0.07] bg-[#070b10]/85 px-4 py-3 backdrop-blur lg:hidden">
          <div className="flex items-center justify-between">
            <Brand />
            <TokenState />
          </div>
          <nav className="mt-3 flex gap-1 overflow-x-auto pb-1">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-xs",
                    isActive ? "bg-emerald-400/10 text-emerald-200" : "text-slate-400",
                  )
                }
              >
                <item.icon className="h-3.5 w-3.5" />
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:py-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
