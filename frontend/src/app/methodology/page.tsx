import type { Metadata } from "next";

import { Card, ErrorState, PageHeader } from "@/components/ui";
import { ApiError, apiGet } from "@/lib/api";

export const metadata: Metadata = { title: "Metodología" };

interface Methodology {
  parser_version: string;
  metrics: Record<string, { label: string; higher_better: boolean; unit: string; pvp_only: boolean }>;
  methods: Record<string, { label: string; partition: string; general: string }>;
  thresholds: Record<string, number>;
  definitions: Record<string, string>;
}

export default async function MethodologyPage() {
  let m: Methodology;
  try {
    m = await apiGet<Methodology>("/meta/methodology");
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} />;
  }
  const t = m.thresholds;
  return (
    <>
      <PageHeader
        eyebrow={`Parser v${m.parser_version}`}
        title="Metodología"
        subtitle="Cómo se calcula cada número. Ningún valor de este sitio es un rating oficial de Blizzard."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Definiciones">
          <dl className="space-y-2 text-sm">
            {Object.entries(m.definitions).map(([k, v]) => (
              <div key={k}>
                <dt className="font-mono text-xs text-arcane">{k}</dt>
                <dd className="text-muted">{v}</dd>
              </div>
            ))}
          </dl>
        </Card>
        <Card title="Métodos de ranking">
          <div className="space-y-4 text-sm">
            {Object.entries(m.methods).map(([k, v]) => (
              <div key={k}>
                <p className="font-display text-gold-strong">{v.label}</p>
                <p className="text-muted">
                  <strong className="text-ink">Por jefe:</strong> {v.partition}
                </p>
                <p className="text-muted">
                  <strong className="text-ink">General:</strong> {v.general}
                </p>
              </div>
            ))}
            <div className="rounded-lg border border-line p-3 text-xs text-muted">
              <p className="mb-1 font-medium text-ink">Fórmulas</p>
              <p>
                Índice normalizado de un registro: <code>100 × valor / mediana(valores del mismo jefe, dificultad y tamaño)</code>.
                100 = rendimiento mediano del encuentro.
              </p>
              <p className="mt-1">
                Percentil: <code>percent_rank()</code> de PostgreSQL × 100 dentro de la cubeta (jefe, dificultad, tamaño, clase y spec):
                (posición − 1) / (n − 1).
              </p>
              <p className="mt-1">
                Umbrales actuales: cubeta mínima {t.min_bucket_size} registros · consistencia con al menos {t.consistency_min_kills} kills
                (últimos {t.consistency_last_n}) · partición mínima {t.min_partition_size} registros para normalizar · combates de menos de{" "}
                {Math.round(t.min_rankable_duration_ms / 1000)} s no se rankean.
              </p>
            </div>
          </div>
        </Card>
        <Card title="Métricas" className="lg:col-span-2">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Métricas disponibles</caption>
              <thead className="text-left text-xs uppercase text-muted">
                <tr>
                  <th scope="col" className="p-2">Clave</th>
                  <th scope="col" className="p-2">Nombre</th>
                  <th scope="col" className="p-2">Unidad</th>
                  <th scope="col" className="p-2">Mejor</th>
                  <th scope="col" className="p-2">Ámbito</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(m.metrics).map(([k, v]) => (
                  <tr key={k} className="border-t border-line/60">
                    <td className="p-2 font-mono text-xs">{k}</td>
                    <td className="p-2">{v.label}</td>
                    <td className="p-2 text-muted">{v.unit}</td>
                    <td className="p-2 text-muted">{v.higher_better ? "más alto" : "más bajo"}</td>
                    <td className="p-2 text-muted">{v.pvp_only ? "PvP" : "PvE y PvP"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title="Reglas de integridad" className="lg:col-span-2">
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            <li>Las absorciones (escudos) se atribuyen al lanzador del escudo y nunca se suman a la curación.</li>
            <li>El golpe duplicado <code>SWING_DAMAGE_LANDED</code>, <code>DAMAGE_SPLIT</code> y los eventos <code>_SUPPORT</code> no se cuentan.</li>
            <li>Mascotas y guardianes suman al dueño (vía <code>SPELL_SUMMON</code> u <code>ownerGUID</code> del log avanzado).</li>
            <li>Fingir Muerte no cuenta como muerte. Los eventos posteriores a <code>ENCOUNTER_END</code> se ignoran.</li>
            <li>El mismo archivo subido dos veces se detecta por SHA-256; el mismo combate grabado por otra persona se detecta por jefe, dificultad, tamaño, hora (±2 min) y jugadores.</li>
            <li>Valores que superan 3× el máximo histórico de un jefe quedan fuera de rankings hasta revisión admin.</li>
            <li>Los datos de demostración nunca se mezclan con los reales: viven en un conjunto separado y se marcan en toda la interfaz.</li>
          </ul>
        </Card>
      </div>
    </>
  );
}
