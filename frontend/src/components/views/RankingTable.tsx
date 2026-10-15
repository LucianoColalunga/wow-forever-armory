"use client";

import Link from "next/link";

import { classLabel, specLabel } from "@/lib/classes";
import { fmtDate, fmtDec, fmtMetric } from "@/lib/format";
import type { RankingRow } from "@/lib/types";

import { type Column, DataTable } from "../DataTable";
import { ClassName } from "../ui";

export type RankingKind = "general" | "partition" | "pvp";

export function RankingTable({
  rows,
  metric,
  metricLabel,
  method,
  kind,
}: {
  rows: RankingRow[];
  metric: string;
  metricLabel: string;
  method: string;
  kind: RankingKind;
}) {
  const isPct = method === "percentile";
  const valueLabel = isPct ? "Percentil" : kind === "general" ? "Índice" : metricLabel;
  const fmtValue = (v: number) => (isPct || kind === "general" ? fmtDec(v) : fmtMetric(metric, v));

  const columns: Column<RankingRow>[] = [
    { key: "rank", label: "#", sortValue: (r) => r.rank, render: (r) => <span className="num text-faint">{r.rank}</span> },
    {
      key: "name",
      label: "Personaje",
      sortValue: (r) => r.name,
      render: (r) => (
        <div className="flex flex-col">
          <ClassName
            name={r.name}
            classSlug={r.class_slug ?? r.character_class}
            spec={r.spec ?? r.character_spec}
            href={`/players/${r.character_id}`}
          />
          {r.guild_name && (
            <Link href={`/guilds/${r.guild_id}`} className="text-xs text-muted hover:text-ink">
              &lt;{r.guild_name}&gt;
            </Link>
          )}
        </div>
      ),
    },
    {
      key: "spec",
      label: "Clase · spec",
      sortValue: (r) => `${r.class_slug ?? r.character_class ?? "zz"}-${r.spec ?? r.character_spec ?? ""}`,
      render: (r) => (
        <span className="text-xs text-muted">
          {classLabel(r.class_slug ?? r.character_class)} · {specLabel(r.spec ?? r.character_spec)}
        </span>
      ),
    },
    {
      key: "value",
      label: valueLabel,
      align: "right",
      title: isPct ? "0–100 dentro de la misma clase y spec" : kind === "general" ? "100 = mediana del encuentro" : undefined,
      sortValue: (r) => r.value,
      render: (r) => <span className="font-semibold text-gold-strong">{fmtValue(r.value)}</span>,
    },
  ];
  if (isPct && kind !== "general") {
    columns.push({
      key: "raw",
      label: metricLabel,
      align: "right",
      sortValue: (r) => r.raw_value ?? null,
      render: (r) => fmtMetric(metric, r.raw_value),
    });
  }
  if (method === "consistency" && kind !== "general") {
    columns.push({
      key: "stddev",
      label: "Desvío",
      align: "right",
      title: "Desvío estándar de la muestra (menor = más constante)",
      sortValue: (r) => r.stddev ?? null,
      render: (r) => fmtMetric(metric, r.stddev),
    });
  }
  if (kind === "general") {
    columns.push({
      key: "partitions",
      label: "Encuentros",
      align: "right",
      sortValue: (r) => r.partitions ?? 0,
      render: (r) => r.partitions ?? "—",
    });
  }
  columns.push(
    {
      key: "samples",
      label: "Registros",
      align: "right",
      title: "Cantidad de combates usados para este valor",
      sortValue: (r) => r.samples,
      render: (r) => r.samples,
    },
    {
      key: "date",
      label: kind === "general" ? "Último" : "Fecha",
      sortValue: (r) => r.occurred_at,
      render: (r) =>
        r.fight_id ? (
          <Link href={`/encounters/${r.fight_id}`} className="text-xs text-muted hover:text-ink hover:underline">
            {fmtDate(r.occurred_at)}
          </Link>
        ) : (
          <span className="text-xs text-muted">{fmtDate(r.occurred_at)}</span>
        ),
    },
  );

  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(r) => r.character_id}
      caption={`Ranking por ${valueLabel}`}
      filterText={(r) => `${r.name} ${r.guild_name ?? ""} ${classLabel(r.class_slug ?? r.character_class)}`}
      emptyMessage="Ningún personaje cumple los filtros y la muestra mínima."
    />
  );
}
