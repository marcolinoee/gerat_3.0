import React, { useMemo, useState } from "react";
import { Upload, Waves } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { EChartBox } from "@/components/charts/EChartBox";
import { Badge, Button, Card, CardHeader, Select } from "@/components/ui/primitives";
import { ENERGY_COLORS, fmtNum } from "@/lib/palette";
import type { HydroPlant, InflowPoint } from "@/types/api";

interface InflowsPageProps {
  projectId: string;
  readOnly: boolean;
  dark: boolean;
}

export function InflowsPage({ projectId, readOnly, dark }: InflowsPageProps) {
  const qc = useQueryClient();
  const [selectedPlantId, setSelectedPlantId] = useState<string>("");
  const [isIncremental, setIsIncremental] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data: plants = [] } = useQuery({
    queryKey: ["hydro", projectId],
    queryFn: () => apiFetch<HydroPlant[]>(`/projects/${projectId}/hydro-plants`),
  });

  const activePlantId = selectedPlantId || plants[0]?.id || "";

  const { data: inflows = [] } = useQuery({
    queryKey: ["inflows", projectId, activePlantId],
    queryFn: () =>
      apiFetch<InflowPoint[]>(
        `/projects/${projectId}/hydro-plants/${activePlantId}/inflows`
      ),
    enabled: Boolean(activePlantId),
  });

  const uploadMut = useMutation({
    mutationFn: async () => {
      if (!file || !activePlantId) throw new Error("Selecione usina e arquivo.");
      if (file.size > 5 * 1024 * 1024) {
        throw new Error("Arquivo excede o limite máximo de 5 MB.");
      }
      const fd = new FormData();
      fd.append("file", file);
      fd.append("is_incremental", String(isIncremental));
      return apiFetch<{ records_imported: number; start_year: number; end_year: number }>(
        `/projects/${projectId}/hydro-plants/${activePlantId}/inflows/upload`,
        { method: "POST", body: fd }
      );
    },
    onSuccess: (res) => {
      setErrorMsg(null);
      setStatusMsg(
        `Importados ${res.records_imported} registros mensais (${res.start_year}–${res.end_year}).`
      );
      setFile(null);
      qc.invalidateQueries({ queryKey: ["inflows", projectId, activePlantId] });
    },
    onError: (err: Error) => {
      setStatusMsg(null);
      setErrorMsg(err.message);
    },
  });

  const chartOption = useMemo(() => {
    const labels = inflows.map((r) => `${r.year}-${String(r.month).padStart(2, "0")}`);
    const flows = inflows.map((r) => r.flow_m3s);
    return {
      tooltip: { trigger: "axis" },
      grid: { top: 24, left: 56, right: 24, bottom: 48 },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 20, bottom: 4 }],
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value", name: "Vazão (m³/s)" },
      series: [
        {
          name: inflows[0]?.is_incremental ? "Vazão Incremental (m³/s)" : "Vazão Natural Total (m³/s)",
          type: "line",
          smooth: true,
          showSymbol: false,
          lineStyle: { color: ENERGY_COLORS.HYDRO, width: 2 },
          areaStyle: { color: "rgba(2, 132, 199, 0.14)" },
          data: flows,
        },
      ],
    };
  }, [inflows]);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Séries Históricas de Vazões (vazoes.txt / CSV / XLSX)"
          description="Suporte ao formato clássico de 13 colunas (ANO + Jan..Dez) ou formato longo (year, month, flow_m3s) — limite 5 MB"
        />
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
            <div>
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
                Usina Hidrelétrica
              </label>
              <Select
                value={activePlantId}
                onChange={(e) => setSelectedPlantId(e.target.value)}
              >
                {plants.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </div>

            {!readOnly && (
              <>
                <div>
                  <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
                    Arquivo de Vazões (.txt, .csv, .xlsx)
                  </label>
                  <input
                    type="file"
                    accept=".txt,.csv,.xlsx"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="block w-full text-xs text-slate-600 dark:text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-sky-50 dark:file:bg-sky-900/40 file:text-sky-700 dark:file:text-sky-300 file:font-medium hover:file:bg-sky-100"
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <label className="inline-flex items-center gap-2 text-xs text-slate-700 dark:text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isIncremental}
                      onChange={(e) => setIsIncremental(e.target.checked)}
                      className="rounded border-slate-300"
                    />
                    Vazão Incremental (usa Σρ cascata)
                  </label>
                  <Button
                    onClick={() => uploadMut.mutate()}
                    disabled={!file || uploadMut.isPending}
                  >
                    <Upload className="h-4 w-4" /> Importar
                  </Button>
                </div>
              </>
            )}
          </div>

          {statusMsg && (
            <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-300">
              {statusMsg}
            </div>
          )}
          {errorMsg && (
            <div className="rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 px-3 py-2 text-xs text-red-700 dark:text-red-300">
              {errorMsg}
            </div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Hidrograma da Série Carregada"
          action={
            inflows.length > 0 ? (
              <div className="flex items-center gap-2">
                <Badge tone={inflows[0].is_incremental ? "amber" : "sky"}>
                  {inflows[0].is_incremental ? "Incremental (Q_inc)" : "Natural Total (Q_nat)"}
                </Badge>
                <Badge className="tabular-nums">{inflows.length} meses</Badge>
              </div>
            ) : null
          }
        />
        <div className="p-4">
          {inflows.length === 0 ? (
            <div className="py-12 text-center text-sm text-slate-500 flex flex-col items-center gap-2">
              <Waves className="h-6 w-6 text-slate-400" />
              Nenhuma série de vazões carregada para esta usina.
            </div>
          ) : (
            <EChartBox option={chartOption} height={340} dark={dark} />
          )}
        </div>
      </Card>

      {inflows.length > 0 && (
        <Card>
          <CardHeader title="Amostra dos Registros (Últimos 24 meses)" />
          <div className="overflow-x-auto">
            <table className="w-full text-xs tabular-nums">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500">
                  <th className="py-2 px-4 text-left">Ano</th>
                  <th className="py-2 px-4 text-left">Mês</th>
                  <th className="py-2 px-4 text-right">Vazão (m³/s)</th>
                  <th className="py-2 px-4 text-left">Tipo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {inflows.slice(-24).map((r) => (
                  <tr key={`${r.year}-${r.month}`}>
                    <td className="py-2 px-4">{r.year}</td>
                    <td className="py-2 px-4">{String(r.month).padStart(2, "0")}</td>
                    <td className="py-2 px-4 text-right font-medium">{fmtNum(r.flow_m3s, 2)}</td>
                    <td className="py-2 px-4">{r.is_incremental ? "Incremental" : "Natural"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
