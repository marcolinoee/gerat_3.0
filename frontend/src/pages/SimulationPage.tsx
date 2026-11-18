import React, { useEffect, useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, Download, FileText, Play, Save, Target } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDownloadBlob, apiFetch } from "@/lib/api";
import { Badge, Button, Card, CardHeader, Input } from "@/components/ui/primitives";
import { fmtNum } from "@/lib/palette";
import type { MonthlyResult, SimulationConfig, SimulationRun } from "@/types/api";

interface SimulationPageProps {
  projectId: string;
  readOnly: boolean;
  latestRun: SimulationRun | null;
  onRunCompleted: (run: SimulationRun) => void;
}

export function SimulationPage({
  projectId,
  readOnly,
  latestRun,
  onRunCompleted,
}: SimulationPageProps) {
  const qc = useQueryClient();
  const [includeMonthlyPdf, setIncludeMonthlyPdf] = useState(false);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [yearFilter, setYearFilter] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: cfg } = useQuery({
    queryKey: ["config", projectId],
    queryFn: () => apiFetch<SimulationConfig>(`/projects/${projectId}/config`),
  });

  const [form, setForm] = useState({
    load_mwm: 6200,
    initial_earm_pct: 85,
    start_year: 2015,
    start_month: 1,
    end_year: 2024,
    end_month: 12,
    interest_rate_pct: 10,
    gh_max_mwm: "" as string,
  });

  useEffect(() => {
    if (cfg) {
      setForm({
        load_mwm: cfg.load_mwm,
        initial_earm_pct: cfg.initial_earm_pct,
        start_year: cfg.start_year,
        start_month: cfg.start_month,
        end_year: cfg.end_year,
        end_month: cfg.end_month,
        interest_rate_pct: cfg.interest_rate_pct,
        gh_max_mwm: cfg.gh_max_mwm !== null ? String(cfg.gh_max_mwm) : "",
      });
    }
  }, [cfg]);

  const saveCfgMut = useMutation({
    mutationFn: () =>
      apiFetch<SimulationConfig>(`/projects/${projectId}/config`, {
        method: "PUT",
        body: JSON.stringify({
          load_mwm: Number(form.load_mwm),
          initial_earm_pct: Number(form.initial_earm_pct),
          start_year: Number(form.start_year),
          start_month: Number(form.start_month),
          end_year: Number(form.end_year),
          end_month: Number(form.end_month),
          interest_rate_pct: Number(form.interest_rate_pct),
          gh_max_mwm: form.gh_max_mwm.trim() === "" ? null : Number(form.gh_max_mwm),
        }),
      }),
    onSuccess: () => {
      setError(null);
      setFeedback("Parâmetros salvos com sucesso.");
      qc.invalidateQueries({ queryKey: ["config", projectId] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const simMut = useMutation({
    mutationFn: () =>
      apiFetch<SimulationRun>(`/projects/${projectId}/simulate`, { method: "POST" }),
    onSuccess: (run) => {
      setError(null);
      setFeedback("Simulação concluída com sucesso.");
      onRunCompleted(run);
    },
    onError: (err: Error) => setError(err.message),
  });

  const firmMut = useMutation({
    mutationFn: () =>
      apiFetch<SimulationRun>(`/projects/${projectId}/firm-energy`, { method: "POST" }),
    onSuccess: (run) => {
      setError(null);
      setFeedback(
        `Energia Firme convergida: ${fmtNum(run.summary.firm_energy_mwm, 2)} MWmês (déficit zero).`
      );
      onRunCompleted(run);
    },
    onError: (err: Error) => setError(err.message),
  });

  const filteredData = useMemo(() => {
    const rows = latestRun?.monthly_results ?? [];
    if (!yearFilter.trim()) return rows;
    return rows.filter((r) => String(r.year).includes(yearFilter.trim()));
  }, [latestRun, yearFilter]);

  const columns = useMemo<ColumnDef<MonthlyResult>[]>(
    () => [
      {
        accessorFn: (r) => `${r.year}-${String(r.month).padStart(2, "0")}`,
        id: "period",
        header: "Ano/Mês",
      },
      {
        accessorKey: "enat_mwm",
        header: "ENA (MWmês)",
        cell: (i) => fmtNum(i.getValue<number>(), 1),
      },
      {
        accessorKey: "gh_delivered_mwm",
        header: "GH (MWmês)",
        cell: (i) => fmtNum(i.getValue<number>(), 1),
      },
      {
        accessorKey: "total_thermal_mwm",
        header: "GT Total (MWmês)",
        cell: (i) => fmtNum(i.getValue<number>(), 1),
      },
      {
        accessorKey: "earm_mwm",
        header: "EA (MWmês)",
        cell: (i) => fmtNum(i.getValue<number>(), 1),
      },
      {
        accessorKey: "earm_pct",
        header: "EA (%)",
        cell: (i) => `${fmtNum(i.getValue<number>(), 1)}%`,
      },
      {
        accessorKey: "evert_mwm",
        header: "Vert. (MWmês)",
        cell: (i) => fmtNum(i.getValue<number>(), 1),
      },
      {
        accessorKey: "deficit_mwm",
        header: "Déficit (MWmês)",
        cell: (i) => {
          const val = i.getValue<number>();
          return (
            <span className={val > 0 ? "text-red-600 font-semibold" : ""}>
              {fmtNum(val, 1)}
            </span>
          );
        },
      },
    ],
    []
  );

  const table = useReactTable({
    data: filteredData,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Parâmetros da Simulação & Energia Firme"
          description="Configure a carga, armazenamento inicial, horizonte histórico, taxa de juros e limite hidráulico (gh_max_mwm)"
        />
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label className="text-xs font-medium">Carga Constante (MWmês)</label>
              <Input
                type="number"
                step="any"
                disabled={readOnly}
                value={form.load_mwm}
                onChange={(e) => setForm({ ...form, load_mwm: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs font-medium">Armazenamento Inicial (%)</label>
              <Input
                type="number"
                step="any"
                min="0"
                max="100"
                disabled={readOnly}
                value={form.initial_earm_pct}
                onChange={(e) => setForm({ ...form, initial_earm_pct: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs font-medium">Taxa de Juros (% a.a.)</label>
              <Input
                type="number"
                step="0.5"
                disabled={readOnly}
                value={form.interest_rate_pct}
                onChange={(e) => setForm({ ...form, interest_rate_pct: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs font-medium">GH Máx (MWmês, opcional)</label>
              <Input
                type="number"
                step="any"
                disabled={readOnly}
                placeholder="Sem limite"
                value={form.gh_max_mwm}
                onChange={(e) => setForm({ ...form, gh_max_mwm: e.target.value })}
              />
            </div>
            <div>
              <label className="text-xs font-medium">Ano Inicial</label>
              <Input
                type="number"
                disabled={readOnly}
                value={form.start_year}
                onChange={(e) => setForm({ ...form, start_year: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs font-medium">Mês Inicial</label>
              <Input
                type="number"
                min="1"
                max="12"
                disabled={readOnly}
                value={form.start_month}
                onChange={(e) => setForm({ ...form, start_month: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs font-medium">Ano Final</label>
              <Input
                type="number"
                disabled={readOnly}
                value={form.end_year}
                onChange={(e) => setForm({ ...form, end_year: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs font-medium">Mês Final</label>
              <Input
                type="number"
                min="1"
                max="12"
                disabled={readOnly}
                value={form.end_month}
                onChange={(e) => setForm({ ...form, end_month: Number(e.target.value) })}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100 dark:border-slate-800">
            <div className="flex flex-wrap items-center gap-2">
              {!readOnly && (
                <Button variant="outline" onClick={() => saveCfgMut.mutate()} disabled={saveCfgMut.isPending}>
                  <Save className="h-4 w-4" /> Salvar Parâmetros
                </Button>
              )}
              <Button onClick={() => simMut.mutate()} disabled={simMut.isPending}>
                <Play className="h-4 w-4" /> {simMut.isPending ? "Simulando..." : "Executar Simulação"}
              </Button>
              <Button variant="secondary" onClick={() => firmMut.mutate()} disabled={firmMut.isPending}>
                <Target className="h-4 w-4" /> {firmMut.isPending ? "Convergindo..." : "Calcular Energia Firme"}
              </Button>
            </div>

            {latestRun && (
              <div className="flex flex-wrap items-center gap-3">
                <label className="inline-flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300">
                  <input
                    type="checkbox"
                    checked={includeMonthlyPdf}
                    onChange={(e) => setIncludeMonthlyPdf(e.target.checked)}
                  />
                  Anexo Mensal no PDF
                </label>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    apiDownloadBlob(
                      `/projects/${projectId}/runs/${latestRun.id}/export-csv`,
                      `gerat_${latestRun.id.slice(0, 8)}.csv`
                    )
                  }
                >
                  <Download className="h-3.5 w-3.5" /> CSV
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    apiDownloadBlob(
                      `/projects/${projectId}/runs/${latestRun.id}/report-pdf?include_monthly_table=${includeMonthlyPdf}`,
                      `relatorio_gerat_${latestRun.id.slice(0, 8)}.pdf`
                    )
                  }
                >
                  <FileText className="h-3.5 w-3.5" /> Relatório PDF
                </Button>
              </div>
            )}
          </div>

          {feedback && (
            <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-300">
              {feedback}
            </div>
          )}
          {error && (
            <div className="rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 px-3 py-2 text-xs text-red-700 dark:text-red-300">
              {error}
            </div>
          )}
        </div>
      </Card>

      {/* Economic Summary Table */}
      {latestRun && latestRun.summary.economics.length > 0 && (
        <Card>
          <CardHeader
            title="Quadro Econômico Anualizado (1000 US$)"
            action={
              <Badge tone="amber" className="tabular-nums">
                Total: {fmtNum(latestRun.summary.total_cost_kusd_year, 2)} kUS$/ano
              </Badge>
            }
          />
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular-nums">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-xs text-slate-500">
                  <th className="py-2.5 px-4 text-left">Usina</th>
                  <th className="py-2.5 px-4 text-right">GT Média (MWano)</th>
                  <th className="py-2.5 px-4 text-right">FRC</th>
                  <th className="py-2.5 px-4 text-right">Custo Fixo (kUS$)</th>
                  <th className="py-2.5 px-4 text-right">Custo Var. (kUS$)</th>
                  <th className="py-2.5 px-4 text-right">Custo Total (kUS$)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {latestRun.summary.economics.map((e) => (
                  <tr key={e.plant_id}>
                    <td className="py-2 px-4 font-medium">{e.name}</td>
                    <td className="py-2 px-4 text-right">{fmtNum(e.avg_generation_mwm, 2)}</td>
                    <td className="py-2 px-4 text-right">{fmtNum(e.frc, 4)}</td>
                    <td className="py-2 px-4 text-right">{fmtNum(e.fixed_cost_kusd_year, 2)}</td>
                    <td className="py-2 px-4 text-right">{fmtNum(e.variable_cost_kusd_year, 2)}</td>
                    <td className="py-2 px-4 text-right font-semibold">
                      {fmtNum(e.total_cost_kusd_year, 2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Monthly Results TanStack Table */}
      {latestRun && (
        <Card>
          <CardHeader
            title="Tabela Mensal de Resultados"
            description={`${filteredData.length} meses exibidos — clique nos cabeçalhos para ordenar`}
            action={
              <Input
                placeholder="Filtrar por ano..."
                value={yearFilter}
                onChange={(e) => setYearFilter(e.target.value)}
                className="w-40 h-8 text-xs"
              />
            }
          />
          <div className="overflow-x-auto max-h-[440px]">
            <table className="w-full text-xs tabular-nums">
              <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id}>
                    {hg.headers.map((header) => (
                      <th
                        key={header.id}
                        onClick={header.column.getToggleSortingHandler()}
                        className="py-2.5 px-3 text-left font-semibold text-slate-600 dark:text-slate-300 cursor-pointer select-none"
                      >
                        <span className="inline-flex items-center gap-1">
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          <ArrowUpDown className="h-3 w-3 opacity-50" />
                        </span>
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="py-2 px-3">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
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
