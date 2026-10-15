"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { clientGet } from "@/lib/client-api";

/** Consulta el estado del procesamiento y refresca la página cuando termina. */
export function ReportStatusPoller({ reportId }: { reportId: string }) {
  const router = useRouter();
  const [status, setStatus] = useState("queued");
  const [attempts, setAttempts] = useState(0);

  useEffect(() => {
    let stop = false;
    let delay = 1500;
    async function tick() {
      if (stop) return;
      try {
        const s = await clientGet<{ status: string; attempts: number }>(`/reports/${reportId}/status`);
        setStatus(s.status);
        setAttempts(s.attempts);
        if (!["queued", "processing"].includes(s.status)) {
          router.refresh();
          return;
        }
      } catch {
        /* reintenta en el próximo ciclo */
      }
      delay = Math.min(delay * 1.4, 10000);
      setTimeout(tick, delay);
    }
    const t = setTimeout(tick, delay);
    return () => {
      stop = true;
      clearTimeout(t);
    };
  }, [reportId, router]);

  return (
    <p className="mb-4 flex items-center gap-2 rounded-lg border border-arcane/50 bg-arcane/10 px-4 py-2 text-sm text-arcane" role="status" aria-live="polite">
      <span className="h-2 w-2 animate-pulse rounded-full bg-arcane" aria-hidden="true" />
      {status === "processing" ? "Procesando el log…" : "En cola para procesar…"}
      {attempts > 1 ? ` (intento ${attempts})` : ""}
    </p>
  );
}
