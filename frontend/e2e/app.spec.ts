import path from "node:path";

import { expect, type Page, test } from "@playwright/test";

const FIXTURES = path.resolve(__dirname, "../../backend/tests/fixtures/logs");

async function useDataset(page: Page, dataset: "real" | "demo") {
  await page.context().addCookies([{ name: "wfa_dataset", value: dataset, url: page.url() === "about:blank" ? "http://127.0.0.1:3100" : page.url() }]);
}

async function login(page: Page) {
  await page.goto("/login?next=/admin");
  await page.getByLabel("Email").fill(process.env.E2E_ADMIN_EMAIL!);
  await page.getByLabel("Contraseña").fill(process.env.E2E_ADMIN_PASSWORD!);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await page.waitForURL((u) => u.pathname === "/admin");
}

test("dashboard con datos reales y cambio a demo con aviso visible", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Panorama competitivo" })).toBeVisible();
  await expect(page.getByText("Datos de demostración.")).toHaveCount(0);
  await expect(page.locator(".card").filter({ has: page.getByText("Reportes", { exact: true }) })).toContainText("3");
  await page.getByRole("button", { name: "Demo" }).click();
  await expect(page.getByText("Datos de demostración.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Demo" })).toHaveAttribute("aria-pressed", "true");
});

test("ranking general: cambiar método actualiza URL y explicación", async ({ page }) => {
  await useDataset(page, "demo");
  await page.goto("/rankings/pve");
  await expect(page.getByText("A · Pico · DPS")).toBeVisible();
  await page.getByLabel("Método").selectOption("percentile");
  await expect(page).toHaveURL(/method=percentile/);
  await expect(page.getByText("C · Percentil · DPS")).toBeVisible();
  await expect(page.getByText("Registros usados")).toBeVisible();
});

test("ranking por jefe con tabla ordenable por teclado", async ({ page }) => {
  await useDataset(page, "real");
  await page.goto("/raids/hyjal-summit");
  await page.getByRole("link", { name: "Ranking", exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "Test Guardian" })).toBeVisible();
  const first = page.getByRole("row").nth(1);
  await expect(first).toContainText("Brakka");
  const header = page.getByRole("columnheader", { name: /DPS/ });
  await header.getByRole("button").focus();
  await page.keyboard.press("Enter");
  await expect(header).toHaveAttribute("aria-sort", "descending");
  await page.keyboard.press("Enter");
  await expect(header).toHaveAttribute("aria-sort", "ascending");
});

test("buscador global lleva al perfil del personaje", async ({ page }) => {
  await useDataset(page, "real");
  await page.goto("/");
  await page.getByLabel("Buscar personajes, hermandades, jefes o reportes").fill("Brakk");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/search\?q=Brakk/);
  await page.getByRole("link", { name: /Brakka/ }).first().click();
  await expect(page.getByRole("heading", { name: "Brakka" })).toBeVisible();
  await expect(page.getByText("Armas Guerrero")).toBeVisible();
});

test("detalle de combate separa curación efectiva y absorciones", async ({ page }) => {
  await useDataset(page, "real");
  await page.goto("/encounters?kind=encounter&success=true");
  // El kill de basic_kill dura 1:00 (el de wipe_then_kill, 0:40).
  await page.getByRole("row").filter({ hasText: "1:00" }).getByRole("link", { name: "Test Guardian" }).click();
  await page.getByRole("tab", { name: "Curación y absorciones" }).click();
  const row = page.getByRole("row", { name: /Lumen/ });
  await expect(row).toContainText("3.500"); // curación efectiva
  await expect(row).toContainText("1.700"); // absorciones (no sumadas)
  await expect(page.getByText("Trazabilidad")).toBeVisible();
});

test("panel admin protegido: redirige y rechaza credenciales inválidas", async ({ page }) => {
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/login\?next=%2Fadmin/);
  await page.getByLabel("Email").fill("nadie@example.com");
  await page.getByLabel("Contraseña").fill("incorrecta-123");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "incorrectos" })).toBeVisible();
});

test("admin: acción auditada con motivo obligatorio", async ({ page }) => {
  await login(page);
  await page.getByRole("tab", { name: "Usuarios" }).click();
  await page.getByRole("button", { name: "Reconstruir rankings (real)" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "motivo" })).toBeVisible();
  await page.getByLabel(/Motivo de la acción/).fill("Prueba end-to-end de auditoría");
  await page.getByRole("button", { name: "Reconstruir rankings (real)" }).click();
  await expect(page.getByRole("status").filter({ hasText: "reconstruida" })).toBeVisible();
  await page.getByRole("tab", { name: "Auditoría" }).click();
  await expect(page.getByText("rankings.rebuild").first()).toBeVisible();
  await expect(page.getByText("Motivo: Prueba end-to-end de auditoría").first()).toBeVisible();
});

test("importador: archivo válido se procesa y uno inválido se rechaza", async ({ page }) => {
  await login(page);
  await page.goto("/import");
  await page.getByLabel("Archivo de combat log").setInputFiles(path.join(FIXTURES, "quoted_names.txt"));
  await page.getByRole("button", { name: "Importar" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Archivo recibido" })).toBeVisible();
  await page.getByRole("link", { name: /Ver reporte/ }).click();
  await expect(page.getByText("Procesado")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Training, the Dummy").first()).toBeVisible();

  await page.goto("/import");
  await page.getByLabel("Archivo de combat log").setInputFiles({
    name: "virus.txt",
    mimeType: "text/plain",
    buffer: Buffer.concat([Buffer.from("MZ"), Buffer.alloc(64)]),
  });
  await page.getByRole("button", { name: "Importar" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "ejecutable" })).toBeVisible();
});

test("accesibilidad básica: enlace para saltar al contenido", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Saltar al contenido" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#contenido$/);
});
