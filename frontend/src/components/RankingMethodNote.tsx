import Link from "next/link";

import { fmtDate, fmtInt } from "@/lib/format";
import type { RankingMeta } from "@/lib/types";

/** Transparencia: método, fórmula, muestra usada y período de cada ranking. */
export function RankingMethodNote({ meta, extra }: { meta: RankingMeta; extra?: string }) {
  return (
    <aside className="card mb-4 grid gap-3 p-4 text-sm sm:grid-cols-[2fr_1fr]" aria-label="Cómo se calcula este ranking">
      <div>
        <p className="font-display text-base text-gold-strong">
          {meta.method_label} · {meta.metric_label}
        </p>
        <p className="mt-1 text-muted">{meta.method_description}</p>
        {extra && <p className="mt-1 text-xs text-warning">{extra}</p>}
        <p className="mt-2 text-xs text-faint">
          Nada de esto es un rating oficial.{" "}
          <Link href="/methodology" className="text-gold-strong underline">
            Ver metodología completa
          </Link>
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <dt className="text-faint">Registros usados</dt>
        <dd className="num text-right text-ink">{fmtInt(meta.records_used)}</dd>
        <dt className="text-faint">Excluidos por muestra</dt>
        <dd className="num text-right text-ink">{fmtInt(meta.records_excluded)}</dd>
        <dt className="text-faint">Personajes</dt>
        <dd className="num text-right text-ink">{fmtInt(meta.characters)}</dd>
        <dt className="text-faint">Período</dt>
        <dd className="text-right text-ink">
          {meta.period_from ? `${fmtDate(meta.period_from)} – ${fmtDate(meta.period_to)}` : "—"}
        </dd>
        {meta.min_bucket_size !== undefined && meta.method === "percentile" && (
          <>
            <dt className="text-faint">Muestra mínima por cubeta</dt>
            <dd className="num text-right text-ink">{meta.min_bucket_size}</dd>
          </>
        )}
        {meta.method === "consistency" && (
          <>
            <dt className="text-faint">Mínimo de kills</dt>
            <dd className="num text-right text-ink">{meta.consistency_min_kills}</dd>
          </>
        )}
      </dl>
    </aside>
  );
}
