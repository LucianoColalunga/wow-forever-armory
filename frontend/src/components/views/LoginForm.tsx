"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ClientApiError, clientSend } from "@/lib/client-api";

export function LoginForm() {
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Hasta hidratar, el botón queda deshabilitado: un envío nativo (sin JS) podría exponer datos en la URL.
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await clientSend("POST", "/auth/login", { email: data.get("email"), password: data.get("password") });
      const next = params.get("next");
      // Sólo rutas internas (evita redirecciones abiertas).
      window.location.href = next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
    } catch (err) {
      setError(err instanceof ClientApiError ? err.message : "No se pudo iniciar sesión.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} method="post" action="/login" className="card space-y-4 p-6" noValidate>
      <div>
        <label htmlFor="email" className="block text-sm">
          Email
        </label>
        <input id="email" name="email" type="email" autoComplete="username" required className="mt-1 w-full rounded-md border border-line bg-surface px-3 py-2 text-sm" />
      </div>
      <div>
        <label htmlFor="password" className="block text-sm">
          Contraseña
        </label>
        <input id="password" name="password" type="password" autoComplete="current-password" required className="mt-1 w-full rounded-md border border-line bg-surface px-3 py-2 text-sm" />
      </div>
      {error && (
        <p className="rounded-md border border-danger/50 bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={busy || !ready} className="w-full rounded-lg bg-gold px-4 py-2 text-sm font-semibold text-bg hover:bg-gold-strong disabled:opacity-60">
        {busy ? "Ingresando…" : "Ingresar"}
      </button>
    </form>
  );
}
