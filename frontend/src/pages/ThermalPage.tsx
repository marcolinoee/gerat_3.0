import React, { useState } from "react";
import { Calculator, Flame, Plus, Save, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Badge, Button, Card, CardHeader, Input, Select } from "@/components/ui/primitives";
import { ENERGY_COLORS, FUEL_LABELS, MONTHS_PT, fmtNum } from "@/lib/palette";
import type { FuelType, ThermalPlant } from "@/types/api";

interface ThermalPageProps {
  projectId: string;
  readOnly: boolean;
}

export function ThermalPage({ projectId, readOnly }: ThermalPageProps) {
  const qc = useQueryClient();

  // New thermal form
  const [name, setName] = useState("");
  const [fuelType, setFuelType] = useState<FuelType>("GAS");
  const [power, setPower] = useState("1000");
  const [fcMax, setFcMax] = useState("0.85");
  const [fcMin, setFcMin] = useState("0.0");
  const [fixedCost, setFixedCost] = useState("1100");
  const [varCost, setVarCost] = useState("75");
  const [life, setLife] = useState("25");
  const [guideCurve, setGuideCurve] = useState<number[]>(new Array(12).fill(50));

  // Heat Rate calculator state
  const [heatRate, setHeatRate] = useState("2150000");
  const [fuelPrice, setFuelPrice] = useState("0.40");
  const [pci, setPci] = useState("10000");
  const [calcCost, setCalcCost] = useState<number | null>(null);

  // Selected plant for editing Guide Curve
  const [editingPlant, setEditingPlant] = useState<ThermalPlant | null>(null);

  const { data: plants = [] } = useQuery({
    queryKey: ["thermals", projectId],
    queryFn: () => apiFetch<ThermalPlant[]>(`/projects/${projectId}/thermal-plants`),
  });

  const createMut = useMutation({
    mutationFn: () =>
      apiFetch<ThermalPlant>(`/projects/${projectId}/thermal-plants`, {
        method: "POST",
        body: JSON.stringify({
          name,
          fuel_type: fuelType,
          installed_power_mw: Number(power),
          fc_max: Number(fcMax),
          fc_min: Number(fcMin),
          fixed_cost_usd_kw: Number(fixedCost),
          variable_cost_usd_mwh: Number(varCost),
          useful_life_years: Number(life),
          guide_curve: guideCurve,
          enabled: true,
        }),
      }),
    onSuccess: () => {
      setName("");
      qc.invalidateQueries({ queryKey: ["thermals", projectId] });
    },
  });

  const updateMut = useMutation({
    mutationFn: (plant: ThermalPlant) =>
      apiFetch<ThermalPlant>(`/projects/${projectId}/thermal-plants/${plant.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          guide_curve: plant.guide_curve,
          enabled: plant.enabled,
          variable_cost_usd_mwh: plant.variable_cost_usd_mwh,
        }),
      }),
    onSuccess: () => {
      setEditingPlant(null);
      qc.invalidateQueries({ queryKey: ["thermals", projectId] });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (plantId: string) =>
      apiFetch(`/projects/${projectId}/thermal-plants/${plantId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["thermals", projectId] }),
  });

  async function computeHeatRate() {
    const res = await apiFetch<{ variable_cost_usd_mwh: number }>("/tools/heat-rate", {
      method: "POST",
      body: JSON.stringify({
        heat_rate_kcal_mwh: Number(heatRate),
        fuel_price_usd_unit: Number(fuelPrice),
        pci_kcal_unit: Number(pci),
      }),
    });
    setCalcCost(res.variable_cost_usd_mwh);
    setVarCost(String(res.variable_cost_usd_mwh));
  }

  return (
    <div className="space-y-6">
      {/* Heat Rate Calculator */}
      <Card>
        <CardHeader
          title="Calculadora de Custo Variável via Heat Rate"
          description="C_comb = (HeatRate × P_comb) / PCI  [US$/MWh]"
        />
        <div className="p-5 grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <div>
            <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
              Heat Rate (Kcal/MWh)
            </label>
            <Input type="number" step="any" value={heatRate} onChange={(e) => setHeatRate(e.target.value)} />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
              Preço Comb. (US$/unid)
            </label>
            <Input type="number" step="any" value={fuelPrice} onChange={(e) => setFuelPrice(e.target.value)} />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
              PCI (Kcal/unid)
            </label>
            <Input type="number" step="any" value={pci} onChange={(e) => setPci(e.target.value)} />
          </div>
          <div>
            <Button type="button" variant="outline" className="w-full" onClick={computeHeatRate}>
              <Calculator className="h-4 w-4" /> Calcular & Aplicar
            </Button>
          </div>
          <div className="rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 px-3 py-2">
            <div className="text-[11px] text-slate-500">Custo Variável</div>
            <div className="text-base font-bold text-amber-600 tabular-nums">
              {calcCost !== null ? `${fmtNum(calcCost, 2)} US$/MWh` : "—"}
            </div>
          </div>
        </div>
      </Card>

      {/* Create Thermal Form */}
      {!readOnly && (
        <Card>
          <CardHeader title="Adicionar Usina Térmica" />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createMut.mutate();
            }}
            className="p-5 space-y-4"
          >
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <label className="text-xs font-medium">Nome</label>
                <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: UTE Gás Nordeste" />
              </div>
              <div>
                <label className="text-xs font-medium">Combustível</label>
                <Select value={fuelType} onChange={(e) => setFuelType(e.target.value as FuelType)}>
                  <option value="NUCLEAR">Nuclear</option>
                  <option value="COAL">Carvão</option>
                  <option value="GAS">Gás Natural</option>
                  <option value="OIL">Óleo</option>
                  <option value="OTHER">Outro</option>
                </Select>
              </div>
              <div>
                <label className="text-xs font-medium">Potência (MW)</label>
                <Input type="number" step="any" required value={power} onChange={(e) => setPower(e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium">Vida Útil (anos)</label>
                <Input type="number" required value={life} onChange={(e) => setLife(e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium">FCmax (0–1)</label>
                <Input type="number" step="0.01" min="0" max="1" required value={fcMax} onChange={(e) => setFcMax(e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium">FCmin (0–1)</label>
                <Input type="number" step="0.01" min="0" max="1" required value={fcMin} onChange={(e) => setFcMin(e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium">Custo Fixo (US$/kW)</label>
                <Input type="number" step="any" required value={fixedCost} onChange={(e) => setFixedCost(e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium">Custo Variável (US$/MWh)</label>
                <Input type="number" step="any" required value={varCost} onChange={(e) => setVarCost(e.target.value)} />
              </div>
            </div>

            <div>
              <label className="text-xs font-medium block mb-1.5">
                Curva Guia Mensal (% EAmax — despacha FCmax se %EA &lt; CG)
              </label>
              <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-12 gap-2">
                {MONTHS_PT.map((m, idx) => (
                  <div key={m}>
                    <span className="text-[10px] text-slate-500 block">{m}</span>
                    <Input
                      type="number"
                      min="0"
                      max="100"
                      value={guideCurve[idx]}
                      onChange={(e) => {
                        const next = [...guideCurve];
                        next[idx] = Number(e.target.value);
                        setGuideCurve(next);
                      }}
                      className="h-8 px-1.5 text-xs tabular-nums"
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-end">
              <Button type="submit" disabled={createMut.isPending}>
                <Plus className="h-4 w-4" /> Adicionar Térmica
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Thermal Fleet Table */}
      <Card>
        <CardHeader title="Parque Térmico e Curvas Guia" />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 text-xs text-slate-500">
                <th className="py-3 px-4 text-left">Usina</th>
                <th className="py-3 px-4 text-left">Combustível</th>
                <th className="py-3 px-4 text-right">Potência (MW)</th>
                <th className="py-3 px-4 text-right">FCmax / FCmin</th>
                <th className="py-3 px-4 text-right">C. Fixo (US$/kW)</th>
                <th className="py-3 px-4 text-right">C. Var (US$/MWh)</th>
                <th className="py-3 px-4 text-right">CG Média (%)</th>
                <th className="py-3 px-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 tabular-nums">
              {plants.map((t) => {
                const avgCg =
                  t.guide_curve.reduce((a, b) => a + b, 0) / (t.guide_curve.length || 1);
                return (
                  <tr key={t.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                    <td className="py-2.5 px-4 font-medium flex items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: ENERGY_COLORS[t.fuel_type] }}
                      />
                      {t.name}
                    </td>
                    <td className="py-2.5 px-4">
                      <Badge>{FUEL_LABELS[t.fuel_type]}</Badge>
                    </td>
                    <td className="py-2.5 px-4 text-right">{fmtNum(t.installed_power_mw, 1)}</td>
                    <td className="py-2.5 px-4 text-right">
                      {fmtNum(t.fc_max, 2)} / {fmtNum(t.fc_min, 2)}
                    </td>
                    <td className="py-2.5 px-4 text-right">{fmtNum(t.fixed_cost_usd_kw, 0)}</td>
                    <td className="py-2.5 px-4 text-right font-semibold">
                      {fmtNum(t.variable_cost_usd_mwh, 2)}
                    </td>
                    <td className="py-2.5 px-4 text-right">{fmtNum(avgCg, 1)}%</td>
                    <td className="py-2.5 px-4 text-right space-x-1">
                      {!readOnly && (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setEditingPlant({ ...t, guide_curve: [...t.guide_curve] })}
                          >
                            <Flame className="h-3.5 w-3.5" /> Curva Guia
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => deleteMut.mutate(t.id)}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Guide Curve Editor Panel */}
      {editingPlant && !readOnly && (
        <Card className="border-sky-300 dark:border-sky-800">
          <CardHeader
            title={`Editor de Curva Guia — ${editingPlant.name}`}
            description="Ajuste o limiar mensal (%EAmax) abaixo do qual a térmica despacha na capacidade máxima (FCmax)"
            action={
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={() => setEditingPlant(null)}>
                  Cancelar
                </Button>
                <Button
                  size="sm"
                  onClick={() => updateMut.mutate(editingPlant)}
                  disabled={updateMut.isPending}
                >
                  <Save className="h-3.5 w-3.5" /> Salvar Curva
                </Button>
              </div>
            }
          />
          <div className="p-5 grid grid-cols-4 sm:grid-cols-6 md:grid-cols-12 gap-2">
            {MONTHS_PT.map((m, idx) => (
              <div key={m}>
                <span className="text-[11px] font-medium text-slate-600 dark:text-slate-300 block mb-1">
                  {m}
                </span>
                <Input
                  type="number"
                  min="0"
                  max="100"
                  value={editingPlant.guide_curve[idx]}
                  onChange={(e) => {
                    const next = [...editingPlant.guide_curve];
                    next[idx] = Number(e.target.value);
                    setEditingPlant({ ...editingPlant, guide_curve: next });
                  }}
                  className="h-8 px-2 text-xs tabular-nums"
                />
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
