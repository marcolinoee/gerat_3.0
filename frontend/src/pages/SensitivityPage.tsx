import React, { useEffect, useMemo, useRef, useState } from "react";
import type * as echarts from "echarts";
import { Download, Pause, Play, Square } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { EChartBox } from "@/components/charts/EChartBox";
import { Badge, Button, Card, CardHeader } from "@/components/ui/primitives";
import { ENERGY_COLORS, fmtNum } from "@/lib/palette";
import type { SensitivityResponse } from "@/types/api";

interface SensitivityPageProps {
  projectId: string;
  dark: boolean;
}

export function SensitivityPage({ projectId, dark }: SensitivityPageProps) {
  const [interestRate, setInterestRate] = useState(10);
  const [mode, setMode] = useState<"unit" | "total">("unit");
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<1 | 2 | 4 | 8>(1);
  const chartRef = useRef<echarts.ECharts | null>(null);

  const { data } = useQuery({
    queryKey: ["sensitivity", projectId, interestRate],
    queryFn: () =>
      apiFetch<SensitivityResponse>(
        `/projects/${projectId}/sensitivity?interest_rate_pct=${interestRate}&steps=37`
      ),
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!playing) return;
    const intervalMs = Math.round(700 / speed);
    const id = window.setInterval(() => {
      setInterestRate((prev) => {
        const next = Number((prev + 0.5).toFixed(1));
        if (next > 24) {
          setPlaying(false);
          return 24;
        }
        return next;
      });
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [playing, speed]);

  const option = useMemo(() => {
    const series = (data?.series ?? []).map((s) => ({
      name: s.name,
      type: "line",
      showSymbol: false,
      lineStyle: { width: 2.5, color: ENERGY_COLORS[s.fuel_type] },
      itemStyle: { color: ENERGY_COLORS[s.fuel_type] },
      data: s.points.map((p) => [
        p.hours,
        mode === "unit"
          ? Number(p.unit_cost_usd_kw_year.toFixed(2))
          : Number(p.total_cost_kusd.toFixed(2)),
      ]),
    }));

    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
      },
      legend: { bottom: 32 },
      grid: { top: 28, left: 72, right: 28, bottom: 72 },
      dataZoom: [
        { type: "inside" },
        { type: "slider", height: 18, bottom: 6 },
      ],
      xAxis: {
        type: "value",
        name: "Horas de Operação (h/ano)",
        min: 0,
        max: 8640,
      },
      yAxis: {
        type: "value",
        name: mode === "unit" ? "US$/kW·ano" : "1000 US$/ano",
      },
      series,
    };
  }, [data, mode]);

  function exportPng() {
    if (!chartRef.current) return;
    const url = chartRef.current.getDataURL({
      type: "png",
      pixelRatio: 2,
      backgroundColor: dark ? "#0f172a" : "#ffffff",
    });
    const a = document.createElement("a");
    a.href = url;
    a.download = `screening_curves_${interestRate}pct.png`;
    a.click();
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Análise de Sensibilidade — Screening Curves"
          description="C_total,j(h, i) = CF_j(i) + C_comb,j · P_inst,j · h para h ∈ [0, 8640] h/ano"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-700 p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setMode("unit")}
                  className={`px-2.5 py-1 rounded-md ${
                    mode === "unit"
                      ? "bg-sky-600 text-white"
                      : "text-slate-600 dark:text-slate-300"
                  }`}
                >
                  US$/kW·ano
                </button>
                <button
                  type="button"
                  onClick={() => setMode("total")}
                  className={`px-2.5 py-1 rounded-md ${
                    mode === "total"
                      ? "bg-sky-600 text-white"
                      : "text-slate-600 dark:text-slate-300"
                  }`}
                >
                  1000 US$/ano
                </button>
              </div>
              <Button size="sm" variant="outline" onClick={exportPng}>
                <Download className="h-3.5 w-3.5" /> Exportar PNG
              </Button>
            </div>
          }
        />

        <div className="p-5 space-y-5">
          {/* Slider + Animation Controls */}
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 p-4">
            <div className="flex-1 min-w-[240px]">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="font-medium text-slate-700 dark:text-slate-300">
                  Taxa de Juros Anual (i)
                </span>
                <Badge tone="sky" className="tabular-nums text-xs">
                  {fmtNum(interestRate, 1)}% a.a.
                </Badge>
              </div>
              <input
                type="range"
                min={0}
                max={24}
                step={0.5}
                value={interestRate}
                onChange={(e) => {
                  setPlaying(false);
                  setInterestRate(Number(e.target.value));
                }}
                className="w-full accent-sky-600"
              />
            </div>

            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  if (interestRate >= 24) setInterestRate(2);
                  setPlaying(true);
                }}
                disabled={playing}
              >
                <Play className="h-3.5 w-3.5" /> Play
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setPlaying(false)}
                disabled={!playing}
              >
                <Pause className="h-3.5 w-3.5" /> Pause
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setPlaying(false);
                  setInterestRate(10);
                }}
              >
                <Square className="h-3.5 w-3.5" /> Stop
              </Button>

              <div className="inline-flex rounded-lg border border-slate-300 dark:border-slate-700 overflow-hidden text-xs ml-1">
                {([1, 2, 4, 8] as const).map((sp) => (
                  <button
                    key={sp}
                    type="button"
                    onClick={() => setSpeed(sp)}
                    className={`px-2 py-1 font-medium tabular-nums ${
                      speed === sp
                        ? "bg-sky-600 text-white"
                        : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300"
                    }`}
                  >
                    {sp}x
                  </button>
                ))}
              </div>
            </div>
          </div>

          <EChartBox
            option={option}
            height={420}
            dark={dark}
            onChartReady={(inst) => {
              chartRef.current = inst;
            }}
          />
        </div>
      </Card>

      {/* FRC & Cost Parameters */}
      {data && data.series.length > 0 && (
        <Card>
          <CardHeader title={`Parâmetros Econômicos para i = ${fmtNum(interestRate, 1)}% a.a.`} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular-nums">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-xs text-slate-500">
                  <th className="py-2.5 px-4 text-left">Usina</th>
                  <th className="py-2.5 px-4 text-right">Potência (MW)</th>
                  <th className="py-2.5 px-4 text-right">FRC</th>
                  <th className="py-2.5 px-4 text-right">Custo Fixo Anual (kUS$)</th>
                  <th className="py-2.5 px-4 text-right">Custo Variável (US$/MWh)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {data.series.map((s) => (
                  <tr key={s.plant_id}>
                    <td className="py-2 px-4 font-medium flex items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: ENERGY_COLORS[s.fuel_type] }}
                      />
                      {s.name}
                    </td>
                    <td className="py-2 px-4 text-right">{fmtNum(s.installed_power_mw, 1)}</td>
                    <td className="py-2 px-4 text-right">{fmtNum(s.frc, 4)}</td>
                    <td className="py-2 px-4 text-right">{fmtNum(s.fixed_cost_usd_year / 1000, 2)}</td>
                    <td className="py-2 px-4 text-right">{fmtNum(s.variable_cost_usd_mwh, 2)}</td>
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
