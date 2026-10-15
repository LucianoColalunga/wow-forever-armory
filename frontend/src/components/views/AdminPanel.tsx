"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { CLASS_INFO, CLASS_SPECS, SPEC_LABELS } from "@/lib/classes";
import { ClientApiError, clientGet, clientSend } from "@/lib/client-api";
import { fmtDateTime, fmtInt } from "@/lib/format";
import type { Character, FightSummary, Instance, Paged, User } from "@/lib/types";

import { Badge, ClassName, Pill } from "../ui";

type TabKey = "overview" | "jobs" | "reports" | "characters" | "review" | "submissions" | "instances" | "users" | "audit";

const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "Resumen" },
  { key: "jobs", label: "Trabajos" },
  { key: "reports", label: "Reportes" },
  { key: "characters", label: "Personajes" },
  { key: "review", label: "Revisión" },
  { key: "submissions", label: "Aportes" },
  { key: "instances", label: "Instancias" },
  { key: "users", label: "Usuarios" },
  { key: "audit", label: "Auditoría" },
];

interface Ctx {
  reason: string;
  notify: (msg: string, ok?: boolean) => void;
}

function useLoad<T>(path: string, params?: Record<string, string | number | undefined>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = JSON.stringify(params ?? {});
  const reload = useCallback(() => {
    setError(null);
    clientGet<T>(path, params)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof ClientApiError ? e.message : "Error al cargar."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, key]);
  useEffect(() => reload(), [reload]);
  return { data, error, reload };
}

async function act(ctx: Ctx, fn: () => Promise<unknown>, ok: string, after?: () => void) {
  if (ctx.reason.trim().length < 5) {
    ctx.notify("Escribí un motivo (mínimo 5 caracteres): queda registrado en la auditoría.", false);
    return;
  }
  try {
    await fn();
    ctx.notify(ok, true);
    after?.();
  } catch (e) {
    ctx.notify(e instanceof ClientApiError ? e.message : "La acción falló.", false);
  }
}

const btn = "rounded-md border border-line px-2 py-1 text-xs hover:border-gold hover:text-gold-strong disabled:opacity-50";

export function AdminPanel() {
  const [me, setMe] = useState<User | null | undefined>(undefined);
  const [tab, setTab] = useState<TabKey>("overview");
  const [reason, setReason] = useState("");
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  useEffect(() => {
    clientGet<User>("/auth/me")
      .then(setMe)
      .catch(() => setMe(null));
  }, []);

  if (me === undefined) return <p className="text-sm text-muted">Verificando permisos…</p>;
  if (me === null || me.role !== "admin")
    return (
      <div className="card p-6 text-sm" role="alert">
        {me === null ? (
          <>
            Tu sesión no es válida.{" "}
            <Link href="/login?next=/admin" className="text-gold-strong underline">
              Iniciá sesión
            </Link>
            .
          </>
        ) : (
          "Tu cuenta no tiene rol de administrador."
        )}
      </div>
    );

  const ctx: Ctx = { reason, notify: (msg, ok = true) => setToast({ msg, ok }) };

  return (
    <div className="space-y-4">
      <div className="card flex flex-col gap-2 p-4 sm:flex-row sm:items-center">
        <label htmlFor="admin-reason" className="text-sm text-muted sm:w-56">
          Motivo de la acción <span className="text-faint">(obligatorio, se audita)</span>
        </label>
        <input
          id="admin-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
          placeholder="Ej.: confirmado por la hermandad en Discord"
          className="flex-1 rounded-md border border-line bg-surface px-3 py-1.5 text-sm"
        />
      </div>
      {toast && (
        <p role={toast.ok ? "status" : "alert"} className={`rounded-md border px-3 py-2 text-sm ${toast.ok ? "border-success/50 text-success" : "border-danger/50 text-danger"}`}>
          {toast.msg}
        </p>
      )}
      <div role="tablist" aria-label="Secciones del panel" className="flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-md px-3 py-1.5 text-sm ${tab === t.key ? "bg-gold/20 text-gold-strong" : "text-muted hover:bg-surface-2 hover:text-ink"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="card p-4">
        {tab === "overview" && <Overview />}
        {tab === "jobs" && <Jobs ctx={ctx} />}
        {tab === "reports" && <Reports ctx={ctx} />}
        {tab === "characters" && <Characters ctx={ctx} />}
        {tab === "review" && <Review ctx={ctx} />}
        {tab === "submissions" && <Submissions ctx={ctx} />}
        {tab === "instances" && <Instances ctx={ctx} />}
        {tab === "users" && <Users ctx={ctx} me={me} />}
        {tab === "audit" && <Audit />}
      </div>
    </div>
  );
}

function Loading({ error }: { error: string | null }) {
  return error ? <p className="text-sm text-danger" role="alert">{error}</p> : <p className="text-sm text-muted">Cargando…</p>;
}

function Overview() {
  const { data, error } = useLoad<{
    jobs: Record<string, number>;
    reports: Record<string, number>;
    datasets: Record<string, number>;
    pending_submissions: number;
    outliers_pending: number;
    workers: { worker_id: string; last_seen_at: string; processed: number }[];
    recent_issues: { report_public_id: string; severity: string; code: string; message: string }[];
    versions: Record<string, number>;
  }>("/admin/overview");
  if (!data) return <Loading error={error} />;
  const kv = (o: Record<string, number>) =>
    Object.entries(o).map(([k, v]) => (
      <li key={k} className="flex justify-between gap-2">
        <span className="text-muted">{k}</span>
        <span className="num">{fmtInt(v)}</span>
      </li>
    ));
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <section>
        <h3 className="mb-2 font-display">Trabajos</h3>
        <ul className="space-y-1 text-sm">{kv(data.jobs)}</ul>
      </section>
      <section>
        <h3 className="mb-2 font-display">Reportes</h3>
        <ul className="space-y-1 text-sm">{kv(data.reports)}</ul>
        <ul className="mt-2 space-y-1 text-sm">{kv(data.datasets)}</ul>
      </section>
      <section>
        <h3 className="mb-2 font-display">Pendientes</h3>
        <ul className="space-y-1 text-sm">
          <li className="flex justify-between"><span className="text-muted">Aportes</span><span>{data.pending_submissions}</span></li>
          <li className="flex justify-between"><span className="text-muted">Outliers</span><span>{data.outliers_pending}</span></li>
          <li className="flex justify-between"><span className="text-muted">Versión caché real/demo</span><span>{data.versions.real} / {data.versions.demo}</span></li>
        </ul>
        <h3 className="mb-1 mt-3 font-display">Workers</h3>
        <ul className="space-y-1 text-xs">
          {data.workers.length === 0 && <li className="text-warning">Sin latidos de workers.</li>}
          {data.workers.map((w) => (
            <li key={w.worker_id} className="text-muted">{w.worker_id} · {fmtDateTime(w.last_seen_at)} · {w.processed} procesados</li>
          ))}
        </ul>
      </section>
      <section className="md:col-span-3">
        <h3 className="mb-2 font-display">Avisos recientes</h3>
        <ul className="space-y-1 text-xs">
          {data.recent_issues.length === 0 && <li className="text-muted">Sin avisos.</li>}
          {data.recent_issues.map((i, k) => (
            <li key={k} className={i.severity === "error" ? "text-danger" : "text-warning"}>
              <Link href={`/reports/${i.report_public_id}`} className="font-mono underline">{i.report_public_id}</Link> [{i.code}] {i.message}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Jobs({ ctx }: { ctx: Ctx }) {
  const [status, setStatus] = useState("");
  const { data, error, reload } = useLoad<Paged<{ id: number; report_public_id: string; report_title: string; kind: string; status: string; attempts: number; max_attempts: number; last_error: string | null; created_at: string }>>("/admin/jobs", { status: status || undefined, page_size: 50 });
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm">
        <span className="text-muted">Estado</span>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-1">
          {["", "queued", "running", "succeeded", "failed", "dead"].map((s) => <option key={s} value={s}>{s || "todos"}</option>)}
        </select>
      </label>
      {!data ? <Loading error={error} /> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Trabajos de importación</caption>
            <thead className="text-left text-xs text-muted"><tr><th className="p-1">#</th><th className="p-1">Reporte</th><th className="p-1">Tipo</th><th className="p-1">Estado</th><th className="p-1">Intentos</th><th className="p-1">Error</th><th className="p-1">Acción</th></tr></thead>
            <tbody>
              {data.items.map((j) => (
                <tr key={j.id} className="border-t border-line/60">
                  <td className="p-1 num">{j.id}</td>
                  <td className="p-1"><Link href={`/reports/${j.report_public_id}`} className="underline">{j.report_title}</Link></td>
                  <td className="p-1">{j.kind}</td>
                  <td className="p-1"><Pill tone={j.status === "succeeded" ? "good" : j.status === "dead" || j.status === "failed" ? "bad" : "warn"}>{j.status}</Pill></td>
                  <td className="p-1 num">{j.attempts}/{j.max_attempts}</td>
                  <td className="max-w-xs truncate p-1 text-xs text-danger" title={j.last_error ?? ""}>{j.last_error}</td>
                  <td className="p-1">
                    {(j.status === "dead" || j.status === "failed") && (
                      <button type="button" className={btn} onClick={() => act(ctx, () => clientSend("POST", `/admin/jobs/${j.id}/retry`, { reason: ctx.reason }), "Trabajo reencolado.", reload)}>Reintentar</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Reports({ ctx }: { ctx: Ctx }) {
  const [dataset, setDataset] = useState("real");
  const { data, error, reload } = useLoad<Paged<{ id: number; public_id: string; title: string; dataset: string; status: string; visibility: string; parser_version: string | null; created_at: string; error: string | null }>>("/admin/reports", { dataset, page_size: 50 });
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm">
        <span className="text-muted">Dataset</span>
        <select value={dataset} onChange={(e) => setDataset(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-1">
          <option value="real">real</option><option value="demo">demo</option>
        </select>
      </label>
      {!data ? <Loading error={error} /> : (
        <ul className="divide-y divide-line/60 text-sm">
          {data.items.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <div>
                <Link href={`/reports/${r.public_id}`} className="font-medium underline">{r.title}</Link>
                <span className="ml-2 text-xs text-muted">{r.public_id} · {r.status} · parser v{r.parser_version ?? "?"} · {r.visibility} · {fmtDateTime(r.created_at)}</span>
              </div>
              <div className="flex flex-wrap gap-1">
                <button type="button" className={btn} onClick={() => act(ctx, () => clientSend("POST", `/admin/reports/${r.public_id}/reprocess`, { reason: ctx.reason }), "Reproceso encolado.", reload)}>Reprocesar</button>
                <button type="button" className={btn} onClick={() => act(ctx, () => clientSend("PATCH", `/admin/reports/${r.public_id}`, { reason: ctx.reason, visibility: r.visibility === "public" ? "private" : "public" }), "Visibilidad actualizada.", reload)}>{r.visibility === "public" ? "Hacer privado" : "Hacer público"}</button>
                <button type="button" className={`${btn} hover:!border-danger hover:!text-danger`} onClick={() => { if (window.confirm(`¿Eliminar el reporte «${r.title}»? Deja de contar en rankings.`)) void act(ctx, () => clientSend("POST", `/admin/reports/${r.public_id}/delete`, { reason: ctx.reason }), "Reporte eliminado.", reload); }}>Eliminar</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Characters({ ctx }: { ctx: Ctx }) {
  const [q, setQ] = useState("");
  const [dataset, setDataset] = useState("real");
  const { data, error, reload } = useLoad<Paged<Character & { hidden: boolean; class_locked: boolean }>>("/admin/characters", { q: q || undefined, dataset, page_size: 25 });
  const [edit, setEdit] = useState<Record<number, { cls: string; spec: string; guild: string }>>({});
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 text-sm">
        <label className="flex items-center gap-2"><span className="text-muted">Buscar</span><input value={q} onChange={(e) => setQ(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-1" /></label>
        <select aria-label="Dataset" value={dataset} onChange={(e) => setDataset(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-1"><option value="real">real</option><option value="demo">demo</option></select>
      </div>
      {!data ? <Loading error={error} /> : (
        <ul className="divide-y divide-line/60 text-sm">
          {data.items.map((c) => {
            const e = edit[c.id] ?? { cls: c.class_slug ?? "", spec: c.spec ?? "", guild: "" };
            const set = (patch: Partial<typeof e>) => setEdit((s) => ({ ...s, [c.id]: { ...e, ...patch } }));
            return (
              <li key={c.id} className="flex flex-wrap items-center gap-2 py-2">
                <span className="min-w-40"><ClassName name={c.name} classSlug={c.class_slug} spec={c.spec} href={`/players/${c.id}`} /></span>
                {c.hidden && <Pill tone="warn">oculto</Pill>}
                {c.class_locked && <Pill>clase fijada</Pill>}
                <select aria-label={`Clase de ${c.name}`} value={e.cls} onChange={(ev) => set({ cls: ev.target.value, spec: "" })} className="rounded-md border border-line bg-surface px-2 py-1 text-xs">
                  <option value="">—</option>
                  {Object.entries(CLASS_INFO).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                </select>
                <select aria-label={`Spec de ${c.name}`} value={e.spec} onChange={(ev) => set({ spec: ev.target.value })} className="rounded-md border border-line bg-surface px-2 py-1 text-xs">
                  <option value="">—</option>
                  {(CLASS_SPECS[e.cls] ?? []).map((s) => <option key={s} value={s}>{SPEC_LABELS[s]}</option>)}
                </select>
                <button type="button" className={btn} disabled={!e.cls} onClick={() => act(ctx, () => clientSend("PATCH", `/admin/characters/${c.id}`, { reason: ctx.reason, class_slug: e.cls, spec: e.spec || undefined }), "Clase/spec corregida.", reload)}>Guardar clase</button>
                <input aria-label={`ID de hermandad para ${c.name}`} placeholder="ID hermandad (0 = quitar)" value={e.guild} onChange={(ev) => set({ guild: ev.target.value })} className="w-44 rounded-md border border-line bg-surface px-2 py-1 text-xs" />
                <button type="button" className={btn} disabled={!/^\d+$/.test(e.guild)} onClick={() => act(ctx, () => clientSend("PATCH", `/admin/characters/${c.id}`, { reason: ctx.reason, guild_id: Number(e.guild) }), "Hermandad actualizada.", reload)}>Asignar</button>
                <button type="button" className={btn} onClick={() => act(ctx, () => clientSend("PATCH", `/admin/characters/${c.id}`, { reason: ctx.reason, hidden: !c.hidden }), c.hidden ? "Personaje visible." : "Personaje oculto.", reload)}>{c.hidden ? "Mostrar" : "Ocultar (privacidad)"}</button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function Review({ ctx }: { ctx: Ctx }) {
  const { data, error, reload } = useLoad<Paged<FightSummary & { excluded_by_admin: boolean }>>("/admin/fights/review", { page_size: 50 });
  const [fightId, setFightId] = useState("");
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label className="flex items-center gap-2"><span className="text-muted">Excluir combate por ID</span><input value={fightId} onChange={(e) => setFightId(e.target.value)} className="w-28 rounded-md border border-line bg-surface px-2 py-1" /></label>
        <button type="button" className={btn} disabled={!/^\d+$/.test(fightId)} onClick={() => act(ctx, () => clientSend("PATCH", `/admin/fights/${fightId}`, { reason: ctx.reason, excluded: true }), "Combate excluido de rankings.", reload)}>Excluir</button>
      </div>
      {!data ? <Loading error={error} /> : data.items.length === 0 ? <p className="text-sm text-muted">No hay combates pendientes ni excluidos.</p> : (
        <ul className="divide-y divide-line/60 text-sm">
          {data.items.map((f) => (
            <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span><Link href={`/encounters/${f.id}`} className="underline">#{f.id} {f.encounter?.name ?? f.zone_name}</Link> <span className="text-xs text-muted">{f.unrankable_reason}</span></span>
              <div className="flex gap-1">
                {f.unrankable_reason === "revision_outlier" && <button type="button" className={btn} onClick={() => act(ctx, () => clientSend("PATCH", `/admin/fights/${f.id}`, { reason: ctx.reason, approve_outlier: true }), "Outlier aprobado.", reload)}>Aprobar</button>}
                <button type="button" className={btn} onClick={() => act(ctx, () => clientSend("PATCH", `/admin/fights/${f.id}`, { reason: ctx.reason, excluded: !f.excluded_by_admin }), "Actualizado.", reload)}>{f.excluded_by_admin ? "Volver a incluir" : "Excluir"}</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Submissions({ ctx }: { ctx: Ctx }) {
  const { data, error, reload } = useLoad<Paged<{ id: number; kind: string; payload: Record<string, unknown>; contact: string | null; created_at: string }>>("/admin/submissions", { page_size: 50 });
  if (!data) return <Loading error={error} />;
  if (data.items.length === 0) return <p className="text-sm text-muted">No hay aportes pendientes.</p>;
  return (
    <ul className="divide-y divide-line/60 text-sm">
      {data.items.map((s) => (
        <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
          <div><span className="font-medium">{s.kind}</span> <code className="text-xs text-muted">{JSON.stringify(s.payload)}</code> <span className="text-xs text-faint">{fmtDateTime(s.created_at)}</span></div>
          <div className="flex gap-1">
            <button type="button" className={btn} onClick={() => act(ctx, () => clientSend("POST", `/admin/submissions/${s.id}/review`, { reason: ctx.reason, approve: true }), "Aporte aprobado y aplicado.", reload)}>Aprobar</button>
            <button type="button" className={btn} onClick={() => act(ctx, () => clientSend("POST", `/admin/submissions/${s.id}/review`, { reason: ctx.reason, approve: false }), "Aporte rechazado.", reload)}>Rechazar</button>
          </div>
        </li>
      ))}
    </ul>
  );
}

function Instances({ ctx }: { ctx: Ctx }) {
  const { data, error, reload } = useLoad<{ instances: (Instance & { game_instance_ids?: number[] })[] }>("/meta/catalog");
  const [ids, setIds] = useState<Record<number, string>>({});
  if (!data) return <Loading error={error} />;
  return (
    <ul className="divide-y divide-line/60 text-sm">
      {data.instances.map((i) => (
        <li key={i.id} className="flex flex-wrap items-center gap-2 py-2">
          <span className="min-w-48">{i.name} <span className="text-xs text-faint">({i.kind})</span></span>
          <Badge status={i.verification} />
          <select aria-label={`Verificación de ${i.name}`} defaultValue={i.verification} onChange={(e) => act(ctx, () => clientSend("PATCH", `/admin/instances/${i.id}`, { reason: ctx.reason, verification: e.target.value }), "Verificación actualizada (rankings reconstruidos).", reload)} className="rounded-md border border-line bg-surface px-2 py-1 text-xs">
            <option value="official">official</option><option value="reported">reported</option><option value="verified_by_admin">verified_by_admin</option>
          </select>
          <input aria-label={`IDs de instancia del juego para ${i.name}`} placeholder="IDs del juego (coma)" value={ids[i.id] ?? ""} onChange={(e) => setIds((s) => ({ ...s, [i.id]: e.target.value }))} className="w-40 rounded-md border border-line bg-surface px-2 py-1 text-xs" />
          <button type="button" className={btn} onClick={() => act(ctx, () => clientSend("PATCH", `/admin/instances/${i.id}`, { reason: ctx.reason, game_instance_ids: (ids[i.id] ?? "").split(",").map((x) => Number(x.trim())).filter((n) => Number.isInteger(n) && n > 0) }), "IDs guardados.", reload)}>Guardar IDs</button>
        </li>
      ))}
    </ul>
  );
}

function Users({ ctx, me }: { ctx: Ctx; me: User }) {
  const { data, error, reload } = useLoad<User[]>("/admin/users");
  const [form, setForm] = useState({ email: "", display_name: "", role: "uploader", password: "" });
  return (
    <div className="space-y-4">
      {!data ? <Loading error={error} /> : (
        <ul className="divide-y divide-line/60 text-sm">
          {data.map((u) => (
            <li key={u.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span>{u.display_name} <span className="text-xs text-muted">{u.email}</span> <Pill>{u.role}</Pill> {!u.is_active && <Pill tone="bad">inactivo</Pill>}</span>
              {u.id !== me.id && (
                <div className="flex gap-1">
                  <button type="button" className={btn} onClick={() => act(ctx, () => clientSend("PATCH", `/admin/users/${u.id}`, { reason: ctx.reason, role: u.role === "admin" ? "uploader" : "admin" }), "Rol actualizado.", reload)}>{u.role === "admin" ? "Hacer uploader" : "Hacer admin"}</button>
                  <button type="button" className={btn} onClick={() => act(ctx, () => clientSend("PATCH", `/admin/users/${u.id}`, { reason: ctx.reason, is_active: !u.is_active }), "Estado actualizado.", reload)}>{u.is_active ? "Desactivar" : "Activar"}</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      <form
        className="grid gap-2 rounded-lg border border-line p-3 sm:grid-cols-5"
        onSubmit={(e) => {
          e.preventDefault();
          void act(ctx, () => clientSend("POST", "/admin/users", { ...form, reason: ctx.reason }), "Usuario creado.", () => { setForm({ email: "", display_name: "", role: "uploader", password: "" }); reload(); });
        }}
      >
        <input aria-label="Email" required type="email" placeholder="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="rounded-md border border-line bg-surface px-2 py-1 text-sm" />
        <input aria-label="Nombre visible" required placeholder="nombre" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} className="rounded-md border border-line bg-surface px-2 py-1 text-sm" />
        <select aria-label="Rol" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className="rounded-md border border-line bg-surface px-2 py-1 text-sm"><option value="uploader">uploader</option><option value="admin">admin</option></select>
        <input aria-label="Contraseña inicial" required type="password" minLength={12} autoComplete="new-password" placeholder="contraseña (12+)" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="rounded-md border border-line bg-surface px-2 py-1 text-sm" />
        <button type="submit" className={btn}>Crear usuario</button>
      </form>
      <div className="flex flex-wrap gap-2">
        {(["real", "demo"] as const).map((d) => (
          <button key={d} type="button" className={btn} onClick={() => act(ctx, () => clientSend("POST", `/admin/rankings/rebuild?dataset=${d}`, { reason: ctx.reason }), `Caché de rankings ${d} reconstruida.`)}>Reconstruir rankings ({d})</button>
        ))}
      </div>
    </div>
  );
}

function Audit() {
  const { data, error } = useLoad<Paged<{ id: number; actor: string; action: string; entity_type: string; entity_id: string; before: unknown; after: unknown; reason: string; created_at: string }>>("/admin/audit", { page_size: 50 });
  if (!data) return <Loading error={error} />;
  if (data.items.length === 0) return <p className="text-sm text-muted">Sin acciones registradas.</p>;
  return (
    <ul className="space-y-2 text-sm">
      {data.items.map((a) => (
        <li key={a.id} className="rounded-md border border-line p-2">
          <p><span className="font-mono text-xs text-arcane">{a.action}</span> · {a.entity_type} #{a.entity_id} · <span className="text-muted">{a.actor}</span> · <span className="text-xs text-faint">{fmtDateTime(a.created_at)}</span></p>
          <p className="text-xs text-muted">Motivo: {a.reason}</p>
          <details className="text-xs"><summary className="cursor-pointer text-faint">Antes / después</summary><pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-faint">{JSON.stringify({ antes: a.before, despues: a.after }, null, 2)}</pre></details>
        </li>
      ))}
    </ul>
  );
}
