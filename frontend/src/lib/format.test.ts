import { describe, expect, it } from "vitest";

import { fmtBytes, fmtDate, fmtDateTime, fmtDec, fmtDuration, fmtInt, fmtMetric, fmtPct, partitionLabel } from "./format";

describe("formatos es-AR", () => {
  it("separa miles con punto y decimales con coma", () => {
    expect(fmtInt(1234567)).toBe("1.234.567");
    expect(fmtDec(91.666)).toBe("91,7");
    expect(fmtPct(58.5)).toBe("58,5 %");
  });

  it("maneja valores vacíos sin romper", () => {
    expect(fmtInt(null)).toBe("—");
    expect(fmtDec(undefined)).toBe("—");
    expect(fmtInt("no-numero")).toBe("—");
    expect(fmtDate(null)).toBe("—");
  });

  it("formatea duraciones", () => {
    expect(fmtDuration(60000)).toBe("1:00");
    expect(fmtDuration(181_400)).toBe("3:01");
    expect(fmtDuration(3_725_000)).toBe("1:02:05");
  });

  it("formatea fechas en UTC y 24 h", () => {
    expect(fmtDate("2026-10-14T23:30:00Z")).toBe("14/10/2026");
    expect(fmtDateTime("2026-10-14T23:30:00Z")).toContain("23:30");
  });

  it("elige el formato según la métrica", () => {
    expect(fmtMetric("deaths", 2)).toBe("2");
    expect(fmtMetric("dps", 91.666)).toBe("91,7");
    expect(fmtMetric("damage_done", 5500)).toBe("5.500");
    expect(fmtMetric("survival_pct", 100)).toBe("100,0 %");
  });

  it("otros", () => {
    expect(fmtBytes(2048)).toBe("2,0 KB");
    expect(partitionLabel(3, 20)).toBe("20 jugadores · dif. 3");
  });
});
