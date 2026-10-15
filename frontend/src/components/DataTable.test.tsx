import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { type Column, DataTable } from "./DataTable";

interface Row {
  id: number;
  name: string;
  dps: number;
}

const rows: Row[] = [
  { id: 1, name: "Brakka", dps: 91.7 },
  { id: 2, name: "Ignis", dps: 55 },
  { id: 3, name: "Arrowyn", dps: 36.7 },
];

const columns: Column<Row>[] = [
  { key: "name", label: "Jugador", sortValue: (r) => r.name, render: (r) => r.name },
  { key: "dps", label: "DPS", align: "right", sortValue: (r) => r.dps, render: (r) => r.dps.toFixed(1) },
];

function names() {
  return screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);
}

describe("DataTable", () => {
  it("ordena al hacer clic y expone aria-sort", async () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} caption="Prueba" initialSort={{ key: "dps", dir: "desc" }} />);
    expect(names()).toEqual(["Brakka", "Ignis", "Arrowyn"]);
    const dpsHeader = screen.getByRole("columnheader", { name: /DPS/ });
    expect(dpsHeader).toHaveAttribute("aria-sort", "descending");
    await userEvent.click(within(dpsHeader).getByRole("button"));
    expect(names()).toEqual(["Arrowyn", "Ignis", "Brakka"]);
    expect(dpsHeader).toHaveAttribute("aria-sort", "ascending");
  });

  it("se puede ordenar con el teclado", async () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} caption="Prueba" />);
    const btn = within(screen.getByRole("columnheader", { name: /Jugador/ })).getByRole("button");
    btn.focus();
    await userEvent.keyboard("{Enter}");
    expect(names()).toEqual(["Ignis", "Brakka", "Arrowyn"]);
  });

  it("filtra la página actual", async () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} caption="Prueba" filterText={(r) => r.name} />);
    await userEvent.type(screen.getByLabelText("Filtrar esta página"), "ign");
    expect(names()).toEqual(["Ignis"]);
    expect(screen.getByText("1 de 3")).toBeInTheDocument();
  });

  it("muestra estado vacío", () => {
    render(<DataTable columns={columns} rows={[]} rowKey={(r) => r.id} caption="Prueba" emptyMessage="Nada por acá" />);
    expect(screen.getByText("Nada por acá")).toBeInTheDocument();
  });

  it("no ejecuta HTML de los datos (los nombres se muestran como texto)", () => {
    const evil = [{ id: 9, name: "<img src=x onerror=alert(1)>", dps: 1 }];
    const { container } = render(<DataTable columns={columns} rows={evil} rowKey={(r) => r.id} caption="Prueba" />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
  });
});
