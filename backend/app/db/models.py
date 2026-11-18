"""PostgreSQL SQLAlchemy 2.0 ORM models for GERAT Web."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Uses native JSONB in PostgreSQL and falls back to JSON in SQLite for unit tests
JSONBVariant = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    PROFESSOR = "PROFESSOR"
    ALUNO = "ALUNO"


class FuelType(str, enum.Enum):
    COAL = "COAL"
    OIL = "OIL"
    NUCLEAR = "NUCLEAR"
    GAS = "GAS"
    OTHER = "OTHER"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False),
        nullable=False,
        default=UserRole.ALUNO,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    owned_classrooms: Mapped[list[Classroom]] = relationship(
        back_populates="professor", cascade="all, delete-orphan"
    )
    memberships: Mapped[list[ClassroomMembership]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    invite_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    professor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    professor: Mapped[User] = relationship(back_populates="owned_classrooms")
    memberships: Mapped[list[ClassroomMembership]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship(back_populates="classroom")


class ClassroomMembership(Base):
    __tablename__ = "classroom_memberships"
    __table_args__ = (
        UniqueConstraint("classroom_id", "student_id", name="uq_classroom_student"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    classroom_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    classroom: Mapped[Classroom] = relationship(back_populates="memberships")
    student: Mapped[User] = relationship(back_populates="memberships")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    classroom_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("classrooms.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    owner: Mapped[User] = relationship(back_populates="projects")
    classroom: Mapped[Classroom | None] = relationship(back_populates="projects")
    hydro_plants: Mapped[list[HydroPlant]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    thermal_plants: Mapped[list[ThermalPlant]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    simulation_config: Mapped[SimulationConfig | None] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    simulation_runs: Mapped[list[SimulationRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class HydroPlant(Base):
    __tablename__ = "hydro_plants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vmax_hm3: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    vmin_hm3: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    productivity_mw_m3s: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    installed_power_mw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    downstream_plant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("hydro_plants.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="hydro_plants")
    inflows: Mapped[list[InflowSeries]] = relationship(
        back_populates="hydro_plant", cascade="all, delete-orphan"
    )


class InflowSeries(Base):
    __tablename__ = "inflow_series"
    __table_args__ = (
        UniqueConstraint("hydro_plant_id", "year", "month", name="uq_inflow_plant_ym"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    hydro_plant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hydro_plants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    flow_m3s: Mapped[float] = mapped_column(Float, nullable=False)
    is_incremental: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    hydro_plant: Mapped[HydroPlant] = relationship(back_populates="inflows")


class ThermalPlant(Base):
    __tablename__ = "thermal_plants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    fuel_type: Mapped[FuelType] = mapped_column(
        Enum(FuelType, name="fuel_type", native_enum=False),
        nullable=False,
        default=FuelType.GAS,
    )
    installed_power_mw: Mapped[float] = mapped_column(Float, nullable=False)
    fc_max: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)
    fc_min: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fixed_cost_usd_kw: Mapped[float] = mapped_column(Float, nullable=False, default=1000.0)
    variable_cost_usd_mwh: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    useful_life_years: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    guide_curve: Mapped[list[float]] = mapped_column(
        JSONBVariant, nullable=False, default=lambda: [50.0] * 12
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    project: Mapped[Project] = relationship(back_populates="thermal_plants")


class SimulationConfig(Base):
    __tablename__ = "simulation_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    load_mwm: Mapped[float] = mapped_column(Float, nullable=False, default=5000.0)
    initial_earm_pct: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2015)
    start_month: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    end_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2024)
    end_month: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    interest_rate_pct: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    gh_max_mwm: Mapped[float | None] = mapped_column(Float, nullable=True)

    project: Mapped[Project] = relationship(back_populates="simulation_config")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    triggered_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    run_type: Mapped[str] = mapped_column(String(32), nullable=False, default="SIMULATION")
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONBVariant, nullable=False, default=dict)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONBVariant, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped[Project] = relationship(back_populates="simulation_runs")
    monthly_results: Mapped[list[SimulationMonthlyResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="SimulationMonthlyResult.year, SimulationMonthlyResult.month"
    )


class SimulationMonthlyResult(Base):
    __tablename__ = "simulation_monthly_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    enat_mwm: Mapped[float] = mapped_column(Float, nullable=False)
    total_thermal_mwm: Mapped[float] = mapped_column(Float, nullable=False)
    gh_delivered_mwm: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    earm_mwm: Mapped[float] = mapped_column(Float, nullable=False)
    earm_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evert_mwm: Mapped[float] = mapped_column(Float, nullable=False)
    deficit_mwm: Mapped[float] = mapped_column(Float, nullable=False)
    thermal_dispatch_by_plant: Mapped[dict[str, float]] = mapped_column(
        JSONBVariant, nullable=False, default=dict
    )

    run: Mapped[SimulationRun] = relationship(back_populates="monthly_results")
