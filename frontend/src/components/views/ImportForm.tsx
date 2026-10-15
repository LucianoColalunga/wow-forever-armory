"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { clientGet, uploadWithProgress } from "@/lib/client-api";
import { fmtBytes } from "@/lib/format";
import type { User } from "@/lib/types";

const MAX_MB = 200;
const ACCEPT = ".txt,.log,.zip";

type Result = { report_id: string; status: string; duplicate: boolean; dataset: string; message: string };

export function ImportForm() {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    clientGet<User>("/auth/me")
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  function pick(f: File | null) {
    setError(null);
    setResult(null);
    if (!f) return setFile(null);
    const ext = f.name.toLowerCase().slice(f.name.lastIndexOf("."));
    if (!ACCEPT.split(",").includes(ext)) return setError("Formato no permitido: usá .txt, .log o .zip.");
    if (f.size > MAX_MB * 1024 * 1024) return setError(`El archivo supera ${MAX_MB} MB.`);
    if (f.size === 0) return setError("El archivo está vacío.");
    setFile(f);
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!file || !formRef.current) return;
    const form = new FormData(formRef.current);
    form.set("file", file);
    // Los campos opcionales vacíos no se envían (la API los valida como números/enumerados).
    for (const key of ["title", "guild_name", "guild_realm", "region", "utc_offset"]) {
      if (!String(form.get(key) ?? "").trim()) form.delete(key);
    }
    setProgress(0);
    setError(null);
    try {
      const { status, body } = await uploadWithProgress(form, setProgress);
      const detail = body && typeof body === "object" && "detail" in body ? String((body as { detail: unknown }).detail) : null;
      if (status === 200 || status === 202) setResult(body as Result);
      else setError(detail ?? `Error ${status}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error de red.");
    } finally {
      setProgress(null);
    }
  }

  if (user === undefined) return <p className="text-sm text-muted">Verificando sesión…</p>;
  if (user === null)
    return (
      <div className="card p-6 text-sm">
        <p>
          Para importar necesitás una cuenta con rol <strong>uploader</strong> o <strong>admin</strong>.{" "}
          <Link href="/login?next=/import" className="text-gold-strong underline">
            Iniciá sesión
          </Link>
          . Para automatizar subidas podés usar una API key (ver documentación).
        </p>
      </div>
    );

  return (
    <form ref={formRef} onSubmit={submit} className="card space-y-4 p-6" aria-describedby="import-help">
      <div>
        <label htmlFor="file" className="block text-sm font-medium">
          Archivo de combat log
        </label>
        <input
          id="file"
          name="file"
          type="file"
          accept={ACCEPT}
          required
          onChange={(e) => pick(e.target.files?.[0] ?? null)}
          className="mt-1 block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-gold/20 file:px-3 file:py-1.5 file:text-gold-strong"
        />
        <p id="import-help" className="mt-1 text-xs text-faint">
          WoWCombatLog*.txt de la carpeta <code>Logs</code> del cliente (con Advanced Combat Logging activado), o un .zip con un
          único archivo. Máximo {MAX_MB} MB. Se rechazan ejecutables y binarios.
        </p>
        {file && <p className="mt-1 text-xs text-muted">{file.name} · {fmtBytes(file.size)}</p>}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="title" className="block text-sm">Título (opcional)</label>
          <input id="title" name="title" maxLength={128} className="mt-1 w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label htmlFor="visibility" className="block text-sm">Visibilidad</label>
          <select id="visibility" name="visibility" defaultValue="public" className="mt-1 w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm">
            <option value="public">Público (entra en rankings)</option>
            <option value="private">Privado (sólo vos y admins; no entra en rankings)</option>
          </select>
        </div>
        <div>
          <label htmlFor="guild_name" className="block text-sm">Hermandad (opcional)</label>
          <input id="guild_name" name="guild_name" maxLength={64} className="mt-1 w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label htmlFor="guild_realm" className="block text-sm">Reino de la hermandad</label>
          <input id="guild_realm" name="guild_realm" maxLength={64} className="mt-1 w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label htmlFor="region" className="block text-sm">Región</label>
          <select id="region" name="region" defaultValue="" className="mt-1 w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm">
            <option value="">Sin especificar</option>
            <option value="us">Américas (US)</option>
            <option value="eu">Europa (EU)</option>
            <option value="kr">Corea (KR)</option>
            <option value="tw">Taiwán (TW)</option>
          </select>
        </div>
        <div>
          <label htmlFor="utc_offset" className="block text-sm">Huso horario del cliente</label>
          <select id="utc_offset" name="utc_offset" defaultValue="" className="mt-1 w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm" aria-describedby="tz-help">
            <option value="">Lo trae el log</option>
            {Array.from({ length: 27 }, (_, i) => i - 12).map((o) => (
              <option key={o} value={String(o)}>
                UTC{o >= 0 ? "+" : ""}
                {o}
              </option>
            ))}
          </select>
          <p id="tz-help" className="mt-1 text-[11px] text-faint">Sólo para logs viejos sin huso en el timestamp.</p>
        </div>
      </div>
      {progress !== null && (
        <div>
          <div className="h-2 overflow-hidden rounded bg-surface-3" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} aria-label="Progreso de subida">
            <div className="h-full bg-gold transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p className="mt-1 text-xs text-muted">Subiendo… {progress} %</p>
        </div>
      )}
      {error && (
        <p className="rounded-md border border-danger/50 bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">
          {error}
        </p>
      )}
      {result && (
        <div className="rounded-md border border-success/50 bg-success/10 px-3 py-2 text-sm text-success" role="status">
          {result.message}{" "}
          <Link href={`/reports/${result.report_id}`} className="underline">
            Ver reporte {result.report_id}
          </Link>
          {result.dataset === "demo" && <span className="text-demo"> (clasificado como DEMO)</span>}
        </div>
      )}
      <button
        type="submit"
        disabled={!file || progress !== null}
        className="rounded-lg bg-gold px-4 py-2 text-sm font-semibold text-bg hover:bg-gold-strong disabled:cursor-not-allowed disabled:opacity-50"
      >
        Importar
      </button>
    </form>
  );
}
