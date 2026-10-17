import Link from "next/link";
import type { ReactNode } from "react";

import { classColor, classLabel, specLabel } from "@/lib/classes";
import { fmtDateTime } from "@/lib/format";
import type { DataMeta } from "@/lib/types";

export function PageHeader({
  title,
  subtitle,
  eyebrow,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <p className="mb-1 text-xs uppercase tracking-[0.2em] text-arcane">{eyebrow}</p>}
        <h1 className="font-display text-2xl text-gold-strong sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Card({ title, children, className = "", actions }: {
  title?: ReactNode;
  children: ReactNode;
  className?: string;
  actions?: ReactNode;
}) {
  return (
    <section className={`card p-4 ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          {title && <h2 className="font-display text-lg text-ink">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-wider text-faint">{label}</p>
      <p className="num mt-1 font-display text-2xl text-gold-strong">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export function ClassName({
  name,
  classSlug,
  spec,
  href,
  realm,
}: {
  name: string;
  classSlug: string | null | undefined;
  spec?: string | null;
  href?: string;
  realm?: string | null;
}) {
  const color = classColor(classSlug);
  const inner = (
    <>
      <span
        className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
        style={{ backgroundColor: color }}
        aria-hidden="true"
      />
      <span className="font-medium" style={{ color }}>
        {name}
      </span>
      {realm ? <span className="text-xs text-faint">{realm}</span> : null}
      <span className="sr-only">
        ({classLabel(classSlug)}
        {spec ? `, ${specLabel(spec)}` : ""})
      </span>
    </>
  );
  return href ? (
    <Link href={href} className="inline-flex items-center gap-1.5 hover:underline">
      {inner}
    </Link>
  ) : (
    <span className="inline-flex items-center gap-1.5">{inner}</span>
  );
}

/** Facción con texto (el color acompaña, nunca es la única señal). */
export function FactionTag({ faction }: { faction: string | null | undefined }) {
  if (faction !== "alliance" && faction !== "horde") return <span className="text-xs text-faint">—</span>;
  const horde = faction === "horde";
  return (
    <span className={`inline-flex items-center gap-1 text-xs ${horde ? "text-horde" : "text-alliance"}`}>
      <span aria-hidden="true" className={`inline-block h-2 w-2 rounded-full ${horde ? "bg-horde" : "bg-alliance"}`} />
      {horde ? "Horda" : "Alianza"}
    </span>
  );
}

export function SpecTag({ classSlug, spec }: { classSlug: string | null | undefined; spec?: string | null }) {
  return (
    <span className="text-xs text-muted">
      {spec ? specLabel(spec) : "Spec ?"} · {classLabel(classSlug)}
    </span>
  );
}

const VERIFY: Record<string, { label: string; cls: string }> = {
  official: { label: "Confirmado por Blizzard", cls: "border-success/50 text-success" },
  verified_by_admin: { label: "Verificado por admin", cls: "border-arcane/50 text-arcane" },
  reported: { label: "Reportado por terceros", cls: "border-warning/50 text-warning" },
  unconfirmed: { label: "Sin confirmar", cls: "border-warning/50 text-warning" },
  not_available: { label: "No disponible", cls: "border-danger/50 text-danger" },
  active: { label: "Activa", cls: "border-success/50 text-success" },
  unavailable: { label: "No disponible", cls: "border-danger/50 text-danger" },
  disabled: { label: "Desactivada", cls: "border-faint/50 text-muted" },
  planned: { label: "Planificada", cls: "border-arcane/50 text-arcane" },
};

export function Badge({ status }: { status: string }) {
  const v = VERIFY[status] ?? { label: status, cls: "border-line text-muted" };
  return <span className={`inline-block rounded-full border px-2 py-0.5 text-[11px] ${v.cls}`}>{v.label}</span>;
}

export function Pill({ children, tone = "default" }: { children: ReactNode; tone?: "default" | "good" | "bad" | "warn" | "demo" }) {
  const tones = {
    default: "border-line text-muted",
    good: "border-success/50 text-success",
    bad: "border-danger/50 text-danger",
    warn: "border-warning/50 text-warning",
    demo: "border-demo/60 text-demo",
  };
  return <span className={`inline-block rounded-full border px-2 py-0.5 text-[11px] ${tones[tone]}`}>{children}</span>;
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-2 p-8 text-center" role="status">
      <svg width="40" height="40" viewBox="0 0 24 24" aria-hidden="true" className="text-faint">
        <path fill="currentColor" d="M12 2 3 7v10l9 5 9-5V7l-9-5Zm0 2.3 6.6 3.7L12 11.7 5.4 8 12 4.3ZM5 9.7l6 3.4v6.6l-6-3.4V9.7Zm8 10v-6.6l6-3.4v6.6l-6 3.4Z" />
      </svg>
      <p className="font-display text-lg text-ink">{title}</p>
      {children && <div className="max-w-xl text-sm text-muted">{children}</div>}
    </div>
  );
}

export function ErrorState({ message, retryHref }: { message: string; retryHref?: string }) {
  return (
    <div className="card border-danger/40 p-6" role="alert">
      <p className="font-display text-lg text-danger">No se pudieron cargar los datos</p>
      <p className="mt-1 text-sm text-muted">{message}</p>
      {retryHref && (
        <Link href={retryHref} className="mt-3 inline-block text-sm text-gold-strong underline">
          Reintentar
        </Link>
      )}
    </div>
  );
}

export function DataBanners({ meta }: { meta: DataMeta | null | undefined }) {
  if (!meta) return null;
  return (
    <div className="mb-4 space-y-2">
      {meta.is_demo && (
        <div className="rounded-lg border border-demo/50 bg-demo/10 px-4 py-2 text-sm text-demo" role="note">
          <strong>Datos de demostración.</strong> Todo lo que ves en este modo es sintético (personajes, jefes y
          logs generados) y nunca se mezcla con datos reales. Cambiá a «Datos reales» arriba a la derecha.
        </div>
      )}
      {meta.stale && (
        <div className="rounded-lg border border-warning/50 bg-warning/10 px-4 py-2 text-sm text-warning" role="note">
          Datos desactualizados: el último reporte procesado es del {fmtDateTime(meta.last_processed_at)}.
        </div>
      )}
    </div>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  basePath,
  params,
}: {
  page: number;
  pageSize: number;
  total: number;
  basePath: string;
  params: Record<string, string | undefined>;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  const href = (p: number) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) qs.set(k, v);
    qs.set("page", String(p));
    return `${basePath}?${qs}`;
  };
  return (
    <nav aria-label="Paginación" className="mt-4 flex items-center justify-between gap-2 text-sm">
      <span className="text-muted">
        Página {page} de {pages} · {total} resultados
      </span>
      <div className="flex gap-2">
        {page > 1 ? (
          <Link className="rounded-md border border-line px-3 py-1.5 hover:border-gold" href={href(page - 1)} rel="prev">
            ← Anterior
          </Link>
        ) : (
          <span className="rounded-md border border-line px-3 py-1.5 text-faint" aria-disabled="true">
            ← Anterior
          </span>
        )}
        {page < pages ? (
          <Link className="rounded-md border border-line px-3 py-1.5 hover:border-gold" href={href(page + 1)} rel="next">
            Siguiente →
          </Link>
        ) : (
          <span className="rounded-md border border-line px-3 py-1.5 text-faint" aria-disabled="true">
            Siguiente →
          </span>
        )}
      </div>
    </nav>
  );
}

export function Skeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="card space-y-3 p-4" aria-busy="true" aria-live="polite">
      <span className="sr-only">Cargando…</span>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-5 animate-pulse rounded bg-surface-3" style={{ width: `${90 - ((i * 13) % 35)}%` }} />
      ))}
    </div>
  );
}
