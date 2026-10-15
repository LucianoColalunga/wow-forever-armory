import type { Metadata } from "next";

import { InstanceGrid } from "@/components/InstancePage";
import { ErrorState, PageHeader } from "@/components/ui";
import { ApiError, apiGet } from "@/lib/api";
import type { Instance } from "@/lib/types";

export const metadata: Metadata = { title: "Mazmorras" };

export default async function DungeonsPage() {
  let dungeons: Instance[];
  try {
    dungeons = await apiGet<Instance[]>("/dungeons");
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref="/dungeons" />;
  }
  return (
    <>
      <PageHeader
        eyebrow="PvE"
        title="Mazmorras"
        subtitle="Mazmorras de 5 jugadores. Se rankea por jefe; los tiempos de recorrido se muestran como historial (no hay anuncios de Mythic+ ni afijos para Forever)."
      />
      <InstanceGrid items={dungeons} base="dungeons" />
    </>
  );
}
