"""Initial schema for GERAT Web.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

jsonb_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "classrooms",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("invite_code", sa.String(length=32), nullable=False),
        sa.Column(
            "professor_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_classrooms_invite_code", "classrooms", ["invite_code"], unique=True)

    op.create_table(
        "classroom_memberships",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "classroom_id",
            sa.String(length=36),
            sa.ForeignKey("classrooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("classroom_id", "student_id", name="uq_classroom_student"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "owner_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "classroom_id",
            sa.String(length=36),
            sa.ForeignKey("classrooms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_index("ix_projects_classroom_id", "projects", ["classroom_id"])

    op.create_table(
        "hydro_plants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("vmax_hm3", sa.Float(), nullable=False, server_default="0"),
        sa.Column("vmin_hm3", sa.Float(), nullable=False, server_default="0"),
        sa.Column("productivity_mw_m3s", sa.Float(), nullable=False, server_default="0"),
        sa.Column("installed_power_mw", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "downstream_plant_id",
            sa.String(length=36),
            sa.ForeignKey("hydro_plants.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_hydro_plants_project_id", "hydro_plants", ["project_id"])

    op.create_table(
        "inflow_series",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "hydro_plant_id",
            sa.String(length=36),
            sa.ForeignKey("hydro_plants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("flow_m3s", sa.Float(), nullable=False),
        sa.Column("is_incremental", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("hydro_plant_id", "year", "month", name="uq_inflow_plant_ym"),
    )
    op.create_index("ix_inflow_series_hydro_plant_id", "inflow_series", ["hydro_plant_id"])

    op.create_table(
        "thermal_plants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("fuel_type", sa.String(length=20), nullable=False, server_default="GAS"),
        sa.Column("installed_power_mw", sa.Float(), nullable=False),
        sa.Column("fc_max", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("fc_min", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fixed_cost_usd_kw", sa.Float(), nullable=False, server_default="1000"),
        sa.Column("variable_cost_usd_mwh", sa.Float(), nullable=False, server_default="50"),
        sa.Column("useful_life_years", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("guide_curve", jsonb_type, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_thermal_plants_project_id", "thermal_plants", ["project_id"])

    op.create_table(
        "simulation_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("load_mwm", sa.Float(), nullable=False, server_default="5000"),
        sa.Column("initial_earm_pct", sa.Float(), nullable=False, server_default="100"),
        sa.Column("start_year", sa.Integer(), nullable=False, server_default="2015"),
        sa.Column("start_month", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("end_year", sa.Integer(), nullable=False, server_default="2024"),
        sa.Column("end_month", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("interest_rate_pct", sa.Float(), nullable=False, server_default="10"),
        sa.Column("gh_max_mwm", sa.Float(), nullable=True),
    )

    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "triggered_by_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("run_type", sa.String(length=32), nullable=False, server_default="SIMULATION"),
        sa.Column("config_snapshot", jsonb_type, nullable=False),
        sa.Column("summary", jsonb_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_simulation_runs_project_id", "simulation_runs", ["project_id"])

    op.create_table(
        "simulation_monthly_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("simulation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("enat_mwm", sa.Float(), nullable=False),
        sa.Column("total_thermal_mwm", sa.Float(), nullable=False),
        sa.Column("gh_delivered_mwm", sa.Float(), nullable=False, server_default="0"),
        sa.Column("earm_mwm", sa.Float(), nullable=False),
        sa.Column("earm_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evert_mwm", sa.Float(), nullable=False),
        sa.Column("deficit_mwm", sa.Float(), nullable=False),
        sa.Column("thermal_dispatch_by_plant", jsonb_type, nullable=False),
    )
    op.create_index(
        "ix_simulation_monthly_results_run_id", "simulation_monthly_results", ["run_id"]
    )


def downgrade() -> None:
    op.drop_table("simulation_monthly_results")
    op.drop_table("simulation_runs")
    op.drop_table("simulation_configs")
    op.drop_table("thermal_plants")
    op.drop_table("inflow_series")
    op.drop_table("hydro_plants")
    op.drop_table("projects")
    op.drop_table("classroom_memberships")
    op.drop_table("classrooms")
    op.drop_table("users")
