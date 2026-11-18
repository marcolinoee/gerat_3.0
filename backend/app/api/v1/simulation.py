"""Simulation config, hydrothermal execution, Firm Energy, Sensitivity, CSV & PDF export."""

from __future__ import annotations

import csv
import io
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authorized_project, get_current_user
from app.db.models import (
    Classroom,
    HydroPlant,
    InflowSeries,
    Project,
    SimulationConfig,
    SimulationMonthlyResult,
    SimulationRun,
    ThermalPlant,
    User,
)
from app.db.session import get_db
from app.engine import (
    CascadeCycleError,
    CascadeReferenceError,
    HydroPlantInput,
    InflowRecordInput,
    SimulationConfigInput,
    SimulationResult,
    ThermalPlantInput,
    calculate_firm_energy,
    calculate_screening_curves,
    run_simulation,
)
from app.engine.parsers import sanitize_csv_cell
from app.reports.pdf_generator import generate_technical_report_pdf
from app.schemas.schemas import (
    MonthlyResultResponse,
    ScreeningPointResponse,
    ScreeningSeriesResponse,
    SensitivityResponse,
    SimulationConfigResponse,
    SimulationConfigUpdate,
    SimulationRunResponse,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["simulation"])


async def _load_project_engine_inputs(
    project_id: str, db: AsyncSession
) -> tuple[
    list[HydroPlant],
    list[HydroPlantInput],
    list[InflowRecordInput],
    list[ThermalPlant],
    list[ThermalPlantInput],
    SimulationConfig,
]:
    hydro_rows = list(
        (await db.execute(select(HydroPlant).where(HydroPlant.project_id == project_id)))
        .scalars()
        .all()
    )
    hydro_ids = [h.id for h in hydro_rows]

    inflow_rows: list[InflowSeries] = []
    if hydro_ids:
        inflow_rows = list(
            (
                await db.execute(
                    select(InflowSeries).where(InflowSeries.hydro_plant_id.in_(hydro_ids))
                )
            )
            .scalars()
            .all()
        )

    thermal_rows = list(
        (
            await db.execute(
                select(ThermalPlant)
                .where(ThermalPlant.project_id == project_id)
                .order_by(ThermalPlant.variable_cost_usd_mwh)
            )
        )
        .scalars()
        .all()
    )

    cfg = (
        await db.execute(
            select(SimulationConfig).where(SimulationConfig.project_id == project_id)
        )
    ).scalar_one_or_none()
    if cfg is None:
        cfg = SimulationConfig(project_id=project_id)
        db.add(cfg)
        await db.flush()

    hydro_inputs = [
        HydroPlantInput(
            plant_id=h.id,
            name=h.name,
            vmax_hm3=h.vmax_hm3,
            vmin_hm3=h.vmin_hm3,
            productivity_mw_m3s=h.productivity_mw_m3s,
            downstream_plant_id=h.downstream_plant_id,
            installed_power_mw=h.installed_power_mw,
        )
        for h in hydro_rows
    ]
    inflow_inputs = [
        InflowRecordInput(
            plant_id=inf.hydro_plant_id,
            year=inf.year,
            month=inf.month,
            flow_m3s=inf.flow_m3s,
            is_incremental=inf.is_incremental,
        )
        for inf in inflow_rows
    ]
    thermal_inputs = [
        ThermalPlantInput(
            plant_id=t.id,
            name=t.name,
            fuel_type=t.fuel_type.value if hasattr(t.fuel_type, "value") else str(t.fuel_type),
            installed_power_mw=t.installed_power_mw,
            fc_max=t.fc_max,
            fc_min=t.fc_min,
            fixed_cost_usd_kw=t.fixed_cost_usd_kw,
            variable_cost_usd_mwh=t.variable_cost_usd_mwh,
            useful_life_years=t.useful_life_years,
            guide_curve=list(t.guide_curve),
            enabled=t.enabled,
        )
        for t in thermal_rows
    ]
    return hydro_rows, hydro_inputs, inflow_inputs, thermal_rows, thermal_inputs, cfg


def _serialize_summary(sim: SimulationResult, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ea_max_mwm": round(sim.ea_max_mwm, 4),
        "initial_earm_mwm": round(sim.initial_earm_mwm, 4),
        "critical_period": asdict(sim.critical_period) if sim.critical_period else None,
        "economics": [asdict(e) for e in sim.economics],
        "total_fixed_cost_usd_year": sim.total_fixed_cost_usd_year,
        "total_variable_cost_usd_year": sim.total_variable_cost_usd_year,
        "total_cost_usd_year": sim.total_cost_usd_year,
        "total_cost_kusd_year": sim.total_cost_kusd_year,
        "max_deficit_mwm": sim.max_deficit_mwm,
        "total_deficit_mwm": sim.total_deficit_mwm,
        "deficit_months": sim.deficit_months,
        "avg_ena_mwm": sim.avg_ena_mwm,
        "avg_thermal_mwm": sim.avg_thermal_mwm,
        "avg_hydro_mwm": sim.avg_hydro_mwm,
        "total_spilled_mwm": sim.total_spilled_mwm,
    }
    if extra:
        data.update(extra)
    return data


async def _persist_run(
    *,
    db: AsyncSession,
    project: Project,
    user: User,
    run_type: str,
    cfg_input: SimulationConfigInput,
    sim: SimulationResult,
    extra_summary: dict[str, Any] | None = None,
) -> SimulationRunResponse:
    config_snapshot = asdict(cfg_input)
    summary = _serialize_summary(sim, extra=extra_summary)

    run = SimulationRun(
        project_id=project.id,
        triggered_by_id=user.id,
        run_type=run_type,
        config_snapshot=config_snapshot,
        summary=summary,
    )
    db.add(run)
    await db.flush()

    monthly_orm = [
        SimulationMonthlyResult(
            run_id=run.id,
            year=m.year,
            month=m.month,
            enat_mwm=m.enat_mwm,
            total_thermal_mwm=m.total_thermal_mwm,
            gh_delivered_mwm=m.gh_delivered_mwm,
            earm_mwm=m.earm_mwm,
            earm_pct=m.earm_pct,
            evert_mwm=m.evert_mwm,
            deficit_mwm=m.deficit_mwm,
            thermal_dispatch_by_plant=m.thermal_dispatch_by_plant,
        )
        for m in sim.monthly_results
    ]
    db.add_all(monthly_orm)
    await db.commit()
    await db.refresh(run)

    return SimulationRunResponse(
        id=run.id,
        project_id=run.project_id,
        run_type=run.run_type,
        config_snapshot=run.config_snapshot,
        summary=run.summary,
        created_at=run.created_at,
        monthly_results=[
            MonthlyResultResponse(
                year=m.year,
                month=m.month,
                enat_mwm=m.enat_mwm,
                total_thermal_mwm=m.total_thermal_mwm,
                gh_delivered_mwm=m.gh_delivered_mwm,
                earm_mwm=m.earm_mwm,
                earm_pct=m.earm_pct,
                evert_mwm=m.evert_mwm,
                deficit_mwm=m.deficit_mwm,
                thermal_dispatch_by_plant=m.thermal_dispatch_by_plant,
            )
            for m in sim.monthly_results
        ],
    )


@router.get("/config", response_model=SimulationConfigResponse)
async def get_config(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SimulationConfigResponse:
    await get_authorized_project(project_id, user, db, require_write=False)
    cfg = (
        await db.execute(
            select(SimulationConfig).where(SimulationConfig.project_id == project_id)
        )
    ).scalar_one_or_none()
    if cfg is None:
        cfg = SimulationConfig(project_id=project_id)
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return SimulationConfigResponse.model_validate(cfg)


@router.put("/config", response_model=SimulationConfigResponse)
async def update_config(
    project_id: str,
    payload: SimulationConfigUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SimulationConfigResponse:
    await get_authorized_project(project_id, user, db, require_write=True)
    if (payload.start_year, payload.start_month) > (payload.end_year, payload.end_month):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Data inicial não pode ser posterior à data final.",
        )

    cfg = (
        await db.execute(
            select(SimulationConfig).where(SimulationConfig.project_id == project_id)
        )
    ).scalar_one_or_none()
    if cfg is None:
        cfg = SimulationConfig(project_id=project_id)
        db.add(cfg)

    for key, val in payload.model_dump().items():
        setattr(cfg, key, val)

    await db.commit()
    await db.refresh(cfg)
    return SimulationConfigResponse.model_validate(cfg)


@router.post("/simulate", response_model=SimulationRunResponse)
async def execute_simulation(
    project_id: str,
    override: SimulationConfigUpdate | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SimulationRunResponse:
    project = await get_authorized_project(project_id, user, db, require_write=False)
    _, hydro_inputs, inflow_inputs, _, thermal_inputs, cfg = await _load_project_engine_inputs(
        project_id, db
    )

    cfg_src = override if override is not None else cfg
    cfg_input = SimulationConfigInput(
        load_mwm=cfg_src.load_mwm,
        initial_earm_pct=cfg_src.initial_earm_pct,
        start_year=cfg_src.start_year,
        start_month=cfg_src.start_month,
        end_year=cfg_src.end_year,
        end_month=cfg_src.end_month,
        interest_rate_pct=cfg_src.interest_rate_pct,
        gh_max_mwm=cfg_src.gh_max_mwm,
    )

    try:
        sim_result = await run_in_threadpool(
            run_simulation, hydro_inputs, inflow_inputs, thermal_inputs, cfg_input
        )
    except (CascadeCycleError, CascadeReferenceError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return await _persist_run(
        db=db,
        project=project,
        user=user,
        run_type="SIMULATION",
        cfg_input=cfg_input,
        sim=sim_result,
    )


@router.post("/firm-energy", response_model=SimulationRunResponse)
async def execute_firm_energy(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SimulationRunResponse:
    project = await get_authorized_project(project_id, user, db, require_write=False)
    _, hydro_inputs, inflow_inputs, _, thermal_inputs, cfg = await _load_project_engine_inputs(
        project_id, db
    )

    cfg_input = SimulationConfigInput(
        load_mwm=cfg.load_mwm,
        initial_earm_pct=cfg.initial_earm_pct,
        start_year=cfg.start_year,
        start_month=cfg.start_month,
        end_year=cfg.end_year,
        end_month=cfg.end_month,
        interest_rate_pct=cfg.interest_rate_pct,
        gh_max_mwm=cfg.gh_max_mwm,
    )

    try:
        firm_res = await run_in_threadpool(
            calculate_firm_energy, hydro_inputs, inflow_inputs, thermal_inputs, cfg_input
        )
    except (CascadeCycleError, CascadeReferenceError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    final_cfg = SimulationConfigInput(
        load_mwm=round(firm_res.firm_energy_mwm, 4),
        initial_earm_pct=cfg.initial_earm_pct,
        start_year=cfg.start_year,
        start_month=cfg.start_month,
        end_year=cfg.end_year,
        end_month=cfg.end_month,
        interest_rate_pct=cfg.interest_rate_pct,
        gh_max_mwm=cfg.gh_max_mwm,
    )

    return await _persist_run(
        db=db,
        project=project,
        user=user,
        run_type="FIRM_ENERGY",
        cfg_input=final_cfg,
        sim=firm_res.simulation,
        extra_summary={
            "firm_energy_mwm": round(firm_res.firm_energy_mwm, 4),
            "bisection_iterations": firm_res.iterations,
            "bisection_precision_mwm": firm_res.precision_mwm,
        },
    )


@router.get("/sensitivity", response_model=SensitivityResponse)
async def get_sensitivity(
    project_id: str,
    interest_rate_pct: float = Query(default=10.0, ge=0.0, le=100.0),
    steps: int = Query(default=37, ge=5, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SensitivityResponse:
    await get_authorized_project(project_id, user, db, require_write=False)
    _, _, _, _, thermal_inputs, _ = await _load_project_engine_inputs(project_id, db)

    curves = await run_in_threadpool(
        calculate_screening_curves, thermal_inputs, interest_rate_pct, steps
    )

    return SensitivityResponse(
        interest_rate_pct=interest_rate_pct,
        series=[
            ScreeningSeriesResponse(
                plant_id=c.plant_id,
                name=c.name,
                fuel_type=c.fuel_type,
                installed_power_mw=c.installed_power_mw,
                frc=c.frc,
                fixed_cost_usd_year=c.fixed_cost_usd_year,
                variable_cost_usd_mwh=c.variable_cost_usd_mwh,
                points=[
                    ScreeningPointResponse(
                        hours=p.hours,
                        total_cost_usd=p.total_cost_usd,
                        total_cost_kusd=p.total_cost_kusd,
                        unit_cost_usd_kw_year=p.unit_cost_usd_kw_year,
                    )
                    for p in c.points
                ],
            )
            for c in curves
        ],
    )


@router.get("/runs", response_model=list[SimulationRunResponse])
async def list_runs(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SimulationRunResponse]:
    await get_authorized_project(project_id, user, db, require_write=False)
    res = await db.execute(
        select(SimulationRun)
        .where(SimulationRun.project_id == project_id)
        .order_by(SimulationRun.created_at.desc())
        .limit(30)
    )
    runs = list(res.scalars().all())
    return [
        SimulationRunResponse(
            id=r.id,
            project_id=r.project_id,
            run_type=r.run_type,
            config_snapshot=r.config_snapshot,
            summary=r.summary,
            created_at=r.created_at,
            monthly_results=[],
        )
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=SimulationRunResponse)
async def get_run_detail(
    project_id: str,
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SimulationRunResponse:
    await get_authorized_project(project_id, user, db, require_write=False)
    run = (
        await db.execute(
            select(SimulationRun).where(
                SimulationRun.id == run_id, SimulationRun.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulação não encontrada.")

    monthly = list(
        (
            await db.execute(
                select(SimulationMonthlyResult)
                .where(SimulationMonthlyResult.run_id == run.id)
                .order_by(SimulationMonthlyResult.year, SimulationMonthlyResult.month)
            )
        )
        .scalars()
        .all()
    )

    return SimulationRunResponse(
        id=run.id,
        project_id=run.project_id,
        run_type=run.run_type,
        config_snapshot=run.config_snapshot,
        summary=run.summary,
        created_at=run.created_at,
        monthly_results=[
            MonthlyResultResponse(
                year=m.year,
                month=m.month,
                enat_mwm=m.enat_mwm,
                total_thermal_mwm=m.total_thermal_mwm,
                gh_delivered_mwm=m.gh_delivered_mwm,
                earm_mwm=m.earm_mwm,
                earm_pct=m.earm_pct,
                evert_mwm=m.evert_mwm,
                deficit_mwm=m.deficit_mwm,
                thermal_dispatch_by_plant=m.thermal_dispatch_by_plant,
            )
            for m in monthly
        ],
    )


@router.get("/runs/{run_id}/export-csv")
async def export_run_csv(
    project_id: str,
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    project = await get_authorized_project(project_id, user, db, require_write=False)
    run = (
        await db.execute(
            select(SimulationRun).where(
                SimulationRun.id == run_id, SimulationRun.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulação não encontrada.")

    monthly = list(
        (
            await db.execute(
                select(SimulationMonthlyResult)
                .where(SimulationMonthlyResult.run_id == run.id)
                .order_by(SimulationMonthlyResult.year, SimulationMonthlyResult.month)
            )
        )
        .scalars()
        .all()
    )
    thermals = list(
        (await db.execute(select(ThermalPlant).where(ThermalPlant.project_id == project_id)))
        .scalars()
        .all()
    )
    t_names = {t.id: sanitize_csv_cell(t.name) for t in thermals}
    t_ids = [t.id for t in thermals]

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    header = [
        "Projeto",
        "Ano",
        "Mes",
        "ENA_MWmes",
        "GH_MWmes",
        "GT_Total_MWmes",
        "EA_MWmes",
        "EA_Pct",
        "Vertimento_MWmes",
        "Deficit_MWmes",
        *[f"GT_{t_names[tid]}" for tid in t_ids],
    ]
    writer.writerow(header)

    safe_proj_name = sanitize_csv_cell(project.name)
    for m in monthly:
        disp = m.thermal_dispatch_by_plant or {}
        writer.writerow(
            [
                safe_proj_name,
                m.year,
                m.month,
                f"{m.enat_mwm:.2f}",
                f"{m.gh_delivered_mwm:.2f}",
                f"{m.total_thermal_mwm:.2f}",
                f"{m.earm_mwm:.2f}",
                f"{m.earm_pct:.2f}",
                f"{m.evert_mwm:.2f}",
                f"{m.deficit_mwm:.2f}",
                *[f"{float(disp.get(tid, 0.0)):.2f}" for tid in t_ids],
            ]
        )

    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="gerat_run_{run.id[:8]}.csv"'
        },
    )


@router.get("/runs/{run_id}/report-pdf")
async def export_run_pdf(
    project_id: str,
    run_id: str,
    include_monthly_table: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    project = await get_authorized_project(project_id, user, db, require_write=False)
    run = (
        await db.execute(
            select(SimulationRun).where(
                SimulationRun.id == run_id, SimulationRun.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulação não encontrada.")

    hydro_rows, _, _, thermal_rows, thermal_inputs, _ = await _load_project_engine_inputs(
        project_id, db
    )
    monthly = list(
        (
            await db.execute(
                select(SimulationMonthlyResult)
                .where(SimulationMonthlyResult.run_id == run.id)
                .order_by(SimulationMonthlyResult.year, SimulationMonthlyResult.month)
            )
        )
        .scalars()
        .all()
    )

    owner = (
        await db.execute(select(User).where(User.id == project.owner_id))
    ).scalar_one_or_none()
    classroom_name: str | None = None
    if project.classroom_id:
        cls = (
            await db.execute(select(Classroom).where(Classroom.id == project.classroom_id))
        ).scalar_one_or_none()
        classroom_name = cls.name if cls else None

    interest_rate = float(run.config_snapshot.get("interest_rate_pct", 10.0))
    screening_objs = await run_in_threadpool(
        calculate_screening_curves, thermal_inputs, interest_rate, 37
    )
    screening_dicts = [asdict(s) for s in screening_objs]

    hydro_dicts = [
        {
            "id": h.id,
            "name": h.name,
            "vmax_hm3": h.vmax_hm3,
            "vmin_hm3": h.vmin_hm3,
            "productivity_mw_m3s": h.productivity_mw_m3s,
            "installed_power_mw": h.installed_power_mw,
        }
        for h in hydro_rows
    ]
    thermal_dicts = [
        {
            "id": t.id,
            "name": t.name,
            "fuel_type": t.fuel_type.value if hasattr(t.fuel_type, "value") else str(t.fuel_type),
            "installed_power_mw": t.installed_power_mw,
            "fc_max": t.fc_max,
            "fc_min": t.fc_min,
            "fixed_cost_usd_kw": t.fixed_cost_usd_kw,
            "variable_cost_usd_mwh": t.variable_cost_usd_mwh,
            "useful_life_years": t.useful_life_years,
        }
        for t in thermal_rows
    ]
    monthly_dicts = [
        {
            "year": m.year,
            "month": m.month,
            "enat_mwm": m.enat_mwm,
            "total_thermal_mwm": m.total_thermal_mwm,
            "gh_delivered_mwm": m.gh_delivered_mwm,
            "earm_mwm": m.earm_mwm,
            "earm_pct": m.earm_pct,
            "evert_mwm": m.evert_mwm,
            "deficit_mwm": m.deficit_mwm,
            "thermal_dispatch_by_plant": m.thermal_dispatch_by_plant,
        }
        for m in monthly
    ]

    pdf_bytes = await run_in_threadpool(
        generate_technical_report_pdf,
        project_name=project.name,
        classroom_name=classroom_name,
        author_name=owner.full_name if owner else user.full_name,
        author_email=owner.email if owner else user.email,
        generated_at=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        hydro_plants=hydro_dicts,
        thermal_plants=thermal_dicts,
        config_snapshot=run.config_snapshot,
        summary=run.summary,
        monthly_results=monthly_dicts,
        screening_series=screening_dicts,
        include_monthly_table=include_monthly_table,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="relatorio_gerat_{run.id[:8]}.pdf"'
        },
    )
