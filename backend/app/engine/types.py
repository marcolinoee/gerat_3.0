"""Pure data structures for the GERAT mathematical engine."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HydroPlantInput:
    """Hydroelectric plant parameters for REE and ENA calculation."""

    plant_id: str
    name: str
    vmax_hm3: float
    vmin_hm3: float
    productivity_mw_m3s: float
    downstream_plant_id: str | None = None
    installed_power_mw: float = 0.0


@dataclass(frozen=True)
class InflowRecordInput:
    """Single monthly inflow record for a hydro plant."""

    plant_id: str
    year: int
    month: int  # 1..12
    flow_m3s: float
    is_incremental: bool = False


@dataclass(frozen=True)
class ThermalPlantInput:
    """Thermal plant parameters for Curva Guia dispatch and economics."""

    plant_id: str
    name: str
    fuel_type: str  # COAL, OIL, NUCLEAR, GAS, OTHER
    installed_power_mw: float
    fc_max: float  # 0..1
    fc_min: float  # 0..1
    fixed_cost_usd_kw: float
    variable_cost_usd_mwh: float
    useful_life_years: int
    guide_curve: list[float]  # 12 values (Jan..Dec) in % [0..100]
    enabled: bool = True


@dataclass(frozen=True)
class SimulationConfigInput:
    """Configuration for a hydrothermal simulation run."""

    load_mwm: float
    initial_earm_pct: float  # 0..100
    start_year: int
    start_month: int  # 1..12
    end_year: int
    end_month: int  # 1..12
    interest_rate_pct: float = 10.0  # Annual interest rate in % (e.g. 10.0 -> 0.10)
    gh_max_mwm: float | None = None


@dataclass(frozen=True)
class REEResult:
    """Result of Equivalent Energy Reservoir (REE) calculation."""

    ea_max_total_mwm: float
    ea_max_by_plant_mwm: dict[str, float]
    cascades: dict[str, list[str]]
    accumulated_productivity: dict[str, float]


@dataclass(frozen=True)
class MonthlyResult:
    """Monthly output of the hydrothermal simulation."""

    year: int
    month: int
    enat_mwm: float
    total_thermal_mwm: float
    gh_req_mwm: float
    gh_efet_mwm: float
    gh_delivered_mwm: float
    earm_mwm: float
    earm_pct: float
    evert_mwm: float
    deficit_pot_mwm: float
    deficit_en_mwm: float
    deficit_mwm: float
    thermal_dispatch_by_plant: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CriticalPeriodResult:
    """Critical period of the simulated reservoir trajectory."""

    start_year: int
    start_month: int
    end_year: int
    end_month: int
    duration_months: int
    min_earm_mwm: float
    min_earm_pct: float


@dataclass(frozen=True)
class ThermalEconomicResult:
    """Annual economic summary for a single thermal plant."""

    plant_id: str
    name: str
    fuel_type: str
    installed_power_mw: float
    avg_generation_mwm: float
    frc: float
    fixed_cost_usd_year: float
    variable_cost_usd_year: float
    total_cost_usd_year: float
    fixed_cost_kusd_year: float
    variable_cost_kusd_year: float
    total_cost_kusd_year: float


@dataclass(frozen=True)
class SimulationResult:
    """Full output of a hydrothermal simulation run."""

    ea_max_mwm: float
    initial_earm_mwm: float
    monthly_results: list[MonthlyResult]
    critical_period: CriticalPeriodResult | None
    economics: list[ThermalEconomicResult]
    total_fixed_cost_usd_year: float
    total_variable_cost_usd_year: float
    total_cost_usd_year: float
    total_cost_kusd_year: float
    max_deficit_mwm: float
    total_deficit_mwm: float
    deficit_months: int
    avg_ena_mwm: float
    avg_thermal_mwm: float
    avg_hydro_mwm: float
    total_spilled_mwm: float


@dataclass(frozen=True)
class FirmEnergyResult:
    """Result of the binary search for Firm Energy."""

    firm_energy_mwm: float
    iterations: int
    precision_mwm: float
    simulation: SimulationResult


@dataclass(frozen=True)
class ScreeningCurvePoint:
    """Single point on a thermal plant's screening curve."""

    hours: float
    total_cost_usd: float
    total_cost_kusd: float
    unit_cost_usd_kw_year: float


@dataclass(frozen=True)
class ScreeningCurveSeries:
    """Screening curve data for a thermal plant."""

    plant_id: str
    name: str
    fuel_type: str
    installed_power_mw: float
    frc: float
    fixed_cost_usd_year: float
    variable_cost_usd_mwh: float
    points: list[ScreeningCurvePoint]
