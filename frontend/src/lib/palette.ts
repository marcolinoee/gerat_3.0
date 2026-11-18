import type { FuelType } from "@/types/api";

export const ENERGY_COLORS = {
  HYDRO: "#0284c7",
  COAL: "#d97706",
  OIL: "#ea580c",
  NUCLEAR: "#4f46e5",
  GAS: "#059669",
  OTHER: "#64748b",
  DEFICIT: "#dc2626",
} as const;

export const FUEL_LABELS: Record<FuelType, string> = {
  NUCLEAR: "Nuclear",
  COAL: "Carvão",
  GAS: "Gás Natural",
  OIL: "Óleo",
  OTHER: "Outras",
};

export const MONTHS_PT = [
  "Jan",
  "Fev",
  "Mar",
  "Abr",
  "Mai",
  "Jun",
  "Jul",
  "Ago",
  "Set",
  "Out",
  "Nov",
  "Dez",
];

export function fmtNum(val: number | undefined | null, digits = 1): string {
  if (val === undefined || val === null || Number.isNaN(val)) return "—";
  return val.toLocaleString("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}
