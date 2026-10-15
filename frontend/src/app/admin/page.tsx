import type { Metadata } from "next";

import { PageHeader } from "@/components/ui";
import { AdminPanel } from "@/components/views/AdminPanel";

export const metadata: Metadata = { title: "Panel admin", robots: { index: false, follow: false } };

export default function AdminPage() {
  return (
    <>
      <PageHeader
        eyebrow="Administración"
        title="Panel admin"
        subtitle="Cada corrección exige un motivo y queda en el registro de auditoría con el estado anterior y el nuevo."
      />
      <AdminPanel />
    </>
  );
}
