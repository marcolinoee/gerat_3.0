"""Pure Python mathematical engine for GERAT Web (REE & Curva Guia)."""

from app.engine.economics import (
    HOURS_PER_COMMERCIAL_YEAR,
    calculate_frc,
    calculate_fuel_cost_from_heat_rate,
    calculate_screening_curves,
    calculate_thermal_economics,
)
from app.engine.ree import (
    SECONDS_PER_COMMERCIAL_MONTH_MILLIONS,
    CascadeCycleError,
    CascadeReferenceError,
    build_cascades,
    calculate_ena_series,
    calculate_ree,
)
from app.engine.simulation import (
    calculate_firm_energy,
    detect_critical_period,
    run_simulation,
)
from app.engine.types import (
    CriticalPeriodResult,
    FirmEnergyResult,
    HydroPlantInput,
    InflowRecordInput,
    MonthlyResult,
    REEResult,
    ScreeningCurvePoint,
    ScreeningCurveSeries,
    SimulationConfigInput,
    SimulationResult,
    ThermalEconomicResult,
    ThermalPlantInput,
)

__all__ = [
    "CascadeCycleError",
    "CascadeReferenceError",
    "CriticalPeriodResult",
    "FirmEnergyResult",
    "HOURS_PER_COMMERCIAL_YEAR",
    "HydroPlantInput",
    "InflowRecordInput",
    "MonthlyResult",
    "REEResult",
    "SECONDS_PER_COMMERCIAL_MONTH_MILLIONS",
    "ScreeningCurvePoint",
    "ScreeningCurveSeries",
    "SimulationConfigInput",
    "SimulationResult",
    "ThermalEconomicResult",
    "ThermalPlantInput",
    "build_cascades",
    "calculate_ena_series",
    "calculate_firm_energy",
    "calculate_frc",
    "calculate_fuel_cost_from_heat_rate",
    "calculate_ree",
    "calculate_screening_curves",
    "calculate_thermal_economics",
    "detect_critical_period",
    "run_simulation",
]
