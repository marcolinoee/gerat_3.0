import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  DollarSign,
  Droplets,
  Flame,
  Pause,
  Play,
  Square,
  Zap,
} from "lucide-react";
import { EChartBox } from "@/components/charts/EChartBox";
import { Badge, Button, Card, CardHeader } from "@/components/ui/primitives";
import { ENERGY_COLORS, FUEL_LABELS, fmtNum } from "@/lib/palette";
import type { SimulationRun, ThermalPlant } from "@/types/api";

interface DashboardPageProps {
  latestRun: SimulationRun | null;
  thermalPlants: ThermalPlant[];
  dark: boolean;
  onRunSimulation: () => void;
  running: boolean;
}

export function DashboardPage({
  latestRun,
  thermalPlants,
  dark,
  onRunSimulation,
  running,
}: DashboardPageProps) {
  const monthly = latestRun?.monthly_results ?? [];
  const summary = latestRun?.summary;

  const [isPlaying, setIsPlaying] = useState(false);
  const [frameIdx, setFrameIdx] = useState<number>(monthly.length);

  useEffect(() => {
    setFrameIdx(monthly.length);
    setIsPlaying(false);
  }, [latestRun?.id, monthly.length]);

  useEffect(() => {
    if (!isPlaying || monthly.length === 0) return;
    const timer = window.setInterval(() => {
      setFrameIdx((prev) => {
        if (prev >= monthly.length) {
          setIsPlaying(false);
          return monthly.length;
        }
        return prev + 1;
      });
    }, 140);
    return () => window.clearInterval(timer);
  }, [isPlaying, monthly.length]);

  const visibleMonthly = useMemo(
    () => monthly.slice(0, Math.max(1, frameIdx)),
    [monthly, frameIdx]
  );

  const thermalMeta = useMemo(() => {
    const map: Record<string, ThermalPlant> = {};
    for (const t of thermalPlants) map[t.id] = t;
    return map;
  }, [thermalPlants]);

  const storageOption = useMemo(() => {
    const labels = visibleMonthly.map(
      (r) => `${r.year}-${String(r.month).padStart(2, "0")}`
    );
    const earmPct = visibleMonthly.map((r) => Number(r.earm_pct.toFixed(2)));
    const enat = visibleMonthly.map((r) => Number(r.enat_mwm.toFixed(1)));

    const cp = summary?.critical_period;
    const markAreaData: unknown[] = [];
    if (cp && visibleMonthly.length > 0) {
      const startLabel = `${cp.start_year}-${String(cp.start_month).padStart(2, "0")}`;
      const endLabel = `${cp.end_year}-${String(cp.end_month).padStart(2, "0")}`;
      if (labels.includes(startLabel) && labels.includes(endLabel)) {
        markAreaData.push([
          {
            name: "Período Crítico",
            xAxis: startLabel,
            itemStyle: { color: "rgba(220, 38, 38, 0.14)" },
          },
          { xAxis: endLabel },
        ]);
      }
    }

    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0 },
      grid: { top: 28, left: 56, right: 56, bottom: 48 },
      xAxis: { type: "category", data: labels },
      yAxis: [
        { type: "value", name: "EA (%)", min: 0, max: 100 },
        { type: "value", name: "ENA (MWmês)" },
      ],
      series: [
        {
          name: "Armazenamento (%)",
          type: "line",
          yAxisIndex: 0,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2.5, color: ENERGY_COLORS.HYDRO },
          areaStyle: { color: "rgba(2, 132, 199, 0.16)" },
          data: earmPct,
          markArea: markAreaData.length ? { data: markAreaData } : undefined,
        },
        {
          name: "ENA (MWmês)",
          type: "bar",
          yAxisIndex: 1,
          itemStyle: { color: "rgba(5, 150, 105, 0.35)" },
          data: enat,
        },
      ],
    };
  }, [visibleMonthly, summary?.critical_period]);

  const dispatchOption = useMemo(() => {
    const labels = visibleMonthly.map(
      (r) => `${r.year}-${String(r.month).padStart(2, "0")}`
    );
    const loadVal = latestRun?.config_snapshot.load_mwm ?? 0;

    const hydroData = visibleMonthly.map((r) => Number(r.gh_delivered_mwm.toFixed(1)));
    const deficitData = visibleMonthly.map((r) => Number(r.deficit_mwm.toFixed(1)));

    const fuelOrder = ["NUCLEAR", "COAL", "GAS", "OIL", "OTHER"] as const;
    const fuelSeries: Record<string, number[]> = {};
    for (const f of fuelOrder) fuelSeries[f] = new Array(visibleMonthly.length).fill(0);

    visibleMonthly.forEach((r, idx) => {
      Object.entries(r.thermal_dispatch_by_plant || {}).forEach(([pid, val]) => {
        const ft = thermalMeta[pid]?.fuel_type ?? "OTHER";
        fuelSeries[ft][idx] += Number(val);
      });
    });

    const series: Record<string, unknown>[] = [
      {
        name: "Hidráulica",
        type: "line",
        stack: "gen",
        areaStyle: {},
        showSymbol: false,
        itemStyle: { color: ENERGY_COLORS.HYDRO },
        data: hydroData,
      },
    ];

    for (const f of fuelOrder) {
      if (fuelSeries[f].some((v) => v > 0)) {
        series.push({
          name: FUEL_LABELS[f],
          type: "line",
          stack: "gen",
          areaStyle: {},
          showSymbol: false,
          itemStyle: { color: ENERGY_COLORS[f] },
          data: fuelSeries[f].map((v) => Number(v.toFixed(1))),
        });
      }
    }

    if (deficitData.some((v) => v > 0)) {
      series.push({
        name: "Déficit",
        type: "line",
        stack: "gen",
        areaStyle: {},
        showSymbol: false,
        itemStyle: { color: ENERGY_COLORS.DEFICIT },
        data: deficitData,
      });
    }

    series.push({
      name: "Carga",
      type: "line",
      showSymbol: false,
      lineStyle: { color: dark ? "#f8fafc" : "#0f172a", type: "dashed", width: 2 },
      data: visibleMonthly.map(() => loadVal),
    });

    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0 },
      grid: { top: 24, left: 60, right: 24, bottom: 52 },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value", name: "MWmês" },
      series,
    };
  }, [visibleMonthly, thermalMeta, latestRun?.config_snapshot.load_mwm, dark]);

  if (!latestRun || !summary) {
    return (
      <Card className="p-10 text-center space-y-4">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-sky-100 dark:bg-sky-900/40 text-sky-600">
          <Activity className="h-6 w-6" />
        </div>
        <div>
          <h2 className="text-lg font-semibold">Nenhuma simulação executada ainda</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Execute uma simulação hidrotérmica para visualizar o armazenamento do REE, despacho por Curva Guia e indicadores econômicos.
          </p>
        </div>
        <Button onClick={onRunSimulation} disabled={running}>
          <Play className="h-4 w-4" />
          {running ? "Simulando..." : "Executar Simulação Agora"}
        </Button>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>EA Máxima (REE)</span>
            <Droplets className="h-4 w-4 text-sky-600" />
          </div>
          <div className="mt-2 text-2xl font-bold tabular-nums">
            {fmtNum(summary.ea_max_mwm, 1)} <span className="text-xs font-normal text-slate-500">MWmês</span>
          </div>
          <div className="mt-1 text-xs text-slate-500 tabular-nums">
            ENA média: {fmtNum(summary.avg_ena_mwm, 1)} MWmês
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>{summary.firm_energy_mwm ? "Energia Firme" : "Carga Simulada"}</span>
            <Zap className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="mt-2 text-2xl font-bold tabular-nums">
            {fmtNum(summary.firm_energy_mwm ?? latestRun.config_snapshot.load_mwm, 2)}{" "}
            <span className="text-xs font-normal text-slate-500">MWmês</span>
          </div>
          <div className="mt-1 text-xs text-slate-500 tabular-nums">
            GT média: {fmtNum(summary.avg_thermal_mwm, 1)} MWmês
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Custo Total Anual</span>
            <DollarSign className="h-4 w-4 text-amber-600" />
          </div>
          <div className="mt-2 text-2xl font-bold tabular-nums">
            {fmtNum(summary.total_cost_kusd_year, 1)}{" "}
            <span className="text-xs font-normal text-slate-500">1000 US$</span>
          </div>
          <div className="mt-1 text-xs text-slate-500 tabular-nums">
            Juros: {fmtNum(latestRun.config_snapshot.interest_rate_pct, 1)}% a.a.
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Déficit & Período Crítico</span>
            {summary.max_deficit_mwm > 0 ? (
              <AlertTriangle className="h-4 w-4 text-red-600" />
            ) : (
              <Flame className="h-4 w-4 text-indigo-600" />
            )}
          </div>
          <div
            className={`mt-2 text-2xl font-bold tabular-nums ${
              summary.max_deficit_mwm > 0 ? "text-red-600" : "text-emerald-600"
            }`}
          >
            {fmtNum(summary.max_deficit_mwm, 1)}{" "}
            <span className="text-xs font-normal text-slate-500">MWmês máx</span>
          </div>
          <div className="mt-1 text-xs text-slate-500 tabular-nums">
            {summary.critical_period
              ? `PC: ${String(summary.critical_period.start_month).padStart(2, "0")}/${summary.critical_period.start_year} – ${String(summary.critical_period.end_month).padStart(2, "0")}/${summary.critical_period.end_year} (${summary.critical_period.duration_months}m)`
              : "Sem período crítico"}
          </div>
        </Card>
      </div>

      {/* Animation Controls + Storage Chart */}
      <Card>
        <CardHeader
          title="Evolução do Reservatório Equivalente (REE) & Período Crítico"
          description="Animação cronológica da trajetória de armazenamento (%) e ENA mensal"
          action={
            <div className="flex items-center gap-2">
              <Badge tone="sky" className="tabular-nums">
                Mês {Math.min(frameIdx, monthly.length)} / {monthly.length}
              </Badge>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  if (frameIdx >= monthly.length) setFrameIdx(1);
                  setIsPlaying(true);
                }}
                disabled={isPlaying}
              >
                <Play className="h-3.5 w-3.5" /> Play
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setIsPlaying(false)}
                disabled={!isPlaying}
              >
                <Pause className="h-3.5 w-3.5" /> Pause
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setIsPlaying(false);
                  setFrameIdx(monthly.length);
                }}
              >
                <Square className="h-3.5 w-3.5" /> Stop
              </Button>
            </div>
          }
        />
        <div className="p-4">
          <EChartBox option={storageOption} height={340} dark={dark} />
        </div>
      </Card>

      {/* Generation Mix Chart */}
      <Card>
        <CardHeader
          title="Despacho Hidrotérmico por Fonte (Curva Guia)"
          description="Composição empilhada da geração hidráulica, parque térmico por combustível e eventual déficit frente à carga"
        />
        <div className="p-4">
          <EChartBox option={dispatchOption} height={340} dark={dark} />
        </div>
      </Card>
    </div>
  );
}
