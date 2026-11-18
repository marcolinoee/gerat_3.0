"""Pydantic v2 request and response schemas for GERAT Web API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.db.models import FuelType, UserRole

# Allows standard emails including internal academic domains such as professor@gerat.local
EmailAddress = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=5,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]


# ---------------------------------------------------------------------------
# Auth & Users
# ---------------------------------------------------------------------------
class UserRegisterRequest(BaseModel):
    email: EmailAddress
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    role: UserRole = UserRole.ALUNO
    invite_code: str | None = None


class UserLoginRequest(BaseModel):
    email: EmailAddress
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: UserRole
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ---------------------------------------------------------------------------
# Classrooms
# ---------------------------------------------------------------------------
class ClassroomCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None


class ClassroomJoinRequest(BaseModel):
    invite_code: str = Field(..., min_length=3, max_length=32)


class ClassroomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    invite_code: str
    professor_id: str
    created_at: datetime
    student_count: int = 0


class StudentMemberResponse(BaseModel):
    id: str
    email: str
    full_name: str
    joined_at: datetime
    project_count: int = 0


class AuditRunSummary(BaseModel):
    run_id: str
    project_id: str
    project_name: str
    student_id: str
    student_name: str
    student_email: str
    run_type: str
    created_at: datetime
    summary: dict[str, Any]


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    classroom_id: str | None = None
    is_template: bool = False


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    is_template: bool | None = None


class ProjectCloneRequest(BaseModel):
    name: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    owner_id: str
    owner_name: str | None = None
    classroom_id: str | None
    is_template: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Hydro Plants & Inflows
# ---------------------------------------------------------------------------
class HydroPlantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    vmax_hm3: float = Field(..., ge=0.0)
    vmin_hm3: float = Field(..., ge=0.0)
    productivity_mw_m3s: float = Field(..., ge=0.0)
    installed_power_mw: float = Field(default=0.0, ge=0.0)
    downstream_plant_id: str | None = None

    @field_validator("vmax_hm3")
    @classmethod
    def check_vmax(cls, v: float, info: Any) -> float:
        vmin = info.data.get("vmin_hm3")
        if vmin is not None and v < vmin:
            raise ValueError("vmax_hm3 deve ser maior ou igual a vmin_hm3.")
        return v


class HydroPlantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    vmax_hm3: float | None = Field(default=None, ge=0.0)
    vmin_hm3: float | None = Field(default=None, ge=0.0)
    productivity_mw_m3s: float | None = Field(default=None, ge=0.0)
    installed_power_mw: float | None = Field(default=None, ge=0.0)
    downstream_plant_id: str | None = None


class HydroPlantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    vmax_hm3: float
    vmin_hm3: float
    productivity_mw_m3s: float
    installed_power_mw: float
    downstream_plant_id: str | None


class REESummaryResponse(BaseModel):
    ea_max_total_mwm: float
    ea_max_by_plant_mwm: dict[str, float]
    cascades: dict[str, list[str]]
    accumulated_productivity: dict[str, float]


class InflowPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    month: int
    flow_m3s: float
    is_incremental: bool


class InflowUploadResponse(BaseModel):
    hydro_plant_id: str
    records_imported: int
    is_incremental: bool
    start_year: int
    end_year: int


# ---------------------------------------------------------------------------
# Thermal Plants & Heat Rate
# ---------------------------------------------------------------------------
class ThermalPlantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    fuel_type: FuelType = FuelType.GAS
    installed_power_mw: float = Field(..., ge=0.0)
    fc_max: float = Field(default=0.85, ge=0.0, le=1.0)
    fc_min: float = Field(default=0.0, ge=0.0, le=1.0)
    fixed_cost_usd_kw: float = Field(default=1000.0, ge=0.0)
    variable_cost_usd_mwh: float = Field(default=50.0, ge=0.0)
    useful_life_years: int = Field(default=25, ge=1, le=100)
    guide_curve: list[float] = Field(default_factory=lambda: [50.0] * 12)
    enabled: bool = True

    @field_validator("guide_curve")
    @classmethod
    def check_guide_curve(cls, v: list[float]) -> list[float]:
        if len(v) != 12:
            raise ValueError("guide_curve deve conter exatamente 12 valores mensais.")
        if any(x < 0.0 or x > 100.0 for x in v):
            raise ValueError("Valores da curva guia devem estar entre 0 e 100 (%).")
        return v


class ThermalPlantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    fuel_type: FuelType | None = None
    installed_power_mw: float | None = Field(default=None, ge=0.0)
    fc_max: float | None = Field(default=None, ge=0.0, le=1.0)
    fc_min: float | None = Field(default=None, ge=0.0, le=1.0)
    fixed_cost_usd_kw: float | None = Field(default=None, ge=0.0)
    variable_cost_usd_mwh: float | None = Field(default=None, ge=0.0)
    useful_life_years: int | None = Field(default=None, ge=1, le=100)
    guide_curve: list[float] | None = None
    enabled: bool | None = None

    @field_validator("guide_curve")
    @classmethod
    def check_guide_curve(cls, v: list[float] | None) -> list[float] | None:
        if v is None:
            return v
        if len(v) != 12:
            raise ValueError("guide_curve deve conter exatamente 12 valores mensais.")
        if any(x < 0.0 or x > 100.0 for x in v):
            raise ValueError("Valores da curva guia devem estar entre 0 e 100 (%).")
        return v


class ThermalPlantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    fuel_type: FuelType
    installed_power_mw: float
    fc_max: float
    fc_min: float
    fixed_cost_usd_kw: float
    variable_cost_usd_mwh: float
    useful_life_years: int
    guide_curve: list[float]
    enabled: bool


class HeatRateCalcRequest(BaseModel):
    heat_rate_kcal_mwh: float = Field(..., ge=0.0)
    fuel_price_usd_unit: float = Field(..., ge=0.0)
    pci_kcal_unit: float = Field(..., gt=0.0)


class HeatRateCalcResponse(BaseModel):
    variable_cost_usd_mwh: float


# ---------------------------------------------------------------------------
# Simulation Config & Results
# ---------------------------------------------------------------------------
class SimulationConfigUpdate(BaseModel):
    load_mwm: float = Field(..., ge=0.0)
    initial_earm_pct: float = Field(..., ge=0.0, le=100.0)
    start_year: int = Field(..., ge=1900, le=2200)
    start_month: int = Field(..., ge=1, le=12)
    end_year: int = Field(..., ge=1900, le=2200)
    end_month: int = Field(..., ge=1, le=12)
    interest_rate_pct: float = Field(default=10.0, ge=0.0, le=100.0)
    gh_max_mwm: float | None = Field(default=None, ge=0.0)


class SimulationConfigResponse(SimulationConfigUpdate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str


class MonthlyResultResponse(BaseModel):
    year: int
    month: int
    enat_mwm: float
    total_thermal_mwm: float
    gh_delivered_mwm: float
    earm_mwm: float
    earm_pct: float
    evert_mwm: float
    deficit_mwm: float
    thermal_dispatch_by_plant: dict[str, float]


class SimulationRunResponse(BaseModel):
    id: str
    project_id: str
    run_type: str
    config_snapshot: dict[str, Any]
    summary: dict[str, Any]
    created_at: datetime
    monthly_results: list[MonthlyResultResponse] = []


class ScreeningPointResponse(BaseModel):
    hours: float
    total_cost_usd: float
    total_cost_kusd: float
    unit_cost_usd_kw_year: float


class ScreeningSeriesResponse(BaseModel):
    plant_id: str
    name: str
    fuel_type: str
    installed_power_mw: float
    frc: float
    fixed_cost_usd_year: float
    variable_cost_usd_mwh: float
    points: list[ScreeningPointResponse]


class SensitivityResponse(BaseModel):
    interest_rate_pct: float
    series: list[ScreeningSeriesResponse]
