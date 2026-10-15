"use client";

import Link from "next/link";

import { fmtDateTime, fmtDuration, fmtPct, partitionLabel } from "@/lib/format";
import type { FightSummary } from "@/lib/types";

import { type Column, DataTable } from "../DataTable";
import { Pill } from "../ui";

const KIND = { encounter: "Jefe", dungeon_run: "Recorrido", battleground: "Campo de batalla" } as const;
const REASON: Record<string, string> = {
  duplicado: "duplicado",
  incompleto: "incompleto",
  duracion_minima: "muy corto",
  revision_outlier: "en revisión",
  excluido_por_admin: "excluido",
  no_rankeable: "no rankeable",
};

export function FightList({ fights, showReport = false }: { fights: FightSummary[]; showReport?: boolean }) {
  const columns: Column<FightSummary>[] = [
    {
      key: "name",
      label: "Combate",
      sortValue: (f) => f.encounter?.name ?? f.zone_name ?? "",
      render: (f) => (
        <div className="flex flex-col">
          <Link href={`/encounters/${f.id}`} className="font-medium text-ink hover:text-gold-strong">
            {f.encounter?.name ?? f.zone_name ?? "Combate"}
          </Link>
          <span className="text-xs text-muted">
            {KIND[f.kind]} · {f.instance?.name ?? f.zone_name ?? "sin instancia"}
          </span>
        </div>
      ),
    },
    {
      key: "partition",
      label: "Grupo",
      sortValue: (f) => f.group_size ?? 0,
      render: (f) => <span className="text-xs text-muted">{f.kind === "encounter" ? partitionLabel(f.difficulty_id, f.group_size) : `${f.player_count} jugadores vistos`}</span>,
    },
    {
      key: "result",
      label: "Resultado",
      sortValue: (f) => (f.success ? 1 : 0),
      render: (f) => (
        <div className="flex flex-wrap gap-1">
          {f.kind === "encounter" &&
            (f.success ? <Pill tone="good">Kill</Pill> : <Pill tone="bad">Wipe {f.boss_min_hp_pct !== null ? `(${fmtPct(f.boss_min_hp_pct, 0)})` : ""}</Pill>)}
          {!f.rankable && f.unrankable_reason && <Pill tone="warn">{REASON[f.unrankable_reason] ?? f.unrankable_reason}</Pill>}
          {f.dataset === "demo" && <Pill tone="demo">DEMO</Pill>}
        </div>
      ),
    },
    { key: "duration", label: "Duración", align: "right", sortValue: (f) => f.duration_ms, render: (f) => fmtDuration(f.duration_ms) },
    {
      key: "date",
      label: "Fecha",
      sortValue: (f) => f.start_at,
      render: (f) => <span className="text-xs text-muted">{fmtDateTime(f.start_at)}</span>,
    },
  ];
  if (showReport) {
    columns.push({
      key: "report",
      label: "Reporte",
      render: (f) => (
        <Link href={`/reports/${f.report_public_id}`} className="font-mono text-xs text-muted hover:text-ink">
          {f.report_public_id}
        </Link>
      ),
    });
  }
  return <DataTable columns={columns} rows={fights} rowKey={(f) => f.id} caption="Combates" emptyMessage="No hay combates registrados." />;
}
