import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/ui";
import { LoginForm } from "@/components/views/LoginForm";

export const metadata: Metadata = { title: "Ingresar" };

export default function LoginPage() {
  return (
    <div className="mx-auto max-w-md">
      <PageHeader title="Ingresar" subtitle="Acceso para cuentas uploader y admin. No hay registro público: un admin crea las cuentas." />
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  );
}
