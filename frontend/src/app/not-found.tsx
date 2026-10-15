import Link from "next/link";

import { EmptyState } from "@/components/ui";

export default function NotFound() {
  return (
    <EmptyState title="No encontramos lo que buscabas">
      Puede que no exista en el conjunto de datos activo (real o demo) o que esté oculto por privacidad.{" "}
      <Link href="/" className="text-gold-strong underline">
        Volver al inicio
      </Link>
    </EmptyState>
  );
}
