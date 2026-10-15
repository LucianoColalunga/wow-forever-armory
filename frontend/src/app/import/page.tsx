import type { Metadata } from "next";

import { Card, PageHeader } from "@/components/ui";
import { ImportForm } from "@/components/views/ImportForm";

export const metadata: Metadata = { title: "Importar combat log" };

export default function ImportPage() {
  return (
    <>
      <PageHeader
        eyebrow="Importador"
        title="Importar combat log"
        subtitle="El archivo se valida, se guarda con su hash (para trazabilidad y deduplicación) y se procesa en segundo plano con reintentos."
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ImportForm />
        </div>
        <Card title="Cómo grabar el log">
          <ol className="list-decimal space-y-2 pl-4 text-sm text-muted">
            <li>
              En el juego: <em>Opciones → Red → Advanced Combat Logging</em> activado (sin esto no hay dueño de mascotas ni vida
              del jefe).
            </li>
            <li>
              Escribí <code>/combatlog</code> antes del primer pull (o usá un addon que lo active al entrar a la instancia).
            </li>
            <li>
              Al terminar, subí el archivo <code>WoWCombatLog-*.txt</code> de la carpeta <code>Logs</code> del cliente de Forever.
            </li>
            <li>Si otra persona ya subió el mismo combate, se detecta como duplicado y no cuenta dos veces.</li>
          </ol>
        </Card>
      </div>
    </>
  );
}
