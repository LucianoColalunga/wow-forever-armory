"use client";

import { fmtCompact, fmtInt } from "@/lib/format";

import { ColumnChart } from "../Charts";

export function DistributionChart({
  bins,
  metric,
  label,
}: {
  bins: { from: number; to: number; count: number }[];
  metric: string;
  label: string;
}) {
  const fmt = (v: number) => (metric === "survival_pct" ? `${Math.round(v)} %` : fmtCompact(v));
  return (
    <ColumnChart
      title={`Distribución de ${label}`}
      description="Todos los registros de la partición (no sólo el mejor de cada personaje)."
      data={bins.map((b) => ({ label: `${fmt(b.from)}–${fmt(b.to)}`, value: b.count }))}
      valueLabel="Registros"
      valueFormat={fmtInt}
    />
  );
}
