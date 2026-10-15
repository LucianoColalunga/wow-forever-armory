"use client";

export default function ErrorBoundary({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="card border-danger/40 p-6" role="alert">
      <h1 className="font-display text-xl text-danger">Algo salió mal</h1>
      <p className="mt-2 text-sm text-muted">
        {error.message.includes("API") ? error.message : "No se pudo cargar esta página. Probá de nuevo en unos segundos."}
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-4 rounded-md border border-gold px-3 py-1.5 text-sm text-gold-strong hover:bg-gold/10"
      >
        Reintentar
      </button>
    </div>
  );
}
