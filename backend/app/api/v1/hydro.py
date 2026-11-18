"""Hydroelectric plants CRUD, REE summary, and inflow series upload endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authorized_project, get_current_user
from app.db.models import HydroPlant, InflowSeries, User
from app.db.session import get_db
from app.engine import (
    CascadeCycleError,
    CascadeReferenceError,
    HydroPlantInput,
    build_cascades,
    calculate_ree,
)
from app.engine.parsers import MAX_INFLOW_FILE_SIZE_BYTES, parse_inflow_file
from app.schemas.schemas import (
    HydroPlantCreate,
    HydroPlantResponse,
    HydroPlantUpdate,
    InflowPointResponse,
    InflowUploadResponse,
    REESummaryResponse,
)

router = APIRouter(prefix="/projects/{project_id}/hydro-plants", tags=["hydro"])


def _to_engine_hydro(plants: list[HydroPlant]) -> list[HydroPlantInput]:
    return [
        HydroPlantInput(
            plant_id=p.id,
            name=p.name,
            vmax_hm3=p.vmax_hm3,
            vmin_hm3=p.vmin_hm3,
            productivity_mw_m3s=p.productivity_mw_m3s,
            downstream_plant_id=p.downstream_plant_id,
            installed_power_mw=p.installed_power_mw,
        )
        for p in plants
    ]


@router.get("", response_model=list[HydroPlantResponse])
async def list_hydro_plants(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[HydroPlantResponse]:
    await get_authorized_project(project_id, user, db, require_write=False)
    res = await db.execute(
        select(HydroPlant).where(HydroPlant.project_id == project_id).order_by(HydroPlant.name)
    )
    return [HydroPlantResponse.model_validate(p) for p in res.scalars().all()]


@router.get("/ree", response_model=REESummaryResponse)
async def get_project_ree(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> REESummaryResponse:
    await get_authorized_project(project_id, user, db, require_write=False)
    res = await db.execute(select(HydroPlant).where(HydroPlant.project_id == project_id))
    plants = list(res.scalars().all())
    try:
        ree = await run_in_threadpool(calculate_ree, _to_engine_hydro(plants))
    except (CascadeCycleError, CascadeReferenceError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return REESummaryResponse(
        ea_max_total_mwm=ree.ea_max_total_mwm,
        ea_max_by_plant_mwm=ree.ea_max_by_plant_mwm,
        cascades=ree.cascades,
        accumulated_productivity=ree.accumulated_productivity,
    )


@router.post("", response_model=HydroPlantResponse, status_code=status.HTTP_201_CREATED)
async def create_hydro_plant(
    project_id: str,
    payload: HydroPlantCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HydroPlantResponse:
    await get_authorized_project(project_id, user, db, require_write=True)

    existing = list(
        (await db.execute(select(HydroPlant).where(HydroPlant.project_id == project_id)))
        .scalars()
        .all()
    )

    plant = HydroPlant(
        project_id=project_id,
        name=payload.name.strip(),
        vmax_hm3=payload.vmax_hm3,
        vmin_hm3=payload.vmin_hm3,
        productivity_mw_m3s=payload.productivity_mw_m3s,
        installed_power_mw=payload.installed_power_mw,
        downstream_plant_id=payload.downstream_plant_id or None,
    )
    db.add(plant)
    await db.flush()

    # Validate DAG acyclicity
    try:
        build_cascades(_to_engine_hydro([*existing, plant]))
    except (CascadeCycleError, CascadeReferenceError) as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    await db.commit()
    await db.refresh(plant)
    return HydroPlantResponse.model_validate(plant)


@router.patch("/{plant_id}", response_model=HydroPlantResponse)
async def update_hydro_plant(
    project_id: str,
    plant_id: str,
    payload: HydroPlantUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HydroPlantResponse:
    await get_authorized_project(project_id, user, db, require_write=True)

    res = await db.execute(
        select(HydroPlant).where(
            HydroPlant.id == plant_id, HydroPlant.project_id == project_id
        )
    )
    plant = res.scalar_one_or_none()
    if plant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usina hidrelétrica não encontrada.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        if key == "name" and val is not None:
            setattr(plant, key, val.strip())
        elif key == "downstream_plant_id":
            setattr(plant, key, val or None)
        else:
            setattr(plant, key, val)

    if plant.vmax_hm3 < plant.vmin_hm3:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="vmax_hm3 deve ser maior ou igual a vmin_hm3.",
        )

    await db.flush()
    all_plants = list(
        (await db.execute(select(HydroPlant).where(HydroPlant.project_id == project_id)))
        .scalars()
        .all()
    )
    try:
        build_cascades(_to_engine_hydro(all_plants))
    except (CascadeCycleError, CascadeReferenceError) as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    await db.commit()
    await db.refresh(plant)
    return HydroPlantResponse.model_validate(plant)


@router.delete("/{plant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hydro_plant(
    project_id: str,
    plant_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await get_authorized_project(project_id, user, db, require_write=True)
    res = await db.execute(
        select(HydroPlant).where(
            HydroPlant.id == plant_id, HydroPlant.project_id == project_id
        )
    )
    plant = res.scalar_one_or_none()
    if plant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usina hidrelétrica não encontrada.")

    # Clear references from upstream plants
    upstream_res = await db.execute(
        select(HydroPlant).where(
            HydroPlant.project_id == project_id,
            HydroPlant.downstream_plant_id == plant_id,
        )
    )
    for up in upstream_res.scalars().all():
        up.downstream_plant_id = None

    await db.delete(plant)
    await db.commit()


@router.get("/{plant_id}/inflows", response_model=list[InflowPointResponse])
async def list_inflows(
    project_id: str,
    plant_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InflowPointResponse]:
    await get_authorized_project(project_id, user, db, require_write=False)
    plant_res = await db.execute(
        select(HydroPlant).where(
            HydroPlant.id == plant_id, HydroPlant.project_id == project_id
        )
    )
    if plant_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usina não encontrada.")

    res = await db.execute(
        select(InflowSeries)
        .where(InflowSeries.hydro_plant_id == plant_id)
        .order_by(InflowSeries.year, InflowSeries.month)
    )
    return [InflowPointResponse.model_validate(r) for r in res.scalars().all()]


@router.post("/{plant_id}/inflows/upload", response_model=InflowUploadResponse)
async def upload_inflows(
    project_id: str,
    plant_id: str,
    file: UploadFile = File(...),
    is_incremental: bool = Form(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InflowUploadResponse:
    await get_authorized_project(project_id, user, db, require_write=True)
    plant_res = await db.execute(
        select(HydroPlant).where(
            HydroPlant.id == plant_id, HydroPlant.project_id == project_id
        )
    )
    if plant_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usina não encontrada.")

    content = await file.read(MAX_INFLOW_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_INFLOW_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo excede o limite máximo de 5 MB.",
        )

    try:
        parsed = await run_in_threadpool(
            parse_inflow_file, content, file.filename or "vazoes.txt"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # Replace existing series for this plant (deduplicate by year, month)
    dedup: dict[tuple[int, int], float] = {}
    for row in parsed:
        dedup[(row.year, row.month)] = row.flow_m3s

    await db.execute(
        delete(InflowSeries).where(InflowSeries.hydro_plant_id == plant_id)
    )
    db.add_all(
        [
            InflowSeries(
                hydro_plant_id=plant_id,
                year=y,
                month=m,
                flow_m3s=q,
                is_incremental=is_incremental,
            )
            for (y, m), q in sorted(dedup.items())
        ]
    )
    await db.commit()

    years = [y for y, _ in dedup.keys()]
    return InflowUploadResponse(
        hydro_plant_id=plant_id,
        records_imported=len(dedup),
        is_incremental=is_incremental,
        start_year=min(years),
        end_year=max(years),
    )
