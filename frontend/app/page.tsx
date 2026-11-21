"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CopyX,
  GitCompareArrows,
  Inbox,
  Link2,
  ListChecks,
  Loader2,
  PlugZap,
  RefreshCw,
  Search,
  Server,
  Timer,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { API_BASE, apiGet, apiPost } from "../lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/* Reading this as: an operations console for interoperability engineers monitoring
   OpenMRS / OpenEMR / SATUSEHAT syncs, in a calm clinical-instrument style, dial
   ENERGY 1 / RHYTHM 2 / MOTION 1. The question the screen answers first is
   "what is healthy and what needs my attention right now?" */

type Tone = "success" | "review" | "warning" | "destructive" | "info" | "secondary";

const STATUS_LABEL: Record<string, string> = {
  success: "Sukses",
  needs_review: "Perlu review",
  failed_temp: "Gagal sementara",
  failed_perm: "Gagal permanen",
  conflict: "Konflik",
  pending: "Menunggu",
  processing: "Diproses",
};

const STATUS_TONE: Record<string, Tone> = {
  success: "success",
  needs_review: "review",
  failed_temp: "warning",
  failed_perm: "destructive",
  conflict: "destructive",
  pending: "secondary",
  processing: "info",
};

// Hex values for chart fills only (Recharts needs concrete colors).
const STATUS_HEX: Record<string, string> = {
  success: "#047857",
  needs_review: "#6d28d9",
  failed_temp: "#b45309",
  failed_perm: "#b91c1c",
  conflict: "#b91c1c",
  pending: "#64748b",
  processing: "#0369a1",
};

const ACTIONABLE = ["needs_review", "failed_temp", "failed_perm"];

// Rows per page for the long lists (jobs, conflicts, mappings).
const PAGE_SIZE = 10;

function toneOf(status: string): Tone {
  return STATUS_TONE[status] ?? "secondary";
}

function labelOf(status: string): string {
  return STATUS_LABEL[status] ?? status;
}

function fmtTime(iso?: string | null): string {
  if (!iso) return "n/a";
  const d = new Date(iso);
  if (Number.isNaN(+d)) return "n/a";
  return d.toLocaleString("id-ID", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function unwrap<T>(payload: any): T[] {
  if (Array.isArray(payload)) return payload as T[];
  if (payload && Array.isArray(payload.value)) return payload.value as T[];
  return [];
}

export default function Home() {
  const [token, setToken] = useState("change_me_admin_token");
  const [tab, setTab] = useState("overview");
  const [metrics, setMetrics] = useState<any>(null);
  const [systems, setSystems] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [conflicts, setConflicts] = useState<any[]>([]);
  const [mappings, setMappings] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [err, setErr] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  const [jobFilter, setJobFilter] = useState<string>("all");
  const [mapQuery, setMapQuery] = useState<string>("");
  const [mapType, setMapType] = useState<string>("all");
  const [jobPage, setJobPage] = useState<number>(1);
  const [mapPage, setMapPage] = useState<number>(1);
  const [conflictPage, setConflictPage] = useState<number>(1);

  const [checkState, setCheckState] = useState<
    Record<string, { status: "idle" | "loading" | "ok" | "fail"; msg?: string }>
  >({});
  const [busyJob, setBusyJob] = useState<string>("");
  const [busyConflict, setBusyConflict] = useState<string>("");

  const [inbound, setInbound] = useState<any>(null);
  const [inboundBusy, setInboundBusy] = useState(false);
  const [ssrme, setSsrme] = useState<any>(null);
  const [ssrmeBusy, setSsrmeBusy] = useState(false);

  const loadAll = useCallback(async () => {
    setErr("");
    setLoading(true);
    try {
      const [m, s, j, c, mp, tl] = await Promise.all([
        apiGet("/api/v1/metrics", token),
        apiGet("/api/v1/systems", token),
        apiGet("/api/v1/jobs?limit=500", token),
        apiGet("/api/v1/conflicts", token),
        apiGet("/api/v1/mappings", token),
        apiGet("/api/v1/metrics/timeline", token).catch(() => null),
      ]);
      setMetrics(m);
      setSystems(unwrap(s));
      setJobs(unwrap(j));
      setConflicts(unwrap(c));
      setMappings(unwrap(mp));
      setTimeline(unwrap(tl));
      setLastUpdated(
        new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      );
    } catch (e: any) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  async function checkConn(name: string) {
    setCheckState((prev) => ({ ...prev, [name]: { status: "loading" } }));
    try {
      const r = await apiPost(`/api/v1/systems/${name}/check`, token);
      setCheckState((prev) => ({
        ...prev,
        [name]: {
          status: r?.ok ? "ok" : "fail",
          msg: r?.ok ? `HTTP ${r?.http_status ?? 200}` : r?.error || "Tidak terhubung",
        },
      }));
    } catch (e: any) {
      setCheckState((prev) => ({ ...prev, [name]: { status: "fail", msg: String(e.message || e) } }));
    }
  }

  async function retryJob(id: string) {
    setBusyJob(id);
    try {
      await apiPost(`/api/v1/jobs/${id}/retry`, token);
      await loadAll();
    } catch (e: any) {
      setErr(String(e.message || e));
    } finally {
      setBusyJob("");
    }
  }

  async function resolveConflict(id: string) {
    setBusyConflict(id);
    try {
      await apiPost(`/api/v1/conflicts/${id}/resolve`, token, { note: "Ditandai selesai dari console" });
      await loadAll();
    } catch (e: any) {
      setErr(String(e.message || e));
    } finally {
      setBusyConflict("");
    }
  }

  async function runInbound() {
    setInboundBusy(true);
    setInbound(null);
    try {
      const r = await apiGet(
        "/api/v1/satusehat/inbound/Patient?identifier=https://fhir.kemkes.go.id/id/ihs-number%7C100000030009",
        token
      );
      setInbound(r);
    } catch (e: any) {
      setInbound({ ok: false, error: String(e.message || e) });
    } finally {
      setInboundBusy(false);
    }
  }

  async function runSsrme(kind: "chlink" | "shlink") {
    setSsrmeBusy(true);
    setSsrme(null);
    try {
      const r = await apiPost(`/api/v1/ssrme/${kind}`, token, {
        patient_id: "100000030009",
        patient_name: "Budi Santoso",
        practitioner_id: "10009880010",
        practitioner_name: "dr. Contoh",
        organization_id: process.env.NEXT_PUBLIC_SATUSEHAT_ORG_ID || "",
        organization_name: "STAGING",
        emergency: kind === "shlink",
      });
      setSsrme(r);
    } catch (e: any) {
      setSsrme({ ok: false, error: String(e.message || e) });
    } finally {
      setSsrmeBusy(false);
    }
  }

  const statusData = useMemo(() => {
    const bs = metrics?.by_status || {};
    return Object.entries(bs).map(([k, v]) => ({
      key: k,
      label: labelOf(k),
      value: v as number,
      color: STATUS_HEX[k] || "#64748b",
      tone: toneOf(k),
    }));
  }, [metrics]);

  const statusTotal = useMemo(
    () => statusData.reduce((a, b) => a + b.value, 0),
    [statusData]
  );

  const resourceData = useMemo(() => {
    const acc: Record<string, number> = {};
    jobs.forEach((j) => {
      acc[j.resource_type] = (acc[j.resource_type] || 0) + 1;
    });
    return Object.entries(acc)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [jobs]);

  const timelineData = useMemo(
    () =>
      timeline.map((t: any) => ({
        label: t.hour
          ? new Date(t.hour).toLocaleString("id-ID", {
              day: "2-digit",
              month: "short",
              hour: "2-digit",
            })
          : "n/a",
        count: t.count as number,
      })),
    [timeline]
  );

  const attentionJobs = useMemo(
    () => jobs.filter((j) => ACTIONABLE.includes(j.status)).slice(0, 4),
    [jobs]
  );

  const filteredJobs = useMemo(
    () => (jobFilter === "all" ? jobs : jobs.filter((j) => j.status === jobFilter)),
    [jobs, jobFilter]
  );

  const jobStatuses = useMemo(() => {
    const set = new Set<string>();
    jobs.forEach((j) => set.add(j.status));
    return Array.from(set);
  }, [jobs]);

  const mappingTypes = useMemo(() => {
    const set = new Set<string>();
    mappings.forEach((m) => set.add(m.identifier_type));
    return Array.from(set);
  }, [mappings]);

  const filteredMappings = useMemo(() => {
    const q = mapQuery.trim().toLowerCase();
    return mappings.filter((m) => {
      const typeOk = mapType === "all" || m.identifier_type === mapType;
      const qOk =
        !q ||
        String(m.source_identifier || "").toLowerCase().includes(q) ||
        String(m.target_identifier || "").toLowerCase().includes(q);
      return typeOk && qOk;
    });
  }, [mappings, mapQuery, mapType]);

  // --- Pagination slices (client-side) ---
  const jobTotalPages = Math.max(1, Math.ceil(filteredJobs.length / PAGE_SIZE));
  const pagedJobs = useMemo(
    () => filteredJobs.slice((jobPage - 1) * PAGE_SIZE, jobPage * PAGE_SIZE),
    [filteredJobs, jobPage]
  );
  const mapTotalPages = Math.max(1, Math.ceil(filteredMappings.length / PAGE_SIZE));
  const pagedMappings = useMemo(
    () => filteredMappings.slice((mapPage - 1) * PAGE_SIZE, mapPage * PAGE_SIZE),
    [filteredMappings, mapPage]
  );
  const conflictTotalPages = Math.max(1, Math.ceil(conflicts.length / PAGE_SIZE));
  const pagedConflicts = useMemo(
    () => conflicts.slice((conflictPage - 1) * PAGE_SIZE, conflictPage * PAGE_SIZE),
    [conflicts, conflictPage]
  );

  // Reset to page 1 whenever a filter/search changes or the data set shrinks.
  useEffect(() => setJobPage(1), [jobFilter, jobs.length]);
  useEffect(() => setMapPage(1), [mapQuery, mapType, mappings.length]);
  useEffect(() => {
    if (conflictPage > conflictTotalPages) setConflictPage(conflictTotalPages);
  }, [conflictPage, conflictTotalPages]);

  const successCount = metrics?.by_status?.success ?? 0;
  const totalJobs = metrics?.total_jobs ?? 0;
  const successRate = metrics?.success_rate_percent ?? 0;
  const avgLatency = metrics?.avg_latency_seconds;

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Lewati ke konten
      </a>

      {/* Header / landmark banner */}
      <header className="sticky top-0 z-20 border-b border-border bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <span
              className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground"
              aria-hidden="true"
            >
              <Activity className="h-6 w-6" />
            </span>
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold tracking-tight">
                Console Interoperabilitas FHIR
              </h1>
              <p className="text-xs text-muted-foreground">
                OpenMRS, OpenEMR, dan SATUSEHAT · HL7 FHIR R4
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <label className="flex flex-col gap-1">
              <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Token admin
              </span>
              <Input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                className="min-h-[44px] w-full font-mono text-xs sm:min-h-9 sm:w-60"
                placeholder="Bearer token"
                autoComplete="off"
                spellCheck={false}
                aria-label="Token admin untuk Management API"
              />
            </label>
            <Button
              onClick={loadAll}
              disabled={loading}
              className="min-h-[44px] sm:min-h-9"
            >
              <RefreshCw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} aria-hidden="true" />
              Muat ulang
            </Button>
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6">
        {/* Error state for the data fetch */}
        {err && (
          <div
            role="alert"
            className="mb-5 flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-medium">Gagal memuat data dari Management API</p>
              <p className="mt-0.5 text-destructive/90">{err}</p>
            </div>
          </div>
        )}

        {/* KPI row */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            label="Total pekerjaan"
            value={loading && !metrics ? <Skel w="w-16" /> : totalJobs}
            sub="Seluruh job sinkronisasi tercatat"
            icon={ListChecks}
          />
          <Kpi
            label="Tingkat sukses"
            value={loading && !metrics ? <Skel w="w-20" /> : `${successRate}%`}
            sub={
              loading && !metrics
                ? "Menghitung"
                : `${successCount} sukses dari ${totalJobs} job`
            }
            icon={CheckCircle2}
            bar={typeof successRate === "number" ? successRate : undefined}
          />
          <Kpi
            label="Latensi rata-rata"
            value={
              loading && !metrics ? (
                <Skel w="w-16" />
              ) : avgLatency === null || avgLatency === undefined ? (
                "n/a"
              ) : (
                `${avgLatency}s`
              )
            }
            sub="Waktu proses job yang sukses"
            icon={Timer}
          />
          <Kpi
            label="Duplikat dilewati"
            value={loading && !metrics ? <Skel w="w-12" /> : metrics?.duplicate_skips ?? 0}
            sub="Idempotensi mencegah tulis ganda"
            icon={CopyX}
          />
        </div>

        {/* Tabs */}
        <Tabs value={tab} onValueChange={setTab} className="mt-6">
          <div className="-mx-1 overflow-x-auto px-1">
            <TabsList className="h-auto w-full flex-wrap justify-start gap-1 bg-muted/70 p-1">
              <TabsTrigger value="overview" className="min-h-[40px] flex-1 sm:flex-none">
                Ringkasan
              </TabsTrigger>
              <TabsTrigger value="connections" className="min-h-[40px] flex-1 sm:flex-none">
                Konektivitas
              </TabsTrigger>
              <TabsTrigger value="jobs" className="min-h-[40px] flex-1 sm:flex-none">
                Pekerjaan
              </TabsTrigger>
              <TabsTrigger value="conflicts" className="min-h-[40px] flex-1 sm:flex-none">
                Konflik
              </TabsTrigger>
              <TabsTrigger value="mappings" className="min-h-[40px] flex-1 sm:flex-none">
                Pemetaan
              </TabsTrigger>
              <TabsTrigger value="integrations" className="min-h-[40px] flex-1 sm:flex-none">
                Integrasi
              </TabsTrigger>
            </TabsList>
          </div>

          {/* OVERVIEW */}
          <TabsContent value="overview" className="mt-5 space-y-4">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
              <Panel
                className="lg:col-span-3"
                title="Kesehatan antrean"
                desc="Proporsi job per status saat ini"
              >
                {loading && !metrics ? (
                  <Skel block />
                ) : statusData.length === 0 ? (
                  <EmptyState
                    icon={Inbox}
                    title="Belum ada job"
                    hint="Antrean kosong. Job akan muncul setelah sinkronisasi berjalan."
                  />
                ) : (
                  <div>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>Total {statusTotal} job</span>
                      <span className="font-medium text-foreground">{successRate}% sukses</span>
                    </div>
                    <div
                      className="mt-2 flex h-3 w-full overflow-hidden rounded-full bg-muted"
                      role="img"
                      aria-label={`Distribusi status: ${statusData
                        .map((d) => `${d.value} ${d.label}`)
                        .join(", ")}`}
                    >
                      {statusData.map((d) => (
                        <span
                          key={d.key}
                          style={{
                            width: `${(d.value / (statusTotal || 1)) * 100}%`,
                            backgroundColor: d.color,
                          }}
                          title={`${d.label}: ${d.value}`}
                        />
                      ))}
                    </div>
                    <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                      {statusData.map((d) => (
                        <li key={d.key} className="rounded-lg border border-border bg-card p-3">
                          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <span
                              className="h-2.5 w-2.5 shrink-0 rounded-full"
                              style={{ backgroundColor: d.color }}
                              aria-hidden="true"
                            />
                            {d.label}
                          </span>
                          <span className="mt-1 block font-mono-num text-2xl font-semibold text-foreground">
                            {d.value}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {Math.round((d.value / (statusTotal || 1)) * 100)}% dari total
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </Panel>

              <Panel
                className="lg:col-span-2"
                title="Beban per resource"
                desc="Jumlah job menurut tipe resource FHIR"
              >
                {loading && !metrics ? (
                  <Skel block />
                ) : resourceData.length === 0 ? (
                  <EmptyState icon={Inbox} title="Belum ada resource" hint="Belum ada job yang tercatat." />
                ) : (
                  <div className="h-[220px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={resourceData}
                        layout="vertical"
                        margin={{ top: 4, right: 12, left: 4, bottom: 0 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e9ef" />
                        <XAxis type="number" allowDecimals={false} fontSize={11} tickLine={false} axisLine={false} />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={78}
                          fontSize={12}
                          tickLine={false}
                          axisLine={false}
                        />
                        <Tooltip
                          cursor={{ fill: "rgba(37,126,123,0.06)" }}
                          contentStyle={tooltipStyle}
                        />
                        <Bar dataKey="value" fill="#257e7b" radius={[0, 4, 4, 0]} barSize={18} isAnimationActive={false} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </Panel>
            </div>

            <Panel
              title="Tren pembuatan job"
              desc="Jumlah job yang dibuat per jam"
            >
              {loading && !metrics ? (
                <Skel block />
              ) : timelineData.length === 0 ? (
                <EmptyState
                  icon={Inbox}
                  title="Belum ada data tren"
                  hint="Data tren muncul setelah ada job pada satu jam penuh."
                />
              ) : (
                <div className="h-[220px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={timelineData} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e9ef" />
                      <XAxis dataKey="label" fontSize={11} tickLine={false} axisLine={false} />
                      <YAxis fontSize={11} allowDecimals={false} tickLine={false} axisLine={false} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Line
                        type="monotone"
                        dataKey="count"
                        stroke="#257e7b"
                        strokeWidth={2}
                        dot={{ r: 3, fill: "#257e7b" }}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Panel>

            <Panel
              title="Perlu perhatian"
              desc="Job yang butuh tindakan: review, gagal sementara, gagal permanen"
              action={
                <Button
                  variant="outline"
                  size="sm"
                  className="min-h-[40px] sm:min-h-8"
                  onClick={() => setTab("jobs")}
                >
                  Lihat semua pekerjaan
                </Button>
              }
            >
              {loading && !metrics ? (
                <Skel block />
              ) : attentionJobs.length === 0 ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-4 w-4 text-[#047857]" aria-hidden="true" />
                  Tidak ada job yang butuh tindakan saat ini.
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {attentionJobs.map((j) => (
                    <li key={j.id} className="flex flex-wrap items-center gap-3 py-2.5 first:pt-0 last:pb-0">
                      <Badge variant={toneOf(j.status)}>{labelOf(j.status)}</Badge>
                      <span className="font-medium">{j.resource_type}</span>
                      <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground">
                        {j.last_error || "Tanpa pesan error"}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        className="min-h-[40px] sm:min-h-8"
                        onClick={() => retryJob(j.id)}
                        disabled={busyJob === j.id}
                        aria-label={`Retry job ${j.resource_type} ${j.source_resource_id}`}
                      >
                        {busyJob === j.id ? (
                          <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                        ) : (
                          <RefreshCw className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                        )}
                        Retry
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </TabsContent>

          {/* CONNECTIONS */}
          <TabsContent value="connections" className="mt-5">
            <Panel
              title="Status konektivitas"
              desc="Uji ketersediaan tiap sistem terintegrasi lewat adapter-nya"
            >
              {loading && systems.length === 0 ? (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <Skel block />
                  <Skel block />
                  <Skel block />
                </div>
              ) : systems.length === 0 ? (
                <EmptyState icon={Server} title="Belum ada sistem" hint="Daftarkan sistem eksternal terlebih dahulu." />
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {systems.map((s) => {
                    const st = checkState[s.name] || { status: "idle" as const };
                    return (
                      <div key={s.id} className="rounded-lg border border-border bg-card p-4">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <Server className="h-4 w-4 text-primary" aria-hidden="true" />
                            <span className="font-medium capitalize">{s.name}</span>
                          </div>
                          <Badge variant="outline">{s.system_type}</Badge>
                        </div>
                        <p className="mt-2 truncate font-mono text-xs text-muted-foreground" title={s.fhir_base_url}>
                          {s.fhir_base_url}
                        </p>
                        <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                          <span
                            className={cn(
                              "h-1.5 w-1.5 rounded-full",
                              s.enabled ? "bg-[#047857]" : "bg-muted-foreground"
                            )}
                            aria-hidden="true"
                          />
                          {s.enabled ? "Aktif" : "Nonaktif"} · {s.auth_type}
                        </div>
                        <div className="mt-3 flex items-center justify-between gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            className="min-h-[40px] sm:min-h-8"
                            onClick={() => checkConn(s.name)}
                            disabled={st.status === "loading"}
                          >
                            {st.status === "loading" ? (
                              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                            ) : (
                              <PlugZap className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                            )}
                            Cek konektivitas
                          </Button>
                          {st.status === "ok" && (
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-[#047857]">
                              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                              {st.msg}
                            </span>
                          )}
                          {st.status === "fail" && (
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-destructive">
                              <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
                              {st.msg}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Panel>
          </TabsContent>

          {/* JOBS */}
          <TabsContent value="jobs" className="mt-5">
            <Panel
              title="Riwayat pekerjaan sinkronisasi"
              desc={`${filteredJobs.length} dari ${jobs.length} job`}
              action={
                <div className="flex flex-wrap gap-1.5">
                  <FilterChip active={jobFilter === "all"} onClick={() => setJobFilter("all")}>
                    Semua
                  </FilterChip>
                  {jobStatuses.map((s) => (
                    <FilterChip key={s} active={jobFilter === s} onClick={() => setJobFilter(s)}>
                      {labelOf(s)}
                    </FilterChip>
                  ))}
                </div>
              }
            >
              <div className="overflow-x-auto">
                <Table>
                  <caption className="sr-only">
                    Daftar job sinkronisasi beserta status, jumlah percobaan, sumber, dan aksi retry
                  </caption>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Waktu</TableHead>
                      <TableHead>Resource</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Percobaan</TableHead>
                      <TableHead>ID sumber</TableHead>
                      <TableHead>Error terakhir</TableHead>
                      <TableHead className="text-right">Aksi</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loading && jobs.length === 0 ? (
                      <SkeletonRows cols={7} rows={6} />
                    ) : filteredJobs.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={7}>
                          <EmptyState
                            icon={Inbox}
                            title="Tidak ada job pada filter ini"
                            hint="Ubah filter status untuk melihat job lain."
                          />
                        </TableCell>
                      </TableRow>
                    ) : (
                      pagedJobs.map((j) => (
                        <TableRow key={j.id}>
                          <TableCell className="whitespace-nowrap font-mono text-xs text-muted-foreground">
                            {fmtTime(j.created_at)}
                          </TableCell>
                          <TableCell className="font-medium">{j.resource_type}</TableCell>
                          <TableCell>
                            <Badge variant={toneOf(j.status)}>{labelOf(j.status)}</Badge>
                          </TableCell>
                          <TableCell className="text-right font-mono-num">{j.attempt_count}</TableCell>
                          <TableCell className="max-w-[200px] truncate font-mono text-xs text-muted-foreground" title={j.source_resource_id}>
                            {j.source_resource_id}
                          </TableCell>
                          <TableCell className="max-w-[320px] truncate text-muted-foreground" title={j.last_error || ""}>
                            {j.last_error || <span className="text-muted-foreground/70">n/a</span>}
                          </TableCell>
                          <TableCell className="text-right">
                            {ACTIONABLE.includes(j.status) ? (
                              <Button
                                variant="outline"
                                size="sm"
                                className="min-h-[40px] sm:min-h-8"
                                onClick={() => retryJob(j.id)}
                                disabled={busyJob === j.id}
                                aria-label={`Retry job ${j.resource_type} ${j.source_resource_id}`}
                              >
                                {busyJob === j.id ? (
                                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                                ) : (
                                  <RefreshCw className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                                )}
                                Retry
                              </Button>
                            ) : (
                              <span className="text-xs text-muted-foreground/70">n/a</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
              <Pagination page={jobPage} totalPages={jobTotalPages} total={filteredJobs.length}
                onPage={setJobPage} label="pekerjaan" />
            </Panel>
          </TabsContent>

          {/* CONFLICTS */}
          <TabsContent value="conflicts" className="mt-5">
            <Panel
              title="Konflik data"
              desc={`${conflicts.length} konflik terdeteksi, perlu peninjauan manual`}
            >
              {loading && conflicts.length === 0 ? (
                <Skel block />
              ) : conflicts.length === 0 ? (
                <EmptyState
                  icon={GitCompareArrows}
                  title="Tidak ada konflik"
                  hint="Tidak ditemukan perbedaan versi yang butuh peninjauan."
                />
              ) : (
                <ul className="space-y-3">
                  {pagedConflicts.map((c) => (
                    <li key={c.id} className="rounded-lg border border-border bg-card p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <GitCompareArrows className="h-4 w-4 text-primary" aria-hidden="true" />
                          <span className="font-medium">{c.resource_type}</span>
                          <Badge variant={c.resolution === "pending" ? "warning" : "success"}>
                            {c.resolution === "pending" ? "Menunggu" : "Selesai"}
                          </Badge>
                        </div>
                        <span className="text-xs text-muted-foreground">{fmtTime(c.detected_at)}</span>
                      </div>
                      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <div className="rounded-md bg-muted/60 px-3 py-2">
                          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Versi sumber</p>
                          <p className="truncate font-mono text-xs" title={c.source_version}>{c.source_version}</p>
                        </div>
                        <div className="rounded-md bg-muted/60 px-3 py-2">
                          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Versi tujuan</p>
                          <p className="truncate font-mono text-xs" title={c.target_version}>{c.target_version}</p>
                        </div>
                      </div>
                      <p className="mt-3 text-sm text-muted-foreground">{c.note}</p>
                      {c.resolution === "pending" && (
                        <div className="mt-3">
                          <Button
                            variant="outline"
                            size="sm"
                            className="min-h-[40px] sm:min-h-8"
                            onClick={() => resolveConflict(c.id)}
                            disabled={busyConflict === c.id}
                          >
                            {busyConflict === c.id ? (
                              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                            ) : (
                              <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                            )}
                            Tandai selesai
                          </Button>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              <Pagination page={conflictPage} totalPages={conflictTotalPages} total={conflicts.length}
                onPage={setConflictPage} label="konflik" />
            </Panel>
          </TabsContent>

          {/* MAPPINGS */}
          <TabsContent value="mappings" className="mt-5">
            <Panel
              title="Pemetaan identitas"
              desc={`${filteredMappings.length} dari ${mappings.length} pemetaan lintas sistem`}
              action={
                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative">
                    <Search
                      className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <Input
                      value={mapQuery}
                      onChange={(e) => setMapQuery(e.target.value)}
                      placeholder="Cari identifier"
                      className="min-h-[40px] w-full pl-8 sm:min-h-8 sm:w-56"
                      aria-label="Cari pemetaan berdasarkan identifier"
                    />
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <FilterChip active={mapType === "all"} onClick={() => setMapType("all")}>
                      Semua tipe
                    </FilterChip>
                    {mappingTypes.map((t) => (
                      <FilterChip key={t} active={mapType === t} onClick={() => setMapType(t)}>
                        {t}
                      </FilterChip>
                    ))}
                  </div>
                </div>
              }
            >
              <div className="overflow-x-auto">
                <Table>
                  <caption className="sr-only">Pemetaan identifier sumber ke target antar sistem</caption>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID sumber</TableHead>
                      <TableHead>ID target</TableHead>
                      <TableHead>Tipe</TableHead>
                      <TableHead>Status validasi</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loading && mappings.length === 0 ? (
                      <SkeletonRows cols={4} rows={6} />
                    ) : filteredMappings.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4}>
                          <EmptyState
                            icon={Link2}
                            title="Tidak ada pemetaan cocok"
                            hint="Ubah kata kunci atau filter tipe identifier."
                          />
                        </TableCell>
                      </TableRow>
                    ) : (
                      pagedMappings.map((m) => (
                        <TableRow key={m.id}>
                          <TableCell className="font-mono text-xs">{m.source_identifier}</TableCell>
                          <TableCell className="font-mono text-xs">{m.target_identifier}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{m.identifier_type}</Badge>
                          </TableCell>
                          <TableCell>
                            <Badge variant={m.validation_status === "verified" ? "success" : "warning"}>
                              {m.validation_status === "verified" ? "Terverifikasi" : m.validation_status}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
              <Pagination page={mapPage} totalPages={mapTotalPages} total={filteredMappings.length}
                onPage={setMapPage} label="pemetaan" />
            </Panel>
          </TabsContent>

          {/* INTEGRATIONS */}
          <TabsContent value="integrations" className="mt-5">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Panel
                title="Inbound SATUSEHAT (selektif)"
                desc="Baca Patient dari SATUSEHAT berdasarkan IHS, hanya baca"
              >
                <Button
                  variant="outline"
                  size="sm"
                  className="min-h-[44px] sm:min-h-9"
                  onClick={runInbound}
                  disabled={inboundBusy}
                >
                  {inboundBusy ? (
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  ) : (
                    <Link2 className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                  )}
                  Ambil Patient 100000030009
                </Button>
                <pre className="mt-3 max-h-64 overflow-auto rounded-md border border-border bg-muted/50 p-3 font-mono text-xs">
{inboundBusy
  ? "Memuat…"
  : inbound
  ? JSON.stringify(inbound, null, 2)
  : "Belum ada permintaan. Tekan tombol untuk membaca Patient."}
                </pre>
              </Panel>

              <Panel
                title="SSRME: CHLink dan SHLink"
                desc="Buat tautan persetujuan pasien dan tautan akses darurat"
              >
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="min-h-[44px] sm:min-h-9"
                    onClick={() => runSsrme("chlink")}
                    disabled={ssrmeBusy}
                  >
                    {ssrmeBusy ? (
                      <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                    ) : (
                      <GitCompareArrows className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                    )}
                    Buat CHLink
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="min-h-[44px] sm:min-h-9"
                    onClick={() => runSsrme("shlink")}
                    disabled={ssrmeBusy}
                  >
                    {ssrmeBusy ? (
                      <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                    ) : (
                      <PlugZap className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                    )}
                    Buat SHLink
                  </Button>
                </div>
                <pre className="mt-3 max-h-64 overflow-auto rounded-md border border-border bg-muted/50 p-3 font-mono text-xs">
{ssrmeBusy
  ? "Memuat…"
  : ssrme
  ? JSON.stringify(ssrme, null, 2)
  : "Belum ada permintaan. Tekan tombol untuk membuat tautan SSRME."}
                </pre>
              </Panel>
            </div>
          </TabsContent>
        </Tabs>
      </main>

      <footer className="mx-auto max-w-[1180px] px-4 pb-8 pt-2 text-xs text-muted-foreground sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
          <span>
            Sumber data: Management API
            {lastUpdated ? ` · diperbarui ${lastUpdated}` : ""}
          </span>
          <a
            href={`${API_BASE}/docs`}
            target="_blank"
            rel="noreferrer"
            className="rounded underline-offset-2 hover:underline"
          >
            Dokumentasi API
          </a>
        </div>
      </footer>
    </div>
  );
}

const tooltipStyle = {
  borderRadius: 8,
  border: "1px solid #dcdfe5",
  fontSize: 12,
  boxShadow: "0 6px 18px rgba(15,23,42,0.08)",
};

/* ---------- small building blocks ---------- */

function Kpi({
  label,
  value,
  sub,
  icon: Icon,
  bar,
}: {
  label: string;
  value: React.ReactNode;
  sub: React.ReactNode;
  icon: any;
  bar?: number;
}) {
  return (
    <div className="panel p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-muted-foreground">{label}</p>
          <p className="mt-1 font-mono-num text-3xl font-semibold tracking-tight text-foreground">
            {value}
          </p>
        </div>
        <span
          className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-accent text-accent-foreground"
          aria-hidden="true"
        >
          <Icon className="h-[18px] w-[18px]" />
        </span>
      </div>
      {typeof bar === "number" && (
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted" aria-hidden="true">
          <div
            className="h-full rounded-full bg-primary"
            style={{ width: `${Math.max(0, Math.min(100, bar))}%` }}
          />
        </div>
      )}
      <p className="mt-2 text-xs text-muted-foreground">{sub}</p>
    </div>
  );
}

function Panel({
  title,
  desc,
  action,
  children,
  className,
}: {
  title: string;
  desc?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("panel", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/70 px-5 py-4">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">{title}</h2>
          {desc && <p className="mt-0.5 text-xs text-muted-foreground">{desc}</p>}
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function EmptyState({ icon: Icon, title, hint }: { icon: any; title: string; hint: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
      <span className="grid h-10 w-10 place-items-center rounded-full bg-muted text-muted-foreground" aria-hidden="true">
        <Icon className="h-5 w-5" />
      </span>
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="max-w-xs text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "min-h-[34px] rounded-md border px-2.5 text-xs font-medium transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      )}
    >
      {children}
    </button>
  );
}

function Pagination({
  page,
  totalPages,
  total,
  onPage,
  label,
}: {
  page: number;
  totalPages: number;
  total: number;
  onPage: (p: number) => void;
  label: string;
}) {
  if (total === 0) return null;
  const start = (page - 1) * PAGE_SIZE + 1;
  const end = Math.min(page * PAGE_SIZE, total);
  return (
    <nav
      className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3"
      aria-label={`Navigasi halaman ${label}`}
    >
      <p className="text-xs text-muted-foreground">
        Menampilkan <span className="font-mono-num font-medium text-foreground">{start}</span>
        {"–"}
        <span className="font-mono-num font-medium text-foreground">{end}</span> dari{" "}
        <span className="font-mono-num font-medium text-foreground">{total}</span> {label}
      </p>
      <div className="flex items-center gap-1.5">
        <Button
          variant="outline"
          size="sm"
          className="min-h-[36px]"
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          aria-label={`Halaman ${label} sebelumnya`}
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Sebelumnya
        </Button>
        <span className="px-1 text-xs text-muted-foreground" aria-hidden="true">
          <span className="font-mono-num font-medium text-foreground">{page}</span> / {totalPages}
        </span>
        <Button
          variant="outline"
          size="sm"
          className="min-h-[36px]"
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPages}
          aria-label={`Halaman ${label} berikutnya`}
        >
          Berikutnya
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
}

function Skel({ block, w = "w-full" }: { block?: boolean; w?: string }) {
  return (
    <span
      className={cn(
        "block animate-pulse rounded bg-muted",
        block ? "h-24 w-full" : `h-5 ${w}`
      )}
      aria-hidden="true"
    />
  );
}

function SkeletonRows({ cols, rows }: { cols: number; rows: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, r) => (
        <TableRow key={r}>
          {Array.from({ length: cols }).map((__, c) => (
            <TableCell key={c}>
              <span className="block h-4 w-full animate-pulse rounded bg-muted" aria-hidden="true" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  );
}
