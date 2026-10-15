"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useState } from "react";

import { classLabel, specLabel } from "@/lib/classes";
import { clientGet } from "@/lib/client-api";
import { fmtDate, fmtDec, fmtPct, partitionLabel } from "@/lib/format";
import type { Character, Encounter } from "@/lib/types";

import { SERIES_COLORS, TimeLineChart } from "../Charts";
import { ClassName } from "../ui";

export interface CompareData {
  players: Character[];
  partitions: {
    encounter_id: number;
    difficulty_id: number | null;
    group_size: number | null;
    encounter: Encounter | null;
    shared_by_all: boolean;
    players: Record<string, { best_dps: number; median_dps: number; best_hps: number; median_hps: number; best_aps: number; kills: number; avg_survival_pct: number }>;
  }[];
  series: { character_id: number; at: string; dps: number; hps: number; encounter_id: number }[];
  note: string;
}

export function PlayerPicker({ ids, dataset }: { ids: number[]; dataset: string }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<{ id: number; name: string; realm: string; class_slug: string | null; spec: string | null }[]>([]);
  const inputId = useId();

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(() => {
      clientGet<{ players: typeof results }>("/search", { q: q.trim(), dataset, limit: 8 })
        .then((r) => setResults(r.players))
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q, dataset]);

  function go(next: number[]) {
    router.push(next.length ? `/compare?ids=${next.join(",")}` : "/compare");
  }

  return (
    <div className="card mb-4 p-4">
      <label htmlFor={inputId} className="text-sm text-muted">
        Agregar personaje ({ids.length}/4)
      </label>
      <input
        id={inputId}
        type="search"
        value={q}
        disabled={ids.length >= 4}
        onChange={(e) => setQ(e.target.value)}
        placeholder={ids.length >= 4 ? "Máximo 4 personajes" : "Escribí un nombre…"}
        className="mt-1 w-full max-w-md rounded-lg border border-line bg-surface px-3 py-1.5 text-sm"
        aria-describedby={`${inputId}-hint`}
      />
      <p id={`${inputId}-hint`} className="mt-1 text-xs text-faint">
        Comparación válida sólo dentro del mismo jefe, dificultad y tamaño de grupo.
      </p>
      {results.length > 0 && (
        <ul className="mt-2 max-w-md divide-y divide-line/60 rounded-lg border border-line" role="listbox" aria-label="Resultados">
          {results
            .filter((r) => !ids.includes(r.id))
            .map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-surface-2"
                  onClick={() => {
                    setQ("");
                    go([...ids, r.id]);
                  }}
                >
                  <ClassName name={r.name} classSlug={r.class_slug} spec={r.spec} realm={r.realm} />
                  <span className="text-xs text-muted">{specLabel(r.spec)}</span>
                </button>
              </li>
            ))}
        </ul>
      )}
      {ids.length > 0 && (
        <button type="button" onClick={() => go([])} className="mt-3 text-xs text-muted underline hover:text-ink">
          Limpiar selección
        </button>
      )}
    </div>
  );
}

export function CompareView({ data }: { data: CompareData }) {
  const [metric, setMetric] = useState<"dps" | "hps">("dps");
  const shared = data.partitions.filter((p) => p.shared_by_all);
  const [partKey, setPartKey] = useState(() => (shared[0] ?? data.partitions[0])?.encounter_id ?? 0);
  const names = Object.fromEntries(data.players.map((p) => [String(p.id), p.name]));
  const chartData = useMemo(() => {
    // Una fila por fecha; columna por jugador (sólo el jefe elegido).
    const byDate = new Map<string, Record<string, number | string | null>>();
    for (const s of data.series.filter((x) => x.encounter_id === partKey)) {
      const row = byDate.get(s.at) ?? { at: s.at };
      row[`p${s.character_id}`] = s[metric];
      byDate.set(s.at, row);
    }
    return Array.from(byDate.values()).sort((a, b) => String(a.at).localeCompare(String(b.at)));
  }, [data.series, partKey, metric]);

  return (
    <div className="space-y-4">
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {data.players.map((p, i) => (
          <li key={p.id} className="card p-3" style={{ borderTopColor: SERIES_COLORS[i], borderTopWidth: 3 }}>
            <ClassName name={p.name} classSlug={p.class_slug} spec={p.spec} realm={p.realm} href={`/players/${p.id}`} />
            <p className="mt-1 text-xs text-muted">
              {specLabel(p.spec)} {classLabel(p.class_slug)}
              {p.guild ? ` · <${p.guild.name}>` : ""}
            </p>
            <Link href={`/compare?ids=${data.players.filter((x) => x.id !== p.id).map((x) => x.id).join(",")}`} className="mt-2 inline-block text-xs text-muted underline hover:text-ink">
              Quitar
            </Link>
          </li>
        ))}
      </ul>
      <div className="card overflow-x-auto p-4">
        <table className="w-full min-w-[640px] text-sm">
          <caption className="mb-2 text-left text-xs text-faint">{data.note}</caption>
          <thead className="text-left text-xs uppercase tracking-wider text-muted">
            <tr>
              <th scope="col" className="px-2 py-1">Jefe</th>
              {data.players.map((p) => (
                <th key={p.id} scope="col" className="px-2 py-1 text-right">
                  {p.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.partitions.map((part) => (
              <tr key={`${part.encounter_id}-${part.difficulty_id}-${part.group_size}`} className="border-t border-line/60">
                <th scope="row" className="px-2 py-2 text-left font-normal">
                  <span className="text-ink">{part.encounter?.name ?? "Jefe"}</span>
                  <span className="block text-xs text-muted">
                    {partitionLabel(part.difficulty_id, part.group_size)}
                    {!part.shared_by_all && " · no todos lo jugaron"}
                  </span>
                </th>
                {data.players.map((p) => {
                  const v = part.players[String(p.id)];
                  return (
                    <td key={p.id} className="num px-2 py-2 text-right">
                      {v ? (
                        <>
                          <span className="text-gold-strong">{fmtDec(metric === "dps" ? v.best_dps : v.best_hps)}</span>
                          <span className="block text-xs text-muted">
                            mediana {fmtDec(metric === "dps" ? v.median_dps : v.median_hps)} · {v.kills} kills · {fmtPct(v.avg_survival_pct, 0)} vivo
                          </span>
                        </>
                      ) : (
                        <span className="text-faint">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap gap-3 text-sm">
          <label className="flex items-center gap-2">
            <span className="text-muted">Jefe</span>
            <select value={partKey} onChange={(e) => setPartKey(Number(e.target.value))} className="rounded-md border border-line bg-surface px-2 py-1">
              {Array.from(new Map(data.partitions.map((p) => [p.encounter_id, p.encounter?.name ?? `Jefe ${p.encounter_id}`]))).map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <span className="text-muted">Métrica</span>
            <select value={metric} onChange={(e) => setMetric(e.target.value as "dps" | "hps")} className="rounded-md border border-line bg-surface px-2 py-1">
              <option value="dps">DPS</option>
              <option value="hps">HPS efectivo</option>
            </select>
          </label>
        </div>
        <TimeLineChart
          title={`Evolución de ${metric.toUpperCase()} por kill`}
          data={chartData}
          series={data.players.map((p) => ({ key: `p${p.id}`, label: names[String(p.id)] }))}
          valueFormat={fmtDec}
          dateFormat={fmtDate}
        />
      </div>
    </div>
  );
}
