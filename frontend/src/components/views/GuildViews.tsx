"use client";

import Link from "next/link";

import { fmtDate, fmtDuration, fmtInt, partitionLabel } from "@/lib/format";
import type { Encounter } from "@/lib/types";

import { ColumnChart } from "../Charts";
import { type Column, DataTable } from "../DataTable";

export interface ProgressionRow {
  encounter: Encounter | null;
  difficulty_id: number | null;
  group_size: number | null;
  first_kill_at: string;
  kills: number;
  fastest_kill_ms: number | null;
}

export function ProgressionTable({ rows }: { rows: ProgressionRow[] }) {
  const columns: Column<ProgressionRow>[] = [
    {
      key: "enc",
      label: "Jefe",
      sortValue: (r) => r.encounter?.name ?? "",
      render: (r) => (
        <div className="flex flex-col">
          {r.encounter ? (
            <Link href={`/rankings/pve/bosses/${r.encounter.id}`} className="font-medium hover:text-gold-strong">
              {r.encounter.name}
            </Link>
          ) : (
            "—"
          )}
          <span className="text-xs text-muted">{partitionLabel(r.difficulty_id, r.group_size)}</span>
        </div>
      ),
    },
    { key: "first", label: "Primer kill", sortValue: (r) => r.first_kill_at, render: (r) => fmtDate(r.first_kill_at) },
    { key: "kills", label: "Kills", align: "right", sortValue: (r) => r.kills, render: (r) => fmtInt(r.kills) },
    { key: "fast", label: "Más rápido", align: "right", sortValue: (r) => r.fastest_kill_ms ?? 0, render: (r) => fmtDuration(r.fastest_kill_ms) },
  ];
  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(r) => `${r.encounter?.id}-${r.difficulty_id}-${r.group_size}`}
      caption="Progreso de la hermandad"
      initialSort={{ key: "first", dir: "asc" }}
      emptyMessage="Sin kills registrados."
    />
  );
}

export function GuildActivity({ weeks }: { weeks: { week: string; pulls: number; kills: number }[] }) {
  return (
    <ColumnChart
      title="Kills por semana"
      description="Sólo reportes etiquetados con esta hermandad."
      data={weeks.map((w) => ({ label: fmtDate(w.week), value: w.kills }))}
      valueLabel="Kills"
      valueFormat={fmtInt}
    />
  );
}
