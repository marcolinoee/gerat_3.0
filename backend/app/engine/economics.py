"""Economic model, Heat Rate variable cost calculator, and Screening Curves."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.engine.types import (
    ScreeningCurvePoint,
    ScreeningCurveSeries,
    ThermalEconomicResult,
    ThermalPlantInput,
)

# Commercial year: 360 days * 24 hours = 8640 hours
HOURS_PER_COMMERCIAL_YEAR: float = 8640.0


def calculate_fuel_cost_from_heat_rate(
    heat_rate_kcal_mwh: float,
    fuel_price_usd_unit: float,
    pci_kcal_unit: float,
) -> float:
    """Compute thermal variable fuel cost in US$/MWh from Heat Rate, fuel price, and LHV (PCI).

    C_comb = (HeatRate * P_comb) / PCI  [US$/MWh]
    """
    if pci_kcal_unit <= 0:
        raise ValueError("PCI (Poder Calorífico Inferior) deve ser maior que zero.")
    if heat_rate_kcal_mwh < 0:
        raise ValueError("Heat Rate não pode ser negativo.")
    if fuel_price_usd_unit < 0:
        raise ValueError("Preço do combustível não pode ser negativo.")

    return (heat_rate_kcal_mwh * fuel_price_usd_unit) / pci_kcal_unit


def calculate_frc(interest_rate_pct: float, useful_life_years: int) -> float:
    """Compute Capital Recovery Factor (FRC).

    FRC = (i * (1 + i)^n) / ((1 + i)^n - 1), where i is annual interest rate in decimal.
    If i == 0, FRC = 1 / n.
    """
    if useful_life_years <= 0:
        raise ValueError("Vida útil (n) deve ser maior que zero.")
    if interest_rate_pct < 0:
        raise ValueError("Taxa de juros não pode ser negativa.")

    i = interest_rate_pct / 100.0
    if i == 0.0:
        return 1.0 / useful_life_years

    factor = (1.0 + i) ** useful_life_years
    return (i * factor) / (factor - 1.0)


def calculate_thermal_economics(
    thermals: Sequence[ThermalPlantInput],
    avg_generation_by_plant: dict[str, float],
    interest_rate_pct: float,
) -> list[ThermalEconomicResult]:
    """Calculate annualized Fixed, Variable, and Total costs for enabled thermal plants.

    CF_j = C_fixo,j * (P_inst,j * 1000) * FRC_j      [US$/ano]
    CV_j = GT_avg,j * C_comb,j * 8640                [US$/ano]
    CT_j = CF_j + CV_j                               [US$/ano]
    """
    results: list[ThermalEconomicResult] = []

    for plant in thermals:
        if not plant.enabled:
            continue

        frc = calculate_frc(interest_rate_pct, plant.useful_life_years)
        avg_gt = avg_generation_by_plant.get(plant.plant_id, 0.0)

        cf = plant.fixed_cost_usd_kw * (plant.installed_power_mw * 1000.0) * frc
        cv = avg_gt * plant.variable_cost_usd_mwh * HOURS_PER_COMMERCIAL_YEAR
        ct = cf + cv

        results.append(
            ThermalEconomicResult(
                plant_id=plant.plant_id,
                name=plant.name,
                fuel_type=plant.fuel_type,
                installed_power_mw=plant.installed_power_mw,
                avg_generation_mwm=avg_gt,
                frc=frc,
                fixed_cost_usd_year=cf,
                variable_cost_usd_year=cv,
                total_cost_usd_year=ct,
                fixed_cost_kusd_year=cf / 1000.0,
                variable_cost_kusd_year=cv / 1000.0,
                total_cost_kusd_year=ct / 1000.0,
            )
        )

    return results


def calculate_screening_curves(
    thermals: Sequence[ThermalPlantInput],
    interest_rate_pct: float,
    steps: int = 37,
) -> list[ScreeningCurveSeries]:
    """Compute Sensitivity / Screening Curves for h in [0, 8640].

    C_total,j(h, i) = CF_j(i) + C_comb,j * P_inst,j * h
    Also computes unit_cost_usd_kw_year = C_total,j(h, i) / (P_inst,j * 1000)
    for direct comparison across plants of different sizes.
    """
    if steps < 2:
        raise ValueError("Número de pontos deve ser >= 2.")

    hours_grid = np.linspace(0.0, HOURS_PER_COMMERCIAL_YEAR, steps)
    series_list: list[ScreeningCurveSeries] = []

    for plant in thermals:
        if not plant.enabled:
            continue

        frc = calculate_frc(interest_rate_pct, plant.useful_life_years)
        cf = plant.fixed_cost_usd_kw * (plant.installed_power_mw * 1000.0) * frc
        kw = plant.installed_power_mw * 1000.0

        points: list[ScreeningCurvePoint] = []
        for h_val in hours_grid:
            h = float(h_val)
            total_usd = cf + plant.variable_cost_usd_mwh * plant.installed_power_mw * h
            unit_cost = total_usd / kw if kw > 0 else 0.0
            points.append(
                ScreeningCurvePoint(
                    hours=round(h, 2),
                    total_cost_usd=total_usd,
                    total_cost_kusd=total_usd / 1000.0,
                    unit_cost_usd_kw_year=unit_cost,
                )
            )

        series_list.append(
            ScreeningCurveSeries(
                plant_id=plant.plant_id,
                name=plant.name,
                fuel_type=plant.fuel_type,
                installed_power_mw=plant.installed_power_mw,
                frc=frc,
                fixed_cost_usd_year=cf,
                variable_cost_usd_mwh=plant.variable_cost_usd_mwh,
                points=points,
            )
        )

    return series_list
