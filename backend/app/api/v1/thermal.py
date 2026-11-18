"""Thermal plants CRUD and Heat Rate variable cost calculator."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authorized_project, get_current_user
from app.db.models import ThermalPlant, User
from app.db.session import get_db
from app.engine import calculate_fuel_cost_from_heat_rate
from app.schemas.schemas import (
    HeatRateCalcRequest,
    HeatRateCalcResponse,
    ThermalPlantCreate,
    ThermalPlantResponse,
    ThermalPlantUpdate,
)

router = APIRouter(tags=["thermal"])


@router.post("/tools/heat-rate", response_model=HeatRateCalcResponse)
async def calculate_heat_rate_endpoint(
    payload: HeatRateCalcRequest,
    _user: User = Depends(get_current_user),
) -> HeatRateCalcResponse:
    try:
        cost = calculate_fuel_cost_from_heat_rate(
            heat_rate_kcal_mwh=payload.heat_rate_kcal_mwh,
            fuel_price_usd_unit=payload.fuel_price_usd_unit,
            pci_kcal_unit=payload.pci_kcal_unit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return HeatRateCalcResponse(variable_cost_usd_mwh=round(cost, 4))


@router.get("/projects/{project_id}/thermal-plants", response_model=list[ThermalPlantResponse])
async def list_thermal_plants(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ThermalPlantResponse]:
    await get_authorized_project(project_id, user, db, require_write=False)
    res = await db.execute(
        select(ThermalPlant)
        .where(ThermalPlant.project_id == project_id)
        .order_by(ThermalPlant.variable_cost_usd_mwh)
    )
    return [ThermalPlantResponse.model_validate(t) for t in res.scalars().all()]


@router.post(
    "/projects/{project_id}/thermal-plants",
    response_model=ThermalPlantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_thermal_plant(
    project_id: str,
    payload: ThermalPlantCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThermalPlantResponse:
    await get_authorized_project(project_id, user, db, require_write=True)
    plant = ThermalPlant(
        project_id=project_id,
        name=payload.name.strip(),
        fuel_type=payload.fuel_type,
        installed_power_mw=payload.installed_power_mw,
        fc_max=payload.fc_max,
        fc_min=payload.fc_min,
        fixed_cost_usd_kw=payload.fixed_cost_usd_kw,
        variable_cost_usd_mwh=payload.variable_cost_usd_mwh,
        useful_life_years=payload.useful_life_years,
        guide_curve=payload.guide_curve,
        enabled=payload.enabled,
    )
    db.add(plant)
    await db.commit()
    await db.refresh(plant)
    return ThermalPlantResponse.model_validate(plant)


@router.patch(
    "/projects/{project_id}/thermal-plants/{plant_id}",
    response_model=ThermalPlantResponse,
)
async def update_thermal_plant(
    project_id: str,
    plant_id: str,
    payload: ThermalPlantUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThermalPlantResponse:
    await get_authorized_project(project_id, user, db, require_write=True)
    res = await db.execute(
        select(ThermalPlant).where(
            ThermalPlant.id == plant_id, ThermalPlant.project_id == project_id
        )
    )
    plant = res.scalar_one_or_none()
    if plant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usina térmica não encontrada.")

    for key, val in payload.model_dump(exclude_unset=True).items():
        if key == "name" and val is not None:
            setattr(plant, key, val.strip())
        else:
            setattr(plant, key, val)

    await db.commit()
    await db.refresh(plant)
    return ThermalPlantResponse.model_validate(plant)


@router.delete(
    "/projects/{project_id}/thermal-plants/{plant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_thermal_plant(
    project_id: str,
    plant_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await get_authorized_project(project_id, user, db, require_write=True)
    res = await db.execute(
        select(ThermalPlant).where(
            ThermalPlant.id == plant_id, ThermalPlant.project_id == project_id
        )
    )
    plant = res.scalar_one_or_none()
    if plant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usina térmica não encontrada.")

    await db.delete(plant)
    await db.commit()
