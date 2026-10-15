"use client";

/**
 * Gráficos interactivos (Recharts) con tabla accesible equivalente.
 *
 * Paleta categórica (modo oscuro), validada con el validador de paletas contra la superficie
 * #1c1926: azul, naranja, aqua, amarillo — orden fijo, máximo 4 series. Una sola serie usa el
 * azul y no lleva leyenda (el título la nombra).
 */

import { type ReactNode, useId, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { CastTimelineData } from "@/lib/types";

export const SERIES_COLORS = ["#3987e5", "#d95926", "#199e70", "#c98500"] as const;
const GRID = "#332c42";
const AXIS = "#8a8174";
const INK = "#ece6d9";
const SURFACE = "#1c1926";

const tooltipStyle = {
  contentStyle: { background: SURFACE, border: `1px solid ${GRID}`, borderRadius: 8, color: INK, fontSize: 12 },
  labelStyle: { color: INK, fontWeight: 600 },
  itemStyle: { color: INK },
  cursor: { stroke: AXIS, strokeWidth: 1, fill: "rgba(255,255,255,0.04)" },
};

function Figure({
  title,
  description,
  children,
  table,
  height = 256,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  table: { headers: string[]; rows: (string | number)[][] };
  height?: number;
}) {
  const [showTable, setShowTable] = useState(false);
  const id = useId();
  return (
    <figure className="m-0" aria-labelledby={`${id}-t`}>
      <div className="mb-2 flex items-start justify-between gap-2">
        <figcaption id={`${id}-t`}>
          <span className="block text-sm font-medium text-ink">{title}</span>
          {description && <span className="block text-xs text-muted">{description}</span>}
        </figcaption>
        <button
          type="button"
          className="shrink-0 rounded-md border border-line px-2 py-1 text-xs text-muted hover:text-ink"
          aria-expanded={showTable}
          aria-controls={`${id}-table`}
          onClick={() => setShowTable((s) => !s)}
        >
          {showTable ? "Ver gráfico" : "Ver como tabla"}
        </button>
      </div>
      {showTable ? (
        <div id={`${id}-table`} className="max-h-72 overflow-auto rounded-lg border border-line">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-surface-2 text-muted">
              <tr>
                {table.headers.map((h) => (
                  <th key={h} scope="col" className="px-2 py-1 text-left font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i} className="border-t border-line/60">
                  {r.map((c, j) => (
                    <td key={j} className={`px-2 py-1 ${j > 0 ? "num text-right" : ""}`}>
                      {c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          role="img"
          aria-label={`${title}. Usá «Ver como tabla» para leer los valores.`}
          className="w-full"
          style={{ height }}
        >
          {children}
        </div>
      )}
    </figure>
  );
}

export interface Series {
  key: string;
  label: string;
}

/** Serie(s) temporal(es): evolución de un valor por fecha. */
export function TimeLineChart({
  title,
  description,
  data,
  series,
  valueFormat,
  dateFormat,
}: {
  title: string;
  description?: string;
  data: Record<string, number | string | null>[];
  series: Series[];
  valueFormat: (v: number) => string;
  dateFormat: (iso: string) => string;
}) {
  const shown = series.slice(0, SERIES_COLORS.length);
  return (
    <Figure
      title={title}
      description={description}
      table={{
        headers: ["Fecha", ...shown.map((s) => s.label)],
        rows: data.map((d) => [
          dateFormat(String(d.at)),
          ...shown.map((s) => (d[s.key] === null || d[s.key] === undefined ? "—" : valueFormat(Number(d[s.key])))),
        ]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="at" tickFormatter={(v) => dateFormat(String(v))} stroke={AXIS} fontSize={11} minTickGap={24} />
          <YAxis stroke={AXIS} fontSize={11} tickFormatter={(v) => valueFormat(Number(v))} width={64} />
          <Tooltip
            {...tooltipStyle}
            labelFormatter={(v) => dateFormat(String(v))}
            formatter={(v, name) => [valueFormat(Number(v)), String(name)]}
          />
          {shown.length > 1 && <Legend wrapperStyle={{ color: INK, fontSize: 12 }} />}
          {shown.map((s, i) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={SERIES_COLORS[i]}
              strokeWidth={2}
              dot={{ r: 3, strokeWidth: 2, stroke: SURFACE, fill: SERIES_COLORS[i] }}
              activeDot={{ r: 5, stroke: SURFACE, strokeWidth: 2 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Figure>
  );
}

/** Área de una sola serie a lo largo del combate (eje X en segundos). */
export function CombatTimeline({
  title,
  description,
  values,
  bucketMs,
  valueFormat,
}: {
  title: string;
  description?: string;
  values: number[];
  bucketMs: number;
  valueFormat: (v: number) => string;
}) {
  const perSecond = bucketMs / 1000;
  const data = values.map((v, i) => ({ t: Math.round(i * perSecond), v: v / perSecond }));
  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  return (
    <Figure
      title={title}
      description={description}
      table={{ headers: ["Tiempo", "Por segundo"], rows: data.map((d) => [mmss(d.t), valueFormat(d.v)]) }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="t" tickFormatter={mmss} stroke={AXIS} fontSize={11} minTickGap={24} />
          <YAxis stroke={AXIS} fontSize={11} tickFormatter={(v) => valueFormat(Number(v))} width={64} />
          <Tooltip
            {...tooltipStyle}
            labelFormatter={(v) => mmss(Number(v))}
            formatter={(v) => [valueFormat(Number(v)), "por segundo"]}
          />
          <Area
            type="monotone"
            dataKey="v"
            stroke={SERIES_COLORS[0]}
            strokeWidth={2}
            fill={SERIES_COLORS[0]}
            fillOpacity={0.18}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </Figure>
  );
}

/** Barras horizontales (magnitud por jugador). */
export function HBarChart({
  title,
  description,
  data,
  valueFormat,
}: {
  title: string;
  description?: string;
  data: { label: string; value: number }[];
  valueFormat: (v: number) => string;
}) {
  const height = Math.max(160, data.length * 26 + 40);
  return (
    <Figure
      title={title}
      description={description}
      table={{ headers: ["Jugador", "Valor"], rows: data.map((d) => [d.label, valueFormat(d.value)]) }}
      height={height}
    >
      <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 4 }} barCategoryGap={2}>
            <CartesianGrid stroke={GRID} horizontal={false} />
            <XAxis type="number" stroke={AXIS} fontSize={11} tickFormatter={(v) => valueFormat(Number(v))} />
            <YAxis type="category" dataKey="label" stroke={AXIS} fontSize={11} width={110} />
            <Tooltip {...tooltipStyle} formatter={(v) => [valueFormat(Number(v)), "valor"]} />
            <Bar dataKey="value" fill={SERIES_COLORS[0]} radius={[0, 4, 4, 0]} isAnimationActive={false} />
          </BarChart>
      </ResponsiveContainer>
    </Figure>
  );
}

/** Columnas verticales: histogramas y conteos por período. */
export function ColumnChart({
  title,
  description,
  data,
  valueLabel,
  valueFormat,
}: {
  title: string;
  description?: string;
  data: { label: string; value: number }[];
  valueLabel: string;
  valueFormat?: (v: number) => string;
}) {
  const fmt = valueFormat ?? ((v: number) => String(v));
  return (
    <Figure
      title={title}
      description={description}
      table={{ headers: ["Tramo", valueLabel], rows: data.map((d) => [d.label, fmt(d.value)]) }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 4 }} barCategoryGap={2}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="label" stroke={AXIS} fontSize={11} minTickGap={12} />
          <YAxis stroke={AXIS} fontSize={11} allowDecimals={false} width={48} tickFormatter={(v) => fmt(Number(v))} />
          <Tooltip {...tooltipStyle} formatter={(v) => [fmt(Number(v)), valueLabel]} />
          <Bar dataKey="value" fill={SERIES_COLORS[0]} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </Figure>
  );
}

const MAX_TIMELINE_ROWS = 14;

function mmss(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Línea de tiempo de lanzamientos: una fila por hechizo y un punto por uso. */
export function CastTimelineChart({
  title,
  description,
  data,
  durationMs,
}: {
  title: string;
  description?: string;
  data: CastTimelineData;
  durationMs: number;
}) {
  const { categories, points, table } = useMemo(() => {
    const counts = new Map<number, number>();
    for (const idx of data.s) counts.set(idx, (counts.get(idx) ?? 0) + 1);
    const order = [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([i]) => i);
    const top = order.slice(0, MAX_TIMELINE_ROWS);
    const topSet = new Set(top);
    const cats = top.map((i) => data.spells[i]);
    if (order.length > MAX_TIMELINE_ROWS) cats.push("Otras");
    const rank = new Map(cats.map((c, i) => [c, i]));
    const pts = data.t
      .map((t, k) => ({ x: t / 1000, y: topSet.has(data.s[k]) ? data.spells[data.s[k]] : "Otras", name: data.spells[data.s[k]] }))
      .sort((a, b) => (rank.get(a.y) ?? 0) - (rank.get(b.y) ?? 0) || a.x - b.x);
    const rows = order.map((i) => {
      const times = data.t.filter((_, k) => data.s[k] === i);
      return [data.spells[i], times.length, mmss(Math.min(...times) / 1000), mmss(Math.max(...times) / 1000)] as (string | number)[];
    });
    return { categories: cats, points: pts, table: rows };
  }, [data]);
  const height = Math.max(160, categories.length * 26 + 70);
  return (
    <Figure
      title={title}
      description={description}
      table={{ headers: ["Hechizo", "Usos", "Primer uso", "Último uso"], rows: table }}
      height={height}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={GRID} />
          <XAxis
            type="number"
            dataKey="x"
            name="Tiempo"
            domain={[0, Math.ceil(durationMs / 1000)]}
            tickFormatter={(v) => mmss(Number(v))}
            stroke={AXIS}
            fontSize={11}
          />
          <YAxis type="category" dataKey="y" allowDuplicatedCategory={false} width={150} stroke={AXIS} fontSize={11} />
          <Tooltip
            {...tooltipStyle}
            content={({ active, payload }) => {
              const pt = active && payload?.[0] ? (payload[0].payload as { x: number; name: string }) : null;
              return pt ? (
                <div style={tooltipStyle.contentStyle}>
                  <div style={{ padding: "4px 8px" }}>
                    <strong>{pt.name}</strong> · {mmss(pt.x)}
                  </div>
                </div>
              ) : null;
            }}
          />
          <Scatter data={points} fill={SERIES_COLORS[0]} shape="circle" isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </Figure>
  );
}
