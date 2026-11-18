"""Monthly hydrothermal simulation, Curva Guia dispatch, Firm Energy, and Critical Period."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from app.engine.economics import calculate_thermal_economics
from app.engine.ree import calculate_ena_series, calculate_ree
from app.engine.types import (
    CriticalPeriodResult,
    FirmEnergyResult,
    HydroPlantInput,
    InflowRecordInput,
    MonthlyResult,
    REEResult,
    SimulationConfigInput,
    SimulationResult,
    ThermalPlantInput,
)


def _iter_months(start_year: int, start_month: int, end_year: int, end_month: int) -> list[tuple[int, int]]:
    """Return inclusive list of (year, month) tuples in chronological order."""
    if not (1 <= start_month <= 12 and 1 <= end_month <= 12):
        raise ValueError("Mês inicial e final devem estar entre 1 e 12.")
    if (start_year, start_month) > (end_year, end_month):
        raise ValueError("Período inicial não pode ser posterior ao período final.")

    months: list[tuple[int, int]] = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def detect_critical_period(
    monthly_results: Sequence[MonthlyResult],
    ea_max_mwm: float,
    initial_earm_mwm: float,
    start_year: int,
    start_month: int,
) -> CriticalPeriodResult | None:
    """Detect the Critical Period of the simulated reservoir trajectory.

    The critical period is the interval between:
    - The last month with EA_t == EA_max before the global storage minimum
      (or the initial month t=0 if the reservoir never reaches 100% full before the trough)
    - The month of the global minimum of EA_t.
    """
    if not monthly_results:
        return None

    eps = 1e-6

    # Find index of first global minimum of EA_t
    min_idx = 0
    min_earm = monthly_results[0].earm_mwm
    for idx, res in enumerate(monthly_results):
        if res.earm_mwm < min_earm - eps:
            min_earm = res.earm_mwm
            min_idx = idx

    # Find last month before min_idx where EA_t == EA_max
    last_full_idx: int | None = None
    if ea_max_mwm > eps:
        for idx in range(min_idx - 1, -1, -1):
            if monthly_results[idx].earm_mwm >= ea_max_mwm - eps:
                last_full_idx = idx
                break

    if last_full_idx is not None:
        cp_start_idx = last_full_idx + 1
        cp_start_year = monthly_results[cp_start_idx].year
        cp_start_month = monthly_results[cp_start_idx].month
        duration = min_idx - last_full_idx
    else:
        cp_start_year = start_year
        cp_start_month = start_month
        duration = min_idx + 1

    end_res = monthly_results[min_idx]
    min_pct = (min_earm / ea_max_mwm * 100.0) if ea_max_mwm > eps else 0.0

    return CriticalPeriodResult(
        start_year=cp_start_year,
        start_month=cp_start_month,
        end_year=end_res.year,
        end_month=end_res.month,
        duration_months=duration,
        min_earm_mwm=min_earm,
        min_earm_pct=min_pct,
    )


def run_simulation(
    hydro_plants: Sequence[HydroPlantInput],
    inflows: Sequence[InflowRecordInput],
    thermal_plants: Sequence[ThermalPlantInput],
    config: SimulationConfigInput,
    *,
    ree: REEResult | None = None,
    ena_series: dict[tuple[int, int], float] | None = None,
) -> SimulationResult:
    """Execute deterministic monthly hydrothermal simulation with Curva Guia dispatch."""
    if config.load_mwm < 0:
        raise ValueError("A carga (MWmês) não pode ser negativa.")
    if not (0.0 <= config.initial_earm_pct <= 100.0):
        raise ValueError("O armazenamento inicial (%) deve estar entre 0 e 100.")
    if config.gh_max_mwm is not None and config.gh_max_mwm < 0:
        raise ValueError("A geração hidráulica máxima (gh_max_mwm) não pode ser negativa.")

    if ree is None:
        ree = calculate_ree(hydro_plants)
    if ena_series is None:
        ena_series = calculate_ena_series(hydro_plants, inflows, ree=ree)

    ea_max = ree.ea_max_total_mwm
    initial_earm = (config.initial_earm_pct / 100.0) * ea_max

    enabled_thermals = [t for t in thermal_plants if t.enabled]
    for t in enabled_thermals:
        if len(t.guide_curve) != 12:
            raise ValueError(
                f"Curva guia da térmica '{t.name}' deve conter exatamente 12 valores mensais."
            )

    months = _iter_months(
        config.start_year, config.start_month, config.end_year, config.end_month
    )

    ea_prev = initial_earm
    monthly_results: list[MonthlyResult] = []
    thermal_sums: dict[str, float] = {t.plant_id: 0.0 for t in enabled_thermals}

    for year, month in months:
        enat = ena_series.get((year, month), 0.0)
        pct_ea_prev = (ea_prev / ea_max * 100.0) if ea_max > 0.0 else 0.0

        # Thermal dispatch by Guide Curve (Curva Guia)
        dispatch_by_plant: dict[str, float] = {}
        total_thermal = 0.0
        for t in enabled_thermals:
            cg_m = t.guide_curve[month - 1]
            if pct_ea_prev < cg_m:
                gt = t.installed_power_mw * t.fc_max
            else:
                gt = t.installed_power_mw * t.fc_min
            dispatch_by_plant[t.plant_id] = gt
            thermal_sums[t.plant_id] += gt
            total_thermal += gt

        # Required hydro generation and optional maximum hydro cap (gh_max_mwm)
        gh_req = max(0.0, config.load_mwm - total_thermal)
        if config.gh_max_mwm is not None and gh_req > config.gh_max_mwm:
            gh_efet = config.gh_max_mwm
            d_pot = gh_req - config.gh_max_mwm
        else:
            gh_efet = gh_req
            d_pot = 0.0

        # Reservoir Energy Balance
        ea_tent = ea_prev + enat - gh_efet
        if ea_tent > ea_max:
            evert = ea_tent - ea_max
            ea_curr = ea_max
            d_en = 0.0
        elif ea_tent < 0.0:
            evert = 0.0
            d_en = -ea_tent
            ea_curr = 0.0
        else:
            evert = 0.0
            d_en = 0.0
            ea_curr = ea_tent

        deficit_total = d_pot + d_en
        gh_delivered = max(0.0, gh_efet - d_en)
        earm_pct = (ea_curr / ea_max * 100.0) if ea_max > 0.0 else 0.0

        monthly_results.append(
            MonthlyResult(
                year=year,
                month=month,
                enat_mwm=enat,
                total_thermal_mwm=total_thermal,
                gh_req_mwm=gh_req,
                gh_efet_mwm=gh_efet,
                gh_delivered_mwm=gh_delivered,
                earm_mwm=ea_curr,
                earm_pct=earm_pct,
                evert_mwm=evert,
                deficit_pot_mwm=d_pot,
                deficit_en_mwm=d_en,
                deficit_mwm=deficit_total,
                thermal_dispatch_by_plant=dispatch_by_plant,
            )
        )

        ea_prev = ea_curr

    n_months = len(monthly_results)
    avg_gt_by_plant = {
        pid: (s / n_months if n_months > 0 else 0.0) for pid, s in thermal_sums.items()
    }

    economics = calculate_thermal_economics(
        enabled_thermals, avg_gt_by_plant, config.interest_rate_pct
    )

    total_cf = sum(e.fixed_cost_usd_year for e in economics)
    total_cv = sum(e.variable_cost_usd_year for e in economics)
    total_ct = total_cf + total_cv

    critical_period = detect_critical_period(
        monthly_results,
        ea_max_mwm=ea_max,
        initial_earm_mwm=initial_earm,
        start_year=config.start_year,
        start_month=config.start_month,
    )

    max_deficit = max((r.deficit_mwm for r in monthly_results), default=0.0)
    total_deficit = sum(r.deficit_mwm for r in monthly_results)
    deficit_months = sum(1 for r in monthly_results if r.deficit_mwm > 1e-9)
    avg_ena = sum(r.enat_mwm for r in monthly_results) / n_months if n_months else 0.0
    avg_thermal = (
        sum(r.total_thermal_mwm for r in monthly_results) / n_months if n_months else 0.0
    )
    avg_hydro = (
        sum(r.gh_delivered_mwm for r in monthly_results) / n_months if n_months else 0.0
    )
    total_spilled = sum(r.evert_mwm for r in monthly_results)

    return SimulationResult(
        ea_max_mwm=ea_max,
        initial_earm_mwm=initial_earm,
        monthly_results=monthly_results,
        critical_period=critical_period,
        economics=economics,
        total_fixed_cost_usd_year=total_cf,
        total_variable_cost_usd_year=total_cv,
        total_cost_usd_year=total_ct,
        total_cost_kusd_year=total_ct / 1000.0,
        max_deficit_mwm=max_deficit,
        total_deficit_mwm=total_deficit,
        deficit_months=deficit_months,
        avg_ena_mwm=avg_ena,
        avg_thermal_mwm=avg_thermal,
        avg_hydro_mwm=avg_hydro,
        total_spilled_mwm=total_spilled,
    )


def calculate_firm_energy(
    hydro_plants: Sequence[HydroPlantInput],
    inflows: Sequence[InflowRecordInput],
    thermal_plants: Sequence[ThermalPlantInput],
    config: SimulationConfigInput,
    precision_mwm: float = 0.01,
    max_iterations: int = 80,
) -> FirmEnergyResult:
    """Find the maximum constant load C with zero deficit via binary search (bisection).

    Converges to precision <= precision_mwm (default 0.01 MWmês).
    """
    if precision_mwm <= 0:
        raise ValueError("Precisão deve ser maior que zero.")

    ree = calculate_ree(hydro_plants)
    ena_series = calculate_ena_series(hydro_plants, inflows, ree=ree)

    max_ena = max(ena_series.values(), default=0.0)
    max_thermal = sum(
        t.installed_power_mw * t.fc_max for t in thermal_plants if t.enabled
    )

    low = 0.0
    high = max(max_ena + ree.ea_max_total_mwm + max_thermal, 100.0)

    def _has_zero_deficit(load: float) -> bool:
        sim = run_simulation(
            hydro_plants,
            inflows,
            thermal_plants,
            replace(config, load_mwm=load),
            ree=ree,
            ena_series=ena_series,
        )
        return sim.max_deficit_mwm <= 1e-9

    # Expand upper bound if still feasible
    while _has_zero_deficit(high) and high < 1e9:
        low = high
        high *= 2.0

    iterations = 0
    while (high - low) > precision_mwm and iterations < max_iterations:
        mid = (low + high) / 2.0
        if _has_zero_deficit(mid):
            low = mid
        else:
            high = mid
        iterations += 1

    # Final simulation evaluated at the guaranteed feasible lower bound `low`
    final_sim = run_simulation(
        hydro_plants,
        inflows,
        thermal_plants,
        replace(config, load_mwm=low),
        ree=ree,
        ena_series=ena_series,
    )

    return FirmEnergyResult(
        firm_energy_mwm=low,
        iterations=iterations,
        precision_mwm=high - low,
        simulation=final_sim,
    )
