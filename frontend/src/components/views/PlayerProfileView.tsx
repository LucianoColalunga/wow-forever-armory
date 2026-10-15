"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { fmtDate, fmtDec, fmtInt, partitionLabel } from "@/lib/format";
import type { Encounter, FightSummary, Participant } from "@/lib/types";

import { TimeLineChart } from "../Charts";
import { type Column, DataTable } from "../DataTable";
import { Pill } from "../ui";

export interface BestRow {
  encounter: Encounter | null;
  difficulty_id: number | null;
  group_size: number | null;
  best_dps: number;
  best_hps: number;
  best_aps: number;
  kills: number;
  last_kill_at: string;
  best_dps_percentile: number | null;
  best_hps_percentile: number | null;
  bucket_size: number;
}

export interface EvolutionPoint {
  at: string;
  encounter_id: number;
  difficulty_id: number | null;
  group_size: number | null;
  dps: number;
  hps: number;
  aps: number;
  fight_id: number;
}

export function BestTable({ rows }: { rows: BestRow[] }) {
  const key = (r: BestRow) => `${r.encounter?.id}-${r.difficulty_id}-${r.group_size}`;
  const columns: Column<BestRow>[] = [
    {
      key: "enc",
      label: "Jefe",
      sortValue: (r) => r.encounter?.name ?? "",
      render: (r) =>
        r.encounter ? (
          <div className="flex flex-col">
            <Link href={`/rankings/pve/bosses/${r.encounter.id}`} className="font-medium hover:text-gold-strong">
              {r.encounter.name}
            </Link>
            <span className="text-xs text-muted">{partitionLabel(r.difficulty_id, r.group_size)}</span>
          </div>
        ) : (
          "—"
        ),
    },
    { key: "kills", label: "Kills", align: "right", sortValue: (r) => r.kills, render: (r) => fmtInt(r.kills) },
    { key: "dps", label: "Mejor DPS", align: "right", sortValue: (r) => r.best_dps, render: (r) => fmtDec(r.best_dps) },
    {
      key: "dps_pct",
      label: "Percentil DPS",
      align: "right",
      title: "Dentro de la misma clase y spec; vacío si la muestra no alcanza el mínimo",
      sortValue: (r) => r.best_dps_percentile,
      render: (r) => (r.best_dps_percentile === null ? <span className="text-faint" title="Muestra insuficiente">n/d</span> : fmtDec(r.best_dps_percentile)),
    },
    { key: "hps", label: "Mejor HPS", align: "right", sortValue: (r) => r.best_hps, render: (r) => fmtDec(r.best_hps) },
    { key: "aps", label: "Mejor Abs/s", align: "right", sortValue: (r) => r.best_aps, render: (r) => fmtDec(r.best_aps) },
    { key: "last", label: "Último kill", sortValue: (r) => r.last_kill_at, render: (r) => <span className="text-xs text-muted">{fmtDate(r.last_kill_at)}</span> },
  ];
  return <DataTable columns={columns} rows={rows} rowKey={key} caption="Mejores marcas por jefe" emptyMessage="Sin kills rankeables." />;
}

export function EvolutionChart({ points, bosses }: { points: EvolutionPoint[]; bosses: Record<number, string> }) {
  const encounterIds = useMemo(() => Array.from(new Set(points.map((p) => p.encounter_id))), [points]);
  const [boss, setBoss] = useState<number | undefined>(encounterIds[0]);
  const [metric, setMetric] = useState<"dps" | "hps" | "aps">(() => {
    const totals = { dps: 0, hps: 0, aps: 0 };
    for (const p of points) {
      totals.dps += p.dps;
      totals.hps += p.hps;
      totals.aps += p.aps;
    }
    return totals.hps > totals.dps ? "hps" : "dps";
  });
  if (points.length === 0) return <p className="text-sm text-muted">Todavía no hay kills para graficar.</p>;
  const data = points.filter((p) => p.encounter_id === boss).map((p) => ({ at: p.at, value: p[metric] }));
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-3 text-sm">
        <label className="flex items-center gap-2">
          <span className="text-muted">Jefe</span>
          <select value={boss} onChange={(e) => setBoss(Number(e.target.value))} className="rounded-md border border-line bg-surface px-2 py-1">
            {encounterIds.map((id) => (
              <option key={id} value={id}>
                {bosses[id] ?? `Jefe ${id}`}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2">
          <span className="text-muted">Métrica</span>
          <select value={metric} onChange={(e) => setMetric(e.target.value as "dps" | "hps" | "aps")} className="rounded-md border border-line bg-surface px-2 py-1">
            <option value="dps">DPS</option>
            <option value="hps">HPS efectivo</option>
            <option value="aps">Absorciones/s</option>
          </select>
        </label>
      </div>
      <TimeLineChart
        title={`Evolución de ${metric.toUpperCase()} en ${bosses[boss ?? -1] ?? "el jefe"}`}
        description="Cada punto es un kill rankeable (sin duplicados)."
        data={data}
        series={[{ key: "value", label: metric.toUpperCase() }]}
        valueFormat={fmtDec}
        dateFormat={fmtDate}
      />
    </div>
  );
}

export function RecentFights({ fights }: { fights: (FightSummary & { performance: Participant })[] }) {
  const columns: Column<FightSummary & { performance: Participant }>[] = [
    {
      key: "enc",
      label: "Combate",
      sortValue: (f) => f.encounter?.name ?? f.zone_name ?? "",
      render: (f) => (
        <Link href={`/encounters/${f.id}`} className="font-medium hover:text-gold-strong">
          {f.encounter?.name ?? f.zone_name ?? "Combate"}
        </Link>
      ),
    },
    {
      key: "res",
      label: "Resultado",
      render: (f) => (f.kind !== "encounter" ? <Pill>{f.kind === "battleground" ? "PvP" : "Recorrido"}</Pill> : f.success ? <Pill tone="good">Kill</Pill> : <Pill tone="bad">Wipe</Pill>),
    },
    { key: "dps", label: "DPS", align: "right", sortValue: (f) => f.performance.dps, render: (f) => fmtDec(f.performance.dps) },
    { key: "hps", label: "HPS", align: "right", sortValue: (f) => f.performance.hps, render: (f) => fmtDec(f.performance.hps) },
    { key: "deaths", label: "Muertes", align: "right", sortValue: (f) => f.performance.deaths, render: (f) => f.performance.deaths },
    { key: "date", label: "Fecha", sortValue: (f) => f.start_at, render: (f) => <span className="text-xs text-muted">{fmtDate(f.start_at)}</span> },
  ];
  return <DataTable columns={columns} rows={fights} rowKey={(f) => f.id} caption="Combates recientes" />;
}
