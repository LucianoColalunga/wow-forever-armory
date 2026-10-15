"use client";

import { usePathname, useRouter } from "next/navigation";
import { useTransition } from "react";

import type { Dataset } from "@/lib/types";

export function DatasetToggle({ dataset }: { dataset: Dataset }) {
  const router = useRouter();
  const pathname = usePathname();
  const [pending, start] = useTransition();

  function choose(next: Dataset) {
    document.cookie = `wfa_dataset=${next}; path=/; max-age=${60 * 60 * 24 * 180}; samesite=lax`;
    start(() => {
      // Se quita ?dataset= para que mande la preferencia elegida.
      const params = new URLSearchParams(window.location.search);
      params.delete("dataset");
      params.delete("page");
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname);
      router.refresh();
    });
  }

  return (
    <div role="group" aria-label="Conjunto de datos" className="flex rounded-lg border border-line p-0.5 text-xs">
      {(["real", "demo"] as const).map((d) => (
        <button
          key={d}
          type="button"
          onClick={() => choose(d)}
          aria-pressed={dataset === d}
          disabled={pending}
          className={`rounded-md px-2.5 py-1 font-medium transition-colors ${
            dataset === d
              ? d === "demo"
                ? "bg-demo/20 text-demo"
                : "bg-gold/20 text-gold-strong"
              : "text-muted hover:text-ink"
          }`}
        >
          {d === "real" ? "Datos reales" : "Demo"}
        </button>
      ))}
    </div>
  );
}
