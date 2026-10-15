import type { Metadata } from "next";

import { DataBanners, EmptyState, ErrorState, PageHeader } from "@/components/ui";
import { type CompareData, CompareView, PlayerPicker } from "@/components/views/CompareView";
import { ApiError, apiGet } from "@/lib/api";
import { first, getDataset } from "@/lib/dataset";
import type { DataMeta } from "@/lib/types";

export const metadata: Metadata = { title: "Comparador" };

export default async function ComparePage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const dataset = await getDataset(sp);
  const ids = (first(sp.ids) ?? "")
    .split(",")
    .map((x) => Number(x))
    .filter((n) => Number.isInteger(n) && n > 0)
    .slice(0, 4);
  let data: (CompareData & { meta: DataMeta }) | null = null;
  let error: string | null = null;
  if (ids.length >= 2) {
    try {
      data = await apiGet<CompareData & { meta: DataMeta }>("/compare", { ids: ids.join(","), dataset });
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Error inesperado.";
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="Herramientas"
        title="Comparador de jugadores"
        subtitle="Hasta 4 personajes. Se comparan mejores marcas y medianas sólo dentro del mismo jefe, dificultad y tamaño de grupo."
      />
      <PlayerPicker ids={ids} dataset={dataset} />
      {error && <ErrorState message={error} />}
      {data && <DataBanners meta={data.meta} />}
      {ids.length < 2 && <EmptyState title="Elegí al menos 2 personajes">Buscalos por nombre en el campo de arriba.</EmptyState>}
      {data && (data.partitions.length === 0 ? <EmptyState title="Estos personajes no tienen kills rankeables" /> : <CompareView data={data} />)}
    </>
  );
}
