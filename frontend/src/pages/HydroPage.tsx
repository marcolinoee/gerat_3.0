import React, { useState } from "react";
import { ArrowRight, Droplets, Plus, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Badge, Button, Card, CardHeader, Input, Select } from "@/components/ui/primitives";
import { fmtNum } from "@/lib/palette";
import type { HydroPlant, REESummary } from "@/types/api";

interface HydroPageProps {
  projectId: string;
  readOnly: boolean;
}

export function HydroPage({ projectId, readOnly }: HydroPageProps) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [vmax, setVmax] = useState("10000");
  const [vmin, setVmin] = useState("2000");
  const [prod, setProd] = useState("0.75");
  const [power, setPower] = useState("1200");
  const [downstreamId, setDownstreamId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: plants = [] } = useQuery({
    queryKey: ["hydro", projectId],
    queryFn: () => apiFetch<HydroPlant[]>(`/projects/${projectId}/hydro-plants`),
  });

  const { data: ree } = useQuery({
    queryKey: ["ree", projectId],
    queryFn: () => apiFetch<REESummary>(`/projects/${projectId}/hydro-plants/ree`),
  });

  const createMut = useMutation({
    mutationFn: () =>
      apiFetch<HydroPlant>(`/projects/${projectId}/hydro-plants`, {
        method: "POST",
        body: JSON.stringify({
          name,
          vmax_hm3: Number(vmax),
          vmin_hm3: Number(vmin),
          productivity_mw_m3s: Number(prod),
          installed_power_mw: Number(power),
          downstream_plant_id: downstreamId || null,
        }),
      }),
    onSuccess: () => {
      setName("");
      setError(null);
      qc.invalidateQueries({ queryKey: ["hydro", projectId] });
      qc.invalidateQueries({ queryKey: ["ree", projectId] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const deleteMut = useMutation({
    mutationFn: (plantId: string) =>
      apiFetch(`/projects/${projectId}/hydro-plants/${plantId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hydro", projectId] });
      qc.invalidateQueries({ queryKey: ["ree", projectId] });
    },
  });

  const plantById = Object.fromEntries(plants.map((p) => [p.id, p]));

  // Find headwater plants (not referenced as downstream by any other plant)
  const downstreamSet = new Set(plants.map((p) => p.downstream_plant_id).filter(Boolean));
  const headwaters = plants.filter((p) => !downstreamSet.has(p.id));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="text-xs text-slate-500">EA Máxima Total (REE)</div>
          <div className="mt-1 text-2xl font-bold text-sky-600 tabular-nums">
            {fmtNum(ree?.ea_max_total_mwm, 2)} MWmês
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-slate-500">Usinas Hidrelétricas</div>
          <div className="mt-1 text-2xl font-bold tabular-nums">{plants.length}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-slate-500">Potência Hidráulica Instalada</div>
          <div className="mt-1 text-2xl font-bold tabular-nums">
            {fmtNum(
              plants.reduce((acc, p) => acc + p.installed_power_mw, 0),
              1
            )}{" "}
            MW
          </div>
        </Card>
      </div>

      {/* Visual Cascade Diagram */}
      <Card>
        <CardHeader
          title="Visualizador de Cascata (Topologia DAG)"
          description="Cadeia montante → jusante utilizada na produtividade acumulada do Reservatório Equivalente"
        />
        <div className="p-5 space-y-3 overflow-x-auto">
          {headwaters.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhuma usina cadastrada.</p>
          ) : (
            headwaters.map((head) => {
              const chain = ree?.cascades[head.id] ?? [head.id];
              return (
                <div key={head.id} className="flex items-center gap-2 flex-wrap">
                  {chain.map((pid, idx) => {
                    const p = plantById[pid];
                    if (!p) return null;
                    const ea = ree?.ea_max_by_plant_mwm[pid] ?? 0;
                    const rhoAcc = ree?.accumulated_productivity[pid] ?? p.productivity_mw_m3s;
                    return (
                      <React.Fragment key={pid}>
                        <div className="rounded-lg border border-sky-200 dark:border-sky-800 bg-sky-50/70 dark:bg-sky-950/40 px-3.5 py-2 min-w-[165px]">
                          <div className="flex items-center gap-1.5 font-semibold text-xs text-sky-900 dark:text-sky-200">
                            <Droplets className="h-3.5 w-3.5 text-sky-600" />
                            {p.name}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-600 dark:text-slate-400 tabular-nums">
                            EAmax: <strong>{fmtNum(ea, 1)}</strong> MWmês
                          </div>
                          <div className="text-[11px] text-slate-500 tabular-nums">
                            ρ indiv: {fmtNum(p.productivity_mw_m3s, 2)} | Σρ: {fmtNum(rhoAcc, 2)}
                          </div>
                        </div>
                        {idx < chain.length - 1 && (
                          <ArrowRight className="h-4 w-4 text-slate-400 shrink-0" />
                        )}
                      </React.Fragment>
                    );
                  })}
                </div>
              );
            })
          )}
        </div>
      </Card>

      {/* Add Hydro Form */}
      {!readOnly && (
        <Card>
          <CardHeader title="Adicionar Usina Hidrelétrica" />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createMut.mutate();
            }}
            className="p-5 grid grid-cols-1 md:grid-cols-6 gap-3 items-end"
          >
            <div className="md:col-span-2">
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300">Nome</label>
              <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: Sobradinho" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300">Vmax (hm³)</label>
              <Input type="number" step="any" required value={vmax} onChange={(e) => setVmax(e.target.value)} />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300">Vmin (hm³)</label>
              <Input type="number" step="any" required value={vmin} onChange={(e) => setVmin(e.target.value)} />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300">ρ (MW/m³/s)</label>
              <Input type="number" step="any" required value={prod} onChange={(e) => setProd(e.target.value)} />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300">Potência (MW)</label>
              <Input type="number" step="any" required value={power} onChange={(e) => setPower(e.target.value)} />
            </div>
            <div className="md:col-span-3">
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300">Usina a Jusante</label>
              <Select value={downstreamId} onChange={(e) => setDownstreamId(e.target.value)}>
                <option value="">Nenhuma (Foz / Última da cascata)</option>
                {plants.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="md:col-span-3 flex justify-end">
              <Button type="submit" disabled={createMut.isPending}>
                <Plus className="h-4 w-4" /> Adicionar Usina
              </Button>
            </div>
            {error && (
              <div className="md:col-span-6 text-xs text-red-600 bg-red-50 dark:bg-red-950/40 p-2 rounded">
                {error}
              </div>
            )}
          </form>
        </Card>
      )}

      {/* Table */}
      <Card>
        <CardHeader title="Cadastro de Hidrelétricas e Contribuição ao REE" />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 text-xs text-slate-500">
                <th className="py-3 px-4 text-left">Usina</th>
                <th className="py-3 px-4 text-right">Vmax (hm³)</th>
                <th className="py-3 px-4 text-right">Vmin (hm³)</th>
                <th className="py-3 px-4 text-right">ρ Indiv.</th>
                <th className="py-3 px-4 text-right">Σρ Cascata</th>
                <th className="py-3 px-4 text-right">EAmax (MWmês)</th>
                <th className="py-3 px-4 text-left">Jusante</th>
                {!readOnly && <th className="py-3 px-4 text-right">Ações</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 tabular-nums">
              {plants.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                  <td className="py-2.5 px-4 font-medium">{p.name}</td>
                  <td className="py-2.5 px-4 text-right">{fmtNum(p.vmax_hm3, 1)}</td>
                  <td className="py-2.5 px-4 text-right">{fmtNum(p.vmin_hm3, 1)}</td>
                  <td className="py-2.5 px-4 text-right">{fmtNum(p.productivity_mw_m3s, 3)}</td>
                  <td className="py-2.5 px-4 text-right">
                    {fmtNum(ree?.accumulated_productivity[p.id], 3)}
                  </td>
                  <td className="py-2.5 px-4 text-right font-semibold text-sky-600">
                    {fmtNum(ree?.ea_max_by_plant_mwm[p.id], 2)}
                  </td>
                  <td className="py-2.5 px-4">
                    {p.downstream_plant_id ? (
                      <Badge tone="sky">{plantById[p.downstream_plant_id]?.name ?? "—"}</Badge>
                    ) : (
                      <Badge>Foz</Badge>
                    )}
                  </td>
                  {!readOnly && (
                    <td className="py-2.5 px-4 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => deleteMut.mutate(p.id)}
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
