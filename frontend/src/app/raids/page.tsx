import type { Metadata } from "next";

import { InstanceGrid } from "@/components/InstancePage";
import { ErrorState, PageHeader } from "@/components/ui";
import { ApiError, apiGet } from "@/lib/api";
import type { Instance } from "@/lib/types";

export const metadata: Metadata = { title: "Bandas" };

export default async function RaidsPage() {
  let raids: Instance[];
  try {
    raids = await apiGet<Instance[]>("/raids");
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref="/raids" />;
  }
  return (
    <>
      <PageHeader
        eyebrow="PvE"
        title="Bandas"
        subtitle="Catálogo con su estado de verificación. Los jefes y sus IDs salen de los combat logs importados, nunca se inventan."
      />
      <InstanceGrid items={raids} base="raids" />
    </>
  );
}
