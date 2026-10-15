import type { Metadata } from "next";
import Link from "next/link";

import { Badge, Card, ClassName, EmptyState, ErrorState, PageHeader } from "@/components/ui";
import { ApiError, apiGet } from "@/lib/api";
import { classLabel, specLabel } from "@/lib/classes";
import { first, getDataset } from "@/lib/dataset";
import { fmtDate } from "@/lib/format";
import type { Encounter, Instance } from "@/lib/types";

export const metadata: Metadata = { title: "Buscar" };

interface SearchResult {
  query: string;
  players: { id: number; name: string; realm: string; class_slug: string | null; spec: string | null; guild: string | null }[];
  guilds: { id: number; name: string; realm: string }[];
  bosses: Encounter[];
  instances: Instance[];
  reports: { public_id: string; title: string; created_at: string }[];
}

export default async function SearchPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const dataset = await getDataset(sp);
  const q = (first(sp.q) ?? "").trim().slice(0, 64);
  if (q.length < 2) {
    return (
      <>
        <PageHeader title="Buscar" subtitle="Escribí al menos 2 letras en el buscador de arriba." />
        <EmptyState title="Buscá personajes, hermandades, jefes, instancias o reportes" />
      </>
    );
  }
  let r: SearchResult;
  try {
    r = await apiGet<SearchResult>("/search", { q, dataset, limit: 10 });
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} />;
  }
  const total = r.players.length + r.guilds.length + r.bosses.length + r.instances.length + r.reports.length;
  return (
    <>
      <PageHeader eyebrow="Resultados" title={`«${q}»`} subtitle={`${total} coincidencias en datos ${dataset === "demo" ? "de demostración" : "reales"} (búsqueda tolerante a errores de tipeo).`} />
      {total === 0 ? (
        <EmptyState title="Sin coincidencias">Probá con otra parte del nombre o cambiá entre datos reales y demo.</EmptyState>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {r.players.length > 0 && (
            <Card title="Personajes">
              <ul className="space-y-2">
                {r.players.map((p) => (
                  <li key={p.id} className="flex flex-wrap items-center justify-between gap-2">
                    <ClassName name={p.name} classSlug={p.class_slug} spec={p.spec} realm={p.realm} href={`/players/${p.id}`} />
                    <span className="text-xs text-muted">
                      {specLabel(p.spec)} {classLabel(p.class_slug)}
                      {p.guild ? ` · <${p.guild}>` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {r.guilds.length > 0 && (
            <Card title="Hermandades">
              <ul className="space-y-2">
                {r.guilds.map((g) => (
                  <li key={g.id}>
                    <Link href={`/guilds/${g.id}`} className="hover:text-gold-strong">
                      &lt;{g.name}&gt; <span className="text-xs text-muted">{g.realm}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {r.bosses.length > 0 && (
            <Card title="Jefes">
              <ul className="space-y-2">
                {r.bosses.map((b) => (
                  <li key={b.id}>
                    <Link href={`/rankings/pve/bosses/${b.id}`} className="hover:text-gold-strong">
                      {b.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {r.instances.length > 0 && (
            <Card title="Instancias">
              <ul className="space-y-2">
                {r.instances.map((i) => (
                  <li key={i.id} className="flex items-center justify-between gap-2">
                    <Link
                      href={i.kind === "battleground" ? "/rankings/pvp" : `/${i.kind === "raid" ? "raids" : "dungeons"}/${i.slug}`}
                      className="hover:text-gold-strong"
                    >
                      {i.name}
                    </Link>
                    <Badge status={i.verification} />
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {r.reports.length > 0 && (
            <Card title="Reportes">
              <ul className="space-y-2">
                {r.reports.map((x) => (
                  <li key={x.public_id} className="flex justify-between gap-2">
                    <Link href={`/reports/${x.public_id}`} className="hover:text-gold-strong">
                      {x.title}
                    </Link>
                    <span className="text-xs text-muted">{fmtDate(x.created_at)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </>
  );
}
