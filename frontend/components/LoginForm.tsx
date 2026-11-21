"use client";

import { useState } from "react";
import { Activity, Eye, EyeOff, HeartPulse, Loader2, LogIn, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { login } from "../lib/api";
import { cn } from "@/lib/utils";

// Split-screen login: a calm clinical illustration on the left, a focused login
// form on the right. Theme-aware (light/dark) via design tokens.
export default function LoginForm({ onSuccess }: { onSuccess: (role: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setErr("");
    setBusy(true);
    try {
      const r = await login(username.trim(), password, remember);
      onSuccess(r?.role || "");
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  function fillUser(u: string) {
    setUsername(u);
    setErr("");
  }

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
      {/* ---- Left: medical illustration panel ---- */}
      <div className="relative hidden overflow-hidden lg:block">
        <div className="absolute inset-0 bg-gradient-to-br from-teal-700 via-teal-800 to-slate-900" />
        {/* subtle grid */}
        <div
          className="absolute inset-0 opacity-[0.12]"
          style={{
            backgroundImage:
              "linear-gradient(to right, white 1px, transparent 1px), linear-gradient(to bottom, white 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
          aria-hidden="true"
        />
        <div className="relative z-10 flex h-full flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-lg bg-white/15 backdrop-blur">
              <Activity className="h-6 w-6" aria-hidden="true" />
            </span>
            <span className="text-lg font-semibold tracking-tight">KapselRPLD</span>
          </div>

          {/* ECG / pulse illustration */}
          <div className="mx-auto w-full max-w-md">
            <svg viewBox="0 0 400 160" className="w-full" role="img" aria-label="Ilustrasi denyut jantung (ECG)">
              <defs>
                <linearGradient id="ecg" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#5eead4" stopOpacity="0" />
                  <stop offset="15%" stopColor="#5eead4" stopOpacity="1" />
                  <stop offset="85%" stopColor="#5eead4" stopOpacity="1" />
                  <stop offset="100%" stopColor="#5eead4" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path
                d="M0 90 H80 L100 90 L112 40 L128 130 L146 70 L160 90 H240 L252 90 L264 55 L280 120 L296 78 L308 90 H400"
                fill="none"
                stroke="url(#ecg)"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <circle cx="112" cy="40" r="4" fill="#5eead4" />
            </svg>
          </div>

          <div>
            <h2 className="text-3xl font-semibold leading-tight">
              Console Interoperabilitas FHIR
            </h2>
            <p className="mt-3 max-w-md text-sm text-teal-100/90">
              Menghubungkan OpenMRS, OpenEMR, dan SATUSEHAT melalui HL7 FHIR R4.
              Pantau sinkronisasi, konflik, dan kepatuhan dalam satu tempat.
            </p>
            <div className="mt-6 flex flex-wrap gap-4 text-xs text-teal-100/80">
              <span className="inline-flex items-center gap-1.5">
                <HeartPulse className="h-4 w-4" aria-hidden="true" /> Patient · Encounter · Observation
              </span>
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" /> RBAC · Audit · Observability
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ---- Right: login form ---- */}
      <div className="flex items-center justify-center bg-background px-4 py-10 sm:px-8">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="grid h-11 w-11 place-items-center rounded-lg bg-primary text-primary-foreground">
              <Activity className="h-6 w-6" aria-hidden="true" />
            </span>
            <span className="text-lg font-semibold tracking-tight">KapselRPLD</span>
          </div>

          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Masuk ke Console</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Gunakan akun Anda untuk mengakses dashboard interoperabilitas.
          </p>

          <form onSubmit={submit} className="mt-7 space-y-4" noValidate>
            <div className="space-y-1.5">
              <label htmlFor="username" className="text-sm font-medium text-foreground">
                Username
              </label>
              <Input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="mis. admin"
                className="min-h-[44px]"
                aria-invalid={!!err}
                required
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="password" className="text-sm font-medium text-foreground">
                Password
              </label>
              <div className="relative">
                <Input
                  id="password"
                  name="password"
                  type={showPw ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="min-h-[44px] pr-11"
                  aria-invalid={!!err}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPw((v) => !v)}
                  className="absolute right-1 top-1/2 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-md text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={showPw ? "Sembunyikan password" : "Tampilkan password"}
                  aria-pressed={showPw}
                >
                  {showPw ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                </button>
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="h-4 w-4 rounded border-input text-primary focus-visible:ring-2 focus-visible:ring-ring"
              />
              Ingat saya selama 7 hari
            </label>

            {err && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
              >
                <span className="mt-0.5">⚠</span>
                <span>{err}</span>
              </div>
            )}

            <Button type="submit" disabled={busy} className="min-h-[44px] w-full">
              {busy ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <LogIn className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              {busy ? "Memproses..." : "Masuk"}
            </Button>
          </form>

          <div className="mt-6 rounded-lg border border-border bg-muted/40 p-3">
            <p className="text-xs font-medium text-foreground">Akun demo</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {["admin", "operator", "viewer"].map((u) => (
                <button
                  key={u}
                  type="button"
                  onClick={() => fillUser(u)}
                  className={cn(
                    "rounded-md border border-border bg-card px-2.5 py-1 text-xs font-medium text-foreground",
                    "hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  )}
                >
                  {u}
                </button>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-muted-foreground">
              Klik untuk isi username. Password demo diatur di <code className="font-mono">.env</code>.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
