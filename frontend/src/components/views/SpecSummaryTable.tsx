import Link from "next/link";

import { classColor, classLabel, specLabel } from "@/lib/classes";
import { fmtMetric } from "@/lib/format";
import type { SpecSummary } from "@/lib/types";

/**
 * Rendimiento típico por clase y spec: mediana del mejor valor de cada personaje (cada jugador cuenta
 * una vez) y el máximo. La barra es relativa a la mejor mediana; el número siempre está escrito.
 */
export function SpecSummaryTable({
  summary,
  metric,
  metricLabel,
  hrefFor,
}: {
  summary: SpecSummary;
  metric: string;
  metricLabel: string;
  hrefFor: (classSlug: string, spec: string | null) => string;
}) {
  const specs = summary.specs.filter((s) => s.median !== null);
  if (specs.length === 0) return <p className="text-sm text-muted">Todavía no hay personajes con clase identificada.</p>;
  const values = specs.map((s) => s.median ?? 0);
  const best = summary.higher_better ? Math.max(...values) : Math.min(...values.filter((v) => v > 0));
  const width = (v: number) => {
    if (!best || v <= 0) return 4;
    const ratio = summary.higher_better ? v / best : best / v;
    return Math.max(4, Math.min(100, Math.round(ratio * 100)));
  };
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">
          {metricLabel} típico por clase y especialización ({summary.higher_better ? "más alto es mejor" : "más bajo es mejor"})
        </caption>
        <thead>
          <tr className="text-left text-xs text-muted">
            <th scope="col" className="py-1.5 pr-3 font-normal">Spec</th>
            <th scope="col" className="py-1.5 pr-3 text-right font-normal">Jugadores</th>
            <th scope="col" className="w-2/5 py-1.5 pr-3 font-normal">
              Mediana de {metricLabel.toLowerCase()}
            </th>
            <th scope="col" className="py-1.5 text-right font-normal">Mejor</th>
          </tr>
        </thead>
        <tbody>
          {specs.map((s) => {
            const color = classColor(s.class_slug);
            return (
              <tr key={`${s.class_slug}-${s.spec ?? "x"}`} className="border-t border-line/60">
                <td className="py-1.5 pr-3">
                  <Link href={hrefFor(s.class_slug, s.spec)} className="inline-flex items-center gap-2 hover:underline">
                    <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
                    <span>
                      {s.spec ? specLabel(s.spec) : "Spec ?"} <span className="text-muted">{classLabel(s.class_slug)}</span>
                    </span>
                  </Link>
                </td>
                <td className="num py-1.5 pr-3 text-right">
                  {s.players}
                  {s.low_sample && (
                    <span className="ml-1 text-[10px] text-warning" title={`Menos de ${summary.min_players} jugadores: muestra chica`}>
                      muestra chica
                    </span>
                  )}
                </td>
                <td className="py-1.5 pr-3">
                  <div className="flex items-center gap-2">
                    <div className="h-2 flex-1 rounded-full bg-surface-3" aria-hidden="true">
                      <div
                        className="h-2 rounded-full"
                        style={{ width: `${width(s.median ?? 0)}%`, background: color, opacity: s.low_sample ? 0.45 : 0.9 }}
                      />
                    </div>
                    <span className="num w-20 text-right text-xs">{fmtMetric(metric, s.median)}</span>
                  </div>
                </td>
                <td className="num py-1.5 text-right text-xs text-muted">{fmtMetric(metric, s.top)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
