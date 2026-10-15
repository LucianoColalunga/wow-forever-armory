"use client";

import { fmtInt } from "@/lib/format";

import { ColumnChart } from "../Charts";

export function DashboardCharts({ activity }: { activity: { label: string; value: number }[] }) {
  return (
    <ColumnChart
      title="Combates registrados por día"
      description="Intentos de jefe (kills y wipes), sin duplicados, en los últimos 30 días con datos."
      data={activity}
      valueLabel="Combates"
      valueFormat={fmtInt}
    />
  );
}
