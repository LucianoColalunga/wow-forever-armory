import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Card, DataBanners, ErrorState, PageHeader, Pill, StatCard } from "@/components/ui";
import { FightList } from "@/components/views/FightList";
import { ReportStatusPoller } from "@/components/views/ReportStatusPoller";
import { ApiError, apiGet } from "@/lib/api";
import { fmtBytes, fmtDateTime, fmtInt } from "@/lib/format";
import type { DataMeta, FightSummary } from "@/lib/types";

export const metadata: Metadata = { title: "Reporte" };

interface ReportDetail {
  public_id: string;
  title: string;
  dataset: "real" | "demo";
  visibility: string;
  status: string;
  guild: { id: number; name: string; realm: string } | null;
  parser_version: string | null;
  dialect: Record<string, string | number | boolean | null> | null;
  stats: Record<string, unknown> | null;
  log_started_at: string | null;
  log_ended_at: string | null;
  created_at: string;
  processed_at: string | null;
  error: string | null;
  source_file: { sha256: string; original_name: string; size_bytes: number; content_kind: string } | null;
  fights: FightSummary[];
  issues: { severity: string; code: string; message: string; line_no: number | null; fight_id: number | null }[];
  job: { status: string; attempts: number; max_attempts: number; last_error: string | null } | null;
  meta: DataMeta;
}

const STATUS: Record<string, { label: string; tone: "good" | "bad" | "warn" | "default" }> = {
  processed: { label: "Procesado", tone: "good" },
  queued: { label: "En cola", tone: "warn" },
  processing: { label: "Procesando", tone: "warn" },
  failed: { label: "Falló", tone: "bad" },
};

export default async function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[a-f0-9]{6,16}$/.test(id)) notFound();
  let r: ReportDetail;
  try {
    r = await apiGet<ReportDetail>(`/reports/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref={`/reports/${id}`} />;
  }
  const st = STATUS[r.status] ?? { label: r.status, tone: "default" as const };
  const stats = (r.stats ?? {}) as Record<string, number>;
  return (
    <>
      <PageHeader
        eyebrow={`Reporte ${r.public_id}${r.guild ? ` · <${r.guild.name}>` : ""}`}
        title={r.title}
        subtitle={`Subido ${fmtDateTime(r.created_at)} · log del ${fmtDateTime(r.log_started_at)} al ${fmtDateTime(r.log_ended_at)}`}
        actions={
          <div className="flex gap-2">
            <Pill tone={st.tone}>{st.label}</Pill>
            {r.visibility === "private" && <Pill>Privado</Pill>}
            {r.dataset === "demo" && <Pill tone="demo">DEMO</Pill>}
          </div>
        }
      />
      <DataBanners meta={r.meta} />
      {["queued", "processing"].includes(r.status) && <ReportStatusPoller reportId={r.public_id} />}
      {r.error && (
        <p className="mb-4 rounded-lg border border-danger/50 bg-danger/10 px-4 py-2 text-sm text-danger" role="alert">
          {r.error}
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Líneas" value={fmtInt(stats.total_lines)} hint={`${fmtInt(stats.error_lines)} con errores`} />
        <StatCard label="Combates" value={fmtInt(stats.fights)} />
        <StatCard label="Kills" value={fmtInt(stats.kills)} />
        <StatCard label="Duplicados" value={fmtInt(stats.duplicates)} hint="No suman a rankings" />
        <StatCard label="No rankeables" value={fmtInt(stats.unrankable)} />
        <StatCard label="Jugadores" value={fmtInt(stats.players)} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Combates" className="lg:col-span-2">
          <FightList fights={r.fights} />
        </Card>
        <Card title="Origen y versión">
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-faint">Archivo</dt>
            <dd className="break-all">{r.source_file?.original_name}</dd>
            <dt className="text-faint">Tamaño</dt>
            <dd>
              {fmtBytes(r.source_file?.size_bytes)} ({r.source_file?.content_kind})
            </dd>
            <dt className="text-faint">SHA-256</dt>
            <dd className="break-all font-mono text-xs text-muted">{r.source_file?.sha256}</dd>
            <dt className="text-faint">Parser</dt>
            <dd>v{r.parser_version ?? "—"}</dd>
            <dt className="text-faint">Formato</dt>
            <dd>
              {String(r.dialect?.label ?? "—")} · v{String(r.dialect?.log_version ?? "?")} · build {String(r.dialect?.build_version ?? "?")}
            </dd>
            <dt className="text-faint">Log avanzado</dt>
            <dd>{r.dialect?.advanced_enabled ? "Sí" : "No"}</dd>
            <dt className="text-faint">Procesado</dt>
            <dd>{fmtDateTime(r.processed_at)}</dd>
            {r.job && (
              <>
                <dt className="text-faint">Trabajo</dt>
                <dd>
                  {r.job.status} · intento {r.job.attempts}/{r.job.max_attempts}
                </dd>
              </>
            )}
          </dl>
        </Card>
      </div>
      <Card title="Avisos de consistencia" className="mt-4">
        {r.issues.length === 0 ? (
          <p className="text-sm text-muted">Sin avisos: el log pasó todas las validaciones.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {r.issues.map((i, k) => (
              <li key={k} className={i.severity === "error" ? "text-danger" : i.severity === "warning" ? "text-warning" : "text-muted"}>
                <span className="font-mono text-xs">[{i.code}]</span> {i.message}
                {i.line_no ? <span className="text-faint"> (línea {i.line_no})</span> : null}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
