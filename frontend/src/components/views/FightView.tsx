"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { ROLE_LABELS, classLabel, specLabel } from "@/lib/classes";
import { fmtCompact, fmtDec, fmtDuration, fmtInt, fmtPct } from "@/lib/format";
import type { FightDetail, Participant } from "@/lib/types";

import { CombatTimeline, HBarChart } from "../Charts";
import { type Column, DataTable } from "../DataTable";
import { ClassName } from "../ui";

type Tab = "damage" | "healing" | "taken" | "utility";

const TABS: { key: Tab; label: string }[] = [
  { key: "damage", label: "Daño" },
  { key: "healing", label: "Curación y absorciones" },
  { key: "taken", label: "Daño recibido y muertes" },
  { key: "utility", label: "Interrupciones y dispels" },
];

function num(key: keyof Participant, label: string, fmt: (v: number) => string, title?: string): Column<Participant> {
  return {
    key: String(key),
    label,
    align: "right",
    title,
    sortValue: (p) => p[key] as number,
    render: (p) => fmt(p[key] as number),
  };
}

export function FightView({ fight }: { fight: FightDetail }) {
  const [tab, setTab] = useState<Tab>("damage");
  const isPvp = fight.kind === "battleground";
  const base: Column<Participant>[] = [
    {
      key: "name",
      label: "Jugador",
      sortValue: (p) => p.name,
      render: (p) => <ClassName name={p.name} classSlug={p.class_slug} spec={p.spec} href={`/players/${p.character_id}`} />,
    },
    {
      key: "role",
      label: "Spec · rol",
      sortValue: (p) => p.role,
      render: (p) => (
        <span className="text-xs text-muted">
          {classLabel(p.class_slug)} ({specLabel(p.spec)}) · {ROLE_LABELS[p.role] ?? p.role}
        </span>
      ),
    },
  ];
  const sets: Record<Tab, Column<Participant>[]> = {
    damage: [
      num("dps", "DPS", fmtDec, "Daño realizado / duración"),
      num("damage_done", "Daño realizado", fmtInt, "Vida quitada + overkill + absorbido por escudos del objetivo"),
      num("effective_damage", "Efectivo", fmtInt, "Vida realmente quitada"),
      num("overkill", "Overkill", fmtInt),
      num("damage_absorbed_by_target", "Absorbido", fmtInt, "Parte del daño que frenaron escudos del objetivo"),
      ...(isPvp ? [num("damage_to_players", "A jugadores", fmtInt), num("killing_blows", "Golpes de gracia", fmtInt)] : []),
    ],
    healing: [
      num("hps", "HPS efectivo", fmtDec),
      num("healing_effective", "Curación efectiva", fmtInt),
      num("overhealing", "Overhealing", fmtInt),
      {
        key: "oh_pct",
        label: "% overheal",
        align: "right",
        sortValue: (p) => (p.healing_gross ? p.overhealing / p.healing_gross : 0),
        render: (p) => (p.healing_gross ? fmtPct((100 * p.overhealing) / p.healing_gross) : "—"),
      },
      num("aps", "Absorciones/s", fmtDec),
      num("absorbs_provided", "Absorciones", fmtInt, "Daño frenado por escudos del jugador; no se suma a la curación"),
    ],
    taken: [
      num("damage_taken", "Daño recibido", fmtInt),
      num("damage_taken_absorbed", "Absorbido", fmtInt, "Daño entrante frenado por escudos (no es vida perdida)"),
      num("dtps", "Recibido/s", fmtDec),
      num("deaths", "Muertes", fmtInt),
      num("survival_pct", "Supervivencia", (v) => fmtPct(v), "% del combate con vida hasta la primera muerte"),
    ],
    utility: [num("interrupts", "Interrupciones", fmtInt), num("dispels", "Dispels", fmtInt)],
  };
  const sortKey = { damage: "dps", healing: "hps", taken: "damage_taken", utility: "interrupts" }[tab];
  const barMetric = sortKey as keyof Participant;
  const bars = useMemo(
    () =>
      [...fight.participants]
        .filter((p) => (p[barMetric] as number) > 0)
        .sort((a, b) => (b[barMetric] as number) - (a[barMetric] as number))
        .slice(0, 25)
        .map((p) => ({ label: p.name, value: p[barMetric] as number })),
    [fight.participants, barMetric],
  );
  const deaths = fight.participants.flatMap((p) => (p.death_log ?? []).map((d) => ({ ...d, name: p.name, cls: p.class_slug })));
  deaths.sort((a, b) => a.t_ms - b.t_ms);

  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="Métricas del combate" className="flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            type="button"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-md px-3 py-1.5 text-sm ${tab === t.key ? "bg-gold/20 text-gold-strong" : "text-muted hover:bg-surface-2 hover:text-ink"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="space-y-4">
        <DataTable
          key={tab}
          columns={[...base, ...sets[tab]]}
          rows={fight.participants}
          rowKey={(p) => p.character_id}
          caption={`Participantes: ${TABS.find((t) => t.key === tab)?.label}`}
          initialSort={{ key: sortKey, dir: "desc" }}
          filterText={(p) => `${p.name} ${classLabel(p.class_slug)}`}
        />
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="card p-4">
            <HBarChart
              title={`${TABS.find((t) => t.key === tab)?.label}: ${sortKey.toUpperCase()} por jugador`}
              data={bars}
              valueFormat={(v) => (["dps", "hps", "aps"].includes(sortKey) ? fmtDec(v) : fmtCompact(v))}
            />
          </div>
          {fight.timeline && (
            <div className="card p-4">
              <CombatTimeline
                title={tab === "healing" ? "Curación efectiva del grupo por segundo" : "Daño del grupo por segundo"}
                description={`Baldes de ${fight.timeline.bucket_ms / 1000} s`}
                values={tab === "healing" ? fight.timeline.raid_healing : fight.timeline.raid_damage}
                bucketMs={fight.timeline.bucket_ms}
                valueFormat={fmtCompact}
              />
            </div>
          )}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card p-4" aria-labelledby="deaths-title">
          <h2 id="deaths-title" className="mb-2 font-display text-lg">
            Muertes
          </h2>
          {deaths.length === 0 ? (
            <p className="text-sm text-muted">Nadie murió en este combate.</p>
          ) : (
            <ol className="space-y-1 text-sm">
              {deaths.map((d, i) => (
                <li key={i} className="flex flex-wrap gap-2">
                  <span className="num text-faint">{fmtDuration(d.t_ms)}</span>
                  <ClassName name={d.name} classSlug={d.cls} />
                  <span className="text-muted">
                    {d.ability ? `por ${d.ability}` : "causa desconocida"}
                    {d.killer ? ` (${d.killer})` : ""}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>
        <section className="card p-4" aria-labelledby="trace-title">
          <h2 id="trace-title" className="mb-2 font-display text-lg">
            Trazabilidad
          </h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-faint">Reporte</dt>
            <dd>
              <Link href={`/reports/${fight.source.report_public_id}`} className="text-gold-strong hover:underline">
                {fight.source.report_title}
              </Link>
            </dd>
            <dt className="text-faint">Archivo</dt>
            <dd className="break-all">{fight.source.file_name}</dd>
            <dt className="text-faint">SHA-256</dt>
            <dd className="break-all font-mono text-xs text-muted">{fight.source.file_sha256}</dd>
            <dt className="text-faint">Líneas</dt>
            <dd className="num">
              {fight.source.first_line} – {fight.source.last_line ?? "fin del archivo"}
            </dd>
            <dt className="text-faint">Parser</dt>
            <dd>v{fight.source.parser_version}</dd>
          </dl>
          {fight.issues.length > 0 && (
            <ul className="mt-3 space-y-1 text-xs">
              {fight.issues.map((i, k) => (
                <li key={k} className={i.severity === "error" ? "text-danger" : i.severity === "warning" ? "text-warning" : "text-muted"}>
                  [{i.severity}] {i.message}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
