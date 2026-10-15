import type { Metadata } from "next";

import { Badge, Card, ErrorState, PageHeader } from "@/components/ui";
import { ApiError, apiGet } from "@/lib/api";
import type { PvpMode, SourceInfo } from "@/lib/types";

export const metadata: Metadata = { title: "Fuentes de datos" };

const VERIFIED_FACTS = [
  {
    fact: "WoW: Forever es una rama nueva de WoW (nivel máximo 60) que corre junto al WoW moderno y a Classic; lanzamiento global el 4/11/2026.",
    source: "https://news.blizzard.com/en-us/article/24302093/carve-a-new-path-with-world-of-warcraft-forever",
  },
  {
    fact: "Bandas anunciadas: Hyjal Summit (20) y Barrow Deeps (10); campo de batalla Darkspear Islands (15 vs 15); nueve mazmorras nuevas.",
    source: "https://news.blizzard.com/en-us/article/24303862/world-of-warcraft-forever-whats-next-panel-recap",
  },
  {
    fact: "Cabecera real de un combat log de la beta: COMBAT_LOG_VERSION 22, BUILD_VERSION 1.60.1, PROJECT_ID 18.",
    source: "https://github.com/Emyrk/chronicle/issues/693",
  },
  {
    fact: "No hay respuesta oficial sobre APIs de Forever en el foro de la API de Blizzard; Blizzard nunca ofreció API para beta/PTR.",
    source: "https://us.forums.blizzard.com/en/blizzard/t/when-will-we-gain-api-access-to-forever-apis/59595",
  },
  {
    fact: "Formato de eventos, sufijos y bloque avanzado del combat log.",
    source: "https://warcraft.wiki.gg/wiki/COMBAT_LOG_EVENT",
  },
];

export default async function SourcesPage() {
  let sources: SourceInfo[];
  let modes: PvpMode[];
  try {
    const [s, cat] = await Promise.all([apiGet<SourceInfo[]>("/meta/sources"), apiGet<{ pvp_modes: PvpMode[] }>("/meta/catalog")]);
    sources = s;
    modes = cat.pvp_modes;
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} />;
  }
  return (
    <>
      <PageHeader
        eyebrow="Transparencia"
        title="Fuentes de datos"
        subtitle="Estado de cada integración. Las fuentes no verificadas no se activan: la falta de API oficial no bloquea el sitio porque el importador de combat logs funciona por su cuenta."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        {sources.map((s) => (
          <Card key={s.key} title={s.label} actions={<Badge status={s.status} />}>
            <p className="text-sm text-muted">{s.description}</p>
            <p className="mt-2 text-xs text-faint">
              <strong className="text-muted">Límites:</strong> {s.limits}
            </p>
            <p className="mt-2 text-xs text-faint">Aporta: {s.provides.join(", ")}</p>
            {s.references.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs">
                {s.references.map((r) => (
                  <li key={r}>
                    <a href={r} target="_blank" rel="noreferrer noopener" className="break-all text-gold-strong underline">
                      {r}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ))}
      </div>
      <Card title="Modalidades PvP" className="mt-4">
        <ul className="space-y-2 text-sm">
          {modes.map((m) => (
            <li key={m.key} className="flex flex-wrap items-center justify-between gap-2">
              <span>
                {m.label} <span className="text-xs text-muted">— {m.detail}</span>
              </span>
              <Badge status={m.status} />
            </li>
          ))}
        </ul>
      </Card>
      <Card title="Hechos verificados (14/10/2026)" className="mt-4">
        <ul className="space-y-2 text-sm">
          {VERIFIED_FACTS.map((f) => (
            <li key={f.source}>
              <p className="text-muted">{f.fact}</p>
              <a href={f.source} target="_blank" rel="noreferrer noopener" className="break-all text-xs text-gold-strong underline">
                {f.source}
              </a>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
